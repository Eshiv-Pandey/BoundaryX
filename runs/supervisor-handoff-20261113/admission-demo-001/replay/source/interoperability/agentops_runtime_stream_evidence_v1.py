"""Validate persisted passive journals without importing an SDK or application.

Recorded sequence numbers establish observer publication order only. Caller
bindings, closed-process attribution, public/raw equality, successful effects
and benchmark grades belong to separate checks. No directory is modified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import stat


SCHEMA = "agentops-runtime-stream/1"
LIMITS = {"max_invocations": 64, "max_events_per_invocation": 4096,
          "max_json_bytes": 4 * 1024 * 1024, "max_total_bytes": 64 * 1024 * 1024,
          "max_files": 8192}
KNOWN = {"user_id", "session_id", "invocation_id", "new_message", "state_delta", "run_config", "yield_user_message"}
SUMMARY = ("invocation_sequence", "directory", "status", "capture_complete", "capture_disabled",
           "durable_receipt_written", "original_termination", "original_aclose_completed", "events_seen",
           "events_recorded", "event_identity_fields_complete", "observed_invocation_ids",
           "supplied_invocation_id_present", "supplied_invocation_id", "supplied_invocation_id_matches_all_observed")


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _regular(path, directory=False):
    path = Path(path).absolute()
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
              "linked/reparse journal path is unsupported")
    _need(path.is_dir() if directory else path.is_file(), "nonregular journal path")
    return path


def _identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _same(left, right):
    """Exact JSON tree equality, preserving boolean and numeric types."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same(value, right[key]) for key, value in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _relative(value):
    _need(type(value) is str and value and "\\" not in value and ":" not in value, "invalid journal relative path")
    parsed = PurePosixPath(value)
    _need(not parsed.is_absolute() and ".." not in parsed.parts and parsed.as_posix() == value, "noncanonical journal relative path")
    return value


