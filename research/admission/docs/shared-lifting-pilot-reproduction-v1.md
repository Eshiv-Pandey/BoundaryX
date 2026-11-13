# Full shared-lifting pilot reproduction

10 November 2026. The entire retained twelve-case, four-budget pilot was
reproduced from original captured source in a fresh allocation. All eight
replay/verification commands returned zero. All 192 algorithm evaluations
matched original decisions, reasons, certificates and deterministic counters.
Timing and process-memory observations were retained separately.

| Work budget | Cases | Accepted certificate checks | Legacy / pruned / original / shared certified decisions |
| ---: | ---: | ---: | --- |
| 32 | 12 | 18 | 6 / 6 / 6 / 0 |
| 256 | 12 | 29 | 8 / 8 / 7 / 6 |
| 4,096 | 12 | 30 | 8 / 8 / 7 / 7 |
| 100,000 | 12 | 32 | 8 / 8 / 8 / 8 |

The fresh execution contained 192 solver workers, 48 reference workers and 109
certificate workers: 349 jobs total. There were no failed commands or worker
timeouts. The driver monitored all 1,989 original pilot files and verified that
their membership and bytes, its own source and the interpreter stayed unchanged.
Every fresh worker has a process-memory observation.

## Comparison scope

The driver uses the original twenty-one-file captured package and each budget's
complete twelve-case replay suite. It preserves the semantic clock of 100, four
original budgets, method order, constructor/recipe language, 30-second worker
timeout and independent checker. It compares each result and certificate, input
hashes, validity and decision-agreement fields. Only internal `elapsed_ns` timing
fields are removed from deterministic payload equality. Outer worker/resource
timings remain separate observations.

This closes the full-pilot computational reproduction gap in the supplied
review. It does not add independent templates, source-to-model fidelity,
application success, scientific novelty or a research gate pass. The same
authored development examples and disclosed reference are used. The new
observations do not establish a speed or memory ranking.

## Evidence

- [Once-only driver](../../scripts/reproduce_shared_lifting_pilot_v1.py).
- [Prospective plan](../../runs/shared-lifting-pilot/reproduction-20261110-v1/plan.json)
  and [artifact manifest](../../runs/shared-lifting-pilot/reproduction-20261110-v1/manifest.json).
- [Execution and deterministic comparisons](../../runs/shared-lifting-pilot/reproduction-20261110-v1/result.json),
  SHA256 `5c46a3e531568992a47462963319477363d7673828bc34013ff15fa1c1345d4b`.
- [Separate root artifact/count audit](../../runs/shared-lifting-pilot/reproduction-20261110-v1-root-audit.json):
  1,941 reproduction-manifest files and all 1,989 original files checked;
  worker counts and certificate totals recomputed from new bundle rows.
  This audit did not reexecute solvers or checkers.
- [Original pilot results and limitations](shared-lifting-pilot-results-v1.md).

The reproduction allocation is consumed. Do not rerun it. The driver accepts
`--check-only` for read-only preflight; a justified future execution requires a
new unused allocation. Preserve original and fresh receipts, including failures.
