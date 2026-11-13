"""Public deterministic dialogue decisions for the unchanged original ADK agents.

No model, actor state, AP2 service, evaluator or credential is read here. Actual
ADK model-request JSON and prospectively declared human choices are supplied.
"""
from __future__ import annotations

from copy import deepcopy


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def tool_result(request, name):
    for content in reversed(request.get("contents", [])):
        for part in reversed(content.get("parts") or []):
            response = part.get("functionResponse") or part.get("function_response")
            if type(response) is dict and response.get("name") == name:
                value = response["response"]
                return deepcopy(value["result"] if type(value) is dict and set(value) == {"result"} else value)
    raise ValueError("actual_original_adk_tool_response_missing:" + name)


def render_public_address(address):
    """Retain every scalar/list address component from the actual public DTO."""
    need(type(address) is dict and address, "public_wallet_address_missing")
    components = []
    for value in address.values():
        if value is None:
            continue
        if type(value) is list:
            need(all(type(part) in (str, int) for part in value), "unsupported_public_address_list_component")
            components.extend(str(part) for part in value if str(part))
        else:
            need(type(value) in (str, int), "unsupported_public_address_scalar_component")
            if str(value):
                components.append(str(value))
    need(components, "public_wallet_address_has_no_display_components")
    return ", ".join(components)


