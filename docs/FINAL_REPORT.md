# BoundaryX migration and research report

Research title: *Benchmarking Framework for LLM-Based Agent Interoperability: Measuring Interoperability Loss Across Heterogeneous Agent Boundaries.* Primary identity: BoundaryX; alternative provisional name: Transfidelity. Report date: 14 November 2026. Receipts use UTC; local Windows validation used Python 3.13.1 and Node 22.13.0.

## 1. Repository and preservation

Completed: [private GitHub repository](https://github.com/Eshiv-Pandey/BoundaryX), owned by Eshiv-Pandey; authenticated administrator access confirmed. The new local directory is `BoundaryX`, a sibling of the original `Ai_Interoperability` directory. The separate local preservation directory is `BoundaryX_LegacyResearch`. Exact machine paths are supplied privately in the delivery response, not embedded in published configuration.

The original checkout is untouched. All 3,230 inventoried owned files matched their original hashes and Git status was unchanged in provenance/original-preservation-check.json. The local archive contains the complete original Git bundle, current owned-source ZIP, canonical supervisor delivery ZIP, full inventory and original status. The 447,068 original run files (about 8.44 GB) remain intact in the original tree; they were inventoried, not all manually reviewed or newly rehashed. Git history begins with a November backup, not the beginning of every research attempt.

Publication and clean-clone validation status are recorded in the delivery-validation section below. No unrelated existing GitHub repository was overwritten. Local preservation refs are never pushed.

## 2. Repository audit

Completed: [REPOSITORY_AUDIT](REPOSITORY_AUDIT.md). All 81 reachable original commits and changed-path histories were inspected. Automated source content/AST/hash/duplicate analysis and direct reads of critical runners, verifiers, contracts, evidence and upstream packages informed the classifications. This is a component-level semantic audit, not a claim that every installed dependency or capture was manually read.

The machine-readable provenance/version ledger records unchanged migrations, modifications, refactors, separate preservation and justified exclusions. Credentials, local instructions, machine launch configurations, installable dependency trees, repeated exports and material without established redistribution rights were excluded from publication; originals remain local. The initial four command-path redactions and the broader historical/generated configuration-log derivatives have explicit digest chains. Evaluated task cells and scientific metrics remain identical; configuration/setup packet lengths and digests describe distribution bytes, with canonical observations preserved locally. Failed attempts and unfavorable research findings were retained.

## 3. Migrated implementations

Completed: reuse of the original loss-v1 definitions, finite development tasks, v2 diagnostics, exhaustive four-group repair lattice, protocol/artifact runners, saved-evidence verifiers, five-control streaming JSON delivery path and regression tests. Historical names and metric denominators remain intact in the compatibility package and manifest-bound paths.

Completed: separate installation of two independently implemented upstream bridges, with original licenses and source/build provenance:

| Implementation | Source pin | Rights and role |
| --- | --- | --- |
| AmirK-S/a2a-to-mcp | 58eff9da469bccdc432bf164662727947de646b4 | Apache-2.0; genuine independent bridge route |
| mgcrea/mcp-a2a | c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5 | MIT; typed and raw surfaces share this implementation |

Four measured routes are not four independent implementations. Actual A2A execution uses 1.0; captured MCP negotiation selected 2025-11-25. No protocol mock substitutes for these bridges. Deterministic receivers and controlled faults are disclosed separately from protocol execution. No model calls were made.

## 4. Algo V1 and successor recovery

Completed: [separate admission module](../research/admission/README.md), version-family ledger and local complete source/history preservation. No file literally named Algo V1 was found; the audit maps that term to the original finite baseline/refinement research from source and dated documentation.

Reused for bounded development demonstrations and regression: finite reachability, refinement, independent exhaustive finite oracle, conservative unknown accounting, certificates and replay. Preserved separately: goal-pruned direct v2, shared lifting v2, guard/cache v3, proof DAG v1/v2, rejected method screens, manuscripts v0-v15 and AP2/AgentOps/provider experiment generations.

Historical Evidence: the early direct comparator expanded off-goal relations and unfairly inflated apparent refinement advantage. Corrected comparisons do not establish consistent superiority. Shared lifting adds no certified case over goal-pruned direct and has unfavorable common-cost results. Proof DAG work compresses representation and uses the existing semantic checker; no new theorem is established. Negative results remain visible.

Excluded from the executable loss package: unrelated native/payment experiments, unimplemented promises and unsupported novelty claims. Their source/evidence remains local or separately documented. One unrelated original AP2 source has a syntax error; it is archived unchanged, not repaired merely to report a green suite. Obsolete delivery builders remain in research/legacy-tools.

## 5. Final architecture

Completed: [ARCHITECTURE](ARCHITECTURE.md), Python source package, CLI, pinned development dependencies, Git byte-preservation rules and CI.

```text
src/boundaryx/
  core/          strict JSON, safe manifest members, hash evidence
  protocols/     A2A identity/wire and MCP schema/capability checks
  adapters/      declared routes and qualification limits
  tasks/         contracts, review eligibility and held-out freeze checks
  execution/     fresh allocation and process receipts
  verification/  independent SQLite oracle and evidence verification
  metrics/       unchanged historical definitions
  recovery/      unchanged finite repair implementation
  reporting/     machine-readable reports
src/interoperability/     historical compatibility and finite admission core
benchmark/, runs/        manifest-bound historical material
benchmarks/development/  24-example review packet
benchmarks/heldout/      separately frozen proposal versions
results/development/     actual reruns, failures and independent reports
research/admission/      separate algorithm research
external/                licensed pinned bridge sources/builds
```

The source checkout is the full reproducible artifact; a Python wheel alone does not contain all Node/evidence inputs. A project-wide license has not been invented.

## 6. Validation and exact commands

Reproduced: 278 benchmark/core passes, one Windows symlink skip, five separate delivery I/O controls, 18 new adverse-evidence/review controls, Ruff pass and mypy pass across 22 new source modules. Historical suites are not represented as lint-clean by a checker scoped to new code.

Completed: Amir integration 42/42; both upstream TypeScript checks; mgcrea lint. Windows mgcrea full suite: 84 passes, three failures. The failures are one POSIX path expectation and two /nonexistent write-permission assumptions. Tests were retained unchanged. Overall validation-002 is correctly marked failed. Earlier failing receipts, including historical-regrade-001, remain available; provenance rebinding made historical-regrade-002 pass without changing scientific values.

Three hash-identical historical snapshots retain the original unrelated AP2 syntax error at line 374. They are excluded from the functional package, preserved as evidence and explicitly recorded by distribution checks. Their syntax is not claimed to pass.

Exact captured commands (run from the repository root unless a working directory is stated):

```powershell
python -B scripts/run_loss_handoff_v2.py --output results/development/reproduction-001 --reproduce --live
python -B scripts/validate_boundaryx.py --output results/development/validation-002
python -B scripts/validate_boundaryx.py --output results/development/validation-003 --core-only
.venv/Scripts/ruff.exe check .
.venv/Scripts/mypy.exe
python -B -m unittest discover -s tests -p 'test_boundaryx*.py' -v
python -B scripts/loss_json_io_v2.py --self-test
python -B scripts/check_loss_software_v2.py --output results/development/software-new-001
```

`software-new-001` is an example unused allocation for reproduction, not a receipt claimed to exist. Actual software results are under reproduction-001/software. `validate_boundaryx.py` records command arrays, working directories, UTC timestamps, exit codes, stdout/stderr and durations. `--core-only` is an explicit affected-code check after the v2 proposal selection; it does not replace the retained full upstream result.

| Working directory | Actual upstream command |
| --- | --- |
| external/a2a-to-mcp | node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json |
| external/a2a-to-mcp | node node_modules/vitest/vitest.mjs run test/integration/send-message.test.ts test/integration/tasks-extension.test.ts |
| external/mcp-a2a | node node_modules/typescript/bin/tsc --noEmit |
| external/mcp-a2a | node node_modules/oxlint/bin/oxlint |
| external/mcp-a2a | node node_modules/vitest/vitest.mjs run |

## 7. Experiments actually reproduced

Reproduced: fresh allocation results/development/reproduction-001, all 11 stages passed between 2026-11-13 17:56:26 and 18:01:24 UTC, zero model calls. Historical allocations remain distinct under runs/supervisor-handoff-20261113.

| Experiment | Newly executed result | Interpretation |
| --- | --- | --- |
| Diagnostic/repair | 160 instances, ten families, twelve conditions, 1,920 episodes, 6,400 repair interventions | Records, task identity, constraints and tool binding form a finite declared repair universe; minimality applies only there |
| Controlled protocol | 480 episodes, four routes, twelve conditions, zero execution errors, 960 separate reads | Reference, placebo, reorder and authorized reread each pass 40/40; eight damaging injected conditions each fail the original contract 40/40 |
| Artifact fidelity | 80 tasks, four commands, five repetitions, four routes | Actual upstream fixture/SDK execution; fixture-specific utility and completeness are distinct |
| mgcrea typed artifacts | text 5/5; structured objects, URI and inline PNG payload 0/5 each; full fidelity 0/20; required fields 5/50 | Does not establish general protocol inability or URI accessibility |
| Same-task raw recovery | 20/20 eligible reads, 50/50 required fields restored | Task/context binding and captured public raw read evidence checked |
| Admission/replay | fresh finite demonstration and replay passed | Separately preserved research, not live LLM evaluation or general superiority |

These executions reproduce the reported figures; previously saved evidence is labeled Historical Evidence. Regrading alone is never counted as a fresh protocol run. Controlled damaging interventions are disclosed fault injections, not naturally occurring bridge failures.

## 8. Held-out bank and hash freeze

Completed: twenty structurally new proposals in benchmarks/heldout/v2, separate from development. Selected bank recorded in benchmarks/heldout/CURRENT.json. v1 remains frozen and unexecuted; the pre-execution v2 revision strengthened four structures (tool set-cover planning, split UTF-8 streaming, normalization collision detection and Merkle integrity). Versions are not counted as forty independent tasks. No held-out outcome informed the revision.

Manifest: benchmarks/heldout/v2/manifest.json. tasks.json SHA-256:

```text
dcc3a6e6b48c9281c27a03421ede77448bbd047874779fe1be6133dbb6a14efa
```

Pending Human Review: gold requirements are provisional, all decisions are blank and evaluations total zero. Not Established: accepted gold, supported execution for new families and held-out scores. The existing receiver covers only ten original families; no fake held-out solver was supplied. Human corrections require a new definition freeze before qualified execution.

```powershell
python -B scripts/boundaryx.py manifest benchmarks/heldout/v2
python -B scripts/boundaryx.py heldout-status
```

## 9. Independent verification

Completed: independently implemented SQLite contract computation and source/sent/received, identity, fields, constraints, allocation and same-task recovery checks. No imports of the legacy receiver, gold-computation or scoring functions. Historical and fresh reports include source hashes and check 5,770 diagnostic, 859 protocol and 121 artifact manifest members per allocation.

Reports: results/development/independent-historical-final.json and independent-reproduction-final.json. Final-source checks are independent-reproduction-003.json and independent-historical-004.json. The latter was executed after the broader historical configuration redaction pass; all 6,331 historical scored files also match canonical import hashes in provenance/scientific-preservation-check.json. Exact command for the fresh bundle:

```powershell
python -B scripts/boundaryx.py verify-independent --diagnostics results/development/reproduction-001/fresh-diagnostics --protocol results/development/reproduction-001/fresh-protocol --artifacts results/development/reproduction-001/fresh-artifacts --output results/development/independent-reproduction-003.json
```

Independence limits: task definitions, standard JSON/SQLite infrastructure and captured observations are shared. Artifact expectations are separately transcribed from the same fixture. Hashes/wire membership do not authenticate origin or independently observe every business effect. AI-assisted separate code is not independent human review. The original shared verifier establishes consistency and reconstruction, not independent semantic correctness.

## 10. Human-review package

Completed: 24 representative development examples with definitions, proposed gold, required fields, constraints, success criteria, protocol assumptions and evidence requirements. Separate held-out forms cover twenty proposals. [HUMAN_REVIEW](HUMAN_REVIEW.md) explains the procedure.

Pending Human Review: two undergraduate reviewers assess clarity, consistency, expected-output logic and traceability; names, decisions, reasoning, disagreements and resolutions remain blank. The supervisor observes progress only; two distinct teammate reviewers supply the human judgments tied to exact definition hashes. No domain expertise or human approval is invented.

## 11. Literature, metrics and novelty

Completed: [METRICS](METRICS.md) and [EXPERIMENT_PROTOCOL](EXPERIMENT_PROTOCOL.md) preserve formal task/field/capability/constraint/recovery/overhead denominators, evidence requirements, unknowns, edge cases and scope boundaries. Different experiment designs are not pooled into one score.

Completed focused primary-source review: [RELATED_WORK](RELATED_WORK.md) and ordered metadata cover official A2A/MCP specifications, AgentBench, ToolLLM, ToolSandbox, StableToolBench, tau-bench, AgentThread, CONTINUITY, proof-carrying contracts, BRIDGE and software fault injection. Preprint/proceedings status and inaccessible full-text/DOI limitations remain explicit.

Established: contracts, schema/field preservation, faults, recovery, pruning, memoization and proof compression. Completed engineering contribution: traceable real bridge experiments, task-relative artifacts/recovery, modular evidence and a separate verification path. Potentially distinctive empirical contribution: paired preservation loss across independently implemented heterogeneous routes. Not Established: general scientific novelty, loss prevalence, LLM semantic transfer or superiority over prior frameworks. Project-name search does not establish novelty.

## 12. Remaining limitations

Pending Human Review: proposed gold and research acceptance. Pending External Evaluation: outside scientific reproduction, live-model applications and production consequence/authentication coverage. Not Established: held-out performance, naturally occurring fault prevalence, general semantic correctness and novelty. See [LIMITATIONS](LIMITATIONS.md).

The framework executes deterministic development tasks through real protocols. It is not yet a completed human-validated LLM empirical study. Windows upstream failures, fixed build-chunk dependency, shared definitions/observations, local-only archives and absent project licensing decision are material limits, not hidden green checks.

## 13. Reproduction instructions

Use [REPRODUCIBILITY](REPRODUCIBILITY.md) for frozen Node installs, licensed build restoration, offline checks, full actual bridge execution and fresh allocations. For dependency-free historical verification:

```powershell
git clone https://github.com/Eshiv-Pandey/BoundaryX.git
cd BoundaryX
python -B scripts/boundaryx.py check-history --output results/development/my-history-001
python -B scripts/boundaryx.py heldout-status
```

`reproduce` adds finite diagnostic/admission execution; `--protocols` adds genuine loopback bridges after installing upstream dependencies and restoring verified pinned builds. Failed allocations are retained and output reuse is refused. Never execute an unreviewed proposal as qualified held-out evaluation.

## 14. Important commits and delivery validation

Original audited HEAD: c781a77f; full original history preserved locally. Publishable migration milestones, with DCO signoffs:

- 7d718e5fdf8bee378dcdac024934ba1b3c659b22: audited legacy recovery and separate research preservation.
- 6b1c33711996c5c12782de89d8deecb85bd23292: modular BoundaryX and independent verification workflow.

Completed: distribution-check-003 checked 23,507 tracked files, 597 successfully parsed Python sources, 17 evidence manifests / 22,348 members, 23 active links and the declared task schema. Zero credential-pattern/machine-path candidates remained; three exact archived syntax failures are recorded separately. The schema count of 64 is 24 development examples plus two versions of twenty proposals, not 64 independent evaluations. Final validation commit, isolated clean-clone receipt, ordinary private push and actual CI outcome follow below. No force push or all-refs publication is used. Sanitized publication milestones preserve the original local milestone objects under local-only refs; provenance/publication-history.json explains the digest/history strategy.

Clean-clone finding: the first isolated attempt at fea8145c2df949c16b4a190d1d790ff44710c6c1 passed five I/O controls but failed historical regrading because vendored ignore rules excluded required dist files. Licensed builds were explicitly added after all nine recorded source-hash checks matched. The failed allocation is retained locally and summarized in the clean-clone receipt; tests and verifier checks were not weakened.

Completed delivery validation: isolated clean clone at 94f861355163b474bc278f4639dca629ad8248a4 passed all four offline pipeline stages, 278 tests with one Windows symlink skip, five I/O controls and the separate historical verifier. A fresh venv had no pip/OpenAI/mypy/Ruff packages; Node dependencies were absent. Exact commands, timestamps, canonical/derivative hashes and both attempts are in results/development/clean-clone-validation.json. The failed first attempt is retained.

Completed: [GitHub Actions run 43493963275](https://github.com/Eshiv-Pandey/BoundaryX/actions/runs/43493963275), both offline and upstream-protocols jobs succeeded on Ubuntu at 94f861355163b474bc278f4639dca629ad8248a4. CI reports 279 benchmark/core passes, 0 skips, 18 new controls, five I/O controls, Ruff, mypy across 22 modules, 42 Amir integration passes and all 87 mgcrea upstream tests passing. The Windows 84-pass / three-failure record remains unchanged. CI regrades historical protocol evidence; it does not newly execute the 480-episode research allocation. Summary and canonical log digest: results/development/github-ci-001.json.

Important delivery commits: fea8145c2df949c16b4a190d1d790ff44710c6c1 (research/framework delivery) and 94f861355163b474bc278f4639dca629ad8248a4 (verified build inputs and clean-clone packaging fix). A signed report/receipt commit follows these; git log --oneline identifies the delivery tip. All pushes use origin main only.

Role clarification: the project owner confirmed that the supervisor observes progress only. Supervisor approval is no longer an evaluation gate. Two distinct teammate reviews, frozen-definition hash binding and disagreement resolution remain required. Current blank forms and the eligibility checker follow benchmarks/review-policy.json. The inactive v1 forms and historical reports retain their original unused supervisor fields/plans for provenance. No task/gold definitions, historical metrics, results or held-out hashes changed. See TEAM_REVIEW_GUIDE.md and PROGRESS_FOR_SUPERVISOR.md for the sharing materials.

Current review-policy validation: 21 BoundaryX controls passed, Ruff and mypy passed, the readable packet manifest validated and the selected held-out task hash remained unchanged. These are new affected-code checks, separate from the previously recorded 18-control validation runs. No human review decisions were filled.
