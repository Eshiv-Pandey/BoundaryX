# Human gold review

Status: Pending Human Review. All teammate names, decisions, reasoning, disagreements and resolutions remain blank. The supervisor observes progress only; she does not review gold or approve evaluation. This user-confirmed role replaces the initial supervisor-review requirement.

Use [TEAM_REVIEW_GUIDE](TEAM_REVIEW_GUIDE.md) and the readable [team packet](../reviews/team/README.md). The development packet contains ten original source-contract examples, four artifact requirements and ten representation/evidence examples: 24 tasks. Every task includes definition, source, proposed gold, required fields, constraints, success criteria, protocol assumptions and evidence requirements. Held-out tasks are separate from development tuning data.

Two distinct teammates independently assess clarity, internal consistency, expected-output logic and source/evidence traceability. They are not asked to certify specialized domain expertise. Each derives the expected answer from the input and rules before comparing the proposed gold. Record names, reasoning and the exact reviewed definition hash; uncertainty remains pending. Discuss actual disagreements after completing the independent forms, and record genuine resolutions and corrections.

The JSON records remain the machine-readable decisions; separate blank Markdown forms make review easier. No judgments are automatically populated. The checker requires two distinct named approvals on the frozen hash, rejects stale approvals and blocks unresolved disagreements. This checks declared review records, not authenticated reviewer identity or domain expertise. Corrections to task/gold create a new version and hash freeze before execution.

The twenty held-out proposals have separate blank forms. Mutable decisions are outside the immutable definition manifest. Never overwrite `v1`; use a new version for corrected definitions/gold. `boundaryx heldout-status` validates the definition hashes and reports eligibility. No held-out evaluation has occurred, and outcomes must never tune implementation. The independent SQL check supports review but cannot replace it. External scientific evaluation remains pending.

The selected held-out candidate bank is v2. Its pre-execution revision strengthens four task structures; the v1 proposal remains frozen and unexecuted. These are versions of a twenty-instance bank, not forty independent evaluations. No results informed the revision.

Current policy: benchmarks/review-policy.json. The active development/v2 forms omit unused supervisor fields. Inactive v1 forms and original historical reports retain the old blank fields/plans for provenance; they are not requirements of the current workflow. Existing task/gold definitions, metrics and held-out manifest bytes are unchanged. Human review does not replace route/solver qualification for the new families.

For supervisor updates, use [PROGRESS_FOR_SUPERVISOR](PROGRESS_FOR_SUPERVISOR.md). No reviewer form or sign-off is required from her.
