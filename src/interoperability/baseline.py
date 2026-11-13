"""Exact finite layered reachability baseline; no algorithmic novelty claimed."""

from __future__ import annotations

from typing import Any

from .manifest import conjunction, digest, validate


def evaluate(manifest: dict[str, Any], now: int) -> dict[str, Any]:
    validate(manifest)
    if type(now) is not int:
        raise ValueError("now must be integer epoch seconds")
    evidence = manifest["evidence"]
    if not evidence["observed_at"] <= now <= evidence["valid_until"]:
        return {"decision": "unknown", "reason": "evidence_not_fresh", "certificate": None}

    horizon = manifest["horizon"]
    states = manifest["states"]
    contract = manifest["runtime_contract"]
    safe = {s: conjunction(attrs, contract["invariants"]) for s, attrs in states.items()}
    goal = {s: conjunction(attrs, contract["goal"]) for s, attrs in states.items()}
    edges: dict[str, list[dict[str, str]]] = {s: [] for s in states}
    for transition in manifest["transitions"]:
        edges[transition["source"]].append(transition)

    initial = manifest["initial"]
    # Known-safe paths can justify acceptance; possibly safe paths retain uncertainty.
    definite: dict[str, list[str]] = {initial: []} if safe[initial] is True else {}
    possible = {initial} if safe[initial] is not False else set()
    layers: list[list[str]] = []
    uncertain = False
    visits = 0
    edge_checks = 0
    base = {
        "model_sha256": digest(manifest), "checked_at": now,
        "horizon": horizon, "valid_until": evidence["valid_until"],
    }
    for depth in range(horizon + 1):
        layers.append(sorted(definite))
        visits += len(possible)
        uncertain |= any(safe[s] is None or goal[s] is None for s in possible)
        for state_id in sorted(definite):
            if goal[state_id] is True:
                return {
                    "decision": "supported", "reason": "bounded_path",
                    "certificate": {**base, "kind": "path", "transition_ids": definite[state_id]},
                    "stats": {"state_visits": visits, "edge_checks": edge_checks},
                }
        if depth == horizon:
            break
        next_definite: dict[str, list[str]] = {}
        next_possible: set[str] = set()
        for state_id in possible:
            for edge in edges[state_id]:
                edge_checks += 1
                if safe[edge["target"]] is not False:
                    next_possible.add(edge["target"])
        for state_id in sorted(definite):
            for edge in edges[state_id]:
                if safe[edge["target"]] is True and edge["target"] not in next_definite:
                    next_definite[edge["target"]] = definite[state_id] + [edge["id"]]
        definite, possible = next_definite, next_possible

    stats = {"state_visits": visits, "edge_checks": edge_checks}
    if uncertain or not evidence["complete"]:
        return {
            "decision": "unknown",
            "reason": "indeterminate_observables" if uncertain else "incomplete_model",
            "certificate": None, "stats": stats,
        }
    return {
        "decision": "unsupported", "reason": "bounded_no_path",
        "certificate": {**base, "kind": "bounded-cut", "layers": layers},
        "stats": stats,
    }
