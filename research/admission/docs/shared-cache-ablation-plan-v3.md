# Shared-cache ablation allocation v3

This prospective supplemental experiment retains every one of the 66 original
authored profiles at budgets 32, 256, 4096 and 100000. It compares neither cache,
prefix cache only, relation cache only and both caches, together with the
preserved original baseline and goal-pruned direct comparator. Each cell and
certificate check runs in a fresh, equally instrumented interpreter. No model
or application request is made by this allocation.

The frozen shared-lifting v2 source remains unchanged. The successor exposes
explicit cache switches without patching predecessor globals. With both caches
enabled, deterministic results, certificate bytes and counters must match the
original retained cells, excluding the elapsed time and method label. Disabled
caches remove their lookups, publication and retained entries; whole-frame
deduplication, witness history, JSON typing and all decision rules stay intact.
The historical `cache_payload_nodes` category also measures necessary
representation copying when a cache is disabled. Work units are method-specific
accounting and do not establish CPU speed.

All four budgets, unknowns, failures, independent certificate-check costs,
process peaks and proof sizes remain in the results. No favorable profile
selection or held-out qualification is implied. Ordinary memoization does not
establish a distinct algorithmic contribution. The original adverse comparison
against goal-pruned direct remains preserved.

Ten focused controls passed on 11 November, covering predecessor equivalence,
correlated and typed frames, owned/current-history witnesses, incomplete
coverage, freshness, interrupted expansion and incomplete final-domain caching.
The first local harness smoke failed before dispatch because its copied suite
did not include its relative input profile. That allocation is preserved.
A fresh corrected one-profile smoke passed all 13 worker dispatch bindings and
six independent certificate jobs in
`runs/shared-cache-ablation/software-smoke-20261111-2/bundle`.

The hosted allocation is `.github/workflows/shared-cache-ablation-v3.yml`;
the driver is `scripts/run_shared_cache_ablation_v3.py`. It freezes 1584 method
cells, including 1056 cache-policy cells, on Python 3.13.1/Ubuntu 24.04 with
30-second individual worker limits and a 25-minute outer limit. Attempted
evidence is uploaded even if a later check fails. This plan is not a result.
