"""Pure preparation planner for an original AP2 merchant-front-door caller.

No AP2/SDK/provider/client/credential import or execution is performed. Supplied
observations are untrusted planning inputs, never authenticated native results.
Original remote applications and signer/client functions are not implemented
or replaced here. A source-bound bootstrap/usage contract remains required.
"""
from __future__ import annotations

import ast
import base64
from copy import deepcopy
import hashlib
import math
import re


SCHEMA = "ap2-hp-reference-plan/1"
MANDATE_KEY = "ap2.mandates.PaymentMandateSdJwt"
CHECKOUT_MANDATE_KEY = "ap2.mandates.CheckoutMandateSdJwt"
CART_KEY = "ap2.cart"
ADDRESS_KEY = "contact_picker.ContactAddress"
METHOD_KEY = "payment_request.PaymentMethodData"
RISK_DATA = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
MERCHANT = "http://localhost:8001/a2a/merchant_agent"
CREDENTIALS = "http://localhost:8002/a2a/credentials_provider"
EXTENSION = "https://github.com/google-agentic-commerce/ap2/v1"
PHASES = (
    "catalog", "cart_selection", "shipping", "payment_methods",
    "payment_selection", "credential_token", "checkout", "approval",
    "checkout_mandate", "payment_mandate", "cp_association", "payment_start",
    "otp_response", "payment_resume",
)
CALLER_FILES = {
    "roles/shopping_agent/tools.py": "612525025661b608a662a8a09bc50ea527543b26c3bdbc78911bd95f6c3926a6",
    "roles/shopping_agent/subagents/shopper/tools.py": "7a577d4088dc9decb3bbe72d3162e356176a4f6b1b0c3cb87d496be4e6245bc4",
    "roles/shopping_agent/subagents/shipping_address_collector/tools.py": "6c11b152344289c075fc66595c7ed344a37c2762c549532c8a9c275ecf8d542d",
    "roles/shopping_agent/subagents/payment_method_collector/tools.py": "be4b5fea7a4c0eef965694cde93205ce1b1652a36c0f121fa7ec6d820fbed8dd",
}


class PlanningError(ValueError):
    pass


def need(value, reason):
    if not value:
        raise PlanningError(reason)


def string(value):
    return isinstance(value, str) and bool(value)


def numeric(value):
    return type(value) is int or type(value) is float and math.isfinite(value)


