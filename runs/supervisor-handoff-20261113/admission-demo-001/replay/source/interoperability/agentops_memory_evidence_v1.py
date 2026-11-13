"""Read-only source-schema memory snapshots and closed-store export.

No AgentOps/SDK import, preparation, migration, PII processing or model call.
An absent lazy store is an observation, not continuous mutation-absence proof.
Closed process attribution belongs to the outer native runner.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import time


SCHEMA = "agentops-memory-snapshot/1"
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 10000
TABLE_SQL = "CREATE TABLE incident_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, user_id TEXT NOT NULL, incident_id TEXT NOT NULL, note TEXT NOT NULL)"
INDEX_SQL = "CREATE INDEX idx_notes_user_incident ON incident_notes (user_id, incident_id)"
COLUMNS = [(0, "id", "INTEGER", 0, None, 1), (1, "ts", "TEXT", 1, None, 0),
           (2, "user_id", "TEXT", 1, None, 0), (3, "incident_id", "TEXT", 1, None, 0), (4, "note", "TEXT", 1, None, 0)]


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _regular(path, directory=False):
    path = Path(path).absolute()
    for candidate in (*reversed(path.parents), path):
        info = candidate.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "linked/reparse memory path is unsupported")
    _need(path.is_dir() if directory else path.is_file(), "expected a regular memory path")
    return path


def _digest(path):
    _regular(path)
    size, hasher = 0, hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            _need(size <= MAX_BYTES, "memory database byte bound exceeded")
            hasher.update(chunk)
    return {"bytes": size, "sha256": hasher.hexdigest()}


def _sidecars(path):
    return [suffix for suffix in ("-wal", "-shm", "-journal")
            if Path(str(path) + suffix).exists() or Path(str(path) + suffix).is_symlink()]


def _encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    _regular(path.parent, True)
    with path.open("xb") as stream:
        stream.write(value if type(value) is bytes else _encoded(value))


def _sql(value):
    _need(type(value) is str, "missing original memory SQL")
    # Only source-declared whitespace/case variation; no expression rewriting.
    return "".join(value.split()).lower().removesuffix(";")


def _read(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        _need(connection.execute("PRAGMA quick_check").fetchall() == [("ok",)], "memory integrity check failed")
        _need(connection.execute("PRAGMA user_version").fetchone()[0] == 0, "unexpected memory user_version")
        rows = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").fetchall()
        objects = {(kind, name): (table, sql) for kind, name, table, sql in rows}
        _need(set(objects) == {("table", "incident_notes"), ("table", "sqlite_sequence"), ("index", "idx_notes_user_incident")},
              "unexpected source memory schema objects")
        _need(objects[("table", "incident_notes")][0] == "incident_notes"
              and _sql(objects[("table", "incident_notes")][1]) == _sql(TABLE_SQL), "memory table differs from original source")
        _need(objects[("table", "sqlite_sequence")] == ("sqlite_sequence", "CREATE TABLE sqlite_sequence(name,seq)"), "unsupported SQLite sequence schema")
        _need(objects[("index", "idx_notes_user_incident")][0] == "incident_notes"
              and _sql(objects[("index", "idx_notes_user_incident")][1]) == _sql(INDEX_SQL), "memory index differs from original source")
        columns = connection.execute('PRAGMA table_info("incident_notes")').fetchall()
        _need(columns == COLUMNS, "memory columns/defaults differ")
        _need(connection.execute('PRAGMA index_info("idx_notes_user_incident")').fetchall() == [(0, 2, "user_id"), (1, 3, "incident_id")],
              "memory index keys differ")
        note_rows = connection.execute("SELECT id,ts,user_id,incident_id,note FROM incident_notes ORDER BY id LIMIT ?", (MAX_ROWS + 1,)).fetchall()
        _need(len(note_rows) <= MAX_ROWS, "memory row bound exceeded")
        names = [item[1] for item in COLUMNS]
        notes = []
        for row in note_rows:
            _need(type(row[0]) is int and row[0] > 0 and all(type(value) is str for value in row[1:]), "invalid source memory row types")
            notes.append(dict(zip(names, row)))
        sequence = connection.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall()
        _need(len(sequence) <= 1 and all(row[0] == "incident_notes" and type(row[1]) is int and row[1] >= 0 for row in sequence),
              "invalid source memory sequence")
        _need(not notes or sequence and sequence[0][1] >= notes[-1]["id"], "memory sequence is behind row identities")
        return {"schema": [{"type": kind, "name": name, "table_name": table, "sql": sql} for kind, name, table, sql in rows],
                "columns": [list(row) for row in columns], "notes": notes,
                "sqlite_sequence": [{"name": name, "seq": seq} for name, seq in sequence],
                "user_version": 0, "transaction_snapshot": True}


def snapshot_memory(database, *, observation_mode="archived"):
    """Capture one read transaction, conservatively refusing journal sidecars.

    In live mode concurrent file changes are recorded rather than interpreted
    as reader mutations. Archived mode requires exact source preservation.
    Neither mode itself proves that a live writer has stopped.
    """
    _need(observation_mode in {"archived", "live"}, "unsupported memory observation mode")
    path = Path(database).absolute()
    report = {"schema_version": SCHEMA, "status": "unsupported", "observation_mode": observation_mode,
              "database_path": str(path), "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "started_monotonic_ns": time.monotonic_ns(), "errors": [], "source_closed_proven": False,
              "continuous_mutation_absence_proven": False, "cross_store_atomic_snapshot": False,
              "application_calls": 0, "database_preparation_or_migration": False, "sqlite_connection_mode": "read-only query_only transaction"}
    before = None
    try:
        _regular(path.parent, True)
        _need(not path.is_symlink(), "linked memory database is unsupported")
        _need(not _sidecars(path), "memory snapshot requires absent WAL/SHM/journal sidecars")
        if not path.exists():
            report.update(status="absent", exists_observed=False, notes=[], sqlite_sequence=[])
            return report
        _regular(path)
        before = _digest(path)
        _need(before["bytes"] >= 100, "invalid memory database header")
        with path.open("rb") as stream:
            header = stream.read(100)
        _need(len(header) == 100 and header[:16] == b"SQLite format 3\0", "invalid memory database header")
        # Opening a WAL-mode file can create SHM/WAL even via mode=ro. The
        # original note store uses rollback mode; reject version2 before SQLite
        # touches this path, rather than using immutable on a live writer.
        _need(header[18] == header[19] == 1, "unsupported non-rollback memory database header")
        report.update(_read(path))
        after = _digest(path)
        _need(not _sidecars(path), "memory sidecar appeared during observation")
        unchanged = before == after
        _need(observation_mode == "live" or unchanged, "archived memory source changed during observation")
        report.update(status="recorded", exists_observed=True, source_before=before, source_after=after,
                      physical_file_unchanged_during_observation=unchanged, row_count=len(report["notes"]))
    except (OSError, ValueError, sqlite3.Error) as error:
        report["errors"].append({"type": type(error).__name__, "reason": str(error)})
    finally:
        report.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), finished_monotonic_ns=time.monotonic_ns())
    return report


def export_memory(database, output):
    """Retain one closed-store snapshot or absent-store observation exclusively."""
    database, output = Path(database).absolute(), Path(output).absolute()
    _need(not output.exists() and not output.is_symlink(), "memory evidence output already consumed")
    _need(output == output.resolve(), "memory evidence output must be canonical")
    _need(not output.resolve().is_relative_to(database.parent.resolve()), "memory evidence output overlaps input state")
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    _regular(ancestor, True)
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "agentops-memory-export/1", "status": "failed", "source_closed_proven": False,
              "snapshot": None, "graded_source_cases": 0, "application_calls": 0, "errors": []}
    protected = {}
    before = None
    try:
        protected["exporter.py"] = Path(__file__).read_bytes()
        protected["plan.json"] = _encoded({"schema_version": "agentops-memory-export-plan/1", "database": str(database),
                                          "sqlite_version": sqlite3.sqlite_version, "observation_mode": "archived",
                                          "source_closed_proven": False, "exporter": {"bytes": len(protected["exporter.py"]),
                                          "sha256": hashlib.sha256(protected["exporter.py"]).hexdigest()}})
        for name, raw in protected.items():
            _write(output / name, raw)
        snapshot = snapshot_memory(database)
        protected["snapshot.json"] = _encoded(snapshot)
        _write(output / "snapshot.json", protected["snapshot.json"])
        report["snapshot"] = snapshot
        _need(snapshot["status"] in {"recorded", "absent"}, "memory snapshot unsupported")
        if snapshot["status"] == "recorded":
            before = _digest(database)
            _need(before == snapshot["source_after"], "memory input changed after snapshot")
            raw = _regular(database).read_bytes()
            _need({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == before, "memory copy identity changed")
            protected["input/memory.db"] = raw
            _write(output / "input/memory.db", raw)
            copied = snapshot_memory(output / "input/memory.db")
            _need(copied["status"] == "recorded" and all(copied[key] == snapshot[key] for key in ("schema", "columns", "notes", "sqlite_sequence", "user_version")),
                  "copied logical memory is unsupported or differs")
            _need(_digest(database) == before and not _sidecars(database), "memory input changed during export")
        else:
            _need(not database.exists() and not database.is_symlink(), "absent memory appeared during export")
        _need(Path(__file__).read_bytes() == protected["exporter.py"], "memory exporter source changed")
        report.update(status="recorded", source_observation_preserved=True)
    except (OSError, ValueError, KeyError) as error:
        report["errors"].append({"type": type(error).__name__, "reason": str(error)})
    finally:
        found = {}
        for path in output.rglob("*"):
            _regular(path, path.is_dir())
            if path.is_file():
                _need(path.stat().st_size <= MAX_BYTES, "memory evidence file bound exceeded")
                found[path.relative_to(output).as_posix()] = path.read_bytes()
        report["captured_files_unchanged"] = found == protected
        if not report["captured_files_unchanged"]:
            report["status"] = "failed"
        report["files"] = [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in sorted(found.items())]
        _write(output / "result.json", report)
    return report
