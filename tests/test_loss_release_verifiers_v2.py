"""Adversarial controls: false success, forged facts and unbound recovery fail."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts import verify_loss_release_v2 as v
from scripts import verify_loss_parts_v2 as parts
from scripts import run_loss_diagnostics_v2 as runner

PROTOCOL = ROOT / "runs/supervisor-handoff-20261113/protocol-main-001"
PARTS = ROOT / "runs/supervisor-handoff-20261113/parts-main-001"


class EvidenceVerifierControls(unittest.TestCase):
    def protocol_cell(self, profile="reference", route="native"):
        path = next((PROTOCOL / "cells").glob("*--" + profile + "--" + route + ".json"))
        cell = v.read_json(path)
        bank = v.read_json(PROTOCOL / "input-bank.json")
        case = next(c for c in bank["cases"] if c["case_id"] == cell["case_id"])
        return cell, case

    def parts_cell(self, kind="data", route="mgcrea_typed"):
        return v.read_json(PARTS / "cells" / f"{kind}--r0--{route}.json")

    def test_real_native_and_bridge_cell_regrade(self):
        for route in ("native", "amirk_typed", "mgcrea_typed", "mgcrea_raw"):
            cell, case = self.protocol_cell("reference", route)
            episode, _, _ = v.verify_protocol_cell(cell, case, [])
            self.assertEqual(episode["task_completion"], "pass")

    def test_false_success_rejected(self):
        cell, case = self.protocol_cell("wrong_task")
        cell["task_completion"] = "pass"
        with self.assertRaisesRegex(ValueError, "grade mismatch"):
            v.verify_protocol_cell(cell, case, [])

    def test_reported_public_artifact_must_match_actual_wire(self):
        cell, case = self.protocol_cell()
        cell["final_public_result"]["artifacts"][0]["parts"][0]["text"] = "{}"
        with self.assertRaisesRegex(ValueError, "public final artifact"):
            v.verify_protocol_cell(cell, case, [])

    def test_claimed_initial_context_cannot_be_restored(self):
        cell, case = self.protocol_cell("dropped_fact")
        cell["observation"]["received"]["records"] = case["records"]
        with self.assertRaisesRegex(ValueError, "service input differs"):
            v.verify_protocol_cell(cell, case, [])

    def test_forged_probe_is_rejected(self):
        cell, case = self.protocol_cell("capability_mismatch")
        cell["capability_probes"][1]["decoded"]["usable"] = True
        with self.assertRaisesRegex(ValueError, "probe outcome"):
            v.verify_protocol_cell(cell, case, [])

    def test_wire_bytes_rejected_before_scoring(self):
        cell, case = self.protocol_cell()
        cell["episode_wire"][0]["request"]["raw"] += " "
        with self.assertRaisesRegex(ValueError, "wire identity"):
            v.verify_protocol_cell(cell, case, [])

    def test_duplicate_manifest_and_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            runner.base.write_new(bundle / "manifest.json", {"files": [{"path": "a"}, {"path": "a"}]})
            with self.assertRaisesRegex(ValueError, "duplicate manifest"):
                v.verify_manifest(bundle)
            for name in ("../secret", "/secret", "dir\\secret"):
                with self.assertRaises(ValueError):
                    v.member(bundle, name)

    def test_repair_certificate_forged_outcome_refused(self):
        case = runner.generated_bank(1, 3)["cases"][0]
        source, _, received = runner.observations(case, {"max_receiver_attempts": 2, "max_snapshot_reads": 2}, "compound_all")
        cert = runner.diagnostic.diagnose_repairs(source, received, lambda x: runner.evaluate(case, x))
        cert["trials"][0]["assessment"]["task_completion"] = "pass"
        with self.assertRaisesRegex(ValueError, "repair outcome"):
            v.verify_repair(case, source, received, cert)

    def test_upstream_data_loss_and_raw_recovery_regrade(self):
        result = parts.verify_cell(self.parts_cell())
        self.assertFalse(result["payload_pass"])
        self.assertTrue(result["recovery_pass"])

    def test_text_payload_success_separate_from_metadata(self):
        result = parts.verify_cell(self.parts_cell("text"))
        self.assertTrue(result["payload_pass"])
        self.assertFalse(result["representation_pass"])

    def test_parts_false_success_rejected(self):
        cell = self.parts_cell()
        cell["required_representation_survived"] = True
        with self.assertRaisesRegex(ValueError, "representation grading"):
            parts.verify_cell(cell)

    def test_recovery_new_task_cannot_be_claimed(self):
        cell = self.parts_cell()
        cell["recovery"]["final_public_task"]["id"] = "foreign-task"
        with self.assertRaisesRegex(ValueError, "recovery final public task"):
            parts.verify_cell(cell)

    def test_upstream_native_gold_cannot_be_replaced(self):
        cell = self.parts_cell()
        cell["spec"]["expected"]["data"]["answer"] = 43
        with self.assertRaisesRegex(ValueError, "part gold mismatch"):
            parts.verify_cell(cell)


if __name__ == "__main__":
    unittest.main()
