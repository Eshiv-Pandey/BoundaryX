"""Versioned, descriptive measurements for development benchmark episodes.

This module measures recorded evidence. It does not grade a task, infer task
success from protocol metadata, or define a composite information-loss score.
Only the Python standard library is needed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

EPISODE_SCHEMA_VERSION = "loss_benchmark_episode_v1"
SUMMARY_SCHEMA_VERSION = "loss_benchmark_summary_v1"
EVIDENCE_KINDS = ("fresh_constructed", "retained_bridge", "retained_native")
COST_UNITS = {
    "wall_ms": "milliseconds",
    "messages": "messages",
    "tool_calls": "tool_calls",
    "request_bytes": "bytes",
    "response_bytes": "bytes",
    "model_tokens": "tokens",
}
STAGES = ("source", "sent", "received")
STATUSES = ("pass", "fail", "unknown")
_EPISODE_KEYS = {
    "schema_version", "episode_id", "family_id", "route_id", "evidence_kind",
    "task_completion", "context_items", "capability_items", "fidelity_checks",
    "recovery", "costs", "source_files", "notes",
}


class EpisodeValidationError(ValueError):
    """An episode cannot be interpreted without inventing missing evidence."""


def _require(condition: bool, location: str, message: str) -> None:
    if not condition:
        raise EpisodeValidationError(f"{location}: {message}")


def _object(value: Any, keys: set[str], location: str,
            optional: set[str] | None = None) -> None:
    _require(type(value) is dict, location, "expected object")
    missing = keys - value.keys()
    extra = value.keys() - keys - (optional or set())
    _require(not missing, location, f"missing keys: {sorted(missing)}")
    _require(not extra, location, f"unexpected keys: {sorted(extra)}")


def _string(value: Any, location: str) -> None:
    _require(type(value) is str and bool(value.strip()), location,
             "expected nonempty string")


def _json_value(value: Any, location: str) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        _require(math.isfinite(value), location, "nonfinite JSON number")
        return
    if type(value) is list:
        for index, element in enumerate(value):
            _json_value(element, f"{location}[{index}]")
        return
    if type(value) is dict:
        for key, element in value.items():
            _require(type(key) is str, location, "JSON object keys must be strings")
            _json_value(element, f"{location}.{key}")
        return
    raise EpisodeValidationError(f"{location}: expected a JSON value")


def _items(value: Any, location: str) -> None:
    _require(type(value) is list, location, "expected list")
    seen: set[str] = set()
    for index, item in enumerate(value):
        _require(type(item) is dict, f"{location}[{index}]", "expected object")
        _require("id" in item, f"{location}[{index}]", "missing id")
        _string(item["id"], f"{location}[{index}].id")
        _require(item["id"] not in seen, location, f"duplicate id {item['id']!r}")
        seen.add(item["id"])


def validate_episode(episode: dict[str, Any]) -> None:
    """Validate explicit observations, count types, identities and provenance.

    Missing required keys are invalid; explicit null means unknown only where
    the contract permits it. Known absence is a presence flag of false.
    """
    _object(episode, _EPISODE_KEYS, "episode", {"metadata"})
    _require(episode["schema_version"] == EPISODE_SCHEMA_VERSION,
             "schema_version", f"expected {EPISODE_SCHEMA_VERSION!r}")
    for name in ("episode_id", "family_id", "route_id"):
        _string(episode[name], name)
    _require(episode["evidence_kind"] in EVIDENCE_KINDS, "evidence_kind",
             "unsupported evidence kind")
    _require(episode["task_completion"] in STATUSES, "task_completion",
             "expected pass, fail or unknown")
    if "metadata" in episode:
        _require(type(episode["metadata"]) is dict, "metadata", "expected object")
        _json_value(episode["metadata"], "metadata")

    _items(episode["context_items"], "context_items")
    for index, item in enumerate(episode["context_items"]):
        location = f"context_items[{index}]"
        _object(item, {"id", "source", "sent", "received", "observed", "present"},
                location)
        _object(item["observed"], set(STAGES), f"{location}.observed")
        _object(item["present"], set(STAGES), f"{location}.present")
        for stage in STAGES:
            observed = item["observed"][stage]
            present = item["present"][stage]
            _require(type(observed) is bool, f"{location}.observed.{stage}",
                     "expected boolean")
            _require(present is None or type(present) is bool,
                     f"{location}.present.{stage}", "expected boolean or null")
            _require(observed == (present is not None), location,
                     f"{stage}: unknown presence requires observed=false; "
                     "known presence/absence requires observed=true")
            if present is not True:
                _require(item[stage] is None, f"{location}.{stage}",
                         "unknown or absent stage value must be null")
            _json_value(item[stage], f"{location}.{stage}")

    _items(episode["capability_items"], "capability_items")
    for index, item in enumerate(episode["capability_items"]):
        location = f"capability_items[{index}]"
        _object(item, {"id", "required", "reference_usable", "observed_usable",
                       "advertised"}, location)
        _require(type(item["required"]) is bool, f"{location}.required",
                 "expected boolean")
        for name in ("reference_usable", "observed_usable", "advertised"):
            _require(item[name] is None or type(item[name]) is bool,
                     f"{location}.{name}", "expected boolean or null")

    _items(episode["fidelity_checks"], "fidelity_checks")
    for index, item in enumerate(episode["fidelity_checks"]):
        _object(item, {"id", "status"}, f"fidelity_checks[{index}]")
        _require(item["status"] in STATUSES, f"fidelity_checks[{index}].status",
                 "expected pass, fail or unknown")

    recovery = episode["recovery"]
    _object(recovery, {"eligible", "status"}, "recovery")
    _require(type(recovery["eligible"]) is bool, "recovery.eligible",
             "expected boolean")
    allowed = STATUSES if recovery["eligible"] else ("not_applicable",)
    _require(recovery["status"] in allowed, "recovery.status",
             "eligible recovery needs pass/fail/unknown; ineligible needs not_applicable")

    _object(episode["costs"], set(COST_UNITS), "costs")
    for name, value in episode["costs"].items():
        if value is None:
            continue
        numeric = type(value) in (int, float) if name == "wall_ms" else type(value) is int
        _require(numeric, f"costs.{name}", "expected numeric duration or integer count")
        _require(value >= 0 and (type(value) is int or math.isfinite(value)),
                 f"costs.{name}", "expected finite nonnegative value")

    sources = episode["source_files"]
    _require(type(sources) is list, "source_files", "expected list")
    _require(bool(sources) or episode["evidence_kind"] == "fresh_constructed",
             "source_files", "retained evidence requires hashed source files")
    paths: set[str] = set()
    for index, source in enumerate(sources):
        location = f"source_files[{index}]"
        _object(source, {"path", "sha256"}, location)
        _string(source["path"], f"{location}.path")
        _require(source["path"] not in paths, location, "duplicate source path")
        paths.add(source["path"])
        _require(type(source["sha256"]) is str and
                 re.fullmatch(r"[0-9a-fA-F]{64}", source["sha256"]) is not None,
                 f"{location}.sha256", "expected 64 hexadecimal SHA-256 characters")
    _require(type(episode["notes"]) is list, "notes", "expected list")
    for index, note in enumerate(episode["notes"]):
        _string(note, f"notes[{index}]")


def _same_json(left: Any, right: Any) -> bool:
    """Exact type-sensitive equality; dict order is irrelevant, array order is not."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _same_json(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(
            _same_json(a, b) for a, b in zip(left, right))
    return left == right


