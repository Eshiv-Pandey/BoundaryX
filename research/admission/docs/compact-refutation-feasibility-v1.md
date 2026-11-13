# Compact refutation feasibility review v1

11 November 2026. Static technical review by Codex, `/root/compact_refutation_feasibility`.

A compact DAG can encode the current exact-prefix refutation cover without changing its meaning. A separately authored checker can also avoid the current repeated scan of every refuted prefix during abstract coverage checking. This is a feasible engineering experiment. It does not establish a new admission principle, better empirical coverage, a smaller proof than the strongest direct comparator, or completed research work.

No solver, application, provider, benchmark, certificate checker or external experiment was executed in this review. The [structured review](compact-refutation-feasibility-v1.json) binds the files read. Prior results are cited at their existing disclosed scope.

## What the current certificate proves

[Shared lifting](../../src/interoperability/refinement_shared_lift_v2.py) publishes `refinement-exhaustion` with a list of exact transition-ID prefixes. It shares complete `(edge ID, whole typed binding frame)` relation expansions internally, but emits the original path-list proof. Prefixes remain exact histories: failure after one binding history cannot delete an edge for another history.

The independently implemented [checker](../../src/interoperability/refinement_oracle.py), `check_certificate` at line 449, first binds the profile hash, integer clock, horizon, expiry and complete coverage. Its `_topology` pass preserves conservative observable uncertainty. For every listed prefix, `_lift_prefix` independently expands every permitted argument assignment and every correlated frame. A refutation is accepted only when its final frame set is empty and its sticky uncertainty flag is false. The checker then explores all bounded invariant-permitted abstract paths and requires each possible goal path to have a refuted prefix. Checking is bounded by 2,000,000 declared checker work units; exhaustion rejects a certificate.

The relevant quantification is universal over all declared argument choices and correlated frames when proving an empty prefix, followed by universal coverage of possible abstract goal paths. An existentially rejected tuple does not establish either condition. The proof remains conditional on the supplied finite recipe model and complete-coverage declarations.

## A precise first successor schema

Use a new certificate kind, for example `refutation-cover-dag/1`. Keep the current `profile_sha256`, `checked_at`, `horizon` and `valid_until` fields. Add exactly `root` and `nodes`. Each node has exactly:

```json
{"terminal": false, "arcs": [{"edge": "declared-edge-id", "next": 1}]}
```

`nodes` is an indexed list, `root` is integer zero, `terminal` is a Boolean and `arcs` is a sorted list with unique transition IDs. Every reference must name a later node, making the representation acyclic. Require all nodes to be root-reachable, all edge labels to exist in the bound profile, no root terminal and no terminal with outgoing arcs. Require every accepted word to have length 1 through the declared horizon. Set explicit node, arc, expanded-prefix, serialized-byte and checker-work bounds before execution; these are proposed requirements, not measured bounds from this review.

The represented refutation language is the set of root-to-terminal edge words. First form the exact-prefix trie; then hash-cons nodes with identical terminal flags and identical labeled child lists. Identical suffix languages can share one node. This transformation preserves the prefix-word set; it must never merge nodes just because their final graph state or edge label agrees. If an existing cover contains a longer prefix already covered by a shorter refuted prefix, that redundancy can be removed after the shorter refutation is independently checked. The resulting certificate need not preserve the old list ordering, but it preserves the negative claim.

The unchanged checker rejects this new kind and its extra fields. Keep it frozen. Implement a new checker or a bounded lossless expansion adapter in new versioned files. An adapter that expands all words back into `refuted_prefixes` provides a simple semantic comparison, but does not avoid expansion or the old checking cost.

## Independent checking with two separate obligations

1. **Refutation validity.** Independently replay every represented prefix from the original initial frame using the declared argument domains, emitted request expressions, guards and atomic updates. Accept its terminal only if every resulting frame is absent and no indeterminate request, guard or update occurred earlier in that prefix. Publish no partially expanded memo entry. A shared terminal is a language node, not a statement that all incoming concrete contexts are equal.
2. **Abstract cover validity.** Check inclusion of the bounded possible-safe-goal language in the prefix closure of the validated refutation language. Traverse the product `(abstract state, depth, proof-DAG node-or-dead)`; a previously validated terminal enters an absorbing `covered` status. A missing proof arc enters `dead`, which must continue exploring graph alternatives rather than discard them. Reject any uncovered possible goal, including an initial goal and a goal reached on a cyclic path within the horizon. Memoizing these finite product states removes repeated abstract-prefix comparisons without assuming concrete binding equality.

