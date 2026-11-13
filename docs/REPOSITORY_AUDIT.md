# Repository audit and migration decisions

Status: Completed inventory and source/history audit, 13 November 2026. Validation and migration receipts are recorded separately. This is a rebuild of the loss benchmark, not a rename of earlier algorithm claims.

## Scope and method

The original checkout remains untouched. Inventory covered every regular-file path exposed by `rg --files --hidden --no-ignore`, excluding Git internals and the installed Python environment. It includes ignored/untracked material, nested upstream checkouts, temporary exports and release copies. The inventory found 447,068 run files, 38,699 external files, 31,594 release files and 22,381 temporary files; runs alone occupy about 8.44 GB. A component-level inventory and original file hashes accompany the migration. Dependency installations and repeated exports were inventoried, not treated as original implementations.

All 81 reachable commits and their changed-path histories were inspected. The first commit, `0cee8af2b5865cdbef1d2e10346f933e1a4fb559`, is a backup dated 9 November, not the creation date of every experiment. The audited HEAD is `c781a77f`. There are two modified tracked files and 429 untracked status entries; current loss-v2 source and captures must be recovered from the working tree as well as HEAD. Authorship is preserved in a selected-file provenance ledger and a local complete Git bundle, rather than replaying 81 unrelated commits into BoundaryX.

An automated content, hash/duplicate and Python AST audit inspected 89 source, 505 script, 194 test, 316 benchmark, 367 document, 148 paper and 21 example files outside embedded evidence/snapshots. Important execution paths, scoring functions, verifier imports, experiment allocations, results, repair rules, research screens and upstream package/license manifests were read directly. This does not mean every dependency or 447,068 evidence file received manual semantic review. Historical results require hash validation and executable regrading; inventory alone does not establish correctness.

## Component classifications

| Component | Classification | Reason and destination |
| --- | --- | --- |
| loss_benchmark_v1 metrics, development cases, schema validation | Migrate unchanged | Preserve definitions, unknown handling, check-item denominators and historical names. Compatibility package remains available. |
| loss_diagnostics_v2 and finite four-group repair lattice | Migrate unchanged | Complete subset enumeration has bounded diagnostic value; minimality is confined to the declared group universe. |
| Python/Node loss runners and saved-evidence verifiers | Migrate unchanged | Preserve operational behavior and source hashes; label shared scoring/gold logic explicitly. |
| loss handoff command and streaming JSON adapter | Migrate unchanged | Reuse the existing tested delivery path and five differential I/O controls. |
| Public package/CLI and execution reporting | Refactor | Add a modular BoundaryX API, allocation receipts and separated result directories around verified implementations. |
| Independent semantic and wire evidence verifier | Refactor | Add a separate path with no legacy scoring, receiver or gold-computation imports. Independence is limited by shared specifications and captured observations. |
| Human gold and supervisor review | Migrate with modifications | Prepare review forms without inventing decisions; original AI-authored gold is provisional. |
| New held-out task specifications | Migrate with modifications | New task structures in separate frozen storage; no evaluation or tuning before human approval. |
| Final 1,920 diagnostic / 480 protocol / 80 artifact allocations | Migrate unchanged | Preserve immutable evidence and manifests, distinguish regrading from fresh execution. |
| Protocol setup failures and smoke attempts | Preserve separately/archive | Retain failure provenance; exclude machine-specific runtime configuration from remote distribution. |
| AmirK-S/a2a-to-mcp and mgcrea/mcp-a2a | Migrate unchanged | Separately implemented Apache-2.0 and MIT routes with official SDK execution. Preserve pins/notices; install dependencies separately. |
| Other external routes and unqualified native-model work | Preserve separately/archive | Retain original checkout and local research archive. They are not silently upgraded to qualified BoundaryX routes. |
| Algo V1 finite baseline / refinement / independent finite oracle | Preserve separately/archive | Useful independent bounded-admission toolkit, not a loss metric or live protocol implementation. |
| Goal-pruned v2, shared lifting v2, guard-pruned v3, cache v3, proof DAG v1/v2 | Preserve separately/archive | Preserve implementation, comparison evidence and unfavorable findings in an independent admission module. |
| Manuscript v0 through v15, method screens and native AP2/AgentOps generations | Preserve separately/archive | Retain distinct research and failed attempts; do not force payment/native application research into the loss framework. |
| Local editor/assistant rules, credentials, provider launch configuration | Exclude, with justification | Local-only/private material is not contribution content. Originals remain intact. |
| .venv, node_modules, bytecode, egg-info, tmp and repeated extracted releases | Exclude, with justification | Generated/installable duplicates; preserve original inventory, dependency locks and evidence identity instead. |
| Missing-rights upstream source and unrelated presentation PDFs | Exclude, with justification | No invented licensing rights; original files remain intact and separately documented. |