def _strict(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _need(key not in value, "duplicate journal JSON key")
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError("nonfinite journal JSON")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    json.dumps(value, allow_nan=False)  # Reject exponents which overflow to infinity.
    return value


def _object(raw):
    value = _strict(raw)
    _need(type(value) is dict, "journal JSON must be an object")
    return value


def _inventory(directory):
    _regular(directory, True)
    files, directories, size = {}, set(), 0
    for path in sorted(directory.rglob("*")):
        _regular(path, path.is_dir())
        name = _relative(path.relative_to(directory).as_posix())
        if path.is_dir():
            directories.add(name)
        else:
            _need(len(files) < LIMITS["max_files"] + 1 and path.stat().st_size <= LIMITS["max_json_bytes"], "journal inventory bound exceeded")
            raw = path.read_bytes()
            _need(len(raw) <= LIMITS["max_json_bytes"], "journal file grew beyond bound")
            size += len(raw)
            _need(size <= LIMITS["max_total_bytes"] + LIMITS["max_json_bytes"], "journal aggregate bound exceeded")
            files[name] = raw
    return files, directories


def _count(value, minimum=0, maximum=None):
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def read_closed_journal(directory, *, expected_receipt_identity=None, expected_observer_identity=None,
                        expected_call_inputs=None):
    """Require a complete stable persisted journal and optional external binding.

    expected_call_inputs is an ordered list of supplied input subsets. For
    new_message/run_config it compares decoded serialized objects, retaining
    distinction between omitted fields and supplied null. The API's name means
    terminal recorder closure; it cannot prove that an external process exited.
    Invalid or incomplete evidence raises; nothing is repaired or rewritten.
    """
    directory = Path(directory).absolute()
    files, directories = _inventory(directory)
    _need("result.json" in files, "missing persisted journal root receipt")
    identity = _identity(files["result.json"])
    _need(expected_receipt_identity is None or _same(identity, expected_receipt_identity), "journal root receipt binding differs")
    root = _object(files["result.json"])
    _need(root.get("schema_version") == SCHEMA and root.get("status") == "recorded", "journal root is not recorded")
    for key in ("durable_receipt_written", "capture_complete", "captured_inputs_unchanged", "eligible_for_ordered_evidence_checks"):
        _need(root.get(key) is True, "journal root completeness flag is absent or false")
    _need(root.get("capture_disabled") is False and root.get("errors") == []
          and _count(root.get("active_calls")) and root["active_calls"] == 0
          and _count(root.get("unallocated_calls")) and root["unallocated_calls"] == 0, "journal root has active/disabled/unallocated calls")
    declared = root.get("files")
    _need(type(declared) is dict and "result.json" not in declared, "invalid journal root manifest")
    for name, item in declared.items():
        _relative(name)
        _need(name in files and _same(item, _identity(files[name])), "journal manifest identity differs")
    _need(set(files) == set(declared) | {"result.json"}, "journal terminal membership differs")
    _need({p.as_posix() for name in files for p in PurePosixPath(name).parents if p.as_posix() != "."} == directories,
          "journal contains unexpected empty directories")
    _need("plan.json" in files and "source/agentops_runtime_stream_v1.py" in files, "missing observer plan/source")
    plan = _object(files["plan.json"])
    _need(plan.get("schema_version") == SCHEMA and plan.get("known_input_fields") == sorted(KNOWN)
          and plan.get("original_call_installed_by_observer") is False and plan.get("sdk_imported_by_observer") is False
          and plan.get("serializer_outputs_are_exact_captured_json_bytes") is True, "unsupported journal plan")
    source_identity = _identity(files["source/agentops_runtime_stream_v1.py"])
    _need(_same(plan.get("observer_source"), source_identity)
          and (expected_observer_identity is None or _same(source_identity, expected_observer_identity)), "observer source binding differs")
    bounds = plan.get("limits")
    _need(type(bounds) is dict and set(bounds) == set(LIMITS)
          and all(_count(bounds[key], 1, LIMITS[key]) for key in LIMITS)
          and bounds["max_total_bytes"] >= 4 * bounds["max_json_bytes"], "unsupported journal limits")
    _need(len(declared) <= bounds["max_files"] and all(len(raw) <= bounds["max_json_bytes"] for raw in files.values())
          and sum(len(files[name]) for name in declared) <= bounds["max_total_bytes"], "journal exceeds declared capture bounds")
    summaries = root.get("invocations")
    _need(type(summaries) is list and _count(root.get("calls_seen"), 1, bounds["max_invocations"])
          and len(summaries) == root["calls_seen"], "journal call count differs")
    _need(expected_call_inputs is None or type(expected_call_inputs) is list and len(expected_call_inputs) == len(summaries),
          "expected input binding count differs")
    membership = {"result.json", "plan.json", "source/agentops_runtime_stream_v1.py"}
    calls, all_records = [], []
    for index, summary in enumerate(summaries, 1):
        name = f"invocations/{index:06d}"
        _need(type(summary) is dict and type(summary.get("invocation_sequence")) is int
              and summary["invocation_sequence"] == index and summary.get("directory") == name,
              "journal invocation sequence/directory differs")
        receipt_name, input_name = name + "/result.json", name + "/input.json"
        _need(receipt_name in files and input_name in files, "missing persisted invocation receipt/input")
        membership.update((receipt_name, input_name))
        receipt, inputs = _object(files[receipt_name]), _object(files[input_name])
        _need(_same(summary, {key: receipt.get(key) for key in SUMMARY}), "root/call summary differs")
        _need(receipt.get("schema_version") == SCHEMA and inputs.get("schema_version") == SCHEMA
              and type(inputs.get("invocation_sequence")) is int and inputs["invocation_sequence"] == index,
              "call/input schema or sequence differs")
        for key in ("capture_complete", "durable_receipt_written", "inputs_complete", "directory_created_exclusively",
                    "original_aclose_attempted", "original_aclose_completed", "event_identity_fields_complete"):
            _need(receipt.get(key) is True, "invocation completeness flag is absent or false")
        _need(receipt.get("status") == "recorded" and receipt.get("capture_disabled") is False
              and receipt.get("capture_errors") == [] and receipt.get("original_termination") == "normal_exhaustion"
              and type(receipt.get("original_call_attempts")) is int and receipt["original_call_attempts"] == 1
              and receipt.get("original_error_type") is None and receipt.get("cleanup_error_type") is None,
              "invocation original execution/cleanup is incomplete")
        supplied = inputs.get("supplied_known_fields")
        _need(type(supplied) is list and all(type(key) is str for key in supplied)
              and supplied == sorted(set(supplied)) and set(supplied) <= KNOWN
              and inputs.get("omitted_known_fields") == sorted(KNOWN - set(supplied))
              and inputs.get("unsupported_capture") is False and inputs.get("objects_or_argument_values_rewritten") is False
              and type(inputs.get("positional_argument_count")) is int and inputs["positional_argument_count"] == 0
              and type(inputs.get("unsupported_keyword_field_count")) is int and inputs["unsupported_keyword_field_count"] == 0,
              "unsupported invocation input capture")
        _need(set(inputs) == {"schema_version", "invocation_sequence", "supplied_known_fields", "omitted_known_fields",
                              "positional_argument_count", "unsupported_keyword_field_count", "unsupported_capture",
                              "objects_or_argument_values_rewritten"} | set(supplied), "supplied input membership differs")
        decoded = {key: inputs[key] for key in supplied}
        for key in supplied:
            value = inputs[key]
            if key in {"new_message", "run_config"} and value is not None:
                target = name + "/input/" + key + ".json"
                _need(type(value) is dict and set(value) == {"path", "bytes", "sha256"} and value["path"] == target
                      and target in files and _same({k: value[k] for k in ("bytes", "sha256")}, _identity(files[target])),
                      "serialized invocation input binding differs")
                membership.add(target)
                decoded[key] = _object(files[target])
            elif key in {"user_id", "session_id"}:
                _need(type(value) is str, "invalid user/session input identity")
            elif key == "invocation_id":
                _need(value is None or type(value) is str, "invalid supplied invocation identity")
            elif key == "yield_user_message":
                _need(type(value) is bool, "invalid supplied yield boolean")
            elif key == "state_delta":
                _need(value is None or type(value) is dict, "invalid supplied state delta")
        if expected_call_inputs is not None:
            expected = expected_call_inputs[index - 1]
            _need(type(expected) is dict and set(expected) <= KNOWN
                  and all(key in decoded and _same(decoded[key], value)
                          for key, value in expected.items()), "invocation input/context binding differs")
        _need(receipt.get("supplied_invocation_id_present") is ("invocation_id" in supplied)
              and receipt.get("supplied_invocation_id") == inputs.get("invocation_id"), "supplied invocation receipt/input differs")
        records = receipt.get("events")
        _need(type(records) is list and _count(receipt.get("events_seen"), 1, bounds["max_events_per_invocation"])
              and len(records) == receipt["events_seen"] and type(receipt.get("events_recorded")) is int
              and receipt["events_recorded"] == len(records) and type(receipt.get("downstream_yields_entered")) is int
              and receipt["downstream_yields_entered"] == len(records), "invocation event counts differ")
        observed_ids, events, previous_global = [], [], 0
        for ordinal, record in enumerate(records, 1):
            event_name = name + f"/events/{ordinal:06d}.json"
            _need(type(record) is dict and type(record.get("event_ordinal")) is int and record["event_ordinal"] == ordinal
                  and type(record.get("batch_ordinal")) is int and record["batch_ordinal"] == ordinal
                  and record.get("path") == event_name and event_name in files
                  and _same({k: record.get(k) for k in ("bytes", "sha256")}, _identity(files[event_name]))
                  and record.get("captured_before_downstream_yield") is True
                  and _count(record.get("global_yield_sequence"), previous_global + 1), "event publication order/identity differs")
            previous_global = record["global_yield_sequence"]
            membership.add(event_name)
            event = _object(files[event_name])
            for key, label in (("id", "actual_event_id"), ("invocation_id", "actual_invocation_id")):
                _need(type(event.get(key)) is str and event[key] and record.get(label) == event[key], "actual event identity differs")
            parts = event.get("content", {}).get("parts") if type(event.get("content")) is dict else None
            part_count = len(parts) if type(parts) is list else None
            _need(type(record.get("part_count_in_original_yield")) is type(part_count)
                  and record.get("part_count_in_original_yield") == part_count, "event batch part count differs")
            if event["invocation_id"] not in observed_ids:
                observed_ids.append(event["invocation_id"])
            events.append(event)
            all_records.append({**record, "invocation_sequence": index, "event": event})
        _need(receipt.get("observed_invocation_ids") == observed_ids, "observed invocation identity set/order differs")
        supplied_id = inputs.get("invocation_id")
        expected_match = all(item == supplied_id for item in observed_ids) if "invocation_id" in supplied and supplied_id is not None else None
        _need(receipt.get("supplied_invocation_id_matches_all_observed") is expected_match and expected_match is not False,
              "supplied invocation identity does not match emitted events")
        calls.append({"invocation_sequence": index, "inputs": decoded, "input_record": inputs, "events": events,
                      "event_records": records, "receipt_identity": _identity(files[receipt_name]), "receipt": receipt})
    _need(membership == set(files), "journal contains undeclared semantic members")
    _need(_count(root.get("global_yields_seen"), 1) and len(all_records) == root["global_yields_seen"], "root event count differs")
    ordered = sorted(all_records, key=lambda item: item["global_yield_sequence"])
    _need([item["global_yield_sequence"] for item in ordered] == list(range(1, len(ordered) + 1)), "global publication sequence is missing or duplicated")
    after_files, after_directories = _inventory(directory)
    _need(files == after_files and directories == after_directories, "journal changed during validation")
    return {"schema_version": "agentops-runtime-stream-evidence/1", "status": "validated", "receipt_identity": identity,
            "observer_identity": source_identity, "files": {name: _identity(raw) for name, raw in files.items()},
            "calls": calls, "ordered_events": [item["event"] for item in ordered], "ordered_event_records": ordered,
            "recorded_publication_order_validated": True, "input_context_binding_checked": expected_call_inputs is not None,
            "source_closed_proven": False, "source_authentication_proven": False, "causal_tool_execution_order_proven": False,
            "public_raw_binding_checked": False, "benchmark_grade_proven": False, "native_qualification_established": False}
