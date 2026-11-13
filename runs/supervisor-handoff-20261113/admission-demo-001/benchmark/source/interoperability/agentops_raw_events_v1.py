"""Export archived ADK SQLite evidence without importing or running AgentOps.

Database rows are evaluator evidence. Their physical order does not establish
causal order, a complete event stream, public visibility, or task qualification.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import stat


TABLES = {
    "adk_internal_metadata": ("key", "value"),
    "sessions": ("app_name", "user_id", "id", "state", "create_time", "update_time"),
    "app_states": ("app_name", "state", "update_time"),
    "user_states": ("app_name", "user_id", "state", "update_time"),
    "events": ("id", "app_name", "user_id", "session_id", "invocation_id", "timestamp", "event_data"),
    "tasks": ("id", "context_id", "kind", "owner", "last_updated", "status", "artifacts", "history", "protocol_version", "metadata"),
}
JSON_COLUMNS = {"sessions": ("state",), "app_states": ("state",), "user_states": ("state",),
                "events": ("event_data",), "tasks": ("status", "artifacts", "history", "metadata")}
MAX_DATABASE_BYTES = 64 * 1024 * 1024
PRIMARY_KEYS = {"adk_internal_metadata": ("key",), "sessions": ("app_name", "user_id", "id"),
                "app_states": ("app_name",), "user_states": ("app_name", "user_id"),
                "events": ("id", "app_name", "user_id", "session_id"), "tasks": ("id",)}
INDEXES = {
    "idx_events_app_user_session_ts_id": ("events", (("app_name", 0), ("user_id", 0), ("session_id", 0), ("timestamp", 1), ("id", 1))),
    "idx_tasks_owner_last_updated": ("tasks", (("owner", 0), ("last_updated", 0))),
    "ix_tasks_id": ("tasks", (("id", 0),)),
}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite JSON constant")


def _encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _json(value):
    _need(type(value) is str, "JSON column must be text")
    parsed = json.loads(value, object_pairs_hook=_unique, parse_constant=_constant)
    _encode(parsed)  # Reject overflowed numbers, including 1e999.
    return parsed


def _digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _regular(path, *, directory=False):
    path = Path(path).absolute()
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        _need(not stat.S_ISLNK(info.st_mode)
              and not (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)),
              "Input paths must not use links or reparse points")
    _need(path.is_dir() if directory else path.is_file(), "Expected a regular input path")
    return path


def _sidecars(database):
    return [str(database) + suffix for suffix in ("-wal", "-shm", "-journal")
            if Path(str(database) + suffix).exists() or Path(str(database) + suffix).is_symlink()]


def _read_snapshot(database):
    _regular(database)
    _need(not _sidecars(database), "Archived database must have no WAL, SHM or journal sidecars")
    _need(database.stat().st_size <= MAX_DATABASE_BYTES, "Database exceeds exporter size limit")
    raw = database.read_bytes()
    _need(raw.startswith(b"SQLite format 3\0"), "Input is not a SQLite database")
    return raw


def _text(value, field):
    _need(type(value) is str and bool(value.strip()), "Missing text identity: " + field)


def _project_event(row, event):
    _need(type(event) is dict, "Event JSON must be an object")
    for field in ("id", "invocation_id"):
        _need(event.get(field) == row[field], "Event JSON/row identity mismatch: " + field)
    for field in ("app_name", "user_id", "session_id"):
        if field in event:
            _need(event[field] == row[field], "Event JSON/row identity mismatch: " + field)
    _text(event.get("author"), "event author")
    timestamp = event.get("timestamp")
    try:
        valid_timestamp = type(timestamp) in (int, float) and math.isfinite(timestamp) and timestamp >= 0
    except OverflowError:
        valid_timestamp = False
    _need(valid_timestamp,
          "Event timestamp must be finite and nonnegative")
    content = event.get("content")
    if content is None:
        return []
    _need(type(content) is dict, "Event content must be an object or null")
    parts = content.get("parts", [])
    _need(type(parts) is list, "Event parts must be a list")
    observations = []
    for index, part in enumerate(parts):
        _need(type(part) is dict, "Event part must be an object")
        _need(not any(part.get(alias) is not None for alias in ("functionCall", "functionResponse")),
              "Unsupported camelCase function part in declared snake_case SDK event format")
        active = [kind for kind in ("function_call", "function_response") if part.get(kind) is not None]
        _need(len(active) <= 1, "Ambiguous function call/response part")
        for kind in active:
            value = part[kind]
            _need(type(value) is dict, "Function part must be an object")
            _text(value.get("name"), "function name")
            identity = value.get("id")
            _need(identity is None or type(identity) is str, "Function ID must be text or null")
            body_field = "args" if kind == "function_call" else "response"
            body = value.get(body_field)
            _need(body is None or type(body) is dict, "Function arguments/response must be an object or null")
            observations.append({"event_rowid": row["sqlite_rowid"], "event_id": row["id"],
                "app_name": row["app_name"], "user_id": row["user_id"], "session_id": row["session_id"],
                "invocation_id": row["invocation_id"], "author": event["author"],
                "event_timestamp": timestamp, "database_timestamp": row["timestamp"],
                "part_index": index, "kind": kind, "function_id": identity,
                "function_identity_complete": type(identity) is str and bool(identity),
                "function": value})
    return observations


def _tables(database):
    result, decoded, observations = {}, {}, []
    uri = database.as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        _need(connection.execute("PRAGMA quick_check").fetchall() == [("ok",)], "SQLite integrity check failed")
        _need(not connection.execute("PRAGMA foreign_key_check").fetchall(), "SQLite foreign-key check failed")
        schema = connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
        tables = [item for item in schema if item[1] == "table"]
        indexes = [item for item in schema if item[1] == "index"]
        _need({item[0] for item in tables} == set(TABLES) and {item[0] for item in indexes} == set(INDEXES)
              and len(tables) + len(indexes) == len(schema), "Unsupported or incomplete SQLite schema")
        _need(all(type(sql) is str and sql.lstrip().upper().startswith("CREATE TABLE")
                  for _, _, _, sql in tables), "Only ordinary SDK tables are supported")
        for name, _, table, sql in indexes:
            target, columns = INDEXES[name]
            actual = tuple((item[2], item[3]) for item in connection.execute(f'PRAGMA index_xinfo("{name}")') if item[5] == 1)
            _need(table == target and actual == columns and type(sql) is str,
                  "Unsupported SDK index layout: " + name)
        sessions = set()
        for table, columns in TABLES.items():
            info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            actual = tuple(item[1] for item in info)
            _need(actual == columns, "Unsupported table columns: " + table)
            primary_key = tuple(item[1] for item in sorted(info, key=lambda item: item[5]) if item[5])
            _need(primary_key == PRIMARY_KEYS[table], "Unsupported SDK primary key: " + table)
            values = connection.execute(f'SELECT rowid,{",".join(chr(34)+c+chr(34) for c in columns)} FROM "{table}" ORDER BY rowid').fetchall()
            rows, parsed_rows = [], []
            for values_row in values:
                row = {"sqlite_rowid": values_row[0], **dict(zip(columns, values_row[1:], strict=True))}
                _need(all(value is None or type(value) in (str, int, float) for value in row.values()),
                      "Unsupported SQLite cell type")
                for field in ("app_name", "user_id", "session_id", "id", "invocation_id"):
                    if field in row:
                        _text(row[field], field)
                parsed = dict(row)
                for field in JSON_COLUMNS.get(table, ()):
                    parsed[field] = None if row[field] is None else _json(row[field])
                if table in ("sessions", "app_states", "user_states"):
                    _need(type(parsed["state"]) is dict, "SDK state must be an object")
                if table == "sessions":
                    sessions.add((row["app_name"], row["user_id"], row["id"]))
                if table == "events":
                    _need((row["app_name"], row["user_id"], row["session_id"]) in sessions,
                          "Event references an absent session")
                    observations.extend(_project_event(row, parsed["event_data"]))
                if table == "tasks":
                    _text(row["context_id"], "task context")
                    _need(type(parsed["status"]) is dict, "Task status must be an object")
                rows.append(row)
                parsed_rows.append(parsed)
            result[table], decoded[table] = rows, parsed_rows
    return schema, result, decoded, observations


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def export_database(database: Path, output: Path) -> dict:
    database, output = Path(database).absolute(), Path(output).absolute()
    _need(not output.exists() and not output.is_symlink(), "Refusing an existing output")
    _need(not output.resolve().is_relative_to(database.parent.resolve()), "Output must be outside the input directory")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema_version": "agentops-raw-event-export/1", "status": "failed",
               "visibility": "evaluator-private archived SQLite evidence",
               "application_requests": 0, "model_calls": 0, "graded_task_outcomes": 0,
               "causal_order_proven": False, "complete_event_stream_proven": False,
               "source_unchanged": None, "captured_files_unchanged": None}
    original = None
    captured = {}
    try:
        source = Path(__file__).read_bytes()
        plan = {"schema_version": "agentops-raw-event-export-plan/1", "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "database": str(database), "exporter_sha256": hashlib.sha256(source).hexdigest(),
                "ordering_basis": "SQLite rowid physical order; not a causal stream-order claim",
                "selected_tables": list(TABLES), "sqlite_mode": "read-only immutable captured database",
                "input_requires_absent_sidecars": True}
        captured["plan.json"] = _encode(plan)
        captured["exporter.py"] = source
        for name, raw in captured.items():
            _write(output / name, raw)
        original = _read_snapshot(database)
        captured["input/runtime.db"] = original
        _write(output / "input/runtime.db", original)
        schema, raw_tables, parsed_tables, observations = _tables(output / "input/runtime.db")
        events = parsed_tables["events"]
        timestamps = [row["event_data"]["timestamp"] for row in events]
        groups = {}
        for row in events:
            groups.setdefault(row["event_data"]["timestamp"], []).append(row["id"])
        ordering = {"basis": plan["ordering_basis"], "causal_order_proven": False,
            "complete_event_stream_proven": False,
            "equal_timestamp_groups": [ids for ids in groups.values() if len(ids) > 1],
            "timestamp_reversals_in_physical_order": [index for index in range(1, len(timestamps)) if timestamps[index] < timestamps[index-1]],
            "same_event_multiple_call_batches": [row["id"] for row in events
                if sum(item["event_rowid"] == row["sqlite_rowid"] and item["kind"] == "function_call" for item in observations) > 1]}
        captured.update({"schema.json": _encode(schema), "raw-tables.json": _encode(raw_tables),
                         "decoded-tables.json": _encode(parsed_tables), "function-observations.json": _encode(observations),
                         "ordering.json": _encode(ordering)})
        for name in ("schema.json", "raw-tables.json", "decoded-tables.json", "function-observations.json", "ordering.json"):
            _write(output / name, captured[name])
        receipt.update(status="passed", database=_digest(original), events=len(events),
                       function_calls=sum(x["kind"] == "function_call" for x in observations),
                       function_responses=sum(x["kind"] == "function_response" for x in observations),
                       table_rows={key: len(rows) for key, rows in raw_tables.items()},
                       interpretation="Export/preservation only; no case association, public-observation, native-execution or admission-grade claim.")
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if original is not None:
                after = _read_snapshot(database)
                receipt["source_after"] = _digest(after)
                receipt["source_unchanged"] = after == original
                _need(receipt["source_unchanged"], "Input database changed during export")
            receipt["captured_files_unchanged"] = all((output / name).read_bytes() == raw for name, raw in captured.items())
            _need(receipt["captured_files_unchanged"], "Captured evidence changed during export")
        except (OSError, ValueError) as error:
            receipt.update(status="failed", preservation_error=f"{type(error).__name__}: {error}")
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["files"] = [{"path": path.relative_to(output).as_posix(), **_digest(path.read_bytes())}
                            for path in sorted(output.rglob("*")) if path.is_file()]
        _write(output / "result.json", _encode(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = export_database(args.database, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"status": result["status"], "events": result.get("events"),
                      "function_calls": result.get("function_calls"), "function_responses": result.get("function_responses"),
                      "error": result.get("error"), "receipt": str(args.output / "result.json")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
