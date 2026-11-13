# Source-derived payload recipes: baseline fragment v0

Reviewed **24 October 2026**. **Decision: no demonstrated C1 algorithmic
distinction.** This is a precise baseline/specification fragment, not a new
algorithm, implementation, comparative experiment or passed scientific gate.
It follows the rejected observation-saving and broader acquisition candidates.
The integrating assistant checked the actual pinned serializer/tool/fetch
sources; a separately tasked AI reviewer assessed the reduction. Neither is
independent human scientific review.

## Exact question and restricted evidence boundary

For an accepted fixed environment `e`, a permitted operation `o`, legal caller
arguments `x`, source-derived serialization `F_o`, transport acceptance `T`,
and a necessary application guard `G`, solve:

```text
exists o, x: Legal_o(x,e) and T(F_o(x,e),e) and G(F_o(x,e),e)
```

The environment includes the pinned deployment/card, reviewed state and ordinary
public task bindings. It is not evaluator-private gold. The output of `F_o`
includes the body, headers, selected endpoint/query and any modeled defaults.
The caller controls only actual exposed arguments. It cannot set an internal
client parameter, assign a generated message nonce, forge a native task ID hidden
behind an opaque handle, alter a card or insert an unavailable header.

The restricted serializer language contains finite acyclic object/list creation,
field projection, constants, explicit omission, defaults and reviewed conditional
branches. Guards contain field presence, equality, finite enums, sequence length
and expressly modeled text predicates. Unresolved calls, arbitrary JavaScript or
Python behavior, opaque relevant state, stale bindings and relevant nondeterminism
remain **unknown**. This does not define a general source compiler or claim a
complete abstraction of the applications.

Generated fields can be omitted from a necessary-guard characterization only
when their irrelevance is justified. If a guard depends on an unpredictable
generated value, existentially choosing that value does not construct a caller
recipe. The initial fragment abstains rather than silently replacing the actual
generator with a caller-controlled input.

A fixed-environment satisfiable formula establishes only that the modeled guard
can be reached by permitted inputs. Full bounded task completion additionally
needs source-faithful state transitions, invariants, a valid task binding and
the original horizon. One-step payload expressibility is not full-route
may-compatibility or a guarantee that an arbitrary future workflow succeeds.
With several possible relevant environments, choosing a different hidden-state
witness for each is not one executable recipe. Uniform or conditional policies
need their own quantified semantics; standard contingent planning and PC2's
visible-state obligations remain prior art.

## Strong faithful baseline

```text
accept the source/schema/guard coverage, or return unknown
for every permitted operation:
    build shared symbolic terms for body, headers and endpoint selection
    substitute these terms backward into transport and application guards
    simplify constants/defaults and solve the remaining legal-input constraints
    if a caller-constructible satisfying assignment exists:
        check its concrete serialization and all accepted binding assumptions
        return the conditional recipe, at this fragment's stated scope
if every permitted operation has a checked obstruction under complete coverage:
    return non-expressible for the exact fragment
return unknown
```

Each symbolic term denotes the corresponding concrete source expression in the
restricted deterministic fragment. Structural induction over expression
construction gives exact denotation for reviewed primitives and branches.
Substitution then gives the same truth value as evaluating `T` and `G` on the
serialized request. Consequently the satisfying caller inputs are precisely
the existential preimage of the accepted request set, under those assumptions.
This is a **standard reduction**, not a new theorem or mechanized proof.

For multiple operation steps, the faithful comparator composes the same
source-derived transition constraints within the declared horizon. An obstruction
for one send operation cannot rule out another permitted operation, raw action,
native fallback or agreed alternative contract. Complete-negative claims require
every relevant legal path to be covered. Failed solver calls, incomplete source
coverage and unmodeled actions yield unknown.

## Actual source cases and their limits

