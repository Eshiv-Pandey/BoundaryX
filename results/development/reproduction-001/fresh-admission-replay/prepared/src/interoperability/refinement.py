"""Bounded witness-lift/refine prototype over supplied public recipe relations.

This is a CEGAR/lazy-symbolic adaptation, not an established novel algorithm.
Source references and public binding declarations are assumptions supplied by the
profile author, not authenticated provenance or an automatic source compiler.
No application, source file, network request, or model is executed here.
"""
from __future__ import annotations

from collections import deque
from itertools import product
import hashlib
import json
import time
from typing import Any

from .manifest import conjunction, validate as validate_model

SCHEMA = "recipe-continuation/1"
DEFAULT_BUDGET = 100_000
MAX_STATES = 128
MAX_TRANSITIONS = 256
MAX_ARGUMENTS = 8
MAX_CHOICES = 16
MAX_BINDINGS = 128
MAX_EXPRESSION_DEPTH = 16
MAX_EXPRESSION_NODES = 4096
_UNKNOWN = object()
_ABSENT = object()
_STOP = object()


def _name(value: Any, label: str) -> None:
    if type(value) is not str or not value or len(value) > 16_384:
        raise ValueError(f"{label}: expected a bounded nonempty string")
    value.encode("utf-8")


def _scalar(value: Any) -> bool:
    if type(value) not in (str, int, bool, type(None)):
        return False
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            return False
    return True


def _keys(value: Any, expected: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label}: expected exactly {sorted(expected)}")


def _expression(value: Any, arguments: set[str], emitted: bool,
                count: list[int], depth: int = 0) -> None:
    count[0] += 1
    if depth > MAX_EXPRESSION_DEPTH or count[0] > MAX_EXPRESSION_NODES:
        raise ValueError("Expression construction limit exceeded")
    if type(value) is not dict or len(value) != 1:
        raise ValueError("An expression must contain exactly one constructor")
    operation, operand = next(iter(value.items()))
    if operation == "const":
        if not _scalar(operand):
            raise ValueError("Constant must be a JSON scalar")
    elif operation in ("arg", "binding", "unknown"):
        _name(operand, operation)
        if operation == "arg" and operand not in arguments:
            raise ValueError("Expression reads an undeclared caller argument")
    elif operation == "object":
        if type(operand) is not dict or len(operand) > MAX_BINDINGS:
            raise ValueError("Object constructor must be a bounded object")
        for name, child in operand.items():
            _name(name, "object field")
            _expression(child, arguments, emitted, count, depth + 1)
    elif operation == "array":
        if type(operand) is not list or len(operand) > MAX_BINDINGS:
            raise ValueError("Array constructor must be a bounded list")
        for child in operand:
            _expression(child, arguments, emitted, count, depth + 1)
    elif operation == "emit_path":
        if not emitted or type(operand) is not list or len(operand) > MAX_EXPRESSION_DEPTH:
            raise ValueError("emit_path is only valid in guards or updates")
        for item in operand:
            if type(item) is str:
                _name(item, "path field")
            elif type(item) is not int or item < 0:
                raise ValueError("Path elements must be field names or nonnegative indices")
    else:
        raise ValueError("Unknown expression constructor")


