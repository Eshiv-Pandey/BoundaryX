"""Retain only the Server constructed by the already imported original run.

No original module/SDK is imported and no server, thread, signal or process is
started here. The caller supplies source-bound modules after its native gates.
"""
from __future__ import annotations

import ast
import builtins
import contextlib
from dataclasses import dataclass, field
import functools
import marshal
import sys
import threading
import types

from .ap2_hp_final_asgi_binding_v1 import FinalAppBindingLease
from .ap2_hp_original_binding_v1 import (
    BindingError, SourceBinding, _codes, _default_equal, _verify_function,
    digest, need, read, regular, verify_module,
)


def verify_class(module, name, path, raw, class_name):
    """Compile-only proof of the three reviewed original descriptor patterns."""
    verify_module(module, name, path, raw, symbols=set())
    namespace = module.__dict__
    tree = ast.parse(raw, filename=str(path))
    definitions = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
    need(len(definitions) == 1, "Unique original runtime class required")
    node, cls = definitions[0], namespace.get(class_name)
    need(type(cls) is type and cls.__module__ == name and cls.__qualname__ == class_name,
         "Original runtime class identity differs")
    need(not node.bases and not node.keywords and not node.decorator_list and cls.__bases__ == (object,),
         "Unreviewed runtime class base/metaclass/decorator")
    declared = set()
    metadata = {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__", "__annotations__",
                "__annotate__", "__annotate_func__", "__static_attributes__", "__firstlineno__"}
    for definition in node.body:
        if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            declared.add(definition.name)
            actual = cls.__dict__.get(definition.name)
            decorators = definition.decorator_list
            kind = None
            if decorators:
                need(len(decorators) == 1, "Unreviewed runtime method decorators")
                decorator = decorators[0]
                if isinstance(decorator, ast.Name) and decorator.id == "property":
                    need(namespace.get("property", builtins.property) is builtins.property
                         and type(actual) is builtins.property and actual.fset is None and actual.fdel is None,
                         "Original builtin property descriptor differs")
                    actual, kind = actual.fget, "property"
                elif (isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Name)
                      and decorator.value.id == "functools" and decorator.attr == "cached_property"):
                    need(namespace.get("functools") is functools and type(actual) is functools.cached_property
                         and actual.attrname == definition.name
                         and set(actual.__dict__) <= {"func", "attrname", "__doc__", "__module__"},
                         "Original cached-property descriptor differs")
                    actual, kind = actual.func, "cached_property"
                elif (isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Name)
                      and decorator.value.id == "contextlib" and decorator.attr == "contextmanager"):
                    need(namespace.get("contextlib") is contextlib and type(actual) is types.FunctionType,
                         "Original contextmanager wrapper differs")
                    wrapped = actual.__dict__.get("__wrapped__")
                    helpers = [code for code in _codes(contextlib.contextmanager.__code__)
                               if code.co_qualname == "contextmanager.<locals>.helper"]
                    need(len(helpers) == 1 and marshal.dumps(actual.__code__) == marshal.dumps(helpers[0])
                         and actual.__globals__ is contextlib.__dict__
                         and actual.__defaults__ is None and actual.__kwdefaults__ is None
                         and actual.__code__.co_freevars == ("func",) and actual.__closure__ is not None
                         and len(actual.__closure__) == 1 and actual.__closure__[0].cell_contents is wrapped,
                         "Original contextmanager code/globals/closure differs")
                    actual, kind = wrapped, "contextmanager"
                else:
                    raise BindingError("Unreviewed runtime method decorator")
            need(type(actual) is types.FunctionType and regular(actual.__code__.co_filename) == path.resolve(),
                 "Original runtime method filename differs")
            compiled = compile(raw, actual.__code__.co_filename, "exec", dont_inherit=True, optimize=0)
            matching = [code for code in _codes(compiled) if code.co_qualname == class_name + "." + definition.name]
            need(len(matching) == 1, "Unique original runtime method code required")
            _verify_function(actual, definition, matching[0], namespace, cls)
            if kind in ("property", "cached_property"):
                need(cls.__dict__[definition.name].__doc__ == actual.__doc__, "Original descriptor doc binding differs")
        elif isinstance(definition, ast.Expr) and isinstance(definition.value, ast.Constant) and type(definition.value.value) is str:
            continue
        else:
            raise BindingError("Unreviewed runtime class body")
    need(set(cls.__dict__) <= declared | metadata, "Original runtime class member footprint differs")
    return cls


