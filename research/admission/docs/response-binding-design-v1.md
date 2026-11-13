# Later public response binding: source assessment v1

29 October 2026. **No-go for another residual-state wrapper, and no-go for
implementing a new preflight admission extension from the current partial
response model.** The source supports extracting disclosed identifiers and
copying them into later requests. That behavior is already implemented. A
symbolic analysis before task creation would be a different formal capability,
but copy relations alone do not establish its response-generation, completion
or certificate semantics. Do not turn this finding into another cache change,
a claimed new algorithm, or an assumed successful future response.

Only this note was written. No code, tests, solver/checker, benchmark, application
or WSL process was run for this assessment. Sources and retained public bytes
were read and hashed; they were not altered.

## What already works and what the sources establish

| Boundary | Source and existing behavior | Limit |
| --- | --- | --- |
| Initial typed send | [`writes.ts:65-102`](../../external/mcp-a2a/src/tools/writes.ts) mirrors a returned Task and exposes its summary. [`shape.ts:85-108`](../../external/mcp-a2a/src/client/shape.ts) copies its ID and any nonempty context ID. [`runPublicEpisode:178-185`](../../scripts/agentops_bridge_client_v1.mjs) binds those received fields. | A bare Message is a separate legal reply; errors or missing fields do not create task bindings. |
| Current task read | [`tasks.ts:76-85`](../../external/mcp-a2a/src/tools/tasks.ts) refreshes an outbound mirror from the peer; [`peer.ts:196-209`](../../external/mcp-a2a/src/client/peer.ts) sends the selected task ID. The client polls submitted/working and checks task/context association. | The local mirror is not self-refreshing. Working does not guarantee input-required or completion within a bound. |
| Confirmation disclosure | [`request.ts:35-81`](../../external/mcp-a2a/src/tools/request.ts) exposes permitted raw methods; [`peer.ts:261-294`](../../external/mcp-a2a/src/client/peer.ts) selects the advertised JSONRPC endpoint and returns parsed raw JSON. [`findRawConfirmation`](../../scripts/agentops_bridge_client_v1.mjs) extracts a received confirmation; [`pending_admission._extract`](../../src/interoperability/pending_admission.py) additionally checks its original action/target. | Raw parameters do not give callers control over bridge-generated RPC IDs, unavailable headers or hidden server history. Ambiguous/unmodeled replies remain unknown. |
| Later request | The client copies task/context/confirmation values into a structured FunctionResponse. [`controller:138-185`](../../scripts/agentops_admission_controller_v1.mjs) checks the admitted request, refreshes tools/discovery/pending/raw observations, compares their signature, and reserves at most one continuation. | This already implements late binding and revalidation. The fifteen-second local window is neither a service lease nor an atomic state lock. |
| Acceptance and effect | The [pinned source map](pending-admission-source-map-v1.md#source-supported-predicates-and-their-limits) identifies ADK shape checks, confirmation-history matching and AgentOps application guards. | Correctly copied IDs do not establish identity, policy, service state, invocation history, redaction or successful commit. |

The inspected deployed `default_request_handler_v2.py:223-333` resolves IDs and
admits Task or Message results. `a2a_agent_executor_impl.py:113-166` publishes
submitted/working and also has failure handling. `long_running_functions.py:159-204`
recognizes function-response shape; `_confirmation.py:126-218,276-325` additionally
uses current server-branch history and consumed responses. These are the exact
paths and hashes in the existing source-map JSON, checked again here.

Those were fresh source-text reads, not only reads of source-map metadata.
The exact paths below are relative to the Windows workspace
`<legacy-workspace>\`:

- `runs/agentops-native-eligibility/linux-bridge-diagnostic-v12/workspace/external/runtime-agentops-linux-v7/venv/lib/python3.13/site-packages/a2a/server/request_handlers/default_request_handler_v2.py`
- `runs/agentops-native-eligibility/linux-bridge-diagnostic-v12/workspace/external/runtime-agentops-linux-v7/venv/lib/python3.13/site-packages/google/adk/a2a/executor/a2a_agent_executor_impl.py`
- `runs/agentops-native-eligibility/linux-bridge-diagnostic-v12/workspace/external/runtime-agentops-linux-v7/venv/lib/python3.13/site-packages/google/adk/a2a/converters/long_running_functions.py`
- `external/runtime-agentops-v2-recovery-2/venv/Lib/site-packages/google/adk/flows/llm_flows/tools/_confirmation.py`

The first three are previously exported Linux-source files stored on the Windows
drive; the fourth is the local recovered installation file identified by the
existing source map. `Get-Content` read their source ranges and `Get-FileHash`
checked their bytes. No WSL UNC path was accessed, no distro was started, and
none of these Python files was imported or executed.

The pinned [`_ConfirmationLlm:57-96`](../../external/agentops-c806b7f1/agents/python/tests/test_server.py)
requests **one** guarded inventory action. Its later completion text follows
the presence of a `restart_service` response, not an independent verification
of the effect. [`actions.py:108-148`](../../external/agentops-c806b7f1/agents/python/src/agent/actions.py)
can return guard/domain errors; [`data.py:620-662`](../../external/agentops-c806b7f1/agents/python/src/agent/data.py)
performs the transaction and conditional idempotency lookup. No second-round
fixture or general completion/liveness guarantee follows.

## Public-byte evidence and provenance boundary

The v12 B7 [public journal](../../runs/agentops-native-eligibility/linux-bridge-diagnostic-v12/workspace/runs/agentops-http-control/bridge-diagnostic-v1-B7/client/mcp.jsonl)
still hashes to `7efb5c56df82e266be2801e895211b32359c9c862ff1fa8f903e15a440a26cec`.
Decoding its retained raw bytes confirmed:

- Event 29: Task ID/context disclosed, state `submitted`; 625 bytes, hash
  `6ef45eb63e1611de0f3cfb3777bec6ff58da4f6bef54e3b8ed585690c2e21455`.
- Event 37: the same association, state `working`; 820 bytes, hash
  `c29d5a9656efb79c8a2434eaf8c8694b42c0caa2dd0b4d7fc2687aa6e766c0f7`.
- Event 43: the same association, state `input_required`; 1,087 bytes, hash
  `ccc2dddf9bb412428b9f6c68959297203c4ce2a7e37d02be85b2eb8b7b1616d4`.
- Event 49: raw input-required task and confirmation ID/name plus original
  inventory action/arguments; 2,986 bytes, hash
  `e87ef133503f92c5293af8057dd3778ef28717c147f089b90b9fc0b4cf9653f2`.

These are **bound to retained public journal bytes**, not authenticated source
observations or evidence about a future task. At a prospective cutoff before
event 29, neither its concrete IDs nor event 49's confirmation may be inputs.
Historical dispatch event 54 is comparison evidence only. Byte identity does
not establish that a future deployment loads the same sources.

The mgcrea checkout reports commit
`c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5`; inspected writes/tasks/shape files have
no diff from that commit. Mapped bridge/SDK/action/data source hashes matched
the existing source map. The local and v12-exported `test_server.py` both hash
to `8257f7267d516d12f656ff886f5796bb58178051cc13d3c582dc9eefbd78b270`.

## Two options and the minimum missing contract

**Online residual state:** a record of the runtime contract, route/source model,
accepted journal prefix, correlated bindings with reply/path provenance,
remaining horizon/budgets, unresolved obligations and consumed continuation.
Bindings are added only after a matched received reply. This is implementable,
but largely formalizes the existing episode/controller; it does not justify a
new implementation now or a new scientific mechanism. The strongest comparator
gets the identical observed frame and uses the existing goal-pruned direct
solver, with observation/revalidation costs charged equally.

**Symbolic response relation:** would add a minimal contract of the form
`(operation, prior-frame guard, request constructor, response cases,
response-to-binding projections, successor predicates, unresolved fallback)`.
Future slots are response projections, not caller-selected literals. For
example, a guarded template can copy `initial_reply.task.id` into a later
`GetTask.id`, and a subsequently disclosed confirmation ID into the answer.
This can prove **conditional copy correctness** before the initial call. It is
not yet an existing concrete `recipe-path` certificate or permission to send a
continuation. A bare/malformed/error reply leaves that template uninstantiated.

Before a distinct preflight admission implementation is justified, the missing
obligations are:

1. A source-supported relation for which response/successor cases are actually
   possible under explicit assumptions, including errors and unmodeled cases.
   Output shape alone does not establish a realizable completion path.
2. An independent checker that proves binding dominance and request/response
   association, parses the retained bytes itself, preserves whole-frame
   correlations and invalidates stale or changed dependencies. It must exclude
   future journal events at each decision cutoff.
3. Explicit quantifiers: existential bounded may-reachability is distinct from
   a strategy guaranteed to work for every possible response. A favorable
   existential response cannot authorize an unconditional dispatch. Existing
   unknown meanings must survive missing bindings and unresolved behavior.
4. No freshness/distinctness axiom merely because an ID is generated or looks
   like a UUID. Copy equality is justified; inequality to another symbol or an
   arbitrary caller literal requires separate evidence.
5. Completion/effect predicates justified separately from request acceptance,
   working status or model-generated completion text. Negative closure remains
   incomplete for this open action space; polling exhaustion means unknown.
6. A strongest same-semantics reference: independent bounded forward symbolic
   composition over the same response relations, guards and binding terms,
   with ordinary memoization/goal pruning and equal construction/checking costs.
   Enumerating arbitrary concrete UUIDs would be an unfair comparator.

No complete response-generating admission model or new proof semantics is frozen
by this note. Conditional copy templates alone would restate the implemented
episode's dataflow while leaving the decisive obligations unresolved. Preserve
the question rather than inventing guarantees or expanding the one-round fixture.

The next dependencies remain qualification of the existing candidate-controlled
task/effect chain when host resources permit the required N11-before-B7 sequence,
and human assessment of the contribution against the strongest comparator.
The [latest live failure](pending-admission-live-results-v3.md) and
[adverse shared-lifting pilot](shared-lifting-pilot-results-v1.md) remain intact.
This is not permission for another live attempt or a reduction of the approved
admission/benchmark research scope. Paper work remains deferred.
