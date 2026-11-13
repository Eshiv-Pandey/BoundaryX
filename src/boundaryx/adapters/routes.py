from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    name: str
    transport: str
    implementation: str
    a2a_version: str
    mcp_version: str | None
    interpretation: str


ROUTES = (
    Route("native", "HTTP JSON-RPC", "official @a2a-js/sdk", "1.0", None,
          "Native reference; deterministic receiver, no LLM"),
    Route("amirk_typed", "MCP HTTP to A2A HTTP", "AmirK-S/a2a-to-mcp", "1.0", "2025-11-25",
          "Typed projection with opaque task/context handles"),
    Route("mgcrea_typed", "MCP stdio to A2A HTTP", "mgcrea/mcp-a2a", "1.0", "2025-11-25",
          "Typed artifact summary; explicit refresh and write authorization"),
    Route("mgcrea_raw", "MCP stdio to A2A HTTP", "mgcrea/mcp-a2a", "1.0", "2025-11-25",
          "Public raw A2A request tool; same implementation as mgcrea typed"),
)
