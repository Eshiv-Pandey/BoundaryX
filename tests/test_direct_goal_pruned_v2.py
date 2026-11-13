"""Focused authored comparator tests; no scaling matrix or application launch."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from interoperability import direct_goal_pruned_v2 as direct
from interoperability import refinement_oracle as original


def relation(*, arguments=None, emit=None, guards=None, updates=None):
    return {'source_ref': 'Focused authored finite test; no source-fidelity claim',
            'arguments': arguments or {}, 'emit': emit or {'object': {}},
            'guards': guards or [], 'updates': updates or {}}


def profile(edges, *, horizon=2, goals=('goal',), relations=None):
    names = {'start'} | {name for _, source, target in edges for name in (source, target)}
    return {'schema_version': 'recipe-continuation/1', 'id': 'focused-goal-pruning',
            'model': {'schema_version': 'finite-continuation/1', 'id': 'focused-graph',
                      'route': 'Authored finite test',
                      'provenance': {'kind': 'authored-development', 'source': 'tests/test_direct_goal_pruned_v2.py',
                                     'review_status': 'Authored software test; no domain qualification'},
                      'horizon': horizon, 'evidence': {'complete': True, 'observed_at': 0, 'valid_until': 1000},
                      'initial': 'start', 'states': {name: {'safe': True, 'done': name in goals} for name in sorted(names)},
                      'transitions': [{'id': edge, 'source': source, 'target': target, 'operation': 'declared_recipe'}
                                      for edge, source, target in edges],
                      'runtime_contract': {'goal': [{'field': 'done', 'op': 'eq', 'value': True}],
                                           'invariants': [{'field': 'safe', 'op': 'eq', 'value': True}]}},
            'initial_bindings': {}, 'relations': relations or {edge: relation() for edge, _, _ in edges},
            'coverage': {'complete': True, 'scope': 'Only this finite authored profile'}}


def off_goal(*, succeeds=True, opaque=False):
    edges = [(f'e{index:04d}', 'start', f'dead{index}') for index in range(4)]
    edges.append(('e0004', 'start', 'goal'))
    arguments = {name: [{'literal': value} for value in range(4)] for name in ('a', 'b')}
    emit = {'unknown': 'opaque'} if opaque else {'object': {'a': {'arg': 'a'}, 'b': {'arg': 'b'}}}
    relations = {edge: relation(arguments=deepcopy(arguments), emit=deepcopy(emit)) for edge, _, _ in edges[:-1]}
    relations['e0004'] = relation(guards=[] if succeeds else [
        {'op': 'eq', 'left': {'const': 0}, 'right': {'const': 1}}])
    return profile(edges, horizon=1, relations=relations)


class GoalPrunedDirectTests(unittest.TestCase):
    def checked(self, value, expected, *, budget=100000):
        before = deepcopy(value)
        answer = direct.evaluate(value, now=100, budget=budget)
        self.assertEqual(answer['decision'], expected, answer)
        if expected == 'unknown':
            self.assertIsNone(answer['certificate'])
        else:
            self.assertTrue(direct.check_certificate(value, answer, 100), answer)
        self.assertEqual(value, before)
        return answer

    def test_dead_relations_do_not_consume_the_witness_budget(self):
        value = off_goal()
        old = original.evaluate(value, 100, 32)
        self.assertEqual(old['decision'], 'unknown')
        self.assertEqual(old['reason'], 'work_budget_exhausted')
        answer = self.checked(value, 'supported', budget=32)
        self.assertEqual(answer['stats']['argument_assignments'], 1)
        self.assertEqual(answer['stats']['expression_evaluations'], 1)
        self.assertEqual(answer['stats']['goal_pruned_edges'], 4)
        self.assertEqual(answer['stats']['work_units'], 32)
        self.assertTrue(original.check_certificate(value, answer, 100))

    def test_first_feasible_goal_tuple_short_circuits_large_domain(self):
        args = {name: [{'literal': i} for i in range(16)] for name in ('a', 'b')}
        value = profile([('finish', 'start', 'goal')], horizon=1,
                        relations={'finish': relation(arguments=args, emit={'object': {'a': {'arg': 'a'}}})})
        for solver in (original, direct):
            answer = solver.evaluate(value, 100, 32)
            self.assertEqual(answer['decision'], 'supported', answer)
            self.assertEqual(answer['stats']['argument_assignments'], 1)
            self.assertTrue(original.check_certificate(value, answer, 100))

    def test_negative_layers_have_an_explicit_new_checked_kind(self):
        value = off_goal(succeeds=False)
        answer = self.checked(value, 'unsupported')
        old = original.evaluate(value, 100, 100000)
        self.assertEqual(old['decision'], 'unsupported')
        self.assertEqual(answer['certificate']['kind'], direct.NEGATIVE_KIND)
        self.assertNotEqual(answer['certificate']['product_layers'], old['certificate']['product_layers'])
        self.assertFalse(original.check_certificate(value, answer, 100))
        self.assertTrue(direct.check_certificate(value, old, 100))
        renamed = deepcopy(answer)
        renamed['certificate']['kind'] = 'relational-exhaustion'
        self.assertFalse(original.check_certificate(value, renamed, 100))
        self.assertFalse(direct.check_certificate(value, renamed, 100))

    def test_new_negative_checker_does_not_call_either_solver(self):
        value = off_goal(succeeds=False)
        answer = self.checked(value, 'unsupported')
        with patch.object(direct, 'evaluate', side_effect=AssertionError('solver called')), \
                patch.object(original, 'evaluate', side_effect=AssertionError('old solver called')):
            self.assertTrue(direct.check_certificate(value, answer, 100))

    def test_off_goal_relation_uncertainty_is_irrelevant(self):
        value = off_goal(succeeds=False, opaque=True)
        self.assertEqual(original.evaluate(value, 100)['decision'], 'unsupported')
        self.checked(value, 'unsupported')

    def test_uncertainty_on_viable_relation_is_preserved(self):
        value = profile([('finish', 'start', 'goal')], horizon=1,
                        relations={'finish': relation(emit={'unknown': 'opaque'})})
        answer = self.checked(value, 'unknown')
        self.assertEqual(answer['reason'], 'indeterminate_observables_or_relations')
        self.assertEqual(original.evaluate(value, 100)['decision'], 'unknown')

    def test_contracted_uncertainty_on_reachable_dead_branch_is_preserved(self):
        for field in ('safe', 'done'):
            value = off_goal(succeeds=False)
            del value['model']['states']['dead0'][field]
            with self.subTest(field=field):
                self.assertEqual(original.evaluate(value, 100)['decision'], 'unknown')
                self.checked(value, 'unknown')

    def test_possible_unknown_goal_is_not_pruned_as_definitely_dead(self):
        value = profile([('finish', 'start', 'goal')], horizon=1)
        del value['model']['states']['goal']['done']
        answer = self.checked(value, 'unknown')
        self.assertEqual(answer['stats']['goal_pruned_edges'], 0)

    def test_horizon_blocks_an_otherwise_reachable_goal(self):
        value = profile([('first', 'start', 'middle'), ('finish', 'middle', 'goal')], horizon=1)
        answer = self.checked(value, 'unsupported')
        self.assertEqual(answer['stats']['argument_assignments'], 0)
        self.assertEqual(original.evaluate(value, 100)['decision'], 'unsupported')
        value['model']['horizon'] = 2
        self.checked(value, 'supported')

    def test_relation_cache_and_correlated_frames_are_retained(self):
        value = profile([('a_loop', 'start', 'start'), ('b_finish', 'start', 'goal')], horizon=3,
                        relations={'a_loop': relation(), 'b_finish': relation(guards=[
                            {'op': 'eq', 'left': {'const': 0}, 'right': {'const': 1}}])})
        answer = self.checked(value, 'unsupported')
        self.assertGreater(answer['stats']['cached_relation_outcomes'], 0)

    def test_freshness_coverage_and_budget_failure_remain_unknown(self):
        value = off_goal(succeeds=False)
        stale = direct.evaluate(value, 1001)
        self.assertEqual((stale['decision'], stale['reason']), ('unknown', 'evidence_not_fresh'))
        for field in ('evidence', 'coverage'):
            changed = deepcopy(value)
            (changed['model']['evidence'] if field == 'evidence' else changed['coverage'])['complete'] = False
            answer = self.checked(changed, 'unknown')
            self.assertEqual(answer['reason'], 'incomplete_model_or_relation_coverage')
        answer = self.checked(value, 'unknown', budget=1)
        self.assertEqual(answer['stats']['work_units'], 1)
        self.assertEqual(answer['reason'], 'work_budget_exhausted')

    def test_negative_checker_rejects_missing_extra_and_duplicate_frames(self):
        value = profile([('a', 'start', 'middle'), ('b', 'middle', 'goal')], horizon=2,
                        relations={'a': relation(), 'b': relation(guards=[
                            {'op': 'eq', 'left': {'const': 0}, 'right': {'const': 1}}])})
        answer = self.checked(value, 'unsupported')
        for mutate in (lambda layers: layers.__setitem__(1, []),
                       lambda layers: layers[1].append(deepcopy(layers[1][0])),
                       lambda layers: layers[1][0]['bindings'].update(forged=1),
                       lambda layers: layers.pop()):
            forged = deepcopy(answer)
            mutate(forged['certificate']['product_layers'])
            self.assertFalse(direct.check_certificate(value, forged, 100))

    def test_rebound_certificate_cannot_hide_newly_feasible_goal(self):
        value = off_goal(succeeds=False)
        answer = self.checked(value, 'unsupported')
        value['relations']['e0004']['guards'] = []
        answer['certificate']['profile_sha256'] = original.finite_oracle._digest(value)
        self.assertFalse(direct.check_certificate(value, answer, 100))

    def test_negative_checker_rejects_changed_clock_or_uncertain_cut(self):
        value = off_goal(succeeds=False)
        answer = self.checked(value, 'unsupported')
        self.assertFalse(direct.check_certificate(value, answer, 1001))
        forged = deepcopy(answer)
        forged['certificate']['horizon'] += 1
        self.assertFalse(direct.check_certificate(value, forged, 100))
        value['relations']['e0004'] = relation(emit={'unknown': 'opaque'})
        answer['certificate']['profile_sha256'] = original.finite_oracle._digest(value)
        self.assertFalse(direct.check_certificate(value, answer, 100))

    def test_small_existing_profiles_agree_with_original_semantics(self):
        # The eleven small development fixtures are focused regression cases;
        # no generated 66-profile scaling matrix is executed by these tests.
        paths = sorted((ROOT / 'examples/refinement-development').glob('[0-9][0-9]-*.json'))
        self.assertEqual(len(paths), 11)
        for path in paths:
            value = json.loads(path.read_bytes())
            with self.subTest(profile=path.name):
                old = original.evaluate(value, 100, 100000)
                answer = self.checked(value, old['decision'])
                if answer['decision'] == 'supported':
                    self.assertTrue(original.check_certificate(value, answer, 100))


if __name__ == '__main__':
    unittest.main()
