"""Small authored-model checks; no applications or comparative timing study."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import generate_refinement_scaling_v1 as generator
from interoperability import benchmark, refinement, refinement_oracle


class ScalingGeneratorTests(unittest.TestCase):
    def test_default_cases_have_authored_decisions_and_independent_certificates(self):
        cases = generator.build_cases(generator.configuration())
        self.assertEqual(len(cases), 18)
        self.assertEqual({case["family"] for case in cases}, set(generator.FAMILIES))
        self.assertEqual({case["expected_decision_with_sufficient_budget"] for case in cases},
                         {"supported", "unsupported", "unknown"})
        for case in cases:
            with self.subTest(family=case["family"], scenario=case["scenario"]):
                profile = case["profile"]
                initial = deepcopy(profile)
                refinement.validate(profile)
                refinement_oracle.validate_profile(profile)
                for evaluator in (refinement.evaluate, refinement_oracle.evaluate):
                    result = evaluator(profile, 100, budget=100000)
                    self.assertEqual(result["decision"], case["expected_decision_with_sufficient_budget"])
                    if result["decision"] != "unknown":
                        self.assertTrue(refinement_oracle.check_certificate(profile, result, 100))
                    else:
                        self.assertIsNone(result["certificate"])
                    self.assertEqual(profile, initial, "Solver/checker mutated its shared input")

    def test_tiny_same_budget_is_unknown_not_a_false_semantic_refutation(self):
        for case in generator.build_cases(generator.configuration()):
            for evaluator in (refinement.evaluate, refinement_oracle.evaluate):
                with self.subTest(case=case["profile"]["id"], solver=evaluator.__module__):
                    result = evaluator(deepcopy(case["profile"]), 100, budget=1)
                    self.assertEqual((result["decision"], result["reason"], result["certificate"]),
                                     ("unknown", "work_budget_exhausted", None))
                    self.assertEqual(result["stats"]["budget"], 1)

    def test_correlated_pair_cannot_be_assembled_from_separate_frames(self):
        profile = generator.correlated_frames(4, 3, "unmatched_pair")
        updates = [relation["updates"] for relation in profile["relations"].values() if relation["updates"]]
        pairs = {(item["x"]["const"], item["y"]["const"]) for item in updates}
        self.assertIn("v0000", {left for left, _ in pairs})
        self.assertIn("v0001", {right for _, right in pairs})
        self.assertNotIn(("v0000", "v0001"), pairs)
        for evaluator in (refinement.evaluate, refinement_oracle.evaluate):
            self.assertEqual(evaluator(profile, 100, budget=100000)["decision"], "unsupported")
        first = refinement_oracle.evaluate(generator.correlated_frames(12, 2, "first_witness"), 100, budget=100000)
        last = refinement_oracle.evaluate(generator.correlated_frames(12, 2, "last_witness"), 100, budget=100000)
        self.assertLess(first["stats"]["argument_assignments"], last["stats"]["argument_assignments"])

    def test_reconvergence_exercises_path_enumeration_and_shared_product_states(self):
        measured = []
        for width in (2, 3):
            profile = generator.layered_reconvergence(width, 3, "late_refutation")
            candidate = refinement.evaluate(profile, 100, budget=100000)
            direct = refinement_oracle.evaluate(profile, 100, budget=100000)
            self.assertEqual((candidate["decision"], direct["decision"]), ("unsupported", "unsupported"))
            measured.append((candidate["stats"], direct["stats"]))
        self.assertGreater(measured[1][0]["abstract_paths"], measured[0][0]["abstract_paths"])
        self.assertEqual(measured[1][1]["product_states"], measured[0][1]["product_states"])
        early = refinement.evaluate(generator.layered_reconvergence(3, 3, "early_refutation"), 100, budget=100000)
        self.assertLess(early["stats"]["abstract_paths"], measured[1][0]["abstract_paths"])
        self.assertGreater(early["stats"]["refinements"], 0)

    def test_off_goal_work_is_irrelevant_to_completion_and_exercises_laziness(self):
        rows = []
        for width in (2, 4):
            profile = generator.off_goal_load(width, 2, "witness")
            candidate = refinement.evaluate(profile, 100, budget=100000)
            direct = refinement_oracle.evaluate(profile, 100, budget=100000)
            self.assertEqual((candidate["decision"], direct["decision"]), ("supported", "supported"))
            rows.append((candidate["stats"]["relation_checks"], direct["stats"]["argument_assignments"]))
        self.assertEqual(rows[0][0], rows[1][0])
        self.assertGreater(rows[1][1], rows[0][1])
        for evaluator in (refinement.evaluate, refinement_oracle.evaluate):
            result = evaluator(generator.off_goal_load(3, 2, "irrelevant_opaque"), 100, budget=100000)
            self.assertEqual(result["decision"], "unsupported")
            self.assertTrue(refinement_oracle.check_certificate(generator.off_goal_load(3, 2, "irrelevant_opaque"), result, 100))

    def test_argument_product_witness_order_changes_work_without_changing_decision(self):
        for evaluator, counter in ((refinement.evaluate, "relation_checks"),
                                   (refinement_oracle.evaluate, "argument_assignments")):
            first = evaluator(generator.argument_product(3, 3, "first_witness"), 100, budget=100000)
            last = evaluator(generator.argument_product(3, 3, "last_witness"), 100, budget=100000)
            self.assertEqual((first["decision"], last["decision"]), ("supported", "supported"))
            self.assertGreater(last["stats"][counter], first["stats"][counter])

    def test_horizon_boundary_refutes_only_completion_inside_declared_bound(self):
        for depth in (1, 4):
            for slack in (-1, 0, 1):
                profile = generator.horizon_boundary(depth, slack)
                for evaluator in (refinement.evaluate, refinement_oracle.evaluate):
                    result = evaluator(profile, 100, budget=100000)
                    self.assertEqual(result["decision"], "unsupported" if slack < 0 else "supported")
                    self.assertTrue(refinement_oracle.check_certificate(profile, result, 100))

    def test_configuration_rejects_invalid_axes_and_large_preparation(self):
        for options in ({"widths": (1,)}, {"widths": (True,)}, {"depths": (9,)},
                        {"argument_counts": (0,)}, {"budgets": (0,)}, {"widths": (2, 2)},
                        {"widths": (16,), "depths": (8,)}, {"widths": (16,), "argument_counts": (8,)},
                        {"families": ("unknown",)}, {"families": ()}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                generator.configuration(**options)

    def test_manifest_freezes_every_file_and_keeps_labels_outside_solver_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "frozen"
            report = generator.generate(destination, generator.configuration())
            manifest = json.loads((destination / "manifest.json").read_bytes())
            self.assertEqual(report["manifest"], generator.record(destination / "manifest.json", destination))
            rows = sorted((generator.record(path, destination) for path in destination.rglob("*")
                           if path.is_file() and path.name != "manifest.json"), key=lambda row: row["path"])
            self.assertEqual(manifest["files"], rows)
            suite, loaded = benchmark._suite(destination / "suite.json")
            self.assertEqual(suite["evaluation_clock"], 100)
            self.assertEqual(len(loaded), len(manifest["cases"]))
            forbidden = {"family", "scenario", "expected_decision_with_sufficient_budget", "expectation_rationale"}

            def no_labels(value):
                if isinstance(value, dict):
                    self.assertFalse(forbidden & value.keys())
                    for item in value.values():
                        no_labels(item)
                elif isinstance(value, list):
                    for item in value:
                        no_labels(item)

            for index, (_, path, profile) in enumerate(loaded, 1):
                no_labels(profile)
                self.assertEqual(profile["id"], f"scale-{index:04d}")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest["cases"][index - 1]["input"]["sha256"])
            self.assertEqual(manifest["measurements_executed_by_generator"], 0)
            self.assertFalse(manifest["held_out"])
            self.assertFalse(manifest["comparison"]["work_units_are_identical_primitives"])
            before = (destination / "manifest.json").read_bytes()
            with self.assertRaises(FileExistsError):
                generator.generate(destination, generator.configuration())
            self.assertEqual((destination / "manifest.json").read_bytes(), before)

    def test_generation_is_byte_reproducible_and_axes_expand_without_duplicate_ids(self):
        config = generator.configuration(widths=(3, 2), depths=(3, 2), argument_counts=(2, 1))
        cases = generator.build_cases(config)
        self.assertEqual(len({row["profile"]["id"] for row in cases}), len(cases))
        for case in cases:
            refinement.validate(case["profile"])
            refinement_oracle.validate_profile(case["profile"])
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / name for name in ("first", "second")]
            for destination in paths:
                generator.generate(destination, generator.configuration())
            self.assertEqual((paths[0] / "manifest.json").read_bytes(), (paths[1] / "manifest.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
