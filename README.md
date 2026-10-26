# The Price of Persistence — reconstructed custom code

**Retrospective implementation, created October 26, 2026. This is not the original code used to produce the paper's observations.** It was written with AI assistance from the author's Methods description, while the historical implementation awaits verification. The examples are synthetic and establish no study findings.

This package implements the described regex refusal detector, persistent switching of **subsequent requests** to a configured fallback model, transcript/event recording, and queued researcher notifications. It also records approval requests and supports a persistent researcher stop.

## Run the offline demonstration

Python 3.10+; no runtime dependencies or API account needed. From the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m persistence_router.cli replay \
  --config examples/config.json --fixture examples/synthetic-turns.json \
  --run-dir runs/demo
```

Use a fresh directory for each independent replay. The first synthetic response refuses; the second request uses the fallback. The refused request is **not retried**. Routing remains on the fallback until a new run is created. Refusals on the fallback do not loop or generate repeated switch notifications.

Outputs:

| File | Contents |
|---|---|
| `state.json` | Agent identity, configuration hash, active model, switch count, stop state |
| `events.jsonl` | Timestamped requests/responses, requested and provider-reported models, refusal matches, approval requests, interventions and errors |
| `notifications.jsonl` | Pending model-switch notifications |
| `notifications-sent.jsonl` | IDs of notifications delivered by the optional email command |

Logs contain the submitted messages and provider-visible responses, including any tool-call fields supplied. They do not recover hidden reasoning. API authorization headers are not logged. Messages and responses can themselves contain sensitive information: local run files are excluded from Git and need review before release.

## Use a model endpoint

Copy `examples/config.json` to an ignored run directory, select actual provider-supported primary/fallback identifiers, and set `endpoint` to a full chat-completions-compatible endpoint. Both models must be available through that endpoint. The paper's identifier `kimi-k3.1-pro` is reported in the provenance notes; it is **not validated or hardcoded** here.

```sh
mkdir -p runs/live
cp examples/config.json runs/live/config.json
# Edit agent_id, primary_model, fallback_model and endpoint in runs/live/config.json.
# Supply MODEL_API_KEY through your shell environment if the endpoint requires it.
PYTHONPATH=src python -m persistence_router.cli live \
  --config runs/live/config.json --messages examples/messages.json \
  --run-dir runs/live/state --max-tokens 512
```

Each `live` invocation makes one non-streaming API request and may incur provider costs. HTTPS is required except for loopback HTTP proxies. Redirects are refused. No real API requests were needed for the offline demonstration or tests. This repository neither provisions subscriptions nor implements a provider authentication proxy.

The caller owns conversation history: include the prior responses and tool results in the next messages array. The router preserves those fields but does not construct missing history or execute tools. `Router.complete(...)` is the integration boundary for an agent harness. See [integration details](docs/INTEGRATION.md).

## Notifications and interventions

Preview queued notifications without sending:

```sh
PYTHONPATH=src python -m persistence_router.notify --run-dir runs/demo
```

Optional email delivery requires `SMTP_HOST`, `SMTP_FROM`, and `RESEARCHER_EMAIL`, plus `SMTP_USER`/`SMTP_PASSWORD` if required; `SMTP_PORT` defaults to 465. Append `--send` to deliver via SMTP over TLS. Notifications contain switch metadata, not transcripts. Email delivery is separate from routing so an SMTP failure cannot undo a model switch. Delivery is at-least-once: a crash after SMTP acceptance but before recording delivery can cause a duplicate. Use a single sender process.

Stop subsequent calls for a run:

```sh
PYTHONPATH=src python -m persistence_router.cli stop \
  --config examples/config.json --run-dir runs/demo \
  --reason 'Researcher ended the run'
```

A stop blocks future calls through this router; it does not cancel an already in-flight request, stop an external harness, or revoke external credentials. One process must own each run directory; concurrent writers and streaming are unsupported.

## Fidelity to the paper

See [provenance and deviations](docs/PROVENANCE.md), [domain inventory](docs/DOMAINS.md), and [integration](docs/INTEGRATION.md).

The original regexes, exact prompts, framework versions, model mappings, and timestamped logs were not available for this reconstruction. Approval detection records a review-needed event; it does **not** implement the draft's blanket automatic-approval behavior. No autonomous business deployment, outreach, payments, third-party interaction, or competitor-disruption code is included. Native OpenClaw/Grokbot/Hermes/IronClaw adapters are not implemented.

The included code does not reproduce empirical pricing results or establish collusion. The test suite checks routing behavior with synthetic responses. Provider integration, real email delivery, and equivalence to the historical experiment still need validation.

## Suggested paper disclosure

> The accompanying repository contains an AI-assisted retrospective reconstruction of the custom routing and logging components described in Methods. It is not the exact implementation used during the reported runs and has not been validated against the historical source or logs. Included demonstrations use synthetic responses.

No open-source license has been selected. Public visibility alone would not grant a reuse license.
