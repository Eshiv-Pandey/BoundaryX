"""Two-profile harness checks; no frozen 66-profile matrix is executed."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from interoperability import benchmark
from interoperability import direct_comparison_v2 as comparison
from test_direct_goal_pruned_v2 import off_goal


def files(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


class DirectComparisonHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cases = []
        for index, succeeds in enumerate((True, False)):
            model = off_goal(succeeds=succeeds)
            model['id'] = f'harness-{index}'
            name = f'profile-{index}.json'
            (cls.base / name).write_text(json.dumps(model), encoding='utf-8')
            cases.append({'path': name, 'family': 'focused-off-goal'})
        cls.suite = cls.base / 'suite.json'
        cls.suite.write_text(json.dumps({'schema_version': 'admission-benchmark-suite/1',
            'id': 'two-profile-harness', 'split': 'development', 'evaluation_clock': 100, 'cases': cases}), encoding='utf-8')
        cls.before_adapter = benchmark.ADAPTERS[comparison.SCHEMA]
        cls.before_configuration = deepcopy(benchmark.ADAPTERS)
        cls.bundle = cls.base / 'comparison'
        cls.result = comparison.run(cls.suite, cls.bundle, work_budget=100000, timeout_seconds=10.0)
        cls.original_files = files(cls.bundle)

    def rows(self, directory=None):
        return [json.loads(line) for line in ((directory or self.bundle) / 'results.jsonl').read_bytes().splitlines()]

    def test_all_three_methods_and_correct_checker_are_captured_and_charged(self):
        execution = json.loads((self.bundle / 'execution.json').read_bytes())
        self.assertEqual(execution['schema_adapter'], comparison.ADAPTER)
        self.assertEqual([x['name'] for x in execution['algorithms']], ['baseline', 'direct_pruned', 'candidate'])
        self.assertEqual(execution['schema_adapter']['reference'], comparison.LEGACY)
        self.assertEqual(self.result['summary']['all_invocation_timing']['invocations'], 14)
        checked = comparison.verify(self.bundle)
        self.assertEqual(checked['certificate_jobs_bound'], 6)
        self.assertEqual(checked['entrypoint'], comparison.ENTRYPOINT)
        self.assertEqual(checked['entrypoint_source']['sha256'],
                         hashlib.sha256(Path(comparison.__file__).read_bytes()).hexdigest())
        self.assertEqual(checked['checker_source']['path'],
                         'source/interoperability/direct_goal_pruned_v2.py')

    def test_new_negative_and_old_proof_kinds_are_accepted_by_captured_checker(self):
        rows = self.rows()
        self.assertEqual([r['case_id'] for r in rows], ['harness-0', 'harness-1'])
        for row, decision in zip(rows, ('supported', 'unsupported')):
            for name, arm in row['algorithms'].items():
                self.assertEqual(arm['execution']['result']['decision'], decision)
                self.assertTrue(arm['certificate_valid'], (name, arm))
        negative = rows[1]['algorithms']
        self.assertEqual(negative['baseline']['execution']['result']['certificate']['kind'], 'relational-exhaustion')
        self.assertEqual(negative['direct_pruned']['execution']['result']['certificate']['kind'],
                         'goal-pruned-relational-exhaustion/2')
        self.assertEqual(negative['candidate']['execution']['result']['certificate']['kind'], 'refinement-exhaustion')
        for index in range(2):
            for name in ('baseline', 'direct_pruned', 'candidate'):
                job = json.loads((self.bundle / f'jobs/case-{index:04d}-{name}-certificate/input.json').read_bytes())
                self.assertEqual(job['module'], comparison.CHECKER)

    def test_adapter_does_not_leak_after_success_or_failure(self):
        self.assertIs(benchmark.ADAPTERS[comparison.SCHEMA], self.before_adapter)
        self.assertEqual(benchmark.ADAPTERS, self.before_configuration)
        with patch.object(benchmark, 'run_benchmark', side_effect=RuntimeError('inert runner failure')):
            with self.assertRaisesRegex(RuntimeError, 'inert runner failure'):
                comparison.run(self.suite, self.base / 'failed-allocation')
        self.assertIs(benchmark.ADAPTERS[comparison.SCHEMA], self.before_adapter)
        self.assertEqual(benchmark.ADAPTERS, self.before_configuration)

    def test_existing_allocation_is_refused_without_mutation(self):
        with self.assertRaises(ValueError):
            comparison.run(self.suite, self.bundle)
        with self.assertRaises(ValueError):
            comparison.replay(self.bundle, self.bundle)
        self.assertEqual(files(self.bundle), self.original_files)

    def test_replay_imports_captured_entrypoint_and_registers_checker_again(self):
        target = self.base / 'replay'
        with patch.object(benchmark, 'replay_benchmark', side_effect=AssertionError('old replay used')):
            result = comparison.replay(self.bundle, target)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['source_package'], str(self.bundle / 'source/interoperability'))
        self.assertEqual(result['verification']['checker'], comparison.CHECKER)
        self.assertEqual(result['verification']['certificate_jobs_bound'], 6)
        for first, repeated in zip(self.rows(), self.rows(target)):
            self.assertEqual(first['model_sha256'], repeated['model_sha256'])
            self.assertEqual(first['evaluation_clock'], repeated['evaluation_clock'])
            for name in ('baseline', 'direct_pruned', 'candidate'):
                a, b = first['algorithms'][name], repeated['algorithms'][name]
                self.assertEqual(a['execution']['result']['decision'], b['execution']['result']['decision'])
                self.assertEqual(a['execution']['result']['certificate'], b['execution']['result']['certificate'])
                self.assertEqual(a['certificate_valid'], b['certificate_valid'])
        self.assertEqual(files(self.bundle), self.original_files)
        self.assertIs(benchmark.ADAPTERS[comparison.SCHEMA], self.before_adapter)
        self.assertEqual(benchmark.ADAPTERS, self.before_configuration)

    def test_verification_does_not_execute_algorithm_or_mutate_bundle(self):
        with patch.object(benchmark, '_invoke', side_effect=AssertionError('algorithm execution during verify')):
            result = comparison.verify(self.bundle)
        self.assertEqual(result['status'], 'passed')
        self.assertFalse(result['fresh_algorithm_execution'])
        self.assertEqual(files(self.bundle), self.original_files)


if __name__ == '__main__':
    unittest.main()