| Pinned source boundary | Consequence justified by source / existing evidence |
| --- | --- |
| Amir `src/tools.ts:184-205`, `src/a2a-client.ts:213-228` | The typed send exposes text and task/context handles; its message constructor fixes `referenceTaskIds=[]` and omits message metadata. No choice of text changes that literal reference field. The disclosed Carol completion branch requires nonempty references and its answer prefix. This is a typed-serializer obstruction, not full-interface non-support. |
| mgcrea `src/tools/writes.ts:34-72`, `src/client/peer.ts:166-182` | The registered tool exposes text/task/context arguments and fixes empty references. The internal client's optional metadata argument is not forwarded by this registered tool. Caller-visible and internal interfaces must remain distinct. |
| mgcrea `src/tools/request.ts:39-77` | Write-enabled raw requests accept native parameters, including references, but the legal RPC names are a finite modern-name enum. Legacy `message/send` and `tasks/get` strings are not permitted by this registered tool. It is not a general arbitrary-method or arbitrary-URL fetch interface. |
| mgcrea `src/client/peer.ts:261-279`, `src/client/fetch.ts:41-63` | Raw requests select the endpoint from the card and initially supply content type. The reviewed fetch wrapper adds authentication/User-Agent and retains the request through its retry loop; it does not insert a version header. Retries do not create a new header-setting action. |
| [Official HTTP controls](sdk-http-version-results-v1.md) | The pinned default handler accepts header-positive native completion and rejects the observed absent/query-only version inputs. Native parameter expressibility alone does not establish transport acceptance. No MCP bridge was run against that handler in those controls. |
| [a2acode source screen](source-evidence/c1-screen-a2acode-v1/decision.md) | A supplied wrong permission request ID is rejected, but absent metadata is allowed. Therefore metadata omission alone does not establish typed echo non-support. Structured question gates are not produced by that upstream echo backend. |

These boundaries reuse actual source and previously retained observations. They
are not new natural-failure trials, a held-out corpus or performance samples.
The source snapshots and verified Git pins are in
[the screen manifest](source-evidence/recipe-method-screen-v1/manifest.json).
The original bridge/application sources were not edited.

## Why the proposed C1 distinction fails this screen

A shared term DAG with field origins and conditional nodes avoids enumerating
all payload strings or expanding every branch. A correctly simplified SSA/SMT
or symbolic/backward comparator can use that same representation. Equality-only
constraints can be simplified cheaply by both arms; adding general branch or
string constraints restores ordinary solving costs. No comparative cost result
or defensible distinct technical step has been identified here.

The existing [predicate-transformer and contract source review](source-evidence/2026-10-24-primary-revalidation.md)
already covers backward reasoning, quotienting and source-linked composition
IR. Existential preimage must remain distinct from demonic weakest preconditions.
[AgentThread](https://arxiv.org/html/2606.28690v1), sections 4.2-4.5, already
links source requirements, typed IR, composition checks and executable replay;
[PC2](https://arxiv.org/html/2610.28484v1), Appendix A, covers proof obligations
and compatible hidden states. Those mechanism reviews are reused, not counted
as fresh discovery or independently executed comparators.

A new inspection of [Cousot and Cousot's author page](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml)
confirms the classical sound-abstraction framework through its published summary;
the full paper was not inspected in this pass. The official
[Z3 sequence guide](https://microsoft.github.io/z3guide/docs/theories/Sequences/)
documents empty sequences, length and prefix operations relevant to this
fragment. It does not provide a blanket complete decision procedure for arbitrary
sequence equations. The [retained primary response](source-evidence/recipe-method-screen-v1/primary-tool-response.json)
is a tool-rendered page record, not complete original source bytes. Neither Z3
nor another solver was executed for this screen.

All practical comparators must receive identical source terms, legal action
alternatives, defaults, task evidence, horizon and accepted assumptions. Charge
source extraction/review, profile construction, compilation, solving, recipe
construction/checking and invalidation to every arm. Compact symbolic analysis
compared only with enumerated payload BFS would create an artificial advantage.

**Decision:** retain this fragment as the source-fidelity baseline. Do not
implement or scale a C1 performance trial merely by renaming it. A future
candidate needs an explicit additional technical step, sound assumptions and
a plausible prespecified advantage over the strongest applicable comparator.
The original method objective remains active, no applied-only route is selected,
CP2 remains open and verified progress remains **5%**.
