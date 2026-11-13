# Shared continuation callsites: constructive C1 screen v1

27 October 2026. **Decision: unselected; no additional C1 construction or
advantage is established.** This is a source-based analytical screen with a
separately tasked AI critique. It is not independent human scientific review,
a compiler implementation, a performance result or an application experiment.
It adds no checkpoint credit. The original bounded safe may-completion target
and full method objective remain unchanged.

## One construction assessed

The candidate factors repeated serializer/sender callsites before bounded
route unrolling. Instead of rebuilding a common suffix separately for each
exposed continuation, it stores one parameterized source summary and keeps
the callsite-specific guards, state changes and response projections around
it. This is more concrete than a general proposal to retain field origins:
the proposed additional operation is replacing repeated function bodies with
shared summary-application nodes and retaining an expansion map for witnesses.

The question follows the [AgentOps effect screen](c1-agentops-effect-screen-v1.md).
It uses the [source-recipe baseline](source-recipe-baseline-v0.md),
[finite continuation semantics](finite-model-v1.md) and
[approved method scope](../../RESEARCH_WORKFLOW.md) without changing their
evidence boundary, invariants, goal or horizon.

## Exact source-supported repetition and its limits

The following Git HEADs were read locally for this screen:

- AmirK-S `external/a2a-to-mcp`:
  `58eff9da469bccdc432bf164662727947de646b4`.
- mgcrea `external/mcp-a2a`:
  `c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5`.

These identify the inspected source checkouts. This screen does not claim a
new installed-runtime equivalence check or new wire observations.

| Pinned source path and lines | Repetition or residual that the construction must preserve |
| --- | --- |
| [Amir `src/a2a-client.ts`](../../external/a2a-to-mcp/src/a2a-client.ts), 90-105, 114-128, 194-229 | Synchronous and streaming methods both call `buildUserMessage`; its one text part, generated message ID, identity defaults and empty references form a shared construction. Method, configuration and stream behavior remain different. |
| [Amir `src/tools.ts`](../../external/a2a-to-mcp/src/tools.ts), 254-314 | The public handler resolves task/context handles, routes verified request state to MRTR, selects Tasks when negotiated, and otherwise calls the ordinary sender. These are source-local residuals, not interchangeable entrypoints. |
| [Amir `src/mrtr.ts`](../../external/a2a-to-mcp/src/mrtr.ts), 155-186 | MRTR checks the state alias, resolves its task handle, interprets the public answer, and calls the same synchronous sender. Missing answers re-elicit; decline/cancel follows cancellation. |
| [Amir `src/tasks/handlers.ts`](../../external/a2a-to-mcp/src/tasks/handlers.ts), 126-168 | Tasks chooses streaming or `returnImmediately`; a stream can return its first lifecycle event while subsequent events continue updating the record in the background. |
| [Amir `src/tasks/handlers.ts`](../../external/a2a-to-mcp/src/tasks/handlers.ts), 252-276, 287-327 | Updates act only while the record is waiting. Answering marks the record working before sending; streamed continuation is consumed asynchronously. Waiting state and scheduling are relevant residuals. |
| [mgcrea `src/client/peer.ts`](../../external/mcp-a2a/src/client/peer.ts), 166-196, 261-289 | Typed send constructs a text message and calls the configured SDK. Raw RPC instead selects the card's JSONRPC endpoint and supplies content type to the fetch path. Raw is not another invocation of the same typed serializer/header configuration. |

This supports a small repeated callsite structure, chiefly within Amir. It
does not establish a scalable family of equivalent continuation handlers or
permit merging the two independent bridges' send semantics.

## Restricted construction and preservation obligations

Let state `s` retain application and bridge state, original task/context,
public observation history, relevant identities and generated values, effect
monitor, freshness and scheduling information. The accepted model determines
which transitions count toward the unchanged horizon `H`. Source statements
are not automatically additional task transitions, and summary applications
must not erase transitions that the accepted model already counts.

For a reviewed function `f`, use an exact relational summary:

```text
S_f(s, arguments, s', return_value, observation, delta)
```

Here `delta` is the number of original model transitions in the represented
segment. Internal invariant checks are retained. Potential goal states and
caller decision points cannot disappear inside a summary: retain their
original control locations, or provide exact prefix summaries for those
boundaries. Every summary application has a concrete expansion map.

For an exposed handler `i`, retain its prefix and continuation residuals:

```text
R_i = W_i ; Apply(S_f, arguments_i) ; V_i
```

