import { type TasksService } from "./handlers.js";
/** Code the 2026-07-28 revision reserves for a header that contradicts the body. */
export declare const HEADER_MISMATCH_ERROR_CODE = -32020;
export interface InterceptContext {
    /** Method named by the Mcp-Method header, when there is one. */
    headerMethod: string | undefined;
    /** Value of the Mcp-Name header, when there is one. */
    headerName: string | undefined;
    /** The raw request body, already buffered by the HTTP layer. */
    body: Buffer;
    /** Server identity stamped on every answer this module writes. */
    serverInfo: {
        name: string;
        version: string;
    };
    tasks: TasksService;
}
/**
 * Answers a tasks request, or returns undefined so the caller hands the
 * request to the SDK unchanged. Call it only when the request was classified
 * modern: on the legacy route the SDK serves the same handlers correctly.
 */
export declare function interceptTasksRequest(context: InterceptContext): Promise<Response | undefined>;
/** Serializes an error thrown by the handlers into a JSON-RPC error response. */
export declare function errorResponse(id: string | number | null, error: unknown): Response;
