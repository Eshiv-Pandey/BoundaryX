"""Run checked shared-admission examples and the four-arm benchmark once.

This software rehearsal uses authored development profiles, frozen Python source
and sequential workers. It does not launch a live application or call a model.
An existing output directory is always refused, including failed attempts.
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
SUITE = Path("examples/benchmark-development/recipe-v1.json")
COMPARISON = "interoperability.shared_lifting_comparison_v3"
ADMISSION = "interoperability.shared_admission_v1"
METHODS = ("baseline", "direct_pruned", "candidate", "shared_lift")
EXAMPLES = (
    ("supported", "04-correlated-prefix-refinement.json", "correlated-prefix-refinement", "supported", 100000),
    ("unsupported", "02-fixed-text-shape-obstruction.json", "fixed-text-shape-obstruction", "unsupported", 100000),
    ("unknown", "07-opaque-serialization.json", "opaque-serialization", "unknown", 100000),
    ("budget-unknown", "04-correlated-prefix-refinement.json", "correlated-prefix-refinement", "unknown", 1),
)
BOOT = (
    "import importlib,sys; sys.path.insert(0,sys.argv[1]); "
    "raise SystemExit(importlib.import_module(sys.argv[2]).main(sys.argv[3:]))"
)


def read(path: Path):
    return json.loads(path.read_bytes())


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def write(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def record(path: Path, base: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular input file: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(base).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def inventory() -> tuple[dict, list[dict]]:
    suite = read(ROOT / SUITE)
    if (suite["schema_version"] != "admission-benchmark-suite/1"
            or suite["id"] != "recipe-development-comparison-v1"
            or suite["split"] != "development"
            or type(suite["evaluation_clock"]) is not int or suite["evaluation_clock"] != 100
            or len(suite["cases"]) != 11):
        raise ValueError("This rehearsal requires the original eleven-case development suite at clock 100")
    paths = {ROOT / SUITE, Path(__file__).resolve()}
    paths.update((ROOT / "src/interoperability").rglob("*.py"))
    paths.update((ROOT / SUITE.parent / case["path"]).resolve() for case in suite["cases"])
    return suite, [record(path, ROOT) for path in sorted(paths)]


def stable_result(result: dict) -> dict:
    # Every other field, including complete certificates and charged work, is
    # compared with JSON type distinctions. Only this measured duration varies.
    result = json.loads(canonical(result))
    if type(result.get("stats")) is dict:
        result["stats"].pop("elapsed_ns", None)
    return result


def validate_command(step: dict, output: Path) -> dict:
    report = read(output / f"{step['name']}.stdout.json")
    if step["kind"] == "admit":
        retained = read(Path(step["output"]))
        projected = {"status": retained["status"], "method": retained["method"],
            "case": retained["runtime_manifest"].get("id"), "decision": retained["result"].get("decision"),
            "reason": retained["result"].get("reason"), "work_budget": retained["work_budget"],
            "certificate_valid": retained["certificate_valid"], "error": retained.get("error"),
            "output": step["output"]}
        if canonical(report) != canonical(projected):
            raise ValueError("Admission stdout differs from its retained receipt projection")
        report = retained
        if (report["schema_version"] != "shared-admission-command/1"
                or report["status"] != "recorded" or report["method"] != "shared_lift"
                or report["solver_module"] != "interoperability.refinement_shared_lift_v2"
                or report["checker_module"] != "interoperability.direct_goal_pruned_v2"
                or report["checker_entrypoint"] != "check_certificate"
                or report["evaluation_clock"] != 100 or report["work_budget"] != step["budget"]
                or report["result"]["decision"] != step["decision"]
                or report["input_sha256"] != hashlib.sha256(Path(step["input"]).read_bytes()).hexdigest()
                or canonical(report["runtime_manifest"]) != canonical(read(Path(step["input"])))):
            raise ValueError("Admission receipt differs from the declared example")
        if step["decision"] == "unknown":
            if (report["certificate_valid"] is not None or report["result"].get("certificate") is not None
                    or report["checker_invoked"] is not False):
                raise ValueError("Unknown admission must not carry a conclusive certificate")
            if report["unknown_has_no_certificate"] is not True:
                raise ValueError("Unknown certificate check was not recorded")
        elif (report["certificate_valid"] is not True or report["result"].get("certificate") is None
                or report["checker_invoked"] is not True):
            raise ValueError("Conclusive admission lacks an accepted certificate")
        if step["name"] == "budget-unknown" and report["result"]["reason"] != "work_budget_exhausted":
            raise ValueError("The small-budget example did not demonstrate budget exhaustion")
        return {"decision": report["result"]["decision"], "certificate_valid": report["certificate_valid"]}
    if step["kind"] in ("run", "replay"):
        if (report["schema_version"] != "shared-lifting-comparison-run/3"
                or report["status"] != "passed" or report["summary"]["status"] != "passed"
                or report["source_package"] != step["source_package"]
                or report["bundle"] != step["output"]
                or canonical(report["summary"]) != canonical(read(Path(step["output"]) / "summary.json"))):
            raise ValueError("Comparison command did not produce the declared passing bundle")
        if step["kind"] == "replay" and report["replay_of"] != str(output / "benchmark"):
            raise ValueError("Replay source differs from this rehearsal's captured benchmark")
        report = report["verification"]
    if (report["schema_version"] != "shared-lifting-comparison-verification/3"
            or report["status"] != "passed" or report["benchmark_status"] != "passed"
            or report["case_records"] != 11):
        raise ValueError("Bundle consistency and benchmark outcome must both pass")
    return {"benchmark_status": report["benchmark_status"], "case_records": report["case_records"],
            "worker_jobs_bound": report["worker_jobs_bound"],
            "certificate_jobs_bound": report["certificate_jobs_bound"]}


def rows(bundle: Path) -> list[dict]:
    return [json.loads(line) for line in (bundle / "results.jsonl").read_bytes().splitlines()]


def inspect_results(output: Path) -> dict:
    bundle = output / "benchmark"
    results = rows(bundle)
    by_id = {row["case_id"]: (index, row) for index, row in enumerate(results)}
    examples = []
    for name, _, profile_id, decision, _ in EXAMPLES[:3]:
        index, row = by_id[profile_id]
        arm = row["algorithms"]["shared_lift"]
        result = arm["execution"]["result"]
        standalone = read(output / f"{name}.json")
        if (result["decision"] != decision or arm["valid_result"] is not True
                or canonical(stable_result(result)) != canonical(stable_result(standalone["result"]))):
            raise ValueError("Standalone example differs from its four-arm benchmark result")
        label = f"case-{index:04d}-shared_lift"
        checker = None
        if decision != "unknown":
            checker = read(bundle / "jobs" / (label + "-certificate") / "reply.json")
            if arm["certificate_valid"] is not True or checker.get("result") is not True:
                raise ValueError("Inspection example lacks an accepted checker reply")
        elif "certificate_check" in arm or result.get("certificate") is not None:
            raise ValueError("Unknown inspection example unexpectedly has a certificate check")
        examples.append({"profile_id": profile_id, "standalone_receipt": f"{name}.json",
            "input": f"benchmark/{row['input_snapshot']}", "model_sha256": row["model_sha256"],
            "reply": f"benchmark/jobs/{label}/reply.json", "result": result,
            "certificate_reply": f"benchmark/jobs/{label}-certificate/reply.json" if checker is not None else None,
            "certificate_check": checker, "certificate_valid": arm["certificate_valid"]})
    summary = read(bundle / "summary.json")
    keys = ("supported", "unsupported", "unknown", "conclusive", "certificates_valid",
            "certificates_invalid", "certificate_check_errors", "errors", "decision_agreements")
    return {"schema_version": "shared-admission-demo-inspection/1", "status": "passed",
            "cases": summary["cases"], "examples": examples,
            "budget_exhaustion_receipt": "budget-unknown.json",
            "budget_exhaustion_result": read(output / "budget-unknown.json")["result"],
            "algorithms": {method: {key: summary["algorithms"][method][key] for key in keys} for method in METHODS},
            "summary": "benchmark/summary.json", "verification": "verify.stdout.json",
            "claim_limit": "Authored eleven-case software rehearsal; no live task, novelty, superiority or completion-percentage claim."}


def compare_replay(output: Path) -> dict:
    original, repeated = rows(output / "benchmark"), rows(output / "replay")
    if len(original) != 11 or len(repeated) != len(original):
        raise ValueError("Replay case count differs")
    for first, second in zip(original, repeated):
        for key in ("case_id", "model_sha256", "input_schema", "family", "evaluation_clock"):
            if canonical(first[key]) != canonical(second[key]):
                raise ValueError("Replay case identity/input/clock differs: " + key)
        if canonical(stable_result(first["reference"]["result"])) != canonical(stable_result(second["reference"]["result"])):
            raise ValueError("Replay reference result differs")
        for method in METHODS:
            a, b = first["algorithms"][method], second["algorithms"][method]
            if (canonical(stable_result(a["execution"]["result"])) != canonical(stable_result(b["execution"]["result"]))
                    or a["certificate_valid"] is not b["certificate_valid"]
                    or ("certificate_check" in a) != ("certificate_check" in b)):
                raise ValueError("Replay algorithm result/certificate differs: " + method)
            if "certificate_check" in a and canonical(a["certificate_check"]["result"]) != canonical(b["certificate_check"]["result"]):
                raise ValueError("Replay checker result differs: " + method)
    return {"status": "passed", "cases": len(original), "algorithm_results_compared": len(original) * len(METHODS),
            "reference_results_compared": len(original), "excluded_result_fields": ["stats.elapsed_ns"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Unused directory; existing attempts are refused")
    parser.add_argument("--replay", action="store_true", help="Also run and verify the captured-source replay")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite existing demonstration: {output}")
    if any(output.is_relative_to(ROOT / name) for name in ("src", "examples", "scripts")):
        parser.error("keep demonstration output outside the source and input directories")
    suite, before = inventory()
    prepared = output / "prepared"
    prefix = [sys.executable, "-I", "-S", "-B", "-c", BOOT, str(prepared / "src")]
    steps = []
    for name, filename, _, decision, budget in EXAMPLES:
        source = prepared / "examples/refinement-development" / filename
        target = output / f"{name}.json"
        steps.append({"name": name, "kind": "admit", "input": str(source), "output": str(target),
            "decision": decision, "budget": budget, "requires": [],
            "argv": prefix + [ADMISSION, "--input", str(source), "--method", "shared_lift",
                "--work-budget", str(budget), "--now", "100", "--output", str(target)]})
    steps.extend([
        {"name": "benchmark", "kind": "run", "requires": [item[0] for item in EXAMPLES],
         "output": str(output / "benchmark"), "source_package": str(prepared / "src/interoperability"),
         "argv": prefix + [COMPARISON, "run", "--suite", str(prepared / SUITE), "--work-budget", "100000",
                             "--timeout-seconds", "30", "--output", str(output / "benchmark")]},
        {"name": "verify", "kind": "verify", "requires": ["benchmark"],
         "argv": prefix + [COMPARISON, "verify", str(output / "benchmark")]},
    ])
    if args.replay:
        steps.extend([
            {"name": "replay", "kind": "replay", "requires": ["verify"], "output": str(output / "replay"),
             "source_package": str(output / "benchmark/source/interoperability"),
             "argv": prefix + [COMPARISON, "replay", str(output / "benchmark"), "--output", str(output / "replay")]},
            {"name": "verify-replay", "kind": "verify", "requires": ["replay"],
             "argv": prefix + [COMPARISON, "verify", str(output / "replay")]},
        ])
    output.mkdir(parents=True, exist_ok=False)
    plan = {"schema_version": "shared-admission-demonstration-plan/1",
            "prepared_at_utc": datetime.now(timezone.utc).isoformat(), "inputs": before,
            "recipe_suite": suite, "evaluation_clock": 100, "benchmark_work_budget": 100000,
            "worker_timeout_seconds": 30, "steps": steps, "replay_requested": args.replay,
            "scope": "Authored development software demonstration; no live application or model execution",
            "success_criteria": ["All scheduled commands and their recorded outcomes pass",
                "Supported and unsupported examples have accepted independent certificates",
                "Opaque and budget-exhausted examples remain unknown", "All eleven cases and four arms verify",
                "Standalone and benchmark examples agree", "Source and input bytes remain unchanged",
                "If requested, captured replay agrees except stats.elapsed_ns"]}
    write(output / "plan.json", plan)
    completed, errors, after, copied_after = {}, [], None, None
    inspection, replay_comparison = None, None
    try:
        for expected in before:
            source, target = ROOT / expected["path"], prepared / expected["path"]
            raw = source.read_bytes()
            if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                raise ValueError("Input changed before frozen capture: " + expected["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(raw)
        for step in steps:
            name = step["name"]
            receipt = {"name": name, "argv": step["argv"], "cwd": str(output),
                       "status": "not_run_dependency_failed", "returncode": None}
            if all(completed[item]["status"] == "passed" for item in step["requires"]):
                print(f"Running {name}...", flush=True)
                receipt["started_at_utc"] = datetime.now(timezone.utc).isoformat()
                tick = time.perf_counter_ns()
                try:
                    with (output / f"{name}.stdout.json").open("xb") as stdout, (output / f"{name}.stderr.txt").open("xb") as stderr:
                        child = subprocess.run(step["argv"], cwd=output, stdin=subprocess.DEVNULL,
                                               stdout=stdout, stderr=stderr)
                    receipt["returncode"] = child.returncode
                    if child.returncode != 0:
                        raise ValueError(f"Command exited with {child.returncode}; retained stdout/stderr contain the outcome")
                    receipt["validated_outcome"] = validate_command(step, output)
                    receipt["status"] = "passed"
                except (OSError, ValueError, KeyError, TypeError) as error:
                    receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
                receipt["wall_ns"] = time.perf_counter_ns() - tick
            completed[name] = receipt
            write(output / f"{name}-command.json", receipt)
            print(f"  {name}: {receipt['status']}", flush=True)
        if completed["verify"]["status"] == "passed":
            inspection = inspect_results(output)
            write(output / "inspection.json", inspection)
        if args.replay and completed["verify-replay"]["status"] == "passed":
            replay_comparison = compare_replay(output)
            write(output / "replay-comparison.json", replay_comparison)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    finally:
        try:
            _, after = inventory()
            copied_after = [record(path, prepared) for path in sorted(prepared.rglob("*")) if path.is_file()]
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"Final inventory: {type(error).__name__}: {error}")
        unchanged = before == after and before == copied_after
        passed = (not errors and unchanged and len(completed) == len(steps)
                  and all(item["status"] == "passed" for item in completed.values())
                  and inspection is not None and (not args.replay or replay_comparison is not None))
        receipt = {"schema_version": "shared-admission-demonstration/1", "status": "passed" if passed else "failed",
            "finished_at_utc": datetime.now(timezone.utc).isoformat(), "inputs_unchanged": unchanged,
            "inputs_after": after, "frozen_inputs_after": copied_after, "steps": list(completed.values()),
            "errors": errors, "inspection": "inspection.json" if inspection is not None else None,
            "replay_comparison": replay_comparison, "application_requests": 0, "live_model_calls": 0,
            "claim_limit": plan["scope"]}
        write(output / "result.json", receipt)
    print(f"Demonstration {receipt['status']}: {output / 'result.json'}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
