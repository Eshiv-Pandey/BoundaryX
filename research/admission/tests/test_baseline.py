import copy
import json
import tempfile
import unittest
from pathlib import Path

from interoperability import baseline
from interoperability.manifest import load, validate


def tiny_model():
    return {
        "schema_version": "finite-continuation/1", "id": "unit-development",
        "route": "authored graph; no adapter observation",
        "provenance": {"kind": "authored-development", "source": "unit test",
                       "review_status": "AI-authored development; human review pending"},
        "horizon": 2, "evidence": {"complete": True, "observed_at": 10, "valid_until": 30},
        "initial": "start", "states": {
            "start": {"safe": True, "done": False},
            "end": {"safe": True, "done": True},
        },
        "transitions": [{"id": "finish", "source": "start", "target": "end", "operation": "finish"}],
        "runtime_contract": {"goal": [{"field": "done", "op": "eq", "value": True}],
                             "invariants": [{"field": "safe", "op": "eq", "value": True}]},
    }


class BaselineSemantics(unittest.TestCase):
    def test_bound_is_number_of_transitions_and_allows_empty_path(self):
        m = tiny_model()
        m["horizon"] = 0
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unsupported")
        m["states"]["start"]["done"] = True
        result = baseline.evaluate(m, 20)
        self.assertEqual(result["certificate"]["transition_ids"], [])

    def test_missing_observables_are_unknown(self):
        m = tiny_model()
        del m["states"]["end"]["done"]
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unknown")

    def test_unknown_invariant_cannot_hide_possible_goal(self):
        m = tiny_model()
        del m["states"]["start"]["safe"]
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unknown")

    def test_may_compatibility_does_not_require_every_branch_to_succeed(self):
        m = tiny_model()
        m["states"]["hazard"] = {"safe": False, "done": True}
        m["transitions"].insert(0, {"id": "hazard", "source": "start", "target": "hazard", "operation": "finish"})
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "supported")

    def test_complete_negative_and_partial_abstention(self):
        m = tiny_model()
        m["transitions"] = []
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unsupported")
        m["evidence"]["complete"] = False
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unknown")

    def test_partial_positive_is_conditional_support(self):
        m = tiny_model()
        m["evidence"]["complete"] = False
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "supported")

    def test_known_false_dominates_unknown_conjunction(self):
        m = tiny_model()
        m["states"]["end"] = {"safe": False}
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unsupported")

    def test_bool_and_integer_are_not_equal(self):
        m = tiny_model()
        m["states"]["end"]["done"] = 1
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unsupported")

    def test_cross_field_binding_is_required(self):
        m = tiny_model()
        for state in m["states"].values():
            state.update(handle="bridge:17", required_handle="native:17")
        m["runtime_contract"]["goal"].append({"field": "handle", "op": "eq_field", "other_field": "required_handle"})
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unsupported")

    def test_ordered_comparison_wrong_type_is_unknown(self):
        m = tiny_model()
        m["runtime_contract"]["goal"] = [{"field": "done", "op": "lt", "value": 2}]
        self.assertEqual(baseline.evaluate(m, 20)["decision"], "unknown")

    def test_evidence_freshness_boundaries(self):
        m = tiny_model()
        for now in (9, 31):
            self.assertEqual(baseline.evaluate(m, now)["decision"], "unknown")
        for now in (10, 30):
            self.assertEqual(baseline.evaluate(m, now)["decision"], "supported")

    def test_negative_certificate_covers_recurrent_layers(self):
        m = tiny_model()
        m["states"]["end"]["done"] = False
        m["transitions"].append({"id": "loop", "source": "end", "target": "end", "operation": "poll"})
        self.assertEqual(baseline.evaluate(m, 20)["certificate"]["layers"], [["start"], ["end"], ["end"]])


class InputValidation(unittest.TestCase):
    def test_rejects_bad_structure(self):
        changes = [
            lambda m: m.update(horizon=True),
            lambda m: m.update(horizon=65),
            lambda m: m.update(evaluation_private={"goal": "hidden"}),
            lambda m: m["evidence"].update(valid_until=0),
            lambda m: m["runtime_contract"]["goal"][0].update(op=[]),
            lambda m: m["states"]["end"].update(done=1.0),
            lambda m: m["transitions"].append(copy.deepcopy(m["transitions"][0])),
        ]
        for change in changes:
            m = tiny_model()
            change(m)
            with self.assertRaises(ValueError):
                validate(m)

    def test_json_duplicate_keys_are_not_silently_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"id": "first", "id": "second"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load(path)


if __name__ == "__main__":
    unittest.main()
