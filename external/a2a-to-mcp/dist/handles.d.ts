/** Raised when a handle was never minted, or was deleted. */
export declare class UnknownHandleError extends Error {
    readonly handle: string;
    constructor(handle: string);
}
/** Raised when a handle exists but its lifetime has elapsed. */
export declare class HandleExpiredError extends Error {
    readonly handle: string;
    constructor(handle: string, ttlMs: number);
}
export interface HandleTableOptions {
    /**
     * Lifetime of a handle, restarted by touch and by minting again for the
     * same idempotency key. Must be strictly positive.
     */
    ttlMs: number;
    /** Clock, injectable for tests. Defaults to Date.now. */
    now?: () => number;
    /** Handle prefix, so handles are recognisable in a transcript. */
    prefix?: string;
}
export declare class HandleTable<T> {
    #private;
    constructor(options: HandleTableOptions);
    /** Mints a fresh handle for a value. Two calls never collide. */
    mint(value: T): string;
    /**
     * Mints a handle for a value under an idempotency key. The same key gives
     * back the same handle as long as that handle is neither expired nor
     * deleted; the stored value is refreshed either way.
     *
     * Minting again for a live key counts as a use, so the lifetime restarts
     * exactly as touch restarts it. That is what makes one retention sentence
     * true of both tables: a context handle is re-minted on every reply that
     * carries it, so a conversation still going never expires under the client.
     */
    mintFor(key: string, value: T): string;
    /** Resolves a handle to its value. Does not extend the lifetime. */
    resolve(handle: string): T;
    /** Restarts the lifetime of a handle from now. */
    touch(handle: string): void;
    /** Milliseconds left before expiry, 0 for an expired or unknown handle. */
    remainingMs(handle: string): number;
    /** Drops every expired entry and returns how many were dropped. */
    sweep(): number;
    /** Drops one handle. True when it was there. */
    delete(handle: string): boolean;
    /** Number of entries held, expired ones included until the next sweep. */
    get size(): number;
    /** One sentence about retention, meant for a tool description. */
    describeRetention(): string;
}
