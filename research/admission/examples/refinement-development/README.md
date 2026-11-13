# Finite recipe development profiles

These eleven records exercise the new witness-lift/refine implementation and
the independent direct relational-product reference. They are **authored
development examples**, including related variants; they are not eleven
independently authored benchmark templates, a held-out/calibration corpus,
qualified domains, or observed application results.

`manifest.json` fixes profile bytes and expected semantic decisions before
comparative measurement. The reproducible logical clock is `now=100`.
Expected decisions are authored assertions, not evaluator-private application
gold. Candidate inputs contain only the individual profile, never this index's
expected-decision field.

The examples cover public-binding construction, text versus structured data,
missing public inputs, prefix-scoped refinement and correlated frames, raw
header coupling, opaque serialization, conservative observable uncertainty,
atomic updates, asynchronous working state, and stale evidence. The source
patterns motivate tests but the files make no source-to-model fidelity claim.

`coverage.complete=true` closes only the explicitly supplied finite recipe
domain. In particular, excluding a missing binding from the listed recipes
does not prove that an arbitrary legal string or an unmodeled public route
could never succeed. The incomplete-coverage example must abstain.

The method is an implemented adaptation of established abstraction/refinement
and symbolic techniques. Novelty, method superiority and source qualification
remain unproved. Both algorithms receive identical profiles, horizons, clocks,
recipe alternatives and the same default work allowance. The reference
memoizes complete public frames and edge/frame relation results; it is not a
deliberately expanded path-enumeration baseline.
