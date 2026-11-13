"""Run original ADK agents with disclosed deterministic model/human fixtures."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

from .ap2_hp_reference_execution_v1 import ReferenceCoordinator, ReferenceOutcome
from .ap2_original_shopper_fixture_v7 import PublicDialogueFixture, need


def append(path, value):
    with Path(path).open("ab") as handle:
        handle.write((json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())
        handle.flush()
        os.fsync(handle.fileno())


class OriginalShopperConversation(ReferenceCoordinator):
    def __init__(self, bindings, planner_class, contract, *, output, case, manifest, writer, serializer,
                 source_binding, fingerprint):
        super().__init__(bindings, planner_class, contract)
        self.output, self.case, self.manifest = Path(output), case, manifest
        self.write, self.serialize, self.source_binding, self.fingerprint = writer, serializer, source_binding, fingerprint
        self.fixture = PublicDialogueFixture(case, manifest)
        self.events, self.human_turns, self.tool_capture, self.source_checks = [], [], [], []

    def _authenticate_original_agents(self, root_agent, retrying):
        stage = self.source_binding.source_root
        modules = ["common.retrying_llm_agent", "roles.shopping_agent.agent",
                   "roles.shopping_agent.subagents.shopper.agent",
                   "roles.shopping_agent.subagents.shipping_address_collector.agent",
                   "roles.shopping_agent.subagents.payment_method_collector.agent"]
        for name in modules:
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            need(path.is_relative_to(stage), "original_adk_agent_module_outside_source_pin")
            rel = path.relative_to(stage).as_posix()
            raw = path.read_bytes()
            need(hashlib.sha256(raw).hexdigest() == self.source_binding.source_files[rel]["sha256"], "original_adk_agent_module_hash_mismatch")
            self.source_checks.append({"module": name, "source_file": rel, "sha256": hashlib.sha256(raw).hexdigest()})
        module = importlib.import_module("common.retrying_llm_agent")
        path = Path(module.__file__).resolve()
        compiled = compile(path.read_bytes(), str(path), "exec", dont_inherit=True, optimize=0)
        def codes(code):
            yield code
            for child in code.co_consts:
                if type(child) is type(code):
                    yield from codes(child)
        for name in ("__init__", "_retry_async", "_run_async_impl"):
            actual = getattr(retrying, name)
            candidates = [code for code in codes(compiled) if code.co_qualname == "RetryingLlmAgent." + name]
            need(len(candidates) == 1 and self.fingerprint(actual.__code__) == self.fingerprint(candidates[0]),
                 "original_retrying_adk_method_structural_mismatch:" + name)
            self.source_checks.append({"qualified_name": "RetryingLlmAgent." + name, "full_structural_code_equal": True})
        agents = [root_agent] + root_agent.sub_agents
        expected_names = ["root_agent", "shopper", "shipping_address_collector", "payment_method_collector"]
        need([agent.name for agent in agents] == expected_names and all(type(agent) is retrying for agent in agents),
             "original_adk_root_and_subagent_membership_changed")
        tool_modules = {agent.name: importlib.import_module("roles.shopping_agent.tools" if agent.name == "root_agent"
            else "roles.shopping_agent.subagents." + agent.name + ".tools") for agent in agents}
        configs = []
        for agent in agents:
            need(agent.model == "gemini-3.1-flash-lite-preview" and type(agent.instruction) is str,
                 "original_adk_agent_model_or_instruction_changed")
            need(all(getattr(tool_modules[agent.name], function.__name__) is function for function in agent.tools),
                 "original_adk_tool_function_alias_changed")
            configs.append({"name": agent.name, "model": agent.model, "class": type(agent).__module__ + "." + type(agent).__qualname__,
                "instruction": agent.instruction, "instruction_sha256": hashlib.sha256(agent.instruction.encode()).hexdigest(),
                "tools": [function.__module__ + "." + function.__qualname__ for function in agent.tools],
                "sub_agents": [child.name for child in agent.sub_agents]})
        return configs

    async def run(self):
        from google import genai
        from google.adk.models.base_llm import BaseLlm
        from google.adk.models.llm_response import LlmResponse
        from google.adk.models import registry
        from google.adk.plugins.base_plugin import BasePlugin
        from google.adk.runners import Runner
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        from google.adk.tools.tool_context import ToolContext
        fixture, output, serialize, captures = self.fixture, self.output, self.serialize, self.tool_capture
        registry_before = registry._llm_registry_dict.copy()
        error = final = None
        initial_configs = None
        runner = None
        session = None
        class DeterministicOriginalShopperLlm(BaseLlm):
            @classmethod
            def supported_models(cls):
                return [r"gemini-.*"]

            async def generate_content_async(self, llm_request, stream=False):
                need(self.model == "gemini-3.1-flash-lite-preview" and stream is False, "unsupported_original_adk_model_or_stream")
                public = serialize(llm_request)
                offered = list(llm_request.tools_dict)
                response = fixture.step(public, offered)
                row = deepcopy(fixture.rows[-1])
                row["public_model_request"] = public
                append(output / "adk-model-interventions.jsonl", row)
                parts = []
                if response.get("text"):
                    parts.append(genai.types.Part.from_text(text=response["text"]))
                if response["kind"] == "call":
                    parts.append(genai.types.Part(function_call=genai.types.FunctionCall(name=response["name"], args=response["args"])))
                yield LlmResponse(content=genai.types.Content(role="model", parts=parts), partial=False, turn_complete=True)

        class OriginalToolCapturePlugin(BasePlugin):
            def retain(self, boundary, tool, args, context, **extra):
                need(type(context) is ToolContext, "actual_original_adk_tool_context_required")
                function = getattr(tool, "func", None)
                row = {"index": len(captures), "boundary": boundary, "name": tool.name,
                       "tool_class": type(tool).__module__ + "." + type(tool).__qualname__,
                       "function": (function.__module__ + "." + function.__qualname__) if function is not None else None,
                       "actual_context_class": type(context).__module__ + "." + type(context).__qualname__,
                       "function_call_id": context.function_call_id, "args": serialize(args),
                       "state": serialize(context.state.to_dict()), **extra}
                captures.append(row)
                append(output / "adk-tool-capture.jsonl", row)

            async def before_tool_callback(self, *, tool, tool_args, tool_context):
                self.retain("before", tool, tool_args, tool_context)
                return None

            async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
                self.retain("after", tool, tool_args, tool_context, result=serialize(result))
                return None

            async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
                self.retain("error", tool, tool_args, tool_context, error_type=type(error).__name__, reason=str(error)[:1000])
                return None
        try:
            registry.LLMRegistry.register(DeterministicOriginalShopperLlm)
            registry.LLMRegistry.resolve.cache_clear()
            need(registry.LLMRegistry.resolve("gemini-3.1-flash-lite-preview") is DeterministicOriginalShopperLlm,
                 "offline_original_adk_model_registry_not_selected")
            retrying = importlib.import_module("common.retrying_llm_agent").RetryingLlmAgent
            root_agent = importlib.import_module("roles.shopping_agent.agent").root_agent
            initial_configs = self._authenticate_original_agents(root_agent, retrying)
            self.write(output / "original-adk-agent-configs.json", initial_configs)
            self.write(output / "original-adk-source-checks.json", self.source_checks)
            sessions = InMemorySessionService()
            session = await sessions.create_session(app_name="shopping_agent", user_id="ap2-development-human")
            self.write(output / "original-adk-session-before.json", {"session_id": session.id, "state": serialize(session.state),
                       "event_count": len(session.events), "class": type(session).__module__ + "." + type(session).__qualname__})
            runner = Runner(app_name="shopping_agent", agent=root_agent, session_service=sessions,
                            plugins=[OriginalToolCapturePlugin(name="ap2-v7-owned-read-only-capture")])
            prompt = self.case["public"]["prompt"]
            for turn in range(self.manifest["human_turn_bound"]):
                row = {"index": turn, "text": prompt, "role": "user", "fixture_authorship": "prospective development human fixture",
                       "session_id": session.id, "created_utc": datetime.now(timezone.utc).isoformat()}
                self.human_turns.append(row)
                append(output / "human-conversation.jsonl", row)
                message = genai.types.Content(role="user", parts=[genai.types.Part.from_text(text=prompt)])
                assistant_text = []
                async for event in runner.run_async(user_id="ap2-development-human", session_id=session.id, new_message=message):
                    value = serialize(event)
                    value["owned_capture_index"] = len(self.events)
                    value["owned_human_turn_index"] = turn
                    self.events.append(value)
                    append(output / "original-adk-events.jsonl", value)
                    if event.content:
                        for part in event.content.parts or []:
                            if part.text and not part.thought:
                                assistant_text.append(part.text)
                prompt = fixture.human_reply("\n".join(assistant_text))
                if prompt is None:
                    break
            else:
                raise ValueError("prospective_human_turn_bound_exhausted")
            session = await sessions.get_session(app_name="shopping_agent", user_id="ap2-development-human", session_id=session.id)
            self.context.state = serialize(session.state)
            self.write(output / "original-adk-session-after.json", {"session_id": session.id, "state": serialize(session.state),
                       "event_count": len(session.events), "event_ids": [event.id for event in session.events]})
            need(self._authenticate_original_agents(root_agent, retrying) == initial_configs, "original_adk_agent_configs_mutated_during_conversation")
            self.tool_returns = [(row["name"], row["result"]) for row in captures if row["boundary"] == "after"]
            last = [row["returned"] for row in self.bindings.merchant.calls if row["returned"] is not None]
            final = last[-1] if last else None
        except Exception as caught:
            error = caught
        finally:
            if runner is not None:
                await runner.close()
            registry._llm_registry_dict.clear()
            registry._llm_registry_dict.update(registry_before)
            registry.LLMRegistry.resolve.cache_clear()
            if session is not None:
                self.context.state = serialize(session.state)
            self.write(output / "shopper-outcome.json", {"schema_version": "ap2-original-adk-conversation/7",
                "candidate_id": self.case["id"], "terminal_reason": fixture.terminal_reason, "fixture_phase": fixture.phase,
                "original_payment_tool_return": fixture.payment_return, "human_turns": len(self.human_turns),
                "original_adk_events": len(self.events), "model_fixture_calls": len(fixture.rows),
                "original_adk_tool_records": len(captures), "supplied_human_otp_replies": fixture.otp_index,
                "original_root_and_subagent_config_unchanged": initial_configs is not None and error is None,
                "original_model_registry_restored": registry._llm_registry_dict == registry_before,
                "error_type": type(error).__name__ if error is not None else None, "reason": str(error)[:1000] if error is not None else None,
                "provider_requests": 0, "native_qualification_established": False, "human_gold_validated": False,
                "candidate_specific_branch_qualification_decided_by_actor": False})
        return ReferenceOutcome("captured_original_adk_conversation" if error is None else "captured_partial_original_adk_conversation",
                                fixture.phase, {"scope": "official original ADK root/subagents under deterministic model/human fixtures"},
                                deepcopy(self.public_records), self.tool_returns, final, error,
                                self.bindings.merchant.calls + self.bindings.credentials.calls)
