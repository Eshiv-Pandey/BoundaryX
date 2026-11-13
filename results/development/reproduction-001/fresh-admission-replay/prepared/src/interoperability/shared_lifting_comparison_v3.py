"""Four-arm development comparison with shared lifting and resource observations.

Preserves the earlier solvers, checker and benchmark engine. All arms run in
fresh workers with identical resource instrumentation. Use this versioned
entrypoint for run, verification and captured-source replay.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys

from . import benchmark, benchmark_resources_v1 as resources
from . import direct_comparison_v2 as previous


ENTRYPOINT = "interoperability.shared_lifting_comparison_v3"
SCHEMA, ADAPTER, CHECKER, LEGACY = previous.SCHEMA, previous.ADAPTER, previous.CHECKER, previous.LEGACY
ALGORITHMS = (*previous.ALGORITHMS,
    benchmark.AlgorithmSpec("shared_lift", "interoperability.refinement_shared_lift_v2", input_schema=SCHEMA))


@contextmanager
def _configuration():
    # The preserved engine already serializes worker execution. This temporary
    # module-level configuration must not be used by concurrent caller threads.
    boot = benchmark._WORKER_BOOT
    with previous._adapter():
        benchmark._WORKER_BOOT = resources.WORKER_BOOT
        try:
            yield
        finally:
            benchmark._WORKER_BOOT = boot


def _recorded_path(value):
    path = PureWindowsPath(value)
    if not path.is_absolute():
        path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Worker path must be an absolute recorded path")
    return path


def _bind_job(directory, label, arm, expected, executable):
    folder = directory / "jobs" / label
    job = benchmark._json(folder / "input.json")
    if (set(job) != set(expected) | {"reply_path"}
            or benchmark.digest({k: job[k] for k in expected}) != benchmark.digest(expected)):
        raise ValueError("Worker dispatch differs from declared comparison: " + label)
    process = benchmark._json(folder / "process.json")
    argv = process["argv"]
    if len(argv) != 8 or argv[:6] != [executable, "-I", "-S", "-B", "-c", resources.WORKER_BOOT]:
        raise ValueError("Worker did not dispatch the resource observer: " + label)
    source_path, job_path = map(_recorded_path, argv[-2:])
    if (job_path.name != "input.json" or job_path.parent.name != label
            or job_path.parent.parent.name != "jobs"
            or source_path != job_path.parents[2] / "source"
            or _recorded_path(job["reply_path"]) != job_path.with_name("reply.json")):
        raise ValueError("Recorded worker paths are inconsistent: " + label)
    reply_path = folder / "reply.json"
    if process["timed_out"]:
        derived = {"status": "timed_out", "process": process}
    elif process["returncode"] != 0 or not reply_path.exists():
        derived = {"status": "worker_failed", "process": process}
    else:
        try:
            reply = benchmark._json(reply_path)
            if type(reply) is not dict:
                raise ValueError("worker reply is not an object")
            derived = {**reply, "process": process}
        except (OSError, ValueError) as error:
            derived = {"status": "invalid_worker_reply", "error": str(error), "process": process}
    if benchmark.digest(arm) != benchmark.digest(derived):
        raise ValueError("Case record differs from worker reply/process: " + label)
    if arm["status"] in ("returned", "error") and "resources" not in arm:
        raise ValueError("Completed worker is missing its resource observation: " + label)
    resources.summarize([arm])
    return source_path


def _resource_summary(rows):
    output = {"reference": resources.summarize([row["reference"] for row in rows]), "algorithms": {}}
    for spec in ALGORITHMS:
        evaluations = [row["algorithms"][spec.name]["execution"] for row in rows]
        checks = [row["algorithms"][spec.name]["certificate_check"] for row in rows
                  if "certificate_check" in row["algorithms"][spec.name]]
        output["algorithms"][spec.name] = {
            "evaluation": resources.summarize(evaluations), "certificate": resources.summarize(checks),
            "evaluation_and_certificate": resources.summarize(evaluations + checks)}
    return output


def _validate_outcomes(row):
    reference_valid = benchmark._valid_decision(row["reference"])
    if row["reference_valid"] is not reference_valid:
        raise ValueError("Reference validity flag differs from retained reply")
    for spec in ALGORITHMS:
        arm = row["algorithms"][spec.name]
        reply = arm["execution"]
        valid = benchmark._valid_decision(reply)
        if arm["status"] != "recorded" or arm["valid_result"] is not valid:
            raise ValueError("Algorithm validity flag differs from retained reply")
        needs_check = valid and reply["result"]["decision"] != "unknown"
        if ("certificate_check" in arm) is not needs_check:
            raise ValueError("Required certificate check is missing or unexpected")
        certificate_valid = None
        if needs_check:
            check = arm["certificate_check"]
            if (check.get("status") == "returned" and check.get("input_unchanged") is True
                    and type(check.get("result")) is bool):
                certificate_valid = check["result"]
        if arm["certificate_valid"] is not certificate_valid:
            raise ValueError("Certificate validity flag differs from retained checker reply")
        agreement = (reply["result"]["decision"] == row["reference"]["result"]["decision"]
                     if valid and reference_valid else None)
        if arm["decision_agreement"] is not agreement:
            raise ValueError("Decision agreement flag differs from retained replies")


def verify(directory: Path) -> dict:
    """Reconcile source, inputs, every dispatch/reply and all reported resources."""
    directory = Path(directory).resolve()
    checked = benchmark.verify_bundle(directory)
    execution = benchmark._json(directory / "execution.json")
    if (execution["input_schema"] != SCHEMA or execution["schema_adapter"] != ADAPTER
            or execution["algorithms"] != [asdict(spec) for spec in ALGORITHMS]
            or execution["reference_implementation_is_baseline"] is not True):
        raise ValueError("Bundle does not declare the exact four-arm comparison")
    inventory = {r["path"]: r for r in benchmark._json(directory / "manifest.json")["files"]}
    required = ["source/interoperability/" + name + ".py" for name in (
        "shared_lifting_comparison_v3", "benchmark_resources_v1", "refinement_shared_lift_v2",
        "direct_comparison_v2", "direct_goal_pruned_v2", "refinement_oracle", "refinement", "benchmark")]
    if any(name not in inventory for name in required):
        raise ValueError("Comparison source closure is missing")
    rows = [json.loads(line) for line in (directory / "results.jsonl").read_bytes().splitlines()]
    roots, jobs, checks = set(), 0, 0
    for index, row in enumerate(rows):
        _validate_outcomes(row)
        model = benchmark._json(directory / row["input_snapshot"])
        base = {"runtime_manifest": model, "now": execution["evaluation_clock"]}
        arms = [("reference", LEGACY, row["reference"])] + [
            (spec.name, spec.module, row["algorithms"][spec.name]["execution"]) for spec in ALGORITHMS]
        for name, module, arm in arms:
            expected = {**base, "kind": "evaluate", "module": module, "entrypoint": "evaluate",
                        "keyword_arguments": {"budget": execution["work_budget"]}}
            roots.add(_bind_job(directory, f"case-{index:04d}-{name}", arm, expected,
                                execution["runtime"]["executable"]))
            jobs += 1
        for spec in ALGORITHMS:
            arm = row["algorithms"][spec.name]
            if "certificate_check" not in arm:
                continue
            expected = {**base, "kind": "certificate", "module": CHECKER,
                        "entrypoint": "check_certificate", "result": arm["execution"]["result"]}
            roots.add(_bind_job(directory, f"case-{index:04d}-{spec.name}-certificate",
                                arm["certificate_check"], expected, execution["runtime"]["executable"]))
            checks += 1
            jobs += 1
    if len(roots) != 1:
        raise ValueError("Workers used different recorded source roots")
    actual_labels = {path.name for path in (directory / "jobs").iterdir() if path.is_dir()}
    if len(actual_labels) != jobs:
        raise ValueError("Unexpected worker jobs in bundle")
    return {**checked, "schema_version": "shared-lifting-comparison-verification/3",
            "entrypoint": ENTRYPOINT, "checker": CHECKER, "worker_jobs_bound": jobs,
            "benchmark_status": benchmark._json(directory / "summary.json")["status"],
            "certificate_jobs_bound": checks, "sources": [inventory[name] for name in required],
            "resource_summary": _resource_summary(rows),
            "invocation_provenance": "Local record consistency; use the outer receipt for invocation evidence."}


def run(suite_path: Path, output: Path, *, work_budget=100000, timeout_seconds=30.0) -> dict:
    suite_path, output = Path(suite_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Refusing to overwrite an existing comparison bundle")
    if type(work_budget) is not int or work_budget <= 0:
        raise ValueError("Require a positive explicit integer work budget")
    package = Path(__file__).resolve().parent
    with _configuration():
        _, cases = benchmark._suite(suite_path)
        if any(model["schema_version"] != SCHEMA for _, _, model in cases):
            raise ValueError("The versioned comparison accepts recipe-continuation/1 only")
        summary = benchmark.run_benchmark(suite_path, output, list(ALGORITHMS),
            work_budget=work_budget, timeout_seconds=timeout_seconds, package_dir=package)
    checked = verify(output)
    return {"schema_version": "shared-lifting-comparison-run/3", "status": summary["status"],
            "entrypoint": ENTRYPOINT, "checker": CHECKER, "source_package": str(package),
            "bundle": str(output), "summary": summary, "verification": checked,
            "claim_limit": "Authored development comparison; ordinary memoization, no established novelty or superiority."}


def replay(directory: Path, output: Path) -> dict:
    directory, output = Path(directory).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Refusing to overwrite an existing comparison replay")
    verify(directory)
    execution = benchmark._json(directory / "execution.json")
    boot = (
        "import json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from interoperability.shared_lifting_comparison_v3 import run; "
        "d=Path(sys.argv[2]); e=json.loads((d/'execution.json').read_bytes()); "
        "r=run(d/'replay-suite.json',Path(sys.argv[3]),work_budget=e['work_budget'],"
        "timeout_seconds=e['timeout_seconds']); print(json.dumps(r)); "
        "raise SystemExit(0 if r['status']=='passed' else 1)"
    )
    cases = len(benchmark._json(directory / "replay-suite.json")["cases"])
    timeout = 120 + cases * (1 + 2 * len(ALGORITHMS)) * execution["timeout_seconds"]
    completed = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", boot,
        str(directory / "source"), str(directory), str(output)], cwd=directory,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        raise ValueError("Captured comparison replay failed: " + completed.stderr.decode("utf-8", errors="replace")[-4000:])
    result = json.loads(completed.stdout)
    if result["source_package"] != str(directory / "source/interoperability"):
        raise ValueError("Replay did not report the captured comparison source package")
    result["verification"] = verify(output)
    result["replay_of"] = str(directory)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--suite", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--work-budget", type=int, default=100000)
    execute.add_argument("--timeout-seconds", type=float, default=30.0)
    check = commands.add_parser("verify")
    check.add_argument("directory", type=Path)
    repeat = commands.add_parser("replay")
    repeat.add_argument("directory", type=Path)
    repeat.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run(args.suite, args.output, work_budget=args.work_budget, timeout_seconds=args.timeout_seconds)
    elif args.command == "verify":
        result = verify(args.directory)
    else:
        result = replay(args.directory, args.output)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
