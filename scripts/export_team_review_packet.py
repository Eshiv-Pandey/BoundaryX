"""Export readable copies and blank teammate forms without changing frozen tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def encoded(value: object) -> str:
    return '```json\n' + json.dumps(value, indent=2, ensure_ascii=False) + '\n```\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for label, source in [('development', ROOT / 'benchmarks/development/human-review'),
                          ('heldout', ROOT / 'benchmarks/heldout/v2')]:
        folder = output / label
        folder.mkdir()
        raw = (source / 'tasks.json').read_bytes()
        definition_hash = hashlib.sha256(raw).hexdigest()
        tasks = json.loads(raw)['tasks']
        source_text = [f'# {label.title()} tasks: {len(tasks)} examples\n\n',
                       f'Canonical tasks.json SHA-256: {definition_hash}\n\n',
                       'Read the source and rules, then derive an answer before opening PROPOSED_GOLD.md. '
                       'Ambiguities are review findings; these proposals are not assumed correct.\n\n']
        gold = ['# Proposed gold: pending human review\n\n',
                'Compare after deriving your own answer. These are expected contract objects; '
                'flag ambiguous field names or differences from the actual output schema.\n\n']
        form = [f'# Independent {label} review\n\nReviewer name: \n\nDate: \n\n',
                'Completed independently before discussing with the other reviewer: \n\n',
                f'Definition hash to bind each decision: {definition_hash}\n\n',
                'Decision choices: approve / revise / uncertain. Reasons are required. '
                'Leave supervisor judgments out; she observes progress.\n\n']
        for number, task in enumerate(tasks, 1):
            source_text += [f'## {number}. {task["id"]}\n\n', task['definition'] + '\n\n',
                           'Source input:\n\n', encoded(task['source']), '\nRequired fields:\n\n',
                           encoded(task['required_fields']), '\nConstraints:\n\n', encoded(task['constraints']),
                           '\nSuccess criteria: ' + task['success_criteria'] + '\n\n',
                           'Protocol assumptions: ' + task['protocol_assumptions'] + '\n\n',
                           'Evidence requirements:\n\n', encoded(task['evidence_requirements']), '\n']
            gold += [f'## {number}. {task["id"]}\n\n', encoded(task['proposed_gold']), '\n']
            form += [f'## {number}. {task["id"]}\n\n',
                     'My derived expected answer or contract, before checking the key: \n\n',
                     'Clarity: \n\nConsistency: \n\nExpected-output logic: \n\nEvidence traceability: \n\n',
                     'Decision: \n\nReasoning: \n\nSuggested correction or missing evidence: \n\n',
                     'Reviewed definition SHA-256: \n\n']
        (folder / 'TASKS.md').write_text(''.join(source_text), encoding='utf8')
        (folder / 'PROPOSED_GOLD.md').write_text(''.join(gold), encoding='utf8')
        for reviewer in (1, 2):
            (folder / f'reviewer-{reviewer}.md').write_text(''.join(form), encoding='utf8')
        (folder / 'canonical').mkdir()
        shutil.copyfile(source / 'tasks.json', folder / 'canonical/tasks.json')
        shutil.copyfile(source / 'review-decisions.json', folder / 'canonical/review-decisions.json')
    evidence = output / 'development/evidence'
    evidence.mkdir()
    for kind in ('text', 'data', 'file', 'image'):
        name = f'{kind}--r0--mgcrea_typed.json'
        shutil.copyfile(ROOT / 'runs/supervisor-handoff-20261113/parts-main-001/cells' / name, evidence / name)
    (output / 'development/EVIDENCE.md').write_text(
        '# Evidence for review\n\n'
        'The four evidence/ JSON files are actual historical artifact captures, including native reads, '
        'typed bridge views and same-task raw recovery. They are observations, not new reviewer executions.\n\n'
        'The ten original contracts come from benchmark/loss-v1/development-cases.json. '
        'Their exact inputs and proposed expectations are in canonical/tasks.json. '
        'The ten representation/evidence examples are logic proposals: no separate protocol execution '
        'of these exact examples is claimed. Record missing evidence instead of inventing it.\n\n'
        'With private repository access, inspect the source contracts, src/boundaryx/verification/semantic.py '
        'and docs/EXPERIMENT_PROTOCOL.md. Derive your answer before reading implementations. '
        'The legacy runner/verifier share critical logic; the separate verifier shares definitions and '
        'observations. Neither substitutes for teammate judgment.\n', encoding='utf8')
    (output / 'supervisor').mkdir()
    progress = (ROOT / 'docs/PROGRESS_FOR_SUPERVISOR.md').read_text(encoding='utf8')
    progress = progress.replace('(FINAL_REPORT.md)', '(https://github.com/Eshiv-Pandey/BoundaryX/blob/main/docs/FINAL_REPORT.md)')
    progress = progress.replace('../reports/supervisor-20261113/images/artifact-survival.png', 'artifact-survival.png')
    (output / 'supervisor/PROGRESS.md').write_text(progress, encoding='utf8')
    shutil.copyfile(ROOT / 'reports/supervisor-20261113/images/artifact-survival.png',
                    output / 'supervisor/artifact-survival.png')
    guide = (ROOT / 'docs/TEAM_REVIEW_GUIDE.md').read_text(encoding='utf8')
    guide = guide.replace('../reviews/team/README.md', 'README.md').replace('PROGRESS_FOR_SUPERVISOR.md', 'supervisor/PROGRESS.md')
    for document in ('ARCHITECTURE.md', 'METRICS.md', 'EXPERIMENT_PROTOCOL.md', 'LIMITATIONS.md'):
        guide = guide.replace('(' + document + ')', '(https://github.com/Eshiv-Pandey/BoundaryX/blob/main/docs/' + document + ')')
    (output / 'GUIDE.md').write_text(guide, encoding='utf8')
    shutil.copyfile(ROOT / 'benchmarks/review-policy.json', output / 'review-policy.json')
    (output / 'README.md').write_text(
        '# BoundaryX team review packet\n\n'
        'Start with development/TASKS.md and your own reviewer-1.md or reviewer-2.md. '
        'Derive answers independently, then compare development/PROPOSED_GOLD.md. '
        'Return your completed form with a name, definition hash, decision and reasons. '
        'Do not fill approvals just because tests pass.\n\n'
        'Review the twenty heldout proposals separately after the first development review. '
        'Their definitions/gold are frozen proposals, with zero evaluations. Corrections require a new freeze.\n\n'
        'The canonical/ files preserve exact machine-readable task definitions and blank decision forms. '
        'The two Markdown reviewer files are separate blank copies, not completed reviews.\n\n'
        'Supervisor: share supervisor/PROGRESS.md and its figure only. '
        'She observes progress; no approval or signature is required.\n\n'
        '[Full review instructions](GUIDE.md)\n',
        encoding='utf8')
    rows = [{'path': p.relative_to(output).as_posix(), 'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(output.rglob('*')) if p.is_file()]
    (output / 'manifest.json').write_text(json.dumps({'schema_version': 'boundaryx_manifest_v1', 'files': rows}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'status': 'Completed', 'development_tasks': 24, 'heldout_proposals': 20,
                      'judgments_filled': False, 'supervisor_role': 'progress_observer'}))


if __name__ == '__main__':
    main()
