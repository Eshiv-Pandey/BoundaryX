"""Capture actual new-code and installed upstream validation commands."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    env_bin = '.venv/Scripts' if __import__('os').name == 'nt' else '.venv/bin'
    executable = '.exe' if __import__('os').name == 'nt' else ''
    jobs = [
        ('lint', '.', [env_bin + '/ruff' + executable, 'check', '.']),
        ('types', '.', [env_bin + '/mypy' + executable]),
        ('new-controls', '.', ['python', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_boundaryx*.py', '-v']),
        ('frozen-heldout', '.', ['python', '-B', 'scripts/boundaryx.py', 'heldout-status']),
        ('amir-types', 'external/a2a-to-mcp', ['node', 'node_modules/typescript/bin/tsc', '--noEmit', '-p', 'tsconfig.json']),
        ('amir-integration', 'external/a2a-to-mcp', ['node', 'node_modules/vitest/vitest.mjs', 'run', 'test/integration/send-message.test.ts', 'test/integration/tasks-extension.test.ts']),
        ('mgcrea-types', 'external/mcp-a2a', ['node', 'node_modules/typescript/bin/tsc', '--noEmit']),
        ('mgcrea-lint', 'external/mcp-a2a', ['node', 'node_modules/oxlint/bin/oxlint']),
        ('mgcrea-tests', 'external/mcp-a2a', ['node', 'node_modules/vitest/vitest.mjs', 'run']),
    ]
    rows = []
    for name, cwd, command in jobs:
        started = datetime.now(timezone.utc).isoformat()
        began = time.perf_counter()
        try:
            process = subprocess.run(command, cwd=ROOT/cwd, capture_output=True, timeout=300)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b'', exc.stderr or b'', None
        except OSError as exc:
            stdout, stderr, code = b'', str(exc).encode(), None
        (args.output/(name+'-stdout.txt')).write_bytes(stdout)
        (args.output/(name+'-stderr.txt')).write_bytes(stderr)
        row = {'name':name,'command':command,'cwd':cwd,'started_utc':started,
               'completed_utc':datetime.now(timezone.utc).isoformat(),'exit_code':code,
               'wall_seconds':time.perf_counter()-began,'status':'passed' if code==0 else 'failed'}
        rows.append(row)
        print(json.dumps(row),flush=True)
    result={'schema_version':'boundaryx_validation_v1','status':'passed' if all(r['exit_code']==0 for r in rows) else 'failed','checks':rows}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    raise SystemExit(result['status']!='passed')


if __name__=='__main__':
    main()