## Algo V1 and successor recovery

No file is literally named Algo V1. The user term is mapped to the original finite continuation/admission line using source and dated documentation, not invented version labels.

1. The original finite layered reachability baseline solves a supplied bounded graph. Its exhaustive oracle is separately authored. Neither runs a protocol nor proves the graph faithfully models an application.
2. Recipe refinement v1 implements bounded witness lifting and refinement, a CEGAR/lazy-symbolic adaptation. Preserve correlated frames, certificates, conservative unknowns and work accounting. Its scientific novelty is Not Established.
3. The first 66-case scaling matrix used a direct comparator that expanded definitely off-goal relations. Preserve its numbers, with the existing fairness correction. It cannot establish candidate advantage.
4. Goal-pruned direct v2 corrects that comparison on the same input. At the largest budget all methods agree: 28 supported, 26 unsupported and 12 unknown. Original refinement does not consistently outperform corrected direct.
5. Shared lifting v2 adds call-local prefix/relation reuse. The v3 four-method matrix reproduces 792 prior deterministic outcomes but adds no certified case over goal-pruned direct and loses some low-budget coverage. Preserve this negative result.
6. Guard pruning v3 and cache ablation/comparison v3 are conventional pruning/memoization studies. Common-cost evidence reports higher shared-lifting CPU/wall/RSS medians than goal-pruned direct on every eligible profile. Do not turn engineering experimentation into a novelty claim.
7. Refutation prefix DAG v1/v2 packages existing exact-prefix proofs. It is lossless representation work delegated to the unchanged checker, not independent semantic verification or a new theorem.
8. Source-recipe v0, callsite-factoring, response-binding and other method screens are analytical proposals/rejections. Preserve their reasoning; exclude unsupported novelty and unimplemented promises from BoundaryX claims.
9. AgentOps generations (native probes v2-v7, HTTP v1-v5, bridge v8-v12, admitted v1-v4, governed/reference/workflow successors) and AP2 generations (application v3-v5, shopper v6/v7, native bridge v8-v13, provider v1-v5) retain useful transport, lifecycle and provenance insights. Preserve separately. Startup, certificate, binding, serialization, shutdown and provider failures are outcomes, not missing data to erase.
10. A full version-family ledger records every numbered successor found in owned source, scripts, tests, benchmarks and documents. Snapshot names do not imply independent experiments or successful executions. One unrelated source file, ap2_hp_gemini_source_graph_v1.py, has a syntax error at line 374; archive it unchanged and do not import it into the functional package.

## Evidence and scientific limits

Historical Evidence: artifact 80 tasks / 4 commands / 5 repetitions / 4 routes; mgcrea typed payload text 5/5, data/URI/inline PNG 0/5; complete artifact fidelity 0/20, fields 5/50; same-task raw recovery 20/20 and 50/50. Historical Evidence: 480 controlled protocol episodes / 12 conditions / 4 routes, zero execution errors and 960 isolated read probes. Historical Evidence: 160 instances / 10 families / 12 conditions, 1,920 episodes and 6,400 finite repair interventions. These counts must be independently checked against saved allocations and newly reproduced only after execution.

The legacy runner and verifier share receiver and gold-computation logic. Their agreement establishes consistency and reconstruction, not independent semantic correctness. Fault injections are controlled interventions; deterministic SDK/bridge execution is real protocol execution, but is not an LLM application experiment. No human or supervisor decisions, held-out scores, external reproduction or novelty are established by migration.

## Preservation and distribution

Source files used by historical manifests are not silently edited. Machine-specific configuration and failed runtime-path traces stay in the local archive; remote-safe evidence must retain verifiable byte identity. The original Git bundle, inventory and current source snapshot are local preservation artifacts. BoundaryX contains selected attribution and file/hash provenance. No project license is granted without a rights decision; third-party licenses retain their original scope.
