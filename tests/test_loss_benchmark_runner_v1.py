"""Constructed runner controls, not native/held-out research evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_loss_benchmark_v1 as runner


class FreshRunnerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = runner.load_cases()
        cls.budget = cls.package["episode_budget"]

    def test_ten_distinct_decisions_and_pinned_gold(self):
        cases = self.package["cases"]
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({case["family_id"] for case in cases}), 10)
        self.assertEqual(len({case["task"]["kind"] for case in cases}), 10)
        for case in cases:
            self.assertEqual(runner.gold_truth(case), case["gold"]["expected_answer"])
        damaged = deepcopy(self.package)
        damaged["cases"][0]["gold"]["expected_answer"] = {"service_ids": ["svc-a"]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps(damaged), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "pinned gold"):
                runner.load_cases(path)

    def test_full_profile_matrix_separates_safe_semantics_from_faults(self):
        expected_pass = {"reference", "placebo_identity", "safe_equivalent", "recovery"}
        for case in self.package["cases"]:
            senders, initial_states = [], []
            for profile in runner.PROFILES:
                episode, trace = runner.run_cell(case, profile, self.budget, [])
                self.assertEqual(episode["task_completion"], "pass" if profile in expected_pass else "fail", (case["case_id"], profile))
                events = trace["events"]
                senders.append(runner.canonical(next(e["payload"] for e in events if e["boundary"] == "sender_to_converter")))
                initial_states.append(runner.canonical(events[0]["payload"]))
                self.assertTrue(episode["metadata"]["gold_checks"]["forbidden_effects_absent"])
                self.assertEqual(episode["evidence_kind"], "fresh_constructed")
                self.assertEqual(episode["costs"]["model_tokens"], 0)
                if profile == "safe_equivalent":
                    records = next(item for item in episode["context_items"] if item["id"] == "records")
                    self.assertEqual(records["sent"], records["received"])
                    self.assertTrue(episode["metadata"]["raw_records_order_changed"])
                    self.assertTrue(all(row["status"] == "pass" for row in episode["fidelity_checks"]))
            self.assertEqual(len(set(senders)), 1, "sender information must be profile-invariant")
            self.assertEqual(len(set(initial_states)), 1, "full initial state must be profile-invariant")

    def test_known_absence_is_explicit_and_recovery_keeps_first_failure(self):
        case = self.package["cases"][0]
        dropped, drop_trace = runner.run_cell(case, "dropped_fact", self.budget, [])
        recovery, rec_trace = runner.run_cell(case, "recovery", self.budget, [])
        fact = next(row for row in dropped["context_items"] if row["id"] == "records")
        self.assertTrue(fact["observed"]["received"])
        self.assertFalse(fact["present"]["received"])
        self.assertIsNone(fact["received"])
        self.assertEqual(rec_trace["events"][:5], drop_trace["events"][:5])
        self.assertEqual(recovery["metadata"]["episode_budget"], dropped["metadata"]["episode_budget"])
        self.assertEqual(recovery["recovery"], {"eligible": True, "status": "pass"})
        self.assertEqual(recovery["metadata"]["receiver_attempts"], 2)
        self.assertEqual(recovery["metadata"]["initial_receiver_status"], "missing_fact")
        self.assertEqual(recovery["costs"]["tool_calls"], 2)
        self.assertEqual(dropped["costs"]["tool_calls"], 1)
        self.assertEqual(dropped["recovery"], {"eligible": False, "status": "not_applicable"})
        self.assertEqual(recovery["context_items"], dropped["context_items"], "successful recovery cannot erase initial converter loss")
        self.assertIsNotNone(recovery["metadata"]["post_recovery_context"]["records"])
        self.assertEqual(recovery["metadata"]["conversion_profile"], "dropped_fact")
        self.assertNotEqual(recovery["metadata"]["receiver_policy_id"], dropped["metadata"]["receiver_policy_id"])

    def test_capability_qualification_uses_isolated_actual_task_bound_invocation(self):
        case = self.package["cases"][0]
        for profile in runner.PROFILES:
            episode, trace = runner.run_cell(case, profile, self.budget, [])
            reference, observed = trace["diagnostic_capability_probes"]
            self.assertEqual(reference["result"]["status"], "pass")
            usable = profile not in {"wrong_task", "capability_mismatch"}
            self.assertEqual(observed["result"]["status"], "pass" if usable else "fail")
            self.assertEqual(episode["capability_items"][0]["observed_usable"], usable)
            self.assertEqual(observed["request"]["task_id"], trace["receiver_final"]["task_id"])
            self.assertEqual(observed["scope"], "isolated_diagnostic_clone_not_policy_episode")
            self.assertEqual(episode["costs"]["tool_calls"], 2 if profile == "recovery" else 1)
            for probe in (reference, observed):
                self.assertEqual(probe["request_identity"], runner.identity(runner.canonical(probe["request"])))
                self.assertEqual(probe["result_identity"], runner.identity(runner.canonical(probe["result"])))

    def test_independent_source_and_order_normalization_preserve_duplicate_records(self):
        case = self.package["cases"][0]
        source = runner.source_truth(case, self.budget)
        fixture = runner.ReadOnlyFixture(case, self.budget)
        sender = runner.make_sender(case, fixture, self.budget)
        sender["records"][0]["status"] = "changed"
        self.assertNotEqual(runner.context_projection(source), runner.context_projection(sender))
        source["records"].append(deepcopy(source["records"][0]))
        reversed_wire = deepcopy(source)
        reversed_wire["records"].reverse()
        projection = runner.context_projection(source)
        self.assertEqual(projection, runner.context_projection(reversed_wire))
        self.assertEqual(len(projection["records"]), 4)

    def test_grader_rejects_correct_answer_with_wrong_target_or_forbidden_effect(self):
        case = self.package["cases"][0]
        fixture = runner.ReadOnlyFixture(case, self.budget)
        sender = runner.make_sender(case, fixture, self.budget)
        output = runner.receiver_decision(sender)
        state = fixture.observe_state()
        self.assertEqual(runner.grade(case, output, state)["task_completion"], "pass")
        changed = deepcopy(output)
        changed["target"] = "wrong-service"
        self.assertEqual(runner.grade(case, changed, state)["task_completion"], "fail")
        changed = deepcopy(output)
        changed["task_id"] = "wrong-task"
        self.assertEqual(runner.grade(case, changed, state)["task_completion"], "fail")
        changed_state = deepcopy(state)
        changed_state["effects"] = ["restart_service"]
        self.assertFalse(runner.grade(case, output, changed_state)["checks"]["forbidden_effects_absent"])
        changed_state = deepcopy(state)
        changed_state["content_unchanged"] = False
        self.assertEqual(runner.grade(case, output, changed_state)["task_completion"], "fail")

    def test_receiver_uses_observation_without_gold_and_fixture_enforces_binding_budget(self):
        case = self.package["cases"][0]
        fixture = runner.ReadOnlyFixture(case, self.budget)
        sender = runner.make_sender(case, fixture, self.budget)
        self.assertNotIn("gold", sender)
        sender["records"][1]["status"] = "up"
        self.assertEqual(runner.receiver_decision(sender)["answer"], {"service_ids": []})
        self.assertEqual(runner.gold_truth(case), {"service_ids": ["svc-b"]})
        self.assertTrue(fixture.observe_state()["content_unchanged"])
        with self.assertRaisesRegex(ValueError, "unbound"):
            fixture.read_snapshot("decoy")
        with self.assertRaisesRegex(ValueError, "unbound"):
            fixture.read_snapshot(case["task"]["task_id"], "fixture.restart_service.v1")
        fixture.read_snapshot(case["task"]["task_id"])
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            fixture.read_snapshot(case["task"]["task_id"])

    def test_byte_costs_are_exact_serialized_transfers_and_resets_do_not_leak(self):
        case = self.package["cases"][0]
        for profile in runner.PROFILES:
            episode, trace = runner.run_cell(case, profile, self.budget, [])
            transfers = trace["transfers"]
            for event in trace["events"]:
                raw = runner.canonical(event["payload"])
                self.assertEqual(event["bytes"], len(raw))
                self.assertEqual(event["sha256"], hashlib.sha256(raw).hexdigest())
            costs = episode["costs"]
            self.assertGreater(costs["wall_ms"], 0)
            self.assertEqual(costs["messages"], len(transfers))
            for direction in ("request", "response"):
                self.assertEqual(costs[direction + "_bytes"], sum(t["bytes"] for t in transfers if t["direction"] == direction))
            self.assertEqual(trace["events"][0]["payload"]["reads"], [])
            self.assertEqual(trace["events"][0]["payload"]["effects"], [])

    def test_cli_artifacts_validate_and_existing_output_is_refused(self):
        from interoperability import loss_benchmark_v1 as metrics
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "fresh"
            command = [sys.executable, "-B", str(ROOT / "scripts/run_loss_benchmark_v1.py"), "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            rows = json.loads((output / "normalized-episodes.json").read_bytes())
            self.assertEqual(len(rows), 80)
            for row in rows:
                metrics.validate_episode(row)
            report = json.loads((output / "fresh-results.json").read_bytes())
            self.assertEqual(report["independent_decision_families"], 10)
            self.assertEqual(report["held_out_cases"], 0)
            receipt = json.loads((output / "execution-receipt.json").read_bytes())
            self.assertEqual(receipt["model_calls"], 0)
            manifest = json.loads((output / "manifest.json").read_bytes())
            for record in manifest["files"]:
                self.assertEqual(runner.identity((output / record["path"]).read_bytes()), {key: record[key] for key in ("bytes", "sha256")})
            before = (output / "manifest.json").read_bytes()
            repeated = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("FileExistsError", repeated.stderr)
            self.assertEqual((output / "manifest.json").read_bytes(), before)

    def test_retained_parser_preserves_kind_and_rejects_constructed_relabel(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "episodes.json"
            row = {"episode_id": "retained-1", "evidence_kind": "retained_empirical", "task_completion": "unknown"}
            path.write_text(json.dumps([row]), encoding="utf-8")
            self.assertEqual(runner.retained_episodes(path), [row])
            path.write_text(json.dumps([{**row, "evidence_kind": "fresh_constructed"}]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot relabel"):
                runner.retained_episodes(path)


if __name__ == "__main__":
    unittest.main()
