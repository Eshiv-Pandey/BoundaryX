"""Adversarial tests for the new development-only operational measurements."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from interoperability.loss_benchmark_v1 import (
    EPISODE_SCHEMA_VERSION,
    EpisodeValidationError,
    load_episodes,
    main,
    score_episode,
    summarize_episodes,
    validate_episode,
)


def fact(identifier: str = "fact-1", value: object = "answer") -> dict:
    return {
        "id": identifier, "source": value, "sent": value, "received": value,
        "observed": {stage: True for stage in ("source", "sent", "received")},
        "present": {stage: True for stage in ("source", "sent", "received")},
    }


def episode(identifier: str = "episode-1", kind: str = "fresh_constructed") -> dict:
    return {
        "schema_version": EPISODE_SCHEMA_VERSION, "episode_id": identifier,
        "family_id": "family-1", "route_id": "route-1", "evidence_kind": kind,
        "task_completion": "pass", "context_items": [fact()],
        "capability_items": [{"id": "read", "required": True,
                              "reference_usable": True, "observed_usable": True,
                              "advertised": True}],
        "fidelity_checks": [{"id": "constraint", "status": "pass"}],
        "recovery": {"eligible": False, "status": "not_applicable"},
        "costs": {"wall_ms": 1.5, "messages": 1, "tool_calls": 1,
                  "request_bytes": 12, "response_bytes": 9, "model_tokens": 0},
        "source_files": [] if kind == "fresh_constructed" else
                        [{"path": "retained/trace.json", "sha256": "a" * 64}],
        "notes": ["Fixture is a constructed measurement test, not runtime qualification."],
    }


class LossBenchmarkTests(unittest.TestCase):
    def test_all_attempt_tcr_keeps_unknown_outcomes(self) -> None:
        records = [episode(str(index)) for index in range(4)]
        for record, status in zip(records, ("pass", "fail", "unknown", "unknown")):
            record["task_completion"] = status
        task = summarize_episodes(records)["scores"]["task_completion"]
        self.assertEqual((task["numerator"], task["denominator"], task["unknown"]),
                         (1, 4, 2))
        self.assertEqual(task["rate"], 0.25)
        self.assertEqual(task["observed_rate"], 0.5)
        self.assertEqual(task["coverage"], 0.5)

    def test_protocol_and_capability_delivery_do_not_infer_task_success(self) -> None:
        record = episode()
        record["task_completion"] = "unknown"
        scores = score_episode(record)["scores"]
        self.assertEqual(scores["task_completion"]["rate"], 0)
        self.assertEqual(scores["context_retention"]["end_to_end"]["rate"], 1)
        self.assertEqual(scores["capability_usability"]["required_usability"]["rate"], 1)

    def test_extraction_omission_is_not_reclassified_as_conversion_loss(self) -> None:
        record = episode()
        item = record["context_items"][0]
        for stage in ("sent", "received"):
            item[stage] = None
            item["present"][stage] = False
        context = score_episode(record)["scores"]["context_retention"]
        self.assertEqual(context["extraction"]["loss_rate"], 1)
        self.assertEqual(context["end_to_end"]["loss_rate"], 1)
        self.assertEqual(context["conversion"]["not_applicable"], 1)
        self.assertIsNone(context["conversion"]["loss_rate"])

    def test_receiver_known_absence_differs_from_unknown_capture(self) -> None:
        record = episode()
        record["context_items"] = [fact("missing"), fact("uncaptured"), fact("kept")]
        missing, uncaptured, _ = record["context_items"]
        missing["received"] = None
        missing["present"]["received"] = False
        uncaptured["received"] = None
        uncaptured["present"]["received"] = None
        uncaptured["observed"]["received"] = False
        conversion = score_episode(record)["scores"]["context_retention"]["conversion"]
        self.assertEqual((conversion["numerator"], conversion["denominator"],
                          conversion["failures"], conversion["unknown"]), (1, 2, 1, 1))
        self.assertEqual(conversion["rate"], 0.5)
        self.assertAlmostEqual(conversion["coverage"], 2 / 3)

    def test_unknown_source_does_not_claim_no_extraction_loss(self) -> None:
        record = episode()
        item = record["context_items"][0]
        item["source"] = None
        item["present"]["source"] = None
        item["observed"]["source"] = False
        context = score_episode(record)["scores"]["context_retention"]
        self.assertEqual(context["extraction"]["state"], "unknown")
        self.assertEqual(context["extraction"]["eligibility_unknown"], 1)
        self.assertIsNone(context["extraction"]["rate"])
        self.assertEqual(context["conversion"]["rate"], 1)

    def test_json_null_is_a_real_present_value(self) -> None:
        record = episode()
        record["context_items"] = [fact(value=None)]
        self.assertEqual(score_episode(record)["scores"]["context_retention"]
                         ["end_to_end"]["rate"], 1)
        record["context_items"][0]["present"]["received"] = False
        self.assertEqual(score_episode(record)["scores"]["context_retention"]
                         ["end_to_end"]["loss_rate"], 1)

    def test_exact_retention_can_fail_while_task_succeeds(self) -> None:
        record = episode()
        record["context_items"] = [fact(value=[1, 2])]
        record["context_items"][0]["received"] = [2, 1]
        scores = score_episode(record)["scores"]
        self.assertEqual(scores["context_retention"]["conversion"]["loss_rate"], 1)
        self.assertEqual(scores["task_completion"]["rate"], 1)

    def test_type_sensitive_equality_rejects_bool_integer_alias(self) -> None:
        record = episode()
        record["context_items"] = [fact(value={"nested": [True]})]
        record["context_items"][0]["received"] = {"nested": [1]}
        self.assertEqual(score_episode(record)["scores"]["context_retention"]
                         ["conversion"]["loss_rate"], 1)

    def test_dict_order_is_not_a_fact_loss(self) -> None:
        record = episode()
        record["context_items"] = [fact(value={"a": 1, "b": 2})]
        record["context_items"][0]["received"] = {"b": 2, "a": 1}
        self.assertEqual(score_episode(record)["scores"]["context_retention"]
                         ["conversion"]["rate"], 1)

    def test_advertisement_and_reference_infeasibility_are_separate(self) -> None:
        record = episode()
        item = record["capability_items"][0]
        item["reference_usable"] = False
        item["observed_usable"] = None
        capability = score_episode(record)["scores"]["capability_usability"]
        self.assertEqual(capability["advertised_only"]["rate"], 1)
        self.assertIsNone(capability["required_usability"]["rate"])
        self.assertEqual(capability["required_usability"]["unknown"], 1)
        self.assertEqual(capability["reference_qualified_retention"]["not_applicable"], 1)

    def test_reference_unknown_is_not_qualified_capability_loss(self) -> None:
        record = episode()
        record["capability_items"][0]["reference_usable"] = None
        record["capability_items"][0]["observed_usable"] = False
        capability = score_episode(record)["scores"]["capability_usability"]
        self.assertEqual(capability["required_usability"]["failures"], 1)
        self.assertEqual(capability["reference_qualified_retention"]
                         ["eligibility_unknown"], 1)

    def test_recovery_counts_unknown_eligible_attempts_and_na_separately(self) -> None:
        records = [episode(str(index)) for index in range(4)]
        for record, status in zip(records, ("pass", "fail", "unknown")):
            record["recovery"] = {"eligible": True, "status": status}
        recovery = summarize_episodes(records)["scores"]["recovery_success"]
        self.assertEqual((recovery["eligible"], recovery["unknown"],
                          recovery["not_applicable"]), (3, 1, 1))
        self.assertEqual(recovery["rate"], 0.5)
        self.assertAlmostEqual(recovery["all_eligible_success_fraction"], 1 / 3)

    def test_unknown_cost_is_not_zero_and_individual_units_stay_separate(self) -> None:
        records = [episode("a"), episode("b")]
        records[1]["costs"]["wall_ms"] = None
        records[1]["costs"]["model_tokens"] = None
        overhead = summarize_episodes(records)["scores"]["overhead"]
        self.assertEqual(overhead["wall_ms"]["mean"], 1.5)
        self.assertEqual(overhead["wall_ms"]["coverage"], 0.5)
        self.assertEqual(overhead["model_tokens"]["total"], 0)
        self.assertEqual(overhead["model_tokens"]["unknown"], 1)
        self.assertEqual(overhead["request_bytes"]["total"], 24)
        self.assertNotIn("loss_rate", overhead)

    def test_fidelity_unknowns_have_coverage(self) -> None:
        record = episode()
        record["fidelity_checks"].append({"id": "tool_effect", "status": "unknown"})
        fidelity = score_episode(record)["scores"]["constraint_tool_fidelity"]
        self.assertEqual(fidelity["rate"], 1)
        self.assertEqual(fidelity["coverage"], 0.5)
        self.assertEqual(fidelity["all_eligible_success_fraction"], 0.5)

    def test_empty_metrics_are_na_not_perfect_and_empty_collection_has_no_scores(self) -> None:
        record = episode()
        record["context_items"] = []
        record["capability_items"] = []
        record["fidelity_checks"] = []
        scores = score_episode(record)["scores"]
        self.assertEqual(scores["context_retention"]["end_to_end"]["state"],
                         "not_applicable")
        self.assertIsNone(scores["constraint_tool_fidelity"]["rate"])
        self.assertIsNone(summarize_episodes([])["scores"])

    def test_mixed_evidence_never_pools_scores(self) -> None:
        records = [episode("constructed"), episode("bridge", "retained_bridge"),
                   episode("native", "retained_native")]
        records[1]["task_completion"] = "fail"
        summary = summarize_episodes(records)
        self.assertTrue(summary["heterogeneous_evidence"])
        self.assertIsNone(summary["scores"])
        self.assertEqual(len(summary["evidence_groups"]), 3)
        by_kind = {group["evidence_kind"]: group for group in summary["evidence_groups"]}
        self.assertEqual(by_kind["fresh_constructed"]["scores"]["task_completion"]["rate"], 1)
        self.assertEqual(by_kind["retained_bridge"]["scores"]["task_completion"]["rate"], 0)

    def test_duplicate_episodes_rejected_across_evidence_kinds(self) -> None:
        with self.assertRaisesRegex(EpisodeValidationError, "duplicate episode_id"):
            summarize_episodes([episode(), episode(kind="retained_native")])

    def test_unrelated_retained_families_have_counts_but_no_pooled_scores(self) -> None:
        records = [episode("a", "retained_native"), episode("b", "retained_native")]
        records[1]["family_id"] = "unrelated-family"
        records[1]["task_completion"] = "unknown"
        summary = summarize_episodes(records)
        self.assertIsNone(summary["scores"])
        self.assertIsNone(summary["evidence_groups"][0]["scores"])
        self.assertEqual(summary["task_outcome_counts"], {"pass": 1, "fail": 0, "unknown": 1})
        self.assertEqual(len(summary["route_groups"]), 2)
        self.assertEqual(summary["route_groups"][0]["scores"]["task_completion"]["rate"], 1)

    def test_missing_null_unknown_and_observation_coherence_are_strict(self) -> None:
        mutations = [
            lambda e: e.pop("task_completion"),
            lambda e: e.update(task_completion=None),
            lambda e: e["costs"].pop("model_tokens"),
            lambda e: e["context_items"][0].pop("present"),
            lambda e: e["context_items"][0]["present"].update(received=None),
            lambda e: e["context_items"][0]["observed"].update(received=False),
            lambda e: e["context_items"][0]["present"].update(received=False),
            lambda e: e.update(task_completin="pass"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                record = episode()
                mutation(record)
                with self.assertRaises(EpisodeValidationError):
                    validate_episode(record)

    def test_bad_counts_nonfinite_json_and_wrong_booleans_rejected(self) -> None:
        mutations = [
            lambda e: e["costs"].update(messages=True),
            lambda e: e["costs"].update(messages=1.5),
            lambda e: e["costs"].update(tool_calls=-1),
            lambda e: e["costs"].update(wall_ms=float("inf")),
            lambda e: e["costs"].update(wall_ms=float("nan")),
            lambda e: e["context_items"][0].update(received=float("nan")),
            lambda e: e["capability_items"][0].update(required=1),
            lambda e: e["recovery"].update(eligible=False, status="pass"),
            lambda e: e.update(metadata={"value": object()}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                record = episode()
                mutation(record)
                with self.assertRaises(EpisodeValidationError):
                    validate_episode(record)

    def test_duplicate_items_and_retained_provenance_are_checked(self) -> None:
        for name in ("context_items", "capability_items", "fidelity_checks"):
            record = episode()
            record[name].append(copy.deepcopy(record[name][0]))
            with self.assertRaisesRegex(EpisodeValidationError, "duplicate id"):
                validate_episode(record)
        record = episode(kind="retained_bridge")
        record["source_files"] = []
        with self.assertRaisesRegex(EpisodeValidationError, "hashed source"):
            validate_episode(record)
        record["source_files"] = [{"path": "trace", "sha256": "invalid"}]
        with self.assertRaisesRegex(EpisodeValidationError, "SHA-256"):
            validate_episode(record)

    def test_jsonl_and_cli_roundtrip_and_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "episodes.jsonl"
            target = Path(directory) / "summary.json"
            source.write_text("\n".join(json.dumps(episode(str(i))) for i in range(2)),
                              encoding="utf-8")
            self.assertEqual(len(load_episodes(source)), 2)
            self.assertEqual(main(["--input", str(source), "--output", str(target)]), 0)
            self.assertEqual(json.loads(target.read_text())["episode_count"], 2)
            saved = target.read_bytes()
            with self.assertRaises(SystemExit) as rejected:
                main(["--input", str(source), "--output", str(target)])
            self.assertEqual(rejected.exception.code, 2)
            self.assertEqual(target.read_bytes(), saved)
            source.write_text('{"episode_id":"a","episode_id":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(EpisodeValidationError, "duplicate object key"):
                load_episodes(source)


if __name__ == "__main__":
    unittest.main()
