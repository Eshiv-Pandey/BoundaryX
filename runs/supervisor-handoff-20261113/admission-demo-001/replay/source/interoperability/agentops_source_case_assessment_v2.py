"""Separate source-case assessment lanes over caller-supplied observations.

The frozen v1 metric is preserved. Reply/value consistency, finite sampled
effects and optional answer/schema checks never become a combined task grade.
This pure API reads no filesystem and authenticates no supplied observation.
"""
from __future__ import annotations

from copy import deepcopy

from .agentops_reply_dependencies_v1 import assess_reply_dependencies
from .agentops_source_case_assessment_v1 import _finite, _need, _same, assess_source_case as assess_metric
from .agentops_source_case_effects_v1 import MEMORY_KEY, NOTE, PREFIX, SUFFIX, assess_source_case_effects


SCHEMA = "agentops-source-case-assessment/2"


def _bind_obligation(application, expectation, obligation):
    """Check exact projection/obligation identity without authenticating it."""
    _finite(obligation)
    _need(type(obligation) is dict, "source case obligation must be an object")
    key = application["eval_set_id"] + "/" + application["eval_id"]
    _need(obligation.get("key") == key
          and obligation.get("eval_set_id") == application["eval_set_id"]
          and obligation.get("eval_id") == application["eval_id"]
          and obligation.get("does_not_grant_new_tools") is True,
          "source obligation identity/tool scope differs from source projections")
    count = len(application["conversation"])
    turns = obligation.get("turns")
    _need(type(obligation.get("turn_count")) is int and obligation["turn_count"] == count
          and type(turns) is list and len(turns) == count, "source obligation turn count differs")
    for index, (turn, source, reference) in enumerate(zip(turns, application["conversation"], expectation["conversation"]), 1):
        _need(type(turn) is dict and type(turn.get("turn_index")) is int and turn["turn_index"] == index
              and turn.get("source_invocation_label") == source["invocation_id"],
              "ordered obligation/source invocation labels differ")
        metric = turn.get("original_metric")
        _need(type(metric) is dict and metric.get("name") == "tool_trajectory_avg_score"
              and metric.get("reference_final_response_not_scored") is True
              and metric.get("reply_content_not_scored") is True
              and _same(metric.get("expected_calls"), reference["intermediate_data"]["tool_uses"]),
              "obligation configured metric differs from original expectations")
        required = metric.get("required_trajectory")
        _need(type(required) is list and len(required) == len(metric["expected_calls"]),
              "required reply trajectory differs from original expected calls")
        for sequence, (item, expected) in enumerate(zip(required, metric["expected_calls"]), 1):
            _need(type(item) is dict and type(item.get("sequence")) is int and item["sequence"] == sequence
                  and item.get("name") == expected["name"] and _same(item.get("required_args"), expected["args"]),
                  "reply/dependency required call differs from original expected call")


def _memory_profile(replies, effects, obligation, user, session, fixture):
    """Use only unique supported replies selected for the two source calls.

    Ambiguous/repeated/missing/partial observations stay unavailable. All
    occurrences remain in the reply lane; this selection never deduplicates.
    """
    observation = {"status": "not_applicable", "selection_is_observed_consistency_only": True,
                   "original_sanitizer_executed_here": False, "reply_observation_refs": []}
    if obligation["key"] != MEMORY_KEY:
        _need(fixture is None, "sanitizer fixture is only applicable to the memory-note source case")
        return None, observation
    observation["status"] = "unknown"
    row = effects["inserted_memory_row"]
    if row is None:
        observation["reason"] = "A sampled single inserted row is required before display consistency can be checked."
        return None, observation
    selected = []
    for turn_index, name in ((1, "save_incident_note"), (2, "recall_incident_context")):
        turn = replies["turns"][turn_index - 1]
        required = turn["required_reply_assessments"]
        if len(required) != 1 or required[0]["status"] != "supported":
            observation["reason"] = "Unique supported required save and recall replies are unavailable."
            return None, observation
        indices = required[0].get("attributed_reply_observation_indices")
        if type(indices) is not list or len(indices) != 1 or type(indices[0]) is not int:
            observation["reason"] = "Required reply attribution is unavailable."
            return None, observation
        reply = turn["tool_replies"][indices[0]]
        selected_call = required[0].get("selected_call_observation_index")
        if (type(selected_call) is not int or turn["tool_calls"][selected_call]["partial"]
                or reply["name"] != name or reply["source_contract_classification"] != "success_reply" or reply["partial"]):
            observation["reason"] = "The required complete source-shaped save or recall reply is unavailable."
            return None, observation
        selected.append(reply)
        observation["reply_observation_refs"].append({"turn_index": turn_index,
            **{field: deepcopy(reply[field]) for field in ("observation_index", "event_id", "invocation_id", "global_yield_sequence", "part_index")}})
    if selected[0]["global_yield_sequence"] >= selected[1]["global_yield_sequence"]:
        observation["reason"] = "Save/recall displayed reply order differs."
        return None, observation
    displayed = selected[0]["payload"]["saved"]["note"]
    representation = "source_spotlight" if displayed == PREFIX + "\n" + row["note"] + "\n" + SUFFIX else "raw"
    profile = {"schema_version": "agentops-source-memory-note-observation/1", "native_user_id": user,
               "native_session_id": session, "incident_id": "INC-010", "source_note_input": NOTE,
               "save_reply_representation": representation, "save_reply": deepcopy(selected[0]["payload"]),
               "recall_reply": deepcopy(selected[1]["payload"])}
    if fixture is not None:
        profile["original_sanitizer_fixture"] = deepcopy(fixture)
    observation.update(status="selected_unique_supported_replies", representation=representation,
                       supplied_single_sanitizer_fixture=fixture is not None)
    return profile, observation


