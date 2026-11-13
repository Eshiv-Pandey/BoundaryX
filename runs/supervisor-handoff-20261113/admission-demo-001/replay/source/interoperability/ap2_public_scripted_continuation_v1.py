"""Prospective owned caller of unchanged original AP2 business functions.

The parent must provide fresh original services/signing state and an isolated
source-bound process. This module starts no server, makes no model call, and is
not an unchanged ADK/root-agent qualification. It has no evaluator or journal
input. Human choices are explicit public facts; Tasks come from public SDK reads.
"""
from __future__ import annotations

from copy import deepcopy
import asyncio
import hashlib
import importlib
import inspect
import os
from pathlib import Path
from types import SimpleNamespace


MODULES = {
    "common.a2a_message_builder": "common/a2a_message_builder.py",
    "common.payment_remote_a2a_client": "common/payment_remote_a2a_client.py",
    "common.artifact_utils": "common/artifact_utils.py",
    "common.constants": "common/constants.py",
    "common.a2a_extension_utils": "common/a2a_extension_utils.py",
    "roles.shopping_agent.remote_agents": "roles/shopping_agent/remote_agents.py",
    "roles.shopping_agent.tools": "roles/shopping_agent/tools.py",
    "roles.shopping_agent.subagents.shopper.tools": "roles/shopping_agent/subagents/shopper/tools.py",
    "roles.shopping_agent.subagents.shipping_address_collector.tools": "roles/shopping_agent/subagents/shipping_address_collector/tools.py",
    "roles.shopping_agent.subagents.payment_method_collector.tools": "roles/shopping_agent/subagents/payment_method_collector/tools.py",
}
FACT_KEYS = {
    "case_id", "catalog_search", "user_email", "cart_index", "payment_method_index",
    "wallet_consent", "confirm_cart", "otp_response", "fault", "repeat_after_completed",
}
FAULTS = {"none", "other_original_context", "public_nested_processor_task"}


