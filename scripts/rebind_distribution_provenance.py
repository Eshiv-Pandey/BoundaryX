"""Rebind source-file hashes after documented command-path redaction.

Only the provenance references in old retained episode distribution copies may
change. All scientific episode fields must compare exactly before publication.
Canonical original bytes remain in the separate local preservation archive.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from boundaryx.core.evidence import digest, read
from scripts.build_loss_benchmark_retained_v1 import build_episodes


def main():
    retained=ROOT/'runs/loss-benchmark-retained-v1/20261112T112741770806Z-3326eed1/episodes.json'
    old=read(retained)
    new=build_episodes(ROOT/'benchmark/loss-v1/retained-inputs',ROOT/'benchmark/loss-v1/retained-manifest.json')
    assert len(old)==len(new)
    for before,after in zip(old,new):
        a,b=deepcopy(before),deepcopy(after)
        a.pop('source_files');b.pop('source_files')
        a['metadata'].pop('manifest_sha256');b['metadata'].pop('manifest_sha256')
        assert a==b,'Scientific values cannot change during distribution redaction'
    ledger=read(ROOT/'provenance/distribution-redactions.json')
    def replace(path,value):
        before=path.read_bytes()
        path.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
        ledger.setdefault('provenance_rebindings',[]).append({'path':path.relative_to(ROOT).as_posix(),'original_sha256':digest(before),'distributed_sha256':digest(path.read_bytes()),'scientific_values_unchanged':True})
    replace(retained,new)
    bundle=ROOT/'runs/loss-benchmark-v1/fresh-development-003'
    combined=read(bundle/'combined-episodes.json')
    assert combined[:len(old)]==old
    replace(bundle/'combined-episodes.json',new+combined[len(old):])
    for root in (retained.parent,bundle):
        path=root/'manifest.json'
        if not path.exists():continue
        manifest=read(path)
        for row in manifest['files']:
            p=root/row['path'];row['bytes']=p.stat().st_size;row['sha256']=digest(p.read_bytes())
        replace(path,manifest)
    (ROOT/'provenance/distribution-redactions.json').write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':'Completed','scientific_episode_values_unchanged':True,'rebound_provenance_only':True}))


if __name__=='__main__':main()
