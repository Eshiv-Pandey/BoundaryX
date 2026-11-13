"""Redact scan-identified configuration paths and rebind dependent digests.

Canonical captures stay local. Evaluated v2 task cells cannot be edited by this
operation. Configuration/setup observations are explicitly distribution copies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan-report', type=Path, required=True)
    args = parser.parse_args()
    scan = json.loads(args.scan_report.read_bytes())
    replacements = [(str(ROOT), '<workspace>'), (str(ROOT.parent/'Ai_Interoperability'), '<legacy-workspace>'),
                    (str(Path.home()), '<user-home>'), (str(Path(sys.executable).parent), '<python-install>')]
    ledger_path = ROOT/'provenance/distribution-derivatives.json'
    ledger = json.loads(ledger_path.read_bytes())
    changes = []
    digests = {}
    store = ROOT/'results/local/distribution-originals/by-sha256'
    store.mkdir(parents=True, exist_ok=True)

    def save(path, raw, scope):
        before = path.read_bytes()
        if before == raw:
            return
        name = path.relative_to(ROOT).as_posix()
        # All evaluated task cells and loss-scoring definitions remain exact.
        assert not any(s in name for s in ('/diagnostics-final-001/', '/protocol-main-001/cells/', '/parts-main-001/cells/'))
        original = sha(before)
        backup = store/original
        if not backup.exists():
            backup.write_bytes(before)
        path.write_bytes(raw)
        digests[original] = sha(raw)
        changes.append({'path': name, 'original_sha256': original, 'distributed_sha256': sha(raw),
                        'scope': scope, 'canonical_local_object': 'results/local/distribution-originals/by-sha256/'+original})

    def config(value):
        if isinstance(value, dict):
            out = {k: config(v) for k, v in value.items()}
            if isinstance(value.get('raw'), str) and out['raw'] != value['raw']:
                original = value['raw'].encode('utf8')
                raw = out['raw'].encode('utf8')
                if 'sha256' in value:
                    assert value['sha256'] == sha(original), 'Existing wire hash must be valid'
                    out['sha256'] = sha(raw)
                    digests[sha(original)] = sha(raw)
                if 'bytes' in value:
                    assert value['bytes'] == len(original), 'Existing wire length must be valid'
                    out['bytes'] = len(raw)
            return out
        if isinstance(value, list):
            return [config(v) for v in value]
        if isinstance(value, str):
            for source, target in replacements:
                for spelling in (source, source.replace('\\', '/'), source.replace('\\', '\\\\')):
                    value = value.replace(spelling, target)
        return value

    for finding in scan['issues']:
        if finding['kind'] != 'machine command/configuration path':
            continue
        path = ROOT/finding['path']
        before = path.read_bytes()
        if path.suffix == '.json':
            value = json.loads(before)
            after = config(value)
            raw = (json.dumps(after, indent=2, ensure_ascii=False)+'\n').encode('utf8') if value != after else before
        elif path.suffix == '.jsonl':
            raw = b''.join((json.dumps(config(json.loads(line)), ensure_ascii=False)+'\n').encode('utf8')
                           for line in before.splitlines() if line.strip())
        else:
            raw = config(before.decode('utf8')).encode('utf8')
        save(path, raw, 'Explicit configuration/command/setup distribution derivative; original observations preserved locally')

    # Rebind digest references until no dependent file changes. Only string
    # digest references change; numeric costs, judgments and gold do not.
    def references(value):
        if isinstance(value, dict):
            return {k: references(v) for k, v in value.items()}
        if isinstance(value, list):
            return [references(v) for v in value]
        if isinstance(value, str) and value in digests:
            visited = set()
            while value in digests:
                assert value not in visited, 'Digest reference cycle'
                visited.add(value)
                value = digests[value]
        return value

    pattern_file = ROOT/'results/local/distribution-digest-patterns.txt'
    for iteration in range(12):
        pattern_file.write_text('\n'.join(digests)+'\n', encoding='ascii')
        process = subprocess.run(['rg', '-l', '-F', '-f', str(pattern_file), '-g', '*.json', '-g', '*.jsonl',
                                  'benchmark', 'runs', 'reports', 'results/development'], cwd=ROOT, capture_output=True)
        assert process.returncode in (0, 1), process.stderr.decode()
        changed_before = len(changes)
        for name in process.stdout.decode('utf8').splitlines():
            path = ROOT/name
            before = path.read_bytes()
            if path.suffix == '.jsonl':
                values = [json.loads(line) for line in before.splitlines() if line.strip()]
                after = references(values)
                if values == after:
                    continue
                raw = b''.join((json.dumps(v, ensure_ascii=False)+'\n').encode('utf8') for v in after)
            else:
                value = json.loads(before)
                after = references(value)
                if value == after:
                    continue
                raw = (json.dumps(after, indent=2, ensure_ascii=False)+'\n').encode('utf8')
            save(path, raw, 'Dependent digest references only; scientific values unchanged')
        print(json.dumps({'digest_pass': iteration+1, 'total_derivatives': len(changes)}), flush=True)
        if len(changes) == changed_before:
            break
    else:
        raise RuntimeError('Digest graph did not stabilize')
    # Digests and file lengths in evidence manifests describe distribution bytes.
    for parent in ('runs', 'results/development'):
        for path in sorted((ROOT/parent).rglob('manifest.json'), key=lambda p: len(p.parts), reverse=True):
            prefix = path.parent.relative_to(ROOT).as_posix()+'/'
            if not any(c['path'].startswith(prefix) for c in changes):
                continue
            value = json.loads(path.read_bytes())
            changed = False
            for row in value.get('files', []):
                member = path.parent/row['path']
                raw = member.read_bytes()
                if row['sha256'] != sha(raw) or row['bytes'] != len(raw):
                    row['sha256'], row['bytes'] = sha(raw), len(raw)
                    changed = True
            if changed:
                save(path, (json.dumps(value, indent=2)+'\n').encode('utf8'), 'Manifest of explicitly distributed bytes')
    ledger['changes'] += changes
    ledger['historical_evaluated_v2_cells_changed'] = False
    ledger['scientific_values_changed'] = False
    ledger['configuration_wire_note'] = 'Setup/configuration packet hashes and sizes refer to redacted distribution bytes; task wire, answers, numerical experiment metrics and original canonical observations are preserved'
    ledger_path.write_text(json.dumps(ledger, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'status': 'Completed', 'additional_derivatives': len(changes)}))


if __name__ == '__main__':
    main()
