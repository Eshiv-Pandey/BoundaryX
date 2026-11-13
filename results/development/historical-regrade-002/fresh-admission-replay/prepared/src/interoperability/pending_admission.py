"""Admission at an observed AgentOps pending-task boundary.

The controller supplies public MCP observations and explicit deployment
assumptions. This module does not run applications, authenticate that deployment,
or assert that an emitted continuation has completed its task. The projected
goal remains original-task completion with the expected inventory effect under
the named deterministic fixture contract; live outcome checking is separate.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from . import refinement, refinement_oracle

SCHEMA = "agentops-pending-admission/1"
CONTRACT = "agentops-inventory-confirmation-fixture/1"
SERIALIZER = "mgcrea-raw-jsonrpc/1"
INITIAL_TEXT = "Restart inventory."
OBSERVATIONS = ("tools", "discovery", "initial", "pending", "raw")


class PendingInputError(ValueError):
    """Malformed envelope, as distinct from insufficient admission evidence."""


class ObservationUnavailable(ValueError):
    """A required public fact, compatibility obligation or assumption is missing."""


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _same(left: object, right: object) -> bool:
    return digest(left) == digest(right)


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise ObservationUnavailable(reason)


def _keys(value: object, keys: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != keys:
        raise PendingInputError(f"{label}: expected exactly {sorted(keys)}")


def _text(value: object) -> bool:
    return type(value) is str and bool(value)


def _unique(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise PendingInputError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise PendingInputError(f"non-JSON numeric constant: {value}")


def _decode(observation: dict) -> dict:
    body = observation["body"]
    _need(type(body) is dict and body.get("isError") is not True
          and body.get("isToolError") is not True, "public_tool_error")
    if type(body.get("structuredContent")) is dict:
        value = body["structuredContent"]
    else:
        content = body.get("content")
        _need(type(content) is list and bool(content) and type(content[0]) is dict
              and content[0].get("type") == "text" and _text(content[0].get("text")),
              "public_json_body_unavailable")
        try:
            value = json.loads(content[0]["text"], object_pairs_hook=_unique, parse_constant=_constant)
        except (ValueError, TypeError) as error:
            raise ObservationUnavailable("public_json_body_invalid") from error
    _need(type(value) is dict, "public_body_not_object")
    return value


def _origin(value: object) -> str:
    _need(_text(value), "public_origin_missing")
    try:
        url = urlsplit(value)
        _need(url.scheme == "http" and url.hostname == "127.0.0.1" and url.port is not None
              and not url.username and not url.password and not url.query and not url.fragment,
              "unsupported_local_origin")
        return f"http://127.0.0.1:{url.port}"
    except ValueError as error:
        raise ObservationUnavailable("invalid_origin") from error


def _state(value: object) -> str | None:
    return value.removeprefix("TASK_STATE_").replace("-", "_").lower() if type(value) is str else None


def _schema_accepts(schema: object, value: object, depth: int = 0) -> bool:
    """Validate only the documented public raw-tool schema subset; else abstain."""
    if depth > 16 or type(schema) is not dict:
        raise ObservationUnavailable("unmodeled_public_tool_schema")
    allowed = {"type", "properties", "required", "additionalProperties", "propertyNames",
               "enum", "default", "description", "title", "$schema", "format", "items"}
    _need(not set(schema) - allowed, "unmodeled_public_tool_schema")
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool,
             "null": type(None)}
    _need(kind is None or kind in types, "unmodeled_public_tool_type")
    if kind is not None and type(value) is not types[kind]:
        return False
    if "enum" in schema:
        _need(type(schema["enum"]) is list, "invalid_public_tool_enum")
        if not any(_same(value, option) for option in schema["enum"]):
            return False
    if "format" in schema:
        _need(schema["format"] == "uri" and type(value) is str, "unmodeled_public_tool_format")
        if not urlsplit(value).scheme:
            return False
    if type(value) is dict:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        _need(type(properties) is dict and type(required) is list
              and all(type(key) is str for key in required), "invalid_public_object_schema")
        if not set(required).issubset(value):
            return False
        for key, item in value.items():
            if "propertyNames" in schema and not _schema_accepts(schema["propertyNames"], key, depth + 1):
                return False
            if key in properties:
                if not _schema_accepts(properties[key], item, depth + 1):
                    return False
            else:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    return False
                if additional is not True and not _schema_accepts(additional, item, depth + 1):
                    return False
    if type(value) is list and "items" in schema:
        return all(_schema_accepts(schema["items"], item, depth + 1) for item in value)
    return True


def _call(name: str, arguments: dict) -> dict:
    return {"method": "tools/call", "params": {"name": name, "arguments": arguments}}


def _request(task: str, context: str, call: str, rationale: str, url: str) -> dict:
    return _call("a2a_request", {"url": url, "method": "SendMessage", "params": {
        "message": {"messageId": "agentops-public-confirmation", "role": "ROLE_USER",
            "taskId": task, "contextId": context, "parts": [{"data": {
                "id": call, "name": "adk_request_confirmation",
                "response": {"confirmed": True, "payload": {"rationale": rationale}}},
                "metadata": {"adk_type": "function_response"}}]}}})


def _extract(snapshot: dict, now: int) -> dict:
    _keys(snapshot, {"schema_version", "id", "route", "deployment", "observations",
                     "rationale", "proposed_call", "valid_until"}, "snapshot")
    if snapshot["schema_version"] != SCHEMA or not _text(snapshot["id"]):
        raise PendingInputError("invalid snapshot schema or ID")
    if type(now) is not int or type(snapshot["valid_until"]) is not int:
        raise PendingInputError("observation clocks must be integers")
    _keys(snapshot["route"], {"arm", "agent_base_url"}, "route")
    _keys(snapshot["deployment"], {"origin", "header_mode", "serializer", "service_contract"}, "deployment")
    _keys(snapshot["observations"], set(OBSERVATIONS), "observations")
    route, deployment, observations = snapshot["route"], snapshot["deployment"], snapshot["observations"]
    _need(route["arm"] in ("B5", "B6", "B7"), "unmodeled_route")
    origin = _origin(route["agent_base_url"])
    _need(urlsplit(route["agent_base_url"]).path in ("", "/"), "route_is_not_base_url")
    _need(_origin(deployment["origin"]) == origin, "deployment_origin_mismatch")
    _need(deployment["header_mode"] == "version-header", "version_header_not_established")
    _need(deployment["serializer"] == SERIALIZER, "unmodeled_serializer")
    _need(deployment["service_contract"] == CONTRACT, "unmodeled_service_effect_contract")
    _need(_text(snapshot["rationale"]), "rationale_unavailable")
    _need(0 < len(snapshot["rationale"].strip()) <= 500, "rationale_outside_source_guard")
    seqs, times = [], []
    for name in OBSERVATIONS:
        observation = observations[name]
        _need(type(observation) is dict, f"{name}_observation_missing")
        _keys(observation, {"seq", "body", "observed_at", "request"}, name)
        if type(observation["seq"]) is not int or observation["seq"] <= 0 or type(observation["observed_at"]) is not int:
            raise PendingInputError("invalid public observation sequence or clock")
        _keys(observation["request"], {"method", "params"}, name + ".request")
        seqs.append(observation["seq"]); times.append(observation["observed_at"])
    _need(seqs == sorted(set(seqs)), "public_observations_out_of_order")
    _need(times == sorted(times) and times[0] >= now - 300 and times[-1] <= now,
          "public_observations_not_fresh")
    _need(times[-1] <= now <= snapshot["valid_until"] <= times[-1] + 15,
          "pending_observation_expired_or_invalid_window")
    _need(_same(observations["tools"]["request"], {"method": "tools/list", "params": {}}),
          "tools_response_request_mismatch")
    listed = observations["tools"]["body"]
    _need(type(listed) is dict and type(listed.get("tools")) is list
          and listed.get("isError") is not True and listed.get("isToolError") is not True
          and "error" not in listed, "tools_list_unavailable")
    tools = [tool for tool in listed["tools"] if type(tool) is dict and tool.get("name") == "a2a_request"]
    _need(len(tools) == 1, "raw_tool_missing_or_ambiguous")
    tool = tools[0]
    _need(type(tool.get("annotations", {})) is dict
          and tool.get("annotations", {}).get("readOnlyHint") is not True, "raw_tool_read_only")
    _need(_same(observations["discovery"]["request"], _call("a2a_discover_agent", {"url": route["agent_base_url"]})),
          "discovery_request_mismatch")
    discovery = _decode(observations["discovery"])
    _need(_origin(discovery.get("url")) == origin, "discovery_origin_mismatch")
    card = discovery.get("card")
    interfaces = card.get("interfaces") if type(card) is dict else None
    _need(type(interfaces) is list, "public_interfaces_missing")
    interfaces = [item for item in interfaces if type(item) is dict and item.get("protocol") == "JSONRPC"]
    _need(bool(interfaces) and _origin(interfaces[0].get("url")) == origin, "raw_endpoint_header_origin_mismatch")
    _need(_same(observations["initial"]["request"], _call("a2a_send_message", {
        "url": route["agent_base_url"], "text": INITIAL_TEXT})), "initial_request_mismatch")
    initial = _decode(observations["initial"]).get("task")
    _need(type(initial) is dict and _text(initial.get("id")) and _text(initial.get("context_id")),
          "initial_public_binding_missing")
    task, context = initial["id"], initial["context_id"]
    _need(_same(observations["pending"]["request"], _call("a2a_get_task", {
        "task_id": task, "history_length": 100, "refresh": True})), "pending_request_mismatch")
    pending = _decode(observations["pending"])
    _need(pending.get("id") == task and pending.get("context_id") == context, "pending_association_changed")
    _need(_state(pending.get("state")) == "input_required", "pending_state_not_input_required")
    _need(_same(observations["raw"]["request"], _call("a2a_request", {
        "url": route["agent_base_url"], "method": "GetTask", "params": {"id": task, "historyLength": 100}})),
        "raw_request_mismatch")
    raw = _decode(observations["raw"])
    rpc_id = raw.get("id")
    _need(raw.get("jsonrpc") == "2.0" and type(rpc_id) in (str, int)
          and (type(rpc_id) is int or bool(rpc_id)) and "error" not in raw,
          "raw_rpc_error_or_invalid_envelope")
    raw_task = raw.get("result")
    _need(type(raw_task) is dict and raw_task.get("id") == task and raw_task.get("contextId") == context,
          "raw_association_changed")
    status = raw_task.get("status")
    _need(type(status) is dict and _state(status.get("state")) == "input_required", "raw_state_not_input_required")
    message = status.get("message")
    if type(message) is dict:
        _need(("taskId" not in message or message["taskId"] == task)
              and ("contextId" not in message or message["contextId"] == context),
              "confirmation_message_association_changed")
    parts = message.get("parts") if type(message) is dict else None
    _need(type(parts) is list, "raw_confirmation_parts_missing")
    calls = []
    for part in parts:
        if type(part) is not dict or type(part.get("metadata")) is not dict:
            continue
        data = part.get("data")
        if (part["metadata"].get("adk_type") == "function_call" and type(data) is dict
                and data.get("name") == "adk_request_confirmation"):
            calls.append(data)
    _need(len(calls) == 1 and _text(calls[0].get("id")), "confirmation_missing_or_ambiguous")
    call = calls[0]
    arguments = call.get("args")
    _need(type(arguments) is dict, "confirmation_target_unavailable")
    original = arguments.get("originalFunctionCall")
    confirmation = arguments.get("toolConfirmation")
    _need(type(original) is dict and _text(original.get("id")) and original.get("name") == "restart_service"
          and _same(original.get("args"), {"name": "inventory"}), "confirmation_target_mismatch")
    _need(type(confirmation) is dict and confirmation.get("confirmed") is False, "confirmation_not_pending")
    request = _request(task, context, call["id"], snapshot["rationale"], route["agent_base_url"])
    schema = tool.get("inputSchema")
    _need(type(schema) is dict and schema.get("type") == "object"
          and type(schema.get("properties")) is dict
          and schema["properties"].get("method", {}).get("enum") is not None,
          "raw_method_permission_unknown")
    _need(_schema_accepts(schema, observations["raw"]["request"]["params"]["arguments"])
          and _schema_accepts(schema, request["params"]["arguments"]), "raw_tool_does_not_accept_request")
    _need(_same(request, snapshot["proposed_call"]), "proposal_differs_from_public_bindings")
    return {"task": task, "context": context, "call": call["id"], "request": request,
            "origin": origin, "observed_at": times[-1]}


def build_profile(snapshot: dict, now: int) -> dict:
    facts = _extract(snapshot, now)
    bindings = {"task": facts["task"], "context": facts["context"], "call": facts["call"],
                "rationale": snapshot["rationale"], "url": snapshot["route"]["agent_base_url"]}
    # The template replaces only exact, named leaves, preserving correlations.
    request = copy.deepcopy(facts["request"])
    replacements = {("params", "arguments", "url"): "url",
        ("params", "arguments", "params", "message", "taskId"): "task",
        ("params", "arguments", "params", "message", "contextId"): "context",
        ("params", "arguments", "params", "message", "parts", 0, "data", "id"): "call",
        ("params", "arguments", "params", "message", "parts", 0, "data", "response", "payload", "rationale"): "rationale"}

    def expression(value, path=()):
        if path in replacements:
            return {"arg": replacements[path]}
        if type(value) is dict:
            return {"object": {key: expression(item, path + (key,)) for key, item in value.items()}}
        if type(value) is list:
            return {"array": [expression(item, path + (index,)) for index, item in enumerate(value)]}
        return {"const": value}

    identity = digest(snapshot)
    source = f"public-snapshot-sha256:{identity}; conditional fixture contract:{CONTRACT}"
    profile = {"schema_version": refinement.SCHEMA, "id": "pending-" + snapshot["id"],
        "model": {"schema_version": "finite-continuation/1", "id": "pending-graph-" + snapshot["id"],
            "route": "Observed public mgcrea raw continuation under explicit AgentOps fixture assumptions",
            "provenance": {"kind": "wire-derived", "source": source,
                           "review_status": "AI source map; caller supplied public snapshots and deployment, human review pending"},
            "horizon": 1, "evidence": {"complete": False, "observed_at": facts["observed_at"],
                                        "valid_until": snapshot["valid_until"]},
            "initial": "pending", "states": {
                "pending": {"original_task_complete": False, "expected_effect": False, "safe": True},
                "fixture_completion": {"original_task_complete": True, "expected_effect": True, "safe": True}},
            "transitions": [{"id": "public_confirmation", "source": "pending", "target": "fixture_completion",
                             "operation": "confirm_inventory_and_allow_fixture_completion"}],
            "runtime_contract": {"goal": [{"field": "original_task_complete", "op": "eq", "value": True},
                                          {"field": "expected_effect", "op": "eq", "value": True}],
                                 "invariants": [{"field": "safe", "op": "eq", "value": True}]}},
        "initial_bindings": bindings,
        "relations": {"public_confirmation": {"source_ref": source,
            "arguments": {key: [{"binding": key}] for key in bindings},
            "emit": expression(request), "guards": [], "updates": {}}},
        "coverage": {"complete": False, "scope": "One source-mapped public confirmation recipe and conditional fixture completion; not full public action-space closure"}}
    refinement.validate(profile)
    return profile


def admit_pending(snapshot: dict, now: int, budget: int | None = None) -> dict:
    identity = digest(snapshot)
    receipt = {"schema_version": "pending-admission-result/1", "status": "recorded", "decision": "unknown",
        "certificate_valid": None, "snapshot_sha256": identity, "evaluation_clock": now,
        "dispatch_permitted": False, "request": None, "profile": None, "result": None,
        "application_requests": 0, "application_completion_verified": False,
        "assumptions": ["Caller supplies genuine public observations and the declared deployment",
            "Server history matches the public confirmation and original call; identity/session/invocation remain valid",
            "Agent write kill-switch is off, inventory target exists, and the guarded atomic effect contract holds",
            "Server rationale redaction succeeds and its output remains within the 500-character guard",
            "Named deterministic fixture completion relation holds; serialized request alone does not prove safety or completion",
            "Fifteen-second local revalidation window is not a service TTL or an atomic lock"]}
    try:
        profile = build_profile(snapshot, now)
        receipt["profile"] = copy.deepcopy(profile)
        before = refinement.digest(profile)
        result = refinement.evaluate(profile, now, budget=budget)
        if before != refinement.digest(profile):
            raise PendingInputError("admission solver mutated profile")
        if type(result) is not dict or result.get("decision") not in ("supported", "unsupported", "unknown"):
            raise PendingInputError("malformed candidate result")
        receipt["result"] = result
        if result["decision"] == "unknown":
            if result.get("certificate") is not None:
                raise PendingInputError("unknown result has a certificate")
            receipt["reason"] = result.get("reason")
            return receipt
        valid = refinement_oracle.check_certificate(copy.deepcopy(profile), copy.deepcopy(result), now)
        receipt["certificate_valid"] = valid is True
        if valid is not True:
            raise PendingInputError("independent certificate check failed")
        if result["decision"] == "supported":
            certificate = result.get("certificate", {})
            steps = certificate.get("steps")
            if certificate.get("kind") != "recipe-path" or type(steps) is not list or len(steps) != 1:
                raise PendingInputError("expected one concrete public request witness")
            request = steps[0].get("request")
            expected = _extract(snapshot, now)["request"]
            if not _same(request, expected) or digest(snapshot) != identity:
                raise PendingInputError("certified request or snapshot changed")
            receipt.update(decision="supported", dispatch_permitted=True, request=copy.deepcopy(request))
        else:
            receipt["decision"] = "unsupported"
        receipt["reason"] = result.get("reason")
    except ObservationUnavailable as error:
        receipt["reason"] = str(error)
    except Exception as error:
        receipt.update(status="failed", decision="unknown", dispatch_permitted=False, request=None,
                       error=f"{type(error).__name__}: {error}")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--budget", type=int, default=100000)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing to overwrite existing admission receipt")
    raw = args.input.read_bytes()
    snapshot = json.loads(raw, object_pairs_hook=_unique, parse_constant=_constant)
    receipt = admit_pending(snapshot, args.now, args.budget)
    receipt["input_sha256"] = hashlib.sha256(raw).hexdigest()
    receipt["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["source_sha256"] = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                               for name in ("pending_admission.py", "refinement.py", "refinement_oracle.py", "manifest.py", "oracle.py")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: receipt[key] for key in ("status", "decision", "certificate_valid", "dispatch_permitted")}))
    return 0 if receipt["status"] == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
