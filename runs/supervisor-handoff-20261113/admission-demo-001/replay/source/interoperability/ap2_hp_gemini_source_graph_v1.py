"""Compile-only graph proof/refusal for supplied original synchronous clients.

No inspected source is executed or imported. A missing Python dependency or
unreviewed descriptor/factory is a graph frontier, never an implicit trust grant.
The verifier does not install a transport, read a key or authenticate a process.
"""
from __future__ import annotations

import ast
import builtins
import contextlib
from dataclasses import dataclass, field
import dis
import functools
import hashlib
import importlib.util
import marshal
from pathlib import Path
import stat
import sys
import sysconfig
import types
from types import MappingProxyType

from .ap2_hp_gemini_client_state_v1 import (
    API_METHODS, HTTP_METHODS, SuppliedHttp1Profile, function_state, state_matches,
)


class GraphRefused(ValueError):
    def __init__(self, reason, frontiers=()):
        super().__init__(reason)
        self.frontiers = tuple(frontiers)


def need(value, reason):
    if not value:
        raise GraphRefused(reason)


def regular(path):
    path = Path(path)
    need(path.is_absolute(), "Absolute graph source path required")
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Linked/reparse graph source refused")
    need(path.is_file(), "Regular graph source required")
    return path.resolve()


def all_codes(code):
    yield code
    for value in code.co_consts:
        if type(value) is types.CodeType:
            yield from all_codes(value)


def literal_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) in (tuple, list):
        return len(actual) == len(expected) and all(literal_equal(a, b) for a, b in zip(actual, expected))
    if type(expected) is dict:
        return len(actual) == len(expected) and all(
            any(literal_equal(k, other) and literal_equal(v, child) for other, child in actual.items())
            for k, v in expected.items())
    if expected is None or type(expected) in (bool, int, float, str, bytes):
        return actual == expected
    return actual is expected


def mutable_state(value, active=None, depth=0):
    """Bounded identity/value snapshot; never invoke an application conversion."""
    need(depth <= 30, "Mutable graph state depth exceeded")
    active = set() if active is None else active
    if value is None or type(value) in (bool, int, float, str, bytes):
        return (type(value), value)
    if type(value) in (tuple, list, dict, set, frozenset):
        need(id(value) not in active and len(value) <= 10000, "Cyclic/oversized graph constant")
        active.add(id(value))
        try:
            if type(value) is dict:
                children = tuple((mutable_state(k, active, depth + 1), mutable_state(v, active, depth + 1))
                                 for k, v in value.items())
            else:
                children = tuple(mutable_state(child, active, depth + 1) for child in value)
            return (type(value), id(value), children)
        finally:
            active.remove(id(value))
    # External instance state is checked by the concrete live profile. This
    # opaque identity snapshot does not certify how that instance was created.
    return (type(value), id(value))


@dataclass(frozen=True)
class SourceUnit:
    name: str
    module: object = field(repr=False)
    path: Path
    sha256: str
    kind: str = "python"

    def read(self):
        need(type(self.name) is str and self.name and type(self.module) is types.ModuleType,
             "Canonical supplied module required")
        need(sys.modules.get(self.name) is self.module, "Supplied module is not the loaded canonical object")
        path = regular(self.path)
        namespace = self.module.__dict__
        spec = namespace.get("__spec__")
        need(namespace.get("__name__") == self.name and regular(namespace.get("__file__")) == path
             and spec is not None and spec.name == self.name and regular(spec.origin) == path,
             "Supplied module/source/specification origin differs")
        raw = path.read_bytes()
        need(len(raw) <= 32 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == self.sha256,
             "Supplied module payload differs from reviewed source pin")
        need(self.kind in {"python", "native"} and (self.kind != "python" or path.suffix == ".py"),
             "Explicit source/native boundary required")
        return raw


@dataclass
class FunctionProof:
    function: object = field(repr=False)
    unit: SourceUnit = field(repr=False)
    node: object = field(repr=False)
    state: object = field(repr=False)
    aliases: dict = field(repr=False)
    mutable_aliases: dict = field(repr=False)
    wrapper: object = field(default=None, repr=False)
    wrapper_state: object = field(default=None, repr=False)


