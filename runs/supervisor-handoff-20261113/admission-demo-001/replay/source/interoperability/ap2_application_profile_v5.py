"""Received-request AP2 development admission with explicit incomplete coverage.

Only caller-held and captured public values are accepted. The finite relation
has one actual received message and does not repair it. Source fidelity and
eventual application completion require separate evaluation of the raw Tasks.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

from . import ap2_pending_admission_v4 as frozen
from . import refinement, refinement_oracle
from . import refinement_shared_lift_v2 as shared_lift

SCHEMA = "ap2-received-application-admission/5"
MERCHANT, EXTENSION = frozen.MERCHANT, frozen.EXTENSION
PAYMENT, CHECKOUT, TEXT = frozen.PAYMENT, frozen.CHECKOUT, frozen.TEXT
EDGE = "actual_original_tool_received_otp_continuation"
WORK_BUDGET = 100_000
SCOPE = "Only this public pending merchant Task and this received original OTP-tool message; incomplete finite/source coverage."
ASSUMPTIONS = [
    "The authored one-step relation projects the retained unchanged original merchant and processor demo branch.",
    "Actual public signing outputs, pending authority, risk and completed credential association are source observations, not evaluator gold.",
    "The allocation has fresh private signing state, no concurrent external Task writer, zero providers and disclosed offline/ASGI interventions.",
    "Only the uniquely offered original demo code 123 is modeled. Explicit wrong replies are never repaired or replaced.",
    "An independently valid certificate establishes finite-model semantics only; original application Tasks and receipts are evaluated separately.",
]
need, encoded, digest, same = frozen.need, frozen.encoded, frozen.digest, frozen.same
wire_message, decode_json, public_challenge, demo_response = (
    frozen.wire_message, frozen.decode_json, frozen.public_challenge, frozen.demo_response)
decode_journal = frozen.decode_journal


def literal_expression(value):
    if type(value) is dict:
        return {"object": {key: literal_expression(child) for key, child in value.items()}}
    if type(value) is list:
        return {"array": [literal_expression(child) for child in value]}
    need(type(value) in (str, int, bool, type(None)), "unmodeled_message_literal")
    return {"const": value}


def canonical_message(task, caller, message_id):
    """Expected original falsey-omitting builder message using captured values."""
    need(type(caller) is dict and caller.get("initiate_payment_task_id") == task["id"]
         and caller.get("shopping_context_id") == task["contextId"], "canonical_source_authority_missing")
    need(all(type(caller.get(key)) is str and caller[key] for key in
             ("payment_mandate_sdjwt", "checkout_mandate_sdjwt", "risk_data")),
         "canonical_original_mandates_or_risk_missing")
    pairs = [(PAYMENT, caller["payment_mandate_sdjwt"]),
             ("shopping_agent_id", "trusted_shopping_agent"), ("challenge_response", "123"),
             ("risk_data", caller["risk_data"]), (CHECKOUT, caller["checkout_mandate_sdjwt"])]
    return {"kind": "message", "role": "agent", "messageId": message_id,
            "taskId": task["id"], "contextId": task["contextId"],
            "parts": [{"kind": "text", "text": TEXT}] +
                     [{"kind": "data", "data": {key: value}} for key, value in pairs]}


def prepare_profile(task, caller, received, *, association_completed, now, valid_for_seconds=15):
    need(type(now) is int and type(valid_for_seconds) is int and 1 <= valid_for_seconds <= 15,
         "invalid_prospective_clock_interval")
    challenge = public_challenge(task)
    need(demo_response(challenge) == "123", "original_demo_recipe_unavailable")
    received = wire_message(received)
    need(type(received.get("messageId")) is str and received["messageId"], "received_message_identity_missing")
    expected = canonical_message(task, caller, received["messageId"])
    request = {"endpoint": MERCHANT, "operation": "send_a2a_message", "message": deepcopy(received)}
    bindings = {"merchant_task_id": task["id"], "shopping_context_id": task["contextId"],
                "original_message_id": received["messageId"], "payment_mandate_sdjwt": caller["payment_mandate_sdjwt"],
                "checkout_mandate_sdjwt": caller["checkout_mandate_sdjwt"], "risk_data": caller["risk_data"],
                "public_demo_response": "123", "credential_association_completed": association_completed}
    expected_expression = literal_expression(expected)
    for field, binding in (("taskId", "merchant_task_id"), ("contextId", "shopping_context_id"),
                           ("messageId", "original_message_id")):
        expected_expression["object"][field] = {"binding": binding}
    for index, key, binding in ((1, PAYMENT, "payment_mandate_sdjwt"), (3, "challenge_response", "public_demo_response"),
                                (4, "risk_data", "risk_data"), (5, CHECKOUT, "checkout_mandate_sdjwt")):
        expected_expression["object"]["parts"]["array"][index]["object"]["data"]["object"][key] = {"binding": binding}
    pending = {"merchant_task_id": task["id"], "shopping_context_id": task["contextId"],
               "original_task_completed": False, "source_mandates_preserved": True}
    completed = dict(pending, original_task_completed=True)
    profile = {
        "schema_version": "recipe-continuation/1", "id": "ap2-received-v5-" + task["id"],
        "model": {
            "schema_version": "finite-continuation/1", "id": "ap2-received-graph-v5-" + task["id"],
            "route": SCOPE,
            "provenance": {"kind": "authored-development", "source": "Public original-tool/Task observations at AP2 " + frozen.SOURCE_PIN,
                           "review_status": "Source fidelity is an explicit assumption; independently checked finite semantics only"},
            "horizon": 1, "evidence": {"complete": False, "observed_at": now, "valid_until": now + valid_for_seconds},
            "initial": "pending", "states": {"pending": pending, "projected_completion": completed},
            "transitions": [{"id": EDGE, "source": "pending", "target": "projected_completion",
                              "operation": "send_a2a_message_to_original_merchant"}],
            "runtime_contract": {
                "goal": [{"field": "original_task_completed", "op": "eq", "value": True}],
                "invariants": [{"field": key, "op": "eq", "value": pending[key]} for key in
                               ("merchant_task_id", "shopping_context_id", "source_mandates_preserved")]},
        },
        "initial_bindings": bindings,
        "relations": {EDGE: {
            "source_ref": "Unchanged original shopping_agent.tools.initiate_payment_with_otp builder and merchant/processor branch; " + SCOPE,
            "arguments": {}, "emit": literal_expression(request),
            "guards": [
                {"op": "eq", "left": {"emit_path": ["message"]}, "right": expected_expression},
                {"op": "eq", "left": {"binding": "credential_association_completed"}, "right": {"const": True}},
            ], "updates": {},
        }},
        "coverage": {"complete": False, "scope": SCOPE},
    }
    refinement.validate(profile)
    return {"schema_version": SCHEMA, "profile": profile, "pending_task": deepcopy(task),
            "canonical_caller": deepcopy(caller), "public_challenge": challenge,
            "original_request": request, "association_completed": association_completed,
            "assumptions": list(ASSUMPTIONS), "observed_task_completion": False,
            "whole_route_non_support_inference_allowed": False}


def verify_supported(prepared, result, now):
    need(result.get("decision") == "supported"
         and refinement_oracle.check_certificate(deepcopy(prepared["profile"]), deepcopy(result), now),
         "positive_fresh_independent_certificate_required")
    certificate = result.get("certificate", {})
    need(certificate.get("kind") == "recipe-path" and certificate.get("transition_ids") == [EDGE]
         and len(certificate.get("steps", [])) == 1
         and same(certificate["steps"][0]["request"], prepared["original_request"]),
         "certificate_not_the_actual_received_original_tool_request")
    return True


def evaluate_prepared(prepared, now, budget=WORK_BUDGET):
    identity = digest(prepared)
    result = shared_lift.evaluate(deepcopy(prepared["profile"]), now, budget=budget)
    need(digest(prepared) == identity, "received_input_mutated_during_admission")
    receipt = {"schema_version": SCHEMA, "solver_result": result, "decision": result["decision"],
               "input_sha256": identity, "profile_sha256": refinement.digest(prepared["profile"]),
               "evaluation_clock": now, "valid_until": prepared["profile"]["model"]["evidence"]["valid_until"],
               "certificate_valid": False, "dispatch_permitted": False, "work_budget": budget,
               "actual_task_completion_established_by_certificate": False,
               "whole_route_non_support_inference_allowed": False, "assumptions": list(ASSUMPTIONS)}
    try:
        verify_supported(prepared, result, now)
    except (ValueError, TypeError, KeyError) as error:
        receipt["refusal_reason"] = str(error)
    else:
        receipt.update(certificate_valid=True, dispatch_permitted=True)
    return receipt


def bind_pending_raw(task, exchanges):
    """Select the original payment-start response, independently of Task reads."""
    candidates = []
    for exchange in exchanges:
        if exchange["stream"] != "merchant_raw" or exchange.get("scope", {}).get("method") != "POST":
            continue
        request = decode_json(exchange["request_bytes"])
        if request.get("method") != "message/send":
            continue
        message = request.get("params", {}).get("message", {})
        texts = [part.get("text") for part in message.get("parts", []) if part.get("kind") == "text"]
        if message.get("taskId") or texts != ["Initiate a payment"]:
            continue
        response = decode_json(exchange["response_bytes"])
        actual = response.get("result", {})
        if actual.get("id") == task["id"]:
            candidates.append((exchange, actual))
    need(len(candidates) == 1, "one_actual_original_payment_start_required")
    exchange, actual = candidates[0]
    need("closed_at_global_index" in exchange and actual.get("contextId") == task["contextId"]
         and actual.get("status", {}).get("state") == "input-required"
         and same(public_challenge(actual), public_challenge(task)), "raw_pending_observation_mismatch")
    return {"stream": exchange["stream"], "exchange": exchange["exchange"],
            "closed_at_global_index": exchange["closed_at_global_index"],
            "first_global_index": exchange["first_global_index"],
            "response_bytes_sha256": hashlib.sha256(exchange["response_bytes"]).hexdigest(),
            "task_id": task["id"], "context_id": task["contextId"]}
