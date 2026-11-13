# Common end-to-end physical-cost development results v1

11 November 2026. The completed hosted comparison retained all 1,650 allocations
for the exact 66 authored development profiles, five unchanged methods and five
dependent timing repeats. Every allocation opened, closed and retained a
full-lifetime resource observation. The independent read auditor found no
archive, source, order, allocation, closure, reply or derived-summary mismatch.
It imported or executed no original worker, method, checker or coordinator.

Run: [42927208534](https://github.com/Eshiv-Pandey/Ai_Interoperability/actions/runs/42927208534),
attempt 1, source commit `d058c2a05e278b71ad5969e49ecdd344576cf166`.
The workflow completed successfully. Saved API metadata binds artifact
`13814891629` to that run and source revision. The retained ZIP is 9,438,211
bytes, SHA256 `bc84692b270eadb32ee80c0e1c4ac594606329542d6db0852c874287c894be23`;
the API digest, collector digest and independent archive digest agree.
All 11,634 archive members match their extracted bytes and extraction inventory.
All 1,730 pre-execution frozen protocol, order, source, profile, provenance,
driver and job records were verified. The declared order SHA256 remains
`0127c1298d519b551d0aa1b3cd016b25e1e2d94a05f93b2eef318f25b80fb9e8`.

The physical-cost protocol and fixed method names are documented in
[common-cost-benchmark-v1.md](common-cost-benchmark-v1.md). Primary costs include
interpreter startup, source/input loading, solver import/evaluation, fresh
independent checker import/checking, serialization/output and termination.
CPU and peak RSS come from the sole terminal Linux `wait4`; outer wall spans
launch through owned-group cleanup and reaping. Phase observations remain
secondary. RSS is the worker process's observed high-water mark, including the
solver and checker. The enforced 512 MiB address-space limit is `RLIMIT_AS`;
there is no claimed Linux RSS hard cap.

| Method | Allocations | Certified supported | Certified unsupported | Unknown | Failure / timeout / stopped / unstarted |
| --- | ---: | ---: | ---: | ---: | ---: |
| `legacy_direct` | 330 | 140 | 130 | 60 | 0 |
| `goal_pruned_direct` | 330 | 140 | 130 | 60 | 0 |
| `original_refinement` | 330 | 140 | 130 | 60 | 0 |
| `shared_lift` | 330 | 140 | 130 | 60 | 0 |
| `guard_pruned_direct` | 330 | 140 | 130 | 60 | 0 |

At the profile level, all five methods and all five repeats agree: 28 profiles
are captured as certified supported, 26 as certified unsupported and 12 remain
unknown. There are no contradictory certified supported/unsupported decisions
and no shared-hash-seed probe discrepancies. The 12 unknown profiles are
`scale-0004`, `0008`, `0012`, `0016`, `0020`, `0024`, `0028`, `0032`, `0036`,
`0040`, `0044` and `0048`. Direct variants report
`indeterminate_observables_or_relations`; the two refinement variants report
`unresolved_relation_or_recipe`. These 300 unknown cells remain in the census
with their actual CPU/wall/RSS observations. Their early or unresolved returns
do not enter cost ratios.

Each of the ten paired comparisons contains the same 54 profiles, with all five
paired repeats certified to the same decision and nonbinding declared
logical/CPU/wall limits. For each eligible profile, the auditor independently
reconstructs each method's five-repeat median, then divides the left median by
the right median. The table below descriptively summarizes those 54 profile
ratios by their median; it adds no population inference or confidence interval.
A ratio below 1 means the left method has lower observed cost for that metric.
Unrounded per-profile medians, ratios and every excluded-profile reason remain
in the linked audit artifact.

| Left method / right method | Profiles | Median CPU ratio | Median outer-wall ratio | Median peak-RSS ratio |
| --- | ---: | ---: | ---: | ---: |
| `legacy_direct` / `goal_pruned_direct` | 54 | 0.974 | 0.973 | 1.001 |
| `legacy_direct` / `original_refinement` | 54 | 1.054 | 1.059 | 1.015 |
| `legacy_direct` / `shared_lift` | 54 | 0.864 | 0.875 | 0.948 |
| `legacy_direct` / `guard_pruned_direct` | 54 | 0.949 | 0.947 | 0.999 |
| `goal_pruned_direct` / `original_refinement` | 54 | 1.079 | 1.088 | 1.012 |
| `goal_pruned_direct` / `shared_lift` | 54 | 0.885 | 0.897 | 0.948 |
| `goal_pruned_direct` / `guard_pruned_direct` | 54 | 0.973 | 0.973 | 0.997 |
| `original_refinement` / `shared_lift` | 54 | 0.820 | 0.826 | 0.936 |
| `original_refinement` / `guard_pruned_direct` | 54 | 0.900 | 0.895 | 0.985 |
| `shared_lift` / `guard_pruned_direct` | 54 | 1.099 | 1.088 | 1.053 |

For the shared-lifting versus strongest same-evidence goal-pruned direct
comparison, the following uses the explicit shared/direct direction. Each
profile still contributes the ratio of its two five-repeat medians. Counts
compare those medians within each of the 54 profiles.

| Metric | Median shared/direct ratio | Range | Shared lower / equal / higher |
| --- | ---: | --- | ---: |
| Lifetime CPU | 1.129994 | 1.114595 to 1.653363 | 0 / 0 / 54 |
| Outer wall | 1.114527 | 1.107784 to 1.659204 | 0 / 0 / 54 |
| Lifetime peak RSS | 1.055200 | 1.044020 to 1.066310 | 0 / 0 / 54 |

Shared lifting adds no certified profile coverage in this capture and has
higher observed CPU, wall and RSS medians than goal-pruned direct on every
eligible profile. The table supplies descriptive paired development evidence;
330 method allocations are not pooled as independent tasks for significance.

Shared lifting used more full-lifetime CPU, outer wall and peak RSS than original
refinement on every eligible profile in this capture: original/shared CPU ratios
range from 0.806 to 0.881, wall ratios from 0.805 to 0.883 and RSS ratios from
0.927 to 0.947. This is an observed end-to-end development tradeoff, not an
algorithmic superiority conclusion. Some other pairs cross 1 across profiles;
for example legacy/goal-pruned CPU ratios range from 0.962 to 1.024. Method
work units remain incomparable diagnostics and do not replace these costs.

The largest observed lifetime CPU was 123,820,000 ns; the largest outer wall was
126,743,173 ns; the largest lifetime peak RSS was 22,188,032 bytes. CPU and wall
observations are nonbinding relative to the declared CPU soft/hard limits of
5/6 seconds and 10-second outer wall limit. The largest recorded solver charge was 14,773
against the identical explicit 100,000,000 allowance.

The frozen worker records logical headroom using only `work_units < budget`.
The independent auditor additionally requires a retained raw result, the exact
allowance/counter types and a statically inspected method/decision reason with
no `work_budget_exhausted` outcome. An exhaustion reason overrides a below-cap
counter, and an unbound or unrecognized reason remains indeterminate. This
capture has no budget-exhaustion reason and no disagreement between the raw
labels and reason-aware classifications. All 1,650 solver results have verified
logical headroom. The conservative eligible cohorts equal the frozen runner's
recorded cohorts; the audit preserves both separately.

Captured certificate acceptance comes from the unchanged
`direct_goal_pruned_v2.check_certificate`, with a fresh package namespace and
fresh input/result copies in each measured child. Its fixed internal allowance
remains 2,000,000. The read audit verifies source, result and acceptance-receipt
binding, reply profile bytes and structural certificate profile, clock, horizon,
expiry and kind headers; it does not reexecute certificate semantics. A checker `False` would
remain an uncertified invalid-proof-or-soft-cap result, without becoming an
unsupported verdict. No such rejection occurred here. The recorded interpreter
identity is retained, but executable bytes are not archived for separate byte
verification by the auditor.

The hosted workflow passed its controls before the allocation and completed
execution, finalization and verification. The separate auditor passed nine
constructed controls covering saved API/archive/extracted identity, exact
source/jobs, full stopped census, known five-repeat medians, resource/status
corruption, malformed closure retention, exhaustion-reason precedence and
profile-wide contradiction quarantine and reply/certificate-header identity.
Constructed controls do not execute the
preserved benchmark methods or add method/checker attempts to the 1,650 cells.

Evidence:

- [Retained run and archive receipt](../../runs/common-cost-development/v1/retained-42927208534-1/retention.json)
- [Independent audit result and ten complete paired cohorts](../../runs/common-cost-development/v1/read-audit-42927208534-3/result.json)
- [All 1,650 cells, raw evidence identities, phases and cap reasons](../../runs/common-cost-development/v1/read-audit-42927208534-3/cells.jsonl)
- [Saved metadata, archive and complete member identities](../../runs/common-cost-development/v1/read-audit-42927208534-3/evidence-files.json)
- [Exact source retained for that audit](../../runs/common-cost-development/v1/read-audit-42927208534-3/auditor-source.py)
- [Standalone auditor](../../scripts/audit_common_cost_results_v1.py)
- [Constructed auditor controls](../../tests/test_audit_common_cost_results_v1.py)

Read-only audit command:

```powershell
python -I -S -B scripts/audit_common_cost_results_v1.py --base runs/common-cost-development/v1/retained-42927208534-1 --output <fresh-analysis-directory>
```

The comparison unit remains the related authored profile, with five dependent
timing replicates. Small costs are sensitive to interpreter/import overhead and
the single runner's scheduling. No held-out, application, provider, model API,
novelty, general superiority or checkpoint outcome is established by this
development capture.
