# BoundaryX

**Benchmarking Framework for LLM-Based Agent Interoperability: Measuring Interoperability Loss Across Heterogeneous Agent Boundaries.**

BoundaryX measures task-relative information, semantic, constraint, capability and artifact preservation across A2A and MCP boundaries. Transfidelity is an alternative provisional name. The framework is functional for finite development tasks and genuine loopback SDK/bridge execution. Human-reviewed gold, held-out scores, live-model application qualification and general scientific novelty remain **Not Established**.

## Run from a source checkout

Python 3.12+; tested with 3.13.1. No third-party Python runtime dependency is needed:

```powershell
python -B scripts/boundaryx.py routes
python -B scripts/boundaryx.py check-history --output results/development/my-history-001
python -B scripts/boundaryx.py reproduce --output results/development/my-reproduction-001
python -B scripts/boundaryx.py heldout-status
```

Use a new output allocation. `check-history` regrades saved evidence and runs software controls. `reproduce` also executes finite diagnostics and the separate admission demonstration. Install pinned upstream Node dependencies using [REPRODUCIBILITY](docs/REPRODUCIBILITY.md), then add `--protocols` for genuine A2A/MCP execution. These commands make zero model calls.

Optional editable installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\boundaryx.exe routes
```

| Material | Status | Scope |
| --- | --- | --- |
| 1,920 diagnostics / 6,400 repair interventions | Reproduced / Historical Evidence | Ten authored families, finite four-group repair universe |
| 480 protocol episodes / 960 read probes | Reproduced / Historical Evidence | Genuine protocols, deterministic receiver, controlled injections |
| 80 artifact tasks / 20 raw recoveries | Reproduced / Historical Evidence | Unchanged upstream fixture, same-task recovery |
| Separate SQLite and wire verifier | Completed | No legacy receiver, gold or scoring imports |
| 24 representative development examples | Pending Human Review | All judgments blank |
| 20 frozen new held-out candidates | Pending Human Review | Provisional gold, zero evaluations |
| Outside reproduction and live LLM evaluation | Pending External Evaluation | No completed external scientific evaluation claimed |

See [FINAL_REPORT](docs/FINAL_REPORT.md) for newly reproduced experiments and actual validation commands. [The original supervisor report](SUPERVISOR_HANDOFF_2026-11-13.md) and [static evidence explorer](demo/benchmark-v2/index.html) preserve development conclusions.

The modular package is `src/boundaryx`. The `interoperability` compatibility package and versioned scripts preserve historical APIs/metrics. New work uses `benchmarks/development`, `benchmarks/heldout` and `results/development`; historical `benchmark/` and `runs/` paths remain for manifest identity. [Algo V1 and later admission research](research/admission/README.md) is a separate research module.

Read [REPOSITORY_AUDIT](docs/REPOSITORY_AUDIT.md), [ARCHITECTURE](docs/ARCHITECTURE.md), [EXPERIMENT_PROTOCOL](docs/EXPERIMENT_PROTOCOL.md), [METRICS](docs/METRICS.md), [LIMITATIONS](docs/LIMITATIONS.md), [HUMAN_REVIEW](docs/HUMAN_REVIEW.md) and [RELATED_WORK](docs/RELATED_WORK.md).

No project-wide license has been invented. Third-party licenses retain their original scope in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). Attribution, version history and selected file hashes are under `provenance/`. Local instructions, credentials and machine configuration are excluded from Git.
