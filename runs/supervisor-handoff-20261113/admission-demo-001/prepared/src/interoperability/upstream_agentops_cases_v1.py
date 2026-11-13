"""Export public upstream AgentOps cases with inputs and expectations separated.

This loader checks selected bytes against the retained source-ingestion record.
It does not import AgentOps, execute SQL, grade an application, or call a model.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat


COMMIT = "c806b7f1cd0042c9817c0a4c46d80a9a95a24293"
SOURCE_TREE = "external/agentops-c806b7f1"
EVAL_DIRECTORY = "agents/python/evals"
SETS = {
    "ops.evalset.json": "agentops_agent_core",
    "triage-report.evalset.json": "agentops_agent_structured_report",
    "workflow.evalset.json": "agentops_incident_workflow",
}
FILES = tuple(f"{EVAL_DIRECTORY}/{name}" for name in SETS) + (
    "agents/LICENSE", "agents/data/incidents.db", "agents/data/sql/schema.sql", "agents/data/sql/seed.sql")
PROVENANCE = {
    "kind": "public-source-derived-development", "commit_label": COMMIT,
    "held_out": False, "independent_human_review": False,
    "independent_git_object_authentication": False,
    "overlap": "Cases reuse incidents, tools and decision structures across all three upstream sets; case count is not an independent-template count.",
}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-JSON numeric constant: " + value)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _json(raw):
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_reject_constant)
    _encoded(value)  # Also reject overflowed JSON numbers such as 1e999.
    return value


def _record(raw, path):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _read(root: Path, relative: str):
    name = PurePosixPath(relative)
    _need(not name.is_absolute() and ".." not in name.parts and "\\" not in relative,
          "Invalid relative source path")
    path = root.joinpath(*name.parts)
    for component in (root, *reversed(path.parents[:len(name.parts) - 1]), path):
        info = component.lstat()
        _need(not stat.S_ISLNK(info.st_mode)
              and not (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)),
              "Source paths must not use links or reparse points: " + relative)
    _need(path.is_file(), "Expected a regular source file: " + relative)
    _need(path.stat().st_size <= 16 * 1024 * 1024, "Selected source exceeds the loader size limit: " + relative)
    return path.read_bytes()


def _keys(value, required, optional=()):
    _need(type(value) is dict and set(required) <= set(value) <= set(required) | set(optional),
          "Malformed or unexpected source fields; expected " + ", ".join(required))


def _text(value, label):
    _need(type(value) is str and bool(value.strip()), label + " must be nonempty text")


def _timestamp(value):
    _need((type(value) is int or (type(value) is float and math.isfinite(value))) and value >= 0,
          "Creation timestamp must be a finite nonnegative number")


def _content(value, role):
    _keys(value, ("role", "parts"))
    _need(value["role"] == role, "Unexpected content role")
    _need(type(value["parts"]) is list and bool(value["parts"]), "Content must contain text parts")
    for part in value["parts"]:
        _keys(part, ("text",))
        _text(part["text"], "Content part")


def _split_sets(raw_sources):
    application, expectations, metadata = [], [], []
    case_ids = set()
    for filename, expected_id in SETS.items():
        relative = f"{EVAL_DIRECTORY}/{filename}"
        document = _json(raw_sources[relative])
        _keys(document, ("eval_set_id", "name", "description", "eval_cases"), ("creation_timestamp",))
        _need(document["eval_set_id"] == expected_id, "Unexpected eval-set identity: " + filename)
        for field in ("name", "description"):
            _text(document[field], field)
        if "creation_timestamp" in document:
            _timestamp(document["creation_timestamp"])
        _need(type(document["eval_cases"]) is list and bool(document["eval_cases"]), "Eval set must have cases")
        metadata.append({"source": relative, **{k: v for k, v in document.items() if k != "eval_cases"}})
        for case in document["eval_cases"]:
            _keys(case, ("eval_id", "conversation", "session_input", "creation_timestamp"))
            case_id = case["eval_id"]
            _text(case_id, "Case id")
            _need(case_id not in case_ids, "Duplicate case id across selected sources: " + case_id)
            case_ids.add(case_id)
            _timestamp(case["creation_timestamp"])
            session = case["session_input"]
            _keys(session, ("app_name", "user_id", "state"))
            _text(session["app_name"], "Session app name")
            _text(session["user_id"], "Session user id")
            _need(type(session["state"]) is dict, "Session state must be an object")
            _need(type(case["conversation"]) is list and bool(case["conversation"]), "Case must have turns")
            public_turns, expected_turns, invocation_ids = [], [], set()
            for turn in case["conversation"]:
                _keys(turn, ("invocation_id", "user_content", "final_response", "intermediate_data", "creation_timestamp"))
                _text(turn["invocation_id"], "Invocation id")
                _need(turn["invocation_id"] not in invocation_ids, "Duplicate invocation id in case: " + case_id)
                invocation_ids.add(turn["invocation_id"])
                _timestamp(turn["creation_timestamp"])
                _content(turn["user_content"], "user")
                _content(turn["final_response"], "model")
                intermediate = turn["intermediate_data"]
                _keys(intermediate, ("tool_uses", "intermediate_responses"))
                _need(type(intermediate["tool_uses"]) is list and type(intermediate["intermediate_responses"]) is list,
                      "Expected trajectory and responses must be lists")
                for use in intermediate["tool_uses"]:
                    _keys(use, ("name", "args"))
                    _text(use["name"], "Expected tool name")
                    _need(type(use["args"]) is dict, "Expected tool arguments must be an object")
                public_turns.append({key: turn[key] for key in ("invocation_id", "user_content", "creation_timestamp")})
                expected_turns.append({key: turn[key] for key in ("invocation_id", "final_response", "intermediate_data", "creation_timestamp")})
            identity = {"eval_set_id": expected_id, "eval_id": case_id, "creation_timestamp": case["creation_timestamp"]}
            application.append({**identity, "session_input": session, "conversation": public_turns})
            expectations.append({**identity, "conversation": expected_turns})
    return (
        {"schema_version": "upstream-agentops-application-cases/1", "provenance": PROVENANCE, "cases": application},
        {"schema_version": "upstream-agentops-evaluator-expectations/1", "provenance": PROVENANCE, "cases": expectations},
        metadata,
    )


def _ingestion(raw):
    document = _json(raw)
    _need(type(document) is dict and document.get("schema_version") == "user-source-archive-ingestion/1"
          and document.get("status") == "passed" and document.get("source_tree") == SOURCE_TREE
          and document.get("archive_root_and_comment_commit") == COMMIT
          and document.get("all_regular_payload_bytes_match_archive") is True
          and document.get("all_archive_file_entries_accounted_for") is True
          and document.get("archive_changed") is False,
          "Ingestion record does not establish the selected source-archive identity")
    _need(type(document.get("records")) is list, "Ingestion records must be a list")
    selected = {}
    for item in document["records"]:
        _need(type(item) is dict and type(item.get("source_relative_path")) is str,
              "Malformed ingestion source record")
        relative = item["source_relative_path"]
        if relative not in FILES:
            continue  # The retained archive contains many other original files.
        _need(relative not in selected, "Duplicate selected ingestion record: " + relative)
        expected = item.get("extracted")
        _need(item.get("kind") == "regular_file" and type(expected) is dict
              and expected.get("path") == f"{SOURCE_TREE}/{relative}"
              and type(expected.get("bytes")) is int and expected["bytes"] >= 0
              and type(expected.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]) is not None,
              "Malformed selected ingestion digest: " + relative)
        selected[relative] = expected
    _need(set(selected) == set(FILES), "Ingestion record omits a selected source file")
    return selected


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def export_cases(source_root: Path, capture_root: Path, output: Path) -> dict:
    """Create a new source-bound data export; retain a failure receipt on error."""
    source_root, capture_root, output = (Path(path).absolute() for path in (source_root, capture_root, output))
    _need(not output.exists() and not output.is_symlink(), "Refusing to overwrite an existing export")
    for root in (source_root, capture_root):
        _need(not output.resolve().is_relative_to(root.resolve()), "Output must be outside source and capture trees")
    output.mkdir(parents=True, exist_ok=False)
    plan = {"schema_version": "upstream-agentops-export-plan/1", "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_root": str(source_root), "capture_root": str(capture_root), "selected_sources": list(FILES),
            "provenance": PROVENANCE, "exporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    _write(output / "plan.json", _encoded(plan))
    receipt = {"schema_version": "upstream-agentops-export/1", "status": "failed", "source_checks": [],
               "provenance": PROVENANCE, "source_inputs_unchanged": None, "captured_outputs_unchanged": None, "application_requests": 0,
               "model_calls": 0, "application_imports": 0, "graded_task_outcomes": 0}
    observed = []
    projected = {}
    try:
        ingestion_raw = _read(capture_root, "ingestion.json")
        observed.append((capture_root, "ingestion.json", _record(ingestion_raw, "capture/ingestion.json")))
        _write(output / "capture/ingestion.json", ingestion_raw)
        expected = _ingestion(ingestion_raw)
        actual_sets = {path.name for path in (source_root / EVAL_DIRECTORY).glob("*.evalset.json")}
        _need(actual_sets == set(SETS), "Missing or extra eval-set source files require a new loader version")
        raw_sources = {}
        for relative in FILES:
            raw = _read(source_root, relative)
            actual = _record(raw, f"source/{relative}")
            observed.append((source_root, relative, actual))
            match = actual["sha256"] == expected[relative]["sha256"] and actual["bytes"] == expected[relative]["bytes"]
            receipt["source_checks"].append({"source": relative, "expected": expected[relative], "actual": actual, "matched": match})
            _need(match, "Source hash or size drift: " + relative)
            raw_sources[relative] = raw
            _write(output / "source" / relative, raw)
        application, expectations, metadata = _split_sets(raw_sources)
        projected = {"application/cases.json": _encoded(application),
                     "evaluator/expectations.json": _encoded(expectations), "source-sets.json": _encoded(metadata)}
        for relative, raw in projected.items():
            _write(output / relative, raw)
        receipt.update(status="passed", case_count=len(application["cases"]),
            turn_count=sum(len(case["conversation"]) for case in application["cases"]),
            cases_by_source={item["eval_set_id"]: sum(case["eval_set_id"] == item["eval_set_id"] for case in application["cases"]) for item in metadata},
            application_inputs="application/cases.json", evaluator_expectations="evaluator/expectations.json",
            interpretation="Public upstream expected responses and tool trajectories; not hidden gold, observed application results, admission certificates or independently reviewed held-out tasks.")
    except (OSError, ValueError, KeyError, TypeError) as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            after = [_record(_read(root, relative), before["path"]) for root, relative, before in observed]
            unchanged = bool(observed) and after == [before for _, _, before in observed]
            receipt["observed_source_inputs_unchanged"] = unchanged
            receipt["source_inputs_unchanged"] = unchanged if len(observed) == len(FILES) + 1 else None
            receipt["source_inputs_after"] = after
            if receipt["status"] == "passed":
                _need(len(observed) == len(FILES) + 1 and receipt["source_inputs_unchanged"], "Source changed during export")
                _need({path.name for path in (source_root / EVAL_DIRECTORY).glob("*.evalset.json")} == set(SETS),
                      "Eval-set membership changed during export")
                captured_matches = all(_record((output / before["path"]).read_bytes(), before["path"]) == before
                                       for _, _, before in observed)
                projected_matches = all((output / relative).read_bytes() == raw for relative, raw in projected.items())
                plan_matches = (output / "plan.json").read_bytes() == _encoded(plan)
                receipt["captured_outputs_unchanged"] = captured_matches and projected_matches and plan_matches
                _need(captured_matches, "Captured source bytes changed during export")
                _need(projected_matches, "Projected inputs or expectations changed during export")
                _need(plan_matches, "Export plan changed during export")
        except (OSError, ValueError, KeyError, TypeError) as error:
            receipt.update(status="failed", error=f"Final preservation check: {type(error).__name__}: {error}")
        receipt["files"] = [_record(path.read_bytes(), path.relative_to(output).as_posix())
                            for path in sorted(output.rglob("*")) if path.is_file()]
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write(output / "result.json", _encoded(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True, help="Directory containing the retained ingestion.json")
    parser.add_argument("--output", type=Path, required=True, help="Unused output directory")
    args = parser.parse_args(argv)
    try:
        report = export_cases(args.source_root, args.capture_root, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"status": report["status"], "cases": report.get("case_count"), "turns": report.get("turn_count"),
                      "error": report.get("error"), "receipt": str(args.output / "result.json")}, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
