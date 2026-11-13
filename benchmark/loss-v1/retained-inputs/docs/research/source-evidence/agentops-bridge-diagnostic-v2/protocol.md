# AgentOps shutdown diagnostic v12: prospective protocol

28 October 2026. Prepared before this allocation is executed. This is a new
failure-diagnosis experiment, not a replacement of any v8/v9/v10 result, a
qualification study, a held-out task sample or a C1 performance trial.

## Question and fixed allocation

V10 B7 recorded completed origin state and one guarded domain effect, then its
Python process survived the 20-second wait after the service routine reported
shutdown. The frozen result remains partial. The new question is which
asynchronous task or thread remains at that boundary, and whether the same
diagnostic phenomenon occurs in matched native or passthrough controls.

Run these three cells once, in order. Original names identify the reused client
profiles; every new path starts `runs/agentops-http-control/bridge-diagnostic-v1-`.
Each cell gets a fresh fixture, model double, state directory, bridge cache and
client process. Never fill a skipped cell by silently resuming this allocation.

| Cell | Frozen profile and public continuation | Prerequisite |
| --- | --- | --- |
| N11 | Native mgcrea SDK polling prefix, canonical raw DataPart confirmation with explicit version header | None |
| B6 | Public mgcrea factory with passthrough fetch; typed prefix then permitted raw read/confirmation policy | New N11 strict native control and complete diagnostic capture |
| B7 | Same factory and policy, fetch adds `A2A-Version: 1.0` only at the selected local origin | New N11 strict native control and complete diagnostic capture |

N11 includes the matching typed/polling prefix and canonical raw positive path;
this choice diagnoses shutdown and does not expand its native eligibility claim.
B6's public-binding stop is an admissible diagnostic outcome and does not block
B7 if its processes and diagnostic capture are clean. A false strict native
result skips both dependent bridge cells. An unclean/unknown process group,
invalid/incomplete diagnostic capture, or source/runtime-integrity error stops
later launches. Keep every failed, skipped and unexecuted row.

The text, rationale, public binding rule, SDK/codecs, accepted output modes,
request bodies, polling and configuration are reused from the original
[v10 protocol](../agentops-bridge-control-v1/protocol.md) and client sources.
Missing confirmation IDs must not be supplied by the evaluator. The grader-only
final origin read remains unavailable to clients. A new task ID across fresh
cells does not imply byte-identical requests or independent population samples.

## What changes

Relative to v10, the allocation, fresh output paths, prospective seal and service
diagnostic launcher change. Relative to the unexecuted v11 preparation, the
new v12 adds a bounded exporter correction and versioned seal/schema plumbing. The launcher wraps the original `serve_agentops_bridge_v1.serve`
routine with `agentops_shutdown_diagnostics_v2.run_observed`. The application,
upstream deterministic model double, bridge implementation and clients remain
unchanged. The controller and supervisor are separately named adaptations of
v10; they preserve its limits and cleanup policy. Original source and all
original records are retained and checked, never patched to change an outcome.

The event contract is `agentops-shutdown-event/2`, with sequence, PID, UTC and
monotonic timestamps. Expected normal phase order is:

1. `asyncio_run_entered`.
2. `teardown_watchdog_armed`, five-second one-shot traceback dump.
3. `coroutine_finished`, current/pending task and thread stack locations.
4. `asyncio_run_exited`, outcome and thread stack locations.

Arming precedes snapshot collection. Diagnostic errors are retained separately;
they must not replace an application exception or imply complete capture.
Frames contain filenames, line numbers and function names, not local values,
coroutine arguments or user-controlled task/thread names. The observer adds no
cancellation, signal, timeout extension or application action. The original
ordinary `asyncio.run` teardown remains in effect. This dedicated process owns
the faulthandler configuration.

