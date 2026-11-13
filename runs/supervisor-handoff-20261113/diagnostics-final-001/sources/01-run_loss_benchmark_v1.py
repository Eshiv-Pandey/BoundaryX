"""Fresh finite software diagnostics, never a real protocol/model benchmark.

The receiver, conversion profiles, fixture and gold grader are separate functions.
Each cell gets a new in-memory fixture. Artifact publication refuses overwrites.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
CASES_PATH = ROOT / "benchmark/loss-v1/development-cases.json"
PROFILES = ("reference", "placebo_identity", "dropped_fact", "capability_mismatch",
            "wrong_task", "constraint_loss", "safe_equivalent", "recovery")
REQUIRED_TOOL = "fixture.read_snapshot.v1"
RUNTIME_POLICY = {"mode": "read_only", "allowed_tools": [REQUIRED_TOOL],
                  "forbidden_effects": ["restart_service", "acknowledge_incident", "write_snapshot"]}
EVIDENCE_NOTICE = ("FRESH CONSTRUCTED software diagnostic; authored development fixtures, "
                   "not real MCP/A2A conversion, not an LLM run, not held-out evidence.")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def identity(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write_new(path: Path, value: Any) -> None:
    """Output directory is exclusively created; each file also uses no-clobber mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical(value) + b"\n")


def load_cases(path: Path = CASES_PATH) -> dict:
    package = json.loads(path.read_bytes())
    if package.get("schema_version") != "loss_benchmark_development_cases_v1":
        raise ValueError("unsupported development-case schema")
    if package.get("evidence_kind") != "fresh_constructed":
        raise ValueError("only authored fresh_constructed fixtures are accepted")
    if package.get("record_order_irrelevant") is not True:
        raise ValueError("v1 context projection requires this finite bank's explicit record-order irrelevance")
    budget = package["episode_budget"]
    if budget != {"max_receiver_attempts": 2, "max_snapshot_reads": 2}:
        raise ValueError("v1 fixes the same two-attempt/read episode budget for every profile")
    cases = package["cases"]
    if not cases or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("case IDs must be nonempty and unique")
    if len({c["family_id"] for c in cases}) != len(cases):
        raise ValueError("this finite v1 bank declares one task per decision family")
    for case in cases:
        gold = case["gold"]
        if gold["expected_task_id"] != case["task"]["task_id"] or gold["expected_target"] != case["task"]["target"]:
            raise ValueError("gold task/target do not bind to the original case")
        if gold["forbidden_effects"] != RUNTIME_POLICY["forbidden_effects"]:
            raise ValueError("case does not carry the common read-only effect policy")
        # This independent truth evaluator never calls the receiver or converter.
        if canonical(gold_truth(case)) != canonical(gold["expected_answer"]):
            raise ValueError("pinned gold disagrees with independent finite task truth: " + case["case_id"])
    return package


