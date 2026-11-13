/**
 * Handle table for stateful MCP tools.
 *
 * The bridge never hands an A2A task id or context id to an MCP client. It
 * mints an opaque handle, keeps the real reference in memory for a bounded
 * time, and answers an explicit error once the handle has expired, as MCP
 * 2026-07-28 asks of stateful tools.
 */
import { randomBytes } from "node:crypto";
/** Raised when a handle was never minted, or was deleted. */
export class UnknownHandleError extends Error {
    handle;
    constructor(handle) {
        super(`Unknown handle ${JSON.stringify(handle)}: it was never minted, or it was deleted.`);
        this.name = "UnknownHandleError";
        this.handle = handle;
    }
}
/** Raised when a handle exists but its lifetime has elapsed. */
export class HandleExpiredError extends Error {
    handle;
    constructor(handle, ttlMs) {
        super(`Handle ${JSON.stringify(handle)} has expired after ${ttlMs} ms of inactivity. ` +
            "Start again from the call that produced it.");
        this.name = "HandleExpiredError";
        this.handle = handle;
    }
}
/** Bytes of randomness behind a handle: 16 bytes give 22 base64url chars. */
const HANDLE_BYTES = 16;
export class HandleTable {
    #entries = new Map();
    #byKey = new Map();
    #ttlMs;
    #now;
    #prefix;
    constructor(options) {
        if (!Number.isFinite(options.ttlMs) || options.ttlMs <= 0) {
            throw new RangeError(`ttlMs must be a positive number of milliseconds, received ${options.ttlMs}.`);
        }
        this.#ttlMs = options.ttlMs;
        this.#now = options.now ?? Date.now;
        this.#prefix = options.prefix ?? "h";
    }
    /** Mints a fresh handle for a value. Two calls never collide. */
    mint(value) {
        return this.#insert(value, undefined);
    }
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
    mintFor(key, value) {
        const existing = this.#byKey.get(key);
        if (existing !== undefined) {
            const entry = this.#entries.get(existing);
            if (entry !== undefined && !this.#isExpired(entry)) {
                entry.value = value;
                entry.expiresAt = this.#now() + this.#ttlMs;
                return existing;
            }
            this.#forget(existing);
        }
        return this.#insert(value, key);
    }
    /** Resolves a handle to its value. Does not extend the lifetime. */
    resolve(handle) {
        const entry = this.#entries.get(handle);
        if (entry === undefined) {
            throw new UnknownHandleError(handle);
        }
        if (this.#isExpired(entry)) {
            throw new HandleExpiredError(handle, this.#ttlMs);
        }
        return entry.value;
    }
    /** Restarts the lifetime of a handle from now. */
    touch(handle) {
        const entry = this.#entries.get(handle);
        if (entry === undefined) {
            throw new UnknownHandleError(handle);
        }
        if (this.#isExpired(entry)) {
            throw new HandleExpiredError(handle, this.#ttlMs);
        }
        entry.expiresAt = this.#now() + this.#ttlMs;
    }
    /** Milliseconds left before expiry, 0 for an expired or unknown handle. */
    remainingMs(handle) {
        const entry = this.#entries.get(handle);
        if (entry === undefined) {
            return 0;
        }
        return Math.max(0, entry.expiresAt - this.#now());
    }
    /** Drops every expired entry and returns how many were dropped. */
    sweep() {
        let dropped = 0;
        for (const [handle, entry] of this.#entries) {
            if (this.#isExpired(entry)) {
                this.#forget(handle);
                dropped += 1;
            }
        }
        return dropped;
    }
    /** Drops one handle. True when it was there. */
    delete(handle) {
        if (!this.#entries.has(handle)) {
            return false;
        }
        this.#forget(handle);
        return true;
    }
    /** Number of entries held, expired ones included until the next sweep. */
    get size() {
        return this.#entries.size;
    }
    /** One sentence about retention, meant for a tool description. */
    describeRetention() {
        return (`Handles live in memory for ${formatDuration(this.#ttlMs)} after their last use; ` +
            "an expired handle returns an explicit error.");
    }
    #insert(value, key) {
        const handle = this.#newHandle();
        this.#entries.set(handle, { value, expiresAt: this.#now() + this.#ttlMs, key });
        if (key !== undefined) {
            this.#byKey.set(key, handle);
        }
        return handle;
    }
    #newHandle() {
        let handle = `${this.#prefix}_${randomBytes(HANDLE_BYTES).toString("base64url")}`;
        while (this.#entries.has(handle)) {
            handle = `${this.#prefix}_${randomBytes(HANDLE_BYTES).toString("base64url")}`;
        }
        return handle;
    }
    #forget(handle) {
        const entry = this.#entries.get(handle);
        if (entry?.key !== undefined && this.#byKey.get(entry.key) === handle) {
            this.#byKey.delete(entry.key);
        }
        this.#entries.delete(handle);
    }
    #isExpired(entry) {
        return this.#now() >= entry.expiresAt;
    }
}
function formatDuration(ttlMs) {
    // Under two minutes, seconds read better and stay plural: a one minute TTL
    // rendered as "1 minute" is worse than "60 seconds" in a tool description.
    if (ttlMs >= 120_000) {
        const minutes = round(ttlMs / 60_000);
        return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
    }
    const seconds = round(ttlMs / 1_000);
    return `${seconds} ${seconds === 1 ? "second" : "seconds"}`;
}
function round(value) {
    return Math.round(value * 100) / 100;
}
