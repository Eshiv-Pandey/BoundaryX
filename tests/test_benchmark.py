"""End-to-end execution, failure accounting and capture/replay invariants."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from interoperability import benchmark
from test_baseline import tiny_model


PLUGIN = '''
from .baseline import evaluate
def abstain(model, now):
    return {'decision':'unknown','reason':'resource abstention','certificate':None,'stats':{'work':0}}
def mutate(model, now):
    model['horizon'] = 0
    return evaluate(model, now)
def malformed(model, now):
    return {'decision':'unknown','reason':'certificate field omitted'}
def fail(model, now):
    raise RuntimeError('intentional worker failure')
def bad_certificate(model, now):
    result = evaluate(model, now)
    result['certificate']['model_sha256'] = '0' * 64
    return result
def stall(model, now):
    import time
    time.sleep(5)
    return evaluate(model, now)
def case_sensitive(model, now):
    if model['id'] == 'unfavourable':
        raise RuntimeError('retained unfavourable case')
    return evaluate(model, now)
'''


class BenchmarkExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="admission benchmark ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "source/interoperability"
        shutil.copytree(Path(benchmark.__file__).parent, self.package,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.package / "benchmark_test_plugin.py").write_text(PLUGIN, encoding="utf-8")
        self.suite = self.root / "suite.json"
        self.output = self.root / "output"
        self.write_suite([tiny_model()])

    def write_suite(self, models, *, split="development"):
        cases = []
        for index, model in enumerate(models):
            name = f"case-{index}.json"
            (self.root / name).write_text(json.dumps(model), encoding="utf-8")
            cases.append({"path": name, "family": "unit-development"})
        self.suite.write_text(json.dumps({"schema_version":"admission-benchmark-suite/1",
            "id":"unit-suite", "split":split, "evaluation_clock":20, "cases":cases}), encoding="utf-8")

    def run_suite(self, function="evaluate", **kwargs):
        candidate = benchmark.AlgorithmSpec("candidate", "interoperability.benchmark_test_plugin", function)
        return benchmark.run_benchmark(self.suite, self.output, [candidate],
                                       package_dir=self.package, **kwargs)

    def rows(self):
        return [json.loads(line) for line in (self.output / "results.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_run_captures_equal_input_clock_code_and_independent_certificate_jobs(self):
        result = self.run_suite()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["candidate_evaluation_complete"])
        self.assertEqual(result["algorithms"]["candidate"]["certified_coverage"], 1)
        row = self.rows()[0]
        self.assertEqual(row["evaluation_clock"], 20)
        self.assertEqual(row["algorithms"]["candidate"]["execution"]["result"]["decision"], "supported")
        self.assertTrue(row["algorithms"]["candidate"]["certificate_valid"])
        self.assertIn("stats", row["algorithms"]["candidate"]["execution"]["result"])
        metric = result["algorithms"]["candidate"]
        self.assertEqual(metric["certificate_timing"]["invocations"], 1)
        self.assertEqual(metric["evaluation_and_certificate_timing"]["invocations"], 2)
        self.assertEqual(result["reference_timing"]["invocations"], 1)
        self.assertEqual(result["all_invocation_timing"]["invocations"], 5)
        self.assertEqual(metric["evaluation_and_certificate_timing"]["worker_wall_ns"]["total"],
                         metric["worker_wall_ns"]["total"] + metric["certificate_timing"]["worker_wall_ns"]["total"])
        self.assertTrue(benchmark.verify_bundle(self.output)["summary_recomputed"])
        for job in (self.output / "jobs").glob("*/input.json"):
            data = json.loads(job.read_bytes())
            self.assertEqual(data["runtime_manifest"], tiny_model())
            self.assertEqual(data["now"], 20)
            self.assertNotIn("gold", data)

    def test_unknown_is_coverage_loss_not_unsoundness_or_certificate(self):
        result = self.run_suite("abstain")
        metric = result["algorithms"]["candidate"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(metric["decision_agreement_rate"], 0)
        self.assertEqual(metric["abstained_on_reference_decided"], 1)
        self.assertEqual(metric["certified_coverage"], 0)
        self.assertEqual(metric["certificates_invalid"], 0)
        self.assertEqual(metric["certificate_timing"]["invocations"], 0)
        self.assertIsNone(metric["certificate_timing"]["evaluation_ns"]["total"])

    def test_recipe_schema_uses_full_profile_and_same_input_direct_baseline(self):
        profile = {"schema_version":"recipe-continuation/1", "id":"recipe-unit",
            "model":tiny_model(), "initial_bindings":{"approval":"allowed"},
            "relations":{"finish":{"source_ref":"authored unit recipe", "arguments":{
                "token":[{"binding":"approval"}]}, "emit":{"object":{"token":{"arg":"token"}}},
                "guards":[{"op":"eq", "left":{"emit_path":["token"]}, "right":{"const":"allowed"}}],
                "updates":{}}}, "coverage":{"complete":True, "scope":"authored finite unit recipes"}}
        self.write_suite([profile])
        candidate = benchmark.AlgorithmSpec("candidate", "interoperability.refinement", input_schema="recipe-continuation/1")
        result = benchmark.run_benchmark(self.suite, self.output, [candidate], package_dir=self.package, work_budget=100000)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["candidate_evaluation_complete"])
        self.assertEqual(result["algorithms"]["candidate"]["supported"], 1)
        execution = json.loads((self.output / "execution.json").read_bytes())
        self.assertTrue(execution["reference_implementation_is_baseline"])
        self.assertEqual(execution["algorithms"][0]["module"], "interoperability.refinement_oracle")
        for job in (self.output / "jobs").glob("*/input.json"):
            data = json.loads(job.read_bytes())
            self.assertEqual(data["runtime_manifest"], profile)
            if data["kind"] == "evaluate":
                self.assertEqual(data["keyword_arguments"], {"budget":100000})
        self.assertTrue(benchmark.verify_bundle(self.output)["summary_recomputed"])

    def test_input_mutation_is_an_error_and_does_not_change_baseline_input(self):
        result = self.run_suite("mutate")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["algorithms"]["candidate"]["errors"], 1)
        self.assertEqual(result["algorithms"]["baseline"]["supported"], 1)
        self.assertFalse(self.rows()[0]["algorithms"]["candidate"]["execution"]["input_unchanged"])

    def test_invalid_certificate_fails_even_when_decision_agrees(self):
        result = self.run_suite("bad_certificate")
        self.assertEqual(result["status"], "failed")
        metric = result["algorithms"]["candidate"]
        self.assertEqual(metric["decision_agreements"], 1)
        self.assertEqual(metric["certificates_invalid"], 1)
        self.assertEqual(metric["certified_coverage"], 0)
        self.assertEqual(metric["certificate_timing"]["evaluation_ns"]["observed"], 1)
        self.assertGreater(metric["certificate_timing"]["worker_wall_ns"]["total"], 0)

    def test_worker_failure_does_not_drop_later_cases_or_error_denominators(self):
        second = tiny_model(); second["id"] = "second"
        self.write_suite([tiny_model(), second])
        result = self.run_suite("fail")
        metric = result["algorithms"]["candidate"]
        self.assertEqual(result["cases"], 2)
        self.assertEqual(metric["scheduled"], 2)
        self.assertEqual(metric["errors"], 2)
        self.assertEqual(metric["decision_coverage"], 0)
        self.assertEqual(metric["evaluation_ns"]["samples"], [None, None])
        self.assertIsNone(metric["evaluation_ns"]["total"])
        self.assertEqual(metric["evaluation_ns"]["missing"], 2)
        self.assertEqual(metric["worker_wall_ns"]["observed"], 2)
        self.assertGreater(metric["worker_wall_ns"]["total"], 0)
        self.assertEqual(result["all_invocation_timing"]["invocations"], 8)
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(benchmark.verify_bundle(self.output)["status"], "passed")

    def test_malformed_unknown_is_not_scored_as_an_abstention(self):
        result = self.run_suite("malformed")
        self.assertEqual(result["algorithms"]["candidate"]["errors"], 1)
        self.assertEqual(result["algorithms"]["candidate"]["unknown"], 0)

    def test_worker_timeout_is_retained(self):
        result = self.run_suite("stall", timeout_seconds=1.0)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.rows()[0]["algorithms"]["candidate"]["execution"]["status"], "timed_out")
        metric = result["algorithms"]["candidate"]
        self.assertEqual(metric["evaluation_ns"]["samples"], [None])
        self.assertIsNone(metric["evaluation_ns"]["total"])
        self.assertGreaterEqual(metric["worker_wall_ns"]["total"], 1000000000)
        self.assertTrue((self.output / "jobs/case-0000-candidate/process.json").exists())

    def test_declared_schema_mismatch_is_explicit_and_not_candidate_completion(self):
        spec = benchmark.AlgorithmSpec("candidate", "interoperability.benchmark_test_plugin", input_schema="another/1")
        result = benchmark.run_benchmark(self.suite, self.output, [spec], package_dir=self.package)
        self.assertEqual(result["status"], "completed_with_gaps")
        self.assertFalse(result["candidate_evaluation_complete"])
        self.assertEqual(result["algorithms"]["candidate"]["eligible"], 0)
        self.assertIsNone(result["algorithms"]["candidate"]["decision_agreement_rate"])

    def test_replay_executes_captured_plugin_even_if_original_source_changed(self):
        original = self.run_suite()
        (self.package / "benchmark_test_plugin.py").write_text("raise RuntimeError('changed original')\n", encoding="utf-8")
        replay = benchmark.replay_benchmark(self.output, self.root / "replay")
        self.assertEqual(replay["status"], "passed")
        self.assertEqual(replay["algorithms"]["candidate"]["supported"], original["algorithms"]["candidate"]["supported"])
        self.assertTrue(replay["snapshot_inputs_unchanged"])

    def test_existing_output_and_non_development_inputs_are_rejected(self):
        self.output.mkdir(); (self.output / "prior.txt").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.run_suite()
        self.assertEqual((self.output / "prior.txt").read_text(), "preserve")
        self.assertFalse((self.output / "runner-failure.json").exists())
        wire = tiny_model(); wire["provenance"]["kind"] = "wire-derived"
        self.write_suite([wire])
        with self.assertRaisesRegex(ValueError, "wire-derived"):
            benchmark.run_benchmark(self.suite, self.root / "wire", package_dir=self.package)
        self.assertFalse((self.root / "wire").exists())
        self.write_suite([tiny_model()], split="held-out")
        with self.assertRaisesRegex(ValueError, "development"):
            benchmark.run_benchmark(self.suite, self.root / "heldout", package_dir=self.package)

    def test_verifier_recomputes_summary_even_when_file_hashes_are_updated(self):
        self.run_suite()
        summary_path = self.output / "summary.json"
        summary = json.loads(summary_path.read_bytes())
        summary["algorithms"]["candidate"]["decision_agreement_rate"] = 0
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        for row in manifest["files"]:
            if row["path"] == "summary.json":
                raw = summary_path.read_bytes()
                row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        manifest["bytes"] = sum(row["bytes"] for row in manifest["files"])
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "summary disagrees"):
            benchmark.verify_bundle(self.output)

    def test_deleted_unfavourable_case_fails_even_with_recomputed_summary_and_hashes(self):
        bad = tiny_model(); bad["id"] = "unfavourable"
        self.write_suite([tiny_model(), bad])
        result = self.run_suite("case_sensitive")
        self.assertEqual(result["status"], "failed")
        favourable_rows = self.rows()[:1]
        execution = json.loads((self.output / "execution.json").read_bytes())
        specs = [benchmark.AlgorithmSpec(**spec) for spec in execution["algorithms"]]
        forged = json.loads((self.output / "summary.json").read_bytes())
        forged.update(benchmark.summarize(favourable_rows, specs))
        self.assertEqual(forged["status"], "passed")
        (self.output / "summary.json").write_text(json.dumps(forged), encoding="utf-8")
        (self.output / "results.jsonl").write_text(json.dumps(favourable_rows[0])+"\n", encoding="utf-8")
        path = self.output / "manifest.json"
        manifest = json.loads(path.read_bytes())
        for row in manifest["files"]:
            if row["path"] in ("summary.json", "results.jsonl"):
                raw = (self.output / row["path"]).read_bytes()
                row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        manifest["bytes"] = sum(row["bytes"] for row in manifest["files"])
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertTrue((self.output / "inputs/case-0001.json").exists())
        with self.assertRaisesRegex(ValueError, "case membership"):
            benchmark.verify_bundle(self.output)

    def test_framework_failure_preserves_partial_run_and_failure_reason(self):
        with patch.object(benchmark, "_invoke", side_effect=OSError("fixture IO failure")):
            with self.assertRaisesRegex(OSError, "fixture IO"):
                self.run_suite()
        self.assertTrue((self.output / "execution.json").exists())
        failure = json.loads((self.output / "runner-failure.json").read_bytes())
        self.assertEqual(failure["status"], "failed")
        self.assertEqual(failure["error_type"], "OSError")

    def test_case_order_family_algorithm_and_input_path_are_bound_even_after_rehash(self):
        second = tiny_model(); second["id"] = "second"
        self.write_suite([tiny_model(), second])
        self.run_suite()
        original = self.rows()
        mutations = [
            ("order", lambda rows: rows.reverse()),
            ("family", lambda rows: rows[0].update(family="changed")),
            ("algorithm", lambda rows: rows[0]["algorithms"].pop("candidate")),
            ("input", lambda rows: rows[0].update(input_snapshot="../case-0.json")),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                rows = json.loads(json.dumps(original))
                mutate(rows)
                target = self.output / "results.jsonl"
                target.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                path = self.output / "manifest.json"
                manifest = json.loads(path.read_bytes())
                for row in manifest["files"]:
                    if row["path"] == "results.jsonl":
                        raw = target.read_bytes()
                        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                manifest["bytes"] = sum(row["bytes"] for row in manifest["files"])
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(ValueError):
                    benchmark.verify_bundle(self.output)

    def test_development_recipe_suite_contains_all_eleven_profiles_at_fixed_clock(self):
        root = Path(__file__).resolve().parents[1]
        suite, cases = benchmark._suite(root / "examples/benchmark-development/recipe-v1.json")
        manifest = json.loads((root / "examples/refinement-development/manifest.json").read_bytes())
        self.assertEqual(suite["evaluation_clock"], 100)
        self.assertEqual(len(cases), 11)
        self.assertEqual({source.name for _, source, _ in cases},
                         {row["file"] for row in manifest["profiles"]})
        self.assertEqual({model["schema_version"] for _, _, model in cases}, {"recipe-continuation/1"})


if __name__ == "__main__":
    unittest.main()
