# Admission refinement prototype v1

Implementation: [refinement.py](../../src/interoperability/refinement.py).
This is a **CEGAR/lazy-symbolic adaptation and candidate prototype; scientific
novelty and comparative advantage are unestablished**. It implements witness
lifting and checked refinement around the existing finite search. It does not
rename the existing BFS as a novel algorithm.

## Decision being implemented

The input describes a finite abstract route plus additional supplied relations
for legal public arguments, emitted requests and correlated public bindings.
The decision asks whether one bounded, invariant-safe model path can be lifted
to a concrete sequence of those public recipes. This preserves the original
existential may-completion target on the **refined supplied model**. It is not
an adversarial winning strategy, future service guarantee or live execution.

The base finite graph is an overapproximation of that refined model: a graph
edge alone no longer proves that its request can be constructed and accepted.
Consequently running the old baseline on just the inner graph answers a weaker
question. It is a useful abstraction-only control, never the decisive accuracy
or efficiency comparator. The direct same-input reference checks the refined
relations too.

`source_ref` strings, `coverage.complete`, the inner model's provenance, and
`initial_bindings` being called public are **supplied-model assumptions**.
Validation does not authenticate source bytes, establish that the declarations
are faithful/complete, or compile a real bridge automatically. An authored
finite recipe alphabet does not cover arbitrary legal strings or every public
route of a real bridge. Existing wire runs remain separate observations.

## Exact input schema

`schema_version` is `recipe-continuation/1`. Exactly these top-level fields are
accepted:

| Field | Meaning |
| --- | --- |
| `schema_version` | Exactly `recipe-continuation/1` |
| `id` | Nonempty prototype profile identifier |
| `model` | An unchanged `finite-continuation/1` manifest, including its original horizon, contract, graph, freshness and completeness fields |
| `initial_bindings` | Object mapping names to supplied public JSON scalars; no evaluator-private state is an accepted extra field |
| `relations` | Object with exactly one relation for every inner transition ID |
| `coverage` | Exactly `{ "complete": boolean, "scope": nonempty string }`, declaring the finite relation/recipe scope |

Each relation has exactly `source_ref`, `arguments`, `emit`, `guards`, and
`updates`. `source_ref` is a nonempty provenance/reference string; it is never
opened or executed. `arguments` maps each declared caller parameter to a finite
list of recipes. An empty list means that parameter has no legal recipe in
this supplied finite profile. Empty arguments permits one empty assignment.

A recipe is exactly `{ "literal": scalar }` or `{ "binding": name }`.
The latter copies a currently available public binding. A missing public binding
makes that recipe unavailable. It does not expose a hidden value, supply a
private oracle ID, fabricate a header, or permit choosing a source-generated
value. Literal choices are only those explicitly supplied in the declared
alphabet; a negative result is scoped accordingly.

`emit` constructs one JSON request using expressions below. Each expression has
exactly one constructor:

| Expression | Meaning |
| --- | --- |
| `{ "const": scalar }` | Known scalar, including explicit null |
| `{ "arg": name }` | Read a declared caller argument |
| `{ "binding": name }` | Read the prior public frame; missing becomes unknown |
| `{ "object": { key: expression, ... } }` | Construct a JSON object |
| `{ "array": [expression, ...] }` | Construct a JSON array |
| `{ "emit_path": [key_or_index, ...] }` | Read a path in this emitted request; allowed only in guards and updates; an empty path selects the whole request |
| `{ "unknown": reason }` | Explicitly unmodeled value; cannot produce a concrete accepted request or update |

Scalars are strings, integers, booleans and null; floats are excluded. Every
guard is exactly `{ "op": "eq" or "ne", "left": expression, "right": expression }`
or `{ "op": "present", "left": expression }`. Equality is structural and
type-sensitive: `true` and `1` differ, including inside objects and arrays.
A missing emitted path is a known ABSENT value; presence is false, equality to
an ordinary value is false, and two ABSENT values compare equal. An explicitly
unknown value is distinct from ABSENT and null. A comparison needing unknown
data is indeterminate. `present` can establish that a known object exists even
when one of its children is unknown.

`guards` are conjoined; a known false guard dominates an unknown guard or
unknown request field in the same assignment. Otherwise, any unknown needed by
the guards or any unknown request field prevents a concrete positive witness.
The `updates` object maps public binding names to expressions; updates are
evaluated **atomically from the old frame and current request**. Every resulting
value must be a scalar. Unknown, ABSENT or non-scalar updates make the assignment
indeterminate. Frames remain correlated: values from different argument choices
or alternative histories are never pooled into independently available atoms.

The transition's target state/effect is supplied by the inner graph and accepted
relation contract. A passing request guard does not independently prove an
actual application's effect. Source-to-model fidelity remains separate work.

## Algorithm and evidence

```text
validate the finite profile and evidence freshness
retain the inner model's conservative contracted-observable uncertainty rule
enumerate bounded potentially safe abstract goal paths
for each path not covered by a learned prefix refutation:
    lift its steps over correlated public frames and legal argument recipes
    construct the emitted request and check every source-relation guard
    preserve atomic updates, exact context and previous recipe choices
    if a fully known safe lifted goal path exists: return its concrete witness
    if all lifts of a prefix are definitively impossible:
        learn that exact profile-bound prefix refutation
    if a lift is indeterminate: retain uncertainty, never learn a refutation
after all abstract paths are accounted for:
    return unsupported only with complete evidence/coverage and no uncertainty
otherwise return unknown
```

