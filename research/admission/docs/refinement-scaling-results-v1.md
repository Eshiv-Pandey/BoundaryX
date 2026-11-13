# Refinement development scaling results, v1

**Comparison correction, 29 October:** this retained matrix used a direct
comparator that expanded definitely off-goal relations. Its low-budget
differences therefore do not establish a candidate algorithm advantage. The
[fairness review](direct-goal-pruning-fairness-v2.md) explains the defect and
the versioned goal-pruned comparator. The original run files and outcomes
below remain unchanged; the new comparison uses the same 66 input profiles.

The implemented generator and benchmark completed 66 authored profiles at four fixed work allowances, using identical profile bytes, logical clock 100 and one frozen package for both solvers and the reference. All four benchmark bundles passed the existing CLI verifier. A separate reconciliation checked all 1,145 worker jobs and all bundle hashes; measured artifacts remained unchanged.

Every conclusive result below has an independently accepted certificate: 353 checks total, zero rejections, zero checker errors/exhaustions, and no failed/timed-out or input-mutating workers. These are development results; they add no held-out cases, application-domain qualification or novelty evidence.

## Overall outcomes

S/U/? means supported/unsupported/unknown. Certified coverage counts only checker-accepted conclusive results, with all 66 cases as the denominator.

| Work allowance | Direct S/U/? | Candidate S/U/? | Direct certified coverage | Candidate certified coverage |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 8/4/54 | 16/8/42 | 12/66 (18.2%) | 24/66 (36.4%) |
| 256 | 27/25/14 | 27/23/16 | 52/66 (78.8%) | 50/66 (75.8%) |
| 4,096 | 28/26/12 | 28/25/13 | 54/66 (81.8%) | 53/66 (80.3%) |
| 100,000 | 28/26/12 | 28/26/12 | 54/66 (81.8%) | 54/66 (81.8%) |

At 100,000 units, both implementations match all 66 authored sufficient-budget expectations: 28 supported, 26 unsupported and 12 unknown. The 12 unknown profiles retain opaque relations; expected labels are authored finite-semantic assertions, not application gold.

At allowance 32, 12 candidate certificates were accepted while the budgeted reference/direct solver abstained; at 256 this occurred twice. Those reference abstentions remain unknown. Conversely, the candidate abstained on four reference-decided cases at 256 and one at 4,096. Expected labels, budgeted reference decisions and independent certificate acceptance remain separate in the retained case records.

## Outcomes by family

Each cell lists `direct S/U/?; candidate S/U/?`. All S and U counts in this table are certificate-validated.

| Family (cases) | Allowance 32 | Allowance 256 | Allowance 4,096 | Allowance 100,000 |
| --- | --- | --- | --- | --- |
| Argument product (16) | 6/2/8; 6/2/8 | 8/4/4; 8/4/4 | 8/4/4; 8/4/4 | 8/4/4; 8/4/4 |
| Layered reconvergence (16) | 0/0/16; 1/0/15 | 4/8/4; 3/5/8 | 4/8/4; 4/7/5 | 4/8/4; 4/8/4 |
| Correlated frames (16) | 0/0/16; 1/0/15 | 8/4/4; 8/4/4 | 8/4/4; 8/4/4 | 8/4/4; 8/4/4 |
| Horizon boundary (6) | 2/1/3; 4/2/0 | 4/2/0; 4/2/0 | 4/2/0; 4/2/0 | 4/2/0; 4/2/0 |
| Off-goal load (12) | 0/1/11; 4/4/4 | 3/7/2; 4/8/0 | 4/8/0; 4/8/0 | 4/8/0; 4/8/0 |

## Two mechanism differences

- **Reconvergent refutation, scale-0031:** width four and depth four create 256 abstract paths to a false final relation. At allowance 4,096, the direct solver certifies unsupported while the candidate exhausts its budget. At 100,000, both certify unsupported; the candidate records 256 lifted paths, 256 refinements and 1,024 relation checks, while the direct solver records four product states and 16 argument assignments.
- **Off-goal work, scale-0064:** four dead branches each contain a 16-assignment product, followed by a separate goal edge. At allowance 256, the candidate certifies supported while the direct solver exhausts its budget. At 100,000, both certify supported; the candidate records one relation check while the direct solver records 65 argument assignments.

These results expose different costs of lazy path lifting and shared relational search. Equal integer allowances charge different internal operations, so the counters are not interchangeable primitive costs. Both favorable and unfavorable candidate cases are retained. Other root live-work may have contended for CPU; no wall-clock speed superiority is claimed. All evaluation, startup and certificate-check timings remain in the raw summaries, including every abstention and all reference invocations. The reference and direct baseline are the same implementation.

## Retained evidence

- [Prospective matrix plan](../../runs/refinement-scaling/v1/plan-v2.json) and [frozen inputs/labels manifest](../../runs/refinement-scaling/v1/inputs/manifest.json). All four budget allocations and package hashes were fixed before evaluation.
- [Complete matrix results](../../runs/refinement-scaling/v1/result.json), including per-family reasons, per-case counters, checking costs and raw evidence references.
- [Reconciliation result](../../runs/refinement-scaling/v1/post-review/result.json), with exact before/after inventories beside it. This was an AI evidence review, not human review.
- Raw verified summaries: [32](../../runs/refinement-scaling/v1/budget-32/summary.json), [256](../../runs/refinement-scaling/v1/budget-256/summary.json), [4,096](../../runs/refinement-scaling/v1/budget-4096/summary.json), [100,000](../../runs/refinement-scaling/v1/budget-100000/summary.json).
