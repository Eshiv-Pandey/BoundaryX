"""Conservative evaluator-side integration of complete stronger observations.

The frozen v2 API supplies original metric, sampled effects and memory checks.
The separate v2 reply assessor recomputes response/dependency/argument lanes.
Optional answer extraction abstains when any observed tool call/reply is partial,
because the frozen answer reader still delegates to the earlier reply assessor.
This pure API authenticates no sources and performs no filesystem/native work.
The frozen v2 CLI does not use this successor API.
"""
from __future__ import annotations

from copy import deepcopy

from .agentops_reply_dependencies_v2 import assess_reply_dependencies
from .agentops_source_case_assessment_v1 import _finite, _need, _same
from .agentops_source_case_assessment_v2 import assess_source_case as assess_frozen_v2

SCHEMA = "agentops-source-case-assessment/3"
FROZEN_V2_SOURCE_SHA256 = "a2fec6d9bafbf1b76bd4654932a994a5e8cb6a8466ae1d30473dac03a8598fc8"
REPLY_V2_SOURCE_SHA256 = "0475d55ba2a4aa84d0dacd77fefaa357440f35c27020d43d747879e3df39d2b3"


def assess_source_case(journal_validation, application_case, expectation_case, case_obligation,
                       boundary_evidence, *, expected_native_user_id, expected_native_session_id,
                       original_sanitizer_fixture=None, source_extraction_bindings=None):
    """Return corrected stronger lanes with unchanged delegated metric/effects.

Inputs remain caller supplied. Repeated and partial observations stay retained.
Any partial tool observation conservatively withholds optional answer extraction;
the result retains pending answer/schema lanes and an explicit reason.
"""
    supplied = (journal_validation, application_case, expectation_case, case_obligation,
                boundary_evidence, original_sanitizer_fixture, source_extraction_bindings)
    for value in supplied:
        _finite(value)
    before = deepcopy(supplied)
    corrected = assess_reply_dependencies(journal_validation, case_obligation,
        expected_native_user_id=expected_native_user_id, expected_native_session_id=expected_native_session_id)
    partial_refs = [
        {"turn_index": turn["turn_index"], "kind": kind,
         **{key: deepcopy(item[key]) for key in ("observation_index", "event_id", "invocation_id",
                                                 "global_yield_sequence", "part_index")}}
        for turn in corrected["turns"]
        for kind, rows in (("call", turn["tool_calls"]), ("reply", turn["tool_replies"]))
        for item in rows if item["partial"]
    ]
    withhold = source_extraction_bindings is not None and bool(partial_refs)
    result = assess_frozen_v2(journal_validation, application_case, expectation_case, case_obligation,
        boundary_evidence, expected_native_user_id=expected_native_user_id,
        expected_native_session_id=expected_native_session_id,
        original_sanitizer_fixture=original_sanitizer_fixture,
        source_extraction_bindings=None if withhold else source_extraction_bindings)
    prior = result["reply_dependencies"]
    _need(_same(corrected["source_case"], prior["source_case"])
          and _same(corrected["journal_receipt_identity"], result["journal_receipt_identity"])
          and _same([turn["native_invocation_id"] for turn in corrected["turns"]], result["native_invocation_ids"])
          and len(corrected["turns"]) == result["turn_count"],
          "Delegated metric and corrected stronger observations differ in case/journal/native turns")
    _need(all(_same(value, original) for value, original in zip(supplied, before)),
          "Supplied observations changed during delegated assessment")
    result["schema_version"] = SCHEMA
    result["reply_dependencies"] = corrected
    for lane, field in (("response", "reply_consistency_status"),
                        ("dependency", "dependency_consistency_status"),
                        ("argument", "argument_consistency_status")):
        result["separate_assessments"][lane] = {"status": corrected[field], "details": "reply_dependencies"}
    result["delegated_computation"] = {
        "metric_effects_memory_API": "agentops_source_case_assessment_v2",
        "declared_frozen_v2_source_sha256": FROZEN_V2_SOURCE_SHA256,
        "corrected_reply_API": "agentops_reply_dependencies_v2",
        "declared_reply_v2_source_sha256": REPLY_V2_SOURCE_SHA256,
        "case_journal_native_turn_bindings_rechecked": True,
        "supplied_observations_unchanged": True,
        "runtime_source_hashes_verified_here": False,
    }
    result["partial_tool_observation_refs"] = partial_refs
    result["supplied_bindings_withheld_due_to_partial"] = withhold
    if withhold:
        result["source_extraction_not_assessed_reason"] = (
            "Partial tool call/reply observations can affect the frozen answer reader's direct source bindings. "
            "Optional extraction is conservatively withheld; answer/schema remain pending."
        )
    return result
