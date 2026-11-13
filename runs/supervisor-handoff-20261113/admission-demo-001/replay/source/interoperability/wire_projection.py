"""Conservative historical projection of recorded MCP task observations.

This cannot certify prospective protocol availability or a service lease.
Native HTTP sidecars are deliberately not accepted or read by this module.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


class ProjectionError(ValueError):
    """Invalid or unsupported evidence, rather than a compatibility failure."""


ROUTES = {
    "amirk_a2a_to_mcp": ("bridge-handle", "58eff9da469bccdc432bf164662727947de646b4"),
    "mgcrea_mcp_a2a": ("public-native-a2a-id", "c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5"),
}
TASK_TOOLS = {"a2a_send_message", "a2a_get_task"}
AMIRK_ORDINARY_STATUS = {
    "TASK_STATE_SUBMITTED": "working", "TASK_STATE_WORKING": "working",
    "TASK_STATE_INPUT_REQUIRED": "input_required", "TASK_STATE_COMPLETED": "completed",
    "TASK_STATE_FAILED": "failed", "TASK_STATE_CANCELED": "cancelled",
    "TASK_STATE_REJECTED": "failed", "TASK_STATE_AUTH_REQUIRED": "failed",
    "TASK_STATE_UNSPECIFIED": "failed",
}


def canonical_digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeError) as error:
        raise ProjectionError("Evidence must have a canonical UTF-8 JSON representation") from error


def _decode_json(raw: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProjectionError("Duplicate JSON key in raw wire evidence")
            result[key] = value
        return result

    def bad_constant(value):
        raise ProjectionError(f"Nonfinite JSON constant: {value}")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProjectionError("Invalid raw JSON wire evidence") from error


def _wire_object(record: dict[str, Any], reply: bool = False) -> dict[str, Any]:
    raw, declared = record.get("raw"), record.get("json")
    if type(raw) is not str or type(declared) is not dict:
        raise ProjectionError("Wire record requires raw text and parsed JSON object")
    try:
        wire = _decode_json(raw)
    except ProjectionError:
        # Explicit SSE framing: identify exactly one declared matching MCP reply.
        if not reply or "data:" not in raw:
            raise
        frames = []
        for block in raw.replace("\r\n", "\n").split("\n\n"):
            data = [line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")]
            if data:
                frames.append(_decode_json("\n".join(data)))
        matched = [x for x in frames if type(x) is dict and x.get("id") == declared.get("id")]
        if len(matched) != 1:
            raise ProjectionError("Ambiguous SSE response correlation")
        wire = matched[0]
    if canonical_digest(wire) != canonical_digest(declared):
        raise ProjectionError("Raw and declared wire JSON disagree")
    if reply:
        try:
            actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        except UnicodeError as error:
            raise ProjectionError("Response is not UTF-8 text") from error
        if record.get("sha256") != actual:
            raise ProjectionError("Raw response SHA-256 mismatch")
    return declared


def _time(value: Any) -> float:
    if type(value) is not str:
        raise ProjectionError("Observation time must be an explicit UTC timestamp")
    try:
        point = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProjectionError("Malformed observation timestamp") from error
    if point.tzinfo is None or point.utcoffset() != timezone.utc.utcoffset(point):
        raise ProjectionError("Observation timestamp must be UTC")
    return point.timestamp()


def _public_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    structured = result.get("structuredContent")
    if type(structured) is dict:
        return structured
    candidates = []
    for block in result.get("content", []) if type(result.get("content", [])) is list else []:
        if type(block) is dict and block.get("type") == "text" and type(block.get("text")) is str:
            try:
                parsed = _decode_json(block["text"])
            except ProjectionError:
                continue
            if type(parsed) is dict:
                candidates.append(parsed)
    if len(candidates) > 1:
        raise ProjectionError("Ambiguous task payload among text blocks")
    return candidates[0] if candidates else None


def _text_field(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if type(value) is str and value else None


def _event_data(route: str, method: str, operation: str, result: dict[str, Any], expected: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if method.startswith("tasks/"):
        payload = result.get("task") if type(result.get("task")) is dict else result
        task = _text_field(payload, "taskId")
        state = _text_field(payload, "status")
        if task is not None:
            out["returned_task_reference"] = task
        if state is not None and state != "completed":
            out["status"] = state
        nested = result.get("result")
        if type(nested) is dict:
            if nested.get("isError") is True or nested.get("isToolError") is True:
                raise ProjectionError("Nested task result is an error; delivery completion is not task success")
            disclosed = _event_data(route, "tools/call", "a2a_get_task", nested, expected)
            for field in ("returned_task_reference",):
                if field in out and field in disclosed and out[field] != disclosed[field]:
                    raise ProjectionError("Contradictory outer task and nested result binding")
            out.update(disclosed)
        return out  # No invented context, artifact or completion from an ack.
    payload = _public_payload(result)
    if payload is None:
        return out
    if route == "mgcrea_mcp_a2a":
        view = payload["task"] if type(payload.get("task")) is dict else payload
        for source, field in (("id", "returned_task_reference"), ("context_id", "returned_context_reference"), ("state", "status")):
            value = _text_field(view, source)
            if value is not None:
                out[field] = value
        if type(view.get("artifacts")) is list:
            texts = [a["text"] for a in view["artifacts"] if type(a) is dict and type(a.get("text")) is str]
            out["artifact_contains_expected"] = any(expected in text for text in texts)
    else:
        exact_state, mapped_state = payload.get("a2aState"), payload.get("status")
        if exact_state is not None and mapped_state is not None:
            if type(exact_state) is not str or exact_state not in AMIRK_ORDINARY_STATUS or AMIRK_ORDINARY_STATUS[exact_state] != mapped_state:
                raise ProjectionError("Ordinary A2A state contradicts the pinned status mapping")
        for source, field in (("taskHandle", "returned_task_reference"), ("contextHandle", "returned_context_reference"), ("status", "status")):
            value = _text_field(payload, source)
            if value is not None:
                out[field] = value
        refs = payload.get("artifacts")
        blocks = result.get("content")
        if type(refs) is list and type(blocks) is list:
            identifiers = {a["artifactId"] for a in refs if type(a) is dict and type(a.get("artifactId")) is str}
            texts = []
            for block in blocks:
                if type(block) is not dict or block.get("type") != "text" or type(block.get("text")) is not str:
                    continue
                meta = block.get("_meta")
                marker = meta.get("io.github.amirk-s/a2a") if type(meta) is dict else None
                if type(marker) is dict and marker.get("artifactId") in identifiers:
                    texts.append(block["text"])
            if not refs or texts:
                out["artifact_contains_expected"] = any(expected in text for text in texts)
    return out


def project_trace(trace: dict[str, Any], expected_artifact_text: str) -> dict[str, Any]:
    """Project one serialized development trace without private traffic/gold."""
    if type(expected_artifact_text) is not str or not expected_artifact_text:
        raise ProjectionError("Expected artifact text must be supplied by the runtime contract")
    if type(trace) is not dict or trace.get("schema_version") != "runtime-wire-observation/1":
        raise ProjectionError("Unsupported runtime trace schema")
    route = trace.get("route_id")
    if type(route) is not str or route not in ROUTES:
        raise ProjectionError("Unpinned route")
    if trace.get("source_commit") != ROUTES[route][1]:
        raise ProjectionError("Unpinned source revision")
    if type(trace.get("protocol")) is not dict:
        raise ProjectionError("Missing pinned protocol record")
    if trace.get("outcome") != "passed" or trace.get("exit_code") != 0:
        raise ProjectionError("Capture failed; retain its evidence, do not project a passing run")
    run_id = trace.get("run_id")
    exchanges = trace.get("exchanges")
    if type(run_id) is not str or not run_id or type(exchanges) is not list:
        raise ProjectionError("Trace needs a run ID and explicit exchanges")
    # Validation covers the whole supplied trace, including unprojected setup.
    seen_exchanges, seen_requests = set(), set()
    previous_end = float("-inf")
    task_events = []
    unsupported_task_actions = []
    positions = {}
    final_time = None
    for exchange in exchanges:
        if type(exchange) is not dict:
            raise ProjectionError("Exchange must be an object")
        identity = exchange.get("exchange_id")
        if type(identity) is not str or not identity or identity in seen_exchanges:
            raise ProjectionError("Missing or duplicate exchange ID")
        seen_exchanges.add(identity)
        positions[identity] = len(positions)
        if exchange.get("run_id", run_id) != run_id:
            raise ProjectionError("Cross-run evidence cannot be merged")
        for field in ("route_id", "source_commit"):
            if field in exchange and exchange[field] != trace[field]:
                raise ProjectionError("Cross-route/source evidence cannot be merged")
        request_record = exchange.get("request")
        if type(request_record) is not dict:
            raise ProjectionError("Missing request evidence")
        request = _wire_object(request_record)
        if "sha256" in request_record and hashlib.sha256(request_record["raw"].encode("utf-8")).hexdigest() != request_record["sha256"]:
            raise ProjectionError("Raw request SHA-256 mismatch")
        if request.get("jsonrpc") != "2.0" or type(request.get("method")) is not str:
            raise ProjectionError("Malformed MCP request")
        started = _time(request_record.get("started_at_utc"))
        response_record = exchange.get("response")
        if response_record is None:
            if "id" in request:
                raise ProjectionError("Unpaired request with a response ID")
            continue  # Captured notification, never a task transition.
        if type(response_record) is not dict:
            raise ProjectionError("Malformed response record")
        request_id = request.get("id")
        if type(request_id) not in (int, str) or (type(request_id), request_id) in seen_requests:
            raise ProjectionError("Missing or reused MCP request ID")
        seen_requests.add((type(request_id), request_id))
        response = _wire_object(response_record, reply=True)
        if response.get("jsonrpc") != "2.0" or type(response.get("id")) is not type(request_id) or response.get("id") != request_id:
            raise ProjectionError("MCP request/response correlation mismatch")
        ended = _time(response_record.get("observed_at_utc"))
        if started > ended or started < previous_end:
            raise ProjectionError("Nonserial or inverted observation intervals")
        previous_end, final_time = ended, ended
        method = request["method"]
        params = request.get("params", {})
        if type(params) is not dict:
            raise ProjectionError("MCP params must be an object")
        operation = params.get("name") if method == "tools/call" else method
        if method == "tools/call" and type(operation) is not str:
            raise ProjectionError("Tool operation name must be a string")
        relevant = (method == "tools/call" and operation in TASK_TOOLS) or method in ("tasks/get", "tasks/update")
        if method == "tasks/cancel" or (method == "tools/call" and operation == "a2a_cancel_task"):
            unsupported_task_actions.append(identity)
        if not relevant:
            continue
        if "error" in response or type(response.get("result")) is not dict:
            raise ProjectionError("Task error needs a separately specified recovery projection; evidence retained")
        result = response["result"]
        if result.get("isError") is True or result.get("isToolError") is True:
            raise ProjectionError("Tool error needs a separately specified recovery projection; evidence retained")
        fields = _event_data(route, method, operation, result, expected_artifact_text)
        source = "extension-observation" if method.startswith("tasks/") else "send-acknowledgement"
        if operation == "a2a_get_task":
            arguments = params.get("arguments", {})
            if type(arguments) is not dict:
                raise ProjectionError("Task arguments must be objects")
            source = "peer-refreshed" if route == "amirk_a2a_to_mcp" or arguments.get("refresh") is True else "local-mirror"
        task_events.append((exchange, request, fields, operation, source))
    initial_index = next((i for i, (_, request, fields, _, _) in enumerate(task_events)
                          if request["method"] == "tools/call" and "returned_task_reference" in fields
                          and "returned_context_reference" in fields), None)
    if initial_index is None or final_time is None:
        raise ProjectionError("No ordinary runtime task/context prefix to project")
    task_events = task_events[initial_index:]
    if any(positions[identity] > positions[task_events[0][0]["exchange_id"]] for identity in unsupported_task_actions):
        raise ProjectionError("Cancellation needs a declared cancellation projection; do not compress a task action")
    if len(task_events) > 65:
        raise ProjectionError("Observed macrostep horizon exceeds finite v1 bound")
    first_fields = task_events[0][2]
    expected_task, expected_context = first_fields["returned_task_reference"], first_fields["returned_context_reference"]
    namespace = ROUTES[route][0]
    events, states, transitions = [], {}, []
    for position, (exchange, request, extracted, operation, source) in enumerate(task_events):
        fields = dict(extracted)
        arguments = request.get("params", {}).get("arguments", {}) if request["method"] == "tools/call" else request.get("params", {})
        if type(arguments) is not dict:
            raise ProjectionError("Task arguments must be objects")
        target_valid = True
        requires_target = position > 0 or operation != "a2a_send_message"
        if requires_target and not any(key in arguments for key in ("taskHandle", "task_id", "taskId")):
            target_valid = False
        for key in ("taskHandle", "task_id", "taskId"):
            if key in arguments:
                target_valid &= type(arguments[key]) is str and arguments[key] == expected_task
        for key in ("contextHandle", "context_id"):
            if key in arguments:
                target_valid &= type(arguments[key]) is str and arguments[key] == expected_context
        fields.update(task_namespace=namespace, request_target_valid=target_valid,
                      required_task_reference=expected_task, required_context_reference=expected_context)
        state_id = run_id + "::" + exchange["exchange_id"]
        states[state_id] = fields
        event = {"state_id": state_id, "exchange_id": exchange["exchange_id"],
                 "request_method": request["method"], "operation": operation,
                 "response_sha256": exchange["response"]["sha256"],
                 "evidence_source": source, "observable_fields": fields}
        if events:
            transitions.append({"id": "edge:" + exchange["exchange_id"], "source": events[-1]["state_id"],
                                "target": state_id, "operation": operation})
        events.append(event)
    trace_digest = canonical_digest(trace)
    clock = math.ceil(final_time)
    manifest = {
        "schema_version": "finite-continuation/1", "id": run_id + ":historical",
        "route": route + " historical observation", "horizon": len(events) - 1,
        "provenance": {"kind": "wire-derived", "source": "runtime-wire-observation/1:" + trace_digest,
                       "review_status": "AI-authored projection; human review pending"},
        "evidence": {"complete": False, "observed_at": clock, "valid_until": clock},
        "initial": events[0]["state_id"], "states": states, "transitions": transitions,
        "runtime_contract": {
            "goal": [{"field": "status", "op": "eq", "value": "completed"},
                     {"field": "returned_task_reference", "op": "eq_field", "other_field": "required_task_reference"},
                     {"field": "returned_context_reference", "op": "eq_field", "other_field": "required_context_reference"},
                     {"field": "artifact_contains_expected", "op": "eq", "value": True}],
            "invariants": [{"field": "request_target_valid", "op": "eq", "value": True},
                           {"field": "task_namespace", "op": "eq", "value": namespace}],
        },
    }
    return {"schema_version": "observed-trace-projection/0", "source_trace_sha256": trace_digest,
            "config": {"expected_artifact_text": expected_artifact_text}, "analysis_clock": clock,
            "initial_exchange_id": events[0]["exchange_id"], "events": events, "manifest": manifest}
