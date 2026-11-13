"""Observed source tool-reply and returned-value consistency, using stdlib only.

The caller supplies read_closed_journal's validated JSON report and one entry
from upstream-agentops-grading-obligations-v1.json. No filesystem, SDK, tool or
model is accessed here. Call projection retains every original-yield occurrence
and every response phase. The frozen calls-only required-trajectory matcher is
used only to identify its earliest selected observations, never to redefine its
metric. A reply must be attributed to one earlier observed call; support for a
consumer additionally requires a strictly earlier original yield and the same
branch. These are observed consistencies, not proof of execution or dataflow.

Source shapes: agent/{tools,memory,longterm,actions,models,guardrails}.py;
pinned SDK tools/{function_tool,skill_toolset}.py and skills/prompt.py.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
import re
import xml.etree.ElementTree as ET

from .agentops_required_trajectory_v1 import required_tools_in_order


SCHEMA = "agentops-reply-dependencies/1"
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INCIDENT = re.compile(r"^INC-\d+$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_UTC_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PREFIX = "<<<TOOL_DATA data-not-instructions>>>"
_SUFFIX = "<<<END_TOOL_DATA>>>"
_PAUSE = "This tool call requires confirmation, please approve or reject."
_ACTIONS = {"restart_service", "resolve_incident"}
_TOOLS = {"get_incident", "list_incidents", "get_service_status", "search_service_logs",
          "get_runbook", "search_runbooks", "recall_incident_context", "save_incident_note",
          "list_skills", "load_skill"} | _ACTIONS
_EXPECTED = {"source_supported_success", "expected_missing_incident_error",
             "expected_missing_service_error", "expected_missing_sample_logs_error", "confirmation_pause_not_execution"}
_KINDS = {"consume_returned_value", "recall_reply_before_incident_read", "discovery_reply_then_full_body_load",
          "explicit_decision_read_reply_barrier", "cross_turn_persistence"}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _text(value):
    return type(value) is str and bool(value.strip())


def _finite(value, depth=0):
    _need(depth <= 48, "JSON nesting exceeds observation bound")
    if type(value) is dict:
        _need(all(type(key) is str for key in value), "nontext JSON key")
        for item in value.values():
            _finite(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _finite(item, depth + 1)
    else:
        _need(value is None or type(value) in (str, int, bool) or type(value) is float and math.isfinite(value),
              "unsupported nonfinite/non-JSON value")


def _same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same(value, right[key]) for key, value in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _keys(value, required, optional=()):
    return type(value) is dict and set(required) <= set(value) <= set(required) | set(optional)


def _identity(value):
    return (_keys(value, ("bytes", "sha256")) and type(value["bytes"]) is int and value["bytes"] > 0
            and type(value["sha256"]) is str and _HASH.fullmatch(value["sha256"]) is not None)


def _slug(value):
    return type(value) is str and _SLUG.fullmatch(value) is not None


def _incident_id(value):
    return type(value) is str and _INCIDENT.fullmatch(value) is not None


def _normalized(args, key, incident=False):
    value = args.get(key)
    if type(value) is not str:
        return None
    normalized = value.strip().upper() if incident else value.strip().lower()
    return normalized if (_incident_id(normalized) if incident else _slug(normalized)) else None


def _count(value, maximum=None):
    return type(value) is int and value >= 0 and (maximum is None or value <= maximum)


def _enum(value, choices):
    return type(value) is str and value in choices


def _timestamp(value):
    if type(value) is not str or _UTC_SECOND.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _incident(value):
    return (_keys(value, ("id", "service", "title", "severity", "status", "runbook", "opened_at", "resolved_at", "summary"))
            and _incident_id(value["id"]) and _slug(value["service"]) and _slug(value["runbook"])
            and all(_text(value[key]) for key in ("title", "opened_at", "summary"))
            and _enum(value["severity"], {"SEV1", "SEV2", "SEV3"}) and _enum(value["status"], {"open", "investigating", "resolved"})
            and (value["resolved_at"] is None or type(value["resolved_at"]) is str))


def _service(value):
    return (_keys(value, ("name", "description", "status", "owner")) and _slug(value["name"])
            and _text(value["description"]) and _text(value["owner"])
            and _enum(value["status"], {"operational", "degraded", "down"}))


def _note(value, *, saved=False):
    # Recall projects existing SQLite TEXT directly; only the current save
    # writer promises normalized incident IDs and UTC-second timestamps.
    return (_keys(value, ("ts", "incident_id", "note"))
            and all(type(value[key]) is str for key in ("ts", "incident_id", "note"))
            and (not saved or _incident_id(value["incident_id"]) and _timestamp(value["ts"]) and _text(value["note"])))


def _frontmatter(value, name):
    return (_keys(value, ("name", "description"), ("license", "compatibility", "allowed_tools", "metadata"))
            and value["name"] == name and _text(value["description"])
            and all(value.get(key) is None or type(value[key]) is str for key in ("license", "compatibility", "allowed_tools"))
            and ("metadata" not in value or type(value["metadata"]) is dict))


def _listed_names(error, prefix):
    # The source listing comes from current data, not an illustrative reference.
    if not error.startswith(prefix) or not error.endswith("."):
        return False
    names = error[len(prefix):-1]
    return not names or all(_slug(name) for name in names.split(", "))


def _skills_xml(value):
    if type(value) is not str or len(value) > 1024 * 1024 or "<!" in value:
        return None
    try:
        root = ET.fromstring(value)
    except ET.ParseError:
        return None
    if root.tag != "available_skills" or root.attrib or (root.text or "").strip():
        return None
    names = []
    for skill in root:
        if skill.tag != "skill" or skill.attrib or (skill.text or "").strip() or (skill.tail or "").strip():
            return None
        if [child.tag for child in skill] != ["name", "description"]:
            return None
        for child in skill:
            if child.attrib or len(child) or (child.tail or "").strip() or not _text(child.text):
                return None
        # The pinned formatter puts newlines around escaped name text.
        names.append(skill[0].text.strip())
    return names


def _audit(value, name, args, user, session, invocation):
    fields = ("id", "schema_version", "ts", "actor", "approved_by", "rationale", "context_summary", "session_id",
              "invocation_id", "action", "target", "detail")
    target = _normalized(args, "name") if name == "restart_service" else _normalized(args, "incident_id", True)
    detail = "service restarted and marked operational (mock)" if name == "restart_service" else "incident resolved (mock)"
    return (_keys(value, fields) and type(value["id"]) is int and type(value["schema_version"]) is int
            and value["id"] > 0 and value["schema_version"] == 1 and all(type(value[key]) is str for key in fields if key not in {"id", "schema_version"})
            and value["actor"] == "agentops-agent" and value["approved_by"] == user.strip() and _text(value["rationale"])
            and value["session_id"] == session.strip() and value["invocation_id"] == invocation.strip()
            and value["action"] == name and value["target"] == target and _timestamp(value["ts"]) and value["detail"] == detail)


def _reply_class(name, args, payload, user, session, invocation):
    """Classify retained JSON shapes, never assert that a body ran or data exists."""
    if name not in _TOOLS or type(payload) is not dict:
        return "unknown"
    if "error" in payload:
        if not _text(payload["error"]) or set(payload) - {"error", "error_code"}:
            return "unknown"
        if "error_code" in payload and (name != "load_skill" or not _enum(payload["error_code"], {"INVALID_ARGUMENTS", "REGISTRY_ERROR", "SKILL_NOT_FOUND"})):
            return "unknown"
        error = payload["error"]
        if name in _ACTIONS and error == _PAUSE and set(payload) == {"error"}:
            return "approval_not_executed_reply"
        incident = _normalized(args, "incident_id", True)
        service = _normalized(args, "name")
        logs = _normalized(args, "service")
        if name == "get_incident" and incident and error == f"No incident found with id {incident!r}.":
            return "expected_missing_incident_error"
        if name == "get_service_status" and service and _listed_names(error, f"No service named {service!r}. Known services: "):
            return "expected_missing_service_error"
        if name == "search_service_logs" and logs and _listed_names(error, f"No logs for service {logs!r}. Available logs: "):
            return "expected_missing_sample_logs_error"
        return "error_reply"
    success = False
    if name == "get_incident":
        success = _keys(payload, ("incident",)) and _incident(payload["incident"]) and payload["incident"]["id"] == _normalized(args, "incident_id", True)
    elif name == "get_service_status":
        rows = payload.get("open_incidents")
        success = (_keys(payload, ("service", "open_incidents")) and _service(payload["service"])
                   and payload["service"]["name"] == _normalized(args, "name") and type(rows) is list
                   and all(_keys(row, ("id", "title", "severity", "status")) and _incident_id(row["id"])
                           and _text(row["title"]) and _enum(row["severity"], {"SEV1", "SEV2", "SEV3"})
                           and _enum(row["status"], {"open", "investigating"}) for row in rows))
    elif name == "list_incidents":
        rows = payload.get("incidents")
        fields = ("id", "service", "title", "severity", "status", "opened_at", "summary")
        success = (_keys(payload, ("count", "incidents")) and type(rows) is list and _count(payload["count"])
                   and payload["count"] == len(rows) and all(_keys(row, fields) and _incident_id(row["id"])
                   and _slug(row["service"]) and all(_text(row[key]) for key in ("title", "opened_at", "summary"))
                   and _enum(row["severity"], {"SEV1", "SEV2", "SEV3"}) and _enum(row["status"], {"open", "investigating", "resolved"}) for row in rows))
    elif name == "search_service_logs":
        lines = payload.get("lines")
        if _keys(payload, ("service", "count", "lines")) and type(lines) is list and _count(payload["count"], 100):
            raw_length = len(lines)
            if len(lines) >= 3 and lines[0] == _PREFIX and lines[-1] == _SUFFIX:
                raw_length -= 2
            success = (_slug(payload["service"]) and payload["service"] == _normalized(args, "service") and type(args.get("query", "")) is str
                       and all(type(line) is str for line in lines)
                       and payload["count"] == raw_length)
    elif name == "get_runbook":
        success = (_keys(payload, ("slug", "content")) and _slug(payload["slug"]) and payload["slug"] == _normalized(args, "slug")
                   and type(payload["content"]) is str)
    elif name == "search_runbooks":
        rows = payload.get("runbooks")
        success = (_keys(payload, ("count", "retrieval", "runbooks")) and type(rows) is list and _count(payload["count"], 3)
                   and type(args.get("query")) is str and payload["count"] == len(rows) and _enum(payload["retrieval"], {"keyword", "semantic"})
                   and all(_keys(row, ("slug", "content")) and _slug(row["slug"]) and type(row["content"]) is str for row in rows))
    elif name == "recall_incident_context":
        rows = payload.get("notes")
        incident = _normalized(args, "incident_id", True) if args.get("incident_id") else None
        success = (_keys(payload, ("count", "notes")) and type(rows) is list and _count(payload["count"], 20)
                   and type(args.get("incident_id", "")) is str and (not args.get("incident_id") or incident is not None)
                   and payload["count"] == len(rows) and all(_note(row) and (incident is None or row["incident_id"] == incident) for row in rows))
    elif name == "save_incident_note":
        saved = payload.get("saved")
        success = (_keys(payload, ("saved",)) and _note(saved, saved=True) and saved["incident_id"] == _normalized(args, "incident_id", True)
                   and _text(args.get("note")) and len(args["note"].strip()) <= 2000)
    elif name == "list_skills":
        success = _keys(payload, ("result",)) and _skills_xml(payload["result"]) is not None
    elif name == "load_skill":
        success = (_keys(payload, ("skill_name", "instructions", "frontmatter"), ("unloaded_skills", "lifecycle_notice"))
                   and _text(args.get("skill_name")) and payload["skill_name"] == args["skill_name"]
                   and _text(payload["instructions"]) and _frontmatter(payload["frontmatter"], args["skill_name"])
                   and ("unloaded_skills" not in payload or type(payload["unloaded_skills"]) is list and all(_text(value) for value in payload["unloaded_skills"]))
                   and ("lifecycle_notice" not in payload or type(payload["lifecycle_notice"]) is str))
    elif name in _ACTIONS:
        target = _normalized(args, "name") if name == "restart_service" else _normalized(args, "incident_id", True)
        result = f"Service {target!r} restarted and marked operational." if name == "restart_service" else f"Incident {target!r} marked resolved."
        success = (_keys(payload, ("result", "audit")) and payload["result"] == result
                   and _audit(payload["audit"], name, args, user, session, invocation))
    return "success_reply" if success else "unknown"


def _validate(journal, obligation, user, session):
    for value in (journal, obligation):
        _finite(value)
    _need(_text(user) and _text(session), "explicit native user/session are required")
    _need(type(obligation) is dict and _text(obligation.get("eval_set_id")) and _text(obligation.get("eval_id"))
          and type(obligation.get("turn_count")) is int and 1 <= obligation["turn_count"] <= 32
          and type(obligation.get("turns")) is list and len(obligation["turns"]) == obligation["turn_count"], "unsupported case obligations")
    permitted = obligation.get("permitted_extra_source_reads")
    _need(type(permitted) is list and all(_enum(name, _TOOLS - _ACTIONS) for name in permitted), "unsupported extra source read scope")
    _need(type(journal) is dict and journal.get("schema_version") == "agentops-runtime-stream-evidence/1"
          and journal.get("status") == "validated" and journal.get("recorded_publication_order_validated") is True
          and _identity(journal.get("receipt_identity")) and _identity(journal.get("observer_identity")), "validated closed-journal report required")
    calls = journal.get("calls")
    _need(type(calls) is list and len(calls) == obligation["turn_count"], "journal/obligation turn count differs")
    ordered, invocations = [], []
    for index, (call, turn) in enumerate(zip(calls, obligation["turns"]), 1):
        _need(type(turn) is dict and type(turn.get("turn_index")) is int and turn["turn_index"] == index, "obligation turn sequence differs")
        metric = turn.get("original_metric")
        _need(type(metric) is dict, "original required-call projection missing")
        required = metric.get("required_trajectory")
        _need(type(required) is list and 1 <= len(required) <= 256, "required source-call obligations missing")
        for sequence, item in enumerate(required, 1):
            _need(type(item) is dict and type(item.get("sequence")) is int and item["sequence"] == sequence
                  and _enum(item.get("name"), _TOOLS) and type(item.get("required_args")) is dict
                  and type(item.get("reply_extra_assessment")) is dict
                  and _enum(item["reply_extra_assessment"].get("classification"), _EXPECTED), "unsupported required reply obligation")
        dependencies = turn.get("source_dependencies_extra_assessment")
        arguments = turn.get("source_tool_argument_obligations_extra_assessment")
        _need(type(dependencies) is list and type(arguments) is list, "source dependency/argument obligations missing")
        for dependency in dependencies:
            _need(type(dependency) is dict and _enum(dependency.get("kind"), _KINDS), "unsupported source dependency kind")
            if dependency["kind"] == "cross_turn_persistence":
                _need(type(dependency.get("producer_turn")) is int and dependency["producer_turn"] == 1
                      and type(dependency.get("consumer_turn")) is int and dependency["consumer_turn"] == 2 and index == 2,
                      "unsupported cross-turn dependency")
                continue
            sequences = [dependency.get("consumer_required_sequence")]
            if dependency["kind"] == "explicit_decision_read_reply_barrier":
                _need(type(dependency.get("producer_required_sequences")) is list, "read barrier producers must be a list")
                sequences += dependency["producer_required_sequences"]
            else:
                sequences += [dependency.get("producer_required_sequence")]
            _need(all(type(value) is int and 1 <= value <= len(required) for value in sequences)
                  and len(sequences) >= 2 and all(value < sequences[0] for value in sequences[1:]), "dependency sequence out of bounds")
            if dependency["kind"] == "consume_returned_value":
                _need(_enum(dependency.get("producer_reply_field"), {"incident.service", "incident.runbook", "incident.id"})
                      and _enum(dependency.get("consumer_argument"), {"name", "service", "slug", "incident_id"}), "unsupported value dependency")
        for argument in arguments:
            _need(type(argument) is dict and argument.get("argument") == "query"
                  and type(argument.get("required_sequence")) is int and 1 <= argument["required_sequence"] <= len(required), "unsupported diagnostic argument obligation")
        _need(type(call) is dict and type(call.get("invocation_sequence")) is int and call["invocation_sequence"] == index
              and _identity(call.get("receipt_identity")), "journal call identity differs")
        inputs = call.get("inputs")
        _need(type(inputs) is dict and type(inputs.get("user_id")) is str and inputs["user_id"] == user
              and type(inputs.get("session_id")) is str and inputs["session_id"] == session, "journal native user/session differs")
        events, records, receipt = call.get("events"), call.get("event_records"), call.get("receipt")
        _need(type(events) is list and 1 <= len(events) <= 4096 and type(records) is list and len(records) == len(events)
              and type(receipt) is dict and receipt.get("schema_version") == "agentops-runtime-stream/1"
              and receipt.get("status") == "recorded" and receipt.get("original_termination") == "normal_exhaustion"
              and receipt.get("capture_disabled") is False and receipt.get("capture_errors") == []
              and receipt.get("original_error_type") is None and receipt.get("cleanup_error_type") is None,
              "journal call evidence is incomplete or failed")
        for key in ("capture_complete", "durable_receipt_written", "inputs_complete", "directory_created_exclusively",
                    "original_aclose_attempted", "original_aclose_completed", "event_identity_fields_complete"):
            _need(receipt.get(key) is True, "journal call completeness flag missing")
        _need(type(receipt.get("invocation_sequence")) is int and receipt["invocation_sequence"] == index
              and type(receipt.get("original_call_attempts")) is int and receipt["original_call_attempts"] == 1
              and _same(receipt.get("events"), records), "journal call receipt binding differs")
        for key in ("events_seen", "events_recorded", "downstream_yields_entered"):
            _need(type(receipt.get(key)) is int and receipt[key] == len(events), "journal call event count differs")
        actual_ids, previous_global = [], 0
        for ordinal, (event, record) in enumerate(zip(events, records), 1):
            _need(type(event) is dict and _text(event.get("id")) and _text(event.get("invocation_id"))
                  and type(record) is dict and type(record.get("event_ordinal")) is int and record["event_ordinal"] == ordinal
                  and type(record.get("batch_ordinal")) is int and record["batch_ordinal"] == ordinal
                  and type(record.get("global_yield_sequence")) is int and record["global_yield_sequence"] > previous_global
                  and record.get("actual_event_id") == event["id"] and record.get("actual_invocation_id") == event["invocation_id"]
                  and record.get("captured_before_downstream_yield") is True, "journal event identity/order binding differs")
            previous_global = record["global_yield_sequence"]
            if event["invocation_id"] not in actual_ids:
                actual_ids.append(event["invocation_id"])
            ordered.append({**record, "invocation_sequence": index, "event": event})
        _need(len(actual_ids) == 1 and actual_ids[0] not in invocations
              and _same(receipt.get("observed_invocation_ids"), actual_ids), "turn native invocation is ambiguous or reused")
        supplied = inputs.get("invocation_id")
        _need(supplied is None or type(supplied) is str and supplied == actual_ids[0], "supplied native invocation differs")
        invocations.append(actual_ids[0])
    ordered.sort(key=lambda row: row["global_yield_sequence"])
    _need([row["global_yield_sequence"] for row in ordered] == list(range(1, len(ordered) + 1))
          and _same(ordered, journal.get("ordered_event_records"))
          and _same([row["event"] for row in ordered], journal.get("ordered_events")), "global publication sequence differs")
    return calls, invocations


def _project(call):
    observed_calls, replies = [], []
    for event, record in zip(call["events"], call["event_records"]):
        _need(event.get("partial") is None or type(event["partial"]) is bool, "unsupported event partial flag")
        content = event.get("content")
        if content is None:
            continue
        _need(type(content) is dict, "unsupported event content")
        parts = content.get("parts")
        if parts is None:
            continue
        _need(type(parts) is list, "unsupported event parts")
        for part_index, part in enumerate(parts):
            _need(type(part) is dict and part.get("functionCall") is None and part.get("functionResponse") is None,
                  "unsupported function-part representation")
            point = {"event_id": event["id"], "invocation_id": event["invocation_id"], "branch": event.get("branch"),
                     "global_yield_sequence": record["global_yield_sequence"], "event_ordinal": record["event_ordinal"],
                     "part_index": part_index, "partial": event.get("partial") is True,
                     "user_authored": str(event.get("author") or "").lower() == "user",
                     "long_running_tool_ids": deepcopy(event.get("long_running_tool_ids"))}
            _need(point["branch"] is None or type(point["branch"]) is str, "unsupported event branch")
            function = part.get("function_call")
            if function is not None:
                _need(type(function) is dict and _text(function.get("name")) and (function.get("args") is None or type(function["args"]) is dict),
                      "unsupported function call")
                observed_calls.append({"observation_index": len(observed_calls), **point, "function": deepcopy(function),
                                       "id": function.get("id"), "name": function["name"], "args": deepcopy(function.get("args") or {}),
                                       "known_source_tool_contract": function["name"] in _TOOLS,
                                       "ordinary_source_call_shape_supported": _text(function.get("id")) and all(value is None for key, value in function.items() if key not in {"id", "name", "args"}),
                                       "user_authored": str(event.get("author") or "").lower() == "user"})
            response = part.get("function_response")
            if response is not None:
                _need(type(response) is dict, "unsupported function response")
                replies.append({"observation_index": len(replies), **point, "function_response": deepcopy(response),
                                "id": response.get("id"), "name": response.get("name"), "payload": deepcopy(response.get("response"))})
    for reply in replies:
        candidates = [item for item in observed_calls if _text(reply["id"]) and reply["id"] == item["id"]
                      and reply["name"] == item["name"] and reply["invocation_id"] == item["invocation_id"]
                      and _same(reply["branch"], item["branch"]) and item["global_yield_sequence"] < reply["global_yield_sequence"]
                      and not item["user_authored"] and not reply["user_authored"] and item["ordinary_source_call_shape_supported"]]
        reply["candidate_call_observation_indices"] = [item["observation_index"] for item in candidates]
        reply["attribution_status"] = "unique_earlier_observation" if len(candidates) == 1 else "unknown"
        extras = {key: value for key, value in reply["function_response"].items() if key not in {"id", "name", "response"} and value is not None}
        reply["source_contract_classification"] = (_reply_class(reply["name"], candidates[0]["args"], reply["payload"],
                                                                  call["inputs"]["user_id"], call["inputs"]["session_id"], reply["invocation_id"])
                                                   if len(candidates) == 1 and not extras else "unknown")
    return observed_calls, replies


def _confirmation_matches(request, action):
    args = request["args"]
    if request["name"] != "adk_request_confirmation" or not _keys(args, ("originalFunctionCall", "toolConfirmation")):
        return False
    original, confirmation = args["originalFunctionCall"], args["toolConfirmation"]
    return (not request["user_authored"] and not request["partial"] and request["ordinary_source_call_shape_supported"]
            and _keys(original, ("id", "name", "args")) and _same(original, {"id": action["id"], "name": action["name"], "args": action["args"]})
            and _keys(confirmation, ("confirmed", "hint"), ("payload",)) and confirmation["confirmed"] is False
            and confirmation["hint"] == f"Please approve or reject the tool call {action['name']}() by responding with a FunctionResponse with an expected ToolConfirmation payload."
            and confirmation.get("payload") is None and _text(request["id"])
            and type(request["long_running_tool_ids"]) is list and request["id"] in request["long_running_tool_ids"]
            and request["id"] != action["id"] and request["global_yield_sequence"] > action["global_yield_sequence"]
            and _same(request["branch"], action["branch"]))


def _required_reply(required, selected, calls, replies):
    row = {"required_sequence": required["sequence"], "expected_source_classification": required["reply_extra_assessment"]["classification"],
           "selected_call_observation_index": selected, "status": "unknown", "reason": "Required observed call or attributed reply is missing."}
    if selected is None:
        return row
    action = calls[selected]
    possible = [reply for reply in replies if reply["id"] == action["id"] and reply["name"] == action["name"]]
    attributed = [reply for reply in possible if reply["candidate_call_observation_indices"] == [selected]]
    row["all_same_id_name_reply_observation_indices"] = [reply["observation_index"] for reply in possible]
    row["attributed_reply_observation_indices"] = [reply["observation_index"] for reply in attributed]
    classes = [reply["source_contract_classification"] for reply in attributed]
    row["observed_attributed_source_classifications"] = classes
    expected = row["expected_source_classification"]
    if expected == "confirmation_pause_not_execution":
        requests = [item["observation_index"] for item in calls if _confirmation_matches(item, action)]
        row["matching_confirmation_request_observation_indices"] = requests
        if "success_reply" in classes:
            row.update(status="inconsistent", reason="An executed-success-shaped reply is observed in a source case that ends at confirmation.")
        elif len(attributed) == len(possible) == 1 and classes == ["approval_not_executed_reply"] and len(requests) == 1:
            row.update(status="supported", reason="Observed preliminary reply and source-shaped matching confirmation request; execution is unproved.")
        return row
    if not possible or len(attributed) != len(possible) or len(attributed) != 1:
        row["reason"] = "Missing, ambiguous or repeated response observations are retained without deduplication."
        return row
    actual = classes[0]
    expected_class = "success_reply" if expected == "source_supported_success" else expected
    if actual == expected_class:
        row.update(status="supported", reason="Unique attributed reply matches the expected source shape and returned target.")
        row["supporting_reply_observation_index"] = attributed[0]["observation_index"]
    elif actual != "unknown":
        row.update(status="inconsistent", reason="Observed reply class differs from the separately specified source-case obligation.")
    else:
        row["reason"] = "Reply shape or target is unsupported; no successful resource observation is invented."
    return row


def _before(producer, consumer, calls, replies):
    if producer["status"] != "supported" or consumer is None or "supporting_reply_observation_index" not in producer:
        return None
    reply = replies[producer["supporting_reply_observation_index"]]
    target = calls[consumer]
    if (reply["source_contract_classification"] != "success_reply" or reply["global_yield_sequence"] >= target["global_yield_sequence"]
            or not _same(reply["branch"], target["branch"])):
        return None
    return reply


def _dependency(obligation, required, selected, calls, replies):
    row = {"obligation": deepcopy(obligation), "status": "unknown", "reason": "Earlier successful attributed reply support is unestablished."}
    kind = obligation["kind"]
    if kind == "cross_turn_persistence":
        row.update(status="unavailable", reason="Committed intended memory rows are not supplied; reply consistency cannot prove persistence.")
        return row
    consumer = selected.get(obligation["consumer_required_sequence"])
    producers = obligation.get("producer_required_sequences", []) if kind == "explicit_decision_read_reply_barrier" else [obligation["producer_required_sequence"]]
    support = [_before(required[sequence - 1], consumer, calls, replies) for sequence in producers]
    row["producer_reply_observation_indices"] = [item["observation_index"] if item is not None else None for item in support]
    if not support or any(item is None for item in support):
        return row
    if kind == "consume_returned_value":
        value = support[0]["payload"]
        for key in obligation["producer_reply_field"].split("."):
            if type(value) is not dict or key not in value:
                return row
            value = value[key]
        args = calls[consumer]["args"]
        argument = obligation["consumer_argument"]
        row.update(producer_observed_value=deepcopy(value), consumer_argument_present=argument in args,
                   consumer_observed_value=deepcopy(args.get(argument)))
        if argument not in args or not _same(value, args[argument]):
            row.update(status="inconsistent", reason="Subsequent argument does not equal the actual earlier reply field verbatim.")
            return row
    elif kind == "discovery_reply_then_full_body_load":
        if required[obligation["consumer_required_sequence"] - 1]["status"] != "supported":
            row["reason"] = "Full instruction-bearing load reply is missing or unsupported."
            return row
        names = _skills_xml(support[0]["payload"].get("result"))
        if names is None or calls[consumer]["args"].get("skill_name") not in names:
            row.update(status="inconsistent", reason="Requested skill is absent from the observed discovery reply.")
            return row
    row.update(status="supported", reason="Supporting reply is in an earlier original yield with matching branch and observed values where required.")
    return row


def _diagnostic(obligation, selected, calls, replies):
    row = {"obligation": deepcopy(obligation), "status": "unknown", "reason": "Diagnostic call observation missing."}
    index = selected.get(obligation["required_sequence"])
    if index is None:
        return row
    target = calls[index]
    relevant = [item for item in calls if item["name"] == "search_service_logs" and not item["user_authored"]
                and _same(item["args"].get("service"), target["args"].get("service"))]
    row["diagnostic_call_observation_indices"] = [item["observation_index"] for item in relevant]
    if not relevant or relevant[0]["args"].get("query", "") != "":
        row.update(status="inconsistent", reason="First observed diagnostic sample for this service is filtered.")
        return row
    for item in relevant:
        if item["args"].get("query", "") == "":
            continue
        earlier = [reply for reply in replies if reply["source_contract_classification"] == "success_reply"
                   and reply["global_yield_sequence"] < item["global_yield_sequence"] and _same(reply["branch"], item["branch"])
                   and len(reply["candidate_call_observation_indices"]) == 1
                   and calls[reply["candidate_call_observation_indices"][0]]["observation_index"] in row["diagnostic_call_observation_indices"]
                   and calls[reply["candidate_call_observation_indices"][0]]["args"].get("query", "") == ""]
        if not earlier:
            row["reason"] = "A later filtered sample lacks an earlier observed successful unfiltered reply."
            return row
    row.update(status="supported", reason="First sample is unfiltered; later filters have earlier attributed unfiltered reply observations.")
    return row


def _aggregate(rows):
    statuses = [row["status"] for row in rows]
    if not statuses:
        return "not_applicable"
    if "inconsistent" in statuses:
        return "inconsistent"
    return "supported" if all(status == "supported" for status in statuses) else "unknown"


def _cross_turn_observation(turns):
    row = {"status": "unknown", "reason": "Unique earlier save and later matching recall reply are required.", "committed_persistence_proven": False}
    if len(turns) != 2:
        return row
    if any(turn["required_reply_assessments"][0]["status"] != "supported" for turn in turns):
        row["reason"] = "Required source save/recall reply observations are missing or unsupported."
        return row
    saves = [reply for reply in turns[0]["tool_replies"] if reply["name"] == "save_incident_note" and reply["source_contract_classification"] == "success_reply"]
    recalls = [reply for reply in turns[1]["tool_replies"] if reply["name"] == "recall_incident_context" and reply["source_contract_classification"] == "success_reply"]
    row["save_reply_observation_indices"] = [reply["observation_index"] for reply in saves]
    row["recall_reply_observation_indices"] = [reply["observation_index"] for reply in recalls]
    if len(saves) != 1 or len(recalls) != 1 or saves[0]["global_yield_sequence"] >= recalls[0]["global_yield_sequence"]:
        return row
    saved = saves[0]["payload"]["saved"]
    matches = [index for index, note in enumerate(recalls[0]["payload"]["notes"]) if _same(note, saved)]
    row["exact_matching_note_indices"] = matches
    if len(matches) == 1:
        row.update(status="supported", reason="One earlier displayed save tuple appears once in the later same-user/session recall; persistence remains unproved.")
    elif not matches:
        row["reason"] = "Exact displayed save tuple is absent from recall; persistence and transformation differences remain unresolved."
    return row


def assess_reply_dependencies(journal_validation, case_obligation, *, expected_native_user_id, expected_native_session_id):
    """Assess plain caller-supplied observed JSON; malformed bindings raise.

    Missing/ambiguous/unsupported reply evidence returns unknown, contradictory
    supported reply classes return inconsistent. The source-case obligations
    and validated report remain caller supplied; this API authenticates neither.
    """
    calls, invocation_ids = _validate(journal_validation, case_obligation, expected_native_user_id, expected_native_session_id)
    turns = []
    for index, (call, turn) in enumerate(zip(calls, case_obligation["turns"]), 1):
        observed, replies = _project(call)
        permitted = set(case_obligation.get("permitted_extra_source_reads", [])) | {item["name"] for item in turn["original_metric"]["required_trajectory"]}
        for item in observed:
            item["declared_source_scope"] = ("runtime_confirmation_request" if item["name"] == "adk_request_confirmation" else
                                             "permitted_tool" if item["name"] in permitted else "outside_supplied_case_tool_scope")
        eligible = [item for item in observed if not item["user_authored"]]
        expected = [{"name": item["name"], "args": item["required_args"]} for item in turn["original_metric"]["required_trajectory"]]
        selection = required_tools_in_order([{"name": item["name"], "args": item["args"]} for item in eligible], expected)
        selected = {sequence: eligible[actual]["observation_index"] for sequence, actual in enumerate(selection["matched_actual_indices"], 1)}
        required = [_required_reply(item, selected.get(item["sequence"]), observed, replies) for item in turn["original_metric"]["required_trajectory"]]
        dependencies = [_dependency(item, required, selected, observed, replies) for item in turn["source_dependencies_extra_assessment"]]
        arguments = [_diagnostic(item, selected, observed, replies) for item in turn["source_tool_argument_obligations_extra_assessment"]]
        turns.append({"turn_index": index, "native_invocation_id": invocation_ids[index - 1], "tool_calls": observed, "tool_replies": replies,
                      "required_reply_assessments": required, "dependency_assessments": dependencies, "argument_assessments": arguments,
                      "reply_consistency_status": _aggregate(required), "dependency_consistency_status": _aggregate(dependencies),
                      "argument_consistency_status": _aggregate(arguments), "required_call_selection_is_original_earliest_subsequence": True,
                      "original_metric_score_assigned_here": False})
    cross = _cross_turn_observation(turns) if any(item["kind"] == "cross_turn_persistence" for turn in case_obligation["turns"] for item in turn["source_dependencies_extra_assessment"]) else {"status": "not_applicable"}
    return {"schema_version": SCHEMA, "status": "observed_reply_and_value_consistency",
            "source_case": {"eval_set_id": case_obligation["eval_set_id"], "eval_id": case_obligation["eval_id"]},
            "turns": turns, "reply_consistency_status": _aggregate([row for turn in turns for row in turn["required_reply_assessments"]]),
            "dependency_consistency_status": _aggregate([row for turn in turns for row in turn["dependency_assessments"]]),
            "argument_consistency_status": _aggregate([row for turn in turns for row in turn["argument_assessments"]]),
            "cross_turn_displayed_note_consistency": cross, "journal_receipt_identity": deepcopy(journal_validation["receipt_identity"]),
            "journal_validation_is_caller_supplied": True, "filesystem_journal_revalidated_here": False,
            "case_obligations_are_caller_supplied": True, "native_user_session_binding_checked": True,
            "source_case_prompt_binding_checked_here": False,
            "all_call_occurrences_and_reply_phases_retained": True, "partial_calls_deduplicated": False,
            "same_yield_array_order_used_as_dependency_support": False, "original_configured_metric_modified": False,
            "original_metric_score_assigned_here": False, "actual_tool_dataflow_proven": False, "awaited_tool_execution_proven": False,
            "source_authentication_proven": False, "causal_tool_execution_order_proven": False,
            "tool_body_execution_proven": False, "complete_native_stream_proven": False, "source_closed_proven": False,
            "state_effects_proven": False, "committed_memory_persistence_proven": False, "full_skill_body_source_binding_proven": False,
            "tool_output_transformation_proven": False, "benchmark_grade_proven": False, "full_task_grade_assigned": False,
            "native_source_case_qualification": False, "native_qualification_established": False}