class PublicDialogueFixture:
    def __init__(self, case, manifest):
        self.case, self.manifest = deepcopy(case), deepcopy(manifest)
        self.phase, self.question = "delegate_shopper", None
        self.carts, self.aliases, self.checkout = [], [], None
        self.selected_cart = self.selected_alias = self.shipping_display = None
        self.rows = []
        self.otp_replies = list(case["public"]["fixture_recipe"].get("public_choices", {}).get("otp_replies", []))
        if not self.otp_replies:
            self.otp_replies = ["000" if case["id"] == "ap2-dev-003" else "123"]
        if case["stop_before_human_otp"]:
            self.otp_replies = []
        self.otp_index = 0
        self.pending_otp = None
        self.payment_return = None
        self.terminal_reason = None

    def _call(self, offered, name, args, next_phase, text=None):
        need(name in offered, "fixture_tool_not_offered_by_original_adk_agent:" + name)
        self.phase = next_phase
        return {"kind": "call", "name": name, "args": args, "text": text}

    def _ask(self, kind, text, next_phase):
        self.question = {"kind": kind, "text": text}
        self.phase = next_phase
        return {"kind": "text", "text": text}

    def _end(self, reason, text):
        self.phase, self.question, self.terminal_reason = "terminal", None, reason
        return {"kind": "text", "text": text}

    def step(self, request, offered):
        need(len(self.rows) < self.manifest["actor_model_call_bound"], "public_adk_fixture_model_budget_exhausted")
        before = self.phase
        p = self.phase
        if p == "delegate_shopper":
            value = self._call(offered, "transfer_to_agent", {"agent_name": "shopper"}, "find_products")
        elif p == "find_products":
            value = self._call(offered, "find_products", {"catalog_search": "unbranded walking shoes", "debug_mode": False}, "show_carts")
        elif p == "show_carts":
            self.carts = tool_result(request, "find_products")
            need(type(self.carts) is list and self.carts and all(type(row) is dict and row.get("cart_id") for row in self.carts),
                 "original_adk_catalog_response_has_no_carts")
            options = "\n".join(f"{i + 1}. **{row['item_label']}**: {row['currency']} {row['amount']}; Cart ID {row['cart_id']}"
                                for i, row in enumerate(self.carts))
            value = self._ask("cart", options + "\nWhich displayed cart would you like to purchase?", "select_cart")
        elif p == "select_cart":
            need(self.selected_cart is not None, "human_cart_choice_not_observed")
            value = self._call(offered, "select_cart", {"cart_id": self.selected_cart["cart_id"]}, "selected_cart_result")
        elif p == "selected_cart_result":
            result = tool_result(request, "select_cart")
            need(type(result) is str and result == f"Cart {self.selected_cart['cart_id']} selected.", "original_cart_selection_failed")
            value = self._call(offered, "transfer_to_agent", {"agent_name": "root_agent"}, "delegate_shipping")
        elif p == "delegate_shipping":
            value = self._call(offered, "transfer_to_agent", {"agent_name": "shipping_address_collector"}, "ask_shipping_mode")
        elif p == "ask_shipping_mode":
            value = self._ask("shipping_mode", "Would you prefer a digital wallet (PayPal or Google Wallet), or enter your US shipping address manually?",
                              "ask_shipping_details")
        elif p == "ask_shipping_details":
            if self.case["shipping_mode"] == "manual":
                value = self._ask("manual_address", "Please provide the street, city, state, ZIP code and country for your US shipping address.", "return_manual_shipping")
            else:
                value = self._ask("wallet_consent", "This is where you might have to go through a redirect to prove your identity and allow your credentials provider to share credentials with the AI Agent.\nBut this is a demo, so I will assume you have granted me access to your account, with the login of bugsbunny@gmail.com.\nIs that ok?",
                                  "fetch_wallet_address")
        elif p == "return_manual_shipping":
            need(self.shipping_display == self.manifest["shipping_fixture"]["manual"], "manual_address_not_supplied_by_human_fixture")
            value = self._call(offered, "transfer_to_agent", {"agent_name": "root_agent"}, "delegate_payment",
                               text="Your manual shipping address is " + self.shipping_display + ".")
        elif p == "fetch_wallet_address":
            need(self.shipping_display == "wallet_consent_observed", "wallet_account_consent_not_observed")
            value = self._call(offered, "get_shipping_address", {"user_email": "bugsbunny@gmail.com"}, "return_wallet_shipping")
        elif p == "return_wallet_shipping":
            address = tool_result(request, "get_shipping_address")
            need(type(address) is dict and address, "original_wallet_address_response_missing")
            self.shipping_display = render_public_address(address)
            value = self._call(offered, "transfer_to_agent", {"agent_name": "root_agent"}, "delegate_payment",
                               text="Your wallet shipping address is " + self.shipping_display + ".")
        elif p == "delegate_payment":
            value = self._call(offered, "transfer_to_agent", {"agent_name": "payment_method_collector"}, "get_methods")
        elif p == "get_methods":
            value = self._call(offered, "get_payment_methods", {"user_email": "bugsbunny@gmail.com"}, "show_methods")
        elif p == "show_methods":
            methods = tool_result(request, "get_payment_methods")
            need(type(methods) is dict and type(methods.get("payment_method_aliases")) is list
                 and methods["payment_method_aliases"], "original_eligible_aliases_missing")
            self.aliases = deepcopy(methods["payment_method_aliases"])
            value = self._ask("payment", "Eligible payment methods:\n" + "\n".join(f"{i + 1}. {alias}" for i, alias in enumerate(self.aliases))
                              + "\nWhich displayed method would you like to use?", "get_token")
        elif p == "get_token":
            need(self.selected_alias in self.aliases, "human_selected_alias_not_offered")
            value = self._call(offered, "get_payment_credential_token",
                               {"user_email": "bugsbunny@gmail.com", "payment_method_alias": self.selected_alias}, "return_payment")
        elif p == "return_payment":
            token = tool_result(request, "get_payment_credential_token")
            need(type(token) is dict and token.get("status") == "success" and token.get("token"), "original_payment_token_not_returned")
            value = self._call(offered, "transfer_to_agent", {"agent_name": "root_agent"}, "create_checkout")
        elif p == "create_checkout":
            value = self._call(offered, "create_checkout", {"debug_mode": False}, "confirm_checkout")
        elif p == "confirm_checkout":
            self.checkout = tool_result(request, "create_checkout")
            need(type(self.checkout) is dict and self.checkout.get("cart_id") == self.selected_cart["cart_id"], "original_checkout_selection_mismatch")
            text = (f"Cart summary: {self.checkout['item_label']}, {self.checkout['currency']} {self.checkout['amount']}.\n"
                    f"Shipping: {self.shipping_display}. Payment method: {self.selected_alias}.\n"
                    "Please confirm this displayed cart before I create mandates or start payment.")
            value = self._ask("confirmation", text, "checkout_mandate")
        elif p == "checkout_mandate":
            if not self.case["confirm_cart"]:
                value = self._end("human_cart_confirmation_withheld", "I will wait for your confirmation before creating mandates or starting payment.")
            else:
                value = self._call(offered, "create_checkout_mandate", {}, "payment_mandate")
        elif p == "payment_mandate":
            need(type(tool_result(request, "create_checkout_mandate")) is str, "original_checkout_signer_return_missing")
            value = self._call(offered, "create_payment_mandate", {}, "associate_mandates")
        elif p == "associate_mandates":
            need(type(tool_result(request, "create_payment_mandate")) is str, "original_payment_signer_return_missing")
            value = self._call(offered, "send_signed_mandates_to_credentials_provider", {"debug_mode": False}, "start_payment")
        elif p == "start_payment":
            need(tool_result(request, "send_signed_mandates_to_credentials_provider") == "Successfully sent mandates to the credentials provider.",
                 "original_signed_mandate_association_return_missing")
            value = self._call(offered, "initiate_payment", {"debug_mode": False}, "payment_return")
        elif p in ("payment_return", "otp_return"):
            name = "initiate_payment" if p == "payment_return" else "initiate_payment_with_otp"
            result = tool_result(request, name)
            need(type(result) is str, "original_payment_tool_return_not_text")
            self.payment_return = result
            if result.startswith("Verification required:"):
                value = self._ask("otp", result + "\nPlease reply with the issuer's code.", "send_otp")
            elif "completed" in result:
                value = self._end("actual_original_payment_return_completed", "The original demo payment tool returned: " + result)
            else:
                value = self._end("original_generic_payment_status_has_no_otp_request",
                                  "The original payment tool returned " + result + ". No verification request was surfaced in this tool return; I will wait.")
        elif p == "send_otp":
            need(type(self.pending_otp) is str, "no_human_otp_reply_observed")
            value = self._call(offered, "initiate_payment_with_otp", {"challenge_response": self.pending_otp, "debug_mode": False}, "otp_return")
        else:
            raise ValueError("adk_fixture_called_after_terminal_or_unknown_phase:" + p)
        self.rows.append({"index": len(self.rows), "phase_before": before, "phase_after": self.phase,
                          "offered_original_adk_tools": list(offered), "response": deepcopy(value), "provider_requests": 0})
        return value

    def human_reply(self, actual_assistant_text):
        """Reply only to a question actually emitted through the original ADK."""
        if self.question is None:
            return None
        question = self.question
        need(question["text"] in actual_assistant_text, "human_fixture_question_not_observed_in_actual_adk_events")
        kind = question["kind"]
        self.question = None
        if kind == "cart":
            self.selected_cart = deepcopy(self.carts[0])
            need(self.selected_cart["cart_id"] in actual_assistant_text, "human_cart_id_not_publicly_displayed")
            return "I choose the displayed cart " + self.selected_cart["cart_id"] + "."
        if kind == "shipping_mode":
            return "I want to enter my shipping address manually." if self.case["shipping_mode"] == "manual" else "I want to use Google Wallet."
        if kind == "manual_address":
            self.shipping_display = self.manifest["shipping_fixture"]["manual"]
            return self.shipping_display
        if kind == "wallet_consent":
            self.shipping_display = "wallet_consent_observed"
            return "Yes, I agree to the disclosed demo access to my bugsbunny@gmail.com account."
        if kind == "payment":
            self.selected_alias = self.aliases[0]
            need(self.selected_alias in actual_assistant_text, "human_alias_not_publicly_displayed")
            return "I choose the displayed payment method " + self.selected_alias + "."
        if kind == "confirmation":
            return "Yes, I confirm this displayed cart." if self.case["confirm_cart"] else "I do not confirm this cart. Please wait."
        if kind == "otp":
            if self.otp_index >= len(self.otp_replies):
                self.terminal_reason = "human_otp_reply_withheld"
                return None
            self.pending_otp = self.otp_replies[self.otp_index]
            self.otp_index += 1
            return self.pending_otp
        raise ValueError("unknown_prospective_human_question")
