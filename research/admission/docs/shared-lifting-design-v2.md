# Shared lifting engineering design, v2

Status: implemented and checked by the captured 23-test software run linked
below. The original design was proposed on 2026-10-29. This is one bounded
engineering adaptation of the existing witness-lift/refine candidate, using
ordinary memoization. It establishes neither a new algorithmic contribution nor
comparative advantage. The [twelve-case engineering pilot](shared-lifting-pilot-results-v1.md)
is now complete: relation reuse reduced duplicate checks but added cache work
and lowered coverage at smaller declared budgets. Shared lifting remains
experimental. No new 66-case matrix or live application execution was run.

## Target and boundary

In [refinement.py](../../src/interoperability/refinement.py), `_lift` starts from
the initial bindings for every abstract goal path. Reconvergent paths therefore
repeat both prefix lifting and identical relation evaluations. The retained
[v2 comparison](refinement-scaling-results-v2.md) reports that `scale-0031` uses
256 candidate paths, 1,024 relation checks and 5,566 solver units, versus four
product states, 16 assignments and 134 units for the corrected direct method.
Those are existing observations, not new measurements.

The implementation is [refinement_shared_lift_v2.py](../../src/interoperability/refinement_shared_lift_v2.py), leaving `refinement.py`,
`refinement_oracle.py`, `direct_goal_pruned_v2.py` and frozen artifacts intact.
Keep the candidate's abstract path enumeration, goal-first lifting, exact-prefix
refinement trie and decision rules. Add a call-local shared-lift memo with two
indexes. Do not replace the search with the direct solver's `(state, depth,
frame)` work queue, merge paths by graph state, or learn global edge exclusions.

## Exact cache contents

| Index | Key within one validated `evaluate(profile, now)` call | Complete stored value |
| --- | --- | --- |
| Prefix | Exact tuple of transition IDs from the initial state | Endpoint and depth; map of canonical whole frame to frame plus one witness history for this exact prefix; sticky uncertainty bit; `contract_known` bit; terminal empty-frontier disposition if applicable |
| Relation | Transition ID and canonical whole input frame | Distinct known successor frames with one local concrete step each, plus a bit recording any indeterminate assignment; complete-domain marker |

Canonical frame keys use the existing sorted, compact JSON encoding. They retain
every binding and distinguish `true`, `1`, null and an absent key. Do not use
ordinary Python scalar equality as the frame key, project away bindings, pool
binding values across frames, or put UNKNOWN/ABSENT into concrete frames.

A relation entry summarizes only the supplied deterministic relation under its
complete before-frame. Its local step contains args, emitted request, before and
after bindings, and edge identity; it contains no prior path history. Rejected
assignments need not be stored, but every legal assignment must have been
evaluated and charged before the complete-domain marker is published. Empty
argument domains can yield a complete empty summary. Duplicate recipe choices
retain current evaluation order and construction charges; this version adds no
separate argument-domain optimization.

Prefix summaries are context-bound, even when two different prefixes produce
the same frames. They include the exact depth, so cycles do not confuse a
remaining-horizon claim. Relation summaries are depth-independent because their
key denotes only one local supplied relation; they carry no claim about future
goals, refutability or horizon. Both indexes are discarded after the invocation.
Freshness is checked before reuse is possible; profile digest, contract,
coverage, horizon and evidence rules remain unchanged.

## Lifting procedure

1. Start with the initial prefix summary. For a selected abstract goal path,
   retrieve the longest previously completed exact-prefix summary; charge every
   lookup and key operation. An empty terminal summary preserves its original
   `refuted` or `unknown` result and does not create successor summaries.
2. For each remaining edge and each whole input frame, look up its complete
   relation summary. On a miss, stream the current legal assignments and use the
   unchanged expression/guard/atomic-update semantics. A false guard still
   dominates unknown values in that assignment.
3. Combine all known successors into the next correlated frontier, retaining
   the first representative history for each exact frame. Append a cached local
   step to the current prefix's history, never to a history cached for another
   path. Immutable predecessor nodes can share histories; charge their creation
   and eventual witness materialization.
4. Preserve sticky relation uncertainty and invariant uncertainty separately
   from the existence of known frames. An empty frontier with any sticky
   uncertainty is `unknown`; only a definitely empty entire prefix is refuted.
   A known safe witness can still succeed when another assignment is unknown.
5. Preserve the first-feasible-tuple return on a final known-safe goal edge.
   Proper-prefix summaries require complete expansions; the final edge remains
   streaming on a miss. An early witness or budget interruption never publishes
   an incomplete entry. A previously complete entry may supply a concrete final
   step immediately. The zero-edge initial-goal case stays unchanged.

The full conservative contracted-observable pass remains in place, including
unknown observables on potentially safe reachable dead branches. Relation
uncertainty is encountered through the same bounded abstract goal paths as v1.
Incomplete evidence/coverage, stale evidence and budget exhaustion keep their
existing conservative outcomes. Exhausted cached summaries do not authorize
uncertainty removal or extrapolation beyond the declared finite recipes.

## Certificates and costs

Keep the existing `recipe-path` and `refinement-exhaustion` schemas. A negative
certificate still lists exact refuted prefixes, even if their lifting reused
relation entries. Use the unchanged independent
[refinement_oracle.check_certificate](../../src/interoperability/refinement_oracle.py).
It reconstructs positive steps and re-lifts every negative prefix from the input;
it receives no solver cache. No new certificate kind or trusted cache digest is
needed for this bounded version. A checker-budget failure remains an uncertified
result, never an accepted negative.

Retain existing candidate work charges and add explicit categories for cache
lookups, canonical-key components, cache insertion, replayed prefix frames,
replayed relation successors, history construction and witness materialization.
Charge every input binding/key component and every stored/replayed step payload
node that is copied or traversed. Charge an entry/status operation even for an
empty cache hit. Account for full assignment/expression evaluation on misses;
cache publication occurs only after all corresponding charges succeed. Include
cache entry/frame peaks, preparation, digest/serialization and checker time in
the retained runtime/memory measurements. Auxiliary peak counts are not extra
work ticks. Declare these method-specific units; do not equate them with the
direct solver's hardware cost.

Certificate cost can erase the practical savings. Prefix enumeration and the
number/size of refuted prefixes remain exponential in branching and horizon.
The unchanged negative checker repeats relation lifting and scans its prefix
cover; it does not inherit the new solver cache. Even if distinct relation
expansions approached 16 in `scale-0031`, the candidate would still account for
256 paths, cache overhead and the existing negative proof. There is no basis to
predict a win over the 134-unit corrected direct solver. Report solver work,
certificate generation/checking, total time and peak memory separately, then
end-to-end together. Do not retain only solver time as the claimed improvement.

## Adversarial checks before any comparison

The existing `correlated_profile()` supplies the essential global-edge trap:
`a_bad_binding` reaches `ready` with `{call: call-A, target: B}`;
`b_good_binding` reaches the same state with `{call: call-B, target: B}`.
`finish` requires `call-B` and `B`. Failure after the first prefix cannot refute
`finish` globally: the second prefix is supported. Its relation-cache keys must
differ. Changing the second target to `A` makes both paths impossible; pooling
`call-B` from one frame with `B` from the other would forge a positive.

Focused v2 checks should also cover identical-frame reconvergence with different
witness histories; cycles reaching the same frame at different depths; unknown
followed by an empty frontier; false-guard dominance; atomic old-frame updates;
boolean/integer/null/absent-key distinctions; stale/changed-profile rejection;
partial coverage; tiny budgets on empty hits; and first-tuple goal success in a
large finite domain. Tamper with cached-path witness prefixes, requests, frames,
refuted-prefix membership and horizon/freshness headers and require the unchanged
checker to reject them. Check that budget interruption never exposes a complete
entry. These are desired boundaries, not a claim that every combination of
mutations was exercised; the test source and captured log specify the actual
executed cases.

A read-only independent design review checked these cache, uncertainty, history
and canonicalization boundaries; it supplied no runtime evidence. Proceed only
as a small versioned experiment. Any new matrix needs a fresh prospective plan,
new outputs and captured candidate/checker bytes while retaining the existing
three-method results. If cache overhead and checking erase the benefit, report
that result and retain the corrected direct solver as the stronger comparator.

## Implementation evidence

[Focused tests](../../tests/test_refinement_shared_lift_v2.py) contain 23 authored
software cases. One initial 22-test development run passed; after source review,
a further test was added for a cached final-goal relation first exhausted under
an uncertain invariant history and then reused by a fully known safe history.
The [final once-only receipt](../../runs/refinement-shared-lift-software/v2/validation-1/result.json)
records all 23 tests passing from eight copied and hashed source/test files.
The [request](../../runs/refinement-shared-lift-software/v2/validation-1/request.json),
[raw test log](../../runs/refinement-shared-lift-software/v2/validation-1/stderr.log)
and [capture program](../../runs/refinement-shared-lift-software/v2/validation-1/capture.py)
are retained. Do not rerun that consumed allocation.

The final module SHA256 is
`927538f7ddcb21120913c6c4257754b65a45703db384eec8cd6a28ba9e9b280b`;
the final test SHA256 is
`d0378383be48abcee894feae27cbe307acd797012cf2cb77102c43b855abd9e8`.
Captured source, workspace dependencies and the preserved solver/oracle/direct
files remained unchanged through the run. The [independent source review](../../runs/refinement-shared-lift-software/v2/source-review-v1.json)
found no blocking semantic or metering issue in these solver bytes. Test-reported time
was 0.024 seconds; whole child-process elapsed time was 1.1420536 seconds. These
are a software validation receipt, not a comparative speed measurement, matrix
result, held-out study, or native-protocol qualification. The existing negative
checker still repeats prefix lifting and can erase solver-cache savings.
