"""Read-only artifact verification and independent finite trace regrading.

No application, bridge, or model is executed. Tests are optional and recorded
outside the immutable input allocation. This is a software/evidence audit,
not independent human task validation or external capture authentication.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from interoperability.loss_benchmark_v1 import load_episodes, summarize_episodes


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          VerificationError("nonfinite JSON number: " + value)))


def local_member(base, name):
    relative = PurePosixPath(name)
    require(isinstance(name, str) and not relative.is_absolute() and
            ".." not in relative.parts and "\\" not in name and ":" not in name,
            "unsafe artifact path")
    path = (base / Path(*relative.parts)).resolve()
    require(path.is_relative_to(base.resolve()), "artifact escapes allocation")
    return path


def project(message):
    """The recorded fixture declares record order irrelevant, not values/types."""
    return {"task_id": message["task"]["task_id"],
            "target": message["task"]["target"],
            "task_kind": message["task"]["kind"],
            "task_constraints": message["task"]["constraints"],
            "records": sorted(message["records"], key=canonical) if "records" in message else None,
            "tool_binding": message["tool_binding"],
            "runtime_policy": message["runtime_policy"],
            "episode_budget": message["episode_budget"]}


def verify_fresh_cell(episode, trace, case):
    require(trace["episode_id"] == episode["episode_id"], "trace episode mismatch")
    events = trace["events"]
    require([row["sequence"] for row in events] == list(range(len(events))),
            "noncontiguous event sequence")
    for row in events:
        raw = canonical(row["payload"])
        require(row["bytes"] == len(raw) and row["sha256"] == hashlib.sha256(raw).hexdigest(),
                "event payload identity mismatch")
    by_boundary = {}
    for row in events:
        require(row["boundary"] not in by_boundary, "duplicate event boundary")
        by_boundary[row["boundary"]] = row["payload"]
    source = by_boundary["pre_sender_source_truth"]
    sent = by_boundary["sender_to_converter"]
    received = by_boundary["converter_to_receiver"]
    final_state = by_boundary["final_fixture_state"]
    final = trace["receiver_final"]
    gold = case["gold"]
    checks = {
        "final_answer": final["status"] == "completed" and
                        canonical(final["answer"]) == canonical(gold["expected_answer"]),
        "correct_task": final["task_id"] == gold["expected_task_id"],
        "correct_target": final["target"] == gold["expected_target"] and
                          all(row["target"] == gold["expected_target"] for row in final_state["reads"]),
        "forbidden_effects_absent": not any(effect in gold["forbidden_effects"]
                                            for effect in final_state["effects"]),
        "state_content_unchanged": final_state["content_unchanged"] is True,
        "runtime_policy_equal": canonical(final_state["runtime_policy"]) == canonical(source["runtime_policy"]),
    }
    outcome = "pass" if all(checks.values()) else "fail"
    require(outcome == episode["task_completion"], "independent task regrade mismatch")
    require(canonical(checks) == canonical(trace["gold_assessment"]["checks"]),
            "recorded task checks disagree with regrade")
    require(canonical(source["task"]) == canonical(case["task"]) and
            canonical(source["records"]) == canonical(case["records"]),
            "pre-sender source differs from pinned case")
    projections = {"source": project(source), "sent": project(sent), "received": project(received)}
    require(len(episode["context_items"]) == len(projections["source"]), "missing context fact group")
    for item in episode["context_items"]:
        for stage, message in (("source", source), ("sent", sent), ("received", received)):
            known_present = item["id"] != "records" or "records" in message
            require(item["observed"][stage] is True and item["present"][stage] is known_present,
                    "context presence/capture mismatch")
            require(canonical(item[stage]) == canonical(projections[stage][item["id"]]),
                    "context value differs from initial boundary")
    probes = {probe["label"]: probe for probe in trace["diagnostic_capability_probes"]}
    require(set(probes) == {"reference_required_binding", "receiver_observed_binding"},
            "missing isolated capability probe")
    probe_receiver = by_boundary.get("recovered_observation_to_receiver", received)
    for label, message in (("reference_required_binding", source), ("receiver_observed_binding", probe_receiver)):
        probe = probes[label]
        request = {"task_id": message["task"]["task_id"], "tool_binding": message["tool_binding"]}
        require(canonical(probe["request"]) == canonical(request), "probe request mismatch")
        expected = request["task_id"] == case["task"]["task_id"] and request["tool_binding"] == "fixture.read_snapshot.v1"
        require(probe["result"]["status"] == ("pass" if expected else "fail"),
                "task-bound capability probe mismatch")
        for field in ("request", "result"):
            raw = canonical(probe[field])
            require(probe[field + "_identity"] == {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
                    "probe payload identity mismatch")
        if expected:
            require(canonical(probe["result"]["records"]) == canonical(case["records"]),
                    "probe returned wrong fixture records")
    capability = episode["capability_items"][0]
    require(capability["reference_usable"] is (probes["reference_required_binding"]["result"]["status"] == "pass") and
            capability["observed_usable"] is (probes["receiver_observed_binding"]["result"]["status"] == "pass"),
            "capability metric is not based on actual probes")
    transfers = trace["transfers"]
    for transfer in transfers:
        require(transfer["direction"] in ("request", "response") and
                transfer["bytes"] == events[transfer["sequence"]]["bytes"], "transfer mismatch")
    expected_costs = {"messages": len(transfers), "tool_calls": len(final_state["reads"]),
                      "request_bytes": sum(row["bytes"] for row in transfers if row["direction"] == "request"),
                      "response_bytes": sum(row["bytes"] for row in transfers if row["direction"] == "response"),
                      "model_tokens": 0}
    for name, value in expected_costs.items():
        require(episode["costs"][name] == value, "cost reanalysis mismatch: " + name)
    require(episode["costs"] == trace["costs"], "trace/episode costs differ")
    recovery = episode["metadata"]["profile"] == "recovery"
    require(episode["recovery"]["eligible"] is recovery, "recovery eligibility mismatch")
    if recovery:
        require("records" not in received and "receiver_attempt_2" in by_boundary,
                "recovery did not retain initial missing field/second attempt")
        require(episode["recovery"]["status"] == outcome, "recovery outcome mismatch")
    return checks


def verify_bundle(bundle, retained, root=ROOT):
    bundle, retained, root = Path(bundle).resolve(), Path(retained).resolve(), Path(root).resolve()
    manifest = read_json(bundle / "manifest.json")
    members = manifest["files"]
    names = [row["path"] for row in members]
    require(len(set(names)) == len(names), "duplicate manifest member")
    actual = {path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()}
    require(actual == set(names) | {"manifest.json"}, "manifest membership mismatch")
    for row in members:
        path = local_member(bundle, row["path"])
        require(path.stat().st_size == row["bytes"] and digest(path) == row["sha256"],
                "artifact integrity mismatch: " + row["path"])
    allocation = read_json(bundle / "allocation.json")
    current_roles = [root / "scripts/run_loss_benchmark_v1.py",
                     root / "src/interoperability/loss_benchmark_v1.py",
                     root / "benchmark/loss-v1/development-cases.json"]
    require(len(allocation["source_files"]) == len(current_roles), "unexpected source-role allocation")
    for index, source in enumerate(allocation["source_files"]):
        current = current_roles[index]
        recorded_name = source["path"].replace("\\", "/").rsplit("/", 1)[-1]
        require(recorded_name == current.name and digest(current) == source["sha256"],
                "current source role/identity mismatch")
        captured = bundle / "sources" / (f"{index:02d}-" + current.name)
        require(digest(captured) == source["sha256"], "captured source mismatch")
    fresh = load_episodes(bundle / "normalized-episodes.json")
    historical = load_episodes(retained)
    combined = load_episodes(bundle / "combined-episodes.json")
    require(canonical(combined) == canonical(historical + fresh), "combined retained prefix/fresh partition mismatch")
    require(len(fresh) == allocation["cell_count"], "allocated cell count mismatch")
    cases = {case["case_id"]: case for case in read_json(bundle / "input-cases.json")["cases"]}
    for row in fresh:
        require(row["evidence_kind"] == "fresh_constructed", "fresh evidence relabelled")
        trace = read_json(local_member(bundle, row["metadata"]["raw_trace"]))
        verify_fresh_cell(row, trace, cases[row["metadata"]["case_id"]])
        saved = read_json(bundle / "cells" / row["episode_id"] / "normalized-episode.json")
        require(canonical(saved) == canonical(row), "per-cell normalized mismatch")
    regenerated = summarize_episodes(combined)
    require(canonical(regenerated) == canonical(read_json(bundle / "metrics-summary.json")), "summary regeneration mismatch")
    require(regenerated["scores"] is None, "heterogeneous evidence was pooled")
    spec = importlib.util.spec_from_file_location("retained_recheck", root / "scripts/build_loss_benchmark_retained_v1.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    portable_root = root / "benchmark/loss-v1/retained-inputs"
    retained_root = portable_root if portable_root.is_dir() else root
    rebuilt = builder.build_episodes(retained_root, root / "benchmark/loss-v1/retained-manifest.json")
    require(canonical(rebuilt) == canonical(historical), "retained raw-data reanalysis mismatch")
    retained_manifest = read_json(root / "benchmark/loss-v1/retained-manifest.json")
    return {"status": "passed", "fresh_episodes_regraded": len(fresh),
            "retained_episodes_rebuilt": len(historical), "combined_episodes": len(combined),
            "manifest_files_verified": len(members), "pinned_retained_inputs": len(retained_manifest["source_files"]),
            "retained_episode_file_sha256": digest(retained), "bundle_manifest_sha256": digest(bundle / "manifest.json"),
            "retained_input_location": "portable_input_mirror" if retained_root == portable_root else "original_local_paths",
            "fresh_outcomes": dict(Counter(row["task_completion"] for row in fresh)),
            "checks": ["complete artifact manifest", "current and captured source hashes", "allocated cell accounting",
                       "independent finite task/identity/effect regrading", "initial boundary context reconstruction",
                       "actual isolated capability probes", "exact scoped communication costs", "retained input partition",
                       "metric-summary regeneration", "pinned raw inputs and retained episode reanalysis"],
            "limitations": ["No new application or model execution; retained reanalysis only.",
                            "Finite gold and tasks are author/AI-authored development material, not human-reviewed holdout.",
                            "Retained reconstruction invokes the retained adapter; this is not an independent reproduction of upstream software.",
                            "Hashes establish artifact consistency, not external capture authenticity or scientific novelty."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--retained", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        result = verify_bundle(args.bundle, args.retained)
        result["verified_utc"] = datetime.now(timezone.utc).isoformat()
        result["verifier_sha256"] = digest(__file__)
        tests = []
        if args.run_tests:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            for pattern in ("test_loss_benchmark_v1.py", "test_loss_benchmark_runner_v1.py", "test_loss_benchmark_retained_v1.py", "test_verify_loss_benchmark_v1.py", "test_capture_loss_benchmark_inputs_v1.py"):
                command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"]
                completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=90)
                stem = pattern.removesuffix(".py")
                (args.output / (stem + ".stdout.bin")).write_bytes(completed.stdout)
                (args.output / (stem + ".stderr.bin")).write_bytes(completed.stderr)
                log = completed.stderr.decode("utf-8", errors="replace")
                count = re.search(r"Ran (\d+) tests?", log)
                skipped = re.search(r"skipped=(\d+)", log)
                total = int(count.group(1)) if count else 0
                skip_count = int(skipped.group(1)) if skipped else 0
                tests.append({"pattern": pattern, "command": command, "exit_code": completed.returncode,
                              "executed_tests": total, "skipped_tests": skip_count,
                              "passed_tests": total - skip_count if completed.returncode == 0 else None})
                require(completed.returncode == 0, "test suite failed: " + pattern)
                require(total > 0, "test discovery ran no tests: " + pattern)
        result["test_suites"] = tests
        result["tests_passed"] = sum(item["passed_tests"] for item in tests) if tests else None
        result["tests_skipped"] = sum(item["skipped_tests"] for item in tests) if tests else None
    except Exception as error:
        result = {"status": "failed", "error": type(error).__name__ + ": " + str(error)}
    (args.output / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
