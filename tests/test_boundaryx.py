"""Adverse evidence controls for the separate verifier and evaluation boundary."""
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from boundaryx.core.evidence import EvidenceError, digest, member, parse, publish, read, same, verify_manifest
from boundaryx.tasks.contracts import check_review, check_team_reviews, heldout_status
from boundaryx.verification.independent import source_check, verify_artifact_cell
from boundaryx.verification.semantic import expected_answer


class EvidenceControls(unittest.TestCase):
    def test_json_number_boolean_and_array_multiplicity(self):
        self.assertFalse(same(True, 1))
        self.assertFalse(same(1, 1.0))
        self.assertFalse(same(['a', 'a'], ['a']))
        self.assertTrue(same({'a': 1, 'b': None}, {'b': None, 'a': 1}))

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(EvidenceError):
                parse(raw)

    def test_missing_and_present_null_remain_different(self):
        self.assertFalse(same({}, {'value': None}))

    def test_manifest_traversal_and_windows_aliases_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for unsafe in ('../x', '/x', 'C:/x', 'a\\b', 'a//b', 'a/./b', 'x:stream'):
                with self.assertRaises(EvidenceError):
                    member(root, unsafe)

    def test_manifest_tampering_duplicate_and_empty_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = b'original'
            (root / 'file').write_bytes(raw)
            row = {'path': 'file', 'bytes': len(raw), 'sha256': digest(raw)}
            publish(root / 'manifest.json', {'files': [row]})
            self.assertEqual(verify_manifest(root), 1)
            (root / 'file').write_bytes(b'tampered')
            with self.assertRaises(EvidenceError):
                verify_manifest(root)
            for rows in ([], [row, row]):
                (root / 'manifest.json').unlink()
                publish(root / 'manifest.json', {'files': rows})
                with self.assertRaises(EvidenceError):
                    verify_manifest(root)

    def test_report_publication_never_overwrites(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'evidence.json'
            publish(path, {'status': 'original'})
            with self.assertRaises(FileExistsError):
                publish(path, {'status': 'replacement'})
            self.assertEqual(read(path)['status'], 'original')


class IndependentSemanticControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = read(ROOT / 'benchmark/loss-v1/development-cases.json')

    def test_all_ten_original_gold_proposals_agree_with_sql_oracle(self):
        self.assertEqual(len(self.bank['cases']), 10)
        for case in self.bank['cases']:
            self.assertTrue(same(expected_answer(case), case['gold']['expected_answer']))

    def test_source_or_gold_tampering_rejected(self):
        case = deepcopy(self.bank['cases'][0])
        source = {'task': deepcopy(case['task']), 'records': deepcopy(case['records'])}
        source_check(case, source)
        case['gold']['expected_answer'] = {'service_ids': ['fabricated']}
        with self.assertRaises(EvidenceError):
            source_check(case, source)
        case = deepcopy(self.bank['cases'][0])
        source['task']['target'] = 'different-target'
        with self.assertRaises(EvidenceError):
            source_check(case, source)

    def test_independent_path_has_no_legacy_critical_imports(self):
        for path in (ROOT / 'src/boundaryx/verification').glob('*.py'):
            tree = ast.parse(path.read_bytes())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn('interoperability', node.module or '')
                    self.assertNotIn('scripts', node.module or '')
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertFalse(alias.name.startswith(('interoperability', 'scripts')))

    def test_unqualified_new_kind_cannot_get_an_invented_answer(self):
        case = deepcopy(self.bank['cases'][0])
        case['task']['kind'] = 'new_heldout_family'
        with self.assertRaises(EvidenceError):
            expected_answer(case)


class ActualArtifactCaptureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cell = read(ROOT / 'runs/supervisor-handoff-20261113/parts-main-001/cells/data--r0--mgcrea_typed.json')

    def test_saved_real_capture_loss_and_same_task_recovery(self):
        result = verify_artifact_cell(self.cell)
        self.assertEqual(result['fields_retained'], 0)
        self.assertEqual(result['recovered_fields'], 2)

    def test_corrupted_actual_wire_rejected(self):
        cell = deepcopy(self.cell)
        entity = next(w['response'] for w in cell['wire'] if w.get('response'))
        entity['sha256'] = '0' * 64
        with self.assertRaises(EvidenceError):
            verify_artifact_cell(cell)

    def test_raw_recovery_new_task_is_not_accepted(self):
        cell = deepcopy(self.cell)
        cell['recovery']['final_public_task']['id'] = 'new-task'
        with self.assertRaises(EvidenceError):
            verify_artifact_cell(cell)

    def test_summary_cannot_invent_surviving_fields(self):
        cell = deepcopy(self.cell)
        cell['field_checks']['data'] = True
        with self.assertRaises(EvidenceError):
            verify_artifact_cell(cell)


class ReviewBoundaryControls(unittest.TestCase):
    def test_pending_review_is_not_approval(self):
        with self.assertRaises(EvidenceError):
            check_review({'decision': None})

    def test_one_teammate_review_is_not_enough(self):
        with self.assertRaises(EvidenceError):
            check_team_reviews({'reviews': [{'decision': 'approve', 'reviewer': 'r', 'reasoning': 'reviewed'}]}, 'hash')

    def test_two_team_approvals_do_not_require_a_supervisor(self):
        reviews = [{'decision': 'approve', 'reviewer': name, 'reasoning': 'reviewed independently',
                    'reviewed_definition_sha256': 'hash'} for name in ('Reviewer A', 'Reviewer B')]
        check_team_reviews({'reviews': reviews}, 'hash')

    def test_duplicate_reviewer_is_not_independent_review(self):
        reviews = [{'decision': 'approve', 'reviewer': name, 'reasoning': 'reviewed',
                    'reviewed_definition_sha256': 'hash'} for name in ('Reviewer A', ' reviewer a ')]
        with self.assertRaises(EvidenceError):
            check_team_reviews({'reviews': reviews}, 'hash')

    def test_unresolved_disagreement_blocks_eligibility(self):
        reviews = [{'decision': 'approve', 'reviewer': name, 'reasoning': 'reviewed',
                    'reviewed_definition_sha256': 'hash'} for name in ('a', 'b')]
        with self.assertRaises(EvidenceError):
            check_team_reviews({'reviews': reviews, 'disagreement': 'conflicting expected answer', 'resolution': None}, 'hash')

    def test_approval_must_bind_current_frozen_gold(self):
        review = {'decision': 'approve', 'reviewer': 'r', 'reasoning': 'reviewed', 'reviewed_definition_sha256': 'old'}
        with self.assertRaises(EvidenceError):
            check_review(review, 'new')

    def test_twenty_frozen_new_candidates_have_zero_eligible_evaluations(self):
        result = heldout_status(ROOT / 'benchmarks/heldout/v2')
        self.assertEqual(result['task_instances'], 20)
        self.assertEqual(result['eligible'], [])
        self.assertEqual(result['evaluations'], 0)
        self.assertFalse(result['supervisor_approval_required'])


if __name__ == '__main__':
    unittest.main()
