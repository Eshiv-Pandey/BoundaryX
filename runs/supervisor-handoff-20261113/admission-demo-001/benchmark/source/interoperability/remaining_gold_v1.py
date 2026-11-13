"""Private, independently authored finite development trace oracles.

This module imports no gate, prior grader, application, SDK or provider. Original
SQL is instantiated only in owned memory. It accepts the four declared typed
tasks, not arbitrary conversations or original shopper episodes. Complete event
and intermediate-state evidence is an explicit observer assumption, never a
claim that a constructed trace authenticates a real runtime capture.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


class GoldError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise GoldError(reason)


def canonical(value):
    """Type-sensitive JSON comparison: False must not equal numeric zero."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def equal(left, right):
    return canonical(left) == canonical(right)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_sources(root, bank):
    root = Path(root).resolve()
    require(bank["schema_version"] == "remaining-development-gold/1", "gold schema")
    require(bank["human_review_status"] == "pending_sole_human_review", "draft review disposition changed")
    require(bank["confirmatory_task_credit"] == 0, "development promoted to confirmation")
    material = {}
    for name, ref in bank["source_bindings"].items():
        path = (root / ref["path"]).resolve()
        require(path.is_relative_to(root), "source path escapes workspace")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "source hash mismatch: " + name)
        content = raw.decode("utf-8")
        lo, hi = ref["lines"]
        require(type(lo) is int and type(hi) is int and 1 <= lo <= hi <= len(content.splitlines()),
                "source line range: " + name)
        material[name] = content
    return material


