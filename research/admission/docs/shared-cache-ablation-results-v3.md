# Audited shared-cache ablation results

[Run 42879031721](https://github.com/Eshiv-Pandey/Ai_Interoperability/actions/runs/42879031721)
at `5fd88aeede3766b8166c3bc476eef36065eafbc0` completed the entire prospective
66-profile, four-budget, six-arm allocation. Its 1584 method cells include
1056 cache-policy cells. The fresh read-only audit checked all 14590 extracted
files, bound every worker dispatch and independently reconstructed decisions,
proof bytes, work charges and disabled-cache counters. Every conclusive result
has an accepted independent certificate. Unknowns stay in all denominators.

| Work allowance | Goal-pruned direct | Neither cache | Prefix only | Relation only | Both caches |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 20/66 | 8/66 | 2/66 | 7/66 | 2/66 |
| 256 | 54/66 | 42/66 | 39/66 | 41/66 | 39/66 |
| 4096 | 54/66 | 53/66 | 53/66 | 53/66 | 53/66 |
| 100000 | 54/66 | 54/66 | 54/66 | 54/66 | 54/66 |

No cache policy certifies a case beyond goal-pruned direct. At allowance 100000,
work totals for neither/prefix/relation/both are 46278/44432/50150/46840,
versus 3382 for goal-pruned direct. Prefix-only reduces charged work by 1846
relative to neither cache on these profiles; relation-only increases it by
3872. Both caches increase it by 562. These units do not have identical
primitive costs and are not a CPU-speed claim.

The same 54 accepted cache-policy certificates occupy 27248 canonical JSON
bytes per arm at the largest allowance, versus 19880 for direct. Prefix-only
has 608 prefix hits, relation-only 2184 relation hits, and both has 608/720 hits.
Thus reuse occurs, but lookup, publication and representation work can offset
it. Disabling caches does not remove typed full-frame deduplication or witness
construction. The both-enabled arm exactly reproduces preserved v2 certificates
and deterministic counters at all 264 profile/budget cells; the two preserved
direct controls also reproduce their earlier deterministic results.

The [raw read audit](../../runs/shared-cache-ablation/read-review-42879031721-1/result.json),
[all method cells](../../runs/shared-cache-ablation/read-review-42879031721-1/case-methods.csv)
and [budget totals](../../runs/shared-cache-ablation/read-review-42879031721-1/budget-methods.csv)
provide checking time, evaluation time, proof size and resource evidence.
Times are single sequential observations with startup and measurement scopes
retained; no timing superiority is inferred. The ZIP archive SHA256 is
`2307d848494e8397b2b28794ff538e707ca534441294a2d436a20c67b1a52cb1`,
matching GitHub's API digest.

These are related authored development profiles and AI-assisted read audits.
They do not qualify application tasks or held-out gold, establish independent
human scientific validation, or support algorithmic novelty. They resolve the
missing cache-component experiment while preserving the adverse comparison.
