# Prospective common end-to-end cost comparison v1

11 November 2026. This protocol compares the exact existing 66 authored
development profiles with all five existing methods and five predeclared timing
repeats on one serial hosted Linux runner. It is practical comparison work in
the existing scope. No held-out, application, provider, novelty, superiority or
checkpoint outcome is assumed. There are 1,650 allocations; the comparison
unit remains the profile, with five dependent timing replicates per method.

The fixed methods are `legacy_direct` (`refinement_oracle`),
`goal_pruned_direct` (`direct_goal_pruned_v2`), `original_refinement`
(`refinement`), `shared_lift` (`refinement_shared_lift_v2`) and
`guard_pruned_direct` (`direct_guard_pruned_v3`). Their source bytes remain
unchanged. The eight-file stdlib-only source closure and all 66 profile bytes
are copied under `benchmark/common-cost-v1`; profile hashes match the prior
development manifest, and seven overlapping source files match the frozen
shared-lifting comparison. The supplemental guard source is separately pinned.

`protocol.json` fixes the source/profile identities, clock 100, method APIs,
resource limits and analysis before execution. `order.json` freezes all 1,650
cells with SHA256
`0127c1298d519b551d0aa1b3cd016b25e1e2d94a05f93b2eef318f25b80fb9e8`.
For each profile, seed 2026111101 generates one initial method permutation and
five cyclic rotations, randomly assigned to the five repeats. Each method
occupies each position exactly once for that profile. Profiles are shuffled
separately within each repeat. Preparation validates the complete order and all
paths/APIs and snapshots source, input, prior suite/manifest bytes and every
job hash before any workload worker starts.

Each cell uses a fresh process. The single-threaded POSIX coordinator installs
identical `RLIMIT_CPU` soft/hard limits of 5/6 seconds, a 512 MiB `RLIMIT_AS`
address-space limit and a 10-second real-time timer before `exec`. These apply
to interpreter startup, profile/source loading, solver import/evaluation,
actual independent certificate checking and output. The coordinator also
enforces a launch-to-exit wall deadline, polling at 2 ms; scheduling and cleanup
can make the observed wall exceed the deadline. There is no separately claimed
resident-memory hard limit: Linux `RLIMIT_RSS` would not enforce one.

Children use `-S -P -B` and a scrubbed environment. They do not use `-I` or `-E`,
which would ignore `PYTHONHASHSEED`. A fixed shared hash seed is declared for
each profile/repeat across its five methods. The worker verifies the seed and
interpreter flags and records a common hash probe. User/site customization and
`PYTHONPATH` are excluded. The worker denies network and descendant-process
capabilities. No App, model API or provider executes.

Every solver receives the same explicit 100,000,000 logical allowance. Its
charged operations remain method-specific diagnostics, not interchangeable
physical costs. A strict counter comparison records whether that allowance had
remaining headroom; budget exhaustion remains unknown and is retained.

Every conclusive solver result is passed to the same unchanged
`direct_goal_pruned_v2.check_certificate`. It supports both old proof kinds and
the new goal-pruned negative cut. The checker uses a freshly imported package
namespace distinct from the solver namespace and a fresh input/result copy,
without access to solver relation caches. The fixed internal checker allowance
remains 2,000,000; the preserved API has no configurable budget argument.
`True` certifies the result and establishes that checking did not exhaust its
internal allowance. `False` means an invalid proof or checker soft-cap failure;
the wrapper does not distinguish them or infer an unsupported outcome.

Primary costs come from the sole terminal `os.wait4` after termination: full
child user/system CPU and Linux peak RSS, including final output and adverse
exits. Outer wall spans process launch through group cleanup/reaping. A
non-reaping `waitid(WNOWAIT)` observation holds the PID while its owned group
is closed, then `wait4` reaps exactly once. Interruptions, timeouts and cleanup
errors retain any acquired resources and stop further dispatch when ownership
cannot be established. `SIGKILL` alone keeps its CPU-hard-or-external cause
unattributed. Missing observations stay null.

Secondary CPU/wall phases cover profile/source loading, solver import and
evaluation, result serialization, fresh independent checker import/checking and
result output. Inner measurements end before final reply output; they do not
replace full-lifetime costs and must not be added to overlapping outer times.
Peak RSS includes the interpreter, loaded solver/checker modules, inputs and
certificates. It is a complete worker process peak, not a solver-only allocation.

All certified, unknown, failure, timeout, stopped and unstarted allocations
remain in the 1,650-cell census. Early failure is not treated as efficiency.
Cost ratios are reported separately for paired profiles with all five repeats
certified to the same decision and nonbinding declared logical/CPU/wall limits.
Each profile supplies median CPU, wall and RSS values across those paired
repeats. An accepted supported/unsupported contradiction anywhere among a
profile's 25 cells excludes it from every cost cohort and is reported explicitly.
Coverage and adverse-status counts remain separate. No successful-only sample
is represented as 1,650 independent research tasks.

Closing and aggregate receipts use atomic no-clobber publication. Interrupted
pending bytes remain retained. Finalization never dispatches a worker; it
preserves malformed or missing closures, all unstarted allocations, and
recovers a missing manifest after an already published result. Source-integrity
failure suppresses certified cost cohorts while retaining the raw census.
A retained post-link manifest pending alias is excluded from its own inventory
only when its bytes equal the published manifest; other pending bytes stay
ordinary inventoried evidence.

The local command is `python -I -S -B tests/test_common_cost_benchmark_v1.py -v`.
Six protocol/publication/retention/cohort controls passed; five actual Linux
cap, wait4, seeded-child and constructed worker acceptance/rejection controls
are pending on the hosted runner and skipped on Windows. Tiny solver/checker
stubs exercise the worker control; controls never run the preserved benchmark
methods and do not add to its 1,650 allocations. These checks are constructed software
evidence; no full 1,650-cell comparison has run locally. Independent reviews
are checking resource cleanup, timing boundaries, exact input provenance,
checker isolation and adverse-result retention.

Workflow: `.github/workflows/common-cost-benchmark-v1.yml`.
It runs controls, prepares a new allocation, executes serially, finalizes without
retry, verifies retained records and uploads the full public artifact even after
failure. A fresh local preparation is available with
`python -I -S -B scripts/run_common_cost_benchmark_v1.py --prepare-only --output <fresh-directory>`.
Execution requires the pinned hosted Linux Python 3.13.1 runtime.
