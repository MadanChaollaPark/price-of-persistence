# Agent harness integration

Install locally with `python -m pip install -e .` or use `PYTHONPATH=src`. Invoke the router where your harness would normally call its model endpoint:

```python
import os
from persistence_router import Config, Router

router = Router(
    Config(
        agent_id="agent-01",
        primary_model="YOUR_PRIMARY_MODEL",
        fallback_model="YOUR_FALLBACK_MODEL",
        endpoint="http://127.0.0.1:8317/v1/chat/completions",
    ),
    "runs/agent-01",
)
messages = [{"role": "user", "content": "Say hello."}]
result = router.complete(messages, api_key=os.environ.get("MODEL_API_KEY"), max_tokens=512)
messages.append(result["choices"][0]["message"])
```

This is an illustrative adapter boundary, not a tested integration with any named framework. The endpoint is illustrative and is not contacted unless you run the code. The surrounding harness must supply the complete subsequent message history and execute any authorized tools itself. Tool definitions may be passed as `tools=...`; they are forwarded unchanged. Calls producing tool requests return those requests without executing them.

Use a different directory and agent ID for each experimental instance. A configuration change requires a fresh run directory. Resume reconstructs routing/stop state; it does not reconstruct the caller's conversation from logs. Preserve your conversation separately or explicitly recover it from audited events.

The regex detector examines assistant-visible text, not user prompts or tool arguments. It uses the first choice only; the router explicitly requests `n=1`. No retry is made on transport failures. Call errors leave the routing state unchanged.

Single-writer scope is deliberate: state replacement is atomic, but state and JSONL logs are not one transaction. A process or machine crash between a saved switch and its notification can leave incomplete audit/notification records. Check these records after interrupted processes; this is a research implementation, not a fault-tolerant distributed scheduler.

Exact condition prompts are absent from the available draft, so no invented “original prompts” are supplied. The synthetic test fixture is only a routing example. A valid replication additionally needs original prompts, versions, model IDs, observation windows, pricing records, intervention evidence and the historical code.
