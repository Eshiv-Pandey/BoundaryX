# Source-backed reference continuation: development probe v0

Prepared **24 October 2026 before execution of this probe**. This investigates a real application requirement that the earlier known-task text fixture did not exercise. It is authorized local feasibility work within the approved research objective, not a replacement contribution, confirmatory experiment, reported adapter defect or passed novelty gate. Model access is unnecessary. **CP1 remains 5%; C1 and CP2 remain open.**

## Why this probe is worth running

The [query feasibility audit](candidate-query-feasibility.md) rules out the current 20% observation saving on the one-bundle text fragment. Additional separate source reviews found no shared receiving-principal lease, arbitrary linked-file reader or enforced task DAG on the two pinned bridges. These cannot be invented to make temporal planning win.

An independent existing application supplies a different issue: the official [A2A number-guessing example's Carol agent](https://github.com/a2aproject/a2a-samples/blob/6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3/samples/python/agents/number_guessing_game/agent_Carol.py) dispatches a message to its follow-up handler only when `reference_task_ids` is nonempty. In that handler, text beginning with `well done` completes the task; otherwise it shuffles history and asks for more input. Its [follow-up wrapper](https://github.com/a2aproject/a2a-samples/blob/6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3/samples/python/agents/number_guessing_game/utils/protocol_wrappers.py) supplies both the original task association and a reference to that task. The task ID alone does not select the follow-up branch. These semantics were found in published source, not added by our harness.

Both pinned bridges' ordinary send serializers explicitly construct `referenceTaskIds: []`: AmirK-S `src/a2a-client.ts`, `buildUserMessage`; mgcrea `src/client/peer.ts`, `sendMessage`. mgcrea additionally exposes raw `a2a_request(SendMessage)` when writes are enabled, with arbitrary native params and an endpoint obtained from the peer's card (`src/tools/request.ts`, `src/client/peer.ts`, `rawRpc`). A typed-path limit must therefore not be described as a limit of mgcrea's entire available interface. AmirK-S's full tool/modern-Tasks surface also needs inspection before any whole-profile non-support conclusion.

This is **action construction**, not acquiring additional task evidence. Raw `SendMessage` is a task action with actual side effects, and every comparator may use the same permitted raw action. The method hypothesis is to analyze which application requirements remain realizable through the complete declared tool interface, separating a lossy typed path from an available alternative. No novel procedure has been identified: ordinary source-derived guard analysis, relational preimage, contract quotient and exact reachability already express the present example.

## Version and semantic boundaries

The exact sample pin is `6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3`, already referenced by AmirK-S's upstream sample script. Carol declares **A2A 0.3.0** and the example pins Python `a2a-sdk==0.3.0`. The two research bridges use **A2A 1.0**. The unchanged example is therefore not currently a demonstrated native-compatible application for either bridge.

[A2A 1.0 specification, sections 3.4.3 and 4.1.4](https://a2a-protocol.org/v1.0.0/specification/) distinguishes task association from optional task references for additional context. It does not require Carol's application-specific nonempty-reference dispatch. A failure on that application would not by itself establish protocol nonconformance. The source checks only that references are nonempty; it does not itself prove referential integrity or require the referenced ID to equal the associated ID. The actual wrapper supplies the original ID in both fields, which is the positive witness we will test.

First verify the **unchanged original** over its own native 0.3 runtime. Preserve original files, root license, exact installed dependency versions/hashes and every failed installation/startup/execution attempt. Do not silently edit its API binding or business logic to obtain native success.

Only after assessing that evidence may a separate, transparently documented 0.3-to-1.0 application port be used as a discriminating bridge probe. Such a port is an **authored adaptation of an external application**. Its wire results would characterize the pinned bridges on that adaptation, rather than establish a naturally observed production defect or an unchanged-sample result. Preserve the source dispatch guard, `well done` terminal behavior, initial input-required behavior and relevant task/context state; document all SDK/event/binding changes. Do not modify either bridge.

## Prospective native controls

Use separate newly created tasks with the same source-valid shuffle request and identical `Well done!` answer text. A one-entry history avoids irrelevant shuffle-order variation. Obtain each task's actual public task/context receipt before continuing it; no private/native sidecar-only identifiers or future answers enter an arm.

| Case | Follow-up association and references | Source-based expectation, to be tested |
| --- | --- | --- |
| N1: Original native positive | Original `task_id` and `context_id`; `reference_task_ids=[original task ID]` | Follow-up branch; the same task/context completes. |
| N2: Original native near miss | Same original `task_id`, `context_id` and answer; empty references | Initial branch; the same task remains input-required rather than completing. |
| N3: Association control | Original context only, empty references and the same answer, if accepted by the original SDK | Record exact new/existing task association and resulting state. Context alone must not be treated as proof of same-task continuation. Rejection is a retained outcome. |

This is one development attempt per listed case after successful setup. The cases are prospective source-based checks, not measured outcomes, population samples or an independent gold corpus. If any expectation is contradicted, retain the raw evidence and diagnose the source/runtime assumption before extending the probe. No favorable repeat may replace an unsuccessful attempt.

The local capture must store exact old-version native request/reply bytes, timestamps, correlation IDs, returned task/context/status/artifacts, actual task reads, source hashes, interpreter/dependency ledger and cleanup outcome. Record exact child PIDs and wait for their exits; do not broadly kill Node/Python processes. Requests that poll asynchronous state are observations, not causes of state advancement. Count all actual sends/gets/discovery and bytes. No model calls are required or authorized by this probe.

## Conditional version-matched bridge checks

These have **not begun**. Before executing them, freeze the port's source, complete exposed tool lists/protocols, mutation settings, runtime contract, reference trajectories and check procedures in a new record. Independent review must check preservation of the original application guard; AI source review does not meet the human novelty gate.

Required discriminating checks are a native 1.0 positive and empty-reference near miss, both ordinary typed bridge routes, AmirK-S modern `tasks/update` if the exposed pending form supports the same action, and mgcrea raw `SendMessage` with the native reference field. Retain the already working reference-indifferent text fixture as a positive control for ordinary continuation. Do not weaken the application goal to make a typed route succeed.

The supplied goal is completion of the **original task and context** after the fixed answer. A completed result-delivery envelope alone is insufficient; inspect the ordinary/native logical task result. Carol's terminal acknowledgement does not require a new completed artifact, so the existing text-artifact historical projector must not be reused with a substituted goal. Define and separately check a matching projection before interpreting any new trace. An observed waiting reply is not a universal proof that completion is impossible; a bounded negative requires the complete source-derived action fragment and declared permitted operations.

Every practical arm receives the identical allowed contract, source-derived profile, public task binding, history setting and raw-action eligibility. Compare the **whole allowed action interface**, including documented escape hatches, before claiming loss. A strong baseline can select the raw action directly. No arm is forced to make a doomed typed send first, and no private sidecar ID supplies its native raw parameters. Writes-disabled profiles remain separate documented controls and cannot be compared as if they had the same action set.

## Prior art and decision rules

[Lost in Translation](https://www.teleperson.com/resources/lost-in-translation-cross-protocol-interoperability), a May 2026 project white paper, already defines semantic bridge faithfulness and success-distinguishability separation (sections 5-6; Appendix 10.4). Its detectability proof additionally uses a target footprint identifying each lost feature (Appendix 10.5); an erasing interface does not automatically supply such a footprint. This does not establish a new theorem for our project.

[Ibrahim et al., AAAI 2017](https://ojs.aaai.org/index.php/AAAI/article/view/10694) already studies diagnosability planning and incremental twin-plant reuse. A separately tasked agent inspected its formal/method sections; the parent verified the primary identity and abstract. Distinguishing twin states, cached diagnosability or an observation planner alone would overlap established work. Retain PC2, AgentThread, CONTINUITY, BRIDGE, active decision-region testing and contract-quotient comparisons in the existing novelty gate.

Proceed with the original-native verification because it tests an independently existing task requirement. Stop expansion and revise its interpretation if native success fails, the port changes the relevant behavior, a typed alternative already emits the required field, or the purported loss is recoverable through a permitted path. Recovery by one obvious raw action is valuable profile evidence and **fails a new-method claim on its own**. Likewise, if the proposed analyzer is ordinary guarded reachability/quotient with renamed fields, retain it as an established analyzer and redesign C1.

No efficiency threshold is relaxed. The old 192-admission comparative pilot remains unrun under the rejected plain-text efficiency hypothesis. A future candidate advantage needs a concrete new technical step, strong same-input comparators and a prospectively frozen meaningful evaluation. Native success, a port, a typed limitation or raw recovery cannot independently pass CP2 or substitute for actual human novelty/feasibility review.
