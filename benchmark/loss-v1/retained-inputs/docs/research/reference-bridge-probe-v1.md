# Reference continuation across the complete bridge interface: probe v1

Prepared **24 October 2026 before bridge execution**. This is a bounded source-backed development probe using the disclosed Carol A2A 1.0 port. The [original application](reference-continuation-results-v0.md) and [version-matched native controls](reference-port-native-results-v1.md) have recorded positive and near-miss trajectories. The port remains an authored adaptation; this probe cannot establish an unchanged external application's natural failure prevalence or C1 novelty. Keep the original title, full study objective, two eligible bridges and human-review gates.

## Frozen inputs and paths

Use port `scripts/fixtures/carol-reference-v1.mjs`, SHA-256 `b6b6492ee5c27cf5db0474054b0f18a8feafe0859d9faaa4fd67946c7768626d`, and its recorded source/change map. Pin AmirK-S `58eff9da469bccdc432bf164662727947de646b4` and mgcrea `c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5` with their existing locks. Do not modify either bridge, SDK or original source. Snapshot the exact spec, driver, logger, port, configuration and dependency/source ledger before startup. Preserve unsuccessful setup/run attempts and make a new version before any corrective source change or repeat.

Use separate fresh port/bridge processes and task bindings for **four variants, one attempt per variant**. All variants start with the same typed initial send and an authoritative ordinary task read, supplying the actual public task/context receipt. Initial text is `{"action":"shuffle","history":[{"guess":25,"response":"Go higher"}]}` and answer text is exactly `Well done!`. The history limit is 10 everywhere: Amir `historyLength`, mgcrea typed `history_length`, native raw `historyLength`. A single history item removes irrelevant permutation variability.

| Variant | Pinned MCP profile | Continuation and final read | Source-based expectation to test |
| --- | --- | --- | --- |
| R1: Amir ordinary | HTTP, MCP 2026-07-28, ordinary client without Tasks declaration | `a2a_send_message` with original task/context handles, then ordinary `a2a_get_task` | Ordinary serializer sends no references; the original task is expected to remain waiting. |
| R2: Amir modern Tasks | HTTP, MCP 2026-07-28, actual per-request Tasks extension declaration | Get the actual pending input request; submit `tasks/update` with its actual key/form field and the fixed answer; read `tasks/get` and ordinary `a2a_get_task` | The answer path uses the same empty-reference native serializer; logical task is expected to remain waiting. |
| R3: mgcrea typed | stdio, negotiated MCP 2025-11-25, writes enabled | `a2a_send_message` with public original task/context IDs, then `a2a_get_task(refresh:true)` | Ordinary serializer sends no references; the original task is expected to remain waiting. |
| R4: mgcrea raw alternative | Same stdio/profile/mutation settings and typed pending prefix as R3 | `a2a_request(SendMessage)` with public original task/context and `referenceTaskIds=[original ID]`; `a2a_request(GetTask)` for the original ID | Existing documented raw action can express the required field; original task/context is expected to complete. |

Expectations are prospective source-based hypotheses, **not conditions for recording an execution as successful**. Record actual valid replies and all errors even if the expected contrast fails. A contradictory result falsifies a source/model assumption; do not relabel or retry it into agreement. Native port completion is already a separate control, not a fifth converter.

R4 does not execute a doomed typed follow-up first. Every strong practical comparator can choose the raw action directly from the identical allowed contract and public pending receipt. Raw `SendMessage` is a **task action**, not an observation-query saving. Tool/profile discovery, initial sends/reads, card fetches, final reads, setup, bytes and logging overhead are all retained. There is no candidate performance comparison or live model experiment here.

## Whole-interface and protocol semantics

Amir's four ordinary tools and exposed modern Tasks handlers are both relevant. Its source creates an answer form even when a task's status message is absent, using a state-text fallback; absence of a question string is not evidence that Tasks continuation is unavailable. Use the returned input-request key and schema rather than inventing them. An outer modern `completed` means result delivery; only a disclosed ordinary/native completed task with the original association establishes the logical goal.

mgcrea's write-enabled raw `SendMessage` is part of the full declared interface. Typed-path loss cannot be called whole-route non-support while that alternative is permitted. Its raw tool returns native JSON-RPC inside MCP text content; an inner native error is still an error even when the outer tool is not marked `isError`. Raw SendMessage's result contains `task`; raw GetTask's result is the task object. Keep both nested correlation namespaces. Raw RPC does not add `A2A-Version`; capture its actual header absence and the port's declared/default 1.0 semantics instead of synthesizing a header.

