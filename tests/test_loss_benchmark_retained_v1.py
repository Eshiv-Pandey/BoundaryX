"""Integrity and task-relative rejection controls for retained reanalysis."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PORTABLE_ROOT = ROOT / "benchmark/loss-v1/retained-inputs"
INPUT_ROOT = PORTABLE_ROOT if PORTABLE_ROOT.is_dir() else ROOT
SPEC = importlib.util.spec_from_file_location("retained_builder", ROOT / "scripts/build_loss_benchmark_retained_v1.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def entity(value):
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return {"base64": base64.b64encode(raw).decode("ascii"), "raw": raw.decode("utf-8"),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "json": value}


class RetainedInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = builder.strict_json(builder.MANIFEST.read_bytes())
        cls.episodes = builder.build_episodes(INPUT_ROOT, builder.MANIFEST)
        cls.by_id = {row["episode_id"]: row for row in cls.episodes}

    def test_selected_exact_capture_accounting(self):
        self.assertEqual(len(self.episodes), 13)
        self.assertEqual(sum(row["task_completion"] == "pass" for row in self.episodes), 5)
        self.assertEqual(sum(row["task_completion"] == "fail" for row in self.episodes), 8)
        self.assertEqual(len({row["family_id"] for row in self.episodes}), 4)

    def test_episodes_satisfy_metric_engine_contract(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from interoperability.loss_benchmark_v1 import validate_episode
        for episode in self.episodes:
            validate_episode(episode)

    def test_all_retained_sources_are_pinned_and_real(self):
        pins = {row["path"]: row["sha256"] for row in self.manifest["source_files"]}
        for episode in self.episodes:
            self.assertTrue(episode["source_files"])
            for row in episode["source_files"]:
                self.assertEqual(row["sha256"], pins[row["path"]])
                self.assertEqual(hashlib.sha256((INPUT_ROOT / row["path"]).read_bytes()).hexdigest(), row["sha256"])

    def test_completed_outer_acknowledgement_is_not_task_completion(self):
        row = self.by_id["retained-carol-bridge-R2"]
        self.assertEqual(row["task_completion"], "fail")
        self.assertFalse(row["metadata"]["task_predicates"]["completed_state"])
        self.assertEqual(row["capability_items"][0]["observed_usable"], None)

    def test_summary_success_is_not_used(self):
        allocation = next(row for row in self.manifest["allocations"] if row["episode_id"] == "retained-carol-bridge-R1")
        original = builder.Inputs.json

        def misleading_summary(inputs, path):
            result = original(inputs, path)
            if path == allocation["runtime"]:
                result["observation"]["goal_achieved"] = True
                result["observation"]["final_state"] = "completed"
            return result

        with patch.object(builder.Inputs, "json", misleading_summary):
            result = builder.build_bridge(builder.Inputs(INPUT_ROOT, self.manifest), allocation)
        self.assertEqual(result["task_completion"], "fail")

    def test_upfront_alternative_is_not_recovery(self):
        for episode in self.episodes:
            self.assertEqual(episode["recovery"], {"eligible": False, "status": "not_applicable"})

    def test_missing_agentops_continuation_is_unknown_payload(self):
        row = self.by_id["retained-agentops-diagnostic-B6"]
        self.assertEqual(row["metadata"]["historical_strict_case_status"], "partial")
        self.assertFalse(row["metadata"]["continuation_attempted"])
        self.assertFalse(row["metadata"]["public_confirmation_observed"])
        self.assertTrue(row["metadata"]["native_errors"])
        for item in row["context_items"]:
            self.assertFalse(item["observed"]["sent"])
            self.assertIsNone(item["present"]["sent"])

    def test_missing_and_absent_reference_are_distinct(self):
        row = self.by_id["retained-carol-bridge-R3"]
        item = next(item for item in row["context_items"] if item["id"] == "reference_task_ids")
        self.assertEqual(item["present"], {"source": None, "sent": False, "received": False})
        self.assertEqual(item["observed"], {"source": False, "sent": True, "received": True})
        self.assertIsNone(item["received"])

    def test_known_json_null_is_distinct_from_absence(self):
        observed_null = builder.context_item("null", None, None, None)
        absent = builder.context_item("absent", builder.ABSENT, builder.ABSENT, builder.ABSENT)
        self.assertTrue(observed_null["present"]["source"])
        self.assertFalse(absent["present"]["source"])

    def test_real_mcp_bytes_recomputed_not_summary(self):
        expected = {"R1": (2174, 8642), "R2": (3144, 8904), "R3": (1125, 19515), "R4": (1451, 20150)}
        for case, numbers in expected.items():
            row = self.by_id["retained-carol-bridge-" + case]
            self.assertEqual((row["costs"]["request_bytes"], row["costs"]["response_bytes"]), numbers)

    def test_unmeasured_latency_and_tokens_are_not_zero(self):
        for episode in self.episodes:
            self.assertIsNone(episode["costs"]["wall_ms"])
            self.assertIsNone(episode["costs"]["model_tokens"])
            self.assertTrue(episode["metadata"]["collection_flags"]["retained_reanalysis"])
            self.assertFalse(episode["metadata"]["collection_flags"]["fresh_experiment"])

    def test_raw_hash_corruption_rejected(self):
        value = entity({"id": "original"})
        value["sha256"] = "0" * 64
        with self.assertRaisesRegex(builder.EvidenceError, "body hash mismatch"):
            builder.blob(value)

    def test_raw_byte_count_corruption_rejected(self):
        value = entity({"id": "original"})
        value["bytes"] += 1
        with self.assertRaisesRegex(builder.EvidenceError, "body byte mismatch"):
            builder.blob(value)

    def test_parsed_body_disagreement_rejected(self):
        value = entity({"id": "original"})
        value["json"] = {"id": "different"}
        with self.assertRaisesRegex(builder.EvidenceError, "parsed JSON disagreement"):
            builder.blob(value)

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        for raw in [b'{"id":1,"id":2}', b'{"cost":NaN}']:
            with self.assertRaises(builder.EvidenceError):
                builder.strict_json(raw)

    def test_changed_task_or_context_never_passes(self):
        original = {"id": "original", "contextId": "context"}
        final = {**original, "status": {"state": "TASK_STATE_COMPLETED"}}
        for field in ("id", "contextId"):
            changed = {**final, field: "another"}
            self.assertEqual(builder.completion(original, changed)[0], "fail")

    def test_missing_final_predicates_remain_unknown(self):
        original = {"id": "original", "contextId": "context"}
        for final in [{}, {**original}, {"id": "original", "status": {"state": "TASK_STATE_COMPLETED"}}]:
            self.assertEqual(builder.completion(original, final)[0], "unknown")
        self.assertEqual(builder.completion(original, {"id": "another"})[0], "fail")

    def test_boolean_integer_raw_json_alias_rejected(self):
        value = entity({"confirmed": True})
        value["json"] = {"confirmed": 1}
        with self.assertRaisesRegex(builder.EvidenceError, "parsed JSON disagreement"):
            builder.blob(value)

    def test_rpc_boolean_integer_identity_alias_rejected(self):
        exchange = {"exchange_id": "typed-id", "request": entity({"jsonrpc": "2.0", "id": 1, "method": "GetTask"}),
                    "response": entity({"jsonrpc": "2.0", "id": True, "result": {}})}
        with self.assertRaisesRegex(builder.EvidenceError, "RPC response identity mismatch"):
            builder.validate_exchanges([exchange])

    def test_changed_capture_identity_rejected(self):
        allocation = next(row for row in self.manifest["allocations"] if row["episode_id"] == "retained-carol-bridge-R4")
        allocation = {**allocation, "run_id": "different-allocation"}
        with self.assertRaisesRegex(builder.EvidenceError, "changed bridge capture identity"):
            builder.build_bridge(builder.Inputs(INPUT_ROOT, self.manifest), allocation)

    def test_source_hash_mismatch_and_unmanifested_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "raw.json").write_bytes(b"{}")
            inputs = builder.Inputs(root, {"source_files": [{"path": "raw.json", "sha256": "0" * 64}]})
            with self.assertRaisesRegex(builder.EvidenceError, "source hash mismatch"):
                inputs.read("raw.json")
            with self.assertRaisesRegex(builder.EvidenceError, "unmanifested source"):
                inputs.read("not-pinned.json")

    def test_cross_root_source_rejected(self):
        inputs = builder.Inputs(ROOT, {"source_files": []})
        for path in ["../escape.json", "/escape.json", "runs\\escape.json"]:
            with self.assertRaisesRegex(builder.EvidenceError, "unsafe retained path"):
                inputs.read(path)

    def test_duplicate_effect_or_wrong_attribution_rejected(self):
        allocation = next(row for row in self.manifest["allocations"] if row["episode_id"] == "retained-agentops-diagnostic-N11")
        inputs = builder.Inputs(INPUT_ROOT, self.manifest)
        wire = builder.agent_wire(inputs, allocation["base"], allocation["wire_exchanges"])
        sends = [row for row in wire if (row["request_json"] or {}).get("method") == "SendMessage"]
        original = builder.task(sends[0]["response_json"]["result"])
        final = wire[-1]["response_json"]["result"]
        initial = inputs.json(allocation["initial_snapshot"])
        terminal = inputs.json(allocation["base"] + "/service/terminal.snapshot.json")
        rationale = inputs.json(allocation["base"] + "/client-config.json")["rationale"]
        self.assertTrue(builder.effect_predicate(initial, terminal, original, final, rationale))
        for mutation in ("duplicate", "wrong_session", "wrong_target"):
            changed = copy.deepcopy(terminal)
            audit = changed["database"]["tables"]["audit_log"]
            if mutation == "duplicate":
                audit.append(copy.deepcopy(audit[0]))
            elif mutation == "wrong_session":
                audit[0]["session_id"] = "another-context"
            else:
                audit[0]["target"] = "payments"
            self.assertFalse(builder.effect_predicate(initial, changed, original, final, rationale))


if __name__ == "__main__":
    unittest.main()
