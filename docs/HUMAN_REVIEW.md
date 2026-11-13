# Human gold review

Status: Pending Human Review and Pending Supervisor Review. All reviewer names, decisions, reasoning, disagreements, resolutions and supervisor judgments remain blank.

The development packet `benchmarks/development/human-review/tasks.json` contains ten original source-contract examples, four artifact requirements and ten representation/evidence examples: 24 tasks. Every task includes definition, source, proposed gold, required fields, constraints, success criteria, protocol assumptions and evidence requirements. Held-out tasks are not development tuning data.

Two undergraduate reviewers independently fill the forms in `review-decisions.json`, assessing clarity, internal consistency, expected-output logic and source/evidence traceability. They are not asked to certify specialized domain expertise. Record names, reasoning and the exact reviewed definition hash; uncertainty remains pending. Record actual disagreements/resolutions only after review.

A separate supervisor reviews contract validity, gold rationale, protocol assumptions, evidence and scope. Approval must be explicit and tied to the reviewed definition. Corrections to task/gold create a new version and hash freeze before execution.

The twenty held-out proposals have separate blank forms. Mutable decisions are outside the immutable definition manifest. Never overwrite `v1`; use a new version for corrected definitions/gold. `boundaryx heldout-status` validates the definition hashes and reports eligibility. No held-out evaluation has occurred, and outcomes must never tune implementation. The independent SQL check supports review but cannot replace it. External scientific evaluation remains pending.
