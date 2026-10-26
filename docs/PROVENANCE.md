# Provenance and reconstruction decisions

Created October 26, 2026, at the author's request, from the supplied draft of **The Price of Persistence: Investigating Tacit Collusion Among Autonomous Business Agents**. The author explicitly requested newly written code while checking the historical implementation. Original source and transcripts were not imported. This repository is not evidence of what ran during the study.

| Draft description | Reconstruction | Unresolved detail or deviation |
|---|---|---|
| Regex keyword refusal detection | Configurable English regex patterns plus provider `refusal` field | Patterns are newly selected, not recovered. Quoted refusals can false-trigger; other languages and paraphrases can be missed. |
| Route next requests to `kimi-k3.1-pro` | Sticky per-agent fallback beginning with the next call | Default model IDs are explicit placeholders. The paper's identifier and provider availability are unverified. No immediate retry. |
| Email researcher on switch | Durable notification queue and explicit SMTP delivery command | Recipient and transport were unspecified. Actual delivery not tested. |
| Record prompts and internal dialogues when possible | Request/response and tool-field logs | Only provider-visible content is recorded. Hidden reasoning is not available. |
| Script responds to requests for approval | Detect and record approval requests | Blanket automatic approval is not reproduced. Harness authorization stays outside this router. |
| Researcher stops agent | Persisted stop with reason | Only future router calls are blocked; stopping external processes is the operator's responsibility. |
| Four frameworks, two conditions, paired domains | Domain inventory and integration guidance | No native framework adapters, framework versions, verified model assignments, or exact original prompts. |

New engineering choices include atomic state-file replacement, explicit request/response correlation IDs, configuration fingerprint checks on resume, a 60-second request timeout, non-streaming single-choice responses, and offline replay fixtures. These are implementation choices, not historical study facts.

The draft inconsistently reports market assignments and reasons for interrupted runs. This package does not resolve those contradictions or encode them as measurements. It supplies no pricing results, fabricated transcripts, or inferred run timestamps.

The historical approval script, source, and logs can be added later with separate provenance and a comparison against this reconstruction. Preserve this version as a distinct tagged reconstruction.
