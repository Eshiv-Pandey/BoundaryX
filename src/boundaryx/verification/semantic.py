"""Separately implemented SQLite oracle for the ten historical task contracts.

This validates declared finite tasks. It does not validate domain expertise or
establish that the authored contracts are scientifically appropriate.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from boundaryx.core.evidence import EvidenceError


def expected_answer(case: dict[str, Any]) -> dict[str, Any]:
    task, rows = case["task"], case["records"]
    c, kind = task["constraints"], task["kind"]
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE records(doc TEXT NOT NULL)")
        db.executemany("INSERT INTO records VALUES (?)", [(json.dumps(r),) for r in rows])

        def query(sql: str, *params: Any) -> list[tuple[Any, ...]]:
            return list(db.execute(sql, params))

        if kind == "health_filter":
            result = query("SELECT doc->>'$.id' FROM records WHERE doc->>'$.region'=? AND doc->>'$.status'=? ORDER BY doc->>'$.id'", c["region"], c["status"])
            return {"service_ids": [r[0] for r in result]}
        if kind == "incident_triage":
            result = query("SELECT doc->>'$.id' FROM records WHERE doc->>'$.region'=? AND doc->>'$.severity'>=? AND (?=0 OR doc->>'$.open'=1) ORDER BY doc->>'$.id'", c["region"], c["minimum_severity"], int(c["open_only"]))
            return {"incident_ids": [r[0] for r in result]}
        if kind == "latency_argmax":
            result = query("SELECT doc->>'$.id',doc->>'$.p95_ms' FROM records WHERE doc->>'$.region'=? AND (?=0 OR doc->>'$.canary'=0) ORDER BY doc->>'$.p95_ms' DESC,doc->>'$.id' LIMIT 1", c["region"], int(c["exclude_canary"]))
            return {"service_id": result[0][0], "p95_ms": result[0][1]}
        if kind == "owner_join":
            result = query("SELECT i.doc->>'$.id',i.doc->>'$.service_id',s.doc->>'$.owner' FROM records i JOIN records s ON i.doc->>'$.service_id'=s.doc->>'$.id' WHERE i.doc->>'$.type'='incident' AND s.doc->>'$.type'='service' AND i.doc->>'$.id'=?", c["incident_id"])
            return {"incident_id": result[0][0], "service_id": result[0][1], "owner": result[0][2]}
        if kind == "headroom_filter":
            result = query("SELECT doc->>'$.id',(doc->>'$.capacity')-(doc->>'$.used') FROM records WHERE doc->>'$.region'=? AND (doc->>'$.capacity')-(doc->>'$.used')<? ORDER BY doc->>'$.id'", c["region"], c["below_units"])
            return {"headroom": [{"service_id": r[0], "units": r[1]} for r in result]}
        if kind == "latest_deployment":
            result = query("SELECT doc->>'$.id',doc->>'$.minute' FROM records WHERE doc->>'$.service_id'=? AND doc->>'$.environment'=? ORDER BY doc->>'$.minute' DESC,doc->>'$.id' LIMIT 1", c["service_id"], c["environment"])
            return {"deployment_id": result[0][0], "minute": result[0][1]}
        if kind == "alert_count":
            result = query("SELECT count(*) FROM records WHERE doc->>'$.service_id'=? AND (?=0 OR doc->>'$.suppressed'=0)", c["service_id"], int(c["exclude_suppressed"]))
            return {"active_alert_count": result[0][0]}
        if kind == "incident_duration":
            result = query("SELECT doc->>'$.id',?-(doc->>'$.opened_minute') FROM records WHERE doc->>'$.id'=?", c["clock_minute"], c["incident_id"])
            return {"incident_id": result[0][0], "duration_minutes": result[0][1]}
        if kind == "dependency_impact":
            depth = c["max_depth"]
            if type(depth) is not int or not 0 <= depth <= 100:
                raise EvidenceError("Invalid declared dependency horizon")
            result = query("WITH RECURSIVE reach(node,depth) AS (SELECT ?,0 UNION SELECT r.doc->>'$.downstream',reach.depth+1 FROM reach JOIN records r ON r.doc->>'$.upstream'=reach.node WHERE reach.depth<?) SELECT DISTINCT node FROM reach WHERE node<>? ORDER BY node", c["start"], depth, c["start"])
            return {"affected_services": [r[0] for r in result]}
        if kind == "snapshot_select":
            result = query("SELECT doc->>'$.id',doc->>'$.version' FROM records WHERE doc->>'$.service_id'=? AND ?-(doc->>'$.created_minute') BETWEEN 0 AND ? AND doc->>'$.version'>=? ORDER BY doc->>'$.created_minute' DESC,doc->>'$.id' LIMIT 1", c["service_id"], c["clock_minute"], c["max_age_minutes"], c["minimum_version"])
            return {"snapshot_id": result[0][0], "version": result[0][1]}
        raise EvidenceError(f"Unsupported independent task kind: {kind}")
    except (IndexError, KeyError, sqlite3.DatabaseError) as exc:
        raise EvidenceError("Source task cannot establish an independent expected answer") from exc
    finally:
        db.close()
