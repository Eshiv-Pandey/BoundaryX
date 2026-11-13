"""Narrow final-app interception at original common.server.uvicorn.run.

Accepts already imported, source-bound modules. It performs no original import,
service start, credential/model operation, alternate server construction or
router/middleware replacement. Original Server ownership is a separate adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import sys

from .ap2_hp_original_binding_v1 import BindingError, SourceBinding, need
from .ap2_hp_passive_capture_v1 import PassiveAsgiCapture
from .ap2_hp_reference_execution_v1 import typed_equal

PORTS = {"merchant": 8001, "credentials": 8002, "processor": 8003}


class FinalAppUvicornProxy:
    def __init__(self, original, original_run, caller_code, caller_globals, port, sink):
        self.original, self.original_run = original, original_run
        self.caller_code, self.caller_globals = caller_code, caller_globals
        self.port, self.sink = port, sink
        self.captures = []
        self.active_runs = 0
        self.calls_seen = 0
        self.observation_errors = []

    def __getattr__(self, name):
        return getattr(self.original, name)

    def run(self, app, **kwargs):
        frame = sys._getframe(1)
        need(frame.f_code is self.caller_code and frame.f_globals is self.caller_globals
             and frame.f_locals.get("app") is app,
             "Only the exact original final-app call site is supported")
        need(typed_equal(kwargs, {"host": "127.0.0.1", "port": self.port, "log_level": "info", "timeout_keep_alive": 120}),
             "Original Uvicorn call fields differ")
        need(not self.calls_seen and not self.active_runs, "Final application capture is once-only")
        self.calls_seen += 1
        observed = app
        try:
            observed = PassiveAsgiCapture(app, self.sink)
            self.captures.append(observed)
        except BaseException as error:
            self.observation_errors.append({"error_type": type(error).__name__})
        self.active_runs += 1
        try:
            return self.original_run(observed, **kwargs)
        finally:
            self.active_runs -= 1


@dataclass
class FinalAppBindingLease:
    source: object
    server_module: object = field(repr=False)
    original_uvicorn: object = field(repr=False)
    uvicorn_main_module: object = field(repr=False)
    proxy: FinalAppUvicornProxy = field(repr=False)
    installed: bool = False
    restored: bool = False
    error: object = field(default=None, repr=False)

    def install(self):
        need(not self.installed and not self.restored, "Final app binding lease is once-only")
        try:
            self.source.verify_unchanged()
            self.source.source_module("common.server", "common/server.py", self.server_module)
            self.source.environment_module("uvicorn", "uvicorn/__init__.py", self.original_uvicorn)
            self.source.environment_module("uvicorn.main", "uvicorn/main.py", self.uvicorn_main_module, symbols={"run"})
            need(self.original_uvicorn.__dict__.get("run") is self.proxy.original_run
                 and self.uvicorn_main_module.__dict__.get("run") is self.proxy.original_run,
                 "Original Uvicorn run authority changed before installation")
            need(self.server_module.__dict__.get("uvicorn") is self.original_uvicorn,
                 "Original server-local Uvicorn alias changed")
            self.server_module.__dict__["uvicorn"] = self.proxy
            self.installed = True
        except BaseException as error:
            self.error = error
            try:
                self.restore()
            except BaseException as restoration_error:
                self.error = restoration_error
        return self

    def restore(self):
        if self.restored:
            return True
        if self.proxy.active_runs:
            self.error = BindingError("Original Uvicorn run remains active; binding authority retained")
            return False
        try:
            current = self.server_module.__dict__.get("uvicorn")
            if current is self.proxy:
                self.server_module.__dict__["uvicorn"] = self.original_uvicorn
            elif current is not self.original_uvicorn:
                self.error = BindingError("Server-local alias interference; binding authority retained")
                return False
        except BaseException as error:
            self.error = error
            return False
        self.restored = True
        return True

    def report(self):
        return {"status": "original_final_app_alias_restored" if self.restored else
                "original_final_app_capture_installed" if self.installed else "not_installed",
                "capture_placement": "original run_agent_blocking after original builder and middleware; uvicorn.run app argument",
                "captures": [capture.report() for capture in self.proxy.captures],
                "placement_observation_errors": list(self.proxy.observation_errors),
                "active_original_runs": self.proxy.active_runs,
                "original_final_app_calls_seen": self.proxy.calls_seen,
                "restoration_authority_retained": not self.restored,
                "original_server_authority_retained": False,
                "graceful_server_stop_installed": False,
                "durable_capture_installed": False,
                "transport_peer_ownership_verified": False,
                "native_qualification_established": False,
                "transitive_sdk_fidelity_verified": False,
                "error_type": type(self.error).__name__ if self.error is not None else None}


def make_final_app_binding(source, server_module, uvicorn_module, uvicorn_main_module, *, role, sink=None):
    need(type(source) is SourceBinding, "Validated original source binding object required")
    need(role in PORTS, "Original service role required")
    source.verify_unchanged()
    source.source_module("common.server", "common/server.py", server_module)
    source.environment_module("uvicorn", "uvicorn/__init__.py", uvicorn_module)
    source.environment_module("uvicorn.main", "uvicorn/main.py", uvicorn_main_module, symbols={"run"})
    original_run = uvicorn_main_module.__dict__["run"]
    need(server_module.__dict__["uvicorn"] is uvicorn_module and uvicorn_module.__dict__["run"] is original_run,
         "Exact original Uvicorn module/run alias required")
    proxy = FinalAppUvicornProxy(uvicorn_module, original_run,
                               server_module.__dict__["run_agent_blocking"].__code__,
                               server_module.__dict__, PORTS[role], sink)
    return FinalAppBindingLease(source, server_module, uvicorn_module, uvicorn_main_module, proxy)
