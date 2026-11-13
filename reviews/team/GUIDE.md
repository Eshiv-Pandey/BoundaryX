# What to share with teammates

The supervisor observes progress; she does not review tasks, approve gold or sign off on evaluation. This replaces the earlier supervisor-review requirement. Two distinct teammates provide the human reviews. All decisions are currently blank; no task/gold definition, experiment result or held-out hash has changed.

## Teammates: start with the 24 development examples

Share the [team packet](README.md). Each teammate should receive:

1. development/TASKS.md: task definitions, source inputs, required fields, constraints, success criteria and evidence requirements.
2. Their own reviewer-1.md or reviewer-2.md: blank forms, including a place to derive the expected answer.
3. development/PROPOSED_GOLD.md: the current proposed answers to check after making their own attempt.

Ask each person to review independently before discussing answers. They assess clarity, consistency, expected-output logic and evidence traceability. They are not certifying domain expertise or overall scientific novelty. Budget about one to two hours for the first 24 examples, adjusting for difficulty.

For every task, record a name, the supplied definition hash, approve/revise/uncertain, a reason, and specific corrections if needed. Derive the expected answer from the source and rules first; then compare with the proposed gold. Flag confusing required-field names, omitted conditions, unsupported assumptions and missing evidence. An uncertain or revise decision stays pending. Do not fill approval automatically because a test passes.

Return the two completed forms separately. The project team records those real judgments in benchmarks/development/human-review/review-decisions.json, documents disagreements and resolves them explicitly. Keep uncertainty visible. Do not invent a resolution or supervisor judgment. The Markdown forms are an accessible entry point; the JSON records are the machine-readable record.

Suggested message to send yourself:

> Please independently review these 24 BoundaryX tasks. Derive the expected answers from the inputs, then check the proposed answers. Flag unclear instructions, wrong outputs, missing constraints or weak evidence, and return your completed review form with reasons.

## Then: review the 20 held-out proposals separately

The heldout/ folder contains the selected v2 definitions and separate forms. These are twenty proposals, not forty tasks across v1/v2. Their gold is provisional and no evaluation has run. Review the definitions and gold before qualified execution; do not use held-out outcomes to tune implementation. Any correction to task/gold needs a new freeze. The present task-file hash remains dcc3a6e6b48c9281c27a03421ede77448bbd047874779fe1be6133dbb6a14efa.

Two distinct named teammate approvals must bind that hash; one review, a repeated reviewer, stale approvals or unresolved disagreements do not qualify a task. The supervisor is not an eligibility gate. Completing human review does not itself establish route/solver support for the new families.

## Optional technical review

For teammates reviewing the implementation, share [ARCHITECTURE](https://github.com/Eshiv-Pandey/BoundaryX/blob/main/docs/ARCHITECTURE.md), [METRICS](https://github.com/Eshiv-Pandey/BoundaryX/blob/main/docs/METRICS.md), [EXPERIMENT_PROTOCOL](https://github.com/Eshiv-Pandey/BoundaryX/blob/main/docs/EXPERIMENT_PROTOCOL.md), [LIMITATIONS](https://github.com/Eshiv-Pandey/BoundaryX/blob/main/docs/LIMITATIONS.md), the independent verifier and its tests. Look for runner/verifier overlap, incorrect denominators, task/context rebinding, missing evidence, conflated historical/fresh results and held-out leakage. Record concrete findings separately from gold review.

## Supervisor: progress only

Share [the short progress page](supervisor/PROGRESS.md), the artifact/protocol figures and the latest CI status. Explain what runs, what was reproduced and what remains. No reviewer form, approval request or signature is required from her.

BoundaryX is private. Teammates need repository access to use the GitHub links; otherwise share the exported ZIP. The packet contains no credentials or original local preservation archives.
