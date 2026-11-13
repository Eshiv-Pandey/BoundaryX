# AP2 procurement source lead, 29 October 2026

The official AP2 repository is a new source lead within the approved procurement
domain. It has not been qualified as a benchmark domain or executed here. The
review distinguishes two original application variants: one has explicit A2A
challenge continuation, while the other has a persistent local checkout effect.
Their properties cannot be combined into a fictitious single implementation.

## Acquired source

The [official repository](https://github.com/google-agentic-commerce/AP2) was
resolved to commit
[`e1ea56db72a6385bce3e5c1112b3a56ce60acb43`](https://github.com/google-agentic-commerce/AP2/commit/e1ea56db72a6385bce3e5c1112b3a56ce60acb43).
The [pin response](source-evidence/ap2-procurement-screen-v1/commit-response.json)
and [complete tree response](source-evidence/ap2-procurement-screen-v1/tree-response.json)
are retained. The
[acquisition result](source-evidence/ap2-procurement-screen-v1/source-result.json)
records all 134 selected files, totaling 651,106 bytes: the complete Python
sample and SDK subtrees plus root LICENSE, README and pyproject. Each raw file's
size and Git blob hash matched the pinned tree; SHA256 values are also recorded.
This is a source subset, not an installed environment or full Go/Android checkout.

The acquired [license](source-evidence/ap2-procurement-screen-v1/source/LICENSE)
is Apache-2.0. No source was imported, dependency installed, model called or
application launched. No Python dependency lockfile was found in the pinned
tree. The sample
[dependency declaration](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/pyproject.toml)
pins A2A SDK 0.3.24 and ADK 1.28.0, but its x402 VCS dependency has no commit pin.
Application card version fields do not establish an A2A protocol version.

## Variant A: human-present A2A card challenge

The [base executor](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/common/base_server_executor.py)
uses the supplied task/context IDs and passes the current task to the selected
tool (lines 98-114). The
[processor](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/roles/merchant_payment_processor_agent/tools.py)
requests input for a new task and handles the follow-up from `input_required`
(108-120). The shopping and merchant code forward stored/discovered task IDs.
These are source-supported continuation paths, not observed native outcomes.

The processor's OTP is the literal demo value `123` (225-227). Its completion
path constructs a success receipt and a fresh receipt identifier; the
[credentials-provider receipt handler](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/roles/credentials_provider_agent/tools.py)
does nothing and completes (298-312). This path does not supply an inspected
debit, reservation, order-commit or payment-deduplication ledger. A different
valid signed mandate supplied on the pending task is a required binding
near-miss to investigate; it is not an observed exploit or an established
enforced same-transaction guard.

The [tool resolver](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/common/function_call_resolver.py)
calls Gemini even for single-tool dispatch. No unchanged inference-free bypass
was found. Source signature verification is real, while credentials and payment
behavior include explicit mocks. Neither fact makes a live payment claim.

## Variant B: original A2A shopping frontend with MCP checkout

The original
[human-not-present card scenario](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/scenarios/a2a/human-not-present/cards/run.sh)
selects the card flow and starts the MCP services plus
[shopping_agent_v2](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/roles/shopping_agent_v2/run_server.py).
The latter enables ADK's A2A frontend (112-120). Its
[agent definitions](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/roles/shopping_agent_v2/shopping_agent/agent.py)
use the original merchant, credential and processor tools through stdio MCP.
Thus the proposed external route can be MCP caller to an existing MCP-to-A2A
bridge, then the original A2A shopping agent and its original MCP tools. No
inverse bridge or merged implementation is needed for that topology.

The [merchant checkout](source-evidence/ap2-procurement-screen-v1/source/code/samples/python/src/roles/merchant_agent_mcp/server.py)
rejects missing, used or expired tokens and verifies the checkout mandate chain
(843-898). It records token use, order ID, amount/currency and checkout hashes
in local state (923-946). This is a meaningful local simulated order commitment,
not bank settlement.

The write occurs before calling the card processor (1009-1025), and file-write
errors are logged (228-234). Do not claim atomic settlement, rollback, durable
exactly-once behavior or safe concurrent deduplication. Downstream failure
after the local write is a necessary adverse case. Successful tool output
contains an order ID and signed checkout receipt (1031-1052); the purchase
prompt asks the model to emit completion JSON in text. That text must be checked
against the returned receipt and independently observed local state.

The original shopping agents require model access. They use conversation and
`app:` state; a shared session does not establish continuation of one original
A2A task. The pinned adapter/client inspection below does not establish the
paused original-task behavior required by the current benchmark contract.

Do not invoke the convenience run script in the existing workspace: it deletes
state/logs and stops port listeners. Any future execution needs a separately
allocated workspace and an owned-process lifecycle around the original modules.

## Qualification boundary

The local checkout effect is real source evidence, but it does not close the
original-task qualification requirement. Keep amount/authority, expiry, token
reuse, consent/task association, local commitment, signed receipt and downstream
completion as separate checks.

Budget constraints are not silently ignored. The SDK's
[BudgetEvaluator](source-evidence/ap2-procurement-screen-v1/source/code/sdk/python/ap2/sdk/constraints.py)
requires `MandateContext` when a Budget constraint is declared (278-313).
The original credential/processor MCP verification calls omit that context and
reject the resulting constraint violation. Without a declared Budget there is
no such evaluator call. This is different from amount-cap checking and the
shopping agent's local recurrence counter, which is updated during mandate
creation before settlement. No authoritative post-payment budget ledger is
claimed.

## Pinned task mapping

The [official PyPI acquisition](source-evidence/ap2-procurement-screen-v1/adk-task-mapping-v1/result.json)
retains ADK 1.28.0 and A2A SDK 0.3.24 wheel bytes with SHA256 values matching
their version metadata, plus 83 selected source/metadata/license files. The
[follow-up acquisition](source-evidence/ap2-procurement-screen-v1/adk-task-mapping-v1/followup-result.json)
adds four adapter/tool sources and three official AP2 client files, bound to
the same Git pin. No package was installed or imported.

- The [official client](source-evidence/ap2-procurement-screen-v1/adk-task-mapping-v1/client-source/code/web-client/src/a2aClient.ts)
  omits both `message.taskId` and `message.contextId` (90-107). Its optional
  `taskId` parameter becomes the JSON-RPC request ID; `sessionId` is metadata.
- The [ADK request converter](source-evidence/ap2-procurement-screen-v1/adk-task-mapping-v1/google-adk/source/google/adk/a2a/converters/request_converter.py)
  uses the request context ID as the ADK session ID and places other metadata
  into custom metadata (98-116). These fields are not interchangeable.
- The [default executor](source-evidence/ap2-procurement-screen-v1/adk-task-mapping-v1/google-adk/source/google/adk/a2a/executor/a2a_agent_executor.py)
  completes ordinary final text turns (275-305). Input-required conversion
  depends on long-running-function metadata. The original ordinary functions
  and MCP tools do not request that suspension; prompt text about consent or
  monitoring does not itself change A2A task state.
- The [SDK handler](source-evidence/ap2-procurement-screen-v1/adk-task-mapping-v1/a2a-sdk/source/a2a/server/request_handlers/default_request_handler.py)
  rejects follow-up messages to terminal tasks (219-225).

Therefore the original MCP-backed shopping path is a model/session/application
workflow with a local effect, not an established paused same-original-A2A-task
purchase. The separate processor OTP continuation cannot supply that missing
property for this variant. A long-running wrapper or modified client/agent is a
new intervention, not unchanged-source qualification. These conclusions are
from the pinned source paths; no application failure or live behavior is claimed.

Host resources still fail the [live eligibility rule](pending-admission-resource-decision-v5.md).
The user has offered free-tier Gemini access and requested local key setup;
configured access and successful inference have not yet been verified. These source findings earn
no domain, novelty, independent-evaluation or percentage credit. The
[implemented algorithm and benchmark demo](shared-admission-command-v1.md)
remains the deliverable for the 31 October review; paper work stays deferred.
