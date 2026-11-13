"""Owned source-bound integration of raw final-app observation and Server.

Only authored dependencies and the standard library are imported. Native
bootstrap must supply already imported original modules after its own gates.
No alternative Config, Server, event loop, task, process or signal is created.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import sys
import threading

from .ap2_hp_durable_observer_v1 import DurableRecorder, Limits, RawAsgiCapture, StreamSink
from .ap2_hp_final_asgi_binding_v1 import FinalAppBindingLease, PORTS
from .ap2_hp_original_binding_v1 import BindingError, SourceBinding, need
from .ap2_hp_original_server_owner_v1 import OriginalServerOwnerLease, make_original_server_owner
from .ap2_hp_reference_execution_v1 import typed_equal


class ServiceSetupError(BindingError):
    def __init__(self, service, reason):
        self.service = service
        super().__init__(reason)


class RawFinalAppUvicornProxy:
    """Bind a prepared raw wrapper only at the exact original final call."""
    def __init__(self, original, original_run, caller_code, caller_globals, port, sink):
        need(type(sink) is StreamSink, "Owned raw observation sink required")
        self.original, self.original_run = original, original_run
        self.caller_code, self.caller_globals = caller_code, caller_globals
        self.port, self.sink = port, sink
        # Construction failure precedes original start and alias installation.
        # Binding .app later is a plain assignment, not another constructor.
        self.raw_capture = RawAsgiCapture(None, sink)
        self.captures = [self.raw_capture]
        self.active_runs = self.calls_seen = 0
        self.observation_errors = []
        self.bound = False
        self.run_error = None
        self.lock = threading.RLock()

    def __getattr__(self, name):
        return getattr(self.original, name)

    def run(self, app, **kwargs):
        frame = sys._getframe(1)
        with self.lock:
            need(frame.f_code is self.caller_code and frame.f_globals is self.caller_globals
                 and frame.f_locals.get("app") is app, "Exact original final-app call site required")
            need(typed_equal(kwargs, {"host": "127.0.0.1", "port": self.port, "log_level": "info", "timeout_keep_alive": 120}),
                 "Original Uvicorn fields differ")
            need(not self.calls_seen and not self.active_runs and not self.bound
                 and len(self.captures) == 1 and self.captures[0] is self.raw_capture
                 and self.raw_capture.app is None and typed_equal(self.raw_capture.witness(), {
                     "source_complete": True, "active_operations": 0, "attempted_records": 0}),
                 "Fresh once-only raw final-app capture required")
            self.raw_capture.app = app
            self.bound = True
            self.calls_seen = self.active_runs = 1
        try:
            return self.original_run(self.raw_capture, **kwargs)
        except BaseException as error:
            self.run_error = error
            raise
        finally:
            with self.lock:
                self.active_runs = 0


def make_raw_final_app_binding(source, common_server, uvicorn_module, main_module, *, role, sink):
    """Return the exact frozen lease class with the new raw-compatible proxy."""
    need(type(source) is SourceBinding and type(role) is str and role in PORTS,
         "Exact source binding and original role required")
    need(type(sink) is StreamSink and sink.name == role
         and sink.recorder.streams[role]["kind"] == "raw_asgi", "Matching role raw stream required")
    source.verify_unchanged()
    source.source_module("common.server", "common/server.py", common_server)
    source.environment_module("uvicorn", "uvicorn/__init__.py", uvicorn_module)
    source.environment_module("uvicorn.main", "uvicorn/main.py", main_module, symbols={"run"})
    original_run = main_module.__dict__["run"]
    need(common_server.__dict__.get("uvicorn") is uvicorn_module
         and uvicorn_module.__dict__.get("run") is original_run, "Original Uvicorn module/run aliases required")
    proxy = RawFinalAppUvicornProxy(uvicorn_module, original_run,
        common_server.__dict__["run_agent_blocking"].__code__, common_server.__dict__, PORTS[role], sink)
    return FinalAppBindingLease(source, common_server, uvicorn_module, main_module, proxy)


@dataclass
class OwnedObservedService:
    source: object = field(repr=False)
    role: str
    recorder: object = field(default=None, repr=False)
    final: object = field(default=None, repr=False)
    owner: object = field(default=None, repr=False)
    modules: dict = field(default_factory=dict, repr=False)
    setup_error: object = field(default=None, repr=False)
    start_error: object = field(default=None, repr=False)
    start_result: object = field(default=None, repr=False)
    cleanup_errors: list = field(default_factory=list, repr=False)
    control_errors: list = field(default_factory=list, repr=False)
    install_attempted: bool = False
    start_attempted: bool = False
    starting: bool = False
    start_returned: bool = False
    source_finished: bool = False
    cleanup_complete: bool = False
    resources_settled: bool = False
    lock: object = field(default_factory=threading.RLock, repr=False)

    def _cleanup_error(self, stage, error):
        if len(self.cleanup_errors) < 64:
            self.cleanup_errors.append((stage, error))

    def _control_error(self, stage, error):
        if len(self.control_errors) < 64:
            self.control_errors.append((stage, error))

    @property
    def installed(self):
        return (self.setup_error is None and type(self.final) is FinalAppBindingLease
                and type(self.owner) is OriginalServerOwnerLease
                and self.final.installed and not self.final.restored
                and self.owner.installed and not self.owner.restored)

    def install(self):
        """Final alias first, original Server factory second, both retained."""
        with self.lock:
            if self.install_attempted:
                return self
            self.install_attempted = True
            if self.setup_error is not None:
                return self
            try:
                need(type(self.recorder) is DurableRecorder and self.recorder.ready
                     and not self.recorder.sealed and type(self.final) is FinalAppBindingLease,
                     "Prepared owned recording and final lease required")
                self.final.install()
                need(self.final.installed and not self.final.restored and self.final.error is None,
                     "Raw final-app alias did not install")
                # Retain the owner before installation can fail or alter alias.
                self.owner = make_original_server_owner(self.source, self.final, self.modules["main"],
                                                        self.modules["config"], self.modules["server"])
                self.owner.install()
                need(self.owner.installed and not self.owner.restored and self.owner.error is None,
                     "Original Server ownership did not install")
            except BaseException as error:
                self.setup_error = error
            return self

    def request_graceful_stop(self):
        with self.lock:
            if not self.installed:
                self._control_error("stop", BindingError("No active installed original Server authority"))
                return False
            try:
                return self.owner.request_graceful_stop()
            except BaseException as error:
                self._control_error("stop", error)
                return False

    def run_start(self, original_start, *args, **kwargs):
        """Delegate the supplied start callable; cleanup never masks its error.

        Original entrypoint identity and native resource/credential/provider
        authorization remain the native bootstrap's separate responsibility.
        """
        self.install()
        with self.lock:
            if self.start_attempted or not callable(original_start) or not self.installed:
                self._control_error("start", BindingError("Fresh installed service and supplied start callable required"))
                self._safe_cleanup()
                raise ServiceSetupError(self, "Original start was not invoked; inspect retained setup/control errors")
            try:
                self.owner.validate(self.owner.factory)
                need(self.final.proxy.calls_seen == 0 and not self.final.proxy.active_runs,
                     "Original run already consumed before service start")
            except BaseException as error:
                self.setup_error = error
                self._safe_cleanup()
                raise ServiceSetupError(self, "Original start was not invoked; source/alias validation failed") from error
            self.start_attempted = self.starting = True
        try:
            result = original_start(*args, **kwargs)
            with self.lock:
                self.start_result, self.start_returned = result, True
            return result
        except BaseException as error:
            # This exact object remains primary even if recording/cleanup fail.
            with self.lock:
                self.start_error = error
            raise
        finally:
            with self.lock:
                self.starting = False
            self._safe_cleanup()

    def _safe_cleanup(self):
        try:
            return self.cleanup()
        except BaseException as error:
            self._cleanup_error("cleanup_call", error)
            return False

    def cleanup(self):
        """Hold the authored raw admission lock through the terminal cutoff.

        Already active operations refuse cleanup; operations admitted after
        the closed interval still preserve their original calls and surface
        as late/incomplete observations. Native quiescence is separate.
        """
        with self.lock:
            capture = self.final.proxy.raw_capture if self.final is not None else None
            if capture is None:
                return self._cleanup_locked()
            with capture._lock:
                return self._cleanup_locked()

    def _cleanup_locked(self):
        """Refuse active original work, then seal, restore aliases and close.

        An incomplete observation may publish only an explicitly partial
        terminal. Resource settlement is separate from successful publication.
        """
        with self.lock:
            proxy = self.final.proxy if self.final is not None else None
            try:
                need(not self.starting and (proxy is None or not proxy.active_runs)
                     and (self.owner is None or not self.owner.constructing), "Original start/run/construction remains active")
                capture = proxy.raw_capture if proxy is not None else None
                need(capture is None or capture.witness()["active_operations"] == 0, "Raw application/IO remains active")
            except BaseException as error:
                self._control_error("cleanup_active", error)
                self.cleanup_complete = self.resources_settled = False
                return False

            observation_finalized = self.recorder is None
            if self.recorder is not None:
                try:
                    need(type(self.recorder) is DurableRecorder and set(self.recorder.streams) == {self.role}
                         and self.recorder.streams[self.role]["kind"] == "raw_asgi", "Owned role stream membership changed")
                    if not self.source_finished:
                        witness = capture.witness() if capture is not None else {
                            "source_complete": False, "active_operations": 0, "attempted_records": 0}
                        witness["source_complete"] = bool(witness["source_complete"] and proxy is not None
                                                          and proxy.bound and proxy.calls_seen == 1)
                        need(self.recorder.finish_stream(self.role, witness), "Final source witness was refused")
                        self.source_finished = True
                    if not self.recorder.published:
                        # Partial output is labelled by the recorder and never
                        # promoted to complete or native-qualified evidence.
                        need(self.recorder.publish(allow_incomplete=True), "Terminal publication failed or remains unavailable")
                    observation_finalized = self.recorder.published
                except BaseException as error:
                    self._cleanup_error("observation_finalize", error)

            owner_restored = self.owner is None
            if self.owner is not None:
                try:
                    owner_restored = self.owner.restore()
                    if not owner_restored:
                        raise BindingError("Original Server alias restoration incomplete")
                except BaseException as error:
                    self._cleanup_error("owner_restore", error)
            final_restored = self.final is None
            if self.final is not None and owner_restored:
                try:
                    final_restored = self.final.restore()
                    if not final_restored:
                        raise BindingError("Raw final-app alias restoration incomplete")
                except BaseException as error:
                    self._cleanup_error("final_restore", error)
            recorder_closed = self.recorder is None
            if self.recorder is not None:
                try:
                    recorder_closed = self.recorder.close()
                    need(recorder_closed, "Owned recorder descriptors did not close")
                except BaseException as error:
                    self._cleanup_error("recorder_close", error)
            self.resources_settled = bool(owner_restored and final_restored and recorder_closed)
            self.cleanup_complete = bool(self.resources_settled and observation_finalized)
            return self.cleanup_complete

    def report(self):
        with self.lock:
            recorder = self.recorder.report() if self.recorder is not None else None
            final = self.final.report() if self.final is not None else None
            owner = self.owner.report() if self.owner is not None else None
            if final is not None:
                # Derived report only; the exact frozen lease/class is intact.
                final = dict(final)
                final["durable_capture_installed"] = bool(self.final.installed and not self.final.restored
                                                         and self.recorder is not None and self.recorder.ready)
                final["raw_final_app_bound"] = self.final.proxy.bound
                final["original_server_authority_retained"] = self.owner is not None and not self.owner.restored
            return {"schema_version": "ap2-hp-owned-observed-service/1", "role": self.role,
                "installed": self.installed, "start_attempted": self.start_attempted, "start_returned": self.start_returned,
                "start_active": self.starting, "original_start_error_type": type(self.start_error).__name__ if self.start_error is not None else None,
                "setup_error_type": type(self.setup_error).__name__ if self.setup_error is not None else None,
                "cleanup_complete": self.cleanup_complete, "resources_settled": self.resources_settled,
                "observation_complete": bool(recorder is not None and recorder["published"]
                                              and recorder["published_complete"] and recorder["observation_complete_current"]),
                "cleanup_errors": [{"stage": stage, "error_type": type(error).__name__} for stage, error in self.cleanup_errors],
                "control_errors": [{"stage": stage, "error_type": type(error).__name__} for stage, error in self.control_errors],
                "recorder": recorder, "final_app": final, "original_server_owner": owner,
                "authority_retained_on_incomplete_cleanup": not self.cleanup_complete,
                "alternate_server_constructed": False, "raw_io_cancelled_by_coordinator": False,
                "process_exit_proven": False, "tcp_peer_ownership_verified": False,
                "transitive_sdk_fidelity_verified": False, "native_qualification_established": False}


def prepare_observed_service(source, common_server, uvicorn_module, main_module, config_module, server_module,
                             *, role, artifact_path, limits=Limits()):
    """Return the same carrier on every post-allocation setup failure."""
    service = OwnedObservedService(source, role, modules={"main": main_module, "config": config_module, "server": server_module})
    try:
        need(type(source) is SourceBinding and type(role) is str and role in PORTS, "Exact source and original service role required")
        service.recorder = DurableRecorder.allocate(artifact_path, {role: "raw_asgi"}, limits=limits)
        need(service.recorder.ready, "Owned recorder allocation incomplete")
        service.final = make_raw_final_app_binding(source, common_server, uvicorn_module, main_module,
                                                  role=role, sink=service.recorder.sink(role))
    except BaseException as error:
        service.setup_error = error
    return service
