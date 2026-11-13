# Run the benchmark framework handoff

Start with [the supervisor report](../../SUPERVISOR_HANDOFF_2026-11-13.md).
The release contains source, tests, captures, checkers, figures and a static
evidence explorer. Unknowns, failed attempts and development scope remain explicit.

## Offline check in an extracted package

Python 3.12 or later; tested with 3.13.1. No pip installation is required.
From the extracted root, choose a new output allocation:

```powershell
python -B scripts/run_loss_handoff_v2.py --output runs/my-check-001
```

The command regrades all three final evidence allocations and runs the benchmark
and finite-model software controls. It records every stage's command, stdout,
stderr, return code and duration. An existing allocation is refused; a failed
allocation is retained. No network service, model or provider call occurs.

Large summary outputs use a declared streaming adapter with the frozen canonical
JSON settings. Only the output writer is replaced at runtime; task/gold/receiver,
conversion/scoring/checking functions stay fixed. Five differential byte and
publication controls run first; wrapper/test source and hashes are captured in
the pipeline output. This keeps delivery exports bounded on the low-memory host.

To additionally execute a new local diagnostic bank and the finite admission
demonstration with captured replay:

```powershell
python -B scripts/run_loss_handoff_v2.py --output runs/my-reproduction-001 --reproduce
```

Read `result.json` and the stage subdirectories. Reproduction of the same seeded
development bank is not new held-out evaluation; timing is not expected to match.
Saved protocol regrading is not fresh protocol execution.

To check every ZIP member against its delivery manifest, use
`python -B scripts/verify_loss_package_v2.py --zip path/to/the-sharing.zip`.
The adjacent `.sha256` file records the final archive digest.

## Inspect without running experiments

Open `demo/benchmark-v2/index.html` directly. For local HTTP links/JSON viewing:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open http://127.0.0.1:8765/demo/benchmark-v2/ . Controls select saved evidence.
Keep the report, demo and runs together. PNG/SVG figures and provenance are under
`reports/supervisor-20261113/images`.

## Fresh genuine protocol execution

This path needs the full upstream checkouts and their Node dependencies. The
sharing package deliberately carries captured source/build files for verification,
not the installations. Use a separate full checkout and Node 22.13.0. Acquire:

```powershell
git clone https://github.com/AmirK-S/a2a-to-mcp.git external/a2a-to-mcp
git -C external/a2a-to-mcp checkout --detach 58eff9da469bccdc432bf164662727947de646b4
git clone https://github.com/mgcrea/mcp-a2a.git external/mcp-a2a
git -C external/mcp-a2a checkout --detach c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5
```

These are prospective acquisition commands for absent directories; do not clone
over the package's captured `external` files or change an existing research
checkout. In each upstream directory, follow its pinned build instructions.
Amir uses `npm ci` then `npm run build`; mgcrea uses its pinned pnpm lockfile
(`pnpm@12.10.1`, frozen-lockfile install then build). SDK pins in the tested
installations are Amir 1.1.0 and mgcrea 1.3.0. Captured package/lock/build hashes
are verified by the evidence checkers. A different rebuild is a new environment,
not byte-identical reproduction; retain its provenance and new allocation.

Once both pinned installations are present at those paths:

```powershell
python -B scripts/run_loss_handoff_v2.py --output runs/my-fresh-protocol-001 --live
```

`--live` runs new loopback A2A/MCP tasks and artifact experiments, then checks
their evidence. It still uses deterministic receivers/fixtures and makes no
model calls. It does not qualify a production application or an LLM. Existing
outputs and sources remain protected by the runners/checkers.

## Individual commands

```powershell
python -B scripts/run_loss_diagnostics_v2.py --output runs/my-diagnostics-001 --variants 16 --seed 20261113
python -B scripts/verify_loss_release_v2.py --diagnostics runs/supervisor-handoff-20261113/diagnostics-final-001 --protocol runs/supervisor-handoff-20261113/protocol-main-001 --output runs/my-task-verification-001
python -B scripts/verify_loss_parts_v2.py --bundle runs/supervisor-handoff-20261113/parts-main-001 --output runs/my-artifact-verification-001
python -B scripts/check_loss_software_v2.py --output runs/my-software-001
python -B scripts/run_shared_admission_demo_v1.py --output runs/my-admission-001 --replay
```

Optional figure regeneration: install matplotlib and Pillow in a development
environment, then run `python -B scripts/build_loss_figures_v2.py`.
Optional browser checks use Playwright in a separate development folder and
`scripts/check_loss_explorer_v2.mjs`; they are not benchmark runtime dependencies.

## Evidence scope and licenses

The main report names the exact final allocations. Diagnostic variants, controlled
protocol tasks, repeated upstream artifact commands and historical captures remain
separate. Human gold review, untouched evaluation and scientific novelty remain
open. Source for upstream text projection and exact upstream license notices is
included; see [third-party notices](../../THIRD_PARTY_NOTICES.md).
