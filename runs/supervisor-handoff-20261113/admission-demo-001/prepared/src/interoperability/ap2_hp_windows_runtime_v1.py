"""Concrete owned Windows startup adapter; no launch or key access by import."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import sys
import time
import types


def load_exact(reference):
    path = Path(reference["path"])
    import hashlib
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("Reviewed helper changed before execution")
    module = types.ModuleType("_ap2_pinned_" + path.stem)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


class WindowsOwner:
    def __init__(self, root):
        self.job = None
        self.stdout = (root / "stdout.bin").open("xb")
        try:
            self.stderr = (root / "stderr.bin").open("xb")
        except BaseException:
            self.stdout.close()
            raise


class WindowsRuntime:
    def __init__(self):
        if sys.platform != "win32":
            raise ValueError("Native Windows runtime required")
        self.plan = None

    def now(self):
        return datetime.now(timezone.utc)

    def bind_plan(self, plan):
        self.plan = plan

    def sleep(self, seconds):
        time.sleep(seconds)

    def memory_sample(self):
        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [(name, ctypes.c_uint64) for name in (
                "total_physical", "available_physical", "total_commit", "available_commit", "total_virtual", "available_virtual", "available_extended")]
        status = Status()
        status.length = ctypes.sizeof(status)
        function = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
        function.argtypes, function.restype = [ctypes.POINTER(Status)], ctypes.c_int
        if not function(ctypes.byref(status)):
            raise OSError("Memory status observation failed")
        return {"observed_at_utc": self.now().isoformat(), "monotonic_ns": time.monotonic_ns(),
                "physical_available_bytes": int(status.available_physical), "commit_available_bytes": int(status.available_commit)}

    def occupied_ports(self, ports):
        if self.plan is None:
            raise ValueError("Validated launch plan must be bound before owner-table access")
        module = load_exact(self.plan["tcp_helper"])
        return [row for row in module.owner_table() if row["state"] == 2 and row["local_port"] in ports]

    def make_owner(self, service, root):
        return WindowsOwner(root)

    def launch_bootstrap(self, owner, plan, service, root):
        self.plan = plan
        expected = Path(__file__).absolute().parent / "ap2_hp_native_gate_v1.py"
        if Path(plan["bootstrap_helper"]["path"]) != expected:
            raise ValueError("Runtime cannot execute an arbitrary plan-selected gate helper")
        gate_helper = load_exact(plan["bootstrap_helper"])
        gate_helper.validate_plan(plan, self.now())
        gate = gate_helper.strict_json((root / "prelaunch.json").read_bytes())
        gate_helper.immediate_check(gate, gate_helper.launch_binding(plan, service["role"]), self.memory_sample(), self.now())
        try:
            owner.job = load_exact(plan["owned_job_helper"]).WindowsJob()
        except BaseException as error:
            owner.job = getattr(error, "owned_job", None)
            raise
        argv = [plan["interpreter"]["path"], "-I", "-S", "-B", plan["bootstrap_script"]["path"],
                "--stage", "before-key", "--plan", str(Path(plan["output_root"]) / "plan.json"), "--role", service["role"],
                "--job-handle", str(int(owner.job.job))]
        handle = int(owner.job.job)
        inherited = os.get_handle_inheritable(handle)
        try:
            os.set_handle_inheritable(handle, True)
            owner.job.launch(argv, str(Path(plan["output_root"])), owner.stdout, owner.stderr)
        finally:
            if not owner.job.closed:
                os.set_handle_inheritable(handle, inherited)

    def wait_original_readiness(self, owner, plan, service, root):
        self.plan = plan
        expected_gate = Path(__file__).absolute().parent / "ap2_hp_native_gate_v1.py"
        if Path(plan["bootstrap_helper"]["path"]) != expected_gate:
            raise ValueError("Runtime cannot execute an arbitrary plan-selected gate helper")
        helper = load_exact(plan["bootstrap_helper"])
        helper.validate_plan(plan, self.now())
        tcp = load_exact(plan["tcp_helper"])
        binding = helper.launch_binding(plan, service["role"])
        expected_path = Path(plan["source_root"]) / "code/samples/python/src" / service["module"].replace(".", "/") / "agent.json"
        expected = helper.strict_json(expected_path.read_bytes())
        deadline = time.monotonic() + 120
        last_error = None
        client_gate = None
        while time.monotonic() < deadline:
            if owner.job.poll() is not None:
                raise ValueError("Owned bootstrap exited before original discovery readiness")
            marker = root / "bootstrap.before-original.json"
            if marker.is_file():
                value = helper.strict_json(marker.read_bytes())
                if value.get("status") != "guarded_before_original_import" or value.get("binding") != binding or type(value.get("pid")) is not int:
                    raise ValueError("Native original-process bootstrap identity differs")
                if client_gate is None:
                    client_gate = helper.collect_gate(self, binding)
                    helper.publish(root / "client-prelaunch.json", client_gate)
                    helper.immediate_check(client_gate, binding, self.memory_sample(), self.now())
                connection = http.client.HTTPConnection("127.0.0.1", service["port"], timeout=2)
                try:
                    connection.connect()
                    ownership = tcp.verify_connection(connection.sock, value["pid"], owner.job)
                    helper.immediate_check(client_gate, binding, self.memory_sample(), self.now())
                    connection.request("GET", service["rpc_path"] + "/.well-known/agent-card.json")
                    response = connection.getresponse()
                    raw = response.read(2 * 1024 * 1024 + 1)
                    if response.status == 200 and len(raw) <= 2 * 1024 * 1024:
                        actual = helper.strict_json(raw)
                        if all(actual.get(key) == expected.get(key) for key in ("name", "url", "protocolVersion")):
                            record = {"binding": binding, "owned_connected_original_card": True,
                                      "native_pid": value["pid"], "ownership": ownership,
                                      "status": response.status, "card": actual,
                                      "response_sha256": helper.sha(raw), "source_authentication_proven": False}
                            helper.publish(root / "original-readiness.json", record)
                            (root / "original-card.body.bin").write_bytes(raw)
                            return record
                except (OSError, ValueError, http.client.HTTPException) as error:
                    last_error = type(error).__name__
                finally:
                    connection.close()
            time.sleep(.1)
        raise ValueError("Original discovery readiness timed out: " + str(last_error))

    def stop_owned(self, owner):
        if owner.job is None:
            owner.stdout.close(); owner.stderr.close()
            return {"launch_attempted": False, "process_created": False, "handles_closed": True, "job_empty_observed": False, "errors": []}
        result = owner.job.finish(graceful_seconds=0, forced_seconds=5)
        result["launch_attempted"] = owner.job.launch_attempted
        result["process_created"] = owner.job.created
        if result["handles_closed"]:
            owner.stdout.close(); owner.stderr.close()
        return result
