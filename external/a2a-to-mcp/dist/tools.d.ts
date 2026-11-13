import type { CallToolResult, McpServer } from "@modelcontextprotocol/server";
import { type A2AClientPool } from "./a2a-client.js";
import { type AgentCardResolver, type ResolvedAgent } from "./agent-card.js";
import { type BridgeHandles } from "./envelope.js";
import { MrtrService, type RequestStatePayload } from "./mrtr.js";
import { type TasksService } from "./tasks/handlers.js";
/** The four tool names, in the order they are registered. */
export declare const TOOL_NAMES: readonly ["a2a_discover", "a2a_send_message", "a2a_get_task", "a2a_cancel_task"];
export interface ToolDeps {
    cards: AgentCardResolver;
    agents: A2AClientPool;
    handles: BridgeHandles;
    tasks: TasksService;
    mrtr: MrtrService;
}
/** What one tools/call says about the client and about its round. */
export interface CallContext {
    /**
     * True when the client declared the tasks extension on the modern route.
     * The declaration is read from the per-request envelope and nowhere else:
     * the bridge holds no session, so a legacy client never reaches this.
     */
    tasksExtension: boolean;
    /**
     * True when the client declared elicitation on the modern route. Read from
     * the same envelope, for the same reason: the legacy leg is served
     * statelessly by instances that never saw an initialize, so the capabilities
     * of that handshake are not recoverable there.
     */
    elicitation: boolean;
    /** Input responses of a retried round, lifted by the SDK. Untrusted. */
    inputResponses: Record<string, unknown> | undefined;
    /** The requestState the seam verified and decoded, when the round had one. */
    requestState: RequestStatePayload | undefined;
}
/** The handler context fields the bridge reads out of one tools/call. */
export interface HandlerContext {
    mcpReq: {
        envelope?: unknown;
        inputResponses?: Record<string, unknown> | undefined;
        requestState: <T>() => T | undefined;
    };
}
/** Registers the four tools and takes tools/call over from the SDK. */
export declare function registerBridgeTools(mcp: McpServer, deps: ToolDeps): void;
/**
 * Reads what one tools/call declares and what it carries back.
 *
 * The SDK lifts the reserved io.modelcontextprotocol/* keys out of the params
 * a handler sees and hands them over as ctx.mcpReq.envelope, and it lifts the
 * multi-round-trip fields out the same way. Both the revision and the
 * declarations are checked: the envelope exists on the 2026-07-28 route only,
 * and neither the extension nor the multi-round-trip is served elsewhere, so a
 * legacy request can never open an MCP task nor be handed an elicitation
 * however it words its params.
 *
 * The requestState has already passed the seam verify hook by the time a
 * handler runs, so what the accessor returns here is the decoded payload of a
 * state this bridge minted, not raw client input.
 */
export declare function readCallContext(ctx: HandlerContext): CallContext;
/**
 * Turns any execution failure into a tool result. An MCP client can show a
 * tool result to the model and let it try something else; a JSON-RPC error
 * usually aborts the turn, which is the wrong answer for an agent that simply
 * declined.
 */
export declare function toolError(error: unknown): CallToolResult;
/** The human readable summary of a card, for clients that ignore structuredContent. */
export declare function summarize(resolved: ResolvedAgent): string;
