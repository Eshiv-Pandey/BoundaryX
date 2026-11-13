"""Run a local admission method with an independently checked result receipt."""
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


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"non-JSON numeric constant: {value}")


def _method(name):
    if name in ("baseline", "oracle"):
        from . import baseline, manifest, oracle

        return (baseline if name == "baseline" else oracle), oracle, manifest.SCHEMA
    from . import refinement, refinement_oracle

    return (refinement if name == "refinement" else refinement_oracle), refinement_oracle, refinement.SCHEMA


def run_admission(input_path: Path, output: Path, method: str, now: int | None = None) -> dict:
    if method not in ("baseline", "oracle", "refinement", "direct"):
        raise ValueError("unknown admission method")
    if output.exists():
        raise ValueError(f"refusing to overwrite existing evidence: {output}")
    raw = input_path.read_bytes()
    model = json.loads(raw, object_pairs_hook=_unique, parse_constant=_reject_constant)
    if not isinstance(model, dict):
        raise ValueError("runtime manifest must be an object")
    solver, checker, schema = _method(method)
    if model.get("schema_version") != schema:
        raise ValueError(f"{method} requires {schema}")
    clock = int(time.time()) if now is None else now
    if type(clock) is not int:
        raise ValueError("evaluation clock must be an integer")
    source = Path(__file__).parent
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(source.glob("*.py"))}
    receipt = {
        "schema_version": "admission-command/1", "status": "failed",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": method, "input_path": str(input_path),
        "input_sha256": hashlib.sha256(raw).hexdigest(), "runtime_manifest": model,
        "evaluation_clock": clock, "python": sys.version, "platform": platform.platform(),
        "source_sha256": sources, "application_requests": 0, "live_model_calls": 0,
        "claim_limit": "Decision under supplied model assumptions; no application execution or established algorithmic novelty.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the receipt before evaluation; never replace an earlier attempt.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        try:
            before = json.dumps(model, sort_keys=True, ensure_ascii=False, allow_nan=False)
            solver_input = copy.deepcopy(model)
            tick = time.perf_counter_ns()
            result = solver.evaluate(solver_input, clock)
            receipt["evaluation_ns"] = time.perf_counter_ns() - tick
            if json.dumps(solver_input, sort_keys=True, ensure_ascii=False, allow_nan=False) != before:
                raise ValueError("admission method mutated its runtime input")
            if not isinstance(result, dict) or result.get("decision") not in ("supported", "unsupported", "unknown"):
                raise ValueError("malformed admission result")
            json.dumps(result, ensure_ascii=False, allow_nan=False)
            receipt["result"] = result
            tick = time.perf_counter_ns()
            if result["decision"] == "unknown":
                valid = result.get("certificate") is None
                receipt["unknown_has_no_certificate"] = valid
                receipt["certificate_valid"] = None
            else:
                valid = checker.check_certificate(copy.deepcopy(model), copy.deepcopy(result), clock)
                receipt["certificate_valid"] = valid is True
            receipt["certificate_check_ns"] = time.perf_counter_ns() - tick
            receipt["status"] = "recorded" if valid is True else "failed_certificate"
        except Exception as error:
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
    parser.add_argument("--method", choices=("refinement", "direct", "baseline", "oracle"), required=True)
    parser.add_argument("--now", type=int, help="Explicit logical clock for reproducible development cases")
    args = parser.parse_args(argv)
    try:
        receipt = run_admission(args.input, args.output, args.method, args.now)
    except (ValueError, OSError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    result = receipt.get("result", {})
    print(json.dumps({"status": receipt["status"], "method": args.method,
                      "case": receipt["runtime_manifest"].get("id"),
                      "decision": result.get("decision"), "reason": result.get("reason"),
                      "certificate_valid": receipt.get("certificate_valid"),
                      "error": receipt.get("error"), "output": str(args.output)}, indent=2))
    return 0 if receipt["status"] == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
