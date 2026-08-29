# Plant AI agent architecture

Status: Stage 2 orchestration, intake, memory, and evidence retrieval, 2026-08-29.

Plant AI now executes scans through a compiled LangGraph `StateGraph`. Nodes read
typed shared state and return partial updates; conditional edges decide which
tool or safety path runs next. This follows the official LangGraph graph model:

- [StateGraph reference](https://reference.langchain.com/python/langgraph/graph/state/StateGraph)
- [LangGraph conditional-edge guidance](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph fault-tolerance guidance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)

## Current graph

```text
START
  -> intake
  -> leaf_gate
       | rejected -----------------> finalize_rejection -> END
       | tool failure -------------> safe_failure ------> END
       | accepted
       v
     vision_models
       | tool failure -------------> safe_failure ------> END
       | low confidence + missing context
       v
     request_context -----------------------------------> END
       | accepted local result ----> finalize_local ----> END
       | uncertain/requested + no AI configured --------^
       | uncertain/requested + AI configured
       v
     ai_assessment (maximum two attempts)
       | success / attempts exhausted
       v
     evidence_retrieval
       | AI result ----------------> finalize_ai -------> END
       | local/fallback result ----> finalize_local ----> END
```

The graph is compiled once when the application starts. Existing inference code
is exposed through injected callbacks, so the graph orchestrates the same
OpenCLIP gate and all registered classifiers without duplicating model logic.

## Typed shared state

`TriageState` carries only bounded run-scoped data:

- validated image bytes and MIME type;
- caller context and whether AI assistance was requested;
- up to five plan-authorized, crop-matched history summaries;
- leaf decision and confidence;
- all local model candidates and selected prediction;
- optional structured AI diagnosis;
- approved crop-and-condition evidence with corpus provenance;
- final disposition and UI result;
- append-only recoverable errors; and
- append-only structured trace events.

Private history is retrieved before graph execution only for the current paid
account. It is bounded to five matching records and never copied into traces.
See [`CONTEXT_AND_MEMORY.md`](CONTEXT_AND_MEMORY.md) for the ownership and
retention contract.

## Node contracts

| Node | Responsibility | Safe output |
| --- | --- | --- |
| `intake` | Accept already validated image and available context. | Records an error if required input is absent. |
| `leaf_gate` | Call OpenCLIP before any disease model. | Rejects non-plants or routes tool failure to safe escalation. |
| `vision_models` | Run the original and every registered classifier, then crop-aware selection. | Routes model failure to safe escalation. |
| `request_context` | Pause a low-confidence result and identify only missing critical context. | Does not diagnose or consume a scan allowance. |
| `ai_assessment` | Request structured multimodal assessment only when configured and needed. | Tries at most twice, then falls back to the cautious local result. |
| `evidence_retrieval` | Match the final crop and condition against the versioned approved corpus. | Returns exact-scope cited actions or no management claim. |
| `verification` | Compare confidence, cross-model crop agreement, and evidence availability. | Adds a pending human checkpoint with explicit review reasons. |
| `finalize_rejection` | Stop without assigning a crop or disease. | User receives better-upload guidance. |
| `finalize_local` | Preserve local result, votes, threshold warning, and source. | Explicitly warns when AI is unavailable or retries fail. |
| `finalize_ai` | Convert validated AI fields into the existing result contract. | Keeps uncertainty and the local comparison visible. |
| `safe_failure` | Handle required-tool failure without inventing a diagnosis. | Returns `escalate_human_or_lab` and low-risk next steps. |

## Trace schema

Every node appends events with:

- `sequence`;
- `node`;
- `status`;
- a sanitized `detail` summary;
- `duration_ms`; and
- `attempt` when applicable.

Raw images, credentials, private history, and prompts are not copied into trace
events. Evaluation outputs pair the trace with a case content hash, normalized
result, configuration, and exact commit. That is enough to reconstruct the path
and inspect tool selection without publishing user data.

## Failure and retry policy

- Leaf/model failures are not treated as evidence about a disease. They route to
  a safe escalation report.
- Optional AI calls are bounded to two attempts within the `ai_assessment` node.
- Exhausted AI attempts retain the local evidence and add a warning; they do not
  fail the entire HTTP request.
- Graph recursion is capped at 12 steps.
- The original classifier and registered-model registry remain responsible for
  their own inference isolation.

No irreversible or consequential tool is present. Future pesticide-related or
external actions must use an explicit human approval node.

## Current boundaries

This stage provides orchestration, not the finished competition agent. The
following remain deliberately separate backlog items:

- committed representative trajectories for every agent (Issue #11).

The evaluation adapter disables the optional LLM and uses the versioned local
evidence corpus. This keeps model quality and external API cost isolated while
the evidence-specific v2 manifest scores claim provenance.
