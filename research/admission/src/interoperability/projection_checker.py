"""Independent review of a *historical* MCP wire projection.

This module imports no projector, baseline, extractor or finite-model helper.
It reads literal MCP bytes and checks the claimed states and serial graph. A
True return establishes agreement with the supplied recorded evidence only;
it is neither task admission nor independent human review.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any


_PINS = {
    "amirk_a2a_to_mcp": "58eff9da469bccdc432bf164662727947de646b4",
    "mgcrea_mcp_a2a": "c4d9d3c57c1746abbf9f6aadd3a9912d464eb1f5",
}
_PROJECTION_FIELDS = {
    "schema_version", "source_trace_sha256", "config", "analysis_clock",
    "initial_exchange_id", "events", "manifest",
}
_EVENT_FIELDS = {
    "state_id", "exchange_id", "request_method", "operation",
    "response_sha256", "evidence_source", "observable_fields",
}
_MANIFEST_FIELDS = {
    "schema_version", "id", "route", "provenance", "horizon", "evidence",
    "initial", "states", "transitions", "runtime_contract",
}
_NATIVE_TO_ORDINARY_STATUS = {
    "TASK_STATE_SUBMITTED": "working", "TASK_STATE_WORKING": "working",
    "TASK_STATE_INPUT_REQUIRED": "input_required", "TASK_STATE_COMPLETED": "completed",
    "TASK_STATE_CANCELED": "cancelled", "TASK_STATE_FAILED": "failed",
    "TASK_STATE_REJECTED": "failed", "TASK_STATE_AUTH_REQUIRED": "failed",
    "TASK_STATE_UNSPECIFIED": "failed",
}


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _plain_string(value: Any) -> bool:
    return type(value) is str and bool(value)


def _same_json(left: Any, right: Any) -> bool:
    """JSON equality including bool/int and null/missing distinctions."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (set(left) == set(right)
                and all(_same_json(left[key], right[key]) for key in left))
    if type(left) is list:
        return (len(left) == len(right)
                and all(_same_json(a, b) for a, b in zip(left, right)))
    return left == right


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("non-JSON numeric constant: " + value)


def _parse(raw: str) -> Any:
    _need(type(raw) is str, "raw JSON is not text")
    raw.encode("utf-8", errors="strict")
    return json.loads(raw, object_pairs_hook=_strict_object,
                      parse_constant=_invalid_constant)


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _instant(value: Any) -> float:
    _need(_plain_string(value), "observation time is missing")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _need(stamp.tzinfo is not None, "observation time has no timezone")
    _need(stamp.utcoffset() == timezone.utc.utcoffset(stamp),
          "observation time is not UTC")
    return stamp.timestamp()


def _body(record: Any, *, response: bool) -> Any:
    _need(type(record) is dict, "wire body record is missing")
    parsed = _parse(record.get("raw"))
    _need("json" in record and _same_json(parsed, record["json"]),
          "raw and parsed JSON differ")
    if response or "sha256" in record:
        digest = hashlib.sha256(record["raw"].encode("utf-8")).hexdigest()
        _need(record.get("sha256") == digest, "raw body hash mismatch")
    return parsed


def _scope(record: dict[str, Any], trace: dict[str, Any]) -> None:
    # Explicit execution markers must agree. Absence is not invented provenance.
    for field in ("run_id", "route_id", "source_commit"):
        if field in record:
            _need(record[field] == trace[field], "cross-run or source marker")


