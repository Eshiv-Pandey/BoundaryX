# Four-method scaling results v3: 10 November 2026

The complete four-method comparison of the **same 66 frozen development profiles
at all four original budgets** finished once. All eight run/verify commands
returned zero. The four budget bundles passed the captured v3 verifier, with
**2,003 worker jobs and 683 accepted certificate checks**. No worker error,
timeout, rejected certificate or source/input mutation was recorded.

The original three methods reproduced all **792 deterministic arm results**
from v2: decisions, reasons, certificates, solver counters and checker acceptance
match. Internal elapsed-time fields are excluded from deterministic equality.
Shared lifting never adds a certified case beyond goal-pruned direct in this
matrix, and it loses coverage at the smaller budgets.

## Fixed inputs and fair comparison

The original suite order, profile bytes and logical evaluation clock 100 are
unchanged. Methods receive identical relations, legal recipes, correlated binding
frames, contract, horizon and freshness/coverage declarations. The 21-file
captured pilot package is unchanged; all 18 files shared with v2 are byte-identical.
Legacy direct is the historical control and disclosed reference. Goal-pruned
memoized direct is the strongest same-input comparator in this experiment.

These 66 related authored variants cover argument products, layered reconvergence,
correlated frames, horizon boundaries and off-goal load. They are development
evidence, not independently authored held-out templates or application gold.

## Certified coverage

Every cell includes all 66 planned profiles. Unknown remains in the denominator
and has no accepted certificate.

| Work budget | Legacy direct | Goal-pruned direct | Original refinement | Shared lifting |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 12/66 | 20/66 | 24/66 | 2/66 |
| 256 | 52/66 | 54/66 | 50/66 | 39/66 |
| 4,096 | 54/66 | 54/66 | 53/66 | 53/66 |
| 100,000 | 54/66 | 54/66 | 54/66 | 54/66 |

At 100,000, every method returns **28 supported, 26 unsupported and 12 unknown**.
At budget 256, shared lifting certifies 3/16 correlated-frame cases versus
12/16 for goal-pruned direct, and 6/16 reconvergence cases versus 12/16.

| Budget | Both direct/shared certified | Direct only | Shared only | Neither |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 2 | 18 | 0 | 46 |
| 256 | 39 | 15 | 0 | 12 |
| 4,096 | 53 | 1 | 0 | 12 |
| 100,000 | 54 | 0 | 0 | 12 |

## Work and proof representation

At 100,000 all arms certify the same 54 profiles. Solver totals below include
all 66 attempts, including unknowns. Work units charge method-specific operations;
they are not equal hardware costs or total solver-plus-checker work counters.

| Method | Solver work units | Total certificate bytes | Largest certificate, bytes |
| --- | ---: | ---: | ---: |
| Legacy direct | 4,292 | 20,064 | 879 |
| Goal-pruned direct | 3,382 | 19,880 | 893 |
| Original refinement | 14,518 | 27,248 | 8,895 |
| Shared lifting | 46,840 | 27,248 | 8,895 |

Certificate size uses UTF-8 JSON with sorted keys, compact separators,
`ensure_ascii=False` and `allow_nan=False`. Unknown has null size, not a
zero-byte proof. All 54 high-budget shared-lifting certificates have the same
canonical hashes as original refinement. The frozen checker returns a boolean;
its internal work counters are unavailable. Its allowance remains 2,000,000,
with every checker invocation bounded by the same 30-second worker timeout.

For `scale-0031`, four stages each have four parallel edges, one shared empty
binding frame, and false final guards. Original/shared lifting inspect 256
abstract paths and retain 256 length-four refutations. Shared lifting reduces
relation checks from 1,024 to 16, but solver work rises from 5,566 to 14,773.
Both proofs remain 8,895 bytes; goal-pruned direct uses four product states,
16 assignments, 134 solver units and a 338-byte proof. Its full charged topology
work is included. Prefix caching therefore removes repeated relation evaluation
without compressing this path-list proof. This is an implementation/representation
limitation, not a general lower bound for CEGAR or symbolic methods.

## Timing, memory and preservation

At 100,000, solver-plus-checker worker-wall sums were 16.689/16.861/16.538/16.896
seconds for legacy/direct/refinement/shared. These are single observations in
fixed order on the current host, not a speed ranking. Worker wall includes
startup/import/output; function and worker-body times overlap it and are not
added. Reference and coordinator costs are separate. All 2,003 workers have
memory observations; none is missing. OS process peaks include interpreter and
input overhead and are not summed across sequential workers.

Before/after guards preserved all 142 monitored original files and 93 snapshots,
including source/input tree membership. The allocation contains 10,516 files.
Existing v2 and pilot captures remain unchanged; this new allocation is consumed.

- [Prospective plan](../../runs/shared-lifting-scaling/v3-20261110-1/plan.json), SHA256 `8908356aa597363359084b641bf9ea3f79003c91337431c6671b404e811b5d8e`.
- [Complete result](../../runs/shared-lifting-scaling/v3-20261110-1/result.json), SHA256 `f0ec201cf13ed4cacfd1eadc80c2700a9c562f2f5e6f3c4fb2efa02a7ec53401`.
- [Driver](../../scripts/run_shared_lifting_scaling_v3.py) and [prospective method/measurement contract](shared-lifting-scaling-plan-v3.md).

This is a verified development comparison with a concrete cache/proof-cost
tradeoff. It establishes neither algorithmic novelty nor application-domain
qualification, a held-out study, human scientific approval, a checkpoint pass
or project completion. No application, SDK, credential or model was executed.
