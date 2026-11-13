import { type Message, type SendMessageResult, type StreamResponse, type Task } from "@a2a-js/sdk";
import type { AgentCardResolver } from "./agent-card.js";
/** The specification name of an A2A error code, when it names one. */
export declare function a2aErrorName(code: number | undefined): string | undefined;
/** An upstream A2A failure, ready to be reported as an MCP tool error. */
export declare class A2ABridgeError extends Error {
    /** The numeric code of the A2A JSON-RPC envelope, when there was one. */
    readonly a2aErrorCode: number | undefined;
    /** The UPPER_SNAKE_CASE reason of the A2A error, when the SDK typed it. */
    readonly a2aReason: string | undefined;
    constructor(message: string, a2aErrorCode?: number, a2aReason?: string);
}
/** What a2a_send_message hands to the upstream agent. */
export interface SendMessageInput {
    text: string;
    /** A2A context id, to continue a conversation. */
    contextId?: string;
    /** A2A task id, to answer a task parked in INPUT_REQUIRED. */
    taskId?: string;
}
export declare class A2AClientPool {
    #private;
    constructor(cards: AgentCardResolver);
    /**
     * Sends one text message. Waits for a terminal or interrupted state by
     * default; `returnImmediately` asks the agent to answer as soon as the
     * task exists, which is what the tasks extension needs from an agent that
     * does not stream.
     */
    sendMessage(alias: string, input: SendMessageInput, options?: {
        returnImmediately?: boolean;
    }): Promise<SendMessageResult>;
    /**
     * Opens the SendStreamingMessage stream of an agent. The generator is
     * handed back unconsumed: the caller reads the first event to answer the
     * MCP request, then keeps pulling in the background.
     */
    sendMessageStream(alias: string, input: SendMessageInput): Promise<AsyncGenerator<StreamResponse, void, undefined>>;
    /** True when the agent card of an alias declares streaming support. */
    supportsStreaming(alias: string): Promise<boolean>;
    /** Reads one task back, optionally trimming its history. */
    getTask(alias: string, taskId: string, historyLength?: number): Promise<Task>;
    /** Asks the agent to cancel a task. Cancellation is cooperative in A2A. */
    cancelTask(alias: string, taskId: string): Promise<Task>;
    /** Drops the cached client of an alias, so the next call rebuilds it. */
    forget(alias: string): void;
}
export declare function buildUserMessage(input: SendMessageInput): Message;
/** Translates anything thrown by the A2A client into an A2ABridgeError. */
export declare function toBridgeError(alias: string, operation: string, error: unknown): A2ABridgeError;
