import { AgentCardResolver } from "./agent-card.js";
/** Path the MCP endpoint is mounted at. */
export declare const MCP_PATH = "/mcp";
export interface BridgeOptions {
    /** The A2A agents to expose, by alias. */
    agents: Record<string, {
        cardUrl: string;
    }>;
    /** Lifetime of a task or context handle. Defaults to fifteen minutes. */
    handleTtlMs?: number;
    /** Lifetime of a cached agent card. Defaults to one minute. */
    cardTtlMs?: number;
    /**
     * Extra hostnames accepted in the Host header, without port. The loopback
     * names are always accepted. Anything else is refused before the SDK sees
     * the request (DNS rebinding protection).
     */
    allowedHosts?: string[];
}
export interface BridgeAddress {
    /** Full URL of the MCP endpoint, ending in /mcp. */
    url: string;
    port: number;
}
export interface Bridge {
    /** Starts the HTTP endpoint. Port 0 binds a free port. */
    listen(port?: number, host?: string): Promise<BridgeAddress>;
    /** Stops the endpoint and releases the SDK handler. */
    close(): Promise<void>;
    /** Serves one request without a socket, for tests and embedding. */
    fetch(request: Request): Promise<Response>;
}
/** Builds a bridge over the configured A2A agents. */
export declare function createBridge(options: BridgeOptions): Promise<Bridge>;
/**
 * The instructions block, rebuilt on every request so an agent name learned
 * since the last one shows up without a restart.
 */
export declare function buildInstructions(cards: AgentCardResolver): string;
