/**
 * Agent card resolution, one entry per configured alias.
 *
 * The bridge fetches the card itself rather than letting the A2A client do it
 * through ClientFactory.createFromUrl, for three reasons: the card is the
 * structuredContent of a2a_discover and must reach the client unmodified; the
 * bridge picks the JSON-RPC interface explicitly instead of taking the first
 * entry of supportedInterfaces (which is what the SDK does by default); and a
 * card fetched once has to be reused across tool calls, so the cache and its
 * TTL live here.
 *
 * Validation is deliberately minimal. The bridge refuses a payload that could
 * not possibly be an A2A v1.0 card, and passes everything else through: a card
 * the bridge does not understand is still useful to the model reading it.
 */
import type { AgentCard, AgentInterface } from "@a2a-js/sdk";
/** Default lifetime of a cached agent card: one minute. */
export declare const DEFAULT_CARD_TTL_MS = 60000;
/** The A2A protocol version the bridge speaks. */
export declare const A2A_VERSION = "1.0";
/** Raised when a card cannot be fetched, parsed or validated. Names the URL. */
export declare class AgentCardError extends Error {
    readonly alias: string;
    readonly cardUrl: string;
    constructor(alias: string, cardUrl: string, reason: string);
}
/** Raised when a tool names an alias that is not configured. */
export declare class UnknownAgentError extends Error {
    readonly alias: string;
    constructor(alias: string, known: readonly string[]);
}
/** One resolved agent: the raw card, its URL, and the interface the bridge calls. */
export interface ResolvedAgent {
    alias: string;
    cardUrl: string;
    /** The card exactly as the agent served it, only validated. */
    card: AgentCard;
    /** The JSON-RPC interface the bridge talks to. */
    agentInterface: AgentInterface;
}
export interface AgentCardResolverOptions {
    /** Alias to card URL, from the bridge configuration. */
    agents: Record<string, {
        cardUrl: string;
    }>;
    /** Lifetime of a cached card. Defaults to DEFAULT_CARD_TTL_MS. */
    ttlMs?: number;
    /** Injectable fetch, for tests. */
    fetchImpl?: typeof fetch;
    /** Injectable clock, for tests. */
    now?: () => number;
}
export declare class AgentCardResolver {
    #private;
    constructor(options: AgentCardResolverOptions);
    /** The configured aliases, in declaration order. */
    get aliases(): string[];
    /** How many times a card was actually fetched over the network. */
    get fetches(): number;
    /** The card URL of an alias, without fetching anything. */
    cardUrlOf(alias: string): string;
    /** The card of an alias, already resolved and still fresh, if there is one. */
    peek(alias: string): ResolvedAgent | undefined;
    /** Resolves an alias, fetching the card at most once per TTL window. */
    get(alias: string): Promise<ResolvedAgent>;
    /** Drops the cached card of an alias, so the next get refetches. */
    invalidate(alias: string): void;
}
/** Minimal structural validation of an A2A v1.0 agent card. */
export declare function validateCard(alias: string, cardUrl: string, payload: unknown): AgentCard;
/** Picks the JSON-RPC interface, preferring the one that declares A2A 1.0. */
export declare function pickJsonRpcInterface(alias: string, cardUrl: string, card: AgentCard): AgentInterface;
