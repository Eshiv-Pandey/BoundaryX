"""Constructor-owned direct HTTP/1 client-state checks on supplied classes.

This module imports no SDK, reads no credentials and enables no native guard.
Actual source/class/global bindings are separate mandatory prerequisites.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import functools
import math
import types
import weakref


class ClientStateRefused(ValueError):
    pass


def need(value, reason):
    if not value:
        raise ClientStateRefused(reason)


API_METHODS = ("__init__", "_request_once")
HTTP_METHODS = ("__init__", "request", "build_request", "send", "_send_handling_auth",
                "_send_handling_redirects", "_send_single_request", "_transport_for_url",
                "_build_request_auth", "_set_timeout")
LOWER_METHODS = ("handle_request",)


def bound_function(instance, name):
    value = object.__getattribute__(instance, name)
    need(type(value) is types.MethodType and value.__self__ is instance,
         "Original bound instance method required")
    return value.__func__


def function_state(function):
    keyword = function.__kwdefaults__
    return (function.__code__, function.__defaults__, keyword,
            None if keyword is None else dict(keyword))


def state_matches(function, state):
    if not (function.__code__ is state[0] and function.__defaults__ is state[1]
            and function.__kwdefaults__ is state[2]):
        return False
    current, expected = function.__kwdefaults__, state[3]
    return current is None if expected is None else (
        set(current) == set(expected) and all(current[name] is value for name, value in expected.items()))


@dataclass
class SuppliedHttp1Profile:
    """Immutable identity expectations supplied by a separate source verifier.

    Validation never upgrades these supplied identities to source authenticity.
    Native integration must prove their origins before constructing this object.
    """
    api_class: type
    http_class: type
    http_mro: tuple
    transport_class: type
    pool_class: type
    backend_class: type
    request_class: type
    url_class: type
    headers_class: type
    stream_class: type
    expected_methods: dict = field(repr=False)
    class_members: dict = field(repr=False)

    def __post_init__(self):
        classes = (self.api_class, self.http_class, self.transport_class, self.pool_class,
                   self.backend_class, self.request_class, self.url_class, self.headers_class, self.stream_class)
        need(all(type(value) is type for value in classes), "Exact supplied class identities required")
        need(type(self.http_mro) is tuple and self.http_mro == self.http_class.__mro__,
             "Exact supplied original HTTP class MRO required")
        required = {(self.api_class, name) for name in API_METHODS}
        required |= {(self.http_class, name) for name in HTTP_METHODS}
        required |= {(cls, "handle_request") for cls in (self.transport_class, self.pool_class)}
        required |= {(self.backend_class, name) for name in ("connect_tcp", "connect_unix_socket")}
        need(set(self.expected_methods) == required
             and all(type(value) is types.FunctionType for value in self.expected_methods.values()),
             "Complete explicit request dispatch method identities required")
        need(set(self.class_members) == set(classes) | set(self.http_mro[:-1]),
             "Complete supplied class-member snapshots required")
        need(all(type(values) is dict for values in self.class_members.values()), "Class snapshot mappings required")
        self.expected_methods = dict(self.expected_methods)
        self.class_members = {cls: dict(values) for cls, values in self.class_members.items()}
        self.class_mros = {cls: cls.__mro__ for cls in self.class_members}
        self.function_state = {value: function_state(value)
                               for value in self.expected_methods.values()}
        self.owned_function_state = {}

    def register_owned_patches(self, patches):
        for cls, name, original, replacement in patches:
            need(self.class_members.get(cls, {}).get(name) is original
                 and type(replacement) is types.FunctionType, "Owned patch origin differs")
            if replacement in self.owned_function_state:
                need(state_matches(replacement, self.owned_function_state[replacement]),
                     "Owned replacement code/defaults changed")
            else:
                self.owned_function_state[replacement] = function_state(replacement)

    def verify_classes(self, owned_patches=()):
        allowed = {}
        for cls, name, original, replacement in owned_patches:
            need((cls, name) not in allowed and type(replacement) is types.FunctionType,
                 "Unique owned function patch required")
            need(self.class_members.get(cls, {}).get(name) is original,
                 "Owned patch does not match supplied original class member")
            need(replacement in self.owned_function_state
                 and state_matches(replacement, self.owned_function_state[replacement]),
                 "Owned patch was not registered unchanged before installation")
            allowed[cls, name] = replacement
        for cls, expected in self.class_members.items():
            need(cls.__mro__ == self.class_mros[cls], "Supplied class inheritance changed")
            current = dict(cls.__dict__)
            need(set(current) == set(expected), "Supplied class member footprint changed")
            for name, original in expected.items():
                need(current[name] is allowed.get((cls, name), original), "Supplied class alias changed")
        for function, state in self.function_state.items():
            need(state_matches(function, state), "Supplied method code/default object changed")
        need(self.http_class.__mro__ == self.http_mro, "HTTP dispatch MRO changed")

    def _methods(self, instance, names, owned_patches):
        for name in names:
            expected = self.expected_methods[type(instance), name]
            for cls, slot, original, replacement in owned_patches:
                if slot == name and cls in type(instance).__mro__ and original is expected:
                    expected = replacement
            need(name not in object.__getattribute__(instance, "__dict__")
                 and bound_function(instance, name) is expected,
                 "Instance or inherited dispatch shadow refused")

    def validate_client(self, api, owned_patches=()):
        self.verify_classes(owned_patches)
        need(type(api) is self.api_class, "Exact supplied API client required")
        self._methods(api, API_METHODS, owned_patches)
        mode = object.__getattribute__(api, "vertexai")
        need(mode is None or mode is False, "Source-derived non-Vertex None/False mode required")
        client = object.__getattribute__(api, "_httpx_client")
        need(type(client) is self.http_class, "Exact supplied default HTTPX client required")
        self._methods(client, HTTP_METHODS, owned_patches)
        need(object.__getattribute__(client, "_auth") is None, "Custom auth flow is unreviewed")
        hooks = object.__getattribute__(client, "_event_hooks")
        need(type(hooks) is dict and set(hooks) == {"request", "response"}
             and all(type(hooks[name]) is list and not hooks[name] for name in hooks),
             "Default empty request/response hooks required")
        need(type(object.__getattribute__(client, "_default_encoding")) is str,
             "Callable response encoding is outside this profile")
        mounts = object.__getattribute__(client, "_mounts")
        need(type(mounts) is dict and all(value is None for value in mounts.values()),
             "Proxy/custom mounted transport is outside this unchanged direct profile")
        transport = object.__getattribute__(client, "_transport")
        need(type(transport) is self.transport_class, "Exact supplied original HTTP transport required")
        self._methods(transport, LOWER_METHODS, owned_patches)
        pool = object.__getattribute__(transport, "_pool")
        need(type(pool) is self.pool_class, "Exact supplied original connection pool required")
        self._methods(pool, LOWER_METHODS, owned_patches)
        for name in ("_proxy", "_uds"):
            need(object.__getattribute__(pool, name) is None, "Proxy/Unix transport is unreviewed")
        need(object.__getattribute__(pool, "_http1") is True
             and object.__getattribute__(pool, "_http2") is False,
             "Original direct HTTP/1 profile required; internal HTTP/2 replays refused")
        retries = object.__getattribute__(pool, "_retries")
        need(type(retries) is int and retries == 0, "Hidden lower transport retries refused")
        backend = object.__getattribute__(pool, "_network_backend")
        need(type(backend) is self.backend_class, "Exact supplied original synchronous backend required")
        self._methods(backend, ("connect_tcp", "connect_unix_socket"), owned_patches)
        return client

    def validate_request(self, request):
        need(type(request) is self.request_class, "Exact supplied HTTPX request required")
        need(type(object.__getattribute__(request, "url")) is self.url_class
             and type(object.__getattribute__(request, "headers")) is self.headers_class
             and type(object.__getattribute__(request, "stream")) is self.stream_class,
             "Exact supplied request URL/headers/byte-stream types required")
        extensions = object.__getattribute__(request, "extensions")
        need(type(extensions) is dict and set(extensions) <= {"timeout"},
             "Custom request extensions including trace callbacks are refused")
        if "timeout" in extensions:
            timeout = extensions["timeout"]
            need(type(timeout) is dict and set(timeout) == {"connect", "read", "write", "pool"},
                 "Original HTTPX timeout extension shape required")
            need(all(value is None or type(value) in (int, float) and math.isfinite(value) and value >= 0
                     for value in timeout.values()), "Finite nonnegative timeout values required")


class ConstructorClientLease:
    """Enroll only clients returned by the exact supplied API constructor.

    An unsuccessful constructor/check never enrolls its API/client. This lease
    changes only the constructor slot and retains restoration on interference.
    Request guards must still check this registry before each transmission.
    """
    def __init__(self, profile):
        need(type(profile) is SuppliedHttp1Profile, "Supplied HTTP/1 profile required")
        self.profile = profile
        self.original = profile.api_class.__dict__["__init__"]
        need(profile.expected_methods[profile.api_class, "__init__"] is self.original,
             "Exact supplied original API constructor required")
        self.clients = {}  # id(api) -> weak refs; equality/hash cannot reuse enrollment.
        self.installed = self.restored = False
        self.active = 0
        self.replacement = None
        self.peer_patches = ()

    def install(self, *, peer_patches=()):
        need(not self.installed and not self.restored, "Constructor lease is once-only")
        self.peer_patches = tuple(peer_patches)
        self.profile.register_owned_patches(self.peer_patches)
        self.profile.verify_classes(self.peer_patches)
        lease = self
        @functools.wraps(self.original)
        def initialize(api, *args, **kwargs):
            lease.active += 1
            try:
                result = lease.original(api, *args, **kwargs)
                client = lease.profile.validate_client(api, lease.patches())
                identity = id(api)
                def forget(reference):
                    current = lease.clients.get(identity)
                    if current is not None and current[0] is reference:
                        lease.clients.pop(identity, None)
                lease.clients[identity] = (weakref.ref(api, forget), weakref.ref(client))
                return result
            finally:
                lease.active -= 1
        self.replacement = initialize
        self.profile.register_owned_patches(((self.profile.api_class, "__init__", self.original, initialize),))
        self.profile.api_class.__init__ = initialize
        self.installed = True
        return self

    def patches(self):
        own = ((self.profile.api_class, "__init__", self.original, self.replacement),) if self.installed else ()
        return (*self.peer_patches, *own)

    def validate_before_transmission(self, api, client, request):
        entry = self.clients.get(id(api))
        need(self.installed and not self.restored and entry is not None and entry[0]() is api,
             "API client was not enrolled by the owned original constructor")
        need(entry[1]() is client and self.profile.validate_client(api, self.patches()) is client,
             "Original constructor-owned HTTP client identity changed")
        self.profile.validate_request(request)
        return True

    def restore(self):
        if self.restored:
            return True
        if self.active:
            return False
        if self.profile.api_class.__dict__.get("__init__") is not self.replacement:
            return False
        self.profile.api_class.__init__ = self.original
        self.restored = True
        return True

    def report(self):
        return {"schema_version": "ap2-hp-supplied-http1-client-state/1",
                "constructor_lease_installed": self.installed and not self.restored,
                "constructor_authority_retained": self.installed and not self.restored,
                "enrolled_api_clients": len(self.clients), "active_constructors": self.active,
                "sdk_imports_performed": 0, "native_guard_installed": False,
                "source_identity_verified_by_this_module": False,
                "transitive_sdk_fidelity_verified": False, "native_qualification_established": False}
