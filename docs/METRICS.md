# Metrics and denominator audit

The formal [v1 operational contract](research/loss-benchmark-metrics-v1.md) and implementation remain unchanged. BoundaryX reexports the engine; no historical metric is silently renamed/redefined, and no universal scalar interoperability-loss score is introduced.

| Area | Numerator / denominator | Evidence and edge cases |
| --- | --- | --- |
| Task completion | Confirmed full-contract successes / all attempts | Unknowns remain counted. Observed-only rate, known-failure fraction and oracle coverage are separate. Protocol completion is insufficient. |
| Context retention | Exact retained eligible facts / measured eligible facts at source→sent, sent→received and source→received | Unknown/N/A and coverage remain explicit; types and duplicates matter. Missing capture differs from omission and present null. |
| Capability usability | Demonstrated usable required operations / measured required operations, plus reference-qualified subset | Advertisement is separate. Unknown reference feasibility is not conversion loss. Probe operation/scope must be fixed. |
| Constraint/tool fidelity | Passed required check items / measurable required check items | Check-item weighting differs from task weighting. Include coverage and eligible confirmed-pass fraction; empty requirements are N/A. |
| Recovery | Successful eligible outcomes / observed eligible outcomes | Also report all-eligible success fraction, coverage and unknowns. A new task cannot recover an old one. |
| Overhead | Separate totals/means/min/max for wall ms, messages, request bytes, response bytes, tool calls and model tokens | Each has coverage. Null is unknown, zero measured. Setup/probes/repairs are separate; no scalar mixes units/designs. |

For non-task rates, eligibility includes measured outcomes and eligible unknowns; coverage also accounts for unknown eligibility. Zero denominators yield null. Task completion deliberately uses all attempts. Heterogeneous evidence is never pooled: the original summary explicitly returns no combined score.

Artifact fields per task are text+media type (2), data+media type (2), URI+filename+media type (3), bytes+filename+media type (3). Five repetitions give 50 required fields per route. Complete fidelity means all fields pass out of 20 tasks. Text utility may be 5/5 while complete fidelity is 0/20 due to omitted metadata. URI survival is not retrieval; inline bytes are compared exactly.

Diagnostic-v2 counts disjoint JSON leaves at frozen pointers, retaining empty objects/arrays. Exact order differs from explicitly declared duplicate-preserving record-order normalization. It is a separate diagnostic, not a replacement for the eight v1 fact groups. Finite repair cardinality counts groups, not bytes/CPU/global optimality. The independent verifier reports contract/wire consistency, not a new benchmark score.
