"""Hand-authored development fixtures for the independent finite oracle.

These tests are algebraic/software checks, never observed bridge experiments.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unittest

from interoperability.oracle import check_certificate, evaluate


NOW = 100


def authored_model(*, states=None, transitions=None, goal=None, invariants=None,
                   horizon=2, complete=True):
    """A labelled synthetic fixture, with no claim of external execution."""
    return {
        "schema_version": "finite-continuation/1",
        "id": "authored-oracle-test",
        "route": "synthetic development graph; no external bridge observed",
        "provenance": {
            "kind": "authored-development",
            "source": "tests/test_oracle.py hand-authored fixture",
            "review_status": "development only; no human independent validation claimed",
        },
        "horizon": horizon,
        "evidence": {"complete": complete, "observed_at": 90, "valid_until": 200},
        "initial": "start",
        "states": {"start": {"done": False, "safe": True}} if states is None else states,
        "transitions": [] if transitions is None else transitions,
        "runtime_contract": {
            "goal": [{"field": "done", "op": "eq", "value": True}] if goal is None else goal,
            "invariants": [{"field": "safe", "op": "eq", "value": True}]
            if invariants is None else invariants,
        },
    }


def edge(identifier, source, target):
    return {"id": identifier, "source": source, "target": target, "operation": "synthetic-step"}


def bound_certificate(model, decision, detail, *, now=NOW):
    """Construct even deliberately forged certificates without calling evaluate."""
    wire = json.dumps(model, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    certificate = {
        "kind": "path" if decision == "supported" else "bounded-cut",
        "model_sha256": hashlib.sha256(wire).hexdigest(),
        "checked_at": now,
        "horizon": model["horizon"],
        "valid_until": model["evidence"]["valid_until"],
        "transition_ids" if decision == "supported" else "layers": detail,
    }
    return {"decision": decision, "reason": "Hand-authored certificate test", "certificate": certificate}


class OracleDecisionTests(unittest.TestCase):
    def assert_decision(self, model, expected):
        result = evaluate(model, NOW)
        self.assertEqual(result["decision"], expected)
        if expected == "unknown":
            self.assertIsNone(result["certificate"])
            self.assertFalse(check_certificate(model, result, NOW))
        else:
            self.assertTrue(check_certificate(model, result, NOW))
        return result

    def test_initial_goal_has_zero_transition_witness(self):
        model = authored_model(states={"start": {"done": True, "safe": True}}, horizon=0)
        result = self.assert_decision(model, "supported")
        self.assertEqual(result["certificate"]["transition_ids"], [])

    def test_zero_horizon_does_not_take_edge_to_goal(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "end": {"done": True, "safe": True}},
            transitions=[edge("finish", "start", "end")], horizon=0)
        result = self.assert_decision(model, "unsupported")
        self.assertEqual(result["certificate"]["layers"], [["start"]])

    def test_horizon_counts_transitions_and_includes_boundary(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "middle": {"done": False, "safe": True},
                    "end": {"done": True, "safe": True}},
            transitions=[edge("first", "start", "middle"), edge("second", "middle", "end")])
        result = self.assert_decision(model, "supported")
        self.assertEqual(result["certificate"]["transition_ids"], ["first", "second"])
        model["horizon"] = 1
        self.assert_decision(model, "unsupported")

    def test_nondeterministic_safe_success_branch_is_may_supported(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "bad": {"done": True, "safe": False},
                    "dead": {"done": False, "safe": True}, "good": {"done": True, "safe": True}},
            transitions=[edge("unsafe", "start", "bad"), edge("refuse", "start", "dead"),
                         edge("deliver", "start", "good")])
        result = self.assert_decision(model, "supported")
        self.assertEqual(result["certificate"]["transition_ids"], ["deliver"])

    def test_definitely_unsafe_intermediate_blocks_later_goal(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "unsafe": {"done": False, "safe": False},
                    "end": {"done": True, "safe": True}},
            transitions=[edge("violate", "start", "unsafe"), edge("recover", "unsafe", "end")])
        result = self.assert_decision(model, "unsupported")
        self.assertEqual(result["certificate"]["layers"], [["start"], [], []])

    def test_initial_invariant_blocks_even_initial_goal(self):
        model = authored_model(states={"start": {"done": True, "safe": False}})
        result = self.assert_decision(model, "unsupported")
        self.assertEqual(result["certificate"]["layers"], [[], [], []])
        model["evidence"]["complete"] = False
        self.assert_decision(model, "unknown")

    def test_partial_graph_can_support_but_cannot_refute(self):
        model = authored_model(complete=False)
        self.assert_decision(model, "unknown")
        model["states"]["start"]["done"] = True
        self.assert_decision(model, "supported")

    def test_unknown_invariant_keeps_possible_successor_alive(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "maybe": {"done": False},
                    "end": {"done": True, "safe": True}},
            transitions=[edge("uncertain", "start", "maybe"), edge("next", "maybe", "end")])
        result = self.assert_decision(model, "unknown")
        self.assertEqual(result["stats"]["path_nodes"], 3)

    def test_unknown_branch_does_not_erase_definite_witness(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "maybe": {"done": True},
                    "end": {"done": True, "safe": True}},
            transitions=[edge("uncertain", "start", "maybe"), edge("certain", "start", "end")])
        result = self.assert_decision(model, "supported")
        self.assertEqual(result["certificate"]["transition_ids"], ["certain"])

    def test_goal_unknown_in_any_potentially_safe_state_prevents_refutation(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "maybe": {"safe": True}},
            transitions=[edge("missing-goal", "start", "maybe")])
        self.assert_decision(model, "unknown")

    def test_unreachable_or_out_of_horizon_unknown_does_not_prevent_refutation(self):
        model = authored_model(states={"start": {"done": False, "safe": True}, "missing": {}})
        self.assert_decision(model, "unsupported")
        model["transitions"] = [edge("beyond-bound", "start", "missing")]
        model["horizon"] = 0
        self.assert_decision(model, "unsupported")

    def test_unknown_goal_in_definitely_unsafe_state_is_irrelevant(self):
        model = authored_model(states={"start": {"safe": False}})
        self.assert_decision(model, "unsupported")

    def test_false_conjunct_dominates_unknown_invariant(self):
        model = authored_model(
            states={"start": {"done": True, "safe": False}},
            invariants=[{"field": "missing", "op": "eq", "value": True},
                        {"field": "safe", "op": "eq", "value": True}])
        self.assert_decision(model, "unsupported")

    def test_false_conjunct_dominates_unknown_goal(self):
        model = authored_model(goal=[{"field": "missing", "op": "eq", "value": True},
                                    {"field": "done", "op": "eq", "value": True}])
        self.assert_decision(model, "unsupported")

    def test_empty_contract_lists_are_true(self):
        self.assert_decision(authored_model(states={"start": {}}, goal=[], invariants=[], horizon=0),
                             "supported")

    def test_missing_observable_differs_from_explicit_null(self):
        model = authored_model(states={"start": {"x": None}}, invariants=[],
                               goal=[{"field": "x", "op": "eq", "value": None}])
        self.assert_decision(model, "supported")
        del model["states"]["start"]["x"]
        self.assert_decision(model, "unknown")

    def test_equality_ne_and_membership_are_type_sensitive(self):
        for op, operand, expected in [
            ("eq", 1, "unsupported"), ("eq", True, "supported"),
            ("ne", 1, "supported"), ("ne", True, "unsupported"),
            ("in", [1, "true", None], "unsupported"), ("in", [False, True], "supported"),
            ("in", [], "unsupported"),
        ]:
            with self.subTest(op=op, operand=operand):
                self.assert_decision(authored_model(states={"start": {"x": True}}, invariants=[],
                                     goal=[{"field": "x", "op": op, "value": operand}]), expected)

    def test_field_equality_requires_both_fields_and_same_type(self):
        model = authored_model(states={"start": {"left": None, "right": None}}, invariants=[],
                               goal=[{"field": "left", "op": "eq_field", "other_field": "right"}])
        self.assert_decision(model, "supported")
        model["states"]["start"] = {"left": True, "right": 1}
        self.assert_decision(model, "unsupported")
        del model["states"]["start"]["right"]
        self.assert_decision(model, "unknown")

    def test_ordered_comparisons_and_bad_operand_types(self):
        for op, operand, expected in [("lt", 4, "supported"), ("lt", 3, "unsupported"),
                                      ("le", 3, "supported"), ("gt", 2, "supported"),
                                      ("gt", 3, "unsupported"), ("ge", 3, "supported")]:
            with self.subTest(op=op, operand=operand):
                self.assert_decision(authored_model(states={"start": {"x": 3}}, invariants=[],
                                     goal=[{"field": "x", "op": op, "value": operand}]), expected)
        for left, right in [(True, 1), (3, True), ("3", 3), (3, "3"), (None, 3), (3, None)]:
            with self.subTest(left=left, right=right):
                self.assert_decision(authored_model(states={"start": {"x": left}}, invariants=[],
                                     goal=[{"field": "x", "op": "ge", "value": right}]), "unknown")

    def test_freshness_is_inclusive_and_stale_or_future_abstains(self):
        model = authored_model(states={"start": {"done": True, "safe": True}})
        for now in (90, 200):
            result = evaluate(model, now)
            self.assertEqual(result["decision"], "supported")
            self.assertTrue(check_certificate(model, result, now))
        for now in (89, 201):
            result = evaluate(model, now)
            self.assertEqual(result["decision"], "unknown")
            self.assertIsNone(result["certificate"])

    def test_recurrence_is_preserved_across_negative_layers(self):
        model = authored_model(transitions=[edge("loop", "start", "start")], horizon=4)
        result = self.assert_decision(model, "unsupported")
        self.assertEqual(result["certificate"]["layers"], [["start"]] * 5)

    def test_duplicate_successors_deduplicated_only_within_a_layer(self):
        model = authored_model(
            states={"start": {"done": False, "safe": True}, "other": {"done": False, "safe": True}},
            transitions=[edge("b", "start", "other"), edge("a", "start", "other"),
                         edge("loop", "other", "other")])
        result = self.assert_decision(model, "unsupported")
        self.assertEqual(result["certificate"]["layers"], [["start"], ["other"], ["other"]])

    def test_maximum_horizon_chain(self):
        states = {"start": {"done": False, "safe": True}}
        transitions = []
        previous = "start"
        for step in range(1, 65):
            state = f"step-{step}"
            states[state] = {"done": step == 64, "safe": True}
            transitions.append(edge(f"edge-{step}", previous, state))
            previous = state
        result = self.assert_decision(authored_model(states=states, transitions=transitions, horizon=64),
                                      "supported")
        self.assertEqual(len(result["certificate"]["transition_ids"]), 64)


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.positive = authored_model(
            states={"start": {"done": False, "safe": True}, "end": {"done": True, "safe": True}},
            transitions=[edge("finish", "start", "end")])
        self.negative = authored_model(
            states={"start": {"done": False, "safe": True}, "a": {"done": False, "safe": True},
                    "b": {"done": False, "safe": True}},
            transitions=[edge("to-a", "start", "a"), edge("to-b", "start", "b"),
                         edge("back", "a", "start")])

    def test_independently_constructed_positive_and_negative_certificates(self):
        self.assertTrue(check_certificate(self.positive, bound_certificate(self.positive, "supported", ["finish"]), NOW))
        self.assertTrue(check_certificate(self.negative,
                        bound_certificate(self.negative, "unsupported", [["start"], ["a", "b"], ["start"]]), NOW))

    def test_replay_rejects_wrong_id_wrong_endpoint_and_non_goal(self):
        model = copy.deepcopy(self.positive)
        model["transitions"].append(edge("return", "end", "start"))
        for path in [["absent"], ["return"], [], ["finish", "return"]]:
            with self.subTest(path=path):
                self.assertFalse(check_certificate(model, bound_certificate(model, "supported", path), NOW))

    def test_positive_certificate_cannot_exceed_horizon(self):
        model = copy.deepcopy(self.positive)
        model["horizon"] = 0
        self.assertFalse(check_certificate(model, bound_certificate(model, "supported", ["finish"]), NOW))

    def test_positive_certificate_rejects_unsafe_and_unknown_initial_or_successor(self):
        for state, safe in [("start", False), ("end", False), ("start", None), ("end", None)]:
            with self.subTest(state=state, safe=safe):
                model = copy.deepcopy(self.positive)
                if safe is None:
                    del model["states"][state]["safe"]
                else:
                    model["states"][state]["safe"] = safe
                self.assertFalse(check_certificate(model, bound_certificate(model, "supported", ["finish"]), NOW))

    def test_positive_certificate_rejects_unknown_final_goal(self):
        del self.positive["states"]["end"]["done"]
        self.assertFalse(check_certificate(self.positive, bound_certificate(self.positive, "supported", ["finish"]), NOW))

    def test_negative_certificate_rejects_hidden_branches_wrong_initial_and_recurrence(self):
        for layers in [
            [[], ["a", "b"], ["start"]],
            [["start"], ["a"], ["start"]],
            [["start"], ["a", "b"], []],
            [["start"], ["a", "b"], ["a"]],
        ]:
            with self.subTest(layers=layers):
                self.assertFalse(check_certificate(self.negative,
                                 bound_certificate(self.negative, "unsupported", layers), NOW))

    def test_negative_certificate_rejects_unknown_goal_or_invariant_and_incomplete_evidence(self):
        layers = [["start"], ["a", "b"], ["start"]]
        for missing in ("done", "safe"):
            model = copy.deepcopy(self.negative)
            del model["states"]["b"][missing]
            self.assertFalse(check_certificate(model, bound_certificate(model, "unsupported", layers), NOW))
        self.negative["evidence"]["complete"] = False
        self.assertFalse(check_certificate(self.negative,
                         bound_certificate(self.negative, "unsupported", layers), NOW))

    def test_negative_certificate_cannot_hide_reachable_goal(self):
        self.negative["states"]["b"]["done"] = True
        for layers in [[["start"], ["a"], ["start"]], [["start"], ["a", "b"], ["start"]]]:
            self.assertFalse(check_certificate(self.negative,
                             bound_certificate(self.negative, "unsupported", layers), NOW))

    def test_negative_certificate_rejects_noncanonical_or_malformed_layers(self):
        for layers in [
            [["start"], ["b", "a"], ["start"]],
            [["start"], ["a", "a", "b"], ["start"]],
            [["start"], ["a", "ghost"], ["start"]],
            [["start"], ["a", True], ["start"]],
            [["start"], ["a", "b"]],
            [["start"], {"a", "b"}, ["start"]],
            "not-layers",
        ]:
            with self.subTest(layers=layers):
                self.assertFalse(check_certificate(self.negative,
                                 bound_certificate(self.negative, "unsupported", layers), NOW))

    def test_model_digest_binds_contract_evidence_route_and_all_observables(self):
        result = bound_certificate(self.positive, "supported", ["finish"])
        mutations = [
            lambda m: m.update(route="changed synthetic route"),
            lambda m: m["runtime_contract"].update(goal=[]),
            lambda m: m["evidence"].update(complete=False),
            lambda m: m["states"]["end"].update(extra="unreferenced but still bound"),
            lambda m: m["provenance"].update(source="different fixture source"),
        ]
        for mutate in mutations:
            model = copy.deepcopy(self.positive)
            mutate(model)
            self.assertFalse(check_certificate(model, result, NOW))

    def test_digest_uses_utf8_sorted_compact_json_and_is_key_order_independent(self):
        self.positive["route"] = "authored development café → synthetic bridge"
        result = bound_certificate(self.positive, "supported", ["finish"])
        reordered = dict(reversed(list(self.positive.items())))
        self.assertTrue(check_certificate(reordered, result, NOW))

    def test_issued_certificate_can_be_replayed_later_inside_validity_window(self):
        result = bound_certificate(self.positive, "supported", ["finish"])
        for now in (NOW, 150, 200):
            self.assertTrue(check_certificate(self.positive, result, now))
        for now in (89, 99, 201):
            self.assertFalse(check_certificate(self.positive, result, now))

    def test_certificate_time_must_be_inside_evidence_window_and_not_future(self):
        for issued in (89, 101, 201, True, "100"):
            result = bound_certificate(self.positive, "supported", ["finish"])
            result["certificate"]["checked_at"] = issued
            self.assertFalse(check_certificate(self.positive, result, NOW))

    def test_changed_horizon_validity_digest_or_kind_is_rejected(self):
        for field, value in [("horizon", 3), ("horizon", True), ("valid_until", 201),
                             ("valid_until", "200"), ("model_sha256", "0" * 64),
                             ("kind", "bounded-cut")]:
            result = bound_certificate(self.positive, "supported", ["finish"])
            result["certificate"][field] = value
            self.assertFalse(check_certificate(self.positive, result, NOW))

    def test_wrong_decision_unknown_and_extra_fields_have_no_valid_certificate(self):
        for decision in ("unsupported", "unknown", "completed", True, ["supported"]):
            result = bound_certificate(self.positive, "supported", ["finish"])
            result["decision"] = decision
            self.assertFalse(check_certificate(self.positive, result, NOW))
        result = bound_certificate(self.positive, "supported", ["finish"])
        result["certificate"]["private_gold"] = True
        self.assertFalse(check_certificate(self.positive, result, NOW))
        result = bound_certificate(self.positive, "supported", ["finish"])
        result["private_gold"] = True
        self.assertFalse(check_certificate(self.positive, result, NOW))
        self.assertFalse(check_certificate(self.positive,
                         {"decision": "unknown", "reason": "abstention", "certificate": None}, NOW))


class MalformedInputTests(unittest.TestCase):
    def assert_invalid(self, model, now=NOW):
        with self.assertRaises(ValueError):
            evaluate(model, now)
        self.assertFalse(check_certificate(model,
                         {"decision": "supported", "reason": "synthetic", "certificate": None}, now))

    def test_top_level_missing_unknown_and_private_gold_are_input_errors(self):
        for field in authored_model():
            model = authored_model()
            del model[field]
            self.assert_invalid(model)
        for field in ("unknown", "private_gold", "expected_decision"):
            model = authored_model()
            model[field] = "supported"
            self.assert_invalid(model)

    def test_nested_unknown_fields_are_input_errors(self):
        for location in ("provenance", "evidence", "runtime_contract"):
            model = authored_model()
            model[location]["hidden"] = True
            self.assert_invalid(model)
        model = authored_model(transitions=[edge("loop", "start", "start")])
        model["transitions"][0]["guard"] = "hidden"
        self.assert_invalid(model)
        model = authored_model()
        model["runtime_contract"]["goal"][0]["hidden"] = True
        self.assert_invalid(model)

    def test_invalid_scalar_objects_and_float_are_input_errors(self):
        for value in (1.0, [], {}, {1}, float("nan")):
            model = authored_model()
            model["states"]["start"]["done"] = value
            self.assert_invalid(model)
            model = authored_model()
            model["runtime_contract"]["goal"][0]["value"] = value
            self.assert_invalid(model)

    def test_malformed_clock_horizon_and_evidence(self):
        for now in (True, 100.0, "100", None):
            self.assert_invalid(authored_model(), now)
        for horizon in (-1, 65, True, 2.0, "2"):
            self.assert_invalid(authored_model(horizon=horizon))
        for field, value in [("complete", 1), ("complete", "yes"), ("observed_at", True),
                             ("valid_until", 200.0), ("observed_at", 201)]:
            model = authored_model()
            model["evidence"][field] = value
            self.assert_invalid(model)

    def test_invalid_identity_provenance_initial_and_states(self):
        for field, value in [("id", ""), ("route", ""), ("initial", "absent"),
                             ("schema_version", "finite-continuation/2"), ("states", {}),
                             ("states", {"start": []}), ("states", {"": {}}),
                             ("states", {"start": {"": True}})]:
            model = authored_model()
            model[field] = value
            self.assert_invalid(model)
        for field, value in [("kind", "observed"), ("kind", []), ("source", ""), ("review_status", True)]:
            model = authored_model()
            model["provenance"][field] = value
            self.assert_invalid(model)

    def test_malformed_transitions(self):
        for transitions in ({}, [None], [edge("", "start", "start")],
                            [edge("x", "absent", "start")], [edge("x", "start", "absent")],
                            [edge("x", "start", "start"), edge("x", "start", "start")]):
            self.assert_invalid(authored_model(transitions=transitions))
        model = authored_model(transitions=[edge("x", "start", "start")])
        model["transitions"][0]["operation"] = ""
        self.assert_invalid(model)

    def test_malformed_predicates_raise_valueerror_instead_of_incidental_typeerror(self):
        for predicate in (None, {}, {"field": "done", "op": [], "value": True},
                          {"field": "done", "op": {}, "value": True},
                          {"field": "done", "op": "unknown", "value": True},
                          {"field": "done", "op": "eq"},
                          {"field": "done", "op": "eq_field", "value": True},
                          {"field": "done", "op": "eq_field", "other_field": "safe", "value": True},
                          {"field": "done", "op": "in", "value": True},
                          {"field": "done", "op": "in", "value": [[True]]},
                          {"field": "", "op": "eq", "value": True}):
            self.assert_invalid(authored_model(goal=[predicate]))
        for goal in (None, {}, True):
            model = authored_model()
            model["runtime_contract"]["goal"] = goal
            self.assert_invalid(model)

    def test_checker_returns_false_for_malformed_result_shapes(self):
        model = authored_model()
        for result in (None, [], {}, {"decision": "supported"},
                       {"decision": "supported", "reason": "test", "certificate": []},
                       {"decision": "supported", "reason": None, "certificate": {}},
                       {"decision": "supported", "reason": "test", "certificate": {}, "stats": []}):
            self.assertFalse(check_certificate(model, result, NOW))


if __name__ == "__main__":
    unittest.main()
