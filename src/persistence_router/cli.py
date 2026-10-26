"""Offline replay by default; network access requires the explicit live command."""
import argparse
import json
import os
from pathlib import Path
from .router import Config, Router


def load_config(path):
    return Config(**json.loads(Path(path).read_text()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("replay", "live", "stop"):
        p = sub.add_parser(command)
        p.add_argument("--config", required=True)
        p.add_argument("--run-dir", required=True)
        if command == "replay":
            p.add_argument("--fixture", required=True)
        elif command == "live":
            p.add_argument("--messages", required=True, help="JSON array of chat messages")
            p.add_argument("--max-tokens", type=int, default=512)
        else:
            p.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.command == "live" and (not config.endpoint or args.max_tokens <= 0):
            raise ValueError("Live calls require an endpoint and a positive max-tokens value")
        router = Router(config, args.run_dir)
        if args.command == "stop":
            router.stop(args.reason)
            print("Run stopped")
        elif args.command == "replay":
            fixture = json.loads(Path(args.fixture).read_text())
            for turn in fixture:
                response = turn["response"]
                router.complete(turn["messages"], transport=lambda *a, r=response: r)
            print(json.dumps({"synthetic_replay": True, "turns": len(fixture), "state": router.state}))
        else:
            messages = json.loads(Path(args.messages).read_text())
            response = router.complete(messages, api_key=os.environ.get("MODEL_API_KEY"),
                                       max_tokens=args.max_tokens)
            print(json.dumps(response, ensure_ascii=False))
    except (OSError, ValueError, KeyError, IndexError, RuntimeError) as exc:
        # Exceptions from network libraries may carry request or response details.
        parser.exit(1, f"Operation failed ({type(exc).__name__}); inspect local events.jsonl.\n")


if __name__ == "__main__":
    main()
