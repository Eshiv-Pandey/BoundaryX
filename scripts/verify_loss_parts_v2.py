"""Independently reconstruct upstream part survival and same-task raw recovery."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts.verify_loss_release_v2 import (read_json, require, equal, sha, verify_manifest, verify_sources, unwrap_mcp)
from scripts.run_loss_benchmark_v1 import write_new

EXPECTED = {
    "text": {"text": "lavivrus-kramhcneb", "mediaType": "text/plain"},
    "data": {"data": {"answer": 42, "echo": "benchmark-survival"}, "mediaType": "application/json"},
    "file": {"url": "https://example.invalid/files/report.pdf", "filename": "report.pdf", "mediaType": "application/pdf"},
    "image": {"raw": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "filename": "pixel.png", "mediaType": "image/png"},
}
PAYLOAD = {"text": "text", "data": "data", "file": "url", "image": "raw"}


def packet(blob):
    text = blob["raw"]
    if text.startswith("data:") or "\ndata:" in text:
        text = next(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    return json.loads(text)


def decode_public(route, final):
    if route in ("native", "mgcrea_raw"):
        return final["artifacts"][0]["parts"][0]
    if route == "mgcrea_typed":
        return final["artifacts"][0]
    blocks = [b for b in final["content"] if b.get("_meta", {}).get("io.github.amirk-s/a2a", {}).get("artifactId")]
    require(len(blocks) == 1, "expected exactly one artifact block")
    block = blocks[0]
    metadata = block["_meta"]["io.github.amirk-s/a2a"]
    if block["type"] == "text":
        return {"data": json.loads(block["text"]), "mediaType": metadata.get("mediaType")} if metadata.get("partKind") == "data" else {"text": block["text"], "mediaType": metadata.get("mediaType")}
    if block["type"] == "resource_link":
        return {"url": block["uri"], "filename": block["name"], "mediaType": block["mimeType"]}
    if block["type"] == "image":
        return {"raw": block["data"], "filename": metadata.get("filename"), "mediaType": block["mimeType"]}
    raise ValueError("unrecognized public artifact representation")


def final_occurred_in_wire(route, final, wire):
    for event in wire:
        if event["role"] not in ("native_client", "mcp_http", "mcp_stdio_response") or event.get("response") is None:
            continue
        result = packet(event["response"]).get("result")
        if result is None:
            continue
        if route == "mgcrea_typed":
            result = unwrap_mcp(result)
        elif route == "mgcrea_raw":
            result = unwrap_mcp(result).get("result")
        if equal(result.get("task", result), final):
            return True
    return False


def verify_cell(cell):
    import hashlib
    for event in cell["wire"]:
        for direction in ("request", "response"):
            blob = event.get(direction)
            if blob is not None:
                raw = blob["raw"].encode("utf-8")
                require(len(raw) == blob["bytes"] and hashlib.sha256(raw).hexdigest() == blob["sha256"], "wire identity mismatch")
        if event["role"] == "recorder_proxy" and event["path"] == "/a2a":
            require(event["rpc_response_bytes_unchanged"] is True and event["upstream_response_sha256"] == event["response"]["sha256"], "recorder changed upstream RPC response")
    require(cell["execution_status"] == "recorded", "part attempt execution error")
    expected = EXPECTED[cell["case_id"]]
    require(equal(cell["spec"]["expected"], expected), "part gold mismatch")
    require(cell["spec"]["payload_key"] == PAYLOAD[cell["case_id"]], "payload definition mismatch")
    native = [e for e in cell["initial_wire"] if e["role"] == "recorder_proxy" and e["path"] == "/a2a"]
    sends = [e for e in native if packet(e["request"])["method"] == "SendMessage"]
    gets = [e for e in native if packet(e["request"])["method"] == "GetTask"]
    require(len(sends) == 1 and gets, "part native send/get census mismatch")
    request = packet(sends[0]["request"])
    require(request["params"]["message"]["parts"][0]["text"] == cell["spec"]["command"], "part native input command mismatch")
    initial_task = packet(sends[0]["response"])["result"]["task"]
    task = packet(gets[-1]["response"])["result"]
    require(initial_task["id"] == task["id"] == packet(gets[-1]["request"])["params"]["id"], "part native task mismatch")
    require(initial_task["contextId"] == task["contextId"], "part native context mismatch")
    require(task["status"]["state"] == "TASK_STATE_COMPLETED", "part source task did not complete")
    upstream_artifact = task["artifacts"][0]["parts"][0]
    require(all(equal(upstream_artifact.get(k), v) for k, v in expected.items()), "upstream native artifact failed frozen gold")
    require(final_occurred_in_wire(cell["route"], cell["final"], cell["initial_wire"]), "part public final result absent from client wire")
    observed = decode_public(cell["route"], cell["final"])
    require(equal(observed, cell["observed_artifact_projection"]), "public artifact projection mismatch")
    checks = {key: equal(observed.get(key), value) for key, value in expected.items()}
    require(cell["field_checks"] == checks and cell["required_representation_survived"] is all(checks.values()), "representation grading mismatch")
    require(cell["required_payload_survived"] is checks[PAYLOAD[cell["case_id"]]], "payload grading mismatch")
    if cell["route"] == "amirk_typed":
        require(cell["final"]["structuredContent"]["taskHandle"] == cell["receipt"]["id"], "Amir task-handle mismatch")
        require(cell["final"]["structuredContent"]["contextHandle"] == cell["receipt"]["contextId"], "Amir context-handle mismatch")
    elif cell["route"] == "mgcrea_typed":
        require(cell["final"]["id"] == cell["receipt"]["id"] == task["id"] and cell["final"]["context_id"] == cell["receipt"]["contextId"] == task["contextId"], "typed public task/context mismatch")
    else:
        require(cell["final"]["id"] == cell["receipt"]["id"] == task["id"] and cell["final"]["contextId"] == cell["receipt"]["contextId"] == task["contextId"], "raw/native public task/context mismatch")
    eligible = cell["route"] == "mgcrea_typed" and not all(checks.values())
    require(cell["recovery"]["eligible"] is eligible, "recovery eligibility mismatch")
    if eligible:
        recovery = cell["recovery"]
        require(recovery["wire"] == cell["wire"][len(cell["initial_wire"]):], "recovery wire partition mismatch")
        reads = [e for e in recovery["wire"] if e["role"] == "recorder_proxy" and e["path"] == "/a2a"]
        require(len(reads) == 1 and packet(reads[0]["request"])["method"] == "GetTask", "recovery is not exactly one public task read")
        recovered_task = packet(reads[0]["response"])["result"]
        require(packet(reads[0]["request"])["params"]["id"] == task["id"] == recovered_task["id"], "recovery changed native task")
        require(recovered_task["contextId"] == task["contextId"], "recovery changed native context")
        require(equal(recovery["final_public_task"], recovered_task), "recovery final public task mismatch")
        require(final_occurred_in_wire("mgcrea_raw", recovered_task, recovery["wire"]), "recovery result absent from public wire")
        artifact = recovered_task["artifacts"][0]["parts"][0]
        restored_checks = {key: equal(artifact.get(key), value) for key, value in expected.items()}
        require(recovery["field_checks"] == restored_checks and recovery["status"] == ("pass" if all(restored_checks.values()) else "fail"), "recovery grade mismatch")
    else:
        require(cell["recovery"]["status"] == "not_applicable", "ineligible recovery should be N/A")
    return {"payload_pass": checks[PAYLOAD[cell["case_id"]]], "representation_pass": all(checks.values()),
            "field_pass": sum(checks.values()), "field_eligible": len(checks),
            "recovery_eligible": eligible, "recovery_pass": eligible and cell["recovery"]["status"] == "pass"}


def verify(bundle):
    members = verify_manifest(bundle)
    allocation = read_json(bundle / "allocation.json")
    verify_sources(bundle, allocation)
    cells = [read_json(path) for path in sorted((bundle / "cells").glob("*.json"))]
    require(Counter((c["case_id"], c["repetition"], c["route"]) for c in cells) == Counter((c["case_id"], c["repetition"], c["route"]) for c in allocation["cells"]), "parts allocation census mismatch")
    analyses = [(c, verify_cell(c)) for c in cells]
    result = read_json(bundle / "results.json")
    require(result["status"] == "complete" and result["changed_sources"] == [], "parts execution not clean")
    for route, profiles in result["by_route"].items():
        for profile, summary in profiles.items():
            selected = [a for c, a in analyses if c["route"] == route and c["case_id"] == profile]
            expected = {"attempts": len(selected), "representation_pass": sum(a["representation_pass"] for a in selected),
                        "representation_fail": sum(not a["representation_pass"] for a in selected), "unknown": 0,
                        "payload_pass": sum(a["payload_pass"] for a in selected), "field_pass": sum(a["field_pass"] for a in selected),
                        "field_eligible": sum(a["field_eligible"] for a in selected), "recovery_eligible": sum(a["recovery_eligible"] for a in selected),
                        "recovery_pass": sum(a["recovery_pass"] for a in selected)}
            require(summary == expected, "parts route summary mismatch")
    lifecycle = read_json(bundle / "lifecycle.json")
    require(lifecycle["fixture_exited"] is True and lifecycle["proxy_closed"] is True, "parts lifecycle not closed")
    return {"schema_version": "loss_parts_verification_v2", "status": "passed", "verified_utc": datetime.now(timezone.utc).isoformat(),
            "verifier_sha256": sha(Path(__file__)), "input_manifest_sha256": sha(bundle / "manifest.json"),
            "manifest_files": members, "part_attempts_regraded": len(cells),
            "native_task_context_associations": len(cells), "same_task_recoveries": sum(a["recovery_pass"] for _, a in analyses),
            "wire_records_verified": sum(len(c["wire"]) for c in cells), "by_route": result["by_route"],
            "limitations": ["Recorded-byte regrading is not a new upstream execution or human validation.",
                "Four deterministic artifact commands and five repeated tasks do not estimate real-world prevalence.",
                "Text payload utility and complete artifact metadata fidelity are distinct outcomes.",
                "The typed metadata/content mapping is intentional upstream behavior; observed contract failure does not establish an upstream bug.",
                "Raw recovery policy is adaptive development selected after the earlier smoke result, not untouched held-out evaluation."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "verification output already exists")
    result = verify(args.bundle)
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("by_route", "limitations")}))


if __name__ == "__main__":
    main()
