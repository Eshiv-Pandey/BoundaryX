"""Call-local cache ablations of frozen shared lifting v2.

The both-enabled arm preserves v2 deterministic certificates and counters.
Each disabled cache removes only its lookup/publication and retained entries.
Complete-frame deduplication, JSON typing, history, unknown propagation and
independent certificate checking remain the same. Representation-copy work
retains its historical cache_payload_nodes category even without either cache.
Ordinary memoization does not establish algorithmic novelty.
Frozen predecessor SHA256: 927538f7ddcb21120913c6c4257754b65a45703db384eec8cd6a28ba9e9b280b.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import time
from typing import Any

from . import refinement as core


POLICIES = {"neither": (False, False), "prefix": (True, False),
            "relation": (False, True), "both": (True, True)}

METHOD = "shared-cache-ablation-v3"
CACHE_WORK = ("cache_lookups", "cache_key_nodes", "cache_insertions",
              "cache_payload_nodes", "cache_status_checks", "cached_prefix_frames",
              "cached_relation_outcomes", "history_nodes", "witness_nodes")


class _Meter(core._Meter):
    def __init__(self, budget):
        super().__init__(budget)
        self.stats.update({name: 0 for name in CACHE_WORK})
        self.stats.update(prefix_cache_hits=0, relation_cache_hits=0,
                          prefix_cache_entries=0, relation_cache_entries=0,
                          peak_cached_frames=0)


@dataclass(frozen=True, slots=True)
class _History:
    previous: _History | None
    step: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Frame:
    bindings: dict[str, Any]
    history: _History | None


@dataclass(frozen=True, slots=True)
class _PrefixSummary:
    path: tuple[str, ...]
    state: str
    frontier: tuple[_Frame, ...]
    unknown: bool
    contract_known: bool


@dataclass(frozen=True, slots=True)
class _RelationSummary:
    # These local steps and their owned JSON values are never mutated. No
    # history is included: reuse attaches each step to the current prefix.
    steps: tuple[dict[str, Any], ...]
    unknown: bool


class _SharedLift:
    """One invocation's memo. No entry or decision escapes into another call."""

    def __init__(self, profile, edges, safe, goal, meter, *, prefix_cache=True, relation_cache=True):
        if type(prefix_cache) is not bool or type(relation_cache) is not bool:
            raise ValueError("Cache switches must be booleans")
        self.prefix_cache, self.relation_cache = prefix_cache, relation_cache
        self.profile, self.edges = profile, edges
        self.safe, self.goal, self.meter = safe, goal, meter
        self._prefixes: dict[tuple[str, ...], _PrefixSummary] = {}
        self._relations: dict[tuple[str, str], _RelationSummary] = {}
        self._cached_frames = 0

    def _walk(self, value, category, *, copy=False):
        """Charge every JSON node and object key copied or traversed.

        A scalar string is one component, not one unit per character. Encoding,
        hashing and string-byte costs additionally remain in elapsed time and
        external process measurements, as do profile validation/serialization.
        """
        self.meter.tick(category)
        if type(value) is dict:
            output = {} if copy else None
            for key, child in value.items():
                self.meter.tick(category)
                item = self._walk(child, category, copy=copy)
                if copy:
                    output[key] = item
            return output
        if type(value) in (list, tuple):
            output = [] if copy else None
            for child in value:
                item = self._walk(child, category, copy=copy)
                if copy:
                    output.append(item)
            return output
        return value if copy else None

    def _frame_key(self, frame):
        self._walk(frame, "cache_key_nodes")
        return json.dumps(frame, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _prefix_key(self, path):
        self._walk(path, "cache_key_nodes")
        return tuple(path)

    def _record_size(self, frames):
        self._cached_frames += frames
        self.meter.stats["peak_cached_frames"] = max(
            self.meter.stats["peak_cached_frames"], self._cached_frames)

    def _save_prefix(self, summary):
        if not self.prefix_cache:
            return
        key = self._prefix_key(summary.path)
        self.meter.tick("cache_insertions")
        self._walk({"state": summary.state, "depth": len(summary.path),
                    "unknown": summary.unknown, "contract_known": summary.contract_known},
                   "cache_payload_nodes")
        for frame in summary.frontier:
            self.meter.tick("cache_payload_nodes")  # frame/history references
            self._walk(frame.bindings, "cache_payload_nodes")
        # All construction charges must succeed before publication. Prefixes
        # are inserted only when every frame's complete expansion is available.
        self._prefixes[key] = summary
        self.meter.stats["prefix_cache_entries"] += 1
        self._record_size(len(summary.frontier))

    def _start(self, path):
        for length in (range(len(path), -1, -1) if self.prefix_cache else ()):
            key = self._prefix_key(path[:length])
            self.meter.tick("cache_lookups")
            summary = self._prefixes.get(key)
            if summary is not None:
                self.meter.stats["prefix_cache_hits"] += 1
                self.meter.tick("cache_status_checks")  # includes empty hits
                for frame in summary.frontier:
                    self.meter.tick("cached_prefix_frames")
                    self._walk(frame.bindings, "cache_payload_nodes")
                return summary
        initial = self.profile["model"]["initial"]
        frame = self._walk(self.profile["initial_bindings"], "cache_payload_nodes", copy=True)
        unknown = self.safe[initial] is None
        summary = _PrefixSummary((), initial, (_Frame(frame, None),), unknown, not unknown)
        self._save_prefix(summary)
        return summary

    def _history(self, previous, step):
        self.meter.tick("history_nodes")
        return _History(previous, step)

    def _witness(self, history):
        self.meter.tick("witness_nodes")  # output list, including the empty one
        steps = []
        while history is not None:
            self.meter.tick("witness_nodes")
            steps.append(self._walk(history.step, "witness_nodes", copy=True))
            history = history.previous
        for _ in steps:
            self.meter.tick("witness_nodes")
        steps.reverse()
        return steps

    def _expand(self, edge_id, frame, *, early_goal):
        """Return (complete summary, None), or (None, one final-goal step).

        Early success and exceptions leave a miss unpublished. A previous
        complete cache entry can safely supply a first existential witness.
        """
        key, cached = None, None
        if self.relation_cache:
            self.meter.tick("cache_key_nodes")  # edge ID in the relation key
            key = (edge_id, self._frame_key(frame))
            self.meter.tick("cache_lookups")
            cached = self._relations.get(key)
        if cached is not None:
            self.meter.stats["relation_cache_hits"] += 1
            self.meter.tick("cache_status_checks")  # uncertainty and empty hits
            for step in cached.steps:
                self.meter.tick("cached_relation_outcomes")
                self._walk(step, "cache_payload_nodes")
                if early_goal:
                    return None, step
            return cached, None

        relation = self.profile["relations"][edge_id]
        retained, unknown = {}, False
        for args in core._arguments(relation, frame):
            self.meter.tick("relation_checks")
            request = core._expr(relation["emit"], args, frame, None, self.meter)
            values = [core._guard(guard, args, frame, request, self.meter)
                      for guard in relation["guards"]]
            if False in values:
                continue
            if None in values or core._contains_unknown(request):
                unknown = True
                continue
            updates = {name: core._expr(expression, args, frame, request, self.meter)
                       for name, expression in relation["updates"].items()}
            if any(not core._scalar(value) for value in updates.values()):
                unknown = True
                continue
            changed = dict(frame, **updates)
            step = self._walk({"edge": edge_id, "args": args, "request": request,
                               "bindings_before": frame, "bindings_after": changed},
                              "cache_payload_nodes", copy=True)
            if early_goal:
                return None, step
            after_key = self._frame_key(changed)
            self.meter.tick("cache_lookups")  # complete-frame deduplication
            retained.setdefault(after_key, step)

        summary = _RelationSummary(tuple(retained.values()), unknown)
        if self.relation_cache:
            self.meter.tick("cache_insertions")
            self.meter.tick("cache_payload_nodes")  # complete-domain/status record
            for _ in summary.steps:
                self.meter.tick("cache_payload_nodes")  # retained local-step reference
            self._relations[key] = summary
            self.meter.stats["relation_cache_entries"] += 1
            self._record_size(len(summary.steps))
        return summary, None

    def lift(self, path):
        summary = self._start(path)
        if not summary.frontier:
            return ("unknown", None) if summary.unknown else ("refuted", summary.path)
        for index in range(len(summary.path), len(path)):
            edge_id = path[index]
            edge = self.edges[edge_id]
            early_goal = (index == len(path) - 1 and summary.contract_known
                          and self.safe[edge["target"]] is True
                          and self.goal[edge["target"]] is True)
            following, unknown = {}, summary.unknown
            for frame in summary.frontier:
                expanded, witness = self._expand(edge_id, frame.bindings, early_goal=early_goal)
                if witness is not None:
                    return "supported", self._witness(self._history(frame.history, witness))
                unknown |= expanded.unknown
                for step in expanded.steps:
                    bindings = step["bindings_after"]
                    key = self._frame_key(bindings)
                    self.meter.tick("cache_lookups")
                    if key not in following:
                        following[key] = _Frame(bindings, self._history(frame.history, step))
            state = edge["target"]
            uncertain_state = self.safe[state] is None
            summary = _PrefixSummary(path[:index + 1], state, tuple(following.values()),
                                     unknown or uncertain_state,
                                     summary.contract_known and not uncertain_state)
            self._save_prefix(summary)
            self.meter.stats["peak_frames"] = max(self.meter.stats["peak_frames"], len(summary.frontier))
            if not summary.frontier:
                return ("unknown", None) if summary.unknown else ("refuted", summary.path)
        if summary.frontier and summary.contract_known and self.goal[summary.state] is True:
            return "supported", self._witness(summary.frontier[0].history)
        return "unknown", None


def evaluate(profile, now, budget=None, *, cache_policy="both"):
    if cache_policy not in POLICIES:
        raise ValueError("Unknown cache policy")
    prefix_cache, relation_cache = POLICIES[cache_policy]
    """Preserve v1's abstract enumeration/refinement with a call-local lifter."""
    started = time.perf_counter_ns()
    core.validate(profile)
    if type(now) is not int:
        raise ValueError("now must be integer epoch seconds")
    meter = _Meter(budget)
    model, evidence = profile["model"], profile["model"]["evidence"]

    def result(decision, reason, certificate=None):
        return {"decision": decision, "reason": reason, "certificate": certificate,
                "method": METHOD, "novelty_established": False,
                "stats": dict(meter.stats, elapsed_ns=time.perf_counter_ns() - started)}

    if not evidence["observed_at"] <= now <= evidence["valid_until"]:
        return result("unknown", "evidence_not_fresh")
    header = {"profile_sha256": core.digest(profile), "checked_at": now,
              "horizon": model["horizon"], "valid_until": evidence["valid_until"]}
    contract = model["runtime_contract"]
    safe = {name: core.conjunction(value, contract["invariants"])
            for name, value in model["states"].items()}
    goal = {name: core.conjunction(value, contract["goal"])
            for name, value in model["states"].items()}
    edges = {edge["id"]: edge for edge in model["transitions"]}
    outgoing = {name: [] for name in model["states"]}
    for edge in model["transitions"]:
        outgoing[edge["source"]].append(edge)
    initial = model["initial"]
    refinements, trie = [], {}
    unresolved = contract_uncertain = False
    memo = _SharedLift(profile, edges, safe, goal, meter,
                       prefix_cache=prefix_cache, relation_cache=relation_cache)
    try:
        # Keep the exact v1 conservative contracted-observable traversal.
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
            if core._blocked(path, trie, meter):
                continue
            if goal[state] is not False:
                meter.tick("abstract_paths")
                disposition, detail = memo.lift(path)
                if disposition == "supported":
                    meter.tick("witness_nodes")
                    for _ in path:
                        meter.tick("witness_nodes")
                    return result("supported", "public_recipe_witness", {
                        **header, "kind": "recipe-path", "transition_ids": list(path), "steps": detail})
                if disposition == "refuted":
                    refinements.append(list(detail))
                    meter.stats["refinements"] += 1
                    node = trie
                    for edge in detail:
                        meter.tick("refinement_edges")
                        node = node.setdefault(edge, {})
                    node[core._STOP] = True
                    continue
                unresolved = True
            if len(path) < model["horizon"]:
                for edge in outgoing[state]:
                    meter.tick("abstract_edge_checks")
                    if safe[edge["target"]] is not False:
                        queue.append((edge["target"], path + (edge["id"],)))
    except core._Limit:
        return result("unknown", "work_budget_exhausted")
    if contract_uncertain:
        return result("unknown", "indeterminate_observables")
    if unresolved:
        return result("unknown", "unresolved_relation_or_recipe")
    if not evidence["complete"] or not profile["coverage"]["complete"]:
        return result("unknown", "incomplete_model_or_relation_coverage")
    return result("unsupported", "certified_refinement_exhaustion", {
        **header, "kind": "refinement-exhaustion", "refuted_prefixes": refinements})


def evaluate_neither(profile, now, budget=None):
    return evaluate(profile, now, budget, cache_policy="neither")


def evaluate_prefix(profile, now, budget=None):
    return evaluate(profile, now, budget, cache_policy="prefix")


def evaluate_relation(profile, now, budget=None):
    return evaluate(profile, now, budget, cache_policy="relation")


def evaluate_both(profile, now, budget=None):
    return evaluate(profile, now, budget, cache_policy="both")
