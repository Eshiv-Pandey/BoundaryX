"""Build local explorer data only from checked final result allocations."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts.verify_loss_release_v2 import read_json, require, sha


def build(destination=ROOT / "demo/benchmark-v2"):
    evidence = ROOT / "runs/supervisor-handoff-20261113"
    require(read_json(evidence / "final-verification-001/verification.json")["status"] == "passed", "Task evidence not verified")
    require(read_json(evidence / "parts-verification-001/verification.json")["status"] == "passed", "Part evidence not verified")
    protocol_cells = []
    for path in sorted((evidence / "protocol-main-001/cells").glob("*.json")):
        cell = read_json(path)
        protocol_cells.append({k: v for k, v in cell.items() if k not in ("episode_wire", "probe_wire")})
        protocol_cells[-1]["raw_path"] = path.relative_to(ROOT).as_posix()
    part_cells = []
    for path in sorted((evidence / "parts-main-001/cells").glob("*--r0--*.json")):
        cell = read_json(path)
        cell.pop("wire")
        cell.pop("initial_wire")
        cell.get("recovery", {}).pop("wire", None)
        cell["raw_path"] = path.relative_to(ROOT).as_posix()
        part_cells.append(cell)
    bank = read_json(evidence / "diagnostics-final-001/input-bank.json")
    selected = [c for c in bank["cases"] if c["generation"]["variant"] == 0]
    diagnostic_cells = []
    for case in selected:
        for profile in read_json(evidence / "diagnostics-final-001/allocation.json")["profiles"]:
            episode_id = case["case_id"] + "--" + profile
            path = evidence / "diagnostics-final-001/cells" / episode_id / "diagnosis.json"
            diagnostic_cells.append({"case_id": case["case_id"], "profile": profile,
                                     "diagnosis": read_json(path), "raw_path": path.relative_to(ROOT).as_posix()})
    data = {"schema_version": "benchmark_review_data_v2",
            "notice": "Saved verified development evidence. No service or model call from the explorer.",
            "caseNames": [{"case_id": c["case_id"], "family": c["family_id"].replace("_", " ")} for c in selected],
            "protocolCells": protocol_cells, "partsCells": part_cells, "diagnosticCells": diagnostic_cells,
            "partsResult": read_json(evidence / "parts-main-001/results.json"),
            "protocolResult": read_json(evidence / "protocol-main-001/results.json"),
            "diagnosticsResult": read_json(evidence / "diagnostics-final-001/results.json"),
            "sources": [{"path": str(path.relative_to(ROOT).as_posix()), "sha256": sha(path)} for path in
                        (evidence / "final-verification-001/verification.json", evidence / "parts-verification-001/verification.json",
                         evidence / "diagnostics-final-001/results.json", evidence / "protocol-main-001/results.json", evidence / "parts-main-001/results.json")]}
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "data.json").write_text(encoded + "\n", encoding="utf-8")
    (destination / "data.js").write_text("window.BENCHMARK_REVIEW = " + encoded.replace("</", "<\\/") + ";\n", encoding="utf-8")
    print(json.dumps({"status": "built", "protocol_cells": len(protocol_cells), "parts_examples": len(part_cells),
                      "diagnostic_examples": len(diagnostic_cells), "data_bytes": len(encoded.encode("utf-8"))}))


if __name__ == "__main__":
    build()
