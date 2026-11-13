# Native A2A 1.0 port preservation probe v1

Prepared **24 October 2026 before execution**. This is a separate, bounded development check of the [authored Carol port](../../scripts/fixtures/carol-reference-v1.mjs), following the unchanged original A2A 0.3 [probe](reference-continuation-probe-v0.md) and [independent verification](../../runs/native-reference-continuation/verification-v1.json). It runs no MCP bridge and supplies no new-method, natural-defect or efficiency claim. Preserve the earlier prospective spec and raw runs unchanged. CP2 and human novelty review remain open.

## Frozen scope and source

Use port SHA-256 `b6b6492ee5c27cf5db0474054b0f18a8feafe0859d9faaa4fd67946c7768626d`, the [change map](source-evidence/reference-continuation/port/change-map.json), [attribution](source-evidence/reference-continuation/port/ATTRIBUTION.md), existing official JS SDK `@a2a-js/sdk==1.1.0` and its AmirK-S checkout/lock pin recorded in `external/source-lock.json`. Capture actual SDK/Node versions, dependency-lock hash, source/change-map/spec hashes and exact driver/port copies before starting the service. If a source change is necessary, preserve the failed attempt and make a new dated source/spec version before rerunning. Do not modify a bridge, its SDK or the original Python example.

The port uses the official `AgentExecutor`, `DefaultRequestHandler`, `InMemoryTaskStore` and JSON-RPC transport. It preserves the tested nonempty-reference dispatch, fixed `well done` completion, no-reference initial/input-required behavior and original global history list. Modern card/binding/events, language serialization and RNG differ; the change map states these differences. The one-entry input is invariant to permutations. This probe checks the declared control fragment, not whole-program or arbitrary-input equivalence with the original sample.

Use a native official SDK client with logged loopback HTTP, negotiated **A2A 1.0** JSON-RPC `SendMessage`/`GetTask` and the advertised card/interface. Source-level SDK objects and actual protobuf JSON wire bodies have different enum/part representations; save both rather than equating their raw shapes. No model, credentials, multi-principal authority or invented freshness lease is involved.

## Controls and runtime goal

Start one isolated port service, obtain its actual Agent Card, then create separate tasks for these three controls in order. Each initial text encodes `{"action":"shuffle","history":[{"guess":25,"response":"Go higher"}]}`. Each answer is exactly `Well done!`. Observe an actual input-required task receipt before answering; use only its public native task/context IDs. No evaluator-private sidecar or future state is supplied to the client.

| Control | Native message | Prospective source-based check |
| --- | --- | --- |
| P1 | Original task/context and `referenceTaskIds=[original ID]` | Answer and subsequent GetTask show the original task/context completed. |
| P2 | Original task/context and empty references; identical answer | Answer and subsequent original-task GetTask remain input-required with original IDs. |
| P3 | Original context, no task ID and empty references; identical answer | Record whether SDK accepts it and which task/context it returns. If a different task is created, get both it and the original, preserving their distinct IDs and states. Rejection is a retained outcome. |

The goal is logical task completion and **the original association**, not delivery of a new terminal artifact. Acknowledgements alone are insufficient. P2/P3 are deliberate authored near-miss controls; they do not measure natural failure prevalence. Source references are only a nonempty dispatch guard; the port adds no reference-ID equality check.

One native attempt per listed control follows successful setup. Log every discovery/send/get attempt and error. Use a 10-second startup/request limit and at most five seconds to observe an initial required state, with a disclosed 50-ms polling interval; actual extra polls/timeouts stay in the record. No private completion schedule is known. A get observes state advancement and does not itself cause it. These development bounds have no efficiency or service-lease interpretation.

## Recording and interpretation

Use a unique driver and immutable output directory under `runs/reference-port-native/`, separate from the original A2A 0.3 attempts. Record setup failures as well as execution failures, exact UTF-8 request/reply bodies and hashes, JSON-RPC correlation IDs, timestamps, public/native namespace, caller input, task/context/status/artifacts, actual body-byte/request counts and the complete source/environment ledger. Do not replace a failed attempt with a favorable repeat.

Record exact process IDs or same-process server ownership and actual close/exit outcome. Close the specific local server/child and wait for completion; do not kill unrelated processes. Capture failure outcomes even when startup/cleanup fails. Exclude no request from cost accounting; report dependency/setup time separately. No inference or remote post is authorized or needed.

Root will independently check source hashes, actual raw correspondence, task/context preservation and the observed P1/P2/P3 contrast. A successful run would establish this port's tested native 1.0 control behavior, not current MCP-bridge behavior or future task admission. A failed contrast falsifies the preservation/SDK assumption and stops bridge expansion until diagnosed.

No bridge captures begin before a separate whole-interface action/projection/check contract is frozen. That later comparison must permit mgcrea's write-enabled raw SendMessage/GetTask alternative equally to all practical arms, distinguish modern MCP result delivery from native task success, and avoid applying the old text-artifact projector to this status-only goal. Exact reachability given the same guards/actions already expresses the present example; a passing native port cannot establish C1 novelty or pass CP2.
