"""Historical status/association projection; no private traffic is consumed.

The graph describes recorded observations, not prospective admission or leases.
Established wire-byte helpers are shared with the older artifact projector;
the independent checker must use separate extraction and graph logic.
"""

from __future__ import annotations

import hashlib
import base64
import math
from typing import Any

from .wire_projection import (
    AMIRK_ORDINARY_STATUS, ROUTES, ProjectionError,
    _public_payload, _time, _wire_object, canonical_digest,
)


GOAL = "logical-completion-and-original-association"
TYPED = {"a2a_send_message", "a2a_get_task"}
NATIVE_STATES = {
    "TASK_STATE_" + name.upper(): name for name in (
        "unspecified", "submitted", "working", "completed", "failed",
        "canceled", "input_required", "rejected", "auth_required")
}


def _field(source, name, target, output):
    if name not in source:
        return
    value = source[name]
    if value is not None and type(value) not in (str, bool, int):
        raise ProjectionError("Selected observable is not a finite v1 scalar")
    output[target] = value


def _ordinary(route, result):
    payload = _public_payload(result)
    if payload is None:
        return {}
    output = {}
    if route == "mgcrea_mcp_a2a":
        view = payload["task"] if type(payload.get("task")) is dict else payload
        keys = (("id", "returned_task_reference"), ("context_id", "returned_context_reference"),
                ("state", "status"))
    else:
        view = payload
        if "a2aState" in view and "status" in view:
            exact = view["a2aState"]
            if type(exact) is not str or exact not in AMIRK_ORDINARY_STATUS or AMIRK_ORDINARY_STATUS[exact] != view["status"]:
                raise ProjectionError("Ordinary A2A state contradicts mapped status")
        keys = (("taskHandle", "returned_task_reference"), ("contextHandle", "returned_context_reference"),
                ("status", "status"))
    for key, target in keys:
        _field(view, key, target, output)
    return output


def _modern(route, result):
    payload = result["task"] if type(result.get("task")) is dict else result
    output = {}
    _field(payload, "taskId", "returned_task_reference", output)
    if payload.get("status") != "completed":
        _field(payload, "status", "status", output)
    nested = result.get("result")
    if type(nested) is dict:
        if nested.get("isError") is True or nested.get("isToolError") is True:
            raise ProjectionError("Nested task result error needs a recovery projection")
        disclosed = _ordinary(route, nested)
        if "returned_task_reference" in output and "returned_task_reference" in disclosed and output["returned_task_reference"] != disclosed["returned_task_reference"]:
            raise ProjectionError("Modern task and disclosed ordinary task disagree")
        output.update(disclosed)
    return output


def _raw(result, method):
    payload = _public_payload(result)
    if type(payload) is not dict or payload.get("jsonrpc") != "2.0" or type(payload.get("id")) not in (str, int):
        raise ProjectionError("Raw tool lacks its separate native JSON-RPC envelope")
    if "error" in payload or type(payload.get("result")) is not dict:
        raise ProjectionError("Native raw error/missing result needs a recovery projection")
    view = payload["result"]
    if method == "SendMessage":
        if type(view.get("task")) is not dict:
            raise ProjectionError("Raw SendMessage did not return a task")
        view = view["task"]
    output = {}
    _field(view, "id", "returned_task_reference", output)
    _field(view, "contextId", "returned_context_reference", output)
    status = view.get("status")
    if type(status) is dict and "state" in status:
        state = status["state"]
        if state is None:
            output["status"] = None
        elif type(state) is str and state in NATIVE_STATES:
            output["status"] = NATIVE_STATES[state]
        else:
            raise ProjectionError("Unmapped native raw state")
    return output, (type(payload["id"]), payload["id"])


def _action(request):
    method, params = request["method"], request.get("params", {})
    if type(params) is not dict:
        raise ProjectionError("MCP params must be objects")
    if method in ("tasks/get", "tasks/update"):
        if method == "tasks/update":
            responses = params.get("inputResponses")
            if type(responses) is not dict or not responses:
                raise ProjectionError("Unmodelled task update")
            for response in responses.values():
                if type(response) is not dict or response.get("action") != "accept" or type(response.get("content")) is not dict or not response["content"] or any(type(value) is not str for value in response["content"].values()):
                    raise ProjectionError("Unmodelled task answer/decline")
        return method, params, True
    if method != "tools/call":
        return method, params, False
    name, arguments = params.get("name"), params.get("arguments", {})
    if type(name) is not str or type(arguments) is not dict:
        raise ProjectionError("Tool name/arguments malformed")
    if name in TYPED:
        return name, arguments, True
    if name == "a2a_request":
        native_method, native_params = arguments.get("method"), arguments.get("params", {})
        if native_method not in ("SendMessage", "GetTask") or type(native_params) is not dict:
            raise ProjectionError("Raw task operation requires its own projection")
        target = native_params
        if native_method == "SendMessage":
            target = native_params.get("message")
            if type(target) is not dict:
                raise ProjectionError("Raw send requires a native message")
        return "a2a_request/" + native_method, target, True
    if name == "a2a_cancel_task":
        raise ProjectionError("Cancellation requires a separate declared projection")
    return name, arguments, False


