"""Fresh multi-fault benchmark with byte-linked boundary and repair evidence."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts import run_loss_benchmark_v1 as base
from interoperability import loss_benchmark_v1 as metrics
from interoperability import loss_diagnostics_v2 as diagnostic

PROFILES = base.PROFILES + ("extraction_loss", "compound_records_binding",
                           "compound_identity_constraints", "compound_all")
NOTICE = "Authored development diagnostics; no LLM, held-out evaluation or original application execution."


def generated_bank(variants: int, seed: int) -> dict:
    if not 1 <= variants <= 100:
        raise ValueError("variants must be in [1,100]")
    bank = base.load_cases()
    rng = random.Random(seed)
    cases = []
    identifier_keys = {"id", "service_id", "upstream", "downstream", "owner", "start", "incident_id"}
    time_keys = {"minute", "created_minute", "opened_minute", "clock_minute"}
    for template in bank["cases"]:
        for index in range(variants):
            case = deepcopy(template)
            suffix = f"-v{index:03d}-{seed}"
            offset = rng.randint(1, 500)

            def transform(value, key=""):
                if isinstance(value, dict):
                    return {k: transform(v, k) for k, v in value.items()}
                if isinstance(value, list):
                    return [transform(v, key) for v in value]
                if isinstance(value, str) and key in identifier_keys:
                    return value + suffix
                if type(value) is int and key in time_keys:
                    return value + offset
                if type(value) is int and key == "p95_ms":
                    return value + offset
                return value

            case["records"] = transform(case["records"])
            case["task"]["constraints"] = transform(case["task"]["constraints"])
            rng.shuffle(case["records"])
            case["case_id"] += suffix
            case["task"]["task_id"] += suffix
            case["task"]["target"] += suffix
            case["gold"] = {"expected_answer": base.gold_truth(case),
                            "expected_task_id": case["task"]["task_id"],
                            "expected_target": case["task"]["target"],
                            "forbidden_effects": deepcopy(base.RUNTIME_POLICY["forbidden_effects"])}
            case["generation"] = {"template_case_id": template["case_id"], "variant": index,
                                  "seed": seed, "numeric_offset": offset,
                                  "changes": "consistent identifier renaming, timestamp/latency translation, record permutation"}
            cases.append(case)
    return {"schema_version": "loss_diagnostic_bank_v2", "evidence_kind": "fresh_constructed",
            "seed": seed, "variants_per_family": variants, "family_count": len(bank["cases"]),
            "case_count": len(cases), "held_out_cases": 0, "notice": NOTICE,
            "episode_budget": deepcopy(bank["episode_budget"]), "cases": cases}


def observations(case: dict, budget: dict, profile: str) -> tuple[dict, dict, dict]:
    if profile not in PROFILES:
        raise ValueError("unknown profile")
    source = base.source_truth(case, budget)
    sent = deepcopy(source)
    if profile == "extraction_loss":
        sent.pop("records")
    received = deepcopy(sent)
    faults = {
        "compound_records_binding": ("dropped_fact", "capability_mismatch"),
        "compound_identity_constraints": ("wrong_task", "constraint_loss"),
        "compound_all": ("dropped_fact", "capability_mismatch", "wrong_task", "constraint_loss"),
    }
    if profile in base.PROFILES:
        received = base.convert(sent, profile)
    elif profile in faults:
        for fault in faults[profile]:
            received = base.convert(received, fault)
    return source, sent, received


def evaluate(case: dict, observation: dict) -> dict:
    try:
        answer = base.receiver_decision(deepcopy(observation))
        state = base.ReadOnlyFixture(case, {"max_receiver_attempts": 2, "max_snapshot_reads": 2}).observe_state()
        assessment = base.grade(case, answer, state)
        return {"task_completion": assessment["task_completion"], "receiver": answer, "checks": assessment["checks"]}
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        return {"task_completion": "fail", "receiver_error": type(exc).__name__ + ": " + str(exc), "checks": {}}


def run_cell(case: dict, profile: str, budget: dict, source_files: list) -> tuple[dict, dict, dict]:
    began = time.perf_counter_ns()
    fixture = base.ReadOnlyFixture(case, budget)
    fixture.read_snapshot(case["task"]["task_id"])
    source, sent, initial = observations(case, budget, profile)
    transfers = [{"boundary": "sender_to_converter", "direction": "request", "payload": sent},
                 {"boundary": "converter_to_receiver", "direction": "request", "payload": initial}]
    first = evaluate(case, initial)
    result, final, attempts = first, deepcopy(initial), 1
    transfers.append({"boundary": "receiver_attempt_1", "direction": "response", "payload": first})
    recovery = {"eligible": profile == "recovery", "status": "not_applicable"}
    if profile == "recovery":
        request = {"task_id": initial["task"]["task_id"], "tool_binding": initial["tool_binding"]}
        rows = fixture.read_snapshot(request["task_id"], request["tool_binding"])
        final["records"] = rows
        result, attempts = evaluate(case, final), 2
        recovery["status"] = result["task_completion"]
        transfers.extend([{"boundary": "recovery_request", "direction": "request", "payload": request},
                          {"boundary": "recovery_response", "direction": "response", "payload": {"records": rows}},
                          {"boundary": "receiver_attempt_2", "direction": "response", "payload": result}])
    state = fixture.observe_state()
    elapsed = (time.perf_counter_ns() - began) / 1e6
    ref_probe = base.capability_probe(case, budget, source, "reference_required_binding")
    rec_probe = base.capability_probe(case, budget, final, "receiver_observed_binding")
    projections = [base.context_projection(x) for x in (source, sent, initial)]
    context = []
    for key in projections[0]:
        context.append({"id": key, **dict(zip(("source", "sent", "received"), (x[key] for x in projections))),
                        "observed": {s: True for s in metrics.STAGES},
                        "present": {s: key != "records" or "records" in obj
                                    for s, obj in zip(metrics.STAGES, (source, sent, initial))}})
    fidelity = {"original_task_binding": final["task"]["task_id"] == case["task"]["task_id"] and final["task"]["target"] == case["task"]["target"],
                "required_tool_binding": final["tool_binding"] == base.REQUIRED_TOOL,
                "required_records_available": "records" in final,
                "task_constraints_preserved": diagnostic.same_json(final["task"]["constraints"], source["task"]["constraints"]),
                "runtime_policy_preserved": diagnostic.same_json(final["runtime_policy"], base.RUNTIME_POLICY),
                "episode_budget_preserved": final["episode_budget"] == budget}
    episode_id = case["case_id"] + "--" + profile
    episode = {"schema_version": metrics.EPISODE_SCHEMA_VERSION, "episode_id": episode_id,
               "family_id": case["family_id"], "route_id": "constructed_python_v2/" + profile,
               "evidence_kind": "fresh_constructed", "task_completion": result["task_completion"],
               "context_items": context,
               "capability_items": [{"id": base.REQUIRED_TOOL, "required": True,
                                     "reference_usable": ref_probe["result"]["status"] == "pass",
                                     "observed_usable": rec_probe["result"]["status"] == "pass",
                                     "advertised": final["tool_binding"] == base.REQUIRED_TOOL}],
               "fidelity_checks": [{"id": k, "status": "pass" if v else "fail"} for k, v in fidelity.items()],
               "recovery": recovery,
               "costs": {"wall_ms": elapsed, "messages": len(transfers), "tool_calls": len(state["reads"]),
                         "request_bytes": sum(len(base.canonical(t["payload"])) for t in transfers if t["direction"] == "request"),
                         "response_bytes": sum(len(base.canonical(t["payload"])) for t in transfers if t["direction"] == "response"), "model_tokens": 0},
               "source_files": source_files, "notes": [NOTICE, "Probe and counterfactual costs are excluded and separately retained.",
                    "Timing covers local fixture read, payload construction, receiver evaluation and recovery, including grading; it excludes probes, repair lattice and file writing. Do not compare this boundary with v1 timings."],
               "metadata": {"case_id": case["case_id"], "profile": profile, "pair_id": case["case_id"],
                            "family_id": case["family_id"], "receiver_attempts": attempts,
                            "generation": case["generation"], "raw_trace": "cells/" + episode_id + "/trace.json"}}
    trace = {"schema_version": "loss_diagnostic_trace_v2", "episode_id": episode_id,
             "source": source, "sent": sent, "received_initial": initial, "received_final": final,
             "receiver_initial": first, "receiver_final": result, "state": state,
             "transfers": [{**t, **base.identity(base.canonical(t["payload"]))} for t in transfers],
             "capability_probes": [ref_probe, rec_probe], "costs": episode["costs"]}
    began_repairs = time.perf_counter_ns()
    repairs = diagnostic.diagnose_repairs(source, initial, lambda wire: evaluate(case, wire))
    detail = {"schema_version": "loss_diagnostic_detail_v2", "episode_id": episode_id,
              "boundaries": {"extraction": diagnostic.boundary_diff(source, sent, True),
                             "conversion": diagnostic.boundary_diff(sent, initial, True),
                             "end_to_end": diagnostic.boundary_diff(source, initial, True),
                             "raw_conversion": diagnostic.boundary_diff(sent, initial, False)},
              "repair_certificate": repairs,
              "repair_diagnostic_cost": {"wall_ms": (time.perf_counter_ns() - began_repairs) / 1e6,
                                         "receiver_evaluations": repairs["trial_count"]}}
    return episode, trace, detail


def run(output: Path, variants: int = 16, seed: int = 20261113) -> dict:
    bank = generated_bank(variants, seed)
    source_paths = [Path(__file__), Path(base.__file__), Path(metrics.__file__), Path(diagnostic.__file__), base.CASES_PATH]
    sources = [{"path": p.resolve().relative_to(ROOT).as_posix(), **base.identity(p.read_bytes())} for p in source_paths]
    # v1 episode source contract accepts path/hash only.
    episode_sources = [{"path": x["path"], "sha256": x["sha256"]} for x in sources]
    output.mkdir(parents=True, exist_ok=False)
    for index, source in enumerate(source_paths):
        dest = output / "sources" / (f"{index:02d}-" + source.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as handle:
            handle.write(source.read_bytes())
    cells = [(case, profile) for case in bank["cases"] for profile in PROFILES]
    random.Random(seed).shuffle(cells)
    base.write_new(output / "input-bank.json", bank)
    base.write_new(output / "allocation.json", {"schema_version": "loss_diagnostic_allocation_v2",
                   "started_utc": datetime.now(timezone.utc).isoformat(), "profiles": list(PROFILES),
                   "seed": seed, "source_files": sources,
                   "cells": [{"case_id": c["case_id"], "profile": p} for c, p in cells]})
    episodes, details = [], []
    for case, profile in cells:
        episode, trace, detail = run_cell(case, profile, bank["episode_budget"], episode_sources)
        metrics.validate_episode(episode)
        directory = output / "cells" / episode["episode_id"]
        base.write_new(directory / "trace.json", trace)
        base.write_new(directory / "episode.json", episode)
        base.write_new(directory / "diagnosis.json", detail)
        episodes.append(episode)
        details.append(detail)
    base.write_new(output / "episodes.json", episodes)
    base.write_new(output / "metrics-summary.json", metrics.summarize_episodes(episodes))
    ref = [{"pair_id": e["metadata"]["pair_id"], "task_completion": e["task_completion"]} for e in episodes if e["metadata"]["profile"] == "reference"]
    by_profile = {}
    detail_index = {d["episode_id"]: d for d in details}
    for profile in PROFILES:
        group = [e for e in episodes if e["metadata"]["profile"] == profile]
        ds = [detail_index[e["episode_id"]] for e in group]
        histogram = {}
        for d in ds:
            key = str(d["repair_certificate"]["minimum_repair_group_count"])
            histogram[key] = histogram.get(key, 0) + 1
        by_profile[profile] = {"attempts": len(group), "task_pass": sum(e["task_completion"] == "pass" for e in group),
                              "scores": metrics.summarize_episodes(group)["scores"],
                              "paired_reference": diagnostic.paired_outcomes(ref, [{"pair_id": e["metadata"]["pair_id"], "task_completion": e["task_completion"]} for e in group]),
                              "minimum_repair_groups_histogram": histogram,
                              "boundary_leaf_totals": {stage: {key: sum(d["boundaries"][stage][key] for d in ds)
                                  for key in ("eligible_leaves", "kept", "changed", "missing", "added")}
                                  for stage in ("extraction", "conversion", "end_to_end", "raw_conversion")}}
    result = {"schema_version": "loss_diagnostic_result_v2", "status": "complete", "notice": NOTICE,
              "case_instances": bank["case_count"], "template_families": bank["family_count"],
              "variants_per_family": variants, "episodes": len(episodes), "held_out_cases": 0,
              "repair_certificates": len(details),
              "repair_interventions": sum(d["repair_certificate"]["trial_count"] for d in details),
              "by_profile": by_profile, "model_calls": 0,
              "python": platform.python_version(), "platform": platform.platform(),
              "completed_utc": datetime.now(timezone.utc).isoformat(),
              "limitations": ["Variants are transformations of ten known task templates, not independent task families or a hidden test set.",
                  "Repairs are authorized source-field replacements in a four-group finite universe; their cost is separate from episode overhead.",
                  "The recovery profile changes receiver policy; repair trials are diagnostics, not observed agent recoveries.",
                  "JSON leaf retention and task-specific normalized retention are separate from semantic or total information loss."]}
    base.write_new(output / "results.json", result)
    base.write_new(output / "manifest.json", {"files": [{"path": p.relative_to(output).as_posix(), **base.identity(p.read_bytes())}
                                               for p in sorted(output.rglob("*")) if p.is_file()]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20261113)
    args = parser.parse_args()
    result = run(args.output, args.variants, args.seed)
    print(json.dumps({"output": str(args.output), "episodes": result["episodes"],
                      "repair_interventions": result["repair_interventions"], "status": result["status"]}))


if __name__ == "__main__":
    main()
