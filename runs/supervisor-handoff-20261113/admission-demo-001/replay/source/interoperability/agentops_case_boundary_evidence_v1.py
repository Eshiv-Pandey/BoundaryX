"""Read-only client/server and sampled business/memory boundary binding.

No application, SDK, model or credential is imported. A successful captured
readiness response supplies a distinct post-startup baseline before source
requests. Archived stores are read behind rollback-header/sidecar guards.
Artifact agreement is not source authentication or continuous absence proof.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path, PurePosixPath
import re
import types

from . import upstream_agentops_client_v1 as client
from .agentops_memory_evidence_v1 import snapshot_memory
from .agentops_runtime_stream_evidence_v1 import _regular, _same


ROOT = Path(__file__).resolve().parents[2]
WIRE_FILES = {"exchange.json", "request.body.bin", "response.body.bin", "before.snapshot.json", "after.snapshot.json",
              "before.memory.snapshot.json", "after.memory.snapshot.json"}
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _read(path):
    path = _regular(path)
    _need(path.stat().st_size <= MAX_FILE, "boundary file byte limit")
    raw = path.read_bytes()
    _need(len(raw) <= MAX_FILE, "boundary file grew beyond byte limit")
    return raw


def _inventory(root):
    root = _regular(root, True)
    files, directories, total = {}, set(), 0
    for path in sorted(root.rglob("*")):
        _regular(path, path.is_dir())
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.add(name)
        else:
            _need(len(files) < 8192 and path.stat().st_size <= MAX_FILE, "boundary archive file/count limit")
            raw = _read(path)
            _need(len(raw) <= MAX_FILE, "boundary archive file grew beyond limit")
            total += len(raw)
            _need(total <= MAX_TOTAL, "boundary archive aggregate byte limit")
            files[name] = raw
    return files, directories


def _object(raw):
    value = client.strict_json(raw)
    _need(type(value) is dict, "boundary JSON must be an object")
    return value


def _manifest(files, report):
    declared = report.get("files")
    _need(type(declared) is list and all(type(row) is dict and set(row) == {"path", "bytes", "sha256"} for row in declared),
          "invalid client manifest")
    names = [row["path"] for row in declared]
    _need(all(type(name) is str and name and ":" not in name and "\\" not in name
              and not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
              and PurePosixPath(name).as_posix() == name for name in names), "unsafe client manifest path")
    _need(len(names) == len(set(names)) and set(files) == set(names) | {"result.json"}, "client manifest membership differs")
    for row in declared:
        _need(_same({key: row[key] for key in ("bytes", "sha256")}, _digest(files[row["path"]])), "client manifest bytes differ")


def _closed_business(database, retained):
    # Frozen reader is stdlib only; its command entrypoints are never invoked.
    before = _inventory(retained)
    raw = before[0].get("incidents.db")
    _need(raw is not None and len(raw) >= 100 and raw[:16] == b"SQLite format 3\0" and raw[18] == raw[19] == 1,
          "retained business store must have a rollback-mode SQLite header")
    _need(not any(name in before[0] for name in ("incidents.db-wal", "incidents.db-shm", "incidents.db-journal")),
          "retained business sidecars are unsupported")
    source = _regular(ROOT / "scripts/agentops_native_probe_v2.py")
    source_before = source.read_bytes()
    module = types.ModuleType("boundary_frozen_business_reader")
    module.__file__ = str(source)
    # Execute exactly the hashed bytes; never consult or create cached bytecode.
    exec(compile(source_before, str(source), "exec"), module.__dict__)
    value = module.database_snapshot(database, retained, "retained")
    _need(_inventory(retained) == before and source.read_bytes() == source_before, "retained business reader or store changed")
    return value, _digest(source_before)


def _boundary(files, prefix, name):
    business = _object(files[prefix + name + ".snapshot.json"])
    _need(type(business.get("database")) is dict, "missing business boundary snapshot")
    memory = _object(files[prefix + name + ".memory.snapshot.json"])
    _need(memory.get("schema_version") == "agentops-memory-snapshot/1" and memory.get("observation_mode") == "live"
          and memory.get("status") in {"recorded", "absent"}, "missing or unsupported memory boundary")
    return {"business": business["database"], "memory": memory,
            "business_observed_at_utc": business.get("observed_at_utc"),
            "business_monotonic_ns": business.get("monotonic_ns"), "wire_boundary": prefix + name}


def _logical_memory(value):
    keys = ("status", "exists_observed", "schema", "columns", "notes", "sqlite_sequence", "user_version", "row_count")
    return {key: value[key] for key in keys if key in value}


def collect_case_boundaries(instance_directory, application_case):
    """Load one v2 retained source instance without creating any evidence files.

    The caller supplies an exact application-only case projection. This API
    validates its equality to retained client input and binds all client entity
    bytes to exactly one server exchange. Invalid/incomplete evidence raises.
    """
    instance = _regular(Path(instance_directory).absolute(), True)
    client._case(application_case)
    service, client_root, retained = instance / "service", instance / "client", instance / "retained-state"
    control_names = ("result.json", "plan.json", "service/bootstrap.created.json", "service/bootstrap.exit.json")
    control_files = {name: _read(instance / name) for name in control_names}
    _need(all(len(raw) <= MAX_FILE for raw in control_files.values()), "boundary control receipt byte limit")
    instance_report = _object(control_files["result.json"])
    constructed = _object(control_files["service/bootstrap.created.json"])
    exited = _object(control_files["service/bootstrap.exit.json"])
    instance_plan = _object(control_files["plan.json"])
    _need(instance_report.get("status") == "recorded_without_benchmark_grade", "complete v2 instance receipt is required")
    cleanup = instance_report.get("cleanup")
    _need(type(cleanup) is dict and type(cleanup.get("returncode")) is int and cleanup["returncode"] == 0
          and cleanup.get("forced") is False and type(cleanup.get("active_processes")) is int and cleanup["active_processes"] == 0
          and cleanup.get("main_handle_signaled") is True and cleanup.get("handles_closed") is True
          and cleanup.get("authority_retained") is False and cleanup.get("job_empty_observed") is True
          and cleanup.get("members") == [] and cleanup.get("errors") == [], "clean owned cleanup receipt is missing")
    _need(constructed.get("schema_version") == exited.get("schema_version") == "upstream-agentops-bootstrap/2"
          and constructed.get("status") == "constructed_not_ready" and exited.get("status") == "stopped"
          and exited.get("owned_stop_accepted") is True and exited.get("original_serve_returned") is True
          and _same(constructed.get("binding"), exited.get("binding")) and type(constructed.get("binding")) is dict,
          "constructed/exited original bootstrap receipts differ")
    binding = constructed["binding"]
    family = {"agentops_agent_core": "core", "agentops_agent_structured_report": "report",
              "agentops_incident_workflow": "workflow"}[application_case["eval_set_id"]]
    _need(instance_plan.get("schema_version") == "upstream-agentops-native-runner/2"
          and _same(instance_plan.get("binding"), binding)
          and binding.get("family") == family and binding.get("host") == "127.0.0.1"
          and type(binding.get("port")) is int and 1 <= binding["port"] <= 65535,
          "source family/endpoint/bootstrap plan binding differs")
    client_files, client_dirs = _inventory(client_root)
    wire, wire_dirs = _inventory(service / "wire")
    retained_before = _inventory(retained)
    client_report = _object(client_files["result.json"])
    _need(client_report.get("schema_version") == "upstream-agentops-case-client/1" and client_report.get("status") == "recorded",
          "complete recorded source-case client is required")
    for key in ("input_objects_unchanged", "application_source_unchanged", "implementation_unchanged", "captured_files_unchanged"):
        _need(client_report.get(key) is True, "client preservation flag is missing/false")
    _manifest(client_files, client_report)
    _need(_same(instance_report.get("client"), client_report), "instance/client receipt differs")
    _need({p.as_posix() for name in client_files for p in PurePosixPath(name).parents if p.as_posix() != "."} == client_dirs,
          "client has unexpected empty directories")
    _need(_same(_object(client_files["input-case.json"]), application_case), "client/source case projection differs")
    policy = _object(client_files["session-policy.json"])
    context = client._session(policy, application_case)
    scheduled = instance_plan.get("source_case")
    _need(type(scheduled) is dict and _same(scheduled.get("case"), application_case)
          and scheduled.get("key") == application_case["eval_set_id"] + "/" + application_case["eval_id"]
          and scheduled.get("family") == family and scheduled.get("context_id") == context
          and type(scheduled.get("sample")) is int and scheduled["sample"] >= 1
          and _same(instance_plan.get("session_policy"), policy), "source case/session instance plan differs")
    _need(all(_same(instance_report.get(key), scheduled[key]) for key in ("key", "sample", "family", "context_id")),
          "instance receipt/source schedule differs")
    client_plan = _object(client_files["plan.json"])
    _need(client_plan.get("schema_version") == "upstream-agentops-case-client-plan/1"
          and client._endpoint(client_plan.get("endpoint")) == binding["port"]
          and client_plan.get("prospective_context_id") == context
          and _same(client_plan.get("case_digest"), _digest(client_files["input-case.json"]))
          and _same(client_plan.get("session_policy_digest"), _digest(client_files["session-policy.json"])),
          "client endpoint/context/case/session plan differs")
    _need(client_report.get("prospective_context_id") == context, "client context policy differs")
    user = policy["native_user_id_expected_from_source"]
    observed_identity = instance_report.get("observed_runtime_identity")
    _need(type(observed_identity) is dict and observed_identity.get("user_id") == user
          and observed_identity.get("session_id") == context and observed_identity.get("context_id") == context
          and observed_identity.get("app_name") == policy["native_app_name_expected"], "observed native identity differs from client policy")
    retention = instance_report.get("retention")
    _need(type(retention) is dict and retention.get("source_and_copy_unchanged") is True
          and _same(retention.get("files"), {name: _digest(raw) for name, raw in retained_before[0].items()}),
          "retained state copy manifest differs")
    exchanges = client_report.get("exchanges")
    _need(type(exchanges) is list and 1 <= len(exchanges) <= 256, "missing/bounded client exchanges")
    server_numbers = sorted(name for name in wire_dirs if "/" not in name)
    _need(server_numbers == [f"{index:06d}" for index in range(1, len(server_numbers) + 1)]
          and 1 <= len(server_numbers) <= 256 and set(server_numbers) == wire_dirs, "server wire directory topology differs")
    server = {}
    for name in server_numbers:
        prefix = name + "/"
        _need({path[len(prefix):] for path in wire if path.startswith(prefix)} == WIRE_FILES, "incomplete/extra server wire members")
        row = _object(wire[prefix + "exchange.json"])
        _need(row.get("schema_version") == "agentops-asgi-exchange/1" and type(row.get("sequence")) is int
              and row["sequence"] == int(name) and row.get("request_body_complete") is True
              and row.get("response_body_complete") is True and not row.get("error") and not row.get("snapshot_error"),
              "server exchange is incomplete or failed")
        _need(row.get("query_string") == base64.b64encode(b"").decode(), "unexpected server query")
        for key, body in (("request_bytes", "request.body.bin"), ("response_bytes", "response.body.bin")):
            _need(type(row.get(key)) is int and row[key] == len(wire[prefix + body]), "server entity count differs")
        chunks, offset = row.get("response_chunks"), 0
        _need(type(chunks) is list and chunks and all(type(chunk) is dict for chunk in chunks), "server response chunk journal missing")
        for index, chunk in enumerate(chunks):
            size = chunk.get("bytes")
            _need(type(size) is int and size >= 0 and type(chunk.get("more_body")) is bool
                  and chunk["more_body"] is (index < len(chunks) - 1), "server response chunk count/termination differs")
            raw_chunk = wire[prefix + "response.body.bin"][offset:offset + size]
            _need(len(raw_chunk) == size and chunk.get("sha256") == hashlib.sha256(raw_chunk).hexdigest(),
                  "server response chunk content differs")
            offset += size
        _need(offset == len(wire[prefix + "response.body.bin"]), "server response chunk coverage differs")
        server[int(name)] = {"row": row, "prefix": prefix}
    bindings, used, previous_server = {}, set(), 0
    for sequence, row in enumerate(exchanges, 1):
        _need(type(row) is dict and type(row.get("sequence")) is int and row["sequence"] == sequence,
              "client exchange sequence differs")
        prefix = f"wire/{sequence:06d}/"
        _need(_same(_object(client_files[prefix + "exchange.json"]), row), "client root/exchange record differs")
        for flag in ("request_send_attempted", "request_fully_sent", "response_eof", "http_body_complete"):
            _need(row.get(flag) is True, "client request/response is incomplete")
        _need(row.get("status") == "received" and type(row.get("http_status")) is int and row["http_status"] == 200,
              "client response is not complete HTTP 200")
        body = client_files[prefix + "request.body.bin"]
        prepared = client_files[prefix + "request.http.bin"]
        expected_headers = [["Host", f"127.0.0.1:{binding['port']}"], ["Connection", "close"], ["Accept-Encoding", "identity"],
                            ["Accept", "application/json"], ["A2A-Version", "1.0"], ["Content-Length", str(len(body))]]
        if body:
            expected_headers.append(["Content-Type", "application/json"])
        expected_prepared = (f"{row['method']} {row['path']} HTTP/1.1\r\n"
                             + "".join(f"{key}: {value}\r\n" for key, value in expected_headers) + "\r\n").encode("ascii") + body
        _need(prepared.partition(b"\r\n\r\n")[2] == body
              and prepared.startswith((row["method"] + " " + row["path"] + " HTTP/1.1\r\n").encode("ascii"))
              and prepared == expected_prepared and _same(row.get("request_headers"), expected_headers)
              and _same(row.get("request_digest"), _digest(prepared)), "client prepared request binding differs")
        status, headers, received_body = client._http(client_files[prefix + "response.http.bin"])
        _need(status == 200 and received_body == client_files[prefix + "response.body.bin"]
              and _same(row.get("received_http_digest"), _digest(client_files[prefix + "response.http.bin"]))
              and _same(row.get("response_headers"), headers)
              and _same(row.get("envelope"), _object(received_body)), "client HTTP/body/envelope binding differs")
        matches = [number for number, observed in server.items()
                   if observed["row"].get("method") == row["method"] and observed["row"].get("path") == row["path"]
                   and wire[observed["prefix"] + "request.body.bin"] == body]
        _need(len(matches) == 1 and matches[0] > previous_server and matches[0] not in used,
              "client/server request is absent/ambiguous/out of order")
        number = matches[0]; observed = server[number]
        _need(type(observed["row"].get("response_status")) is int and observed["row"]["response_status"] == 200
              and wire[observed["prefix"] + "response.body.bin"] == received_body, "client/server response entity differs")
        used.add(number); previous_server = number
        bindings[sequence] = number
    turns = client_report.get("turns")
    source_turns = application_case["conversation"]
    _need(type(turns) is list and len(turns) == len(source_turns)
          and type(client_report.get("turns_completed")) is int
          and client_report["turns_completed"] == sum(turn.get("final_state") == "completed" for turn in turns),
          "all source turns must have a recorded terminal observation")
    first_send = bindings[turns[0]["send_capture_sequence"]]
    readiness = [number for number, observed in server.items() if number < first_send
                 and observed["row"].get("method") == "GET" and observed["row"].get("path") == "/healthz"
                 and observed["row"].get("response_status") == 200
                 and _object(wire[observed["prefix"] + "response.body.bin"]) == {"status": "ready"}]
    _need(readiness, "distinct successful pre-case readiness baseline is missing")
    baseline_number = min(readiness)
    baseline_prefix = server[baseline_number]["prefix"]
    startup_before, startup_after = _boundary(wire, baseline_prefix, "before"), _boundary(wire, baseline_prefix, "after")
    _need(_same(startup_before["business"], startup_after["business"])
          and _same(_logical_memory(startup_before["memory"]), _logical_memory(startup_after["memory"])),
          "readiness baseline state changed during health observation")
    _need(all(number in used or observed["row"].get("method") == "GET" and observed["row"].get("path") == "/healthz"
              and number < first_send for number, observed in server.items()), "foreign server traffic is present")
    samples = []
    assigned_sequences, prior_tasks = [], []
    for index, (source, turn) in enumerate(zip(source_turns, turns), 1):
        _need(type(turn.get("turn_index")) is int and turn["turn_index"] == index - 1
              and turn.get("source_invocation_id") == source["invocation_id"]
              and _same(turn.get("source_user_content"), source["user_content"])
              and turn.get("final_state") in {"completed", "input_required"} and turn.get("status") == "recorded"
              and (turn["final_state"] != "input_required" or index == len(turns)), "source/client terminal turn differs")
        observations = turn.get("observations")
        _need(type(observations) is list and observations and all(type(row) is dict for row in observations), "turn observations are missing")
        sequences = [row.get("capture_sequence") for row in observations]
        _need(all(type(value) is int and value in bindings for value in sequences)
              and sequences == sorted(set(sequences)) and sequences[0] == turn.get("send_capture_sequence")
              and observations[-1].get("state") == turn["final_state"], "source turn exchange progression differs")
        _need(sequences == list(range(sequences[0], sequences[-1] + 1)), "turn client poll coverage differs")
        prepared_message = {"messageId": turn.get("message_id"), "role": "ROLE_USER", "contextId": context,
                            "parts": [{"text": part["text"]} for part in source["user_content"]["parts"]]}
        _need(type(prepared_message["messageId"]) is str and prepared_message["messageId"]
              and type(turn.get("send_rpc_id")) is str and turn["send_rpc_id"], "source turn message/RPC identity missing")
        expected_send = {"jsonrpc": "2.0", "id": turn["send_rpc_id"], "method": "SendMessage", "params": {"message": prepared_message}}
        send_body = _object(client_files[f"wire/{sequences[0]:06d}/request.body.bin"])
        send_record = exchanges[sequences[0] - 1]
        _need(send_record.get("method") == "POST" and send_record.get("path") == "/"
              and send_record.get("request_rpc_id") == turn["send_rpc_id"] and send_record.get("rpc_method") == "SendMessage"
              and _same(send_body, expected_send), "actual source SendMessage body differs from exact user input")
        task_id = None
        for observation_index, (sequence, observation) in enumerate(zip(sequences, observations)):
            captured = exchanges[sequence - 1]
            request_body = _object(client_files[f"wire/{sequence:06d}/request.body.bin"])
            if observation_index:
                _need(type(captured.get("request_rpc_id")) is str and captured["request_rpc_id"],
                      "poll RPC identity must be nonempty text")
                _need(captured.get("method") == "POST" and captured.get("path") == "/"
                      and captured.get("rpc_method") == "GetTask"
                      and _same(request_body, {"jsonrpc": "2.0", "id": captured.get("request_rpc_id"), "method": "GetTask",
                                              "params": {"id": task_id, "historyLength": 100}}), "actual source poll request differs")
            task, shape, state = client._task(captured["envelope"], request_body.get("id"), context,
                                              expected_task=task_id, prior_tasks=prior_tasks)
            if task_id is None:
                task_id = task["id"]
            _need(observation_index == len(observations) - 1 or state in {"submitted", "working"},
                  "source client cannot poll after a terminal or confirmation-pause observation")
            _need(_same(observation, client._observation(task, shape, state, sequence)), "client turn/task observation differs from received bytes")
            assigned_sequences.append(sequence)
        _need(turn.get("task_id") == task_id and turn.get("observed_context_id") == context, "turn task/context differs")
        prior_tasks.append(task_id)
        start, end = bindings[sequences[0]], bindings[sequences[-1]]
        points = []
        for number in range(start, end + 1):
            for boundary in ("before", "after"):
                stage = "before" if number == start and boundary == "before" else "terminal" if number == end and boundary == "after" else "in_progress"
                points.append({"sample_ordinal": len(points) + 1, "stage": stage,
                               **_boundary(wire, server[number]["prefix"], boundary)})
        samples.append({"turn_index": index, "source_invocation_label": source["invocation_id"],
                        "native_user_id": user, "native_session_id": context,
                        "terminal_public_state": turn["final_state"], "samples": points})
    _need(exchanges[0].get("method") == "GET" and exchanges[0].get("path") == "/.well-known/agent-card.json"
          and assigned_sequences == list(range(2, len(exchanges) + 1)), "client source-task exchange coverage differs")
    close_business, reader_identity = _closed_business(retained / "incidents.db", retained)
    close_memory = snapshot_memory(retained / "memory.db", observation_mode="archived")
    _need(close_memory.get("status") in {"absent", "recorded"}, "retained close memory unsupported")
    _need(_inventory(client_root) == (client_files, client_dirs) and _inventory(service / "wire") == (wire, wire_dirs)
          and _inventory(retained) == retained_before
          and all(_regular(instance / name).read_bytes() == raw for name, raw in control_files.items()),
          "boundary inputs changed during collection")
    return {"schema_version": "agentops-source-case-boundaries/1", "status": "bound_sampled_observations",
            "source_case": {key: application_case[key] for key in ("eval_set_id", "eval_id")},
            "startup": {**startup_after, "kind": "successful_original_readiness_boundary_before_source_requests",
                        "wire_sequence": baseline_number, "readiness_before": startup_before},
            "turns": samples, "retained_close": {"business": close_business, "memory": close_memory},
            "client_server_entity_bindings": [{"client_sequence": sequence, "server_sequence": number} for sequence, number in bindings.items()],
            "input_files": {"control_receipts": {name: _digest(raw) for name, raw in control_files.items()},
                            "client": {name: _digest(raw) for name, raw in client_files.items()},
                            "server_wire": {name: _digest(raw) for name, raw in wire.items()},
                            "retained": {name: _digest(raw) for name, raw in retained_before[0].items()}},
            "business_reader_identity": reader_identity, "source_authentication_proven": False,
            "owned_cleanup_receipt_consistency_checked": True,
            "source_closed_proven": False, "process_exit_proven": False, "continuous_mutation_absence_proven": False,
            "cross_store_atomic_snapshot": False, "native_qualification_established": False, "full_task_grade_assigned": False}
