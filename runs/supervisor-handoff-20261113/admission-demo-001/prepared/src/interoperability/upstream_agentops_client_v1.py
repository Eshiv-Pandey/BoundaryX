"""Once-only loopback A2A 1.0 transport for original application case inputs.

No SDK, agent, model, evaluator references, authentication or implicit retry is
used. Public task observations are transport evidence, never benchmark grades.
Readiness, application launch, resource gates and overall study policy belong
to the separately audited outer runner.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import socket
import stat
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4


SESSION_SCHEMA = "upstream-agentops-session-policy/1"
CASE_SCHEMA = "upstream-agentops-application-cases/1"
FAMILIES = {"agentops_agent_core", "agentops_agent_structured_report", "agentops_incident_workflow"}
DEFAULT_LIMITS = {"total_timeout_seconds": 180.0, "request_timeout_seconds": 45.0,
                  "poll_interval_seconds": 0.25, "max_polls": 60, "max_response_bytes": 32 * 1024 * 1024}
STATE_NAMES = {name: name for name in ("submitted", "working", "completed", "canceled", "failed", "rejected", "unknown")}
STATE_NAMES.update({"input_required": "input_required", "input-required": "input_required", "auth_required": "auth_required", "auth-required": "auth_required"})
STATE_NAMES.update({"TASK_STATE_" + name.upper(): name for name in ("submitted", "working", "completed", "canceled", "failed", "rejected", "unknown", "input_required", "auth_required")})


class EvidenceError(ValueError):
    """A preserved observation cannot establish the required transport binding."""


def _need(condition, message):
    if not condition:
        raise EvidenceError(message)


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def strict_json(raw):
    """Reject duplicate members, nonfinite constants and overflowed numbers."""
    if type(raw) is bytes:
        raw = raw.decode("utf-8")
    _need(type(raw) is str, "json_input_not_utf8_text")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _need(key not in result, "duplicate_json_member")
            result[key] = value
        return result
    def invalid(value):
        raise EvidenceError("nonfinite_json_constant: " + value)
    parsed = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    _encoded(parsed)
    return parsed


def _same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _text(value):
    return type(value) is str and bool(value.strip())


def _regular(path, directory=False):
    path = Path(path).absolute()
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        _need(not stat.S_ISLNK(info.st_mode)
              and not (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)), "linked_input_path")
    _need(path.is_dir() if directory else path.is_file(), "nonregular_input_path")
    return path


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    _regular(path.parent, True)
    with path.open("xb") as stream:
        stream.write(raw)


def _inventory(root):
    _regular(root, True)
    result = {}
    for path in sorted(root.rglob("*")):
        _regular(path, path.is_dir())
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def _endpoint(url):
    _need(type(url) is str, "endpoint_not_text")
    parsed = urlsplit(url)
    _need(parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port is not None
          and 1024 <= parsed.port <= 65535 and parsed.path == "/" and not parsed.query and not parsed.fragment
          and parsed.username is None and parsed.password is None
          and url == f"http://127.0.0.1:{parsed.port}/", "endpoint_not_exact_numeric_loopback_origin")
    return parsed.port


def _limits(supplied):
    result = dict(DEFAULT_LIMITS)
    if supplied is not None:
        _need(type(supplied) is dict and set(supplied) <= set(result), "unsupported_limits")
        result.update(supplied)
    for key, upper in (("total_timeout_seconds", 600), ("request_timeout_seconds", 60), ("poll_interval_seconds", 2)):
        value = result[key]
        _need(type(value) in (int, float) and math.isfinite(value) and 0 < value <= upper, "invalid_limit_" + key)
    for key, upper in (("max_polls", 120), ("max_response_bytes", 32 * 1024 * 1024)):
        _need(type(result[key]) is int and 0 < result[key] <= upper, "invalid_limit_" + key)
    return result


def _case(value):
    _need(type(value) is dict and set(value) == {"eval_set_id", "eval_id", "creation_timestamp", "session_input", "conversation"}, "unsupported_application_case_fields")
    _need(value["eval_set_id"] in FAMILIES and _text(value["eval_id"]), "unknown_case_family_or_id")
    _need(type(value["creation_timestamp"]) in (int, float) and math.isfinite(value["creation_timestamp"])
          and value["creation_timestamp"] >= 0, "unsupported_case_creation_timestamp")
    session = value["session_input"]
    _need(type(session) is dict and set(session) == {"app_name", "user_id", "state"}
          and _text(session["app_name"]) and _text(session["user_id"]) and type(session["state"]) is dict, "unsupported_source_session_input")
    _need(session["state"] == {}, "nonempty_source_state_requires_original_supported_initialization")
    turns = value["conversation"]
    _need(type(turns) is list and turns and len(turns) <= 32, "unsupported_source_conversation")
    seen = set()
    for turn in turns:
        _need(type(turn) is dict and set(turn) == {"invocation_id", "user_content", "creation_timestamp"}
              and _text(turn["invocation_id"]) and turn["invocation_id"] not in seen, "unsupported_or_duplicate_source_turn")
        seen.add(turn["invocation_id"])
        _need(type(turn["creation_timestamp"]) in (int, float) and math.isfinite(turn["creation_timestamp"])
              and turn["creation_timestamp"] >= 0, "unsupported_turn_creation_timestamp")
        content = turn["user_content"]
        _need(type(content) is dict and set(content) == {"role", "parts"} and content["role"] == "user"
              and type(content["parts"]) is list and content["parts"], "unsupported_source_user_content")
        _need(all(type(part) is dict and set(part) == {"text"} and _text(part["text"]) for part in content["parts"]), "unsupported_source_user_part")
    return value


def _session(policy, case):
    required = {"schema_version", "context_id", "source_session_input", "native_app_name_expected",
                "native_user_id_expected_from_source", "native_session_id_expected_from_source", "mapping_basis"}
    _need(type(policy) is dict and set(policy) == required and policy["schema_version"] == SESSION_SCHEMA, "unsupported_session_policy")
    context = policy["context_id"]
    _need(type(context) is str and str(UUID(context)) == context, "context_id_not_canonical_uuid")
    _need(_same(policy["source_session_input"], case["session_input"]), "source_session_policy_mismatch")
    _need(policy["native_app_name_expected"] == "agentops-agent"
          and policy["native_session_id_expected_from_source"] == context
          and policy["native_user_id_expected_from_source"] == "A2A_USER_" + context
          and _text(policy["mapping_basis"]), "unsupported_expected_native_mapping")
    return context


def load_case(path, eval_set_id, eval_id):
    """Select only an application input; never read evaluator references."""
    document = strict_json(_regular(path).read_bytes())
    _need(type(document) is dict and document.get("schema_version") == CASE_SCHEMA and type(document.get("cases")) is list, "unsupported_application_cases_document")
    selected = [value for value in document["cases"] if value.get("eval_set_id") == eval_set_id and value.get("eval_id") == eval_id]
    _need(len(selected) == 1, "source_case_not_unique")
    return _case(selected[0])


def _http(raw):
    """Decode one complete HTTP/1.1 message while retaining raw headers separately."""
    head, separator, body = raw.partition(b"\r\n\r\n")
    _need(separator and len(head) <= 65536, "incomplete_or_oversized_http_headers")
    lines = head.decode("iso-8859-1").split("\r\n")
    match = re.fullmatch(r"HTTP/1\.1 ([1-5][0-9]{2})(?: [^\r\n]*)?", lines[0])
    _need(match is not None, "unsupported_http_status_line")
    headers = []
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        _need(colon and re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) is not None
              and not any(ord(char) < 32 and char != "\t" for char in value), "malformed_http_header")
        headers.append([name, value.strip()])
    def values(name):
        return [value for key, value in headers if key.lower() == name]
    for name in ("content-length", "transfer-encoding", "content-type", "content-encoding"):
        _need(len(values(name)) <= 1, "duplicate_http_framing_or_content_header")
    encoding = values("content-encoding")
    _need(not encoding or encoding == ["identity"], "encoded_http_body_unsupported")
    transfer, length = values("transfer-encoding"), values("content-length")
    if transfer:
        _need(transfer[0].lower() == "chunked" and not length, "ambiguous_or_unsupported_http_framing")
        remaining, parts = body, []
        while True:
            line, sep, remaining = remaining.partition(b"\r\n")
            _need(sep and re.fullmatch(b"[0-9a-fA-F]+", line) is not None, "unsupported_or_incomplete_chunk_size")
            size = int(line, 16)
            if size == 0:
                _need(remaining == b"\r\n", "unsupported_chunk_trailers_or_trailing_bytes")
                body = b"".join(parts)
                break
            _need(len(remaining) >= size + 2 and remaining[size:size + 2] == b"\r\n", "incomplete_http_chunk")
            parts.append(remaining[:size])
            remaining = remaining[size + 2:]
    else:
        _need(length and re.fullmatch(r"[0-9]+", length[0]) is not None and len(body) == int(length[0]), "missing_or_mismatched_http_content_length")
    return int(match[1]), headers, body


class _Journal:
    def __init__(self, output, port, limits, deadline, captures, connection_guard=None):
        self.output, self.port, self.limits, self.deadline, self.captures = output, port, limits, deadline, captures
        self.connection_guard = connection_guard
        self.records = []

    def save(self, relative, raw):
        _need(relative not in self.captures, "duplicate_capture_allocation")
        _write(self.output / relative, raw)
        self.captures[relative] = raw

    def request(self, method, path, payload=None):
        left = self.deadline - time.monotonic()
        _need(left > 0, "case_deadline_before_request")
        sequence = len(self.records) + 1
        prefix = f"wire/{sequence:06d}/"
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        headers = [["Host", f"127.0.0.1:{self.port}"], ["Connection", "close"], ["Accept-Encoding", "identity"],
                   ["Accept", "application/json"], ["A2A-Version", "1.0"], ["Content-Length", str(len(body))]]
        if payload is not None:
            headers.append(["Content-Type", "application/json"])
        request = (f"{method} {path} HTTP/1.1\r\n" + "".join(f"{name}: {value}\r\n" for name, value in headers) + "\r\n").encode("ascii") + body
        record = {"schema_version": "upstream-agentops-client-exchange/1", "sequence": sequence, "method": method, "path": path,
                  "rpc_method": payload.get("method") if payload else None, "request_rpc_id": payload.get("id") if payload else None,
                  "request_headers": headers, "started_at_utc": datetime.now(timezone.utc).isoformat(), "started_monotonic_ns": time.monotonic_ns(),
                  "request_capture_representation": "prepared_http_request_bytes", "request_send_attempted": False,
                  "request_fully_sent": False, "response_eof": False, "http_body_complete": False, "status": "partial",
                  "connection_guard_configured": self.connection_guard is not None, "connection_guard_invoked": False,
                  "connection_guard_passed": False,
                  "redirects_followed": 0, "attempts": 1}
        self.records.append(record)
        self.save(prefix + "request.http.bin", request)
        self.save(prefix + "request.body.bin", body)
        response = bytearray()
        request_deadline = min(self.deadline, time.monotonic() + self.limits["request_timeout_seconds"])
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=min(left, self.limits["request_timeout_seconds"])) as connection:
                record.update(connected_local_endpoint=list(connection.getsockname()), connected_peer_endpoint=list(connection.getpeername()))
                if self.connection_guard is not None:
                    record["connection_guard_invoked"] = True
                    try:
                        self.connection_guard(connection)
                    except Exception as error:
                        record["connection_guard_error_type"] = type(error).__name__
                        raise EvidenceError("connection_guard_rejected: " + type(error).__name__) from error
                    record["connection_guard_passed"] = True
                remaining = request_deadline - time.monotonic()
                _need(remaining > 0, "request_deadline_before_send")
                connection.settimeout(remaining)
                record["request_send_attempted"] = True
                connection.sendall(request)
                record["request_fully_sent"] = True
                while True:
                    remaining = request_deadline - time.monotonic()
                    _need(remaining > 0, "request_deadline_while_receiving")
                    connection.settimeout(remaining)
                    chunk = connection.recv(65536)
                    if not chunk:
                        record["response_eof"] = True
                        break
                    response.extend(chunk)
                    _need(len(response) <= self.limits["max_response_bytes"], "response_byte_limit")
            status, received_headers, entity = _http(bytes(response))
            record.update(http_status=status, response_headers=received_headers, http_body_complete=True)
            self.save(prefix + "response.body.bin", entity)
            _need(status == 200, "http_status_" + str(status))
            content = [value for name, value in received_headers if name.lower() == "content-type"]
            _need(content and content[0].split(";", 1)[0].strip().lower() == "application/json", "unsupported_non_json_response")
            parsed = strict_json(entity)
            record.update(status="received", envelope=parsed,
                          response_rpc_id=parsed.get("id") if type(parsed) is dict else None,
                          response_rpc_id_type=type(parsed.get("id")).__name__ if type(parsed) is dict and "id" in parsed else None)
        except (OSError, ValueError, TypeError, OverflowError) as error:
            record["error"] = f"{type(error).__name__}: {error}"
            if prefix + "response.body.bin" not in self.captures:
                # This is an available undecoded prefix, never a complete entity claim.
                self.save(prefix + "response.body.bin", bytes(response).partition(b"\r\n\r\n")[2])
                record["response_body_representation"] = "available_undecoded_http_body_prefix"
        finally:
            self.save(prefix + "response.http.bin", bytes(response))
            record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), finished_monotonic_ns=time.monotonic_ns(),
                          request_digest=_digest(request), received_http_digest=_digest(bytes(response)))
            self.save(prefix + "exchange.json", _encoded(record))
        _need(record["status"] == "received", record.get("error", "partial_http_exchange"))
        return parsed, record


def _card(value, endpoint):
    _need(type(value) is dict and type(value.get("supportedInterfaces")) is list, "missing_declared_agent_interfaces")
    interfaces = [item for item in value["supportedInterfaces"] if type(item) is dict and item.get("url") == endpoint
                  and item.get("protocolBinding") == "JSONRPC"]
    _need(len(interfaces) == 1, "agent_card_does_not_uniquely_bind_loopback_jsonrpc_endpoint")
    _need(not value.get("security") and not value.get("securityRequirements"), "credential_authentication_unsupported")
    interface = interfaces[0]
    _need(not interface.get("tenant"), "unsupported_interface_tenant")
    legacy = value.get("protocolVersion")
    version_present = "protocolVersion" in interface
    if version_present:
        _need(interface["protocolVersion"] == "1.0", "agent_card_declares_non_1_0_interface")
        _need(legacy is None or legacy in ("0.3", "0.3.0", "1.0"), "unsupported_or_conflicting_global_card_version")
        advertisement = "declared_interface_1_0"
        request_basis = "Explicit selected interface protocolVersion=1.0; no SDK or alternate transport used"
    else:
        # Proto3 omission is an empty string, NOT an advertised 1.0 default.
        # Pinned ClientFactory sends CURRENT=1.0, selects a versionless interface,
        # treats empty as nonlegacy, then constructs native JsonRpcTransport.
        # The server's native dispatcher validates 1.0 for SendMessage/GetTask.
        # Its card serializer separately adds global legacy 0.3 compatibility
        # fields for that empty interface. Preserve this ambiguity as evidence.
        _need(legacy is None or legacy in ("0.3", "0.3.0"), "omitted_interface_version_has_unsupported_global_declaration")
        advertisement = "unresolved_omitted_interface_version"
        request_basis = (
            "Separate source-supported requested 1.0 attempt: pinned a2a ClientFactory sets CURRENT=1.0 header, "
            "accepts versionless interface, is_legacy_version(empty)=False, and selects native JsonRpcTransport; "
            "native JSONRPC dispatcher validates 1.0. Omitted interface field does not advertise a version.")
    _need("url" not in value or value["url"] == endpoint, "legacy_card_url_conflicts_with_selected_endpoint")
    _need("preferredTransport" not in value or value["preferredTransport"] == "JSONRPC", "legacy_transport_conflicts_with_selected_interface")
    _need(value.get("additionalInterfaces") is None or value["additionalInterfaces"] == [], "additional_legacy_interfaces_ambiguous_for_this_client")
    return {"declared_interface": interface, "interface_protocol_version_present": version_present,
            "interface_protocol_version": interface.get("protocolVersion"), "legacy_global_protocol_version": legacy,
            "advertised_1_0": version_present, "advertisement_qualification": advertisement,
            "requested_protocol_version": "1.0", "requested_version_basis": request_basis,
            "card_rewritten": False, "legacy_protocol_fallback_attempted": False,
            "native_protocol_qualification_established": False,
            "pinned_source_basis": [
                "agents/python/src/agent/server.py:286-295",
                "a2a/server/request_handlers/response_helpers.py:87-113",
                "a2a/compat/v0_3/conversions.py:916-951",
                "a2a/client/client_factory.py:82-84,101-127,232-256",
                "a2a/compat/v0_3/versions.py:8-19",
                "a2a/server/routes/jsonrpc_dispatcher.py:496-518",
            ]}


def _task(envelope, rpc_id, expected_context, expected_task=None, prior_tasks=()):
    _need(type(envelope) is dict and envelope.get("jsonrpc") == "2.0", "invalid_jsonrpc_envelope")
    _need("id" in envelope and type(envelope["id"]) is type(rpc_id) and envelope["id"] == rpc_id, "response_rpc_id_type_or_value_mismatch")
    _need(("result" in envelope) != ("error" in envelope), "ambiguous_jsonrpc_result_or_error")
    if "error" in envelope:
        raise EvidenceError("jsonrpc_error_response")
    result = envelope["result"]
    _need(type(result) is dict, "missing_task_result")
    if "task" in result:
        _need("message" not in result, "ambiguous_task_and_message_result")
        task, shape = result["task"], "wrapped_task"
    elif "status" in result and "id" in result:
        task, shape = result, "direct_task"
    elif "message" in result or result.get("kind") == "message":
        raise EvidenceError("message_only_reply_task_unresolved")
    else:
        raise EvidenceError("missing_or_unsupported_task_result")
    _need(type(task) is dict and _text(task.get("id")) and _text(task.get("contextId")), "missing_public_task_or_context")
    _need("kind" not in task or task["kind"] == "task", "contradictory_task_kind")
    _need(task["contextId"] == expected_context, "returned_task_context_mismatch")
    if expected_task is not None:
        _need(task["id"] == expected_task, "polled_task_id_mismatch")
    else:
        _need(task["id"] not in prior_tasks, "completed_task_reused_for_new_source_turn")
    status = task.get("status")
    _need(type(status) is dict and type(status.get("state")) is str and status["state"] in STATE_NAMES, "missing_or_unsupported_task_state")
    _need(task.get("history") is None or type(task["history"]) is list, "unsupported_task_history")
    _need(task.get("artifacts") is None or type(task["artifacts"]) is list, "unsupported_task_artifacts")
    _need(status.get("message") is None or type(status["message"]) is dict, "unsupported_status_message")
    return task, shape, STATE_NAMES[status["state"]]


def _observation(task, shape, state, sequence):
    return {"capture_sequence": sequence, "task_shape": shape, "observed_task_id": task["id"], "observed_context_id": task["contextId"],
            "state": state, "status": task["status"], "status_message": task["status"].get("message"),
            "history_present": "history" in task, "history": task.get("history"), "artifacts_present": "artifacts" in task,
            "artifacts": task.get("artifacts"), "observed_task_metadata": task.get("metadata"), "task": task}


def run_case(application_case, endpoint, output, *, session_policy, limits=None, source_case_path=None, connection_guard=None):
    """Preserve one original source case with no retries or confirmation answers.

    Every source turn creates a fresh public task in the same prospective context.
    A later turn is attempted only after the previous task is observed completed.
    Optional ``source_case_path`` must be the audited application-only cases JSON;
    its bytes and the supplied objects are checked for preservation.
    Optional ``connection_guard(sock)`` inspects each connected socket before
    this client sends bytes. It must return normally to accept the connection,
    or raise to reject it; it must not send or receive application bytes itself.
    Guard success records the callback's acceptance, not native ownership proof.
    """
    output = Path(output).absolute()
    _need(not output.exists() and not output.is_symlink(), "refusing_existing_output")
    if source_case_path is not None:
        _need(not output.resolve().is_relative_to(Path(source_case_path).absolute().parent.resolve()), "output_within_application_source_directory")
    output.mkdir(parents=True, exist_ok=False)
    _regular(output, True)
    captures, implementations, source_raw = {}, {}, None
    case_bytes = policy_bytes = None
    journal = None
    report = {"schema_version": "upstream-agentops-case-client/1", "status": "partial", "turns": [], "errors": [],
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "graded_upstream_cases": 0, "automatic_confirmations_sent": 0,
              "answer_attempts": 0, "hidden_retries": 0, "direct_model_calls": 0, "sdk_imports": 0, "native_processes_launched": 0,
              "model_calls_observed": None, "runtime_identity_authenticated": False, "runtime_identity_observed": False,
              "source_authenticity_proven": False, "causal_order_proven": False, "client_receipt_is_application_acceptance": False,
              "complete_event_stream_proven": False, "qualification_established": False,
              "connection_guard_configured": connection_guard is not None,
              "claim_scope": "Exact attempted HTTP requests and received responses plus bounded public task observations; no task/effect or upstream-case grade"}
    def save(name, raw):
        _write(output / name, raw)
        captures[name] = raw
    try:
        case_bytes, policy_bytes = _encoded(application_case), _encoded(session_policy)
        case, policy = strict_json(case_bytes), strict_json(policy_bytes)
        save("input-case.json", case_bytes)
        save("session-policy.json", policy_bytes)
        _case(case)
        _need(connection_guard is None or callable(connection_guard), "connection_guard_not_callable")
        context = _session(policy, case)
        port, configured = _endpoint(endpoint), _limits(limits)
        report.update(eval_set_id=case["eval_set_id"], eval_id=case["eval_id"], turns_total=len(case["conversation"]),
                      prospective_context_id=context, expected_native_session_mapping=policy, source_session_input=case["session_input"])
        if source_case_path is not None:
            source_raw = _regular(source_case_path).read_bytes()
            _need(len(source_raw) <= 16 * 1024 * 1024, "application_case_source_too_large")
            document = strict_json(source_raw)
            _need(type(document) is dict and document.get("schema_version") == CASE_SCHEMA and type(document.get("cases")) is list,
                  "unsupported_application_cases_document")
            selected = [item for item in document["cases"] if type(item) is dict and item.get("eval_set_id") == case["eval_set_id"] and item.get("eval_id") == case["eval_id"]]
            _need(len(selected) == 1, "source_case_not_unique")
            source = _case(selected[0])
            _need(_same(case, source), "supplied_case_differs_from_application_source")
            save("input/application-cases.json", source_raw)
            report["application_source_case_bound"] = True
        else:
            report["application_source_case_bound"] = False
        for path in (Path(__file__), Path(__file__).with_name("__init__.py")):
            implementations[path] = _regular(path).read_bytes()
            save("source/" + path.name, implementations[path])
        deadline = time.monotonic() + configured["total_timeout_seconds"]
        save("plan.json", _encoded({"schema_version": "upstream-agentops-case-client-plan/1", "endpoint": endpoint, "limits": configured,
                                    "case_digest": _digest(case_bytes), "session_policy_digest": _digest(policy_bytes),
                                    "application_source_digest": _digest(source_raw) if source_raw is not None else None,
                                    "source_files": {path.name: _digest(raw) for path, raw in implementations.items()},
                                    "prospective_context_id": context, "requested_protocol_version": "1.0", "transport": "JSONRPC",
                                    "protocol_version_negotiated": False, "agent_card_advertisement_not_yet_observed": True,
                                    "source_invocation_ids_are_labels_only": True, "new_task_per_source_turn": True,
                                    "expected_runtime_mapping_is_observed_or_authenticated": False, "automatic_approval": False,
                                    "connection_guard_configured": connection_guard is not None,
                                    "connection_guard_acceptance_is_native_ownership_proof": False}))
        journal = _Journal(output, port, configured, deadline, captures, connection_guard)
        card, card_record = journal.request("GET", "/.well-known/agent-card.json")
        card_binding = _card(card, endpoint)
        report["agent_card_binding"] = {"capture_sequence": card_record["sequence"], **card_binding}
        prior_tasks = []
        for index, source_turn in enumerate(case["conversation"]):
            turn = {"turn_index": index, "source_invocation_id": source_turn["invocation_id"], "source_user_content": source_turn["user_content"],
                    "new_task_requested": True, "completed_task_id_resent": False, "observations": [], "status": "partial", "outcome": "unresolved"}
            report["turns"].append(turn)
            rpc_id, message_id = str(uuid4()), str(uuid4())
            message = {"messageId": message_id, "role": "ROLE_USER", "contextId": context,
                       "parts": [{"text": part["text"]} for part in source_turn["user_content"]["parts"]]}
            request = {"jsonrpc": "2.0", "id": rpc_id, "method": "SendMessage", "params": {"message": message}}
            turn.update(message_id=message_id, send_rpc_id=rpc_id)
            envelope, record = journal.request("POST", "/", request)
            turn["send_capture_sequence"] = record["sequence"]
            task, shape, state = _task(envelope, rpc_id, context, prior_tasks=prior_tasks)
            turn["observations"].append(_observation(task, shape, state, record["sequence"]))
            turn.update(task_id=task["id"], observed_context_id=task["contextId"])
            polls = 0
            while state in {"submitted", "working"}:
                _need(polls < configured["max_polls"], "poll_limit_reached")
                left = deadline - time.monotonic()
                _need(left > 0, "case_poll_deadline_reached")
                time.sleep(min(configured["poll_interval_seconds"], left))
                rpc_id = str(uuid4())
                request = {"jsonrpc": "2.0", "id": rpc_id, "method": "GetTask", "params": {"id": task["id"], "historyLength": 100}}
                envelope, record = journal.request("POST", "/", request)
                polls += 1
                task, shape, state = _task(envelope, rpc_id, context, expected_task=turn["task_id"])
                turn["observations"].append(_observation(task, shape, state, record["sequence"]))
            turn.update(polls=polls, final_state=state)
            if state == "input_required":
                turn.update(status="recorded", outcome="input_required_no_approval_sent")
                report.update(status="recorded", stopped_for_input_required=True)
                break
            if state != "completed":
                turn["outcome"] = "observed_terminal_state_" + state
                raise EvidenceError("source_turn_did_not_complete: " + state)
            turn.update(status="recorded", outcome="observed_completed_without_grade")
            prior_tasks.append(task["id"])
        else:
            report["status"] = "recorded"
    except (OSError, ValueError, TypeError, KeyError, OverflowError, AttributeError) as error:
        problem = {"type": type(error).__name__, "message": str(error)}
        report["errors"].append(problem)
        if report["turns"]:
            current = report["turns"][-1]
            current["error"] = problem
            current["last_observed_state"] = current["observations"][-1]["state"] if current["observations"] else None
            current["poll_observations"] = max(0, len(current["observations"]) - 1)
        report["status"] = "partial"
    finally:
        report.update(turns_attempted=len(report["turns"]), turns_completed=sum(turn.get("final_state") == "completed" for turn in report["turns"]),
                      http_requests=len(journal.records) if journal else 0,
                      a2a_requests=sum(record["method"] == "POST" for record in journal.records) if journal else 0,
                      exchanges=journal.records if journal else [], finished_at_utc=datetime.now(timezone.utc).isoformat())
        try:
            report["input_objects_unchanged"] = case_bytes is not None and policy_bytes is not None and _encoded(application_case) == case_bytes and _encoded(session_policy) == policy_bytes
            report["application_source_unchanged"] = source_raw is None or _regular(source_case_path).read_bytes() == source_raw
            report["implementation_unchanged"] = bool(implementations) and all(_regular(path).read_bytes() == raw for path, raw in implementations.items())
            report["captured_files_unchanged"] = _inventory(output) == captures
            _need(report["input_objects_unchanged"] and report["application_source_unchanged"] and report["captured_files_unchanged"], "client_input_or_capture_changed")
            if implementations:
                _need(report["implementation_unchanged"], "client_implementation_changed")
        except (OSError, ValueError, TypeError) as error:
            report["status"] = "failed"
            report["preservation_error"] = f"{type(error).__name__}: {error}"
        report["files"] = [{"path": name, **_digest(raw)} for name, raw in sorted(_inventory(output).items())]
        _write(output / "result.json", _encoded(report))
    return report
