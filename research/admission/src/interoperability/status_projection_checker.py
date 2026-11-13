"""Independent literal-byte review of historical status/association evidence.

The two public functions are pure: callers supply already loaded public traces
and, separately, evaluator-private HTTP records.  No projector, solver, source
program, clock, filesystem or transport is imported.  Acceptance establishes
recorded projection fidelity, not prospective availability or human review.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any


_PINS = {
    "amirk_a2a_to_mcp": "58eff9da469bccdc432bf164662727947de646b4",
    "mgcrea_mcp_a2a": "c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5",
}
_NAMESPACES = {"amirk_a2a_to_mcp": "bridge-handle", "mgcrea_mcp_a2a": "public-native-a2a-id"}
_AMIR_STATES = {
    "TASK_STATE_UNSPECIFIED": "failed", "TASK_STATE_SUBMITTED": "working",
    "TASK_STATE_WORKING": "working", "TASK_STATE_INPUT_REQUIRED": "input_required",
    "TASK_STATE_COMPLETED": "completed", "TASK_STATE_CANCELED": "cancelled",
    "TASK_STATE_FAILED": "failed", "TASK_STATE_REJECTED": "failed",
    "TASK_STATE_AUTH_REQUIRED": "failed",
}
_MG_STATES = {
    "TASK_STATE_UNSPECIFIED": "unspecified", "TASK_STATE_SUBMITTED": "submitted",
    "TASK_STATE_WORKING": "working", "TASK_STATE_INPUT_REQUIRED": "input_required",
    "TASK_STATE_COMPLETED": "completed", "TASK_STATE_CANCELED": "canceled",
    "TASK_STATE_FAILED": "failed", "TASK_STATE_REJECTED": "rejected",
    "TASK_STATE_AUTH_REQUIRED": "auth_required",
}
_READ_TOOLS = {"a2a_discover", "a2a_discover_agent", "a2a_list_agents"}
_SETUP_METHODS = {"initialize", "server/discover", "tools/list", "ping", "notifications/initialized"}
_VARIANT_ROUTES = {"R1": "amirk_a2a_to_mcp", "R2": "amirk_a2a_to_mcp", "R3": "mgcrea_mcp_a2a", "R4": "mgcrea_mcp_a2a"}
_GOAL = [
    {"field": "status", "op": "eq", "value": "completed"},
    {"field": "returned_task_reference", "op": "eq_field", "other_field": "required_task_reference"},
    {"field": "returned_context_reference", "op": "eq_field", "other_field": "required_context_reference"},
]


def _assert(condition: bool) -> None:
    if not condition:
        raise ValueError("invalid or unsupported status evidence")


def _equal(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def _pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in entries:
        _assert(key not in result)
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("not a JSON number: " + value)


def _json(raw: Any) -> Any:
    _assert(type(raw) is str)
    raw.encode("utf-8", errors="strict")
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8", errors="strict")).hexdigest()


def _string(value: Any) -> bool:
    return type(value) is str and bool(value)


def _seconds(value: Any) -> float:
    _assert(_string(value))
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _assert(stamp.tzinfo is not None and stamp.utcoffset() == timezone.utc.utcoffset(stamp))
    return stamp.timestamp()


def _bytes(record: Any, required_hash: bool) -> bytes:
    _assert(type(record) is dict and type(record.get("raw")) is str)
    raw = record["raw"].encode("utf-8", errors="strict")
    if required_hash or "sha256" in record:
        _assert(record.get("sha256") == hashlib.sha256(raw).hexdigest())
    if "bytes" in record:
        _assert(type(record["bytes"]) is int and record["bytes"] == len(raw))
    if "base64" in record:
        _assert(type(record["base64"]) is str and base64.b64decode(record["base64"], validate=True) == raw)
    return raw


def _sse(raw: str) -> list[Any]:
    values = []
    lines = []
    for line in raw.replace("\r\n", "\n").split("\n") + [""]:
        if line.startswith("data:"):
            lines.append(line[5:].removeprefix(" "))
        elif not line and lines:
            values.append(_json("\n".join(lines)))
            lines = []
    _assert(bool(values))
    return values


def _headers(value: Any) -> dict[str, str]:
    _assert(type(value) is dict)
    result = {}
    for key, item in value.items():
        _assert(type(key) is str and type(item) is str and key.lower() not in result)
        result[key.lower()] = item
    return result


def _body(record: Any, *, response: bool = False) -> Any:
    _bytes(record, response)
    _assert("json" in record)
    headers = _headers(record.get("headers", {}))
    content_type = headers.get("content-type", "")
    if response and "text/event-stream" in content_type:
        candidates = _sse(record["raw"])
        expected = record["json"]
        _assert(type(expected) is dict)
        matches = [item for item in candidates if type(item) is dict and _equal(item.get("id"), expected.get("id"))]
        _assert(len(matches) == 1 and _equal(matches[0], expected))
        return matches[0]
    value = _json(record["raw"])
    _assert(_equal(value, record["json"]))
    return value


def _scope(record: dict[str, Any], trace: dict[str, Any]) -> None:
    for key in ("run_id", "route_id", "source_commit"):
        if key in record:
            _assert(_equal(record[key], trace[key]))


def _operation(request: dict[str, Any], route: str) -> str | None:
    method = request["method"]
    params = request.get("params", {})
    _assert(type(params) is dict)
    if method.startswith("tasks/"):
        _assert(route == "amirk_a2a_to_mcp" and method in {"tasks/get", "tasks/update"})
        if method == "tasks/update":
            responses = params.get("inputResponses")
            _assert(type(responses) is dict and len(responses) > 0)
            for response in responses.values():
                _assert(type(response) is dict and response.get("action") == "accept")
                content = response.get("content")
                _assert(type(content) is dict and len(content) > 0 and all(type(x) is str for x in content.values()))
        return method
    if method != "tools/call":
        _assert(method in _SETUP_METHODS)
        return None
    name = params.get("name")
    _assert(_string(name))
    arguments = params.get("arguments", {})
    _assert(type(arguments) is dict)
    if name in {"a2a_send_message", "a2a_get_task"}:
        return name
    if name == "a2a_request":
        _assert(route == "mgcrea_mcp_a2a" and _string(arguments.get("method")))
        inner = arguments["method"]
        _assert(type(arguments.get("params", {})) is dict)
        if inner in {"SendMessage", "GetTask"}:
            return "a2a_request/" + inner
        _assert(False)
    # Only explicitly modelled read-only discovery can precede the prefix.
    _assert(name in _READ_TOOLS)
    return None


def _wire(trace: Any) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]]:
    _assert(type(trace) is dict and trace.get("schema_version") == "runtime-wire-observation/1")
    _assert(_string(trace.get("run_id")) and trace.get("route_id") in _PINS)
    _assert(trace.get("source_commit") == _PINS[trace["route_id"]])
    variant = trace.get("variant_id")
    if "variant_id" in trace:
        _assert(type(variant) is str and variant in _VARIANT_ROUTES and _VARIANT_ROUTES[variant] == trace["route_id"])
    _assert(type(trace.get("protocol")) is dict and type(trace.get("provenance")) is dict)
    _assert(trace["protocol"].get("mcp") == ("2026-07-28" if trace["route_id"] == "amirk_a2a_to_mcp" else "2025-11-25"))
    _assert(trace.get("outcome") in {"recorded", "passed"})
    if "exit_code" in trace:
        _assert(type(trace["exit_code"]) is int and trace["exit_code"] == 0)
    exchanges = trace.get("exchanges")
    _assert(type(exchanges) is list and len(exchanges) > 0)
    used_exchanges, used_ids, paired = set(), set(), []
    utc_end, mono_end, initializations, discoveries, notifications = -math.inf, None, 0, 0, 0
    for exchange in exchanges:
        _assert(type(exchange) is dict)
        _scope(exchange, trace)
        identifier = exchange.get("exchange_id")
        _assert(_string(identifier) and identifier not in used_exchanges)
        used_exchanges.add(identifier)
        first = exchange.get("request")
        request = _body(first)
        _assert(type(request) is dict and request.get("jsonrpc") == "2.0" and _string(request.get("method")))
        _scope(first, trace)
        _scope(request, trace)
        operation = _operation(request, trace["route_id"])
        if trace["route_id"] == "amirk_a2a_to_mcp":
            metadata = request.get("params", {}).get("_meta")
            headers = _headers(first.get("headers"))
            _assert(type(metadata) is dict and metadata.get("io.modelcontextprotocol/protocolVersion") == "2026-07-28")
            capabilities = metadata.get("io.modelcontextprotocol/clientCapabilities")
            _assert(type(capabilities) is dict)
            _assert(headers.get("mcp-protocol-version") == "2026-07-28")
            _assert(headers.get("mcp-method") == request["method"])
            if request["method"] == "tools/call":
                _assert(headers.get("mcp-name") == request["params"]["name"])
            if request["method"].startswith("tasks/"):
                _assert(_string(request["params"].get("taskId")) and headers.get("mcp-name") == request["params"]["taskId"])
            extensions = capabilities.get("extensions", {})
            _assert(type(extensions) is dict)
            if variant == "R1":
                _assert("io.modelcontextprotocol/tasks" not in extensions)
            if variant == "R2":
                _assert(type(extensions.get("io.modelcontextprotocol/tasks")) is dict)
            if operation in {"tasks/get", "tasks/update"}:
                _assert(type(extensions.get("io.modelcontextprotocol/tasks")) is dict)
            if operation is not None:
                _assert(discoveries == 1)
        elif operation is not None:
            _assert(initializations == 1 and notifications == 1)
        started = _seconds(first.get("started_at_utc"))
        _assert(started >= utc_end)
        has_id = "id" in request
        if has_id:
            rid = request["id"]
            _assert(type(rid) in (str, int) and (type(rid), rid) not in used_ids)
            used_ids.add((type(rid), rid))
        last = exchange.get("response")
        if last is None:
            _assert(not has_id and request["method"] == "notifications/initialized" and operation is None)
            _assert(trace["route_id"] == "mgcrea_mcp_a2a" and initializations == 1 and notifications == 0)
            notifications += 1
            utc_end = started
            if "monotonic_ns" in first:
                _assert(type(first["monotonic_ns"]) is str and first["monotonic_ns"].isdigit())
                current = int(first["monotonic_ns"])
                _assert(mono_end is None or current >= mono_end)
                mono_end = current
            continue
        _assert(has_id)
        response = _body(last, response=True)
        _scope(last, trace)
        _scope(response, trace)
        _assert(type(response) is dict and response.get("jsonrpc") == "2.0")
        _assert("id" in response and _equal(request["id"], response["id"]))
        _assert(("result" in response) != ("error" in response))
        _assert("error" not in response and type(response.get("result")) is dict)
        _assert(response["result"].get("isError") is not True and response["result"].get("isToolError") is not True and "error" not in response["result"])
        if "status" in last:
            _assert(type(last["status"]) is int and 200 <= last["status"] < 300)
        if request["method"] == "initialize":
            _assert(trace["route_id"] == "mgcrea_mcp_a2a")
            initializations += 1
            _assert(initializations == 1)
            expected = "2026-07-28" if trace["route_id"] == "amirk_a2a_to_mcp" else "2025-11-25"
            _assert(request.get("params", {}).get("protocolVersion") == expected)
            _assert(type(response.get("result")) is dict and response["result"].get("protocolVersion") == expected)
        if request["method"] == "server/discover":
            _assert(trace["route_id"] == "amirk_a2a_to_mcp")
            discoveries += 1
            _assert(discoveries == 1 and type(response.get("result")) is dict)
            versions = response["result"].get("supportedVersions")
            _assert(type(versions) is list and "2026-07-28" in versions)
        ended = _seconds(last.get("observed_at_utc"))
        _assert(started <= ended)
        utc_end = ended
        elapsed = exchange.get("elapsed_ms")
        if elapsed is not None:
            _assert(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0)
        if "monotonic_ns" in first or "monotonic_ns" in last:
            a, b = first.get("monotonic_ns"), last.get("monotonic_ns")
            _assert(type(a) is str and a.isdigit() and type(b) is str and b.isdigit())
            a, b = int(a), int(b)
            _assert(a <= b and (mono_end is None or a >= mono_end))
            if elapsed is not None:
                _assert(abs(elapsed - (b - a) / 1_000_000) < .001)
            mono_end = b
        if operation is not None:
            _assert("error" not in response and type(response.get("result")) is dict)
            result = response["result"]
            _assert(result.get("isError") is not True and result.get("isToolError") is not True and "error" not in result)
            if "status" in last:
                _assert(type(last["status"]) is int and 200 <= last["status"] < 300)
        paired.append((exchange, request, response, operation))
    _assert((discoveries == 1 and initializations == 0) if trace["route_id"] == "amirk_a2a_to_mcp" else (initializations == 1 and notifications == 1))
    return paired


def _payload(result: dict[str, Any]) -> dict[str, Any] | None:
    structured = result.get("structuredContent")
    if structured is not None:
        _assert(type(structured) is dict)
    content = result.get("content", [])
    _assert(type(content) is list)
    values = []
    for block in content:
        _assert(type(block) is dict)
        if block.get("type") == "text" and type(block.get("text")) is str and block["text"].lstrip().startswith("{"):
            decoded = _json(block["text"])
            _assert(type(decoded) is dict)
            values.append(decoded)
    if type(structured) is dict:
        _assert(all(_equal(structured, candidate) for candidate in values))
        return structured
    _assert(len(values) <= 1)
    return values[0] if values else None


def _copy_fields(view: dict[str, Any], fields: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    result = {}
    for name, projected in fields:
        if name in view:
            _assert(type(view[name]) in (str, int, bool, type(None)))
            result[projected] = view[name]
    return result


def _ordinary_amir(result: dict[str, Any]) -> dict[str, Any] | None:
    envelope = result.get("structuredContent")
    if type(envelope) is not dict or envelope.get("kind") != "task":
        return None
    values = _copy_fields(envelope, (("taskHandle", "returned_task_reference"), ("contextHandle", "returned_context_reference"), ("status", "status")))
    if "a2aState" in envelope:
        if "status" in envelope:
            _assert(envelope["a2aState"] in _AMIR_STATES)
            _assert(_equal(envelope["status"], _AMIR_STATES[envelope["a2aState"]]))
    return values


def _raw_rpc(result: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(result)
    _assert(type(payload) is dict and payload.get("jsonrpc") == "2.0")
    _assert(type(payload.get("id")) in (str, int) and "result" in payload and "error" not in payload)
    _assert(type(payload["result"]) is dict)
    return payload


def _observed(route: str, request: dict[str, Any], response: dict[str, Any], operation: str) -> tuple[dict[str, Any], bool]:
    result = response["result"]
    if route == "mgcrea_mcp_a2a":
        if operation.startswith("a2a_request/"):
            native = _raw_rpc(result)["result"]
            if operation.endswith("/SendMessage"):
                task = native.get("task")
                if task is None:
                    return {}, False
            else:
                task = native
            _assert(type(task) is dict)
            values = _copy_fields(task, (("id", "returned_task_reference"), ("contextId", "returned_context_reference")))
            if "status" in task:
                status = task["status"]
                _assert(type(status) is dict)
                if "state" in status:
                    if status["state"] is None:
                        values["status"] = None
                    else:
                        _assert(status["state"] in _MG_STATES)
                        values["status"] = _MG_STATES[status["state"]]
            return values, False
        payload = _payload(result)
        if payload is None:
            return {}, True
        task = payload.get("task", payload)
        _assert(type(task) is dict)
        return _copy_fields(task, (("id", "returned_task_reference"), ("context_id", "returned_context_reference"), ("state", "status"))), True
    ordinary = _ordinary_amir(result)
    if ordinary is not None:
        return ordinary, request["method"] == "tools/call"
    # Modern delivery records do not supply a logical completion predicate.
    values = _copy_fields(result, (("taskId", "returned_task_reference"),))
    if "status" in result and result["status"] != "completed":
        _assert(type(result["status"]) in (str, int, bool, type(None)))
        values["status"] = result["status"]
    nested = result.get("result")
    if nested is not None:
        _assert(type(nested) is dict and nested.get("isError") is not True and nested.get("isToolError") is not True and "error" not in nested)
        logical = _ordinary_amir(nested)
        if logical is not None:
            if "returned_task_reference" in values and "returned_task_reference" in logical:
                _assert(_equal(values["returned_task_reference"], logical["returned_task_reference"]))
            values.update(logical)
    return values, False


def _valid_target(request: dict[str, Any], operation: str, route: str, task: str, context: str, first: bool) -> bool:
    params = request.get("params", {})
    if request["method"] == "tools/call":
        params = params.get("arguments", {})
    if operation.startswith("a2a_request/"):
        params = params.get("params", {})
        if operation.endswith("/SendMessage"):
            params = params.get("message", {})
            task_key, context_key = "taskId", "contextId"
        else:
            task_key, context_key = "id", "contextId"
    else:
        task_key = "taskId" if request["method"].startswith("tasks/") else ("taskHandle" if route == "amirk_a2a_to_mcp" else "task_id")
        context_key = "contextHandle" if route == "amirk_a2a_to_mcp" else "context_id"
    _assert(type(params) is dict)
    target = (first and operation == "a2a_send_message") if task_key not in params else _equal(params[task_key], task)
    if context_key in params:
        target = target and _equal(params[context_key], context)
    return target


def _source(route: str, request: dict[str, Any], operation: str) -> str:
    if operation.startswith("tasks/"):
        return "extension-observation"
    if operation in {"a2a_send_message", "a2a_request/SendMessage"}:
        return "send-acknowledgement"
    if operation == "a2a_request/GetTask" or route == "amirk_a2a_to_mcp":
        return "peer-refreshed"
    return "peer-refreshed" if request.get("params", {}).get("arguments", {}).get("refresh") is True else "local-mirror"


def check_status_projection(trace: Any, projection: Any) -> bool:
    """Check the exact graph and status-only contract against all public bytes."""
    try:
        pairs = _wire(trace)
        _assert(type(projection) is dict)
        _assert(set(projection) == {"schema_version", "source_trace_sha256", "config", "analysis_clock", "initial_exchange_id", "events", "manifest"})
        _assert(projection["schema_version"] == "observed-status-trace-projection/1")
        _assert(_equal(projection["config"], {"goal": "logical-completion-and-original-association"}))
        digest = _digest(trace)
        _assert(projection["source_trace_sha256"] == digest)
        selected = []
        inner_ids = set()
        for exchange, request, response, operation in pairs:
            if operation is None:
                continue
            fields, ordinary = _observed(trace["route_id"], request, response, operation)
            if operation.startswith("a2a_request/"):
                rpc_id = _raw_rpc(response["result"])["id"]
                key = (type(rpc_id), rpc_id)
                _assert(key not in inner_ids)
                inner_ids.add(key)
            selected.append((exchange, request, fields, ordinary, operation))
        initial = next(i for i, (_, _, fields, ordinary, _) in enumerate(selected) if ordinary and _string(fields.get("returned_task_reference")) and _string(fields.get("returned_context_reference")))
        original_fields = selected[initial][2]
        for _, _, before, _, _ in selected[:initial]:
            for field in ("returned_task_reference", "returned_context_reference"):
                if _string(before.get(field)):
                    _assert(_equal(before[field], original_fields[field]))
        selected = selected[initial:]
        _assert(0 < len(selected) <= 65)
        prefix_id = selected[0][0]["exchange_id"]
        prefix_position = next(i for i, pair in enumerate(pairs) if pair[0]["exchange_id"] == prefix_id)
        for _, request, _, operation in pairs[prefix_position:]:
            if operation is None:
                _assert(request["method"] in {"tools/list", "ping"})
        task, context = selected[0][2]["returned_task_reference"], selected[0][2]["returned_context_reference"]
        namespace, run = _NAMESPACES[trace["route_id"]], trace["run_id"]
        events, states, edges = [], {}, []
        for index, (exchange, request, literal, _, operation) in enumerate(selected):
            fields = dict(literal)
            fields.update(task_namespace=namespace, required_task_reference=task, required_context_reference=context,
                          request_target_valid=_valid_target(request, operation, trace["route_id"], task, context, index == 0))
            state = run + "::" + exchange["exchange_id"]
            event = {"state_id": state, "exchange_id": exchange["exchange_id"], "request_method": request["method"],
                     "operation": operation, "response_sha256": exchange["response"]["sha256"],
                     "evidence_source": _source(trace["route_id"], request, operation), "observable_fields": fields}
            if events:
                edges.append({"id": "edge:" + exchange["exchange_id"], "source": events[-1]["state_id"], "target": state, "operation": operation})
            events.append(event)
            states[state] = fields
        clock = math.ceil(max(_seconds(exchange["response"]["observed_at_utc"]) for exchange, _, _, _ in pairs))
        _assert(type(projection["analysis_clock"]) is int and projection["analysis_clock"] == clock)
        _assert(projection["initial_exchange_id"] == events[0]["exchange_id"] and _equal(projection["events"], events))
        expected = {"schema_version": "finite-continuation/1", "id": run + ":historical-status", "route": trace["route_id"] + " historical status observation",
                    "provenance": {"kind": "wire-derived", "source": "runtime-wire-observation/1:" + digest, "review_status": "AI-authored status projection; human review pending"},
                    "horizon": len(events) - 1, "evidence": {"complete": False, "observed_at": clock, "valid_until": clock},
                    "initial": events[0]["state_id"], "states": states, "transitions": edges,
                    "runtime_contract": {"goal": _GOAL, "invariants": [{"field": "request_target_valid", "op": "eq", "value": True}, {"field": "task_namespace", "op": "eq", "value": namespace}]}}
        _assert(_equal(projection["manifest"], expected))
        return True
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, StopIteration, AttributeError, RecursionError):
        return False


def _native_records(records: Any, trace: dict[str, Any]) -> list[dict[str, Any]]:
    _assert(type(records) is list and len(records) > 1)
    metadata = records[0]
    _assert(type(metadata) is dict and metadata.get("schema_version") == "private-native-http/1")
    _assert(metadata.get("run_id") == trace["run_id"] and metadata.get("route_id") == trace["route_id"])
    pending, completed, result = {}, set(), []
    modern = any(type(r) is dict and r.get("type") == "request-started" for r in records[1:])
    for record in records[1:]:
        _assert(type(record) is dict)
        _scope(record, trace)
        kind = record.get("type")
        if kind in {"shutdown-request", "logger-exit"}:
            _assert(type(record.get("pid")) is int)
            if "pid" in metadata:
                _assert(record["pid"] == metadata["pid"])
            _seconds(record.get("observed", {}).get("utc") if type(record.get("observed")) is dict else record.get("observed"))
            continue
        _assert(record.get("role") == "native_peer_response")
        identifier = record.get("exchange_id")
        _assert(_string(identifier))
        if kind == "request-started":
            _assert(identifier not in pending and identifier not in completed and record.get("response") is None)
            pending[identifier] = record
            continue
        _assert(kind in (None, "exchange-completed"))
        _assert(identifier not in completed)
        if modern:
            _assert(kind == "exchange-completed" and identifier in pending and _equal(record.get("request"), pending.pop(identifier)["request"]))
        _assert(type(record.get("response")) is dict and "error" not in record)
        completed.add(identifier)
        result.append(record)
    _assert(not pending and bool(result))
    return result


def _native_messages(last: dict[str, Any]) -> list[dict[str, Any]]:
    _bytes(last, True)
    _assert("json" in last)
    headers = _headers(last.get("headers", {}))
    if "text/event-stream" in str(headers.get("content-type", "")):
        _assert(last["json"] is None)
        return _sse(last["raw"])
    decoded = _json(last["raw"])
    _assert(_equal(decoded, last["json"]) and type(decoded) is dict)
    return [decoded]


def _native_task(messages: list[dict[str, Any]], method: str) -> list[dict[str, Any]]:
    tasks = []
    for message in messages:
        result = message["result"]
        _assert(type(result) is dict)
        if method == "GetTask":
            tasks.append(result)
        elif type(result.get("task")) is dict:
            tasks.append(result["task"])
        elif type(result.get("statusUpdate")) is dict:
            tasks.append(result["statusUpdate"])
    return tasks


def _native_state(task: dict[str, Any], route: str) -> str | None:
    if "status" not in task:
        return None
    status = task["status"]
    _assert(type(status) is dict)
    if "state" not in status:
        return None
    if status["state"] is None:
        return None
    mapping = _AMIR_STATES if route == "amirk_a2a_to_mcp" else _MG_STATES
    _assert(status["state"] in mapping)
    return mapping[status["state"]]


def check_status_native_sidecar(trace: Any, records: Any) -> bool:
    """Check explicit private HTTP correlation; never supply IDs to projection.

    Native request initiation must lie in a unique MCP interval. Response-body
    completion may follow an asynchronous acknowledgement. Raw RPC header
    absence is retained, using a captured 1.0 agent-card interface instead.
    """
    try:
        pairs = _wire(trace)
        native = _native_records(records, trace)
        route = trace["route_id"]
        public = {e["exchange_id"]: _observed(route, q, r, op)[0] for e, q, r, op in pairs if op is not None}
        rpc_ids, calls, handles, contexts, cards = set(), {}, {}, {}, set()
        observed = False
        for record in native:
            first, last = record.get("request"), record.get("response")
            _assert(type(first) is dict and type(last) is dict)
            start, finish = _seconds(first.get("started_at_utc")), _seconds(last.get("observed_at_utc"))
            _assert(start <= finish and type(last.get("status")) is int and 200 <= last["status"] < 300)
            if "headers_observed_at_utc" in last:
                _assert(start <= _seconds(last["headers_observed_at_utc"]) <= finish)
            matching = []
            for exchange, request, response, operation in pairs:
                a, b = exchange["request"], exchange["response"]
                if "monotonic_ns" in first and "monotonic_ns" in a and "monotonic_ns" in b:
                    _assert(type(first["monotonic_ns"]) is str and first["monotonic_ns"].isdigit())
                    inside = int(a["monotonic_ns"]) <= int(first["monotonic_ns"]) <= int(b["monotonic_ns"])
                    if "monotonic_ns" in last:
                        _assert(type(last["monotonic_ns"]) is str and last["monotonic_ns"].isdigit() and int(first["monotonic_ns"]) <= int(last["monotonic_ns"]))
                else:
                    inside = _seconds(a["started_at_utc"]) <= start <= _seconds(b["observed_at_utc"])
                if inside:
                    matching.append((exchange, request, response, operation))
            _assert(len(matching) == 1)
            exchange, mcp_request, mcp_response, operation = matching[0]
            if first.get("raw") in (None, ""):
                if first.get("raw") == "":
                    _bytes(first, True)
                _assert(first.get("json") is None)
                if first.get("raw") is None:
                    _assert(first.get("sha256") is None)
                card = _native_messages(last)[0]
                for interface in card.get("supportedInterfaces", []):
                    if type(interface) is dict and interface.get("protocolBinding") == "JSONRPC" and interface.get("protocolVersion") == "1.0":
                        cards.add(interface.get("url"))
                continue
            request = _body(first, response=True)
            messages = _native_messages(last)
            _assert(type(request) is dict and request.get("jsonrpc") == "2.0" and type(request.get("id")) in (str, int))
            key = (type(request["id"]), request["id"])
            _assert(key not in rpc_ids)
            rpc_ids.add(key)
            for message in messages:
                _assert(type(message) is dict and message.get("jsonrpc") == "2.0" and _equal(message.get("id"), request["id"]))
                _assert("result" in message and "error" not in message)
            method = request.get("method")
            _assert(method in {"SendMessage", "SendStreamingMessage", "GetTask"})
            params = request.get("params", {})
            _assert(type(params) is dict)
            arguments = mcp_request.get("params", {}).get("arguments", {})
            raw = operation in {"a2a_request/SendMessage", "a2a_request/GetTask"}
            if raw:
                _assert(method == arguments["method"] and _equal(params, arguments.get("params", {})))
                _assert(len(messages) == 1 and _equal(messages[0], _raw_rpc(mcp_response["result"])))
            elif method == "GetTask":
                _assert(operation in {"a2a_get_task", "tasks/get", "tasks/update"})
            else:
                _assert(operation in {"a2a_send_message", "tasks/update"})
                if operation == "a2a_send_message":
                    answer = arguments.get("text")
                else:
                    forms = mcp_request.get("params", {}).get("inputResponses", {})
                    answers = [value for form in forms.values() for value in form.get("content", {}).values()]
                    _assert(len(answers) == 1)
                    answer = answers[0]
                parts = params.get("message", {}).get("parts", [])
                _assert(type(answer) is str and [p.get("text") for p in parts if type(p) is dict and "text" in p] == [answer])
            headers = _headers(first.get("headers", {}))
            version = headers.get("a2a-version")
            _assert(version == "1.0" or (version is None and raw and first.get("url") in cards))
            calls.setdefault(exchange["exchange_id"], []).append(method)
            native_views = _native_task(messages, method)
            projected = public.get(exchange["exchange_id"], {})
            message_params = params.get("message", {})
            _assert(type(message_params) is dict)
            target = params.get("id") if method == "GetTask" else message_params.get("taskId")
            if route == "mgcrea_mcp_a2a" and not raw:
                if "task_id" in arguments:
                    _assert(_equal(target, arguments["task_id"]))
                if "context_id" in arguments and method != "GetTask":
                    _assert(_equal(message_params.get("contextId"), arguments["context_id"]))
            for task_view in native_views:
                task = task_view.get("id", task_view.get("taskId"))
                context = task_view.get("contextId")
                if not (_string(task) and _string(context)):
                    _assert(method != "GetTask")
                    continue
                observed = True
                _assert(target in (None, "", task))
                _assert(message_params.get("contextId") in (None, "", context))
                public_task = projected.get("returned_task_reference")
                public_context = projected.get("returned_context_reference")
                if route == "mgcrea_mcp_a2a":
                    if public_task is not None:
                        _assert(_equal(public_task, task))
                    if public_context is not None:
                        _assert(_equal(public_context, context))
                else:
                    if _string(public_task):
                        _assert(public_task not in handles or handles[public_task] == task)
                        handles[public_task] = task
                    if _string(public_context):
                        _assert(public_context not in contexts or contexts[public_context] == context)
                        contexts[public_context] = context
                # A later native snapshot cannot retroactively back a different
                # public status; Sends with streams compare only disclosed seed.
                status = _native_state(task_view, route)
                if method != "SendStreamingMessage" and "status" in projected:
                    _assert(_equal(projected["status"], status))
            if method == "GetTask":
                _assert(bool(native_views))
            if route == "amirk_a2a_to_mcp" and operation is not None:
                requested = mcp_request.get("params", {}) if mcp_request["method"].startswith("tasks/") else arguments
                opaque = requested.get("taskId", requested.get("taskHandle"))
                if opaque in handles and target is not None:
                    _assert(target == handles[opaque])
                opaque_context = requested.get("contextHandle")
                if opaque_context in contexts and "contextId" in message_params:
                    _assert(message_params["contextId"] == contexts[opaque_context])
                nested = mcp_response.get("result", {})
                if mcp_request["method"] == "tasks/get" and type(nested.get("result")) is dict:
                    nested = nested["result"]
                for block in nested.get("content", []):
                    _assert(type(block) is dict)
                    metadata = block.get("_meta", {})
                    if type(metadata) is not dict:
                        continue
                    origin = metadata.get("io.github.amirk-s/a2a", {})
                    if type(origin) is dict:
                        if "taskId" in origin and native_views:
                            _assert(origin["taskId"] == native_views[0].get("id", native_views[0].get("taskId")))
                        if "contextId" in origin and native_views:
                            _assert(origin["contextId"] == native_views[0].get("contextId"))
        _assert(observed)
        for exchange, request, _, operation in pairs:
            if operation in {"a2a_request/GetTask", "a2a_request/SendMessage"}:
                _assert(operation.split("/")[1] in calls.get(exchange["exchange_id"], []))
            elif operation == "a2a_get_task":
                refreshed = route == "amirk_a2a_to_mcp" or request.get("params", {}).get("arguments", {}).get("refresh") is True
                _assert(("GetTask" in calls.get(exchange["exchange_id"], [])) == refreshed)
            elif operation == "a2a_send_message":
                _assert(any(method in {"SendMessage", "SendStreamingMessage"} for method in calls.get(exchange["exchange_id"], [])))
        return True
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, AttributeError, RecursionError):
        return False
