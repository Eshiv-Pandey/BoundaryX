# Four-method scaling extension: prospective plan v3

10 November 2026. This experiment extends the preserved 66-profile v2 matrix
with shared lifting. It changes neither a solver nor an input profile. Results
will be reported after the complete new allocation finishes.

## Question and fixed sample

Does invocation-local relation/prefix caching improve certified coverage or
reduce total solver/checker cost across the same existing development families,
and when does unchanged path-list proof construction dominate its saved relation
work? Report every outcome, including unfavorable cache overhead and abstentions.

Use the exact bytes and original order of `runs/refinement-scaling/v2/inputs/suite.json`
and all 66 manifest-bound profiles. The existing families are argument products,
layered reconvergence, correlated frames, horizon boundaries and off-goal load.
These are related authored development variants, not 66 independent templates,
held-out examples or observed application outcomes.

The logical evaluation clock remains 100. The original budgets are 32, 256,
4,096 and 100,000. All methods receive the same supplied relations, legal recipes,
bindings, completeness/freshness declarations, contract and horizon.

## Methods and captured implementation

The entire 21-file package captured by `runs/shared-lifting-pilot/v1/plan.json`
is copied unchanged. Its 18-file overlap with the earlier v2 package must be
byte-identical. The four arms are the historical direct control/reference,
the strongest goal-pruned memoized direct comparator, original refinement, and
shared lifting. No new favorable cases, weaker comparator or hidden private
runtime input is introduced.

The versioned v3 command sends every conclusive decision to the existing
independent checker, which does not trust the solver cache. Its frozen work
allowance is 2,000,000; internal checker work counters are not returned, so their
absence is explicit. Every worker has the original 30-second timeout. Bundles
and workers run sequentially, with at most 2,376 worker jobs across the matrix.
The coordinator has no separate killing timeout while it owns a bounded worker.

## Measurements and reconciliation

Retain exact command vectors, return codes, binary stdout/stderr, source/input
hashes, worker results, resource observations, and independent bundle verification.
Reconcile all original three arms' decisions, reasons, certificates and deterministic
counters against their preserved v2 rows; internal elapsed-time fields are excluded
from deterministic equality.

Report certificate UTF-8 byte counts under sorted-key compact JSON with
`ensure_ascii=False` and `allow_nan=False`, alongside certificate hashes, refutation
counts/edge counts, product-layer/frame counts, and all deterministic solver counters.
Unknown outcomes have no certificate size, rather than a fabricated zero-byte proof.
Coverage includes all 66 cases; family and shared-versus-direct paired counts are
reported without selecting only successful cases.

Function, worker-body and worker-wall timings overlap. Keep solver/checker worker
wall sums, reference workers and coordinator time separate. Process memory is the
observed OS high-water mark, including interpreter/import/input overhead. These
are single observations in fixed method order on the current host, not evidence
of a general speed or memory ranking. Raw frozen dispatch records retain absolute
paths; the additional analysis references project-relative input paths.

## Execution and preservation

The new allocation is `runs/shared-lifting-scaling/v3-20261110-1`. Preparation
refuses an existing directory; execution refuses every started/consumed allocation.
Failures remain recorded. If a future successor is justified, it must use a fresh
numbered suffix and a new prospective decision rather than rerunning this output.

```powershell
<python-install>\python.exe -I -S -B scripts/run_shared_lifting_scaling_v3.py prepare
<python-install>\python.exe -I -S -B scripts/run_shared_lifting_scaling_v3.py execute
```

Preparation performs no solver work. It seals the driver, this plan, exact suite,
profiles, provenance and captured package before execution. Original v2 and pilot
source/input tree membership and bytes, previous v2 rows/summaries, and snapshots
are checked before/after every command. Existing captures and output allocations
are never altered.

The isolated coordinators deny socket/HTTP/urllib network operations and use a
minimal environment without provider credentials. Frozen solver workers keep
their original bootstrap. Their offline assurance comes from the fixed reviewed
stdlib-only source closure and module dispatch, not an inherited coordinator
audit hook. No SDK, application, model, credential or provider request is executed.

This experiment can establish an engineering tradeoff and reproduction evidence.
It does not establish algorithmic novelty, universal superiority, a qualified
domain, independent human review, a full research gate pass or project completion.
