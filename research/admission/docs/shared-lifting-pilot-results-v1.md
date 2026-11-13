# Shared-lifting engineering pilot: 29 October 2026

The shared-lifting implementation and four-method benchmark ran successfully.
All four budget bundles passed verification, with **349 worker jobs and 109 accepted
certificate checks**. The [independent result audit](../../runs/shared-lifting-pilot/independent-result-review-v1.json)
reconciled all 1,897 manifest-listed files and all 1,989 allocation files stayed
unchanged during review. No discrepancy, worker error or rejected certificate
was recorded, and the frozen source/input guards stayed unchanged. Shared lifting remains an
experimental option: it reduced repeated relation evaluation, but its added
cache work reduced conclusive coverage at smaller declared budgets.

This pilot uses all eleven original recipe examples plus `scale-0031`, the
previously observed stress case that motivated caching. That extra case was
deliberately selected; the twelve cases are authored development inputs, not a
held-out or representative application study. The existing
[66-case three-method results](refinement-scaling-results-v2.md) are unchanged.

The mandatory fair comparator is `direct_pruned`: same-input memoized
relational-product search with remaining-horizon goal-cone pruning. Legacy
direct (`baseline`) is a historical same-input control and the disclosed
reference, not the decisive superiority comparator. Both direct arms check
the supplied relations. A separately labelled abstraction-only finite BFS
was not run in this pilot; it is not one of the four columns below.

## Demonstration coverage

This map refers to the measured profiles in the retained high-budget bundle
and their [case results](../../runs/shared-lifting-pilot/v1/budget-100000/results.jsonl).
Every conclusive result listed here was accepted by its separate checker at
100,000 units. These are authored finite-model demonstrations; the map does
not qualify actual typed/raw clients, source-generated values or application
task identity.

| Prototype demonstration requirement | Measured case evidence | Coverage and remaining limit |
| --- | --- | --- |
| Legal typed/raw distinction | [direct-public-binding](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0000.json) is supported; [fixed-text-shape-obstruction](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0001.json) is unsupported | Partial: a structured `data` object satisfies the guard, while JSON-looking text does not create those fields. An actual typed-versus-raw API pair was not demonstrated. |
| Fixed-header obstruction | [raw-parameters-without-version-header](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0004.json) is unsupported; [explicit-header-configuration](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0005.json) is supported | Covered within supplied models: the first request cannot emit the required `A2A-Version`; the second profile explicitly emits `1.0`. This is a declared configuration contrast, not a live header experiment. |
| Task/context/call/target correlation | [correlated-prefix-refinement](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0003.json) is supported | Partial: correlated `call` and `target` frames are exercised. The profile contains no task/context identity fields, so those obligations remain missing. |
| Unavailable public binding | [missing-public-binding-partial-coverage](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0002.json) is unknown | The recipe refers to absent `public_call`, and declared coverage is also incomplete. The result abstains without a certificate; it does not isolate the effect of missing binding from incomplete coverage. |
| Opaque generated value | [opaque-serialization](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0006.json) is unknown | Partial: an explicitly unknown emitted request prevents a concrete witness. No source-generated identifier or native opaque-value exchange was observed. |
| Alternative succeeds after another is refuted | [correlated-prefix-refinement](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0003.json) is supported | The declared bad prefix cannot satisfy the final guard. The retained candidate records a refinement and returns the checked `b_good_binding`, `finish` witness. |
| A previously failing edge becomes legal in another context | [correlated-prefix-refinement](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0003.json) | The same `finish` edge fails for the `call-A`, `B` frame and succeeds for `call-B`, `B`; the edge is not globally deleted. This is binding-frame context, not a demonstration of application task/context identity. |

[working-state-blocks-second-answer](../../runs/shared-lifting-pilot/v1/budget-100000/inputs/case-0009.json)
separately returns unsupported after the first answer changes `phase` from
`waiting` to `working`. It demonstrates a phase obstruction, not recovery of
a previously failing edge. The other cases exercise atomic binding updates,
uncertain contracted observables, stale evidence and the selected reconvergence
stress case. Independent adversarial task/context and typed/raw route coverage
remain work to complete; case names alone do not establish it.

## Certificate-validated coverage

Every count includes all twelve planned cases in the denominator. Unknown is a
valid abstention, not a negative decision or an accepted certificate.

| Work budget | Legacy direct | Goal-pruned direct | Original refinement | Shared lifting |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 6/12 | 6/12 | 6/12 | 0/12 |
| 256 | 8/12 | 8/12 | 7/12 | 6/12 |
| 4,096 | 8/12 | 8/12 | 7/12 | 7/12 |
| 100,000 | 8/12 | 8/12 | 8/12 | 8/12 |

At 100,000, all four methods return **4 supported, 4 unsupported and 4 unknown**.
The shared solver's persistent unknowns retain incomplete coverage, opaque
relations, uncertain contracted observables and stale evidence. At lower budgets,
additional cases exhaust their work allowance. Every outcome and reason remains
in the [complete result](../../runs/shared-lifting-pilot/v1/result.json).

