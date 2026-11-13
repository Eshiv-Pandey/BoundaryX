import { type Message, type Task } from "@a2a-js/sdk";
import type { A2AClientPool, SendMessageInput } from "../a2a-client.js";
import { type BridgeHandles } from "../envelope.js";
/** Identifier of the tasks extension, as clients declare it. */
export declare const TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks";
/** The only MCP revision on which the bridge serves the extension. */
export declare const MODERN_REVISION = "2026-07-28";
/** The three methods the extension defines on the 2026-07-28 revision. */
export declare const TASKS_METHODS: readonly ["tasks/get", "tasks/update", "tasks/cancel"];
export type TasksMethod = (typeof TASKS_METHODS)[number];
/** True for the three method names of the extension. */
export declare function isTasksMethod(method: string): method is TasksMethod;
/** The client capabilities view a route hands to the handlers. */
export interface ClientCapabilitiesView {
    extensions?: Record<string, unknown> | undefined;
    [key: string]: unknown;
}
export interface TasksServiceOptions {
    handles: BridgeHandles;
    agents: A2AClientPool;
    /** Handle lifetime, reported to the client as the task ttlMs. */
    ttlMs: number;
    /** Server identity, stamped on an inlined tool result as tools/call does. */
    serverInfo: {
        name: string;
        version: string;
    };
}
/** Cadence the bridge advertises to a polling client, in milliseconds. */
export declare const POLL_INTERVAL_MS = 500;
/** What a2a_send_message got back when the client asked for a task. */
export type CreateTaskOutcome = 
/** A CreateTaskResult, flat, ready to travel as the tools/call result. */
{
    kind: "task";
    result: Record<string, unknown>;
}
/** The agent answered outright: the call stays an ordinary tool call. */
 | {
    kind: "synchronous";
    result: Message | Task;
};
export declare class TasksService {
    #private;
    constructor(options: TasksServiceOptions);
    /**
     * Refuses a client that did not declare the extension, with the -32021 the
     * extension mandates and the capability it would have to declare.
     */
    assertExtensionDeclared(capabilities: ClientCapabilitiesView | undefined): void;
    /**
     * Refuses the three methods on the 2025-11-25 route, whatever the client
     * declared at initialize. The legacy leg is served
     * statelessly, one fresh instance per request, so no handshake is
     * recoverable there; the extension lives on the modern revision only, and
     * the answer says so rather than pretending the declaration was missing.
     */
    refuseOnLegacyRoute(): never;
    /**
     * Opens an MCP task over one A2A message, for a client that declared the
     * extension on the modern route.
     *
     * A streaming agent is read only as far as its first lifecycle event: that
     * is enough to answer, and the rest of the stream keeps feeding the record
     * in the background. An agent that does not stream is asked to return as
     * soon as the task exists, and every later state comes from GetTask.
     */
    createTask(alias: string, input: SendMessageInput): Promise<CreateTaskOutcome>;
    /** Dispatches one extension method, after the capability gate. */
    handle(method: TasksMethod, params: unknown, capabilities: ClientCapabilitiesView | undefined): Promise<Record<string, unknown>>;
}
/**
 * The statusMessage of a task: what the agent wrote, or the exact A2A state
 * when the mapping onto an MCP status dropped something and the agent said
 * nothing.
 */
export declare function statusMessageOf(task: Task): string;
/**
 * Key of the single input request the bridge ever issues. One A2A question
 * becomes one elicitation, so one key is enough, and both the extension route
 * and the synchronous multi-round-trip route use this one.
 */
export declare const ANSWER_KEY = "answer";
/** Wording of the one field the synthesized form asks for. */
export declare const ANSWER_DESCRIPTION = "Your answer to the agent";
/**
 * The elicitation form an A2A question becomes. A2A carries the question as
 * free text with no schema, so the schema is a single required string and the
 * agent wording travels as the message.
 */
export declare function answerSchema(): Record<string, unknown>;
/**
 * The one form-mode elicitation an A2A INPUT_REQUIRED becomes, in the shape
 * tasks/get reports it: the bare embedded request, since the extension has no
 * builder of its own.
 */
export declare function inputRequestsFor(question: string): Record<string, unknown>;
/** Reads params.inputResponses, tolerating anything that is not a map. */
export declare function readInputResponses(params: unknown): Record<string, unknown> | undefined;
/**
 * The answer text of an accepted elicitation. The content comes from the
 * client and is not validated by the SDK, so a missing or ill-typed field is
 * read as no answer at all rather than sent on to the agent.
 */
export declare function readAnswer(content: Record<string, unknown> | undefined): string | undefined;
/** Reads params.taskId, refusing anything else with -32602. */
export declare function readTaskId(params: unknown): string;
