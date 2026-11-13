/**
 * The store behind the io.modelcontextprotocol/tasks extension.
 *
 * An MCP task id is a bridge handle: the opaque tk_ token minted when
 * a2a_send_message produced an A2A task. The store maps it back to the agent
 * alias, to the A2A identifiers, and to the last A2A Task the bridge saw.
 *
 * That snapshot is what a stream writes into: an agent that streams feeds the
 * record event by event, and the bridge only falls back on a fresh GetTask
 * when no stream is alive and the task is not terminal yet. A terminal record
 * is frozen, so two tasks/get on a finished task answer identically.
 *
 * Minting is idempotent on alias plus A2A task id, so a client that sends
 * three messages to the same task sees one handle, not three.
 */
import type { Task } from "@a2a-js/sdk";
import { HandleExpiredError, UnknownHandleError } from "../handles.js";
/** Prefix of every MCP task handle minted by the bridge. */
export declare const TASK_HANDLE_PREFIX = "tk";
/** A failure of the bridge itself, reported as an MCP failed task. */
export interface BridgeTaskError {
    code: number;
    message: string;
    data: Record<string, unknown>;
}
/** What the bridge remembers about one MCP task. */
export interface TaskRecord {
    /** The tk_ handle this record is filed under. */
    handle: string;
    /** Alias of the A2A agent running the task. */
    alias: string;
    /** Identifier of the task on the A2A side. */
    a2aTaskId: string;
    /** A2A context the task belongs to. */
    contextId: string;
    /** When the handle was minted, ISO 8601. */
    createdAt: string;
    /** When the bridge last refreshed the record, ISO 8601. */
    lastUpdatedAt: string;
    /** The last A2A Task the bridge saw, artifacts accumulated. */
    snapshot: Task;
    /** True once the snapshot reached one of the four terminal A2A states. */
    terminal: boolean;
    /** True while a SendStreamingMessage stream is still feeding the snapshot. */
    streaming: boolean;
    /** Set when the bridge itself could not carry the task any further. */
    bridgeError?: BridgeTaskError;
    /** The terminal tool result, built once and handed back unchanged. */
    frozenResult?: Record<string, unknown>;
}
export interface TaskStoreOptions {
    /** Handle lifetime in milliseconds. */
    ttlMs: number;
    /** Injectable clock, for tests. */
    now?: () => number;
}
export declare class TaskStore {
    #private;
    constructor(options: TaskStoreOptions);
    /**
     * Mints the handle of an A2A task, or refreshes the one already minted for
     * it. The idempotency key is the alias and the A2A task id together, because
     * two agents may well use the same task id.
     *
     * A record that already reached a terminal state keeps the snapshot it
     * settled on: the extension requires tasks/get to answer identically once
     * the task is finished.
     */
    mintFor(alias: string, task: Task, terminal?: boolean): string;
    /** Resolves a handle. Throws UnknownHandleError or HandleExpiredError. */
    resolve(handle: string): TaskRecord;
    /** Restarts the lifetime of a handle. */
    touch(handle: string): void;
    /** The current time in the ISO 8601 spelling the records use. */
    stamp(): string;
    /** Stamps a task as just refreshed and restarts its lifetime. */
    markUpdated(handle: string): TaskRecord;
    /** Forgets a handle. True when it was there. */
    delete(handle: string): boolean;
    /** Number of handles held, expired ones included until the next sweep. */
    get size(): number;
    /** Drops every expired handle and returns how many were dropped. */
    sweep(): number;
    /** One sentence about retention, meant for a tool description. */
    describeRetention(): string;
}
export { HandleExpiredError, UnknownHandleError };
