"""Pure source-case trajectory assessment over caller-supplied journal validation.

The caller must first use read_closed_journal on persisted terminal evidence.
This module checks the returned JSON shape, turn/prompt/context bindings and
the original configured calls-only metric. It does not re-read that filesystem
or authenticate observations. Reference answers never become passing oracles.
"""
from __future__ import annotations

import math
import re

from .agentops_required_trajectory_v1 import invocations_from_events, score_invocations


SCHEMA = "agentops-source-case-assessment/1"
FAMILIES = {"agentops_agent_core", "agentops_agent_structured_report", "agentops_incident_workflow"}
KNOWN_INPUTS = {"user_id", "session_id", "invocation_id", "new_message", "state_delta", "run_config", "yield_user_message"}
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _need(value, reason):
    if not value:
        raise ValueError(reason)


def _keys(value, required, optional=()):
    _need(type(value) is dict and set(required) <= set(value) <= set(required) | set(optional),
          "unsupported source/observation fields")


def _text(value):
    return type(value) is str and bool(value.strip())


def _number(value):
    return type(value) is int and value >= 0 or type(value) is float and math.isfinite(value) and value >= 0


def _finite(value, depth=0):
    _need(depth <= 48, "observation JSON nesting exceeds bound")
    if type(value) is dict:
        _need(all(type(key) is str for key in value), "nontext JSON member")
        for item in value.values():
            _finite(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _finite(item, depth + 1)
    else:
        _need(value is None or type(value) in (str, int, bool) or type(value) is float and math.isfinite(value),
              "nonfinite/non-JSON observation")


def _same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same(value, right[key]) for key, value in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _identity(value):
    return (type(value) is dict and set(value) == {"bytes", "sha256"}
            and type(value["bytes"]) is int and value["bytes"] > 0
            and type(value["sha256"]) is str and _HASH.fullmatch(value["sha256"]) is not None)


def _source_content(value, role):
    _keys(value, ("role", "parts"))
    _need(value["role"] == role and type(value["parts"]) is list and bool(value["parts"]),
          "unsupported source content role/parts")
    for part in value["parts"]:
        _keys(part, ("text",))
        _need(_text(part["text"]), "source part is not nonempty exact text")


def _source_pair(application, expectation):
    _keys(application, ("eval_set_id", "eval_id", "creation_timestamp", "session_input", "conversation"))
    _keys(expectation, ("eval_set_id", "eval_id", "creation_timestamp", "conversation"))
    for key in ("eval_set_id", "eval_id", "creation_timestamp"):
        _need(_same(application[key], expectation[key]), "application/evaluator source case identity differs")
    _need(type(application["eval_set_id"]) is str and application["eval_set_id"] in FAMILIES
          and _text(application["eval_id"]) and _number(application["creation_timestamp"]), "unsupported source case identity")
    session = application["session_input"]
    _keys(session, ("app_name", "user_id", "state"))
    _need(_text(session["app_name"]) and _text(session["user_id"]) and type(session["state"]) is dict
          and session["state"] == {}, "unsupported source initial session state")
    source, expected = application["conversation"], expectation["conversation"]
    _need(type(source) is list and 1 <= len(source) <= 32 and type(expected) is list and len(source) == len(expected),
          "source/evaluator turn count differs")
    labels = set()
    for turn, reference in zip(source, expected):
        _keys(turn, ("invocation_id", "user_content", "creation_timestamp"))
        _keys(reference, ("invocation_id", "final_response", "intermediate_data", "creation_timestamp"))
        _need(_text(turn["invocation_id"]) and turn["invocation_id"] not in labels
              and turn["invocation_id"] == reference["invocation_id"]
              and _same(turn["creation_timestamp"], reference["creation_timestamp"])
              and _number(turn["creation_timestamp"]), "source/evaluator ordered turn labels differ")
        labels.add(turn["invocation_id"])
        _source_content(turn["user_content"], "user")
        _source_content(reference["final_response"], "model")
        intermediate = reference["intermediate_data"]
        _keys(intermediate, ("tool_uses", "intermediate_responses"))
        _need(type(intermediate["tool_uses"]) is list and type(intermediate["intermediate_responses"]) is list,
              "unsupported original expected intermediate data")
        for call in intermediate["tool_uses"]:
            _keys(call, ("name", "args"))
            _need(_text(call["name"]) and type(call["args"]) is dict, "unsupported original expected tool call")
    return source, expected


def _prompt(actual, source):
    _keys(actual, ("role", "parts"))
    _need(actual["role"] == "user" and type(actual["parts"]) is list and len(actual["parts"]) == len(source["parts"]),
          "native/source user-content role or part count differs")
    for observed, required in zip(actual["parts"], source["parts"]):
        # These are the original A2A text converter's harmless defaults only.
        _keys(observed, ("text",), ("thought", "part_metadata"))
        _need(type(observed["text"]) is str and observed["text"] == required["text"], "native/source exact user text differs")
        _need(observed.get("thought") is None or observed.get("thought") is False, "native user part contains model thoughts")
        _need(observed.get("part_metadata") is None or type(observed["part_metadata"]) is dict and not observed["part_metadata"],
              "native user part contains additional metadata")


def _journal(journal, source, user, session):
    _need(type(journal) is dict and journal.get("schema_version") == "agentops-runtime-stream-evidence/1"
          and journal.get("status") == "validated" and journal.get("recorded_publication_order_validated") is True,
          "complete validated closed-journal evidence is required")
    _need(_identity(journal.get("receipt_identity")) and _identity(journal.get("observer_identity")),
          "validated journal receipt/observer identities are missing")
    calls = journal.get("calls")
    _need(type(calls) is list and len(calls) == len(source), "journal/source turn count differs")
    records, native_ids = [], []
    for index, (call, turn) in enumerate(zip(calls, source), 1):
        _need(type(call) is dict and type(call.get("invocation_sequence")) is int and call["invocation_sequence"] == index,
              "journal call order differs from source turn order")
        inputs = call.get("inputs")
        _keys(inputs, ("user_id", "session_id", "new_message"), KNOWN_INPUTS)
        _need(type(inputs["user_id"]) is str and inputs["user_id"] == user
              and type(inputs["session_id"]) is str and inputs["session_id"] == session,
              "native user/session context differs")
        _prompt(inputs["new_message"], turn["user_content"])
        events, event_records, receipt = call.get("events"), call.get("event_records"), call.get("receipt")
        _need(type(events) is list and 1 <= len(events) <= 4096 and type(event_records) is list and len(event_records) == len(events)
              and type(receipt) is dict and _identity(call.get("receipt_identity")), "incomplete journal call events/receipt")
        _need(receipt.get("schema_version") == "agentops-runtime-stream/1" and receipt.get("status") == "recorded"
              and type(receipt.get("invocation_sequence")) is int and receipt["invocation_sequence"] == index
              and receipt.get("original_termination") == "normal_exhaustion" and receipt.get("capture_disabled") is False
              and receipt.get("capture_errors") == [] and receipt.get("original_error_type") is None
              and receipt.get("cleanup_error_type") is None, "journal call is partial or failed")
        for key in ("capture_complete", "durable_receipt_written", "inputs_complete", "directory_created_exclusively",
                    "original_aclose_attempted", "original_aclose_completed", "event_identity_fields_complete"):
            _need(receipt.get(key) is True, "journal call completeness flag is missing or false")
        _need(type(receipt.get("original_call_attempts")) is int and receipt["original_call_attempts"] == 1,
              "journal original delegation count differs")
        for key in ("events_seen", "events_recorded", "downstream_yields_entered"):
            _need(type(receipt.get(key)) is int and receipt[key] == len(events), "journal call event count differs")
        _need(_same(receipt.get("events"), event_records), "journal receipt/event records differ")
        identities = []
        previous_global = 0
        for ordinal, (event, record) in enumerate(zip(events, event_records), 1):
            _need(type(event) is dict and _text(event.get("id")) and _text(event.get("invocation_id"))
                  and type(record) is dict and type(record.get("event_ordinal")) is int and record["event_ordinal"] == ordinal
                  and type(record.get("batch_ordinal")) is int and record["batch_ordinal"] == ordinal
                  and type(record.get("global_yield_sequence")) is int and record["global_yield_sequence"] > previous_global
                  and record.get("actual_event_id") == event["id"] and record.get("actual_invocation_id") == event["invocation_id"]
                  and record.get("captured_before_downstream_yield") is True,
                  "journal event identity/publication order differs")
            previous_global = record["global_yield_sequence"]
            if event["invocation_id"] not in identities:
                identities.append(event["invocation_id"])
            records.append({**record, "invocation_sequence": index, "event": event})
        _need(len(identities) == 1 and _same(receipt.get("observed_invocation_ids"), identities)
              and identities[0] not in native_ids, "source turn has missing/reused/multiple native invocation groups")
        supplied = inputs.get("invocation_id")
        _need(supplied is None or type(supplied) is str and supplied == identities[0], "supplied native invocation ID differs")
        native_ids.append(identities[0])
    ordered = sorted(records, key=lambda row: row["global_yield_sequence"])
    _need([row["global_yield_sequence"] for row in ordered] == list(range(1, len(ordered) + 1)),
          "journal global recorder sequence is missing or duplicated")
    _need(_same(journal.get("ordered_event_records"), ordered)
          and _same(journal.get("ordered_events"), [row["event"] for row in ordered]),
          "journal ordered events differ from recorded calls")
    invocations = invocations_from_events(journal["ordered_events"])
    _need([row["invocation_id"] for row in invocations] == native_ids, "native invocation groups do not match source turn order")
    return invocations, native_ids


def assess_source_case(journal_validation, application_case, expectation_case, *,
                       expected_native_user_id, expected_native_session_id):
    """Assess a source projection; invalid/incomplete input raises ValueError.

    The accepted validation report remains caller supplied. Original source
    labels are matched across projections, never substituted for native IDs.
    All authenticated/native/process/effect qualification stays separate.
    """
    _need(_text(expected_native_user_id) and _text(expected_native_session_id), "explicit native user/session identities required")
    for value in (journal_validation, application_case, expectation_case):
        _finite(value)
    source, expected = _source_pair(application_case, expectation_case)
    actual, native_ids = _journal(journal_validation, source, expected_native_user_id, expected_native_session_id)
    metric = score_invocations(actual, expected, threshold=1.0)
    pending = {
        "response": {"status": "pending", "reason": "Tool-response success/error assessment is not implemented."},
        "dependency": {"status": "pending", "reason": "Recorded call order does not establish awaited causal dependencies."},
        "state": {"status": "unavailable", "reason": "No before/after state or effect evidence is supplied to this API."},
        "schema": {"status": "pending", "reason": "Original structured output schema assessment is not implemented."},
        "answer": {"status": "pending", "reason": "Reference answer copying is not a semantic or grounding oracle."},
    }
    return {"schema_version": SCHEMA, "status": "assessed_configured_metric_only",
            "source_case": {"eval_set_id": application_case["eval_set_id"], "eval_id": application_case["eval_id"]},
            "turn_count": len(source), "native_invocation_ids": native_ids,
            "expected_native_user_id": expected_native_user_id, "expected_native_session_id": expected_native_session_id,
            "source_case_projection_binding_checked": True, "native_prompt_context_binding_checked": True,
            "exact_user_text_part_order_checked": True, "configured_metric": metric,
            "separate_assessments": pending, "reference_answer_used_as_passing_oracle": False,
            "journal_validation_is_caller_supplied": True, "filesystem_journal_revalidated_here": False,
            "journal_receipt_identity": journal_validation["receipt_identity"],
            "source_authentication_proven": False, "native_authentication_proven": False,
            "source_closed_proven": False, "process_exit_proven": False, "public_raw_binding_checked": False,
            "causal_tool_execution_order_proven": False, "state_effects_proven": False,
            "benchmark_grade_proven": False, "native_qualification_established": False,
            "native_source_case_qualification": False, "full_task_grade_assigned": False}
