from copy import deepcopy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from interoperability import loss_diagnostics_v2 as d
from scripts import run_loss_diagnostics_v2 as runner


class LossDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.bank = runner.generated_bank(1, 19)
        self.case = self.bank["cases"][0]
        self.source = runner.base.source_truth(self.case, self.bank["episode_budget"])

    def test_compound_fault_requires_both_repairs(self):
        _, _, observed = runner.observations(self.case, self.bank["episode_budget"], "compound_records_binding")
        cert = d.diagnose_repairs(self.source, observed, lambda x: runner.evaluate(self.case, x))
        self.assertEqual(cert["trial_count"], 4)
        self.assertEqual(cert["minimal_repair_sets"], [["records", "tool_binding"]])
        self.assertEqual(cert["minimum_repair_group_count"], 2)
        self.assertEqual([t["assessment"]["task_completion"] for t in cert["trials"]], ["fail", "fail", "fail", "pass"])

    def test_all_four_faults_require_four_repairs(self):
        _, _, observed = runner.observations(self.case, self.bank["episode_budget"], "compound_all")
        cert = d.diagnose_repairs(self.source, observed, lambda x: runner.evaluate(self.case, x))
        self.assertEqual(cert["trial_count"], 16)
        self.assertEqual(cert["minimum_repair_group_count"], 4)

    def test_success_needs_empty_repair(self):
        cert = d.diagnose_repairs(self.source, self.source, lambda x: runner.evaluate(self.case, x))
        self.assertEqual(cert["minimal_repair_sets"], [[]])

    def test_multiple_inclusion_minimal_repairs(self):
        observed = deepcopy(self.source)
        observed.pop("records")
        observed["tool_binding"] = "bad"
        cert = d.diagnose_repairs(self.source, observed, lambda x: {"task_completion": "pass" if "records" in x or x["tool_binding"] == runner.base.REQUIRED_TOOL else "fail"})
        self.assertEqual(cert["minimal_repair_sets"], [["records"], ["tool_binding"]])

    def test_unknown_is_preserved_in_certificate(self):
        cert = d.diagnose_repairs(self.source, self.source, lambda x: {"task_completion": "unknown"})
        self.assertEqual(cert["status"], "partial")
        self.assertIsNone(cert["minimum_repair_group_count"])

    def test_checker_rejects_tampered_minimality(self):
        cert = d.diagnose_repairs(self.source, self.source, lambda x: runner.evaluate(self.case, x))
        cert["minimal_repair_sets"] = [["records"]]
        with self.assertRaises(ValueError):
            d.verify_repair_certificate(cert, self.source, self.source, lambda x: runner.evaluate(self.case, x))

    def test_restore_is_pure_and_supports_absence(self):
        observed = deepcopy(self.source)
        observed.pop("records")
        restored = d.restore_groups(observed, self.source, ["records"])
        self.assertNotIn("records", observed)
        self.assertIn("records", restored)
        self.assertNotIn("records", d.restore_groups(restored, observed, ["records"]))

    def test_duplicate_and_unknown_group_rejected(self):
        for groups in (["records", "records"], ["nonexistent"]):
            with self.assertRaises(ValueError):
                d.restore_groups(self.source, self.source, groups)

    def test_leaf_type_sensitivity_and_escaping(self):
        diff = d.boundary_diff({"x/y": True, "empty": []}, {"x/y": 1, "empty": []})
        self.assertEqual(diff["changed_paths"], ["/x~1y"])
        self.assertEqual(diff["kept"], 1)
        self.assertFalse(d.same_json(1, 1.0))

    def test_uncaptured_boundary_is_unknown(self):
        self.assertEqual(d.boundary_diff(None, {})["status"], "unknown")
        self.assertIsNone(d.boundary_diff(None, {})["rate"])

    def test_reorder_differs_raw_but_not_declared_normalized(self):
        received = deepcopy(self.source)
        received["records"].reverse()
        self.assertGreater(d.boundary_diff(self.source, received)["changed"], 0)
        self.assertEqual(d.boundary_diff(self.source, received, True)["rate"], 1)

    def test_duplicate_preservation(self):
        before = {"records": [{"x": 1}, {"x": 1}]}
        after = {"records": [{"x": 1}]}
        self.assertEqual(d.boundary_diff(before, after, True)["missing"], 1)

    def test_extraction_loss_has_no_conversion_loss(self):
        source, sent, received = runner.observations(self.case, self.bank["episode_budget"], "extraction_loss")
        self.assertGreater(d.boundary_diff(source, sent, True)["missing"], 0)
        self.assertEqual(d.boundary_diff(sent, received, True)["rate"], 1)

    def test_generated_reference_gold_matches_distinct_receiver(self):
        bank = runner.generated_bank(3, 91)
        self.assertEqual(len(bank["cases"]), 30)
        self.assertEqual(len({c["family_id"] for c in bank["cases"]}), 10)
        for case in bank["cases"]:
            result = runner.evaluate(case, runner.base.source_truth(case, bank["episode_budget"]))
            self.assertEqual(result["task_completion"], "pass", case["case_id"])
        self.assertEqual(d.canonical(bank), d.canonical(runner.generated_bank(3, 91)))

    def test_recovery_keeps_initial_loss_and_separate_costs(self):
        episode, trace, detail = runner.run_cell(self.case, "recovery", self.bank["episode_budget"], [])
        self.assertEqual(episode["task_completion"], "pass")
        self.assertGreater(detail["boundaries"]["conversion"]["missing"], 0)
        self.assertEqual(episode["costs"]["tool_calls"], 2)
        self.assertEqual(detail["repair_diagnostic_cost"]["receiver_evaluations"], 2)
        self.assertEqual(len(trace["capability_probes"]), 2)

    def test_pairing_rejects_duplicates_and_retains_unknown(self):
        rows = [{"pair_id": "a", "task_completion": "pass"}, {"pair_id": "b", "task_completion": "unknown"}]
        comparison = [{"pair_id": "a", "task_completion": "fail"}, {"pair_id": "b", "task_completion": "pass"}, {"pair_id": "c", "task_completion": "pass"}]
        result = d.paired_outcomes(rows, comparison)
        self.assertEqual(result["outcomes"]["unknown"], 1)
        self.assertEqual(result["unmatched_comparison"], ["c"])
        self.assertEqual(result["observed_pass_difference"], -1)
        with self.assertRaises(ValueError):
            d.paired_outcomes(rows + rows, comparison)


if __name__ == "__main__":
    unittest.main()
