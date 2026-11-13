"""Stdlib realization of the original AgentOps required-trajectory metric.

Source: agents/python/evals/required_trajectory.py. This metric accepts an
ordered subsequence and recursively required arguments, including batched
array order. It does not assess responses, causality, state, answers or native
qualification. Stronger evidence obligations must be reported separately.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import math


SCHEMA = "agentops-required-trajectory-score/1"


def contains_required(actual, required):
    """Preserve the original recursive subset/default/bool semantics."""
    if isinstance(required, list):
        return (isinstance(actual, list) and len(actual) == len(required)
                and all(contains_required(a, r) for a, r in zip(actual, required)))
    if not isinstance(required, Mapping):
        if isinstance(actual, bool) or isinstance(required, bool):
            return type(actual) is type(required) and actual == required
        return actual == required
    if not isinstance(actual, Mapping):
        return False
    for key, value in required.items():
        if key not in actual:
            if isinstance(value, str) and value == "":
                continue
            return False
        if not contains_required(actual[key], value):
            return False
    return True


def _call(value):
    if type(value) is not dict or type(value.get("name")) is not str or not value["name"]:
        raise ValueError("function call must contain a nonempty name")
    args = value.get("args")
    if args is not None and type(args) is not dict:
        raise ValueError("function arguments must be an object or null")
    _finite(value)
    return value


def _finite(value):
    # Native protobuf JSON/retained source inputs live in this finite JSON
    # domain; this is validation, not an alternative equality rule.
    if type(value) is float and not math.isfinite(value):
        raise ValueError("nonfinite observation is unsupported")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("JSON object keys must be strings")
        for item in value.values():
            _finite(item)
    elif type(value) is list:
        for item in value:
            _finite(item)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("non-JSON observation is unsupported")


def required_tools_in_order(actual_calls, expected_calls):
    """Return source-equivalent subsequence result and its selected indices."""
    if type(actual_calls) is not list or type(expected_calls) is not list:
        raise ValueError("call sequences must be lists")
    for value in (*actual_calls, *expected_calls):
        _call(value)
    cursor, selected = 0, []
    for expected in expected_calls:
        while cursor < len(actual_calls):
            index, actual = cursor, actual_calls[cursor]
            cursor += 1
            if actual["name"] == expected["name"] and contains_required(actual.get("args") or {}, expected.get("args") or {}):
                selected.append(index)
                break
        else:
            return {"matches": False, "matched_actual_indices": selected, "first_unmatched_required_index": len(selected)}
    return {"matches": True, "matched_actual_indices": selected, "first_unmatched_required_index": None}


def get_all_tool_calls(intermediate_data):
    """Project the two original SDK serialized intermediate-data forms."""
    if intermediate_data is None or intermediate_data == {}:
        return []
    if type(intermediate_data) is not dict:
        raise ValueError("unsupported serialized intermediate-data type")
    has_uses, has_events = "tool_uses" in intermediate_data, "invocation_events" in intermediate_data
    if has_uses and has_events:
        raise ValueError("ambiguous intermediate-data representation")
    if has_uses:
        calls = intermediate_data["tool_uses"]
        if type(calls) is not list:
            raise ValueError("tool_uses must be a list")
        return [_call(item) for item in calls]
    if not has_events or type(intermediate_data["invocation_events"]) is not list:
        raise ValueError("unsupported serialized intermediate-data representation")
    calls = []
    for event in intermediate_data["invocation_events"]:
        if type(event) is not dict:
            raise ValueError("invocation event must be an object")
        content = event.get("content")
        if content is None:
            continue
        if type(content) is not dict:
            raise ValueError("event content must be an object or null")
        parts = content.get("parts")
        if parts is None:
            continue
        if type(parts) is not list:
            raise ValueError("event parts must be a list")
        for part in parts:
            if type(part) is not dict or part.get("functionCall") is not None:
                raise ValueError("unsupported function part representation")
            call = part.get("function_call")
            if call is not None:
                calls.append(_call(call))
    return calls


def invocations_from_events(events):
    """Group emitted events by first-seen invocation ID, without UUID/time sort.

    The source EvaluationGenerator groups by invocation_id, skips user content,
    and preserves function-call parts, even on its final response. For this
    calls-only metric the other final/text metadata does not affect the result.
    These are caller-supplied observations, not an authenticated stream.
    """
    if type(events) is not list:
        raise ValueError("events must be a list")
    groups = {}
    for event in events:
        if type(event) is not dict or type(event.get("invocation_id")) is not str or not event["invocation_id"]:
            raise ValueError("actual event invocation identity is missing")
        _finite(event)
        groups.setdefault(event["invocation_id"], []).append(event)
    output = []
    for identity, group in groups.items():
        selected = []
        for event in group:
            if str(event.get("author") or "agent").lower() == "user":
                continue
            selected.append({"content": event.get("content"), "author": event.get("author")})
        output.append({"invocation_id": identity, "intermediate_data": {"invocation_events": selected}})
    return output


def score_invocations(actual_invocations, expected_invocations, *, threshold=1.0):
    """Score the configured original metric; assign no stronger task grade."""
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be a finite number from zero to one")
    if type(actual_invocations) is not list or type(expected_invocations) is not list:
        raise ValueError("actual and expected invocations must be lists")
    if len(actual_invocations) != len(expected_invocations):
        raise ValueError("actual and expected invocation counts must match")
    _finite(actual_invocations)
    _finite(expected_invocations)
    results = []
    for index, (actual, expected) in enumerate(zip(actual_invocations, expected_invocations)):
        if type(actual) is not dict or type(expected) is not dict:
            raise ValueError("invocations must be objects")
        observed = get_all_tool_calls(actual.get("intermediate_data"))
        required = get_all_tool_calls(expected.get("intermediate_data"))
        match = required_tools_in_order(observed, required)
        score = float(match["matches"])
        results.append({"turn_index": index, "actual_invocation_id": actual.get("invocation_id"),
                        "expected_invocation_label": expected.get("invocation_id"),
                        "observed_calls": observed, "required_calls": required, **match,
                        "score": score, "eval_status": "passed" if score >= threshold else "failed"})
    overall = sum(item["score"] for item in results) / len(results) if results else None
    return {"schema_version": SCHEMA, "metric_name": "tool_trajectory_avg_score", "match_type": "IN_ORDER",
            "threshold": threshold, "overall_score": overall,
            "overall_eval_status": ("passed" if overall >= threshold else "failed") if overall is not None else None,
            "per_invocation_results": results, "configured_source_metric_only": True,
            "extra_actual_calls_allowed": True, "required_arguments_are_recursive_subset": True,
            "batch_array_order_can_satisfy_metric": True, "call_response_success_assessed": False,
            "awaited_dependencies_proven": False, "answer_grounding_assessed": False,
            "state_effects_assessed": False, "complete_native_stream_proven": False,
            "native_source_case_qualification": False, "full_task_grade_assigned": False}
