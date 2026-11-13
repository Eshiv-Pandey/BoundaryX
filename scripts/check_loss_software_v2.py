"""Run all benchmark and core finite-model controls with retained process receipts."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SUITES = ["test_loss_benchmark_v1", "test_loss_benchmark_runner_v1", "test_loss_benchmark_retained_v1",
          "test_verify_loss_benchmark_v1", "test_capture_loss_benchmark_inputs_v1",
          "test_loss_diagnostics_v2", "test_loss_release_verifiers_v2"]
CORE = ["test_baseline", "test_refinement", "test_refinement_shared_lift_v2", "test_direct_goal_pruned_v2",
        "test_oracle", "test_direct_comparison_v2", "test_shared_lifting_comparison_v3", "test_benchmark_resources_v1",
        "test_benchmark", "test_refinement_scaling_generator_v1", "test_shared_admission_v1"]
BOOT = """import json,sys,unittest
from pathlib import Path
root=Path(sys.argv[1]); sys.path[:0]=[str(root/'src'),str(root/'tests'),str(root/'scripts'),str(root)]
suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[2:])
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'successful':result.wasSuccessful()}))
raise SystemExit(0 if result.wasSuccessful() else 1)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    rows = []
    for name, suites in (("benchmark", SUITES), ("core", CORE)):
        command = [sys.executable, "-B", "-c", BOOT, str(ROOT), *suites]
        began = time.perf_counter()
        process = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        for suffix, blob in (("stdout.txt", process.stdout), ("stderr.txt", process.stderr)):
            with (args.output / (name + "-" + suffix)).open("xb") as handle:
                handle.write(blob)
        summary = json.loads(process.stdout.splitlines()[-1])
        rows.append({"suite": name, "modules": suites, "exit_code": process.returncode, "result": summary,
                     "wall_seconds": time.perf_counter() - began,
                     "test_files": [{"path": "tests/" + suite + ".py", "sha256": hashlib.sha256((ROOT / "tests" / (suite + ".py")).read_bytes()).hexdigest()} for suite in suites]})
        print(json.dumps(rows[-1]), flush=True)
    result = {"schema_version": "loss_software_validation_v2", "status": "passed" if all(x["exit_code"] == 0 for x in rows) else "failed",
              "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "suites": rows, "passed_tests": sum(x["result"]["run"] - x["result"]["skipped"] - x["result"]["failures"] - x["result"]["errors"] for x in rows),
              "skipped_tests": sum(x["result"]["skipped"] for x in rows)}
    with (args.output / "result.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2); stream.write("\n")
    raise SystemExit(result["status"] != "passed")


if __name__ == "__main__":
    main()
