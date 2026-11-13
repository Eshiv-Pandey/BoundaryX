"""Normalize archived A2A protocol bodies while retaining original evidence.

ASGI captures establish server-observed protocol bytes, not client receipt,
complete ADK history, causal ordering or execution of an upstream case.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from .agentops_raw_events_v1 import _digest, _encode, _json, _need, _regular, _text, _write
else:
    from agentops_raw_events_v1 import _digest, _encode, _json, _need, _regular, _text, _write


FILES = {"exchange.json", "request.body.bin", "response.body.bin", "before.snapshot.json", "after.snapshot.json"}
SEND = {"SendMessage", "message/send"}
GET = {"GetTask", "tasks/get"}
STATES = {"submitted", "working", "input-required", "completed", "canceled", "failed", "rejected", "auth-required", "unknown"}
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def _inventory(root):
    _regular(root, directory=True)
    directories = sorted(root.iterdir())
    _need(bool(directories), "Wire input has no exchanges")
    raw = {}
    total = 0
    for directory in directories:
        _need(re.fullmatch(r"[0-9]{6}", directory.name) is not None and directory.is_dir(),
              "Unexpected wire directory entry")
        _regular(directory, directory=True)
        _need({path.name for path in directory.iterdir()} == FILES, "Incomplete or unexpected exchange files")
        for name in sorted(FILES):
            path = _regular(directory / name)
            _need(path.stat().st_size <= MAX_FILE_BYTES, "Wire file exceeds size limit")
            content = path.read_bytes()
            total += len(content)
            _need(total <= MAX_TOTAL_BYTES, "Wire collection exceeds size limit")
            raw[f"{directory.name}/{name}"] = content
    return raw


def _decode(raw):
    return _json(raw.decode("utf-8"))


def _state(value):
    _text(value, "task state")
    if value.startswith("TASK_STATE_"):
        return value[len("TASK_STATE_"):].lower().replace("_", "-")
    return value


def _rpc_id(value):
    _need(value is None or (type(value) in (str, int, float)), "Invalid JSON-RPC ID")


def _profile(exchange):
    headers = exchange.get("request_headers", [])
    _need(type(headers) is list, "Malformed recorded headers")
    versions = []
    for pair in headers:
        _need(type(pair) is list and len(pair) == 2 and all(type(value) is str for value in pair),
              "Malformed recorded header pair")
        if pair[0].lower() == "a2a-version":
            versions.append(pair[1])
    _need(len(versions) <= 1, "Ambiguous protocol-version headers")
    return versions[0] if versions else "not-declared"


def _validate_exchange(exchange, sequence, request, response):
    _need(type(exchange) is dict and exchange.get("schema_version") == "agentops-asgi-exchange/1",
          "Unsupported ASGI capture schema")
    _need(type(exchange.get("sequence")) is int and exchange["sequence"] == sequence,
          "Exchange sequence/directory mismatch")
    for flag in ("request_body_complete", "response_body_complete"):
        _need(type(exchange.get(flag)) is bool, "Missing body-completeness flag")
    for field, raw in (("request_bytes", request), ("response_bytes", response)):
        _need(type(exchange.get(field)) is int and exchange[field] == len(raw), "Body byte-count mismatch")
    _need(type(exchange.get("response_status")) is int and 100 <= exchange["response_status"] <= 599,
          "Invalid HTTP status")
    _text(exchange.get("method"), "HTTP method")
    _text(exchange.get("path"), "HTTP path")
    for field in ("started_at_utc", "finished_at_utc"):
        _text(exchange.get(field), field)
        datetime.fromisoformat(exchange[field])


def normalize(raw):
    records, observations, associations = [], [], {}
    messages = {}
    message_signatures = {}
    artifact_signatures = {}
    seen = {}
    unsupported = []
    repeats = 0

    def retain(namespace, identity, part_index, part, container, task_id, context_id, profile, sequence,
               event_id=None, *, signature_value=None, location=None):
        nonlocal repeats
        _need(type(part) is dict, "Protocol part must be an object")
        metadata = part.get("metadata")
        if metadata is None:
            metadata = {}
        _need(type(metadata) is dict, "Protocol part metadata must be an object")
        kind = metadata.get("adk_type")
        if kind in ("function_call", "function_response"):
            function = part.get("data")
            _need(type(function) is dict, "Function data must be an object")
            _text(function.get("name"), "function name")
            _need(function.get("id") is None or type(function.get("id")) is str, "Function ID must be text or null")
            payload_field = "args" if kind == "function_call" else "response"
            _need(function.get(payload_field) is None or type(function.get(payload_field)) is dict,
                  "Function arguments/response must be an object or null")
        key = (profile, task_id, context_id, namespace, identity, part_index)
        stable = {"container": container, "part": part} if signature_value is None else signature_value
        signature = _encode(stable)
        representation = {"capture_sequence": sequence, "location": location, "container": container, "part": part}
        if key in seen:
            _need(seen[key][0] == signature, "Conflicting repeated event/message part; replacement needs another normalizer version")
            seen[key][1]["observed_in_sequences"].append(sequence)
            seen[key][1]["representations"].append(representation)
            repeats += 1
            return
        observation = {"namespace": namespace, "identity": identity, "part_index": part_index,
            "protocol_version_header": profile, "task_id": task_id, "context_id": context_id,
            "adk_event_id": event_id, "first_capture_sequence": sequence, "observed_in_sequences": [sequence],
            "container": container, "part": part, "adk_type": kind,
            "representations": [representation],
            "function_id": part.get("data", {}).get("id") if kind in ("function_call", "function_response") else None,
            "function_identity_complete": (type(part.get("data", {}).get("id")) is str and bool(part["data"]["id"]))
                if kind in ("function_call", "function_response") else None}
        observations.append(observation)
        seen[key] = (signature, observation)

    def retain_message(message, task_id, context_id, profile, sequence, location):
        _need(type(message) is dict, "Message must be an object")
        _need(message.get("metadata") is None or type(message.get("metadata")) is dict, "Message metadata must be an object or null")
        identity = message.get("messageId")
        _text(identity, "message ID")
        roles = {"ROLE_USER": "user", "ROLE_AGENT": "agent", "user": "user", "agent": "agent"}
        _need(type(message.get("role")) is str and message["role"] in roles, "Unsupported message role")
        role = roles[message["role"]]
        for field, expected in (("taskId", task_id), ("contextId", context_id)):
            if field in message:
                _need(message[field] == expected, "Message/task/context association mismatch")
        parts = message.get("parts", [])
        _need(type(parts) is list, "Message parts must be a list")
        semantic_parts = []
        for part in parts:
            _need(type(part) is dict, "Message part must be an object")
            semantic = dict(part)
            if type(part.get("text")) is str and "data" not in part:
                if semantic.get("mediaType") == "text/plain":
                    semantic.pop("mediaType")
                if semantic.get("kind") == "text":
                    semantic.pop("kind")
            elif type(part.get("data")) is dict and semantic.get("kind") == "data":
                semantic.pop("kind")
            if semantic.get("metadata") is None:
                semantic.pop("metadata", None)
            semantic_parts.append(semantic)
        key = (profile, task_id, context_id, identity)
        canonical = {name: value for name, value in message.items() if name not in ("parts", "taskId", "contextId")}
        canonical.update(role=role, parts=semantic_parts)
        if canonical.get("metadata") is None:
            canonical.pop("metadata", None)
        if canonical.get("kind") == "message":
            canonical.pop("kind")
        signature = _encode(canonical)
        _need(key not in message_signatures or message_signatures[key] == signature,
              "Conflicting repeated message content, part count or metadata")
        message_signatures[key] = signature
        if key not in messages:
            messages[key] = {"message_id": identity, "task_id": task_id, "context_id": context_id,
                             "protocol_version_header": profile, "role": role, "representations": []}
        _need(messages[key]["role"] == role, "Message role changed")
        messages[key]["representations"].append({"capture_sequence": sequence, "location": location, "message": message})
        container = {name: value for name, value in message.items() if name != "parts"}
        for index, part in enumerate(parts):
            # ADK history recreates plain-text parts without optional text/plain
            # transport decoration. Retain both exact representations above.
            retain("message", identity, index, part, container, task_id, context_id, profile, sequence,
                   signature_value={"role": role, "part": semantic_parts[index]}, location=location)

    for directory in sorted({name.split("/")[0] for name in raw}):
        sequence = int(directory)
        exchange = _decode(raw[f"{directory}/exchange.json"])
        request_raw, response_raw = raw[f"{directory}/request.body.bin"], raw[f"{directory}/response.body.bin"]
        _validate_exchange(exchange, sequence, request_raw, response_raw)
        profile = _profile(exchange)
        record = {"capture_sequence": sequence, "method": exchange["method"], "path": exchange["path"],
            "http_status": exchange["response_status"], "started_at_utc": exchange["started_at_utc"],
            "finished_at_utc": exchange["finished_at_utc"], "protocol_version_header": profile,
            "request_body": _digest(request_raw), "response_body": _digest(response_raw)}
        records.append(record)
        if not exchange["request_body_complete"] or not exchange["response_body_complete"]:
            record["outcome"] = "incomplete_exchange"
            unsupported.append(sequence)
            continue
        if exchange["response_status"] != 200:
            record["outcome"] = "non_success_http"
            continue
        if exchange["method"] == "GET" and exchange["path"] in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
            card = _decode(response_raw)
            _need(type(card) is dict, "Agent card must be an object")
            record.update(outcome="agent_card", card=card)
            continue
        if exchange["method"] != "POST":
            record["outcome"] = "unsupported_http_operation"
            unsupported.append(sequence)
            continue
        request, response = _decode(request_raw), _decode(response_raw)
        _need(type(request) is dict and type(response) is dict and request.get("jsonrpc") == "2.0" and response.get("jsonrpc") == "2.0",
              "Unsupported JSON-RPC envelope")
        _need("id" in request and "id" in response, "JSON-RPC notification/unbound response cannot be normalized")
        _rpc_id(request["id"])
        _rpc_id(response["id"])
        _need(request["id"] == response["id"] and not isinstance(request["id"], bool), "JSON-RPC response ID mismatch")
        _need(("result" in response) != ("error" in response), "Ambiguous JSON-RPC result/error")
        record.update(rpc_method=request.get("method"), request=request, response=response)
        if "error" in response:
            _need(type(response["error"]) is dict, "Malformed JSON-RPC error")
            _need(type(response["error"].get("code")) is int and type(response["error"].get("message")) is str,
                  "Malformed JSON-RPC error code/message")
            record["outcome"] = "jsonrpc_error"
            continue
        method = request.get("method")
        if method not in SEND | GET:
            record["outcome"] = "unsupported_rpc_operation"
            unsupported.append(sequence)
            continue
        result = response["result"]
        _need(type(result) is dict, "Unsupported RPC result")
        if "task" in result:
            _need("message" not in result, "Ambiguous task/message result")
            task = result["task"]
            shape = "wrapped_task"
        elif "status" in result and "id" in result:
            task = result
            shape = "direct_task"
        elif "message" in result or result.get("kind") == "message":
            record["outcome"] = "message_result"
            unsupported.append(sequence)
            continue
        else:
            record["outcome"] = "unsupported_rpc_result"
            unsupported.append(sequence)
            continue
        _need(type(task) is dict, "Task must be an object")
        task_id, context_id = task.get("id"), task.get("contextId")
        if not (type(task_id) is str and bool(task_id.strip()) and type(context_id) is str and bool(context_id.strip())):
            record.update(outcome="unbound_task_result", task=task)
            unsupported.append(sequence)
            continue
        _text(task_id, "task ID")
        _text(context_id, "context ID")
        _need(task_id not in associations or associations[task_id] == context_id, "Task/context association changed")
        associations[task_id] = context_id
        status = task.get("status")
        _need(type(status) is dict, "Missing Task status")
        state = _state(status.get("state"))
        record.update(outcome="task", task_shape=shape, task_id=task_id, context_id=context_id, state=state, task=task)
        if state not in STATES:
            unsupported.append(sequence)
            record["unsupported_state"] = True
        params = request.get("params")
        _need(type(params) is dict, "Missing RPC parameters")
        if method in GET:
            _need(params.get("id") == task_id, "GetTask returned an unrelated task")
        else:
            message = params.get("message")
            _need(type(message) is dict, "Missing outgoing message")
            for field, value in (("taskId", task_id), ("contextId", context_id)):
                if field in message:
                    _need(message[field] == value, "SendMessage returned an unrelated task/context")
            retain_message(message, task_id, context_id, profile, sequence, "request")
        artifacts = task.get("artifacts")
        if artifacts is None:
            artifacts = []
        _need(type(artifacts) is list, "Task artifacts must be a list")
        for artifact in artifacts:
            _need(type(artifact) is dict, "Artifact must be an object")
            metadata = artifact.get("metadata")
            _need(type(metadata) is dict, "Artifact needs ADK metadata for this normalizer")
            event_id = metadata.get("adk_event_id")
            _text(event_id, "ADK event ID")
            _text(metadata.get("adk_invocation_id"), "ADK invocation ID")
            _text(metadata.get("adk_author"), "ADK author")
            _text(artifact.get("artifactId"), "artifact ID")
            artifact_key = (profile, task_id, context_id, event_id, artifact["artifactId"])
            signature = _encode(artifact)
            _need(artifact_key not in artifact_signatures or artifact_signatures[artifact_key] == signature,
                  "Conflicting repeated artifact or part replacement")
            artifact_signatures[artifact_key] = signature
            parts = artifact.get("parts")
            _need(type(parts) is list, "Artifact parts must be a list")
            if metadata.get("adk_partial") is True:
                unsupported.append(sequence)
            container = {key: value for key, value in artifact.items() if key != "parts"}
            for index, part in enumerate(parts):
                retain("artifact_event", event_id, index, part, container, task_id, context_id, profile, sequence,
                       event_id, location="artifact")
        message = status.get("message")
        if message is not None:
            retain_message(message, task_id, context_id, profile, sequence, "status")
        history = task.get("history")
        if history is None:
            history = []
        _need(type(history) is list, "Task history must be a list")
        for message in history:
            retain_message(message, task_id, context_id, profile, sequence, "history")
    return {"schema_version": "agentops-public-observations/1", "records": records, "observations": observations,
        "messages": list(messages.values()),
        "task_context_associations": associations, "identical_repeated_parts": repeats,
        "unsupported_sequences": sorted(set(unsupported)), "normalization_complete": not unsupported,
        "ordering_basis": "Server capture request sequence, not response-arrival or ADK causal order",
        "client_receipt_proven": False, "causal_order_proven": False, "complete_event_stream_proven": False,
        "graded_task_outcomes": 0}


def export_wire(wire_root: Path, output: Path) -> dict:
    wire_root, output = Path(wire_root).absolute(), Path(output).absolute()
    _need(not output.exists() and not output.is_symlink(), "Refusing an existing output")
    _need(not output.resolve().is_relative_to(wire_root.resolve()), "Output must be outside source wire tree")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema_version": "agentops-public-event-export/1", "status": "failed", "source_unchanged": None,
        "captured_files_unchanged": None, "application_requests": 0, "model_calls": 0, "graded_task_outcomes": 0,
        "visibility": "Server-observed public-protocol bytes; not proof of client receipt"}
    source = None
    implementations = {}
    captures = {}
    try:
        module = Path(__file__)
        helper = module.with_name("agentops_raw_events_v1.py")
        implementations = {module: module.read_bytes(), helper: helper.read_bytes()}
        plan = {"schema_version": "agentops-public-event-export-plan/1", "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "wire_root": str(wire_root), "exporter_sha256": hashlib.sha256(implementations[module]).hexdigest(),
                "helper_sha256": hashlib.sha256(implementations[helper]).hexdigest(), "original_source_files": sorted(FILES)}
        captures.update({"plan.json": _encode(plan), "source/agentops_public_events_v1.py": implementations[module],
                         "source/agentops_raw_events_v1.py": implementations[helper]})
        for name, raw in captures.items():
            _write(output / name, raw)
        source = _inventory(wire_root)
        for name, raw in source.items():
            captures["wire/" + name] = raw
            _write(output / "wire" / name, raw)
        normalized = normalize(source)
        captures["observations.json"] = _encode(normalized)
        _write(output / "observations.json", captures["observations.json"])
        parts = normalized["observations"]
        receipt.update(status="passed" if normalized["normalization_complete"] else "partial",
            capture_exchanges=len(normalized["records"]), task_replies=sum(row["outcome"] == "task" for row in normalized["records"]),
            distinct_tasks=len(normalized["task_context_associations"]), unique_parts=len(parts),
            distinct_messages=len(normalized["messages"]),
            function_calls=sum(row["adk_type"] == "function_call" for row in parts),
            function_responses=sum(row["adk_type"] == "function_response" for row in parts),
            identical_repeated_parts=normalized["identical_repeated_parts"], unsupported_sequences=normalized["unsupported_sequences"],
            normalization_complete=normalized["normalization_complete"], client_receipt_proven=False, causal_order_proven=False,
            complete_event_stream_proven=False, interpretation="Normalization/preservation only; no upstream-case association, fresh native run or task/effect grade.")
    except (OSError, ValueError, TypeError, KeyError) as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if source is not None:
                after = _inventory(wire_root)
                receipt["source_unchanged"] = after == source
                _need(receipt["source_unchanged"], "Wire bytes or membership changed during export")
            receipt["implementation_sources_unchanged"] = all(_regular(path).read_bytes() == raw for path, raw in implementations.items())
            _need(receipt["implementation_sources_unchanged"], "Normalizer implementation changed during export")
            actual_membership = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            receipt["captured_files_unchanged"] = (actual_membership == set(captures)
                and all(_regular(output / name).read_bytes() == raw for name, raw in captures.items()))
            _need(receipt["captured_files_unchanged"], "Captured evidence changed during export")
        except (OSError, ValueError) as error:
            receipt.update(status="failed", preservation_error=f"{type(error).__name__}: {error}")
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["files"] = [{"path": path.relative_to(output).as_posix(), **_digest(path.read_bytes())}
                            for path in sorted(output.rglob("*")) if path.is_file()]
        _write(output / "result.json", _encode(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wire-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = export_wire(args.wire_root, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"status": result["status"], "exchanges": result.get("capture_exchanges"),
                     "parts": result.get("unique_parts"), "error": result.get("error"), "receipt": str(args.output / "result.json")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