def original_seed_state(material):
    """Load the raw source dataset; no original data.py/tools.py is executed."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(material["agentops_schema"])
        connection.executescript(material["agentops_seed"])
        names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(names == {"services", "incidents", "audit_log", "sqlite_sequence"}, "seed table closure")
        database = {name: [dict(row) for row in connection.execute('SELECT * FROM "' + name + '"')]
                    for name in sorted(names)}
    finally:
        connection.close()
    return {"database": database, "durable_notes": {}}


def empty_ap2_state():
    return {"merchant_store": {}, "key_files": {}, "credential_tokens": {},
            "payment_receipts": [], "processor_requests": []}


def first_and_all(data_key, data_parts):
    """Independent positional relation, including falsy values and multiplicity."""
    require(type(data_key) is str and type(data_parts) is list and
            all(type(part) is dict for part in data_parts), "DataPart domain")
    positions = tuple(index for index in range(len(data_parts)) if data_key in data_parts[index])
    values = tuple(data_parts[index][data_key] for index in positions)
    return {"first": None if not positions else data_parts[min(positions)][data_key], "all": list(values)}


def service_read(state, name):
    database = state["database"]
    service_rows = tuple(row for row in database["services"] if row["name"] == name)
    require(len(service_rows) == 1, "fixed service is not unique")
    active_ids = {row["id"] for row in database["incidents"]
                  if row["service"] == name and row["status"] in ("open", "investigating")}
    chronology = sorted(database["incidents"], key=lambda row: row["opened_at"], reverse=True)
    active = [{key: row[key] for key in ("id", "title", "severity", "status")}
              for row in chronology if row["id"] in active_ids]
    return {"service": dict(service_rows[0]), "open_incidents": active}


def expected_case(case, material):
    kind = case["oracle_kind"]
    if kind.startswith("agentops_"):
        state = original_seed_state(material)
    else:
        state = empty_ap2_state()
    if kind == "agentops_health":
        observed = service_read(state, "api-gateway")
        calls = {"health": ("get_service_status", {"name": " API-GATEWAY "}, observed)}
        final = {"service": observed["service"], "active_incidents": observed["open_incidents"]}
        dependencies = {"health": set()}
    elif kind == "agentops_dependent":
        rows = [row for row in state["database"]["incidents"] if row["id"] == "INC-006"]
        require(len(rows) == 1, "fixed incident not unique")
        incident = dict(rows[0])
        service = service_read(state, incident["service"])
        # Build a chronological index and select the newest source lines through
        # descending positions; this is independent of the application's loop.
        log_rows = dict(enumerate(material["checkout_logs"].splitlines()))
        indexes = sorted(log_rows, reverse=True)
        unfiltered = [log_rows[index] for index in indexes[:20]]
        narrowed = [log_rows[index] for index in indexes if "disk" in log_rows[index].casefold()][:20]
        runbook = {"slug": incident["runbook"], "content": material["disk_full_runbook"]}
        calls = {
            "incident": ("get_incident", {"incident_id": " inc-006 "}, {"incident": incident}),
            "health": ("get_service_status", {"name": incident["service"]}, service),
            "logs_all": ("search_service_logs", {"service": incident["service"], "query": "", "limit": 20},
                         {"service": incident["service"], "count": len(unfiltered), "lines": unfiltered}),
            "logs_disk": ("search_service_logs", {"service": incident["service"], "query": "disk", "limit": 20},
                          {"service": incident["service"], "count": len(narrowed), "lines": narrowed}),
            "runbook": ("get_runbook", {"slug": incident["runbook"]}, runbook),
        }
        dependencies = {"incident": set(), "health": {"incident"}, "logs_all": {"incident"},
                        "runbook": {"incident"}, "logs_disk": {"incident", "logs_all"}}
        final = {"incident": incident, "current_service": service["service"],
                 "active_incidents": service["open_incidents"], "unfiltered_logs": unfiltered,
                 "disk_matches": narrowed, "runbook": runbook,
                 "disk_fault_observed_in_current_sample": bool(narrowed)}
    elif kind == "ap2_lookup":
        parts = case["input_data_parts"]
        outcome = first_and_all("risk_data", parts)
        args = {"data_key": "risk_data", "data_parts": parts}
        calls = {"first": ("find_data_part", args, outcome["first"]),
                 "all": ("find_data_parts", args, outcome["all"])}
        dependencies = {"first": set(), "all": set()}
        final = outcome
    elif kind == "ap2_missing_risk":
        parts = case["input_data_parts"]
        payment = first_and_all("ap2.mandates.PaymentMandateSdJwt", parts)["first"]
        checkout = first_and_all("ap2.mandates.CheckoutMandateSdJwt", parts)["first"]
        risk = first_and_all("risk_data", parts)["first"]
        require(bool(payment) and not checkout and not risk, "missing-risk branch preconditions")
        calls = {"initiate": ("initiate_payment", {"data_parts": parts}, None)}
        dependencies = {"initiate": set()}
        final = {"payment_started": False, "task_state": "failed", "reason": "Missing risk_data."}
    else:
        raise GoldError("unknown oracle kind")
    return state, calls, dependencies, final


def grade_case(root, bank, case, trace):
    """Return accepted/rejected/unknown for one complete finite typed trace.

    Every nonempty accepted trace has a checked final goal and no forbidden
    intermediate action. Missing observer coverage stays unknown. A complete
    observed but truncated task is rejected, rather than counted as completion.
    """
    try:
        material = verify_sources(root, bank)
        require(case["split"] == "development" and case["confirmatory_task_credit"] == 0,
                "case promoted out of development")
        require(trace["schema_version"] == "remaining-development-trace/1", "trace schema")
        require(trace["case_id"] == case["id"], "case identity")
        require(equal(trace["identity"], case["fixture_identity"]), "foreign task/context identity")
        coverage = trace.get("coverage", {})
        if coverage != {"event_log_complete": True, "business_state_complete_at_each_event": True,
                        "adapter_status": "constructed_only"}:
            return {"disposition": "unknown", "task_complete": False, "reason": "observer coverage not established"}
        require(trace["evidence_class"] == "constructed_owned_trace", "unqualified runtime evidence class")
        state, calls, dependencies, final = expected_case(case, material)
        require(equal(trace["before_state"], state), "initial complete state differs from source-bound fixture")
        require(equal(trace["after_state"], state), "forbidden final business write")
        events = trace["events"]
        require(type(events) is list and 0 < len(events) <= case["max_events"], "finite event horizon")
        complete, identifiers = set(), set()
        pending = None
        answered = failed = False
        for ordinal, event in enumerate(events):
            require(type(event["seq"]) is int and event["seq"] == ordinal, "event order/sequence")
            require(event["task_id"] == trace["identity"]["task_id"] and
                    event["context_id"] == trace["identity"]["context_id"], "foreign event identity")
            require(equal(event["state"], state), "forbidden intermediate business write or incomplete snapshot")
            require(not answered, "action after final answer")
            base = {"seq", "kind", "task_id", "context_id", "state"}
            kind = event["kind"]
            if kind == "call":
                require(set(event) == base | {"call_id", "tool", "args"}, "call evidence shape")
                require(pending is None, "dependent call before previous terminal")
                call_id = event["call_id"]
                require(type(call_id) is str and bool(call_id) and call_id not in identifiers,
                        "call identity missing or reused")
                matches = [name for name, (tool, args, _) in calls.items()
                           if event["tool"] == tool and equal(event["args"], args)]
                require(len(matches) == 1, "forbidden, guessed or undeclared call")
                name = matches[0]
                require(name not in complete and dependencies[name] <= complete, "read dependency/order violation")
                identifiers.add(call_id)
                pending = (name, call_id)
            elif kind == "result":
                require(set(event) == base | {"call_id", "tool", "output"}, "result evidence shape")
                require(pending is not None and event["call_id"] == pending[1], "unbound or foreign result")
                name = pending[0]
                require(event["tool"] == calls[name][0] and equal(event["output"], calls[name][2]),
                        "result disagrees with independent source oracle")
                if case["oracle_kind"] == "ap2_missing_risk":
                    require(failed, "function returned without required early task failure")
                complete.add(name)
                pending = None
            elif kind == "task_failed":
                require(set(event) == base | {"call_id", "status", "message"}, "task failure evidence shape")
                require(case["oracle_kind"] == "ap2_missing_risk" and pending is not None and
                        event["call_id"] == pending[1] and not failed, "unexpected or unbound task failure")
                require(event["status"] == "failed" and event["message"] == "Missing risk_data.",
                        "incorrect early-rejection state/message")
                failed = True
            elif kind == "answer":
                require(set(event) == base | {"output"}, "typed answer evidence shape")
                require(pending is None and complete == set(calls), "answer before all grounded reads")
                require(equal(event["output"], final), "typed task goal or grounding differs")
                answered = True
            else:
                raise GoldError("forbidden or unmodelled action: " + str(kind))
        require(answered and pending is None and complete == set(calls), "incomplete task trace")
        return {"disposition": "accepted", "task_complete": True,
                "reason": "all finite goals, identities, dependencies and intermediate state checked"}
    except (GoldError, KeyError, TypeError, ValueError, OSError) as error:
        return {"disposition": "rejected", "task_complete": False, "reason": str(error)}


def review_packet(root, directory):
    directory = Path(directory)
    public = load_json(directory / "application.json")
    bank = load_json(directory / "evaluator-private.json")
    verify_sources(root, bank)
    require(public["schema_version"] == "remaining-development-tasks/1", "public schema")
    public_rows = {row["id"]: row for row in public["records"]}
    private_rows = {row["id"]: row for row in bank["records"]}
    require(len(public_rows) == len(private_rows) == 4 and public_rows.keys() == private_rows.keys(),
            "four-task public/private join")
    references = load_json(directory / "reference-traces.json")
    misses = load_json(directory / "near-miss-traces.json")
    outcomes = []
    for record in references["traces"]:
        case = private_rows[record["case_id"]]
        require(equal(case["public_task"], public_rows[case["id"]]["public"]), "public/private task differs")
        result = grade_case(root, bank, case, record)
        require(result["disposition"] == "accepted", "reference rejected: " + result["reason"])
        outcomes.append({"id": record["case_id"], **result})
    require(len(outcomes) == 4 and {r["id"] for r in outcomes} == set(private_rows), "reference coverage")
    negative_outcomes = []
    for record in misses["cases"]:
        result = grade_case(root, bank, private_rows[record["trace"]["case_id"]], record["trace"])
        require(result["disposition"] == record["expected_disposition"] and not result["task_complete"],
                "near miss accepted or misclassified: " + record["name"])
        negative_outcomes.append({"name": record["name"], **result})
    return {"schema_version": "remaining-development-gold-validation/1", "status": "software_controls_passed",
            "reference_results": outcomes, "near_miss_results": negative_outcomes,
            "complete_only_for_declared_finite_typed_tasks": True,
            "human_semantic_validation": "pending_sole_human_review",
            "independent_second_human_review": False, "new_original_application_calls": 0,
            "new_provider_calls": 0, "confirmatory_task_credit": 0,
            "AP2_full_shopper_task_credit": 0, "unseen_family_holdout_credit": 0}