def _ratio(numerator: int | float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _rates(statuses: Iterable[str]) -> dict[str, Any]:
    counts = {name: 0 for name in
              ("pass", "fail", "unknown", "eligibility_unknown", "not_applicable")}
    for status in statuses:
        counts[status] += 1
    measured = counts["pass"] + counts["fail"]
    eligible = measured + counts["unknown"]
    candidates = eligible + counts["eligibility_unknown"]
    state = ("not_applicable" if candidates == 0 else
             "unknown" if measured == 0 else
             "partial" if measured < candidates else "measured")
    return {
        "state": state,
        "numerator": counts["pass"], "denominator": measured,
        "failures": counts["fail"], "unknown": counts["unknown"],
        "eligible": eligible, "eligibility_unknown": counts["eligibility_unknown"],
        "not_applicable": counts["not_applicable"], "total": sum(counts.values()),
        "rate": _ratio(counts["pass"], measured),
        "coverage": _ratio(measured, candidates),
        "all_eligible_success_fraction": _ratio(counts["pass"], eligible),
    }


def _context_status(item: dict[str, Any], before: str, after: str) -> str:
    baseline = item["present"][before]
    if baseline is None:
        return "eligibility_unknown"
    if baseline is False:
        return "not_applicable"
    destination = item["present"][after]
    if destination is None:
        return "unknown"
    return "pass" if destination and _same_json(item[before], item[after]) else "fail"


def _scores(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    task = _rates(episode["task_completion"] for episode in episodes)
    task["observed_rate"] = task["rate"]
    task["observed_denominator"] = task["denominator"]
    task["denominator"] = len(episodes)
    task["rate"] = _ratio(task["numerator"], len(episodes))
    task["rate_definition"] = "confirmed_successes / all_attempts"
    task["weighting"] = "attempt_weighted"
    task["known_failure_fraction"] = _ratio(task["failures"], len(episodes))

    facts = [item for episode in episodes for item in episode["context_items"]]
    context: dict[str, Any] = {}
    for name, before, after in (("extraction", "source", "sent"),
                                ("conversion", "sent", "received"),
                                ("end_to_end", "source", "received")):
        rate = _rates(_context_status(item, before, after) for item in facts)
        rate["loss_numerator"] = rate["failures"]
        rate["loss_rate"] = _ratio(rate["failures"], rate["denominator"])
        rate["boundary"] = f"{before}->{after}"
        rate["weighting"] = "fact_item_weighted"
        context[name] = rate

    capabilities = [item for episode in episodes for item in episode["capability_items"]]

    def usability(item: dict[str, Any], name: str) -> str:
        if not item["required"]:
            return "not_applicable"
        value = item[name]
        return "unknown" if value is None else "pass" if value else "fail"

    def retention(item: dict[str, Any]) -> str:
        if not item["required"] or item["reference_usable"] is False:
            return "not_applicable"
        if item["reference_usable"] is None:
            return "eligibility_unknown"
        return usability(item, "observed_usable")

    capability_scores = {
        "required_usability": _rates(usability(item, "observed_usable")
                                     for item in capabilities),
        "reference_qualified_retention": _rates(retention(item) for item in capabilities),
        "advertised_only": _rates(usability(item, "advertised") for item in capabilities),
    }
    for rate in capability_scores.values():
        rate["weighting"] = "capability_item_weighted"
    fidelity = _rates(check["status"] for episode in episodes
                      for check in episode["fidelity_checks"])
    fidelity["weighting"] = "check_item_weighted"
    recovery = _rates(episode["recovery"]["status"] for episode in episodes)
    recovery["weighting"] = "eligible_attempt_weighted"
    overhead: dict[str, Any] = {}
    for name, unit in COST_UNITS.items():
        values = [episode["costs"][name] for episode in episodes
                  if episode["costs"][name] is not None]
        observed = len(values)
        overhead[name] = {
            "unit": unit, "total": sum(values) if values else None,
            "observed": observed, "unknown": len(episodes) - observed,
            "coverage": _ratio(observed, len(episodes)),
            "mean": sum(values) / observed if observed else None,
            "min": min(values) if observed else None,
            "max": max(values) if observed else None,
            "state": "unknown" if not observed else
                     "partial" if observed < len(episodes) else "measured",
        }
    return {
        "task_completion": task, "context_retention": context,
        "capability_usability": capability_scores, "constraint_tool_fidelity": fidelity,
        "recovery_success": recovery, "overhead": overhead,
    }


def score_episode(episode: dict[str, Any]) -> dict[str, Any]:
    """Return six separate operational areas for one validated episode."""
    validate_episode(episode)
    return {"schema_version": SUMMARY_SCHEMA_VERSION,
            "episode_id": episode["episode_id"], "evidence_kind": episode["evidence_kind"],
            "scores": _scores([episode])}


def summarize_episodes(episodes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Describe all attempts, separating evidence kinds and route/family groups.

    A mixed-evidence input has no pooled score. Group totals are descriptive,
    without paired-effect estimates, significance tests, or a composite score.
    """
    records = list(episodes)
    seen: set[str] = set()
    evidence_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for episode in records:
        validate_episode(episode)
        _require(episode["episode_id"] not in seen, "episodes",
                 f"duplicate episode_id {episode['episode_id']!r}")
        seen.add(episode["episode_id"])
        evidence_groups[episode["evidence_kind"]].append(episode)
        route_groups[(episode["evidence_kind"], episode["family_id"],
                      episode["route_id"])].append(episode)
    kinds = sorted(evidence_groups)

    def allow_overview_scores(group: list[dict[str, Any]]) -> bool:
        # Unrelated retained families have different predicates and observation
        # scopes. Their overview exposes counts, not a meaningful pooled rate.
        return bool(group) and (group[0]["evidence_kind"] == "fresh_constructed" or
                                len({record["family_id"] for record in group}) == 1)

    def task_counts(group: list[dict[str, Any]]) -> dict[str, int]:
        return {status: sum(record["task_completion"] == status for record in group)
                for status in STATUSES}

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "episode_count": len(records), "evidence_kinds": kinds,
        "heterogeneous_evidence": len(kinds) > 1,
        "scores": _scores(records) if len(kinds) == 1 and allow_overview_scores(records)
                  else None,
        "task_outcome_counts": task_counts(records),
        "evidence_groups": [
            {"evidence_kind": kind, "episode_count": len(group),
             "family_ids": sorted({record["family_id"] for record in group}),
             "task_outcome_counts": task_counts(group),
             "scores": _scores(group) if allow_overview_scores(group) else None}
            for kind, group in sorted(evidence_groups.items())],
        "route_groups": [
            {"evidence_kind": key[0], "family_id": key[1], "route_id": key[2],
             "episode_count": len(group), "scores": _scores(group)}
            for key, group in sorted(route_groups.items())],
        "limitations": [
            "Operational definitions v1 are new; undefined earlier acronyms are not expanded.",
            "Task status must come from the producer's stated task oracle, not metadata delivery.",
            "Exact context equality measures recorded representation, not semantic utility.",
            "Context/capability/fidelity rates are item-weighted; inspect family/route groups.",
            "Unrelated retained families have outcome counts but no pooled overview scores.",
            "No composite information-loss percentage, causal attribution, p-values or paperscore.",
            "Recorded source hashes are syntax-validated here; artifact integrity needs external verification.",
        ],
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EpisodeValidationError(f"JSON: duplicate object key {key!r}")
        result[key] = value
    return result


def load_episodes(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSON episode/list or a .jsonl/.ndjson stream, rejecting duplicate keys."""
    source = Path(path)
    contents = source.read_text(encoding="utf-8-sig")
    if source.suffix.lower() in (".jsonl", ".ndjson"):
        records = []
        for number, line in enumerate(contents.splitlines(), 1):
            if line.strip():
                try:
                    records.append(json.loads(line, object_pairs_hook=_unique_object))
                except (ValueError, TypeError) as exc:
                    raise EpisodeValidationError(f"{source}:{number}: {exc}") from exc
        return records
    result = json.loads(contents, object_pairs_hook=_unique_object)
    return result if type(result) is list else [result]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = summarize_episodes(load_episodes(args.input))
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(rendered)
        except OSError as exc:
            parser.error(str(exc))
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
