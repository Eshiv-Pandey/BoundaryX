# Architecture

Status: Completed development framework. Standard-library Python core and pinned Node upstream implementations.

Frozen task/gold proposal, source, sent, received, receiver output and raw public wire are distinct evidence boundaries. Allocations bind code/input hashes and refuse existing paths. Missing capture, observed omission and present JSON null remain distinct.

`core/evidence.py` parses strict JSON and validates safe manifest paths. `protocols/a2a` and `protocols/mcp` decode captures; actual execution is in official SDKs and the licensed upstream implementations. `adapters/routes.py` records measured profiles. Extend a route only with actual transport execution, payload/identity capture and qualification tests; registry entries alone are not integration.

`execution` and the CLI orchestrate unchanged versioned runners. `metrics` and `recovery` reuse the historical measurement engine and repair lattice. `verification/semantic.py` is a separate SQLite implementation of the ten original source contracts. `verification/independent.py` independently checks source identity, expected answers, actual wire hashes, received payloads, required artifact fields and same-task recovery; it enumerates the declared repair universe separately. It imports no legacy scoring/receiver/gold computation. Definitions, JSON/SQLite infrastructure and captured observations remain shared; this is not independent task design or human scientific review.

```text
src/boundaryx/{core,protocols,adapters,tasks,execution,verification,metrics,recovery,reporting}
src/interoperability/            historical API and finite-core compatibility
benchmarks/development/          review package
benchmarks/heldout/v1/           frozen new proposals, review/evaluation pending
benchmarks/schemas/              task contract schemas
benchmark/ and runs/             selected historical definitions/evidence
results/development/             new execution and verification
results/heldout/                 no scored evaluation yet
results/manifests/               distribution integrity
results/local/                  ignored original command/configuration captures
research/admission/              separate older finite-model research
provenance/                      audit, attribution, versions, redaction ledger
external/{a2a-to-mcp,mcp-a2a}/    licensed implementations/builds and locks
tests/, scripts/, docs/          regression controls, execution, research contracts
```

Historical names remain because manifests bind them. Unrelated provider/native generations are locally preserved instead of becoming production dependencies. Sharing a delivery test command does not combine scientific hypotheses. The CLI operates from a source checkout; editable installation preserves script/dataset access. A module-only wheel is not the complete research artifact.