def _wire(trace: Any) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    _need(type(trace) is dict, "trace is not an object")
    _need(trace.get("schema_version") == "runtime-wire-observation/1",
          "unsupported runtime trace")
    _need(_plain_string(trace.get("run_id")), "run id is missing")
    route = trace.get("route_id")
    _need(route in _PINS, "unrecognized pinned route")
    _need(trace.get("source_commit") == _PINS[route], "source pin mismatch")
    _need(type(trace.get("protocol")) is dict, "protocol record is missing")
    _need(type(trace.get("provenance")) is dict, "provenance record is missing")
    exchanges = trace.get("exchanges")
    _need(type(exchanges) is list and len(exchanges) > 0, "no wire exchanges")
    request_ids: set[tuple[type, Any]] = set()
    exchange_ids: set[str] = set()
    previous_end = -math.inf
    pairs = []
    previous_mono: int | None = None
    for exchange in exchanges:
        _need(type(exchange) is dict, "exchange is not an object")
        _scope(exchange, trace)
        identifier = exchange.get("exchange_id")
        _need(_plain_string(identifier) and identifier not in exchange_ids,
              "missing or duplicate exchange id")
        exchange_ids.add(identifier)
        request_record = exchange.get("request")
        request = _body(request_record, response=False)
        _need(type(request) is dict and request.get("jsonrpc") == "2.0",
              "request is not JSON-RPC 2.0")
        _scope(request_record, trace)
        _scope(request, trace)
        _need(_plain_string(request.get("method")), "request method is missing")
        start = _instant(request_record.get("started_at_utc"))
        _need(start >= previous_end, "overlapping or reversed MCP intervals")
        request_id = request.get("id")
        if "id" in request:
            _need(type(request_id) in (str, int), "invalid JSON-RPC request id")
            key = (type(request_id), request_id)
            _need(key not in request_ids, "duplicate JSON-RPC request id")
            request_ids.add(key)
        response_record = exchange.get("response")
        if response_record is None:
            # Unpaired observations are source evidence, not modeled successes.
            previous_end = start
            continue
        response = _body(response_record, response=True)
        _scope(response_record, trace)
        _need(type(response) is dict and response.get("jsonrpc") == "2.0",
              "response is not JSON-RPC 2.0")
        _scope(response, trace)
        end = _instant(response_record.get("observed_at_utc"))
        _need(start <= end, "response precedes request")
        previous_end = end
        elapsed = exchange.get("elapsed_ms")
        _need(type(elapsed) in (float, int) and math.isfinite(elapsed) and elapsed >= 0,
              "invalid measured elapsed time")
        if "monotonic_ns" in request_record or "monotonic_ns" in response_record:
            _need("monotonic_ns" in request_record and "monotonic_ns" in response_record,
                  "incomplete monotonic interval")
            first, last = request_record["monotonic_ns"], response_record["monotonic_ns"]
            _need(type(first) is str and first.isdigit() and type(last) is str and last.isdigit(),
                  "invalid monotonic interval")
            start_mono, end_mono = int(first), int(last)
            _need(start_mono <= end_mono and
                  (previous_mono is None or start_mono >= previous_mono),
                  "overlapping monotonic MCP intervals")
            _need(abs(elapsed - (end_mono - start_mono) / 1_000_000) < 0.001,
                  "elapsed time differs from measured interval")
            previous_mono = end_mono
        if "id" not in request:
            _need("id" not in response, "notification paired with a reply")
            continue
        _need("id" in response and _same_json(request_id, response["id"]),
              "JSON-RPC correlation mismatch")
        _need(("result" in response) != ("error" in response),
              "reply must have exactly one of result and error")
        if "error" in response:
            _need(_operation(request) is None, "task operation error requires a recovery model")
            continue
        result = response["result"]
        if type(result) is dict and result.get("isError") is True:
            _need(_operation(request) is None, "task tool error requires a recovery model")
            continue
        if "status" in response_record:
            status = response_record["status"]
            _need(type(status) is int, "invalid HTTP status")
            if not 200 <= status < 300:
                _need(_operation(request) is None, "task HTTP error requires a recovery model")
                continue
        pairs.append((exchange, request, response))
    return pairs


def _mgcrea_payload(result: Any) -> dict[str, Any]:
    _need(type(result) is dict, "tool result is not an object")
    structured = result.get("structuredContent")
    content = result.get("content", [])
    payloads = []
    if type(content) is list:
        for block in content:
            if type(block) is dict and block.get("type") == "text":
                raw = block.get("text")
                if type(raw) is str and raw.lstrip().startswith("{"):
                    decoded = _parse(raw)
                    if type(decoded) is dict:
                        payloads.append(decoded)
    if type(structured) is dict:
        _need(all(_same_json(structured, item) for item in payloads),
              "structured/text task data disagree")
        return structured
    _need(len(payloads) == 1, "ambiguous or missing mgcrea JSON tool payload")
    return payloads[0]


