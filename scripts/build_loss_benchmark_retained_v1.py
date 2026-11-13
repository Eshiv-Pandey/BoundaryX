"""Reanalyse pinned retained bytes; never start an application, bridge, or model."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmark/loss-v1/retained-manifest.json"
UNKNOWN = object()
ABSENT = object()


class EvidenceError(ValueError):
    """The retained input no longer agrees with its pinned identity/integrity."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def strict_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              EvidenceError("nonfinite JSON number: " + value)))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError("invalid UTF-8/JSON input") from error


def exact_json(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(exact_json(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact_json(a, b) for a, b in zip(left, right))
    return left == right


class Inputs:
    def __init__(self, root, manifest):
        self.root = Path(root).resolve()
        self.manifest = manifest
        self.pins = {row["path"]: row["sha256"] for row in manifest["source_files"]}
        require(len(self.pins) == len(manifest["source_files"]), "duplicate source pin")
        self.used = {}

    def read(self, relative):
        name = PurePosixPath(relative)
        require(not name.is_absolute() and ".." not in name.parts and "\\" not in relative,
                "unsafe retained path")
        require(relative in self.pins, "unmanifested source: " + relative)
        path = (self.root / Path(*name.parts)).resolve()
        require(path.is_relative_to(self.root), "retained path escapes root")
        require(path.is_file(), "missing retained source: " + relative)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == self.pins[relative], "source hash mismatch: " + relative)
        self.used[relative] = digest
        return raw

    def json(self, relative):
        return strict_json(self.read(relative))

    def jsonl(self, relative):
        return [strict_json(line) for line in self.read(relative).splitlines() if line.strip()]

    def sources(self, before):
        return [{"path": path, "sha256": digest} for path, digest in sorted(self.used.items())
                if path not in before]


def blob(value, *, empty_allowed=False):
    """Check exact entity encoding/hash/length/parsed agreement before using JSON."""
    encoded = value.get("base64", value.get("raw_base64"))
    raw_text = value.get("raw")
    if encoded is None:
        require(empty_allowed and raw_text is None and value.get("json") is None,
                "missing body encoding")
        raw = b""
    else:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise EvidenceError("corrupt body base64") from error
        if raw_text is not None:
            require(raw_text.encode("utf-8") == raw, "body text/base64 disagreement")
    if value.get("sha256") is not None:
        require(hashlib.sha256(raw).hexdigest() == value["sha256"], "body hash mismatch")
    if "bytes" in value:
        require(type(value["bytes"]) is int and len(raw) == value["bytes"], "body byte mismatch")
    parsed = strict_json(raw) if raw.strip() else None
    if "json" in value:
        require(exact_json(parsed, value["json"]), "body parsed JSON disagreement")
    return parsed, len(raw)


def validate_exchanges(rows):
    counts = {"requests": 0, "rpc_requests": 0, "notifications": 0,
              "tool_calls": 0, "request_bytes": 0, "response_bytes": 0, "errors": []}
    checked = []
    ids = set()
    for row in rows:
        require(row["exchange_id"] not in ids, "duplicate exchange identity")
        ids.add(row["exchange_id"])
        request, request_bytes = blob(row["request"], empty_allowed=True)
        response, response_bytes = (None, 0) if row.get("response") is None else blob(row["response"])
        counts["requests"] += 1
        counts["request_bytes"] += request_bytes
        counts["response_bytes"] += response_bytes
        if isinstance(request, dict) and request.get("jsonrpc") == "2.0":
            if "id" in request:
                counts["rpc_requests"] += 1
                require(isinstance(response, dict) and exact_json(response.get("id"), request["id"]),
                        "RPC response identity mismatch")
            else:
                counts["notifications"] += 1
            counts["tool_calls"] += request.get("method") == "tools/call"
        if isinstance(response, dict) and "error" in response:
            counts["errors"].append({"exchange_id": row["exchange_id"], "error": response["error"]})
        checked.append({**row, "request_json": request, "response_json": response})
    return checked, counts


def task(value):
    if isinstance(value, dict) and "task" in value:
        return value["task"]
    return value


def task_state(value):
    return str(value.get("status", {}).get("state", value.get("state", "unknown")))


def completion(original, final):
    """The goal is original task AND original context AND completed state."""
    if not isinstance(final, dict):
        return "unknown", {"original_task": None, "original_context": None, "completed_state": None}
    def identity(key):
        if key not in final or key not in original:
            return None
        return exact_json(final[key], original[key])

    status = final.get("status", {})
    state = status.get("state", UNKNOWN) if isinstance(status, dict) else UNKNOWN
    if state is UNKNOWN:
        state = final.get("state", UNKNOWN)
    predicates = {"original_task": identity("id"), "original_context": identity("contextId"),
                  "completed_state": None if state is UNKNOWN else state in ("completed", "TASK_STATE_COMPLETED")}
    result = "pass" if all(value is True for value in predicates.values()) else (
        "fail" if any(value is False for value in predicates.values()) else "unknown")
    return result, predicates


def context_item(name, source=UNKNOWN, sent=UNKNOWN, received=UNKNOWN):
    values = {"source": source, "sent": sent, "received": received}
    return {"id": name, **{key: None if value is UNKNOWN or value is ABSENT else value
                           for key, value in values.items()},
            "observed": {key: value is not UNKNOWN for key, value in values.items()},
            "present": {key: None if value is UNKNOWN else value is not ABSENT
                        for key, value in values.items()}}


def field(obj, name):
    return obj[name] if name in obj else ABSENT


def one(rows, predicate, label):
    found = [row for row in rows if predicate(row)]
    require(len(found) == 1, "expected one " + label)
    return found[0]


def text_message(message):
    parts = message.get("parts", [])
    texts = [part["text"] for part in parts if "text" in part]
    return texts[0] if len(texts) == 1 else UNKNOWN


def public_mcp(response):
    result = response.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content", [])
    require(len(content) == 1 and content[0].get("type") == "text", "ambiguous MCP JSON-text result")
    return strict_json(content[0]["text"])


def episode_base(allocation, sources, tcr, contexts, fidelity, notes, counters, metadata):
    return {"schema_version": "loss_benchmark_episode_v1",
            "episode_id": allocation["episode_id"], "family_id": allocation["family_id"],
            "route_id": allocation["route_id"], "evidence_kind": allocation["evidence_kind"],
            "task_completion": tcr, "context_items": contexts,
            "capability_items": [{"id": "strict_goal@" + allocation["profile"], "required": True,
                                  "reference_usable": None, "observed_usable": True if tcr == "pass" else None,
                                  "advertised": None}],
            "fidelity_checks": fidelity, "recovery": {"eligible": False, "status": "not_applicable"},
            "costs": {"wall_ms": None, "messages": counters["messages"],
                      "tool_calls": counters.get("tool_calls"), "request_bytes": counters["request_bytes"],
                      "response_bytes": counters["response_bytes"], "model_tokens": None},
            "source_files": sources, "notes": notes,
            "metadata": {"profile": allocation["profile"], "collection_flags": {
                "retained_reanalysis": True, "fresh_experiment": False, "held_out": False,
                "generalization_sample": False, "model_inference_executed_by_builder": False,
                "native_service_executed_by_builder": False}, **metadata}}


def build_bridge(inputs, allocation):
    before = set(inputs.used)
    runtime = inputs.json(allocation["runtime"])
    require(runtime["run_id"] == allocation["run_id"] and runtime["variant_id"] == allocation["case_id"]
            and runtime["route_id"] == allocation["bridge_route"], "changed bridge capture identity")
    require(runtime["source_commit"] == allocation["commit"], "changed bridge source identity")
    require(runtime["provenance"]["fixture"]["kind"] == "Separate authored A2A1.0 port of official Carol application",
            "changed application provenance")
    require(inputs.pins["scripts/fixtures/carol-reference-v1.mjs"] == runtime["provenance"]["fixture"]["sha256"],
            "authored port source pin disagrees with recorded provenance")
    rows, counts = validate_exchanges(runtime["exchanges"])
    native_rows = inputs.jsonl(allocation["native_http"])
    require(native_rows[0]["run_id"] == runtime["run_id"], "changed sidecar identity")
    native, native_counts = validate_exchanges([row for row in native_rows if row.get("type") == "exchange-completed"])
    sends = [row for row in native if (row["request_json"] or {}).get("method") == "SendMessage"]
    require(len(sends) == 2, "expected original and fixed-answer native sends")
    original = task(sends[0]["response_json"]["result"])
    followup = sends[1]["request_json"]["params"]["message"]
    gets = [row for row in native if (row["request_json"] or {}).get("method") == "GetTask"]
    require(gets and gets[-1]["request_json"]["params"]["id"] == original["id"], "final read changed original identity")
    final = task(gets[-1]["response_json"].get("result"))
    tcr, predicates = completion(original, final)
    answer = one(rows, lambda row: "fixed_same_task_answer" in row["phase"], "fixed MCP answer")
    params = answer["request_json"]["params"]
    case = allocation["case_id"]
    if case == "R2":
        sent_text = params["inputResponses"]["answer"]["content"]["answer"]
        sent = {}
    elif case == "R4":
        sent = params["arguments"]["params"]["message"]
        sent_text = text_message(sent)
    else:
        sent = params["arguments"]
        sent_text = sent["text"]
    contexts = [context_item("fixed_answer_text", "Well done!", sent_text, text_message(followup)),
                context_item("reference_task_ids", UNKNOWN, field(sent, "referenceTaskIds"),
                             field(followup, "referenceTaskIds"))]
    if case in ("R3", "R4"):
        contexts.extend([context_item("original_task_uuid", original["id"],
                                     field(sent, "taskId" if case == "R4" else "task_id"), field(followup, "taskId")),
                         context_item("original_context_uuid", original["contextId"],
                                     field(sent, "contextId" if case == "R4" else "context_id"), field(followup, "contextId"))])
    pending = one(rows, lambda row: row["phase"] == "initial_authoritative_pending_get", "public pending read")
    last = one(rows, lambda row: row["phase"].startswith("final_authoritative"), "public final read")
    public_initial, public_final = public_mcp(pending["response_json"]), public_mcp(last["response_json"])
    if case in ("R1", "R2"):
        public_association = (public_initial["taskHandle"] == public_final["taskHandle"] and
                              public_initial["contextHandle"] == public_final["contextHandle"])
        public_state = public_final["a2aState"]
    else:
        public_final = task(public_final.get("result", public_final))
        public_association = (public_initial["id"] == public_final["id"] and
                              public_initial["context_id"] == public_final.get("contextId", public_final.get("context_id")))
        public_state = task_state(public_final)
    agree = public_association and ((public_state in ("completed", "TASK_STATE_COMPLETED")) == predicates["completed_state"])
    counts["messages"] = counts["requests"] + counts["rpc_requests"]
    return episode_base(allocation, inputs.sources(before), tcr, contexts,
                        [{"id": "original_task_context_association", "status": "pass" if predicates["original_task"] and predicates["original_context"] else "fail"},
                         {"id": "public_native_final_state_agreement", "status": "pass" if agree else "fail"}],
                        ["Historical development capture on disclosed authored Carol A2A 1.0 port; pinned bridge remained unchanged.",
                         "TCR failure means the original task did not complete in this executed bounded prefix; historical non-support decision remains unknown.",
                         "Required usability is scoped to this named selected-action profile; incomplete failures do not establish whole-interface non-support.",
                         "R4 raw SendMessage/GetTask was selected upfront; no failed typed continuation preceded it, so recovery is N/A.",
                         "Amir opaque handles are excluded from cross-namespace UUID equality. Only actually captured context facts are scored.",
                         "Missing reference field is known absence, not an invented empty list; source requirement is unobserved. Raw absent version-header completion applies only to authored-port default 1.0 policy.",
                         "Costs count MCP entities including setup and initialized notification; native HTTP counters are separate metadata. Latency and model-token counts unavailable."],
                        counts, {"application": "disclosed_authored_carol_a2a_1_0_port", "task_predicates": predicates,
                                 "native_counts": native_counts, "mcp_counts": counts, "public_final_state": public_state,
                                 "original_task_id": original["id"], "original_context_id": original["contextId"],
                                 "capture_model_calls": runtime["provenance"]["model_calls"],
                                 "capture_claimed_evidence_complete": runtime["provenance"]["evidence_complete"]})


def build_native(inputs, allocation):
    before = set(inputs.used)
    report = inputs.json(allocation["runtime"])
    require(report["run_id"] == allocation["run_id"], "changed native capture identity")
    port = allocation["application"] == "disclosed_authored_carol_a2a_1_0_port"
    if not port:
        require(report["source_commit"] == "6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3", "changed unchanged-original identity")
    rows, _ = validate_exchanges(report["exchanges"] if port else report["http_exchanges"])
    prefix = allocation["case_id"] + ":"
    selected = [row for row in rows if row["phase"].startswith(prefix)]
    require(bool(selected), "missing native case")
    _, counts = validate_exchanges([row for row in (report["exchanges"] if port else report["http_exchanges"])
                                   if row["phase"].startswith(prefix)])
    sends = [row for row in selected if row["request_json"]["method"] in ("SendMessage", "message/send")]
    require(len(sends) == 2, "native case send count mismatch")
    original = task(sends[0]["response_json"]["result"])
    followup = sends[1]["request_json"]["params"]["message"]
    final_row = one(selected, lambda row: row["phase"].endswith("original-get-after-answer") or row["phase"].endswith("get_original_after_answer"), "original native final read")
    require(final_row["request_json"]["params"]["id"] == original["id"], "native final read changed original identity")
    final = task(final_row["response_json"].get("result"))
    tcr, predicates = completion(original, final)
    contexts = []
    sent = UNKNOWN
    if port:
        control = one(report["controls"], lambda row: row["control_id"] == allocation["case_id"], "native SDK control")
        sent = control["followup_input"]["message"]
    for name, key in [("task_uuid", "taskId"), ("context_uuid", "contextId"), ("reference_task_ids", "referenceTaskIds")]:
        contexts.append(context_item(name, UNKNOWN, field(sent, key) if sent is not UNKNOWN else UNKNOWN, field(followup, key)))
    counts["messages"] = 2 * counts["requests"]
    counts["tool_calls"] = counts["rpc_requests"]
    return episode_base(allocation, inputs.sources(before), tcr, contexts,
                        [{"id": "original_task_context_association", "status": "pass" if predicates["original_task"] and predicates["original_context"] else "fail"}],
                        ["Retained native reference control, not an MCP bridge execution or fresh experimental trial.",
                         "P2/P3 and N2/N3 are deliberately authored near misses. Their task failures are not natural memory-loss prevalence.",
                         "Source/extraction facts are unknown where no independent upstream payload was captured. Original 0.3 lacks separate SDK sent payload; port preserves exact SDK-to-wire observations.",
                         "Optional empty SDK task IDs/references may be omitted by protobuf; exact presence difference is retained, without calling it semantic nonconformance.",
                         "Case costs cover its HTTP exchanges; shared one-card discovery is excluded and documented separately. No latency or token claim."],
                        counts, {"application": allocation["application"], "task_predicates": predicates,
                                 "original_task_id": original["id"], "original_context_id": original["contextId"],
                                 "http_counts": counts, "shared_card_discovery_allocated_to_case": False,
                                 "capture_model_calls": report["model_calls"]})


def agent_wire(inputs, base, paths):
    rows = []
    for relative in paths:
        exchange = inputs.json(relative)
        folder = str(PurePosixPath(relative).parent)
        request = inputs.read(folder + "/request.body.bin")
        response = inputs.read(folder + "/response.body.bin")
        require(exchange["request_body_complete"] and exchange["response_body_complete"], "incomplete ASGI entity capture")
        require(len(request) == exchange["request_bytes"] and len(response) == exchange["response_bytes"], "ASGI body byte mismatch")
        require(sum(chunk["bytes"] for chunk in exchange["response_chunks"]) == len(response), "response chunk count mismatch")
        offset = 0
        for chunk in exchange["response_chunks"]:
            raw = response[offset:offset + chunk["bytes"]]
            require(hashlib.sha256(raw).hexdigest() == chunk["sha256"], "response chunk hash mismatch")
            offset += chunk["bytes"]
        req = strict_json(request) if request else None
        rsp = strict_json(response) if response else None
        if req and "id" in req:
            require(exact_json(rsp.get("id"), req["id"]), "ASGI RPC identity mismatch")
        rows.append({"request_json": req, "response_json": rsp, "exchange": exchange})
    return rows


def confirmation_data(task_value):
    parts = task_value.get("status", {}).get("message", {}).get("parts", [])
    found = [part["data"] for part in parts if part.get("data", {}).get("name") == "adk_request_confirmation"]
    return found[0] if len(found) == 1 else None


def effect_predicate(initial, terminal, original, final, rationale):
    """Read actual table rows, not any stored strict_success/check status."""
    before, after = initial["database"]["tables"], terminal["database"]["tables"]
    baseline = next(row for row in before["services"] if row["name"] == "inventory")
    inventory = next(row for row in after["services"] if row["name"] == "inventory")
    expected_services = [{**row, "status": "operational"} if row["name"] == "inventory" else row for row in before["services"]]
    audit = after["audit_log"]
    invocation_ids = {artifact.get("metadata", {}).get("adk_invocation_id") for artifact in final.get("artifacts", [])}
    effect = (baseline["status"] == "down" and inventory["status"] == "operational" and
              after["services"] == expected_services and before["incidents"] == after["incidents"] and
              not before["audit_log"] and len(audit) == 1)
    if effect:
        row = audit[0]
        effect = (row["action"] == "restart_service" and row["target"] == "inventory" and
                  row["actor"] == "agentops-agent" and row["session_id"] == original["contextId"] and
                  row["approved_by"] == "A2A_USER_" + original["contextId"] and row["rationale"] == rationale and
                  row["invocation_id"] in invocation_ids and row["context_summary"] == "service inventory was down; open incidents: INC-002")
    return bool(effect)


def build_agentops(inputs, allocation):
    before = set(inputs.used)
    base = allocation["base"]
    plan = inputs.json(base + "/plan.json")
    config = inputs.json(base + "/client-config.json")
    require(plan["case_id"] == allocation["case_id"] and plan["kind"] == allocation["kind"], "changed AgentOps case identity")
    require(config.get("profile", config.get("arm")) == allocation["client_profile"], "changed AgentOps executed profile")
    wire = agent_wire(inputs, base, allocation["wire_exchanges"])
    sends = [row for row in wire if (row["request_json"] or {}).get("method") == "SendMessage"]
    require(len(sends) in (1, 2), "unexpected diagnostic send count")
    original = task(sends[0]["response_json"]["result"])
    gets = [row for row in wire if (row["request_json"] or {}).get("method") == "GetTask" and "result" in row["response_json"]]
    require(gets[-1]["request_json"]["params"]["id"] == original["id"], "AgentOps original task read mismatch")
    final = task(gets[-1]["response_json"]["result"])
    state_tcr, predicates = completion(original, final)
    initial = inputs.json(allocation["initial_snapshot"])
    terminal = inputs.json(base + "/service/terminal.snapshot.json")
    effect_gate = inputs.json(allocation["effect_gate_snapshot"])
    guarded_before_response = exact_json(initial["database"]["tables"], effect_gate["database"]["tables"])
    effect = effect_predicate(initial, terminal, original, final, config["rationale"])
    predicates["exactly_one_attributed_expected_effect"] = effect
    tcr = "pass" if state_tcr == "pass" and effect else ("unknown" if state_tcr == "unknown" else "fail")
    log = inputs.jsonl(allocation["public_log"])
    mcp = allocation["kind"] == "bridge"
    if mcp:
        public = [row for row in log if row.get("kind") == "mcp-message"]
        for row in public:
            raw = row["raw"]
            parsed, _ = blob({**raw, "json": row["parsed"]})
            require(parsed == row["parsed"], "MCP log raw mismatch")
        outgoing = [row for row in public if row["direction"] == "client_to_bridge"]
        answer_rows = [row for row in outgoing if row["phase"] == "raw_answer"]
        sent = answer_rows[0]["parsed"]["params"]["arguments"]["params"]["message"] if answer_rows else None
        pending_public = [public_mcp(row["parsed"]) for row in public if row["direction"] == "bridge_to_client" and row["phase"] == "public_raw_get"]
        public_confirm = confirmation_data(task(pending_public[0].get("result", {}))) if pending_public else None
        counters = {"messages": len(public), "tool_calls": sum(row["parsed"].get("method") == "tools/call" for row in outgoing),
                    "request_bytes": sum(row["raw"]["bytes"] for row in outgoing),
                    "response_bytes": sum(row["raw"]["bytes"] for row in public if row["direction"] == "bridge_to_client")}
    else:
        answer_rows = [row for row in log if row.get("kind") == "sdk-call" and row.get("phase") == "resume-raw"]
        sent = answer_rows[0]["arguments"]["params"]["message"] if answer_rows else None
        for row in log:
            if row.get("kind") in ("raw-http-request", "raw-http-response"):
                blob(row["raw"])
        source_rows = [row for row in log if row.get("kind") == "sdk-result" and row.get("phase") == "get-pending"]
        public_confirm = None
        for row in source_rows:
            parts = row["value"].get("status", {}).get("message", {}).get("parts", [])
            for part in parts:
                data = part.get("content", {}).get("value")
                if isinstance(data, dict) and data.get("name") == "adk_request_confirmation":
                    public_confirm = data
        counters = {"messages": 2 * len(wire), "tool_calls": sum(bool(row["request_json"]) for row in wire),
                    "request_bytes": sum(row["exchange"]["request_bytes"] for row in wire),
                    "response_bytes": sum(row["exchange"]["response_bytes"] for row in wire)}
    received = sends[1]["request_json"]["params"]["message"] if len(sends) == 2 else None
    contexts = [context_item("original_task_uuid", original["id"], field(sent, "taskId") if sent else UNKNOWN, field(received, "taskId") if received else UNKNOWN),
                context_item("original_context_uuid", original["contextId"], field(sent, "contextId") if sent else UNKNOWN, field(received, "contextId") if received else UNKNOWN)]
    sent_data = sent["parts"][0]["data"] if sent else None
    received_data = received["parts"][0]["data"] if received else None
    for key in ("id", "name"):
        contexts.append(context_item("confirmation_" + key, public_confirm[key] if public_confirm else UNKNOWN,
                                     sent_data[key] if sent_data else UNKNOWN, received_data[key] if received_data else UNKNOWN))
    contexts.append(context_item("approval_rationale", config["rationale"],
                                 sent_data["response"]["payload"]["rationale"] if sent_data else UNKNOWN,
                                 received_data["response"]["payload"]["rationale"] if received_data else UNKNOWN))
    confirmation_ok = bool(public_confirm and sent_data and received_data and
                           public_confirm["id"] == sent_data["id"] == received_data["id"] and
                           public_confirm["name"] == sent_data["name"] == received_data["name"] and
                           public_confirm["args"]["originalFunctionCall"]["name"] == "restart_service" and
                           public_confirm["args"]["originalFunctionCall"]["args"] == {"name": "inventory"} and
                           received["parts"][0].get("metadata", {}).get("adk_type") == "function_response" and
                           received_data["response"]["confirmed"] is True)
    if not guarded_before_response:
        tcr = "fail"
    predicates["no_effect_before_confirmation_response"] = guarded_before_response
    errors = [{"sequence": row["exchange"]["sequence"], "error": row["response_json"]["error"]}
              for row in wire if isinstance(row["response_json"], dict) and "error" in row["response_json"]]
    return episode_base(allocation, inputs.sources(before), tcr, contexts,
                        [{"id": "original_task_context_association", "status": "pass" if predicates["original_task"] and predicates["original_context"] else "fail"},
                         {"id": "public_confirmation_binding_and_response", "status": "pass" if confirmation_ok else "unknown"},
                         {"id": "no_domain_effect_before_confirmation_response", "status": "pass" if guarded_before_response else "fail"},
                         {"id": "exactly_one_attributed_expected_effect", "status": "pass" if effect else "fail"}],
                        ["Retained v12 diagnostic on ORIGINAL deterministic confirmation double and simulated SQLite domain; no LLM inference and no unchanged production application claim.",
                         "B7 explicitly configured A2A-Version: 1.0 at local origin; B6 passthrough raw read error and missing public confirmation remain retained.",
                         "B6 has no continuation payload: missing sent/received context stays unknown. B6 strict whole-case historical status remains partial; bounded goal TCR fails because terminal original task waits and no effect occurs.",
                         "Raw confirmation alternative is selected in the executed profile; no post-failed-answer recovery trial is measured.",
                         "Terminal GetTask includes evaluator-only observation; native N11 costs include it, while bridge MCP costs exclude evaluator HTTP. Complete native counts remain separate metadata.",
                         "Shutdown boundaries are not latency measurements. Retained diagnostics do not replace historical v10 failures or establish reliability."],
                        counters, {"application": "original_deterministic_confirmation_double_simulated_sqlite", "task_predicates": predicates,
                                   "original_task_id": original["id"], "original_context_id": original["contextId"],
                                   "public_confirmation_observed": public_confirm is not None, "continuation_attempted": sent is not None,
                                   "native_http_requests": len(wire), "native_request_bytes": sum(row["exchange"]["request_bytes"] for row in wire),
                                   "native_response_bytes": sum(row["exchange"]["response_bytes"] for row in wire), "native_errors": errors,
                                   "historical_strict_case_status": "partial" if allocation["case_id"] == "B6" else "pass",
                                   "model_kind": "original_deterministic_confirmation_double"})


def build_episodes(root=ROOT, manifest_path=MANIFEST):
    manifest_raw = Path(manifest_path).read_bytes()
    manifest = strict_json(manifest_raw)
    require(manifest["schema_version"] == "loss_benchmark_retained_manifest_v1", "unexpected manifest schema")
    inputs = Inputs(root, manifest)
    episodes = []
    allocations = {row["episode_id"]: row for row in manifest["allocations"]}
    require(len(allocations) == len(manifest["allocations"]), "duplicate manifest allocation")
    loaders = {"bridge": build_bridge, "native": build_native, "agentops": build_agentops}
    for allocation in manifest["allocations"]:
        # Each episode retains its own complete raw source inventory, including shared reports.
        inputs.used = {}
        require(allocation["loader"] in loaders, "unknown retained loader")
        episode = loaders[allocation["loader"]](inputs, allocation)
        reference_allocation = allocations[allocation["reference_episode_id"]]
        reference = loaders[reference_allocation["loader"]](inputs, reference_allocation)
        episode["capability_items"][0]["reference_usable"] = True if reference["task_completion"] == "pass" else None
        for path in allocation["provenance_files"]:
            inputs.read(path)
        episode["source_files"] = inputs.sources(set())
        episode["metadata"]["reference_episode_id"] = reference["episode_id"]
        episode["metadata"]["reference_witness_task_predicates"] = reference["metadata"]["task_predicates"]
        episode["metadata"]["manifest_sha256"] = hashlib.sha256(manifest_raw).hexdigest()
        episodes.append(episode)
    require(len({row["episode_id"] for row in episodes}) == len(episodes), "duplicate episode identity")
    return episodes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    episodes = build_episodes(args.root, args.manifest)
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from interoperability.loss_benchmark_v1 import summarize_episodes, validate_episode
    for row in episodes:
        validate_episode(row)
    output = args.output or (args.root / "runs/loss-benchmark-retained-v1" /
                             (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]))
    require(not output.exists(), "output allocation already exists; choose a fresh path")
    output.mkdir(parents=True, exist_ok=False)
    (output / "episodes.json").write_text(json.dumps(episodes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = summarize_episodes(episodes)
    (output / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "episodes": len(episodes), "task_completion_counts": {
        key: sum(row["task_completion"] == key for row in episodes) for key in ("pass", "fail", "unknown")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