def validate(profile: Any) -> dict[str, Any]:
    """Validate the finite supplied-relation boundary; establish no provenance."""
    _keys(profile, {"schema_version", "id", "model", "initial_bindings", "relations", "coverage"}, "profile")
    if profile["schema_version"] != SCHEMA:
        raise ValueError("Unsupported recipe schema")
    _name(profile["id"], "profile.id")
    model = validate_model(profile["model"])
    if len(model["states"]) > MAX_STATES or len(model["transitions"]) > MAX_TRANSITIONS:
        raise ValueError("Prototype finite graph limit exceeded")
    bindings = profile["initial_bindings"]
    if type(bindings) is not dict or len(bindings) > MAX_BINDINGS:
        raise ValueError("Initial public bindings must be a bounded object")
    for name, value in bindings.items():
        _name(name, "binding")
        if not _scalar(value):
            raise ValueError("Public bindings must be JSON scalars")
    _keys(profile["coverage"], {"complete", "scope"}, "coverage")
    if type(profile["coverage"]["complete"]) is not bool:
        raise ValueError("coverage.complete must be boolean")
    _name(profile["coverage"]["scope"], "coverage.scope")
    relations = profile["relations"]
    if type(relations) is not dict or set(relations) != {e["id"] for e in model["transitions"]}:
        raise ValueError("Exactly one supplied relation is required per transition")
    all_bindings = set(bindings)
    for relation in relations.values():
        _keys(relation, {"source_ref", "arguments", "emit", "guards", "updates"}, "relation")
        _name(relation["source_ref"], "source_ref")
        arguments = relation["arguments"]
        if type(arguments) is not dict or len(arguments) > MAX_ARGUMENTS:
            raise ValueError("Caller arguments must be a bounded object")
        for name, recipes in arguments.items():
            _name(name, "caller argument")
            if type(recipes) is not list or len(recipes) > MAX_CHOICES:
                raise ValueError("Caller recipe choices must be a bounded list")
            for recipe in recipes:
                if type(recipe) is not dict or len(recipe) != 1:
                    raise ValueError("A recipe must be exactly literal or binding")
                if "literal" in recipe:
                    if not _scalar(recipe["literal"]):
                        raise ValueError("Literal caller recipe must be a scalar")
                elif "binding" in recipe:
                    _name(recipe["binding"], "public recipe binding")
                else:
                    raise ValueError("Caller recipes cannot choose internal/generated values")
        count = [0]
        _expression(relation["emit"], set(arguments), False, count)
        if type(relation["guards"]) is not list or len(relation["guards"]) > MAX_BINDINGS:
            raise ValueError("Guards must be a bounded list")
        for guard in relation["guards"]:
            if type(guard) is not dict or guard.get("op") not in ("eq", "ne", "present"):
                raise ValueError("Guard operation must be eq, ne or present")
            _keys(guard, {"op", "left"} if guard["op"] == "present" else {"op", "left", "right"}, "guard")
            _expression(guard["left"], set(arguments), True, count)
            if guard["op"] != "present":
                _expression(guard["right"], set(arguments), True, count)
        if type(relation["updates"]) is not dict or len(relation["updates"]) > MAX_BINDINGS:
            raise ValueError("Updates must be a bounded object")
        for name, expression in relation["updates"].items():
            _name(name, "updated public binding")
            all_bindings.add(name)
            _expression(expression, set(arguments), True, count)
    if len(all_bindings) > MAX_BINDINGS:
        raise ValueError("Total declared binding names exceed the finite limit")
    return profile


def digest(profile: dict[str, Any]) -> str:
    raw = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class _Limit(Exception):
    pass


class _Meter:
    def __init__(self, budget: int | None):
        if budget is None:
            budget = DEFAULT_BUDGET
        if type(budget) is not int or budget <= 0:
            raise ValueError("budget must be a positive integer work allowance")
        self.limit = budget
        self.stats = {"work_units": 0, "budget": budget, "abstract_state_visits": 0,
                      "abstract_edge_checks": 0, "abstract_paths": 0,
                      "relation_checks": 0, "expression_evaluations": 0,
                      "refinement_lookups": 0, "refinement_edges": 0,
                      "refinements": 0, "peak_frames": 1}

    def tick(self, category: str) -> None:
        if self.stats["work_units"] >= self.limit:
            raise _Limit
        self.stats["work_units"] += 1
        self.stats[category] += 1


def _contains_unknown(value: Any) -> bool:
    if value is _UNKNOWN:
        return True
    if type(value) is dict:
        return any(_contains_unknown(x) for x in value.values())
    if type(value) is list:
        return any(_contains_unknown(x) for x in value)
    return False