def _operation(request: dict[str, Any]) -> str | None:
    method = request["method"]
    if method in {"tasks/get", "tasks/update"}:
        return method
    if method == "tools/call":
        params = request.get("params")
        if type(params) is dict and params.get("name") in {"a2a_send_message", "a2a_get_task"}:
            return params["name"]
    return None


def _literal_view(route: str, request: dict[str, Any], response: dict[str, Any],
                  expected: str) -> tuple[dict[str, Any], bool]:
    """Read only supported, explicit public field paths; no aliases or history."""
    values: dict[str, Any] = {}
    result = response["result"]
    _need(type(result) is dict, "task-related result is not an object")
    ordinary = False
    if route == "mgcrea_mcp_a2a":
        payload = _mgcrea_payload(result)
        task = payload.get("task", payload)
        _need(type(task) is dict, "mgcrea task payload is not an object")
        for raw_field, field in (("id", "returned_task_reference"),
                                 ("context_id", "returned_context_reference"),
                                 ("state", "status")):
            if raw_field in task:
                values[field] = task[raw_field]
        ordinary = True
        if "artifacts" in task:
            artifacts = task["artifacts"]
            _need(type(artifacts) is list, "artifact body is not a list")
            _need(all(type(a) is dict for a in artifacts), "malformed artifact descriptor")
            if any(type(a.get("text")) is str and expected in a["text"] for a in artifacts):
                values["artifact_contains_expected"] = True
            elif len(artifacts) == 0 or all(type(a.get("text")) is str for a in artifacts):
                values["artifact_contains_expected"] = False
    else:
        envelope = result.get("structuredContent")
        if request["method"] == "tasks/get" and type(result.get("result")) is dict:
            outer = result
            result = result["result"]
            _need(result.get("isError") is not True, "nested task tool error requires a recovery model")
            envelope = result.get("structuredContent")
            if type(envelope) is dict:
                for outer_field, inner_field in (("taskId", "taskHandle"),):
                    if outer_field in outer and inner_field in envelope:
                        _need(_same_json(outer[outer_field], envelope[inner_field]),
                              "nested Tasks result contradicts outer task record")
        if type(envelope) is dict and envelope.get("kind") == "task":
            ordinary = request["method"] == "tools/call"
            a2a_state = envelope.get("a2aState")
            if type(a2a_state) is str and a2a_state in _NATIVE_TO_ORDINARY_STATUS and "status" in envelope:
                _need(envelope["status"] == _NATIVE_TO_ORDINARY_STATUS[a2a_state],
                      "ordinary status contradicts disclosed A2A state")
            for raw_field, field in (("taskHandle", "returned_task_reference"),
                                     ("contextHandle", "returned_context_reference"),
                                     ("status", "status")):
                if raw_field in envelope:
                    values[field] = envelope[raw_field]
            if "status" not in envelope and "a2aState" in envelope:
                a2a = envelope["a2aState"]
                _need(type(a2a) is str, "A2A status is not a string")
                values["status"] = a2a.removeprefix("TASK_STATE_").lower()
            if "artifacts" in envelope:
                refs = envelope["artifacts"]
                _need(type(refs) is list, "artifact refs are not a list")
                _need(all(type(ref) is dict and _plain_string(ref.get("artifactId")) for ref in refs),
                      "invalid public artifact reference")
                ids = {ref["artifactId"] for ref in refs}
                _need(len(ids) == len(refs), "duplicate artifact reference")
                blocks = result.get("content", [])
                _need(type(blocks) is list, "content blocks are not a list")
                visible = []
                observed_ids = set()
                for block in blocks:
                    if type(block) is not dict:
                        continue
                    metadata = block.get("_meta", {})
                    if type(metadata) is not dict:
                        continue
                    origin = metadata.get("io.github.amirk-s/a2a", {})
                    if type(origin) is not dict or origin.get("artifactId") not in ids:
                        continue
                    if block.get("type") == "text" and type(block.get("text")) is str:
                        visible.append(block["text"])
                        observed_ids.add(origin["artifactId"])
                if any(expected in item for item in visible):
                    values["artifact_contains_expected"] = True
                elif not ids or observed_ids == ids:
                    values["artifact_contains_expected"] = False
        else:
            # Modern Tasks has different returned observables from ordinary tools.
            for raw_field, field in (("taskId", "returned_task_reference"), ("status", "status")):
                if raw_field in result:
                    if raw_field == "status" and result[raw_field] == "completed":
                        # Modern completion establishes result delivery. Without
                        # its ordinary result it does not establish A2A success.
                        continue
                    values[field] = result[raw_field]
    _need(all(type(value) in (str, int, bool, type(None)) for value in values.values()),
          "observable value is not a finite-model scalar")
    return values, ordinary


