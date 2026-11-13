"""Fail-closed Gemini accounting core; this module does not enable native calls.

No key, environment variable, SDK, provider service or model is read/called.
Policy numbers must come from separately reviewed evidence, never defaults.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import stat


MODEL = "gemini-3.1-flash-lite-preview"
POLICY_SCHEMA = "ap2-hp-gemini-accounting-policy/1"
ROLES = {"merchant", "credentials", "processor"}
COUNTS = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount",
          "toolUsePromptTokenCount", "cachedContentTokenCount", "totalTokenCount")
NUMBERS = {"remaining_total_tokens", "remaining_day_requests", "requests_per_minute",
           "input_tokens_per_minute", "initial_minute_requests", "initial_minute_input_tokens",
           "full_input_upper_bound", "maximum_output_upper_bound"}
VERIFIED = {"remaining_allowance_verified", "counting_rules_verified", "reset_rules_verified",
            "full_input_bound_verified", "maximum_output_bound_verified", "same_project_activity_accounted"}


class UsageRefused(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise UsageRefused(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def timestamp(value):
    need(type(value) is str and value.endswith(("Z", "+00:00")), "Explicit UTC time required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise UsageRefused("Invalid UTC time") from error
    need(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, "UTC time required")
    return result.timestamp()


def now_seconds(now=None):
    return datetime.now(timezone.utc).timestamp() if now is None else timestamp(now)


def regular(path, *, exists=True):
    path = Path(path)
    need(path.is_absolute(), "Absolute ledger/evidence path required")
    for item in (path, *path.parents):
        if not item.exists() and not item.is_symlink():
            continue
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Linked/reparse ledger or evidence path refused")
    if exists:
        need(path.is_file(), "Regular evidence/ledger file required")
    else:
        need(not path.exists() and path.parent.is_dir(), "Fresh ledger path with existing parent required")
    return path


def reference(entry):
    need(type(entry) is dict and set(entry) == {"path", "sha256"}, "Exact evidence path/hash required")
    need(type(entry["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "Invalid evidence hash")
    path = regular(entry["path"])
    need(path.stat().st_size <= 4 * 1024 * 1024, "Oversized allowance evidence refused")
    need(sha(path.read_bytes()) == entry["sha256"], "Allowance evidence bytes changed")


def validate_policy(policy, *, now=None):
    required = {"schema_version", "model", "project_alias", "run_id", "configuration_sha256",
                "observed_at_utc", "expires_at_utc", "billing_mode", "allowance_evidence", *NUMBERS, *VERIFIED}
    need(type(policy) is dict and set(policy) == required, "Complete explicit accounting policy required; unknown limits have no default")
    need(policy["schema_version"] == POLICY_SCHEMA and policy["model"] == MODEL, "Exact policy/model required")
    need(policy["billing_mode"] == "reviewed_free_tier", "Actual reviewed project free-tier/billing evidence required")
    need(type(policy["project_alias"]) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", policy["project_alias"]), "Nonsecret project alias required")
    need(type(policy["run_id"]) is str and re.fullmatch(r"[0-9a-f]{32}", policy["run_id"]), "Exact run identity required")
    need(type(policy["configuration_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", policy["configuration_sha256"]), "Exact native configuration hash required")
    need(all(policy[name] is True for name in VERIFIED), "Remaining/count/reset/input/output/activity evidence is unverified")
    need(all(type(policy[name]) is int and 0 <= policy[name] <= (2**63 - 1) // 16 for name in NUMBERS), "Explicit nonnegative integer quota/bound counters required")
    need(all(policy[name] > 0 for name in NUMBERS - {"initial_minute_requests", "initial_minute_input_tokens"}), "No usable positive allowance or per-request bound")
    current = now_seconds(now)
    observed, expires = timestamp(policy["observed_at_utc"]), timestamp(policy["expires_at_utc"])
    need(observed <= current < expires, "Quota observation is future-dated or expired; no automatic reset/replenishment")
    need(type(policy["allowance_evidence"]) is list and policy["allowance_evidence"], "Reviewed provider/project/bound evidence required")
    for item in policy["allowance_evidence"]:
        reference(item)
    # Floor arithmetic keeps at least 20 percent untouched, including small quotas.
    ceilings = {"total_tokens": policy["remaining_total_tokens"] * 4 // 5,
                "day_requests": policy["remaining_day_requests"] * 4 // 5,
                "minute_requests": policy["requests_per_minute"] * 4 // 5,
                "minute_input_tokens": policy["input_tokens_per_minute"] * 4 // 5}
    need(min(ceilings.values()) > 0, "Locked reserve leaves no usable allowance")
    return {"ceilings": ceilings, "observed": observed, "expires": expires,
            "policy_sha256": sha(encoded(policy)), "provider_entitlement_authenticated": False}


def create_ledger(path, policy, *, now=None):
    validated = validate_policy(policy, now=now)  # Refuse before creating anything.
    path = regular(path, exists=False)
    with path.open("xb"):
        pass
    with sqlite3.connect(path) as db:
        db.executescript("""
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=FULL;
            CREATE TABLE policy (singleton INTEGER PRIMARY KEY CHECK(singleton=1), body TEXT NOT NULL, digest TEXT NOT NULL, halted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE attempts (id INTEGER PRIMARY KEY, started REAL NOT NULL, role TEXT NOT NULL, request_digest TEXT NOT NULL, input_bound INTEGER NOT NULL, total_bound INTEGER NOT NULL, charged_total INTEGER NOT NULL, state TEXT NOT NULL);
            CREATE TABLE events (id INTEGER PRIMARY KEY, attempt INTEGER, kind TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        db.execute("INSERT INTO policy(singleton,body,digest) VALUES(1,?,?)", (encoded(policy).decode(), validated["policy_sha256"]))
        db.execute("INSERT INTO events(attempt,kind,payload) VALUES(NULL,'initialized',?)", (encoded(validated).decode(),))
    return {"status": "local_accounting_ledger_initialized", "policy_sha256": validated["policy_sha256"],
            "provider_entitlement_authenticated": False, "native_dispatch_enabled": False}


@contextmanager
def transaction(path):
    path = regular(path)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")  # One shared model/project ledger across service processes.
        yield db
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def policy_row(db, expected_policy_sha256):
    need(type(expected_policy_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_policy_sha256), "Bound immutable policy digest required")
    row = db.execute("SELECT body,digest,halted FROM policy WHERE singleton=1").fetchone()
    need(row is not None and sha(row[0].encode()) == row[1] == expected_policy_sha256, "Ledger policy identity changed")
    return json.loads(row[0]), row[2]


def reserve_attempt(path, *, expected_policy_sha256, role, request_sha256, now=None):
    need(role in ROLES, "Unknown service role")
    need(type(request_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", request_sha256), "Request body digest required; never store body/headers/keys")
    current = now_seconds(now)
    with transaction(path) as db:
        policy, halted = policy_row(db, expected_policy_sha256)
        validated = validate_policy(policy, now=now)
        need(not halted, "Ledger halted after quota/usage-bound failure")
        count, total = db.execute("SELECT COUNT(*),COALESCE(SUM(charged_total),0) FROM attempts").fetchone()
        minute_count, minute_input = db.execute("SELECT COUNT(*),COALESCE(SUM(input_bound),0) FROM attempts WHERE started>=?", (current - 60,)).fetchone()
        if current - validated["observed"] < 60:
            minute_count += policy["initial_minute_requests"]
            minute_input += policy["initial_minute_input_tokens"]
        full_input = policy["full_input_upper_bound"]
        full_total = full_input + policy["maximum_output_upper_bound"]
        ceilings = validated["ceilings"]
        need(count + 1 <= ceilings["day_requests"] and total + full_total <= ceilings["total_tokens"], "Working allowance would cross locked reserve")
        need(minute_count + 1 <= ceilings["minute_requests"] and minute_input + full_input <= ceilings["minute_input_tokens"], "Conservative rolling-minute quota would be exceeded")
        cursor = db.execute("INSERT INTO attempts(started,role,request_digest,input_bound,total_bound,charged_total,state) VALUES(?,?,?,?,?,?,'reserved_unknown_usage')", (current, role, request_sha256, full_input, full_total, full_total))
        attempt = cursor.lastrowid
        value = {"attempt_id": attempt, "role": role, "request_sha256": request_sha256, "reserved_input_tokens": full_input, "reserved_total_tokens": full_total, "reserved_requests": 1}
        db.execute("INSERT INTO events(attempt,kind,payload) VALUES(?,'reserved_before_attempt',?)", (attempt, encoded(value).decode()))
    return value


def record_provider_result(path, attempt_id, *, expected_policy_sha256, usage_metadata=None, http_status=None):
    need(type(attempt_id) is int and attempt_id > 0, "Exact reserved attempt identity required")
    need(http_status is None or type(http_status) is int and 100 <= http_status <= 599, "Typed HTTP status or unknown required")
    counts = {}
    reasons = []
    if http_status != 200:
        reasons.append("provider_http_status_unverified_or_unsuccessful")
    typed_counts = type(usage_metadata) is dict
    if not typed_counts:
        reasons.append("usage_metadata_absent_or_malformed")
    if typed_counts:
        for name in COUNTS:
            if name in usage_metadata:
                value = usage_metadata[name]
                if type(value) is not int or not 0 <= value <= (2**63 - 1) // 16:
                    typed_counts = False
                    reasons.append("malformed_count:" + name)
                else:
                    counts[name] = value
    # SDK source declares the four primary counts as total components. Cached
    # input is included in prompt, not an additional total component. Missing
    # counts are not assumed zero: compare only the known nonnegative lower bound.
    consistent = typed_counts
    known_components = sum(counts[name] for name in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "toolUsePromptTokenCount") if name in counts)
    known_input = max(counts.get("promptTokenCount", 0), counts.get("cachedContentTokenCount", 0))
    known_primary_lower_bound = known_input + sum(counts[name] for name in ("candidatesTokenCount", "thoughtsTokenCount", "toolUsePromptTokenCount") if name in counts)
    known_total_lower_bound = max(counts.get("totalTokenCount", 0), known_primary_lower_bound)
    if typed_counts and "totalTokenCount" in counts:
        consistent = known_primary_lower_bound <= counts["totalTokenCount"]
        if known_components > counts["totalTokenCount"]:
            reasons.append("primary_components_exceed_reported_total")
        if known_primary_lower_bound > counts["totalTokenCount"] and known_components <= counts["totalTokenCount"]:
            reasons.append("cached_input_lower_bound_exceeds_reported_total")
    if typed_counts and "cachedContentTokenCount" in counts and "promptTokenCount" in counts:
        cache_consistent = counts["cachedContentTokenCount"] <= counts["promptTokenCount"]
        consistent = consistent and cache_consistent
        if not cache_consistent:
            reasons.append("cached_count_exceeds_prompt")
    if "totalTokenCount" not in counts:
        reasons.append("total_token_count_missing")
    valid = http_status == 200 and typed_counts and consistent
    # Use the provider total literally. Do not add cached/thinking components twice.
    actual = counts.get("totalTokenCount") if valid else None
    with transaction(path) as db:
        policy_row(db, expected_policy_sha256)
        row = db.execute("SELECT input_bound,total_bound,state FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        need(row is not None and row[2] == "reserved_unknown_usage", "Missing/already-reconciled attempt")
        overrun = known_total_lower_bound > row[1] or known_input > row[0]
        worst_bound = max(row[1], known_total_lower_bound)
        charged = actual if actual is not None else worst_bound
        halt = actual is None or overrun or http_status == 429
        state = "provider_usage_recorded" if actual is not None else "unknown_usage_full_bound_retained"
        value = {"attempt_id": attempt_id, "http_status": http_status, "usage_counts": counts,
                 "reported_total_tokens": counts.get("totalTokenCount"),
                 "usage_metadata_consistent": consistent,
                 "usage_validation_reasons": reasons,
                 "usage_total_observed": actual is not None, "charged_total_tokens": charged,
                 "token_bound_exceeded": overrun, "request_charge_refunded": False,
                 "future_attempts_halted": halt}
        db.execute("UPDATE attempts SET charged_total=?,state=? WHERE id=?", (charged, state, attempt_id))
        db.execute("INSERT INTO events(attempt,kind,payload) VALUES(?,'provider_result',?)", (attempt_id, encoded(value).decode()))
        if halt:
            db.execute("UPDATE policy SET halted=1 WHERE singleton=1")
    return value


def install_guard(*, plan, service, configuration_sha256):
    """Refuse native startup: accounting core is not an SDK before-wire hook.

    The runner's native contract requires installed=True and exact per-request
    transport coverage. This module truthfully supplies neither until a separate
    reviewed SDK hook can call reserve_attempt for every actual HTTP attempt.
    """
    return {"installed": False, "configuration_sha256": configuration_sha256,
            "contract": "accounting_core_only_no_native_enablement",
            "reason": "Verified project quota/token bounds and reviewed SDK before-wire interception are required",
            "model": MODEL, "provider_entitlement_authenticated": False,
            "positive_native_reservation_created": False, "model_requests": 0}