def _equal(left: Any, right: Any) -> bool:
    if left is _ABSENT or right is _ABSENT:
        return left is right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _expr(expression: dict[str, Any], args: dict[str, Any], frame: dict[str, Any],
          request: Any, meter: _Meter) -> Any:
    meter.tick("expression_evaluations")
    operation, value = next(iter(expression.items()))
    if operation == "const":
        return value
    if operation == "arg":
        return args.get(value, _UNKNOWN)
    if operation == "binding":
        return frame.get(value, _UNKNOWN)
    if operation == "unknown":
        return _UNKNOWN
    if operation == "object":
        return {key: _expr(child, args, frame, request, meter) for key, child in value.items()}
    if operation == "array":
        return [_expr(child, args, frame, request, meter) for child in value]
    current = request
    for key in value:
        if current is _UNKNOWN:
            return _UNKNOWN
        if type(key) is str and type(current) is dict:
            current = current.get(key, _ABSENT)
        elif type(key) is int and type(current) is list and key < len(current):
            current = current[key]
        else:
            return _ABSENT
    return current


def _guard(guard: dict[str, Any], args: dict[str, Any], frame: dict[str, Any],
           request: Any, meter: _Meter) -> bool | None:
    left = _expr(guard["left"], args, frame, request, meter)
    if guard["op"] == "present":
        return None if left is _UNKNOWN else left is not _ABSENT
    right = _expr(guard["right"], args, frame, request, meter)
    if _contains_unknown(left) or _contains_unknown(right):
        return None
    equal = _equal(left, right)
    return equal if guard["op"] == "eq" else not equal


def _arguments(relation: dict[str, Any], frame: dict[str, Any]):
    names = list(relation["arguments"])
    choices = []
    for name in names:
        values = []
        for recipe in relation["arguments"][name]:
            if "literal" in recipe:
                values.append(recipe["literal"])
            elif recipe["binding"] in frame:
                values.append(frame[recipe["binding"]])
        choices.append(values)
    for values in product(*choices):
        yield dict(zip(names, values))


def _lift(profile: dict[str, Any], path: tuple[str, ...], edges: dict[str, Any],
          safe: dict[str, bool | None], goal: dict[str, bool | None], meter: _Meter):
    """Retain correlated whole frames; prove an entire prefix empty before learning."""
    frontier = [(dict(profile["initial_bindings"]), [])]
    unknown = safe[profile["model"]["initial"]] is None
    contract_known = not unknown
    state = profile["model"]["initial"]
    for index, edge_id in enumerate(path):
        edge = edges[edge_id]
        relation = profile["relations"][edge_id]
        next_frames = {}
        for frame, steps in frontier:
            for args in _arguments(relation, frame):
                meter.tick("relation_checks")
                request = _expr(relation["emit"], args, frame, None, meter)
                values = [_guard(g, args, frame, request, meter) for g in relation["guards"]]
                # A definite false conjunct refutes even a partly unknown request.
                if False in values:
                    continue
                if None in values or _contains_unknown(request):
                    unknown = True
                    continue
                updates = {name: _expr(expr, args, frame, request, meter)
                           for name, expr in relation["updates"].items()}
                if any(not _scalar(value) for value in updates.values()):
                    unknown = True
                    continue
                changed = dict(frame, **updates)
                step = {"edge": edge_id, "args": args, "request": request,
                        "bindings_before": dict(frame), "bindings_after": dict(changed)}
                # May-completion needs one fully known witness. Do not exhaust
                # the remaining argument product after this final step proves it.
                if (index == len(path) - 1 and contract_known
                        and safe[edge["target"]] is True and goal[edge["target"]] is True):
                    return "supported", steps + [step]
                key = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                next_frames.setdefault(key, (changed, steps + [step]))
        frontier = list(next_frames.values())
        meter.stats["peak_frames"] = max(meter.stats["peak_frames"], len(frontier))
        state = edge["target"]
        if safe[state] is None:
            unknown = True
            contract_known = False
        if not frontier:
            return ("unknown", None) if unknown else ("refuted", path[:index + 1])
    if frontier and contract_known and goal[state] is True:
        return "supported", frontier[0][1]
    return "unknown", None


