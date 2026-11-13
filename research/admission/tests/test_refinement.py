"""Adversarial correctness tests for the supplied finite public-recipe boundary.

Constructed development examples; not application traces or a held-out study.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from interoperability import refinement as candidate
from interoperability import refinement_oracle as reference

NOW = 100


def const(value):
    return {'const': value}


def eq(left, right):
    return {'op': 'eq', 'left': left, 'right': right}


def relation(*, emit=None, arguments=None, guards=None, updates=None):
    return {'source_ref': 'Authored finite development relation; source validity is not asserted',
            'arguments': {} if arguments is None else arguments,
            'emit': {'object': {}} if emit is None else emit,
            'guards': [] if guards is None else guards,
            'updates': {} if updates is None else updates}


def profile(case_id='direct-public-binding'):
    return {
        'schema_version': 'recipe-continuation/1', 'id': case_id,
        'model': {
            'schema_version': 'finite-continuation/1', 'id': case_id + '-graph',
            'route': 'Authored finite public-recipe development model; not a qualified protocol route',
            'provenance': {'kind': 'authored-development', 'source': 'tests/test_refinement.py',
                           'review_status': 'AI-authored semantic development; human review pending'},
            'horizon': 1, 'evidence': {'complete': True, 'observed_at': 0, 'valid_until': 4102444800},
            'initial': 'start', 'states': {'start': {'safe': True, 'done': False},
                                          'end': {'safe': True, 'done': True}},
            'transitions': [{'id': 'finish', 'source': 'start', 'target': 'end', 'operation': 'finish'}],
            'runtime_contract': {'goal': [{'field': 'done', 'op': 'eq', 'value': True}],
                                 'invariants': [{'field': 'safe', 'op': 'eq', 'value': True}]}},
        'initial_bindings': {'public_call': 'call-A'},
        'relations': {'finish': relation(
            arguments={'call': [{'binding': 'public_call'}]},
            emit={'object': {'data': {'object': {'call': {'arg': 'call'}, 'approved': const(True)}}}},
            guards=[eq({'emit_path': ['data', 'call']}, {'binding': 'public_call'}),
                    eq({'emit_path': ['data', 'approved']}, const(True))])},
        'coverage': {'complete': True,
                     'scope': 'Only the declared finite graph, literal/binding recipe choices and supplied relations; no whole-interface closure claim'}}


def correlated_profile():
    p = profile('correlated-prefix-refinement')
    p['model']['horizon'] = 2
    p['model']['states']['ready'] = {'safe': True, 'done': False}
    p['model']['transitions'] = [
        {'id': 'a_bad_binding', 'source': 'start', 'target': 'ready', 'operation': 'select_declared_binding'},
        {'id': 'b_good_binding', 'source': 'start', 'target': 'ready', 'operation': 'select_declared_binding'},
        {'id': 'finish', 'source': 'ready', 'target': 'end', 'operation': 'confirm'}]
    p['initial_bindings'] = {}
    p['relations'] = {
        'a_bad_binding': relation(updates={'call': const('call-A'), 'target': const('B')}),
        'b_good_binding': relation(updates={'call': const('call-B'), 'target': const('B')}),
        'finish': relation(arguments={'call': [{'binding': 'call'}], 'target': [{'binding': 'target'}]},
                           emit={'object': {'call': {'arg': 'call'}, 'target': {'arg': 'target'}}},
                           guards=[eq({'emit_path': ['call']}, const('call-B')),
                                   eq({'emit_path': ['target']}, const('B'))])}
    return p


def development_profiles():
    profiles = [(profile(), 'supported')]
    p = profile('fixed-text-shape-obstruction')
    p['relations']['finish']['emit'] = {'object': {'text': const('{"data":{"approved":true}}')}}
    profiles.append((p, 'unsupported'))
    p = profile('missing-public-binding-partial-coverage')
    p['initial_bindings'] = {}
    p['coverage']['complete'] = False
    profiles.append((p, 'unknown'))
    profiles.append((correlated_profile(), 'supported'))
    p = profile('raw-parameters-without-version-header')
    p['relations']['finish']['guards'].append(eq({'emit_path': ['headers', 'A2A-Version']}, const('1.0')))
    profiles.append((p, 'unsupported'))
    p = deepcopy(p)
    p['id'] = 'explicit-header-configuration'
    p['model']['id'] = p['id'] + '-graph'
    p['relations']['finish']['emit']['object']['headers'] = {'object': {'A2A-Version': const('1.0')}}
    profiles.append((p, 'supported'))
    p = profile('opaque-serialization')
    p['relations']['finish']['emit'] = {'unknown': 'Unmodeled public serialization boundary'}
    profiles.append((p, 'unknown'))
    p = profile('conservative-observable-uncertainty')
    p['relations']['finish']['guards'] = [eq(const(1), const(2))]
    p['model']['states']['uncertain_dead_end'] = {'done': False}
    p['model']['transitions'].append({'id': 'dead_branch', 'source': 'start',
                                    'target': 'uncertain_dead_end', 'operation': 'inspect'})
    p['relations']['dead_branch'] = relation()
    profiles.append((p, 'unknown'))
    p = profile('atomic-public-binding-updates')
    p['model']['horizon'] = 2
    p['model']['states']['ready'] = {'safe': True, 'done': False}
    p['model']['transitions'] = [
        {'id': 'update', 'source': 'start', 'target': 'ready', 'operation': 'public_update'},
        {'id': 'finish', 'source': 'ready', 'target': 'end', 'operation': 'finish'}]
    p['initial_bindings'] = {'x': 'A', 'y': 'unused'}
    p['relations'] = {'update': relation(updates={'x': const('B'), 'y': {'binding': 'x'}}),
                      'finish': relation(guards=[eq({'binding': 'x'}, const('B')),
                                                   eq({'binding': 'y'}, const('A'))])}
    profiles.append((p, 'supported'))
    p = profile('working-state-blocks-second-answer')
    p['model']['horizon'] = 2
    p['model']['states']['working'] = {'safe': True, 'done': False}
    p['model']['transitions'] = [
        {'id': 'first_answer', 'source': 'start', 'target': 'working', 'operation': 'answer'},
        {'id': 'second_answer', 'source': 'working', 'target': 'end', 'operation': 'answer'}]
    p['initial_bindings'] = {'phase': 'waiting'}
    p['relations'] = {edge: relation(guards=[eq({'binding': 'phase'}, const('waiting'))],
                                         updates={'phase': const('working')})
                      for edge in ('first_answer', 'second_answer')}
    profiles.append((p, 'unsupported'))
    p = profile('stale-evidence')
    p['model']['evidence']['valid_until'] = NOW - 1
    profiles.append((p, 'unknown'))
    return profiles


class RefinementSemantics(unittest.TestCase):
    def assert_agree(self, p, expected, budget=None):
        results = []
        for method in (candidate.evaluate, reference.evaluate):
            result = method(p, NOW, budget=budget)
            self.assertEqual(result['decision'], expected, (p['id'], method.__module__, result))
            self.assertEqual(reference.check_certificate(p, result, NOW), expected != 'unknown',
                             (p['id'], method.__module__, result))
            results.append(result)
        return results

    def test_authored_development_profiles_have_declared_outcomes(self):
        for p, expected in development_profiles():
            with self.subTest(profile=p['id']):
                self.assert_agree(p, expected)

    def test_refinement_is_prefix_scoped_not_global_edge_deletion(self):
        p = correlated_profile()
        result, _ = self.assert_agree(p, 'supported')
        self.assertEqual(result['certificate']['transition_ids'], ['b_good_binding', 'finish'])
        self.assertGreaterEqual(result['stats']['refinements'], 1)

    def test_bindings_cannot_be_mixed_across_alternative_frames(self):
        p = correlated_profile()
        p['relations']['a_bad_binding']['updates'] = {'call': const('call-A'), 'target': const('B')}
        p['relations']['b_good_binding']['updates'] = {'call': const('call-B'), 'target': const('A')}
        self.assert_agree(p, 'unsupported')

    def test_missing_recipe_is_unavailable_only_in_declared_finite_domain(self):
        p = profile()
        p['initial_bindings'] = {}
        self.assert_agree(p, 'unsupported')
        p['coverage']['complete'] = False
        self.assert_agree(p, 'unknown')

    def test_private_or_generated_recipe_constructor_is_rejected(self):
        for tag in ('private', 'generated', 'nonce', 'oracle'):
            p = profile()
            p['relations']['finish']['arguments']['call'] = [{tag: 'not-a-public-input'}]
            for validate in (candidate.validate, reference.validate_profile):
                with self.subTest(tag=tag, validator=validate.__module__), self.assertRaises(ValueError):
                    validate(p)

    def test_unknown_generated_field_is_not_a_free_existential_variable(self):
        p = profile()
        p['relations']['finish']['emit']['object']['message_id'] = {'unknown': 'runtime generated nonce'}
        self.assert_agree(p, 'unknown')

    def test_known_false_guard_dominates_unknown_request(self):
        p = profile()
        p['relations']['finish']['emit'] = {'unknown': 'opaque request'}
        p['relations']['finish']['guards'] = [eq({'unknown': 'one guard'}, const(1)), eq(const(1), const(2))]
        self.assert_agree(p, 'unsupported')

    def test_missing_null_and_scalar_types_are_distinct(self):
        for value, expected in ((None, 'supported'), (False, 'unsupported'), (0, 'unsupported')):
            p = profile()
            p['relations']['finish'] = relation(emit={'object': {'known': const(value)}},
                                                guards=[{'op': 'present', 'left': {'emit_path': ['known']}},
                                                        eq({'emit_path': ['known']}, const(None))])
            self.assert_agree(p, expected)
        p['relations']['finish']['emit'] = {'object': {}}
        self.assert_agree(p, 'unsupported')

    def test_false_is_not_integer_zero_in_nested_json_guards(self):
        p = profile()
        p['relations']['finish'] = relation(guards=[eq({'object': {'x': const(False)}},
                                                     {'object': {'x': const(0)}})])
        self.assert_agree(p, 'unsupported')

    def test_atomic_updates_use_old_frame_not_prior_update_in_dict(self):
        p = next(p for p, _ in development_profiles() if p['id'] == 'atomic-public-binding-updates')
        first, _ = self.assert_agree(p, 'supported')
        self.assertEqual(first['certificate']['steps'][0]['bindings_after'], {'x': 'B', 'y': 'A'})

    def test_non_scalar_binding_update_is_indeterminate(self):
        p = profile()
        p['relations']['finish']['updates'] = {'bad': {'object': {'x': const(1)}}}
        self.assert_agree(p, 'unknown')

    def test_uncertainty_is_not_cleared_by_a_later_false_guard(self):
        p = next(p for p, _ in development_profiles() if p['id'] == 'atomic-public-binding-updates')
        p['relations']['update']['emit'] = {'unknown': 'unknown first step'}
        p['relations']['finish']['guards'] = [eq(const(1), const(2))]
        self.assert_agree(p, 'unknown')

    def test_unknown_on_a_no_goal_suffix_does_not_poison_relation_result(self):
        p = profile()
        p['relations']['finish']['guards'] = [eq(const(1), const(2))]
        p['model']['states']['dead'] = {'safe': True, 'done': False}
        p['model']['transitions'].append({'id': 'irrelevant', 'source': 'start', 'target': 'dead', 'operation': 'other'})
        p['relations']['irrelevant'] = relation(emit={'unknown': 'unneeded request'})
        self.assert_agree(p, 'unsupported')

    def test_incomplete_positive_still_has_checked_conditional_witness(self):
        p = profile()
        p['coverage']['complete'] = False
        p['model']['evidence']['complete'] = False
        self.assert_agree(p, 'supported')

    def test_zero_horizon_and_initial_goal(self):
        p = profile()
        p['model']['horizon'] = 0
        self.assert_agree(p, 'unsupported')
        p['model']['states']['start']['done'] = True
        a, b = self.assert_agree(p, 'supported')
        self.assertEqual(a['certificate']['steps'], [])
        self.assertEqual(b['certificate']['steps'], [])

    def test_unsafe_initial_state_blocks_all_recipes(self):
        p = profile()
        p['model']['states']['start']['safe'] = False
        self.assert_agree(p, 'unsupported')

    def test_low_work_budget_abstains_and_budget_is_reported(self):
        for result in self.assert_agree(profile(), 'unknown', budget=1):
            self.assertEqual(result['reason'], 'work_budget_exhausted')
            self.assertEqual(result['stats']['budget'], 1)
        for invalid in (0, -1, True, 1.5, '10'):
            for evaluate in (candidate.evaluate, reference.evaluate):
                with self.subTest(budget=invalid, method=evaluate.__module__), self.assertRaises(ValueError):
                    evaluate(profile(), NOW, invalid)

    def test_wide_domain_first_valid_goal_does_not_require_full_cartesian_scan(self):
        p = profile('wide-domain-first-witness')
        arguments = {'a' + str(i): [{'literal': value} for value in range(16)] for i in range(8)}
        p['relations']['finish'] = relation(arguments=arguments,
            emit={'object': {name: {'arg': name} for name in arguments}})
        # A first public tuple already proves the goal. Both implementations
        # must avoid traversing 16**8 remaining tuples before returning it.
        for result in self.assert_agree(p, 'supported', budget=300):
            self.assertLessEqual(result['stats']['work_units'], 300)

    def test_unknown_alternative_prefix_does_not_hide_known_witness(self):
        p = correlated_profile()
        p['relations']['a_bad_binding']['updates'] = {'target': const('B')}
        p['relations']['finish']['arguments'] = {}
        p['relations']['finish']['emit'] = {'object': {'call': {'binding': 'call'},
                                                    'target': {'binding': 'target'}}}
        self.assert_agree(p, 'supported')

    def test_reference_collapses_equal_frames_and_reuses_relations_on_cycles(self):
        p = profile()
        p['model']['horizon'] = 8
        p['relations']['finish']['guards'] = [eq(const(1), const(2))]
        p['model']['transitions'].insert(0, {'id': 'loop', 'source': 'start', 'target': 'start', 'operation': 'poll'})
        p['relations']['loop'] = relation()
        _, r = self.assert_agree(p, 'unsupported')
        self.assertEqual(r['stats']['argument_assignments'], 2)

    def test_replaying_cached_relations_still_consumes_the_work_budget(self):
        p = profile('bounded-cached-outcomes')
        p['model']['horizon'] = 64
        p['model']['transitions'].append(
            {'id': 'loop', 'source': 'start', 'target': 'start', 'operation': 'poll'})
        p['relations']['loop'] = relation()
        p['relations']['finish'] = relation(
            arguments={name: [{'literal': value} for value in range(16)] for name in ('a', 'b')},
            guards=[eq(const(1), const(2))])
        limited = reference.evaluate(p, NOW, budget=2000)
        self.assertEqual(limited['decision'], 'unknown')
        self.assertEqual(limited['reason'], 'work_budget_exhausted')
        self.assertEqual(limited['stats']['work_units'], 2000)
        complete = reference.evaluate(p, NOW, budget=50000)
        self.assertEqual(complete['decision'], 'unsupported')
        self.assertTrue(reference.check_certificate(p, complete, NOW))

    def test_deterministic_small_relational_models_crosscheck(self):
        random_source = random.Random(271828)
        for index in range(40):
            p = profile('generated-semantic-test-' + str(index))
            p['model']['horizon'] = random_source.randrange(4)
            p['model']['states'] = {str(n): {'safe': True, 'done': n == 3} for n in range(4)}
            p['model']['initial'] = '0'
            p['model']['transitions'] = []
            p['relations'] = {}
            p['initial_bindings'] = {'x': random_source.randrange(2)}
            for edge_index in range(5):
                edge_id = 'e' + str(edge_index)
                source, target = str(random_source.randrange(4)), str(random_source.randrange(4))
                p['model']['transitions'].append({'id': edge_id, 'source': source, 'target': target, 'operation': 'authored'})
                p['relations'][edge_id] = relation(guards=[eq({'binding': 'x'}, const(random_source.randrange(2)))],
                                                    updates={'x': const(random_source.randrange(2))})
            expected = reference.evaluate(p, NOW)['decision']
            with self.subTest(index=index):
                self.assert_agree(p, expected)


class RefinementCertificates(unittest.TestCase):
    def test_unreachable_prefixes_still_consume_the_checker_work_budget(self):
        p = profile('bounded-empty-prefix-checking')
        p['model']['horizon'] = 64
        p['relations']['finish']['arguments']['call'] = []
        p['model']['transitions'].append(
            {'id': 'loop', 'source': 'end', 'target': 'end', 'operation': 'poll'})
        p['relations']['loop'] = relation()
        result = candidate.evaluate(p, NOW)
        # Every prefix is validly impossible, but scanning many empty lifts
        # must remain bounded even though no argument tuple is ever evaluated.
        result['certificate']['refuted_prefixes'] = [
            ['finish'] + ['loop'] * depth for depth in range(64)]
        self.assertTrue(reference.check_certificate(p, result, NOW))
        with patch.object(reference, 'CHECK_BUDGET', 256):
            self.assertFalse(reference.check_certificate(p, result, NOW))

    def test_late_tuple_membership_checks_domains_without_cartesian_enumeration(self):
        p = profile('late-public-argument-tuple')
        arguments = {'a' + str(i): [{'literal': value} for value in range(16)] for i in range(8)}
        assignment = {name: 15 for name in arguments}
        p['relations']['finish'] = relation(arguments=arguments,
            emit={'object': {name: {'arg': name} for name in arguments}},
            guards=[eq({'emit_path': [name]}, const(15)) for name in arguments])
        # Construct the legitimate last tuple directly. Evaluating a Cartesian
        # search here would itself be the bug under test (16**8 combinations).
        step = {'edge': 'finish', 'args': assignment, 'request': dict(assignment),
                'bindings_before': dict(p['initial_bindings']),
                'bindings_after': dict(p['initial_bindings'])}
        result = {'decision': 'supported', 'reason': 'explicit legitimate public tuple',
                  'certificate': {'kind': 'recipe-path', 'profile_sha256': candidate.digest(p),
                                  'checked_at': NOW, 'horizon': 1, 'valid_until': 4102444800,
                                  'transition_ids': ['finish'], 'steps': [step]}}
        with patch.object(reference, '_assignments', side_effect=AssertionError('Cartesian membership is forbidden')):
            self.assertTrue(reference.check_certificate(p, result, NOW))
            result['certificate']['steps'][0]['args']['a7'] = 16
            self.assertFalse(reference.check_certificate(p, result, NOW))

    def test_forged_positive_fields_and_stale_clock_are_rejected(self):
        p = profile()
        good = candidate.evaluate(p, NOW)
        mutations = []
        for field, value in (('args', {'call': 'private-or-guessed'}), ('request', {'data': 'forged'}),
                             ('bindings_before', {}), ('bindings_after', {'public_call': 'changed'}),
                             ('edge', 'unknown')):
            r = deepcopy(good);r['certificate']['steps'][0][field] = value;mutations.append(r)
        for field, value in (('profile_sha256', '0' * 64), ('horizon', 0), ('checked_at', NOW + 1),
                             ('valid_until', 1), ('transition_ids', [])):
            r = deepcopy(good);r['certificate'][field] = value;mutations.append(r)
        for index, result in enumerate(mutations):
            with self.subTest(index=index):
                self.assertFalse(reference.check_certificate(p, result, NOW))
        changed = deepcopy(p);changed['initial_bindings']['public_call'] = 'other'
        self.assertFalse(reference.check_certificate(changed, good, NOW))
        self.assertFalse(reference.check_certificate(p, good, 4102444801))

    def test_empty_and_globalized_refutations_cannot_cover_a_real_witness(self):
        p = correlated_profile()
        positive = candidate.evaluate(p, NOW)
        header = {k: positive['certificate'][k] for k in ('profile_sha256', 'checked_at', 'horizon', 'valid_until')}
        for prefixes in ([], [['a_bad_binding']], [['finish']], [['a_bad_binding', 'finish']]):
            result = {'decision': 'unsupported', 'reason': 'forged', 'certificate': dict(
                header, kind='refinement-exhaustion', refuted_prefixes=prefixes)}
            self.assertFalse(reference.check_certificate(p, result, NOW))

    def test_negative_refutations_need_complete_coverage_and_truthful_prefixes(self):
        p = next(p for p, _ in development_profiles() if p['id'] == 'fixed-text-shape-obstruction')
        result = candidate.evaluate(p, NOW)
        self.assertTrue(reference.check_certificate(p, result, NOW))
        bad = deepcopy(result);bad['certificate']['refuted_prefixes'] = []
        self.assertFalse(reference.check_certificate(p, bad, NOW))
        bad = deepcopy(result);bad['certificate']['refuted_prefixes'] *= 2
        self.assertFalse(reference.check_certificate(p, bad, NOW))
        p['coverage']['complete'] = False
        bad = deepcopy(result);bad['certificate']['profile_sha256'] = candidate.digest(p)
        self.assertFalse(reference.check_certificate(p, bad, NOW))

    def test_reference_product_certificate_rejects_omitted_states(self):
        p = profile();p['model']['horizon'] = 0
        result = reference.evaluate(p, NOW)
        self.assertTrue(reference.check_certificate(p, result, NOW))
        result['certificate']['product_layers'][0] = []
        self.assertFalse(reference.check_certificate(p, result, NOW))

    def test_unknown_provides_no_certificate(self):
        p = profile();p['coverage']['complete'] = False;p['relations']['finish']['guards'] = [eq(const(1), const(2))]
        r = candidate.evaluate(p, NOW)
        self.assertIsNone(r['certificate'])
        self.assertFalse(reference.check_certificate(p, r, NOW))


class RefinementInputValidation(unittest.TestCase):
    def test_missing_relations_unknown_constructor_bad_argument_and_forbidden_emit_path(self):
        variations = []
        p = profile();p['relations'] = {};variations.append(p)
        p = profile();p['relations']['finish']['emit'] = {'unmodeled_constructor': 1};variations.append(p)
        p = profile();p['relations']['finish']['emit'] = {'arg': 'undeclared'};variations.append(p)
        p = profile();p['relations']['finish']['emit'] = {'emit_path': ['data']};variations.append(p)
        p = profile();p['initial_bindings']['bad'] = {};variations.append(p)
        p = profile();p['relations']['finish']['guards'][0]['left'] = {'emit_path': [True]};variations.append(p)
        for index, p in enumerate(variations):
            for validate in (candidate.validate, reference.validate_profile):
                with self.subTest(index=index, validator=validate.__module__), self.assertRaises(ValueError):
                    validate(p)

    def test_shared_profile_limits_are_enforced_independently(self):
        variations = []
        p = profile();p['initial_bindings'] = {str(i): i for i in range(129)};variations.append(p)
        p = profile();p['relations']['finish']['arguments']['call'] = [{'literal': i} for i in range(17)];variations.append(p)
        p = profile();p['relations']['finish']['arguments'] = {str(i): [] for i in range(9)};variations.append(p)
        p = profile();expr = const(1)
        for _ in range(17): expr = {'array': [expr]}
        p['relations']['finish']['emit'] = expr;variations.append(p)
        for index, p in enumerate(variations):
            for validate in (candidate.validate, reference.validate_profile):
                with self.subTest(index=index, validator=validate.__module__), self.assertRaises(ValueError):
                    validate(p)

    def test_frozen_authored_profiles_match_manifest(self):
        folder = ROOT / 'examples/refinement-development'
        index = json.loads((folder / 'manifest.json').read_bytes())
        self.assertEqual(index['scope'], 'authored-development-only')
        self.assertFalse(index['held_out'])
        for row in index['profiles']:
            raw = (folder / row['file']).read_bytes()
            self.assertEqual(len(raw), row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
            p = json.loads(raw)
            self.assertEqual(p['model']['provenance']['kind'], 'authored-development')
            self.assertEqual(candidate.evaluate(p, index['now'])['decision'], row['expected_decision'])
            self.assertEqual(reference.evaluate(p, index['now'])['decision'], row['expected_decision'])


if __name__ == '__main__':
    unittest.main()