The learned obstruction is bound to the whole profile digest and an exact
transition prefix. It never deletes an edge globally because that edge failed
under one task/context/call/target binding. A separately implemented checker
re-lifts each claimed refuted prefix and verifies that the set covers every
abstract bounded goal path. Unsupported does not mean a sampled call failed.
At the final edge of a known-safe goal path, the lifter returns the first fully
known legal witness immediately. It does not exhaust other argument tuples
after existential completion has been established. Negative prefix refutations
still require exhaustive consideration of their finite legal recipes.

As in finite v1, an indeterminate invariant or goal on an abstract potentially
safe reachable state prevents an unsupported result when no positive is found,
even if later relational analysis might prove the uncertainty irrelevant. A
definitely unsafe state blocks exploration. A definite initial goal permits a
zero-transition witness. Fresh partial evidence can support a concrete witness;
incomplete evidence or relation coverage cannot support a negative certificate.

Relation uncertainty matters when encountered from a concretely reachable
prefix of a potentially safe abstract goal path within the horizon. Unmodeled
relations on a graph branch that cannot reach even a possible goal do not
invent a completion. Once a goal-reaching prefix encounters an unknown
assignment, the prototype conservatively retains it even when later known
assignments fail. It does not solve arbitrary constraints over unknown frames.

`evaluate(profile, now, budget=None)` returns `decision`, `reason`, `certificate`,
`method`, `novelty_established: false`, and `stats`. `now` is integer epoch time.
Stale/future evidence and exhausted work budget return unknown without a
certificate. Malformed profiles raise `ValueError`, not an admission decision.

The optional positive integer budget defaults to 100,000 metered work units.
Graph states/edges, candidate paths, recipe assignments, expression evaluations
and refinement-trie work consume units. Counters and total elapsed nanoseconds
are implementation measurements, not an established performance advantage.
Validation and serialization overhead are included in elapsed time. Budget
exhaustion is an abstention, not a negative proof.

The direct reference also meters each replayed cached relation outcome. Its
independent certificate checker uses an operational 2,000,000-unit allowance;
prefix traversal and prefix-coverage comparisons consume units even when a
prefix has no legal argument assignment. A valid proof beyond that allowance
can fail checking; the benchmark retains that outcome as a checking failure.

Current limits are 128 abstract states, 256 edges, eight arguments per relation,
16 recipes per argument, 128 binding names, expression depth 16 and 4,096
expression nodes per relation. The inner horizon retains its existing maximum
of 64 transitions. These are disclosed prototype limits, not a benchmark
qualification or a real-protocol completeness theorem.

## Certificate formats

Every certificate has `profile_sha256`, `checked_at`, `horizon`, and
`valid_until`. SHA-256 uses the entire profile encoded as UTF-8 JSON with sorted
keys, compact separators and `ensure_ascii=False`. Changing a binding, relation,
profile, contract, source reference or completeness declaration invalidates it.

A `recipe-path` adds `transition_ids` and `steps`. Each step contains exactly
`edge`, `args`, `request`, `bindings_before`, and `bindings_after`. The checker
must verify that each argument is a legal literal/public-binding recipe,
reconstruct the JSON request, replay guards and atomic updates, verify graph
edges/horizon and check every invariant and the final goal.

A `refinement-exhaustion` adds `refuted_prefixes`, a list of transition-ID
lists. The checker proves each listed prefix has no known or unknown legal
lift, checks complete declarations/freshness and verifies bounded abstract-goal
coverage. A list of claimed failed edges without context is insufficient.
Unknown results have no certificate.

The independently implemented direct reference may emit a separate
`relational-exhaustion` certificate containing exact refined-product layers.
Different proof formats do not give different input evidence or action spaces.

## Fair comparison and demonstration

The mandatory comparator is direct same-evidence forward relational search
over `(abstract_state, depth, complete_public_frame)`, with memoization of
repeated relation/frame evaluations and safe backward goal-cone analysis.
It receives the same constructor language, finite recipes, bounds, bindings,
freshness and coverage. Give it no pre-expansion or cold-cache handicap.
The four-method pilot implements this comparator as `direct_pruned`, using
[direct_goal_pruned_v2.py](../../src/interoperability/direct_goal_pruned_v2.py).
Its `baseline` arm is the preserved same-input relational-product solver and
a historical control; it also checks relations and is not abstraction-only.
A separately labelled abstraction-only finite BFS is a weaker control. It was
not run as an arm of the four-method pilot.

Demonstrate a legal typed/raw distinction, fixed-header obstruction, correct
task/context/call/target correlation, an unavailable public binding, an opaque
generated value, an alternative that succeeds after another is refuted, and
a context in which a previously failing edge becomes legal. Use independently
authored adversarial profiles and compare actual decisions/certificates and
full costs. Keep authored, source-adapted and observed data labels separate.
The [pilot coverage map](shared-lifting-pilot-results-v1.md#demonstration-coverage)
identifies which of these obligations the measured examples cover and which
remain partial or missing; the list above is not a claim of completed coverage.
No held-out sample, native execution, two-domain qualification, scientific
novelty, C1 pass or 70% completion follows merely from these examples.
