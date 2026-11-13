"""Adverse codec and unchanged-checker controls; no admission solver runs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from interoperability import refutation_prefix_dag_v1 as codec
from interoperability import refinement_oracle as checker
from test_refinement import NOW, const, correlated_profile, eq, profile


def negative(p, prefixes):
    return {"decision": "unsupported", "reason": "authored codec control",
            "certificate": dict(checker._header(p, NOW), kind="refinement-exhaustion",
                                refuted_prefixes=deepcopy(prefixes))}


def packaged(p, prefixes):
    result = negative(p, prefixes)
    result["certificate"] = codec.encode_certificate(result["certificate"])
    return result


class PrefixDagStructure(unittest.TestCase):
    def test_suffix_sharing_preserves_exact_input_order(self):
        prefixes = [["b", "c", "x"], ["a", "c", "x"]]
        before = deepcopy(prefixes)
        encoded = codec.encode_prefixes(prefixes)
        self.assertEqual(len(encoded["nodes"]), 4)
        self.assertEqual(encoded["nodes"][0]["arcs"][0]["next"],
                         encoded["nodes"][0]["arcs"][1]["next"])
        self.assertEqual(encoded["word_order"], [1, 0])
        self.assertEqual(codec.decode_prefixes(encoded), prefixes)
        with patch.object(codec, "encode_prefixes", side_effect=AssertionError("Encoder must not verify itself")):
            self.assertTrue(codec.check_encoding(prefixes, encoded))
        self.assertEqual(prefixes, before)

    def test_redundant_longer_prefixes_remain_lossless(self):
        prefixes = [["a", "b"], ["a"]]
        encoded = codec.encode_prefixes(prefixes)
        self.assertTrue(any(node["terminal"] and node["arcs"] for node in encoded["nodes"]))
        self.assertEqual(codec.decode_prefixes(encoded), prefixes)

    def test_minimality_matches_independent_finite_right_languages(self):
        universe = [word for length in range(1, 4) for word in itertools.product("abc", repeat=length)]
        for words in (universe, universe[::3], list(reversed(universe[::2]))):
            prefixes = {word[:length] for word in words for length in range(len(word) + 1)}
            right_languages = {frozenset(word[len(prefix):] for word in words
                                          if word[:len(prefix)] == prefix) for prefix in prefixes}
            encoded = codec.encode_prefixes([list(word) for word in words])
            self.assertEqual(len(encoded["nodes"]), len(right_languages))
            self.assertEqual(codec.decode_prefixes(encoded), [list(word) for word in words])

    def test_empty_cover_and_zero_horizon(self):
        limits = replace(codec.DEFAULT_LIMITS, max_horizon=0)
        encoded = codec.encode_prefixes([], limits=limits)
        self.assertEqual(encoded["nodes"], [{"terminal": False, "arcs": []}])
        self.assertEqual(codec.decode_prefixes(encoded, limits=limits), [])

    def test_duplicate_or_malformed_words_are_rejected(self):
        for bad in ([["a"], ["a"]], [[]], ["a"], [("a",)], [[1]], [[""]], [["\ud800"]]):
            with self.subTest(value=repr(bad)), self.assertRaises(codec.DagError):
                codec.encode_prefixes(bad)

    def test_cycle_backward_and_dangling_references_are_rejected(self):
        for target in (0, -1, 2, True):
            bad = codec.encode_prefixes([["a"]])
            bad["nodes"][0]["arcs"][0]["next"] = target
            with self.subTest(target=target), self.assertRaises(codec.DagError):
                codec.decode_prefixes(bad)

    def test_unreachable_nonduplicate_node_is_rejected(self):
        bad = {"schema_version": codec.SCHEMA, "root": 0, "word_order": [0], "nodes": [
            {"terminal": False, "arcs": [{"edge": "a", "next": 2}]},
            {"terminal": True, "arcs": [{"edge": "z", "next": 2}]},
            {"terminal": True, "arcs": []}]}
        with self.assertRaisesRegex(codec.DagError, "unreachable"):
            codec.decode_prefixes(bad)

    def test_duplicate_suffix_nodes_and_duplicate_arcs_are_rejected(self):
        duplicate = {"schema_version": codec.SCHEMA, "root": 0, "word_order": [0, 1], "nodes": [
            {"terminal": False, "arcs": [{"edge": "a", "next": 1}, {"edge": "b", "next": 2}]},
            {"terminal": True, "arcs": []}, {"terminal": True, "arcs": []}]}
        with self.assertRaisesRegex(codec.DagError, "duplicate_suffix"):
            codec.decode_prefixes(duplicate)
        bad = codec.encode_prefixes([["a"]])
        bad["nodes"][0]["arcs"].append(deepcopy(bad["nodes"][0]["arcs"][0]))
        with self.assertRaisesRegex(codec.DagError, "duplicate_or_unsorted"):
            codec.decode_prefixes(bad)

    def test_unsorted_arcs_and_extra_fields_are_rejected(self):
        bad = codec.encode_prefixes([["a"], ["b"]])
        bad["nodes"][0]["arcs"].reverse()
        with self.assertRaises(codec.DagError):
            codec.decode_prefixes(bad)
        for location in ("dag", "node", "arc"):
            bad = codec.encode_prefixes([["a"]])
            target = bad if location == "dag" else bad["nodes"][0] if location == "node" else bad["nodes"][0]["arcs"][0]
            target["unchecked_claim"] = True
            with self.subTest(location=location), self.assertRaises(codec.DagError):
                codec.decode_prefixes(bad)

    def test_terminal_root_and_dead_language_leaf_are_rejected(self):
        for root in (True, False):
            bad = codec.encode_prefixes([["a"]])
            if root:
                bad["nodes"][0]["terminal"] = True
            else:
                bad["nodes"][1]["terminal"] = False
            with self.subTest(root=root), self.assertRaises(codec.DagError):
                codec.decode_prefixes(bad)

    def test_word_order_is_an_exact_integer_permutation(self):
        for bad_order in ([0, 0], [0], [0, 2], [False, 1], [0, [1]]):
            bad = codec.encode_prefixes([["a"], ["b"]])
            bad["word_order"] = bad_order
            with self.subTest(order=bad_order), self.assertRaises(codec.DagError):
                codec.decode_prefixes(bad)

    def test_language_changes_fail_independent_round_trip_check(self):
        original = [["a", "finish"], ["b", "finish"]]
        changed = codec.encode_prefixes([["a", "finish"]])
        self.assertFalse(codec.check_encoding(original, changed))
        self.assertFalse(codec.check_encoding([["b", "finish"], ["a", "finish"]],
                                              codec.encode_prefixes(original)))

    def test_decoded_objects_do_not_alias_encoded_or_input_objects(self):
        original = [["a", "finish"]]
        encoded = codec.encode_prefixes(original)
        decoded = codec.decode_prefixes(encoded)
        decoded[0][0] = "changed"
        self.assertTrue(codec.check_encoding(original, encoded))


class PrefixDagBounds(unittest.TestCase):
    def test_certificate_envelopes_share_the_inner_codec_work_budget(self):
        p = profile()
        certificate = negative(p, [["finish"]])["certificate"]
        wrapped = codec.encode_certificate(certificate)
        controls = ((codec.encode_prefixes, certificate["refuted_prefixes"], codec.encode_certificate, certificate),
                    (codec.decode_prefixes, wrapped["dag"], codec.decode_certificate, wrapped))
        for inner, payload, envelope, full in controls:
            for allowance in range(1, 400):
                limits = replace(codec.DEFAULT_LIMITS, max_work_units=allowance)
                try:
                    inner(payload, limits=limits)
                except codec.DagError:
                    continue
                with self.assertRaisesRegex(codec.DagError, "work_budget"):
                    envelope(full, limits=limits)
                break
            else:
                self.fail("Constructed inner codec did not fit the bounded search")

    def test_encode_count_edge_node_arc_byte_and_work_bounds(self):
        controls = [({"max_prefixes": 1}, [["a"], ["b"]]),
                    ({"max_total_edges": 1}, [["a", "b"]]),
                    ({"max_nodes": 2}, [["a", "b"]]),
                    ({"max_arcs": 1}, [["a"], ["b"]]),
                    ({"max_horizon": 1}, [["a", "b"]]),
                    ({"max_label_bytes": 3}, [["éé"]]),
                    ({"max_serialized_bytes": 40}, [["a"]]),
                    ({"max_work_units": 1}, [["a"]])]
        for changed, prefixes in controls:
            with self.subTest(limit=changed), self.assertRaises(codec.DagError):
                codec.encode_prefixes(prefixes, limits=replace(codec.DEFAULT_LIMITS, **changed))

    def test_invalid_limit_types_are_rejected(self):
        for changed in ({"max_nodes": True}, {"max_prefixes": 0}, {"max_horizon": 65}):
            with self.subTest(limit=changed), self.assertRaises(codec.DagError):
                codec.encode_prefixes([], limits=replace(codec.DEFAULT_LIMITS, **changed))

    def test_small_shared_dag_cannot_exceed_expansion_bounds(self):
        depth = 12
        small = {"schema_version": codec.SCHEMA, "root": 0, "word_order": [], "nodes": [
            {"terminal": False, "arcs": [{"edge": "a", "next": i + 1}, {"edge": "b", "next": i + 1}]}
            for i in range(depth)] + [{"terminal": True, "arcs": []}]}
        for changed, reason in (({"max_prefixes": 16}, "expanded_prefix_count"),
                                ({"max_horizon": 6}, "expanded_horizon"),
                                ({"max_total_edges": 16}, "expanded_total_edge"),
                                ({"max_work_units": 1}, "work_budget")):
            with self.subTest(limit=changed), self.assertRaisesRegex(codec.DagError, reason):
                codec.decode_prefixes(small, limits=replace(codec.DEFAULT_LIMITS, **changed))

    def test_expanded_serialized_bytes_are_bounded(self):
        prefixes = [list(word) for word in itertools.product("ab", repeat=8)]
        encoded = codec.encode_prefixes(prefixes)
        serialized = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        self.assertLess(len(serialized(encoded)), 4000)
        self.assertGreater(len(serialized(prefixes)), 4000)
        with self.assertRaisesRegex(codec.DagError, "serialized_byte_bound"):
            codec.decode_prefixes(encoded, limits=replace(codec.DEFAULT_LIMITS, max_serialized_bytes=4000))


class PrefixDagUnchangedChecker(unittest.TestCase):
    def test_zero_horizon_empty_refutation_cover_keeps_original_semantics(self):
        p = profile()
        p["model"]["horizon"] = 0
        self.assertTrue(codec.check_certificate(p, packaged(p, []), NOW))

    def test_exact_certificate_round_trip_and_unchanged_checker_delegation(self):
        p = profile()
        p["relations"]["finish"]["guards"] = [eq(const(1), const(2))]
        original = negative(p, [["finish"]])
        compressed = codec.encode_certificate(original["certificate"])
        self.assertEqual(codec.decode_certificate(compressed), original["certificate"])
        self.assertFalse(checker.check_certificate(p, dict(original, certificate=compressed), NOW))
        with patch.object(checker, "evaluate", side_effect=AssertionError("No solver execution")):
            self.assertTrue(codec.check_certificate(p, dict(original, certificate=compressed), NOW))

    def test_bad_binding_refutation_cannot_erase_good_binding_witness(self):
        p = correlated_profile()
        for prefixes in ([["finish"]], [["a_bad_binding", "finish"]],
                         [["a_bad_binding", "finish"], ["b_good_binding", "finish"]]):
            with self.subTest(prefixes=prefixes), patch.object(checker, "evaluate", side_effect=AssertionError("No solver execution")):
                self.assertFalse(codec.check_certificate(p, packaged(p, prefixes), NOW))

    def test_shared_suffix_still_replays_each_correlated_incoming_frame(self):
        p = correlated_profile()
        p["relations"]["b_good_binding"]["updates"]["target"] = const("A")
        prefixes = [["a_bad_binding", "finish"], ["b_good_binding", "finish"]]
        result = packaged(p, prefixes)
        self.assertEqual(len(result["certificate"]["dag"]["nodes"]), 3)
        self.assertTrue(codec.check_certificate(p, result, NOW))
        p["relations"]["b_good_binding"]["updates"]["target"] = const("B")
        refreshed = packaged(p, prefixes)
        self.assertFalse(codec.check_certificate(p, refreshed, NOW))

    def test_sticky_unknown_and_incomplete_coverage_never_become_refutations(self):
        p = correlated_profile()
        p["model"]["transitions"] = [p["model"]["transitions"][0], p["model"]["transitions"][2]]
        p["relations"] = {name: p["relations"][name] for name in ("a_bad_binding", "finish")}
        p["relations"]["a_bad_binding"]["emit"] = {"unknown": "unmodeled request"}
        p["relations"]["finish"]["guards"] = [eq(const(1), const(2))]
        self.assertFalse(codec.check_certificate(p, packaged(p, [["a_bad_binding", "finish"]]), NOW))
        p = profile()
        p["relations"]["finish"]["guards"] = [eq(const(1), const(2))]
        p["coverage"]["complete"] = False
        self.assertFalse(codec.check_certificate(p, packaged(p, [["finish"]]), NOW))

    def test_changed_profile_clock_horizon_and_malformed_header_are_rejected(self):
        p = profile()
        p["relations"]["finish"]["guards"] = [eq(const(1), const(2))]
        result = packaged(p, [["finish"]])
        changed = deepcopy(p)
        changed["id"] = "changed-profile"
        self.assertFalse(codec.check_certificate(changed, result, NOW))
        self.assertFalse(codec.check_certificate(p, result, p["model"]["evidence"]["valid_until"] + 1))
        for key, value in (("horizon", 0), ("checked_at", True), ("profile_sha256", "not-a-digest")):
            bad = deepcopy(result)
            bad["certificate"][key] = value
            with self.subTest(header=key):
                self.assertFalse(codec.check_certificate(p, bad, NOW))

    def test_adapter_refuses_other_decisions_and_codec_exhaustion(self):
        p = profile()
        p["relations"]["finish"]["guards"] = [eq(const(1), const(2))]
        result = packaged(p, [["finish"]])
        for decision in ("supported", "unknown"):
            self.assertFalse(codec.check_certificate(p, dict(result, decision=decision), NOW))
        self.assertFalse(codec.check_certificate(p, result, NOW,
                                                limits=replace(codec.DEFAULT_LIMITS, max_work_units=1)))


if __name__ == "__main__":
    unittest.main()
