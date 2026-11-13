# Experiment protocol

## Unchanged experimental designs

Artifact: four commands, five fresh task repetitions, four routes, 80 tasks. Native A2A, Amir typed, mgcrea typed and mgcrea raw are route labels; typed/raw mgcrea share one implementation. The unchanged upstream fixture produces text, structured objects, file URIs and inline PNG bytes. Exact payload utility differs from complete metadata fidelity. File bytes are not fetched. The recorder forwards RPC bytes unchanged and rewrites discovery endpoints to loopback. Repetitions are not independent application-family samples.

Artifact recovery is one authorized raw GetTask on the original typed task/context when required fields fail. It was selected adaptively after development smoke and fixed before the final allocation. Recovery success is not untouched policy discovery.

Controlled protocol: ten cases × twelve conditions × four routes = 480 episodes. A genuine SDK-backed A2A server invokes an authored deterministic Python receiver. Two isolated read probes per episode give 960; probe communication is recorded separately from episode overhead. Conditions are reference, placebo_identity, dropped_fact, capability_mismatch, wrong_task, constraint_loss, safe_equivalent, recovery, extraction_loss, compound_records_binding, compound_identity_constraints and compound_all. These are deliberate injections, not naturally occurring bridge faults.

Diagnostics: ten families × sixteen development variants × twelve conditions = 1,920 episodes on 160 instances. Renaming, numeric/time translation and permutation do not create held-out diversity. Every applicable subset of records, task identity, constraints and tool binding is evaluated, giving 6,400 interventions. Inclusion-minimality and minimum cardinality apply only to this finite universe, not arbitrary semantic edits or global repair cost.

## Route execution audit

| Route/component | Actual execution and state | Limits |
| --- | --- | --- |
| native | Official A2A JS SDK; HTTP JSON-RPC SendMessage/GetTask, A2A-Version 1.0; native task/context/artifacts | Deterministic receiver; no LLM |
| amirk_typed | Independent a2a-to-mcp HTTP MCP tool server; initialize/tools/call; opaque task/context handles | In-memory handle TTL and omitted optional/auth surfaces |
| mgcrea_typed | Independent mcp-a2a stdio server and official A2A HTTP client; refresh=true reads native truth | Local mirror, explicit write authorization, artifact summary projection |
| mgcrea_raw | Same implementation's public a2a_request tool | Different interface, not independent bridge implementation |
| Python loss/diagnostic receiver | Constructed local read-only fixture and recorded state/reads | No protocol conversion in this component |
| admission toolkit | Supplied finite model and relation interpreter | No model/network/application execution |

Measured MCP negotiation is 2025-11-25 on the selected paths. Newer advertised specification support is not a measured negotiation. Wire deadlines are ten seconds; polling/startup and outer stages are bounded. Owned subprocesses close; failures/timeouts remain in their allocations. Source hashes are checked after execution. Model calls are explicitly zero. The loopback study does not establish authentication, complete streaming, production restart behavior or full protocol conformance.

## New evaluation separation

Historical evidence, development reproduction, held-out candidates and final scientific evaluation are separate. Reproduction reuses the original design in new allocations, with fresh timings and no pooling. Twenty new task structures are frozen before execution, with proposed gold and hash manifests. Human gold and route support are unqualified; evaluations are zero. Two distinct teammates review clarity, consistency, expected-output logic and evidence. The supervisor observes progress and has no approval gate. Corrections require a new freeze; held-out outcomes cannot tune implementation. Final evaluation remains Not Established.
