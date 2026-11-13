"""Source-bound leases for already imported original AP2 caller modules.

No original module, SDK, credential, service or model is imported or invoked.
The native caller must gate/import first and supply the exact module objects.
These checks establish source consistency, not capture/source authentication.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import json
import marshal
from pathlib import Path, PurePosixPath
import stat
import sys
import types

from .ap2_hp_reference_execution_v1 import (
    CREDENTIALS, EXTENSION, MERCHANT, PublicClientObserver, ReferenceBindings, typed_equal,
)

STAGE_SHA256 = "78828cea09bdd387230a2fc0772b542beabfe07b72c3a2f24b24c02c1a2f4463"
ENVIRONMENT_SHA256 = "4d6efdd2e4003b82517f45aead140a7afd6f1e180b3ce518904d87c96e5adeb5"
SOURCE_MODULES = {
    "common.a2a_message_builder": "common/a2a_message_builder.py",
    "common.payment_remote_a2a_client": "common/payment_remote_a2a_client.py",
    "common.artifact_utils": "common/artifact_utils.py",
    "common.constants": "common/constants.py",
    "common.a2a_extension_utils": "common/a2a_extension_utils.py",
    "roles.shopping_agent.remote_agents": "roles/shopping_agent/remote_agents.py",
    "roles.shopping_agent.tools": "roles/shopping_agent/tools.py",
    "roles.shopping_agent.subagents.shopper.tools": "roles/shopping_agent/subagents/shopper/tools.py",
    "roles.shopping_agent.subagents.payment_method_collector.tools": "roles/shopping_agent/subagents/payment_method_collector/tools.py",
    "roles.shopping_agent.subagents.shipping_address_collector.tools": "roles/shopping_agent/subagents/shipping_address_collector/tools.py",
}
CLIENT_ALIASES = {
    "roles.shopping_agent.remote_agents": ("merchant_agent_client", "credentials_provider_client"),
    "roles.shopping_agent.tools": ("merchant_agent_client", "credentials_provider_client"),
    "roles.shopping_agent.subagents.shopper.tools": ("merchant_agent_client",),
    "roles.shopping_agent.subagents.payment_method_collector.tools": ("credentials_provider_client",),
    "roles.shopping_agent.subagents.shipping_address_collector.tools": ("credentials_provider_client",),
}


class BindingError(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise BindingError(reason)


def regular(path, directory=False):
    path = Path(path)
    need(path.is_absolute(), "Absolute source/environment path required")
    for item in (path, *path.parents):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Linked/reparse binding path refused")
    need(path.is_dir() if directory else path.is_file(), "Regular binding path required")
    return path.resolve()


def digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read(path, bound=32 * 1024 * 1024):
    path = regular(path)
    need(path.stat().st_size <= bound, "Binding input exceeds size bound")
    return path.read_bytes()


def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate binding JSON key")
            value[key] = item
        return value
    def invalid(_):
        raise BindingError("Nonfinite binding JSON")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def inventory(root):
    root = regular(root, True)
    files = {}
    for path in sorted(root.rglob("*")):
        regular(path, path.is_dir())
        if path.is_file():
            need(len(files) < 20000, "Binding tree exceeds file-count bound")
            files[path.relative_to(root).as_posix()] = digest(read(path))
    return files


def relative(value):
    need(type(value) is str and value and "\\" not in value and ":" not in value,
         "Canonical relative source path required")
    path = PurePosixPath(value)
    need(not path.is_absolute() and ".." not in path.parts and path.as_posix() == value,
         "Source path escapes declared tree")
    return value


@dataclass(frozen=True)
class SourceBinding:
    source_root: Path
    environment_root: Path
    stage_path: Path
    environment_path: Path
    stage_raw: bytes = field(repr=False)
    environment_raw: bytes = field(repr=False)
    source_files: dict = field(repr=False)
    environment_files: dict = field(repr=False)

    def verify_unchanged(self):
        need(read(self.stage_path) == self.stage_raw and read(self.environment_path) == self.environment_raw,
             "Frozen binding manifests changed")
        need(digest(self.stage_raw)["sha256"] == STAGE_SHA256
             and digest(self.environment_raw)["sha256"] == ENVIRONMENT_SHA256,
             "Binding object does not contain the frozen manifest bytes")
        stage, environment = strict(self.stage_raw), strict(self.environment_raw)
        expected = {relative(row["path"]): {key: row[key] for key in ("bytes", "sha256")}
                    for row in stage["files"] if row["project"] == "ap2"}
        need(self.source_files == expected and self.environment_files == environment["files"]
             and self.environment_root == regular(environment["root"], True),
             "Binding descriptors differ from the frozen manifests")
        need(inventory(self.source_root) == self.source_files, "Complete AP2 source tree changed")
        need(inventory(self.environment_root) == self.environment_files, "Verified environment tree changed")
        return True

    def source_module(self, name, suffix, supplied):
        path = self.source_root / "code/samples/python/src" / relative(suffix)
        key = path.relative_to(self.source_root).as_posix()
        raw = read(path)
        need(digest(raw) == self.source_files.get(key), "Original module source differs from frozen stage")
        verify_module(supplied, name, path, raw)
        return supplied

    def environment_module(self, name, suffix, supplied, symbols=None):
        key = "Lib/site-packages/" + relative(suffix)
        path = self.environment_root / key
        raw = read(path)
        need(digest(raw) == self.environment_files.get(key), "Runtime module source differs from environment receipt")
        verify_module(supplied, name, path, raw, symbols=symbols)
        return supplied


def validate_inputs(source_root, stage_manifest, environment_manifest):
    """Read/verify frozen trees without executing any original source."""
    source_root = regular(source_root, True)
    stage_path, environment_path = regular(stage_manifest), regular(environment_manifest)
    stage_raw, environment_raw = read(stage_path), read(environment_path)
    need(digest(stage_raw)["sha256"] == STAGE_SHA256, "Frozen 136-file stage manifest required")
    need(digest(environment_raw)["sha256"] == ENVIRONMENT_SHA256, "Verified installed environment manifest required")
    stage, environment = strict(stage_raw), strict(environment_raw)
    need(stage.get("schema_version") == "ap2-hp-pristine-source-stage/1"
         and stage.get("status") == "pristine_source_stage_created" and stage.get("ap2_files") == 136,
         "Unsupported complete original stage")
    source_files = {}
    for row in stage["files"]:
        if row["project"] == "ap2":
            name = relative(row["path"])
            need(name not in source_files, "Duplicate AP2 stage path")
            source_files[name] = {key: row[key] for key in ("bytes", "sha256")}
    need(len(source_files) == 136, "Exact AP2 source union required")
    need(environment.get("schema_version") == "ap2-hp-native-environment/1"
         and environment.get("status") == "installed_hash_verified"
         and environment.get("environment_unchanged_during_assessment") is True
         and environment.get("pip_consistency_passed") is True,
         "Verified environment with explicit retained documentation collisions required")
    environment_root = regular(environment["root"], True)
    environment_files = environment["files"]
    binding = SourceBinding(source_root, environment_root, stage_path, environment_path,
                            stage_raw, environment_raw, source_files, environment_files)
    binding.verify_unchanged()
    return binding


def _codes(code):
    yield code
    for child in code.co_consts:
        if type(child) is types.CodeType:
            yield from _codes(child)


def _default_equal(left, right):
    """Preserve types recursively in supported original literal defaults."""
    if type(left) is not type(right):
        return False
    if type(left) in (tuple, list):
        return len(left) == len(right) and all(_default_equal(a, b) for a, b in zip(left, right))
    if type(left) is dict:
        return len(left) == len(right) and all(
            any(_default_equal(key, other_key) and _default_equal(value, other_value)
                for other_key, other_value in right.items()) for key, value in left.items())
    if type(left) in (set, frozenset):
        return len(left) == len(right) and all(
            any(_default_equal(value, other) for other in right) for value in left)
    return left == right


def _verify_function(function, node, code, namespace, enclosing=None):
    need(type(function) is types.FunctionType and function.__globals__ is namespace,
         "Original callable globals/function identity differs")
    need(marshal.dumps(function.__code__) == marshal.dumps(code), "Loaded original callable code differs")
    def default(item):
        try:
            return ast.literal_eval(item)
        except (ValueError, TypeError):
            if isinstance(item, ast.Name):
                need(item.id in namespace, "Source default global is absent")
                return namespace[item.id]
            if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name):
                module = namespace.get(item.value.id)
                need(type(module) is types.ModuleType and item.attr in module.__dict__,
                     "Source default module constant is absent")
                return module.__dict__[item.attr]
            raise BindingError("Unreviewed original default expression")
    defaults = tuple(default(item) for item in node.args.defaults)
    keyword = {arg.arg: default(value) for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults)
               if value is not None}
    actual_defaults = function.__defaults__ or ()
    need(len(actual_defaults) == len(defaults)
         and all(_default_equal(actual, expected) for actual, expected in zip(actual_defaults, defaults)),
         "Original positional defaults changed")
    need(_default_equal(function.__kwdefaults__ or {}, keyword), "Original keyword defaults changed")
    if function.__closure__:
        need(function.__code__.co_freevars == ("__class__",) and enclosing is not None
             and len(function.__closure__) == 1 and function.__closure__[0].cell_contents is enclosing,
             "Original callable closure differs")


def verify_module(module, name, path, raw, symbols=None):
    """Compile-only source comparison; never exec/import the inspected source."""
    need(type(module) is types.ModuleType and sys.modules.get(name) is module,
         "Exact already imported module object required")
    namespace = module.__dict__
    need(namespace.get("__name__") == name and regular(namespace.get("__file__")) == path.resolve(),
         "Original module name/file origin differs")
    spec = namespace.get("__spec__")
    need(spec is not None and spec.name == name and regular(spec.origin) == path.resolve(),
         "Original module specification origin differs")
    need(sys.flags.optimize == 0, "Unoptimized original source profile required")
    tree = ast.parse(raw, filename=str(path))
    seen = set()
    for node in tree.body:
        if symbols is not None and getattr(node, "name", None) not in symbols:
            continue
        candidates = [(node, namespace.get(node.name), None, node.name)] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
        if isinstance(node, ast.ClassDef):
            cls = namespace.get(node.name)
            need(type(cls) is type and cls.__module__ == name, "Original class identity differs")
            need(not node.decorator_list and not node.keywords, "Unreviewed original class decorator/metaclass")
            bases = []
            for base in node.bases:
                need(isinstance(base, ast.Name) and base.id in namespace, "Unreviewed original class base")
                bases.append(namespace[base.id])
            need(len(cls.__bases__) == len(bases or [object])
                 and all(actual is expected for actual, expected in zip(cls.__bases__, bases or [object])),
                 "Original class bases changed")
            declared = {child.name for child in node.body
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for child in node.body:
                if isinstance(child, ast.Assign):
                    declared.update(target.id for target in child.targets if isinstance(target, ast.Name))
                elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    declared.add(child.target.id)
            metadata = {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__", "__annotations__",
                        "__annotate__", "__annotate_func__", "__static_attributes__", "__firstlineno__"}
            need(set(cls.__dict__) <= declared | metadata, "Original class member footprint changed")
            candidates = [(child, cls.__dict__.get(child.name), cls, node.name + "." + child.name)
                          for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for definition, actual, enclosing, qualified in candidates:
            need(not definition.decorator_list, "Unreviewed original callable decorator")
            need(type(actual) is types.FunctionType and regular(actual.__code__.co_filename) == path.resolve(),
                 "Original callable filename differs")
            compiled = compile(raw, actual.__code__.co_filename, "exec", dont_inherit=True, optimize=0)
            matching = [code for code in _codes(compiled) if code.co_qualname == qualified]
            need(len(matching) == 1, "Original callable code is not unique")
            _verify_function(actual, definition, matching[0], namespace, enclosing)
            seen.add(qualified)
    need(symbols is None or set(symbols) <= seen, "Required source callable is absent")


class OwnedPublicObserver(PublicClientObserver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_calls = 0

    async def _call(self, operation, request=None):
        self.active_calls += 1
        try:
            return await super()._call(operation, request)
        finally:
            self.active_calls -= 1


@dataclass
class CallerBindingLease:
    source: SourceBinding
    bindings: ReferenceBindings
    slots: list = field(repr=False)
    modules: dict = field(repr=False)
    installed: bool = False
    restored: bool = False
    error: object = field(default=None, repr=False)
    validator: object = field(default=None, repr=False)

    def install(self):
        need(not self.installed and not self.restored, "Binding lease is once-only")
        try:
            if self.validator is not None:
                self.validator()
            else:
                self.source.verify_unchanged()
                for name, suffix in SOURCE_MODULES.items():
                    self.source.source_module(name, suffix, self.modules[name])
            for namespace, key, original, proxy in self.slots:
                need(namespace.get(key) is original, "Original client alias changed before installation")
            for namespace, key, original, proxy in self.slots:
                namespace[key] = proxy
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
        if self.bindings.merchant.active_calls or self.bindings.credentials.active_calls:
            self.error = BindingError("Active observed client calls retain binding authority")
            return False
        complete = True
        for namespace, key, original, proxy in self.slots:
            try:
                current = namespace.get(key)
                if current is proxy:
                    namespace[key] = original
                elif current is not original:
                    complete = False
                    self.error = BindingError("Client alias interference; original binding authority retained")
            except BaseException as error:
                complete, self.error = False, error
        self.restored = complete
        return complete

    def report(self):
        return {"status": "original_client_bindings_restored" if self.restored else
                "original_client_bindings_installed" if self.installed else "binding_installation_incomplete",
                "exact_client_alias_count": len(self.slots), "source_manifest_sha256": STAGE_SHA256,
                "environment_manifest_sha256": ENVIRONMENT_SHA256,
                "restoration_authority_retained": not self.restored,
                "error_type": type(self.error).__name__ if self.error is not None else None,
                "original_source_authentication_proven": False, "native_execution_performed_by_adapter": False,
                "transport_peer_ownership_verified": False, "provider_request_hook_verified": False,
                "transitive_sdk_fidelity_verified": False}


def make_caller_binding(source, modules, *, temporary_root, merchant_sink=None, credentials_sink=None):
    """Build a not-yet-installed lease; only exact original aliases are changed."""
    need(set(modules) == set(SOURCE_MODULES), "Exact original caller module membership required")
    need(type(source) is SourceBinding, "Validated original source binding object required")
    source.verify_unchanged()
    checked = {name: source.source_module(name, path, modules[name]) for name, path in SOURCE_MODULES.items()}
    remote = checked["roles.shopping_agent.remote_agents"].__dict__
    client_class = checked["common.payment_remote_a2a_client"].__dict__["PaymentRemoteA2aClient"]
    builder = checked["common.a2a_message_builder"].__dict__["A2aMessageBuilder"]
    artifact = checked["common.artifact_utils"]
    constants = checked["common.constants"].__dict__
    expected_constants = {
        "PAYMENT_MANDATE_SD_JWT_KEY": "ap2.mandates.PaymentMandateSdJwt",
        "CHECKOUT_MANDATE_SD_JWT_KEY": "ap2.mandates.CheckoutMandateSdJwt",
        "PAYMENT_RECEIPT_DATA_KEY": "ap2.PaymentReceipt",
        "DEFAULT_MANDATE_TTL_SECONDS": 3600,
    }
    need(all(typed_equal(constants.get(key), value) for key, value in expected_constants.items()),
         "Original mandate/receipt constants changed")
    temporary_root = regular(temporary_root, True)
    need(constants["TEMP_DB"] == temporary_root
         and constants["AGENT_PROVIDER_KEY_PATH"] == temporary_root / "agent_provider_signing_key.pem"
         and constants["AGENT_PROVIDER_PUB_PATH"] == temporary_root / "agent_provider_signing_key.pub",
         "Original signing-path configuration differs from the owned temporary root")
    originals = {"merchant_agent_client": remote["merchant_agent_client"],
                 "credentials_provider_client": remote["credentials_provider_client"]}
    need(remote["PaymentRemoteA2aClient"] is client_class
         and checked["common.a2a_extension_utils"].__dict__.get("EXTENSION_URI") == EXTENSION
         and remote["EXTENSION_URI"] == EXTENSION
         and typed_equal(checked["common.payment_remote_a2a_client"].__dict__.get("DEFAULT_TIMEOUT"), 600.0),
         "Original registry factory/extension identity differs")
    for key, name, endpoint in (("merchant_agent_client", "merchant_agent", MERCHANT),
                                ("credentials_provider_client", "credentials_provider", CREDENTIALS)):
        client = originals[key]
        need(type(client) is client_class, "Exact original client type required")
        need(set(client.__dict__) == {"_httpx_client", "_a2a_client_factory", "_name", "_base_url",
                                     "_agent_card", "_client_required_extensions"},
             "Original fresh client field footprint differs")
        need(typed_equal(client.__dict__.get("_name"), name)
             and typed_equal(client.__dict__.get("_base_url"), endpoint)
             and typed_equal(client.__dict__.get("_client_required_extensions"), {EXTENSION})
             and client.__dict__.get("_agent_card") is None
             and client.__dict__.get("_httpx_client") is not None
             and client.__dict__.get("_a2a_client_factory") is not None,
             "Fresh original endpoint/extension/card state required")
    merchant = OwnedPublicObserver(originals["merchant_agent_client"], MERCHANT, sink=merchant_sink)
    credentials = OwnedPublicObserver(originals["credentials_provider_client"], CREDENTIALS, sink=credentials_sink)
    slots = [(remote, key, original, merchant if key == "merchant_agent_client" else credentials)
             for key, original in originals.items()]
    for name in SOURCE_MODULES:
        namespace = checked[name].__dict__
        need({key for key in originals if key in namespace} == set(CLIENT_ALIASES.get(name, ())),
             "Original client alias placement differs")
        if name == "roles.shopping_agent.remote_agents":
            continue
        if name in CLIENT_ALIASES:
            need(namespace.get("A2aMessageBuilder") is builder, "Imported original builder alias differs")
        if name in CLIENT_ALIASES and name != "roles.shopping_agent.subagents.shopper.tools":
            need(namespace.get("artifact_utils") is artifact, "Imported artifact helper module differs")
        if name == "roles.shopping_agent.subagents.shopper.tools":
            need(namespace.get("find_canonical_objects") is artifact.__dict__["find_canonical_objects"],
                 "Imported original artifact function differs")
        for key, original in originals.items():
            if key in namespace:
                need(namespace[key] is original, "Imported original client alias differs")
                slots.append((namespace, key, original, merchant if key == "merchant_agent_client" else credentials))
    need(len(slots) == 7, "Exact original seven-client-alias footprint required")
    tools = checked["roles.shopping_agent.tools"].__dict__
    for key in ("AGENT_PROVIDER_KEY_PATH", "AGENT_PROVIDER_PUB_PATH", "CHECKOUT_MANDATE_SD_JWT_KEY",
                "PAYMENT_MANDATE_SD_JWT_KEY", "PAYMENT_RECEIPT_DATA_KEY", "DEFAULT_MANDATE_TTL_SECONDS"):
        need(typed_equal(tools[key], constants[key]), "Imported original constant alias differs")
    shopper = checked["roles.shopping_agent.subagents.shopper.tools"].__dict__
    payment = checked["roles.shopping_agent.subagents.payment_method_collector.tools"].__dict__
    shipping = checked["roles.shopping_agent.subagents.shipping_address_collector.tools"].__dict__
    bindings = ReferenceBindings(merchant, credentials, builder, shopper["find_products"], shopper["select_cart"],
        shipping["get_shipping_address"], payment["get_payment_methods"], payment["get_payment_credential_token"],
        tools["create_checkout"], tools["create_checkout_mandate"], tools["create_payment_mandate"],
        tools["send_signed_mandates_to_credentials_provider"], tools["_store_receipt_if_present"])
    lease = CallerBindingLease(source, bindings, slots, checked)
    def validate_before_install():
        probe = make_caller_binding(source, modules, temporary_root=temporary_root)
        need(all(probe.modules[name] is checked[name] for name in SOURCE_MODULES)
             and len(probe.slots) == len(slots)
             and all(current[0] is expected[0] and current[1] == expected[1] and current[2] is expected[2]
                     for current, expected in zip(probe.slots, slots)),
             "Original client authority changed after lease construction")
        for key, value in bindings.__dict__.items():
            if key not in ("merchant", "credentials"):
                need(getattr(probe.bindings, key) is value, "Original reference callable changed before installation")
    lease.validator = validate_before_install
    return lease
