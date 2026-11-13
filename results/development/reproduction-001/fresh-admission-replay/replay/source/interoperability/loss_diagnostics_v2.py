"""Task-conditioned boundary diagnostics and exhaustive finite repair certificates.

These diagnostics describe recorded JSON and explicitly executed interventions.
They do not infer natural-language meaning, population effects, or optimal repairs
outside the declared finite field groups and receiver policy.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from itertools import combinations
import json
from typing import Callable, Any

REPAIR_GROUPS = {
    "records": (("records",),),
    "task_identity": (("task", "task_id"), ("task", "target")),
    "constraints": (("task", "constraints"),),
    "tool_binding": (("tool_binding",),),
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def same_json(left: Any, right: Any) -> bool:
    return canonical(left) == canonical(right)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _lookup(value: Any, path: tuple) -> tuple[bool, Any]:
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return False, None
        value = value[key]
    return True, value


def restore_groups(observed: dict, reference: dict, groups: list[str]) -> dict:
    if len(groups) != len(set(groups)) or any(g not in REPAIR_GROUPS for g in groups):
        raise ValueError("repair groups must be unique declared groups")
    restored = deepcopy(observed)
    for group in groups:
        for path in REPAIR_GROUPS[group]:
            present, value = _lookup(reference, path)
            parent = restored
            for key in path[:-1]:
                if not isinstance(parent.get(key), dict):
                    parent[key] = {}
                parent = parent[key]
            if present:
                parent[path[-1]] = deepcopy(value)
            else:
                parent.pop(path[-1], None)
    return restored


def changed_groups(reference: dict, observed: dict) -> list[str]:
    return [group for group, paths in REPAIR_GROUPS.items()
            if any(not same_json(_lookup(reference, p), _lookup(observed, p)) for p in paths)]


def leaf_values(value: Any, path: str = "") -> dict[str, Any]:
    """Disjoint JSON leaves, with empty arrays/objects retained as explicit values."""
    if isinstance(value, dict) and value:
        result = {}
        for key in sorted(value):
            escaped = key.replace("~", "~0").replace("/", "~1")
            result.update(leaf_values(value[key], path + "/" + escaped))
        return result
    if isinstance(value, list) and value:
        result = {}
        for index, item in enumerate(value):
            result.update(leaf_values(item, path + "/" + str(index)))
        return result
    return {path or "/": value}


def boundary_diff(before: dict | None, after: dict | None,
                  normalize_record_order: bool = False) -> dict:
    if before is None or after is None:
        return {"status": "unknown", "reason": "boundary not captured", "rate": None}
    before, after = deepcopy(before), deepcopy(after)
    if normalize_record_order:
        for value in (before, after):
            if isinstance(value.get("records"), list):
                value["records"] = sorted(value["records"], key=canonical)
    left, right = leaf_values(before), leaf_values(after)
    kept = [p for p in left if p in right and same_json(left[p], right[p])]
    changed = [p for p in left if p in right and not same_json(left[p], right[p])]
    missing = [p for p in left if p not in right]
    added = [p for p in right if p not in left]
    return {"status": "measured", "unit": "reference JSON leaf at frozen JSON pointer",
            "normalization": "canonical full-record sort, duplicate preserving" if normalize_record_order else "exact JSON",
            "eligible_leaves": len(left), "kept": len(kept), "changed": len(changed),
            "missing": len(missing), "added": len(added), "rate": len(kept) / len(left),
            "kept_paths": kept, "changed_paths": changed, "missing_paths": missing,
            "added_paths": added, "before_sha256": digest(before), "after_sha256": digest(after)}


def diagnose_repairs(reference: dict, observed: dict,
                     evaluate: Callable[[dict], dict]) -> dict:
    """Execute the complete subset lattice, retaining unsuccessful interventions.

    The reference is an authorized source snapshot. Every evaluation uses a new
    receiver invocation under the same policy and task predicate. Repairs count
    field groups, not bytes or runtime cost. A certificate is inclusion-minimal,
    with a separate minimum cardinality, only within this four-group universe.
    """
    changed = changed_groups(reference, observed)
    trials = []
    for size in range(len(changed) + 1):
        for subset in combinations(changed, size):
            payload = restore_groups(observed, reference, list(subset))
            result = evaluate(deepcopy(payload))
            if result.get("task_completion") not in ("pass", "fail", "unknown"):
                raise ValueError("evaluator must declare pass/fail/unknown")
            trials.append({"restore": list(subset), "payload_sha256": digest(payload),
                           "assessment": deepcopy(result)})
    successful = [set(t["restore"]) for t in trials if t["assessment"]["task_completion"] == "pass"]
    minimal = [s for s in successful if not any(other < s for other in successful)]
    unknown = sum(t["assessment"]["task_completion"] == "unknown" for t in trials)
    return {"schema_version": "finite_repair_certificate_v2",
            "reference_sha256": digest(reference), "observed_sha256": digest(observed),
            "universe": list(REPAIR_GROUPS), "changed_groups": changed,
            "trial_count": len(trials), "trials": trials,
            "minimal_repair_sets": [sorted(s) for s in minimal],
            "minimum_repair_group_count": min(map(len, minimal)) if minimal else None,
            "status": "complete" if unknown == 0 else "partial", "unknown_trials": unknown,
            "scope": "exhaustively evaluated field-group repairs on this captured source and fixed receiver; no general optimality claim"}


def verify_repair_certificate(certificate: dict, reference: dict, observed: dict,
                              evaluate: Callable[[dict], dict]) -> dict:
    """Re-execute interventions; verify outcomes, payloads, census and minimality."""
    rebuilt = diagnose_repairs(reference, observed, evaluate)
    if not same_json(certificate, rebuilt):
        raise ValueError("repair certificate disagrees with independent re-execution")
    return {"status": "passed", "interventions_reexecuted": rebuilt["trial_count"],
            "minimal_repair_sets": rebuilt["minimal_repair_sets"]}


def paired_outcomes(reference: list[dict], comparison: list[dict]) -> dict:
    """Exact paired finite-bank counts. Missing/unknown pairs never become failures."""
    def index(rows):
        mapping = {}
        for row in rows:
            pair = row["pair_id"]
            if pair in mapping or row["task_completion"] not in ("pass", "fail", "unknown"):
                raise ValueError("invalid or duplicate pair")
            mapping[pair] = row["task_completion"]
        return mapping
    left, right = index(reference), index(comparison)
    pairs = sorted(left.keys() & right.keys())
    census = {"both_pass": 0, "both_fail": 0, "reference_only": 0, "comparison_only": 0, "unknown": 0}
    for pair in pairs:
        a, b = left[pair], right[pair]
        key = "unknown" if "unknown" in (a, b) else ("both_pass" if a == b == "pass" else
              "both_fail" if a == b == "fail" else "reference_only" if a == "pass" else "comparison_only")
        census[key] += 1
    known = len(pairs) - census["unknown"]
    return {"matched_pairs": len(pairs), "unmatched_reference": sorted(left.keys() - right.keys()),
            "unmatched_comparison": sorted(right.keys() - left.keys()), "outcomes": census,
            "known_pair_coverage": known / len(pairs) if pairs else None,
            "observed_pass_difference": (census["comparison_only"] - census["reference_only"]) / known if known else None,
            "scope": "descriptive paired bank result; no independence, prevalence or population significance claim"}
