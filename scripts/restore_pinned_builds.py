"""Restore the licensed recorded mgcrea build used by the historical runners.

The runner pins a hashed chunk filename. A newly built tsdown output may have a
different name. This copies retained upstream build bytes, not a mock or rewrite.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    upstream = ROOT / 'external/mcp-a2a'
    manifest = json.loads((upstream / 'pinned-build-manifest.json').read_bytes())
    for row in manifest['files']:
        source = upstream / 'pinned-dist' / row['path']
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256'] or len(raw) != row['bytes']:
            raise ValueError('Pinned upstream build has changed')
        target = upstream / 'dist' / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    print(json.dumps({'status': 'Completed', 'restored_pinned_build_files': len(manifest['files'])}))


if __name__ == '__main__':
    main()