def runtime_classes(source, main_module, config_module, server_module):
    source.verify_unchanged()
    source.environment_module("uvicorn.main", "uvicorn/main.py", main_module, symbols={"run"})
    classes = {}
    for name, suffix, module, names in (
        ("uvicorn.config", "uvicorn/config.py", config_module, ("Config",)),
        ("uvicorn.server", "uvicorn/server.py", server_module, ("Server", "ServerState")),
    ):
        path = source.environment_root / "Lib/site-packages" / suffix
        raw = read(path)
        need(digest(raw) == source.environment_files.get("Lib/site-packages/" + suffix),
             "Original runtime class source differs from installed receipt")
        for class_name in names:
            classes[class_name] = verify_class(module, name, path, raw, class_name)
    return classes


class OriginalServerFactory:
    def __init__(self, lease):
        self.lease = lease

    def __call__(self, *args, **kwargs):
        return self.lease.construct(sys._getframe(1), args, kwargs)


def method_names(cls):
    # cached_property legitimately writes its result under its own name.
    return {key for key, value in cls.__dict__.items() if type(value) is types.FunctionType}


@dataclass
class OriginalServerOwnerLease:
    source: SourceBinding
    final: FinalAppBindingLease
    main_module: object = field(repr=False)
    config_module: object = field(repr=False)
    server_module: object = field(repr=False)
    classes: dict = field(repr=False)
    original_run: object = field(repr=False)
    run_code: object = field(repr=False)
    factory: object = field(default=None, repr=False)
    server: object = field(default=None, repr=False)
    config: object = field(default=None, repr=False)
    capture: object = field(default=None, repr=False)
    original_app: object = field(default=None, repr=False)
    config_fields: dict = field(default_factory=dict, repr=False)
    installed: bool = False
    restored: bool = False
    constructing: bool = False
    attempts: int = 0
    stop_requests: int = 0
    error: object = field(default=None, repr=False)
    construction_error: object = field(default=None, repr=False)
    lock: object = field(default_factory=threading.RLock, repr=False)

    def validate(self, expected_factory):
        checked = runtime_classes(self.source, self.main_module, self.config_module, self.server_module)
        need(all(checked[key] is value for key, value in self.classes.items()), "Original runtime class authority changed")
        main, config, server = self.main_module.__dict__, self.config_module.__dict__, self.server_module.__dict__
        need(main.get("run") is self.original_run and self.original_run.__code__ is self.run_code
             and self.original_run.__globals__ is main and main.get("Server") is expected_factory
             and main.get("Config") is self.classes["Config"] and config.get("Config") is self.classes["Config"]
             and server.get("Server") is self.classes["Server"] and server.get("ServerState") is self.classes["ServerState"]
             and server.get("Config") is self.classes["Config"], "Original Config/Server/run aliases differ")
        need(self.final.installed and not self.final.restored
             and self.final.uvicorn_main_module is self.main_module
             and self.final.source is self.source and self.final.proxy.original_run is self.original_run
             and self.final.server_module.__dict__.get("uvicorn") is self.final.proxy
             and self.final.original_uvicorn.__dict__.get("run") is self.original_run
             and self.final.original_uvicorn.__dict__.get("Config") is self.classes["Config"]
             and self.final.original_uvicorn.__dict__.get("Server") is self.classes["Server"],
             "Final application lease or original Uvicorn aliases differ")

    def install(self):
        with self.lock:
            need(not self.installed and not self.restored, "Original Server owner is once-only")
            try:
                self.validate(self.classes["Server"])
                need(not self.final.proxy.active_runs and not self.final.proxy.calls_seen,
                     "Server ownership must install before the original run")
                self.main_module.__dict__["Server"] = self.factory
                self.installed = True
            except BaseException as error:
                self.error = error
                self.restore()
        return self

    def construct(self, frame, args, kwargs):
        with self.lock:
            try:
                return self._construct(frame, args, kwargs)
            except BaseException as error:
                self.error = error
                raise

    def _construct(self, frame, args, kwargs):
        with self.lock:
            need(self.installed and not self.restored, "Original Server owner is not installed")
            self.validate(self.factory)
            need(frame.f_code is self.run_code and frame.f_globals is self.main_module.__dict__
                 and not args and set(kwargs) == {"config"} and frame.f_locals.get("config") is kwargs["config"],
                 "Only original run's Server(config=config) call site is supported")
            need(not self.attempts and not self.constructing and self.final.proxy.active_runs == 1
                 and self.final.proxy.calls_seen == 1 and len(self.final.proxy.captures) == 1
                 and not self.final.proxy.observation_errors, "One active captured original app is required")
            config = kwargs["config"]
            need(type(config) is self.classes["Config"], "Exact original Config instance required")
            capture = self.final.proxy.captures[0]
            need(frame.f_locals.get("app") is capture and config.__dict__.get("app") is capture,
                 "Original Config does not contain the captured final app")
            expected = {"host": "127.0.0.1", "port": self.final.proxy.port, "timeout_keep_alive": 120,
                        "reload": False, "workers": 1, "uds": None, "fd": None, "factory": False}
            need(all(_default_equal(config.__dict__.get(key), value) for key, value in expected.items())
                 and not set(config.__dict__) & method_names(self.classes["Config"]),
                 "Original single-server Config fields or callable overrides differ")
            self.attempts += 1
            self.constructing = True
            try:
                instance = self.classes["Server"](*args, **kwargs)
                if type(instance) is self.classes["Server"]:
                    # Keep exact construction authority even if its state is
                    # contrary evidence. No run/stop eligibility follows.
                    self.config, self.server, self.capture, self.original_app = config, instance, capture, capture.app
                    self.config_fields = expected
                need(type(instance) is self.classes["Server"] and instance.__dict__.get("config") is config
                     and instance.__dict__.get("started") is False and instance.__dict__.get("should_exit") is False
                     and instance.__dict__.get("force_exit") is False,
                     "Original fresh Server instance differs")
                return instance
            except BaseException as error:
                self.construction_error = error
                raise
            finally:
                self.constructing = False

    def request_graceful_stop(self):
        """Set only the retained original instance's should_exit flag."""
        with self.lock:
            try:
                need(self.installed and not self.restored, "Original Server ownership is inactive")
                self.validate(self.factory)
                need(self.server is not None and self.construction_error is None
                     and not self.constructing and self.final.proxy.active_runs == 1,
                     "Original retained Server must have an active run")
                need(type(self.server) is self.classes["Server"] and self.server.__dict__.get("config") is self.config
                     and self.config.__dict__.get("app") is self.capture
                     and len(self.final.proxy.captures) == 1 and self.final.proxy.captures[0] is self.capture
                     and self.capture.app is self.original_app,
                     "Retained original Server/Config/app identity changed")
                need(all(_default_equal(self.config.__dict__.get(key), value)
                         for key, value in self.config_fields.items())
                     and not set(self.config.__dict__) & method_names(self.classes["Config"]),
                     "Retained original Config fields or methods changed")
                need(not set(self.server.__dict__) & method_names(self.classes["Server"]),
                     "Original Server instance method override detected")
                need(self.server.__dict__.get("force_exit") is False
                     and type(self.server.__dict__.get("should_exit")) is bool,
                     "Original graceful-exit flag state differs")
                if self.server.__dict__.get("started") is not True:
                    return False
                self.server.should_exit = True
                self.stop_requests += 1
                return True
            except BaseException as error:
                self.error = error
                return False

    def restore(self):
        with self.lock:
            if self.restored:
                return True
            if self.constructing or self.final.proxy.active_runs:
                self.error = BindingError("Original delegated run is active; Server alias authority retained")
                return False
            current = self.main_module.__dict__.get("Server")
            if current is self.factory:
                self.main_module.__dict__["Server"] = self.classes["Server"]
            elif current is not self.classes["Server"]:
                self.error = BindingError("Server factory alias interference; authority retained")
                return False
            self.restored = True
            return True

    def report(self):
        return {"schema_version": "ap2-hp-original-server-owner/1",
                "status": "original_server_alias_restored" if self.restored else "installed" if self.installed else "not_installed",
                "original_server_retained": self.server is not None, "constructor_attempts": self.attempts,
                "graceful_stop_requests": self.stop_requests, "construction_active": self.constructing,
                "delegated_run_inactive_observed": bool(self.attempts and not self.constructing and not self.final.proxy.active_runs),
                "restoration_authority_retained": not self.restored,
                "error_type": type(self.error).__name__ if self.error is not None else None,
                "constructor_error_type": type(self.construction_error).__name__ if self.construction_error is not None else None,
                "alternate_server_constructed": False, "signal_sent": False, "force_exit_requested": False,
                "process_exit_proven": False, "native_job_ownership_verified": False,
                "tcp_peer_ownership_verified": False, "graceful_shutdown_proven": False,
                "native_qualification_established": False, "transitive_sdk_fidelity_verified": False}


def make_original_server_owner(source, final_lease, main_module, config_module, server_module):
    need(type(source) is SourceBinding and type(final_lease) is FinalAppBindingLease,
         "Exact source and final application leases required")
    classes = runtime_classes(source, main_module, config_module, server_module)
    original_run = main_module.__dict__["run"]
    lease = OriginalServerOwnerLease(source, final_lease, main_module, config_module, server_module,
                                     classes, original_run, original_run.__code__)
    lease.factory = OriginalServerFactory(lease)
    lease.validate(classes["Server"])
    return lease
