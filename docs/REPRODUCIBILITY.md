# Reproducibility

Status: source-checkout artifact. Python 3.13.1 and Node v22.13.0 were used on Windows. Every new experiment has an unused allocation, before/after code hashes, timestamps, captured commands/stdout/stderr, actual exit codes and manifests. Canonical unredacted machine command/configuration captures remain local; distributed derivatives and their original hashes are labeled in provenance. Scientific payloads/metrics remain unchanged.

## Offline checks

```powershell
git clone https://github.com/Eshiv-Pandey/BoundaryX.git
cd BoundaryX
python -B scripts/boundaryx.py check-history --output results/development/clean-history-001
python -B scripts/boundaryx.py reproduce --output results/development/clean-finite-001
python -B scripts/boundaryx.py heldout-status
```

Private repository access is required. Offline means no protocol/model request; Git clone and optional dependency installation require network access. The check regrades historical bytes, executes software controls and runs a separate verifier. `reproduce` adds 1,920 new finite development diagnostics and the separate algorithm/replay demonstration. It is not new held-out evaluation. Existing output paths are refused.

## Genuine protocol reproduction

Install dependencies only in the new checkout, preserving upstream locks:

```powershell
cd external/a2a-to-mcp
npm.cmd ci --ignore-scripts --no-audit --no-fund
node node_modules/typescript/bin/tsc -p tsconfig.build.json
node node_modules/vitest/vitest.mjs run test/integration/send-message.test.ts test/integration/tasks-extension.test.ts
cd ../mcp-a2a
npm.cmd exec --yes --package=pnpm@12.10.1 -- pnpm install --frozen-lockfile --ignore-scripts
npm.cmd run build -- --config-loader tsx
cd ../..
python -B scripts/restore_pinned_builds.py
python -B scripts/boundaryx.py reproduce --output results/development/clean-real-001 --protocols
```

On Linux/macOS use `npm` rather than `npm.cmd`. npm child scripts must be able to find Node in PATH. A fresh tsdown build can change hashed mgcrea chunk filenames, while unchanged historical runners pin the retained filename. The hash-checking restore copies the licensed original build; no mock or replacement protocol is used. The frozen runtime locks install official A2A/MCP SDKs separately. Dist files are deliberately retained in Git as evidence/build inputs.

The full command regrades saved evidence, executes controls, reproduces finite diagnostics, runs admission/replay, executes 480 actual loopback protocol episodes and 80 actual upstream artifact tasks, then runs legacy and separate checks. Model calls remain zero. Wall times are new observations, not expected to equal history. Inference/provider credentials are not required.

## Development validation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe
python -B -m unittest discover -s tests -p 'test_boundaryx*.py' -v
python -B scripts/loss_json_io_v2.py --self-test
python -B scripts/check_loss_software_v2.py --output results/development/software-new-001
python -B scripts/boundaryx.py manifest benchmarks/heldout/v2
python -B scripts/boundaryx.py verify-independent --diagnostics results/development/clean-real-001/pipeline/fresh-diagnostics --protocol results/development/clean-real-001/pipeline/fresh-protocol --artifacts results/development/clean-real-001/pipeline/fresh-artifacts --output results/development/independent-new.json
```

The historical suite has 278 passes and one Windows symlink skip in the fresh reproduction; the five differential delivery I/O controls are separate. New adverse-evidence controls and type/lint results are in FINAL_REPORT. Lint/type checking applies to new BoundaryX code; unchanged archival implementations are covered by their relevant regression suites, not represented as newly lint-clean code.

Twenty held-out proposals and their manifest are frozen. Do not rerun the preparation script over them. Named human/supervisor review is pending; corrections require a new freeze before qualified execution. Final evaluation, live LLM tasks and independent external scientific reproduction remain Not Established.
