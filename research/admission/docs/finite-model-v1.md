# Finite continuation model v1

Prepared 2026-10-24. This shared interchange specification precedes the separately authored baseline and oracle. It is a development abstraction, not a protocol conformance claim or an implemented novel algorithm. Hand-authored model fixtures must never be presented as observed bridge behavior.

## Scope

The target is finite **may-compatibility**: at least one path from the supplied initial state, of at most `horizon` transitions, satisfies the supplied runtime goal while every visited state satisfies the invariants. Nondeterministic edges describe possible outcomes; finding a path does not establish a winning strategy against an environment or actual LLM compliance. States include the explicit observables relevant to the runtime contract, such as task namespace, required handle, receiving principal, artifact accessibility and expiry.

The development manifest has exactly these top-level fields:

- `schema_version`: `finite-continuation/1`.
- `id`: nonempty case identifier.
- `route`: nonempty description; provenance indicates whether this is authored or wire-derived.
- `provenance`: object with `kind` (`authored-development` or `wire-derived`), `source` and `review_status`. Source validity is not established by this string.
- `horizon`: integer from 0 through 64, in **transitions**, identical for all comparators.
- `evidence`: `complete` (boolean), `observed_at` and `valid_until` (integer UTC epoch seconds). Fresh iff `observed_at <= now <= valid_until`. Completeness is a declared assumption, not proven by a successful probe.
- `initial`: state identifier.
- `states`: nonempty dictionary from nonempty state IDs to observable objects. Values are JSON strings, booleans, integers or null. Missing observable is unknown, not false; explicit null is a known value.
- `transitions`: list of objects with unique nonempty `id`, valid `source`/`target` state IDs and nonempty `operation` label. No hidden transitions, guards or effects: their finite projection is already in this explicit graph.
- `runtime_contract`: `goal` and `invariants`, each a list of predicates ANDed together. Empty lists are true. No private evaluation gold is accepted by this interface.

Predicates use `field`, `op`, and either `value` or `other_field`. Supported operators: `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in`, and `eq_field`. `eq_field` requires `other_field` instead of `value`; `in` takes a list of scalar values. Ordered comparisons require integer fields/values (booleans are not integers here). Equality is type-sensitive, including null. Any missing referenced field or invalid operand type is indeterminate, not silently converted to false. A malformed manifest is an input error, not an interoperability result.

## Decision semantics

1. Stale/future-dated evidence returns `unknown`, with no certificate.
2. A path whose states have definitely true invariants and whose final state has a definitely true goal establishes `supported`, even if the model is partial. This is conditional on the modeled path being realizable and on the pinned evidence assumptions.
3. `unsupported` requires fresh, declared complete evidence, no accepted path and no indeterminate invariant or goal in any potentially safe state reachable within the horizon. This conservative rule can return unknown even if more analysis could resolve an irrelevant uncertainty.
4. Otherwise return `unknown`. Do not interpret unknown or correct refusal as task completion.

Invariants are checked at the initial state and after every transition. A definitely unsafe state blocks the path. An indeterminate invariant does not produce an accepted witness but keeps uncertainty alive; exploration must not erase its possibly safe successors. Goal predicates need only be checked at possibly safe states. A definitely unsafe initial state permits an unsupported result under a complete, fresh model. An initial goal may produce a zero-transition supported certificate.

## Results and independently checked certificates

Root implementation owns `interoperability.baseline.evaluate(manifest, now)`; independent oracle owns `interoperability.oracle.evaluate(manifest, now)` and `interoperability.oracle.check_certificate(manifest, result, now)`. Each returns `decision` (`supported`, `unsupported`, `unknown`), `reason`, `certificate` (object or null) and optional `stats`. The oracle must not import or call the baseline or its predicate/transition implementation. Shared wire format is allowed; shared decision logic is not independent validation.

Model digest is SHA-256 over UTF-8 JSON of the entire manifest with sorted keys, compact separators and `ensure_ascii=False`. It binds the runtime contract and evidence as well as the route. Every certificate includes `model_sha256`, `checked_at`, `horizon`, and `valid_until`. Checking rejects a changed manifest, stale certificate, changed horizon, malformed fields or wrong decision.

- Supported certificate: `kind='path'`, `transition_ids` in order. The checker independently replays from `initial`, validates endpoints, every invariant, final goal and length. It cannot verify a real bridge from an authored graph alone.
- Unsupported certificate: `kind='bounded-cut'`, `layers`, a list of `horizon+1` sorted lists of state IDs. Layer 0 contains the initial state iff it is definitely safe. Subsequent layers contain **all** invariant-safe successors of the prior layer (duplicates removed within each layer, without dropping recurrence across layers). Goal must be false in every layer; relevant indeterminacy or incomplete evidence invalidates the certificate. The checker independently validates the full finite closure, not merely the absence of a listed goal.
- Unknown: certificate is null. Unknown is a transparent abstention, not a proof.

An independent exhaustive path oracle establishes agreement only within this explicit finite abstraction. Protocol projection fidelity, runtime/gold separation in application tasks, complete profiles, external bridge behavior, human review and novel advantage remain separate gates.
