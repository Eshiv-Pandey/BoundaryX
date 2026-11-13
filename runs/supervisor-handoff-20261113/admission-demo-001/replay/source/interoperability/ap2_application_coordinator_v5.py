"""Owned AP2 development decisions around unchanged original payment tools."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import time
from types import SimpleNamespace

from . import ap2_application_profile_v5 as profile
from . import ap2_hp_reference_execution_v1 as execution
from .ap2_hp_reference_execution_v1 import ReferenceCoordinator, ReferenceOutcome, invoke, typed_equal


class AdmissionRefused(RuntimeError):
    """An owned admission refusal, distinct from an original source exception."""


class ReceivedAdmissionBoundary:
    def __init__(self, output, recorder, durable, case, policy, writer):
        self.output, self.recorder, self.durable = Path(output), recorder, durable
        self.case, self.policy, self.write = case, policy, writer
        self.pending = self.canonical = None
        self.association_completed = False
        self.attempts = []
        self.dispatched = False

    def configure(self, pending, canonical, association_completed):
        self.pending, self.canonical = deepcopy(pending), deepcopy(canonical)
        self.association_completed = association_completed

    async def authorize(self, raw, sender_message):
        """Runs after the original builder, before any original ASGI handler."""
        if not self.policy["shared_admission"]:
            if self.case.get("dispatch_delay_seconds"):
                await asyncio.sleep(self.case["dispatch_delay_seconds"])
            return
        number = len(self.attempts)
        base = self.output / "admission" / f"attempt-{number:03d}"
        base.mkdir(parents=True, exist_ok=False)
        row = {"index": number, "attempted_utc": datetime.now(timezone.utc).isoformat(),
               "raw_received_request": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
               "original_sender_message": deepcopy(sender_message), "original_raw_continuation_dispatched": False,
               "whole_route_non_support_inference_allowed": False}
        self.attempts.append(row)
        self.write(base / "attempt.json", row)
        try:
            if self.dispatched:
                raise AdmissionRefused("once_only_original_continuation_already_dispatched")
            profile.need(self.pending is not None and self.canonical is not None, "public_pending_input_not_configured")
            journal = (self.recorder.path / "events.jsonl").read_bytes()
            checkpoint, exchanges = profile.decode_journal(journal, self.durable)
            report = self.recorder.report()
            profile.need(report["observation_complete_current"] is True
                         and report["missing_global_indices"] == []
                         and checkpoint["events"] == report["attempted_events"] == report["durably_committed_events"],
                         "complete_durable_prefix_required")
            # The original public send attempt is active. All raw handlers must
            # still be quiescent because no continuation has been forwarded.
            profile.need(all(not value["active"] for key, value in self.recorder.streams.items() if key.endswith("_raw")),
                         "raw_application_interval_active_before_admission")
            binding = profile.bind_pending_raw(self.pending, exchanges)
            request = profile.decode_json(raw)
            profile.need(request.get("jsonrpc") == "2.0" and request.get("method") == "message/send",
                         "received_request_not_original_sdk_send")
            now = int(time.time())
            prepared = profile.prepare_profile(self.pending, self.canonical, request["params"]["message"],
                                               association_completed=self.association_completed, now=now,
                                               valid_for_seconds=self.case.get("certificate_valid_for_seconds", 15))
            receipt = profile.evaluate_prepared(prepared, now)
            receipt.update(journal_checkpoint_before_admission=checkpoint, pending_raw_binding=binding)
            self.write(base / "pending-input.json", prepared)
            self.write(base / "profile.json", prepared["profile"])
            self.write(base / "solver-result.json", receipt["solver_result"])
            self.write(base / "admission-before-send.json", receipt)
            if not receipt["dispatch_permitted"]:
                raise AdmissionRefused("incomplete_received_relation_refused:" + receipt["decision"])
            if self.case.get("dispatch_delay_seconds"):
                await asyncio.sleep(self.case["dispatch_delay_seconds"])
            dispatch_clock = int(time.time())
            profile.verify_supported(prepared, receipt["solver_result"], dispatch_clock)
            profile.need(profile.same(profile.wire_message(request["params"]["message"]),
                                      prepared["original_request"]["message"]), "received_raw_changed_before_dispatch")
            profile.need((self.recorder.path / "events.jsonl").read_bytes() == journal,
                         "journal_changed_during_owned_admission")
            dispatch = {"schema_version": profile.SCHEMA, "checked_at": dispatch_clock,
                        "evaluation_clock": now, "valid_until": receipt["valid_until"],
                        "input_sha256": profile.digest(prepared), "profile_sha256": receipt["profile_sha256"],
                        "raw_request": row["raw_received_request"], "journal_checkpoint_before_dispatch": checkpoint,
                        "actual_rpc_id": request["id"], "original_message_id": request["params"]["message"]["messageId"],
                        "original_merchant_task_id": self.pending["id"], "original_context_id": self.pending["contextId"],
                        "independent_checker_rechecked_at_dispatch": True,
                        "actual_task_completion_established_by_certificate": False}
            self.write(base / "raw-dispatch.json", dispatch)
            self.dispatched = True
            row.update(original_raw_continuation_dispatched=True, evaluation_clock=now,
                       raw_dispatch_clock=dispatch_clock, decision=receipt["decision"])
        except BaseException as error:
            row.update(error_type=type(error).__name__, reason=str(error)[:1000])
            self.write(base / "refusal.json", row)
            raise

    def finish(self):
        self.write(self.output / "admission-result.json", {"schema_version": profile.SCHEMA,
            "shared_admission_enabled": self.policy["shared_admission"], "attempts": self.attempts,
            "any_original_raw_continuation_dispatched": self.dispatched,
            "actual_task_completion_established_by_certificate": False,
            "whole_route_non_support_inference_allowed": False})


class ApplicationCoordinator(ReferenceCoordinator):
    def __init__(self, bindings, planner_class, contract, *, original_tools, output, case, policy,
                 boundary, writer, serializer, task_query_class):
        super().__init__(bindings, planner_class, contract)
        self.original_tools, self.output, self.case, self.policy = original_tools, Path(output), case, policy
        self.boundary, self.write, self.serialize, self.task_query_class = boundary, writer, serializer, task_query_class
        self.source_invocations, self.recovery_records = [], []
        self.association_completed = False

    async def _source(self, name, function, *args, **kwargs):
        row = {"index": len(self.source_invocations), "callable": function.__module__ + "." + function.__qualname__,
               "phase": name, "invoked_utc": datetime.now(timezone.utc).isoformat()}
        self.source_invocations.append(row)
        try:
            result = await invoke(function, *args, **kwargs)
        except BaseException as error:
            row.update(error_type=type(error).__name__, reason=str(error)[:1000])
            raise
        row["return"] = self.serialize(result)
        self.tool_returns.append((name, result))
        return result

    async def _associate(self, phase):
        await self._source(phase, self.bindings.send_signed_mandates, self.context, debug_mode=False)
        observation = self.bindings.credentials.calls[-1]["public_result"]
        profile.need(type(observation) is dict and observation.get("kind") == "task"
                     and observation.get("contextId") == self.context.state["shopping_context_id"]
                     and observation.get("status", {}).get("state") == "completed",
                     "actual_original_credential_association_not_completed")
        self.association_completed = True
        self.write(self.output / (phase + "-task.json"), observation)

    async def run(self, **unused):
        b, p, c = self.bindings, self.plan, self.context
        final = error = pending = canonical = None
        start_return = response = None
        decision = "prefix_incomplete"
        try:
            profile.need(not self._started, "fresh_coordinator_required")
            self._started = True
            carts = await self._tool("catalog", b.find_products, b.merchant, p.contract["catalog_search"], c, debug_mode=False)
            self._state_matches("shopping_context_id", "available_carts", "risk_data")
            profile.need(type(carts) is list and typed_equal([execution.public_json(item) for item in carts], p.state["available_carts"]),
                         "original_carts_do_not_match_public_catalog")
            choice = p.state["available_carts"][0]["cart_id"]
            p.observe("cart_selection", choice)
            self.tool_returns.append(("cart_selection", await invoke(b.select_cart, choice, c)))
            self._state_matches("chosen_cart_id")
            address = await self._tool("shipping", b.get_shipping_address, b.credentials, p.contract["user_email"], c)
            profile.need(typed_equal(execution.public_json(address), p.state["shipping_address"]), "original_shipping_projection_differs")
            await self._tool("payment_methods", b.get_payment_methods, b.credentials, p.contract["user_email"], c)
            alias = p.state["payment_method_aliases"][0]
            p.observe("payment_selection", alias)
            await self._tool("credential_token", b.get_payment_credential_token, b.credentials,
                             p.contract["user_email"], alias, c, card=True)
            self._state_matches("payment_credential_token")
            await self._tool("checkout", b.create_checkout, b.merchant, c, debug_mode=False)
            self._state_matches("checkout_data")
            p.observe("approval", {"approved": True, "summary": deepcopy(p.approval_summary())})
            for phase, function in (("checkout_mandate", b.create_checkout_mandate), ("payment_mandate", b.create_payment_mandate)):
                value = await invoke(function, c)
                self.tool_returns.append((phase, value))
                p.observe(phase, value)
                self._state_matches(phase + "_sdjwt")
            self._state_matches("checkout_hash")
            self.write(self.output / "prefix-observations.json", p.report())
            if not (self.case["fault"] == "omit_original_credential_association" and self.policy["apply_received_fault"]):
                await self._associate("cp_association")
            start_return = await self._source("original_payment_start", self.original_tools.initiate_payment, c, debug_mode=False)
            pending = deepcopy(b.merchant.calls[-1]["public_result"])
            profile.public_challenge(pending)
            profile.need(c.state["initiate_payment_task_id"] == pending["id"], "original_tool_did_not_store_actual_payment_task")
            canonical = self.serialize(c.state)
            self.write(self.output / "payment-start-task.json", pending)
            self.write(self.output / "canonical-input.json", canonical)
            fault = self.case["fault"] if self.policy["apply_received_fault"] else "none"
            if fault == "prior_catalog_task_id":
                c.state["initiate_payment_task_id"] = p.observations[0]["supplied_value"]["id"]
            elif fault == "nested_processor_task_id":
                nested = pending["status"]["message"].get("taskId")
                profile.need(type(nested) is str and nested and nested != pending["id"], "actual_nested_processor_reference_missing")
                c.state["initiate_payment_task_id"] = nested
            elif fault == "other_original_catalog_context":
                other = SimpleNamespace(state={})
                await self._source("other_original_catalog", b.find_products, p.contract["catalog_search"], other, debug_mode=False)
                other_task = deepcopy(b.merchant.calls[-1]["public_result"])
                profile.need(other_task["contextId"] != pending["contextId"], "other_original_catalog_not_fresh")
                self.write(self.output / "other-original-catalog-task.json", other_task)
                c.state["shopping_context_id"] = other_task["contextId"]
            elif fault == "remove_caller_payment_mandate":
                del c.state["payment_mandate_sdjwt"]
            elif fault == "checkout_in_payment_slot":
                c.state["payment_mandate_sdjwt"] = c.state["checkout_mandate_sdjwt"]
            self.write(self.output / "received-caller-state.json", self.serialize(c.state))
            if self.policy["recover"]:
                # Canonical authority was already returned by the original
                # payment tool. This legal original SDK query uses that ID.
                client = await b.merchant.client._get_a2a_client()
                query = self.task_query_class(id=pending["id"], history_length=100)
                task = await client.get_task(query)
                recovered = self.serialize(task)
                profile.need(recovered["id"] == pending["id"] and recovered["contextId"] == pending["contextId"],
                             "public_original_task_recovery_changed_authority")
                self.recovery_records.append({"operation": "original_sdk_get_task", "query": self.serialize(query),
                                              "public_result": recovered})
                pending = recovered
                for key in ("initiate_payment_task_id", "shopping_context_id", "payment_mandate_sdjwt", "checkout_mandate_sdjwt", "risk_data"):
                    if not typed_equal(self.serialize(c.state.get(key)), canonical.get(key)):
                        self.recovery_records.append({"operation": "restore_already_observed_source_caller_value", "field": key})
                        c.state[key] = deepcopy(canonical[key])
                if not self.association_completed:
                    await self._associate("recovery_cp_association")
                    self.recovery_records.append({"operation": "invoke_omitted_original_credential_association"})
            self.boundary.configure(pending, canonical, self.association_completed)
            human = self.case["human_response"]
            if human is None:
                decision = "waiting_for_explicit_human_reply"
            elif human == "public_demo_hint":
                if self.policy["inspect_public_task"]:
                    response = profile.demo_response(profile.public_challenge(pending))
                    decision = "demo_hint_from_actual_public_task"
                else:
                    offered = re.findall(r"\(Demo only hint: the code is ([0-9]+)\)", start_return)
                    response = offered[0] if len(offered) == 1 else None
                    decision = "original_generic_tool_return_has_no_otp" if response is None else "demo_hint_in_original_tool_return"
            else:
                response, decision = human, "explicit_development_human_response_preserved"
            if response is not None:
                await self._source("original_payment_otp", self.original_tools.initiate_payment_with_otp,
                                   response, c, debug_mode=False)
                final = b.merchant.calls[-1]["returned"]
                if self.case["fault"] == "repeat_original_otp_tool":
                    await self._source("duplicate_original_payment_otp", self.original_tools.initiate_payment_with_otp,
                                       response, c, debug_mode=False)
                    final = b.merchant.calls[-1]["returned"]
        except Exception as caught:
            error = caught
        finally:
            self.write(self.output / "source-tool-invocations.json", self.source_invocations)
            self.write(self.output / "public-recovery.json", self.recovery_records)
            self.write(self.output / "application-outcome.json", {
                "schema_version": "ap2-original-tool-cell/5", "case_id": self.case["id"], "arm_id": self.policy["id"],
                "decision": decision, "original_payment_start_return": start_return, "supplied_otp_response": response,
                "error_type": type(error).__name__ if error is not None else None,
                "reason": str(error)[:1000] if error is not None else None,
                "final_task": self.serialize(final) if final is not None else None,
                "source_bank_task_qualification_established": False, "native_qualification_established": False,
                "provider_requests_allowed": 0, "whole_route_non_support_inference_allowed": False})
        return ReferenceOutcome("captured_original_tool_sequence" if error is None else "captured_original_tool_error_or_admission_refusal",
                                p.phase, p.report(), deepcopy(self.public_records), self.tool_returns,
                                final, error, b.merchant.calls + b.credentials.calls)
