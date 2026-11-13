"""Read-only evidence checker for local diagnostics and fresh protocol runs.

Reconstructs outcomes, boundaries, task associations, probe outcomes, costs,
allocation census and finite repair minimality from captured inputs. This is a
separate software checker, not independent human validation or a live rerun.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from interoperability import loss_benchmark_v1 as metrics
from interoperability import loss_diagnostics_v2 as diagnostic
from scripts import run_loss_benchmark_v1 as receiver


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=metrics._unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def equal(a, b):
    return diagnostic.canonical(a) == diagnostic.canonical(b)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def member(bundle, relative):
    name = PurePosixPath(relative)
    require(not name.is_absolute() and ".." not in name.parts and "\\" not in relative, "unsafe manifest path")
    target = bundle.joinpath(*name.parts)
    require(target.resolve().is_relative_to(bundle.resolve()), "member escaped bundle")
    require(not target.is_symlink(), "symbolic evidence member refused")
    return target


def verify_manifest(bundle):
    manifest = read_json(bundle / "manifest.json")
    listed = [x["path"] for x in manifest["files"]]
    require(len(listed) == len(set(listed)), "duplicate manifest member")
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file() and p != bundle / "manifest.json"}
    require(actual == set(listed), "manifest does not enumerate the complete bundle")
    for item in manifest["files"]:
        path = member(bundle, item["path"])
        require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], "artifact mismatch: " + item["path"])
    return len(listed)


def verify_sources(bundle, allocation):
    for index, source in enumerate(allocation["source_files"] if "source_files" in allocation else allocation["sources"]):
        local = ROOT / source["path"]
        captured = bundle / "sources" / source["path"]
        if not captured.exists():
            captured = bundle / "sources" / (f"{index:02d}-" + Path(source["path"]).name)
        require(sha(local) == source["sha256"] == sha(captured), "current/captured source mismatch: " + source["path"])


def grade(case, result):
    gold = case["gold"]
    checks = {"answer": result.get("status") == "completed" and equal(result.get("answer"), gold["expected_answer"]),
              "original_task": result.get("task_id") == gold["expected_task_id"],
              "original_target": result.get("target") == gold["expected_target"]}
    return "pass" if all(checks.values()) else "fail"


def projection(message):
    task = message["task"]
    return {"task_id": task["task_id"], "target": task["target"], "task_kind": task["kind"],
            "task_constraints": task["constraints"], "records": sorted(message["records"], key=diagnostic.canonical) if "records" in message else None,
            "tool_binding": message["tool_binding"], "runtime_policy": message["runtime_policy"], "episode_budget": message["episode_budget"]}


def expected_context(source, sent, received):
    values = list(map(projection, (source, sent, received)))
    return [{"id": key, **dict(zip(metrics.STAGES, (value[key] for value in values))),
             "observed": dict.fromkeys(metrics.STAGES, True),
             "present": {stage: key != "records" or "records" in message for stage, message in zip(metrics.STAGES, (source, sent, received))}}
            for key in values[0]]


def expected_fidelity(case, final, source):
    task = final["task"]
    return {"original_task_binding": task["task_id"] == case["task"]["task_id"] and task["target"] == case["task"]["target"],
            "required_tool_binding": final["tool_binding"] == receiver.REQUIRED_TOOL,
            "required_records_available": "records" in final,
            "task_constraints_preserved": equal(task["constraints"], source["task"]["constraints"]),
            "runtime_policy_preserved": equal(final["runtime_policy"], receiver.RUNTIME_POLICY),
            "episode_budget_preserved": equal(final["episode_budget"], source["episode_budget"])}


def expected_boundaries(case, profile, budget):
    """Checker-owned reconstruction of each frozen intervention definition."""
    source = receiver.source_truth(case, budget)
    sent = deepcopy(source)
    if profile == "extraction_loss":
        del sent["records"]
    received = deepcopy(sent)
    if profile in ("dropped_fact", "recovery", "compound_records_binding", "compound_all"):
        del received["records"]
    if profile in ("capability_mismatch", "compound_records_binding", "compound_all"):
        received["tool_binding"] = "fixture.restart_service.v1"
    if profile in ("wrong_task", "compound_identity_constraints", "compound_all"):
        received["task"]["task_id"] = "decoy-" + received["task"]["task_id"]
        received["task"]["target"] = "decoy/" + received["task"]["target"]
    if profile in ("constraint_loss", "compound_identity_constraints", "compound_all"):
        received["task"]["constraints"] = {}
    if profile == "safe_equivalent":
        received["records"].reverse()
    if profile == "placebo_identity":
        received["annotation"] = "Placebo envelope decoration; task payload unchanged."
    return source, sent, received


def replay_receiver(observation):
    try:
        return receiver.receiver_decision(deepcopy(observation))
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        return {"status": "receiver_error", "error": type(exc).__name__ + ": " + str(exc)}


def verify_repair(case, source, received, certificate):
    changed = diagnostic.changed_groups(source, received)
    require(certificate["reference_sha256"] == diagnostic.digest(source), "repair source mismatch")
    require(certificate["observed_sha256"] == diagnostic.digest(received), "repair observation mismatch")
    require(certificate["changed_groups"] == changed and certificate["universe"] == list(diagnostic.REPAIR_GROUPS), "repair universe mismatch")
    subsets = [list(c) for size in range(len(changed) + 1) for c in combinations(changed, size)]
    require([t["restore"] for t in certificate["trials"]] == subsets, "repair subset census mismatch")
    successful = []
    for trial in certificate["trials"]:
        restored = diagnostic.restore_groups(received, source, trial["restore"])
        require(diagnostic.digest(restored) == trial["payload_sha256"], "repair payload mismatch")
        result = replay_receiver(restored)
        outcome = grade(case, result)
        require(outcome == trial["assessment"]["task_completion"], "repair outcome mismatch")
        if "receiver" in trial["assessment"]:
            require(equal(result, trial["assessment"]["receiver"]), "repair receiver mismatch")
        if outcome == "pass":
            successful.append(set(trial["restore"]))
    minimal = [s for s in successful if not any(t < s for t in successful)]
    require(certificate["minimal_repair_sets"] == [sorted(s) for s in minimal], "repair minimality mismatch")
    require(certificate["minimum_repair_group_count"] == (min(map(len, minimal)) if minimal else None), "minimum cardinality mismatch")
    require(certificate["trial_count"] == len(subsets) and certificate["unknown_trials"] == 0 and certificate["status"] == "complete", "repair completion mismatch")
    return len(subsets)


def verify_diagnostics(bundle):
    members = verify_manifest(bundle)
    allocation = read_json(bundle / "allocation.json")
    verify_sources(bundle, allocation)
    bank = read_json(bundle / "input-bank.json")
    cases = {c["case_id"]: c for c in bank["cases"]}
    for case in cases.values():
        require(equal(receiver.gold_truth(case), case["gold"]["expected_answer"]), "case gold mismatch")
    episodes = read_json(bundle / "episodes.json")
    require(len(episodes) == len(allocation["cells"]), "diagnostic allocation census mismatch")
    allocated = Counter((c["case_id"], c["profile"]) for c in allocation["cells"])
    require(allocated == Counter((e["metadata"]["case_id"], e["metadata"]["profile"]) for e in episodes), "diagnostic cell identity mismatch")
    interventions = 0
    for episode in episodes:
        metrics.validate_episode(episode)
        directory = bundle / "cells" / episode["episode_id"]
        trace, detail = read_json(directory / "trace.json"), read_json(directory / "diagnosis.json")
        require(equal(read_json(directory / "episode.json"), episode), "cell episode copy mismatch")
        case = cases[episode["metadata"]["case_id"]]
        source, sent, received, final = (trace[k] for k in ("source", "sent", "received_initial", "received_final"))
        require(equal(source, receiver.source_truth(case, bank["episode_budget"])), "diagnostic source truth mismatch")
        require(equal((source, sent, received), expected_boundaries(case, episode["metadata"]["profile"], bank["episode_budget"])), "diagnostic condition implementation mismatch")
        expected_final = deepcopy(received)
        recovered = episode["metadata"]["profile"] == "recovery"
        if recovered:
            expected_final["records"] = deepcopy(case["records"])
        require(equal(final, expected_final), "undeclared receiver repair or changed final observation")
        require(episode["metadata"]["receiver_attempts"] == (2 if recovered else 1), "receiver attempt census mismatch")
        require(episode["recovery"] == {"eligible": recovered, "status": episode["task_completion"] if recovered else "not_applicable"}, "recovery score mismatch")
        require(equal(episode["context_items"], expected_context(source, sent, received)), "diagnostic context mismatch")
        require(grade(case, trace["receiver_final"]["receiver"]) == episode["task_completion"], "diagnostic final grade mismatch")
        require(equal(trace["receiver_final"]["receiver"], replay_receiver(final)), "diagnostic receiver re-execution mismatch")
        fidelity = expected_fidelity(case, final, source)
        require(episode["fidelity_checks"] == [{"id": k, "status": "pass" if v else "fail"} for k, v in fidelity.items()], "diagnostic fidelity mismatch")
        require(trace["state"]["effects"] == [] and trace["state"]["content_unchanged"], "diagnostic state/effect mismatch")
        for transfer in trace["transfers"]:
            raw = diagnostic.canonical(transfer["payload"])
            require(transfer["bytes"] == len(raw) and transfer["sha256"] == hashlib.sha256(raw).hexdigest(), "diagnostic transfer identity mismatch")
        for direction in ("request", "response"):
            require(episode["costs"][direction + "_bytes"] == sum(t["bytes"] for t in trace["transfers"] if t["direction"] == direction), "diagnostic transfer cost mismatch")
        require(episode["costs"]["messages"] == len(trace["transfers"]), "diagnostic message census mismatch")
        require(episode["costs"]["tool_calls"] == len(trace["state"]["reads"]), "diagnostic read census mismatch")
        require(episode["costs"]["model_tokens"] == 0, "diagnostic model usage mismatch")
        expected_caps = []
        for probe, wire, label in zip(trace["capability_probes"], (source, final), ("reference_required_binding", "receiver_observed_binding")):
            request = {"task_id": wire["task"]["task_id"], "tool_binding": wire["tool_binding"]}
            usable = request["task_id"] == case["task"]["task_id"] and request["tool_binding"] == receiver.REQUIRED_TOOL
            require(probe["label"] == label and equal(probe["request"], request), "diagnostic probe request mismatch")
            require(probe["result"]["status"] == ("pass" if usable else "fail"), "diagnostic probe outcome mismatch")
            if usable:
                require(equal(probe["result"]["records"], case["records"]), "diagnostic probe record mismatch")
            for key in ("request", "result"):
                raw = diagnostic.canonical(probe[key])
                require(probe[key + "_identity"] == {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, "diagnostic probe identity mismatch")
            expected_caps.append(usable)
        require(equal(episode["capability_items"], [{"id": receiver.REQUIRED_TOOL, "required": True,
            "reference_usable": expected_caps[0], "observed_usable": expected_caps[1],
            "advertised": final["tool_binding"] == receiver.REQUIRED_TOOL}]), "diagnostic capability score mismatch")
        for label, before, after, normalize in (("extraction", source, sent, True), ("conversion", sent, received, True), ("end_to_end", source, received, True), ("raw_conversion", sent, received, False)):
            require(equal(detail["boundaries"][label], diagnostic.boundary_diff(before, after, normalize)), "leaf boundary reconstruction mismatch")
        interventions += verify_repair(case, source, received, detail["repair_certificate"])
    require(equal(metrics.summarize_episodes(episodes), read_json(bundle / "metrics-summary.json")), "diagnostic score regeneration mismatch")
    results = read_json(bundle / "results.json")
    require(results["episodes"] == len(episodes) and results["repair_interventions"] == interventions, "diagnostic result census mismatch")
    for profile, group in results["by_profile"].items():
        rows = [e for e in episodes if e["metadata"]["profile"] == profile]
        require(group["task_pass"] == sum(e["task_completion"] == "pass" for e in rows), "profile pass mismatch")
        require(equal(group["scores"], metrics.summarize_episodes(rows)["scores"]), "profile score mismatch")
        reference_rows = [{"pair_id": e["metadata"]["pair_id"], "task_completion": e["task_completion"]} for e in episodes if e["metadata"]["profile"] == "reference"]
        require(equal(group["paired_reference"], diagnostic.paired_outcomes(reference_rows, [{"pair_id": e["metadata"]["pair_id"], "task_completion": e["task_completion"]} for e in rows])), "paired profile result mismatch")
        details = [read_json(bundle / "cells" / e["episode_id"] / "diagnosis.json") for e in rows]
        require(group["minimum_repair_groups_histogram"] == dict(Counter(str(d["repair_certificate"]["minimum_repair_group_count"]) for d in details)), "repair histogram mismatch")
        for stage, totals in group["boundary_leaf_totals"].items():
            require(totals == {key: sum(d["boundaries"][stage][key] for d in details) for key in ("eligible_leaves", "kept", "changed", "missing", "added")}, "leaf summary mismatch")
    return {"status": "passed", "manifest_files": members, "episodes_regraded": len(episodes),
            "repair_interventions_reexecuted": interventions, "cases": len(cases), "families": len({c["family_id"] for c in cases.values()})}


def unwrap_mcp(body):
    if body.get("structuredContent") is not None:
        return body["structuredContent"]
    return json.loads(body["content"][0]["text"])


def public_result(cell, public):
    route = cell["route"]
    if route == "amirk_typed":
        texts = [p["text"] for p in public["content"] if p["type"] == "text" and p["text"].startswith("{") and "task_id" in p["text"]]
        return json.loads(texts[-1])
    if route == "mgcrea_typed":
        return json.loads(public["artifacts"][-1]["text"])
    return json.loads(public["artifacts"][-1]["parts"][0]["text"])


def verify_protocol_cell(cell, case, source_files):
    for wire in cell["episode_wire"] + cell["probe_wire"]:
        for direction in ("request", "response"):
            blob = wire.get(direction)
            if blob is not None:
                raw = blob["raw"].encode("utf-8")
                require(blob["bytes"] == len(raw) and blob["sha256"] == hashlib.sha256(raw).hexdigest(), "protocol wire identity mismatch")
    require("execution_error" not in cell, "protocol allocation contains execution error")
    require(len(cell["capability_probes"]) == 2, "probe census mismatch")
    native = [w for w in cell["episode_wire"] if w["role"] == "native_service_wire" and w.get("request") and w.get("path") == "/a2a"]
    sends = [w for w in native if json.loads(w["request"]["raw"])["method"] == "SendMessage"]
    gets = [w for w in native if json.loads(w["request"]["raw"])["method"] == "GetTask"]
    require(sends and gets, "missing actual native send/get")
    first = json.loads(sends[0]["request"]["raw"])
    actual_observation = json.loads(first["params"]["message"]["parts"][0]["text"])
    require(actual_observation["operation"] == "evaluate" and equal(actual_observation["observation"], cell["observation"]["received"]), "service input differs from captured converter output")
    initial_task = json.loads(sends[0]["response"]["raw"])["result"]["task"]
    last_request, last_response = (json.loads(gets[-1][key]["raw"]) for key in ("request", "response"))
    task = last_response["result"]
    require(last_request["params"]["id"] == initial_task["id"] == task["id"], "actual final read task association mismatch")
    require(initial_task["contextId"] == task["contextId"], "actual final read context association mismatch")
    authoritative = json.loads(task["artifacts"][-1]["parts"][0]["text"])
    require(equal(authoritative, cell["service_result"]), "authoritative native artifact differs from reported result")
    require(equal(public_result(cell, cell["final_public_result"]), authoritative), "public final artifact differs from native artifact")
    # Public final result must actually occur in a captured response.
    public_matches = []
    for wire in cell["episode_wire"]:
        if wire["role"] in ("mcp_client_wire", "mcp_server_message", "native_client_wire") and wire.get("response"):
            raw = wire["response"]["raw"]
            if raw.startswith("data:") or "\ndata:" in raw:
                raw = next(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
            decoded = json.loads(raw)
            result = decoded.get("result")
            if cell["route"] == "mgcrea_typed" and result:
                result = unwrap_mcp(result)
            elif cell["route"] == "mgcrea_raw" and result:
                result = unwrap_mcp(result).get("result")
            if result and equal(result.get("task", result), cell["final_public_result"]):
                public_matches.append(wire)
    require(public_matches, "reported public final result absent from client wire")
    final_observation = deepcopy(cell["observation"]["received"])
    if cell["profile"] == "recovery":
        require(len(sends) == 2, "recovery native send census mismatch")
        followup = json.loads(sends[1]["request"]["raw"])["params"]["message"]
        require(followup["taskId"] == initial_task["id"] and followup["contextId"] == initial_task["contextId"], "recovery native binding mismatch")
        final_observation["records"] = deepcopy(case["records"])
    else:
        require(len(sends) == 1, "nonrecovery case unexpectedly resumed")
    require(equal(replay_receiver(final_observation), authoritative), "protocol receiver re-execution mismatch")
    outcome = grade(case, authoritative)
    require(outcome == cell["task_completion"], "protocol final grade mismatch")
    # Completed A2A state alone never supplies task success.
    if outcome == "pass":
        require(task["status"]["state"] == "TASK_STATE_COMPLETED", "successful task lacks authoritative completion")
    for probe in cell["capability_probes"]:
        require("error" not in probe, "actual read probe failed to execute")
        request = probe["request"]
        expected = request["task_id"] == case["task"]["task_id"] and request["tool_binding"] == receiver.REQUIRED_TOOL
        require(probe["decoded"]["usable"] is expected, "actual probe outcome mismatch")
        require(equal(public_result(cell, probe["final"]), probe["decoded"]), "probe public artifact mismatch")
        if expected:
            require(equal(probe["decoded"]["records"], case["records"]), "probe content mismatch")
        actual_probe_records = [w for w in cell["probe_wire"] if w["role"] == "native_service_wire" and w.get("request") and w.get("path") == "/a2a"]
        actual_probe_sends = [w for w in actual_probe_records if json.loads(w["request"]["raw"])["method"] == "SendMessage"]
        linked = []
        for wire in actual_probe_sends:
            packet = json.loads(wire["request"]["raw"])
            payload = json.loads(packet["params"]["message"]["parts"][0]["text"])
            if payload == {"operation": "probe_read", **request}:
                native_task = json.loads(wire["response"]["raw"])["result"]["task"]
                for read_wire in actual_probe_records:
                    query = json.loads(read_wire["request"]["raw"])
                    if query["method"] == "GetTask" and query["params"]["id"] == native_task["id"]:
                        probe_task = json.loads(read_wire["response"]["raw"])["result"]
                        require(probe_task["contextId"] == native_task["contextId"], "probe context mismatch")
                        native_decoded = json.loads(probe_task["artifacts"][-1]["parts"][0]["text"])
                        if equal(native_decoded, probe["decoded"]):
                            linked.append(native_task["id"])
        require(linked, "claimed probe is absent from actual native request/result")
    source, sent, received = (cell["observation"][s] for s in ("source", "sent", "received"))
    require(equal(source, receiver.source_truth(case, source["episode_budget"])), "protocol source truth mismatch")
    require(equal((source, sent, received), expected_boundaries(case, cell["profile"], source["episode_budget"])), "protocol condition implementation mismatch")
    caps = {p["label"]: p["decoded"]["usable"] for p in cell["capability_probes"]}
    fidelity = expected_fidelity(case, final_observation, source)
    # Each protocol layer has its own cost inventory; count every wire entity once.
    counts = {}
    for role in ("native_service_wire", "native_client_wire", "mcp_client_wire", "mcp_client_message", "mcp_server_message"):
        group = [w for w in cell["episode_wire"] if w["role"] == role]
        counts[role] = {"request_bytes": sum(w["request"]["bytes"] for w in group if w.get("request")),
                        "response_bytes": sum(w["response"]["bytes"] for w in group if w.get("response")),
                        "request_entities": sum(w.get("request") is not None for w in group),
                        "response_entities": sum(w.get("response") is not None for w in group)}
    costs = counts["native_service_wire"]
    normalized = {"schema_version": metrics.EPISODE_SCHEMA_VERSION, "episode_id": cell["episode_id"],
                  "family_id": cell["family_id"], "route_id": "protocol_v2/" + cell["route"] + "/" + cell["profile"],
                  "evidence_kind": "fresh_constructed", "task_completion": outcome,
                  "context_items": expected_context(source, sent, received),
                  "capability_items": [{"id": receiver.REQUIRED_TOOL, "required": True,
                                        "reference_usable": caps["reference"], "observed_usable": caps["receiver"],
                                        "advertised": received["tool_binding"] == receiver.REQUIRED_TOOL}],
                  "fidelity_checks": [{"id": k, "status": "pass" if v else "fail"} for k, v in fidelity.items()],
                  "recovery": {"eligible": cell["profile"] == "recovery", "status": outcome if cell["profile"] == "recovery" else "not_applicable"},
                  "costs": {"wall_ms": cell["wall_ms"], "messages": costs["request_entities"] + costs["response_entities"],
                            "tool_calls": 2 if cell["profile"] == "recovery" else 1,
                            "request_bytes": costs["request_bytes"], "response_bytes": costs["response_bytes"], "model_tokens": 0},
                  "source_files": source_files, "notes": ["Authored deterministic tasks over actual MCP/A2A protocols; engine evidence kind denotes constructed tasks, wrapper records fresh protocol execution.",
                    "Context captures owned source/extraction/injected conversion and service input, not autonomous model extraction.",
                    "Core overhead bytes/messages count native A2A service entities, excluding setup and diagnostic probes. MCP costs are in wire_costs_by_layer.",
                    "tool_calls count owned source snapshot acquisition plus recovery reread; actual task-bound probes are separate.",
                    "Read-only receiver has no business effect operations; this controlled task does not qualify a production effect policy."],
                  "metadata": {"case_id": cell["case_id"], "pair_id": cell["case_id"], "profile": cell["profile"],
                               "route": cell["route"], "execution_kind": "fresh_protocol_development", "wire_costs_by_layer": counts,
                               "boundary_diagnostics": {s: diagnostic.boundary_diff(a, b, True) for s, a, b in
                                   (("extraction", source, sent), ("conversion", sent, received), ("end_to_end", source, received))}}}
    metrics.validate_episode(normalized)
    return normalized, len(cell["episode_wire"]), len(cell["probe_wire"])


def verify_protocol(bundle):
    members = verify_manifest(bundle)
    allocation = read_json(bundle / "allocation.json")
    verify_sources(bundle, allocation)
    cases = {c["case_id"]: c for c in read_json(bundle / "input-bank.json")["cases"]}
    paths = sorted((bundle / "cells").glob("*.json"))
    require(len(paths) == len(allocation["cells"]), "protocol allocation count mismatch")
    allocated = Counter((c["case_id"], c["profile"], c["route"]) for c in allocation["cells"])
    cells = [read_json(p) for p in paths]
    require(allocated == Counter((c["case_id"], c["profile"], c["route"]) for c in cells), "protocol allocation identity mismatch")
    source_files = [{"path": x["path"], "sha256": x["sha256"]} for x in allocation["sources"]]
    episodes, wire_count, probe_count = [], 0, 0
    for cell in cells:
        episode, wires, probes = verify_protocol_cell(cell, cases[cell["case_id"]], source_files)
        episodes.append(episode)
        wire_count += wires
        probe_count += probes
    result = read_json(bundle / "results.json")
    require(result["protocol_errors"] == 0 and result["sources_changed"] == [] and result["service_closed"] is True, "protocol run not clean")
    by_route = {}
    for route in allocation["routes"]:
        by_route[route] = {}
        refs = [{"pair_id": e["metadata"]["pair_id"], "task_completion": e["task_completion"]} for e in episodes if e["metadata"]["route"] == route and e["metadata"]["profile"] == "reference"]
        for profile in allocation["profiles"]:
            group = [e for e in episodes if e["metadata"]["route"] == route and e["metadata"]["profile"] == profile]
            score = metrics.summarize_episodes(group)
            expected = {"attempts": len(group), **{s: sum(e["task_completion"] == s for e in group) for s in metrics.STATUSES}}
            require(equal(result["by_route"][route][profile], expected), "protocol route/profile summary mismatch")
            by_route[route][profile] = {**expected, "scores": score["scores"],
                                      "paired_reference": diagnostic.paired_outcomes(refs, [{"pair_id": e["metadata"]["pair_id"], "task_completion": e["task_completion"]} for e in group])}
    verification = {"status": "passed", "manifest_files": members, "episodes_regraded": len(episodes),
                    "episode_wire_records_verified": wire_count, "probe_wire_records_verified": probe_count,
                    "actual_probe_attempts": len(episodes) * 2,
                    "native_task_context_associations": len(episodes), "routes": allocation["routes"],
                    "constructed_task_families": len({c["family_id"] for c in cells}), "by_route": by_route,
                    "limitations": ["Independent checker code regrades recorded bytes; no new live service reproduction.",
                        "Author/AI-authored task gold and software are not independent human validation.",
                        "Owned controlled receiver and injected transformations do not establish original application loss prevalence.",
                        "No LLM generation, remote network latency, population statistics or scientific novelty demonstrated."]}
    return verification, episodes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.diagnostics or args.protocol, "at least one evidence bundle is required")
    require(not args.output.exists(), "verification output already exists")
    result = {"schema_version": "loss_release_verification_v2", "status": "passed",
              "verified_utc": datetime.now(timezone.utc).isoformat(), "verifier_sha256": sha(Path(__file__)), "inputs": {}}
    episodes = None
    if args.diagnostics:
        result["inputs"]["diagnostics"] = {"path": str(args.diagnostics), "manifest_sha256": sha(args.diagnostics / "manifest.json")}
        result["diagnostics"] = verify_diagnostics(args.diagnostics)
    if args.protocol:
        result["inputs"]["protocol"] = {"path": str(args.protocol), "manifest_sha256": sha(args.protocol / "manifest.json")}
        result["protocol"], episodes = verify_protocol(args.protocol)
    args.output.mkdir(parents=True, exist_ok=False)
    receiver.write_new(args.output / "verification.json", result)
    if episodes is not None:
        receiver.write_new(args.output / "protocol-episodes.json", episodes)
        receiver.write_new(args.output / "protocol-metrics-summary.json", {"schema_version": "fresh_protocol_summary_v2", "evidence_scope": "authored tasks on actual protocol routes", "by_route": result["protocol"]["by_route"]})
    print(json.dumps({"status": result["status"], "diagnostics": {k: v for k, v in result.get("diagnostics", {}).items() if k != "by_route"},
                      "protocol": {k: v for k, v in result.get("protocol", {}).items() if k not in ("by_route", "limitations")}, "output": str(args.output)}))


if __name__ == "__main__":
    main()
