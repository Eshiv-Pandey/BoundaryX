# Runnable admission development benchmark

`recipe-v1.json` compares the implemented witness-lift/refine candidate with
the direct relational-product baseline on all eleven authored recipe profiles,
at logical clock 100. `suite.json` separately exercises the four original
finite models. These supply repeatable software development benchmarks, not a qualified application domain,
held-out corpus, natural bridge failure sample or evidence of algorithmic novelty.
Its fixed evaluation clock is a simulation input inside the fixture intervals.
V10/V12 application evidence remains separately recorded; no trace is relabeled
as a complete finite runtime model by this runner.

From the project root in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
python -m interoperability benchmark --suite examples/benchmark-development/recipe-v1.json --algorithm candidate=interoperability.refinement:evaluate --work-budget 100000 --timeout-seconds 30 --output runs/admission-benchmark/new-comparison
python -m interoperability benchmark --suite examples/benchmark-development/suite.json --output runs/admission-benchmark/new-smoke
```

Baseline is always included. Add a repository-local candidate implementing
`evaluate(manifest, now)` and returning `decision`, `reason`, `certificate` and
optional JSON `stats`:

```text
python -m interoperability.benchmark --suite examples/benchmark-development/suite.json --output runs/admission-benchmark/new-comparison --algorithm candidate=interoperability.candidate:evaluate
```

The example candidate module name is a placeholder for a finite-schema plugin.
For `recipe-continuation/1` suites, the implemented candidate is selected with
`--algorithm candidate=interoperability.refinement:evaluate`. That module's
schema is registered explicitly; the direct relational-product
`refinement_oracle` becomes its same-input strong baseline and independent
candidate reference. Their shared implementation is disclosed in the execution
record. The inner finite graph alone is never substituted as this comparator.
Python callers can pass `AlgorithmSpec(name, module, entrypoint, input_schema)`
to `run_benchmark`; a different declared schema produces an explicit
`not_applicable` row, never an implicit conversion or a false comparison.
Only development suites and `authored-development` finite models or recipe
profiles are admitted. Suites use one schema each. `--algorithm-schema NAME=SCHEMA`
overrides a plugin declaration explicitly; other richer input schemas need their
own faithful benchmark adapter. `--work-budget N` supplies the same positive
budget to recipe candidate, baseline and reference; it is rejected for schemas
without that resource interface. Omission preserves the captured solver defaults.

Each algorithm runs in a fresh Python process using an exact copied package
snapshot and the same model/clock. A separate process runs the independently
authored oracle, and separate jobs validate conclusive certificates against
the original runtime input. Exceptions, timeouts, malformed results, input
mutation, schema incompatibility, wrong decisions and invalid certificates
remain in the artifact and its denominators. Unknown is an abstention, never
counted as a certificate or task success. Worker isolation is an execution
convenience for trusted local algorithms, not a security sandbox.

The summary includes the full three-way confusion matrix, decision agreement,
opposing conclusive answers, abstentions, decision and certified coverage, certificate failures,
function timings and worker wall timings. Raw returned work counters remain
in the individual case results. Family
labels group authored cases; they do not establish independently authored tasks.
An unknown answer when the reference is conclusive loses coverage but is not
an unsound answer. A conclusive answer when the reference exhausts its own
budget still needs an independently valid certificate. `decision_agreement_rate`
measures agreement with that resource-limited reference, not private-gold accuracy.
Single-call timings
establish no general performance advantage. Function timing
includes work inside `evaluate`; full worker timing additionally charges Python
startup, imports and result capture. Every call is cold: no persistent cache is
silently provided to one arm.

Timing aggregates include every attempted evaluation, including malformed
returns, exceptions and timeouts. Missing function timings remain `null`;
reported totals sum observed measurements only. `certificate_timing` records
check costs separately, `evaluation_and_certificate_timing` includes both,
and `reference_timing` preserves reference costs. `all_invocation_timing`
charges every reference, solver and certificate worker, including failures;
it excludes the parent runner's own overhead.

Each new output directory contains the original suite, exact case/source
snapshots, a portable replay suite, execution settings, all worker jobs/logs,
JSONL case results, summary and a SHA-256 inventory. Existing directories are
never overwritten. Failed runs remain failed even when their byte inventory
verifies.

```text
python -m interoperability.benchmark --verify runs/admission-benchmark/new-smoke
python -m interoperability.benchmark --replay runs/admission-benchmark/new-smoke --output runs/admission-benchmark/new-replay
```

`--verify` checks exact files, all copied-suite case identities/order/families,
algorithm membership and applicability, and recomputes the summary from retained attempts;
it does not execute algorithms or certify authenticity. `--replay` executes the
captured software on its copied inputs in a new directory. Timings will differ.
These commands run no original application, bridge service or live model.

Python 3.11 or later and the standard library are sufficient. The benchmark
worker uses `-I -S -B`; a plugin requiring third-party dependencies is outside
this initial self-contained execution profile and must not be silently enabled.
