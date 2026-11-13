"""Read-only consistency lanes for the original AP2 human-present public flow.

Inputs are caller-supplied A2A 0.3 JSON Message/Task observations. This module
does not authenticate a capture, verify a signature, execute AP2 or award a
task/native grade. Missing or ambiguous observations remain unknown.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import math


MANDATE_KEY = "ap2.mandates.PaymentMandateSdJwt"
RECEIPT_KEY = "ap2.PaymentReceipt"


def _lane(value, detail):
    return {"status": "unknown" if value is None else "consistent" if value else "discrepant",
            "detail": detail}


def _string(value):
    return isinstance(value, str) and bool(value)


def _identity(task):
    if not isinstance(task, dict):
        return None
    task_id, context_id = task.get("id"), task.get("contextId")
    return (task_id, context_id) if _string(task_id) and _string(context_id) else None


def _state(task):
    status = task.get("status") if isinstance(task, dict) else None
    return status.get("state") if isinstance(status, dict) else None


def _same_json(left, right):
    try:
        return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
            right, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return None


def _json_value(value):
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_json_value(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _json_value(item) for key, item in value.items())
    return False


def _parts(message):
    parts = message.get("parts") if isinstance(message, dict) else None
    return parts if isinstance(parts, list) else None


def _part_shape(part):
    if not isinstance(part, dict):
        return False
    kind = part.get("kind")
    if kind == "text":
        return isinstance(part.get("text"), str)
    if kind == "data":
        return isinstance(part.get("data"), dict)
    if kind == "file":
        value = part.get("file")
        return isinstance(value, dict) and (_string(value.get("uri")) or _string(value.get("bytes")))
    return False


def _one_data(message, key):
    parts = _parts(message)
    if parts is None:
        return None
    found = []
    for part in parts:
        if not _part_shape(part):
            return None
        if part.get("kind") == "data":
            data = part.get("data")
            if not isinstance(data, dict):
                return None
            if key in data:
                found.append(data[key])
    return found[0] if len(found) == 1 else None


def receipt_reference(presentation):
    """Exact source leaf/hash operation, with no JWT/signature validation."""
    if not _string(presentation):
        return None
    leaf = presentation.rsplit("~~", 1)[-1].split("~", 1)[0]
    if not leaf:
        return None
    try:
        encoded = leaf.encode("utf-8")
    except UnicodeError:
        return None
    return base64.urlsafe_b64encode(hashlib.sha256(encoded).digest()).decode("ascii").rstrip("=")


def _receipt(task):
    if not isinstance(task, dict) or not isinstance(task.get("artifacts"), list):
        return None, "Receipt artifacts are missing."
    found = []
    for artifact in task["artifacts"]:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("parts"), list):
            return None, "An artifact representation is incomplete."
        for part in artifact["parts"]:
            if not _part_shape(part):
                return None, "An artifact part representation is incomplete."
            if part.get("kind") == "data":
                data = part.get("data")
                if not isinstance(data, dict):
                    return None, "An artifact DataPart is incomplete."
                if RECEIPT_KEY in data:
                    found.append(data[RECEIPT_KEY])
    if len(found) != 1:
        return None, "A unique receipt cannot be selected from the supplied artifacts."
    return found[0], "One receipt occurrence was supplied."


def _success_projection(receipt):
    if not isinstance(receipt, dict):
        return False
    # Empty issuer is an original source output when the mandate has no pisp.
    return (receipt.get("status") == "Success" and isinstance(receipt.get("iss"), str)
            and type(receipt.get("iat")) is int
            and all(_string(receipt.get(k)) for k in (
                "reference", "payment_id", "psp_confirmation_id", "network_confirmation_id"))
            and receipt.get("error") is None and receipt.get("error_description") is None)


def _receipt_schema_projection(receipt):
    """Strict JSON types for the generated union, not SDK coercion equivalence."""
    if not isinstance(receipt, dict) or type(receipt.get("iat")) is not int:
        return False
    if not all(isinstance(receipt.get(key), str) for key in ("iss", "reference", "payment_id")):
        return False
    if receipt.get("status") == "Success":
        return (all(isinstance(receipt.get(key), str) for key in ("psp_confirmation_id", "network_confirmation_id"))
                and all(receipt.get(key) is None or isinstance(receipt.get(key), str)
                        for key in ("error", "error_description")))
    if receipt.get("status") == "Error":
        return (all(isinstance(receipt.get(key), str) for key in ("error", "error_description"))
                and all(receipt.get(key) is None or isinstance(receipt.get(key), str)
                        for key in ("psp_confirmation_id", "network_confirmation_id")))
    return False


def _continuity(pending, resume, after):
    identity = _identity(pending)
    if identity is None or not isinstance(resume, dict) or _identity(after) is None:
        return _lane(None, "Complete pending, continuation and later task identities are required.")
    if "taskId" not in resume or "contextId" not in resume:
        return _lane(None, "Continuation message taskId/contextId is missing.")
    supplied = (resume.get("taskId"), resume.get("contextId"))
    return _lane(supplied == identity == _identity(after),
                 "Compare the continuation message and later task with the supplied pending task/context.")


def _challenge(task):
    if _state(task) is None:
        return _lane(None, "Pending task state is absent.")
    status = task.get("status")
    challenge = _one_data(status.get("message"), "challenge")
    if challenge is None:
        return _lane(None, "A unique public challenge DataPart was not supplied.")
    return _lane(_state(task) == "input_required" and isinstance(challenge, dict)
                 and challenge.get("type") == "otp" and _string(challenge.get("display_text")),
                 "Check the original input_required status and public OTP DataPart, not a status.challenge field.")


def _after_state(resume, after):
    response = _one_data(resume, "challenge_response")
    state = _state(after)
    if not isinstance(response, str) or state is None:
        return _lane(None, "Challenge response or subsequent state is missing/ambiguous.")
    expected = "completed" if response == "123" else "input_required"
    return _lane(state == expected,
                 "Requested target: completed after 123, otherwise input_required. A downstream failure leaves completion unmet; it is not proof of source nonconformance or payment.")


def _success_absence(task):
    if not isinstance(task, dict) or not isinstance(task.get("artifacts"), list):
        return None
    for artifact in task["artifacts"]:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("parts"), list):
            return None
        for part in artifact["parts"]:
            if not _part_shape(part):
                return None
            if part.get("kind") == "data":
                data = part.get("data")
                if not isinstance(data, dict):
                    return None
                if RECEIPT_KEY in data:
                    receipt = data[RECEIPT_KEY]
                    if not isinstance(receipt, dict):
                        return None
                    if receipt.get("status") == "Success":
                        return False
    return True


def _retry_absence(resume, after):
    response = _one_data(resume, "challenge_response")
    if not isinstance(response, str) or response == "123":
        return _lane(None, "Incorrect-OTP receipt-absence lane is missing or not applicable.")
    return _lane(_success_absence(after), "An incorrect-OTP retry must not expose a Success receipt.")


def _forwarded(merchant, processor, key):
    left, right = _one_data(merchant, key), _one_data(processor, key)
    if not isinstance(left, str) or not isinstance(right, str):
        return _lane(None, "Unique typed values in both continuation messages are required.")
    return _lane(left == right, "Compare exact publicly supplied merchant and processor continuation values.")


def _challenge_propagation(merchant, processor):
    if _identity(processor) is None:
        return _lane(None, "Processor task/context observation is missing.")
    left = merchant.get("status", {}).get("message") if isinstance(merchant, dict) and isinstance(merchant.get("status"), dict) else None
    right = processor.get("status", {}).get("message") if isinstance(processor, dict) and isinstance(processor.get("status"), dict) else None
    if not isinstance(left, dict) or not isinstance(right, dict):
        return _lane(None, "Both public status messages are required.")
    if "taskId" not in right or "contextId" not in right:
        return _lane(None, "Processor status-message identity is missing.")
    identity = (right.get("taskId"), right.get("contextId"))
    equality = _same_json(left, right)
    return _lane(None if equality is None else equality and identity == _identity(processor),
                 "The merchant preserves the complete processor status Message and child identity, not a rewritten parent message.")


def _receipt_lanes(resume, after):
    receipt, detail = _receipt(after)
    if receipt is None:
        return {"receipt_projection": _lane(None, detail),
                "strict_json_receipt_schema_projection": _lane(None, detail),
                "receipt_reference": _lane(None, detail),
                "source_confirmation_ids": _lane(None, detail)}, None
    mandate = _one_data(resume, MANDATE_KEY)
    expected_reference = receipt_reference(mandate)
    projected = _success_projection(receipt)
    reference_match = None if expected_reference is None else (
        isinstance(receipt, dict) and receipt.get("reference") == expected_reference)
    payment_id = receipt.get("payment_id") if isinstance(receipt, dict) else None
    ids_match = None if not isinstance(receipt, dict) else (
        projected and _string(payment_id) and len(payment_id) == 32 and all(c in "0123456789abcdef" for c in payment_id)
        and payment_id[12] == "4" and payment_id[16] in "89ab"
        and receipt.get("payment_id") == receipt.get("psp_confirmation_id") == receipt.get("network_confirmation_id"))
    return {"receipt_projection": _lane(projected, "Check the source success-field projection; this is not full SDK schema or signature validation."),
            "strict_json_receipt_schema_projection": _lane(_receipt_schema_projection(receipt), "Strict JSON field types for the generated Success/Error union; extra fields are permitted. SDK coercion and signature trust are not assessed."),
            "receipt_reference": _lane(reference_match, "Compare with SHA256/base64url of the currently supplied mandate's closed JWT leaf."),
            "source_confirmation_ids": _lane(ids_match, "The original mock creator uses the same UUID4 hex payment_id for both confirmation IDs.")}, receipt


def assess_public_payment(initial_message, merchant_pending, resume_message, merchant_after, *,
                          processor_pending=None, processor_resume_message=None, processor_after=None):
    """Return separate consistency lanes, never an aggregate full-task result.

    Processor observations, if supplied, must come from its public exchanges.
    Their identity labels do not establish authenticated merchant-child linkage.
    Initial/resumed mandate equality is reported separately: the source may
    accept a different valid supplied mandate on the same pending task.
    """
    for value in (initial_message, merchant_pending, resume_message, merchant_after,
                  processor_pending, processor_resume_message, processor_after):
        if not _json_value(value):
            raise ValueError("Observations must be finite JSON values with string object keys.")
    initial_mandate = _one_data(initial_message, MANDATE_KEY)
    resumed_mandate = _one_data(resume_message, MANDATE_KEY)
    equality = None if not _string(initial_mandate) or not _string(resumed_mandate) else initial_mandate == resumed_mandate
    receipt_lanes, merchant_receipt = _receipt_lanes(resume_message, merchant_after)
    lanes = {"merchant_task_continuity": _continuity(merchant_pending, resume_message, merchant_after),
             "merchant_public_challenge": _challenge(merchant_pending),
             "initial_mandate_preserved": _lane(equality, "Observed equality only; a change is not an established source rejection or an aggregate failure."),
             "merchant_after_state": _after_state(resume_message, merchant_after), **receipt_lanes}
    if not isinstance(initial_message, dict) or "contextId" not in initial_message or _identity(merchant_pending) is None:
        initial_binding = None
    else:
        initial_binding = initial_message.get("taskId") is None and initial_message["contextId"] == _identity(merchant_pending)[1]
    lanes["initial_merchant_binding"] = _lane(initial_binding, "Original initiation has no taskId and uses the pending task's public context; this proves no shopper prelude.")
    lanes["merchant_pending_success_receipt_absence"] = _lane(_success_absence(merchant_pending), "No Success receipt is supplied before OTP continuation.")
    lanes["merchant_incorrect_otp_success_receipt_absence"] = _retry_absence(resume_message, merchant_after)
    processor_lanes, processor_receipt = _receipt_lanes(processor_resume_message, processor_after)
    lanes["processor_task_continuity"] = _continuity(processor_pending, processor_resume_message, processor_after)
    lanes["processor_public_challenge"] = _challenge(processor_pending)
    lanes["processor_after_state"] = _after_state(processor_resume_message, processor_after)
    lanes["processor_receipt_reference"] = processor_lanes["receipt_reference"]
    lanes["processor_receipt_projection"] = processor_lanes["receipt_projection"]
    lanes["processor_strict_json_receipt_schema_projection"] = processor_lanes["strict_json_receipt_schema_projection"]
    lanes["processor_source_confirmation_ids"] = processor_lanes["source_confirmation_ids"]
    lanes["processor_pending_success_receipt_absence"] = _lane(_success_absence(processor_pending), "No processor Success receipt is supplied before OTP continuation.")
    lanes["processor_incorrect_otp_success_receipt_absence"] = _retry_absence(processor_resume_message, processor_after)
    lanes["otp_forwarding"] = _forwarded(resume_message, processor_resume_message, "challenge_response")
    lanes["mandate_forwarding"] = _forwarded(resume_message, processor_resume_message, MANDATE_KEY)
    lanes["child_challenge_propagation"] = _challenge_propagation(merchant_pending, processor_pending)
    lanes["receipt_propagation"] = _lane(
        None if merchant_receipt is None or processor_receipt is None else (
            _receipt_schema_projection(merchant_receipt) and _receipt_schema_projection(processor_receipt)
            and _same_json(merchant_receipt, processor_receipt)),
        "Compare unique strict-schema-projected processor and merchant receipt objects with exact JSON types; equality is not full SDK validation or causal provenance.")
    if _identity(merchant_pending) is None or _identity(processor_pending) is None:
        shared_context = None
    else:
        shared_context = (_identity(merchant_pending)[1] == _identity(processor_pending)[1]
                          and _identity(merchant_pending)[0] != _identity(processor_pending)[0])
    lanes["distinct_child_task_shared_context"] = _lane(shared_context, "Distinct task IDs and matching public context do not authenticate child ownership.")
    return {"schema_version": "ap2-hp-public-assessment/1", "scope": "caller_supplied_public_observation_consistency_only",
            "lanes": deepcopy(lanes), "aggregate_task_grade": None,
            "source_authentication": "unknown", "capture_completeness": "unknown",
            "mandate_signature_verification": "unknown", "credential_transaction_association": "unknown",
            "original_stage_mapping_and_order": "unknown", "authority_expiry_amount_checks": "unknown", "user_consent": "unknown",
            "state_reset_and_effects": "unknown", "semantic_purchase_success": "unknown",
            "native_qualification_established": False, "scientific_novelty_established": False}
