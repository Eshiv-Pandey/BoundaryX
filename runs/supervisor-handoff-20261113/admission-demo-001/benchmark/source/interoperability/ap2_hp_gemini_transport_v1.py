"""Per-transmission guards for the pinned synchronous AP2 HP model profile.

Importing this module performs no SDK import, key read, network or native work.
Installation requires reviewed allowance/body bounds and exact loaded methods.
Constructed class bindings alone do not authorize a native installation.
"""
from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import functools
import hashlib
import importlib
import json
from pathlib import Path
import stat
import types
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
MODEL = "gemini-3.1-flash-lite-preview"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent"
ENV_SHA = "4d6efdd2e4003b82517f45aead140a7afd6f1e180b3ce518904d87c96e5adeb5"
ACCOUNTING_SHA = "0475f889a5825626adaec6fc1b2477c15972a9c09138c795343538c3b391fe45"
SOURCES = {
    "google/genai/_api_client.py": "3f1a7c22fc01c870511880bb78f27b790d4c7104b2e8998611fa6547c72acce4",
    "httpx/_client.py": "c43f941baefe58c91e96d00039e1868fe719d91453026d7db1647194563bff8d",
    "httpx/_transports/default.py": "03379a454c95c0271c4f2c8d25ec437f49f57457f3cf2769748420bf0ecf2e79",
    "aiohttp/client_reqrep.py": "75153bcadc900440fad5607bae0b1852a736c17370505f52c9050cbdd39904ca",
}
_INVOCATION = ContextVar("ap2_hp_original_sync_provider_invocation", default=None)
_LIVE_GUARD = None
NATIVE_CLIENT_CONSTRUCTION_VERIFIED = False


class TransportRefused(ValueError):
    pass


def need(value, reason):
    if not value:
        raise TransportRefused(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key refused")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(TransportRefused("Nonfinite JSON refused")))


def regular(path):
    path = Path(path)
    need(path.is_absolute(), "Absolute source/evidence path required")
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Linked/reparse source or evidence refused")
    need(path.is_file(), "Regular source/evidence file required")
    return path


def read_ref(ref):
    need(type(ref) is dict and set(ref) == {"path", "sha256"}, "Exact artifact reference required")
    path = regular(ref["path"])
    need(path.stat().st_size <= 32 * 1024 * 1024, "Oversized guard artifact")
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == ref["sha256"], "Guard artifact bytes changed")
    return raw


def provider_url(value):
    """Recognize the two SDK provider host families, never inspect headers."""
    host = urlsplit(str(value)).hostname or ""
    return (host == "generativelanguage.googleapis.com" or host == "aiplatform.googleapis.com"
            or host.endswith((".aiplatform.googleapis.com", "-aiplatform.googleapis.com")))


def headroom_before_sdk():
    """Immediate independent Windows observation; the caller supplies timed gates."""
    import sys
    import ctypes
    from ctypes import wintypes
    need(sys.platform == "win32", "Native transport installation requires the gated Windows runtime")
    class Memory(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *[(name, ctypes.c_ulonglong) for name in
                      ("total_physical", "available_physical", "total_commit", "available_commit",
                       "total_virtual", "available_virtual", "extended_virtual")]]
    value = Memory()
    value.length = ctypes.sizeof(value)
    need(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)), "Windows headroom observation failed")
    need(value.available_physical >= 1024**3 and value.available_commit >= 2 * 1024**3,
         "Immediate headroom below the unchanged physical/commit minima")
    return {"physical_available_bytes": value.available_physical, "commit_available_bytes": value.available_commit,
            "observed_at_utc": datetime.now(timezone.utc).isoformat()}


