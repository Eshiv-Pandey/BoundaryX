"""Documented distribution-only redaction of machine command/configuration paths.

Canonical original execution files are retained under ignored results/local.
Protocol payloads and source snapshots are not edited. Manifest digest chains
are re-established for the distributed copies, with original hashes recorded.
"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from boundaryx.core.evidence import digest


def main():
    replacements=[(str(ROOT),'<workspace>'),(str(ROOT.parent/'Ai_Interoperability'),'<legacy-workspace>'),
                  (str(Path(sys.executable).parent),'<python-install>')]
    changes=[]
    backup=ROOT/'results/local/distribution-originals'
    def strings(value):
        if isinstance(value,dict):return {k:strings(v) for k,v in value.items()}
        if isinstance(value,list):return [strings(v) for v in value]
        if isinstance(value,str):
            for source,target in replacements:
                for spelling in (source,source.replace('\\','/'),source.replace('\\','\\\\')):
                    value=value.replace(spelling,target)
        return value
    def replace(path,raw):
        before=path.read_bytes()
        if before==raw:return
        relative=path.relative_to(ROOT)
        old=backup/relative
        old.parent.mkdir(parents=True,exist_ok=True)
        if not old.exists():old.write_bytes(before)
        path.write_bytes(raw)
        changes.append({'path':relative.as_posix(),'original_sha256':digest(before),'distributed_sha256':digest(raw),
                        'scope':'machine command/configuration strings or dependent provenance hashes only'})
    files=[p for p in (ROOT/'results/development').rglob('*') if p.is_file() and p.suffix in ('.json','.txt')]
    for p in files:
        before=p.read_bytes()
        try:
            if p.suffix=='.json':
                value=json.loads(before)
                after=strings(value)
                if value!=after:replace(p,(json.dumps(after,indent=2,ensure_ascii=False)+'\n').encode())
            else:
                text=before.decode('utf8');after=strings(text)
                if text!=after:replace(p,after.encode())
        except (UnicodeError,ValueError):continue
    # Hash inner manifests before outer manifests that include their bytes.
    for p in sorted([p for p in files if p.name=='manifest.json'],key=lambda p:len(p.parts),reverse=True):
        value=json.loads(p.read_bytes()); changed=False
        for row in value.get('files',[]):
            target=p.parent/row['path']
            if not target.is_file():continue
            raw=target.read_bytes()
            if row['sha256']!=digest(raw) or row['bytes']!=len(raw):
                row['sha256']=digest(raw);row['bytes']=len(raw);changed=True
        if changed:replace(p,(json.dumps(value,indent=2)+'\n').encode())
    document=ROOT/'research/admission/docs/response-binding-design-v1.md'
    before=document.read_text(encoding='utf8');after=strings(before)
    if before!=after:replace(document,after.encode())
    ledger=ROOT/'provenance/distribution-derivatives.json'
    existing=json.loads(ledger.read_bytes()) if ledger.exists() else {'schema_version':'boundaryx_distribution_derivatives_v1','changes':[]}
    existing['changes']+=changes
    existing['scientific_values_changed']=False
    existing['original_location']='ignored results/local/distribution-originals; original research archive unchanged'
    ledger.write_text(json.dumps(existing,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':'Completed','documented_derivatives':len(changes),'scientific_values_changed':False}))


if __name__=='__main__':
    main()
