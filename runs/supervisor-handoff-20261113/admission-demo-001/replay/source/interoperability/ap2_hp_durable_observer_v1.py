"""Owned durable observations of supplied public records and raw HTTP ASGI.

Standard library only. No original module, SDK, credential, provider, service,
socket or process is imported or invoked. Completeness concerns declared local
observation intervals, not task success, native fidelity or authentication.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import threading


SCHEMA = "ap2-hp-durable-observer/1"
KINDS = {"raw_asgi", "frozen_asgi", "public"}
HTTP_SCOPE_FIELDS = (
    "type", "asgi", "http_version", "scheme", "method", "path", "raw_path",
    "query_string", "root_path", "headers", "client", "server",
)
ENDPOINTS = {"http://localhost:8001/a2a/merchant_agent", "http://localhost:8002/a2a/credentials_provider"}


class ObservationError(ValueError):
    pass


def need(value, reason):
    if not value:
        raise ObservationError(reason)


@dataclass(frozen=True)
class Limits:
    record_bytes: int = 1024 * 1024
    log_bytes: int = 64 * 1024 * 1024
    events: int = 10000
    nodes: int = 10000
    depth: int = 40

    def validate(self):
        need(all(type(value) is int and value > 0 for value in self.__dict__.values()), "Positive finite integer limits required")
        need(self.record_bytes <= 4 * 1024 * 1024 and self.log_bytes <= 1024 * 1024 * 1024
             and self.events <= 100000 and self.nodes <= 100000 and self.depth <= 100,
             "Recorder limits exceed reviewed finite bounds")
        return self


def encode_value(value, limits=Limits()):
    """Injective tagged encoding; no object conversion, coercion or __dict__."""
    need(type(limits) is Limits, "Exact limits object required")
    limits.validate()
    active, nodes = set(), 0
    def encode(item, depth):
        nonlocal nodes
        nodes += 1
        need(nodes <= limits.nodes and depth <= limits.depth, "Value node/depth bound exceeded")
        kind = type(item)
        if item is None:
            return {"type": "none"}
        if kind is bool:
            return {"type": "bool", "value": item}
        if kind is int:
            need(item.bit_length() <= 4096, "Integer size bound exceeded")
            return {"type": "int", "value": str(item)}
        if kind is float:
            need(math.isfinite(item), "Nonfinite public value")
            return {"type": "float", "value": item.hex()}
        if kind is str:
            need(len(item) <= limits.record_bytes, "String size bound exceeded")
            return {"type": "str", "value": item}
        if kind is bytes:
            need(len(item) <= limits.record_bytes, "Byte size bound exceeded")
            return {"type": "bytes", "value": base64.b64encode(item).decode("ascii"),
                    "bytes": len(item), "sha256": hashlib.sha256(item).hexdigest()}
        need(kind in (list, tuple, dict), "Unsupported public value type")
        need(id(item) not in active, "Cyclic public value")
        active.add(id(item))
        try:
            if kind is dict:
                return {"type": "dict", "entries": [[encode(key, depth + 1), encode(child, depth + 1)]
                                                     for key, child in item.items()]}
            return {"type": "tuple" if kind is tuple else "list",
                    "items": [encode(child, depth + 1) for child in item]}
        finally:
            active.remove(id(item))
    return encode(value, 0)


def decode_value(value, limits=Limits()):
    """Strict bounded inverse, including dictionary key types and ordering."""
    need(type(limits) is Limits, "Exact limits object required")
    limits.validate()
    nodes = 0
    def decode(item, depth):
        nonlocal nodes
        nodes += 1
        need(nodes <= limits.nodes and depth <= limits.depth and type(item) is dict,
             "Malformed/bounded tagged value required")
        need(all(type(key) is str for key in item), "Tagged fields must have string keys")
        kind = item.get("type")
        need(type(kind) is str, "Tagged kind must be a string")
        if kind == "none":
            need(set(item) == {"type"}, "Malformed none tag")
            return None
        if kind in ("bool", "int", "float", "str"):
            need(set(item) == {"type", "value"}, "Malformed scalar tag")
            raw = item["value"]
            if kind == "bool":
                need(type(raw) is bool, "Malformed bool value")
                return raw
            need(type(raw) is str and len(raw) <= limits.record_bytes, "Malformed scalar text")
            if kind == "str":
                return raw
            if kind == "int":
                need(len(raw) <= 1235, "Integer text bound exceeded")
                number = int(raw)
                need(str(number) == raw and number.bit_length() <= 4096, "Noncanonical integer value")
                return number
            number = float.fromhex(raw)
            need(math.isfinite(number) and number.hex() == raw, "Noncanonical/nonfinite float value")
            return number
        if kind == "bytes":
            need(set(item) == {"type", "value", "bytes", "sha256"}
                 and type(item["value"]) is str and type(item["bytes"]) is int
                 and 0 <= item["bytes"] <= limits.record_bytes
                 and type(item["sha256"]) is str and len(item["sha256"]) == 64
                 and all(char in "0123456789abcdef" for char in item["sha256"]), "Malformed byte tag")
            need(len(item["value"]) <= 4 * ((limits.record_bytes + 2) // 3), "Base64 size bound exceeded")
            raw = base64.b64decode(item["value"], validate=True)
            need(len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
                 and base64.b64encode(raw).decode("ascii") == item["value"], "Byte identity differs")
            return raw
        if kind in ("tuple", "list"):
            need(set(item) == {"type", "items"} and type(item["items"]) is list, "Malformed sequence tag")
            result = [decode(child, depth + 1) for child in item["items"]]
            return tuple(result) if kind == "tuple" else result
        need(kind == "dict" and set(item) == {"type", "entries"} and type(item["entries"]) is list,
             "Malformed dictionary tag")
        result = {}
        for pair in item["entries"]:
            need(type(pair) is list and len(pair) == 2, "Malformed dictionary entry")
            key, child = decode(pair[0], depth + 1), decode(pair[1], depth + 1)
            try:
                need(key not in result, "Duplicate/colliding decoded dictionary key")
                result[key] = child
            except TypeError as error:
                raise ObservationError("Unhashable decoded dictionary key") from error
        return result
    try:
        return decode(value, 0)
    except ObservationError:
        raise
    except (ValueError, TypeError, OverflowError) as error:
        raise ObservationError("Malformed tagged scalar/byte value") from error


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def regular(path, directory=False):
    path = Path(path)
    need(path.is_absolute(), "Absolute owned path required")
    for parent in (path, *path.parents):
        info = parent.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Linked/reparse artifact path refused")
    need(path.is_dir() if directory else path.is_file(), "Regular owned artifact path required")
    return path.resolve()


def file_id(info):
    return info.st_dev, info.st_ino


def full_write(fd, raw):
    offset = 0
    while offset < len(raw):
        count = os.write(fd, raw[offset:])
        need(type(count) is int and 0 < count <= len(raw) - offset, "Zero/invalid durable write count")
        offset += count
    os.fsync(fd)


def validate_row(stream, row):
    """Check callback membership and interval closure, not native task semantics."""
    need(type(row) is dict and type(row.get("sequence")) is int
         and row["sequence"] == stream["next_source_index"], "Source sequence gap/reuse/type mismatch")
    kind = stream["kind"]
    if kind == "public":
        need(set(row) <= {"sequence", "call", "endpoint", "operation", "boundary", "public_value"}
             and {"sequence", "call", "endpoint", "operation", "boundary"} <= set(row), "Malformed public record")
        call, operation, endpoint = row["call"], row["operation"], row["endpoint"]
        need(type(call) is int and call >= 0 and type(operation) is str
             and operation in {"get_agent_card", "send_a2a_message"}
             and type(endpoint) is str and endpoint in ENDPOINTS, "Malformed public call identity")
        boundary = row["boundary"]
        if boundary == "attempt":
            need(call == stream["next_interval"] and call not in stream["active"], "Public call index gap/reuse")
            need(("public_value" in row) == (operation == "send_a2a_message"), "Public request presence differs")
            stream["active"][call] = (operation, endpoint)
            stream["next_interval"] += 1
        else:
            need(boundary in {"returned", "error"} and stream["active"].get(call) == (operation, endpoint),
                 "Unbound public terminal record")
            need(("public_value" in row) == (boundary == "returned"), "Public terminal value presence differs")
            del stream["active"][call]
    else:
        allowed = {"sequence", "exchange", "boundary", "value", "error_type"}
        if kind == "raw_asgi":
            allowed.add("io_id")
        need(set(row) <= allowed and {"sequence", "exchange", "boundary", "value"} <= set(row), "Malformed ASGI record")
        exchange, boundary = row["exchange"], row["boundary"]
        need(type(exchange) is int and exchange >= 0 and type(boundary) is str, "Malformed ASGI exchange")
        if boundary == "scope":
            need(exchange == stream["next_interval"] and exchange not in stream["active"]
                 and type(row["value"]) is dict and row["value"].get("type") == "http"
                 and "io_id" not in row and "error_type" not in row, "Malformed/duplicate HTTP scope")
            stream["active"][exchange] = {"send": {}, "receive": {}, "next_send": 0, "next_receive": 0,
                                          "response_started": False, "response_terminal": False, "disconnected": False}
            stream["next_interval"] += 1
        else:
            need(exchange in stream["active"], "ASGI event has no active exchange")
            current = stream["active"][exchange]
            if boundary in {"application_returned", "application_error"}:
                need("io_id" not in row and not current["send"] and not current["receive"], "Active IO at application terminal")
                if boundary == "application_returned":
                    need(current["response_terminal"] or current["disconnected"], "HTTP response/disconnect terminal not observed")
                    need("error_type" not in row, "Unexpected application return error")
                else:
                    need(type(row.get("error_type")) is str and row["error_type"], "Application error type required")
                del stream["active"][exchange]
            else:
                direction = "send" if boundary.startswith("send_") else "receive" if boundary.startswith("receive_") else None
                need(direction is not None and boundary in {"send_attempt", "send_completed", "send_error",
                                                            "receive_attempt", "receive_returned", "receive_error"}, "Unknown ASGI boundary")
                pending = current[direction]
                if kind == "raw_asgi":
                    io_id = row.get("io_id")
                    need(type(io_id) is int and io_id >= 0, "Raw IO identity required")
                else:
                    io_id = current["next_" + direction] if boundary.endswith("attempt") else next(iter(pending), None)
                if boundary.endswith("attempt"):
                    need(io_id == current["next_" + direction] and io_id not in pending and "error_type" not in row,
                         "IO attempt index gap/reuse")
                    pending[io_id] = True
                    current["next_" + direction] += 1
                else:
                    need(io_id in pending, "IO completion has no attempt")
                    del pending[io_id]
                    need(("error_type" in row) == boundary.endswith("error"), "IO error presence differs")
                    if boundary.endswith("error"):
                        need(type(row["error_type"]) is str and row["error_type"], "IO error type required")
                if boundary in {"receive_returned", "send_attempt", "send_completed"}:
                    event = row["value"]
                    need(type(event) is dict and type(event.get("type")) is str, "Malformed ASGI event dictionary")
                    if kind == "raw_asgi":
                        if "body" in event:
                            need(type(event["body"]) is bytes, "Raw ASGI body must be bytes")
                        if "more_body" in event:
                            need(type(event["more_body"]) is bool, "Raw more_body must be boolean")
                    if boundary == "receive_returned" and event["type"] == "http.disconnect":
                        current["disconnected"] = True
                    if boundary == "send_completed":
                        if event["type"] == "http.response.start":
                            need(not current["response_started"], "Duplicate response start")
                            current["response_started"] = True
                        elif event["type"] == "http.response.body":
                            need(current["response_started"] and not current["response_terminal"], "Unbound/late response body")
                            if event.get("more_body", False) is False:
                                current["response_terminal"] = True
    stream["next_source_index"] += 1


class DurableRecorder:
    """One-process owned append authority, with explicit complete/partial seals."""
    def __init__(self, path, streams, limits):
        self.path, self.limits = path, limits
        self.streams = {name: {"kind": kind, "next_source_index": 0, "next_interval": 0,
                               "active": {}, "witness": None} for name, kind in streams.items()}
        self._lock = threading.RLock()
        self._fds, self._file_ids = {}, {}
        self._directory_id = None
        self.directory_allocated = False
        self._digest, self._committed_bytes = hashlib.sha256(), 0
        self.attempted_events = self.committed_events = 0
        self.missing_indices, self.errors = [], []
        self.capture_complete = True
        self.ready = self.journal_poisoned = self.sealed = self.published = False
        self.publication_attempted = self._writing = False
        self.published_complete = None
        self.last_control_error = None
        self.post_seal_attempts = 0

    @classmethod
    def allocate(cls, path, streams, *, limits=Limits()):
        need(type(limits) is Limits, "Exact finite limits required")
        limits.validate()
        need(type(streams) is dict and 0 < len(streams) <= 64, "One to 64 explicit named streams required")
        need(all(type(name) is str and 0 < len(name) <= 80 and all(char.isascii() and (char.isalnum() or char in "-_") for char in name)
                 and type(kind) is str and kind in KINDS for name, kind in streams.items()), "Canonical stream names/kinds required")
        path = Path(path)
        need(path.is_absolute() and path.name not in {"", ".", ".."} and not path.exists(), "Exclusive new absolute artifact directory required")
        parent = regular(path.parent, True)
        need(path == parent / path.name, "Canonical artifact target required")
        owner = cls(path, streams, limits)
        # mkdir failure allocates no authority; failures after mkdir return it.
        path.mkdir()
        owner.directory_allocated = True
        try:
            owner._directory_id = file_id(path.stat())
            fd = owner._create("events.jsonl")
            os.fsync(fd)
            owner._write_owned("allocation.json", json_bytes({"schema_version": SCHEMA,
                "streams": streams, "limits": limits.__dict__, "scope": "declared local observation intervals",
                "cross_process_writers_supported": False, "authentication_established": False}))
            owner.ready = True
        except BaseException as error:
            owner._error("allocation", error)
        return owner

    def _error(self, stage, error):
        self.capture_complete = False
        if len(self.errors) < 64:
            self.errors.append({"stage": stage, "error_type": type(error).__name__})

    def _check_owner(self, name=None):
        root = regular(self.path, True)
        need(file_id(root.stat()) == self._directory_id, "Owned artifact directory replaced")
        if name is not None:
            path = regular(root / name)
            info = path.stat()
            need(file_id(info) == self._file_ids[name], "Owned artifact file replaced")
            if name == "events.jsonl":
                need(info.st_nlink == 1, "Journal hard-link interference")
            if name in self._fds:
                need(file_id(os.fstat(self._fds[name])) == self._file_ids[name], "Owned descriptor/path differs")

    def _create(self, name):
        self._check_owner()
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        if name == "events.jsonl":
            flags |= os.O_APPEND
        fd = os.open(self.path / name, flags, 0o600)
        self._fds[name] = fd
        self._file_ids[name] = file_id(os.fstat(fd))
        return fd

    def _close_owned(self, name):
        fd = self._fds[name]
        if name in self._file_ids:
            need(file_id(os.fstat(fd)) == self._file_ids[name], "Descriptor identity changed before owned close")
        os.close(fd)
        del self._fds[name]

    def _write_owned(self, name, raw):
        fd = self._create(name)
        full_write(fd, raw)
        self._close_owned(name)

    def sink(self, name):
        need(type(name) is str and name in self.streams, "Declared stream required")
        return StreamSink(self, name)

    def append(self, name, row):
        """False on observation failure; StreamSink raises for frozen wrappers."""
        with self._lock:
            index = self.attempted_events
            self.attempted_events += 1
            writing_started = False
            try:
                need(not self.sealed and not self._writing, "Sealed/reentrant recorder call refused")
                need(self.ready and not self.journal_poisoned and "events.jsonl" in self._fds, "Durable journal unavailable")
                need(name in self.streams and self.streams[name]["witness"] is None, "Unknown/finished source stream")
                need(index < self.limits.events, "Event count bound exceeded")
                tagged = encode_value(row, self.limits)
                snapshot = decode_value(tagged, self.limits)
                candidate = deepcopy(self.streams[name])
                validate_row(candidate, snapshot)
                raw = json_bytes({"schema_version": SCHEMA, "global_index": index, "stream": name,
                                  "source_index": snapshot["sequence"], "payload": tagged})
                need(len(raw) <= self.limits.record_bytes and self._committed_bytes + len(raw) <= self.limits.log_bytes,
                     "Durable byte bound exceeded")
                self._check_owner("events.jsonl")
                self._writing = writing_started = True
                full_write(self._fds["events.jsonl"], raw)
                self._digest.update(raw)
                self._committed_bytes += len(raw)
                self.committed_events += 1
                self.streams[name] = candidate
                return True
            except BaseException as error:
                if writing_started:
                    self.journal_poisoned = True
                if self.sealed:
                    self.post_seal_attempts += 1
                if len(self.missing_indices) < self.limits.events:
                    self.missing_indices.append(index)
                self._error("append", error)
                return False
            finally:
                if writing_started:
                    self._writing = False

    def finish_stream(self, name, witness):
        """Explicit final source witness, computed after original work settles."""
        with self._lock:
            try:
                need(not self.sealed and name in self.streams and self.streams[name]["witness"] is None, "Fresh source finish required")
                need(type(witness) is dict and set(witness) == {"source_complete", "active_operations", "attempted_records"},
                     "Exact final source witness required")
                need(type(witness["source_complete"]) is bool
                     and all(type(witness[key]) is int and witness[key] >= 0 for key in ("active_operations", "attempted_records")),
                     "Typed final source witness required")
                need(witness["active_operations"] == 0, "Active source retains finish authority")
                stream = self.streams[name]
                if not witness["source_complete"] or witness["attempted_records"] != stream["next_source_index"] or stream["active"]:
                    self._error("source_witness", ObservationError("Source incomplete, gapped or has unmatched interval"))
                stream["witness"] = dict(witness)
                return True
            except BaseException as error:
                self.last_control_error = type(error).__name__
                return False

    def _journal_identity(self):
        self._check_owner("events.jsonl")
        result, size = hashlib.sha256(), 0
        with (self.path / "events.jsonl").open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                need(size <= self.limits.log_bytes + self.limits.record_bytes, "Retained journal exceeds bound")
                result.update(chunk)
        return {"bytes": size, "sha256": result.hexdigest()}

    def publish(self, *, allow_incomplete=False):
        """Exclusive durable pending file plus no-overwrite hard-link publication.

        Complete publication refuses gaps/unmatched intervals. Partial seals
        require an explicit flag and settled final witnesses from every source.
        """
        with self._lock:
            try:
                need(type(allow_incomplete) is bool and not self.publication_attempted and not self.sealed,
                     "Publication is once-only")
                need(all(stream["witness"] is not None for stream in self.streams.values()), "Every source must finish before publication")
                journal = self._journal_identity()
                verified = journal == {"bytes": self._committed_bytes, "sha256": self._digest.hexdigest()}
                if not verified:
                    self._error("journal_identity", ObservationError("Retained journal differs from acknowledged prefix"))
                complete = self.ready and self.capture_complete and not self.journal_poisoned and verified
                need(complete or allow_incomplete, "Incomplete/gapped capture cannot publish a complete terminal")
                self.publication_attempted = self.sealed = True
                if "events.jsonl" in self._fds:
                    os.fsync(self._fds["events.jsonl"])
                    self._close_owned("events.jsonl")
                manifest = {"schema_version": SCHEMA, "capture_complete_for_declared_intervals": complete,
                    "attempted_events": self.attempted_events, "durably_committed_events": self.committed_events,
                    "missing_global_indices": list(self.missing_indices), "journal": journal,
                    "committed_prefix_identity_verified": verified, "journal_poisoned": self.journal_poisoned,
                    "streams": {name: {"kind": stream["kind"], "next_source_index": stream["next_source_index"],
                                       "next_interval": stream["next_interval"], "active_intervals": encode_value(stream["active"], self.limits),
                                       "final_witness": deepcopy(stream["witness"])} for name, stream in self.streams.items()},
                    "observation_errors": list(self.errors),
                    "publication": "fsynced owned pending file then exclusive same-directory hard link",
                    "directory_crash_durability_verified": False, "authentication_established": False,
                    "native_qualification_established": False, "scope": "declared closed local source intervals only"}
                manifest_raw = json_bytes(manifest)
                need(len(manifest_raw) <= 4 * 1024 * 1024, "Terminal publication size bound exceeded")
                self._write_owned("terminal.pending.json", manifest_raw)
                self._check_owner("terminal.pending.json")
                need(self.capture_complete or not complete, "Observation changed during complete publication")
                os.link(self.path / "terminal.pending.json", self.path / "terminal.json")
                need(file_id((self.path / "terminal.json").stat()) == self._file_ids["terminal.pending.json"], "Published terminal identity differs")
                self.published, self.published_complete = True, complete
                return True
            except BaseException as error:
                self.last_control_error = type(error).__name__
                if self.publication_attempted:
                    self._error("publication", error)
                return False

    def close(self):
        """Close only retained own descriptors; failures retain their authority."""
        with self._lock:
            if not self.sealed:
                self._error("close_before_seal", ObservationError("Recording authority closed before terminal seal"))
            complete = True
            for name in tuple(self._fds):
                try:
                    self._close_owned(name)
                except BaseException as error:
                    self._error("close", error)
                    complete = False
            return complete

    def report(self):
        with self._lock:
            return {"schema_version": SCHEMA, "ready": self.ready, "observation_complete_current": self.capture_complete,
                    "attempted_events": self.attempted_events, "durably_committed_events": self.committed_events,
                    "missing_global_indices": list(self.missing_indices), "journal_poisoned": self.journal_poisoned,
                    "sealed": self.sealed, "published": self.published, "published_complete": self.published_complete,
                    "post_seal_attempts": self.post_seal_attempts, "open_file_authority_retained": bool(self._fds),
                    "owned_directory_allocated": self.directory_allocated,
                    "observation_errors": list(self.errors), "last_control_error": self.last_control_error,
                    "cross_process_writers_supported": False, "order": "same-process sink lock acquisition and fsynced append order",
                    "directory_crash_durability_verified": False, "native_qualification_established": False,
                    "authentication_established": False}


class StreamSink:
    """Failure propagation consumed by frozen observer fail-open handling."""
    def __init__(self, recorder, name):
        need(type(recorder) is DurableRecorder and type(name) is str and name in recorder.streams,
             "Exact owned recorder and declared stream required")
        self.recorder, self.name = recorder, name

    def __call__(self, row):
        if not self.recorder.append(self.name, row):
            raise ObservationError("Durable observation incomplete")

    def finish(self, witness):
        return self.recorder.finish_stream(self.name, witness)


class RawAsgiCapture:
    """Raw HTTP observations tagged once by the recorder, no rewritten IO.

    Lifespan/non-HTTP calls are forwarded unchanged and counted for final
    quiescence, but are outside the declared durable HTTP record scope.
    """
    def __init__(self, app, sink):
        need(type(sink) is StreamSink and sink.recorder.streams[sink.name]["kind"] == "raw_asgi",
             "Owned raw-ASGI stream sink required")
        self.app, self.sink = app, sink
        self._lock = threading.RLock()
        self._next_source_index = self._next_exchange = 0
        self.active_operations = 0
        self.active_io_operations = 0
        self.capture_complete = True
        self.errors = []

    def _record(self, exchange, boundary, value=None, *, error=None, io_id=None):
        with self._lock:
            sequence = self._next_source_index
            self._next_source_index += 1
            try:
                row = {"sequence": sequence, "exchange": exchange, "boundary": boundary, "value": value}
                if error is not None:
                    row["error_type"] = type(error).__name__
                if io_id is not None:
                    row["io_id"] = io_id
                self.sink(row)
            except BaseException as caught:
                self.capture_complete = False
                if len(self.errors) < 64:
                    self.errors.append({"sequence": sequence, "boundary": boundary, "error_type": type(caught).__name__})

    async def __call__(self, scope, receive, send):
        with self._lock:
            self.active_operations += 1
        try:
            supported = type(scope) is dict and all(type(key) is str for key in scope)
            scope_type = scope.get("type") if supported else None
            supported = supported and type(scope_type) is str and scope_type in {"http", "lifespan", "websocket"}
            if not supported or scope_type != "http":
                if not supported:
                    with self._lock:
                        self.capture_complete = False
                        if len(self.errors) < 64:
                            self.errors.append({"boundary": "scope", "error_type": "MalformedScope"})
                return await self.app(scope, receive, send)
            with self._lock:
                exchange = self._next_exchange
                self._next_exchange += 1
                self._record(exchange, "scope", {key: scope[key] for key in HTTP_SCOPE_FIELDS if key in scope})
            next_io = {"send": 0, "receive": 0}
            def begin_io(direction, value=None):
                with self._lock:
                    index = next_io[direction]
                    next_io[direction] += 1
                    self.active_io_operations += 1
                    self._record(exchange, direction + "_attempt", value, io_id=index)
                    return index
            async def observed_receive():
                io_id = begin_io("receive")
                try:
                    try:
                        event = await receive()
                    except BaseException as error:
                        self._record(exchange, "receive_error", error=error, io_id=io_id)
                        raise
                    self._record(exchange, "receive_returned", event, io_id=io_id)
                    return event
                finally:
                    with self._lock:
                        self.active_io_operations -= 1
            async def observed_send(event):
                io_id = begin_io("send", event)
                try:
                    try:
                        returned = await send(event)
                    except BaseException as error:
                        self._record(exchange, "send_error", error=error, io_id=io_id)
                        raise
                    self._record(exchange, "send_completed", event, io_id=io_id)
                    return returned
                finally:
                    with self._lock:
                        self.active_io_operations -= 1
            try:
                returned = await self.app(scope, observed_receive, observed_send)
            except BaseException as error:
                self._record(exchange, "application_error", error=error)
                raise
            self._record(exchange, "application_returned")
            return returned
        finally:
            with self._lock:
                self.active_operations -= 1

    def witness(self):
        with self._lock:
            return {"source_complete": self.capture_complete,
                    "active_operations": self.active_operations + self.active_io_operations,
                    "attempted_records": self._next_source_index}

    def finish(self):
        with self._lock:
            return self.sink.finish(self.witness())

    def report(self):
        with self._lock:
            return {"schema_version": "ap2-hp-raw-asgi-capture/1", **self.witness(),
                    "active_application_calls": self.active_operations, "active_io_operations": self.active_io_operations,
                    "observation_errors": list(self.errors), "scope": "public HTTP ASGI boundary only",
                    "raw_values_tagged_once_by_recorder": True, "native_hook_placement_verified": False,
                    "transport_peer_ownership_verified": False, "native_qualification_established": False}
