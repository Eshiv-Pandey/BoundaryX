"""Trace-producing development CLI; never invents benchmark outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from . import __version__, baseline
from .manifest import digest, load


def _source_hashes() -> dict[str, str]:
    directory = Path(__file__).parent
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.glob("*.py"))
    }


def run_development(inputs: list[Path], output: Path, now: int | None = None) -> dict:
    # Import only at execution so the independently authored module remains separate.
    from . import oracle

    if output.exists():
        raise ValueError(f"refusing to overwrite existing evidence: {output}")
    if not inputs:
        raise ValueError("no input manifests")
    manifests = [(path, load(path)) for path in inputs]
    if any(m["provenance"]["kind"] != "authored-development" for _, m in manifests):
        raise ValueError("development command requires explicitly authored-development inputs")
    if len({m["id"] for _, m in manifests}) != len(manifests):
        raise ValueError("duplicate case IDs")
    started_at = int(time.time())
    evaluated_at = started_at if now is None else now
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = _source_hashes()
    summary = {"cases": len(manifests), "agreements": 0, "supported": 0,
               "unsupported": 0, "unknown": 0, "invalid_certificates": 0}
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({
            "record_type": "run_metadata", "experiment_kind": "authored-development",
            "package_version": __version__, "started_at": started_at,
            "evaluation_clock": evaluated_at, "python": sys.version,
            "platform": platform.platform(), "source_sha256": hashes,
            "claim_limit": "Finite abstraction self-consistency only; no real bridge or LLM result.",
        }, sort_keys=True) + "\n")
        for path, manifest in manifests:
            tick = time.perf_counter_ns()
            result = baseline.evaluate(manifest, evaluated_at)
            baseline_ns = time.perf_counter_ns() - tick
            tick = time.perf_counter_ns()
            reference = oracle.evaluate(manifest, evaluated_at)
            oracle_ns = time.perf_counter_ns() - tick
            conclusive = result["decision"] != "unknown"
            valid = oracle.check_certificate(manifest, result, evaluated_at) if conclusive else None
            agreement = result["decision"] == reference["decision"]
            summary["agreements"] += int(agreement)
            summary[result["decision"]] += 1
            summary["invalid_certificates"] += int(valid is False)
            handle.write(json.dumps({
                "record_type": "case_result", "case_id": manifest["id"],
                "input_path": str(path), "model_sha256": digest(manifest),
                "runtime_manifest": manifest,
                "provenance": manifest["provenance"], "baseline": result,
                "oracle": reference, "decision_agreement": agreement,
                "certificate_valid": valid, "baseline_ns": baseline_ns, "oracle_ns": oracle_ns,
            }, sort_keys=True) + "\n")
            handle.flush()
        handle.write(json.dumps({"record_type": "run_summary", **summary,
                                 "finished_at": int(time.time())}, sort_keys=True) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "benchmark":
        from .benchmark import main as benchmark_main

        return benchmark_main(argv[1:])
    if argv and argv[0] == "admit":
        from .admission_cli import main as admission_main

        return admission_main(argv[1:])
    parser = argparse.ArgumentParser(description="Bounded interoperability research development tools")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("admit", help="Run an admission method and independently check its certificate")
    commands.add_parser("benchmark", help="Compare admission methods on the same development suite")
    demo = commands.add_parser("development", help="Run authored finite fixtures, not bridge experiments")
    demo.add_argument("--inputs", type=Path, default=Path("examples/development"))
    demo.add_argument("--output", type=Path, required=True, help="New JSONL evidence path")
    args = parser.parse_args(argv)
    try:
        summary = run_development(sorted(args.inputs.glob("*.json")), args.output)
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(summary, sort_keys=True))
    return int(summary["agreements"] != summary["cases"] or summary["invalid_certificates"] != 0)