def code_identity(code):
    def constant(value):
        if isinstance(value, types.CodeType):
            return {"code": code_identity(value)}
        if type(value) is bytes:
            return {"type": "bytes", "hex": value.hex()}
        if type(value) is tuple:
            return {"type": "tuple", "values": [constant(item) for item in value]}
        if type(value) is frozenset:
            return {"type": "frozenset", "values": sorted((constant(item) for item in value), key=lambda item: encoded(item))}
        need(value is None or type(value) in (bool, int, float, str), "Unsupported code constant")
        return {"type": type(value).__name__, "value": value}
    return {"name": code.co_name, "qualname": code.co_qualname, "filename": code.co_filename,
            "firstline": code.co_firstlineno, "args": [code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount],
            "flags": code.co_flags, "bytecode": code.co_code.hex(), "constants": [constant(v) for v in code.co_consts],
            "exception_table": code.co_exceptiontable.hex(), "stacksize": code.co_stacksize,
            "locals": code.co_nlocals, "line_table": code.co_linetable.hex(),
            "names": code.co_names, "variables": code.co_varnames, "free": code.co_freevars, "cells": code.co_cellvars}


def verify_method(cls, name, path, raw, *, defaults=None):
    actual = cls.__dict__.get(name)
    need(type(actual) is types.FunctionType and actual.__code__.co_filename == str(path),
         "Original method origin differs")
    module_code = compile(raw, str(path), "exec", dont_inherit=True)  # Inspect exact source compiler flags.
    class_code = next((item for item in module_code.co_consts
                       if isinstance(item, types.CodeType) and item.co_name == cls.__name__), None)
    need(class_code is not None, "Original class definition absent")
    expected = next((item for item in class_code.co_consts
                     if isinstance(item, types.CodeType) and item.co_name == name), None)
    need(expected is not None and code_identity(actual.__code__) == code_identity(expected),
         "Loaded method differs from exact compiled source")
    need(actual.__kwdefaults__ is None, "Unexpected method keyword defaults")
    if defaults is None:
        need(actual.__defaults__ is None, "Unexpected method defaults")
    else:
        need(type(actual.__defaults__) is tuple and len(actual.__defaults__) == 1
             and actual.__defaults__[0] is False, "Original stream=False default required")
    return actual


