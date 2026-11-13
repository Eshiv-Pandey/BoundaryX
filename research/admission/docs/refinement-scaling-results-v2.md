# Three-method development benchmark results, v2

The admission candidate and corrected comparison benchmark completed all **66 authored development profiles at four fixed budgets**. All four bundles passed the versioned verifier, with **1,591 worker invocations and 535 accepted certificate checks**. There were no worker errors, timeouts, rejected certificates or input mutations. The frozen plan, package and inputs remained unchanged.

**The candidate does not consistently outperform the corrected direct solver.** It certifies four additional cases at budget 32, while the corrected solver certifies four additional cases at 256 and one at 4,096. At 100,000 all three methods give the same decisions: **28 supported, 26 unsupported and 12 unknown**. These results support a working development implementation and expose its tradeoffs; they do not establish scientific novelty, application-domain qualification or general superiority.

## Certified decisions

Each cell gives checker-accepted conclusive results out of all 66 cases. Unknowns remain in the denominator.

| Work budget | Legacy direct | Goal-pruned direct | Refinement candidate |
| ---: | ---: | ---: | ---: |
| 32 | 12/66 | 20/66 | 24/66 |
| 256 | 52/66 | 54/66 | 50/66 |
| 4,096 | 54/66 | 54/66 | 53/66 |
| 100,000 | 54/66 | 54/66 | 54/66 |

The paired comparison below uses the actual `candidate` and `direct_pruned` arms. Reference decisions still come from the budgeted legacy direct solver; a reference abstention is not a false result. The generic engine counts two non-baseline alternatives, but only the arm named `candidate` is the refinement candidate.

| Budget | Both certified | Candidate only | Pruned direct only | Neither certified |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 20 | 4 | 0 | 42 |
| 256 | 50 | 0 | 4 | 12 |
| 4,096 | 53 | 0 | 1 | 12 |
| 100,000 | 54 | 0 | 0 | 12 |

At the largest budget, all methods match the external authored sufficient-budget expectations. Those labels are finite-semantic development assertions, kept outside the solver inputs; they are not independently observed application ground truth. The 12 persistent unknowns retain opaque relations.

## Coverage by family

Each cell is `goal-pruned direct / candidate` certified count. The variants within a family are related, not independent workload samples.

| Family (cases) | 32 | 256 | 4,096 | 100,000 |
| --- | ---: | ---: | ---: | ---: |
| Argument products (16) | 8 / 8 | 12 / 12 | 12 / 12 | 12 / 12 |
| Layered reconvergence (16) | 0 / 1 | 12 / 8 | 12 / 11 | 12 / 12 |
| Correlated frames (16) | 0 / 1 | 12 / 12 | 12 / 12 | 12 / 12 |
| Horizon boundaries (6) | 4 / 6 | 6 / 6 | 6 / 6 | 6 / 6 |
| Off-goal load (12) | 8 / 8 | 12 / 12 | 12 / 12 | 12 / 12 |

## What the correction changes

The preserved [v1 matrix](refinement-scaling-results-v1.md) used a direct comparator that computed a goal cone but still expanded definitely off-goal relations. The [fairness review](direct-goal-pruning-fairness-v2.md) records the deficiency. V2 keeps the original direct and candidate source bytes, adds conventional goal-cone pruning to a versioned direct solver, and reruns the identical 66 frozen profiles at the identical budgets and logical clock 100. The v1 evidence remains intact.

- In `scale-0064`, the legacy direct solver enumerates 65 assignments and spends 288 internal work units. Goal-pruned direct enumerates one assignment at 32 units; the candidate checks one relation at 30 units. The earlier off-goal difference mostly disappears with the corrected comparator.
- In `scale-0031`, the candidate refines 256 paths and performs 1,024 relation checks at 5,566 units. Goal-pruned direct shares four product states and enumerates 16 assignments at 134 units. The candidate abstains at budget 4,096 and certifies the negative only at the larger allowance.

These examples explain mechanisms visible in the full retained matrix. Integer budgets charge method-specific operations, so their units are not interchangeable hardware costs. Windows memory pressure and other work may have affected timing; no wall-clock speed advantage is claimed. Every solver, reference and certificate invocation is retained with its timing, including abstentions. The new negative checker reconstructs relevant relational closure without invoking either solver; it shares preserved language/topology primitives.

## Evidence and reproduction

- [Frozen prospective plan](../../runs/refinement-scaling/v2/plan.json), SHA256 `22e8ad19e16e8a09027ace151594779da0f5cbafa4de4ede062a23aee036536a`.
- [Complete matrix result](../../runs/refinement-scaling/v2/result.json), including case/family aggregates and all four invocation receipts.
- [Budget 32](../../runs/refinement-scaling/v2/budget-32/summary.json), [256](../../runs/refinement-scaling/v2/budget-256/summary.json), [4,096](../../runs/refinement-scaling/v2/budget-4096/summary.json) and [100,000](../../runs/refinement-scaling/v2/budget-100000/summary.json) summaries; each neighboring `results.jsonl` and `jobs` directory retains the underlying evidence.
- [Versioned entrypoint](../../src/interoperability/direct_comparison_v2.py) and [goal-pruned solver/checker](../../src/interoperability/direct_goal_pruned_v2.py), both captured in every bundle.
- [Focused software receipt](../../runs/direct-comparison-software/windows-v1/result.json): 15 comparator and 6 harness tests passed, including old/new certificate kinds, adapter restoration and actual captured-code replay of a two-profile harness. This receipt transcribes prior tool outputs; it does not pretend to contain raw historical logs or a replay of all 66 matrix profiles.

The [separately authored byte/record audit](../../runs/refinement-scaling/v2/independent-review/result.json) verified all 8,451 retained files, 1,591 worker jobs and 535 recorded certificate checks with zero discrepancies. It confirmed unchanged measured artifacts and unchanged legacy outcomes against v1. A separate reviewer authored the standard-library auditor; the primary agent executed it unchanged. This was record reconciliation, with no solver or checker reruns and no human review.

Read-only verification from the workspace root:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'runs/refinement-scaling/v2/source'
python -B -m interoperability.direct_comparison_v2 verify runs/refinement-scaling/v2/budget-100000
```

Use the versioned entrypoint for any fresh replay because the legacy CLI does not register `goal-pruned-relational-exhaustion/2`. Existing output allocations are refused. The [supervisor guide](supervisor-package-v1.md) supplies unused demonstration paths. This development matrix adds neither a qualified second domain nor a held-out study, and it does not determine overall project percentage or supervisor acceptance.
