"""Small actual run/replay plus adversarial record binding; no scaling matrix."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from interoperability import benchmark, benchmark_resources_v1 as resources
from interoperability import shared_lifting_comparison_v3 as comparison
from test_direct_goal_pruned_v2 import off_goal


def files(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


class SharedComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cases = []
        for index, succeeds in enumerate((True, False)):
            profile = off_goal(succeeds=succeeds)
            profile["id"] = f"shared-harness-{index}"
            name = f"profile-{index}.json"
            (cls.base / name).write_text(json.dumps(profile), encoding="utf-8")
            cases.append({"path": name, "family": "focused-off-goal"})
        cls.suite = cls.base / "suite.json"
        cls.suite.write_text(json.dumps({"schema_version": "admission-benchmark-suite/1",
            "id": "shared-two-profile-harness", "split": "development", "evaluation_clock": 100,
            "cases": cases}), encoding="utf-8")
        cls.adapter = benchmark.ADAPTERS[comparison.SCHEMA]
        cls.boot = benchmark._WORKER_BOOT
        cls.bundle = cls.base / "comparison"
        cls.result = comparison.run(cls.suite, cls.bundle, work_budget=100000, timeout_seconds=30)
        cls.original = files(cls.bundle)

    def rows(self, directory=None):
        return [json.loads(line) for line in ((directory or self.bundle) / "results.jsonl").read_bytes().splitlines()]

    def test_four_arms_checking_costs_and_resource_observations(self):
        result = self.result
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["summary"]["all_invocation_timing"]["invocations"], 18)
        checked = result["verification"]
        self.assertEqual(checked["worker_jobs_bound"], 18)
        self.assertEqual(checked["certificate_jobs_bound"], 8)
        for row, decision in zip(self.rows(), ("supported", "unsupported")):
            for arm in row["algorithms"].values():
                self.assertEqual(arm["execution"]["result"]["decision"], decision)
                self.assertTrue(arm["certificate_valid"])
                self.assertEqual(arm["execution"]["resources"]["schema_version"], resources.SCHEMA)
                self.assertEqual(arm["certificate_check"]["resources"]["schema_version"], resources.SCHEMA)
        for arm in checked["resource_summary"]["algorithms"].values():
            self.assertEqual(arm["evaluation_and_certificate"]["invocations"], 4)
            self.assertEqual(arm["evaluation_and_certificate"]["peak_resident_bytes"]["observed"], 4)
        self.assertEqual(self.rows()[1]["algorithms"]["shared_lift"]["execution"]["result"]["certificate"]["kind"],
                         "refinement-exhaustion")

    def test_configuration_restores_and_existing_allocation_is_immutable(self):
        self.assertIs(benchmark.ADAPTERS[comparison.SCHEMA], self.adapter)
        self.assertEqual(benchmark._WORKER_BOOT, self.boot)
        with patch.object(benchmark, "run_benchmark", side_effect=RuntimeError("inert failure")):
            with self.assertRaisesRegex(RuntimeError, "inert failure"):
                comparison.run(self.suite, self.base / "failed-allocation")
        self.assertIs(benchmark.ADAPTERS[comparison.SCHEMA], self.adapter)
        self.assertEqual(benchmark._WORKER_BOOT, self.boot)
        with self.assertRaises(ValueError):
            comparison.run(self.suite, self.bundle)
        with self.assertRaises(ValueError):
            comparison.replay(self.bundle, self.bundle)
        self.assertEqual(files(self.bundle), self.original)

    def test_actual_captured_replay_preserves_decisions_and_certificates(self):
        target = self.base / "replay"
        with patch.object(benchmark, "replay_benchmark", side_effect=AssertionError("legacy replay used")):
            result = comparison.replay(self.bundle, target)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["source_package"], str(self.bundle / "source/interoperability"))
        self.assertEqual(result["verification"]["worker_jobs_bound"], 18)
        for first, repeated in zip(self.rows(), self.rows(target)):
            self.assertEqual(first["model_sha256"], repeated["model_sha256"])
            for name in first["algorithms"]:
                a, b = first["algorithms"][name], repeated["algorithms"][name]
                self.assertEqual(a["execution"]["result"]["decision"], b["execution"]["result"]["decision"])
                self.assertEqual(a["execution"]["result"]["certificate"], b["execution"]["result"]["certificate"])
                self.assertEqual(a["certificate_valid"], b["certificate_valid"])
        self.assertEqual(files(self.bundle), self.original)

    def test_verify_is_read_only_and_rejects_worker_dispatch_tampering_after_rehash(self):
        with patch.object(benchmark, "_invoke", side_effect=AssertionError("verification invoked a worker")):
            result = comparison.verify(self.bundle)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(files(self.bundle), self.original)
        forged = self.base / "forged"
        shutil.copytree(self.bundle, forged)
        job_path = forged / "jobs/case-0000-shared_lift/input.json"
        job = json.loads(job_path.read_bytes())
        job["module"] = "interoperability.refinement"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        manifest_path = forged / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"] = [benchmark._record(forged / record["path"], forged) for record in manifest["files"]]
        manifest["bytes"] = sum(record["bytes"] for record in manifest["files"])
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        benchmark.verify_bundle(forged)
        with self.assertRaisesRegex(ValueError, "Worker dispatch"):
            comparison.verify(forged)

    def test_validity_flags_and_required_checks_are_derived_after_rehash(self):
        mutations = (
            ("reference", lambda row: row.update(reference_valid=False), "Reference validity"),
            ("valid", lambda row: row["algorithms"]["shared_lift"].update(valid_result=False), "Algorithm validity"),
            ("certificate", lambda row: row["algorithms"]["shared_lift"].update(certificate_valid=False), "Certificate validity"),
            ("missing", lambda row: row["algorithms"]["shared_lift"].pop("certificate_check"), "Required certificate"),
            ("agreement", lambda row: row["algorithms"]["shared_lift"].update(decision_agreement=False), "Decision agreement"),
        )
        for label, mutate, message in mutations:
            with self.subTest(label=label):
                forged = self.base / ("forged-" + label)
                shutil.copytree(self.bundle, forged)
                rows = self.rows(forged)
                mutate(rows[0])
                (forged / "results.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                summary_path = forged / "summary.json"
                summary = json.loads(summary_path.read_bytes())
                summary.update(benchmark.summarize(rows, list(comparison.ALGORITHMS)))
                summary_path.write_text(json.dumps(summary), encoding="utf-8")
                manifest_path = forged / "manifest.json"
                manifest = json.loads(manifest_path.read_bytes())
                manifest["files"] = [benchmark._record(forged / record["path"], forged) for record in manifest["files"]]
                manifest["bytes"] = sum(record["bytes"] for record in manifest["files"])
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                benchmark.verify_bundle(forged)
                with self.assertRaisesRegex(ValueError, message):
                    comparison.verify(forged)


if __name__ == "__main__":
    unittest.main()
