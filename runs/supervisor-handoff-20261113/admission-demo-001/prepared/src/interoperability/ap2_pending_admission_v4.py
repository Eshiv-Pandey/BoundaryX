"""Finite AP2 demo admission from an actual public pending-task boundary.

This controller builds one declared recipe relation, rather than compiling the
whole AP2 interface. Its positive proof projects original-task completion under
the stated deterministic development contract. Actual completion and receipt
correspondence must be checked separately against original application outputs.
No application, provider, credential file or environment is read here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

from . import refinement, refinement_oracle
from . import refinement_shared_lift_v2 as shared_lift


MERCHANT = "http://localhost:8001/a2a/merchant_agent"
EXTENSION = "https://github.com/google-agentic-commerce/ap2/v1"
PAYMENT = "ap2.mandates.PaymentMandateSdJwt"
CHECKOUT = "ap2.mandates.CheckoutMandateSdJwt"
TEXT = "Initiate a payment. Include the challenge response."
SCHEMA = "ap2-public-pending-admission/4"
EDGE = "original_merchant_otp_continuation"
VALID_FOR_SECONDS = 15
WORK_BUDGET = 100_000
SOURCE_PIN = "e1ea56db72a6385bce3e5c1112b3a56ce60acb43"
SCOPE = (
    "Only this observed pending task, the one publicly offered demo response, "
    "the original caller-held mandates and the exact original builder message; "
    "no whole-interface closure or whole-route non-support claim."
)
ASSUMPTIONS = [
    "The authored finite relation faithfully projects the unchanged original "
    "merchant/processor demo continuation at the retained AP2 source pin.",
    "The public demo hint and deterministic original demo branch agree; the "
    "existing caller-held signed mandates remain associated and acceptable.",
    "The owned development allocation has no concurrent external task writer; "
    "its original handlers and task stores use the disclosed ASGI transport.",
    "Offline model fixtures select only offered original tools and supply the "
    "declared catalog fixture; they do not generate mandates or receipts.",
    "The single-step goal is a model projection of original-task completion, "
    "not an observed future Task, receipt or guarantee about arbitrary AP2 runs.",
    "The independent checker verifies supplied finite-model semantics only. "
    "Source fidelity, native TCP, live-provider and human-gold are separate.",
]


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def same(left, right):
    return encoded(left) == encoded(right)


def _text(value):
    return type(value) is str and bool(value) and len(value) <= 16_384


def decode_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("nonfinite_json")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def public_challenge(task):
    need(type(task) is dict and task.get("kind") == "task" and _text(task.get("id"))
         and _text(task.get("contextId")), "public_pending_task_identity_missing")
    status = task.get("status")
    need(type(status) is dict and status.get("state") == "input-required",
         "public_task_is_not_pending_input_required")
    message = status.get("message")
    need(type(message) is dict and message.get("kind") == "message"
         and message.get("contextId") == task["contextId"]
         and type(message.get("parts")) is list, "public_challenge_message_missing")
    challenges = [part["data"]["challenge"] for part in message["parts"]
                  if type(part) is dict and part.get("kind") == "data"
                  and type(part.get("data")) is dict and "challenge" in part["data"]]
    need(len(challenges) == 1 and type(challenges[0]) is dict,
         "unique_public_challenge_required")
    challenge = challenges[0]
    need(set(challenge) == {"type", "display_text"} and challenge["type"] == "otp"
         and _text(challenge["display_text"]), "unmodeled_public_challenge")
    return deepcopy(challenge)


def demo_response(challenge):
    need(type(challenge) is dict and challenge.get("type") == "otp"
         and _text(challenge.get("display_text")), "public_demo_otp_hint_missing")
    offered = re.findall(r"\(Demo only hint: the code is ([0-9]+)\)", challenge["display_text"])
    need(offered == ["123"], "public_demo_123_not_uniquely_offered")
    return offered[0]


def wire_message(message):
    """Remove only documented optional model nulls, preserving all data values."""
    need(type(message) is dict and type(message.get("parts")) is list,
         "message_projection_unavailable")
    result = deepcopy(message)
    for key in ("metadata", "extensions", "referenceTaskIds", "taskId", "contextId"):
        if key in result and result[key] is None:
            del result[key]
    for part in result["parts"]:
        need(type(part) is dict, "invalid_message_part")
        if "metadata" in part and part["metadata"] is None:
            del part["metadata"]
    return result


def _validate_original_request(message, task, caller, response):
    need(type(message) is dict and set(message) == {
        "kind", "role", "messageId", "taskId", "contextId", "parts", "metadata",
        "extensions", "referenceTaskIds"}, "unmodeled_original_builder_message_shape")
    need(message["kind"] == "message" and message["role"] == "agent"
         and _text(message["messageId"]) and message["taskId"] == task["id"]
         and message["contextId"] == task["contextId"], "original_builder_authority_mismatch")
    need(all(message[key] is None for key in ("metadata", "extensions", "referenceTaskIds")),
         "unmodeled_original_builder_optional_value")
    need(type(caller) is dict and caller.get("initiate_payment_task_id") == task["id"]
         and caller.get("shopping_context_id") == task["contextId"],
         "original_caller_pending_authority_mismatch")
    need(_text(caller.get("payment_mandate_sdjwt"))
         and _text(caller.get("checkout_mandate_sdjwt")), "caller_held_mandates_missing")
    risk = caller.get("risk_data", "")
    need(type(risk) is str, "unmodeled_original_risk_value")
    pairs = [(PAYMENT, caller["payment_mandate_sdjwt"]),
             ("shopping_agent_id", "trusted_shopping_agent"), ("challenge_response", response)]
    if risk:
        pairs.append(("risk_data", risk))
    pairs.append((CHECKOUT, caller["checkout_mandate_sdjwt"]))
    parts = message["parts"]
    need(type(parts) is list and len(parts) == len(pairs) + 1,
         "original_builder_part_count_mismatch")
    need(same(parts[0], {"kind": "text", "text": TEXT, "metadata": None}),
         "original_builder_text_mismatch")
    for part, (key, value) in zip(parts[1:], pairs):
        need(same(part, {"kind": "data", "data": {key: value}, "metadata": None}),
             "original_builder_caller_value_mismatch")
    return pairs


def prepare_profile(task, caller, message, response, now):
    """Use only public task values and values already held by the original caller."""
    need(type(now) is int, "evaluation_clock_must_be_integer")
    challenge = public_challenge(task)
    offered = demo_response(challenge)
    need(type(response) is str and response == offered, "response_not_the_public_demo_recipe")
    pairs = _validate_original_request(message, task, caller, response)
    bindings = {
        "merchant_task_id": task["id"], "shopping_context_id": task["contextId"],
        "public_pending_state": task["status"]["state"],
        "public_challenge_type": challenge["type"],
        "public_challenge_text": challenge["display_text"], "public_demo_response": offered,
        "original_message_id": message["messageId"],
        "payment_mandate_sdjwt": caller["payment_mandate_sdjwt"],
        "checkout_mandate_sdjwt": caller["checkout_mandate_sdjwt"],
        "risk_data": caller.get("risk_data", ""),
        "shopping_agent_id": pairs[1][1],
    }
    names = {PAYMENT: "payment_mandate_sdjwt", CHECKOUT: "checkout_mandate_sdjwt",
             "risk_data": "risk_data", "shopping_agent_id": "shopping_agent_id"}
    emitted_parts = [{"object": {"kind": {"const": "text"}, "text": {"const": TEXT},
                                 "metadata": {"const": None}}}]
    guards = []
    for index, (key, _) in enumerate(pairs, 1):
        expression = {"arg": "otp_response"} if key == "challenge_response" else {"binding": names[key]}
        emitted_parts.append({"object": {"kind": {"const": "data"}, "metadata": {"const": None},
                                          "data": {"object": {key: expression}}}})
        guards.append({"op": "eq", "left": {"emit_path": ["message", "parts", index, "data", key]},
                       "right": {"binding": "public_demo_response" if key == "challenge_response" else names[key]}})
    for field, binding in (("taskId", "merchant_task_id"), ("contextId", "shopping_context_id"),
                           ("messageId", "original_message_id")):
        guards.append({"op": "eq", "left": {"emit_path": ["message", field]},
                       "right": {"binding": binding}})
    projected = {"merchant_task_id": task["id"], "shopping_context_id": task["contextId"],
                 "caller_mandates_preserved": True, "original_task_completed": True}
    pending = dict(projected, original_task_completed=False)
    profile = {
        "schema_version": "recipe-continuation/1", "id": "ap2-public-otp-" + task["id"],
        "model": {
            "schema_version": "finite-continuation/1", "id": "ap2-public-otp-graph-" + task["id"],
            "route": "One original merchant pending-task continuation under explicit AP2 offline demo assumptions",
            "provenance": {"kind": "authored-development",
                           "source": "Actual public pending Task and caller-held builder values; AP2 source " + SOURCE_PIN,
                           "review_status": "AI-authored finite relation; source fidelity is an explicit assumption"},
            "horizon": 1, "evidence": {"complete": False, "observed_at": now,
                                       "valid_until": now + VALID_FOR_SECONDS},
            "initial": "public_pending", "states": {"public_pending": pending,
                                                        "projected_original_completion": projected},
            "transitions": [{"id": EDGE, "source": "public_pending", "target": "projected_original_completion",
                              "operation": "send_a2a_message_to_original_merchant"}],
            "runtime_contract": {
                "goal": [{"field": "original_task_completed", "op": "eq", "value": True}],
                "invariants": [{"field": "merchant_task_id", "op": "eq", "value": task["id"]},
                               {"field": "shopping_context_id", "op": "eq", "value": task["contextId"]},
                               {"field": "caller_mandates_preserved", "op": "eq", "value": True}]},
        },
        "initial_bindings": bindings,
        "relations": {EDGE: {
            "source_ref": "Authored projection of retained ReferenceCoordinator._payment_message and original merchant/processor demo branch; " + SCOPE,
            "arguments": {"otp_response": [{"binding": "public_demo_response"}]},
            "emit": {"object": {"endpoint": {"const": MERCHANT}, "operation": {"const": "send_a2a_message"},
                                  "message": {"object": {
                                      "kind": {"const": "message"}, "role": {"const": "agent"},
                                      "messageId": {"binding": "original_message_id"},
                                      "taskId": {"binding": "merchant_task_id"},
                                      "contextId": {"binding": "shopping_context_id"},
                                      "metadata": {"const": None}, "extensions": {"const": None},
                                      "referenceTaskIds": {"const": None}, "parts": {"array": emitted_parts}}}}},
            "guards": guards, "updates": {},
        }},
        "coverage": {"complete": False, "scope": SCOPE},
    }
    refinement.validate(profile)
    return {"schema_version": SCHEMA, "profile": profile, "pending_task": deepcopy(task),
            "original_request": {"endpoint": MERCHANT, "operation": "send_a2a_message", "message": deepcopy(message)},
            "public_challenge": challenge, "assumptions": list(ASSUMPTIONS),
            "observed_task_completion": False, "whole_route_non_support_inference_allowed": False}


def verify_supported(profile, result, request, now):
    need(type(result) is dict and result.get("decision") == "supported",
         "only_positive_model_relative_admission_can_dispatch")
    need(refinement_oracle.check_certificate(deepcopy(profile), deepcopy(result), now) is True,
         "independent_certificate_check_failed")
    certificate = result.get("certificate", {})
    need(certificate.get("kind") == "recipe-path" and certificate.get("transition_ids") == [EDGE]
         and type(certificate.get("steps")) is list and len(certificate["steps"]) == 1,
         "one_original_continuation_witness_required")
    need(same(certificate["steps"][0]["request"], request),
         "certified_request_differs_from_original_builder")
    return True


def evaluate_prepared(prepared, now, budget=WORK_BUDGET):
    profile, request = prepared["profile"], prepared["original_request"]
    identity = digest(prepared)
    result = shared_lift.evaluate(deepcopy(profile), now, budget=budget)
    need(digest(prepared) == identity, "pending_input_changed_during_admission")
    receipt = {"schema_version": SCHEMA, "status": "finite_model_admission_refused",
            "decision": result["decision"], "solver_result": result, "certificate_valid": False,
            "profile_sha256": refinement.digest(profile), "input_sha256": identity,
            "original_request_sha256": digest(request), "evaluation_clock": now,
            "valid_until": profile["model"]["evidence"]["valid_until"], "work_budget": budget,
            "dispatch_permitted": False, "scope": SCOPE, "assumptions": list(ASSUMPTIONS),
            "native_qualification_established": False, "aggregate_task_grade": None,
            "actual_task_completion_established_by_certificate": False,
            "whole_route_non_support_inference_allowed": False}
    try:
        verify_supported(profile, result, request, now)
    except (ValueError, KeyError, TypeError) as error:
        receipt["refusal_reason"] = str(error)
        return receipt
    receipt.update(status="positive_finite_model_admission_checked", certificate_valid=True,
                   dispatch_permitted=True)
    return receipt


def decode_journal(raw, durable):
    """Replay the retained raw ASGI bytes without changing frozen observers."""
    need(type(raw) is bytes and len(raw) <= 64 * 1024 * 1024, "journal_read_bound")
    events = [decode_json(line) for line in raw.splitlines()]
    next_sequence, exchanges = {}, {}
    for index, event in enumerate(events):
        need(event["global_index"] == index, "journal_global_sequence_gap")
        stream = event["stream"]
        row = durable.decode_value(event["payload"])
        expected = next_sequence.get(stream, 0)
        need(event["source_index"] == row["sequence"] == expected, "journal_source_sequence_gap")
        next_sequence[stream] = expected + 1
        if not stream.endswith("_raw"):
            continue
        exchange = exchanges.setdefault((stream, row["exchange"]), {
            "stream": stream, "exchange": row["exchange"], "request_bytes": b"", "response_bytes": b"",
            "first_global_index": index})
        if row["boundary"] == "scope":
            exchange["scope"] = row["value"]
        elif row["boundary"] == "receive_returned" and row["value"].get("type") == "http.request":
            exchange["request_bytes"] += row["value"].get("body", b"")
        elif row["boundary"] == "send_completed" and row["value"].get("type") == "http.response.body":
            exchange["response_bytes"] += row["value"].get("body", b"")
        elif row["boundary"] == "application_returned":
            exchange["closed_at_global_index"] = index
    checkpoint = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                  "events": len(events), "next_source_indices": next_sequence}
    return checkpoint, list(exchanges.values())


def rpc_exchange(exchange):
    need(exchange.get("scope", {}).get("method") == "POST" and "closed_at_global_index" in exchange,
         "closed_rpc_exchange_required")
    request, response = decode_json(exchange["request_bytes"]), decode_json(exchange["response_bytes"])
    need(request.get("jsonrpc") == response.get("jsonrpc") == "2.0"
         and request.get("id") == response.get("id") and "error" not in response
         and type(response.get("result")) is dict, "raw_rpc_correlation_or_result_missing")
    return request, response


def bind_pending_raw(task, exchanges):
    candidates = []
    for exchange in exchanges:
        if exchange["stream"] != "merchant_raw" or exchange.get("scope", {}).get("method") != "POST":
            continue
        request, response = rpc_exchange(exchange)
        if response["result"].get("id") == task["id"]:
            candidates.append((exchange, request, response))
    need(len(candidates) == 1, "one_captured_original_pending_merchant_response_required")
    exchange, request, response = candidates[0]
    actual = response["result"]
    need(actual.get("contextId") == task["contextId"]
         and actual.get("status", {}).get("state") == task["status"]["state"]
         and same(wire_message(actual["status"]["message"]), wire_message(task["status"]["message"]))
         and same(public_challenge(actual), public_challenge(task)), "raw_public_pending_authority_or_challenge_mismatch")
    need(request.get("method") == "message/send"
         and not request.get("params", {}).get("message", {}).get("taskId"),
         "pending_response_did_not_follow_original_start")
    headers = dict(exchange["scope"].get("headers", []))
    need(EXTENSION.encode() in headers.get(b"x-a2a-extensions", b"").split(b", "),
         "pending_raw_ap2_extension_missing")
    return {"stream": exchange["stream"], "exchange": exchange["exchange"],
            "first_global_index": exchange["first_global_index"],
            "closed_at_global_index": exchange["closed_at_global_index"],
            "request_bytes_sha256": hashlib.sha256(exchange["request_bytes"]).hexdigest(),
            "response_bytes_sha256": hashlib.sha256(exchange["response_bytes"]).hexdigest(),
            "public_pending_task_sha256": digest(task),
            "original_merchant_task_id": task["id"], "original_context_id": task["contextId"],
            "challenge_message_task_reference": task["status"]["message"].get("taskId"),
            "challenge_message_reference_is_merchant_authority": False}


def bind_raw_request(prepared, admission, raw, now):
    need(type(now) is int and admission.get("dispatch_permitted") is True
         and admission.get("certificate_valid") is True
         and admission.get("input_sha256") == digest(prepared)
         and admission.get("profile_sha256") == refinement.digest(prepared["profile"]),
         "admission_input_or_profile_changed_before_raw_dispatch")
    verify_supported(prepared["profile"], admission["solver_result"], prepared["original_request"], now)
    request = decode_json(raw)
    need(type(request) is dict and request.get("jsonrpc") == "2.0"
         and request.get("method") == "message/send" and "id" in request
         and type(request["id"]) in (str, int) and (type(request["id"]) is int or bool(request["id"]))
         and type(request.get("params")) is dict
         and type(request["params"].get("message")) is dict, "unmodeled_raw_continuation_request")
    need(same(wire_message(request["params"]["message"]),
              wire_message(prepared["original_request"]["message"])),
         "raw_request_differs_from_certified_original_builder")
    return {"schema_version": SCHEMA, "status": "raw_dispatch_bound_to_checked_positive_witness",
            "checked_at": now, "certificate_checked_at": admission["evaluation_clock"],
            "profile_sha256": admission["profile_sha256"], "input_sha256": admission["input_sha256"],
            "original_request_sha256": admission["original_request_sha256"],
            "raw_request": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
            "actual_rpc_id": request["id"], "actual_rpc_method": request["method"],
            "original_message_id": request["params"]["message"]["messageId"],
            "original_merchant_task_id": request["params"]["message"]["taskId"],
            "original_context_id": request["params"]["message"]["contextId"],
            "independent_checker_rechecked_at_dispatch": True,
            "actual_task_completion_established_by_certificate": False}


def verify_observed(prepared, admission, dispatch, raw, durable, public_records):
    checkpoint, exchanges = decode_journal(raw, durable)
    before = admission["journal_checkpoint_before_admission"]
    need(hashlib.sha256(raw[:before["bytes"]]).hexdigest() == before["sha256"],
         "admission_journal_prefix_changed")
    matched = [exchange for exchange in exchanges if exchange["stream"] == "merchant_raw"
               and exchange.get("scope", {}).get("method") == "POST"
               and hashlib.sha256(exchange["request_bytes"]).hexdigest() == dispatch["raw_request"]["sha256"]]
    need(len(matched) == 1, "one_raw_original_continuation_required")
    exchange = matched[0]
    request, response = rpc_exchange(exchange)
    need(exchange["first_global_index"] >= dispatch["journal_checkpoint_before_dispatch"]["events"]
         >= before["events"] > admission["pending_raw_binding"]["closed_at_global_index"],
         "admission_did_not_precede_raw_original_continuation")
    rebound = bind_raw_request(prepared, admission, exchange["request_bytes"], dispatch["checked_at"])
    need(all(same(dispatch[key], value) for key, value in rebound.items()), "retained_raw_dispatch_binding_changed")
    message_id = prepared["original_request"]["message"]["messageId"]
    public = [row for row in public_records if row["endpoint"] == MERCHANT
              and row["boundary"] == "attempt" and row["operation"] == "send_a2a_message"
              and row.get("public_value", {}).get("messageId") == message_id]
    need(len(public) == 1 and same(public[0]["public_value"], prepared["original_request"]["message"]),
         "public_original_dispatch_differs_from_checked_builder")
    final = response["result"]
    need(final.get("id") == prepared["pending_task"]["id"]
         and final.get("contextId") == prepared["pending_task"]["contextId"],
         "observed_continuation_authority_changed")
    return {"schema_version": SCHEMA, "status": "checked_admission_bound_to_actual_original_continuation",
            "profile_sha256": admission["profile_sha256"], "evaluation_clock": admission["evaluation_clock"],
            "raw_dispatch_clock": dispatch["checked_at"], "journal": checkpoint,
            "pending_raw_binding": admission["pending_raw_binding"], "raw_continuation_exchange": exchange["exchange"],
            "raw_continuation_first_global_index": exchange["first_global_index"],
            "raw_continuation_closed_at_global_index": exchange["closed_at_global_index"],
            "original_message_id": message_id, "original_merchant_task_id": final["id"],
            "original_context_id": final["contextId"], "actual_original_task_state": final["status"]["state"],
            "actual_original_task_completed": final["status"]["state"] == "completed",
            "observed_completion_is_separate_from_certificate": True, "scope": SCOPE,
            "native_qualification_established": False, "aggregate_task_grade": None,
            "whole_route_non_support_inference_allowed": False}
