"""Independent source/payload/outcome and public-wire checks.

No legacy scoring, gold or receiver functions are imported. Hashes bind copies,
not authenticated origin. Read-only effects are observations of the supplied
fixture; protocol captures alone cannot prove unobserved business effects.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterator

from boundaryx.core.evidence import EvidenceError, digest, parse, publish, read, same, verify_manifest
from boundaryx.protocols.a2a.evidence import identity, public_task
from boundaryx.verification.semantic import expected_answer

GROUPS: dict[str, list[tuple[str, ...]]] = {"records": [("records",)],
          "task_identity": [("task", "task_id"), ("task", "target")],
          "constraints": [("task", "constraints")], "tool_binding": [("tool_binding",)]}
ARTIFACT_GOLD: dict[str, dict[str, Any]] = {
    "text": {"text": "lavivrus-kramhcneb", "mediaType": "text/plain"},
    "data": {"data": {"answer": 42, "echo": "benchmark-survival"}, "mediaType": "application/json"},
    "file": {"url": "https://example.invalid/files/report.pdf", "filename": "report.pdf", "mediaType": "application/pdf"},
    "image": {"raw": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "filename": "pixel.png", "mediaType": "image/png"},
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise EvidenceError(reason)


def json_hash(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode())


def nested(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from nested(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested(child)
    elif isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            yield from nested(parse(value))
        except EvidenceError:
            pass


def packets(wire: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in wire:
        for side in ("request", "response"):
            entity = row.get(side)
            if not entity:
                continue
            raw = entity["raw"].encode("utf8")
            require(len(raw) == entity["bytes"] and digest(raw) == entity["sha256"], "Wire entity hash/size mismatch")
            if not raw:
                continue
            if raw.startswith(b"data:") or b"\ndata:" in raw:
                values = [parse(line[5:].strip()) for line in raw.splitlines() if line.startswith(b"data:")]
            else:
                values = [parse(raw)]
            result.extend(v for v in values if isinstance(v, dict))
    return result


def occurred(value: Any, wire: list[dict[str, Any]]) -> bool:
    return any(same(value, candidate) for packet in packets(wire) for candidate in nested(packet))


def boundaries(source: dict[str, Any], sent: dict[str, Any], received: dict[str, Any]) -> dict[str, Any]:
    def comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, bool]:
        checks = {}
        for key in ("task", "records", "tool_binding", "runtime_policy", "episode_budget"):
            checks[key] = key in a and key in b and same(a[key], b[key])
        return checks
    return {"source_to_sent": comparison(source, sent), "sent_to_received": comparison(sent, received),
            "source_to_received": comparison(source, received),
            "meaning": "exact typed structural checks; intentional fault losses are observations, not verifier errors"}


def source_check(case: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    require(same(case["task"], source["task"]) and same(case["records"], source["records"]), "Source differs from frozen case")
    expected = expected_answer(case)
    require(same(expected, case["gold"]["expected_answer"]), "Independent oracle disagrees with proposed gold")
    require(case["gold"]["expected_task_id"] == source["task"]["task_id"] and case["gold"]["expected_target"] == source["task"]["target"], "Gold identity differs from source")
    return expected


def completion(case: dict[str, Any], answer: dict[str, Any], state: dict[str, Any] | None) -> str:
    expected = expected_answer(case)
    checks = [answer.get("status") == "completed", same(answer.get("answer"), expected),
              same(answer.get("task_id"), case["task"]["task_id"]), same(answer.get("target"), case["task"]["target"])]
    if state is not None:
        checks += [state.get("content_unchanged") is True,
                   not any(e in case["gold"]["forbidden_effects"] for e in state.get("effects", [])),
                   same(state.get("runtime_policy"), {"mode": "read_only", "allowed_tools": ["fixture.read_snapshot.v1"], "forbidden_effects": ["restart_service", "acknowledge_incident", "write_snapshot"]}),
                   all(r.get("target") == case["task"]["target"] for r in state.get("reads", []))]
    return "pass" if all(checks) else "fail"


def restore(observed: dict[str, Any], source: dict[str, Any], groups: list[str]) -> dict[str, Any]:
    result = deepcopy(observed)
    for group in groups:
        for path in GROUPS[group]:
            dest, src = result, source
            for key in path[:-1]:
                dest = dest.setdefault(key, {})
                src = src[key]
            if path[-1] in src:
                dest[path[-1]] = deepcopy(src[path[-1]])
            else:
                dest.pop(path[-1], None)
    return result


def repair_check(case: dict[str, Any], trace: dict[str, Any], diagnosis: dict[str, Any]) -> int:
    cert = diagnosis["repair_certificate"]
    source, observed = trace["source"], trace["received_initial"]
    require(cert["reference_sha256"] == json_hash(source) and cert["observed_sha256"] == json_hash(observed), "Repair source/observation digest mismatch")
    changed = []
    for group in GROUPS:
        if not same(restore(observed, source, [group]), observed):
            changed.append(group)
    require(cert["changed_groups"] == changed, "Changed repair-group universe differs")
    expected_subsets = {frozenset(changed[i] for i in range(len(changed)) if mask & (1 << i)) for mask in range(1 << len(changed))}
    seen: set[frozenset[str]] = set()
    successes: list[set[str]] = []
    for trial in cert["trials"]:
        group_set = frozenset(trial["restore"])
        require(group_set not in seen and group_set in expected_subsets and len(group_set) == len(trial["restore"]), "Invalid/duplicate repair subset")
        seen.add(group_set)
        payload = restore(observed, source, trial["restore"])
        require(json_hash(payload) == trial["payload_sha256"], "Repair intervention digest mismatch")
        assessment = trial["assessment"]
        independent = completion(case, assessment.get("receiver", {}), trace["state"])
        require(independent == assessment["task_completion"], "Independent repair outcome disagrees")
        if independent == "pass":
            # Successful assessment must be possible under its restored task and binding.
            require(payload.get("tool_binding") == "fixture.read_snapshot.v1" and "records" in payload, "Successful repair lacks required capability/data")
            require(same(payload["task"], source["task"]), "Successful repair changes original task contract")
            successes.append(set(group_set))
    require(seen == expected_subsets and cert["trial_count"] == len(seen), "Incomplete finite repair enumeration")
    minimal = [s for s in successes if not any(t < s for t in successes)]
    require({frozenset(s) for s in minimal} == {frozenset(s) for s in cert["minimal_repair_sets"]}, "Incorrect finite minimal repair sets")
    require(cert["minimum_repair_group_count"] == (min(map(len, minimal)) if minimal else None), "Incorrect minimum repair cardinality")
    return len(seen)


def verify_diagnostics(bundle: Path) -> dict[str, Any]:
    files = verify_manifest(bundle)
    bank = read(bundle / "input-bank.json")
    cases = {c["case_id"]: c for c in bank["cases"]}
    allocation = read(bundle / "allocation.json")
    expected = {(c["case_id"], c["profile"]) for c in allocation["cells"]}
    rows = []
    repairs = 0
    seen = set()
    for folder in sorted((bundle / "cells").iterdir()):
        trace, episode = read(folder / "trace.json"), read(folder / "episode.json")
        key = (episode["metadata"]["case_id"], episode["metadata"]["profile"])
        require(key not in seen and key in expected, "Unallocated/duplicate diagnostic episode")
        seen.add(key)
        case = cases[key[0]]
        source_check(case, trace["source"])
        result = completion(case, trace["receiver_final"].get("receiver", {}), trace["state"])
        require(result == episode["task_completion"] == trace["receiver_final"]["task_completion"], "Independent diagnostic outcome differs")
        for transfer in trace["transfers"]:
            require(json_hash(transfer["payload"]) == transfer["sha256"], "Transfer payload digest mismatch")
        repairs += repair_check(case, trace, read(folder / "diagnosis.json"))
        rows.append({"episode_id": trace["episode_id"], "task_completion": result,
                     "boundaries": boundaries(trace["source"], trace["sent"], trace["received_final"])})
    require(seen == expected, "Missing allocated diagnostic episodes")
    return {"kind": "diagnostics", "files_verified": files, "episodes": len(rows),
            "repair_interventions": repairs, "rows": rows}


def verify_protocol(bundle: Path) -> dict[str, Any]:
    files = verify_manifest(bundle)
    bank = read(bundle / "input-bank.json")
    cases = {c["case_id"]: c for c in bank["cases"]}
    allocation = read(bundle / "allocation.json")
    expected = {(c["case_id"], c["profile"], c["route"]) for c in allocation["cells"]}
    seen = set()
    rows = []
    probes = 0
    for path in sorted((bundle / "cells").glob("*.json")):
        cell = read(path)
        key = (cell["case_id"], cell["profile"], cell["route"])
        require(key not in seen and key in expected, "Unallocated/duplicate protocol episode")
        seen.add(key)
        obs = cell["observation"]
        case = cases[key[0]]
        source_check(case, obs["source"])
        wire = cell["episode_wire"]
        decoded = packets(wire)
        require(occurred(cell["final_public_result"], wire), "Final public result absent from recorded wire")
        require(occurred(cell["service_result"], wire), "Receiver result absent from public wire")
        requests = [p for p in decoded if p.get("method") == "SendMessage"]
        evaluations = []
        recovery_requests = []
        for request in requests:
            for part in request["params"]["message"].get("parts", []):
                if "text" not in part:
                    continue
                try:
                    payload = parse(part["text"])
                except EvidenceError:
                    continue
                if payload.get("operation") == "evaluate":
                    evaluations.append(payload["observation"])
                if payload.get("operation") == "recover_read":
                    recovery_requests.append(request["params"]["message"])
        require(any(same(obs["received"], value) for value in evaluations), "Received payload absent from actual A2A request")
        if cell["recovery"]["eligible"]:
            require(bool(recovery_requests), "Recovery has no public continuation")
            native_ids = []
            for w in wire:
                if w.get("request") and w.get("response"):
                    request = parse(w["request"]["raw"])
                    if request.get("method") == "SendMessage":
                        native_ids.append(identity(public_task(parse(w["response"]["raw"]))))
            original = next((pair for pair in native_ids if all(pair)), None)
            require(original is not None and all((m.get("taskId"), m.get("contextId")) == original for m in recovery_requests), "Recovery does not preserve original A2A task/context")
        result = completion(case, cell["service_result"], None)
        require(result == cell["task_completion"], "Independent protocol answer/identity outcome differs")
        packets(cell["probe_wire"])
        probes += len(cell["capability_probes"])
        rows.append({"episode_id": cell["episode_id"], "task_completion": result,
                     "boundaries": boundaries(obs["source"], obs["sent"], obs["received"]),
                     "effects": "unknown outside controlled read-only fixture"})
    require(seen == expected, "Missing allocated protocol episodes")
    return {"kind": "protocol", "files_verified": files, "episodes": len(rows), "separate_read_probes": probes, "rows": rows}


def artifact_projection(cell: dict[str, Any]) -> Any:
    result, route = cell["final"], cell["route"]
    if route in ("native", "mgcrea_raw"):
        return result.get("artifacts", [{}])[0].get("parts", [None])[0]
    if route == "mgcrea_typed":
        return result.get("artifacts", [None])[0]
    for block in result.get("content", []):
        meta = block.get("_meta", {}).get("io.github.amirk-s/a2a", {})
        if not meta.get("artifactId"):
            continue
        if block["type"] == "text":
            key = "data" if meta.get("partKind") == "data" else "text"
            return {key: parse(block["text"]) if key == "data" else block["text"], "mediaType": meta.get("mediaType")}
        if block["type"] == "resource_link":
            return {"url": block["uri"], "filename": block["name"], "mediaType": block["mimeType"]}
        if block["type"] == "image":
            return {"raw": block["data"], "filename": meta.get("filename"), "mediaType": block["mimeType"]}
    return None


def verify_artifact_cell(cell: dict[str, Any]) -> dict[str, Any]:
    gold = ARTIFACT_GOLD[cell["case_id"]]
    require(same(gold, cell["spec"]["expected"]), "Artifact specification differs from independent fixture contract")
    require(occurred(cell["final"], cell["wire"]), "Artifact final read absent from captured wire")
    observed = artifact_projection(cell)
    fields = {k: isinstance(observed, dict) and k in observed and same(v, observed[k]) for k, v in gold.items()}
    require(same(fields, cell["field_checks"]) and all(fields.values()) == cell["required_representation_survived"], "Artifact field assessment differs")
    recovery = cell["recovery"]
    recovered_fields = 0
    if recovery["eligible"]:
        task = recovery["final_public_task"]
        require(identity(task) == (cell["receipt"]["id"], cell["receipt"]["contextId"]), "Raw recovery returned a different task/context")
        require(occurred(task, recovery["wire"]), "Recovered task absent from actual raw response")
        actual = task["artifacts"][0]["parts"][0]
        require(all(k in actual and same(v, actual[k]) for k, v in gold.items()), "Raw recovery has not restored every required field")
        requests = [p for p in packets(recovery["wire"]) if p.get("method") == "GetTask"]
        require(bool(requests) and all(p["params"]["id"] == cell["receipt"]["id"] for p in requests), "Recovery lacks same-task public GetTask")
        recovered_fields = len(gold)
    return {"route": cell["route"], "case_id": cell["case_id"], "fields_retained": sum(fields.values()),
            "required_fields": len(fields), "complete": all(fields.values()),
            "raw_recovery": recovery["eligible"], "recovered_fields": recovered_fields}


def verify_artifacts(bundle: Path) -> dict[str, Any]:
    files = verify_manifest(bundle)
    allocation = read(bundle / "allocation.json")
    expected = {(c["case_id"], c["repetition"], c["route"]) for c in allocation["cells"]}
    seen = set()
    rows = []
    for path in sorted((bundle / "cells").glob("*.json")):
        cell = read(path)
        key = (cell["case_id"], cell["repetition"], cell["route"])
        require(key not in seen and key in expected, "Unallocated/duplicate artifact cell")
        seen.add(key)
        rows.append(verify_artifact_cell(cell))
    require(seen == expected, "Missing allocated artifact cells")
    totals = {}
    for route in sorted({r["route"] for r in rows}):
        route_rows = [r for r in rows if r["route"] == route]
        totals[route] = dict(Counter({"tasks": len(route_rows), "complete": sum(r["complete"] for r in route_rows),
                                    "fields_retained": sum(r["fields_retained"] for r in route_rows),
                                    "required_fields": sum(r["required_fields"] for r in route_rows),
                                    "recoveries": sum(r["raw_recovery"] for r in route_rows),
                                    "recovered_fields": sum(r["recovered_fields"] for r in route_rows)}))
    return {"kind": "artifacts", "files_verified": files, "tasks": len(rows), "by_route": totals, "rows": rows}


def report(output: Path, *, diagnostics: Path | None = None, protocol: Path | None = None,
           artifacts: Path | None = None) -> dict[str, Any]:
    reports = []
    for path, verifier in ((diagnostics, verify_diagnostics), (protocol, verify_protocol), (artifacts, verify_artifacts)):
        if path is not None:
            reports.append(verifier(path))
    require(bool(reports), "No evidence selected")
    package = Path(__file__).resolve().parents[1]
    paths = ["verification/independent.py", "verification/semantic.py", "core/evidence.py", "protocols/a2a/evidence.py"]
    result = {"schema_version": "boundaryx_independent_verification_v1", "status": "Completed",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "reports": reports,
              "verifier_sources": [{"path": "src/boundaryx/" + p, "sha256": digest((package / p).read_bytes())} for p in paths],
              "independence": "SQLite task oracle and separate evidence checks; no legacy receiver/gold/scoring functions",
              "limits": ["Shared task definitions, standard JSON/SQLite infrastructure and captured observations",
                         "No authenticated source provenance or independent human scientific review",
                         "Protocol effects outside the controlled fixture are unknown",
                         "Artifact fixture expectations are independently transcribed, not independent task design"]}
    publish(output, result)
    return result
