"""Independent checker of the three original Carol A2A 0.3 observations.

This checks a saved development record, not a bridge, future completion,
protocol conformance, model/source authenticity, or a novel method. The pure
checker does not read files or import the capture driver/application/solvers.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from urllib.parse import urlsplit


PIN = "6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3"
CONTROLS = (
    "N1_same_task_with_reference",
    "N2_same_task_without_reference",
    "N3_context_only_without_reference",
)
STATES = {"submitted", "working", "input-required", "completed", "canceled",
          "failed", "rejected", "auth-required", "unknown"}
SOURCE_FILES = {
    "README.md", "agent_Alice.py", "agent_Bob.py", "agent_Carol.py", "config.py",
    "requirements.txt", "utils/__init__.py", "utils/game_logic.py",
    "utils/helpers.py", "utils/protocol_wrappers.py", "utils/server.py",
}


def _require(condition):
    if not condition:
        raise ValueError("Saved native reference record violates the checking contract")


def _string(value):
    return isinstance(value, str) and bool(value)


def _integer(value):
    return type(value) is int and value >= 0


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _same(left, right):
    # JSON equality must not confuse True with 1 or False with 0.
    return json.dumps(left, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")) == json.dumps(
                          right, sort_keys=True, ensure_ascii=False,
                          allow_nan=False, separators=(",", ":"))


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


def _json(raw):
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_bad_constant)


def _base64(value):
    _require(isinstance(value, str))
    decoded = base64.b64decode(value, validate=True)
    _require(base64.b64encode(decoded).decode("ascii") == value)
    return decoded


def _body(record):
    _require(isinstance(record, dict) and isinstance(record["raw"], str))
    raw = _base64(record["raw_base64"])
    _require(raw.decode("utf-8") == record["raw"])
    _require(_hash(record["sha256"]) and hashlib.sha256(raw).hexdigest() == record["sha256"])
    value = _json(record["raw"])
    _require(_same(value, record["json"]))
    return value, len(raw)


def _time(value):
    _require(isinstance(value, str))
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed))
    return parsed


def _part(value):
    # The pinned Carol fragment sends and produces TextParts only.
    _require(isinstance(value, dict) and value.get("kind") == "text"
             and isinstance(value.get("text"), str))


def _message(value, *, user=False):
    _require(isinstance(value, dict) and value.get("kind") == "message")
    _require(value.get("role") == "user" if user else value.get("role") in {"user", "agent"})
    _require(_string(value.get("messageId")) and isinstance(value.get("parts"), list)
             and bool(value["parts"]))
    for part in value["parts"]:
        _part(part)
    for key in ("contextId", "taskId"):
        if key in value:
            _require(_string(value[key]))
    if "referenceTaskIds" in value:
        _require(isinstance(value["referenceTaskIds"], list)
                 and all(_string(item) for item in value["referenceTaskIds"]))


def _task(value):
    _require(isinstance(value, dict) and value.get("kind") == "task"
             and _string(value.get("id")) and _string(value.get("contextId")))
    status = value.get("status")
    _require(isinstance(status, dict) and status.get("state") in STATES)
    if "timestamp" in status:
        _time(status["timestamp"])
    if "message" in status and status["message"] is not None:
        _message(status["message"])
    if "history" in value and value["history"] is not None:
        _require(isinstance(value["history"], list))
        for message in value["history"]:
            _message(message)
    if "artifacts" in value and value["artifacts"] is not None:
        _require(isinstance(value["artifacts"], list))
        for artifact in value["artifacts"]:
            _require(isinstance(artifact, dict) and _string(artifact.get("artifactId"))
                     and isinstance(artifact.get("parts"), list) and bool(artifact["parts"]))
            for part in artifact["parts"]:
                _part(part)
    return value


def _bound(task, task_id, context_id, state=None):
    _task(task)
    _require(task["id"] == task_id and task["contextId"] == context_id)
    if state is not None:
        _require(task["status"]["state"] == state)


def _check(report):
    _require(isinstance(report, dict)
             and report.get("schema_version") == "native-reference-continuation/1"
             and report.get("mode") == "run" and report.get("outcome") == "observed"
             and type(report.get("exit_code")) is int and report["exit_code"] == 0
             and report.get("source_commit") == PIN
             and report.get("protocol") == "Original A2A 0.3.0 JSONRPC"
             and type(report.get("model_calls")) is int and report["model_calls"] == 0)
    hashes = report["original_source_sha256"]
    _require(isinstance(hashes, dict) and set(hashes) == SOURCE_FILES
             and all(_hash(value) for value in hashes.values())
             and report.get("original_source_unchanged_after_execution") is True)
    for key in ("installed_artifacts_sha256", "resolved_requirements_sha256"):
        _require(_hash(report.get(key)))
    specification = report["prospective_specification"]
    _require(isinstance(specification, dict) and _hash(specification.get("sha256"))
             and specification.get("path", "").replace("\\", "/")
             == "docs/research/reference-continuation-probe-v0.md")
    sdk_checks = [item for item in report["setup_attempts"]
                  if item.get("label") == "verify_original_SDK_imports"]
    _require(len(sdk_checks) == 1)
    sdk = sdk_checks[0]
    _require(type(sdk.get("exit_code")) is int and sdk["exit_code"] == 0)
    sdk_stdout = _base64(sdk["stdout_raw_base64"]).decode("utf-8")
    _require(sdk_stdout == sdk["stdout_text"] and sdk_stdout.splitlines() == ["0.3.0", "0.35.0"])

    endpoint = report["endpoint"]
    parsed_endpoint = urlsplit(endpoint)
    _require(parsed_endpoint.scheme == "http" and parsed_endpoint.hostname == "127.0.0.1"
             and parsed_endpoint.port is not None and not parsed_endpoint.path
             and not parsed_endpoint.query and not parsed_endpoint.fragment
             and parsed_endpoint.username is None and parsed_endpoint.password is None)
    started, completed = _time(report["started_at_utc"]), _time(report["completed_at_utc"])
    process = report["process"]
    _require(_integer(process.get("pid")) and process["pid"] > 0
             and process.get("terminal_verified") is True and type(process.get("exit_code")) is int)
    process_started, ready, cleaned = (_time(process[key]) for key in
                                      ("started_at_utc", "ready_at_utc", "cleanup_at_utc"))
    _require(started <= process_started <= ready <= cleaned <= completed)
    exchanges = report["http_exchanges"]
    _require(isinstance(exchanges, list) and len(exchanges) >= 14)
    seen, previous_utc, previous_ns = set(), ready, None
    requests_bytes = responses_bytes = 0
    checked = []
    for index, exchange in enumerate(exchanges):
        _require(isinstance(exchange, dict) and _string(exchange.get("exchange_id"))
                 and exchange["exchange_id"] not in seen and "error" not in exchange)
        seen.add(exchange["exchange_id"])
        _require(exchange.get("role") == "native-client-to-original-Carol"
                 and exchange.get("task_namespace") == "Original Carol A2A task UUID"
                 and exchange.get("context_namespace") == "Original Carol A2A context UUID"
                 and exchange.get("validity_interval") is None
                 and exchange.get("recipient_authority") is None)
        request, response = exchange["request"], exchange["response"]
        _require(isinstance(request, dict) and isinstance(response, dict)
                 and type(response.get("status")) is int and response["status"] == 200)
        began, ended = _time(request["started_at_utc"]), _time(response["observed_at_utc"])
        begin_ns, end_ns = request["monotonic_ns"], response["monotonic_ns"]
        _require(previous_utc <= began <= ended <= cleaned and _integer(begin_ns)
                 and _integer(end_ns) and begin_ns <= end_ns
                 and (previous_ns is None or previous_ns <= begin_ns))
        elapsed = exchange.get("elapsed_ms")
        _require(type(elapsed) in (int, float) and math.isfinite(elapsed)
                 and elapsed >= (end_ns - begin_ns) / 1e6)
        previous_utc, previous_ns = ended, end_ns
        payload, response_bytes = _body(response)
        responses_bytes += response_bytes
        source = exchange["source"]
        _require(isinstance(source, dict) and source.get("sample_commit") == PIN
                 and source.get("endpoint") == request.get("url"))
        if index == 0:
            _require(exchange.get("phase") == "agent_card"
                     and exchange.get("protocol") == "AgentCard HTTP discovery"
                     and request.get("url") == endpoint + "/.well-known/agent-card.json"
                     and request.get("http_method") == "GET"
                     and all(request.get(key) is None for key in ("raw", "raw_base64", "json", "sha256")))
            _require(isinstance(payload, dict) and payload.get("protocolVersion") == "0.3.0"
                     and payload.get("preferredTransport") == "JSONRPC"
                     and payload.get("name") == "AgentCarol"
                     and _same(payload, report["observed_card"]))
            card_url = urlsplit(payload["url"])
            _require(card_url.scheme == "http" and card_url.hostname in {"localhost", "127.0.0.1"}
                     and card_url.port == parsed_endpoint.port and card_url.path == "/a2a/v1"
                     and not card_url.query and not card_url.fragment)
            continue
        _require(exchange.get("protocol") == "A2A 0.3.0 JSONRPC"
                 and request.get("url") == endpoint + "/a2a/v1"
                 and request.get("http_method") == "POST")
        call, request_bytes = _body(request)
        requests_bytes += request_bytes
        _require(isinstance(call, dict) and call.get("jsonrpc") == "2.0"
                 and call.get("id") == exchange["exchange_id"]
                 and call.get("method") in {"message/send", "tasks/get"}
                 and isinstance(call.get("params"), dict)
                 and isinstance(payload, dict) and payload.get("jsonrpc") == "2.0"
                 and payload.get("id") == call["id"] and "error" not in payload)
        task = _task(payload["result"])
        if call["method"] == "message/send":
            _message(call["params"]["message"], user=True)
        else:
            _require(_string(call["params"].get("id")) and call["params"]["id"] == task["id"])
        checked.append((exchange["phase"], call, task))

    expected_costs = {"native_http_requests": len(exchanges), "native_rpc_requests": len(checked),
                      "request_bytes": requests_bytes, "response_bytes": responses_bytes}
    costs = report["costs"]
    _require(isinstance(costs, dict) and all(type(costs.get(key)) is int
             and costs[key] == value for key, value in expected_costs.items()))
    controls = report["controls"]
    _require(isinstance(controls, list) and len(controls) == 3)
    contract = report["contract"]
    _require(isinstance(contract, dict) and contract.get("answer_text") == "Well done!"
             and isinstance(contract.get("initial_text"), str))
    initial_payload = _json(contract["initial_text"])
    _require(isinstance(initial_payload, dict) and initial_payload.get("action") == "shuffle"
             and isinstance(initial_payload.get("history"), list)
             and len(initial_payload["history"]) == 1)
    entry = initial_payload["history"][0]
    _require(isinstance(entry, dict) and type(entry.get("guess")) is int
             and _string(entry.get("response")))

    position, original_tasks, all_message_ids = 0, set(), set()
    for control_index, name in enumerate(CONTROLS):
        control = controls[control_index]
        _require(isinstance(control, dict) and control.get("control_id") == name
                 and control.get("outcome") == "observed" and "error" not in control)
        group = []
        while position < len(checked) and checked[position][0].startswith(name + ":"):
            group.append(checked[position])
            position += 1
        _require(len(group) >= (5 if control_index == 2 else 4))
        phases = [row[0][len(name) + 1:] for row in group]
        pending_count = len(group) - (4 if control_index == 2 else 3)
        _require(phases == ["create"] + ["get_pending"] * pending_count
                 + ["answer", "get_original_after_answer"]
                 + (["get_answer_created_task"] if control_index == 2 else []))
        create, pending, answer, final = group[0], group[pending_count], group[pending_count + 1], group[pending_count + 2]
        _require(create[1]["method"] == answer[1]["method"] == "message/send"
                 and all(row[1]["method"] == "tasks/get" for row in group[1:pending_count + 1])
                 and final[1]["method"] == "tasks/get")
        initial_message = create[1]["params"]["message"]
        _require("taskId" not in initial_message and "contextId" not in initial_message
                 and initial_message.get("referenceTaskIds", []) == []
                 and len(initial_message["parts"]) == 1
                 and initial_message["parts"][0]["text"] == contract["initial_text"])
        task_id, context_id = pending[2]["id"], pending[2]["contextId"]
        _require(task_id not in original_tasks)
        original_tasks.add(task_id)
        _bound(create[2], task_id, context_id)
        for row in group[1:pending_count + 1]:
            _bound(row[2], task_id, context_id)
        _bound(pending[2], task_id, context_id, "input-required")
        message = answer[1]["params"]["message"]
        for msg in (initial_message, message):
            _require(msg["messageId"] not in all_message_ids)
            all_message_ids.add(msg["messageId"])
        _require(message.get("contextId") == context_id and len(message["parts"]) == 1
                 and message["parts"][0]["text"] == "Well done!")
        expected_refs = [task_id] if control_index == 0 else []
        _require(message.get("referenceTaskIds") == expected_refs
                 and control.get("with_refs") is (control_index == 0)
                 and control.get("with_task_id") is (control_index != 2)
                 and control.get("task_id") == task_id and control.get("context_id") == context_id)
        if control_index < 2:
            expected_state = "completed" if control_index == 0 else "input-required"
            _require(message.get("taskId") == task_id)
            _bound(answer[2], task_id, context_id, expected_state)
            _bound(final[2], task_id, context_id, expected_state)
            _require(control.get("same_task_answer_id") is True
                     and "answer_created_task_get" not in control)
        else:
            _require("taskId" not in message and answer[2]["id"] != task_id)
            new_task_id = answer[2]["id"]
            _require(new_task_id not in original_tasks)
            _bound(answer[2], new_task_id, context_id, "input-required")
            _bound(final[2], task_id, context_id, "input-required")
            new_get = group[-1]
            _require(new_get[1]["method"] == "tasks/get")
            _bound(new_get[2], new_task_id, context_id, "input-required")
            _require(control.get("same_task_answer_id") is False
                     and _same(control["answer_created_task_get"], new_get[2]))
        _require(control.get("same_context_answer") is True
                 and control.get("native_completion_observed") is (control_index == 0)
                 and _same(control["pending"], pending[2])
                 and _same(control["answer_reply"], answer[2])
                 and _same(control["final_original_task"], final[2]))
    _require(position == len(checked) and report.get("source_discrimination_observed") is True)


def check_reference_trace(report) -> bool:
    """Return whether the supplied record establishes the specified observations.

    Invalid/missing data returns False. This never reads archived source or
    verifies that metadata hashes authenticate the real executed software.
    """
    try:
        _check(report)
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, RecursionError,
            OverflowError, UnicodeError):
        return False