def _target(request: dict[str, Any], operation: str, route: str,
            required_task: str, required_context: str, initial: bool) -> bool:
    params = request.get("params", {})
    _need(type(params) is dict, "task params are not an object")
    if request["method"] == "tools/call":
        params = params.get("arguments", {})
        _need(type(params) is dict, "tool arguments are not an object")
    task_key = "taskId" if request["method"].startswith("tasks/") else (
        "taskHandle" if route == "amirk_a2a_to_mcp" else "task_id")
    context_key = "contextHandle" if route == "amirk_a2a_to_mcp" else "context_id"
    if task_key not in params:
        valid = initial and operation == "a2a_send_message"
    else:
        valid = _same_json(params[task_key], required_task)
    if context_key in params:
        valid = valid and _same_json(params[context_key], required_context)
    return valid


def _source(route: str, request: dict[str, Any], operation: str) -> str:
    """Configuration tag, not a claim of native-peer authority."""
    if operation in {"tasks/update", "tasks/get"}:
        return "extension-observation"
    if operation == "a2a_send_message":
        return "send-acknowledgement"
    if route == "mgcrea_mcp_a2a":
        args = request.get("params", {}).get("arguments", {})
        return "peer-refreshed" if args.get("refresh") is True else "local-mirror"
    return "peer-refreshed"


