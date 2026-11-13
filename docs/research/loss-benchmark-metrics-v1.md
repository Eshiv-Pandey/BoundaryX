# Development benchmark operational measurements v1

These are **new operational definitions** for a descriptive benchmark delivery.
Earlier six acronyms were not defined in the available task brief. This document
does not guess their expansions or claim to implement an earlier metric scheme.
TCR is used here only for task completion rate as explicitly requested. There is
no composite "information loss %", new continuation algorithm, p-value, research
qualification claim, or confirmed study score in this engine.

The implementation is `src/interoperability/loss_benchmark_v1.py` and uses the
Python standard library on Python 3.11 or later. The public functions are
`validate_episode(episode)`, `score_episode(episode)`,
`summarize_episodes(episodes)`, and `load_episodes(path)`.

## Six separate measurement areas

| Area | Operational measurement | Required qualification |
| --- | --- | --- |
| Task completion / TCR | Confirmed task successes divided by **all attempts**, including unknown outcomes. Known failures, unknowns, observed-only rate and oracle coverage are also reported. | Producer uses a stated full-task outcome predicate. Delivery, task-ID preservation, capability advertisement and transport success cannot establish full-task success. |
| Context / fact retention | Exact recorded JSON fact survival at source to sent (extraction), sent to received (conversion), and source to received (end to end). Each reports retained, lost, unknown and N/A counts, measurable rate and coverage. | Presence and observation are explicit for each boundary. This is recorded representation equality; it is not semantic utility or a causal estimate. |
| Required capability usability | Fraction of required capabilities with demonstrated usable behavior. A second rate is restricted to capabilities explicitly known usable at the reference boundary. Advertisement is reported separately. | `reference_usable` and `observed_usable` refer to the producer's stated operation and counting scope, not a universal capability claim. Unknown reference feasibility does not become demonstrated loss. |
| Constraint / tool fidelity | Passed stated required checks divided by measurable checks, with coverage and all-eligible confirmed-pass fraction. This is check-item-weighted, not task-weighted. | Checks must represent task identity, policy, tool arguments or effects that the producer can actually observe. Empty checks are N/A. |
| Recovery success | Successful eligible recovery attempts divided by observed eligible outcomes; all-eligible confirmed-success fraction and coverage are retained. | Recovery eligibility is stated before outcomes. No recovery attempt is N/A, not a successful recovery. Unknown outcomes remain counted. |
| Overhead vector | Wall milliseconds, messages, request bytes, response bytes, tool calls and model tokens, each with observed total, mean, min, max and coverage. | Producer documents the counted stages. Unknown costs are null; zero is a measured zero. No scalar combines units and no unpaired overhead difference is inferred. |

For context, capability, fidelity and recovery rates, `numerator` is passes and
`denominator` is passes plus known failures in the measurable subset. `eligible`
includes measurable outcomes plus known-eligible unknown outcomes.
`eligibility_unknown` counts items whose baseline qualification is unknown.
`coverage` is measurable outcomes divided by eligible plus eligibility-unknown
items. `unknown` is a missing outcome for an item already known eligible.
`not_applicable` is explicit known ineligibility. The rate is null when no
measurable denominator exists. States are `measured`, `partial`, `unknown`, or
`not_applicable`. Coverage remains null when there are no candidate items.

TCR deliberately uses a different denominator: `denominator` is **all attempts**.
Its `rate` is the confirmed-success fraction, a lower bound when outcomes are
unknown. `observed_denominator`, `observed_rate`, `known_failure_fraction` and
`coverage` make missing outcomes visible. No unknown attempt is discarded.
`all_eligible_success_fraction` for other rates is also a confirmed-success
fraction and must not be interpreted as an imputed failure rate.

## Episode contract

All shown keys are required, even if their value is null or their list is empty.
Only `metadata` is an optional additional top-level object. Unexpected keys are
rejected to catch producer mistakes. Missing fields are not the same as null.

```json
{
  "schema_version": "loss_benchmark_episode_v1",
  "episode_id": "unique-attempt-id",
  "family_id": "declared-task-family",
  "route_id": "declared-route-or-condition",
  "evidence_kind": "fresh_constructed",
  "task_completion": "unknown",
  "context_items": [
    {
      "id": "required-fact",
      "source": "value",
      "sent": "value",
      "received": null,
      "observed": {"source": true, "sent": true, "received": true},
      "present": {"source": true, "sent": true, "received": false}
    }
  ],
  "capability_items": [
    {"id": "read-resource", "required": true, "reference_usable": true,
     "observed_usable": null, "advertised": true}
  ],
  "fidelity_checks": [{"id": "policy-preserved", "status": "unknown"}],
  "recovery": {"eligible": false, "status": "not_applicable"},
  "costs": {"wall_ms": null, "messages": null, "tool_calls": null,
            "request_bytes": null, "response_bytes": null, "model_tokens": null},
  "source_files": [],
  "notes": ["Producer must record task predicate and observation scope."],
  "metadata": {"condition": "example", "scope": "not a runtime qualification"}
}
```