For mgcrea use isolated state/configuration with writes=1, channel=0, retries=0 and no token. A local `refresh:false` mirror cannot replace the required authoritative pending/final reads; it may be preserved as a separately labelled diagnostic, with all added requests charged. This protocol probe does not assert receiving-principal authorization, leases or cross-peer completion prerequisites.

## Recording and bounded execution

Use new exclusive directories under `runs/reference-bridge-observation/`, separate from older artifact-goal captures. Retain `runtime-wire-observation/1` with paired exact raw MCP exchanges, parsed JSON, response SHA-256, UTC intervals, unique request/exchange IDs, route/commit/profile and `variant_id`. Add a pre-execution source/spec snapshot ledger, actual status-only contract, process lifecycle and costs. No raw record is overwritten.

The public trace must contain only MCP-visible inputs/replies plus ordinary source/profile metadata. Native HTTP is an explicitly separate evaluator-private sidecar. A native ID already returned through MCP is public; a sidecar-only ID must not be supplied to any arm or projector. In particular R4 learns native task/context IDs from the public mgcrea receipt, while opaque Amir handles remain in their own namespace.

Use genuine bridge subprocess/HTTP/stdio and the official native port service. Read-only native fetch logging may stamp/hash/clone bodies; it must not alter requests, add correlation headers or replace transport semantics. Disclosure includes instrumentation overhead and response-body logging that can finish after an MCP acknowledgement. Preserve exact child PIDs, request/server ownership, specific close/exit results and diagnostics. No broad process kill is permitted.

Startup/request limit is 10 seconds. Initial pending observation may poll for at most five seconds with a disclosed 50-ms interval; all polls remain in the trace and cost ledger. After the fixed answer, read the actual final state rather than waiting indefinitely to force a desired outcome. Additional asynchronous observations, if needed to clarify an in-flight response, must be explicit and bounded by the same five-second budget. No private future schedule or hypothetical expiry is supplied. A get observes advancement, rather than causing it.

## Historical status/association projection contract

Implement a new pure `project_status_trace(trace)` returning `observed-status-trace-projection/1` with `source_trace_sha256`, `config.goal="logical-completion-and-original-association"`, `analysis_clock`, `initial_exchange_id`, `events` and a finite v1 `manifest`. It reads no private sidecar, filesystem, source program or future schedule. A separate pure `check_status_projection(trace, projection)` independently checks its claims, without importing projector extraction/solver logic. Native correlation is a separate explicit `check_status_native_sidecar(trace, records)` input boundary.

The first complete ordinary public task/context view establishes original references. Raw mgcrea views preserve public native `id/contextId`; shaped views use `id/context_id`; Amir uses opaque `taskHandle/contextHandle`. Do not normalize different executions or namespaces into shared aliases. Missing response references remain unknown; the request target does not supply a missing returned context. A task update acknowledgement does not invent successful task status.

Any earlier nonempty public task reference must agree with that complete prefix, including a modern Tasks creation ID. Earlier nonempty public context references must also agree. A missing/empty context can be learned later for the same task; it does not permit substituting another task when the context arrives. Reject a conflicting prefix as an unmodelled multi-task trace. This clarifies original association before executing the probe.

The finite goal is exactly logical `status == completed`, returned task equal to original task, and returned context equal to original context. Invariants require the correct task namespace and valid original request target. **No artifact predicate is present.** Do not reuse the previous artifact-goal result with a substituted expected string. Raw native `TASK_STATE_*` statuses have explicit pinned logical mappings; outer modern Tasks completion alone does not satisfy the goal.

Include every selected task read/action from that prefix, including raw SendMessage/GetTask. Each state is a real paired response and each edge the next recorded observational macrostep. Task cancellation, unsupported mutations, missing/unpaired/error replies or unmodelled native errors require a separately declared recovery model; reject projection rather than silently removing the action. Read-only setup remains in complete source/cost records. Validate raw/parsed/hash agreement, duplicate-free JSON, paired IDs and serial intervals across the entire trace, including setup.

All trace-derived manifests have `evidence.complete=False` and a zero-width fixed archival analysis clock after the last response. A recorded completed path may yield historical supported with a checked certificate. A waiting-only path yields unknown, **not unsupported**, because unobserved continuations remain unknown. Later-clock replay abstains. A separate source-derived, complete bounded action abstraction would be needed for a prospective non-support argument; this probe does not provide one automatically.

## Decision boundary

Do not interpret a documented typed omission or successful raw alternative as a new algorithm. Exact reachability/guard analysis with the same permitted actions already handles the present example. The probe strengthens real-route/source fidelity and may identify a concrete diagnostic problem; it does not pass C1's novel-method condition, waive human review or revive the rejected 192-episode efficiency pilot. Preserve all adverse findings. CP2 remains open and progress remains 5% until all mandatory evidence gates pass.