def gold_truth(case: dict) -> dict:
    """Independent task truth; uses full pinned case constraints and never receiver output.

    Kept separate deliberately: the gold uses relational sets/joins and path expansion;
    the receiver below uses its converted observation and ordinary sequential operations.
    """
    rows, c, kind = case["records"], case["task"]["constraints"], case["task"]["kind"]
    if kind == "health_filter":
        return {"service_ids": sorted({r["id"] for r in rows if (r["region"], r["status"]) == (c["region"], c["status"])})}
    if kind == "incident_triage":
        return {"incident_ids": sorted({r["id"] for r in rows if r["region"] == c["region"] and r["severity"] >= c["minimum_severity"] and (r["open"] or not c["open_only"])})}
    if kind == "latency_argmax":
        eligible = {r["id"]: r["p95_ms"] for r in rows if r["region"] == c["region"] and (not r["canary"] or not c["exclude_canary"])}
        service_id = sorted(eligible, key=lambda key: (-eligible[key], key))[0]
        return {"service_id": service_id, "p95_ms": eligible[service_id]}
    if kind == "owner_join":
        incidents = {r["id"]: r["service_id"] for r in rows if r["type"] == "incident"}
        owners = {r["id"]: r["owner"] for r in rows if r["type"] == "service"}
        service = incidents[c["incident_id"]]
        return {"incident_id": c["incident_id"], "service_id": service, "owner": owners[service]}
    if kind == "headroom_filter":
        values = {r["id"]: r["capacity"] - r["used"] for r in rows if r["region"] == c["region"]}
        return {"headroom": [{"service_id": key, "units": values[key]} for key in sorted(values) if values[key] < c["below_units"]]}
    if kind == "latest_deployment":
        scoped = {(r["minute"], r["id"]) for r in rows if (r["service_id"], r["environment"]) == (c["service_id"], c["environment"])}
        minute, deployment = sorted(scoped, key=lambda pair: (-pair[0], pair[1]))[0]
        return {"deployment_id": deployment, "minute": minute}
    if kind == "alert_count":
        return {"active_alert_count": len({r["id"] for r in rows if r["service_id"] == c["service_id"] and (not r["suppressed"] or not c["exclude_suppressed"])})}
    if kind == "incident_duration":
        starts = {r["id"]: r["opened_minute"] for r in rows}
        return {"incident_id": c["incident_id"], "duration_minutes": c["clock_minute"] - starts[c["incident_id"]]}
    if kind == "dependency_impact":
        edges = {(r["upstream"], r["downstream"]) for r in rows}
        paths = {(c["start"],)}
        for _ in range(c["max_depth"]):
            paths |= {path + (b,) for path in list(paths) for a, b in edges if path[-1] == a and b not in path}
        return {"affected_services": sorted({node for path in paths for node in path[1:]} - {c["start"]})}
    if kind == "snapshot_select":
        eligible = {(r["created_minute"], r["id"], r["version"]) for r in rows if r["service_id"] == c["service_id"] and 0 <= c["clock_minute"] - r["created_minute"] <= c["max_age_minutes"] and r["version"] >= c["minimum_version"]}
        _, snapshot, version = sorted(eligible, key=lambda row: (-row[0], row[1]))[0]
        return {"snapshot_id": snapshot, "version": version}
    raise ValueError("unknown task kind")


class ReadOnlyFixture:
    """Controlled in-memory service. New instance per cell is the complete reset."""
    def __init__(self, case: dict, budget: dict):
        self.case = deepcopy(case)
        self.budget = deepcopy(budget)
        self.state = {"reads": [], "effects": [], "rejected_calls": []}
        self.initial_content = canonical(self.case["records"])

    def read_snapshot(self, task_id: str, tool: str = REQUIRED_TOOL) -> list:
        if tool != REQUIRED_TOOL or task_id != self.case["task"]["task_id"]:
            self.state["rejected_calls"].append({"task_id": task_id, "tool": tool})
            raise ValueError("fixture rejects unbound task/tool")
        if len(self.state["reads"]) >= self.budget["max_snapshot_reads"]:
            raise ValueError("snapshot read budget exhausted")
        self.state["reads"].append({"task_id": task_id, "target": self.case["task"]["target"], "tool": tool})
        return deepcopy(self.case["records"])

    def observe_state(self) -> dict:
        return {**deepcopy(self.state), "content_unchanged": canonical(self.case["records"]) == self.initial_content,
                "runtime_policy": deepcopy(RUNTIME_POLICY)}


def make_sender(case: dict, fixture: ReadOnlyFixture, budget: dict) -> dict:
    return {"task": deepcopy(case["task"]), "records": fixture.read_snapshot(case["task"]["task_id"]),
            "tool_binding": REQUIRED_TOOL, "runtime_policy": deepcopy(RUNTIME_POLICY),
            "episode_budget": deepcopy(budget)}


def source_truth(case: dict, budget: dict) -> dict:
    """Independent pre-sender truth, rather than reconstructing source from sent data."""
    return {"task": deepcopy(case["task"]), "records": deepcopy(case["records"]),
            "tool_binding": REQUIRED_TOOL, "runtime_policy": deepcopy(RUNTIME_POLICY),
            "episode_budget": deepcopy(budget)}


