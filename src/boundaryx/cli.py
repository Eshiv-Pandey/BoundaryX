"""BoundaryX commands use fresh allocations and refuse unreviewed held-out gold."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from boundaryx.adapters.routes import ROUTES
from boundaryx.core.evidence import EvidenceError, verify_manifest
from boundaryx.execution.process import execute
from boundaryx.tasks.contracts import heldout_status
from boundaryx.verification.independent import report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("routes")
    sub.add_parser("heldout-status")
    verify = sub.add_parser("verify-independent")
    for kind in ("diagnostics", "protocol", "artifacts"):
        verify.add_argument("--" + kind, type=Path)
    verify.add_argument("--output", type=Path, required=True)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("bundle", type=Path)
    for name in ("check-history", "reproduce"):
        command_parser = sub.add_parser(name)
        command_parser.add_argument("--output", type=Path, required=True)
        if name == "reproduce":
            command_parser.add_argument("--protocols", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        if args.command == "routes":
            print(json.dumps([asdict(r) for r in ROUTES], indent=2))
        elif args.command == "heldout-status":
            print(json.dumps(heldout_status(root / "benchmarks/heldout/v2"), indent=2))
        elif args.command == "manifest":
            print(json.dumps({"status": "Completed", "verified_files": verify_manifest(args.bundle)}))
        elif args.command == "verify-independent":
            result = report(args.output, diagnostics=args.diagnostics, protocol=args.protocol, artifacts=args.artifacts)
            print(json.dumps({"status": result["status"], "reports": [{k: v for k, v in r.items() if k != "rows"} for r in result["reports"]]}))
        else:
            output = args.output.resolve()
            if not output.is_relative_to(root / "results/development"):
                raise EvidenceError("Development execution must use a fresh results/development allocation")
            relative = output.relative_to(root)
            command = [sys.executable, "-B", "scripts/run_loss_handoff_v2.py", "--output", str(relative / "pipeline")]
            if args.command == "reproduce":
                command.append("--reproduce")
                if args.protocols:
                    command.append("--live")
            receipt = execute(root, command, output / "execution")
            if receipt["exit_code"] != 0:
                return 1
            old = root / "runs/supervisor-handoff-20261113"
            report(output / "independent-historical.json", diagnostics=old / "diagnostics-final-001",
                   protocol=old / "protocol-main-001", artifacts=old / "parts-main-001")
            if args.command == "reproduce":
                pipeline = output / "pipeline"
                report(output / "independent-fresh.json", diagnostics=pipeline / "fresh-diagnostics",
                       protocol=pipeline / "fresh-protocol" if args.protocols else None,
                       artifacts=pipeline / "fresh-artifacts" if args.protocols else None)
        return 0
    except (EvidenceError, FileExistsError) as exc:
        print(json.dumps({"status": "Not Established", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