def assess_source_case(journal_validation, application_case, expectation_case, case_obligation,
                       boundary_evidence, *, expected_native_user_id, expected_native_session_id,
                       original_sanitizer_fixture=None, source_extraction_bindings=None):
    """Bind observations and return independent lanes; malformed bindings raise.

    Call read_closed_journal and collect_case_boundaries before this API. Their
    results remain caller supplied. Optional answer extraction bindings invoke
    the separately reviewed answer/schema assessor; absence stays pending.
    """
    for value in (boundary_evidence, original_sanitizer_fixture, source_extraction_bindings):
        _finite(value)
    metric = assess_metric(journal_validation, application_case, expectation_case,
        expected_native_user_id=expected_native_user_id, expected_native_session_id=expected_native_session_id)
    _bind_obligation(application_case, expectation_case, case_obligation)
    replies = assess_reply_dependencies(journal_validation, case_obligation,
        expected_native_user_id=expected_native_user_id, expected_native_session_id=expected_native_session_id)
    effects = assess_source_case_effects(case_obligation, boundary_evidence,
        expected_native_user_id=expected_native_user_id, expected_native_session_id=expected_native_session_id)
    profile, note_selection = _memory_profile(replies, effects, case_obligation,
        expected_native_user_id, expected_native_session_id, original_sanitizer_fixture)
    if profile is not None:
        effects = assess_source_case_effects(case_obligation, boundary_evidence,
            expected_native_user_id=expected_native_user_id, expected_native_session_id=expected_native_session_id,
            sanitized_note_profile=profile)
    answer_schema = None
    pending = {"status": "pending", "reason": "Explicit source extraction bindings and the separate reviewed assessor are required."}
    if source_extraction_bindings is not None:
        from .agentops_answer_schema_v1 import assess_answer_schema
        answer_schema = assess_answer_schema(journal_validation, case_obligation,
            expected_native_user_id=expected_native_user_id, expected_native_session_id=expected_native_session_id,
            source_extraction_bindings=source_extraction_bindings)
    lanes = {
        "response": {"status": replies["reply_consistency_status"], "details": "reply_dependencies"},
        "dependency": {"status": replies["dependency_consistency_status"], "details": "reply_dependencies"},
        "argument": {"status": replies["argument_consistency_status"], "details": "reply_dependencies"},
        "state": {"status": effects["status"], "details": "sampled_effects"},
        "schema": deepcopy(pending) if answer_schema is None else {"status": "separate_checks_available", "details": "answer_schema"},
        "answer": deepcopy(pending) if answer_schema is None else {"status": "separate_checks_available", "details": "answer_schema"},
    }
    return {"schema_version": SCHEMA, "status": "assessed_separate_source_observation_lanes",
            "source_case": deepcopy(metric["source_case"]), "turn_count": metric["turn_count"],
            "native_invocation_ids": deepcopy(metric["native_invocation_ids"]),
            "expected_native_user_id": expected_native_user_id, "expected_native_session_id": expected_native_session_id,
            "configured_metric": deepcopy(metric["configured_metric"]), "configured_metric_definition_unchanged": True,
            "source_case_projection_binding_checked": True, "obligation_projection_binding_checked": True,
            "native_prompt_context_binding_checked": True, "exact_user_text_part_order_checked": True,
            "separate_assessments": lanes, "reply_dependencies": replies, "sampled_effects": effects,
            "memory_reply_profile_selection": note_selection, "answer_schema": answer_schema,
            "journal_receipt_identity": deepcopy(journal_validation["receipt_identity"]),
            "journal_validation_is_caller_supplied": True, "case_obligations_are_caller_supplied": True,
            "boundary_evidence_is_caller_supplied": True, "filesystem_inputs_revalidated_here": False,
            "reference_answer_used_as_passing_oracle": False, "aggregate_task_pass_assigned": False,
            "source_authentication_proven": False, "native_authentication_proven": False,
            "source_closed_proven": False, "process_exit_proven": False, "public_raw_binding_checked": False,
            "causal_tool_execution_order_proven": False, "state_effects_proven": False,
            "continuous_mutation_absence_proven": False, "cross_store_atomicity_proven": False,
            "benchmark_grade_proven": False, "native_qualification_established": False,
            "native_source_case_qualification": False, "full_task_grade_assigned": False}
