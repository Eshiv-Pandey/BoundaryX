# Parameterized recipe development benchmark

The existing `supervisor-1/benchmark` retained eleven recipe cases at clock 100
and work budget 100,000. Both algorithms agreed on all eleven: four supported,
three unsupported and four unknown, with seven valid certificates each. Those
profiles have only two or three states, one to three transitions and horizons
one or two. They test semantics and certificates, but do not establish scaling
behavior, performance superiority or a useful budget operating range.

`scripts/generate_refinement_scaling_v1.py` adds five controlled authored
families. The default is an 18-case smoke suite, with width two, depth two and
two caller arguments. It validates profiles and freezes inputs; it does not
call either evaluator or execute a benchmark.

| Family | Parameters and cases | Mechanism exercised |
| --- | --- | --- |
| Argument product | Choices per argument and argument count; first/last witness, impossible guard, opaque request | Finite Cartesian assignment cost and early witness termination |
| Layered reconvergence | Parallel edge width and path depth; witness, early/late false layer, opaque final layer | Candidate path lifting and prefix refinement versus the direct solver's shared state/frame search |
| Correlated frames | Number of whole `(x=i,y=i)` frames and continuation depth; first/last matching frame, unmatched marginal pair, opacity | Binding correlation, frame propagation and witness order without combining values from different histories |
| Horizon boundary | Chain length with horizon one below, equal to, and one above it | Bounded refutation versus reachable witness; no unbounded non-support claim |
| Off-goal load | Dead branch count and argument product; reachable witness, refuted goal, irrelevant opaque relations | Candidate avoidance of off-goal relation lifting and the direct solver's actual relation work; uncertainty outside the goal cone does not require abstention |

These families deliberately include workloads that can favor either mechanism.
They are related parameterized development variants, not independent templates,
held-out cases, qualified domains or application gold. All relation coverage
claims close only the declared finite choices and horizon.

## Freeze and run

From the repository root in PowerShell, create a fresh directory:

```powershell
python -B scripts/generate_refinement_scaling_v1.py --output examples/refinement-scaling-development/v1
```

For a modest 66-case matrix, choose `--widths 2,4 --depths 2,4
--argument-counts 1,2` and a different new output directory. `--families` accepts
a comma-separated subset of the five names in the table, using underscores.
Preparation rejects oversized argument/path products and more than 512 cases.
It never overwrites an allocation.

The generated `manifest.json` freezes the configuration, neutral profile IDs,
external family/scenario labels, authored semantic expectations, every profile
and suite hash, and exact generator/validator source copies. Its file inventory
covers every generated regular file except the manifest itself. Generation is
deterministic. The existing benchmark runner separately captures its complete
algorithm package when a measurement is made.

The generated suite uses the existing runner without solver or harness changes:

```powershell
$env:PYTHONPATH = 'src'
python -B -m interoperability benchmark --suite examples/refinement-scaling-development/v1/suite.json --algorithm candidate=interoperability.refinement:evaluate --work-budget 100000 --timeout-seconds 30 --output runs/refinement-scaling/v1/budget-100000
```

Only individual profiles reach `evaluate`. Family, scenario and expectation
labels remain in the suite/manifest. Inputs use neutral identifiers and
consistent edge ordering; correlated frame values are padded so the direct
solver's lexical frame ordering agrees with the intended witness order.

The prospective budget list is 32, 256, 4,096 and 100,000. Each budget must use
the identical frozen suite and a new output directory. Both algorithms and the
reference invocation receive the same integer allowance and clock. However,
their work counters charge different internal operations: equal budgets are
an operational comparison, not identical primitive instruction counts.

Report decisions and abstention reasons first, then certificate validity and
checking cost, all invocation timings, and per-family mechanism counters.
Useful counters include candidate `abstract_paths`, `refinements`,
`relation_checks`, `peak_frames`; direct `product_states`,
`argument_assignments`, `cached_relation_outcomes`; and each implementation's
`expression_evaluations`. Compare counter growth within an implementation;
do not treat unequal categories as interchangeable units. The reference and
baseline are the same direct implementation, so agreement is not a third
independent algorithm comparison.

Expected labels describe the finite semantics with sufficient budget.
`unknown/work_budget_exhausted` is an abstention, not a false refutation. An
algorithm may certify a result while the budgeted reference abstains; preserve
both the certificate outcome and the reference's unknown status. Do not turn
an 18-case smoke run or a single timing sample into a superiority claim.

## Small validation

`tests/test_refinement_scaling_generator_v1.py` checks all 18 default profiles
against both solvers at clock 100/budget 100,000 and independently checks every
conclusive certificate. It also checks a shared budget of one (unknown without
a certificate), immutable inputs, larger-width correlated ordering, small
counter-growth examples, deterministic generation, complete file hashes,
label separation, schema validity and overwrite refusal. Ten focused tests
passed. These are implementation checks, not a comparative timing study.