def check_projection(trace: Any, projection: Any) -> bool:
    """Return whether every claimed historical state/edge follows raw MCP data.

    Malformed bytes or unsupported projection claims return False. A faithful
    partial projection can return True while its finite evaluation is unknown.
    Evaluator-private native records are checked by ``check_native_sidecar``;
    they never supply a missing public observable here.
    """
    try:
        pairs = _wire(trace)
        _need(type(projection) is dict and set(projection) == _PROJECTION_FIELDS,
              "projection fields differ")
        _need(projection["schema_version"] == "observed-trace-projection/0",
              "unsupported projection")
        digest = _canonical_digest(trace)
        _need(projection["source_trace_sha256"] == digest, "source digest differs")
        config = projection["config"]
        _need(type(config) is dict and set(config) == {"expected_artifact_text"},
              "invalid projection configuration")
        expected = config["expected_artifact_text"]
        _need(_plain_string(expected), "expected artifact text is missing")
        route = trace["route_id"]
        candidates = []
        for exchange, request, response in pairs:
            operation = _operation(request)
            if operation is not None:
                view, ordinary = _literal_view(route, request, response, expected)
                candidates.append((exchange, request, operation, view, ordinary))
        first = next((index for index, (_, _, _, view, ordinary) in enumerate(candidates)
                      if ordinary and _plain_string(view.get("returned_task_reference"))
                      and _plain_string(view.get("returned_context_reference"))), None)
        _need(first is not None, "no complete ordinary public task view")
        candidates = candidates[first:]
        prefix_position = next(index for index, exchange in enumerate(trace["exchanges"])
                               if exchange["exchange_id"] == candidates[0][0]["exchange_id"])
        for exchange in trace["exchanges"][prefix_position:]:
            request = exchange["request"]["json"]
            cancel = request["method"] == "tasks/cancel"
            if request["method"] == "tools/call":
                params = request.get("params", {})
                cancel = type(params) is dict and params.get("name") == "a2a_cancel_task"
            _need(not cancel, "cancellation requires a separately specified historical model")
        required_task = candidates[0][3]["returned_task_reference"]
        required_context = candidates[0][3]["returned_context_reference"]
        _need(projection["initial_exchange_id"] == candidates[0][0]["exchange_id"],
              "initial view is not the earliest public task view")
        clock = math.ceil(max(_instant(exchange["response"]["observed_at_utc"])
                              for exchange in trace["exchanges"]
                              if exchange.get("response") is not None))
        _need(type(projection["analysis_clock"]) is int and projection["analysis_clock"] == clock,
              "archival analysis clock differs")
        events = projection["events"]
        _need(type(events) is list and len(events) == len(candidates), "event sequence differs")
        namespace = "bridge-handle" if route == "amirk_a2a_to_mcp" else "public-native-a2a-id"
        states = {}
        ids = []
        for index, (event, (exchange, request, operation, view, _)) in enumerate(zip(events, candidates)):
            _need(type(event) is dict and set(event) == _EVENT_FIELDS, "event fields differ")
            exchange_id = exchange["exchange_id"]
            state_id = trace["run_id"] + "::" + exchange_id
            _need(event["exchange_id"] == exchange_id and event["state_id"] == state_id,
                  "event does not name its exact source exchange/run")
            _need(event["request_method"] == request["method"] and event["operation"] == operation,
                  "event request operation differs")
            _need(event["response_sha256"] == exchange["response"]["sha256"],
                  "event response hash differs")
            _need(event["evidence_source"] == _source(route, request, operation), "read-source tag differs")
            observables = dict(view)
            observables.update(task_namespace=namespace,
                               request_target_valid=_target(request, operation, route, required_task,
                                                            required_context, index == 0),
                               required_task_reference=required_task,
                               required_context_reference=required_context)
            _need(_same_json(event["observable_fields"], observables), "observable claims differ from raw MCP")
            states[state_id] = observables
            ids.append(state_id)
        manifest = projection["manifest"]
        _need(type(manifest) is dict and set(manifest) == _MANIFEST_FIELDS, "manifest fields differ")
        fixed = {
            "schema_version": "finite-continuation/1", "id": trace["run_id"] + ":historical",
            "route": route + " historical observation",
            "provenance": {"kind": "wire-derived", "source": "runtime-wire-observation/1:" + digest,
                           "review_status": "AI-authored projection; human review pending"},
            "horizon": len(ids) - 1,
            "evidence": {"complete": False, "observed_at": clock, "valid_until": clock},
            "initial": ids[0], "states": states,
            "transitions": [{"id": "edge:" + event["exchange_id"], "source": ids[index - 1],
                             "target": ids[index], "operation": event["operation"]}
                            for index, event in enumerate(events) if index > 0],
            "runtime_contract": {
                "goal": [{"field": "status", "op": "eq", "value": "completed"},
                         {"field": "returned_task_reference", "op": "eq_field", "other_field": "required_task_reference"},
                         {"field": "returned_context_reference", "op": "eq_field", "other_field": "required_context_reference"},
                         {"field": "artifact_contains_expected", "op": "eq", "value": True}],
                "invariants": [{"field": "request_target_valid", "op": "eq", "value": True},
                               {"field": "task_namespace", "op": "eq", "value": namespace}],
            },
        }
        _need(0 <= fixed["horizon"] <= 64, "observed horizon exceeds finite-v1")
        _need(_same_json(manifest, fixed), "finite graph/contract lacks exact wire backing")
        return True
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, StopIteration, AttributeError):
        return False


def _native_messages(record: dict[str, Any]) -> list[Any]:
    """Decode exact JSON bodies or SSE data without mixing their byte hashes."""
    raw = record.get("raw")
    _need(type(raw) is str, "native response body is missing")
    _need(record.get("sha256") == hashlib.sha256(raw.encode("utf-8")).hexdigest(),
          "native raw hash mismatch")
    if record.get("json") is not None:
        decoded = _parse(raw)
        _need(_same_json(decoded, record["json"]), "native raw/parsed JSON differ")
        return [decoded]
    # JSON null and an SSE body have distinct meanings; only declared SSE can
    # use event framing. Comments and event-name lines carry no JSON-RPC reply.
    headers = record.get("headers", {})
    _need(type(headers) is dict and "text/event-stream" in headers.get("content-type", ""),
          "null parsed native body is not declared SSE")
    result = []
    data: list[str] = []
    for line in raw.replace("\r\n", "\n").split("\n") + [""]:
        if line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
        elif not line and data:
            result.append(_parse("\n".join(data)))
            data = []
    _need(len(result) > 0, "native SSE has no observed JSON data")
    return result