Relational composition retains intermediate state and observations. Costs
add across the represented segments. If `W_i` or `V_i` includes concurrent
activity, its accepted interleavings remain in the model; a request/response
pair is not silently made atomic.

```text
accept source/language/state coverage for the declared fragment, or return unknown
for each reviewed function used at several legal callsites:
    compile its exact guarded transition fragment and boundary observations
    retain internal safety checks, eligible goal boundaries and original costs
    store one parameterized summary with a witness expansion map
for each exposed operation:
    retain its legal arguments and wrapper-specific state/observation transitions
    replace repeated bodies with applications of the corresponding summary
intern only summaries justified equivalent under the same source and assumptions
solve the original invariant-safe completion query with total cost at most H
expand and check positive witnesses; require complete closure for negatives
```

The claimed preservation would be:

```text
May_H(original model, initial state, I, G)
    iff
May_H(factored model, initial state, I, G)
```

For exact summaries, projection replaces each represented segment by its
summary application. Lifting expands applications using the same intermediate
state, observation and generator constraints. Preserved costs and safety/goal
boundaries give the same bounded safe traces. This is ordinary exact-summary
substitution, not a new theorem proved or mechanized by this screen. Inexact
source closure, opaque relevant callbacks or an unjustified concurrency model
prevent a complete-negative claim.

All original legal inputs remain available, including arbitrary permitted
strings and lucky guesses. An absent public confirmation field does not turn
a legally guessable string into an unnameable private atom. Conversely,
generated values are not newly caller-controlled parameters. The construction
does not provide evaluator-private values to practical methods or convert
fixed-state/evidence-relative existence into a uniform caller guarantee.

## Reduction to the same-evidence comparator

The faithful comparator already receives the source terms, legal operations,
wrapper guards, state, observations, scheduling assumptions and original
contract. It may use ordinary interprocedural relational summaries, shared
symbolic call DAGs, substitution, caching and valid partial-order reductions.
It can therefore construct precisely the same `W_i ; S_f ; V_i` representation.
Mapping a candidate summary node to an ordinary parameterized summary call
preserves every parameter, residual guard, observation and cost; it does not
require a new decision rule or a weaker input domain.

This objection is stronger than observing that an SMT formula can encode the
candidate. The candidate's proposed factoring operation itself is established
summary construction and sharing. It supplies no extra step after those
mechanisms have been granted to the comparator.

With `k` callsites, either implementation can store a shared template in space
proportional to `|S_f| + sum_i(|W_i| + |V_i|) + k`, rather than textually copying
the suffix `k` times. This is a representation accounting statement, not a
solver-time bound. Different calls still require distinct state/value bindings;
their solving or instantiation costs cannot be hidden by counting only the
template. The comparator gets the same sharing and applicable cache keys.

Charge source acquisition/review, extraction, summary construction, equivalent
summary justification, instantiation, solving, witness expansion, negative
checking, updates and invalidation to both arms. A source/profile revision,
changed relevant state, task/identity binding, principal, expiry or scheduling
assumption must invalidate whichever cached result depends on it in either
implementation. Comparing the candidate against forced repeated inlining or
unshared UUID enumeration would manufacture an advantage.

## Why coarser merging does not supply the missing step

Grouping handlers only by emitted request shape would discard real state.
Amir Tasks `#answer` marks its record working before the send and may return
while `#consume` continues. `#update` forwards an answer only when `#isWaiting`
holds; another update while working is ignored. A representation retaining
only the pending native task binding and a common send suffix could incorrectly
admit another upstream `SendMessage` transition or change observable timing.

This is a source-established transition distinction, not an observed duplicate
AgentOps effect or a demonstrated may-completion separation for the fixture.
Retaining the record state, observations, stream schedule and original costs
repairs the fidelity issue, but restores the ordinary stateful summary and
symbolic/POR construction. MRTR state validation, handle resolution and
re-elicitation similarly remain residuals. The raw-versus-typed transport
configuration difference cannot be removed merely because both bodies can
name a native task.

## Decision

Do not select this construction for a C1 performance trial. No substantive
additional procedure or advantage over the equally informed optimized
comparator is established, and the inspected few callsites do not establish
a nontrivial repeated family on which to prespecify such an advantage.

The separate AI critique independently identified the same exact-summary
reduction and the Tasks residual-state limitation. It does not replace human
review or establish that every possible new method is impossible. No compiler,
solver, application/performance experiment, inference, human review or research
credit was produced by this screen. Frozen checker, client, launch and prior
evidence files, checkpoint records and the workflow were not changed.
