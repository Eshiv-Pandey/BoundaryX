import { type Task } from "@a2a-js/sdk";
import { type CallToolResult, type InputRequiredResult, type RequestStateCodec } from "@modelcontextprotocol/server";
import type { A2AClientPool } from "./a2a-client.js";
import { type BridgeHandles } from "./envelope.js";
/**
 * What the bridge seals into requestState between two rounds: the alias and
 * the tk_ handle, and nothing else. The payload is readable by the client, so
 * the A2A task id and context id stay behind the handle table.
 */
export interface RequestStatePayload {
    alias: string;
    taskHandle: string;
}
export type BridgeRequestStateCodec = RequestStateCodec<RequestStatePayload>;
/**
 * Builds the requestState codec of one bridge.
 *
 * The key is drawn once at startup and never leaves the process: on the
 * 2026-07-28 route every request is served by a fresh server instance, so the
 * state itself is the only thing that survives between rounds, and a single
 * process serves every round of a flow. The state expires with the handle it
 * names, so a replay cannot outlive what it points at.
 */
export declare function createBridgeRequestStateCodec(ttlMs: number): BridgeRequestStateCodec;
/**
 * Reads back what the verify hook decoded. The value is already proven by the
 * HMAC, so this only rejects a shape the bridge never minted.
 */
export declare function readRequestState(value: unknown): RequestStatePayload | undefined;
export interface MrtrServiceOptions {
    handles: BridgeHandles;
    agents: A2AClientPool;
    requestState: BridgeRequestStateCodec;
}
/** Raised when a requestState names an agent other than the one called. */
export declare class WrongAgentStateError extends Error {
    constructor(expected: string, actual: string);
}
/** The two rounds of one A2A question asked through MCP elicitation. */
export declare class MrtrService {
    #private;
    constructor(options: MrtrServiceOptions);
    /** True when an A2A answer is a task the agent parked on a question. */
    static isWaitingForInput(result: Task): boolean;
    /**
     * Turns an A2A question into the one form-mode elicitation the bridge ever
     * asks for. A2A carries the question as free text with no schema, so the
     * schema is a single required string and the agent wording is the message.
     */
    ask(alias: string, task: Task): Promise<InputRequiredResult>;
    /**
     * The round after the client answered.
     *
     * An accepted answer travels to the agent on the same A2A task, and the
     * call waits for the terminal or interrupted state exactly as an ordinary
     * a2a_send_message does; an agent that asks again gets a fresh
     * InputRequiredResult, which is the natural loop of the pattern. A declined
     * or cancelled elicitation cancels the A2A task rather than leaving it
     * parked until its handle expires.
     */
    resume(alias: string, state: RequestStatePayload, responses: Record<string, unknown> | undefined): Promise<CallToolResult | InputRequiredResult>;
}
