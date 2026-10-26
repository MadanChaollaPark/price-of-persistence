"""Explicit delivery of queued model-switch notifications through SMTP."""
import argparse
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--send", action="store_true", help="Actually send; default previews event metadata")
    args = parser.parse_args()
    path = Path(args.run_dir)
    queue = path / "notifications.jsonl"
    sent_path = path / "notifications-sent.jsonl"
    records = [json.loads(x) for x in queue.read_text().splitlines()] if queue.exists() else []
    sent = {json.loads(x)["event_id"] for x in sent_path.read_text().splitlines()} if sent_path.exists() else set()
    for record in records:
        event = record["event"]
        if event["event_id"] in sent:
            continue
        if not args.send:
            print(json.dumps(event))
            continue
        message = EmailMessage()
        message["From"] = os.environ["SMTP_FROM"]
        message["To"] = os.environ["RESEARCHER_EMAIL"]
        message["Subject"] = "Study router: model switch"
        message["Message-ID"] = "<" + event["event_id"] + "@persistence-router.invalid>"
        message.set_content(json.dumps(event, indent=2))
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465")),
                              context=ssl.create_default_context(), timeout=30) as smtp:
            if os.environ.get("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            refused = smtp.send_message(message)
            if refused:
                raise RuntimeError("Notification recipient rejected")
        fd = os.open(sent_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(json.dumps({"event_id": event["event_id"]}) + "\n")
        sent.add(event["event_id"])


if __name__ == "__main__":
    main()
