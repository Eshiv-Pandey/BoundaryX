"""Strict finite-model interchange and baseline predicate semantics.

The independent oracle deliberately does not import this module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FIELDS = {
    "schema_version", "id", "route", "provenance", "horizon", "evidence",
    "initial", "states", "transitions", "runtime_contract",
}
SCHEMA = "finite-continuation/1"
SCALAR_TYPES = (str, int, bool, type(None))


def _keys(obj: Any, expected: set[str], label: str) -> None:
    if type(obj) is not dict or set(obj) != expected:
        raise ValueError(f"{label}: expected exactly {sorted(expected)}")


def _text(value: Any, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{label}: expected nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ValueError(f"{label}: expected valid UTF-8 text") from error


def _scalar(value: Any) -> bool:
    if type(value) not in SCALAR_TYPES:
        return False
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            return False
    return True


def validate(manifest: Any) -> dict[str, Any]:
    """Reject malformed/ambiguous inputs instead of scoring them as failures."""
    _keys(manifest, FIELDS, "manifest")
    if manifest["schema_version"] != SCHEMA:
        raise ValueError("unsupported schema_version")
    _text(manifest["id"], "id")
    _text(manifest["route"], "route")
    provenance = manifest["provenance"]
    _keys(provenance, {"kind", "source", "review_status"}, "provenance")
    if provenance["kind"] not in ("authored-development", "wire-derived"):
        raise ValueError("invalid provenance kind")
    _text(provenance["source"], "provenance.source")
    _text(provenance["review_status"], "provenance.review_status")
    horizon = manifest["horizon"]
    if type(horizon) is not int or not 0 <= horizon <= 64:
        raise ValueError("horizon must be an integer in [0, 64]")
    evidence = manifest["evidence"]
    _keys(evidence, {"complete", "observed_at", "valid_until"}, "evidence")
    if type(evidence["complete"]) is not bool:
        raise ValueError("evidence.complete must be boolean")
    for field in ("observed_at", "valid_until"):
        if type(evidence[field]) is not int:
            raise ValueError(f"evidence.{field} must be integer epoch seconds")
    if evidence["valid_until"] < evidence["observed_at"]:
        raise ValueError("evidence interval is inverted")
    states = manifest["states"]
    if type(states) is not dict or not states:
        raise ValueError("states must be a nonempty object")
    for state_id, observables in states.items():
        _text(state_id, "state ID")
        if type(observables) is not dict:
            raise ValueError("state observables must be objects")
        for field, value in observables.items():
            _text(field, "observable field")
            if not _scalar(value):
                raise ValueError("observable must be a JSON string, integer, boolean or null")
    if type(manifest["initial"]) is not str or manifest["initial"] not in states:
        raise ValueError("initial state is absent")
    transitions = manifest["transitions"]
    if type(transitions) is not list:
        raise ValueError("transitions must be a list")
    edge_ids: set[str] = set()
    for transition in transitions:
        _keys(transition, {"id", "source", "target", "operation"}, "transition")
        for field in ("id", "source", "target", "operation"):
            _text(transition[field], f"transition.{field}")
        if transition["id"] in edge_ids:
            raise ValueError("duplicate transition ID")
        edge_ids.add(transition["id"])
        if transition["source"] not in states or transition["target"] not in states:
            raise ValueError("transition endpoint is absent")
    contract = manifest["runtime_contract"]
    _keys(contract, {"goal", "invariants"}, "runtime_contract")
    for section in ("goal", "invariants"):
        if type(contract[section]) is not list:
            raise ValueError(f"{section} must be a predicate list")
        for predicate in contract[section]:
            if type(predicate) is not dict or "op" not in predicate:
                raise ValueError("predicate must declare op")
            op = predicate["op"]
            if type(op) is not str or op not in {"eq", "ne", "lt", "le", "gt", "ge", "in", "eq_field"}:
                raise ValueError("unsupported predicate operator")
            rhs = "other_field" if op == "eq_field" else "value"
            _keys(predicate, {"field", "op", rhs}, "predicate")
            _text(predicate["field"], "predicate.field")
            value = predicate[rhs]
            if op == "eq_field":
                _text(value, "predicate.other_field")
            elif op == "in":
                if type(value) is not list or not all(_scalar(x) for x in value):
                    raise ValueError("in requires a list of scalar values")
            elif not _scalar(value):
                raise ValueError("predicate value must be scalar")
    return manifest


def load(path: str | Path) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle, object_pairs_hook=unique_pairs)
    return validate(data)


def digest(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def predicate_value(observables: dict[str, Any], predicate: dict[str, Any]) -> bool | None:
    field, op = predicate["field"], predicate["op"]
    if field not in observables:
        return None
    left = observables[field]
    if op == "eq_field":
        other = predicate["other_field"]
        return None if other not in observables else _equal(left, observables[other])
    right = predicate["value"]
    if op == "eq":
        return _equal(left, right)
    if op == "ne":
        return not _equal(left, right)
    if op == "in":
        return any(_equal(left, item) for item in right)
    if type(left) is not int or type(right) is not int:
        return None
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    return left >= right


def conjunction(observables: dict[str, Any], predicates: list[dict[str, Any]]) -> bool | None:
    values = [predicate_value(observables, predicate) for predicate in predicates]
    if False in values:
        return False
    return None if None in values else True