def convert(sender: dict, profile: str) -> dict:
    if profile not in PROFILES:
        raise ValueError("unknown profile")
    wire = deepcopy(sender)
    if profile in ("dropped_fact", "recovery"):
        del wire["records"]
    elif profile == "capability_mismatch":
        wire["tool_binding"] = "fixture.restart_service.v1"
    elif profile == "wrong_task":
        wire["task"]["task_id"] = "decoy-" + wire["task"]["task_id"]
        wire["task"]["target"] = "decoy/" + wire["task"]["target"]
    elif profile == "constraint_loss":
        wire["task"]["constraints"] = {}
    elif profile == "safe_equivalent":
        wire["records"].reverse()  # Record ordering is irrelevant to these ten tasks.
    elif profile == "placebo_identity":
        wire["annotation"] = "Placebo envelope decoration; task payload unchanged."
    return wire


def receiver_decision(wire: dict) -> dict:
    """Deterministic receiver; it has no access to the case gold or source message."""
    task = wire["task"]
    base = {"task_id": task["task_id"], "target": task["target"]}
    if wire.get("tool_binding") != REQUIRED_TOOL:
        return {**base, "status": "capability_unusable", "answer": None}
    if "records" not in wire:
        return {**base, "status": "missing_fact", "answer": None}
    rows = wire["records"]
    c, kind = task.get("constraints", {}), task["kind"]
    selected = []
    if kind == "health_filter":
        for row in rows:
            if ("region" not in c or row["region"] == c["region"]) and ("status" not in c or row["status"] == c["status"]):
                selected.append(row["id"])
        answer = {"service_ids": sorted(selected)}
    elif kind == "incident_triage":
        for row in rows:
            if ("region" not in c or row["region"] == c["region"]) and row["severity"] >= c.get("minimum_severity", 0) and (not c.get("open_only", False) or row["open"]):
                selected.append(row["id"])
        answer = {"incident_ids": sorted(selected)}
    elif kind == "latency_argmax":
        for row in rows:
            if ("region" not in c or row["region"] == c["region"]) and (not c.get("exclude_canary", False) or not row["canary"]):
                selected.append(row)
        winner = min(selected, key=lambda row: (-row["p95_ms"], row["id"]))
        answer = {"service_id": winner["id"], "p95_ms": winner["p95_ms"]}
    elif kind == "owner_join":
        incidents = [r for r in rows if r["type"] == "incident"]
        incident = next((r for r in incidents if r["id"] == c.get("incident_id")), sorted(incidents, key=lambda r: r["id"])[0])
        owner = next(r["owner"] for r in rows if r["type"] == "service" and r["id"] == incident["service_id"])
        answer = {"incident_id": incident["id"], "service_id": incident["service_id"], "owner": owner}
    elif kind == "headroom_filter":
        for row in rows:
            units = row["capacity"] - row["used"]
            if ("region" not in c or row["region"] == c["region"]) and units < c.get("below_units", float("inf")):
                selected.append({"service_id": row["id"], "units": units})
        answer = {"headroom": sorted(selected, key=lambda row: row["service_id"])}
    elif kind == "latest_deployment":
        for row in rows:
            if ("service_id" not in c or row["service_id"] == c["service_id"]) and ("environment" not in c or row["environment"] == c["environment"]):
                selected.append(row)
        winner = min(selected, key=lambda row: (-row["minute"], row["id"]))
        answer = {"deployment_id": winner["id"], "minute": winner["minute"]}
    elif kind == "alert_count":
        count = 0
        for row in rows:
            if ("service_id" not in c or row["service_id"] == c["service_id"]) and (not c.get("exclude_suppressed", False) or not row["suppressed"]):
                count += 1
        answer = {"active_alert_count": count}
    elif kind == "incident_duration":
        incident = next((r for r in rows if r["id"] == c.get("incident_id")), sorted(rows, key=lambda r: r["id"])[0])
        answer = {"incident_id": incident["id"], "duration_minutes": c.get("clock_minute", 0) - incident["opened_minute"]}
    elif kind == "dependency_impact":
        start = c.get("start", "")
        visited, frontier = {start}, [start]
        for _ in range(c.get("max_depth", 0)):
            following = []
            for node in frontier:
                for row in rows:
                    if row["upstream"] == node and row["downstream"] not in visited:
                        visited.add(row["downstream"])
                        following.append(row["downstream"])
            frontier = following
        answer = {"affected_services": sorted(visited - {start})}
    elif kind == "snapshot_select":
        for row in rows:
            age = c.get("clock_minute", row["created_minute"]) - row["created_minute"]
            if ("service_id" not in c or row["service_id"] == c["service_id"]) and 0 <= age <= c.get("max_age_minutes", float("inf")) and row["version"] >= c.get("minimum_version", 0):
                selected.append(row)
        winner = min(selected, key=lambda row: (-row["created_minute"], row["id"]))
        answer = {"snapshot_id": winner["id"], "version": winner["version"]}
    else:
        return {**base, "status": "unsupported_task", "answer": None}
    return {**base, "status": "completed", "answer": answer}


