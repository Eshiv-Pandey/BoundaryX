# Direct comparator goal-pruning correction

The preserved v1 matrix measures the implementations it captured, but its
off-goal low-budget differences do not establish a candidate algorithm advantage.
The direct comparator computes a bounded safe may-goal cone in `_topology` and
uses it only to suppress irrelevant relation uncertainty. Its forward solver
still enumerates argument tuples and builds frames on definitely dead branches.
This falls short of using goal-cone analysis to prune the direct search.

In captured `scale-0064`, the horizon is one. Four dead branches each have two
four-choice arguments; a separate goal edge occurs last. The original direct
solver records 65 assignments, 193 expression evaluations, 21 graph-edge ticks
and nine state-expansion ticks: 288 work units. The candidate records one lifted
relation and 30 units. The 64 dead assignments and their 192 expression
evaluations account for 256 avoidable direct units. The matrix and captured
sources are retained without rewriting those results.

The original direct solver already evaluates goal-edge tuples lazily and returns
at the first feasible witness. No eager goal-tuple short-circuit defect was found.
The new `interoperability.direct_goal_pruned_v2` preserves that behavior, complete
correlated frames, relation/frame memoization, the original clock and coverage
rules, and conservative contracted-observable uncertainty. It prunes a relation
before argument enumeration only when its target is outside the possible-goal
cone for the remaining horizon. The full topology pass and every inspected
outgoing edge retain their existing work charges. Counter units remain specific
to each implementation; equal budgets are not identical hardware work.

Positive `recipe-path` witnesses remain compatible with the old independent
checker. A pruned negative has different product layers from the original full
product, so relabeling it as the old `relational-exhaustion` would be incorrect.
Its explicit new kind is `goal-pruned-relational-exhaustion/2`. The new checker
reconstructs exact depth-by-depth closure from the known initial frame, checking
all goal-relevant relation assignments without calling either solver. It
recomputes the cone and rejects missing/extra frames, feasible goals, relevant
unknown relations, stale evidence and incomplete or uncertain negative models.
It delegates the existing proof kinds to the preserved checker.

A comparison runner must explicitly capture this module and select its checker
for new negative certificates. It must capture every solver and certificate
invocation, including abstentions, timeouts and checker rejection, against the
same frozen profiles, logical clock and stated work allowances. The existing
benchmark's fixed recipe checker cannot accept the new proof kind. No generated
matrix rerun or performance/novelty claim is authorized by this implementation
note alone; the next comparison requires a prospective frozen plan.
