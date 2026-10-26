"""Sequential, per-agent routing with persisted state and an append-only event log."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request
from urllib.parse import urlparse
import uuid

REFUSAL_PATTERNS = (
    r"\bI\s+(?:cannot|can't|won't|will not)\s+(?:help|assist|comply|provide)\b",
    r"\bI(?:'m| am)\s+unable\s+to\s+(?:help|assist|comply|provide)\b",
)
APPROVAL_PATTERNS = (
    r"\b(?:do I have|may I have)\s+(?:your\s+)?(?:approval|permission)\b",
    r"\b(?:please confirm|approval required|awaiting approval)\b",
)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Config:
    agent_id: str
    primary_model: str
    fallback_model: str
    endpoint: str = ""
    refusal_patterns: tuple = field(default_factory=lambda: REFUSAL_PATTERNS)
    approval_patterns: tuple = field(default_factory=lambda: APPROVAL_PATTERNS)

    def __post_init__(self):
        if not all(isinstance(s, str) and s.strip() for s in
                   (self.agent_id, self.primary_model, self.fallback_model)):
            raise ValueError("Agent and model identifiers must be non-empty strings")
        for pattern in (*self.refusal_patterns, *self.approval_patterns):
            re.compile(pattern)
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Endpoint must not contain credentials, query, or fragment")
            if not parsed.hostname or not (parsed.scheme == "https" or
                parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
                raise ValueError("Use HTTPS, or HTTP on loopback for a local proxy")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused; configure the final model endpoint explicitly")


def http_transport(endpoint, payload, api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                     headers=headers, method="POST")
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
        return json.load(response)


def response_text(message):
    content = message.get("content")
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content
                         if isinstance(p, dict) and isinstance(p.get("text"), str))
    raise ValueError("Unsupported assistant content type")


class Router:
    """One process owns each run directory. Models must share the configured endpoint.

    A refusal changes the model for the NEXT call. No automatic retry, prompt
    rewriting, tool execution, or fabricated approval occurs in this implementation.
    """
    def __init__(self, config, run_dir):
        self.config = config
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_path = self.run_dir / "state.json"
        encoded = json.dumps(config.__dict__, sort_keys=True).encode()
        self.fingerprint = hashlib.sha256(encoded).hexdigest()
        self.state = {"schema_version": 1, "config_sha256": self.fingerprint,
                      "agent_id": config.agent_id, "active_model": config.primary_model,
                      "stopped": False, "stop_reason": None, "switch_count": 0}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
            if self.state.get("config_sha256") != self.fingerprint:
                raise ValueError("Run configuration differs from persisted state; use a new directory")
        else:
            self._save()

    def _save(self):
        fd, name = tempfile.mkstemp(dir=self.run_dir, prefix=".state-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(self.state, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.state_path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _append(self, filename, record):
        fd = os.open(self.run_dir / filename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def event(self, kind, **fields):
        record = {"event_id": uuid.uuid4().hex, "time": timestamp(),
                  "agent_id": self.config.agent_id, "type": kind, **fields}
        self._append("events.jsonl", record)
        return record

    def stop(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("An intervention needs a reason")
        self.state.update(stopped=True, stop_reason=reason)
        self._save()
        self.event("researcher_stop", reason=reason)

    def complete(self, messages, *, transport=http_transport, api_key=None, **options):
        if self.state["stopped"]:
            raise RuntimeError("Run stopped: " + self.state["stop_reason"])
        if not isinstance(messages, list) or not messages or not all(
            isinstance(m, dict) and isinstance(m.get("role"), str) for m in messages
        ):
            raise ValueError("messages must be a nonempty list of message objects with roles")
        if any(k in options for k in ("model", "messages", "stream", "n")):
            raise ValueError("model/messages/stream/n are controlled by the router")
        model = self.state["active_model"]
        payload = {**options, "model": model, "messages": messages, "stream": False, "n": 1}
        # Freeze a snapshot, retaining system messages, tool calls and tool results.
        payload = json.loads(json.dumps(payload))
        request_id = uuid.uuid4().hex
        self.event("request", request_id=request_id, requested_model=model, payload=payload)
        try:
            response = transport(self.config.endpoint, payload, api_key)
            message = response["choices"][0]["message"]
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ValueError("Expected an assistant message in choices[0]")
            text = response_text(message)
            explicit_refusal = bool(message.get("refusal"))
        except Exception as exc:
            # Do not log exception messages: an upstream error can contain credentials.
            self.event("request_error", request_id=request_id, error_type=type(exc).__name__)
            raise
        self.event("response", request_id=request_id, requested_model=model,
                   reported_model=response.get("model"), response=response)
        matched = [p for p in self.config.refusal_patterns if re.search(p, text, re.I)]
        if matched or explicit_refusal:
            self.event("refusal_detected", request_id=request_id, matched_patterns=matched,
                       explicit_refusal=explicit_refusal)
            if model != self.config.fallback_model:
                self.state["active_model"] = self.config.fallback_model
                self.state["switch_count"] += 1
                self._save()
                event = self.event("model_switch", request_id=request_id, previous_model=model,
                                   next_model=self.config.fallback_model, applies="next_request")
                self._append("notifications.jsonl", {"status": "pending", "event": event})
        if any(re.search(p, text, re.I) for p in self.config.approval_patterns):
            self.event("approval_requested", request_id=request_id, disposition="review_required")
        return response