def grade(case: dict, receiver: dict, state: dict) -> dict:
    """Gold task grader: checks final answer, original task/target and forbidden effects."""
    gold = case["gold"]
    checks = {"final_answer": receiver["status"] == "completed" and canonical(receiver["answer"]) == canonical(gold["expected_answer"]),
              "correct_task": receiver["task_id"] == gold["expected_task_id"],
              "correct_target": receiver["target"] == gold["expected_target"] and all(r["target"] == gold["expected_target"] for r in state["reads"]),
              "forbidden_effects_absent": not any(e in gold["forbidden_effects"] for e in state["effects"]),
              "state_content_unchanged": state["content_unchanged"],
              "runtime_policy_equal": state["runtime_policy"] == RUNTIME_POLICY}
    return {"task_completion": "pass" if all(checks.values()) else "fail", "checks": checks,
            "expected_answer": deepcopy(gold["expected_answer"])}


def context_projection(message: dict) -> dict:
    # These finite tasks explicitly disregard snapshot record order. Sort by the
    # canonical full record, retaining duplicate records and all field types.
    # This is a task-specific fact-group representation, not natural-language meaning.
    records = sorted(deepcopy(message["records"]), key=canonical) if "records" in message else None
    return {"task_id": message["task"]["task_id"], "target": message["task"]["target"],
            "task_kind": message["task"]["kind"], "task_constraints": message["task"]["constraints"],
            "records": records, "tool_binding": message["tool_binding"],
            "runtime_policy": message["runtime_policy"], "episode_budget": message["episode_budget"]}


def capability_probe(case: dict, budget: dict, message: dict, label: str) -> dict:
    """Actual isolated invocation, excluded from episode state, budget and costs."""
    began = time.perf_counter_ns()
    fixture = ReadOnlyFixture(case, budget)
    request = {"task_id": message["task"]["task_id"], "tool_binding": message["tool_binding"]}
    try:
        records = fixture.read_snapshot(request["task_id"], request["tool_binding"])
        result = {"status": "pass", "records": records}
    except ValueError as exc:
        result = {"status": "fail", "error": str(exc)}
    request_raw, result_raw = canonical(request), canonical(result)
    state = fixture.observe_state()
    return {"label": label, "scope": "isolated_diagnostic_clone_not_policy_episode",
            "request": request, "request_identity": identity(request_raw),
            "result": result, "result_identity": identity(result_raw),
            "state": state, "costs": {"wall_ms": (time.perf_counter_ns() - began) / 1_000_000,
                                      "invocation_attempts": 1, "successful_snapshot_reads": len(state["reads"]),
                                      "request_bytes": len(request_raw), "response_bytes": len(result_raw)}}


