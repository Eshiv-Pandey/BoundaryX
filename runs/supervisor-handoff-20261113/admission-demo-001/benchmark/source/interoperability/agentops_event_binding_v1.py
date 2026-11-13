"""Check consistency of existing public and evaluator event exports.

No exporter, SDK, database, application or model is executed. A matching
recorded payload is not a causal, complete-stream, client-receipt or task grade.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re

if __package__:
    from .agentops_raw_events_v1 import JSON_COLUMNS, PRIMARY_KEYS, TABLES, _digest, _encode, _json, _need, _regular, _text, _write
else:
    from agentops_raw_events_v1 import JSON_COLUMNS, PRIMARY_KEYS, TABLES, _digest, _encode, _json, _need, _regular, _text, _write


KINDS = {"function_call", "function_response"}
MAX_FILES = 10000
MAX_BYTES = 512 * 1024 * 1024
WIRE_FILES = {"exchange.json", "request.body.bin", "response.body.bin", "before.snapshot.json", "after.snapshot.json"}


def _decode(raw):
    return _json(raw.decode("utf-8"))


def _count(value):
    _need(type(value) is int and value >= 0, "Invalid recorded count")
    return value


def _same(left, right):
    """Exact JSON values and types; transport exceptions are handled separately."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _function_same(raw, public, kind):
    """Permit integral protobuf floats only in the two known audit integer fields."""
    try:
        candidate = json.loads(json.dumps(public, allow_nan=False))
    except (ValueError, TypeError, OverflowError):
        return False
    raw_response = raw.get("response") if type(raw) is dict else None
    public_response = candidate.get("response") if type(candidate) is dict else None
    if kind == "function_response" and type(raw_response) is dict and type(public_response) is dict:
        raw_audit, public_audit = raw_response.get("audit"), public_response.get("audit")
        if type(raw_audit) is dict and type(public_audit) is dict:
            for field in ("id", "schema_version"):
                if field not in raw_audit and field not in public_audit:
                    continue
                original, value = raw_audit.get(field), public_audit.get(field)
                if not (type(original) is int and 0 <= original <= 2**53 - 1
                        and type(value) in (int, float) and 0 <= value <= 2**53 - 1
                        and math.isfinite(value) and value == original):
                    return False
                public_audit[field] = original
    return _same(raw, candidate)


