"""Pure observed-answer and strict report projections; no SDK/model/file access.

The closed-journal report, source obligations and extraction bindings are
caller supplied. Their consistency is checked, not their authenticity. The
public reply assessor supplies earlier call/reply attribution, without scoring
the original metric. No prose judge or workflow JSON schema is invented.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re

from .agentops_reply_dependencies_v1 import assess_reply_dependencies


SCHEMA = "agentops-answer-schema/1"
BINDING_SCHEMA = "agentops-answer-extraction-bindings/1"
SELECTION_PROFILE = "complete_model_text_after_node_tools_v1"
SOURCE_BINDINGS = {
    "models.py": "35e60ecd98f064570b63f9126a70c4b09ae736f7faa4c0364b457f372e0731c0",
    "report.py": "e524a70ea71d23a3530869e6f4e39125d77ef9e8b21141f9b0e151d19f12d043",
    "workflow.py": "68c3fefa9966ecddb69d96150423379433016be508f811df7638a30ba9bb9747",
    "composition.py": "d1ad9f887328345f6edda5ef7d412c48938e62d708e39c645a479e1d5c166ad8",
    "events/event.py": "efde6a9f9ef990730be08648cbcc419b0ba6b3460d6262d3a8a3b77921393720",
    "workflow/_llm_agent_wrapper.py": "7cdf7b9d0e657764dff725bb03bcdcaaca2269dcb9fff0e8fbf177dfacf65c41",
    "workflow/_node_runner.py": "9d932ae24bbaa60781c5a92cd8c8200cc1b00c393243f82f9ddd6807bb598b28",
    "workflow/_workflow.py": "c61e473933236ac707a6b794c3fc7c1d680f4bf77afeebd13af18de7d7f99edc",
}
# Canonical minimal original user-content hashes, projected from application
# cases.json. Null SDK serialization defaults are ignored, text is unchanged.
USER_CONTENT_HASHES = {
    "agentops_agent_core/inventory-status": [
        "fbce7bf87f4571c91fe396a24951129438ae225757e69b5162b3a15d82b47665"
    ],
    "agentops_agent_core/incident-detail": [
        "23c192e1fa4fb1157e8072a15ababcda503f210253e6041f5556df52b54a7516"
    ],
    "agentops_agent_core/recommend-fix": [
        "b653b892f4dc3ac0a19529e64808698ddcb9dcbab227416ec1c99302012442f6"
    ],
    "agentops_agent_core/investigation-recalls-context": [
        "b2959723448b75129efe9c739e7248d3c27429b892636f4058d599863fbccfae"
    ],
    "agentops_agent_core/remediation-loads-skill": [
        "af9243bca9d99a92b5ee0c88275d0481ac4a12cfc5b5d948c68913c877b1436b"
    ],
    "agentops_agent_core/unknown-incident": [
        "08ae8aa132f8dd9c8d6cbf85ee4e2b72aa68baef8428b1519996d53c94e07bce"
    ],
    "agentops_agent_core/unknown-service": [
        "82b4316d46b54088689618d84ff6b36d615ea38313ab742a22ca0fe92b2c8d2f"
    ],
    "agentops_agent_core/cascade-root-cause": [
        "a4c9d0340668ef17dbd583ddf7603c571b334ea7fd87a7df2b7469409d9dfe9b"
    ],
    "agentops_agent_core/cascade-origin-detail": [
        "9067fbc619c35647c4371d247bee866329d72f16e7f2ae6f928ba63d46b520cd"
    ],
    "agentops_agent_core/diagnose-with-logs": [
        "4b153d82fcda71303ecbb04e04e84f351ff33c340e1e6ad3c4ad6eee6cae1d2f"
    ],
    "agentops_agent_core/restart-needs-approval": [
        "f384970969d43f04e4d9d3e1d7211a34bcb77e3fd027ebb4e69e47576ccb975b"
    ],
    "agentops_agent_core/resolve-needs-approval": [
        "a2e8b0b5c96fc0141ebf36b2b10728523a4d81bf84ac9c17b3f824b0f280166f"
    ],
    "agentops_agent_core/injection-restart-rejected": [
        "6d87c690e4577a65cfc69bf4fbe6083c01ee4c22d51e3bf30127d4a4a8727fbd"
    ],
    "agentops_agent_core/ambiguous-symptom": [
        "7368b2b304ae519e22626e4153ccee161b1dc39b080416f8858db12ca3cdc158"
    ],
    "agentops_agent_core/memory-note-recall": [
        "c75eeb8771b7a4c4db348eff4df0938a2468cc30d1548243509657f5d820b400",
        "d2ad1a16e0c31882469229c832bf5ed1170e4d86b6d999f9b4c106ac441f31de"
    ],
    "agentops_agent_structured_report/inventory-incident-report": [
        "45233677c60dbd33e8e22bed37d28385d53a84f86b5d3646d09f1c9da37cce58"
    ],
    "agentops_agent_structured_report/gateway-memory-report": [
        "08738d5edc0859c9b5d23c0a9760e0ac884a200a96eac62817746cff8a8595bd"
    ],
    "agentops_agent_structured_report/resolved-cache-report-rejects-user-override": [
        "ed2d09cbf34a8f7b0271534f8dc7d1b8218e828941a957c00a59f58a0fb4c7ad"
    ],
    "agentops_incident_workflow/checkout-evidence-review": [
        "3788785339e99dc2f44f6cfa5301fa04caf30b5c7194f44a3a89f7a52c3323aa"
    ],
    "agentops_incident_workflow/gateway-memory-evidence-review": [
        "8d672eac0616945b2e877b8e75b2322d7deddb9630a0650cb8d3a6aa54799b99"
    ],
    "agentops_incident_workflow/resolved-cache-rejects-injected-action": [
        "77533c6775b55b1f9ea480d507b54750100ffb625220ed99c49bdd99d4629929"
    ]
}
REPORT_TARGETS = {"inventory-incident-report": "INC-002", "gateway-memory-report": "INC-010",
                  "resolved-cache-report-rejects-user-override": "INC-007"}
STAGES = ("plan", "investigate", "evidence_review", "recommend")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INCIDENT = re.compile(r"^INC-\d+$")


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _same(a, b):
    if type(a) is not type(b): return False
    if type(a) is dict: return set(a) == set(b) and all(_same(v, b[k]) for k, v in a.items())
    if type(a) is list: return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _result(status, reason, **fields):
    return {"status": status, "reason": reason, **fields}


def _finite_json(value, depth=0):
    _need(depth <= 48, "answer extraction JSON nesting exceeds bound")
    if type(value) is dict:
        _need(all(type(k) is str for k in value), "nontext extraction JSON member")
        for child in value.values(): _finite_json(child, depth + 1)
    elif type(value) is list:
        for child in value: _finite_json(child, depth + 1)
    else:
        _need(value is None or type(value) in (str, bool, int) or type(value) is float and math.isfinite(value),
              "nonfinite or non-JSON extraction value")


def _content_hash(content):
    if type(content) is not dict or content.get("role") != "user" or type(content.get("parts")) is not list:
        return None
    if any(v is not None for k, v in content.items() if k not in {"role", "parts"}): return None
    projected = []
    for part in content["parts"]:
        if (type(part) is not dict or type(part.get("text")) is not str
                or any(v is not None and not (k == "thought" and v is False)
                       and not (k == "part_metadata" and type(v) is dict and not v)
                       for k, v in part.items() if k != "text")):
            return None
        projected.append({"text": part["text"]})
    raw = json.dumps({"role": "user", "parts": projected}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_profile(bindings, family, turn_count):
    if bindings is None: return _result("unknown", "Explicit source extraction bindings are unavailable.")
    _need(type(bindings) is dict, "unsupported extraction binding object")
    _need(bindings.get("schema_version") == BINDING_SCHEMA and bindings.get("family") == family
          and bindings.get("selection_profile") == SELECTION_PROFILE, "unsupported source extraction profile")
    _need(type(bindings.get("turns")) is list and len(bindings["turns"]) == turn_count,
          "extraction turn bindings differ")
    if not _same(bindings.get("source_bindings"), SOURCE_BINDINGS):
        return _result("unknown", "Supplied source hashes do not match the pinned extraction profile.")
    return _result("consistent_with_supplied_profile", "Pinned source hashes supplied; source execution/authenticity is unproved.")


def _node_binding(binding, name, family):
    _need(type(binding) is dict and set(binding) == {"author", "node_path", "branch"}, "unsupported answer node binding")
    author = "triage_workflow" if family == "workflow" else "triage_report_agent" if family == "report" else "agentops_agent"
    _need(binding["author"] == author, "answer author differs from original entrypoint")
    _need(binding["branch"] is None or type(binding["branch"]) is str, "unsupported answer branch")
    path = binding["node_path"]
    _need(type(path) is str and (bool(path) or family != "workflow") or path is None and family != "workflow",
          "workflow needs explicit observed node paths")
    return binding


def _event_ref(event, record):
    return {"event_id": event["id"], "invocation_id": event["invocation_id"],
            "event_ordinal": record["event_ordinal"], "global_yield_sequence": record["global_yield_sequence"],
            "author": event.get("author"), "branch": event.get("branch"),
            "node_info": deepcopy(event.get("node_info")), "record": deepcopy(record), "event": deepcopy(event)}


def _surface(event):
    content = event.get("content")
    if content is None: return "empty", "", []
    if type(content) is not dict or type(content.get("parts")) is not list: return "unsupported", "", []
    parts = content["parts"]
    if any(type(p) is not dict for p in parts): return "unsupported", "", []
    if any(p.get("function_call") is not None or p.get("function_response") is not None for p in parts):
        return "tool", "", []
    if content.get("role") != "model": return "nonmodel", "", []
    text, spans = "", []
    for index, part in enumerate(parts):
        if part.get("thought") is not None and type(part["thought"]) is not bool: return "unsupported", "", []
        if any(value is not None for key, value in part.items() if key not in {"text", "thought", "thought_signature"}):
            return "unsupported", "", []
        value = part.get("text")
        if value is not None and type(value) is not str: return "unsupported", "", []
        if value is not None and not part.get("thought"):
            spans.append({"part_index": index, "answer_start": len(text), "answer_end": len(text) + len(value),
                          "part_text_start": 0, "part_text_end": len(value)})
            text += value
    return "text" if text.strip() else "empty", text, spans


def _extract(call, node, family):
    scope, candidates, outputs = [], [], []
    last_tool, terminal_error = 0, None
    unsupported, partial_sequences = [], []
    for event, record in zip(call["events"], call["event_records"]):
        info = event.get("node_info")
        path = info.get("path") if type(info) is dict else None
        if event.get("author") != node["author"] or not _same(path, node["node_path"]) or not _same(event.get("branch"), node["branch"]):
            continue
        ref = _event_ref(event, record)
        scope.append(ref)
        seq = record["global_yield_sequence"]
        if info is not None and type(info) is not dict:
            unsupported.append(seq)
            continue
        if event.get("output") is not None:
            outputs.append({"event_id": event["id"], "event_ordinal": record["event_ordinal"],
                            "global_yield_sequence": seq, "value": deepcopy(event["output"])})
        kind, text, spans = _surface(event)
        if event.get("error_code") is not None and type(event["error_code"]) is not str:
            unsupported.append(seq)
        elif event.get("error_code") not in (None, ""):
            terminal_error = seq
        if kind == "tool": last_tool = seq
        if kind == "unsupported": unsupported.append(seq)
        if event.get("partial") is True:
            partial_sequences.append(seq)
        elif kind == "text" and event.get("error_code") in (None, ""):
            candidates.append({"text": text, "part_spans": spans, "evidence_ref": ref})
    candidates = [item for item in candidates if item["evidence_ref"]["global_yield_sequence"] > last_tool]
    outputs = [item for item in outputs if item["global_yield_sequence"] > last_tool]
    evidence = {"scope_events": scope, "candidate_event_ordinals": [c["evidence_ref"]["event_ordinal"] for c in candidates],
                "selection_profile": SELECTION_PROFILE, "source_node_identity_proven": False,
                "unresolved_terminal_surfaces": any(v > last_tool for v in unsupported + partial_sequences),
                "output_surface_observations": outputs}
    if terminal_error is not None and (not candidates or terminal_error > candidates[-1]["evidence_ref"]["global_yield_sequence"]):
        return _result("unavailable", "Terminal observed provider/runtime error; no answer inferred.", **evidence)
    if len(candidates) != 1:
        return _result("unknown", "A unique complete model text after node tool activity is unestablished.", **evidence)
    chosen = candidates[0]
    seq = chosen["evidence_ref"]["global_yield_sequence"]
    if any(value > last_tool for value in unsupported) or any(value >= seq for value in partial_sequences):
        return _result("unknown", "Unsupported or terminal partial surfaces prevent unambiguous selection.", **evidence)
    if any(type(o["value"]) not in ((str, dict) if family == "report" else (str,)) for o in outputs):
        return _result("unknown", "Observed output surface has an unsupported type.", **evidence)
    if any(type(o["value"]) is str and o["value"] != chosen["text"] for o in outputs):
        return _result("unknown", "Observed output and non-thought text surfaces disagree.", **evidence)
    return _result("observed", "Unique source-profile model text selected; semantic adequacy is unassessed.",
                   **evidence, **chosen, output_surface=deepcopy(chosen["evidence_ref"]["event"].get("output")))


def _duplicate(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("Duplicate JSON object member: " + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-JSON constant: " + value)


def _confirmation_terminal(extracted, pause, reply_turn):
    indices = pause.get("matching_confirmation_request_observation_indices", [])
    if len(indices) != 1: return False
    request = reply_turn["tool_calls"][indices[0]]
    tool_events = [ref for ref in extracted.get("scope_events", []) if _surface(ref["event"])[0] == "tool"]
    if not tool_events: return False
    last = tool_events[-1]
    if (last["global_yield_sequence"] != request["global_yield_sequence"] or last["event_id"] != request["event_id"]
            or last["event"].get("output") is not None):
        return False
    parts = last["event"]["content"]["parts"]
    return (len(parts) == 1 and _same(parts[0].get("function_call"), request["function"])
            and all(value is None for key, value in parts[0].items() if key != "function_call"))


def _report(text):
    if len(text) > 1024 * 1024:
        return _result("unknown", "Report text exceeds the bounded parser size; syntax is unassessed."), _result("unknown", "Bounded parser unavailable."), None
    try:
        body = json.loads(text, object_pairs_hook=_duplicate, parse_constant=_constant)
        _need(type(body) is dict, "Dedicated report answer must be one JSON object")
    except RecursionError:
        return _result("unknown", "JSON exceeds parser recursion resources; syntax is unassessed."), _result("unknown", "Bounded parser unavailable."), None
    except ValueError as error:
        return _result("failed", str(error)), _result("unknown", "No strict JSON object available."), None
    try: _finite_json(body)
    except ValueError as error:
        return _result("unknown", str(error) + "; finite JSON projection is unavailable."), _result("unknown", "Bounded finite projection unavailable."), None
    fields = {"incident_id", "severity", "affected_services", "hypothesis", "evidence", "recommended_runbook"}
    errors = []
    if not fields <= set(body) or not set(body) <= fields | {"proposed_actions"}: errors.append("Required or extra report fields differ.")
    for key, pattern in (("incident_id", _INCIDENT), ("recommended_runbook", _SLUG)):
        if type(body.get(key)) is not str or pattern.search(body[key]) is None: errors.append(key + " violates declared string pattern.")
    if type(body.get("severity")) is not str or body["severity"] not in {"SEV1", "SEV2", "SEV3"}: errors.append("severity violates declared enum.")
    if type(body.get("hypothesis")) is not str or len(body["hypothesis"]) < 1: errors.append("hypothesis violates string/min_length.")
    for key in ("affected_services", "evidence", "proposed_actions"):
        value = body.get(key, [] if key == "proposed_actions" else None)
        if type(value) is not list or (key != "proposed_actions" and not value) or any(type(v) is not str for v in value):
            errors.append(key + " violates declared array/item constraints.")
        elif key == "affected_services" and any(_SLUG.search(v) is None for v in value):
            errors.append("affected_services violates declared item pattern.")
    projection = _result("failed" if errors else "passed", "; ".join(errors) if errors else "Declared field constraints passed in a strict stdlib projection.",
                         installed_Pydantic_equivalence_proven=False, strict_types_supplemental=True,
                         regex_engine="stdlib_re_search_declared_patterns", quality_constraints_added=False)
    return _result("passed", "Observed text is one strict JSON object; fences/prose/duplicates/constants rejected."), projection, body


def _direct(body, extraction, reply_turn, target, call):
    checks = [{"field": "incident_id", "authority": "pinned_original_case_target", "expected": target,
               "observed": body["incident_id"], "status": "passed" if body["incident_id"] == target else "failed"}]
    required = [r for r in reply_turn["required_reply_assessments"] if r["required_sequence"] == 1]
    reply = None
    if len(required) == 1 and required[0]["status"] == "supported" and "supporting_reply_observation_index" in required[0]:
        candidate = reply_turn["tool_replies"][required[0]["supporting_reply_observation_index"]]
        if candidate["name"] == "get_incident" and candidate["global_yield_sequence"] < extraction["evidence_ref"]["global_yield_sequence"]:
            producer = reply_turn["tool_calls"][candidate["candidate_call_observation_indices"][0]]
            native_events = [call["events"][point["event_ordinal"] - 1] for point in (producer, candidate)]
            selected = extraction["evidence_ref"]
            def matching_node(event):
                info = event.get("node_info")
                path = info.get("path") if type(info) is dict else None
                selected_info = selected["node_info"]
                selected_path = selected_info.get("path") if type(selected_info) is dict else None
                return (event.get("author") == selected["author"] and _same(event.get("branch"), selected["branch"])
                        and _same(path, selected_path))
            if all(matching_node(event) for event in native_events): reply = candidate
    if reply is None:
        status = "failed" if checks[0]["status"] == "failed" else "unknown"
        return _result(status, "Earlier successful attributed incident reply is unavailable.", checks=checks, source_reply_ref=None)
    incident = reply["payload"]["incident"]
    for field, source in (("incident_id", "id"), ("severity", "severity"), ("recommended_runbook", "runbook")):
        checks.append({"field": field, "authority": "incident." + source, "expected": incident[source],
                       "observed": body[field], "status": "passed" if _same(body[field], incident[source]) else "failed"})
    services = body["affected_services"]
    checks.append({"field": "affected_services", "authority": "incident.service", "expected_member": incident["service"],
                   "observed": deepcopy(services), "status": "passed" if incident["service"] in services else "failed"})
    extra = [v for v in services if v != incident["service"]]
    status = "failed" if any(c["status"] == "failed" for c in checks) else "unknown" if extra else "passed"
    return _result(status, "Direct parsed fields compared to actual earlier incident reply; extra-service support remains semantic." if extra
                   else "Direct parsed fields compared to the actual earlier incident reply and original target.",
                   checks=checks, source_reply_ref=deepcopy(reply), additional_services_pending=extra,
                   uniqueness_or_singleton_schema_rule_added=False)


def assess_answer_schema(journal_validation, case_obligation, *, expected_native_user_id,
                         expected_native_session_id, source_extraction_bindings=None):
    """Return separately labeled observation/strict-schema results, never a grade.

    Malformed supplied bindings raise. Missing source/prompt/terminal evidence
    remains unknown/unavailable. A supported confirmation pause can have no model
    prose. Semantic, original answer-judge and prose lanes remain pending.
    """
    replies = assess_reply_dependencies(journal_validation, case_obligation,
                                       expected_native_user_id=expected_native_user_id,
                                       expected_native_session_id=expected_native_session_id)
    _finite_json(source_extraction_bindings)
    key = case_obligation.get("key")
    _need(type(key) is str and key in USER_CONTENT_HASHES, "unsupported pinned source case")
    _need(case_obligation["turn_count"] == len(USER_CONTENT_HASHES[key]), "pinned source turn count differs")
    family = case_obligation.get("family")
    expected_family = "report" if key.startswith("agentops_agent_structured_report/") else "workflow" if key.startswith("agentops_incident_workflow/") else "core"
    _need(family == expected_family, "source case family differs")
    _need(key == case_obligation["eval_set_id"] + "/" + case_obligation["eval_id"], "source case key differs")
    profile = _source_profile(source_extraction_bindings, family, case_obligation["turn_count"])
    turns = []
    for index, (call, obligation, reply_turn) in enumerate(zip(journal_validation["calls"], case_obligation["turns"], replies["turns"]), 1):
        fingerprint = _content_hash(call["inputs"].get("new_message"))
        prompt = _result("consistent_with_pinned_source" if fingerprint == USER_CONTENT_HASHES[key][index - 1] else "unknown",
                         "Observed user-content projection compared to pinned original source turn.", observed_sha256=fingerprint,
                         expected_sha256=USER_CONTENT_HASHES[key][index - 1], source_prompt_authenticity_proven=False)
        names = STAGES if family == "workflow" else ("answer",)
        extraction = {name: _result("unknown", "Source extraction or original prompt binding is unavailable.") for name in names}
        if profile["status"] == "consistent_with_supplied_profile":
            binding = source_extraction_bindings["turns"][index - 1]
            _need(type(binding) is dict and binding.get("turn_index") == index and type(binding.get("turn_index")) is int
                  and binding.get("native_invocation_id") == reply_turn["native_invocation_id"]
                  and binding.get("source_invocation_label") == obligation["source_invocation_label"], "source extraction runtime turn differs")
            nodes = binding.get("nodes")
            _need(type(nodes) is dict and set(nodes) == set(names), "source node binding membership differs")
            checked = {name: _node_binding(nodes[name], name, family) for name in names}
            if family == "workflow":
                _need(len({(n["node_path"], n["branch"]) for n in checked.values()}) == 4, "workflow node paths are reused")
            if prompt["status"] == "consistent_with_pinned_source":
                extraction = {name: _extract(call, checked[name], family) for name in names}
        if (family == "core" and profile["status"] == "consistent_with_supplied_profile"
                and extraction["answer"]["status"] == "unknown" and prompt["status"] == "consistent_with_pinned_source"):
            pauses = [r for r in reply_turn["required_reply_assessments"] if r["expected_source_classification"] == "confirmation_pause_not_execution"]
            if (len(pauses) == 1 and pauses[0]["status"] == "supported" and not extraction["answer"].get("candidate_event_ordinals")
                    and not extraction["answer"].get("unresolved_terminal_surfaces")
                    and not extraction["answer"].get("output_surface_observations")
                    and _confirmation_terminal(extraction["answer"], pauses[0], reply_turn)):
                extraction["answer"] = {**extraction["answer"], "status": "unavailable",
                                        "reason": "source_confirmation_pause: final sole node tool is the matching request; no observed model prose inferred.",
                                        "confirmation_evidence": deepcopy(pauses[0])}
        strict = declared = direct = _result("not_applicable", "Original entrypoint has no report output schema.")
        output_agreement = _result("not_applicable", "No report output-surface comparison applies.")
        if family == "report":
            strict = declared = direct = _result("unknown", "Attributed complete report text is unavailable.")
            answer = extraction["answer"]
            if answer["status"] == "observed":
                strict, declared, body = _report(answer["text"])
                if declared["status"] == "passed":
                    outputs = answer["output_surface_observations"]
                    expected_output = {**body, "proposed_actions": body.get("proposed_actions", [])}
                    compatible = all(type(o["value"]) is str or _same(o["value"], body) or _same(o["value"], expected_output) for o in outputs)
                    output_agreement = _result("not_applicable" if not outputs else "consistent" if compatible else "unknown",
                                               "Observed output surface retained; only declared default normalization is allowed.")
                    if output_agreement["status"] != "unknown":
                        direct = _direct(body, answer, reply_turn, REPORT_TARGETS[case_obligation["eval_id"]], call)
        stage_order = _result("not_applicable", "Core/report entrypoint has no four-stage graph.")
        candidate_order = _result("not_applicable", "Core/report entrypoint has no four supplied stage labels.")
        if family == "workflow":
            stage_order = _result("unknown", "Caller path labels alone do not establish original graph stage identity or output routing.")
            observed = [extraction[n] for n in STAGES]
            if all(e["status"] == "observed" for e in observed):
                order = [e["evidence_ref"]["global_yield_sequence"] for e in observed]
                first = [min(r["global_yield_sequence"] for r in e["scope_events"]) for e in observed]
                linear = order == sorted(set(order)) and all(order[i] < first[i + 1] for i in range(3))
                candidate_order = _result("consistent" if linear else "inconsistent",
                                          "Candidate order under caller-supplied path labels only; original stage identity/routing is unproved.",
                                          original_stage_order_proven=False)
            else: candidate_order = _result("unknown", "All four selected path outputs are not established.", original_stage_order_proven=False)
        turns.append({"turn_index": index, "native_invocation_id": reply_turn["native_invocation_id"], "prompt_binding": prompt,
                      "answer_extraction": extraction, "strict_report_JSON": strict, "report_declared_schema_projection": declared,
                      "report_direct_source_bindings": direct, "report_output_surface_consistency": output_agreement,
                      "workflow_stage_order": stage_order, "selected_candidate_order_consistency": candidate_order,
                      "workflow_formal_output_schema": None,
                      "semantic_manual_assessment": _result("pending", obligation.get("unresolved_semantic_criteria", "Case-specific semantic review is required.")),
                      "prose_lexical_assessment": _result("pending", "No original prose judge or strengthened lexical judge is executed here."),
                      "exact_quote_assessment": _result("pending", "No verbatim quotation spans supplied; paraphrase is not literal equality."),
                      "original_answer_judges_executed": False})
    return {"schema_version": SCHEMA, "status": "observed_answer_and_strict_report_projections_only", "source_case_key": key,
            "source_extraction_profile": profile, "turns": turns, "journal_receipt_identity": deepcopy(journal_validation["receipt_identity"]),
            "original_metric_modified": False, "original_metric_score_assigned_here": False, "full_task_grade_assigned": False,
            "benchmark_grade_proven": False, "native_source_case_qualification": False, "native_qualification_established": False,
            "source_authentication_proven": False, "complete_native_stream_proven": False, "source_closed_proven": False,
            "tool_execution_or_dataflow_proven": False, "installed_Pydantic_equivalence_proven": False,
            "caller_supplied_journal_and_source_bindings": True, "semantic_judge_executed": False}