def run_cell(case: dict, profile: str, budget: dict, source_files: list,
             replicate: int = 0, order_seed: int = 1729, position: int = 0) -> tuple[dict, dict]:
    events, transfers = [], []

    def event(boundary: str, payload: Any, transfer: str | None = None) -> None:
        raw = canonical(payload)
        events.append({"sequence": len(events), "boundary": boundary, "payload": deepcopy(payload), **identity(raw)})
        if transfer:
            transfers.append({"sequence": len(events) - 1, "direction": transfer, "bytes": len(raw)})

    started = time.perf_counter_ns()
    fixture = ReadOnlyFixture(case, budget)
    event("reset_initial_state", fixture.observe_state())
    original_source = source_truth(case, budget)
    event("pre_sender_source_truth", original_source)
    sender = make_sender(case, fixture, budget)
    event("sender_to_converter", sender, "request")
    wire = convert(sender, profile)
    event("converter_to_receiver", wire, "request")
    first_result = receiver_decision(wire)
    result, final_wire, attempts = first_result, wire, 1
    event("receiver_attempt_1", first_result, "response")
    recovery_status = "not_applicable"
    if profile == "recovery":
        if first_result["status"] == "missing_fact" and attempts < budget["max_receiver_attempts"]:
            request = {"task_id": wire["task"]["task_id"], "tool_binding": wire["tool_binding"], "reason": "missing_records"}
            event("receiver_recovery_request", request, "request")
            recovered = fixture.read_snapshot(request["task_id"], request["tool_binding"])
            event("fixture_recovery_response", {"records": recovered}, "response")
            final_wire = deepcopy(wire)
            final_wire["records"] = recovered
            event("recovered_observation_to_receiver", final_wire, "request")
            result, attempts = receiver_decision(final_wire), 2
            event("receiver_attempt_2", result, "response")
        recovery_status = "fail"  # Updated by the independent final grader below.
    state = fixture.observe_state()
    event("final_fixture_state", state)
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    assessment = grade(case, result, state)
    if profile == "recovery" and attempts == 2 and assessment["task_completion"] == "pass":
        recovery_status = "pass"
    # Initial conversion loss remains visible even if a subsequent policy reread
    # repairs the final task outcome. Both observations remain in the raw trace.
    source, sent, received = context_projection(original_source), context_projection(sender), context_projection(wire)
    reference_probe = capability_probe(case, budget, original_source, "reference_required_binding")
    receiver_probe = capability_probe(case, budget, final_wire, "receiver_observed_binding")
    constraints_equal = canonical(sender["task"]["constraints"]) == canonical(final_wire["task"]["constraints"])
    fidelity = {"original_task_binding": result["task_id"] == case["task"]["task_id"] and result["target"] == case["task"]["target"],
                "required_tool_binding": final_wire["tool_binding"] == REQUIRED_TOOL,
                "required_records_available": "records" in final_wire,
                "task_constraints_preserved": constraints_equal,
                "runtime_policy_preserved": final_wire["runtime_policy"] == RUNTIME_POLICY,
                "episode_budget_preserved": final_wire["episode_budget"] == budget}
    episode_id = f"{case['case_id']}--{profile}--r{replicate:03d}"
    episode = {"schema_version": "loss_benchmark_episode_v1", "episode_id": episode_id,
               "family_id": case["family_id"], "route_id": "constructed_python_fixture_v1/" + profile,
               "evidence_kind": "fresh_constructed", "task_completion": assessment["task_completion"],
               "context_items": [{"id": key, "source": source[key], "sent": sent[key], "received": received[key],
                                  "observed": {"source": True, "sent": True, "received": True},
                                  "present": {"source": True, "sent": True, "received": key != "records" or "records" in wire}} for key in source],
               "capability_items": [{"id": REQUIRED_TOOL, "required": True, "reference_usable": reference_probe["result"]["status"] == "pass",
                                     "observed_usable": receiver_probe["result"]["status"] == "pass",
                                     "advertised": final_wire["tool_binding"] == REQUIRED_TOOL}],
               "fidelity_checks": [{"id": key, "status": "pass" if value else "fail"} for key, value in fidelity.items()],
               "recovery": {"eligible": profile == "recovery", "status": recovery_status},
               "costs": {"wall_ms": elapsed_ms, "messages": len(transfers), "tool_calls": len(state["reads"]),
                         "request_bytes": sum(t["bytes"] for t in transfers if t["direction"] == "request"),
                         "response_bytes": sum(t["bytes"] for t in transfers if t["direction"] == "response"), "model_tokens": 0},
               "source_files": deepcopy(source_files),
               "notes": [EVIDENCE_NOTICE, "Known absence of a converted field is observed=true with received=null; no inaccessible observation is fabricated.",
                         "wall_ms covers reset, pre-sender source truth, sender fixture read, conversion, receiver attempt(s), state capture and boundary serialization. It excludes gold grading, isolated diagnostic capability probes, metric scoring, artifact I/O and process startup.",
                         "messages and bytes count exactly the transferred boundary payloads in raw_trace.transfers; tool_calls count successful controlled fixture snapshot reads.",
                         "Context units are eight explicit fact groups; records are canonical-sorted with duplicates preserved because these ten authored tasks declare record order irrelevant. Generic engine equality is unchanged; no natural-language equivalence is claimed.",
                         "Context received is the initial converter output. Post-recovery context is retained separately and cannot erase initial conversion loss.",
                         "Capability qualification comes from actual read invocations on separate diagnostic clones, with requests/results and costs in the raw trace; those probes do not consume the task episode budget or inflate episode costs.",
                         "Replicates measure Python timing variation and are not independent tasks."],
               "metadata": {"case_id": case["case_id"], "task_kind": case["task"]["kind"], "profile": profile,
                            "replicate": replicate, "order_seed": order_seed, "position": position,
                            "pair_id": f"{case['case_id']}--r{replicate:03d}", "baseline_profile": "reference",
                            "episode_budget": deepcopy(budget), "receiver_attempts": attempts,
                            "conversion_profile": "dropped_fact" if profile == "recovery" else profile,
                            "receiver_policy_id": "missing_fact_public_snapshot_reread_v1" if profile == "recovery" else "single_attempt_no_recovery_v1",
                            "post_recovery_context": context_projection(final_wire) if profile == "recovery" else None,
                            "raw_records_order_changed": "records" in wire and canonical(sender["records"]) != canonical(wire["records"]),
                            "capability_probe_scope": "isolated_diagnostic_clone_not_policy_episode",
                            "initial_receiver_status": first_result["status"], "gold_checks": assessment["checks"],
                            "raw_trace": f"cells/{episode_id}/raw-trace.json"}}
    trace = {"schema_version": "loss_benchmark_raw_trace_v1", "episode_id": episode_id,
             "evidence_notice": EVIDENCE_NOTICE, "case_id": case["case_id"], "profile": profile,
             "events": events, "transfers": transfers, "receiver_final": result,
             "diagnostic_capability_probes": [reference_probe, receiver_probe],
             "gold_assessment": assessment, "costs": episode["costs"]}
    return episode, trace


