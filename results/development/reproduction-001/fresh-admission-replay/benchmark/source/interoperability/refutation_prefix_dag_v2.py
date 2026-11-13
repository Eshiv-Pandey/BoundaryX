"""Bounded, lossless packaging of existing exact-prefix refutation proofs.

This module changes representation only. The adapter expands the original
ordered prefix list and delegates semantic validity to the unchanged checker.
Suffix sharing is finite-language compression, not a new admission theorem or
an established improvement in end-to-end checking cost.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import json
import re
from typing import Any


SCHEMA = "refutation-prefix-language-dag/2"
CERTIFICATE_KIND = "refinement-prefix-dag/2"
OLD_KIND = "refinement-exhaustion"
HEADER = {"kind", "profile_sha256", "checked_at", "horizon", "valid_until"}


class DagError(ValueError):
    """Malformed representation or exceeded explicit codec bound."""


@dataclass(frozen=True, slots=True)
class Limits:
    max_horizon: int = 64
    max_prefixes: int = 4096
    max_total_edges: int = 65536
    max_nodes: int = 65536
    max_arcs: int = 65536
    max_serialized_bytes: int = 4 * 1024 * 1024
    max_label_bytes: int = 16384
    max_header_integer_bits: int = 4096
    max_work_units: int = 2_000_000


DEFAULT_LIMITS = Limits()


def _need(value: bool, reason: str) -> None:
    if not value:
        raise DagError(reason)


class _Budget:
    def __init__(self, limits: Limits):
        _need(type(limits) is Limits, "exact_limits_required")
        for field in fields(limits):
            value = getattr(limits, field.name)
            minimum = 0 if field.name == "max_horizon" else 1
            _need(type(value) is int and value >= minimum, "invalid_codec_limit")
        _need(limits.max_horizon <= 64, "profile_horizon_limit_exceeded")
        self.limits, self.work, self.label_bytes = limits, 0, 0

    def tick(self, count: int = 1) -> None:
        self.work += count
        _need(self.work <= self.limits.max_work_units, "codec_work_budget_exhausted")

    def label(self, value: Any) -> None:
        self.tick()
        _need(type(value) is str and 0 < len(value) <= self.limits.max_label_bytes,
              "bounded_nonempty_edge_label_required")
        try:
            raw = value.encode("utf-8")
        except UnicodeError as error:
            raise DagError("invalid_utf8_edge_label") from error
        _need(len(raw) <= self.limits.max_label_bytes, "edge_label_byte_bound_exceeded")
        self.label_bytes += len(raw)
        _need(self.label_bytes <= self.limits.max_serialized_bytes,
              "cumulative_label_byte_bound_exceeded")


def _serialized_size(value: Any, budget: _Budget) -> int:
    # Stream the size check instead of allocating an unbounded JSON byte string.
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    size = 0
    try:
        for chunk in encoder.iterencode(value):
            budget.tick()
            size += len(chunk.encode("utf-8"))
            _need(size <= budget.limits.max_serialized_bytes,
                  "serialized_byte_bound_exceeded")
    except DagError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise DagError("invalid_bounded_json") from error
    return size


def _prefix_words(prefixes: Any, budget: _Budget) -> list[tuple[str, ...]]:
    _need(type(prefixes) is list and len(prefixes) <= budget.limits.max_prefixes,
          "prefix_count_bound_or_type")
    words, seen, edge_count = [], set(), 0
    for prefix in prefixes:
        budget.tick()
        _need(type(prefix) is list and 0 < len(prefix) <= budget.limits.max_horizon,
              "prefix_length_bound_or_type")
        edge_count += len(prefix)
        _need(edge_count <= budget.limits.max_total_edges, "total_prefix_edge_bound_exceeded")
        for label in prefix:
            budget.label(label)
        word = tuple(prefix)
        _need(word not in seen, "duplicate_refuted_prefix")
        seen.add(word)
        words.append(word)
    _serialized_size(prefixes, budget)
    return words


def _encode_words(words: list[tuple[str, ...]], budget: _Budget) -> dict[str, Any]:
    limits = budget.limits
    trie = [{"terminal": False, "children": {}}]
    arc_count = 0
    for word in words:
        position = 0
        for label in word:
            budget.tick()
            children = trie[position]["children"]
            if label not in children:
                _need(len(trie) < limits.max_nodes, "trie_node_bound_exceeded")
                arc_count += 1
                _need(arc_count <= limits.max_arcs, "trie_arc_bound_exceeded")
                children[label] = len(trie)
                trie.append({"terminal": False, "children": {}})
            position = children[label]
        trie[position]["terminal"] = True

    interned, signatures, mapping = [], {}, {}
    for position in range(len(trie) - 1, -1, -1):
        budget.tick()
        node = trie[position]
        arcs = tuple((label, mapping[child]) for label, child in sorted(node["children"].items()))
        budget.tick(len(arcs))
        signature = (node["terminal"], arcs)
        if signature not in signatures:
            signatures[signature] = len(interned)
            interned.append(signature)
        mapping[position] = signatures[signature]
    # Every child was interned first. Reverse IDs so all references point ahead.
    last = len(interned) - 1
    _need(mapping[0] == last, "unexpected_root_language_alias")
    nodes = []
    for terminal, arcs in reversed(interned):
        budget.tick(1 + len(arcs))
        nodes.append({"terminal": terminal,
                      "arcs": [{"edge": label, "next": last - child} for label, child in arcs]})
    ranks = {word: rank for rank, word in enumerate(sorted(words))}
    encoded = {"schema_version": SCHEMA, "root": 0, "nodes": nodes,
               "word_order": [ranks[word] for word in words]}
    _serialized_size(encoded, budget)
    return encoded


def encode_prefixes(prefixes: Any, *, limits: Limits = DEFAULT_LIMITS) -> dict[str, Any]:
    """Encode an ordered list exactly; duplicate words are rejected.

    The language DAG is minimal under exact equal right-language sharing.
    ``word_order`` preserves the input order relative to lexicographic words.
    Terminal nodes may have arcs, preserving redundant longer refutations.
    """
    budget = _Budget(limits)
    return _encode_words(_prefix_words(prefixes, budget), budget)


def _dag_structure(encoded: Any, budget: _Budget) -> tuple[list[dict[str, Any]], list[int]]:
    # Length checks precede key materialization. Malformed nested objects must
    # be rejected before sort_keys can traverse them during envelope sizing.
    _need(type(encoded) is dict and len(encoded) == 4
          and set(encoded) == {"schema_version", "root", "nodes", "word_order"},
          "invalid_dag_fields")
    _need(type(encoded["schema_version"]) is str and encoded["schema_version"] == SCHEMA
          and type(encoded["root"]) is int
          and encoded["root"] == 0, "invalid_dag_schema_or_root")
    nodes, order = encoded["nodes"], encoded["word_order"]
    _need(type(nodes) is list and 0 < len(nodes) <= budget.limits.max_nodes,
          "dag_node_count_bound_or_type")
    _need(type(order) is list and len(order) <= budget.limits.max_prefixes,
          "dag_word_order_bound_or_type")
    ranks = set()
    for rank in order:
        budget.tick()
        _need(type(rank) is int and 0 <= rank < len(order) and rank not in ranks,
              "invalid_or_duplicate_word_order_rank")
        ranks.add(rank)
    arcs_total = 0
    for position, node in enumerate(nodes):
        budget.tick()
        _need(type(node) is dict and len(node) == 2 and set(node) == {"terminal", "arcs"}
              and type(node["terminal"]) is bool and type(node["arcs"]) is list,
              "invalid_dag_node_fields")
        previous = None
        arcs_total += len(node["arcs"])
        _need(arcs_total <= budget.limits.max_arcs, "dag_arc_bound_exceeded")
        for arc in node["arcs"]:
            budget.tick()
            _need(type(arc) is dict and len(arc) == 2 and set(arc) == {"edge", "next"},
                  "invalid_dag_arc_fields")
            budget.label(arc["edge"])
            _need(previous is None or previous < arc["edge"], "duplicate_or_unsorted_dag_arc")
            previous = arc["edge"]
            _need(type(arc["next"]) is int and position < arc["next"] < len(nodes),
                  "cyclic_backward_or_dangling_dag_reference")
        _need(node["terminal"] or node["arcs"] or (position == 0 and len(nodes) == 1),
              "dead_nonterminal_language_node")
    _need(nodes[0]["terminal"] is False, "empty_refutation_prefix_forbidden")
    return nodes, order


def _decode(encoded: Any, budget: _Budget, *, structure_checked: bool = False) -> list[list[str]]:
    if structure_checked:
        # Only the certificate adapter supplies this flag, immediately after
        # the bounded shape preflight and complete input-envelope size check.
        nodes, order = encoded["nodes"], encoded["word_order"]
    else:
        nodes, order = _dag_structure(encoded, budget)
        _serialized_size(encoded, budget)

    # This decoder does not call the encoder. Reject semantically duplicate
    # suffix nodes even if an attacker uses different child IDs for them.
    languages, classes = {}, {}
    for position in range(len(nodes) - 1, -1, -1):
        budget.tick()
        node = nodes[position]
        signature = (node["terminal"], tuple((arc["edge"], classes[arc["next"]])
                                              for arc in node["arcs"]))
        budget.tick(len(node["arcs"]))
        _need(signature not in languages, "duplicate_suffix_language_node")
        languages[signature] = len(languages)
        classes[position] = languages[signature]
    reached, pending = set(), [0]
    while pending:
        budget.tick()
        position = pending.pop()
        if position in reached:
            continue
        reached.add(position)
        for arc in nodes[position]["arcs"]:
            budget.tick()
            pending.append(arc["next"])
    _need(len(reached) == len(nodes), "unreachable_dag_node")

    words, pending, total_edges = [], [(0, ())], 0
    while pending:
        budget.tick()
        position, prefix = pending.pop()
        _need(len(prefix) <= budget.limits.max_horizon, "expanded_horizon_bound_exceeded")
        node = nodes[position]
        if node["terminal"]:
            _need(len(words) < budget.limits.max_prefixes, "expanded_prefix_count_bound_exceeded")
            total_edges += len(prefix)
            _need(total_edges <= budget.limits.max_total_edges, "expanded_total_edge_bound_exceeded")
            budget.tick(len(prefix))
            words.append(list(prefix))
        for arc in reversed(node["arcs"]):
            budget.tick(1 + len(prefix))
            pending.append((arc["next"], prefix + (arc["edge"],)))
    _need(len(order) == len(words), "word_order_does_not_match_language")
    decoded = [words[rank] for rank in order]
    # A tiny shared DAG can expand to large labels repeated in many words.
    # Bound the actual expanded serialized output before it leaves the codec.
    _serialized_size(decoded, budget)
    return decoded


def decode_prefixes(encoded: Any, *, limits: Limits = DEFAULT_LIMITS) -> list[list[str]]:
    """Independently validate structure/minimality and expand bounded exact words."""
    return _decode(encoded, _Budget(limits))


def check_encoding(prefixes: Any, encoded: Any, *, limits: Limits = DEFAULT_LIMITS) -> bool:
    """Check exact ordered round-trip language without invoking the encoder."""
    try:
        budget = _Budget(limits)
        words = _prefix_words(prefixes, budget)
        return _decode(encoded, budget) == [list(word) for word in words]
    except (DagError, TypeError, KeyError, UnicodeError, RecursionError):
        return False


def _certificate_header(certificate: Any, kind: str, payload: str, limits: Limits) -> Limits:
    _need(type(certificate) is dict and len(certificate) == len(HEADER) + 1
          and set(certificate) == HEADER | {payload}
          and type(certificate["kind"]) is str and certificate["kind"] == kind,
          "invalid_certificate_fields_or_kind")
    _need(type(certificate["profile_sha256"]) is str
          and len(certificate["profile_sha256"]) == 64
          and re.fullmatch("[0-9a-f]{64}", certificate["profile_sha256"]) is not None,
          "invalid_profile_digest")
    _need(all(type(certificate[name]) is int for name in ("checked_at", "horizon", "valid_until")),
          "integer_certificate_clock_and_horizon_required")
    _Budget(limits)
    integer_bound = min(limits.max_header_integer_bits, limits.max_serialized_bytes * 4)
    _need(all(certificate[name].bit_length() <= integer_bound
              for name in ("checked_at", "horizon", "valid_until")),
          "header_integer_bound_exceeded")
    _need(0 <= certificate["horizon"] <= limits.max_horizon, "certificate_horizon_bound_exceeded")
    return replace(limits, max_horizon=certificate["horizon"])


def encode_certificate(certificate: Any, *, limits: Limits = DEFAULT_LIMITS) -> dict[str, Any]:
    """Package an existing negative certificate; this does not validate it."""
    bounded = _certificate_header(certificate, OLD_KIND, "refuted_prefixes", limits)
    budget = _Budget(bounded)
    words = _prefix_words(certificate["refuted_prefixes"], budget)
    _serialized_size(certificate, budget)
    encoded = {name: certificate[name] for name in HEADER}
    encoded.update(kind=CERTIFICATE_KIND,
                   dag=_encode_words(words, budget))
    _serialized_size(encoded, budget)
    return encoded


def decode_certificate(certificate: Any, *, limits: Limits = DEFAULT_LIMITS) -> dict[str, Any]:
    """Restore the exact original certificate object and ordered prefix words."""
    bounded = _certificate_header(certificate, CERTIFICATE_KIND, "dag", limits)
    budget = _Budget(bounded)
    _dag_structure(certificate["dag"], budget)
    _serialized_size(certificate, budget)
    decoded = {name: certificate[name] for name in HEADER}
    decoded.update(kind=OLD_KIND,
                   refuted_prefixes=_decode(certificate["dag"], budget, structure_checked=True))
    _serialized_size(decoded, budget)
    return decoded


def check_certificate(profile: Any, result: Any, now: Any, *, limits: Limits = DEFAULT_LIMITS) -> bool:
    """Expand exact words and use the unchanged independent semantic checker.

    Codec refusal or checker refusal returns False. No stronger semantic claim
    or faster checker is supplied. Existing positive proof kinds are not handled
    by this representation adapter.
    """
    try:
        _need(type(result) is dict and result.get("decision") == "unsupported",
              "dag_adapter_requires_negative_result")
        certificate = decode_certificate(result.get("certificate"), limits=limits)
        restored = {"decision": "unsupported", "certificate": certificate}
        from . import refinement_oracle as unchanged_checker
        return unchanged_checker.check_certificate(profile, restored, now)
    except (DagError, TypeError, KeyError, UnicodeError, RecursionError):
        return False