def _nonempty(value):
    return type(value) is str and bool(value)


def _byte_record(record):
    raw = record["raw"].encode("utf-8")
    if record.get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ProjectionError("Wire record hash disagrees")
    if "bytes" in record and (type(record["bytes"]) is not int or record["bytes"] != len(raw)):
        raise ProjectionError("Wire record byte count disagrees")
    if "base64" in record:
        try:
            if base64.b64decode(record["base64"], validate=True) != raw:
                raise ProjectionError("Wire record base64 disagrees")
        except (ValueError, TypeError) as error:
            raise ProjectionError("Malformed wire base64") from error


def _modern_profile(request, request_record, variant):
    params = request.get("params")
    meta = params.get("_meta") if type(params) is dict else None
    capabilities = meta.get("io.modelcontextprotocol/clientCapabilities") if type(meta) is dict else None
    if type(meta) is not dict or meta.get("io.modelcontextprotocol/protocolVersion") != "2026-07-28" or type(capabilities) is not dict:
        raise ProjectionError("Missing/changed modern per-request profile")
    headers = request_record.get("headers")
    if type(headers) is not dict or any(type(k) is not str for k in headers):
        raise ProjectionError("Missing modern request headers")
    lowered = {key.lower(): value for key, value in headers.items()}
    if len(lowered) != len(headers) or lowered.get("mcp-protocol-version") != "2026-07-28" or lowered.get("mcp-method") != request["method"]:
        raise ProjectionError("Modern header/body profile disagrees")
    if request["method"] == "tools/call" and lowered.get("mcp-name") != params.get("name"):
        raise ProjectionError("Modern tool name header disagrees")
    if request["method"].startswith("tasks/") and lowered.get("mcp-name") != params.get("taskId"):
        raise ProjectionError("Modern task name header disagrees")
    extensions = capabilities.get("extensions", {})
    if type(extensions) is not dict:
        raise ProjectionError("Malformed modern client extensions")
    declared = "io.modelcontextprotocol/tasks" in extensions
    if (variant == "R1" and declared) or ((variant == "R2" or request["method"].startswith("tasks/")) and not declared):
        raise ProjectionError("Tasks declaration contradicts selected profile")