def _native_views(messages: list[Any]) -> list[dict[str, Any]]:
    views = []
    for message in messages:
        if type(message) is not dict or type(message.get("result")) is not dict:
            continue
        result = message["result"]
        if type(result.get("task")) is dict:
            views.append(result["task"])
        elif "id" in result and "status" in result:
            views.append(result)
        for kind in ("statusUpdate", "artifactUpdate"):
            if type(result.get(kind)) is dict:
                views.append(result[kind])
    return views


def _native_identity(view: dict[str, Any]) -> tuple[Any, Any]:
    return view.get("id", view.get("taskId")), view.get("contextId")


def _native_artifacts(views: list[dict[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for view in views:
        artifacts = view.get("artifacts", [])
        if "artifact" in view:
            artifacts = artifacts + [view["artifact"]]
        _need(type(artifacts) is list, "native artifacts are not a list")
        for artifact in artifacts:
            _need(type(artifact) is dict, "native artifact is not an object")
            identifier = artifact.get("artifactId")
            _need(_plain_string(identifier), "native artifact id is missing")
            parts = artifact.get("parts", [])
            _need(type(parts) is list, "native artifact parts are not a list")
            texts = []
            for part in parts:
                if type(part) is not dict:
                    continue
                if type(part.get("text")) is str:
                    texts.append(part["text"])
                content = part.get("content")
                if type(content) is dict and content.get("$case") == "text":
                    _need(type(content.get("value")) is str, "native text part is malformed")
                    texts.append(content["value"])
            result[identifier] = texts
    return result


def check_native_sidecar(trace: Any, records: Any) -> bool:
    """Privately check native IDs, byte hashes and MCP interval correlation.

    ``records`` is the explicitly loaded JSONL record list including its first
    metadata line. No files, endpoints or environment state are accessed. SSE
    completion may occur after its MCP acknowledgement; request start and
    response-header reception is retained even when it follows an asynchronous
    acknowledgement. Request initiation must identify one MCP interval. This
    checks the recorded single-task development execution, not future truth.
    """
    try:
        paired = _wire(trace)
        _need(type(records) is list and len(records) > 1, "native records are missing")
        meta = records[0]
        _need(type(meta) is dict and meta.get("schema_version") == "private-native-http/1",
              "native metadata is missing")
        _need(meta.get("run_id") == trace["run_id"] and meta.get("route_id") == trace["route_id"],
              "native sidecar belongs to a different execution")
        intervals = []
        for exchange, request, response in paired:
            first = exchange["request"]
            last = exchange["response"]
            intervals.append((exchange, request, response, first, last))
        native_ids: set[str] = set()
        rpc_ids: set[tuple[type, Any]] = set()
        public_to_native: dict[str, tuple[str, str]] = {}
        observed_task: tuple[str, str] | None = None
        native_queries: dict[str, list[str]] = {}
        for record in records[1:]:
            _need(type(record) is dict and record.get("role") == "native_peer_response",
                  "unrecognized private native record")
            _scope(record, trace)
            identifier = record.get("exchange_id")
            _need(_plain_string(identifier) and identifier not in native_ids, "duplicate native exchange id")
            native_ids.add(identifier)
            first, last = record.get("request"), record.get("response")
            _need(type(first) is dict and type(last) is dict, "native HTTP interval is missing")
            start = _instant(first.get("started_at_utc"))
            headers = _instant(last.get("headers_observed_at_utc"))
            finish = _instant(last.get("observed_at_utc"))
            _need(start <= headers <= finish, "reversed native HTTP times")
            _need(type(last.get("status")) is int, "native HTTP status is missing")
            if first.get("raw") is None:
                _need(first.get("json") is None and first.get("sha256") is None,
                      "absent native request body has parsed data/hash")
                request = None
            else:
                request = _body(first, response=True)
            messages = _native_messages(last)
            matching = []
            for exchange, mcp_request, mcp_response, mcp_start, mcp_end in intervals:
                if all("monotonic_ns" in item for item in (first, mcp_start, mcp_end)) and "headers_monotonic_ns" in last:
                    a, b = int(first["monotonic_ns"]), int(last["headers_monotonic_ns"])
                    inside = int(mcp_start["monotonic_ns"]) <= a <= int(mcp_end["monotonic_ns"])
                    _need(a <= b, "native headers precede request initiation")
                else:
                    inside = (_instant(mcp_start["started_at_utc"]) <= start
                              <= _instant(mcp_end["observed_at_utc"]))
                if inside:
                    matching.append((exchange, mcp_request, mcp_response))
            _need(len(matching) == 1, "native request initiation has no unique MCP correlation")
            exchange, mcp_request, mcp_response = matching[0]
            if type(request) is not dict or "method" not in request:
                continue  # Native HTTP discovery is not a JSON-RPC task reply.
            _need(request.get("jsonrpc") == "2.0" and type(request.get("id")) in (int, str),
                  "invalid native JSON-RPC request")
            key = (type(request["id"]), request["id"])
            _need(key not in rpc_ids, "duplicate native request id")
            rpc_ids.add(key)
            for message in messages:
                _need(type(message) is dict and message.get("jsonrpc") == "2.0",
                      "invalid native JSON-RPC response")
                _need("id" in message and _same_json(request["id"], message["id"]),
                      "native JSON-RPC correlation differs")
                _need(("result" in message) != ("error" in message), "ambiguous native reply")
            method = request["method"]
            # Confirm the actual dispatched request matches the MCP operation.
            # A streaming header/body may arrive during a later read; that read
            # did not dispatch this continuation and does not cause advancement.
            operation = _operation(mcp_request)
            if method == "GetTask":
                _need(operation in {"a2a_get_task", "tasks/get", "tasks/update"},
                      "native task read is correlated to an unrelated MCP call")
            if method in {"SendMessage", "SendStreamingMessage"}:
                _need(operation in {"a2a_send_message", "tasks/update"},
                      "native send is correlated to an unrelated MCP call")
                params = mcp_request.get("params", {})
                if operation == "a2a_send_message":
                    answer = params.get("arguments", {}).get("text")
                else:
                    answer = params.get("inputResponses", {}).get("answer", {}).get("content", {}).get("answer")
                native_parts = request.get("params", {}).get("message", {}).get("parts", [])
                native_text = [part.get("text") for part in native_parts if type(part) is dict and "text" in part]
                _need(type(answer) is str and native_text == [answer],
                      "native dispatched text differs from the actual MCP request")
            native_queries.setdefault(exchange["exchange_id"], []).append(method)
            views = _native_views(messages)
            native_params = request.get("params", {})
            _need(type(native_params) is dict, "native params are not an object")
            native_message = native_params.get("message", {})
            _need(type(native_message) is dict, "native message is not an object")
            native_target = native_params.get("id") if method == "GetTask" else native_message.get("taskId")
            if observed_task is not None:
                if native_target is not None:
                    _need(native_target == observed_task[0], "native request switches underlying task")
                if "contextId" in native_message:
                    _need(native_message["contextId"] == observed_task[1], "native request switches underlying context")
            if method == "GetTask":
                public_result = mcp_response["result"]
                represented_failure = (mcp_request["method"] == "tasks/get"
                                       and public_result.get("status") == "failed"
                                       and type(public_result.get("error")) is dict)
                represented_ack = mcp_request["method"] == "tasks/update"
                if any("error" in message for message in messages):
                    _need(represented_failure or represented_ack,
                          "native GetTask error cannot back a successful ordinary task reply")
                _need(bool(views) or represented_failure or represented_ack,
                      "native GetTask lacks a disclosed task snapshot")
            identities = [_native_identity(view) for view in views]
            identities = [(task, context) for task, context in identities
                          if _plain_string(task) and _plain_string(context)]
            if identities:
                _need(all(identity == identities[0] for identity in identities),
                      "native stream changes task or context")
                identity = identities[0]
                if observed_task is None:
                    observed_task = identity
                _need(identity == observed_task, "native execution switches underlying task/context")
                params = request.get("params", {})
                _need(type(params) is dict, "native params are not an object")
                message = params.get("message", {})
                _need(type(message) is dict, "native message is not an object")
                target = params.get("id") if method == "GetTask" else message.get("taskId")
                if target is not None:
                    _need(target == identity[0], "native request targets another task")
                if "contextId" in message:
                    _need(message["contextId"] == identity[1], "native request targets another context")
                result = mcp_response["result"]
                if trace["route_id"] == "mgcrea_mcp_a2a":
                    public = _mgcrea_payload(result)
                    public = public.get("task", public)
                    _need(type(public) is dict, "public task payload is not an object")
                    for field, actual in (("id", identity[0]), ("context_id", identity[1])):
                        if field in public:
                            _need(public[field] == actual, "public/native task identity differs")
                else:
                    public_task = result.get("taskId")
                    if mcp_request["method"] == "tasks/get" and type(result.get("result")) is dict:
                        result = result["result"]
                    envelope = result.get("structuredContent", {})
                    if type(envelope) is dict and "taskHandle" in envelope:
                        public_task = envelope["taskHandle"]
                    if _plain_string(public_task):
                        _need(public_to_native.get(public_task, identity) == identity,
                              "one opaque handle maps to multiple native identities")
                        public_to_native[public_task] = identity
                    for block in result.get("content", []):
                        if type(block) is not dict:
                            continue
                        origin = block.get("_meta", {}).get("io.github.amirk-s/a2a", {})
                        for field, actual in (("taskId", identity[0]), ("contextId", identity[1])):
                            if field in origin:
                                _need(origin[field] == actual, "public native metadata differs")
                artifacts = _native_artifacts(views)
                # Exact final artifact text must remain artifact text on both
                # sides. History and status messages never enter this comparison.
                if method == "GetTask":
                    native_status = views[0].get("status", {}).get("state")
                    if trace["route_id"] == "mgcrea_mcp_a2a":
                        public_artifacts = public.get("artifacts", [])
                        _need(type(public_artifacts) is list and all(type(a) is dict for a in public_artifacts),
                              "public artifact body is malformed")
                        _need({a.get("artifact_id") for a in public_artifacts} == set(artifacts),
                              "public/native artifact identity sets differ")
                        for artifact in public_artifacts:
                            native_text = artifacts.get(artifact.get("artifact_id"))
                            _need(native_text is not None and artifact.get("text") == "\n".join(native_text),
                                  "public/native artifact differs")
                        if type(native_status) is str and "state" in public:
                            _need(public["state"] == native_status.removeprefix("TASK_STATE_").lower(),
                                  "public/native task state differs")
                    else:
                        public_refs = envelope.get("artifacts", [])
                        _need(type(public_refs) is list and all(type(a) is dict for a in public_refs),
                              "public artifact references are malformed")
                        _need({a.get("artifactId") for a in public_refs} == set(artifacts),
                              "public/native artifact identity sets differ")
                        public_texts: dict[str, list[str]] = {identifier: [] for identifier in artifacts}
                        for block in result.get("content", []):
                            if type(block) is not dict or block.get("type") != "text":
                                continue
                            origin = block.get("_meta", {}).get("io.github.amirk-s/a2a", {})
                            if "artifactId" in origin:
                                _need(block.get("text") in artifacts.get(origin["artifactId"], []),
                                      "public/native artifact text differs")
                                public_texts[origin["artifactId"]].append(block["text"])
                        _need(public_texts == artifacts, "public/native artifact part lists differ")
                        if type(native_status) is str:
                            if "a2aState" in envelope:
                                _need(envelope["a2aState"] == native_status, "public/native A2A state differs")
                            if "status" in envelope and native_status in _NATIVE_TO_ORDINARY_STATUS:
                                _need(envelope["status"] == _NATIVE_TO_ORDINARY_STATUS[native_status],
                                      "public/native ordinary task status differs")
        _need(observed_task is not None, "no native task/context evidence")
        for exchange, request, response in paired:
            operation = _operation(request)
            if operation != "a2a_get_task":
                continue
            args = request.get("params", {}).get("arguments", {})
            methods = native_queries.get(exchange["exchange_id"], [])
            if trace["route_id"] == "mgcrea_mcp_a2a" and args.get("refresh") is not True:
                _need("GetTask" not in methods, "local-mirror read unexpectedly queries native peer")
            else:
                _need("GetTask" in methods, "peer-refreshed read lacks native GetTask evidence")
        return True
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, AttributeError):
        return False
