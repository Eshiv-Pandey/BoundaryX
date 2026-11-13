"""Verify the supervisor delivery offline; optionally reproduce local experiments.

The default reads saved protocol bytes and runs software controls. --reproduce
also executes fresh finite diagnostics and the admission/replay demonstration.
--live adds genuine loopback bridge experiments and needs the full upstream
installations. Every output allocation is new; failed allocations are retained.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "runs/supervisor-handoff-20261113"


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reproduce", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    py = [sys.executable, "-B"]
    def checked(script, *arguments):
        return py + ["scripts/loss_json_io_v2.py", script, *arguments]
    io_sources = []
    for relative in ("scripts/run_loss_handoff_v2.py", "scripts/loss_json_io_v2.py", "tests/test_loss_json_io_v2.py"):
        raw = (ROOT / relative).read_bytes()
        capture = output / "pipeline-sources" / Path(relative).name
        capture.parent.mkdir(parents=True, exist_ok=True)
        with capture.open("xb") as stream:
            stream.write(raw)
        io_sources.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
    jobs = [
        ("streaming-io-controls", py + ["scripts/loss_json_io_v2.py", "--self-test"], 120),
        ("recorded-tasks", checked("verify_loss_release_v2.py", "--diagnostics", str(EVIDENCE / "diagnostics-final-001"),
            "--protocol", str(EVIDENCE / "protocol-main-001"), "--output", str(output / "recorded-tasks")), 300),
        ("recorded-artifacts", py + ["scripts/verify_loss_parts_v2.py", "--bundle", str(EVIDENCE / "parts-main-001"),
            "--output", str(output / "recorded-artifacts")], 120),
        ("software", py + ["scripts/check_loss_software_v2.py", "--output", str(output / "software")], 600),
    ]
    if args.reproduce:
        jobs += [
            ("fresh-diagnostics", checked("run_loss_diagnostics_v2.py", "--variants", "16", "--seed", "20261113",
                "--output", str(output / "fresh-diagnostics")), 300),
            ("check-fresh-diagnostics", checked("verify_loss_release_v2.py", "--diagnostics", str(output / "fresh-diagnostics"),
                "--output", str(output / "check-fresh-diagnostics")), 300),
            ("fresh-admission-replay", py + ["scripts/run_shared_admission_demo_v1.py", "--replay",
                "--output", str(output / "fresh-admission-replay")], 300),
        ]
    if args.live:
        jobs += [
            ("fresh-protocol", ["node", "scripts/run_loss_protocol_v2.mjs", "--bank", str(EVIDENCE / "diagnostics-final-001/input-bank.json"),
                "--variants-per-family", "1", "--python", sys.executable, "--output", str(output / "fresh-protocol")], 600),
            ("check-fresh-protocol", checked("verify_loss_release_v2.py", "--protocol", str(output / "fresh-protocol"),
                "--output", str(output / "check-fresh-protocol")), 300),
            ("fresh-artifacts", ["node", "scripts/run_loss_parts_v2.mjs", "--repetitions", "5", "--output", str(output / "fresh-artifacts")], 300),
            ("check-fresh-artifacts", py + ["scripts/verify_loss_parts_v2.py", "--bundle", str(output / "fresh-artifacts"),
                "--output", str(output / "check-fresh-artifacts")], 120),
        ]
    rows = []
    for name, command, timeout in jobs:
        print("Running " + name, flush=True)
        began = time.perf_counter()
        try:
            process = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
            error = None
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
            error = "stage_timeout"
        except OSError as exc:
            stdout, stderr, code = b"", str(exc).encode("utf-8"), None
            error = "stage_launch_error"
        for suffix, raw in (("stdout.txt", stdout), ("stderr.txt", stderr)):
            with (output / (name + "-" + suffix)).open("xb") as stream:
                stream.write(raw)
        row = {"stage": name, "command": command, "exit_code": code, "error": error,
               "wall_seconds": time.perf_counter() - began, "status": "passed" if code == 0 else "failed",
               "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("stage", "status", "exit_code", "wall_seconds")}), flush=True)
        if code != 0:
            break
    result = {"schema_version": "loss_handoff_pipeline_v2", "status": "passed" if len(rows) == len(jobs) and all(r["status"] == "passed" for r in rows) else "failed",
              "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "planned_stages": len(jobs), "executed_stages": len(rows), "reproduce_local": args.reproduce,
              "live_protocol_execution": args.live, "model_calls": 0, "stages": rows,
              "io_adapter_sources": io_sources, "io_adapter_scope": "Only canonical output serialization is streamed; frozen task/gold/receiver/conversion/scoring source is unchanged. Five differential byte/no-overwrite/rejection controls run first.",
              "scope": "Offline regrading and fresh software controls by default; local finite reproduction only with --reproduce; new real bridge execution only with --live. None constitutes human or held-out review."}
    write(output / "result.json", result)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