class ProviderGuard:
    """Bind already supplied classes; retain original objects and restoration authority."""
    def __init__(self, accounting, ledger, policy_sha256, role, maximum_body_bytes, *, clock=None,
                 client_check=None):
        need(role in {"merchant", "credentials", "processor"}, "Original service role required")
        need(type(maximum_body_bytes) is int and maximum_body_bytes > 0, "Reviewed serialized-body bound required")
        self.accounting, self.ledger, self.policy_sha256 = accounting, Path(ledger), policy_sha256
        self.role, self.maximum_body_bytes = role, maximum_body_bytes
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.client_check = client_check
        self.patches, self.records, self.errors = [], [], []
        self.disabled = False
        self.halt_path = self.ledger.with_name(self.ledger.name + ".transport-halt")

    def _halt(self, error):
        self.disabled = True
        self.errors.append({"error_type": type(error).__name__})
        try:
            with self.halt_path.open("xb") as out:
                out.write(encoded({"status": "transport_accounting_failure", "run_policy_sha256": self.policy_sha256}))
                out.flush()
                import os
                os.fsync(out.fileno())
        except FileExistsError:
            pass
        except BaseException as marker_error:
            self.errors.append({"halt_marker_error_type": type(marker_error).__name__})

    def _reconcile(self, reservation, *, status=None, metadata=None):
        try:
            value = self.accounting.record_provider_result(
                self.ledger, reservation["attempt_id"], expected_policy_sha256=self.policy_sha256,
                usage_metadata=metadata, http_status=status)
            self.records.append({"boundary": "provider_result", **deepcopy(value)})
        except BaseException as error:
            # The committed worst-bound reservation remains. Preserve the original
            # transport result/error, and refuse later attempts across this ledger.
            self._halt(error)

    def _sync_send(self, original, client, request):
        context = _INVOCATION.get()
        if context is None:
            need(not provider_url(request.url), "Provider request outside original guarded invocation")
            return original(client, request)
        guard, expected_client = context
        need(guard is self and client is expected_client, "Provider client/context binding differs")
        need(not self.disabled and not self.halt_path.exists() and not self.halt_path.is_symlink(),
             "Transport accounting is halted")
        need(str(request.url) == ENDPOINT and request.method == "POST", "Unexpected provider endpoint/model/method")
        body = request.content  # Do not consume or materialize an unknown request stream.
        need(type(body) is bytes and len(body) <= self.maximum_body_bytes, "Serialized request bound exceeded")
        reservation = self.accounting.reserve_attempt(
            self.ledger, expected_policy_sha256=self.policy_sha256, role=self.role,
            request_sha256=hashlib.sha256(body).hexdigest(), now=self.clock())
        self.records.append({"boundary": "reserved_before_transmission", **deepcopy(reservation)})
        try:
            response = original(client, request)
        except BaseException:
            self._reconcile(reservation)
            raise
        try:
            raw = response.read()  # Selected original callers are nonstreaming.
        except BaseException:
            self._reconcile(reservation, status=response.status_code)
            try:
                response.close()  # Match HTTPX's nonstreaming read-failure cleanup.
            except BaseException as cleanup_error:
                self._halt(cleanup_error)  # Preserve the original response-read error.
            raise
        metadata = None
        try:
            document = strict_json(raw)
            if type(document) is dict:
                metadata = document.get("usageMetadata")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            pass
        self._reconcile(reservation, status=response.status_code, metadata=metadata)
        return response  # Same HTTPX response, already cached as the original request would read it.

    def _patch(self, cls, name, replacement):
        original = cls.__dict__[name]
        self.patches.append((cls, name, original, replacement))
        setattr(cls, name, replacement)

    def bind_classes(self, api_class, sync_class, async_class, aio_request_class):
        need(not self.patches, "Guard class lease is already consumed")
        original_api = api_class.__dict__["_request_once"]
        original_async_api = api_class.__dict__["_async_request_once"]
        original_sync = sync_class.__dict__["_send_single_request"]
        original_async = async_class.__dict__["_send_single_request"]
        original_aio = aio_request_class.__dict__["send"]
        guard = self

        @functools.wraps(original_api)
        def api_request(client, http_request, stream=False):
            need(stream is False and client.vertexai is False, "Only original synchronous nonstreaming API-key profile")
            if guard.client_check is not None:
                guard.client_check(client._httpx_client)
            token = _INVOCATION.set((guard, client._httpx_client))
            try:
                return original_api(client, http_request, stream)
            finally:
                _INVOCATION.reset(token)

        @functools.wraps(original_async_api)
        async def async_api_request(client, http_request, stream=False):
            raise TransportRefused("Async GenAI requests are outside the original selected HP profile")

        @functools.wraps(original_sync)
        def sync_send(client, request):
            return guard._sync_send(original_sync, client, request)

        @functools.wraps(original_async)
        async def async_send(client, request):
            need(_INVOCATION.get() is None and not provider_url(request.url), "Async provider transmission refused")
            return await original_async(client, request)

        @functools.wraps(original_aio)
        async def aio_send(request, connection):
            need(_INVOCATION.get() is None and not provider_url(request.url), "Async provider transmission refused")
            return await original_aio(request, connection)

        try:
            for cls, name, replacement in (
                (sync_class, "_send_single_request", sync_send),
                (async_class, "_send_single_request", async_send),
                (aio_request_class, "send", aio_send),
                (api_class, "_async_request_once", async_api_request),
                (api_class, "_request_once", api_request),
            ):
                self._patch(cls, name, replacement)
        except BaseException:
            self.restore()
            raise
        return self

    def restore(self):
        remaining = []
        for cls, name, original, replacement in reversed(self.patches):
            try:
                need(cls.__dict__.get(name) is replacement, "Guard alias changed; restoration authority retained")
                setattr(cls, name, original)
            except BaseException:
                remaining.append((cls, name, original, replacement))
        self.patches = list(reversed(remaining))
        return not self.patches

    def report(self):
        return {"schema_version": "ap2-hp-gemini-transport-observation/1", "model": MODEL,
                "records": deepcopy(self.records), "accounting_errors": deepcopy(self.errors),
                "halted_in_this_process": self.disabled, "patch_authority_retained": bool(self.patches),
                "original_request_body_or_headers_stored": False, "native_qualification_established": False}


