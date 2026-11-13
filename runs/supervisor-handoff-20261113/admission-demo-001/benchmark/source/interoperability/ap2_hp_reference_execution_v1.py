"""Executable injected reference orchestration, without original imports.

Bindings must supply the original functions/builder/client through a separately
reviewed adapter. Constructed bindings exercise sequencing only. This module
does not start services, read credentials, authenticate source, or grant grades.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import inspect
import json
import math
from types import SimpleNamespace


MERCHANT = "http://localhost:8001/a2a/merchant_agent"
CREDENTIALS = "http://localhost:8002/a2a/credentials_provider"
EXTENSION = "https://github.com/google-agentic-commerce/ap2/v1"
PAYMENT = "ap2.mandates.PaymentMandateSdJwt"
CHECKOUT = "ap2.mandates.CheckoutMandateSdJwt"


class ExecutionError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise ExecutionError(reason)


def public_json(value):
    """Only an explicit public model dump or plain JSON, never __dict__."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True)
    def plain(item):
        if item is None or type(item) in (str, int, bool):
            return True
        if type(item) is float:
            return math.isfinite(item)
        if type(item) is list:
            return all(plain(child) for child in item)
        if type(item) is dict:
            return all(type(key) is str and plain(child) for key, child in item.items())
        return False
    require(plain(value), "Public snapshots require finite plain JSON with string object keys")
    # Detach observations without coercing object keys or consulting __dict__.
    return json.loads(json.dumps(value, allow_nan=False))


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(typed_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


async def invoke(function, *args, **kwargs):
    value = function(*args, **kwargs)
    return await value if inspect.isawaitable(value) else value


class PublicClientObserver:
    """Retain actual public return objects while returning them unchanged.

    Delegation leaves the original client's AP2 extension/discovery behavior
    untouched. This high-level boundary does not prove actual HTTP headers,
    raw bytes, client factory fidelity or connected-peer ownership.
    """
    def __init__(self, client, endpoint, *, serializer=public_json, sink=None):
        require(endpoint in (MERCHANT, CREDENTIALS), "Only original merchant/credentials boundaries are accepted")
        self.client, self.endpoint = client, endpoint
        self.serializer, self.sink = serializer, sink
        self.calls, self.records, self.observation_errors = [], [], []
        self.capture_complete = True

    def _record(self, call, boundary, value=None):
        try:
            row = {"sequence": len(self.records), "call": call["index"],
                   "endpoint": self.endpoint, "operation": call["operation"], "boundary": boundary}
            if value is not None:
                row["public_value"] = self.serializer(value)
            self.records.append(row)
            if self.sink is not None:
                self.sink(deepcopy(row))
            return row.get("public_value")
        except BaseException as error:
            self.capture_complete = False
            self.observation_errors.append({"call": call["index"], "boundary": boundary,
                                            "error_type": type(error).__name__})
            return None

    async def _call(self, operation, request=None):
        call = {"index": len(self.calls), "operation": operation, "request": request,
                "returned": None, "public_result": None, "error": None}
        self.calls.append(call)
        self._record(call, "attempt", request)
        try:
            method = getattr(self.client, operation)
            result = await invoke(method, request) if request is not None else await invoke(method)
        except BaseException as error:
            call["error"] = error
            self._record(call, "error")
            raise
        call["returned"] = result
        call["public_result"] = self._record(call, "returned", result)
        return result

    async def send_a2a_message(self, message):
        return await self._call("send_a2a_message", message)

    async def get_agent_card(self):
        return await self._call("get_agent_card")


@dataclass
class ReferenceBindings:
    merchant: PublicClientObserver
    credentials: PublicClientObserver
    builder_factory: object
    find_products: object
    select_cart: object
    get_shipping_address: object
    get_payment_methods: object
    get_payment_credential_token: object
    create_checkout: object
    create_checkout_mandate: object
    create_payment_mandate: object
    send_signed_mandates: object
    store_receipt: object


@dataclass
class ReferenceOutcome:
    status: str
    phase: str
    planning_report: dict
    public_records: list
    tool_returns: list = field(default_factory=list, repr=False)
    final_task: object = field(default=None, repr=False)
    error: object = field(default=None, repr=False)
    public_calls: list = field(default_factory=list, repr=False)

    def report(self):
        return {"schema_version": "ap2-hp-injected-reference-execution/1", "status": self.status,
                "phase": self.phase, "planning_report": deepcopy(self.planning_report),
                "public_records": deepcopy(self.public_records),
                "public_record_order": "coordinator_observer_boundary_order",
                "error_type": type(self.error).__name__ if self.error is not None else None,
                "scope": "injected public reference coordination",
                "original_bindings_authenticated": False, "native_execution_enabled": False,
                "native_qualification_established": False, "aggregate_task_grade": None,
                "required_http_extension": {"X-A2A-Extensions": EXTENSION},
                "http_extension_observed": False, "transport_peer_ownership_verified": False}


class ReferenceCoordinator:
    def __init__(self, bindings, planner_class, contract):
        require(bindings.merchant.endpoint == MERCHANT and bindings.credentials.endpoint == CREDENTIALS,
                "Reference roles must use original endpoints")
        require(not bindings.merchant.calls and not bindings.credentials.calls, "Fresh public observers are required")
        self.bindings, self.plan = bindings, planner_class(contract)
        self.context = SimpleNamespace(state={})  # disclosed caller carrier, not ADK ToolContext
        self.tool_returns = []
        self._started = False
        self.public_records = []
        for observer in (bindings.merchant, bindings.credentials):
            existing_sink = observer.sink
            def ordered_sink(row, prior=existing_sink):
                ordered = deepcopy(row)
                ordered["global_sequence"] = len(self.public_records)
                self.public_records.append(ordered)
                if prior is not None:
                    prior(row)
            observer.sink = ordered_sink

    async def _tool(self, phase, function, boundary, *args, card=False, **kwargs):
        starts = (len(self.bindings.merchant.calls), len(self.bindings.credentials.calls))
        returned = await invoke(function, *args, **kwargs)
        self.tool_returns.append((phase, returned))
        merchant = self.bindings.merchant.calls[starts[0]:]
        credentials = self.bindings.credentials.calls[starts[1]:]
        calls, other = (merchant, credentials) if boundary is self.bindings.merchant else (credentials, merchant)
        expected = ["send_a2a_message", "get_agent_card"] if card else ["send_a2a_message"]
        require(not other and [item["operation"] for item in calls] == expected,
                "Original tool's public call boundary was not captured exactly")
        require(all(item["error"] is None and item["public_result"] is not None for item in calls)
                and boundary.capture_complete, "Public observation is incomplete")
        observation = ({"task": calls[0]["public_result"], "agent_card": calls[1]["public_result"]}
                       if card else calls[0]["public_result"])
        self.plan.observe(phase, observation)
        return returned

    def _state_matches(self, *keys):
        for key in keys:
            left = self.context.state.get(key)
            right = self.plan.state.get(key)
            require(typed_equal(public_json(left), public_json(right)),
                    "Original caller state differs from public phase observation: " + key)

    def _payment_message(self, response=None, resume=False):
        state = self.context.state
        builder = self.bindings.builder_factory().set_context_id(state["shopping_context_id"])
        if resume:
            builder.set_task_id(state["initiate_payment_task_id"])
            builder.add_text("Initiate a payment. Include the challenge response.")
            pairs = [(PAYMENT, state["payment_mandate_sdjwt"]),
                     ("shopping_agent_id", "trusted_shopping_agent"), ("challenge_response", response),
                     ("risk_data", state.get("risk_data", "")), ("debug_mode", False)]
        else:
            builder.add_text("Initiate a payment")
            pairs = [(PAYMENT, state["payment_mandate_sdjwt"]), ("risk_data", state.get("risk_data", "")),
                     ("shopping_agent_id", "trusted_shopping_agent"), ("debug_mode", False)]
        for key, value in pairs:
            builder.add_data(key, value)
        checkout = state.get("checkout_mandate_sdjwt")
        if checkout:
            builder.add_data(CHECKOUT, checkout)
        return builder.build()  # original builder owns UUID4 generation/falsey omission

    async def run(self, *, choose_cart, choose_alias, approve, respond_otp):
        b, p, c = self.bindings, self.plan, self.context
        final, error = None, None
        try:
            require(not self._started, "Reference coordination is once-only")
            self._started = True
            carts = await self._tool("catalog", b.find_products, b.merchant, p.contract["catalog_search"], c, debug_mode=False)
            self._state_matches("shopping_context_id", "available_carts", "risk_data")
            require(isinstance(carts, list) and typed_equal([public_json(item) for item in carts], p.state["available_carts"]),
                    "Returned carts differ from public canonical carts")
            choice = await invoke(choose_cart, deepcopy(p.state["available_carts"]))
            p.observe("cart_selection", choice)
            self.tool_returns.append(("cart_selection", await invoke(b.select_cart, choice, c)))
            self._state_matches("chosen_cart_id")
            address = await self._tool("shipping", b.get_shipping_address, b.credentials, p.contract["user_email"], c)
            require(typed_equal(public_json(address), p.state["shipping_address"]), "Returned address differs from public canonical address")
            methods = await self._tool("payment_methods", b.get_payment_methods, b.credentials, p.contract["user_email"], c)
            require(type(public_json(methods)) is dict and typed_equal(public_json(methods).get("payment_method_aliases"), p.state["payment_method_aliases"]),
                    "Returned methods differ from public aliases")
            alias = await invoke(choose_alias, deepcopy(p.state["payment_method_aliases"]))
            p.observe("payment_selection", alias)
            await self._tool("credential_token", b.get_payment_credential_token, b.credentials,
                             p.contract["user_email"], alias, c, card=True)
            self._state_matches("payment_credential_token")
            await self._tool("checkout", b.create_checkout, b.merchant, c, debug_mode=False)
            self._state_matches("checkout_data")
            p.observe("approval", await invoke(approve, deepcopy(p.approval_summary())))
            for phase, function in (("checkout_mandate", b.create_checkout_mandate), ("payment_mandate", b.create_payment_mandate)):
                value = await invoke(function, c)
                self.tool_returns.append((phase, value))
                p.observe(phase, value)
                self._state_matches(phase + "_sdjwt")
            self._state_matches("checkout_hash")
            # Keep the actual Task even though the unchanged helper returns success text.
            await self._tool("cp_association", b.send_signed_mandates, b.credentials, c, debug_mode=False)
            task = await b.merchant.send_a2a_message(self._payment_message())
            require(b.merchant.capture_complete, "Merchant observation is incomplete")
            await invoke(b.store_receipt, task, c)
            p.observe("payment_start", b.merchant.calls[-1]["public_result"])
            c.state["initiate_payment_task_id"] = p.state["initiate_payment_task_id"]
            response = await invoke(respond_otp, deepcopy(p.state["public_challenge"]))
            p.observe("otp_response", response)
            final = await b.merchant.send_a2a_message(self._payment_message(response, resume=True))
            require(b.merchant.capture_complete, "Merchant observation is incomplete")
            await invoke(b.store_receipt, final, c)
            p.observe("payment_resume", b.merchant.calls[-1]["public_result"])
        except Exception as caught:
            error = caught
        return ReferenceOutcome("public_sequence_observed" if error is None else "refused_or_partial_reference",
                                p.phase, p.report(), deepcopy(self.public_records),
                                self.tool_returns, final, error, b.merchant.calls + b.credentials.calls)


@dataclass
class OwnedReferenceOutcome:
    group: object = field(repr=False)
    reference: object = None
    error: object = field(default=None, repr=False)
    cleanup_error: object = field(default=None, repr=False)
    settled: bool = False

    def report(self):
        return {"schema_version": "ap2-hp-injected-owned-reference/1",
                "status": "cleanup_incomplete_authority_retained" if not self.settled else "owned_reference_settled",
                "reference": self.reference.report() if self.reference is not None else None,
                "error_type": type(self.error).__name__ if self.error is not None else None,
                "cleanup_error_type": type(self.cleanup_error).__name__ if self.cleanup_error is not None else None,
                "live_authority_retained": not self.settled, "native_qualification_established": False,
                "aggregate_task_grade": None}


async def run_owned_reference(start_group, make_coordinator, decisions, publish):
    """Own an injected returned group through reference, publication and cleanup.

    Start must return its authority even on partial failure, as frozen GroupRun
    does. No factory/bootstrap/native adapter is supplied by this module.
    """
    group = await invoke(start_group)
    outcome = OwnedReferenceOutcome(group)
    try:
        require(group.report.get("status") == "owned_original_services_ready_without_case_execution",
                "Owned group did not establish readiness")
        coordinator = await invoke(make_coordinator, group)
        outcome.reference = await coordinator.run(**decisions)
        await invoke(publish, outcome.reference.report())
    except BaseException as error:
        outcome.error = error
    finally:
        try:
            stopped = await invoke(group.stop)
            outcome.settled = stopped is True and not group.owners
        except BaseException as error:
            outcome.cleanup_error = error
    return outcome  # retains the original authority if cleanup could not settle