Work units are method-specific operations, not equal hardware costs. Shared
lifting explicitly charges cache keys, lookups, payload traversal and histories
in addition to the preserved search charges. This table compares the declared
meters; it does not establish a CPU-speed ranking.

## What happened in the motivating case

All methods certify `scale-0031` as unsupported at the largest allowance.

| Method | Relation work | Search size | Solver work units |
| --- | ---: | ---: | ---: |
| Legacy direct | 16 assignments | 4 product states | 134 |
| Goal-pruned direct | 16 assignments | 4 product states | 134 |
| Original refinement | 1,024 checks | 256 abstract paths | 5,566 |
| Shared lifting | 16 checks | 256 abstract paths | 14,773 |

The new solver records 16 complete relation-cache entries and 324 hits, plus
341 prefix-cache entries and 255 hits. Its key and payload work contributes
4,901 and 4,447 units respectively. Reuse removes duplicate relation evaluation,
but all 256 paths and refutations remain. The unchanged negative checker still
reconstructs the proof without the solver cache. These observations support
retaining shared lifting for inspection and further engineering, without
promoting it as an efficiency improvement.

## Retained time and memory observations

The following are totals over all twelve cases at budget 100,000. Each method
has twelve solver workers and eight certificate workers. The reference and
outer coordinator are recorded separately. These are single observations in
fixed method order on a resource-constrained host; differences are not speed
or memory-superiority evidence.

| Method | Solver function, ms | Checker function, ms | Solver + checker worker wall, s | Maximum process peak, MiB |
| --- | ---: | ---: | ---: | ---: |
| Legacy direct | 17.099 | 6.216 | 5.889 | 21.68 |
| Goal-pruned direct | 5.641 | 4.116 | 5.904 | 21.76 |
| Original refinement | 11.418 | 37.619 | 5.262 | 21.80 |
| Shared lifting | 16.420 | 27.163 | 4.962 | 21.79 |

The smaller shared-lifting worker-wall total is one fixed-order observation on
the constrained host. It establishes neither a speed ranking nor a memory
advantage; this table contains no repetitions or statistical uncertainty estimate.

Function timings are contained within worker wall time; do not add those columns.
Worker wall includes process startup, imports and output. Process memory is the
OS high-water observation before final reply output, including interpreter and
input overhead; the table reports a maximum across workers, not their sum or
solver-only allocation. All eighty method/checker workers in this high-budget
slice have a memory observation. The independent audit confirmed observations
for all 349 pilot workers, with none missing. Other budgets, reference workers, preparation,
serialization, missing counts and per-case observations remain in the raw result.
See the [measurement contract](shared-lifting-comparison-v3.md).

Historical worker records retain their original absolute Windows paths. Those
paths are not normalized by this documentation update: rewriting retained
records would change their evidence bytes. Portable path presentation for
future outputs remains a separate implementation task.

## Evidence and demonstration

- [Prospective plan](../../runs/shared-lifting-pilot/v1/plan.json), SHA256
  `8c66caa0467f09588a533019526df2401f1ac526cd53b7aa364961bffe612265`.
- [Complete result and eight command receipts](../../runs/shared-lifting-pilot/v1/result.json).
- Bundle summaries at [32](../../runs/shared-lifting-pilot/v1/budget-32/summary.json),
  [256](../../runs/shared-lifting-pilot/v1/budget-256/summary.json),
  [4,096](../../runs/shared-lifting-pilot/v1/budget-4096/summary.json) and
  [100,000](../../runs/shared-lifting-pilot/v1/budget-100000/summary.json).
- [Prospective independent review](../../runs/shared-lifting-pilot/source-review-v1.json)
  verified exact membership and all 51 originals and 51 snapshots before execution.
- [Independent result reconciliation](../../runs/shared-lifting-pilot/independent-result-review-v1.json),
  SHA256 `fbf07438a0f58aa921a309f7a27705e45c76dc73b6f3d97c8608b71e634e69b7`.
  This read-only audit invoked no project code, tests, solvers, checkers or replay.
- [Algorithm, software tests and comparison source reviews](shared-lifting-comparison-v3.md).

The twelve-case allocation is consumed. Do not rerun its driver. Read-only
verification of the retained high-budget bundle uses its captured source:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'runs/shared-lifting-pilot/v1/source'
python -B -m interoperability.shared_lifting_comparison_v3 verify runs/shared-lifting-pilot/v1/budget-100000
```

**10 November reproduction:** the [complete twelve-case pilot was replayed at
all four budgets](shared-lifting-pilot-reproduction-v1.md) from captured source
in a fresh allocation. All 192 algorithm evaluations matched original decisions,
reasons, certificates and deterministic counters; 349 fresh worker jobs included
109 accepted certificate checks. All 1,989 original allocation files stayed
unchanged. Timing and memory remain separate host observations. The earlier
two-case harness and read-only audit retain their original scopes; supervisor
or task/gold approval is not inferred.
The preserved [larger comparison](refinement-scaling-results-v2.md) provides
additional development measurements. The live-startup gap remains in the
[v4 report](pending-admission-live-results-v3.md). No application success,
algorithmic novelty, 70% completion or supervisor extension follows from this pilot.