def project_status_trace(trace: dict[str, Any]) -> dict[str, Any]:
    if type(trace) is not dict or trace.get("schema_version") != "runtime-wire-observation/1":
        raise ProjectionError("Unsupported runtime trace")
    route = trace.get("route_id")
    if type(route) is not str or route not in ROUTES or trace.get("source_commit") != ROUTES[route][1]:
        raise ProjectionError("Unpinned route/source")
    if type(trace.get("protocol")) is not dict or trace.get("outcome") not in ("recorded", "passed") or trace.get("exit_code") != 0:
        raise ProjectionError("Missing profile or unsuccessful capture")
    variant = trace.get("variant_id")
    if variant is not None and (variant not in ("R1", "R2", "R3", "R4") or ((variant in ("R1", "R2")) != (route == "amirk_a2a_to_mcp"))):
        raise ProjectionError("Variant does not match route")
    run_id, exchanges = trace.get("run_id"), trace.get("exchanges")
    if not _nonempty(run_id) or type(exchanges) is not list or not exchanges:
        raise ProjectionError("Missing execution identity/exchanges")
    seen_exchange, seen_mcp, seen_native = set(), set(), set()
    task_events, other_operations, initialization, discovery, notifications = [], [], [], [], []
    previous_end, final_time, previous_monotonic = float("-inf"), None, None
    for position, exchange in enumerate(exchanges):
        if type(exchange) is not dict or not _nonempty(exchange.get("exchange_id")) or exchange["exchange_id"] in seen_exchange:
            raise ProjectionError("Missing/duplicate exchange identity")
        identity = exchange["exchange_id"]
        seen_exchange.add(identity)
        if exchange.get("run_id", run_id) != run_id or exchange.get("route_id", route) != route or exchange.get("source_commit", trace["source_commit"]) != trace["source_commit"]:
            raise ProjectionError("Cross-execution/source evidence")
        request_record = exchange.get("request")
        if type(request_record) is not dict:
            raise ProjectionError("Missing request")
        request = _wire_object(request_record)
        _byte_record(request_record)
        if request.get("jsonrpc") != "2.0" or type(request.get("method")) is not str:
            raise ProjectionError("Malformed MCP request")
        started = _time(request_record.get("started_at_utc"))
        if started < previous_end:
            raise ProjectionError("Nonserial request interval")
        if route == "amirk_a2a_to_mcp":
            _modern_profile(request, request_record, variant)
        response_record = exchange.get("response")
        if response_record is None:
            if route != "mgcrea_mcp_a2a" or "id" in request or request["method"] != "notifications/initialized":
                raise ProjectionError("Unpaired request/unmodelled notification")
            notifications.append(position)
            previous_end = started
            if "monotonic_ns" in request_record:
                value = request_record["monotonic_ns"]
                if type(value) is not str or not value.isdigit() or (previous_monotonic is not None and int(value) < previous_monotonic):
                    raise ProjectionError("Notification monotonic interval disagrees")
                previous_monotonic = int(value)
            continue
        if type(response_record) is not dict:
            raise ProjectionError("Missing response evidence")
        request_id = request.get("id")
        if type(request_id) not in (str, int) or (type(request_id), request_id) in seen_mcp:
            raise ProjectionError("Missing/reused MCP request ID")
        seen_mcp.add((type(request_id), request_id))
        response = _wire_object(response_record, reply=True)
        _byte_record(response_record)
        if response.get("jsonrpc") != "2.0" or type(response.get("id")) is not type(request_id) or response.get("id") != request_id:
            raise ProjectionError("MCP response correlation disagrees")
        ended = _time(response_record.get("observed_at_utc"))
        if started > ended or started < previous_end:
            raise ProjectionError("Nonserial/inverted exchange interval")
        if "monotonic_ns" in request_record or "monotonic_ns" in response_record:
            first, last = request_record.get("monotonic_ns"), response_record.get("monotonic_ns")
            if type(first) is not str or not first.isdigit() or type(last) is not str or not last.isdigit():
                raise ProjectionError("Malformed monotonic clock")
            first, last = int(first), int(last)
            if first > last or (previous_monotonic is not None and first < previous_monotonic):
                raise ProjectionError("Nonserial monotonic interval")
            previous_monotonic = last
            elapsed = exchange.get("elapsed_ms")
            if elapsed is not None and (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or abs(elapsed - (last - first) / 1e6) >= 0.001):
                raise ProjectionError("Elapsed/monotonic interval disagrees")
        previous_end = final_time = ended
        method = request["method"]
        if "error" in response or type(response.get("result")) is not dict:
            raise ProjectionError("RPC error/missing result requires a recovery projection")
        if method == "initialize":
            initialization.append((position, request.get("params", {}).get("protocolVersion"), response["result"].get("protocolVersion")))
        if method == "server/discover":
            discovery.append((position, response["result"].get("supportedVersions")))
        if method == "tasks/cancel":
            raise ProjectionError("Cancellation requires a separate projection")
        operation, target, relevant = _action(request)
        if not relevant:
            if operation not in ("initialize", "server/discover", "tools/list", "ping", "a2a_discover", "a2a_discover_agent", "a2a_list_agents"):
                raise ProjectionError("Unmodelled operation in trace")
            other_operations.append((position, method, operation))
            continue
        if "error" in response or type(response.get("result")) is not dict:
            raise ProjectionError("Task RPC error requires a recovery projection")
        result = response["result"]
        if result.get("isError") is True or result.get("isToolError") is True:
            raise ProjectionError("Task tool error requires a recovery projection")
        if operation.startswith("a2a_request/"):
            if route != "mgcrea_mcp_a2a":
                raise ProjectionError("Raw escape hatch is not declared by this route")
            fields, native_id = _raw(result, operation.split("/", 1)[1])
            if native_id in seen_native:
                raise ProjectionError("Reused raw native RPC identity")
            seen_native.add(native_id)
        else:
            fields = _modern(route, result) if method.startswith("tasks/") or (route == "amirk_a2a_to_mcp" and result.get("resultType") == "task") else _ordinary(route, result)
        source = "extension-observation" if method.startswith("tasks/") else "send-acknowledgement"
        if operation in ("a2a_get_task", "a2a_request/GetTask"):
            source = "peer-refreshed" if operation == "a2a_request/GetTask" or route == "amirk_a2a_to_mcp" or target.get("refresh") is True else "local-mirror"
        task_events.append((position, exchange, request, operation, target, fields, source))
    expected_protocol = "2026-07-28" if route == "amirk_a2a_to_mcp" else "2025-11-25"
    if trace["protocol"].get("mcp") != expected_protocol or not task_events:
        raise ProjectionError("Missing/changed declared protocol or task evidence")
    if route == "amirk_a2a_to_mcp":
        if initialization or notifications or len(discovery) != 1 or discovery[0][1] != [expected_protocol] or discovery[0][0] >= task_events[0][0]:
            raise ProjectionError("Missing/changed modern discovery profile")
    elif discovery or len(initialization) != 1 or initialization[0][1:] != (expected_protocol, expected_protocol) or len(notifications) != 1 or not initialization[0][0] < notifications[0] < task_events[0][0]:
        raise ProjectionError("Missing/changed negotiated protocol setup")
    initial_index = next((i for i, event in enumerate(task_events)
                          if event[3] in TYPED and _nonempty(event[5].get("returned_task_reference"))
                          and _nonempty(event[5].get("returned_context_reference"))), None)
    if initial_index is None or final_time is None:
        raise ProjectionError("No complete ordinary public prefix")
    initial = task_events[initial_index]
    expected_task = initial[5]["returned_task_reference"]
    expected_context = initial[5]["returned_context_reference"]
    for event in task_events[:initial_index]:
        for field, expected in (("returned_task_reference", expected_task), ("returned_context_reference", expected_context)):
            value = event[5].get(field)
            if _nonempty(value) and value != expected:
                raise ProjectionError("Early public reference contradicts original prefix")
    if any(position > initial[0] and method not in ("tools/list", "ping") for position, method, operation in other_operations):
        raise ProjectionError("Unmodelled operation after original prefix")
    task_events = task_events[initial_index:]
    if len(task_events) > 65:
        raise ProjectionError("Historical macrostep horizon exceeds finite v1")
    namespace = ROUTES[route][0]
    events, states, transitions = [], {}, []
    for index, (_, exchange, request, operation, target, fields, source) in enumerate(task_events):
        fields = dict(fields)
        task_keys = ("id",) if operation == "a2a_request/GetTask" else ("taskHandle", "task_id", "taskId")
        requires_target = index > 0 or operation != "a2a_send_message"
        valid = not requires_target or any(key in target for key in task_keys)
        for key in task_keys:
            if key in target:
                valid &= type(target[key]) is str and target[key] == expected_task
        for key in ("contextHandle", "context_id", "contextId"):
            if key in target:
                valid &= type(target[key]) is str and target[key] == expected_context
        fields.update(task_namespace=namespace, request_target_valid=valid,
                      required_task_reference=expected_task, required_context_reference=expected_context)
        state_id = run_id + "::" + exchange["exchange_id"]
        states[state_id] = fields
        if events:
            transitions.append({"id": "edge:" + exchange["exchange_id"], "source": events[-1]["state_id"],
                                "target": state_id, "operation": operation})
        events.append({"state_id": state_id, "exchange_id": exchange["exchange_id"],
                       "request_method": request["method"], "operation": operation,
                       "response_sha256": exchange["response"]["sha256"],
                       "evidence_source": source, "observable_fields": fields})
    trace_digest, clock = canonical_digest(trace), math.ceil(final_time)
    manifest = {
        "schema_version": "finite-continuation/1", "id": run_id + ":historical-status",
        "route": route + " historical status observation", "horizon": len(events) - 1,
        "provenance": {"kind": "wire-derived", "source": "runtime-wire-observation/1:" + trace_digest,
                       "review_status": "AI-authored status projection; human review pending"},
        "evidence": {"complete": False, "observed_at": clock, "valid_until": clock},
        "initial": events[0]["state_id"], "states": states, "transitions": transitions,
        "runtime_contract": {
            "goal": [{"field": "status", "op": "eq", "value": "completed"},
                     {"field": "returned_task_reference", "op": "eq_field", "other_field": "required_task_reference"},
                     {"field": "returned_context_reference", "op": "eq_field", "other_field": "required_context_reference"}],
            "invariants": [{"field": "request_target_valid", "op": "eq", "value": True},
                           {"field": "task_namespace", "op": "eq", "value": namespace}]},
    }
    return {"schema_version": "observed-status-trace-projection/1", "source_trace_sha256": trace_digest,
            "config": {"goal": GOAL}, "analysis_clock": clock,
            "initial_exchange_id": events[0]["exchange_id"], "events": events, "manifest": manifest}
