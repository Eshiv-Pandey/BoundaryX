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
import { createServer } from "node:http";
import { hostHeaderValidationResponse, isLegacyRequest, } from "@modelcontextprotocol/server";
import { interceptTasksRequest } from "./tasks/intercept.js";
const MAX_BODY_BYTES = 8 * 1024 * 1024;
/** Builds the fetch-shaped entry point of the bridge. */
export function createRouter(options) {
    return {
        async fetch(request) {
            const rejected = hostHeaderValidationResponse(request, options.allowedHosts);
            if (rejected !== undefined) {
                return rejected;
            }
            const body = request.method === "GET" || request.method === "HEAD"
                ? Buffer.alloc(0)
                : Buffer.from(await request.arrayBuffer());
            const rebuild = () => rebuildRequest(request, body);
            const legacy = await isLegacyRequest(rebuild());
            if (!legacy) {
                const intercepted = await interceptTasksRequest({
                    headerMethod: request.headers.get("mcp-method") ?? undefined,
                    headerName: request.headers.get("mcp-name") ?? undefined,
                    body,
                    serverInfo: options.serverInfo,
                    tasks: options.tasks,
                });
                if (intercepted !== undefined) {
                    return intercepted;
                }
            }
            return options.handler.fetch(rebuild());
        },
    };
}
function rebuildRequest(original, body) {
    const init = {
        method: original.method,
        headers: original.headers,
    };
    if (body.length > 0) {
        init.body = body;
        init.duplex = "half";
    }
    return new Request(original.url, init);
}
/** Builds the unstarted node:http server that serves the router. */
export function createHttpServer(router, path) {
    return createServer((req, res) => {
        void serve(req, res, router, path).catch((error) => {
            if (!res.headersSent) {
                res.writeHead(500, { "Content-Type": "application/json" });
            }
            res.end(JSON.stringify({
                jsonrpc: "2.0",
                id: null,
                error: {
                    code: -32603,
                    message: error instanceof Error ? error.message : String(error),
                },
            }));
        });
    });
}
async function serve(req, res, router, path) {
    const requestUrl = new URL(req.url ?? "/", `http://${req.headers.host ?? "127.0.0.1"}`);
    if (requestUrl.pathname !== path) {
        res.writeHead(404, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: `No MCP endpoint at ${requestUrl.pathname}. Use ${path}.` }));
        return;
    }
    const body = await readBody(req);
    const headers = new Headers();
    for (const [name, value] of Object.entries(req.headers)) {
        if (value === undefined) {
            continue;
        }
        for (const single of Array.isArray(value) ? value : [value]) {
            headers.append(name, single);
        }
    }
    const init = { method: req.method ?? "GET", headers };
    if (body.length > 0 && req.method !== "GET" && req.method !== "HEAD") {
        init.body = body;
        init.duplex = "half";
    }
    const response = await router.fetch(new Request(requestUrl.toString(), init));
    const outgoing = {};
    response.headers.forEach((value, name) => {
        outgoing[name] = value;
    });
    res.writeHead(response.status, outgoing);
    if (response.body === null) {
        res.end();
        return;
    }
    // The legacy leg answers in SSE, so the body is streamed rather than
    // buffered: a keep-alive stream must not be held until it closes.
    const reader = response.body.getReader();
    for (;;) {
        const chunk = await reader.read();
        if (chunk.done) {
            break;
        }
        res.write(Buffer.from(chunk.value));
    }
    res.end();
}
function readBody(req) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        let size = 0;
        req.on("data", (chunk) => {
            size += chunk.length;
            if (size > MAX_BODY_BYTES) {
                reject(new Error(`Request body exceeds ${MAX_BODY_BYTES} bytes.`));
                req.destroy();
                return;
            }
            chunks.push(chunk);
        });
        req.on("end", () => {
            resolve(Buffer.concat(chunks));
        });
        req.on("error", reject);
    });
}
/** Resolves the base URL of a listening server. */
export function addressOf(server) {
    const address = server.address();
    if (address === null) {
        throw new Error("The bridge is not listening.");
    }
    return { host: address.address, port: address.port };
}
