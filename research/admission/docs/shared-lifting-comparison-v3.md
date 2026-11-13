# Shared lifting: implementation and four-method comparison

The new [shared-lifting solver](../../src/interoperability/refinement_shared_lift_v2.py)
keeps the original abstract-path search and failed-prefix refinement. It reuses
completed exact prefixes and complete relation evaluations keyed by the edge and
whole binding frame. Cached local steps attach to the current path's history.
This is ordinary memoization engineering; it does not establish scientific novelty.
The [design](shared-lifting-design-v2.md) specifies uncertainty, cache publication,
history and budget rules.

The [versioned comparison command](../../src/interoperability/shared_lifting_comparison_v3.py)
implements four arms on identical supplied recipe profiles:

| Arm | Implementation |
| --- | --- |
| `baseline` | Preserved same-input relational-product solver; historical control and disclosed reference implementation |
| `direct_pruned` | Same-input memoized relational-product search with remaining-horizon goal-cone pruning; mandatory fair comparator |
| `candidate` | Preserved witness-lift/refine solver |
| `shared_lift` | New solver with invocation-local shared lifting |

`direct_pruned`, implemented in
[direct_goal_pruned_v2.py](../../src/interoperability/direct_goal_pruned_v2.py),
is the fair comparator required by the prototype specification and the
strongest direct arm in this comparison. It memoizes complete edge/frame
relation evaluations and receives the same constructors, recipes, bindings,
horizon, evidence freshness and coverage as the candidate. The `baseline` arm
is a historical same-input control, not the decisive superiority comparator.
Neither direct arm is abstraction-only: a separately labelled finite-graph BFS
was not run in this four-method pilot.

Every conclusive result goes to the existing independent checker in a separate
worker. Shared lifting retains the original certificate kinds; the checker does
not trust or reuse solver caches. Verification derives validity, required-check
presence, certificate acceptance and decision agreement from retained replies.
It also reconciles dispatch, input/source hashes, process records and observations.
Verification `status` reports record consistency; `benchmark_status` separately
reports the recorded benchmark outcome.

## Running the implementation

From the workspace root, this runs the eleven original development examples
with all four methods. Use a fresh output directory each time:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
python -B -m interoperability.shared_lifting_comparison_v3 run --suite examples/benchmark-development/recipe-v1.json --work-budget 100000 --timeout-seconds 30 --output runs/admission-demo/shared-supervisor-1
python -B -m interoperability.shared_lifting_comparison_v3 verify runs/admission-demo/shared-supervisor-1
```

Captured-code replay uses this same versioned entrypoint:

```powershell
python -B -m interoperability.shared_lifting_comparison_v3 replay runs/admission-demo/shared-supervisor-1 --output runs/admission-demo/shared-supervisor-replay-1
```

These are demonstration commands, not claims that these output allocations have
been executed. The older CLI and captured v2 package demonstrate the original
methods. The completed [66-case v2 results](refinement-scaling-results-v2.md)
remain unchanged and contain no shared-lifting measurements.

## What the measurements include

The [resource worker](../../src/interoperability/benchmark_resources_v1.py) applies
the same observations to every solver, reference and certificate worker. Results
retain unknowns, errors, timeouts and unavailable measurements.

| Measurement | Interpretation |
| --- | --- |
| Solver work counters | Method-specific charged operations, including new cache and history work; not interchangeable hardware costs |
| Function time | Evaluation or certificate-check attempt, including validation performed inside that function |
| Preparation and serialization | Worker-entry input loading/digest and target import; result JSON serialization and input post-check are recorded separately |
| Solver plus checker wall time | Sum of the corresponding sequential worker wall times, including process startup, imports and output; reference and outer-runner overhead remain separate |
| Process peak memory | OS high-water mark observed before final reply output, including interpreter/input/import overhead; maximum across workers, never the sum or a solver-only allocation |

Function, worker-body and worker-wall timings overlap and must not be added
together. Missing memory/timing observations remain null. Fixed method order,
host contention and related authored cases limit any performance interpretation.
Negative certificate checking can erase solver-side caching savings.

## Software evidence

- [23 focused solver tests](../../runs/refinement-shared-lift-software/v2/validation-1/result.json)
  passed from captured source, with raw logs and unchanged source/dependency hashes.
- [Three resource tests and five comparison tests](../../runs/shared-lifting-comparison-software/validation-1/result.json)
  passed from captured source, including an actual two-profile run and replay,
  altered outcome flags, missing checks and dispatch tampering.
- Independent source reviews found no remaining blocker in the
  [solver](../../runs/refinement-shared-lift-software/v2/source-review-v1.json) or
  [comparison/resource code](../../runs/shared-lifting-comparison-software/source-review-v1.json).

The initial comparison test capture remains preserved separately. The final
capture includes the fix for trusting recorded outcome flags. These are authored
software checks, not human acceptance or application-domain qualification.
The [completed engineering pilot](shared-lifting-pilot-results-v1.md) uses all
eleven original examples plus the motivating `scale-0031` stress case, at the
four existing budgets. All bundles passed verification. Reduced relation
evaluation did not offset the added cache work under the declared meters;
shared lifting remains experimental. This twelve-case result is separate from
the preserved 66-case v2 comparison.