# These are mandatory roots, not a completeness claim. Dependencies encountered
# beneath them must also close; the public factory refuses unresolved edges.
DIRECT_ROOTS = (
    ("google.genai.client", "Client"),
    ("google.genai._api_client", "BaseApiClient"),
    ("google.genai._api_client", "SyncHttpxClient"),
    ("google.genai._api_client", "AsyncHttpxClient"),
    ("httpx._client", "BaseClient"), ("httpx._client", "Client"),
    ("httpx._auth", "Auth"), ("httpx._transports.default", "HTTPTransport"),
    ("httpx._models", "Request"), ("httpx._models", "Response"), ("httpx._models", "Headers"),
    ("httpx._urls", "URL"), ("httpx._content", "ByteStream"),
    ("httpcore._sync.connection_pool", "ConnectionPool"),
    ("httpcore._sync.connection", "HTTPConnection"),
    ("httpcore._sync.http11", "HTTP11Connection"),
    ("httpcore._backends.sync", "SyncBackend"), ("httpcore._backends.sync", "SyncStream"),
    ("httpcore._models", "Request"), ("httpcore._models", "URL"),
    ("httpcore._trace", "Trace"), ("h11._connection", "Connection"),
)


class SourceGraph:
    """Proof of exact supplied Python definitions, consulted aliases and edges.

    The controlled profile trusts canonical stdlib semantics and explicitly
    pinned native extension origins. Python helpers require source proof;
    unsupported generated classes, dynamic factories and descriptors refuse.
    No discovery import occurs, including for a lazy import in inspected code.
    """
    def __init__(self, units, *, maximum_nodes=5000):
        need(type(units) is dict and 0 < len(units) <= 512 and type(maximum_nodes) is int
             and 0 < maximum_nodes <= 20000, "Finite explicit graph inventory required")
        need(all(type(unit) is SourceUnit and name == unit.name for name, unit in units.items()),
             "Exact named source-unit inventory required")
        need(sys.flags.optimize == 0, "Unoptimized source graph profile required")
        self.units = MappingProxyType(dict(units))
        self.maximum_nodes = maximum_nodes
        self.raw, self.trees, self.compiled = {}, {}, {}
        self.proofs, self.classes, self.class_members, self.class_mros = {}, {}, {}, {}
        self.aliases, self.frontiers, self.roots = {}, [], ()
        self.native_boundaries, self.stdlib_boundaries = set(), set()
        self._visiting, self._proved = set(), set()
        self._complete = False
        self._owned = {}

    def _frontier(self, label, reason):
        row = {"edge": label, "reason": reason}
        if row not in self.frontiers and len(self.frontiers) < 512:
            self.frontiers.append(row)

    def _unit(self, name):
        need(name in self.units, "Python/native dependency has no supplied source unit: " + name)
        unit = self.units[name]
        raw = unit.read()
        if name in self.raw:
            need(raw == self.raw[name], "Graph source changed during verification")
        else:
            self.raw[name] = raw
            if unit.kind == "python":
                self.trees[name] = ast.parse(raw, filename=str(unit.path))
                self.compiled[name] = compile(raw, str(unit.path), "exec", dont_inherit=True, optimize=0)
            else:
                self.native_boundaries.add(name)
        return unit

    def _stdlib(self, value):
        if value is builtins or (type(value) is type and value.__module__ == "builtins"):
            return True
        name = value.__name__ if type(value) is types.ModuleType else getattr(value, "__module__", None)
        if type(name) is not str or name.split(".")[0] not in sys.stdlib_module_names:
            return False
        module = sys.modules.get(name)
        if type(module) is not types.ModuleType:
            return False
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if origin not in {"built-in", "frozen"}:
            if type(origin) is not str:
                return False
            path = Path(origin).resolve()
            stdlib = Path(sysconfig.get_path("stdlib")).resolve()
            if not path.is_relative_to(stdlib) or "site-packages" in path.parts:
                return False
        self.stdlib_boundaries.add(name)
        return type(value) is not types.ModuleType or module is value

    def _canonical(self, value):
        """Find a definition by namespace identity, including reviewed relabels."""
        candidates = []
        for name, unit in self.units.items():
            if unit.kind != "python":
                continue
            self._unit(name)
            for node in self.trees[name].body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if unit.module.__dict__.get(node.name) is value:
                        candidates.append((unit, node))
        need(len(candidates) == 1, "Unique source definition is absent/ambiguous for graph object")
        return candidates[0]

    def _expression(self, node, namespace):
        try:
            return ast.literal_eval(node), True
        except (ValueError, TypeError):
            pass
        if isinstance(node, ast.Name):
            if node.id in namespace:
                return namespace[node.id], False
            need(node.id in builtins.__dict__, "Source expression name is absent: " + node.id)
            return builtins.__dict__[node.id], False
        if isinstance(node, ast.Attribute):
            parent, _ = self._expression(node.value, namespace)
            need(type(parent) in (types.ModuleType, type), "Dynamic source attribute expression is unreviewed")
            mapping = parent.__dict__
            need(node.attr in mapping, "Source attribute alias absent: " + node.attr)
            return mapping[node.attr], False
        raise GraphRefused("Unreviewed source expression/default factory: " + type(node).__name__)

    def _import_bindings(self, unit):
        namespace = unit.module.__dict__
        result = {}
        for node in ast.walk(self.trees[unit.name]):
            # Function-local imports are resolved at their call site separately.
            if isinstance(node, ast.Import):
                for alias in node.names:
                    key = alias.asname or alias.name.split(".")[0]
                    name = alias.name if alias.asname else alias.name.split(".")[0]
                    if key in namespace:
                        result.setdefault(key, []).append((name, None))
            elif isinstance(node, ast.ImportFrom):
                package = namespace.get("__package__")
                name = ("." * node.level) + (node.module or "")
                name = importlib.util.resolve_name(name, package) if node.level else name
                for alias in node.names:
                    key = alias.asname or alias.name
                    if key in namespace and alias.name != "*":
                        result.setdefault(key, []).append((name, alias.name))
        return result

    def _import_alias(self, unit, key, value):
        possibilities = self._import_bindings(unit).get(key, ())
        if not possibilities:
            return False
        for name, member in possibilities:
            module = sys.modules.get(name)
            if type(module) is not types.ModuleType:
                continue
            target = module if member is None else module.__dict__.get(member)
            if target is value:
                if not self._stdlib(module):
                    self._unit(name)
                self.aliases[unit.name, key] = value
                return True
        raise GraphRefused("Consulted imported alias differs from canonical dependency: " + key)

    def _relabel(self, unit, node, cls):
        expected = unit.name
        actual = cls.__dict__.get("__module__")
        if actual == expected:
            return
        need(actual in {"httpx", "httpcore"} and unit.name.startswith(actual + "."),
             "Unreviewed class definition/public origin relabel")
        public = self._unit(actual)
        namespace = public.module.__dict__
        need(namespace.get(node.name) is cls and node.name in namespace.get("__all__", ()),
             "Public class re-export/relabel membership differs")
        # Accept only the exact reviewed package terminal relabel syntax.
        matches = []
        for statement in self.trees[actual].body:
            if not isinstance(statement, ast.For) or not isinstance(statement.target, ast.Name):
                continue
            for call in ast.walk(statement):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "setattr"
                        and len(call.args) == 3 and isinstance(call.args[1], ast.Constant)
                        and call.args[1].value == "__module__" and isinstance(call.args[2], ast.Constant)
                        and call.args[2].value == actual):
                    matches.append(call)
        need(len(matches) == 1, "Reviewed package class relabel rule absent")
        self.aliases[actual, node.name] = cls

    def _verify_function(self, unit, node, function, enclosing=None, wrapper=None):
        need(type(function) is types.FunctionType and function.__globals__ is unit.module.__dict__,
             "Original function/global namespace differs")
        need(function.__builtins__ is builtins.__dict__, "Custom function builtins refused")
        need(regular(function.__code__.co_filename) == regular(unit.path), "Original function source origin differs")
        matches = [code for code in all_codes(self.compiled[unit.name])
                   if code.co_qualname == function.__code__.co_qualname
                   and code.co_firstlineno == function.__code__.co_firstlineno]
        need(len(matches) == 1 and marshal.dumps(matches[0]) == marshal.dumps(function.__code__),
             "Original function code/exception routing differs from compiled source")
        if function.__closure__:
            need(function.__code__.co_freevars == ("__class__",) and enclosing is not None
                 and len(function.__closure__) == 1 and function.__closure__[0].cell_contents is enclosing,
                 "Unreviewed source function closure")
        actual = function.__defaults__ or ()
        need(len(actual) == len(node.args.defaults), "Original positional default arity differs")
        for observed, expression in zip(actual, node.args.defaults):
            expected, literal = self._expression(expression, unit.module.__dict__)
            need(literal_equal(observed, expected) if literal else observed is expected,
                 "Original positional default value/alias differs")
        expected_keyword = {arg.arg: self._expression(value, unit.module.__dict__)
                            for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults) if value is not None}
        keyword = function.__kwdefaults__ or {}
        need(set(keyword) == set(expected_keyword), "Original keyword default footprint differs")
        for name, (expected, literal) in expected_keyword.items():
            need(literal_equal(keyword[name], expected) if literal else keyword[name] is expected,
                 "Original keyword default value/alias differs")
        aliases = {}
        for code in all_codes(function.__code__):
            for instruction in dis.get_instructions(code):
                if instruction.opname == "LOAD_GLOBAL" and instruction.argval in function.__globals__:
                    name = instruction.argval
                    aliases[name] = function.__globals__[name]
                    self._import_alias(unit, name, aliases[name])
        proof = FunctionProof(function, unit, node, function_state(function), aliases,
                              {name: mutable_state(value) for name, value in aliases.items()},
                              wrapper, function_state(wrapper) if wrapper is not None else None)
        self.proofs[id(function)] = proof
        for name, value in aliases.items():
            self._edge(unit.name + "." + function.__qualname__ + ":" + name, value)
        # Attribute calls rooted at imported modules must bind their consulted
        # member, not only the module object. Calls on runtime values are part
        # of the explicit live profile, or remain a refusal frontier.
        for call in (child for child in ast.walk(node) if isinstance(child, ast.Call)):
            target = call.func
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                name = target.value.id
                if name in aliases and type(aliases[name]) is types.ModuleType:
                    module = aliases[name]
                    need(target.attr in module.__dict__, "Consulted module callable alias absent")
                    value = module.__dict__[target.attr]
                    self.aliases[module.__name__, target.attr] = value
                    self._edge(unit.name + "." + function.__qualname__ + ":" + name + "." + target.attr, value)
        return function

    def _descriptor(self, unit, definition, actual, cls):
        decorators = definition.decorator_list
        if not decorators:
            return self._verify_function(unit, definition, actual, cls)
        need(len(decorators) == 1, "Unreviewed stacked method decorators")
        decorator = decorators[0]
        namespace = unit.module.__dict__
        if isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Name)
                and decorator.attr in {"setter", "deleter"}:
            need(type(actual) is property and decorator.value.id == definition.name,
                 "Original property setter/deleter binding differs")
            function = actual.fset if decorator.attr == "setter" else actual.fdel
            return self._verify_function(unit, definition, function, cls)
        expected, _ = self._expression(decorator, namespace)
        if expected is builtins.property:
            need(type(actual) is property, "Original property descriptor differs")
            return self._verify_function(unit, definition, actual.fget, cls)
        if expected in (builtins.staticmethod, builtins.classmethod):
            need(type(actual) is expected, "Original static/class method descriptor differs")
            return self._verify_function(unit, definition, actual.__func__, cls)
        if expected is functools.cached_property:
            need(type(actual) is functools.cached_property and actual.attrname == definition.name,
                 "Original cached-property binding differs")
            return self._verify_function(unit, definition, actual.func, cls)
        if expected is contextlib.contextmanager:
            need(type(actual) is types.FunctionType and actual.__globals__ is contextlib.__dict__,
                 "Original contextmanager wrapper globals differ")
            helpers = [code for code in all_codes(contextlib.contextmanager.__code__)
                       if code.co_qualname == "contextmanager.<locals>.helper"]
            wrapped = actual.__dict__.get("__wrapped__")
            need(len(helpers) == 1 and marshal.dumps(actual.__code__) == marshal.dumps(helpers[0])
                 and actual.__defaults__ is None and actual.__kwdefaults__ is None
                 and actual.__code__.co_freevars == ("func",) and actual.__closure__ is not None
                 and len(actual.__closure__) == 1 and actual.__closure__[0].cell_contents is wrapped,
                 "Original contextmanager wrapper code/closure differs")
            return self._verify_function(unit, definition, wrapped, cls, actual)
        raise GraphRefused("Unreviewed original method decorator")

    def _class(self, unit, node, cls):
        need(type(cls) is type and cls.__qualname__ == node.name and not node.keywords and not node.decorator_list,
             "Unreviewed generated/metaclass/decorated source class")
        bases = tuple(self._expression(base, unit.module.__dict__)[0] for base in node.bases) or (object,)
        need(len(cls.__bases__) == len(bases) and all(a is b for a, b in zip(cls.__bases__, bases)),
             "Original source class bases differ")
        self._relabel(unit, node, cls)
        self.classes[unit.name, node.name] = cls
        self.class_members[cls] = dict(cls.__dict__)
        self.class_mros[cls] = cls.__mro__
        declared = set()
        definitions = []
        for definition in node.body:
            if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # typing.overload stubs do not survive the actual definition.
                if any(isinstance(dec, ast.Name) and dec.id == "overload" for dec in definition.decorator_list):
                    continue
                declared.add(definition.name)
                definitions.append(definition)
            elif isinstance(definition, (ast.Assign, ast.AnnAssign)):
                targets = definition.targets if isinstance(definition, ast.Assign) else [definition.target]
                need(all(isinstance(target, ast.Name) for target in targets), "Unreviewed class assignment target")
                declared.update(target.id for target in targets)
                if definition.value is not None:
                    expected, literal = self._expression(definition.value, unit.module.__dict__)
                    for target in targets:
                        need(target.id in cls.__dict__ and (literal_equal(cls.__dict__[target.id], expected)
                             if literal else cls.__dict__[target.id] is expected), "Original class constant differs")
            elif isinstance(definition, ast.Expr) and isinstance(definition.value, ast.Constant):
                need(type(definition.value.value) is str, "Unreviewed class body expression")
            elif isinstance(definition, ast.Pass):
                continue
            else:
                raise GraphRefused("Unreviewed conditional/dynamic class body")
        metadata = {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__", "__annotations__",
                    "__annotate__", "__annotate_func__", "__static_attributes__", "__firstlineno__"}
        need(set(cls.__dict__) <= declared | metadata, "Original class member footprint differs")
        for definition in definitions:
            need(definition.name in cls.__dict__, "Original class descriptor absent")
            self._descriptor(unit, definition, cls.__dict__[definition.name], cls)
        for base in bases:
            self._edge(unit.name + "." + node.name + ":base", base)

    def _edge(self, label, value):
        if self._stdlib(value) or value is None or type(value) in (bool, int, float, str, bytes):
            return
        if type(value) in (tuple, list, dict, set, frozenset):
            need(len(value) <= 10000, "Oversized graph constant edge")
            children = (*value.keys(), *value.values()) if type(value) is dict else value
            for child in children:
                self._edge(label + ":constant", child)
            return
        identity = id(value)
        if identity in self._visiting or identity in self._proved:
            return
        if len(self._visiting) + len(self._proved) >= self.maximum_nodes:
            self._frontier(label, "Graph node limit reached")
            return
        self._visiting.add(identity)
        try:
            if type(value) is types.ModuleType:
                unit = self._unit(value.__name__)
                need(unit.module is value, "Consulted module alias differs")
            elif type(value) in (types.FunctionType, type):
                unit, node = self._canonical(value)
                if isinstance(node, ast.ClassDef):
                    self._class(unit, node, value)
                else:
                    need(not node.decorator_list, "Unreviewed module function decorator")
                    self._verify_function(unit, node, value)
            else:
                name = type(value).__module__
                if name in self.units and self._unit(name).kind == "native":
                    self.native_boundaries.add(name)
                else:
                    raise GraphRefused("Unreviewed Python factory/generated instance edge: " + name)
            self._proved.add(identity)
        except (GraphRefused, ValueError, TypeError, KeyError, AttributeError, OSError) as error:
            self._frontier(label, str(error))
        finally:
            self._visiting.remove(identity)

    def prove(self, roots):
        need(not self.roots and type(roots) is tuple and roots and len(roots) <= 256,
             "One finite explicit root graph required")
        self.roots = roots
        for name, symbol in roots:
            try:
                unit = self._unit(name)
                need(symbol in unit.module.__dict__, "Mandatory graph root absent")
                self._edge(name + "." + symbol, unit.module.__dict__[symbol])
            except (GraphRefused, ValueError, TypeError, KeyError, AttributeError, OSError) as error:
                self._frontier(name + "." + symbol, str(error))
        self._complete = not self.frontiers
        if not self._complete:
            raise GraphRefused("Mandatory source graph has unresolved edges; no verified handles", self.frontiers)
        self.verify()
        return self

    def verify(self, owned_patches=()):
        need(self._complete, "Incomplete source graph cannot yield verified handles")
        for name, raw in self.raw.items():
            need(self.units[name].read() == raw, "Bound graph source bytes changed")
        allowed = {}
        for cls, name, original, replacement in owned_patches:
            need((cls, name) in self._owned and self._owned[cls, name][0] is original
                 and self._owned[cls, name][1] is replacement
                 and state_matches(replacement, self._owned[cls, name][2]), "Unregistered/changed owned graph patch")
            allowed[cls, name] = replacement
        for cls, expected in self.class_members.items():
            need(cls.__mro__ == self.class_mros[cls] and set(cls.__dict__) == set(expected), "Source class footprint/MRO changed")
            for name, original in expected.items():
                need(cls.__dict__[name] is allowed.get((cls, name), original), "Source class descriptor/alias changed")
        for proof in self.proofs.values():
            need(proof.function.__globals__ is proof.unit.module.__dict__ and state_matches(proof.function, proof.state),
                 "Source function code/globals/defaults changed")
            for name, value in proof.aliases.items():
                need(proof.function.__globals__.get(name) is value and mutable_state(value) == proof.mutable_aliases[name],
                     "Consulted source global/mutable constant changed")
            if proof.wrapper is not None:
                need(state_matches(proof.wrapper, proof.wrapper_state)
                     and proof.wrapper.__dict__.get("__wrapped__") is proof.function
                     and proof.wrapper.__closure__[0].cell_contents is proof.function,
                     "Source wrapper code/defaults/closure changed")
        for (name, symbol), value in self.aliases.items():
            module = self.units[name].module if name in self.units else sys.modules.get(name)
            need(type(module) is types.ModuleType and module.__dict__.get(symbol) is value,
                 "Consulted dependency/public alias changed")
        return True

    def register_owned_patches(self, patches):
        self.verify()
        for cls, name, original, replacement in patches:
            need(self.class_members.get(cls, {}).get(name) is original and type(replacement) is types.FunctionType,
                 "Owned instrumentation does not match source class slot")
            self._owned[cls, name] = (original, replacement, function_state(replacement))

    def http1_profile(self):
        """Only the closed complete mandatory graph can supply live-state handles."""
        need(self.roots == DIRECT_ROOTS, "Complete original direct-profile root graph required")
        self.verify()
        def cls(module, name):
            need((module, name) in self.classes, "Mandatory source class proof absent")
            return self.classes[module, name]
        api, http = cls("google.genai._api_client", "BaseApiClient"), cls("google.genai._api_client", "SyncHttpxClient")
        transport = cls("httpx._transports.default", "HTTPTransport")
        pool, backend = cls("httpcore._sync.connection_pool", "ConnectionPool"), cls("httpcore._backends.sync", "SyncBackend")
        request, url = cls("httpx._models", "Request"), cls("httpx._urls", "URL")
        headers, stream = cls("httpx._models", "Headers"), cls("httpx._content", "ByteStream")
        methods = {(api, name): getattr(api, name) for name in API_METHODS}
        methods.update({(http, name): getattr(http, name) for name in HTTP_METHODS})
        methods.update({(value, "handle_request"): getattr(value, "handle_request") for value in (transport, pool)})
        methods.update({(backend, name): getattr(backend, name) for name in ("connect_tcp", "connect_unix_socket")})
        selected = {api, http, transport, pool, backend, request, url, headers, stream, *http.__mro__[:-1]}
        return SuppliedHttp1Profile(api, http, http.__mro__, transport, pool, backend, request, url, headers, stream,
            methods, {value: dict(self.class_members[value]) for value in selected})

    def validate_live_connections(self, api, client, request, profile, owned_patches=()):
        """Check original direct pool/HTTP1 dispatch; no operation is invoked."""
        self.verify(owned_patches)
        need(profile.validate_client(api, owned_patches) is client, "Live source/client identity differs")
        profile.validate_request(request)
        expected_connection = self.classes["httpcore._sync.connection", "HTTPConnection"]
        expected_http1 = self.classes["httpcore._sync.http11", "HTTP11Connection"]
        expected_stream = self.classes["httpcore._backends.sync", "SyncStream"]
        pool = object.__getattribute__(object.__getattribute__(client, "_transport"), "_pool")
        connections = object.__getattribute__(pool, "_connections")
        need(type(connections) is list and len(connections) <= 10000, "Original bounded pool connection list required")
        for connection in connections:
            need(type(connection) is expected_connection, "Proxy/custom pooled connection refused")
            self._no_instance_dispatch_shadow(connection)
            need(object.__getattribute__(connection, "_http1") is True
                 and object.__getattribute__(connection, "_http2") is False
                 and type(object.__getattribute__(connection, "_retries")) is int
                 and object.__getattribute__(connection, "_retries") == 0
                 and object.__getattribute__(connection, "_uds") is None,
                 "Live lower connection left original HTTP1/zero-retry profile")
            backend = object.__getattribute__(connection, "_network_backend")
            need(type(backend) is profile.backend_class, "Live connection backend differs")
            self._no_instance_dispatch_shadow(backend)
            protocol = object.__getattribute__(connection, "_connection")
            if protocol is not None:
                need(type(protocol) is expected_http1, "Live HTTP2/custom protocol connection refused")
                self._no_instance_dispatch_shadow(protocol)
                network = object.__getattribute__(protocol, "_network_stream")
                need(type(network) is expected_stream, "Custom or proxy TLS-in-TLS stream refused")
                self._no_instance_dispatch_shadow(network)
        return True

    def _no_instance_dispatch_shadow(self, instance):
        values = object.__getattribute__(instance, "__dict__")
        for cls in type(instance).__mro__:
            for name, descriptor in self.class_members.get(cls, {}).items():
                if type(descriptor) in (types.FunctionType, property, staticmethod, classmethod):
                    need(name not in values, "Live lower/request dispatch instance shadow")

    def report(self):
        return {"schema_version": "ap2-hp-source-dispatch-graph/1", "mandatory_roots": [list(root) for root in self.roots],
                "graph_closed": self._complete, "source_functions_verified": len(self.proofs),
                "source_classes_verified": len(self.class_members), "frontiers": [dict(row) for row in self.frontiers],
                "trusted_stdlib_boundaries": sorted(self.stdlib_boundaries),
                "file_bound_native_extension_boundaries": sorted(self.native_boundaries),
                "source_units_consulted": {name: self.units[name].sha256 for name in self.raw},
                "sdk_imports_performed": 0, "original_functions_executed": 0, "native_guard_installed": False,
                "provider_entitlement_authenticated": False, "process_memory_authenticated": False,
                "native_qualification_established": False}


def prove_original_direct_graph(units):
    """Return handles only after every mandatory root and dependency edge closes."""
    graph = SourceGraph(units)
    graph.prove(DIRECT_ROOTS)
    return graph, graph.http1_profile()
