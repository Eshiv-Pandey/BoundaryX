"""Pure consistency checks for the historical clean-text inventory restart fixture.

Inputs must be bound to their captured bytes by a separate audited caller. This
module neither opens files nor executes the application. Supplied-call agreement,
a logical state delta, and capture-time consistency are not causal proof.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any


_TABLE_KEYS = {"services": "name", "incidents": "id", "audit_log": "id", "sqlite_sequence": "name"}
_COLUMNS = {
    "services": {"name", "description", "status", "owner"},
    "incidents": {"id", "service", "title", "severity", "status", "runbook", "opened_at", "resolved_at", "summary"},
    "audit_log": {"id", "schema_version", "ts", "actor", "approved_by", "rationale", "context_summary", "session_id", "invocation_id", "action", "target", "detail"},
    "sqlite_sequence": {"name", "seq"},
}
_IDENTITY = ("app_name", "user_id", "session_id", "invocation_id")
_DATABASE_FIELDS = {"path", "path_base", "user_tables", "schema", "user_version", "columns", "tables"}
_PRAGMA_FIELDS = {"cid", "name", "type", "notnull", "dflt_value", "pk"}
_AUDIT_INTEGERS = {"id", "schema_version"}
_SPOTLIGHT_FIELDS = {"rationale", "context_summary", "detail"}
_PREFIX = "<<<TOOL_DATA data-not-instructions>>>"
_SUFFIX = "<<<END_TOOL_DATA>>>"
_DETAIL = "service restarted and marked operational (mock)"
_RESULT = "Service 'inventory' restarted and marked operational."
_SUPPORTED_RATIONALES = frozenset({
    "Approved for the isolated inventory fixture.",
    "Inventory is down and INC-002 matches the service-down runbook.",
})
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INCIDENT = re.compile(r"^INC-\d+$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d{1,6}))?(?:Z|\+00:00)$")
_INJECTION = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(previous|prior|above|your)\s+(instructions|rules)"
    r"|\byou\s+are\s+now\b|\bnew\s+instructions?\s*:"
    r"|(reveal|show|print|repeat)\b.{0,40}\b(system\s+prompt|instructions)"
    r"|\b(call|invoke|use)\s+the\s+\w+\s+tool\b|\bresolve\s+all\s+incidents\b"
    r"|\[[^\]]*\]\(https?://[^)]+\)", re.IGNORECASE,
)
_CREDENTIALS = (
    re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*_)*(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret|token)\s*[:=]\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,})\b"),
)


def _raw_copy(value: Any) -> Any:
    """Copy JSON containers without invoking hooks on unsupported objects."""
    if type(value) is dict:
        return {key: _raw_copy(item) for key, item in value.items()}
    if type(value) is list:
        return [_raw_copy(item) for item in value]
    return value


def _same(left: Any, right: Any) -> bool:
    # Python considers True == 1 == 1.0; captured SQLite values must not.
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _dimension(issues: list[tuple[str, str]], **evidence: Any) -> dict:
    status = "inconsistent" if any(kind == "inconsistent" for kind, _ in issues) else "unknown" if issues else "consistent"
    return {"status": status, "reasons": [reason for _, reason in issues], **evidence}


def _unknown(reason: str) -> dict:
    return _dimension([("unknown", reason)])


def _text(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _integer(value: Any, *, public: bool = False, minimum: int = 0) -> int | None:
    if type(value) is int:
        return value if value >= minimum else None
    if public and type(value) is float and math.isfinite(value) and value.is_integer() and abs(value) <= 2**53 - 1:
        return int(value) if value >= minimum else None
    return None


def _clean_text_dimension(rationale: Any, identity: Any, observation: Any) -> dict:
    """A declared fixture allowlist, never an implementation of Presidio."""
    issues = []
    if not _text(rationale):
        issues.append(("unknown", "nonempty fixture rationale is unavailable"))
    elif (not rationale.isascii() or rationale != rationale.strip() or _PREFIX in rationale or _SUFFIX in rationale
          or _INJECTION.search(rationale) or any(pattern.search(rationale) for pattern in _CREDENTIALS)):
        issues.append(("unknown", "rationale may require pinned persistence/guardrail transforms"))
    elif rationale not in _SUPPORTED_RATIONALES:
        issues.append(("unknown", "rationale is outside the explicitly declared clean fixture texts"))
    for label, scope in (("expected", identity), ("executed", observation)):
        if type(scope) is not dict:
            issues.append(("unknown", f"{label} identity is unavailable for the canonical-text check"))
            continue
        for key in _IDENTITY:
            value = scope.get(key)
            if not _text(value) or not value.isascii() or value != value.strip():
                issues.append(("unknown", f"{label} {key} is outside the canonical ASCII fixture identity contract"))
            elif (_PREFIX in value or _SUFFIX in value or _INJECTION.search(value)
                  or any(pattern.search(value) for pattern in _CREDENTIALS)):
                issues.append(("unknown", f"{label} {key} may require pinned output transforms"))
    return _dimension(issues, rationale_scope="declared_clean_fixture_texts_only", source_clean_transforms_proven=False)


def _context_dimension(before: dict | None, audit: dict | None) -> dict:
    """Mirror only the pinned SELECT/filter/TEXT order, not SQLite execution."""
    if before is None or audit is None or "inventory" not in before["services"]:
        return _unknown("valid before state and uniquely appended audit are required for context comparison")
    selected = [row for row in before["incidents"].values() if row["service"] == "inventory" and row["status"] != "resolved"]
    opened_at = [row["opened_at"] for row in selected]
    if any(not value.isascii() for value in opened_at):
        return _unknown("incident TEXT ordering is outside the ASCII historical fixture representation")
    if len(set(opened_at)) != len(opened_at):
        return _unknown("equal qualifying opened_at values have no pinned query tie-breaker or captured row-order proof")
    # The pinned query orders the stored TEXT, not parsed chronological instants.
    ordered = sorted(selected, key=lambda row: row["opened_at"], reverse=True)
    incident_ids = [row["id"] for row in ordered]
    context = f"service inventory was {before['services']['inventory']['status']}; open incidents: {', '.join(incident_ids) or 'none'}"
    issues = [] if _same(audit["context_summary"], context) else [("inconsistent", "appended audit context does not match the pinned query over before-state rows")]
    return _dimension(issues, derived_context_summary=context, ordered_open_incident_ids=incident_ids,
                      context_source="pinned before-state SELECT semantics; transaction-time state not proven")


def _row_valid(table: str, row: dict) -> bool:
    if set(row) != _COLUMNS[table]:
        return False
    if table == "sqlite_sequence":
        return _text(row["name"]) and _integer(row["seq"]) is not None
    if table == "audit_log":
        return (_integer(row["id"], minimum=1) is not None and type(row["schema_version"]) is int
                and row["schema_version"] == 1 and all(_text(row[key]) for key in _COLUMNS[table] - _AUDIT_INTEGERS)
                and len(row["rationale"]) <= 500)
    if table == "services":
        return (all(_text(row[key]) for key in _COLUMNS[table]) and bool(_SLUG.fullmatch(row["name"]))
                and row["status"] in {"down", "degraded", "operational"})
    strings = _COLUMNS[table] - {"resolved_at"}
    return (all(_text(row[key]) for key in strings) and bool(_INCIDENT.fullmatch(row["id"]))
            and bool(_SLUG.fullmatch(row["service"])) and bool(_SLUG.fullmatch(row["runbook"]))
            and row["severity"] in {"SEV1", "SEV2", "SEV3"}
            and row["status"] in {"open", "investigating", "resolved"}
            and (row["resolved_at"] is None or _text(row["resolved_at"])))


def _parse_database(snapshot: Any, label: str) -> tuple[dict | None, dict | None, list[tuple[str, str]]]:
    issues: list[tuple[str, str]] = []
    if type(snapshot) is not dict or type(snapshot.get("database")) is not dict:
        return None, None, [("unknown", f"{label}: unsupported or missing snapshot/database object")]
    database = snapshot["database"]
    missing = _DATABASE_FIELDS - set(database)
    if missing:
        return None, None, [("unknown", f"{label}: missing database fields {sorted(missing)}")]
    if set(database) != _DATABASE_FIELDS:
        issues.append(("unknown", f"{label}: unsupported database metadata extensions"))
    if type(database["tables"]) is not dict or type(database["columns"]) is not dict:
        return None, None, [("unknown", f"{label}: unsupported tables/columns shape")]
    if set(database["tables"]) != set(_TABLE_KEYS) or set(database["columns"]) != set(_TABLE_KEYS):
        return None, None, [("unknown", f"{label}: unsupported table or column-table membership")]
    if not _text(database["path"]) or not _text(database["path_base"]) or _integer(database["user_version"]) is None:
        issues.append(("inconsistent", f"{label}: malformed database path/base/user_version"))
    names = database["user_tables"]
    if type(names) is not list:
        issues.append(("unknown", f"{label}: unsupported user_tables shape"))
    elif any(type(name) is not str for name in names) or len(set(names)) != len(names) or set(names) != set(_TABLE_KEYS) - {"sqlite_sequence"}:
        issues.append(("inconsistent", f"{label}: malformed or duplicate user_tables names"))
    schema = database["schema"]
    schema_map: dict = {}
    if type(schema) is not list:
        issues.append(("unknown", f"{label}: unsupported sqlite_schema shape"))
    else:
        for item in schema:
            if type(item) is not dict or set(item) != {"type", "name", "tbl_name", "sql"}:
                issues.append(("unknown", f"{label}: unsupported sqlite_schema row shape"))
                continue
            if (not all(_text(item[key]) for key in ("type", "name", "tbl_name"))
                    or item["type"] not in {"table", "index", "trigger", "view"}
                    or (item["sql"] is not None and not _text(item["sql"]))
                    or (item["type"] == "table" and (item["sql"] is None or item["tbl_name"] != item["name"]))
                    or (item["type"] in {"index", "trigger"} and item["tbl_name"] not in _TABLE_KEYS)):
                issues.append(("inconsistent", f"{label}: malformed sqlite_schema row"))
                continue
            key = (item["type"], item["name"])
            if key in schema_map:
                issues.append(("inconsistent", f"{label}: duplicate sqlite_schema row key {key}"))
            schema_map[key] = item
        if {name for kind, name in schema_map if kind == "table"} != set(_TABLE_KEYS):
            issues.append(("inconsistent", f"{label}: schema table membership disagrees with tables"))
    columns: dict = {}
    tables: dict = {}
    for table, key_name in _TABLE_KEYS.items():
        descriptors = database["columns"][table]
        column_map: dict = {}
        if type(descriptors) is not list:
            issues.append(("unknown", f"{label}: unsupported {table} PRAGMA columns shape"))
        else:
            cids: set[int] = set()
            for item in descriptors:
                if type(item) is not dict or set(item) != _PRAGMA_FIELDS:
                    issues.append(("unknown", f"{label}: unsupported {table} column descriptor"))
                    continue
                cid = _integer(item["cid"])
                if (cid is None or not _text(item["name"]) or type(item["type"]) is not str
                        or type(item["notnull"]) is not int or item["notnull"] not in {0, 1}
                        or _integer(item["pk"]) is None
                        or (item["dflt_value"] is not None and type(item["dflt_value"]) is not str)):
                    issues.append(("inconsistent", f"{label}: malformed {table} column descriptor"))
                    continue
                if item["name"] in column_map or cid in cids:
                    issues.append(("inconsistent", f"{label}: duplicate {table} column name/cid"))
                cids.add(cid)
                column_map[item["name"]] = item
            if set(column_map) != _COLUMNS[table] or cids != set(range(len(_COLUMNS[table]))):
                issues.append(("unknown", f"{label}: unsupported {table} column-name/cid schema"))
        columns[table] = column_map
        rows = database["tables"][table]
        row_map: dict = {}
        if type(rows) is not list:
            issues.append(("unknown", f"{label}: unsupported {table} row-list shape"))
        else:
            for row in rows:
                if type(row) is not dict or not _row_valid(table, row):
                    issues.append(("inconsistent", f"{label}: malformed {table} row or row schema"))
                    continue
                key = row[key_name]
                if key in row_map:
                    issues.append(("inconsistent", f"{label}: duplicate {table} row key {key!r}"))
                row_map[key] = row
        tables[table] = row_map
    if issues:
        return None, None, issues
    metadata = {key: value for key, value in database.items() if key != "tables"}
    metadata.update(user_tables=sorted(names), schema=schema_map, columns=columns)
    return tables, metadata, issues


def _utc_interval(value: Any, label: str) -> tuple[datetime | None, datetime | None, list[tuple[str, str]]]:
    if value is None:
        return None, None, [("unknown", f"{label}: missing UTC timestamp")]
    if type(value) is not str:
        return None, None, [("inconsistent", f"{label}: timestamp is not text")]
    match = _UTC.fullmatch(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, None, [("inconsistent", f"{label}: malformed timestamp")]
    if match is None or parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None, None, [("unknown", f"{label}: unsupported UTC representation or precision")]
    fraction = match.group(1)
    precision = timedelta(microseconds=10 ** (6 - len(fraction))) if fraction else timedelta(seconds=1)
    try:
        return parsed.astimezone(timezone.utc), parsed.astimezone(timezone.utc) + precision, []
    except OverflowError:
        return None, None, [("unknown", f"{label}: timestamp precision interval overflows")]


def _time_dimension(before: Any, after: Any, audit: dict | None, exchange: Any) -> dict:
    if audit is None:
        return _unknown("no uniquely appended valid audit row for time comparison")
    if type(before) is not dict or type(after) is not dict or type(exchange) is not dict:
        return _unknown("unsupported snapshot/exchange objects for time comparison")
    issues: list[tuple[str, str]] = []
    if exchange.get("schema_version") != "agentops-asgi-exchange/1":
        issues.append(("unknown", "missing or unsupported captured exchange schema"))
    if "error" in exchange or "snapshot_error" in exchange:
        issues.append(("unknown", "captured exchange reports an execution/snapshot error"))
    values = []
    for value, label in ((before.get("observed_at_utc"), "before snapshot"),
                         (after.get("observed_at_utc"), "after snapshot"),
                         (exchange.get("started_at_utc"), "exchange start"),
                         (exchange.get("finished_at_utc"), "exchange finish"), (audit.get("ts"), "audit")):
        start, end, problems = _utc_interval(value, label)
        values.append((start, end))
        issues.extend(problems)
    ticks = (before.get("monotonic_ns"), after.get("monotonic_ns"))
    if any(value is None for value in ticks):
        issues.append(("unknown", "snapshot monotonic observations are missing"))
    elif any(_integer(value) is None for value in ticks):
        issues.append(("inconsistent", "snapshot monotonic observations must be nonnegative integers, excluding booleans"))
    elif ticks[0] >= ticks[1]:
        issues.append(("unknown", "snapshot monotonic observations do not establish a strict interval"))
    if any(start is None for start, _ in values):
        return _dimension(issues, audit_timestamp_precision="unresolved", authoritative_clock_proven=False)
    before_interval, after_interval, start_interval, finish_interval, audit_interval = values
    audit_at, audit_end = audit_interval
    evidence = {"audit_interval_start_utc": audit_at.isoformat(), "audit_interval_end_exclusive_utc": audit_end.isoformat(),
                "audit_timestamp_precision_seconds": (audit_end - audit_at).total_seconds(), "authoritative_clock_proven": False,
                "endpoint_intervals": {label: {"start_utc": start.isoformat(), "end_exclusive_utc": end.isoformat()}
                                       for label, (start, end) in zip(("before_snapshot", "after_snapshot", "exchange_start", "exchange_finish"), values[:4])}}
    if before_interval[1] > after_interval[0] or start_interval[1] > finish_interval[0]:
        issues.append(("unknown", "UTC observations do not establish strict snapshot/exchange intervals"))
    elif start_interval[1] <= before_interval[0] or after_interval[1] <= finish_interval[0]:
        issues.append(("inconsistent", "snapshot observations do not bracket the captured exchange"))
    else:
        ordering = ((before_interval, start_interval), (start_interval, finish_interval), (finish_interval, after_interval))
        if any(left[1] > right[0] for left, right in ordering):
            issues.append(("unknown", "snapshot/exchange endpoint precision intervals overlap; strict capture ordering is unresolved"))
        possible_lower = max(before_interval[0], start_interval[0])
        possible_upper = min(after_interval[1], finish_interval[1])
        guaranteed_lower = max(before_interval[1], start_interval[1])
        guaranteed_upper = min(after_interval[0], finish_interval[0])
        evidence.update(guaranteed_bracket_start_utc=guaranteed_lower.isoformat(), guaranteed_bracket_end_utc=guaranteed_upper.isoformat())
        if audit_end <= possible_lower or audit_at >= possible_upper:
            issues.append(("inconsistent", "declared audit precision interval is disjoint from the capture bracket"))
        elif audit_at < guaranteed_lower or audit_end > guaranteed_upper:
            issues.append(("unknown", "audit precision interval overlaps but is not wholly bracketed by the capture"))
    return _dimension(issues, **evidence)


def check_restart_effect(before_snapshot: Any, after_snapshot: Any, executed_function: Any,
                         expected_identity: Any, rationale: Any, exchange: Any) -> dict:
    """Check a supplied historical fixture pair without file I/O or runtime calls.

    ``executed_function`` is the raw response observation enriched with
    ``original_function_call`` (id/name/args) by the separately audited caller.
    Expected identity has app_name/user_id/session_id/invocation_id. Missing or
    unsupported evidence stays unknown; an observed contradiction is inconsistent.
    """
    dimensions = {name: _unknown("required evidence was not checked") for name in (
        "input_shape", "database_metadata", "service_delta", "incident_preservation", "audit_append",
        "audit_identity", "audit_context", "idempotency_consistency", "clean_text_contract", "executed_result_agreement",
        "sqlite_sequence", "timestamp_consistency", "unrelated_table_preservation")}
    before, before_metadata, shape = _parse_database(before_snapshot, "before")
    after, after_metadata, problems = _parse_database(after_snapshot, "after")
    shape.extend(problems)
    identity_ok = type(expected_identity) is dict
    if not identity_ok:
        shape.append(("unknown", "missing or unsupported expected identity object"))
    elif any(key not in expected_identity for key in _IDENTITY):
        identity_ok = False
        shape.append(("unknown", "expected identity is missing required scope fields"))
    elif any(not _text(expected_identity[key]) for key in _IDENTITY):
        identity_ok = False
        shape.append(("inconsistent", "expected identity scope fields must be nonempty text"))
    rationale_ok = _text(rationale) and len(rationale) <= 500
    if rationale is None:
        shape.append(("unknown", "approval rationale is missing"))
    elif not rationale_ok:
        shape.append(("inconsistent", "approval rationale must be nonempty text of at most 500 characters"))
    elif (not rationale.isascii() or rationale != rationale.strip() or _PREFIX in rationale or _SUFFIX in rationale
          or _INJECTION.search(rationale) or any(pattern.search(rationale) for pattern in _CREDENTIALS)
          or rationale not in _SUPPORTED_RATIONALES):
        rationale_ok = False
        shape.append(("unknown", "approval rationale is outside this clean-text fixture contract"))
    function = original = response = None
    function_issues: list[tuple[str, str]] = []
    if type(executed_function) is not dict:
        function_issues.append(("unknown", "missing or unsupported executed function observation"))
    else:
        function = executed_function.get("function")
        original = executed_function.get("original_function_call")
        if type(function) is not dict or not {"id", "name", "response"} <= set(function):
            function_issues.append(("unknown", "missing or unsupported executed function payload"))
            function = None
        else:
            response = function["response"]
            if set(function) != {"id", "name", "response"}:
                function_issues.append(("unknown", "executed function payload has unsupported fields"))
            if "kind" not in executed_function:
                function_issues.append(("unknown", "executed observation kind is missing"))
            elif executed_function["kind"] != "function_response":
                function_issues.append(("inconsistent", "executed observation kind is not function_response"))
            if function["name"] != "restart_service" or not _text(function["id"]):
                function_issues.append(("inconsistent", "executed observation is not the declared restart_service response"))
        if type(original) is not dict or not {"id", "name", "args"} <= set(original):
            function_issues.append(("unknown", "original_function_call is missing or unsupported"))
            original = None
        elif not _text(original["id"]) or original["name"] != "restart_service" or not _same(original["args"], {"name": "inventory"}):
            function_issues.append(("inconsistent", "original call does not declare the inventory restart fixture"))
        elif set(original) != {"id", "name", "args"}:
            function_issues.append(("unknown", "original function call has unsupported fields"))
        if original is not None and function is not None and (not _same(original["id"], function["id"]) or not _same(original["name"], function["name"])):
            function_issues.append(("inconsistent", "supplied original/executed function IDs or names disagree"))
        if any(key not in executed_function for key in _IDENTITY):
            function_issues.append(("unknown", "executed observation is missing runtime scope fields"))
        elif any(not _text(executed_function[key]) for key in _IDENTITY):
            function_issues.append(("inconsistent", "executed runtime scope fields must be nonempty text"))
        elif identity_ok and any(not _same(executed_function[key], expected_identity[key]) for key in _IDENTITY):
            function_issues.append(("inconsistent", "executed observation disagrees with expected runtime scope"))
    shape.extend(function_issues)
    dimensions["input_shape"] = _dimension(shape)
    dimensions["clean_text_contract"] = _clean_text_dimension(rationale, expected_identity, executed_function)
    # Compare all logical metadata, including extensions, even when another
    # malformed input prevents parsing the supported table model.
    if before_metadata is not None and after_metadata is not None:
        dimensions["database_metadata"] = _dimension([] if _same(before_metadata, after_metadata) else [("inconsistent", "logical database metadata/schema/columns changed")])
    elif (type(before_snapshot) is dict and type(after_snapshot) is dict
          and type(before_snapshot.get("database")) is dict and type(after_snapshot.get("database")) is dict
          and _DATABASE_FIELDS <= set(before_snapshot["database"]) and _DATABASE_FIELDS <= set(after_snapshot["database"])):
        a = {key: value for key, value in before_snapshot["database"].items() if key != "tables"}
        b = {key: value for key, value in after_snapshot["database"].items() if key != "tables"}
        dimensions["database_metadata"] = _unknown("supported metadata is incomplete") if _same(a, b) else _dimension([("inconsistent", "logical database metadata/schema/columns changed")])
    raw_tables = [snapshot.get("database", {}).get("tables") if type(snapshot) is dict and type(snapshot.get("database")) is dict else None for snapshot in (before_snapshot, after_snapshot)]
    if all(type(value) is dict for value in raw_tables):
        a, b = raw_tables
        extras = (set(a) | set(b)) - set(_TABLE_KEYS)
        changes = set(a) != set(b) or any(key not in a or key not in b or not _same(a[key], b[key]) for key in extras)
        dimensions["unrelated_table_preservation"] = _dimension([("inconsistent", "unsupported/unrelated table membership or contents changed")] if changes else [])
    audit = None
    if before is not None and after is not None:
        services_before, services_after = before["services"], after["services"]
        expected_services = _raw_copy(services_before)
        if "inventory" not in expected_services or "inventory" not in services_after:
            dimensions["service_delta"] = _dimension([("inconsistent", "inventory fixture service is missing")])
        else:
            expected_services["inventory"]["status"] = "operational"
            valid = services_before["inventory"]["status"] == "down" and _same(expected_services, services_after)
            dimensions["service_delta"] = _dimension([] if valid else [("inconsistent", "expected only inventory status down -> operational; other service contents must be unchanged")])
        dimensions["incident_preservation"] = _dimension([] if _same(before["incidents"], after["incidents"]) else [("inconsistent", "incident rows changed")])
        prior, current = before["audit_log"], after["audit_log"]
        new_ids = set(current) - set(prior)
        preserved = all(key in current and _same(row, current[key]) for key, row in prior.items())
        append_issues = []
        if not preserved:
            append_issues.append(("inconsistent", "prior audit rows were modified or removed"))
        if len(new_ids) != 1:
            append_issues.append(("inconsistent", "expected exactly one new audit row"))
        elif next(iter(new_ids)) <= max(prior, default=0):
            append_issues.append(("inconsistent", "new audit ID is not fresh and increasing"))
        else:
            audit = current[next(iter(new_ids))]
        dimensions["audit_append"] = _dimension(append_issues, appended_audit_id=audit["id"] if audit else None)
        if audit is not None:
            prior_matches = [row["id"] for row in prior.values() if row["invocation_id"] == audit["invocation_id"]
                             and row["action"] == "restart_service" and row["target"] == "inventory"]
            dimensions["idempotency_consistency"] = _dimension(
                [("inconsistent", "prior audit already has the restart invocation/action/target key; pinned source would return it without a new effect")] if prior_matches else [],
                matching_prior_audit_ids=sorted(prior_matches))
        seq_before, seq_after = before["sqlite_sequence"], after["sqlite_sequence"]
        if audit is not None:
            prior_seq = seq_before.get("audit_log", {}).get("seq", 0)
            expected_seq = _raw_copy(seq_before)
            expected_seq["audit_log"] = {"name": "audit_log", "seq": audit["id"]}
            valid = prior_seq >= max(prior, default=0) and audit["id"] == prior_seq + 1 and _same(expected_seq, seq_after)
            dimensions["sqlite_sequence"] = _dimension([] if valid else [("inconsistent", "only audit_log sequence may advance once to the new audit ID")])
        else:
            dimensions["sqlite_sequence"] = _unknown("no unique new audit ID for the expected sequence delta")
    if audit is not None:
        issues = []
        constants = {"actor": "agentops-agent", "schema_version": 1, "action": "restart_service", "target": "inventory", "detail": _DETAIL}
        for key, expected in constants.items():
            if not _same(audit[key], expected):
                issues.append(("inconsistent", f"appended audit {key} disagrees with the fixture"))
        if not identity_ok:
            issues.append(("unknown", "expected runtime identity is unavailable"))
        else:
            for key, identity_key in (("approved_by", "user_id"), ("session_id", "session_id"), ("invocation_id", "invocation_id")):
                if not _same(audit[key], expected_identity[identity_key]):
                    issues.append(("inconsistent", f"appended audit {key} disagrees with runtime identity"))
        if not rationale_ok:
            issues.append(("unknown", "supported clean-text approval rationale is unavailable"))
        elif not _same(audit["rationale"], rationale):
            issues.append(("inconsistent", "appended audit rationale disagrees with the supplied approval rationale"))
        dimensions["audit_identity"] = _dimension(issues, identity_assurance="supplied runtime identity; authenticated human identity not established")
    dimensions["audit_context"] = _context_dimension(before, audit)
    agreement = list(function_issues)
    if audit is None:
        agreement.append(("unknown", "no uniquely appended valid audit for executed result agreement"))
    if type(response) is not dict:
        agreement.append(("unknown", "executed function response is missing or unsupported"))
    elif "error" in response or set(response) - {"result", "audit"}:
        agreement.append(("inconsistent", "executed response contains an error or undeclared result fields"))
    elif not {"result", "audit"} <= set(response):
        agreement.append(("unknown", "executed response is missing its result or audit"))
    else:
        if not _same(response["result"], _RESULT):
            agreement.append(("inconsistent", "executed restart outcome disagrees with the fixture"))
        public_audit = response["audit"]
        if type(public_audit) is not dict:
            agreement.append(("unknown", "executed audit payload is unsupported"))
        elif set(public_audit) != _COLUMNS["audit_log"]:
            agreement.append(("inconsistent", "executed audit schema differs from the stored audit schema"))
        elif audit is not None:
            for key, stored in audit.items():
                supplied = public_audit[key]
                if key in _AUDIT_INTEGERS:
                    parsed = _integer(supplied, public=True, minimum=1)
                    matches = parsed is not None and parsed == stored
                elif key in _SPOTLIGHT_FIELDS:
                    matches = _same(supplied, f"{_PREFIX}\n{stored}\n{_SUFFIX}")
                else:
                    matches = _same(supplied, stored)
                if not matches:
                    agreement.append(("inconsistent", f"executed audit {key} differs from its narrowly declared stored representation"))
    dimensions["executed_result_agreement"] = _dimension(agreement)
    dimensions["timestamp_consistency"] = _time_dimension(before_snapshot, after_snapshot, audit, exchange)
    statuses = [item["status"] for item in dimensions.values()]
    status = "inconsistent" if "inconsistent" in statuses else "unknown" if "unknown" in statuses else "consistent"
    return {"schema_version": "agentops-restart-effects/1", "status": status, "dimensions": dimensions,
            "raw": {"before_snapshot": _raw_copy(before_snapshot), "after_snapshot": _raw_copy(after_snapshot),
                    "executed_function": _raw_copy(executed_function), "expected_identity": _raw_copy(expected_identity),
                    "rationale": _raw_copy(rationale), "exchange": _raw_copy(exchange)},
            "graded_upstream_cases": 0, "new_native_runs": 0, "raw_byte_binding_checked": False,
            "rationale_scope": "declared_clean_fixture_texts_only", "source_clean_transforms_proven": False,
            "phase_linkage_checked": False, "continuous_absence_of_mutation_proven": False,
            "causal_order_proven": False, "complete_event_stream_proven": False,
            "qualification_established": False, "client_receipt_proven": False}