The second phase is ordinary bounded automata-language inclusion. Its sharing is safe only after the first phase has validated every accepted refutation word. The first phase may still have exponentially many distinct incoming words despite a small DAG. Thus fewer serialized proof bytes or a faster coverage pass does not imply an inexpensive entire checker.

To share first-phase concrete replay, a safe call-local memo key must contain the profile identity, exact graph state, depth or remaining horizon, the complete type-preserving correlated frontier as a canonical set, sticky relation uncertainty, and applicable path-contract status. Clock and expiry remain bound to the whole invocation. Relation summaries may omit witness history only because the current DSL reads arguments, emitted request values and the full current frame, not an implicit path history. Any history-dependent external obligation must first be represented in the model/frame or the equivalence argument does not apply. For a positive witness, independently reconstruct the actual incoming history; do not return a cached history from another route.

Before accepting any negative, recompute the existing global contract-uncertainty and completeness checks. A later known-false relation does not erase an earlier unknown. Distinguish `true` from `1`, missing bindings from explicit `null`, and complete empty domains from interrupted enumeration. Do not treat generated unknown values as freely choosable existential variables.

## Concrete unsafe-sharing counterexample from current source

The existing `correlated_profile` in [test_refinement.py](../../tests/test_refinement.py), line 64, has horizon two and two transitions into the same `ready` state:

| Incoming prefix | Correlated frame at `ready` | Result of `finish` |
| --- | --- | --- |
| `a_bad_binding` | `{"call":"call-A","target":"B"}` | Rejected: emitted call is not `call-B` |
| `b_good_binding` | `{"call":"call-B","target":"B"}` | A declared concrete goal witness |

The finish relation draws both caller arguments from that same frame and requires emitted `call == call-B` and `target == B`. A naive DAG/checker keyed only by `(ready, finish)` can replay the first branch, store an empty finish result, and reuse that refutation on the second branch. It would incorrectly certify unsupported even though `b_good_binding, finish` is a real modeled witness. Current tests explicitly reject globalized `finish` refutations and the incomplete cover `a_bad_binding, finish`. This is a source-derived correctness argument; those tests were read, not rerun here.

The related existing adversarial test changes the second frame's target to `A`. Both whole frames then fail, but a coordinate-wise merge can fabricate `call-B,target-B` and a false positive. Sharing must preserve whole correlated frames in both directions.

## Comparator and implementation decision

The strongest executed aggregate comparator is [goal-pruned memoized direct search](../../src/interoperability/direct_goal_pruned_v2.py), with an independently reconstructed negative product cut. It already shares `(state, depth, whole frame)` reachability and closes only the remaining-horizon goal cone. A concrete-frontier DAG that proves complete successor closure is largely another encoding of that product. Compare against its existing compact cut, not only against the shared-lifter path list.

The [current contribution assessment](method-contribution-assessment-v2.md) reports the retained `scale-0031` proof as 8,895 bytes for shared lifting versus 338 for goal-pruned direct. Those numbers motivate a compression experiment, but are not results for this unimplemented design. Memoization, trie minimization, bounded automata inclusion and product reachability do not themselves supply a distinct technical contribution.

The smallest useful implementation sequence is: a new bounded codec and checker; a versioned shared-lifter successor emitting the DAG; independently audited lossless-language and decision comparisons on the existing development corpus; mutation checks for dangling/cyclic nodes, missed alternative words, false empty terminals, typed frame confusion, unknown clearing and clock/profile changes; then a separately frozen comparison against goal-pruned direct. Charge codec construction, key traversal, serialized bytes, concrete replay, cover checking and checker refusal rates. Use actual process time/resources only in a fair, prospectively ordered run. Keep positive certificates unchanged initially.

Touchpoints are the shared lifter's `refinements`/trie publication in `evaluate`, the oracle's negative-kind dispatch and `_lift_prefix`/coverage loop, and the scaling runner's certificate-size/refutation counters and checker-entrypoint dispatch. Existing algorithm files, proof kinds, captured outputs and historical comparisons must remain frozen. Until that implementation and evaluation exist, this review adds a concrete design and counterexample, not an admission result, novelty pass or project-completion credit.