For each context boundary:

| `present` | `observed` | Value | Meaning |
| --- | --- | --- | --- |
| `true` | `true` | Any JSON, including null | A captured, present fact. Actual JSON null is a real value. |
| `false` | `true` | null | Captured boundary definitely lacks this fact. |
| null | `false` | null | Boundary was not captured sufficiently to know whether this fact exists. |

Other combinations are invalid. Extraction and end-to-end retention qualify
facts present at source. Conversion qualifies facts present at sent. A known
source omission is therefore an extraction loss and end-to-end loss; it cannot
also be labeled conversion loss merely because the receiver lacks that fact.
Facts known absent at the baseline boundary are N/A for that boundary metric;
uncaptured baselines are eligibility-unknown. Conversion can be measured even
when source extraction is unknown, if sent and received are directly captured.
Stage losses are separate measurements and are not added into a percentage.
These counts do not attribute loss to a converter without validated boundary
provenance, and a later restoration does not erase an earlier extraction loss.

JSON comparison is recursively type-sensitive: boolean true differs from
integer 1, integers differ from floating-point values, array order matters,
and object key order does not. A semantic equivalent can fail exact retention
while still passing the task oracle. Producers must normalize only under a
declared, frozen representation rule; this engine never silently normalizes.

Each list requires unique nonempty item IDs. Episode IDs must be unique across
the whole input, including evidence kinds. Task and fidelity statuses are
`pass`, `fail`, or `unknown`. Recovery status follows those values when eligible
and must be `not_applicable` when ineligible. Capability booleans may be null
for unknown; `required` must be a boolean. Count costs must be nonnegative
integers; wall duration can be a nonnegative finite number. Booleans are not
counts. Nonfinite JSON numbers, inconsistent observations and duplicate JSON
object keys are rejected.

`source_files` contains objects with `path` and a 64-hex-character `sha256`.
Retained evidence requires at least one hashed source; constructed episodes may
temporarily have no sources until their producer saves and hashes the trace.
The engine validates hash syntax and duplicate path strings; **it does not
open those files or verify their contents**. Producers verify provenance and
use a consistent path representation to avoid aliased duplicate sources.
Notes and metadata should retain the oracle, observation scope, counted cost
boundary, source collection limitations, and any diagnostic-double flags.

## Evidence separation and output

`evidence_kind` is exactly one of `fresh_constructed`, `retained_bridge`, or
`retained_native`. Summaries expose separate evidence groups and separate
evidence/family/route groups. Mixed evidence has `scores: null`; it never gets
a pooled overall rate. A homogeneous evidence group may contain multiple routes
and families. Unrelated retained families have task-outcome counts and
`scores: null` in the overview; inspect evidence/family/route groups for rates.
Constructed controls may have a descriptive overview across families. Task
completion is attempt weighted; context, capability and fidelity are fact-,
capability- and check-item weighted respectively. An overview is not a paired
route effect or comparison.
Metadata such as fixture doubles, seeds and profile constraints remains part
of the source episode; the summary does not upgrade its evidence class.
Retained runtime evidence is retained, not fresh execution in this benchmark.
Constructed controls demonstrate engine behavior, not bridge qualifications.

Run the engine from the repository with its package on the import path:

```powershell
$env:PYTHONPATH = 'src'
python -m interoperability.loss_benchmark_v1 --input episodes.jsonl --output summary.json
python -m unittest discover -s tests -p test_loss_benchmark_v1.py -v
```

Input accepts one JSON episode, a JSON array, or `.jsonl`/`.ndjson` records.
The CLI creates its output exclusively and refuses to overwrite an existing
artifact. Use a new output path for every benchmark invocation.
Empty input has no pooled score and no perfect empty metric. Tests exercise
unknown outcomes, absent versus uncaptured facts, extraction versus conversion,
semantic success despite exact loss, advertisement without usability, unknown
reference feasibility, recovery eligibility, zero versus unknown costs,
heterogeneous evidence separation, strict validation and CLI serialization.
