"""Differential, correlation and interruption controls for cache ablations."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from interoperability import refinement as core
from interoperability import refinement_oracle as checker
from interoperability import refinement_shared_lift_v2 as previous
from interoperability import shared_cache_ablation_v3 as ablation
from test_refinement import NOW, const, correlated_profile, development_profiles, eq, profile, relation
from test_refinement_shared_lift_v2 import reconvergent_profile, witness_result


def deterministic(value):
    return {key: ({k: v for k, v in item.items() if k != "elapsed_ns"}
                  if key == "stats" else item)
            for key, item in value.items() if key != "method"}


def lifter(p, policy):
    core.validate(p)
    model, contract = p["model"], p["model"]["runtime_contract"]
    safe = {s: core.conjunction(v, contract["invariants"]) for s, v in model["states"].items()}
    goal = {s: core.conjunction(v, contract["goal"]) for s, v in model["states"].items()}
    meter = ablation._Meter(100000)
    prefix, local = ablation.POLICIES[policy]
    return ablation._SharedLift(p, {e["id"]: e for e in model["transitions"]}, safe, goal,
                               meter, prefix_cache=prefix, relation_cache=local), meter


class CacheAblationTests(unittest.TestCase):
    def all_policies(self, p, expected):
        before = deepcopy(p)
        for policy in ablation.POLICIES:
            with self.subTest(policy=policy, profile=p["id"]):
                result = ablation.evaluate(p, NOW, 100000, cache_policy=policy)
                self.assertEqual(result["decision"], expected)
                self.assertEqual(checker.check_certificate(p, result, NOW), expected != "unknown")
                self.assertEqual(p, before)
                if expected == "unknown":
                    self.assertIsNone(result["certificate"])
                prefix, local = ablation.POLICIES[policy]
                if not prefix:
                    self.assertEqual(result["stats"]["prefix_cache_hits"], 0)
                    self.assertEqual(result["stats"]["prefix_cache_entries"], 0)
                if not local:
                    self.assertEqual(result["stats"]["relation_cache_hits"], 0)
                    self.assertEqual(result["stats"]["relation_cache_entries"], 0)

    def test_frozen_predecessor_and_all_enabled_deterministic_equivalence(self):
        self.assertEqual(hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest(),
                         "927538f7ddcb21120913c6c4257754b65a45703db384eec8cd6a28ba9e9b280b")
        for p, _ in development_profiles():
            for budget in (1, 32, 256, 4096, 100000):
                with self.subTest(profile=p["id"], budget=budget):
                    self.assertEqual(deterministic(previous.evaluate(p, NOW, budget)),
                                     deterministic(ablation.evaluate_both(p, NOW, budget)))

    def test_all_existing_development_profiles_keep_decisions_and_valid_certificates(self):
        for p, expected in development_profiles():
            self.all_policies(p, expected)

    def test_correlated_histories_cannot_pool_bindings(self):
        p = correlated_profile()
        self.all_policies(p, "supported")
        p["relations"]["a_bad_binding"]["updates"] = {"call": const("call-A"), "target": const("B")}
        p["relations"]["b_good_binding"]["updates"] = {"call": const("call-B"), "target": const("A")}
        self.all_policies(p, "unsupported")

    def test_typed_frames_distinguish_boolean_integer_and_missing_null(self):
        for first, second, final in (
            ({"x": const(True)}, {"x": const(1)}, relation(guards=[eq({"binding": "x"}, const(1))])),
            ({}, {"x": const(None)}, relation(arguments={"x": [{"binding": "x"}]},
                                            guards=[eq({"arg": "x"}, const(None))]))):
            p = correlated_profile()
            p["initial_bindings"] = {}
            p["relations"]["a_bad_binding"] = relation(updates=first)
            p["relations"]["b_good_binding"] = relation(updates=second)
            p["relations"]["finish"] = final
            self.all_policies(p, "supported")

    def test_current_history_and_owned_witness_survive_reuse(self):
        for policy in ablation.POLICIES:
            p = reconvergent_profile()
            memo, meter = lifter(p, policy)
            first = ("a", "common", "finish")
            status, steps = memo.lift(first)
            self.assertEqual(status, "supported")
            self.assertTrue(checker.check_certificate(p, witness_result(p, first, steps), NOW))
            steps[1]["bindings_after"]["x"] = "tampered output"
            second = ("b", "common", "finish")
            status, steps = memo.lift(second)
            self.assertEqual(status, "supported")
            self.assertEqual([s["edge"] for s in steps], list(second))
            self.assertTrue(checker.check_certificate(p, witness_result(p, second, steps), NOW))
            if ablation.POLICIES[policy][1]:
                self.assertGreater(meter.stats["relation_cache_hits"], 0)
            self.assertEqual(bool(memo._prefixes), ablation.POLICIES[policy][0])
            self.assertEqual(bool(memo._relations), ablation.POLICIES[policy][1])

    def test_unknown_prefix_and_incomplete_coverage_never_yield_false_negative(self):
        p = correlated_profile()
        p["model"]["transitions"] = [p["model"]["transitions"][0], p["model"]["transitions"][2]]
        p["relations"] = {"a_bad_binding": relation(emit={"unknown": "opaque"}),
                          "finish": relation(guards=[eq(const(1), const(2))])}
        self.all_policies(p, "unknown")
        p = profile()
        p["coverage"]["complete"] = False
        p["model"]["evidence"]["complete"] = False
        self.all_policies(p, "supported")
        p["relations"]["finish"] = relation(guards=[eq(const(1), const(2))])
        self.all_policies(p, "unknown")

    def test_freshness_and_call_isolation(self):
        p = profile()
        self.all_policies(p, "supported")
        p["relations"]["finish"] = relation(guards=[eq(const(1), const(2))])
        self.all_policies(p, "unsupported")
        p["model"]["evidence"]["valid_until"] = NOW - 1
        self.all_policies(p, "unknown")

    def test_partial_expansion_is_never_published_with_any_policy(self):
        for policy in ablation.POLICIES:
            p = profile()
            p["relations"]["finish"] = relation(arguments={"x": [{"literal": n} for n in range(16)]},
                                                updates={"x": {"arg": "x"}})
            memo, meter = lifter(p, policy)
            original = meter.tick
            def interrupt(kind):
                if kind == "relation_checks" and meter.stats["relation_checks"] == 2:
                    meter.limit = meter.stats["work_units"]
                original(kind)
            with patch.object(meter, "tick", side_effect=interrupt):
                with self.assertRaises(core._Limit):
                    memo._expand("finish", p["initial_bindings"], early_goal=False)
            self.assertFalse(memo._relations)
            self.assertEqual(meter.stats["relation_cache_entries"], 0)

    def test_final_early_witness_does_not_publish_incomplete_relation(self):
        for policy in ablation.POLICIES:
            p = profile()
            args = {"a" + str(i): [{"literal": v} for v in range(16)] for i in range(8)}
            p["relations"]["finish"] = relation(arguments=args)
            memo, meter = lifter(p, policy)
            self.assertEqual(memo.lift(("finish",))[0], "supported")
            self.assertEqual(meter.stats["relation_checks"], 1)
            self.assertFalse(memo._relations)

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            ablation.evaluate(profile(), NOW, cache_policy="unbounded")


if __name__ == "__main__":
    unittest.main()