def retained_episodes(path: Path | None) -> list:
    if path is None:
        return []
    if path.is_dir():
        path = path / "normalized-episodes.json"
    raw = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
        rows = value if isinstance(value, list) else value["episodes"]
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not isinstance(rows, list):
        raise ValueError("retained input must be an episode list or JSONL")
    if any(row.get("evidence_kind") == "fresh_constructed" for row in rows):
        raise ValueError("--retained cannot relabel fresh constructed rows as retained evidence")
    return rows


def run(output: Path, cases_path: Path = CASES_PATH, profiles: tuple = PROFILES,
        replicates: int = 1, seed: int = 1729, retained: Path | None = None) -> dict:
    from interoperability import loss_benchmark_v1 as metrics

    if replicates < 1 or replicates > 100:
        raise ValueError("replicates must be in [1,100]; replication is timing-only")
    if not profiles or any(profile not in PROFILES for profile in profiles) or len(set(profiles)) != len(profiles):
        raise ValueError("profiles must be unique known values")
    package = load_cases(cases_path)
    retained_rows = retained_episodes(retained)
    for row in retained_rows:
        metrics.validate_episode(row)
    metrics_path = Path(metrics.__file__).resolve()
    source_paths = [Path(__file__).resolve(), metrics_path, cases_path.resolve()]
    sources = [{"path": str(path), "sha256": identity(path.read_bytes())["sha256"]} for path in source_paths]
    cells = [(case, profile, replicate) for case in package["cases"] for profile in profiles for replicate in range(replicates)]
    random.Random(seed).shuffle(cells)
    # This is the sole allocation mutation. Existing paths are refused even if empty.
    output.mkdir(parents=True, exist_ok=False)
    started_utc = datetime.now(timezone.utc).isoformat()
    write_new(output / "input-cases.json", package)
    for index, path in enumerate(source_paths):
        destination = output / "sources" / (f"{index:02d}-" + path.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(path.read_bytes())
    allocation = {"schema_version": "loss_benchmark_allocation_v1", "evidence_notice": EVIDENCE_NOTICE,
                  "started_utc": started_utc, "order_seed": seed, "replicates": replicates,
                  "profiles": list(profiles), "case_count": len(package["cases"]), "cell_count": len(cells),
                  "episode_budget": package["episode_budget"], "source_files": sources,
                  "cells": [{"position": pos, "case_id": case["case_id"], "profile": profile, "replicate": rep} for pos, (case, profile, rep) in enumerate(cells)]}
    write_new(output / "allocation.json", allocation)
    fresh = []
    for position, (case, profile, replicate) in enumerate(cells):
        episode, trace = run_cell(case, profile, package["episode_budget"], sources, replicate, seed, position)
        metrics.validate_episode(episode)
        write_new(output / episode["metadata"]["raw_trace"], trace)
        write_new(output / "cells" / episode["episode_id"] / "normalized-episode.json", episode)
        fresh.append(episode)
    combined = retained_rows + fresh
    if len({row["episode_id"] for row in combined}) != len(combined):
        raise ValueError("duplicate episode IDs between retained and fresh evidence")
    write_new(output / "normalized-episodes.json", fresh)
    write_new(output / "combined-episodes.json", combined)
    summary = metrics.summarize_episodes(combined)
    write_new(output / "metrics-summary.json", summary)
    grouped = {}
    for profile in profiles:
        group = [row for row in fresh if row["metadata"]["profile"] == profile]
        grouped[profile] = {"episodes": len(group), "task_pass": sum(row["task_completion"] == "pass" for row in group),
                            "metrics": metrics.summarize_episodes(group)}
    report = {"schema_version": "loss_benchmark_fresh_result_v1", "evidence_notice": EVIDENCE_NOTICE,
              "fresh_episodes": len(fresh), "retained_episodes": len(retained_rows),
              "independent_decision_families": len(package["cases"]), "held_out_cases": 0,
              "by_profile": grouped, "combined_metrics_path": "metrics-summary.json",
              "limitations": ["Authored finite rules and injected faults demonstrate metric/runner behavior only.",
                              "No network transport, external tool, model token, native MCP/A2A route, or provider latency is measured.",
                              "All task data are public development truth, and there is one case per family.",
                              "Replicates and conversion profiles do not add independent task families.",
                              "Gold grading is independent of the receiver/converter but both truth and software are authored in this workspace."]}
    write_new(output / "fresh-results.json", report)
    receipt = {"schema_version": "loss_benchmark_execution_receipt_v1", "status": "complete",
               "started_utc": started_utc, "completed_utc": datetime.now(timezone.utc).isoformat(),
               "python_executable": sys.executable, "python_version": platform.python_version(),
               "platform": platform.platform(), "argv": sys.argv, "exit_code": 0,
               "provider_services_started": False, "model_calls": 0, "source_files": sources,
               "fresh_episodes": len(fresh), "evidence_notice": EVIDENCE_NOTICE}
    write_new(output / "execution-receipt.json", receipt)
    manifest = {"schema_version": "loss_benchmark_artifact_manifest_v1", "files": [
        {"path": path.relative_to(output).as_posix(), **identity(path.read_bytes())}
        for path in sorted(output.rglob("*")) if path.is_file()]}
    write_new(output / "manifest.json", manifest)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=EVIDENCE_NOTICE)
    parser.add_argument("--output", type=Path, required=True, help="fresh directory; existing path is refused")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1729, help="cell-order seed, not model sampling")
    parser.add_argument("--retained", type=Path, help="previous normalized retained JSON/JSONL; evidence kinds stay separate")
    args = parser.parse_args(argv)
    try:
        report = run(args.output, args.cases, tuple(args.profiles), args.replicates, args.seed, args.retained)
    except Exception as exc:
        print(f"loss-benchmark-v1 refused/failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "fresh_episodes": report["fresh_episodes"],
                      "retained_episodes": report["retained_episodes"], "independent_decision_families": report["independent_decision_families"],
                      "by_profile": {key: {"episodes": value["episodes"], "task_pass": value["task_pass"]} for key, value in report["by_profile"].items()},
                      "notice": EVIDENCE_NOTICE}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