def _blocked(path: tuple[str, ...], trie: dict[Any, Any], meter: _Meter) -> bool:
    node = trie
    for edge in path:
        meter.tick("refinement_lookups")
        if _STOP in node:
            return True
        if edge not in node:
            return False
        node = node[edge]
    return _STOP in node


def evaluate(profile: dict[str, Any], now: int, budget: int | None = None) -> dict[str, Any]:
    """Decide conditional realizable may-completion for the supplied finite profile."""
    started = time.perf_counter_ns()
    validate(profile)
    if type(now) is not int:
        raise ValueError("now must be integer epoch seconds")
    meter = _Meter(budget)
    model = profile["model"]
    evidence = model["evidence"]

    def result(decision: str, reason: str, certificate=None):
        return {"decision": decision, "reason": reason, "certificate": certificate,
                "method": "witness-lift-refine-prototype", "novelty_established": False,
                "stats": dict(meter.stats, elapsed_ns=time.perf_counter_ns() - started)}

    if not evidence["observed_at"] <= now <= evidence["valid_until"]:
        return result("unknown", "evidence_not_fresh")
    header = {"profile_sha256": digest(profile), "checked_at": now,
              "horizon": model["horizon"], "valid_until": evidence["valid_until"]}
    contract = model["runtime_contract"]
    safe = {name: conjunction(value, contract["invariants"]) for name, value in model["states"].items()}
    goal = {name: conjunction(value, contract["goal"]) for name, value in model["states"].items()}
    edges = {edge["id"]: edge for edge in model["transitions"]}
    outgoing = {name: [] for name in model["states"]}
    for edge in model["transitions"]:
        outgoing[edge["source"]].append(edge)
    initial = model["initial"]
    refinements: list[list[str]] = []
    trie: dict[Any, Any] = {}
    unresolved = False
    contract_uncertain = False
    try:
        # Retain v1's deliberately conservative contracted-observable rule.
        layer = {initial} if safe[initial] is not False else set()
        for depth in range(model["horizon"] + 1):
            following = set()
            for state in sorted(layer):
                meter.tick("abstract_state_visits")
                contract_uncertain |= safe[state] is None or goal[state] is None
                if depth < model["horizon"]:
                    for edge in outgoing[state]:
                        meter.tick("abstract_edge_checks")
                        if safe[edge["target"]] is not False:
                            following.add(edge["target"])
            layer = following
        queue = deque([(initial, ())]) if safe[initial] is not False else deque()
        while queue:
            state, path = queue.popleft()
            meter.tick("abstract_state_visits")
            if _blocked(path, trie, meter):
                continue
            if goal[state] is not False:
                meter.tick("abstract_paths")
                disposition, detail = _lift(profile, path, edges, safe, goal, meter)
                if disposition == "supported":
                    return result("supported", "public_recipe_witness", {
                        **header, "kind": "recipe-path", "transition_ids": list(path), "steps": detail})
                if disposition == "refuted":
                    refinements.append(list(detail))
                    meter.stats["refinements"] += 1
                    node = trie
                    for edge in detail:
                        meter.tick("refinement_edges")
                        node = node.setdefault(edge, {})
                    node[_STOP] = True
                    continue
                unresolved = True
            if len(path) < model["horizon"]:
                for edge in outgoing[state]:
                    meter.tick("abstract_edge_checks")
                    if safe[edge["target"]] is not False:
                        queue.append((edge["target"], path + (edge["id"],)))
    except _Limit:
        return result("unknown", "work_budget_exhausted")
    if contract_uncertain:
        return result("unknown", "indeterminate_observables")
    if unresolved:
        return result("unknown", "unresolved_relation_or_recipe")
    if not evidence["complete"] or not profile["coverage"]["complete"]:
        return result("unknown", "incomplete_model_or_relation_coverage")
    return result("unsupported", "certified_refinement_exhaustion", {
        **header, "kind": "refinement-exhaustion", "refuted_prefixes": refinements})
