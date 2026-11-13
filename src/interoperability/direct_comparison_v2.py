"""Explicit three-method recipe comparison using the preserved benchmark engine.

The adapter override is scoped to one call and restored even on failure. All
workers, source/input capture and timing accounting remain the existing engine's
responsibility. Replay imports this entrypoint from the captured package before
registering the checker again; the old CLI replay is intentionally not used.

An external command receipt proves invocation. Bundle verification proves local
file consistency and the advertised method/checker configuration, not signed
execution provenance, statistical superiority or algorithmic novelty.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

from . import benchmark


ENTRYPOINT = 'interoperability.direct_comparison_v2'
SCHEMA = 'recipe-continuation/1'
CHECKER = 'interoperability.direct_goal_pruned_v2'
LEGACY = 'interoperability.refinement_oracle'
ADAPTER = {'baseline': LEGACY, 'reference': LEGACY, 'checker': CHECKER, 'supports_budget': True}
ALGORITHMS = (
    benchmark.AlgorithmSpec('baseline', LEGACY, input_schema=SCHEMA),
    benchmark.AlgorithmSpec('direct_pruned', CHECKER, input_schema=SCHEMA),
    benchmark.AlgorithmSpec('candidate', 'interoperability.refinement', input_schema=SCHEMA),
)


@contextmanager
def _adapter():
    previous = benchmark.ADAPTERS[SCHEMA]
    if (previous.get('baseline') != LEGACY or previous.get('reference') != LEGACY
            or previous.get('supports_budget') is not True):
        raise ValueError('Preserved recipe baseline/reference contract changed')
    benchmark.ADAPTERS[SCHEMA] = dict(ADAPTER)
    try:
        yield
    finally:
        benchmark.ADAPTERS[SCHEMA] = previous


def verify(directory: Path) -> dict:
    """Read-only bundle/configuration verification; never run a solver."""
    directory = Path(directory).resolve()
    checked = benchmark.verify_bundle(directory)
    execution = benchmark._json(directory / 'execution.json')
    if (execution['input_schema'] != SCHEMA or execution['schema_adapter'] != ADAPTER
            or execution['algorithms'] != [asdict(spec) for spec in ALGORITHMS]
            or execution['reference_implementation_is_baseline'] is not True):
        raise ValueError('Bundle does not declare the exact three-method recipe comparison')
    manifest = benchmark._json(directory / 'manifest.json')
    inventory = {row['path']: row for row in manifest['files']}
    runner_path = 'source/interoperability/direct_comparison_v2.py'
    checker_path = 'source/interoperability/direct_goal_pruned_v2.py'
    if runner_path not in inventory or checker_path not in inventory:
        raise ValueError('Comparison entrypoint/checker source is absent from the captured package')
    rows = [json.loads(line) for line in (directory / 'results.jsonl').read_bytes().splitlines()]
    checker_jobs = 0
    for index, row in enumerate(rows):
        # The engine's generic verifier binds cases, results and manifest bytes.
        # This entrypoint additionally binds the actual worker dispatch modules
        # to the exact explicitly advertised comparator/checker configuration.
        for name, module in [('reference', LEGACY)] + [(spec.name, spec.module) for spec in ALGORITHMS]:
            job = benchmark._json(directory / f'jobs/case-{index:04d}-{name}/input.json')
            if (job['kind'] != 'evaluate' or job['module'] != module or job['entrypoint'] != 'evaluate'
                    or job['now'] != execution['evaluation_clock']
                    or benchmark.digest(job['runtime_manifest']) != row['model_sha256']
                    or job['keyword_arguments'] != {'budget': execution['work_budget']}):
                raise ValueError('Evaluation worker dispatch differs from advertised comparison')
        for spec in ALGORITHMS:
            arm = row['algorithms'][spec.name]
            if 'certificate_check' not in arm:
                continue
            job = benchmark._json(directory / f'jobs/case-{index:04d}-{spec.name}-certificate/input.json')
            if (job['kind'] != 'certificate' or job['module'] != CHECKER or job['entrypoint'] != 'check_certificate'
                    or job['now'] != execution['evaluation_clock']
                    or benchmark.digest(job['runtime_manifest']) != row['model_sha256']
                    or job['result'] != arm['execution']['result']):
                raise ValueError('Certificate worker dispatch differs from advertised checker/result')
            checker_jobs += 1
    return {**checked, 'schema_version': 'direct-comparison-verification/2',
            'entrypoint': ENTRYPOINT, 'entrypoint_source': inventory[runner_path],
            'checker': CHECKER, 'checker_source': inventory[checker_path],
            'algorithms': [asdict(spec) for spec in ALGORITHMS],
            'certificate_jobs_bound': checker_jobs,
            'benchmark_status': benchmark._json(directory / 'summary.json')['status'],
            'invocation_provenance': 'Use the external command receipt; captured source is not an invocation attestation.'}


def run(suite_path: Path, output: Path, *, work_budget=100000, timeout_seconds=30.0) -> dict:
    """Allocate a new bundle with three methods and the explicit proof checker."""
    suite_path, output = Path(suite_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite an existing comparison bundle')
    if type(work_budget) is not int or work_budget <= 0:
        raise ValueError('Require a positive explicit integer work budget')
    package = Path(__file__).resolve().parent
    with _adapter():
        _, cases = benchmark._suite(suite_path)
        if any(model['schema_version'] != SCHEMA for _, _, model in cases):
            raise ValueError('The versioned comparison accepts recipe-continuation/1 only')
        summary = benchmark.run_benchmark(suite_path, output, list(ALGORITHMS),
                                          work_budget=work_budget, timeout_seconds=timeout_seconds,
                                          package_dir=package)
    checked = verify(output)
    return {'schema_version': 'direct-comparison-run/2', 'status': summary['status'],
            'entrypoint': ENTRYPOINT, 'checker': CHECKER, 'source_package': str(package),
            'bundle': str(output), 'summary': summary, 'verification': checked,
            'claim_limit': 'Authored development comparison; no performance, novelty or domain-qualification claim.'}


def replay(directory: Path, output: Path) -> dict:
    """Execute the captured entrypoint, preserving checker registration on replay."""
    directory, output = Path(directory).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite an existing comparison replay')
    verify(directory)
    execution = benchmark._json(directory / 'execution.json')
    boot = (
        "import json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from interoperability.direct_comparison_v2 import run; "
        "d=Path(sys.argv[2]); e=json.loads((d/'execution.json').read_bytes()); "
        "r=run(d/'replay-suite.json',Path(sys.argv[3]),work_budget=e['work_budget'],"
        "timeout_seconds=e['timeout_seconds']); print(json.dumps(r)); "
        "raise SystemExit(0 if r['status']=='passed' else 1)"
    )
    cases = len(benchmark._json(directory / 'replay-suite.json')['cases'])
    timeout = 120 + cases * (1 + 2 * len(ALGORITHMS)) * execution['timeout_seconds']
    completed = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', boot,
        str(directory / 'source'), str(directory), str(output)], cwd=directory,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        raise ValueError('Captured comparison replay failed: '
                         + completed.stderr.decode('utf-8', errors='replace')[-4000:])
    result = json.loads(completed.stdout)
    if result['source_package'] != str(directory / 'source/interoperability'):
        raise ValueError('Replay did not report the captured comparison source package')
    result['verification'] = verify(output)
    result['replay_of'] = str(directory)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    execute = commands.add_parser('run')
    execute.add_argument('--suite', type=Path, required=True)
    execute.add_argument('--output', type=Path, required=True)
    execute.add_argument('--work-budget', type=int, default=100000)
    execute.add_argument('--timeout-seconds', type=float, default=30.0)
    check = commands.add_parser('verify')
    check.add_argument('directory', type=Path)
    repeat = commands.add_parser('replay')
    repeat.add_argument('directory', type=Path)
    repeat.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'run':
        result = run(args.suite, args.output, work_budget=args.work_budget,
                     timeout_seconds=args.timeout_seconds)
    elif args.command == 'verify':
        result = verify(args.directory)
    else:
        result = replay(args.directory, args.output)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
