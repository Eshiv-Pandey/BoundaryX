"""Adversarial finite constraint-pruning checks, without application calls."""
from copy import deepcopy
import itertools
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from interoperability import direct_guard_pruned_v3 as guarded
from interoperability import direct_goal_pruned_v2 as exact
from test_direct_goal_pruned_v2 import profile, relation


def one_step(*, arguments=None, emit=None, guards=None, updates=None):
    return profile([("finish", "start", "goal")], horizon=1, relations={"finish":
        relation(arguments=arguments, emit=emit, guards=guards, updates=updates)})


class GuardPrunedTests(unittest.TestCase):
    def checked(self, value, expected=None, budget=100000):
        before = deepcopy(value)
        observed = guarded.evaluate(value, 100, budget)
        if expected is not None:
            self.assertEqual(observed["decision"], expected, observed)
        if observed["decision"] != "unknown":
            self.assertTrue(exact.check_certificate(value, observed, 100), observed)
        else:
            self.assertIsNone(observed["certificate"])
        self.assertEqual(value, before)
        return observed

    def test_constant_false_prunes_full_product_despite_unknown_request(self):
        args = {f"a{i}": [{"literal": v} for v in range(8)] for i in range(4)}
        value = one_step(arguments=args, emit={"unknown": "opaque"}, guards=[
            {"op": "eq", "left": {"const": 0}, "right": {"const": 1}}])
        result = self.checked(value, "unsupported", budget=256)
        self.assertEqual(result["stats"]["argument_assignments"], 0)
        self.assertEqual(exact.evaluate(value, 100, 256)["decision"], "unknown")

    def test_late_witness_is_found_without_discarding_permitted_values(self):
        value = one_step(arguments={"a": [{"literal": v} for v in range(16)],
                                    "b": [{"literal": v} for v in range(16)]}, guards=[
            {"op": "eq", "left": {"arg": "a"}, "right": {"const": 15}},
            {"op": "eq", "left": {"arg": "b"}, "right": {"const": 15}}])
        result = self.checked(value, "supported", budget=256)
        self.assertEqual(result["certificate"]["steps"][0]["args"], {"a": 15, "b": 15})
        self.assertEqual(result["stats"]["argument_assignments"], 1)

    def test_emit_path_waits_for_all_request_arguments(self):
        value = one_step(arguments={"a": [{"literal": 1}], "b": [{"literal": 2}]},
            emit={"object": {"x": {"arg": "a"}, "y": {"arg": "b"}}}, guards=[
            {"op": "eq", "left": {"emit_path": ["y"]}, "right": {"const": 2}}])
        self.checked(value, "supported")

    def test_unknown_guard_never_prunes_a_possible_tuple(self):
        value = one_step(arguments={"a": [{"literal": 1}, {"literal": 2}]}, guards=[
            {"op": "eq", "left": {"arg": "a"}, "right": {"binding": "missing"}}])
        result = self.checked(value, "unknown")
        self.assertEqual(result["stats"]["argument_assignments"], 2)

    def test_type_sensitive_boolean_integer_and_null_domains(self):
        for wanted in (True, 1, None):
            value = one_step(arguments={"a": [{"literal": x} for x in (True, 1, None)]}, guards=[
                {"op": "eq", "left": {"arg": "a"}, "right": {"const": wanted}}])
            result = self.checked(value, "supported")
            self.assertIs(type(result["certificate"]["steps"][0]["args"]["a"]), type(wanted))

    def test_present_and_absent_request_path_semantics(self):
        for name, expected in (("exists", "supported"), ("missing", "unsupported")):
            value = one_step(emit={"object": {"exists": {"const": None}}}, guards=[
                {"op": "present", "left": {"emit_path": [name]}}])
            self.checked(value, expected)

    def test_updates_are_atomic_in_old_correlated_frame(self):
        value = profile([("a", "start", "ready"), ("b", "ready", "goal")], horizon=2,
            relations={"a": relation(updates={"x": {"binding": "y"}, "y": {"binding": "x"}}),
                       "b": relation(guards=[{"op": "eq", "left": {"binding": "x"}, "right": {"const": 2}},
                                             {"op": "eq", "left": {"binding": "y"}, "right": {"const": 1}}])})
        value["initial_bindings"] = {"x": 1, "y": 2}
        self.checked(value, "supported")

    def test_frames_are_not_pooled_across_reconvergent_paths(self):
        value = profile([("a", "start", "ready"), ("b", "start", "ready"), ("c", "ready", "goal")],
            relations={"a": relation(updates={"x": {"const": 1}, "y": {"const": 2}}),
                       "b": relation(updates={"x": {"const": 2}, "y": {"const": 1}}),
                       "c": relation(guards=[{"op": "eq", "left": {"binding": "x"}, "right": {"const": 1}},
                                             {"op": "eq", "left": {"binding": "y"}, "right": {"const": 1}}])})
        self.checked(value, "unsupported")

    def test_empty_domain_is_exhausted_but_missing_emit_binding_is_unknown(self):
        self.checked(one_step(arguments={"a": []}), "unsupported")
        self.checked(one_step(emit={"binding": "missing"}), "unknown")

    def test_staleness_partial_coverage_and_budget_keep_unknown(self):
        value = one_step(guards=[{"op": "eq", "left": {"const": 0}, "right": {"const": 1}}])
        value["coverage"]["complete"] = False
        self.checked(value, "unknown")
        value["coverage"]["complete"] = True
        self.checked(value, "unknown", budget=1)
        value["model"]["evidence"]["valid_until"] = 99
        self.checked(value, "unknown")

    def test_initial_goal_and_horizon_are_preserved(self):
        value = one_step()
        value["model"]["horizon"] = 0
        self.checked(value, "unsupported")
        value["model"]["states"]["start"]["done"] = True
        result = self.checked(value, "supported")
        self.assertEqual(result["certificate"]["steps"], [])

    def test_checker_is_unchanged_and_does_not_call_solver(self):
        value = one_step(guards=[{"op": "eq", "left": {"const": 0}, "right": {"const": 1}}])
        result = self.checked(value, "unsupported")
        with patch.object(guarded, "evaluate", side_effect=AssertionError("solver invoked")):
            self.assertTrue(guarded.check_certificate(value, result, 100))
        result["certificate"]["product_layers"][0] = []
        self.assertFalse(guarded.check_certificate(value, result, 100))

    def test_seeded_differential_guards_with_unknown_and_nested_requests(self):
        randomizer = random.Random(20261110)
        for _ in range(120):
            choices = [None, False, 0, 1, "x"]
            arguments = {name: [{"literal": randomizer.choice(choices)} for _ in range(3)]
                         for name in ("a", "b")}
            expressions = [{"arg": "a"}, {"arg": "b"}, {"const": randomizer.choice(choices)},
                           {"binding": "missing"}, {"emit_path": ["v", 1]}]
            guards = [{"op": randomizer.choice(("eq", "ne")), "left": randomizer.choice(expressions),
                       "right": randomizer.choice(expressions)} for _ in range(3)]
            value = one_step(arguments=arguments, emit={"object": {"v": {"array": [{"arg": "a"}, {"arg": "b"}]}}}, guards=guards)
            observed = self.checked(value)
            self.assertEqual(observed["decision"], exact.evaluate(value, 100, 100000)["decision"])


if __name__ == "__main__":
    unittest.main()
