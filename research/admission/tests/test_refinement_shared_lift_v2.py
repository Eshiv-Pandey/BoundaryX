"""Safety and accounting tests for call-local shared lifting, v2.

These are authored finite development cases, not application qualification or
evidence of comparative speed. The preserved oracle checks both proof kinds.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from interoperability import refinement as core
from interoperability import refinement_oracle as checker
from interoperability import refinement_shared_lift_v2 as shared
from test_refinement import NOW, const, correlated_profile, development_profiles, eq, profile, relation


def frame_key(bindings):
    return json.dumps(bindings, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def lifter(p, budget=100_000):
    core.validate(p)
    model, contract = p['model'], p['model']['runtime_contract']
    safe = {name: core.conjunction(value, contract['invariants'])
            for name, value in model['states'].items()}
    goal = {name: core.conjunction(value, contract['goal'])
            for name, value in model['states'].items()}
    meter = shared._Meter(budget)
    return shared._SharedLift(p, {e['id']: e for e in model['transitions']}, safe, goal, meter), meter


def reconvergent_profile():
    p = profile('shared-identical-frames-different-histories')
    p['model']['horizon'] = 3
    p['initial_bindings'] = {'x': 0}
    p['model']['states'].update(ready={'safe': True, 'done': False},
                                checked={'safe': True, 'done': False})
    p['model']['transitions'] = [
        {'id': 'a', 'source': 'start', 'target': 'ready', 'operation': 'authored'},
        {'id': 'b', 'source': 'start', 'target': 'ready', 'operation': 'authored'},
        {'id': 'common', 'source': 'ready', 'target': 'checked', 'operation': 'authored'},
        {'id': 'finish', 'source': 'checked', 'target': 'end', 'operation': 'authored'}]
    p['relations'] = {'a': relation(), 'b': relation(),
                      'common': relation(updates={'x': const(1)}),
                      'finish': relation(guards=[eq({'binding': 'x'}, const(1))])}
    return p


def witness_result(p, path, steps):
    return {'decision': 'supported', 'reason': 'authored cache replay witness',
            'certificate': {'kind': 'recipe-path', 'profile_sha256': core.digest(p),
                            'checked_at': NOW, 'horizon': p['model']['horizon'],
                            'valid_until': p['model']['evidence']['valid_until'],
                            'transition_ids': list(path), 'steps': steps}}


class SharedLiftSemantics(unittest.TestCase):
    def assert_decision(self, p, expected, budget=100_000):
        before = deepcopy(p)
        result = shared.evaluate(p, NOW, budget=budget)
        self.assertEqual(result['decision'], expected, p['id'])
        self.assertEqual(p, before, 'Evaluation must not mutate the supplied profile')
        self.assertEqual(checker.check_certificate(p, result, NOW), expected != 'unknown', p['id'])
        if expected == 'unknown':
            self.assertIsNone(result['certificate'])
        return result

    def test_all_existing_development_profiles_keep_their_decisions_and_proofs(self):
        for p, expected in development_profiles():
            with self.subTest(profile=p['id']):
                result = self.assert_decision(p, expected)
                self.assertFalse(result['novelty_established'])

    def test_contextual_failure_cannot_refute_a_shared_edge_globally(self):
        p = correlated_profile()
        result = self.assert_decision(p, 'supported')
        self.assertEqual(result['certificate']['transition_ids'], ['b_good_binding', 'finish'])
        self.assertGreaterEqual(result['stats']['refinements'], 1)

    def test_bindings_from_different_histories_cannot_be_combined(self):
        p = correlated_profile()
        p['relations']['a_bad_binding']['updates'] = {'call': const('call-A'), 'target': const('B')}
        p['relations']['b_good_binding']['updates'] = {'call': const('call-B'), 'target': const('A')}
        self.assert_decision(p, 'unsupported')

    def test_identical_frames_reuse_local_steps_with_the_current_history(self):
        p = reconvergent_profile()
        memo, meter = lifter(p)
        first_path, second_path = ('a', 'common', 'finish'), ('b', 'common', 'finish')
        disposition, first_steps = memo.lift(first_path)
        self.assertEqual(disposition, 'supported')
        self.assertTrue(checker.check_certificate(p, witness_result(p, first_path, first_steps), NOW))
        self.assertIn(('common', frame_key({'x': 0})), memo._relations)
        previous_hits = meter.stats['relation_cache_hits']
        # Returned evidence must not give the caller a mutable reference into
        # a cached local step used by another abstract history.
        first_steps[1]['bindings_after']['x'] = 'forged by caller'
        disposition, second_steps = memo.lift(second_path)
        self.assertEqual(disposition, 'supported')
        self.assertGreater(meter.stats['relation_cache_hits'], previous_hits)
        self.assertEqual([row['edge'] for row in second_steps], list(second_path))
        self.assertEqual(second_steps[1]['bindings_after'], {'x': 1})
        self.assertTrue(checker.check_certificate(p, witness_result(p, second_path, second_steps), NOW))

    def test_complete_final_relation_cache_can_support_a_later_known_safe_path(self):
        p = profile('shared-cached-final-goal-witness')
        p['model']['horizon'] = 3
        p['model']['states'].update(a_uncertain={'done': False},
                                    b_safe={'safe': True, 'done': False},
                                    ready={'safe': True, 'done': False})
        p['model']['transitions'] = [
            {'id': 'a_enter', 'source': 'start', 'target': 'a_uncertain', 'operation': 'authored'},
            {'id': 'b_enter', 'source': 'start', 'target': 'b_safe', 'operation': 'authored'},
            {'id': 'a_join', 'source': 'a_uncertain', 'target': 'ready', 'operation': 'authored'},
            {'id': 'b_join', 'source': 'b_safe', 'target': 'ready', 'operation': 'authored'},
            {'id': 'finish', 'source': 'ready', 'target': 'end', 'operation': 'authored'}]
        p['relations'] = {edge['id']: relation() for edge in p['model']['transitions']}
        memo, _ = lifter(p)
        # Uncertain safety prevents a witness on this history, so its final
        # known relation is exhausted and published as a complete local entry.
        self.assertEqual(memo.lift(('a_enter', 'a_join', 'finish')), ('unknown', None))
        cached = memo._relations[('finish', frame_key(p['initial_bindings']))]
        self.assertEqual(len(cached.steps), 1)
        self.assertFalse(cached.unknown)
        result = self.assert_decision(p, 'supported')
        self.assertEqual(result['certificate']['transition_ids'], ['b_enter', 'b_join', 'finish'])
        self.assertGreater(result['stats']['relation_cache_hits'], 0)

    def test_full_frame_keys_distinguish_boolean_integer_and_missing_null(self):
        cases = [({'x': const(True)}, {'x': const(1)},
                  relation(guards=[eq({'binding': 'x'}, const(1))])),
                 ({}, {'x': const(None)},
                  relation(arguments={'x': [{'binding': 'x'}]},
                           guards=[eq({'arg': 'x'}, const(None))]))]
        for first, second, finish in cases:
            p = correlated_profile()
            p['initial_bindings'] = {}
            p['relations']['a_bad_binding'] = relation(updates=first)
            p['relations']['b_good_binding'] = relation(updates=second)
            p['relations']['finish'] = finish
            with self.subTest(first=first, second=second):
                result = self.assert_decision(p, 'supported')
                self.assertEqual(result['certificate']['transition_ids'], ['b_good_binding', 'finish'])

    def test_cached_unknown_prefix_cannot_become_a_negative_after_an_empty_suffix(self):
        p = correlated_profile()
        p['model']['transitions'] = [p['model']['transitions'][0], p['model']['transitions'][2]]
        p['relations'] = {
            'a_bad_binding': relation(emit={'unknown': 'Unmodeled public request'}),
            'finish': relation(guards=[eq(const(1), const(2))])}
        memo, meter = lifter(p)
        path = ('a_bad_binding', 'finish')
        self.assertEqual(memo.lift(path), ('unknown', None))
        summary = memo._prefixes[('a_bad_binding',)]
        self.assertTrue(summary.unknown)
        self.assertFalse(summary.frontier)
        previous_hits = meter.stats['prefix_cache_hits']
        self.assertEqual(memo.lift(path), ('unknown', None))
        self.assertGreater(meter.stats['prefix_cache_hits'], previous_hits)
        self.assert_decision(p, 'unknown')

    def test_conservative_contract_uncertainty_survives_a_later_refutation(self):
        p = correlated_profile()
        del p['model']['states']['ready']['safe']
        p['relations']['finish'] = relation(guards=[eq(const(1), const(2))])
        self.assert_decision(p, 'unknown')

    def test_unknown_alternative_does_not_hide_a_known_witness(self):
        p = correlated_profile()
        p['relations']['a_bad_binding']['updates'] = {'target': const('B')}
        p['relations']['finish']['arguments'] = {}
        p['relations']['finish']['emit'] = {'object': {
            'call': {'binding': 'call'}, 'target': {'binding': 'target'}}}
        result = self.assert_decision(p, 'supported')
        self.assertEqual(result['certificate']['transition_ids'], ['b_good_binding', 'finish'])

    def test_false_guard_dominates_an_unknown_request_in_cached_expansion(self):
        p = profile('shared-false-dominates-unknown')
        p['relations']['finish'] = relation(emit={'unknown': 'Opaque but definitely rejected'},
                                          guards=[eq(const(1), const(2))])
        memo, _ = lifter(p)
        self.assertEqual(memo.lift(('finish',)), ('refuted', ('finish',)))
        summary = memo._relations[('finish', frame_key(p['initial_bindings']))]
        self.assertFalse(summary.unknown)
        self.assertFalse(summary.steps)
        self.assert_decision(p, 'unsupported')

    def test_exact_prefix_cache_keeps_cycle_depths_separate(self):
        p = profile('shared-cyclic-prefixes')
        p['model']['horizon'] = 3
        p['model']['transitions'].insert(0, {
            'id': 'loop', 'source': 'start', 'target': 'start', 'operation': 'authored'})
        p['relations']['loop'] = relation()
        p['relations']['finish'] = relation(guards=[eq(const(1), const(2))])
        memo, meter = lifter(p)
        first, second = ('loop', 'finish'), ('loop', 'loop', 'finish')
        self.assertEqual(memo.lift(first), ('refuted', first))
        previous_hits = meter.stats['relation_cache_hits']
        self.assertEqual(memo.lift(second), ('refuted', second))
        self.assertEqual(memo._prefixes[('loop',)].path, ('loop',))
        self.assertEqual(memo._prefixes[('loop', 'loop')].path, ('loop', 'loop'))
        self.assertGreater(meter.stats['relation_cache_hits'], previous_hits)
        self.assert_decision(p, 'unsupported')

    def test_horizon_changes_do_not_reuse_an_admission_decision(self):
        p = profile('shared-horizon-context')
        p['initial_bindings'] = {'phase': 'waiting'}
        p['model']['transitions'].insert(0, {
            'id': 'loop', 'source': 'start', 'target': 'start', 'operation': 'authored'})
        p['relations']['loop'] = relation(updates={'phase': const('ready')})
        p['relations']['finish'] = relation(guards=[eq({'binding': 'phase'}, const('ready'))])
        self.assert_decision(p, 'unsupported')
        p['model']['horizon'] = 2
        result = self.assert_decision(p, 'supported')
        self.assertEqual(result['certificate']['transition_ids'], ['loop', 'finish'])

    def test_atomic_updates_read_the_old_frame_when_local_steps_are_cached(self):
        p = reconvergent_profile()
        p['initial_bindings'] = {'x': 'A'}
        p['relations']['common'] = relation(updates={'x': const('B'), 'y': {'binding': 'x'}})
        p['relations']['finish'] = relation(guards=[eq({'binding': 'x'}, const('B')),
                                                  eq({'binding': 'y'}, const('A'))])
        memo, _ = lifter(p)
        memo.lift(('a', 'common', 'finish'))
        path = ('b', 'common', 'finish')
        disposition, steps = memo.lift(path)
        self.assertEqual(disposition, 'supported')
        self.assertEqual(steps[1]['bindings_after'], {'x': 'B', 'y': 'A'})
        self.assertTrue(checker.check_certificate(p, witness_result(p, path, steps), NOW))

    def test_new_calls_bind_caches_to_current_profile_and_freshness(self):
        p = profile('shared-call-isolation')
        p['initial_bindings'] = {'x': 0}
        p['relations']['finish'] = relation(guards=[eq({'binding': 'x'}, const(1))])
        negative = self.assert_decision(p, 'unsupported')
        p['initial_bindings']['x'] = 1
        positive = self.assert_decision(p, 'supported')
        self.assertFalse(checker.check_certificate(p, negative, NOW))
        p['relations']['finish']['guards'] = [eq(const(1), const(2))]
        self.assert_decision(p, 'unsupported')
        self.assertFalse(checker.check_certificate(p, positive, NOW))
        p['model']['evidence']['valid_until'] = NOW - 1
        stale = self.assert_decision(p, 'unknown')
        self.assertEqual(stale['reason'], 'evidence_not_fresh')
        self.assertEqual(stale['stats']['relation_cache_entries'], 0)

    def test_partial_coverage_can_support_a_witness_but_never_a_negative(self):
        p = profile('shared-partial-coverage')
        p['coverage']['complete'] = False
        p['model']['evidence']['complete'] = False
        self.assert_decision(p, 'supported')
        p['relations']['finish']['guards'] = [eq(const(1), const(2))]
        self.assert_decision(p, 'unknown')


class SharedLiftBudgetAndCertificates(unittest.TestCase):
    def test_final_first_tuple_does_not_exhaust_or_publish_a_huge_domain(self):
        p = profile('shared-wide-final-goal')
        arguments = {'a' + str(i): [{'literal': value} for value in range(16)] for i in range(8)}
        p['relations']['finish'] = relation(arguments=arguments,
            emit={'object': {name: {'arg': name} for name in arguments}})
        result = shared.evaluate(p, NOW, budget=1000)
        self.assertEqual(result['decision'], 'supported')
        self.assertEqual(result['stats']['relation_checks'], 1)
        self.assertTrue(checker.check_certificate(p, result, NOW))
        memo, _ = lifter(p, budget=1000)
        self.assertEqual(memo.lift(('finish',))[0], 'supported')
        self.assertNotIn(('finish', frame_key(p['initial_bindings'])), memo._relations)

    def test_interrupted_expansion_never_publishes_a_partial_relation(self):
        p = profile('shared-interrupted-domain')
        p['relations']['finish'] = relation(
            arguments={'x': [{'literal': value} for value in range(16)]},
            updates={'x': {'arg': 'x'}})
        memo, meter = lifter(p)
        original_tick = meter.tick

        def exhaust_before_third_assignment(kind):
            if kind == 'relation_checks' and meter.stats['relation_checks'] == 2:
                meter.limit = meter.stats['work_units']
            original_tick(kind)

        # Force the real work-meter exception after two successful local
        # outcomes. Neither outcome is a complete expansion of this domain.
        with patch.object(meter, 'tick', side_effect=exhaust_before_third_assignment):
            with self.assertRaises(core._Limit):
                memo._expand('finish', p['initial_bindings'], early_goal=False)
        self.assertEqual(meter.stats['relation_checks'], 2)
        self.assertEqual(meter.stats['work_units'], meter.limit)
        self.assertNotIn(('finish', frame_key(p['initial_bindings'])), memo._relations)
        self.assertEqual(meter.stats['relation_cache_entries'], 0)

    def test_budget_failure_during_cache_publication_leaves_no_entry(self):
        p = profile('shared-interrupted-publication')
        p['relations']['finish'] = relation(guards=[eq(const(1), const(2))])
        memo, meter = lifter(p)
        original_tick = meter.tick

        def exhaust_before_publication(kind):
            if kind == 'cache_insertions':
                meter.limit = meter.stats['work_units']
            original_tick(kind)

        with patch.object(meter, 'tick', side_effect=exhaust_before_publication):
            with self.assertRaises(core._Limit):
                memo._expand('finish', p['initial_bindings'], early_goal=False)
        self.assertFalse(memo._relations)
        self.assertEqual(meter.stats['relation_cache_entries'], 0)

    def test_interrupted_prefix_publication_keeps_only_completed_entries(self):
        p = reconvergent_profile()
        memo, meter = lifter(p)
        original_tick = meter.tick

        def exhaust_before_second_prefix(kind):
            # Initial prefix and complete relation expansion have committed.
            if kind == 'cache_insertions' and meter.stats['cache_insertions'] == 2:
                meter.limit = meter.stats['work_units']
            original_tick(kind)

        with patch.object(meter, 'tick', side_effect=exhaust_before_second_prefix):
            with self.assertRaises(core._Limit):
                memo.lift(('a', 'common', 'finish'))
        self.assertIn((), memo._prefixes)
        self.assertNotIn(('a',), memo._prefixes)
        self.assertIn(('a', frame_key(p['initial_bindings'])), memo._relations)
        self.assertEqual(meter.stats['prefix_cache_entries'], 1)
        self.assertEqual(meter.stats['relation_cache_entries'], 1)

    def test_empty_relation_and_prefix_hits_still_consume_budget(self):
        p = profile('shared-metered-empty-hits')
        p['relations']['finish'] = relation(arguments={'x': []})
        memo, meter = lifter(p)
        self.assertEqual(memo.lift(('finish',)), ('refuted', ('finish',)))
        checks, work = meter.stats['cache_status_checks'], meter.stats['work_units']
        summary, witness = memo._expand('finish', p['initial_bindings'], early_goal=False)
        self.assertFalse(summary.steps)
        self.assertIsNone(witness)
        self.assertGreater(meter.stats['work_units'], work)
        self.assertGreater(meter.stats['cache_status_checks'], checks)
        self.assertGreater(meter.stats['relation_cache_hits'], 0)
        self.assertEqual(meter.stats['relation_checks'], 0)
        work = meter.stats['work_units']
        self.assertEqual(memo.lift(('finish',)), ('refuted', ('finish',)))
        self.assertGreater(meter.stats['work_units'], work)
        self.assertGreater(meter.stats['prefix_cache_hits'], 0)
        meter.limit = meter.stats['work_units']
        with self.assertRaises(core._Limit):
            memo.lift(('finish',))

    def test_budget_abstention_has_no_proof(self):
        result = shared.evaluate(profile(), NOW, budget=1)
        self.assertEqual(result['decision'], 'unknown')
        self.assertEqual(result['reason'], 'work_budget_exhausted')
        self.assertEqual(result['stats']['work_units'], 1)
        self.assertIsNone(result['certificate'])
        self.assertFalse(checker.check_certificate(profile(), result, NOW))

    def test_existing_checker_accepts_both_proof_kinds_without_candidate_execution(self):
        p = profile('shared-original-proof-kinds')
        positive = shared.evaluate(p, NOW)
        negative_profile = deepcopy(p)
        negative_profile['relations']['finish']['guards'] = [eq(const(1), const(2))]
        negative = shared.evaluate(negative_profile, NOW)
        self.assertEqual(positive['certificate']['kind'], 'recipe-path')
        self.assertEqual(negative['certificate']['kind'], 'refinement-exhaustion')
        with patch.object(shared, 'evaluate', side_effect=AssertionError('Do not rerun the candidate')):
            self.assertTrue(checker.check_certificate(p, positive, NOW))
            self.assertTrue(checker.check_certificate(negative_profile, negative, NOW))

    def test_forged_witnesses_and_global_edge_refutations_are_rejected(self):
        p = correlated_profile()
        positive = shared.evaluate(p, NOW)
        forged = deepcopy(positive)
        forged['certificate']['steps'][0]['bindings_after']['call'] = 'call-A'
        self.assertFalse(checker.check_certificate(p, forged, NOW))
        header = {key: positive['certificate'][key]
                  for key in ('profile_sha256', 'checked_at', 'horizon', 'valid_until')}
        for prefixes in ([], [['finish']], [['a_bad_binding', 'finish']]):
            forged = {'decision': 'unsupported', 'reason': 'forged global refutation',
                      'certificate': dict(header, kind='refinement-exhaustion', refuted_prefixes=prefixes)}
            with self.subTest(prefixes=prefixes):
                self.assertFalse(checker.check_certificate(p, forged, NOW))


if __name__ == '__main__':
    unittest.main()
