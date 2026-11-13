/** Default lifetime of a handle: fifteen minutes. */
export declare const DEFAULT_HANDLE_TTL_MS: number;
/** Default port of the MCP HTTP server. */
export declare const DEFAULT_PORT = 8931;
/** Default bind address: loopback only. */
export declare const DEFAULT_HOST = "127.0.0.1";
/** Path of the agent card, relative to the agent base URL (A2A v1.0.1). */
export declare const AGENT_CARD_PATH = "/.well-known/agent-card.json";
/** One A2A agent, resolved to the URL of its agent card. */
export interface AgentConfig {
    cardUrl: string;
}
export interface BridgeConfig {
    agents: Record<string, AgentConfig>;
    handleTtlMs: number;
    port: number;
    host: string;
    /** Extra hostnames accepted in the Host header, without port. Loopback is always accepted. */
    allowedHosts: string[];
}
/** Raised when the configuration is unusable. Names the offending field. */
export declare class ConfigError extends Error {
    /** Dotted path of the field at fault, when there is one. */
    readonly field: string | undefined;
    constructor(message: string, field?: string);
}
/** Validates a parsed configuration object and applies the defaults. */
export declare function parseConfig(raw: unknown): BridgeConfig;
/** Reads a JSON configuration file and validates it. */
export declare function loadConfig(path: string): Promise<BridgeConfig>;