def public_json(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, dict):
        return {key: public_json(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [public_json(child) for child in value]
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("Only public JSON or original typed tool results can be retained.")


def validate_facts(facts):
    if type(facts) is not dict or set(facts) != FACT_KEYS:
        raise ValueError("Only the prospectively declared public human fact fields are accepted.")
    for key in ("case_id", "catalog_search", "user_email"):
        if type(facts[key]) is not str or not facts[key]:
            raise ValueError("A nonempty public fact is required: " + key)
    for key in ("cart_index", "payment_method_index"):
        if type(facts[key]) is not int or facts[key] < 0:
            raise ValueError("Human selection must be a nonnegative offered index: " + key)
    for key in ("wallet_consent", "confirm_cart", "repeat_after_completed"):
        if type(facts[key]) is not bool:
            raise ValueError("Explicit human boolean required: " + key)
    if facts["otp_response"] is not None and type(facts["otp_response"]) is not str:
        raise ValueError("OTP must be an explicit human string or no reply.")
    if facts["fault"] not in FAULTS:
        raise ValueError("The prospective public authority fault is not supported.")
    return deepcopy(facts)


def bind_original_modules(samples_root, expected_hashes):
    """Check source bytes and loaded function bodies without executing source text."""
    from .ap2_hp_original_binding_v1 import verify_module

    samples_root = Path(samples_root).resolve(strict=True)
    modules, records = {}, {}
    if set(expected_hashes) != set(MODULES.values()):
        raise ValueError("Exact original business-source hash membership is required.")
    for name, relative in MODULES.items():
        source = samples_root / relative
        raw = source.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hashes[relative]:
            raise ValueError("Pinned original business source changed: " + relative)
        module = importlib.import_module(name)
        loaded = Path(module.__file__).resolve(strict=True)
        if loaded.read_bytes() != raw:
            raise ValueError("Imported business source differs from its original stage: " + name)
        verify_module(module, name, loaded, raw)
        modules[name] = module
        records[name] = {"staged_source": str(source), "imported_source": str(loaded),
                         "sha256": actual_hash, "original_function_bodies_verified": True}
    remote = modules["roles.shopping_agent.remote_agents"]
    original_client_class = modules["common.payment_remote_a2a_client"].PaymentRemoteA2aClient
    if type(remote.merchant_agent_client) is not original_client_class or type(remote.credentials_provider_client) is not original_client_class:
        raise ValueError("The original remote-client instances were replaced.")
    for name, module in modules.items():
        if name.startswith("roles.shopping_agent."):
            for alias in ("merchant_agent_client", "credentials_provider_client"):
                if hasattr(module, alias) and getattr(module, alias) is not getattr(remote, alias):
                    raise ValueError("An original business-module client alias was replaced: " + name)
    return modules, records


class PublicScriptedContinuation:
    def __init__(self, modules, source_records, facts, writer):
        self.modules, self.source_records = modules, deepcopy(source_records)
        self.facts, self.write = validate_facts(facts), writer
        self.context = SimpleNamespace(state={})
        self.events, self.calls, self.public_reads = [], [], []
        self.business = modules["roles.shopping_agent.tools"]
        self.shopper = modules["roles.shopping_agent.subagents.shopper.tools"]
        self.shipping = modules["roles.shopping_agent.subagents.shipping_address_collector.tools"]
        self.payment = modules["roles.shopping_agent.subagents.payment_method_collector.tools"]

    def event(self, kind, **values):
        row = {"index": len(self.events), "kind": kind, **public_json(values)}
        self.events.append(row)
        self.write("actor-public-event", row)

    async def call(self, phase, function, *args, **kwargs):
        row = {"index": len(self.calls), "phase": phase,
               "callable": function.__module__ + "." + function.__qualname__}
        self.calls.append(row)
        self.write("original-call-start", row)
        try:
            returned = function(*args, **kwargs)
            if inspect.isawaitable(returned):
                returned = await asyncio.wait_for(returned, timeout=60.0)
        except BaseException as error:
            row.update(error_type=type(error).__name__, error=str(error))
            self.write("original-call-error", row)
            raise
        row["public_return"] = public_json(returned)
        self.write("original-call-return", row)
        return returned

    async def read(self, phase):
        from .ap2_public_task_read_v1 import read_public_payment_task

        query = {"id": self.context.state.get("initiate_payment_task_id"),
                 "caller_context": self.context.state.get("shopping_context_id")}
        self.write("public-task-read-start", {"phase": phase, "query": query})
        try:
            observation = await read_public_payment_task(self.context)
        except BaseException as error:
            row = {"phase": phase, "query": query, "error_type": type(error).__name__, "error": str(error)}
            if hasattr(error, "public_observation"):
                row["refused_public_observation"] = public_json(error.public_observation)
            if hasattr(error, "error") and hasattr(error.error, "model_dump"):
                row["public_rpc_error"] = public_json(error.error)
            self.public_reads.append(row)
            self.write("public-task-read-error", row)
            raise
        row = {"phase": phase, "public_observation": observation}
        self.public_reads.append(row)
        self.write("public-task-read-return", row)
        return observation["task"]

    @staticmethod
    def challenge(task):
        parts = (task.get("status", {}).get("message") or {}).get("parts") or []
        candidates = [part["data"]["challenge"] for part in parts
                      if type(part.get("data")) is dict and "challenge" in part["data"]]
        if (task.get("status", {}).get("state") != "input-required" or len(candidates) != 1
                or type(candidates[0]) is not dict or candidates[0].get("type") != "otp"
                or type(candidates[0].get("display_text")) is not str):
            raise ValueError("An actual unique public OTP challenge was not returned.")
        return deepcopy(candidates[0])

    @staticmethod
    def receipts(task):
        return [deepcopy(part["data"]["ap2.PaymentReceipt"])
                for artifact in task.get("artifacts") or [] for part in artifact.get("parts") or []
                if type(part.get("data")) is dict and "ap2.PaymentReceipt" in part["data"]]

    async def run(self):
        c, f = self.context, self.facts
        pending = final = None
        outcome, error = "incomplete", None
        try:
            carts = await self.call("catalog", self.shopper.find_products, f["catalog_search"], c, debug_mode=False)
            if f["cart_index"] >= len(carts):
                raise ValueError("The explicit human cart choice was not offered.")
            cart = public_json(carts[f["cart_index"]])
            self.event("human-cart-selection", offered=public_json(carts), selected=cart)
            await self.call("cart-selection", self.shopper.select_cart, cart["cart_id"], c)
            self.event("human-wallet-consent", consent=f["wallet_consent"], user_email=f["user_email"])
            if not f["wallet_consent"]:
                outcome = "waiting_for_wallet_consent"
                return self.result(outcome, pending, final, error)
            address = await self.call("shipping", self.shipping.get_shipping_address, f["user_email"], c)
            self.event("public-shipping-display", address=public_json(address))
            methods = await self.call("payment-methods", self.payment.get_payment_methods, f["user_email"], c)
            aliases = methods.get("payment_method_aliases") if type(methods) is dict else None
            if type(aliases) is not list or f["payment_method_index"] >= len(aliases):
                raise ValueError("The explicit human payment-method choice was not offered.")
            alias = aliases[f["payment_method_index"]]
            self.event("human-payment-selection", offered=methods, selected=alias)
            await self.call("credential-token", self.payment.get_payment_credential_token, f["user_email"], alias, c)
            checkout = await self.call("checkout", self.business.create_checkout, c, debug_mode=False)
            self.event("human-cart-confirmation", approved=f["confirm_cart"], cart=cart,
                       shipping=public_json(address), payment_method=alias)
            if not f["confirm_cart"]:
                outcome = "waiting_for_cart_confirmation"
                return self.result(outcome, pending, final, error)
            if os.environ.get("AGENT_PROVIDER_SIGNING_KEY_PEM") or self.business.AGENT_PROVIDER_KEY_PATH.exists():
                raise ValueError("A fresh original caller signing key is required for this task.")
            await self.call("checkout-mandate", self.business.create_checkout_mandate, c)
            await self.call("payment-mandate", self.business.create_payment_mandate, c)
            await self.call("credential-association", self.business.send_signed_mandates_to_credentials_provider, c, debug_mode=False)
            await self.call("payment-start", self.business.initiate_payment, c, debug_mode=False)
            pending = await self.read("initial-payment-task")
            self.event("public-otp-request", challenge=self.challenge(pending),
                       merchant_task_id=pending["id"], context_id=pending["contextId"])
            self.event("explicit-human-otp", response=f["otp_response"])
            if f["fault"] != "none":
                from a2a.client.errors import A2AClientJSONRPCError
                from .ap2_public_task_read_v1 import PublicTaskAuthorityError

                if f["fault"] == "other_original_context":
                    other = SimpleNamespace(state={})
                    await self.call("other-original-catalog", self.shopper.find_products, f["catalog_search"], other, debug_mode=False)
                    received = other.state.get("shopping_context_id")
                    if not received or received == pending["contextId"]:
                        raise ValueError("An actual other original context was not returned.")
                    c.state["shopping_context_id"] = received
                else:
                    received = pending.get("status", {}).get("message", {}).get("taskId")
                    if type(received) is not str or not received or received == pending["id"]:
                        raise ValueError("An actual public child processor task reference was not returned.")
                    c.state["initiate_payment_task_id"] = received
                self.event("received-public-authority-fault", fault=f["fault"], received=received)
                if f["otp_response"] is not None:
                    try:
                        await self.call("adverse-original-payment-otp", self.business.initiate_payment_with_otp,
                                        f["otp_response"], c, debug_mode=False)
                    except A2AClientJSONRPCError as adverse_error:
                        if adverse_error.error.code not in {-32001, -32602}:
                            raise
                        self.event("adverse-original-rpc-error", public_rpc_error=public_json(adverse_error.error))
                try:
                    await self.read("adverse-authority-read")
                except Exception as fault_error:
                    if f["fault"] == "other_original_context" and isinstance(fault_error, PublicTaskAuthorityError):
                        disposition = "owned_caller_context_check_refused_actual_public_task"
                    elif (f["fault"] == "public_nested_processor_task" and isinstance(fault_error, A2AClientJSONRPCError)
                          and fault_error.error.code == -32001):
                        disposition = "original_merchant_task_store_returned_task_not_found"
                    else:
                        self.event("unexpected-adverse-read-error", error_type=type(fault_error).__name__, error=str(fault_error))
                        raise
                    self.event("adverse-read-disposition", disposition=disposition,
                               error_type=type(fault_error).__name__, error=str(fault_error))
                else:
                    raise ValueError("The adverse authority read was not refused.")
                # Only restore values actually returned on this caller's public read surface.
                c.state["initiate_payment_task_id"], c.state["shopping_context_id"] = pending["id"], pending["contextId"]
                self.event("recover-from-prior-public-task", task_id=pending["id"], context_id=pending["contextId"])
            if f["otp_response"] is None:
                outcome = "waiting_for_explicit_human_otp"
                final = await self.read("waiting-payment-task")
            else:
                await self.call("payment-otp", self.business.initiate_payment_with_otp, f["otp_response"], c, debug_mode=False)
                final = await self.read("after-original-otp")
                receipts = self.receipts(final)
                outcome = "completed_with_public_receipt" if final.get("status", {}).get("state") == "completed" and len(receipts) == 1 else "public_continuation_remains_incomplete"
                self.event("public-payment-observation", state=final.get("status", {}).get("state"), receipts=receipts)
                if f["repeat_after_completed"]:
                    if outcome != "completed_with_public_receipt":
                        raise ValueError("Duplicate continuation requires an actual completed public receipt first.")
                    await self.call("repeat-original-otp", self.business.initiate_payment_with_otp, f["otp_response"], c, debug_mode=False)
                    repeated = await self.read("after-repeated-original-otp")
                    self.event("public-repeat-observation", task=repeated, receipts=self.receipts(repeated))
        except Exception as caught:
            error = {"type": type(caught).__name__, "message": str(caught)}
            outcome = "actual_failed_or_partial_attempt_retained"
            self.event("actor-error", **error)
        return self.result(outcome, pending, final, error)

    def result(self, outcome, pending, final, error):
        return {"schema_version": "ap2-owned-public-scripted-continuation/1", "case_id": self.facts["case_id"],
                "status": outcome, "error": error, "source_records": self.source_records,
                "public_human_facts": self.facts, "original_business_calls": self.calls,
                "public_task_reads": self.public_reads, "public_pending_task": pending, "public_final_task": final,
                "caller_state": public_json(self.context.state), "actor_public_events": self.events,
                "owned_caller_and_public_read_intervention": True, "unchanged_adk_root_tool_qualification": False,
                "bridge_qualification_established": False, "provider_or_native_launcher_qualification_established": False,
                "evaluator_or_private_journal_inputs": [], "grade": None}
