"""Focused single-profile command checks; no matrix or live application."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from interoperability import shared_admission_v1 as command

PROFILES = ROOT / "examples/refinement-development"
POSITIVE = PROFILES / "04-correlated-prefix-refinement.json"
NEGATIVE = PROFILES / "02-fixed-text-shape-obstruction.json"
OPAQUE = PROFILES / "07-opaque-serialization.json"


class SharedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.output = self.base / "receipt.json"

    def run_case(self, profile=POSITIVE, *, method="shared_lift", budget=100000, output=None):
        return command.run_admission(profile, output or self.output, method=method,
                                     work_budget=budget, now=100)

    def test_real_supported_witness_is_checked_and_bound_to_raw_input(self):
        receipt = self.run_case()
        self.assertEqual(receipt["status"], "recorded")
        self.assertEqual(receipt["result"]["decision"], "supported")
        self.assertEqual(receipt["result"]["certificate"]["kind"], "recipe-path")
        self.assertIs(receipt["certificate_valid"], True)
        self.assertTrue(receipt["checker_invoked"])
        self.assertEqual(receipt["input_sha256"], hashlib.sha256(POSITIVE.read_bytes()).hexdigest())
        self.assertEqual(receipt["model_sha256"], receipt["result"]["certificate"]["profile_sha256"])
        self.assertEqual(receipt["work_budget"], 100000)
        self.assertEqual(receipt["evaluation_clock"], 100)
        self.assertIn("refinement_shared_lift_v2.py", receipt["source_sha256"])
        self.assertEqual(receipt["application_requests"], 0)
        self.assertEqual(json.loads(self.output.read_bytes()), receipt)

    def test_both_negative_kinds_use_the_appropriate_independent_checker(self):
        expected = {"shared_lift": "refinement-exhaustion",
                    "direct_pruned": "goal-pruned-relational-exhaustion/2"}
        for method, kind in expected.items():
            with self.subTest(method=method):
                receipt = self.run_case(NEGATIVE, method=method, output=self.base / (method + ".json"))
                self.assertEqual(receipt["status"], "recorded")
                self.assertEqual(receipt["result"]["decision"], "unsupported")
                self.assertEqual(receipt["result"]["certificate"]["kind"], kind)
                self.assertIs(receipt["certificate_valid"], True)
                self.assertEqual(receipt["checker_module"], "interoperability.direct_goal_pruned_v2")

    def test_opaque_and_budget_unknowns_do_not_invoke_the_checker(self):
        cases = [(OPAQUE, 100000, "unresolved_relation_or_recipe"),
                 (POSITIVE, 1, "work_budget_exhausted")]
        with patch.object(command.direct, "check_certificate", side_effect=AssertionError("unknown checked")):
            for index, (profile, budget, reason) in enumerate(cases):
                with self.subTest(reason=reason):
                    receipt = self.run_case(profile, budget=budget, output=self.base / f"unknown-{index}.json")
                    self.assertEqual(receipt["status"], "recorded")
                    self.assertEqual(receipt["result"]["decision"], "unknown")
                    self.assertEqual(receipt["result"]["reason"], reason)
                    self.assertIsNone(receipt["result"]["certificate"])
                    self.assertIsNone(receipt["certificate_valid"])
                    self.assertIsNone(receipt["certificate_check_ns"])
                    self.assertTrue(receipt["unknown_has_no_certificate"])
                    self.assertFalse(receipt["checker_invoked"])

    def test_real_checker_rejects_a_forged_witness_and_failure_cannot_be_overwritten(self):
        model = json.loads(POSITIVE.read_bytes())
        forged = command.shared.evaluate(model, 100, budget=100000)
        forged["certificate"]["profile_sha256"] = "0" * 64
        with patch.object(command.shared, "evaluate", return_value=forged):
            receipt = self.run_case()
        self.assertEqual(receipt["status"], "failed_certificate")
        self.assertIs(receipt["certificate_valid"], False)
        self.assertEqual(receipt["result"], forged)
        retained = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.run_case()
        self.assertEqual(self.output.read_bytes(), retained)

    def test_missing_or_invented_certificates_fail_closed(self):
        for index, result in enumerate((
                {"decision": "supported", "reason": "missing proof", "certificate": None},
                {"decision": "unsupported", "reason": "missing proof", "certificate": None},
                {"decision": "unknown", "reason": "unresolved", "certificate": {"kind": "invented"}})):
            with self.subTest(result=result), patch.object(command.shared, "evaluate", return_value=result):
                receipt = self.run_case(output=self.base / f"missing-{index}.json")
                self.assertEqual(receipt["status"], "failed_certificate")
                self.assertFalse(receipt["checker_invoked"])
                self.assertEqual(receipt["result"], result)

    def test_malformed_json_results_are_retained_as_failure(self):
        cases = (
            {"decision": "unknown"},
            {"decision": "unknown", "certificate": None},
            {"decision": "unknown", "reason": 1, "certificate": None},
            {"decision": "unsupported", "reason": "certificate field absent"},
            {"decision": [], "reason": "invalid decision type", "certificate": None},
            [],
        )
        for index, result in enumerate(cases):
            output = self.base / f"malformed-{index}.json"
            with self.subTest(result=result), patch.object(command.shared, "evaluate", return_value=result):
                receipt = self.run_case(output=output)
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("malformed admission result", receipt["error"])
            self.assertFalse(receipt["checker_invoked"])
            self.assertEqual(receipt["result"], result)
            self.assertEqual(json.loads(output.read_bytes())["result"], result)

    def test_checker_return_must_be_exact_true(self):
        with patch.object(command.direct, "check_certificate", return_value=1):
            receipt = self.run_case()
        self.assertEqual(receipt["status"], "failed_certificate")
        self.assertIs(receipt["certificate_valid"], False)

    def test_solver_failure_is_retained_without_an_invented_decision(self):
        with patch.object(command.shared, "evaluate", side_effect=RuntimeError("focused failure")):
            receipt = self.run_case()
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("RuntimeError", receipt["error"])
        self.assertNotIn("result", receipt)
        self.assertIsInstance(receipt["evaluation_ns"], int)
        self.assertEqual(json.loads(self.output.read_bytes()), receipt)

    def test_json_type_changing_mutation_is_detected_without_changing_retained_model(self):
        profile = json.loads(POSITIVE.read_bytes())
        profile["initial_bindings"]["type_marker"] = True
        path = self.base / "boolean.json"
        path.write_text(json.dumps(profile), encoding="utf-8")

        def mutate(model, now, budget):
            model["initial_bindings"]["type_marker"] = 1
            return {"decision": "unknown", "reason": "test mutation", "certificate": None}

        with patch.object(command.shared, "evaluate", side_effect=mutate):
            receipt = self.run_case(path)
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("mutated", receipt["error"])
        self.assertIs(receipt["runtime_manifest"]["initial_bindings"]["type_marker"], True)
        self.assertEqual(json.loads(path.read_bytes()), profile)

    def test_ambiguous_json_and_invalid_numeric_options_are_rejected_before_evaluation(self):
        for index, raw in enumerate((b'{"id":"a","id":"b"}',
                                    b'{"schema_version":"recipe-continuation/1","value":NaN}',
                                    b'{"schema_version":"recipe-continuation/1","value":1e999}')):
            path = self.base / f"invalid-{index}.json"
            path.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.run_case(path)
            self.assertFalse(self.output.exists())
        for budget in (True, 0, -1, 1.0):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                self.run_case(budget=budget)
        with self.assertRaises(ValueError):
            command.run_admission(POSITIVE, self.output, work_budget=10, now=True)

    def test_cli_runs_corrected_direct_with_explicit_clock_and_budget(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = command.main(["--input", str(POSITIVE), "--method", "direct_pruned",
                                 "--work-budget", "100000", "--now", "100",
                                 "--output", str(self.output)])
        summary = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(summary["method"], "direct_pruned")
        self.assertEqual(summary["decision"], "supported")
        self.assertIs(summary["certificate_valid"], True)


if __name__ == "__main__":
    unittest.main()