def _inventory(root):
    root = _regular(root, directory=True)
    files, total = {}, 0
    for path in sorted(root.rglob("*")):
        _regular(path, directory=path.is_dir())
        if path.is_dir():
            continue
        total += path.stat().st_size
        _need(total <= MAX_BYTES and len(files) < MAX_FILES, "Input export exceeds checker limits")
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _validate_bundle(files, schema):
    _need("result.json" in files and "plan.json" in files, "Input export lacks its receipt or plan")
    receipt = _decode(files["result.json"])
    _need(type(receipt) is dict and receipt.get("schema_version") == schema, "Unsupported input receipt")
    _need(receipt.get("status") in {"passed", "partial"}, "Input export did not pass or retain a partial result")
    for field in ("source_unchanged", "captured_files_unchanged"):
        _need(receipt.get(field) is True, "Input preservation is not verified: " + field)
    for field in ("application_requests", "model_calls", "graded_task_outcomes"):
        _need(type(receipt.get(field)) is int and receipt[field] == 0, "Unexpected input execution/grade claim")
    for field in ("causal_order_proven", "complete_event_stream_proven"):
        _need(receipt.get(field) is False, "Unexpected input proof claim")
    entries = receipt.get("files")
    _need(type(entries) is list, "Missing input manifest")
    manifest = {}
    for entry in entries:
        _need(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"}, "Malformed manifest entry")
        name = entry["path"]
        _need(type(name) is str and name and "\\" not in name and ":" not in name, "Invalid manifest path")
        parts = PurePosixPath(name)
        _need(not parts.is_absolute() and ".." not in parts.parts and parts.as_posix() == name,
              "Manifest path must be canonical and relative")
        _need(name != "result.json" and name not in manifest, "Duplicate or self-referential manifest entry")
        _need(type(entry["bytes"]) is int and entry["bytes"] >= 0 and type(entry["sha256"]) is str
              and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None, "Invalid manifest digest")
        _need(name in files and _digest(files[name]) == {key: entry[key] for key in ("bytes", "sha256")},
              "Input manifest byte/hash mismatch")
        manifest[name] = entry
    _need(set(manifest) | {"result.json"} == set(files), "Input allocation membership differs from manifest")
    return receipt, _decode(files["plan.json"])


def _raw_parts(files, receipt, plan):
    _need(plan.get("schema_version") == "agentops-raw-event-export-plan/1", "Unsupported raw plan")
    _need(_digest(files["exporter.py"])["sha256"] == plan.get("exporter_sha256"), "Raw exporter copy mismatch")
    _need(_digest(files["input/runtime.db"]) == receipt.get("database"), "Raw database copy mismatch")
    raw, decoded = _decode(files["raw-tables.json"]), _decode(files["decoded-tables.json"])
    _need(type(raw) is dict and type(decoded) is dict and set(raw) == set(decoded) == set(TABLES),
          "Unsupported decoded runtime tables")
    unknown = []
    for table, columns in TABLES.items():
        rows, parsed = raw[table], decoded[table]
        _need(type(rows) is list and type(parsed) is list and len(rows) == len(parsed), "Raw/decoded row count mismatch")
        identities = set()
        for row, item in zip(rows, parsed):
            _need(type(row) is dict and type(item) is dict and set(row) == set(item) == set(columns) | {"sqlite_rowid"},
                  "Runtime table row shape mismatch")
            _need(type(row["sqlite_rowid"]) is int, "Invalid physical row identity")
            identity = tuple(row[field] for field in PRIMARY_KEYS[table])
            _need(all(type(value) is str and value for value in identity) and identity not in identities,
                  "Invalid or duplicate runtime row identity")
            identities.add(identity)
            for field in row:
                expected = _json(row[field]) if field in JSON_COLUMNS.get(table, ()) and row[field] is not None else row[field]
                _need(_same(expected, item[field]), "Raw/decoded runtime field mismatch")
        _need(_count(receipt.get("table_rows", {}).get(table)) == len(rows), "Receipt table count mismatch")
    expected = []
    for row in decoded["events"]:
        for field in ("id", "app_name", "user_id", "session_id", "invocation_id"):
            _text(row.get(field), "raw event row " + field)
        event = row["event_data"]
        if event is None:
            unknown.append({"reason": "missing_raw_event_payload", "event_id": row["id"]})
            continue
        _need(type(event) is dict and event.get("id") == row["id"] and event.get("invocation_id") == row["invocation_id"],
              "Raw event envelope identity mismatch")
        for field in ("app_name", "user_id", "session_id"):
            _need(field not in event or event[field] == row[field], "Raw event optional scope mismatch")
        _text(event.get("author"), "raw event author")
        timestamp = event.get("timestamp")
        try:
            valid_timestamp = type(timestamp) in (int, float) and timestamp >= 0 and math.isfinite(timestamp)
        except OverflowError:
            valid_timestamp = False
        _need(valid_timestamp, "Raw event timestamp must be finite and nonnegative")
        content = event.get("content")
        parts = content.get("parts", []) if type(content) is dict else []
        _need(content is None or type(content) is dict, "Malformed raw event content")
        _need(type(parts) is list, "Malformed raw parts")
        for index, part in enumerate(parts):
            _need(type(part) is dict, "Malformed raw event part")
            active = [kind for kind in KINDS if part.get(kind) is not None]
            _need(len(active) <= 1, "Ambiguous raw function part")
            for kind in active:
                value = part[kind]
                _need(type(value) is dict, "Malformed raw function payload")
                _text(value.get("name"), "raw function name")
                identity = value.get("id")
                _need(identity is None or type(identity) is str, "Malformed raw function ID")
                body = value.get("args" if kind == "function_call" else "response")
                _need(body is None or type(body) is dict, "Malformed raw function body")
                expected.append({"event_rowid": row["sqlite_rowid"], "event_id": row["id"],
                    "app_name": row["app_name"], "user_id": row["user_id"], "session_id": row["session_id"],
                    "invocation_id": row["invocation_id"], "author": event["author"],
                    "event_timestamp": event["timestamp"], "database_timestamp": row["timestamp"],
                    "part_index": index, "kind": kind, "function_id": identity,
                    "function_identity_complete": type(identity) is str and bool(identity), "function": value})
    observations = _decode(files["function-observations.json"])
    _need(_same(observations, expected), "Raw function projection differs from event rows")
    _need(_count(receipt.get("events")) == len(decoded["events"]), "Raw event count mismatch")
    for kind, field in (("function_call", "function_calls"), ("function_response", "function_responses")):
        _need(_count(receipt.get(field)) == sum(item["kind"] == kind for item in expected), "Raw function count mismatch")
    return decoded, observations, unknown


def _source_records(files):
    """Derive envelope classifications and profiles from the copied wire files."""
    wire = {}
    for name in files:
        if not name.startswith("wire/"):
            continue
        parts = name.split("/")
        _need(len(parts) == 3 and re.fullmatch(r"[0-9]{6}", parts[1]) is not None and int(parts[1]) > 0,
              "Invalid copied wire path")
        wire.setdefault(int(parts[1]), set()).add(parts[2])
    _need(wire and all(names == WIRE_FILES for names in wire.values()), "Incomplete copied wire exchange inventory")
    result = {}
    for sequence in sorted(wire):
        prefix = f"wire/{sequence:06d}/"
        exchange = _decode(files[prefix + "exchange.json"])
        _need(type(exchange) is dict and exchange.get("schema_version") == "agentops-asgi-exchange/1"
              and type(exchange.get("sequence")) is int and exchange["sequence"] == sequence,
              "Copied exchange schema or sequence mismatch")
        request_raw, response_raw = files[prefix + "request.body.bin"], files[prefix + "response.body.bin"]
        for field, raw in (("request_bytes", request_raw), ("response_bytes", response_raw)):
            _need(type(exchange.get(field)) is int and exchange[field] == len(raw), "Copied exchange byte-count mismatch")
        for field in ("request_body_complete", "response_body_complete"):
            _need(type(exchange.get(field)) is bool, "Copied exchange completeness flag missing")
        _need(type(exchange.get("response_status")) is int and 100 <= exchange["response_status"] <= 599,
              "Copied exchange HTTP status invalid")
        headers = exchange.get("request_headers")
        _need(type(headers) is list, "Copied exchange headers malformed")
        versions = []
        for pair in headers:
            _need(type(pair) is list and len(pair) == 2 and all(type(value) is str for value in pair), "Copied header pair malformed")
            if pair[0].lower() == "a2a-version":
                versions.append(pair[1])
        _need(len(versions) <= 1, "Copied exchange protocol profile ambiguous")
        profile = versions[0] if versions else "not-declared"
        expected = {"capture_sequence": sequence, "method": exchange.get("method"), "path": exchange.get("path"),
                    "http_status": exchange["response_status"], "started_at_utc": exchange.get("started_at_utc"),
                    "finished_at_utc": exchange.get("finished_at_utc"), "protocol_version_header": profile,
                    "request_body": _digest(request_raw), "response_body": _digest(response_raw)}
        if not exchange["request_body_complete"] or not exchange["response_body_complete"]:
            expected["outcome"] = "incomplete_exchange"
        elif exchange["response_status"] != 200:
            expected["outcome"] = "non_success_http"
        elif exchange.get("method") == "GET" and exchange.get("path") in {"/.well-known/agent-card.json", "/.well-known/agent.json"}:
            expected.update(outcome="agent_card", card=_decode(response_raw))
        elif exchange.get("method") != "POST":
            expected["outcome"] = "unsupported_http_operation"
        else:
            request, response = _decode(request_raw), _decode(response_raw)
            _need(type(request) is dict and type(response) is dict, "Copied RPC envelopes malformed")
            expected.update(request=request, response=response, rpc_method=request.get("method"))
            if "error" in response:
                _need("result" not in response, "Copied RPC response ambiguous")
                expected["outcome"] = "jsonrpc_error"
            elif request.get("method") not in {"SendMessage", "message/send", "GetTask", "tasks/get"}:
                expected["outcome"] = "unsupported_rpc_operation"
            else:
                value = response.get("result")
                _need(type(value) is dict, "Copied RPC result malformed")
                shape, task = None, None
                if "task" in value:
                    _need("message" not in value, "Copied RPC task/message result ambiguous")
                    shape, task = "wrapped_task", value["task"]
                elif "status" in value and "id" in value:
                    shape, task = "direct_task", value
                if shape is None:
                    expected["outcome"] = "message_result" if "message" in value or value.get("kind") == "message" else "unsupported_rpc_result"
                else:
                    _need(type(task) is dict, "Copied task malformed")
                    if not all(type(task.get(field)) is str and task[field].strip() for field in ("id", "contextId")):
                        expected.update(outcome="unbound_task_result", task=task)
                    else:
                        _need(type(task.get("status")) is dict, "Copied task status malformed")
                        state = task["status"].get("state")
                        _text(state, "copied task state")
                        if state.startswith("TASK_STATE_"):
                            state = state[len("TASK_STATE_"):].lower().replace("_", "-")
                        expected.update(outcome="task", task_shape=shape, task=task,
                                        task_id=task["id"], context_id=task["contextId"], state=state)
        result[sequence] = expected
    return result


def _public_parts(files, receipt, plan):
    _need(plan.get("schema_version") == "agentops-public-event-export-plan/1", "Unsupported public plan")
    for file, field in (("source/agentops_public_events_v1.py", "exporter_sha256"), ("source/agentops_raw_events_v1.py", "helper_sha256")):
        _need(_digest(files[file])["sha256"] == plan.get(field), "Public implementation copy mismatch")
    view = _decode(files["observations.json"])
    _need(type(view) is dict and view.get("schema_version") == "agentops-public-observations/1", "Unsupported public projection")
    _need(type(view.get("normalization_complete")) is bool and type(view.get("unsupported_sequences")) is list
          and all(type(value) is int and value > 0 for value in view["unsupported_sequences"]), "Malformed public completion/partial flags")
    _need(view.get("normalization_complete") is receipt.get("normalization_complete"), "Public completion flag mismatch")
    _need(view.get("unsupported_sequences") == receipt.get("unsupported_sequences"), "Public partial-sequence mismatch")
    records = view.get("records")
    _need(type(records) is list and len(records) == _count(receipt.get("capture_exchanges")), "Public exchange count mismatch")
    source_records = _source_records(files)
    origins = {}

    def retain(namespace, identity, container, task, context, profile, sequence, location):
        _need(type(container) is dict and type(container.get("parts", [])) is list, "Malformed public source container")
        for index, part in enumerate(container.get("parts", [])):
            _need(type(part) is dict, "Malformed public source part")
            metadata = part.get("metadata", {})
            if type(metadata) is dict and metadata.get("adk_type") in KINDS:
                key = (namespace, identity, index, task, context, profile, sequence, location)
                _need(key not in origins, "Duplicate public source origin")
                origins[key] = {"part": part, "container": {k: v for k, v in container.items() if k != "parts"},
                                "task_id": task, "context_id": context}

    sequences = set()
    associations = {}
    for record in records:
        _need(type(record) is dict and type(record.get("capture_sequence")) is int, "Invalid public record")
        seq = record["capture_sequence"]
        _need(seq > 0 and seq not in sequences, "Duplicate public capture sequence")
        sequences.add(seq)
        _need(seq in source_records and all(field in record and _same(record[field], value)
              for field, value in source_records[seq].items()), "Public record classification or fields differ from copied exchange/envelopes")
        if record.get("outcome") != "task":
            continue
        task = record.get("task")
        response = record["response"].get("result")
        source_task = response.get("task") if type(response) is dict and "task" in response else response
        _need(_same(task, source_task), "Public task projection differs from response envelope")
        _need(type(task) is dict and task.get("id") == record.get("task_id") and task.get("contextId") == record.get("context_id"),
              "Public task/context envelope mismatch")
        task_id, context = task["id"], task["contextId"]
        profile = source_records[seq]["protocol_version_header"]
        _text(task_id, "public task ID"); _text(context, "public context ID")
        _need(task_id not in associations or associations[task_id] == context, "Conflicting public task context")
        associations[task_id] = context
        artifacts, history = task.get("artifacts"), task.get("history")
        artifacts = [] if artifacts is None else artifacts
        history = [] if history is None else history
        _need(type(artifacts) is list and type(history) is list, "Public task artifact/history shape invalid")
        for artifact in artifacts:
            _need(type(artifact) is dict and type(artifact.get("metadata")) is dict, "Public artifact metadata malformed")
            retain("artifact_event", artifact["metadata"].get("adk_event_id"), artifact, task_id, context, profile, seq, "artifact")
        messages = [("history", message) for message in history]
        if type(task.get("status")) is dict and task["status"].get("message") is not None:
            messages.append(("status", task["status"]["message"]))
        params = record["request"].get("params")
        _need(type(params) is dict, "Copied task RPC parameters malformed")
        request = params.get("message")
        if request is not None:
            messages.append(("request", request))
        for location, message in messages:
            _need(type(message) is dict, "Public message container malformed")
            retain("message", message.get("messageId"), message, task_id, context, profile, seq, location)
    _need(sequences == set(source_records), "Public records omit copied wire exchanges")
    _need(associations == view.get("task_context_associations"), "Public association projection mismatch")
    parts = view.get("observations")
    _need(type(parts) is list and len(parts) == _count(receipt.get("unique_parts")), "Public observation count mismatch")
    functions, seen, covered = [], set(), set()
    for item in parts:
        _need(type(item) is dict, "Malformed normalized public part")
        if item.get("adk_type") not in KINDS:
            continue
        namespace, identity, index = item.get("namespace"), item.get("identity"), item.get("part_index")
        _need(namespace in {"artifact_event", "message"} and type(index) is int and index >= 0, "Invalid public function namespace/index")
        _text(identity, "public container identity")
        key = (namespace, identity, index, item.get("task_id"), item.get("context_id"), item.get("protocol_version_header"))
        _need(key not in seen, "Duplicate normalized public function part")
        seen.add(key)
        _need(associations.get(item.get("task_id")) == item.get("context_id"), "Unbound normalized public function")
        part = item.get("part")
        _need(type(part) is dict and type(part.get("metadata")) is dict and part["metadata"].get("adk_type") == item["adk_type"],
              "Public function kind mismatch")
        payload = part.get("data")
        _need(type(payload) is dict and item.get("function_id") == payload.get("id"), "Public function ID mismatch")
        _text(payload.get("name"), "public function name")
        _need(item.get("function_identity_complete") is (type(payload.get("id")) is str and bool(payload["id"])),
              "Public function identity flag mismatch")
        representations = item.get("representations")
        _need(type(representations) is list and representations, "Public function lacks source representations")
        _need(item.get("observed_in_sequences") == [rep.get("capture_sequence") for rep in representations]
              and item.get("first_capture_sequence") == representations[0].get("capture_sequence"), "Public sequence projection mismatch")
        for rep in representations:
            sequence = rep.get("capture_sequence")
            _need(sequence in source_records and item.get("protocol_version_header") == source_records[sequence]["protocol_version_header"],
                  "Public observation protocol profile differs from copied exchange")
            origin = (namespace, identity, index, item["task_id"], item["context_id"], item["protocol_version_header"], sequence, rep.get("location"))
            _need(origin in origins and _same(origins[origin]["part"], rep.get("part"))
                  and _same(origins[origin]["container"], rep.get("container")), "Public representation lacks a matching copied-body origin")
            _need(origin not in covered, "Public source origin is reused or represented more than once")
            _need(_same(part, rep["part"]), "Conflicting normalized public payload")
            _need(origins[origin]["task_id"] == item["task_id"] and origins[origin]["context_id"] == item["context_id"], "Public origin scope mismatch")
            covered.add(origin)
        _need(_same(item.get("container"), representations[0].get("container")), "Public representative container mismatch")
        functions.append(item)
    if view.get("normalization_complete") is True:
        _need(covered == set(origins), "Public function projection omits or invents source parts")
    for kind, field in (("function_call", "function_calls"), ("function_response", "function_responses")):
        _need(_count(receipt.get(field)) == sum(item["adk_type"] == kind for item in functions), "Public function count mismatch")
    unsupported_outcomes = {"incomplete_exchange", "unsupported_http_operation", "unsupported_rpc_operation",
                            "message_result", "unsupported_rpc_result", "unbound_task_result"}
    source_partial = any(record["outcome"] in unsupported_outcomes for record in source_records.values())
    return view, functions, source_partial


def _compare_bytes(raw_files, public_files):
    raw_receipt, raw_plan = _validate_bundle(raw_files, "agentops-raw-event-export/1")
    public_receipt, public_plan = _validate_bundle(public_files, "agentops-public-event-export/1")
    _need(raw_files["exporter.py"] == public_files["source/agentops_raw_events_v1.py"], "Exports use different raw schema implementations")
    decoded, raw_parts, unresolved = _raw_parts(raw_files, raw_receipt, raw_plan)
    view, public_parts, source_partial = _public_parts(public_files, public_receipt, public_plan)
    if raw_receipt["status"] != "passed" or public_receipt["status"] != "passed" or view.get("normalization_complete") is not True or source_partial:
        unresolved.append({"reason": "partial_input_export"})
    sessions = {(row["app_name"], row["user_id"], row["id"]): row for row in decoded["sessions"]}
    tasks = {row["id"]: row for row in decoded["tasks"]}
    bindings = {}
    for task_id, context in view["task_context_associations"].items():
        task = tasks.get(task_id)
        if task is None:
            unresolved.append({"reason": "missing_recorded_task", "task_id": task_id}); continue
        _need(task["context_id"] == context, "Recorded task context conflicts with public context")
        metadata = task.get("metadata")
        fields = ("adk_app_name", "adk_user_id", "adk_session_id")
        if type(metadata) is not dict or not all(type(metadata.get(field)) is str and metadata[field] for field in fields):
            unresolved.append({"reason": "missing_recorded_task_session_metadata", "task_id": task_id}); continue
        scope = tuple(metadata[field] for field in fields)
        if scope not in sessions:
            unresolved.append({"reason": "missing_recorded_session", "task_id": task_id}); continue
        bindings[task_id] = {"context_id": context, "app_name": scope[0], "user_id": scope[1], "session_id": scope[2],
                             "mapping_basis": "Recorded task context and explicit ADK task metadata reference an existing session row"}
    pairs = []
    for public in public_parts:
        binding = bindings.get(public["task_id"])
        if binding is None:
            continue
        if public.get("function_identity_complete") is not True:
            unresolved.append({"reason": "missing_public_function_id", "identity": public["identity"]}); continue
        scope = [item for item in raw_parts if all(item[field] == binding[field] for field in ("app_name", "user_id", "session_id"))]
        namespace = public["namespace"]
        identity_proven = namespace == "artifact_event"
        if identity_proven:
            metadata = public["container"].get("metadata", {})
            _need(public.get("adk_event_id") == public["identity"] == metadata.get("adk_event_id"), "Artifact event ID projection mismatch")
            _text(metadata.get("adk_invocation_id"), "artifact invocation ID"); _text(metadata.get("adk_author"), "artifact author")
            candidates = [item for item in scope if item["event_id"] == public["adk_event_id"] and item["part_index"] == public["part_index"]]
            if candidates:
                _need(len(candidates) == 1 and candidates[0]["kind"] == public["adk_type"]
                      and candidates[0]["invocation_id"] == metadata["adk_invocation_id"] and candidates[0]["author"] == metadata["adk_author"]
                      and _function_same(candidates[0]["function"], public["part"]["data"], public["adk_type"]), "Artifact recorded identity or payload conflict")
            for rep in public["representations"]:
                rep_meta = rep["container"].get("metadata", {})
                _need(all(rep_meta.get(field) == metadata[field] for field in ("adk_event_id", "adk_invocation_id", "adk_author")),
                      "Repeated artifact metadata conflict")
            basis = "Scoped recorded ADK event ID, part index, invocation, author and full function payload agree"
        else:
            _need(public.get("adk_event_id") is None, "Message ADK event identity must remain absent in this format")
            for container in [public["container"], *(rep["container"] for rep in public["representations"])]:
                metadata = container.get("metadata")
                _need(metadata is None or (type(metadata) is dict and not any(field in metadata for field in
                      ("adk_event_id", "adk_invocation_id", "adk_author"))), "Message explicitly declares unsupported ADK event metadata")
            candidates = [item for item in scope if item["kind"] == public["adk_type"] and _function_same(item["function"], public["part"]["data"], public["adk_type"])]
            basis = "Unique full function payload match within the explicitly recorded task/session scope; public ADK event identity remains absent"
        if len(candidates) != 1:
            unresolved.append({"reason": "missing_raw_match" if not candidates else "ambiguous_raw_match",
                               "namespace": namespace, "identity": public["identity"], "candidate_count": len(candidates)}); continue
        raw = candidates[0]
        if raw["function_identity_complete"] is not True:
            unresolved.append({"reason": "missing_raw_function_id", "event_id": raw["event_id"]}); continue
        pairs.append({"public_namespace": namespace, "public_identity": public["identity"], "public_adk_event_id": public.get("adk_event_id"),
            "public_part_index": public["part_index"], "task_id": public["task_id"], **binding,
            "kind": public["adk_type"], "function_id": public["function_id"], "function_name": raw["function"]["name"],
            "matched_raw_event_id": raw["event_id"], "matched_raw_part_index": raw["part_index"], "matched_raw_invocation_id": raw["invocation_id"],
            "matched_raw_author": raw["author"], "event_identity_proven": identity_proven, "mapping_basis": basis})
    if not public_parts:
        unresolved.append({"reason": "no_public_function_evidence"})
    return {"schema_version": "agentops-event-binding/1", "status": "unresolved" if unresolved else "passed",
        "verified_function_pairs": len(pairs), "public_function_parts": len(public_parts), "raw_function_parts": len(raw_parts),
        "pairs": pairs, "task_session_bindings": bindings, "unresolved": unresolved,
        "artifact_recorded_identity_pairs": sum(pair["event_identity_proven"] for pair in pairs),
        "message_payload_only_pairs": sum(not pair["event_identity_proven"] for pair in pairs),
        "payload_comparison_basis": "Exact JSON values/types except response.audit.id and response.audit.schema_version: a raw nonnegative integer within 2**53-1 may equal its integral protobuf float representation. No other numeric, redaction or guardrail transformation is applied",
        "input_manifests_verified": True, "input_files_verified": {"raw": len(raw_files), "public": len(public_files)},
        "application_requests": 0, "model_calls": 0, "graded_task_outcomes": 0,
        "causal_order_proven": False, "client_receipt_proven": False, "complete_event_stream_proven": False, "source_authenticity_proven": False,
        "claim_limit": "Consistency of copied recorded views only; no source authentication, fresh execution, causal order, client receipt, complete event stream, effect, upstream-case or admission qualification."}


def compare(raw_root: Path, public_root: Path) -> dict:
    """Read and compare existing exports; malformed/tampered inputs raise ValueError."""
    raw_root, public_root = Path(raw_root).absolute(), Path(public_root).absolute()
    before = {"raw": _inventory(raw_root), "public": _inventory(public_root)}
    report = _compare_bytes(before["raw"], before["public"])
    _need(_inventory(raw_root) == before["raw"] and _inventory(public_root) == before["public"], "Input exports changed during comparison")
    report["inputs_unchanged"] = True
    return report


def export_comparison(raw_root: Path, public_root: Path, output: Path) -> dict:
    roots = {"raw": Path(raw_root).absolute(), "public": Path(public_root).absolute()}
    output = Path(output).absolute()
    _need(not output.exists() and not output.is_symlink(), "Refusing an existing output")
    _need(all(not output.resolve().is_relative_to(root.resolve()) for root in roots.values()), "Output must be outside input exports")
    output.mkdir(parents=True, exist_ok=False)
    captured, inputs, implementations = {}, {}, {}
    report = {"schema_version": "agentops-event-binding/1", "status": "failed", "inputs_unchanged": None,
              "application_requests": 0, "model_calls": 0, "graded_task_outcomes": 0,
              "causal_order_proven": False, "client_receipt_proven": False, "complete_event_stream_proven": False, "source_authenticity_proven": False}
    try:
        module, helper = Path(__file__), Path(__file__).with_name("agentops_raw_events_v1.py")
        implementations = {module: module.read_bytes(), helper: helper.read_bytes()}
        plan = {"schema_version": "agentops-event-binding-plan/1", "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "raw_export": str(roots["raw"]), "public_export": str(roots["public"]),
                "implementation_sha256": _digest(implementations[module])["sha256"], "helper_sha256": _digest(implementations[helper])["sha256"]}
        captured = {"plan.json": _encode(plan), "source/agentops_event_binding_v1.py": implementations[module], "source/agentops_raw_events_v1.py": implementations[helper]}
        for name, content in captured.items():
            _write(output / name, content)
        for label, root in roots.items():
            inputs[label] = _inventory(root)
            for name, content in inputs[label].items():
                target = f"inputs/{label}/{name}"
                captured[target] = content
                _write(output / target, content)
        report = _compare_bytes(inputs["raw"], inputs["public"])
        report["input_receipts"] = {label: _digest(values["result.json"]) for label, values in inputs.items()}
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        try:
            report["inputs_unchanged"] = len(inputs) == 2 and all(_inventory(roots[label]) == content for label, content in inputs.items())
            _need(report["inputs_unchanged"], "Input exports changed or could not both be observed")
            report["implementation_unchanged"] = all(_regular(path).read_bytes() == content for path, content in implementations.items())
            _need(report["implementation_unchanged"], "Checker implementation changed during comparison")
            membership = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            report["captured_files_unchanged"] = membership == set(captured) and all(_regular(output / name).read_bytes() == content for name, content in captured.items())
            _need(report["captured_files_unchanged"], "Copied evidence changed during comparison")
        except (OSError, ValueError) as error:
            report.update(status="failed", preservation_error=f"{type(error).__name__}: {error}")
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["files"] = [{"path": path.relative_to(output).as_posix(), **_digest(path.read_bytes())}
                           for path in sorted(output.rglob("*")) if path.is_file()]
        _write(output / "result.json", _encode(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-export", type=Path, required=True)
    parser.add_argument("--public-export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = export_comparison(args.raw_export, args.public_export, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"status": report["status"], "pairs": report.get("verified_function_pairs"),
                      "unresolved": report.get("unresolved"), "error": report.get("error"), "receipt": str(args.output / "result.json")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
