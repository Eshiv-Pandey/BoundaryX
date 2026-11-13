"""Once-only gated native source-case scheduler and evidence retention.

Only stdlib and the stdlib client are imported here. No evaluator references,
SDK, upstream agent or credential is imported/read by this outer process.
Mocked scheduler checks are software evidence, never native qualification.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import sys
import time
import tomllib
from uuid import uuid4

from . import upstream_agentops_client_v1 as client


SCHEMA = "upstream-agentops-native-runner/1"
MINIMUMS = {"physical_available_bytes": 1024**3, "commit_available_bytes": 2 * 1024**3}
FAMILIES = {"agentops_agent_core": "core", "agentops_agent_structured_report": "report",
            "agentops_incident_workflow": "workflow"}
IMPLEMENTATION = (
    "src/interoperability/__init__.py", "src/interoperability/upstream_agentops_client_v1.py",
    "src/interoperability/upstream_agentops_native_runner_v1.py", "src/interoperability/windows_owned_job_v1.py",
    "src/interoperability/windows_tcp_ownership_v1.py",
    "src/interoperability/agentops_raw_events_v1.py", "src/interoperability/agentops_public_events_v1.py",
    "src/interoperability/agentops_event_binding_v1.py", "scripts/run_upstream_agentops_cases_v1.py",
    "scripts/serve_upstream_agentops_cases_v1.py", "scripts/agentops_asgi_capture_v1.py",
    "scripts/agentops_native_probe_v2.py", "scripts/with_gemini_key.ps1",
)
READINESS_SECONDS = 120.0


class ConnectionOwnershipError(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def regular(path, directory=False):
    path = Path(path).absolute()
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "linked/reparse path is unsupported")
    info = path.stat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), "nonregular path")
    return path


def digest(path):
    path = regular(path)
    hasher, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": hasher.hexdigest()}


def read_json(path):
    need(regular(path).stat().st_size <= 32 * 1024 * 1024, "oversized JSON input")
    return client.strict_json(Path(path).read_bytes())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    regular(path.parent, True)
    with path.open("xb") as stream:
        stream.write(client._encoded(value))


def relative(value):
    need(type(value) is str and value and "\\" not in value and ":" not in value, "invalid relative source path")
    parsed = PurePosixPath(value)
    need(not parsed.is_absolute() and ".." not in parsed.parts and parsed.as_posix() == value, "noncanonical relative path")
    return value


def inventory(root):
    regular(root, True)
    found = {}
    for path in sorted(Path(root).rglob("*")):
        regular(path, path.is_dir())
        if path.is_file():
            found[path.relative_to(root).as_posix()] = digest(path)
    return found


def copy_checked(source, target, identity):
    need(digest(source) == identity, "copy input identity changed")
    target.parent.mkdir(parents=True, exist_ok=True)
    regular(target.parent, True)
    with regular(source).open("rb") as incoming, target.open("xb") as outgoing:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(chunk)
    need(digest(source) == identity and digest(target) == identity, "copied identity mismatch")


@dataclass(frozen=True)
class Config:
    workspace: Path
    output: Path
    source_root: Path
    ingestion: Path
    application_source: Path
    application_receipt: Path
    interpreter: Path
    model: str
    selectors: tuple[str, ...] = ()
    samples: int | None = None


def validate_config(config):
    need(re.fullmatch(r"gemini-[A-Za-z0-9._-]{1,100}", config.model) is not None, "explicit Gemini model required")
    need(config.samples is None or type(config.samples) is int and 1 <= config.samples <= 10, "invalid explicit sample count")
    need(type(config.selectors) is tuple and all(type(item) is str for item in config.selectors), "invalid selectors")
    for path in (config.workspace, config.output, config.source_root, config.ingestion,
                 config.application_source, config.application_receipt, config.interpreter):
        need(path.is_absolute(), "all configuration paths must be absolute")
        need(path == path.resolve(), "configuration paths must be canonical without traversal or links")
    regular(config.workspace, True)
    for path in (config.source_root,):
        regular(path, True)
    for path in (config.ingestion, config.application_source, config.application_receipt, config.interpreter):
        regular(path)
    need(config.output.is_relative_to(config.workspace / "runs/upstream-agentops-native"), "output outside named native allocations")
    need(not config.output.exists() and not config.output.is_symlink(), "allocation already consumed")
    need(not config.output.is_relative_to(config.source_root), "output overlaps upstream source")
    ancestor = config.output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    regular(ancestor, True)


def load_application(config):
    document, receipt = read_json(config.application_source), read_json(config.application_receipt)
    need(receipt.get("schema_version") == "upstream-agentops-export/1" and receipt.get("status") == "passed",
         "audited application export receipt required")
    entries = [item for item in receipt.get("files", []) if item.get("path") == receipt.get("application_inputs")]
    need(len(entries) == 1, "application export file binding not unique")
    expected = {key: entries[0][key] for key in ("bytes", "sha256")}
    need(digest(config.application_source) == expected, "application export changed")
    need(document.get("schema_version") == client.CASE_SCHEMA and type(document.get("cases")) is list, "invalid application export schema")
    cases = document["cases"]
    need(len(cases) == 21 and receipt.get("case_count") == 21, "original 21-case scope required")
    seen, counts, turns = set(), {name: 0 for name in FAMILIES}, 0
    for case in cases:
        client._case(case)
        key = (case["eval_set_id"], case["eval_id"])
        need(key not in seen, "duplicate source case")
        need(case["session_input"]["state"] == {}, "nonempty source session state is unsupported")
        seen.add(key)
        counts[key[0]] += 1
        turns += len(case["conversation"])
    need(list(counts.values()) == [15, 3, 3] and turns == 22, "source family/turn scope differs")
    return cases, {"application": expected, "receipt": digest(config.application_receipt), "case_count": 21,
                   "turn_count": 22, "family_counts": counts, "evaluator_reference_texts_parsed_or_given_to_model": False}


def verify_sources(config):
    ingestion = read_json(config.ingestion)
    need(ingestion.get("schema_version") == "user-source-archive-ingestion/1" and ingestion.get("status") == "passed",
         "passed original ingestion required")
    need((config.workspace / relative(ingestion["source_tree"])).absolute() == config.source_root,
         "original source root differs from ingestion")
    identities = {}
    for row in ingestion["records"]:
        name = relative(row["source_relative_path"])
        if row["kind"] == "regular_file":
            need(name not in identities, "duplicate ingestion file")
            need(relative(row["extracted"]["path"]) == (PurePosixPath(ingestion["source_tree"]) / name).as_posix(),
                 "ingestion extracted path conflicts")
            expected = {key: row["extracted"][key] for key in ("bytes", "sha256")}
            need(digest(config.source_root / name) == expected, "original source differs from ingestion")
            identities[name] = expected
        else:
            need(row["kind"] == "symlink_payload_not_materialized", "unsupported source acquisition record")
            need(not (config.source_root / name).exists() and not (config.source_root / name).is_symlink(),
                 "unmaterialized acquisition link was changed")
            payload = config.workspace / relative(row["extracted"]["path"])
            need(digest(payload) == {key: row["extracted"][key] for key in ("bytes", "sha256")}, "inert link payload changed")
    need(len(identities) == ingestion.get("regular_files") == 421, "original ingestion file scope differs")
    need(inventory(config.source_root) == identities, "original source tree membership differs")
    runtime_names = [name for name in identities if name.startswith(("agents/python/src/", "agents/data/")) or name in {
        "agents/LICENSE", "agents/python/pyproject.toml", "agents/python/uv.lock"}]
    need(runtime_names and not any("evals/" in name for name in runtime_names), "evaluator references overlap runtime staging")
    return identities, runtime_names, ingestion


def original_repeats(source_root):
    """Read inert TOML/AST, never import the original evaluation wrappers."""
    mise_path = source_root / "agents/python/mise.toml"
    core_path = source_root / "agents/python/evals/run_adk_eval.py"
    report_path = source_root / "agents/python/evals/report_eval.py"
    tasks = tomllib.loads(regular(mise_path).read_text(encoding="utf-8"))["tasks"]
    need("--repeat" not in tasks["eval"]["run"], "core upstream repeat contract changed")
    tree = ast.parse(regular(core_path).read_text(encoding="utf-8"))
    defaults = [kw.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                and any(isinstance(arg, ast.Constant) and arg.value == "--repeat" for arg in node.args)
                for kw in node.keywords if kw.arg == "default" and isinstance(kw.value, ast.Constant)]
    need(defaults == [1], "core default repeat is not source-verified 1")
    report_tree = ast.parse(regular(report_path).read_text(encoding="utf-8"))
    report_runs = [kw.value.value for node in ast.walk(report_tree) if isinstance(node, ast.Call)
                   for kw in node.keywords if kw.arg == "num_runs" and isinstance(kw.value, ast.Constant)]
    need(report_runs == [3], "report original repeat is not source-verified 3")
    need(re.search(r"(?:^|\s)--repeat 3(?:\s|$)", tasks["eval:workflow"]["run"]), "workflow repeat contract differs")
    return {"core": 1, "report": 3, "workflow": 3}, {
        "source_files": {path.relative_to(source_root).as_posix(): digest(path) for path in (mise_path, core_path, report_path)},
        "basis": "Core wrapper default 1; report num_runs=3; workflow mise --repeat 3. A2A schedule mirrors counts, not the original evaluator execution."}


def schedule(cases, repeats, selectors=(), samples=None):
    available = {case["eval_set_id"] + "/" + case["eval_id"]: case for case in cases}
    need(len(set(selectors)) == len(selectors) and all(key in available for key in selectors), "unknown or duplicate selected source case")
    items = []
    for case in cases:
        key = case["eval_set_id"] + "/" + case["eval_id"]
        if selectors and key not in selectors:
            continue
        family = FAMILIES[case["eval_set_id"]]
        for sample in range(1, (samples if samples is not None else repeats[family]) + 1):
            items.append({"index": len(items) + 1, "key": key, "family": family, "sample": sample,
                          "context_id": str(uuid4()), "case": case})
    need(items, "empty source schedule")
    return items


def session_policy(item):
    context = item["context_id"]
    return {"schema_version": client.SESSION_SCHEMA, "context_id": context,
            "source_session_input": item["case"]["session_input"], "native_app_name_expected": "agentops-agent",
            "native_user_id_expected_from_source": "A2A_USER_" + context,
            "native_session_id_expected_from_source": context,
            "mapping_basis": "Original agent.server _A2ASessionService plus pinned ADK A2A executor; prospective source-derived mapping, not observed/authenticated"}


def collect_gate(runtime, stage, binding):
    samples = [runtime.memory_sample()]
    runtime.sleep(10.1)
    samples.append(runtime.memory_sample())
    eligible = all(type(sample.get(key)) is int and sample[key] >= minimum for sample in samples for key, minimum in MINIMUMS.items())
    try:
        wall = (datetime.fromisoformat(samples[1]["observed_at_utc"]) - datetime.fromisoformat(samples[0]["observed_at_utc"])).total_seconds()
        gap = (samples[1]["monotonic_ns"] - samples[0]["monotonic_ns"]) / 1e9
        eligible = eligible and all(type(sample["monotonic_ns"]) is int and sample["monotonic_ns"] >= 0 for sample in samples)
        eligible = eligible and 10 <= wall <= 30 and 10 <= gap <= 30 and abs(wall - gap) <= 1
    except (KeyError, TypeError, ValueError):
        eligible = False
    return {"schema_version": "upstream-agentops-resource-gate/1", "stage": stage, "binding": binding,
            "minimums": dict(MINIMUMS), "samples": samples, "eligible": bool(eligible),
            "threshold_safety_proven": False, "signed_authorization_proven": False}


def load_bootstrap(path):
    spec = importlib.util.spec_from_file_location("_upstream_source_bootstrap", regular(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def powershell_launcher(config, project, bootstrap_args, destination):
    """Only single-quoted nonsecret literals enter the generated script."""
    def literal(value):
        need(type(value) is str and "\0" not in value and "\r" not in value and "\n" not in value, "invalid launch argument")
        return "'" + value.replace("'", "''") + "'"
    lines = ["$ErrorActionPreference = 'Stop'", "$nativeCaseArgs = @(",
             ",\n".join("  " + literal(item) for item in bootstrap_args), ")",
             "& " + literal(str(project / "scripts/with_gemini_key.ps1")) + " -Program " + literal(str(config.interpreter)) + " -ProgramArguments $nativeCaseArgs",
             "exit $LASTEXITCODE", ""]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    windir = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    executable = regular(windir / "System32/WindowsPowerShell/v1.0/powershell.exe")
    return [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(destination)]


def clean_cleanup(receipt):
    return terminal_cleanup(receipt) and receipt.get("forced") is False and receipt["returncode"] == 0


def terminal_cleanup(receipt):
    return (type(receipt) is dict and type(receipt.get("returncode")) is int and receipt.get("members") == []
            and receipt.get("active_processes") == 0 and type(receipt.get("active_processes")) is int
            and receipt.get("main_handle_signaled") is True and receipt.get("handles_closed") is True
            and receipt.get("authority_retained") is False and receipt.get("job_empty_observed") is True and receipt.get("errors") == [])


def finish_owned(runtime, job, graceful_seconds):
    try:
        receipt = job.finish(graceful_seconds=graceful_seconds, forced_seconds=5)
    except BaseException as error:
        receipt = {"status": "cleanup_exception", "errors": [type(error).__name__], "handles_closed": False,
                   "authority_retained": True, "job_empty_observed": False}
    if receipt.get("handles_closed") is not True:
        if not hasattr(runtime, "held_jobs"):
            runtime.held_jobs = []
        if all(held is not job for held in runtime.held_jobs):
            runtime.held_jobs.append(job)
    elif hasattr(runtime, "held_jobs"):
        runtime.held_jobs[:] = [held for held in runtime.held_jobs if held is not job]
    return receipt


def runtime_identity(item, observed_client, tables):
    """Bind actual retained IDs; expected mappings alone establish no observation."""
    policy = session_policy(item)
    context, user, app = item["context_id"], policy["native_user_id_expected_from_source"], policy["native_app_name_expected"]
    sessions = tables.get("sessions", [])
    need(type(sessions) is list and len(sessions) == 1, "isolated runtime session is not unique")
    session = sessions[0]
    need((session.get("app_name"), session.get("user_id"), session.get("id")) == (app, user, context), "actual native session mapping differs")
    tasks = tables.get("tasks", [])
    need(type(tasks) is list and tasks and all(row.get("context_id") == context for row in tasks), "runtime tasks context differs")
    public_ids = [turn["task_id"] for turn in observed_client.get("turns", []) if "task_id" in turn]
    need(public_ids and len(set(public_ids)) == len(public_ids) and {row.get("id") for row in tasks} == set(public_ids),
         "retained task identities differ from observed client tasks")
    events = tables.get("events", [])
    need(type(events) is list and events and all((row.get("app_name"), row.get("user_id"), row.get("session_id")) == (app, user, context) for row in events),
         "retained event session identity differs")
    return {"schema_version": "upstream-agentops-observed-runtime-identity/1", "app_name": app, "user_id": user,
            "session_id": context, "context_id": context, "task_ids": public_ids,
            "event_ids": [row["id"] for row in events], "invocation_ids": sorted({row["invocation_id"] for row in events}),
            "source_case_key": item["key"], "source_invocation_labels_are_native_ids": False,
            "runtime_identity_observed": True, "runtime_identity_authenticated": False, "benchmark_grade_proven": False,
            "causal_order_proven": False, "complete_event_stream_proven": False}


class Runtime:
    """Real operations; tests override these methods without native launches."""
    def memory_sample(self):
        from ctypes import Structure, byref, sizeof, WinDLL, c_ulong, c_ulonglong
        need(os.name == "nt", "native Windows memory observation required")
        class Memory(Structure):
            _fields_ = [("length", c_ulong), ("load", c_ulong)] + [(name, c_ulonglong) for name in (
                "total_physical", "physical_available", "total_commit", "commit_available", "total_virtual", "available_virtual", "available_extended")]
        status = Memory()
        status.length = sizeof(Memory)
        need(WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx(byref(status)), "memory observation failed")
        return {"observed_at_utc": now(), "monotonic_ns": time.monotonic_ns(),
                "physical_available_bytes": int(status.physical_available), "commit_available_bytes": int(status.commit_available)}

    def sleep(self, seconds):
        time.sleep(seconds)

    def dependencies(self, config):
        root = config.interpreter.parent.parent
        regular(root / "pyvenv.cfg")
        library = regular(root / "Lib/site-packages", True)
        records = inventory(library)
        metadata = {}
        for name in records:
            if name.endswith(".dist-info/METADATA"):
                text = (library / name).read_text(encoding="utf-8")
                package = re.search(r"^Name: (.+)$", text, re.M)
                version = re.search(r"^Version: (.+)$", text, re.M)
                if package and version:
                    key = re.sub(r"[-_.]+", "-", package[1]).lower()
                    need(key not in metadata, "duplicate installed distribution")
                    metadata[key] = version[1]
        lock = tomllib.loads((config.source_root / "agents/python/uv.lock").read_text(encoding="utf-8"))
        locked = {re.sub(r"[-_.]+", "-", package["name"]).lower(): package["version"]
                  for package in lock["package"] if "version" in package}
        differences = {name: {"installed": version, "locked": locked[name]} for name, version in metadata.items()
                       if name in locked and version != locked[name]}
        declared = tomllib.loads((config.source_root / "agents/python/pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
        required = {re.sub(r"[-_.]+", "-", re.match(r"[A-Za-z0-9_.-]+", entry)[0]).lower() for entry in declared}
        return {"interpreter": {"path": str(config.interpreter), **digest(config.interpreter)},
                "pyvenv_cfg": digest(root / "pyvenv.cfg"), "library": str(library), "files": records,
                "distribution_versions": metadata, "locked_version_differences": differences,
                "required_distribution_names": sorted(required), "missing_required_distributions": sorted(required - metadata.keys()),
                "extra_distributions": {name: version for name, version in metadata.items() if name not in locked},
                "runtime_install_performed": False, "lock_equivalence_proven": False,
                "installed_locked_intersection_versions_match": not differences,
                "loaded_module_identities_proven": False}

    def job(self):
        from .windows_owned_job_v1 import WindowsJob
        return WindowsJob()

    def free_port(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def launch_argv(self, config, project, args, destination):
        return powershell_launcher(config, project, args, destination)

    def connection_guard(self, service, job):
        from .windows_tcp_ownership_v1 import verify_connection
        def guard(sock):
            constructed = read_json(service / "bootstrap.created.json")
            binding = read_json(service.parent / "plan.json")["binding"]
            need(constructed.get("binding") == binding and constructed.get("status") == "constructed_not_ready",
                 "connection guard bootstrap binding differs")
            observed = verify_connection(sock, constructed.get("pid"), job)
            directory = service / "connection-ownership"
            directory.mkdir(exist_ok=True)
            write_json(directory / f"{len(list(directory.iterdir())) + 1:06d}.json", observed)
        return guard

    def ready(self, service, endpoint, job):
        observations, started = [], time.monotonic()
        port = client._endpoint(endpoint)
        while time.monotonic() - started < READINESS_SECONDS:
            need(job.poll() is None, "owned wrapper exited before readiness")
            if not (service / "bootstrap.created.json").is_file():
                observations.append({"observed_at_utc": now(), "state": "awaiting_original_construction"})
                self.sleep(2)
                continue
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            observation = {"observed_at_utc": now(), "monotonic_ns": time.monotonic_ns(), "path": "/healthz"}
            try:
                connection.connect()
                try:
                    self.connection_guard(service, job)(connection.sock)
                except (OSError, ValueError, TypeError, KeyError) as error:
                    observation["ownership_error_type"] = type(error).__name__
                    observations.append(observation)
                    write_json(service / "readiness.json", {"status": "ownership_rejected", "observations": observations,
                               "health_request_bytes_sent_on_rejected_socket": False})
                    raise ConnectionOwnershipError("accepted readiness socket ownership rejected") from None
                connection.request("GET", "/healthz", headers={"A2A-Version": "1.0", "Connection": "close"})
                response = connection.getresponse()
                raw = response.read(65537)
                need(len(raw) <= 65536, "oversized readiness entity")
                observation.update(status=response.status, headers=response.getheaders(), body_base64=__import__("base64").b64encode(raw).decode("ascii"))
                if response.status == 200 and client.strict_json(raw) == {"status": "ready"} and (service / "bootstrap.created.json").is_file():
                    constructed = read_json(service / "bootstrap.created.json")
                    need(constructed.get("status") == "constructed_not_ready", "unexpected bootstrap construction receipt")
                    observations.append(observation)
                    write_json(service / "readiness.json", {"status": "observed", "observations": observations,
                               "scope": "Original healthz read-only readiness and constructed receipt; no application grade"})
                    return
            except ConnectionOwnershipError:
                raise
            except (OSError, ValueError, http.client.HTTPException) as error:
                observation["error_type"] = type(error).__name__
            finally:
                connection.close()
            observations.append(observation)
            self.sleep(2)
        write_json(service / "readiness.json", {"status": "timeout", "observations": observations})
        raise ValueError("original application readiness deadline reached")

    def client(self, item, endpoint, output, application, *, job):
        return client.run_case(item["case"], endpoint, output, session_policy=session_policy(item), source_case_path=application,
                               connection_guard=self.connection_guard(output.parent / "service", job))

    def settle_owned_jobs(self):
        # A live unassigned suspended child cannot be recovered from a saved PID.
        # Keep this exact owner process/handles alive until cleanup is observed.
        held = getattr(self, "held_jobs", [])
        if held:
            try:
                print(json.dumps({"schema_version": SCHEMA, "status": "waiting_for_owned_cleanup", "count": len(held)}), flush=True)
            except BaseException:
                pass  # A closed output pipe/interruption cannot discard live authority.
        while held:
            try:
                for job in list(held):
                    try:
                        receipt = finish_owned(self, job, 0)
                        if receipt.get("handles_closed") is True and job in held:
                            held.remove(job)
                    except BaseException:
                        pass  # Keep the exact object/handles while cleanup remains unknown.
                if held:
                    try:
                        self.sleep(2)
                    except BaseException:
                        pass
            except BaseException:
                # Even snapshot allocation/iteration failure cannot discard the
                # continuing exact owner of an unassigned suspended child.
                continue

    def retain(self, service, destination):
        state = service / "state"
        records = inventory(state)
        destination.mkdir(exist_ok=False)
        for name, identity in records.items():
            copy_checked(state / name, destination / name, identity)
        need(inventory(state) == records and inventory(destination) == records, "closed state retention changed")
        return {"schema_version": "upstream-agentops-retained-state/1", "files": records,
                "stores": {name: name in records for name in ("incidents.db", "runtime.db", "memory.db")},
                "source_and_copy_unchanged": True, "group_termination_observed_before_copy": True,
                "memory_database_lazy_absence_is_not_failure_or_no_write_proof": True}

    def export(self, service, retained, output):
        from .agentops_raw_events_v1 import export_database
        from .agentops_public_events_v1 import export_wire
        from .agentops_event_binding_v1 import export_comparison
        output.mkdir(exist_ok=False)
        records = {}
        if (retained / "runtime.db").is_file():
            records["raw"] = export_database(retained / "runtime.db", output / "raw")
        if (service / "wire").is_dir():
            records["public"] = export_wire(service / "wire", output / "public")
        if records.get("raw", {}).get("status") == records.get("public", {}).get("status") == "passed":
            records["binding"] = export_comparison(output / "raw", output / "public", output / "binding")
        return {"status": "recorded", "exports": records, "benchmark_grade_proven": False,
                "all_pipeline_steps_passed": len(records) == 3 and all(row.get("status") == "passed" for row in records.values())}


def run_one(config, runtime, item, project, staged, allocation):
    service = allocation / "service"
    service.mkdir(parents=True, exist_ok=False)
    (service / "state").mkdir(exist_ok=False)
    report = {"key": item["key"], "sample": item["sample"], "family": item["family"], "context_id": item["context_id"],
              "status": "partial", "launch_attempted": False, "client_attempted": False, "cleanup": None,
              "native_case_grade": None, "qualification_established": False, "errors": [], "started_at_utc": now()}
    job = None
    try:
        port, token = runtime.free_port(), uuid4().hex
        module = load_bootstrap(project / "scripts/serve_upstream_agentops_cases_v1.py")
        bootstrap_config = module.BootstrapConfig(staged, service, item["family"], "gemini", config.model,
                                                 "127.0.0.1", port, allocation / "prelaunch-gate.json", token)
        binding = module.binding_for(bootstrap_config, str(config.interpreter), digest(project / "scripts/serve_upstream_agentops_cases_v1.py")["sha256"])
        args = ["-I", "-S", "-B", str(project / "scripts/serve_upstream_agentops_cases_v1.py"),
                "--source-root", str(staged), "--service-dir", str(service), "--family", item["family"],
                "--provider", "gemini", "--model", config.model, "--host", "127.0.0.1", "--port", str(port),
                "--resource-gate-receipt", str(allocation / "prelaunch-gate.json"), "--stop-token", token]
        argv = runtime.launch_argv(config, project, args, allocation / "launch.ps1")
        write_json(allocation / "plan.json", {"schema_version": SCHEMA, "binding": binding, "source_case": item,
                   "session_policy": session_policy(item), "native_arguments": args, "owned_wrapper_arguments": argv,
                   "readiness_seconds": READINESS_SECONDS, "client_limits": client.DEFAULT_LIMITS,
                   "automatic_confirmations": False, "upstream_default_model": "gemini-3.5-flash", "selected_model": config.model,
                   "model_config_differs_from_upstream_default": config.model != "gemini-3.5-flash"})
        gate = collect_gate(runtime, "prelaunch", binding)
        write_json(allocation / "prelaunch-gate.json", gate)
        need(gate["eligible"], "prelaunch headroom ineligible")
        module.validate_resource_gate(gate, binding, datetime.now(timezone.utc))
        job = runtime.job()
        with (allocation / "stdout.bin").open("xb") as stdout, (allocation / "stderr.bin").open("xb") as stderr:
            report["launch_attempted"] = True
            try:
                report["owned_wrapper_pid"] = job.launch(argv, str(allocation), stdout, stderr)
                endpoint = f"http://127.0.0.1:{port}/"
                runtime.ready(service, endpoint, job)
                need(read_json(service / "bootstrap.created.json").get("binding") == binding, "constructed bootstrap binding differs")
                report["client_attempted"] = True
                report["client"] = runtime.client(item, endpoint, allocation / "client", config.application_source, job=job)
            finally:
                # Atomic non-HTTP stop request; never signal a PID/name found by search.
                temporary = service / "stop.request.pending.json"
                write_json(temporary, {"schema_version": "upstream-agentops-stop/1", "stop_token": token})
                need(not (service / "stop.request.json").exists(), "stop marker already exists")
                os.rename(temporary, service / "stop.request.json")
                report["cleanup"] = finish_owned(runtime, job, 20)
                if report["cleanup"].get("handles_closed") is True:
                    job = None
        need(clean_cleanup(report["cleanup"]), "owned process cleanup did not establish clean exit and empty job")
        exited = read_json(service / "bootstrap.exit.json")
        need(exited.get("status") == "stopped" and exited.get("owned_stop_accepted") is True
             and exited.get("original_serve_returned") is True and exited.get("binding") == binding, "original lifespan stop receipt missing or mismatched")
        report["retention"] = runtime.retain(service, allocation / "retained-state")
        need(report["retention"]["stores"].get("incidents.db") and report["retention"]["stores"].get("runtime.db"), "required retained stores missing")
        report["evidence_pipeline"] = runtime.export(service, allocation / "retained-state", allocation / "evidence")
        need(report.get("client", {}).get("status") == "recorded", "client transport observations incomplete")
        need(report["evidence_pipeline"].get("all_pipeline_steps_passed") is True, "raw/public/binding pipeline incomplete")
        report["observed_runtime_identity"] = runtime_identity(item, report["client"], read_json(allocation / "evidence/raw/decoded-tables.json"))
        report["status"] = "recorded_without_benchmark_grade"
    except BaseException as error:
        attached = getattr(error, "owned_job", None)
        if job is None and attached is not None:
            # Assignment to runtime.job() may never complete when construction
            # raises with a still-open exact Job handle attached to the error.
            job = attached
        report["errors"].append({"type": type(error).__name__})
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            report["interrupted"] = True
    finally:
        if job is not None:
            first = report["cleanup"]
            report["cleanup"] = finish_owned(runtime, job, 0)
            report["cleanup_first_attempt"] = first
            if first is not None and not clean_cleanup(first):
                report["status"] = "partial"
        # Preserve terminal closed state even on failed/forced execution; it cannot qualify.
        if terminal_cleanup(report["cleanup"]) and not (allocation / "retained-state").exists():
            try:
                report["retention"] = runtime.retain(service, allocation / "retained-state")
            except (OSError, ValueError) as error:
                report["errors"].append({"type": type(error).__name__, "phase": "partial_retention"})
        report["finished_at_utc"] = now()
        write_json(allocation / "result.json", report)
    return report


def run(config, runtime=None):
    runtime = runtime or Runtime()
    validate_config(config)
    cases, inputs = load_application(config)
    config.output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": SCHEMA, "status": "partial", "started_at_utc": now(), "instances": [], "errors": [],
              "native_launch_attempts": 0, "client_attempts": 0, "native_upstream_case_grades": 0, "qualification_established": False,
              "overall_implementation_percent": None, "model": config.model, "provider": "gemini",
              "evaluator_reference_content_used_for_model_or_grading": False, "hash_only_source_verification_reads": True}
    originals = staged_identities = dependency_receipt = identities = None
    try:
        gate = collect_gate(runtime, "prestage", {"output": str(config.output), "source_root": str(config.source_root),
                            "interpreter": str(config.interpreter), "model": config.model, "application": inputs["application"]})
        write_json(config.output / "prestage-gate.json", gate)
        need(gate["eligible"], "prestage resource headroom ineligible")
        identities, runtime_names, ingestion = verify_sources(config)
        repeats, schedule_basis = original_repeats(config.source_root)
        planned = schedule(cases, repeats, config.selectors, config.samples)
        implementations = {name: digest(config.workspace / name) for name in IMPLEMENTATION}
        originals = {str(config.source_root / name): identity for name, identity in identities.items()}
        originals.update({str(config.workspace / row["extracted"]["path"]): {key: row["extracted"][key] for key in ("bytes", "sha256")}
                          for row in ingestion.get("records", []) if row["kind"] == "symlink_payload_not_materialized"})
        originals.update({str(config.workspace / name): identity for name, identity in implementations.items()})
        originals.update({str(path): digest(path) for path in (config.ingestion, config.application_source, config.application_receipt)})
        dependency_receipt = runtime.dependencies(config)
        write_json(config.output / "dependency-identities.json", dependency_receipt)
        need(not dependency_receipt.get("locked_version_differences"), "installed dependencies differ from original lock")
        need(not dependency_receipt.get("missing_required_distributions"), "required original runtime dependencies missing")
        # Hashing may take time; qualify headroom again immediately before copies.
        staging_gate = collect_gate(runtime, "prestage", gate["binding"])
        write_json(config.output / "prestage-after-identities-gate.json", staging_gate)
        need(staging_gate["eligible"], "headroom fell below minima before source staging")
        staged, project = config.output / "stage/upstream", config.output / "stage/project"
        for name in runtime_names:
            copy_checked(config.source_root / name, staged / name, identities[name])
        for name, identity in implementations.items():
            copy_checked(config.workspace / name, project / name, identity)
        staged_identities = inventory(config.output / "stage")
        write_json(config.output / "plan.json", {"schema_version": SCHEMA, "source_root": str(config.source_root),
                   "source_commit_label": ingestion["archive_root_and_comment_commit"], "independent_git_object_authentication": False,
                   "inputs": inputs, "original_repeats": repeats, "schedule_basis": schedule_basis,
                   "sample_override": config.samples, "selected_source_cases": list(config.selectors), "planned_instances": planned,
                   "full_source_case_scope": len({item["key"] for item in planned}) == 21, "references_staged_for_runtime": False,
                   "runtime_files": {name: identities[name] for name in runtime_names}, "implementation": implementations,
                   "stage_files": staged_identities, "source_import_route": "explicit original agents/python/src; no symlink materialization",
                   "credentials_injected_by": "with_gemini_key.ps1 inside owned native wrapper only; not inspected by outer runner",
                   "original_evaluation_metrics_reimplemented": False, "benchmark_grading_performed": False})
        report["planned_instances"] = len(planned)
        for item in planned:
            result = run_one(config, runtime, item, project, staged, config.output / "instances" / f"{item['index']:04d}")
            report["instances"].append(result)
            report["native_launch_attempts"] += int(result["launch_attempted"])
            report["client_attempts"] += int(result["client_attempted"])
            if result["status"] != "recorded_without_benchmark_grade":
                report["stopped_after_unqualified_instance"] = item["index"]
                break
            need(inventory(config.output / "stage") == staged_identities, "staged input changed during case execution")
        report["status"] = "recorded_without_benchmark_grade" if len(report["instances"]) == len(planned) and all(
            row["status"] == "recorded_without_benchmark_grade" for row in report["instances"]) else "partial"
    except BaseException as error:
        report["errors"].append({"type": type(error).__name__})
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            report["interrupted"] = True
    finally:
        runtime.settle_owned_jobs()
        try:
            report["original_inputs_unchanged"] = originals is not None and all(digest(Path(path)) == identity for path, identity in originals.items())
            report["original_source_tree_membership_unchanged"] = identities is not None and inventory(config.source_root) == identities
            report["staged_inputs_unchanged"] = staged_identities is not None and inventory(config.output / "stage") == staged_identities
            if dependency_receipt is not None:
                report["dependency_inputs_unchanged"] = runtime.dependencies(config) == dependency_receipt
            if originals is not None and not (report["original_inputs_unchanged"] and report["staged_inputs_unchanged"]
                                              and report.get("dependency_inputs_unchanged") is True and report["original_source_tree_membership_unchanged"]):
                report["status"] = "failed_preservation"
        except (OSError, ValueError) as error:
            report.update(status="failed_preservation", preservation_error_type=type(error).__name__)
        report["unattempted_instances"] = max(0, report.get("planned_instances", 0) - len(report["instances"]))
        report["finished_at_utc"] = now()
        report["files"] = inventory(config.output)
        write_json(config.output / "result.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--case", action="append", dest="selectors", default=[])
    parser.add_argument("--samples", type=int)
    parser.add_argument("--interpreter", type=Path)
    args = parser.parse_args(argv)
    workspace = Path(__file__).resolve().parents[2]
    config = Config(workspace, args.output.resolve(), workspace / "external/agentops-c806b7f1",
                    workspace / "docs/research/source-evidence/agentops-local-archive-v1/ingestion.json",
                    workspace / "runs/upstream-agentops-cases/v1/application/cases.json",
                    workspace / "runs/upstream-agentops-cases/v1/result.json",
                    (args.interpreter or workspace / "external/runtime-agentops-v2-recovery-2/venv/Scripts/python.exe").resolve(),
                    args.model, tuple(args.selectors), args.samples)
    result = run(config)
    print(json.dumps({key: result[key] for key in ("schema_version", "status", "native_launch_attempts", "client_attempts", "native_upstream_case_grades")}))
    return 0 if result["status"] == "recorded_without_benchmark_grade" else 1


if __name__ == "__main__":
    raise SystemExit(main())
