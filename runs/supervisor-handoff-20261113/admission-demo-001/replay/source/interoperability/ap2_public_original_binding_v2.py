"""Prospective V2 compile-only original-source verifier.

Copied source/module/default/decorator checks from owned binding V1. Code
comparison uses the established V13 structural fingerprint, excluding marshal
reference memoization while preserving typed values, filenames and positions.
No original application, SDK or model is imported or executed by this module.
"""
from __future__ import annotations
import ast
from pathlib import Path
import stat
import struct
import sys
import types
from types import CodeType

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


CODE_FIELDS = (
    'co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals', 'co_stacksize',
    'co_flags', 'co_code', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars',
    'co_filename', 'co_name', 'co_qualname', 'co_firstlineno', 'co_linetable', 'co_exceptiontable',
)


def constant_fingerprint(value):
    """Typed structural constants; serialization reference memoization is excluded."""
    if type(value) is CodeType:
        return code_fingerprint(value)
    if value is None:
        return ('none',)
    if value is Ellipsis:
        return ('ellipsis',)
    if type(value) in (str, int, bool, bytes):
        return (type(value).__name__, value)
    if type(value) is float:
        return ('float', struct.pack('!d', value))
    if type(value) is complex:
        return ('complex', struct.pack('!d', value.real), struct.pack('!d', value.imag))
    if type(value) is tuple:
        return ('tuple', tuple(constant_fingerprint(child) for child in value))
    if type(value) is frozenset:
        return ('frozenset', tuple(sorted((constant_fingerprint(child) for child in value), key=repr)))
    raise ValueError('unsupported_code_constant_type')


def code_fingerprint(code):
    """All code identity attributes plus recursively typed constants and positions."""
    need(type(code) is CodeType, 'exact_code_object_required')
    return ('code', tuple((name, constant_fingerprint(getattr(code, name))) for name in CODE_FIELDS),
            constant_fingerprint(code.co_consts),
            constant_fingerprint(tuple(code.co_lines())),
            constant_fingerprint(tuple(code.co_positions())))


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
    need(code_fingerprint(function.__code__) == code_fingerprint(code), "Loaded original callable code differs")
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
