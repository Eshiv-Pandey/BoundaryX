"""Prospective owned AP2 read tool; no original function body is replaced.

This module is not installed into an agent or dispatched by importing it. A
future runner must disclose adding this tool to the original ADK tool surface.
Only the original caller-held payment task/context and public SDK API are used.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from google.adk.tools.tool_context import ToolContext


class PublicTaskAuthorityError(ValueError):
    """Retain the actual public SDK reply even when its authority is refused."""

    def __init__(self, observation):
        super().__init__("The public Task does not match the caller-held task and context.")
        self.public_observation = observation


async def read_public_payment_task(tool_context: ToolContext) -> dict:
    """Read the current original merchant payment Task and its public message.

    Use after initiate_payment or initiate_payment_with_otp returns a generic
    status. Relay a public OTP request to the user and preserve their exact
    response. Present a receipt only if the returned Task contains one. This
    tool does not submit an OTP, repair caller state, or choose a human reply.
    """
    import httpx
    from a2a.client.client import ClientConfig
    from a2a.client.client_factory import ClientFactory
    from a2a.extensions.common import HTTP_EXTENSION_HEADER
    from a2a.types import TaskQueryParams
    from common.a2a_extension_utils import EXTENSION_URI
    from roles.shopping_agent.remote_agents import merchant_agent_client

    task_id = tool_context.state.get("initiate_payment_task_id")
    context_id = tool_context.state.get("shopping_context_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("No original caller-held payment task ID is available.")
    if not isinstance(context_id, str) or not context_id:
        raise ValueError("No original caller-held shopping context is available.")

    card = await merchant_agent_client.get_agent_card()
    endpoint = urlsplit(card.url)
    if (endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1"}
            or endpoint.port != 8001 or endpoint.path != "/a2a/merchant_agent"
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or card.protocol_version != "0.3.0"):
        raise ValueError("The public card does not match the original merchant endpoint/version.")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0), headers={HTTP_EXTENSION_HEADER: EXTENSION_URI}
    ) as http_client:
        client = ClientFactory(ClientConfig(
            httpx_client=http_client, extensions=[EXTENSION_URI]
        )).create(card)
        task = await client.get_task(TaskQueryParams(id=task_id, history_length=100))

    observation = {
        "observation_source": "owned read tool using original public Python SDK get_task",
        "query": {"id": task_id, "historyLength": 100},
        "task": task.model_dump(mode="json", by_alias=True, exclude_none=True),
        "original_card_rewritten": False,
        "caller_state_repaired": False,
    }
    if task.id != task_id or task.context_id != context_id:
        raise PublicTaskAuthorityError(observation)
    return observation
