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
import { Role, TaskState, taskStateToJSON, } from "@a2a-js/sdk";
import { HandleTable } from "./handles.js";
import { isTerminalA2AState, toMcpStatus } from "./lifecycle.js";
import { artifactToContent, messageToContent, structuredContentFromParts } from "./parts.js";
import { TaskStore } from "./tasks/store.js";
/** Prefix of every A2A context handle minted by the bridge. */
export const CONTEXT_HANDLE_PREFIX = "cx";
/** The A2A states the bridge reports as a failed tool call. */
const ERROR_STATES = [
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_REJECTED,
    TaskState.TASK_STATE_AUTH_REQUIRED,
    TaskState.TASK_STATE_UNSPECIFIED,
];
/** The two handle tables of the bridge, minted and resolved in one place. */
export class BridgeHandles {
    tasks;
    #contexts;
    constructor(options) {
        const clock = options.now === undefined ? {} : { now: options.now };
        this.tasks = new TaskStore({ ttlMs: options.ttlMs, ...clock });
        this.#contexts = new HandleTable({
            ttlMs: options.ttlMs,
            prefix: CONTEXT_HANDLE_PREFIX,
            ...clock,
        });
    }
    /** Mints the handle of an A2A context, idempotently on alias and context id. */
    mintContext(alias, contextId) {
        return this.#contexts.mintFor(`${alias}:${contextId}`, { alias, contextId });
    }
    /** Resolves a context handle. Throws UnknownHandleError or HandleExpiredError. */
    resolveContext(handle) {
        return this.#contexts.resolve(handle);
    }
    /** One sentence about retention, meant for a tool description. */
    describeRetention() {
        return this.tasks.describeRetention();
    }
    /** Drops every expired handle of both tables. */
    sweep() {
        return this.tasks.sweep() + this.#contexts.sweep();
    }
}
/** True when an A2A SendMessage result is a Task rather than a Message. */
export function isTask(result) {
    return "status" in result && !("messageId" in result);
}
/** Builds the tool result for a direct Message reply. */
export function messageEnvelope(handles, alias, message) {
    return {
        content: messageToContent(message),
        structuredContent: {
            kind: "message",
            contextHandle: handles.mintContext(alias, message.contextId),
        },
    };
}
/** Builds the tool result for a Task, whatever state it is in. */
export function taskEnvelope(handles, alias, task, options = {}) {
    const state = task.status?.state ?? TaskState.TASK_STATE_UNSPECIFIED;
    const mapping = toMcpStatus(state);
    const artifacts = task.artifacts ?? [];
    const parts = artifacts.flatMap((artifact) => artifact.parts);
    const content = artifacts.flatMap((artifact) => artifactToContent(artifact));
    const statusMessage = task.status?.message;
    if (statusMessage !== undefined) {
        content.push(...messageToContent(statusMessage));
    }
    const refs = artifacts.map((artifact) => ({
        artifactId: artifact.artifactId,
        name: artifact.name,
    }));
    const data = structuredContentFromParts(parts);
    const envelope = {
        kind: "task",
        contextHandle: handles.mintContext(alias, task.contextId),
        taskHandle: handles.tasks.mintFor(alias, task, isTerminalA2AState(state)),
        a2aState: taskStateToJSON(state),
        status: mapping.status,
        ...(mapping.lossy && mapping.note !== undefined ? { note: mapping.note } : {}),
        ...(refs.length > 0 ? { artifacts: refs } : {}),
        ...(data === undefined ? {} : { data }),
        ...(options.includeHistory === true ? { history: historyOf(task) } : {}),
    };
    return {
        content,
        structuredContent: envelope,
        ...(ERROR_STATES.includes(state) ? { isError: true } : {}),
    };
}
/** Builds the tool result for whichever arm SendMessage returned. */
export function resultEnvelope(handles, alias, result) {
    return isTask(result)
        ? taskEnvelope(handles, alias, result)
        : messageEnvelope(handles, alias, result);
}
/** Flattens the A2A history of a task into role and text turns. */
export function historyOf(task) {
    return (task.history ?? []).map((message) => ({
        // Role is a numeric ts-proto enum: anything that is not the agent is
        // reported as the user side of the conversation.
        role: message.role === Role.ROLE_AGENT ? "agent" : "user",
        text: textOfMessage(message),
    }));
}
/** The text parts of a message, joined, for a history turn. */
function textOfMessage(message) {
    return message.parts
        .filter((part) => part.content?.$case === "text")
        .map((part) => (part.content?.$case === "text" ? part.content.value : ""))
        .join("\n");
}
