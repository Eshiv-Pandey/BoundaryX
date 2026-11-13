"""Run one supplied recipe profile with an explicit budget and checked receipt.

The shared-lifting candidate is opt-in here; existing admission commands and
defaults are unchanged. This command makes no application or network request.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

from . import direct_goal_pruned_v2 as direct
from . import refinement_shared_lift_v2 as shared


METHODS = {"shared_lift": shared, "direct_pruned": direct}


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError(f"non-JSON numeric constant: {value}")


def _encoded(value):
    # Comparing serialized JSON preserves distinctions such as true versus 1.
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def run_admission(input_path: Path, output: Path, *, method: str = "shared_lift",
                  work_budget: int, now: int) -> dict:
    """Retain one attempt; a rejected certificate never becomes a recorded pass."""
    input_path, output = Path(input_path), Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError(f"refusing to overwrite existing evidence: {output}")
    if method not in METHODS:
        raise ValueError("unknown admission method")
    if type(work_budget) is not int or work_budget <= 0:
        raise ValueError("work_budget must be a positive explicit integer")
    if type(now) is not int:
        raise ValueError("evaluation clock must be an integer")
    raw = input_path.read_bytes()
    model = json.loads(raw, object_pairs_hook=_unique, parse_constant=_reject_constant)
    if type(model) is not dict or model.get("schema_version") != direct.INPUT_SCHEMA:
        raise ValueError(f"require a {direct.INPUT_SCHEMA} profile object")
    encoded_model = _encoded(model)
    solver = METHODS[method]
    source = Path(__file__).parent
    receipt = {
        "schema_version": "shared-admission-command/1", "status": "failed",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": method, "solver_module": solver.__name__,
        "checker_module": direct.__name__, "checker_entrypoint": "check_certificate",
        "input_path": str(input_path), "input_sha256": hashlib.sha256(raw).hexdigest(),
        "model_sha256": hashlib.sha256(encoded_model).hexdigest(), "runtime_manifest": model,
        "evaluation_clock": now, "work_budget": work_budget,
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(source.glob("*.py"))},
        "python": sys.version, "platform": platform.platform(),
        "evaluation_ns": None, "certificate_check_ns": None,
        "certificate_valid": None, "checker_invoked": False,
        "application_requests": 0, "live_model_calls": 0,
        "claim_limit": "Decision under supplied finite recipe assumptions; no application execution, established novelty or performance advantage.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Invalid command/input syntax is rejected above. Once evaluation starts,
    # reserve this attempt even when the solver or checker fails.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        try:
            solver_input = copy.deepcopy(model)
            tick = time.perf_counter_ns()
            try:
                result = solver.evaluate(solver_input, now, budget=work_budget)
            finally:
                receipt["evaluation_ns"] = time.perf_counter_ns() - tick
            if _encoded(solver_input) != encoded_model:
                raise ValueError("admission method mutated its runtime input")
            _encoded(result)
            receipt["result"] = result
            if (type(result) is not dict or type(result.get("decision")) is not str
                    or result["decision"] not in ("supported", "unsupported", "unknown")
                    or type(result.get("reason")) is not str or "certificate" not in result):
                raise ValueError("malformed admission result")
            if result["decision"] == "unknown":
                receipt["unknown_has_no_certificate"] = result.get("certificate") is None
                receipt["status"] = ("recorded" if receipt["unknown_has_no_certificate"]
                                     else "failed_certificate")
            elif type(result.get("certificate")) is not dict:
                receipt["certificate_valid"] = False
                receipt["status"] = "failed_certificate"
            else:
                checker_input, checker_result = copy.deepcopy(model), copy.deepcopy(result)
                encoded_result = _encoded(result)
                receipt["checker_invoked"] = True
                tick = time.perf_counter_ns()
                try:
                    accepted = direct.check_certificate(checker_input, checker_result, now)
                finally:
                    receipt["certificate_check_ns"] = time.perf_counter_ns() - tick
                if (_encoded(checker_input) != encoded_model
                        or _encoded(checker_result) != encoded_result):
                    raise ValueError("certificate checker mutated its supplied input")
                receipt["certificate_valid"] = accepted is True
                receipt["status"] = "recorded" if accepted is True else "failed_certificate"
        except Exception as error:
            receipt["status"] = "failed"
            receipt["error"] = f"{type(error).__name__}: {error}"
        finally:
            receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New result JSON path")
    parser.add_argument("--method", choices=tuple(METHODS), default="shared_lift")
    parser.add_argument("--work-budget", type=int, required=True)
    parser.add_argument("--now", type=int, required=True, help="Explicit evaluation clock")
    args = parser.parse_args(argv)
    try:
        receipt = run_admission(args.input, args.output, method=args.method,
                                work_budget=args.work_budget, now=args.now)
    except (ValueError, OSError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    result = receipt.get("result")
    result = result if type(result) is dict else {}
    print(json.dumps({"status": receipt["status"], "method": args.method,
                      "case": receipt["runtime_manifest"].get("id"),
                      "decision": result.get("decision"), "reason": result.get("reason"),
                      "work_budget": args.work_budget,
                      "certificate_valid": receipt["certificate_valid"],
                      "error": receipt.get("error"), "output": str(args.output)}, indent=2))
    return 0 if receipt["status"] == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
