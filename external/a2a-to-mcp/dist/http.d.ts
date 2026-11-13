/**
 * The HTTP face of the bridge: one node:http server in front of the SDK
 * handler.
 *
 * Two things happen here and nowhere else. The request body is buffered once
 * and replayed into as many web Requests as needed, because the SDK consumes a
 * web Request and never touches the Node stream. And a modern request naming a
 * tasks method is answered by the interceptor rather than by the SDK
 * (typescript-sdk issue 2598).
 *
 * Nothing else is remembered between requests: the bridge holds no session, it
 * never reads and never mints an Mcp-Session-Id, and the legacy route serves
 * the tasks methods with a refusal that needs no handshake.
 */
import { type Server } from "node:http";
import { type McpHttpHandler } from "@modelcontextprotocol/server";
import type { TasksService } from "./tasks/handlers.js";
export interface RouterOptions {
    handler: McpHttpHandler;
    /** Hostnames accepted in the Host header, without port (DNS rebinding protection). */
    allowedHosts: string[];
    tasks: TasksService;
    serverInfo: {
        name: string;
        version: string;
    };
}
export interface BridgeRouter {
    fetch(request: Request): Promise<Response>;
}
/** Builds the fetch-shaped entry point of the bridge. */
export declare function createRouter(options: RouterOptions): BridgeRouter;
/** Builds the unstarted node:http server that serves the router. */
export declare function createHttpServer(router: BridgeRouter, path: string): Server;
/** Resolves the base URL of a listening server. */
export declare function addressOf(server: Server): {
    host: string;
    port: number;
};
