/**
 * The result envelope of a2a_send_message, a2a_get_task and a2a_cancel_task.
 *
 * A2A answers SendMessage with either a Message or a Task, and the union is
 * not discriminated on the wire, so it is told apart structurally. Both arms
 * collapse into one shape: content blocks for a client that only reads text,
 * and a structuredContent envelope for a client that reads the lifecycle.
 *
 * The envelope reports the A2A state twice on purpose: a2aState carries the
 * exact ProtoJSON name (TASK_STATE_AUTH_REQUIRED), status carries the MCP task
 * status it maps onto, and note says what the mapping dropped. A client that
 * only knows MCP reads status; a client that knows A2A never loses the state
 * the agent actually reported.
 */
import { type Message, type Task } from "@a2a-js/sdk";
import type { ContentBlock } from "@modelcontextprotocol/server";
import { type McpTaskStatus } from "./lifecycle.js";
import { TaskStore } from "./tasks/store.js";
/** Prefix of every A2A context handle minted by the bridge. */
export declare const CONTEXT_HANDLE_PREFIX = "cx";
/** What the bridge remembers behind a cx_ handle. */
export interface ContextRecord {
    alias: string;
    contextId: string;
}
/** One past turn of a task, flattened to the text a model can read. */
export interface HistoryTurn {
    role: "user" | "agent";
    text: string;
}
/** One artifact, named but not inlined, so a client can ask for it by id. */
export interface ArtifactRef {
    artifactId: string;
    name: string;
}
/** The structuredContent of every tool result that carries A2A output. */
export interface BridgeEnvelope {
    kind: "message" | "task";
    contextHandle: string;
    taskHandle?: string;
    /** Exact A2A state, ProtoJSON spelling, for example TASK_STATE_COMPLETED. */
    a2aState?: string;
    /** The MCP task status the A2A state maps onto. */
    status?: McpTaskStatus;
    /** What the mapping dropped, present only when it dropped something. */
    note?: string;
    artifacts?: ArtifactRef[];
    /** The single data part of the artifacts, when there is exactly one. */
    data?: Record<string, unknown>;
    /** Past turns of the task, present only when the caller asked for them. */
    history?: HistoryTurn[];
}
/** The shape the tools return to the MCP seam. */
export interface EnvelopeResult {
    content: ContentBlock[];
    structuredContent: BridgeEnvelope;
    isError?: boolean;
}
/** The two handle tables of the bridge, minted and resolved in one place. */
export declare class BridgeHandles {
    #private;
    readonly tasks: TaskStore;
    constructor(options: {
        ttlMs: number;
        now?: () => number;
    });
    /** Mints the handle of an A2A context, idempotently on alias and context id. */
    mintContext(alias: string, contextId: string): string;
    /** Resolves a context handle. Throws UnknownHandleError or HandleExpiredError. */
    resolveContext(handle: string): ContextRecord;
    /** One sentence about retention, meant for a tool description. */
    describeRetention(): string;
    /** Drops every expired handle of both tables. */
    sweep(): number;
}
/** True when an A2A SendMessage result is a Task rather than a Message. */
export declare function isTask(result: Message | Task): result is Task;
/** Builds the tool result for a direct Message reply. */
export declare function messageEnvelope(handles: BridgeHandles, alias: string, message: Message): EnvelopeResult;
/** How much of a Task the envelope carries beyond its current state. */
export interface TaskEnvelopeOptions {
    /**
     * Adds the task history to the envelope. Only a2a_get_task asks for it: the
     * envelope a2a_send_message returns is also the result a completed MCP task
     * hands back, and that one must stay exactly what tools/call returned.
     */
    includeHistory?: boolean;
}
/** Builds the tool result for a Task, whatever state it is in. */
export declare function taskEnvelope(handles: BridgeHandles, alias: string, task: Task, options?: TaskEnvelopeOptions): EnvelopeResult;
/** Builds the tool result for whichever arm SendMessage returned. */
export declare function resultEnvelope(handles: BridgeHandles, alias: string, result: Message | Task): EnvelopeResult;
/** Flattens the A2A history of a task into role and text turns. */
export declare function historyOf(task: Task): HistoryTurn[];
