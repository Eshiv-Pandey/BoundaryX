"""Independent, exhaustive oracle for the finite-continuation/1 abstraction.

This module deliberately imports no baseline, schema, predicate or transition
implementation. Its search enumerates finite paths depth first. Certificate
checking replays a positive path or reconstructs a negative finite closure.
Agreement is evidence about this declared finite model, not protocol fidelity,
actual bridge execution, human independent review, or adversarial strategies.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_TOP_FIELDS = {
    "schema_version", "id", "route", "provenance", "horizon", "evidence",
    "initial", "states", "transitions", "runtime_contract",
}
_OPERATORS = {"eq", "ne", "lt", "le", "gt", "ge", "in", "eq_field"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _object(value: Any, fields: set[str], label: str) -> None:
    _require(type(value) is dict, f"{label} must be an object")
    _require(set(value) == fields, f"{label} has missing or unknown fields")


def _text(value: Any, label: str, *, nonempty: bool = True) -> None:
    _require(type(value) is str, f"{label} must be a string")
    _require(not nonempty or len(value) > 0, f"{label} must be nonempty")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8 text") from exc


def _scalar(value: Any, label: str) -> None:
    _require(type(value) in (str, bool, int, type(None)),
             f"{label} must be a JSON string, boolean, integer or null")
    if type(value) is str:
        _text(value, label, nonempty=False)


def _validate(manifest: Any, now: Any) -> None:
    """Validate the wire shape locally; invalid inputs are never decisions."""
    _require(type(now) is int, "now must be integer UTC epoch seconds")
    _object(manifest, _TOP_FIELDS, "manifest")
    _text(manifest["schema_version"], "schema_version")
    _require(manifest["schema_version"] == "finite-continuation/1",
             "unsupported schema_version")
    _text(manifest["id"], "id")
    _text(manifest["route"], "route")
    provenance = manifest["provenance"]
    _object(provenance, {"kind", "source", "review_status"}, "provenance")
    _text(provenance["kind"], "provenance.kind")
    _require(provenance["kind"] in {"authored-development", "wire-derived"},
             "unknown provenance.kind")
    _text(provenance["source"], "provenance.source")
    _text(provenance["review_status"], "provenance.review_status")
    horizon = manifest["horizon"]
    _require(type(horizon) is int and 0 <= horizon <= 64,
             "horizon must be an integer from 0 through 64")
    evidence = manifest["evidence"]
    _object(evidence, {"complete", "observed_at", "valid_until"}, "evidence")
    _require(type(evidence["complete"]) is bool, "evidence.complete must be boolean")
    for field in ("observed_at", "valid_until"):
        _require(type(evidence[field]) is int, f"evidence.{field} must be integer")
    _require(evidence["observed_at"] <= evidence["valid_until"],
             "evidence validity interval is reversed")
    states = manifest["states"]
    _require(type(states) is dict and len(states) > 0, "states must be a nonempty object")
    for state_id, observables in states.items():
        _text(state_id, "state id")
        _require(type(observables) is dict, "state observables must be objects")
        for field, value in observables.items():
            _text(field, "observable field")
            _scalar(value, "observable value")
    _text(manifest["initial"], "initial")
    _require(manifest["initial"] in states, "initial references an unknown state")
    transitions = manifest["transitions"]
    _require(type(transitions) is list, "transitions must be a list")
    edge_ids: set[str] = set()
    for edge in transitions:
        _object(edge, {"id", "source", "target", "operation"}, "transition")
        for field in ("id", "source", "target", "operation"):
            _text(edge[field], f"transition.{field}")
        _require(edge["id"] not in edge_ids, "duplicate transition id")
        edge_ids.add(edge["id"])
        _require(edge["source"] in states and edge["target"] in states,
                 "transition endpoint references an unknown state")
    contract = manifest["runtime_contract"]
    _object(contract, {"goal", "invariants"}, "runtime_contract")
    for role in ("goal", "invariants"):
        _require(type(contract[role]) is list, f"{role} must be a list")
        for predicate in contract[role]:
            _require(type(predicate) is dict, "predicate must be an object")
            _text(predicate.get("op"), "predicate.op")
            op = predicate["op"]
            _require(op in _OPERATORS, "unknown predicate operator")
            fields = {"field", "op", "other_field" if op == "eq_field" else "value"}
            _object(predicate, fields, "predicate")
            _text(predicate["field"], "predicate.field")
            if op == "eq_field":
                _text(predicate["other_field"], "predicate.other_field")
            elif op == "in":
                _require(type(predicate["value"]) is list, "in requires a scalar list")
                for operand in predicate["value"]:
                    _scalar(operand, "in operand")
            else:
                # Bad ordered operand types are well-formed but indeterminate.
                _scalar(predicate["value"], "predicate.value")


def _same(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _predicate_truth(observables: dict[str, Any], predicate: dict[str, Any]) -> bool | None:
    field = predicate["field"]
    if field not in observables:
        return None
    left = observables[field]
    op = predicate["op"]
    if op == "eq_field":
        other = predicate["other_field"]
        return None if other not in observables else _same(left, observables[other])
    right = predicate["value"]
    if op == "eq":
        return _same(left, right)
    if op == "ne":
        return not _same(left, right)
    if op == "in":
        return any(_same(left, member) for member in right)
    if type(left) is not int or type(right) is not int:
        return None
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    return left >= right


def _all_truth(observables: dict[str, Any], predicates: list[dict[str, Any]]) -> bool | None:
    indeterminate = False
    for predicate in predicates:
        value = _predicate_truth(observables, predicate)
        if value is False:
            return False
        if value is None:
            indeterminate = True
    return None if indeterminate else True


def _digest(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _certificate_header(manifest: dict[str, Any], now: int) -> dict[str, Any]:
    return {
        "model_sha256": _digest(manifest),
        "checked_at": now,
        "horizon": manifest["horizon"],
        "valid_until": manifest["evidence"]["valid_until"],
    }


def evaluate(manifest: dict[str, Any], now: int) -> dict[str, Any]:
    """Enumerate finite paths and return a conditional decision/certificate.

    Raises ValueError for a malformed manifest or noninteger clock. A complete
    negative search may be exponential in the horizon; this is an independent
    small-model oracle, not a scalable production solver.
    """
    _validate(manifest, now)
    evidence = manifest["evidence"]
    if not evidence["observed_at"] <= now <= evidence["valid_until"]:
        return {"decision": "unknown", "reason": "Evidence is stale or future-dated.",
                "certificate": None, "stats": {"path_nodes": 0}}

    states = manifest["states"]
    contract = manifest["runtime_contract"]
    outgoing: dict[str, list[dict[str, Any]]] = {state: [] for state in states}
    for transition in manifest["transitions"]:
        outgoing[transition["source"]].append(transition)
    uncertainty = False
    path_nodes = 0

    def visit(state: str, path: list[str], definite_prefix: bool) -> list[str] | None:
        nonlocal uncertainty, path_nodes
        path_nodes += 1
        invariants = _all_truth(states[state], contract["invariants"])
        if invariants is False:
            return None
        goal = _all_truth(states[state], contract["goal"])
        if invariants is None or goal is None:
            uncertainty = True
        safe_prefix = definite_prefix and invariants is True
        if safe_prefix and goal is True:
            return path
        if len(path) == manifest["horizon"]:
            return None
        for transition in outgoing[state]:
            accepted = visit(transition["target"], path + [transition["id"]], safe_prefix)
            if accepted is not None:
                return accepted
        return None

    witness = visit(manifest["initial"], [], True)
    stats = {"path_nodes": path_nodes}
    if witness is not None:
        certificate = _certificate_header(manifest, now)
        certificate.update(kind="path", transition_ids=witness)
        return {"decision": "supported",
                "reason": "A modeled invariant-safe path satisfies the runtime goal within the horizon.",
                "certificate": certificate, "stats": stats}
    if not evidence["complete"] or uncertainty:
        return {"decision": "unknown",
                "reason": "The finite evidence is incomplete or a relevant observable is indeterminate.",
                "certificate": None, "stats": stats}

    # The exhaustive path search established known safety/goal truth. Package
    # its negative conclusion as exact safe-state layers for external replay.
    first = manifest["initial"]
    current = {first} if _all_truth(states[first], contract["invariants"]) is True else set()
    layers = [sorted(current)]
    for _ in range(manifest["horizon"]):
        successors: set[str] = set()
        for source in current:
            for transition in outgoing[source]:
                target = transition["target"]
                if _all_truth(states[target], contract["invariants"]) is True:
                    successors.add(target)
        current = successors
        layers.append(sorted(current))
    certificate = _certificate_header(manifest, now)
    certificate.update(kind="bounded-cut", layers=layers)
    return {"decision": "unsupported",
            "reason": "No accepted path exists in the fresh, declared-complete finite model.",
            "certificate": certificate, "stats": stats}


def check_certificate(manifest: dict[str, Any], result: dict[str, Any], now: int) -> bool:
    """Check a conclusive certificate by path replay or full finite closure.

    Returns False for unknown (there is no proof), malformed inputs, expired
    evidence, future certificates or changed manifests. This cannot certify
    that an authored development graph represents an actual protocol bridge.
    """
    try:
        _validate(manifest, now)
        _require(type(result) is dict, "result must be an object")
        _require(set(result) in ({"decision", "reason", "certificate"},
                                {"decision", "reason", "certificate", "stats"}),
                 "result has missing or unknown fields")
        _text(result["decision"], "result.decision")
        _text(result["reason"], "result.reason")
        if "stats" in result:
            _require(type(result["stats"]) is dict, "stats must be an object")
        decision = result["decision"]
        _require(decision in {"supported", "unsupported"}, "no conclusive decision")
        certificate = result["certificate"]
        common = {"kind", "model_sha256", "checked_at", "horizon", "valid_until"}
        detail = "transition_ids" if decision == "supported" else "layers"
        _object(certificate, common | {detail}, "certificate")
        expected_kind = "path" if decision == "supported" else "bounded-cut"
        _text(certificate["kind"], "certificate.kind")
        _require(certificate["kind"] == expected_kind, "certificate kind disagrees with decision")
        _require(type(certificate["model_sha256"]) is str
                 and certificate["model_sha256"] == _digest(manifest), "model digest mismatch")
        for field in ("checked_at", "horizon", "valid_until"):
            _require(type(certificate[field]) is int, f"certificate.{field} must be integer")
        _require(certificate["horizon"] == manifest["horizon"], "changed horizon")
        evidence = manifest["evidence"]
        _require(certificate["valid_until"] == evidence["valid_until"], "changed validity limit")
        _require(evidence["observed_at"] <= certificate["checked_at"] <= now
                 <= evidence["valid_until"], "certificate outside evidence validity interval")
        states = manifest["states"]
        contract = manifest["runtime_contract"]

        if decision == "supported":
            ids = certificate["transition_ids"]
            _require(type(ids) is list and len(ids) <= manifest["horizon"], "invalid path length")
            state = manifest["initial"]
            _require(_all_truth(states[state], contract["invariants"]) is True,
                     "initial invariants are not definitely true")
            by_id = {edge["id"]: edge for edge in manifest["transitions"]}
            for transition_id in ids:
                _text(transition_id, "path transition id")
                _require(transition_id in by_id, "path references unknown transition")
                edge = by_id[transition_id]
                _require(edge["source"] == state, "path endpoints do not join")
                state = edge["target"]
                _require(_all_truth(states[state], contract["invariants"]) is True,
                         "path invariants are not definitely true")
            _require(_all_truth(states[state], contract["goal"]) is True,
                     "final goal is not definitely true")
            return True

        _require(evidence["complete"], "negative evidence is incomplete")
        layers = certificate["layers"]
        _require(type(layers) is list and len(layers) == manifest["horizon"] + 1,
                 "invalid layer count")
        initial = manifest["initial"]
        initial_safety = _all_truth(states[initial], contract["invariants"])
        _require(initial_safety is not None, "indeterminate initial invariants")
        expected = {initial} if initial_safety is True else set()
        for depth, layer in enumerate(layers):
            _require(type(layer) is list, "layer must be a list")
            for state_id in layer:
                _text(state_id, "layer state id")
                _require(state_id in states, "layer references unknown state")
            _require(layer == sorted(set(layer)), "layers must be sorted and unique")
            _require(layer == sorted(expected), "layer is not the complete finite closure")
            for state in expected:
                _require(_all_truth(states[state], contract["goal"]) is False,
                         "reachable goal is true or indeterminate")
            if depth < manifest["horizon"]:
                next_expected: set[str] = set()
                # Scan the manifest's entire edge list: a certificate cannot
                # hide a branch by omitting its successor from a supplied cut.
                for edge in manifest["transitions"]:
                    if edge["source"] not in expected:
                        continue
                    target = edge["target"]
                    safety = _all_truth(states[target], contract["invariants"])
                    _require(safety is not None, "reachable invariants are indeterminate")
                    if safety is True:
                        next_expected.add(target)
                expected = next_expected
        return True
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False
