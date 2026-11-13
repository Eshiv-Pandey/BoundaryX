/** Default lifetime of a cached agent card: one minute. */
export const DEFAULT_CARD_TTL_MS = 60_000;
/** The A2A protocol version the bridge speaks. */
export const A2A_VERSION = "1.0";
/** The protocolBinding value of the JSON-RPC interface, compared case-insensitively. */
const JSONRPC_BINDING = "jsonrpc";
/** Raised when a card cannot be fetched, parsed or validated. Names the URL. */
export class AgentCardError extends Error {
    alias;
    cardUrl;
    constructor(alias, cardUrl, reason) {
        super(`Cannot use the agent card of ${JSON.stringify(alias)} at ${cardUrl}: ${reason}`);
        this.name = "AgentCardError";
        this.alias = alias;
        this.cardUrl = cardUrl;
    }
}
/** Raised when a tool names an alias that is not configured. */
export class UnknownAgentError extends Error {
    alias;
    constructor(alias, known) {
        super(`Unknown agent alias ${JSON.stringify(alias)}. ` +
            `The configured agents are: ${known.map((name) => JSON.stringify(name)).join(", ")}.`);
        this.name = "UnknownAgentError";
        this.alias = alias;
    }
}
export class AgentCardResolver {
    #agents;
    #cache = new Map();
    #inFlight = new Map();
    #ttlMs;
    #fetch;
    #now;
    #fetches = 0;
    constructor(options) {
        this.#agents = { ...options.agents };
        this.#ttlMs = options.ttlMs ?? DEFAULT_CARD_TTL_MS;
        this.#fetch = options.fetchImpl ?? fetch;
        this.#now = options.now ?? Date.now;
    }
    /** The configured aliases, in declaration order. */
    get aliases() {
        return Object.keys(this.#agents);
    }
    /** How many times a card was actually fetched over the network. */
    get fetches() {
        return this.#fetches;
    }
    /** The card URL of an alias, without fetching anything. */
    cardUrlOf(alias) {
        const entry = this.#agents[alias];
        if (entry === undefined) {
            throw new UnknownAgentError(alias, this.aliases);
        }
        return entry.cardUrl;
    }
    /** The card of an alias, already resolved and still fresh, if there is one. */
    peek(alias) {
        const cached = this.#cache.get(alias);
        if (cached === undefined || cached.expiresAt <= this.#now()) {
            return undefined;
        }
        return cached.resolved;
    }
    /** Resolves an alias, fetching the card at most once per TTL window. */
    async get(alias) {
        const cardUrl = this.cardUrlOf(alias);
        const fresh = this.peek(alias);
        if (fresh !== undefined) {
            return fresh;
        }
        // Two tool calls racing on a cold cache must still fetch only once.
        const pending = this.#inFlight.get(alias);
        if (pending !== undefined) {
            return pending;
        }
        const attempt = this.#load(alias, cardUrl).finally(() => {
            this.#inFlight.delete(alias);
        });
        this.#inFlight.set(alias, attempt);
        return attempt;
    }
    /** Drops the cached card of an alias, so the next get refetches. */
    invalidate(alias) {
        this.#cache.delete(alias);
    }
    async #load(alias, cardUrl) {
        const card = await this.#fetchCard(alias, cardUrl);
        const resolved = {
            alias,
            cardUrl,
            card,
            agentInterface: pickJsonRpcInterface(alias, cardUrl, card),
        };
        this.#cache.set(alias, { resolved, expiresAt: this.#now() + this.#ttlMs });
        return resolved;
    }
    async #fetchCard(alias, cardUrl) {
        let response;
        try {
            response = await this.#fetch(cardUrl, {
                headers: { Accept: "application/json", "A2A-Version": A2A_VERSION },
            });
        }
        catch (error) {
            throw new AgentCardError(alias, cardUrl, `the request failed (${messageOf(error)})`);
        }
        this.#fetches += 1;
        if (!response.ok) {
            throw new AgentCardError(alias, cardUrl, `the agent answered HTTP ${response.status} ${response.statusText}`);
        }
        let payload;
        try {
            payload = await response.json();
        }
        catch (error) {
            throw new AgentCardError(alias, cardUrl, `the body is not JSON (${messageOf(error)})`);
        }
        return validateCard(alias, cardUrl, payload);
    }
}
/** Minimal structural validation of an A2A v1.0 agent card. */
export function validateCard(alias, cardUrl, payload) {
    if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
        throw new AgentCardError(alias, cardUrl, `expected a JSON object, received ${describe(payload)}`);
    }
    const card = payload;
    if (typeof card["name"] !== "string" || card["name"] === "") {
        throw new AgentCardError(alias, cardUrl, "the card has no name");
    }
    const interfaces = card["supportedInterfaces"];
    if (!Array.isArray(interfaces) || interfaces.length === 0) {
        throw new AgentCardError(alias, cardUrl, "supportedInterfaces must be a non-empty array. " +
            "A v0.3 card with url and preferredTransport is not an A2A v1.0 card.");
    }
    if (!Array.isArray(card["skills"])) {
        throw new AgentCardError(alias, cardUrl, "skills must be an array");
    }
    return card;
}
/** Picks the JSON-RPC interface, preferring the one that declares A2A 1.0. */
export function pickJsonRpcInterface(alias, cardUrl, card) {
    const candidates = (card.supportedInterfaces ?? []).filter((entry) => typeof entry === "object" &&
        entry !== null &&
        typeof entry.url === "string" &&
        entry.url !== "" &&
        typeof entry.protocolBinding === "string" &&
        entry.protocolBinding.toLowerCase() === JSONRPC_BINDING);
    const preferred = candidates.find((entry) => String(entry.protocolVersion ?? "").startsWith(A2A_VERSION)) ??
        candidates[0];
    if (preferred === undefined) {
        const bindings = (card.supportedInterfaces ?? [])
            .map((entry) => String(entry.protocolBinding))
            .join(", ");
        throw new AgentCardError(alias, cardUrl, `no JSONRPC interface is declared. The card offers: ${bindings || "nothing"}. ` +
            "The bridge only speaks the A2A JSON-RPC binding.");
    }
    return preferred;
}
function describe(value) {
    if (value === null) {
        return "null";
    }
    return Array.isArray(value) ? "an array" : typeof value;
}
function messageOf(error) {
    if (error instanceof Error) {
        const cause = error.cause;
        if (cause instanceof Error && cause.message !== "") {
            return `${error.message}: ${cause.message}`;
        }
        return error.message;
    }
    return String(error);
}
