"""Prepare provisional review materials. This never executes an evaluation."""
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from boundaryx.core.evidence import digest, publish, read


def task(identifier, definition, source, expected, constraints, success, evidence):
    return {'id': identifier, 'definition': definition, 'source': source,
            'proposed_gold': expected, 'gold_status': 'Pending Human Review',
            'required_fields': list(expected) if isinstance(expected, dict) else ['full_output'],
            'constraints': constraints, 'success_criteria': success,
            'protocol_assumptions': 'A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.',
            'evidence_requirements': evidence}


def blank_review():
    return {'reviewer': None, 'decision': None, 'reasoning': None,
            'clarity': None, 'consistency': None, 'expected_output_logic': None,
            'evidence_traceability': None, 'reviewed_definition_sha256': None}


def main():
    bank = read(ROOT / 'benchmark/loss-v1/development-cases.json')
    examples = []
    for case in bank['cases']:
        examples.append(task('development-' + case['case_id'], 'Apply the frozen ' + case['task']['kind'] + ' predicate to the declared source records.',
                             {'task': case['task'], 'records': case['records']}, case['gold'], case['task']['constraints'],
                             'Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.',
                             ['source and sent/received payloads', 'actual receiver answer', 'state/read observations', 'original allocation and hashes']))
    artifacts = read(ROOT / 'runs/supervisor-handoff-20261113/parts-main-001/allocation.json')['specifications']
    for spec in artifacts:
        examples.append(task('development-artifact-' + spec['id'], spec['requirement'], {'command': spec['command']}, spec['expected'],
                             {'same_task_recovery': True, 'uri_fetch_required': False}, 'Exact payload and every required metadata field survive, or the authorized raw read restores them on the original task.',
                             ['public send/get bytes', 'task/context association', 'artifact projection', 'raw recovery read if eligible']))
    for index, (source, expected, definition) in enumerate([
        ({'x': None}, {'x': None}, 'Retain a present JSON null and distinguish it from an omitted field.'),
        ({'x': False, 'y': 0}, {'x': False, 'y': 0}, 'Preserve Boolean and integer types without coercion.'),
        ({'items': ['a', 'a', 'b']}, {'items': ['a', 'a', 'b']}, 'Preserve duplicate record multiplicity and array order.'),
        ({'task_id': 'first', 'context_id': 'shared'}, {'task_id': 'first', 'context_id': 'shared'}, 'Bind a reread to the original task rather than a new task in the same context.'),
        ({'budget': 0}, {'budget': 0}, 'Retain a zero operation budget as a measured constraint.'),
        ({'allowed_tools': ['read'], 'forbidden': ['write']}, {'allowed_tools': ['read'], 'forbidden': ['write']}, 'Preserve the allowed tool and forbidden effect requirements.'),
        ({'bytes_b64': 'AAH/'}, {'bytes_b64': 'AAH/'}, 'Preserve exact inline binary bytes in base64 form.'),
        ({'uri': 'https://example.invalid/a', 'fetch': False}, {'uri': 'https://example.invalid/a', 'fetch': False}, 'Preserve an artifact URI without treating it as proof of successful retrieval.'),
        ({'captured': False, 'value': None}, {'status': 'unknown'}, 'Report an uncaptured boundary as unknown instead of observed omission.'),
        ({'tools': ['read'], 'read_probe': None}, {'usability': 'unknown'}, 'Do not infer capability usability from a tool advertisement alone.'),
    ]):
        examples.append(task(f'development-contract-{index+1:02}', definition, source, expected,
                             {'read_only': True}, 'Apply the stated representation or evidence rule without imputing missing observations.',
                             ['original input', 'boundary capture or explicit absence of capture', 'declared comparison rule']))
    reviews = {t['id']: {'reviews': [blank_review(), blank_review()], 'disagreement': None,
                         'resolution': None} for t in examples}
    publish(ROOT / 'benchmarks/development/human-review/tasks.json', {'status': 'Pending Human Review', 'tasks': examples})
    publish(ROOT / 'benchmarks/development/human-review/review-decisions.json', {'status': 'Pending Human Review', 'tasks': reviews})

    candidates = []
    def add(*args):
        candidates.append(task(f'heldout-{len(candidates)+1:02}', *args))
    evidence = ['frozen source/task/gold proposal hashes', 'source/sent/received captures', 'task/context binding', 'actual final output and any tool/effect evidence']
    add('Stable multi-key sorting: category ascending, score descending, equal keys retain source order.',
        {'rows': [{'id':'r1','category':'b','score':2},{'id':'r2','category':'a','score':3},{'id':'r3','category':'a','score':3},{'id':'r4','category':'a','score':1}]},
        {'ordered_ids':['r2','r3','r4','r1']}, {'stable_ties':True}, 'Retain every row exactly once in the specified order.', evidence)
    add('Union half-open intervals; overlapping or touching intervals merge, gaps stay separate.',
        {'intervals':[[1,4],[3,7],[7,8],[10,12]]}, {'intervals':[[1,8],[10,12]]}, {'half_open':True}, 'Return the exact disjoint union.', evidence)
    add('Compute a two-line invoice with exact decimal arithmetic and round the final sum to two decimals using half-even.',
        {'lines':[{'quantity':3,'unit_price':'0.105'},{'quantity':2,'unit_price':'1.20'}]}, {'total':'2.72','currency':'USD'}, {'currency':'USD','rounding':'ROUND_HALF_EVEN'}, 'Do not round individual lines or use binary-float display as the gold.', evidence)
    add('Composite-key many-to-many join, retaining all match multiplicities and source left/right order.',
        {'left':[{'k':['a',1],'id':'l1'},{'k':['a',1],'id':'l2'}], 'right':[{'k':['a',1],'id':'r1'},{'k':['a',1],'id':'r2'},{'k':['a',2],'id':'r3'}]},
        {'pairs':[['l1','r1'],['l1','r2'],['l2','r1'],['l2','r2']]}, {'key_fields':['name','revision']}, 'Match composite keys with no duplicate collapse.', evidence)
    add('Merge independent edits to a base object and explicitly report a same-field conflict.',
        {'base':{'x':1,'y':2},'left':{'x':3,'y':2},'right':{'x':4,'y':5}}, {'merged':{'y':5},'conflicts':{'x':{'base':1,'left':3,'right':4}}}, {'no_silent_conflict_resolution':True}, 'Retain competing values and provenance rather than selecting an arbitrary winner.', evidence)
    add('Correlate interleaved tasks sharing a context; task identity takes precedence over arrival order.',
        {'context':'ctx','tasks':[{'id':'A','expected':'alpha'},{'id':'B','expected':'beta'}],'received':[{'task':'B','answer':'beta'},{'task':'A','answer':'alpha'}]},
        {'A':'alpha','B':'beta'}, {'cross_task_contamination':False}, 'Produce the original task association for each answer.', evidence)
    add('Validate a strict Boolean field and reject an integer value without coercion.',
        {'schema':{'flag':'boolean','additional_fields':False},'payload':{'flag':1}}, {'valid':False,'reason':'flag_type'}, {'coercion':False}, 'A numeric one is not the declared Boolean type.', evidence)
    add('Enforce a per-task zero write budget despite an advertised writable tool.',
        {'advertised_tools':['read','write'],'task_budget':{'writes':0},'requested':'write'}, {'authorized':False,'executed_writes':0}, {'writes':0}, 'Refuse the forbidden call and retain observable evidence of no execution; protocol acknowledgment is insufficient.', evidence)
    text='π\n'
    add('Preserve a UTF-8 text artifact together with its exact byte length and SHA-256.', {'text':text,'encoding':'utf-8'}, {'text':text,'bytes':len(text.encode()),'sha256':digest(text.encode())}, {'byte_equality':True}, 'Retain both original bytes and declared metadata.', evidence)
    entries={'a.txt':b'a','b.bin':b'\x00\xff'}
    add('Preserve a two-entry artifact manifest with mixed text/binary content and distinct file identities.',
        {'entries':{'a.txt':'YQ==','b.bin':'AP8='}}, {'manifest':[{'path':k,'bytes':len(v),'sha256':digest(v)} for k,v in entries.items()]}, {'file_order':['a.txt','b.bin']}, 'Keep both entries and verify every individual content digest.', evidence)
    add('Combine paginated records only when their snapshot versions agree.', {'pages':[{'version':7,'items':['a'],'next':'p2'},{'version':8,'items':['b'],'next':None}]}, {'status':'snapshot_conflict','versions':[7,8]}, {'single_snapshot':True}, 'Expose version inconsistency rather than silently combining records.', evidence)
    add('Deduplicate event retries by event identity while preserving the declared dependency order.', {'events':[{'id':'e2','after':'e1'},{'id':'e1','after':None},{'id':'e1','after':None}]}, {'ordered_event_ids':['e1','e2'],'retry_count':1}, {'identity_based_deduplication':True}, 'Distinguish a repeated observation from an additional effect.', evidence)
    add('Intersect parent and child authorization scopes without widening either.', {'parent':['read','list'],'child':['read','write']}, {'effective':['read']}, {'scope_rule':'intersection'}, 'A child request cannot add parent-forbidden capabilities.', evidence)
    add('Convert measurements using explicit rational unit factors and retain measurement identities.', {'measurements':[{'id':'x','millimetres':1250},{'id':'y','millimetres':-500}]}, {'metres':[{'id':'x','value':'1.25'},{'id':'y','value':'-0.5'}]}, {'factor':'1/1000'}, 'Preserve sign, units and record association without hidden rounding.', evidence)
    add('Convert an explicit-offset leap-day timestamp to UTC without changing the instant.', {'timestamp':'2024-02-29T23:30:00+05:30'}, {'utc':'2024-02-29T18:00:00Z'}, {'timezone_required':True}, 'Preserve the exact instant and timezone provenance.', evidence)
    add('Aggregate rational quantities exactly, returning a reduced rational fraction.', {'quantities':['1/3','1/6','-1/4']}, {'sum':str(Fraction(1,3)+Fraction(1,6)-Fraction(1,4))}, {'arithmetic':'rational'}, 'Return 1/4, with no decimal tolerance substitution.', evidence)
    add('Preserve original Unicode code points and provide a separately labeled NFC view.', {'original':'e\u0301'}, {'original':'e\u0301','nfc':'\u00e9'}, {'original_must_not_be_replaced':True}, 'Do not silently normalize the original artifact.', evidence)
    add('Reject a schema downgrade that would drop a required v2 integrity field.', {'source_version':2,'receiver_version':1,'payload':{'body':'abc','integrity':'required'}}, {'status':'incompatible_schema','lost_required_fields':['integrity']}, {'lossy_downgrade_allowed':False}, 'Report the incompatibility with evidence rather than a partial successful delivery.', evidence)
    add('Keep artifact URI identity and retrieval status separate when retrieval evidence is absent.', {'uri':'https://example.invalid/private/report','owner_task':'task-u','retrieval_capture':None}, {'uri':'https://example.invalid/private/report','owner_task':'task-u','retrieval_status':'unknown'}, {'do_not_fetch_remote_uri':True}, 'Preserve the reference and do not invent successful access.', evidence)
    add('Preserve a nested artifact attachment reference chain and its originating task.', {'task':'root-task','artifact':{'id':'main','attachments':[{'id':'aux','parent':'main','uri':'urn:artifact:aux'}]}}, {'task':'root-task','edges':[['main','aux']],'uri_bindings':{'aux':'urn:artifact:aux'}}, {'no_reference_rebinding':True}, 'Retain the origin, child identity and URI association.', evidence)
    heldout=ROOT/'benchmarks/heldout/v1'
    publish(heldout/'tasks.json',{'schema_version':'boundaryx_heldout_candidates_v1','status':'Pending Human Review',
                               'design':'Twenty new task structures, not identifier or timestamp variations of the ten historical development templates.',
                               'authorship':'AI-assisted task proposals; not independently authored human gold.', 'executed':False,'tasks':candidates})
    decisions={t['id']:{'reviews':[blank_review(),blank_review()], 'disagreement':None,'resolution':None} for t in candidates}
    publish(heldout/'review-decisions.json',{'status':'Pending Human Review','tasks':decisions})
    publish(heldout/'freeze.json',{'schema_version':'boundaryx_freeze_v1','frozen_utc':datetime.now(timezone.utc).isoformat(),
                                 'task_instances':20,'executed':False,'gold_status':'proposed, not established',
                                 'tasks_sha256':digest((heldout/'tasks.json').read_bytes()),
                                 'rule':'Changes to task definitions or proposed gold require a new version/freeze before execution. Mutable review decisions are outside the definition manifest.'})
    publish(heldout/'manifest.json',{'schema_version':'boundaryx_manifest_v1','files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in [heldout/'tasks.json',heldout/'freeze.json']]})
    print(json.dumps({'development_review_tasks':len(examples),'heldout_candidates':len(candidates),'evaluations':0,'status':'Pending Human Review'}))


if __name__=='__main__':
    main()
