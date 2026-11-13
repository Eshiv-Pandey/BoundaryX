"""Controls for independent artifact/trace verification, not additional episodes."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("loss_verifier", ROOT / "scripts/verify_loss_benchmark_v1.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
BUNDLE = ROOT / "runs/loss-benchmark-v1/fresh-development-003"
RETAINED = ROOT / "runs/loss-benchmark-retained-v1/20261112T112741770806Z-3326eed1/episodes.json"


class VerifierControls(unittest.TestCase):
    def cell(self, profile):
        episodes = verifier.load_episodes(BUNDLE / "normalized-episodes.json")
        row = next(item for item in episodes if item["metadata"]["profile"] == profile)
        trace = verifier.read_json(BUNDLE / row["metadata"]["raw_trace"])
        case = next(case for case in verifier.read_json(BUNDLE / "input-cases.json")["cases"]
                    if case["case_id"] == row["metadata"]["case_id"])
        return row, trace, case

    def test_complete_captured_bundle_and_raw_retained_inputs_recheck(self):
        result = verifier.verify_bundle(BUNDLE, RETAINED)
        self.assertEqual((result["fresh_episodes_regraded"], result["retained_episodes_rebuilt"]), (80, 13))

    def test_false_success_cannot_override_wrong_original_task(self):
        row, trace, case = self.cell("wrong_task")
        row = deepcopy(row)
        row["task_completion"] = "pass"
        with self.assertRaisesRegex(verifier.VerificationError, "task regrade"):
            verifier.verify_fresh_cell(row, trace, case)

    def test_recovery_cannot_rewrite_initial_conversion_loss(self):
        row, trace, case = self.cell("recovery")
        row = deepcopy(row)
        item = next(item for item in row["context_items"] if item["id"] == "records")
        item["received"] = item["source"]
        item["present"]["received"] = True
        with self.assertRaisesRegex(verifier.VerificationError, "context presence"):
            verifier.verify_fresh_cell(row, trace, case)

    def test_manifest_rejects_changed_artifact_before_scoring(self):
        with tempfile.TemporaryDirectory(prefix="loss-verifier-control-") as temporary:
            copied = Path(temporary) / "allocation"
            shutil.copytree(BUNDLE, copied)
            with (copied / "fresh-results.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaisesRegex(verifier.VerificationError, "artifact integrity"):
                verifier.verify_bundle(copied, RETAINED)


if __name__ == "__main__":
    unittest.main()
