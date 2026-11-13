import { HandleExpiredError, HandleTable, UnknownHandleError } from "../handles.js";
/** Prefix of every MCP task handle minted by the bridge. */
export const TASK_HANDLE_PREFIX = "tk";
export class TaskStore {
    #table;
    /** Idempotency index: `alias:a2aTaskId` to the handle minted for it. */
    #byKey = new Map();
    #now;
    constructor(options) {
        this.#now = options.now ?? Date.now;
        this.#table = new HandleTable({
            ttlMs: options.ttlMs,
            prefix: TASK_HANDLE_PREFIX,
            ...(options.now === undefined ? {} : { now: options.now }),
        });
    }
    /**
     * Mints the handle of an A2A task, or refreshes the one already minted for
     * it. The idempotency key is the alias and the A2A task id together, because
     * two agents may well use the same task id.
     *
     * A record that already reached a terminal state keeps the snapshot it
     * settled on: the extension requires tasks/get to answer identically once
     * the task is finished.
     */
    mintFor(alias, task, terminal = false) {
        const key = `${alias}:${task.id}`;
        const stamp = this.#stamp();
        const known = this.#byKey.get(key);
        if (known !== undefined) {
            const record = this.#peek(known);
            if (record !== undefined) {
                // The stored object is handed back by reference, so the record is
                // updated in place and the creation date survives.
                record.contextId = task.contextId;
                record.lastUpdatedAt = stamp;
                if (!record.terminal) {
                    record.snapshot = task;
                    record.terminal = terminal;
                }
                this.#table.touch(known);
                return known;
            }
            this.#byKey.delete(key);
        }
        const handle = this.#table.mint({
            handle: "",
            alias,
            a2aTaskId: task.id,
            contextId: task.contextId,
            createdAt: stamp,
            lastUpdatedAt: stamp,
            snapshot: task,
            terminal,
            streaming: false,
        });
        this.#table.resolve(handle).handle = handle;
        this.#byKey.set(key, handle);
        return handle;
    }
    /** Resolves a handle. Throws UnknownHandleError or HandleExpiredError. */
    resolve(handle) {
        return this.#table.resolve(handle);
    }
    /** Restarts the lifetime of a handle. */
    touch(handle) {
        this.#table.touch(handle);
    }
    /** The current time in the ISO 8601 spelling the records use. */
    stamp() {
        return this.#stamp();
    }
    /** Stamps a task as just refreshed and restarts its lifetime. */
    markUpdated(handle) {
        const record = this.#table.resolve(handle);
        record.lastUpdatedAt = this.#stamp();
        this.#table.touch(handle);
        return record;
    }
    /** Forgets a handle. True when it was there. */
    delete(handle) {
        const record = this.#peek(handle);
        if (record !== undefined) {
            this.#byKey.delete(`${record.alias}:${record.a2aTaskId}`);
        }
        return this.#table.delete(handle);
    }
    /** Number of handles held, expired ones included until the next sweep. */
    get size() {
        return this.#table.size;
    }
    /** Drops every expired handle and returns how many were dropped. */
    sweep() {
        const dropped = this.#table.sweep();
        for (const [key, handle] of this.#byKey) {
            if (this.#peek(handle) === undefined) {
                this.#byKey.delete(key);
            }
        }
        return dropped;
    }
    /** One sentence about retention, meant for a tool description. */
    describeRetention() {
        return this.#table.describeRetention();
    }
    #peek(handle) {
        try {
            return this.#table.resolve(handle);
        }
        catch {
            return undefined;
        }
    }
    #stamp() {
        return new Date(this.#now()).toISOString();
    }
}
export { HandleExpiredError, UnknownHandleError };