def json_value(value):
    kind = type(value)
    if value is None or kind in (str, bool, int):
        return True
    if kind is float:
        return math.isfinite(value)
    if kind is list:
        return all(json_value(item) for item in value)
    if kind is dict:
        return all(type(key) is str and json_value(item) for key, item in value.items())
    return False


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(typed_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def exact_message(text, data, *, message_id, context_id=None, task_id=None):
    """Original A2aMessageBuilder JSON form, including falsey DataPart omission.

    A fresh caller-provided message ID is required; this pure helper neither
    generates nor sends a message. No caller field is coerced to a string.
    """
    need(isinstance(message_id, str) and re.fullmatch(r"[0-9a-f]{32}", message_id) is not None and string(text), "A supplied source-shaped UUID hex nonce and nonempty text are required.")
    need(isinstance(data, list), "Ordered (key, value) DataPart pairs are required.")
    parts = [{"kind": "text", "text": text}]
    for pair in data:
        need(isinstance(pair, (list, tuple)) and len(pair) == 2, "Malformed ordered DataPart pair.")
        key, value = pair
        need(string(key), "A nonempty source DataPart key is required.")
        need(json_value(value), "DataPart values must be finite plain JSON values.")
        if value:
            parts.append({"kind": "data", "data": {key: deepcopy(value)}})
    result = {"kind": "message", "messageId": message_id, "role": "agent", "parts": parts}
    if context_id is not None:
        need(string(context_id), "Nonempty context identity is required when supplied.")
        result["contextId"] = context_id
    if task_id is not None:
        need(string(task_id), "Nonempty task identity is required when supplied.")
        result["taskId"] = task_id
    return result


def _task(value, context=None, states=("completed",)):
    need(isinstance(value, dict) and value.get("kind") == "task", "A supplied public Task object is required.")
    need(string(value.get("id")) and string(value.get("contextId")), "Supplied task/context identities are incomplete.")
    need(isinstance(value.get("status"), dict), "Supplied task status is incomplete.")
    need(value["status"].get("state") in states, "Original source task did not reach this phase's required public state.")
    if context is not None:
        need(value["contextId"] == context, "Supplied task belongs to a different shopping context.")
    return value


def _data_parts(task):
    need(isinstance(task.get("artifacts"), list), "Supplied task artifacts are incomplete.")
    values = []
    for artifact in task["artifacts"]:
        need(isinstance(artifact, dict) and isinstance(artifact.get("parts"), list), "Malformed supplied artifact.")
        for part in artifact["parts"]:
            _valid_part(part)
            if part.get("kind") == "data":
                need(isinstance(part.get("data"), dict), "Malformed supplied artifact DataPart.")
                values.append(part["data"])
    return values


def _valid_part(part):
    need(isinstance(part, dict) and part.get("kind") in ("text", "data"), "Malformed or unsupported supplied Part shape.")
    if part["kind"] == "text":
        need(isinstance(part.get("text"), str), "Supplied TextPart text is incomplete.")
    else:
        need(isinstance(part.get("data"), dict), "Supplied DataPart data is incomplete.")


def _canonical(task, key):
    return [data[key] for data in _data_parts(task) if key in data]


def _only(values, reason):
    need(len(values) == 1, reason)
    return values[0]


def _first(task):
    return _only(_data_parts(task)[:1], "The original first DataPart result is absent.")


def _hash(value):
    return base64.urlsafe_b64encode(hashlib.sha256(value.encode("utf-8")).digest()).decode("ascii").rstrip("=")


def _address_projection(address):
    fields = {"city", "country", "dependent_locality", "organization", "phone_number", "postal_code",
              "recipient", "region", "sorting_code"}
    need(isinstance(address, dict) and bool(set(address) & (fields | {"address_line"})), "Supplied address has no source ContactAddress field.")
    for field in fields:
        need(field not in address or address[field] is None or isinstance(address[field], str), "Supplied ContactAddress string/null projection differs.")
    lines = address.get("address_line")
    need(lines is None or isinstance(lines, list) and all(isinstance(line, str) for line in lines), "Supplied address_line must be a string list or null.")


def _new_task(state, task):
    previous = state.setdefault("supplied_distinct_prelude_task_ids", [])
    need(task["id"] not in previous, "A newly initiated source phase reused an earlier supplied task ID.")
    previous.append(task["id"])


def inspect_caller_footprint(files):
    """Static exact-byte closure only; never import or execute caller sources."""
    need(isinstance(files, dict) and set(files) == set(CALLER_FILES), "Exact four original caller source files are required.")
    rows = []
    for name, expected in CALLER_FILES.items():
        raw = files[name]
        need(isinstance(raw, bytes), "Original caller source bytes are required.")
        digest = hashlib.sha256(raw).hexdigest()
        need(digest == expected, "Original caller source digest differs: " + name)
        tree = ast.parse(raw, filename=name)
        attributes = sorted({node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "tool_context"})
        need(attributes == ["state"], "Original ToolContext attribute footprint differs: " + name)
        rows.append({"path": name, "sha256": digest, "context_attributes": attributes})
    return {"schema_version": "ap2-hp-caller-footprint/1", "status": "exact_source_static_footprint_matched",
            "files": rows, "imports_executed": False, "runtime_equivalence_established": False}


class ReferencePlan:
    """Incremental pure caller plan from explicitly supplied phase observations.

    `observe` never calls business logic. Source-like failure/malformed input
    raises PlanningError without advancing. Each follow-up uses public IDs from
    supplied Task objects; no processor ID or private state is accepted.
    """
    def __init__(self, contract):
        required = {"catalog_search", "user_email", "currency", "max_amount_cents"}
        need(json_value(contract), "Reference contract must contain finite plain JSON values.")
        need(isinstance(contract, dict) and set(contract) == required, "Exact declared reference-contract fields are required.")
        need(all(string(contract[key]) for key in required - {"max_amount_cents"}), "Reference contract strings are incomplete.")
        need(type(contract["max_amount_cents"]) is int and contract["max_amount_cents"] >= 0, "A nonnegative integer reference spending cap is required.")
        self.contract = deepcopy(contract)
        self.state = {"risk_data": RISK_DATA}
        self.index = 0
        self.observations = []

    @property
    def phase(self):
        return PHASES[self.index] if self.index < len(PHASES) else "finished"

    def approval_summary(self):
        need("checkout_data" in self.state and "payment_method_alias" in self.state, "Actual checkout and payment choice are required before approval.")
        checkout = self.state["checkout_data"]
        return {"cart_id": checkout["cart_id"], "checkout_hash": checkout["checkout_hash"],
                "item_label": checkout["item_label"], "amount_cents": checkout["amount_cents"],
                "currency": checkout["currency"], "payment_method_alias": self.state["payment_method_alias"],
                "shipping_address": deepcopy(self.state["shipping_address"])}

    def next_action(self, *, message_id=None):
        phase, state = self.phase, self.state
        local = {
            "cart_selection": ("select_cart", {"available_carts": state.get("available_carts", [])}),
            "payment_selection": ("select_returned_payment_alias", {"payment_method_aliases": state.get("payment_method_aliases", [])}),
            "approval": ("record_explicit_reference_approval", self.approval_summary() if "checkout_data" in state else {}),
            "checkout_mandate": ("roles.shopping_agent.tools.create_checkout_mandate", {}),
            "payment_mandate": ("roles.shopping_agent.tools.create_payment_mandate", {}),
            "otp_response": ("record_response_to_public_merchant_otp", {"public_challenge": state.get("public_challenge")}),
        }
        if phase == "finished":
            return {"phase": phase, "kind": "planning_finished_without_task_grade", "dispatch_eligible": False}
        if phase in local:
            operation, inputs = local[phase]
            return {"phase": phase, "kind": "local_original_source_or_reference_action_required",
                    "operation": operation, "inputs": deepcopy(inputs), "dispatch_eligible": False}
        data, context, task_id, endpoint = [], state.get("shopping_context_id"), None, CREDENTIALS
        if phase == "catalog":
            text, endpoint, context = "Find products that match the user's request.", MERCHANT, None
            data = [("catalog_search", self.contract["catalog_search"]), ("risk_data", state["risk_data"]),
                    ("debug_mode", False), ("shopping_agent_id", "trusted_shopping_agent")]
        elif phase == "shipping":
            text = "Get the user's shipping address."
            data = [("user_email", self.contract["user_email"])]
        elif phase == "payment_methods":
            text = "Get a filtered list of the user's payment methods."
            data = [("user_email", self.contract["user_email"]), (METHOD_KEY, {"supported_methods": "CARD", "data": {"network": ["mastercard", "amex"]}})]
        elif phase == "credential_token":
            text = "Get a payment credential token for the user's payment method."
            data = [("payment_method_alias", state["payment_method_alias"]), ("user_email", self.contract["user_email"])]
        elif phase == "checkout":
            text, endpoint = "Create a checkout for the selected cart.", MERCHANT
            data = [("cart_id", state["chosen_cart_id"]), ("shopping_agent_id", "trusted_shopping_agent"), ("debug_mode", False)]
        elif phase == "cp_association":
            text = "This is the signed payment mandate"
            data = [(MANDATE_KEY, state["payment_mandate_sdjwt"]), ("risk_data", state["risk_data"]), ("debug_mode", False)]
        else:
            need(phase in ("payment_start", "payment_resume"), "Unsupported planning phase.")
            endpoint = MERCHANT
            if phase == "payment_start":
                text = "Initiate a payment"
                data = [(MANDATE_KEY, state["payment_mandate_sdjwt"]), ("risk_data", state["risk_data"]),
                        ("shopping_agent_id", "trusted_shopping_agent"), ("debug_mode", False)]
            else:
                text, task_id = "Initiate a payment. Include the challenge response.", state["initiate_payment_task_id"]
                data = [(MANDATE_KEY, state["payment_mandate_sdjwt"]), ("shopping_agent_id", "trusted_shopping_agent"),
                        ("challenge_response", state["challenge_response"]), ("risk_data", state["risk_data"]), ("debug_mode", False)]
            data.append((CHECKOUT_MANDATE_KEY, state["checkout_mandate_sdjwt"]))
        return {"phase": phase, "kind": "source_exact_public_message_plan", "endpoint": endpoint,
                "required_extensions": [EXTENSION], "message": exact_message(text, data, message_id=message_id, context_id=context, task_id=task_id),
                "transport_preconditions": {"extension_header": "X-A2A-Extensions", "required_value": EXTENSION,
                    "message_metadata_substitution_permitted": False, "delegate_original_pinned_client": True},
                "message_identity_provenance": "caller_supplied_planning_nonce_not_original_builder_execution",
                "original_router_choice": "unknown", "dispatch_eligible": False}

    def observe(self, phase, value):
        need(phase == self.phase, "Observation phase is out of order.")
        need(json_value(value), "Supplied observations must contain finite plain JSON values.")
        state = deepcopy(self.state)
        if phase == "catalog":
            task = _task(value)
            _new_task(state, task)
            carts = _canonical(task, CART_KEY)
            need(carts, "Original catalog supplied no canonical cart.")
            for cart in carts:
                need(isinstance(cart, dict) and all(string(cart.get(key)) for key in ("cart_id", "item_label", "currency")), "Supplied cart projection is incomplete.")
                need(numeric(cart.get("amount")) and cart["amount"] >= 0, "Supplied cart amount is invalid.")
            need(len({cart["cart_id"] for cart in carts}) == len(carts), "Duplicate supplied cart identities are ambiguous.")
            state.update(shopping_context_id=task["contextId"], available_carts=deepcopy(carts))
        elif phase == "cart_selection":
            selected = _only([cart for cart in state["available_carts"] if cart["cart_id"] == value], "Selection must match exactly one returned cart.")
            need(selected["currency"] == self.contract["currency"] and int(round(selected["amount"] * 100)) <= self.contract["max_amount_cents"], "Selected returned cart violates the declared reference spending contract.")
            state.update(chosen_cart_id=value, selected_cart=deepcopy(selected))
        elif phase == "shipping":
            task = _task(value, state["shopping_context_id"])
            _new_task(state, task)
            address = _only(_canonical(task, ADDRESS_KEY), "An unambiguous canonical source address is required.")
            _address_projection(address)
            state["shipping_address"] = deepcopy(address)
        elif phase == "payment_methods":
            task = _task(value, state["shopping_context_id"])
            _new_task(state, task)
            aliases = _first(task).get("payment_method_aliases")
            need(isinstance(aliases, list) and aliases and all(string(alias) for alias in aliases), "Original first DataPart supplied no selectable eligible aliases.")
            state["payment_method_aliases"] = deepcopy(aliases)
        elif phase == "payment_selection":
            need(string(value) and value in state["payment_method_aliases"], "Payment selection must be an actually returned eligible alias.")
            state["payment_method_alias"] = value
        elif phase == "credential_token":
            need(isinstance(value, dict) and set(value) == {"task", "agent_card"}, "Original token task plus actually discovered credentials-provider card are required.")
            task = _task(value["task"], state["shopping_context_id"])
            _new_task(state, task)
            token = _first(task).get("token")
            need(string(token), "Original first token DataPart is missing.")
            card = value["agent_card"]
            need(isinstance(card, dict) and string(card.get("url")), "Actually discovered credentials-provider card URL is missing.")
            state["payment_credential_token"] = {"value": token, "url": card["url"]}
        elif phase == "checkout":
            task = _task(value, state["shopping_context_id"])
            _new_task(state, task)
            checkout = _only(_canonical(task, "ap2.checkout"), "A unique canonical checkout is required.")
            need(isinstance(checkout, dict), "Checkout projection is incomplete.")
            need(numeric(checkout.get("amount")) and checkout["amount"] >= 0, "Supplied checkout major amount is invalid.")
            selected = state["selected_cart"]
            need(all(checkout.get(key) == selected.get(key) for key in ("cart_id", "item_label", "amount", "currency")), "Checkout differs from the selected returned offer.")
            need(type(checkout.get("amount_cents")) is int and checkout["amount_cents"] == int(round(selected["amount"] * 100)), "Checkout minor amount differs from the original source rounding.")
            need(string(checkout.get("checkout_jwt")) and checkout.get("checkout_hash") == _hash(checkout["checkout_jwt"]), "Checkout hash does not match supplied exact JWT bytes; this is not signature validation.")
            state["checkout_data"] = deepcopy(checkout)
        elif phase == "approval":
            need(isinstance(value, dict) and set(value) == {"approved", "summary"} and value["approved"] is True and typed_equal(value["summary"], self.approval_summary()), "Explicit approval must match the actual typed checkout/address/payment summary.")
            state["explicit_reference_approval"] = deepcopy(value)
        elif phase in ("checkout_mandate", "payment_mandate"):
            need(string(value), "An actual original signer output must be supplied; no mandate is generated by this planner.")
            state[phase + "_sdjwt"] = value
            if phase == "checkout_mandate":
                state["checkout_hash"] = state["checkout_data"]["checkout_hash"]
        elif phase == "cp_association":
            task = _task(value, state["shopping_context_id"])
            _new_task(state, task)
            state["cp_association_public_completion_observed"] = True
        elif phase == "payment_start":
            task = _task(value, state["shopping_context_id"], ("input_required",))
            _new_task(state, task)
            message = task["status"].get("message")
            need(isinstance(message, dict) and message.get("kind") == "message" and isinstance(message.get("parts"), list), "A public merchant challenge message is required.")
            for part in message["parts"]:
                _valid_part(part)
            challenges = [part["data"]["challenge"] for part in message["parts"] if isinstance(part, dict) and part.get("kind") == "data" and isinstance(part.get("data"), dict) and "challenge" in part["data"]]
            challenge = _only(challenges, "A unique public OTP challenge is required.")
            need(isinstance(challenge, dict) and challenge.get("type") == "otp" and string(challenge.get("display_text")), "The supplied public challenge is not the original OTP projection.")
            state.update(initiate_payment_task_id=task["id"], public_challenge=deepcopy(challenge))
        elif phase == "otp_response":
            need(isinstance(value, str), "An explicit caller response to the public OTP request is required.")
            state["challenge_response"] = value
        elif phase == "payment_resume":
            task = _task(value, state["shopping_context_id"], ("completed", "input_required", "failed", "rejected", "canceled"))
            need(task["id"] == state["initiate_payment_task_id"], "Later merchant task differs from the original pending task.")
            state["supplied_merchant_after"] = deepcopy(task)
            target = "completed" if state["challenge_response"] == "123" else "input_required"
            state["source_branch_requested_target"] = target
            state["supplied_continuation_target_observed"] = task["status"]["state"] == target
        else:
            raise PlanningError("No observation is accepted after the fixed planned sequence.")
        self.state = state
        self.observations.append({"phase": phase, "supplied_value": deepcopy(value)})
        self.index += 1

    def report(self):
        return {"schema_version": SCHEMA, "scope": "pure_source_derived_caller_planning_only",
                "next_phase": self.phase, "observations": deepcopy(self.observations),
                "caller_state": deepcopy(self.state), "aggregate_task_grade": None,
                "native_execution_enabled": False, "native_qualification_established": False,
                "original_source_authenticated": False, "capture_order_and_completeness": "unknown",
                "credential_transaction_association": "unknown", "mandate_signatures": "unknown",
                "source_reset_and_effects": "unknown", "model_usage_guard": "not_implemented",
                "bootstrap_environment_gate_contract": "not_implemented"}