The watchdog covers teardown after the service coroutine finishes. It does not
diagnose a hang before that point, and it is cancelled when `asyncio.run` exits.
If an exit event is present but the process later needs termination, report
post-asyncio process survival; do not falsely claim a traceback from that later
phase. Stack-source files are copied after capture from workspace-contained
paths into a separate diagnostic-source receipt. Missing or outside sources
remain explicit closure gaps. This is post-capture source inspection, not proof
of all pre-execution loaded-module bytes.

## Bounds and stopping

Use the retained Linux Python 3.13 environment and pinned Node v22.23.2/runtime
graph. Install nothing and make no live model call. Loopback ports remain
18764 (origin) and 18765 (unused Amir configuration field for these profiles).
Retain the 15-second request timeout, 100-ms polling/30 attempts, 180-second
client policy deadline, 32-MiB response cap, 256-request server capture bound,
65-second startup wait, 220-second outer client wait, 300-second fixture
watchdog, 10-second Uvicorn graceful limit, 20-second process wait and
480-second outer controller limit. No timing advantage is measured.

After every controller exit, independently inspect its owned controller,
client and service groups. Any forced cleanup remains forced even if a later
scan confirms absence. Snapshot the domain only under the unchanged original
terminal-boundary policy. Source inspection never restarts or signals a service.
Do not regard an observation timeout as a terminal process; revalidate the
same live tool/process handle. Use new paths for failed setup/checker outputs.

## Interpretation and evidence

Keep unchanged `check_case` task/effect outcomes separate from the new diagnostic
check. B6 can have partial continuation evidence and complete shutdown capture.
Possible diagnostics include normal asyncio return/raise, observed asyncio
teardown stall, post-asyncio process survival, and incomplete evidence before the
supported boundary. Require recorded PID/time/order and actual trace bytes for
a stall classification. A truncated/unrecognized nonempty trace is incomplete.
The checker caps each diagnostic input file at 8 MiB.

Preserve original MCP/A2A capture, all boundary databases, client/protocol
configuration, process receipts, diagnostic JSONL/trace bytes, post-capture source
copies, source/runtime manifests and exits. The new group checker verifies
exact case order, skips, cleanup, source binding, export completeness and
recomputed case/diagnostic reports. Run meaningful observer, mutation, supervision
group, preparation-absence and exporter tests under the selected Linux Python before sealing every launch
input. Preserve any failed test and its exact source snapshot.

If all new processes exit normally, report non-reproduction of the earlier
teardown problem; do not claim that v10 was repaired or its failure disappeared.
If a stall appears, inspect the retained stack before proposing a repair.
Neither branch establishes causal isolation merely from three outcomes.
CP2 novelty, domain validity, human review and checkpoint credit remain unchanged.

## Supersession before launch

The sealed v11 preparation is superseded before any diagnostic application
launch. Its original seal, software receipt, source files and failed checks
remain retained. A read-only review found that the generic exporter interpreted
the diagnostic checker's top-level `files` references as workspace-relative,
although that checker writes them relative to the case directory. This would
produce export-reference failures after capture. No v11 application outcome is
claimed and no consumed case path is reused.

The new `export_agentops_diagnostic_workspace_v1.py` handles only recognized
`agentops-shutdown-diagnostic-check/1` records at the three exact permitted case
paths, binds the case ID, and rebases those top-level file records. It retains
unchanged byte/hash verification and workspace-relative treatment of other
references. The correction changes evidence export, not client policy, process
bounds, observation/effect rules or any original result.

The version-2 preparation seal binds this protocol, the supersession record,
new exporter, v12 runner, minimal version-2 controller, group checker, tests and
the superseded version-1 seal. Before sealing, the preparation checks that both
parent group output paths (v11 and v12) and all three intended native case
directories are absent. The runner repeats the case/output absence checks before
launch. Exact Linux software validation and a prospective seal/preflight must
pass first. The case prefix remains `bridge-diagnostic-v1-`; it was not consumed
by the unexecuted v11 preparation.
