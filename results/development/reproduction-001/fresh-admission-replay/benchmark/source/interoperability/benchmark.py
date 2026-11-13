"""Reproducible development benchmark for schema-compatible admission plugins.

Workers receive only a copied runtime manifest and the shared evaluation clock.
They execute a captured package snapshot, never an archived application run.
The independent finite oracle and certificate checker remain separate jobs.
This is software benchmarking, not a held-out study or proof of method novelty.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import re
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .manifest import SCHEMA, digest, load as load_model

DECISIONS = ("supported", "unsupported", "unknown")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_MODULE = re.compile(r"interoperability(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z")


@dataclass(frozen=True)
class AlgorithmSpec:
    name: str
    module: str
    entrypoint: str = "evaluate"
    input_schema: str = SCHEMA

    def validate(self) -> None:
        if not _NAME.fullmatch(self.name) or self.name == "reference":
            raise ValueError("invalid or reserved algorithm name")
        if not _MODULE.fullmatch(self.module) or not self.entrypoint.isidentifier():
            raise ValueError("algorithm must name an interoperability package function")
        if type(self.input_schema) is not str or not self.input_schema:
            raise ValueError("algorithm input_schema must be explicit")


BASELINE = AlgorithmSpec("baseline", "interoperability.baseline")

# Adapters name actual input formats and independent validators. A recipe
# profile is never coerced to its inner finite graph for candidate comparison.
ADAPTERS = {
    SCHEMA: {"baseline": "interoperability.baseline", "reference": "interoperability.oracle",
             "checker": "interoperability.oracle", "supports_budget": False},
    "recipe-continuation/1": {"baseline": "interoperability.refinement_oracle",
             "reference": "interoperability.refinement_oracle", "checker": "interoperability.refinement_oracle",
             "supports_budget": True},
}
MODULE_SCHEMAS = {"interoperability.refinement": "recipe-continuation/1",
                  "interoperability.refinement_oracle": "recipe-continuation/1"}


def _load_input(path: Path) -> dict:
    value = _json(path)
    if type(value) is not dict or value.get("schema_version") not in ADAPTERS:
        raise ValueError("input has no registered benchmark schema adapter")
    if value["schema_version"] == SCHEMA:
        value = load_model(path)
        provenance = value["provenance"]
    else:
        validator = importlib.import_module(ADAPTERS[value["schema_version"]]["reference"])
        validator.validate_profile(value)
        provenance = value["model"]["provenance"]
    if provenance["kind"] != "authored-development":
        raise ValueError("benchmark refuses to relabel wire-derived evidence as development")
    return value


def _provenance(value: dict) -> dict:
    return value["provenance"] if value["schema_version"] == SCHEMA else value["model"]["provenance"]


def _json(path: Path) -> Any:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key: " + key)
            value[key] = item
        return value
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def _write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def _record(path: Path, root: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def _suite(path: Path) -> tuple[dict, list[tuple[dict, Path, dict]]]:
    value = _json(path)
    if type(value) is not dict or set(value) != {"schema_version", "id", "split", "evaluation_clock", "cases"}:
        raise ValueError("invalid benchmark suite fields")
    if value["schema_version"] != "admission-benchmark-suite/1" or value["split"] != "development":
        raise ValueError("only explicit development suites are supported")
    if type(value["id"]) is not str or not value["id"] or type(value["evaluation_clock"]) is not int:
        raise ValueError("suite needs an ID and fixed integer evaluation clock")
    if type(value["cases"]) is not list or not value["cases"]:
        raise ValueError("suite needs at least one case")
    cases, ids = [], set()
    for row in value["cases"]:
        if type(row) is not dict or set(row) != {"path", "family"} or not all(
                type(row[key]) is str and row[key] for key in row):
            raise ValueError("case needs a path and family label")
        source = (path.parent / row["path"]).resolve()
        model = _load_input(source)
        if model["id"] in ids:
            raise ValueError("duplicate case ID: " + model["id"])
        ids.add(model["id"])
        cases.append((row, source, model))
    if len({model["schema_version"] for _, _, model in cases}) != 1:
        raise ValueError("use separate suites for different input schemas")
    return value, cases


def _worker(job_path: str) -> None:
    """Worker entry point used only by the parent-created job files."""
    job = _json(Path(job_path))
    model = job["runtime_manifest"]
    before = digest(model)
    reply: dict[str, Any] = {"status": "error", "input_sha256_before": before}
    tick = time.perf_counter_ns()
    try:
        module = importlib.import_module(job["module"])
        package = Path(__file__).resolve().parent
        if not Path(module.__file__).resolve().is_relative_to(package):
            raise ValueError("worker imported an algorithm outside the captured package")
        function = getattr(module, job["entrypoint"])
        start = time.perf_counter_ns()
        if job["kind"] == "certificate":
            result = function(model, job["result"], job["now"])
        else:
            result = function(model, job["now"], **job.get("keyword_arguments", {}))
        elapsed = time.perf_counter_ns() - start
        # Round-trip now, so non-JSON results/NaN cannot corrupt the parent record.
        json.dumps(result, allow_nan=False)
        reply.update(status="returned", result=result, evaluation_ns=elapsed)
    except Exception as error:
        reply.update(error_type=type(error).__name__, error=str(error),
                     traceback=traceback.format_exc())
    finally:
        try:
            reply["input_sha256_after"] = digest(model)
            reply["input_unchanged"] = reply["input_sha256_after"] == before
        except Exception:
            reply["input_unchanged"] = False
        reply["worker_body_ns"] = time.perf_counter_ns() - tick
        _write(Path(job["reply_path"]), reply)


_WORKER_BOOT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from interoperability.benchmark import _worker; _worker(sys.argv[2])"
)


def _invoke(output: Path, label: str, job: dict, timeout_seconds: float) -> dict:
    folder = output / "jobs" / label
    folder.mkdir()
    reply_path = folder / "reply.json"
    _write(folder / "input.json", {**job, "reply_path": str(reply_path)})
    argv = [sys.executable, "-I", "-S", "-B", "-c", _WORKER_BOOT,
            str(output / "source"), str(folder / "input.json")]
    tick = time.perf_counter_ns()
    process = {"argv": argv, "timed_out": False, "returncode": None}
    with (folder / "stdout.bin").open("xb") as stdout, (folder / "stderr.bin").open("xb") as stderr:
        try:
            child = subprocess.run(argv, cwd=folder, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, timeout=timeout_seconds)
            process["returncode"] = child.returncode
        except subprocess.TimeoutExpired:
            process["timed_out"] = True
        except OSError as error:
            process.update(error_type=type(error).__name__, error=str(error))
    process["worker_wall_ns"] = time.perf_counter_ns() - tick
    _write(folder / "process.json", process)
    if process["timed_out"]:
        return {"status": "timed_out", "process": process}
    if process["returncode"] != 0 or not reply_path.exists():
        return {"status": "worker_failed", "process": process}
    try:
        reply = _json(reply_path)
        if type(reply) is not dict:
            raise ValueError("worker reply is not an object")
        return {**reply, "process": process}
    except (OSError, ValueError) as error:
        return {"status": "invalid_worker_reply", "error": str(error), "process": process}


def _valid_decision(reply: dict) -> bool:
    result = reply.get("result")
    return (reply.get("status") == "returned" and reply.get("input_unchanged") is True
            and type(result) is dict and result.get("decision") in DECISIONS
            and type(result.get("reason")) is str and "certificate" in result
            and ((result["decision"] == "unknown" and result.get("certificate") is None)
                 or (result["decision"] != "unknown" and type(result.get("certificate")) is dict)))


def _timing_summary(executions: list[dict]) -> dict:
    """Account for every invocation without inventing unavailable timings."""
    metrics = {}
    for key in ("evaluation_ns", "worker_body_ns", "worker_wall_ns"):
        samples = [((execution.get("process") or {}).get(key) if key == "worker_wall_ns"
                    else execution.get(key)) for execution in executions]
        observed = [value for value in samples if value is not None]
        if any(type(value) is not int or value < 0 for value in observed):
            raise ValueError("invalid retained timing: " + key)
        metrics[key] = {"samples": samples, "observed": len(observed),
                        "missing": len(samples) - len(observed),
                        "total": sum(observed) if observed else None}
    return {"invocations": len(executions), **metrics}


def summarize(rows: list[dict], algorithms: list[AlgorithmSpec]) -> dict:
    """Keep failures and inapplicable schemas in explicit denominators."""
    metrics = {}
    any_failure, any_gap = False, False
    references = [row["reference"] for row in rows]
    all_executions = list(references)
    for spec in algorithms:
        totals = {key: 0 for key in ("scheduled", "eligible", "not_applicable", "returned_valid",
            "errors", "reference_scored", "decision_agreements", "supported", "unsupported", "unknown",
            "conclusive", "certificates_valid", "certificates_invalid", "certificate_check_errors",
            "false_support", "false_refusal", "conclusive_on_reference_unknown", "abstained_on_reference_decided")}
        confusion = {reference: {decision: 0 for decision in DECISIONS} for reference in DECISIONS}
        evaluations, checks = [], []
        for row in rows:
            arm = row["algorithms"][spec.name]
            totals["scheduled"] += 1
            if arm["status"] == "not_applicable":
                totals["not_applicable"] += 1
                any_gap = True
                continue
            totals["eligible"] += 1
            evaluations.append(arm["execution"])
            if "certificate_check" in arm:
                checks.append(arm["certificate_check"])
            if not arm["valid_result"]:
                totals["errors"] += 1
                any_failure = True
                continue
            totals["returned_valid"] += 1
            decision = arm["execution"]["result"]["decision"]
            totals[decision] += 1
            if decision != "unknown":
                totals["conclusive"] += 1
                if arm["certificate_valid"] is True:
                    totals["certificates_valid"] += 1
                elif arm["certificate_valid"] is False:
                    totals["certificates_invalid"] += 1
                    any_failure = True
                else:
                    totals["certificate_check_errors"] += 1
                    any_failure = True
            if row["reference_valid"]:
                reference = row["reference"]["result"]["decision"]
                totals["reference_scored"] += 1
                totals["decision_agreements"] += int(reference == decision)
                confusion[reference][decision] += 1
                totals["false_support"] += int(reference == "unsupported" and decision == "supported")
                totals["false_refusal"] += int(reference == "supported" and decision == "unsupported")
                totals["conclusive_on_reference_unknown"] += int(reference == "unknown" and decision != "unknown")
                totals["abstained_on_reference_decided"] += int(reference != "unknown" and decision == "unknown")
                # Budgeted/conservative abstention is coverage loss, not an
                # unsound answer. A conclusive claim still needs its own proof.
                any_failure |= reference != decision and reference != "unknown" and decision != "unknown"
            else:
                any_gap = True
        def ratio(numerator, denominator):
            return numerator / denominator if denominator else None
        evaluation_timing = _timing_summary(evaluations)
        all_executions.extend(evaluations + checks)
        metrics[spec.name] = {**totals, "confusion_reference_by_decision": confusion,
            "decision_agreement_rate": ratio(totals["decision_agreements"], totals["reference_scored"]),
            "decision_coverage": ratio(totals["conclusive"], totals["eligible"]),
            "certified_coverage": ratio(totals["certificates_valid"], totals["eligible"]),
            "evaluation_ns": evaluation_timing["evaluation_ns"],
            "worker_wall_ns": evaluation_timing["worker_wall_ns"],
            "certificate_timing": _timing_summary(checks),
            "evaluation_and_certificate_timing": _timing_summary(evaluations + checks)}
    return {"schema_version": "admission-benchmark-summary/1",
        "status": "failed" if any_failure else "completed_with_gaps" if any_gap else "passed",
        "cases": len(rows), "family_labels": sorted({row["family"] for row in rows}),
        "reference_errors": sum(not row["reference_valid"] for row in rows),
        "candidate_count": len(algorithms) - 1,
        "candidate_evaluation_complete": len(algorithms) > 1 and not any_failure and not any_gap,
        "algorithms": metrics, "reference_timing": _timing_summary(references),
        "all_invocation_timing": _timing_summary(all_executions),
        "held_out_cases": 0, "qualified_domains": 0,
        "novelty_established": False,
        "claim_limit": "Authored development contracts in registered schemas only; no application task success, domain qualification, statistical independence, novelty or performance advantage established.",
        "timing_scope": "Every attempted evaluation and certificate check is counted, including failures and timeouts. Unavailable timings stay null; totals sum observed samples only and are null when none were measured. evaluation_ns includes function work and excludes import/startup; worker_wall_ns includes process startup, imports and capture. Reference timing is separate; all_invocation_timing includes references, solvers and checks, not parent-runner overhead. Fresh workers; no persistent warm cache or performance inference."}


def _run_benchmark(suite_path: Path, output: Path, algorithms: list[AlgorithmSpec] | None = None,
                  *, timeout_seconds: float = 10.0, package_dir: Path | None = None,
                  work_budget: int | None = None) -> dict:
    suite_path, output = Path(suite_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("refusing to overwrite existing benchmark evidence: " + str(output))
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be finite and in (0, 600]")
    suite, cases = _suite(suite_path)
    schema = cases[0][2]["schema_version"]
    adapter = ADAPTERS[schema]
    expected_baseline = AlgorithmSpec("baseline", adapter["baseline"], input_schema=schema)
    if work_budget is not None and (type(work_budget) is not int or work_budget <= 0 or not adapter["supports_budget"]):
        raise ValueError("work_budget requires a compatible schema and positive integer")
    keywords = {"budget": work_budget} if work_budget is not None else {}
    algorithms = list(algorithms or [expected_baseline])
    if not any(spec.name == "baseline" for spec in algorithms):
        algorithms.insert(0, expected_baseline)
    if len({spec.name for spec in algorithms}) != len(algorithms):
        raise ValueError("duplicate algorithm name")
    for spec in algorithms:
        spec.validate()
        if spec.name == "baseline" and spec != expected_baseline:
            raise ValueError("baseline label is reserved for the established baseline")
    package = Path(package_dir or Path(__file__).parent).resolve()
    sources = sorted(package.rglob("*.py"))
    if not sources or not (package / "benchmark.py").is_file():
        raise ValueError("source package lacks the benchmark worker")
    for spec in algorithms:
        relative = Path(*spec.module.split(".")[1:]).with_suffix(".py")
        if not (package / relative).is_file():
            raise ValueError("algorithm source is absent: " + spec.module)
    output.mkdir(parents=True, exist_ok=False)
    for name in ("inputs", "source", "jobs"):
        (output / name).mkdir()
    copied, originals = [], []
    for source in sources:
        if source.is_symlink():
            raise ValueError("source snapshot refuses symbolic links")
        target = output / "source/interoperability" / source.relative_to(package)
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw)
        copied.append(_record(target, output))
        originals.append((source, hashlib.sha256(raw).hexdigest()))
    suite_raw = suite_path.read_bytes()
    (output / "inputs/original-suite.json").write_bytes(suite_raw)
    if _json(output / "inputs/original-suite.json") != suite:
        raise ValueError("suite changed before capture")
    copied.append(_record(output / "inputs/original-suite.json", output))
    originals.append((suite_path, hashlib.sha256(suite_raw).hexdigest()))
    replay_cases = []
    for index, (entry, source, model) in enumerate(cases):
        name = f"inputs/case-{index:04d}.json"
        raw = source.read_bytes()
        # Detect an input changed between validation and snapshotting.
        target = output / name
        target.write_bytes(raw)
        if _load_input(target) != model:
            raise ValueError("runtime input changed before capture: " + str(source))
        replay_cases.append({"path": name, "family": entry["family"]})
        copied.append(_record(target, output))
        originals.append((source, hashlib.sha256(raw).hexdigest()))
    _write(output / "replay-suite.json", {**suite, "cases": replay_cases})
    execution = {"schema_version": "admission-benchmark-execution/1", "status": "started",
        "started_at_epoch_ns": time.time_ns(), "suite_id": suite["id"], "split": "development",
        "evaluation_clock": suite["evaluation_clock"], "timeout_seconds": timeout_seconds,
        "input_schema": schema, "work_budget": work_budget, "schema_adapter": adapter,
        "reference_implementation_is_baseline": adapter["baseline"] == adapter["reference"],
        "algorithms": [asdict(spec) for spec in algorithms],
        "runtime": {"python": sys.version, "implementation": platform.python_implementation(),
                    "platform": platform.platform(), "executable": sys.executable},
        "captured_inputs": copied, "live_application_runs": 0, "live_model_calls": 0}
    _write(output / "execution.json", execution)
    rows = []
    with (output / "results.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for index, (entry, source, model) in enumerate(cases):
            base = {"runtime_manifest": model, "now": suite["evaluation_clock"]}
            reference = _invoke(output, f"case-{index:04d}-reference", {**base, "kind": "evaluate",
                "module": adapter["reference"], "entrypoint": "evaluate", "keyword_arguments": keywords}, timeout_seconds)
            row = {"record_type": "case_result", "case_id": model["id"], "family": entry["family"],
                "input_schema": model["schema_version"], "model_sha256": digest(model),
                "input_snapshot": replay_cases[index]["path"], "source_path": str(source),
                "evaluation_clock": suite["evaluation_clock"], "provenance": _provenance(model),
                "reference": reference, "reference_valid": _valid_decision(reference), "algorithms": {}}
            for spec in algorithms:
                if spec.input_schema != model["schema_version"]:
                    row["algorithms"][spec.name] = {"status": "not_applicable",
                        "reason": "input_schema_mismatch", "declared_input_schema": spec.input_schema}
                    continue
                reply = _invoke(output, f"case-{index:04d}-{spec.name}", {**base, "kind": "evaluate",
                    "module": spec.module, "entrypoint": spec.entrypoint, "keyword_arguments": keywords}, timeout_seconds)
                valid = _valid_decision(reply)
                arm = {"status": "recorded", "execution": reply, "valid_result": valid,
                       "certificate_valid": None, "decision_agreement": None}
                if valid:
                    if reply["result"]["decision"] != "unknown":
                        check = _invoke(output, f"case-{index:04d}-{spec.name}-certificate", {
                            **base, "kind": "certificate", "module": adapter["checker"],
                            "entrypoint": "check_certificate", "result": reply["result"]}, timeout_seconds)
                        arm["certificate_check"] = check
                        if check.get("status") == "returned" and check.get("input_unchanged") is True and type(check.get("result")) is bool:
                            arm["certificate_valid"] = check["result"]
                    if row["reference_valid"]:
                        arm["decision_agreement"] = reply["result"]["decision"] == reference["result"]["decision"]
                row["algorithms"][spec.name] = arm
            rows.append(row)
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
    summary = summarize(rows, algorithms)
    captured_names = {r["path"] for r in copied}
    snapshot_names = {p.relative_to(output).as_posix() for name in ("source", "inputs")
                      for p in (output / name).rglob("*") if p.is_file()}
    summary["snapshot_inputs_unchanged"] = (snapshot_names == captured_names and
        all(_record(output / r["path"], output) == r for r in copied))
    summary["original_inputs_unchanged"] = all(source.exists() and hashlib.sha256(source.read_bytes()).hexdigest() == value for source, value in originals)
    if not summary["snapshot_inputs_unchanged"] or not summary["original_inputs_unchanged"]:
        summary["status"] = "failed"
        summary["candidate_evaluation_complete"] = False
    summary["finished_at_epoch_ns"] = time.time_ns()
    _write(output / "summary.json", summary)
    inventory = [_record(path, output) for path in sorted(output.rglob("*")) if path.is_file()]
    _write(output / "manifest.json", {"schema_version": "admission-benchmark-bundle/1", "files": inventory,
        "bytes": sum(row["bytes"] for row in inventory), "scope": "Exact local software/input/attempt evidence, not authenticated provenance or an application runtime"})
    return summary


def run_benchmark(suite_path: Path, output: Path, algorithms: list[AlgorithmSpec] | None = None,
                  *, timeout_seconds: float = 10.0, package_dir: Path | None = None,
                  work_budget: int | None = None) -> dict:
    """Run once into a fresh directory; retain framework failures as well as arm failures."""
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("refusing to overwrite existing benchmark evidence: " + str(output))
    try:
        return _run_benchmark(suite_path, output, algorithms, timeout_seconds=timeout_seconds,
                              package_dir=package_dir, work_budget=work_budget)
    except Exception as error:
        if output.is_dir():
            _write(output / "runner-failure.json", {"schema_version": "admission-benchmark-runner-failure/1",
                "status": "failed", "error_type": type(error).__name__, "error": str(error),
                "recorded_at_epoch_ns": time.time_ns(), "partial_attempts_retained": True})
        raise


def _bundle_path(directory: Path, name: str, inventory: set[str] | None = None) -> Path:
    if type(name) is not str or not name:
        raise ValueError("invalid bundle path")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or ".." in relative.parts or name != relative.as_posix()
            or "\\" in name or ":" in name or "\0" in name
            or (inventory is not None and name not in inventory)):
        raise ValueError("path is not a canonical inventoried bundle input")
    path = directory / name
    if not path.resolve().is_relative_to(directory) or path.is_symlink():
        raise ValueError("bundle path escapes its root")
    return path


def verify_bundle(directory: Path) -> dict:
    directory = Path(directory).resolve()
    manifest = _json(directory / "manifest.json")
    if manifest.get("schema_version") != "admission-benchmark-bundle/1":
        raise ValueError("unknown bundle schema")
    names, folded = set(), set()
    for row in manifest["files"]:
        name = row["path"]
        path = _bundle_path(directory, name)
        if name in names or name.casefold() in folded:
            raise ValueError("invalid or duplicate bundle path")
        if _record(path, directory) != row:
            raise ValueError("changed bundle file: " + name)
        names.add(name)
        folded.add(name.casefold())
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    if actual != names | {"manifest.json"} or manifest["bytes"] != sum(row["bytes"] for row in manifest["files"]):
        raise ValueError("bundle inventory mismatch")
    execution = _json(directory / "execution.json")
    replay_suite = _json(_bundle_path(directory, "replay-suite.json", names))
    original_suite = _json(_bundle_path(directory, "inputs/original-suite.json", names))
    if (set(replay_suite) != {"schema_version", "id", "split", "evaluation_clock", "cases"}
            or replay_suite["schema_version"] != "admission-benchmark-suite/1"
            or replay_suite["split"] != "development"
            or {k: v for k, v in replay_suite.items() if k != "cases"}
               != {k: v for k, v in original_suite.items() if k != "cases"}
            or replay_suite["id"] != execution["suite_id"]
            or replay_suite["evaluation_clock"] != execution["evaluation_clock"]
            or len(replay_suite["cases"]) != len(original_suite["cases"])):
        raise ValueError("replay suite differs from captured execution inputs")
    captured = {}
    for record in execution["captured_inputs"]:
        name = record["path"]
        if name in captured or _record(_bundle_path(directory, name, names), directory) != record:
            raise ValueError("execution input inventory differs from captured bytes")
        captured[name] = record
    expected = []
    for index, (entry, original) in enumerate(zip(replay_suite["cases"], original_suite["cases"])):
        if (set(entry) != {"path", "family"} or entry["family"] != original["family"]
                or entry["path"] != f"inputs/case-{index:04d}.json"
                or entry["path"] not in captured):
            raise ValueError("replay case order/family differs from captured suite")
        model = _json(_bundle_path(directory, entry["path"], names))
        expected.append((entry, model))
    specs = [AlgorithmSpec(**spec) for spec in execution["algorithms"]]
    for spec in specs:
        spec.validate()
    algorithm_names = {spec.name for spec in specs}
    if len(algorithm_names) != len(specs):
        raise ValueError("duplicate captured algorithm identity")
    rows = [json.loads(line) for line in (directory / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(rows) != len(expected) or len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("retained case membership differs from captured suite")
    for row, (entry, model) in zip(rows, expected):
        _bundle_path(directory, row["input_snapshot"], names)
        if (row["input_snapshot"] != entry["path"] or row["family"] != entry["family"]
                or digest(model) != row["model_sha256"] or model["id"] != row["case_id"]
                or row["input_schema"] != model["schema_version"]
                or row["provenance"] != _provenance(model)
                or row["evaluation_clock"] != execution["evaluation_clock"]
                or set(row["algorithms"]) != algorithm_names):
            raise ValueError("retained case does not bind its copied runtime input/clock")
        for spec in specs:
            if (row["algorithms"][spec.name]["status"] == "not_applicable") != (spec.input_schema != model["schema_version"]):
                raise ValueError("algorithm applicability differs from captured schema")
        for arm in [row["reference"], *[x["execution"] for x in row["algorithms"].values() if x["status"] != "not_applicable"]]:
            if "input_sha256_before" in arm and arm["input_sha256_before"] != row["model_sha256"]:
                raise ValueError("worker received a different runtime input")
    calculated = summarize(rows, specs)
    summary = _json(directory / "summary.json")
    for key, value in calculated.items():
        if key == "status" and (not summary["snapshot_inputs_unchanged"] or not summary["original_inputs_unchanged"]):
            value = "failed"
        if key == "candidate_evaluation_complete" and (not summary["snapshot_inputs_unchanged"] or not summary["original_inputs_unchanged"]):
            value = False
        if summary.get(key) != value:
            raise ValueError("summary disagrees with retained attempts: " + key)
    return {"status": "passed", "files_verified": len(names), "case_records": len(rows),
            "summary_recomputed": True, "fresh_algorithm_execution": False}


def replay_benchmark(directory: Path, output: Path) -> dict:
    directory = Path(directory).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("refusing to overwrite existing benchmark evidence: " + str(output))
    verify_bundle(directory)
    execution = _json(directory / "execution.json")
    # Load the captured parent runner/validators too, so a later checkout's
    # validation changes cannot silently govern an older captured replay.
    boot = (
        "import sys,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from interoperability.benchmark import run_benchmark,AlgorithmSpec; "
        "d=Path(sys.argv[2]); e=json.loads((d/'execution.json').read_bytes()); "
        "r=run_benchmark(d/'replay-suite.json',Path(sys.argv[3]),"
        "[AlgorithmSpec(**x) for x in e['algorithms']],timeout_seconds=e['timeout_seconds'],"
        "package_dir=d/'source/interoperability',work_budget=e['work_budget']); "
        "print(json.dumps({'status':r['status']}))"
    )
    case_count = len(_json(directory / "replay-suite.json")["cases"])
    limit = 120 + case_count * (1 + 2 * len(execution["algorithms"])) * execution["timeout_seconds"]
    child = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", boot,
        str(directory / "source"), str(directory), str(output)], cwd=directory,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=limit)
    if child.returncode != 0:
        raise ValueError("captured replay runner failed: " + child.stderr.decode("utf-8", errors="replace")[-4000:])
    verify_bundle(output)
    return _json(output / "summary.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--suite", type=Path)
    source.add_argument("--verify", type=Path)
    source.add_argument("--replay", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--algorithm", action="append", default=[], metavar="NAME=MODULE:FUNCTION")
    parser.add_argument("--algorithm-schema", action="append", default=[], metavar="NAME=SCHEMA")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--work-budget", type=int)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.output or args.algorithm or args.algorithm_schema:
                raise ValueError("verify does not accept output or algorithm arguments")
            report = verify_bundle(args.verify)
        else:
            if args.output is None:
                raise ValueError("run/replay needs a new --output directory")
            if args.replay:
                if args.algorithm or args.algorithm_schema:
                    raise ValueError("replay uses the retained algorithm inventory")
                report = replay_benchmark(args.replay, args.output)
            else:
                algorithms = []
                schemas = dict(value.split("=", 1) for value in args.algorithm_schema)
                for value in args.algorithm:
                    name, target = value.split("=", 1)
                    module, function = target.rsplit(":", 1)
                    algorithms.append(AlgorithmSpec(name, module, function, schemas.pop(name, MODULE_SCHEMAS.get(module, SCHEMA))))
                if schemas:
                    raise ValueError("schema override names an unconfigured algorithm")
                report = run_benchmark(args.suite, args.output, algorithms or None,
                                       timeout_seconds=args.timeout_seconds, work_budget=args.work_budget)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["status"] == "passed" else 1
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, "error: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