def install_guard(*, plan, service, configuration_sha256):
    """Native bootstrap entry: refuse missing evidence before any SDK import.

    Required extra usage-receipt refs: accounting_policy and transport_policy.
    Actual project/bound evidence is currently absent; no positive receipt is
    generated by this function or its constructed tests.
    """
    global _LIVE_GUARD
    guard = None
    try:
        need(_LIVE_GUARD is None, "Transport guard installation already consumed")
        need(plan.get("model") == MODEL and service.get("role") in {"merchant", "credentials", "processor"},
             "Exact original model/service profile required")
        need(NATIVE_CLIENT_CONSTRUCTION_VERIFIED is True,
             "Native client construction, aliases and transitive SDK fidelity remain unverified")
        expected_configuration = hashlib.sha256(encoded({key: value for key, value in plan.items()
                                                         if key != "usage_receipt"})).hexdigest()
        need(configuration_sha256 == expected_configuration, "Exact native configuration binding required")
        usage = strict_json(read_ref(plan["usage_receipt"]))
        need(usage.get("run_id") == plan["run_id"] and usage.get("configuration_sha256") == configuration_sha256,
             "Usage receipt is bound to another run/configuration")
        policy_raw = read_ref(usage["accounting_policy"])
        policy = strict_json(policy_raw)
        transport = strict_json(read_ref(usage["transport_policy"]))
        required = {"schema_version", "profile", "model", "run_id", "configuration_sha256",
                    "maximum_serialized_body_bytes", "input_bound_covering_body_verified", "bound_evidence"}
        need(type(transport) is dict and set(transport) == required
             and transport["schema_version"] == "ap2-hp-gemini-sync-transport-policy/1"
             and transport["profile"] == "original_hp_sync_generate_content"
             and transport["model"] == MODEL and transport["run_id"] == plan["run_id"]
             and transport["configuration_sha256"] == configuration_sha256
             and transport["input_bound_covering_body_verified"] is True,
             "Reviewed source/body/token-bound transport policy required")
        maximum = transport["maximum_serialized_body_bytes"]
        need(type(maximum) is int and maximum > 0, "Positive reviewed body-byte bound required")
        need(type(transport["bound_evidence"]) is list and transport["bound_evidence"], "Bound evidence required")
        for ref in transport["bound_evidence"]:
            read_ref(ref)
        accounting_path = ROOT / "src/interoperability/ap2_hp_gemini_usage_v1.py"
        accounting_raw = read_ref({"path": str(accounting_path), "sha256": ACCOUNTING_SHA})
        accounting = types.ModuleType("ap2_frozen_usage_accounting")
        accounting.__file__ = str(accounting_path)
        exec(compile(accounting_raw, str(accounting_path), "exec", dont_inherit=True), accounting.__dict__)
        validated = accounting.validate_policy(policy)
        need(policy["run_id"] == plan["run_id"] and policy["configuration_sha256"] == configuration_sha256,
             "Accounting policy binding differs")
        read_ref(usage["ledger"])  # Initial ledger bytes are bound before the first model attempt.
        ledger = regular(usage["ledger"]["path"])
        with accounting.transaction(ledger) as db:
            stored, halted = accounting.policy_row(db, validated["policy_sha256"])
            need(encoded(stored) == accounting.encoded(policy) and not halted, "Ledger policy differs or is halted")
        need(plan["environment_manifest"]["sha256"] == ENV_SHA, "Exact assessed environment required")
        environment = strict_json(read_ref(plan["environment_manifest"]))
        sites = Path(environment["site_packages"])
        source_bytes = {name: read_ref({"path": str(sites / name), "sha256": sha}) for name, sha in SOURCES.items()}
        # Only now may the actual pinned SDK/class definitions be imported.
        headroom = headroom_before_sdk()
        api = importlib.import_module("google.genai._api_client")
        httpx = importlib.import_module("httpx._client")
        aio = importlib.import_module("aiohttp.client_reqrep")
        http_transport = importlib.import_module("httpx._transports.default")
        for module, name in ((api, "google/genai/_api_client.py"), (httpx, "httpx/_client.py"),
                             (aio, "aiohttp/client_reqrep.py"), (http_transport, "httpx/_transports/default.py")):
            need(module.__file__ == str(sites / name) and module.__spec__.origin == str(sites / name),
                 "Loaded provider/transport module origin differs")
        for cls, method, relative, defaults in (
            (api.BaseApiClient, "_request_once", "google/genai/_api_client.py", (False,)),
            (api.BaseApiClient, "_async_request_once", "google/genai/_api_client.py", (False,)),
            (httpx.Client, "_send_single_request", "httpx/_client.py", None),
            (httpx.AsyncClient, "_send_single_request", "httpx/_client.py", None),
            (aio.ClientRequest, "send", "aiohttp/client_reqrep.py", None),
            (http_transport.HTTPTransport, "handle_request", "httpx/_transports/default.py", None),
        ):
            verify_method(cls, method, sites / relative, source_bytes[relative], defaults=defaults)

        def client_check(client):
            need(type(client) is api.SyncHttpxClient, "Custom provider HTTPX client is outside the original profile")
            need(api.SyncHttpxClient.__mro__[1] is httpx.Client, "Provider HTTPX base-class origin differs")
            need(client._event_hooks == {"request": [], "response": []},
                 "Custom event hooks are outside the original nonstreaming profile")
            transports = [client._transport, *[item for item in client._mounts.values() if item is not None]]
            for item in transports:
                need(type(item) is http_transport.HTTPTransport, "Custom lower transport is unreviewed")
                pool = getattr(item, "_pool", None)
                need(getattr(pool, "_http1", None) is True and getattr(pool, "_http2", None) is False,
                     "Only original HTTP/1 lower transport; HTTP/2 internal retries are unreviewed")
                retries = getattr(pool, "_retries", None)
                need(type(retries) is int and retries == 0, "Hidden lower-transport retries are unreviewed")

        guard = ProviderGuard(accounting, ledger, validated["policy_sha256"], service["role"], maximum,
                              client_check=client_check)
        _LIVE_GUARD = guard  # Retain authority before any class replacement.
        guard.bind_classes(api.BaseApiClient, httpx.Client, httpx.AsyncClient, aio.ClientRequest)
        return {"status": "installed", "installed": True, "contract": "enforce_before_every_provider_request",
                "configuration_sha256": configuration_sha256, "profile": "original_hp_sync_generate_content",
                "policy_sha256": validated["policy_sha256"], "source_hashes": deepcopy(SOURCES), "pre_sdk_headroom": headroom,
                "async_provider_requests": "refused_before_transmission", "provider_entitlement_authenticated": False,
                "native_qualification_established": False}
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        if guard is not None:
            guard.restore()  # A duplicate refusal must not release another installation's lease.
        return {"status": "refused", "installed": False, "configuration_sha256": configuration_sha256,
                "contract": "original_hp_sync_guard_not_established", "error_type": type(error).__name__,
                "native_client_construction_verified": NATIVE_CLIENT_CONSTRUCTION_VERIFIED,
                "native_qualification_established": False}
