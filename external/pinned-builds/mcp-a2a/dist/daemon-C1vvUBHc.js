import { A as ServerCallContext, D as JsonRpcTransportHandler, M as UnauthenticatedUser, P as BUILD_INFO, T as DefaultRequestHandler, c as nowIso, j as TaskState, x as AgentEvent } from "./config-B77d6yRo.js";
import { A2A_PROTOCOL_VERSION, AGENT_CARD_PATH } from "@a2a-js/sdk";
import { timingSafeEqual } from "node:crypto";
import { localhostHostValidation, localhostOriginValidation } from "@modelcontextprotocol/hono";
import { Hono } from "hono";
//#region src/card.ts
/** Where the daemon serves the JSON-RPC binding. Advertised in the card. */
const A2A_RPC_PATH = "/a2a/v1";
/**
* The agent card this machine publishes at `/.well-known/agent-card.json`.
*
* Every field the v1.0 spec marks required is present: `name`, `description`,
* `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`,
* `defaultOutputModes`, `skills`. The optional ones are omitted rather than
* filled with placeholders — an empty `provider.organization` is worse than no
* provider, because a peer renders it.
*
* Two capabilities are deliberately FALSE in v1, and saying so in the card is
* the whole point of having one:
*
*   streaming          — `SendStreamingMessage`/`SubscribeToTask` are not served.
*                        A peer should poll `GetTask`, which for a task that
*                        waits on a human-supervised agent is the honest shape
*                        anyway.
*   pushNotifications  — the daemon accepts no push configs. It could store
*                        them, but the state changes that matter here are
*                        written by the *other* process (the stdio server, when
*                        an agent answers), so a sender wired into the request
*                        handler would never fire on the event a caller cares
*                        about. A config that silently never delivers is worse
*                        than a declined capability.
*/
const buildAgentCard = (config) => ({
	name: config.agentName,
	description: config.agentDescription,
	supportedInterfaces: [{
		url: `${config.daemonUrl.replace(/\/+$/, "")}${A2A_RPC_PATH}`,
		protocolBinding: "JSONRPC",
		tenant: "",
		protocolVersion: A2A_PROTOCOL_VERSION
	}],
	provider: void 0,
	version: BUILD_INFO.version,
	capabilities: {
		streaming: false,
		pushNotifications: false,
		extensions: [],
		extendedAgentCard: false
	},
	securitySchemes: {},
	securityRequirements: [],
	defaultInputModes: ["text/plain", "application/json"],
	defaultOutputModes: ["text/plain", "application/json"],
	skills: [{
		id: "delegate-task",
		name: "Delegate a task to a local coding agent",
		description: "Queue a request for one of the coding agents running on this machine — Claude Code, Codex, Cursor, LM Studio. The task is created immediately in SUBMITTED and stays there until an agent picks it up; poll GetTask for the answer. Nothing is executed automatically: an inbound task is a proposal a human-supervised agent chooses to act on, so treat a reply as a considered answer rather than a guaranteed one.",
		tags: [
			"code",
			"delegation",
			"local",
			"human-in-the-loop"
		],
		examples: [
			"Read src/server.ts in ~/Projects/example and summarise how requests are routed.",
			"Run the test suite in ~/Projects/example and report which tests fail.",
			"Draft a migration plan for moving this project off express."
		],
		inputModes: [],
		outputModes: [],
		securityRequirements: []
	}],
	signatures: []
});
//#endregion
//#region src/executor.ts
/**
* What the daemon does with an inbound task: park it, and tell the caller it is
* parked.
*
* This is the whole inbound design in one class, and the reason it looks so
* unlike a normal `AgentExecutor` — it runs no agent. An inbound A2A task is a
* PROPOSAL for a human-supervised agent on this machine, so the executor's only
* job is to record it in `SUBMITTED` and return. Acting on it is a separate,
* deliberate act by the receiving agent (`a2a_respond_to_task`), for two
* reasons that point the same way:
*
*   * measured — content that reaches an agent through a channel arrives as
*     untrusted data, and the receiving agent correctly refused to act on an
*     instruction inside it. A design where arrival triggers execution would be
*     both a prompt-injection surface and one the agent rightly ignores;
*   * a daemon that executed inbound work would be a remote-code-execution
*     endpoint on loopback, gated by nothing but a shared token.
*
* `SUBMITTED` is the right resting state and not merely a convenient one: the
* spec defines it as "successfully submitted and acknowledged", which is exactly
* what has happened. It is also neither terminal nor interrupted, so
* `DefaultRequestHandler` does not hold the caller open waiting for it —
* publishing it and returning settles the bus, and the caller gets its task
* straight back.
*/
var ProposalExecutor = class {
	store;
	logger;
	constructor(opts) {
		this.store = opts.store;
		this.logger = opts.logger;
	}
	execute = async (requestContext, eventBus) => {
		const peer = peerFromContext(requestContext.context);
		const existing = requestContext.task;
		const task = existing ? {
			...existing,
			status: submitted()
		} : {
			id: requestContext.taskId,
			contextId: requestContext.contextId,
			status: submitted(),
			artifacts: [],
			history: [],
			metadata: void 0
		};
		this.store.put(task, {
			direction: "inbound",
			peer
		});
		this.logger?.warn?.(`inbound task ${task.id} from ${peer} — parked as a proposal in SUBMITTED`);
		eventBus.publish(AgentEvent.task(task));
	};
	/**
	* A peer withdrawing a request. Honoured unconditionally: nothing was running,
	* so there is nothing that can refuse to stop.
	*/
	cancelTask = async (taskId, eventBus) => {
		const record = this.store.get(taskId);
		const contextId = record && typeof record.task.contextId === "string" ? record.task.contextId : "";
		this.logger?.warn?.(`inbound task ${taskId} canceled by the peer`);
		eventBus.publish(AgentEvent.statusUpdate({
			taskId,
			contextId,
			status: {
				state: TaskState.TASK_STATE_CANCELED,
				message: void 0,
				timestamp: nowIso()
			},
			metadata: void 0
		}));
	};
};
const submitted = () => ({
	state: TaskState.TASK_STATE_SUBMITTED,
	message: void 0,
	timestamp: nowIso()
});
/**
* Who sent this. There is no field for it in A2A — the protocol has no notion of
* a caller identity beyond whatever the security scheme establishes — so it is
* read from the request headers the default context builder stashes in
* `context.state`, preferring an explicit `X-A2A-From` over the `User-Agent`
* every HTTP client sends anyway.
*
* It is attribution, not authentication: anything that can reach the daemon can
* claim any name. The thing that actually gates access is the bearer token, and
* the thing that limits the damage is that nothing here executes.
*/
const peerFromContext = (context) => {
	const headers = context?.state.get("headers");
	if (typeof headers === "object" && headers !== null) {
		const bag = headers;
		const from = first(bag["x-a2a-from"]) ?? first(bag["user-agent"]);
		if (from) return from.slice(0, 200);
	}
	return "unknown";
};
const first = (value) => {
	const trimmed = (Array.isArray(value) ? value[0] : value)?.trim();
	return trimmed ? trimmed : void 0;
};
//#endregion
//#region src/daemon.ts
/** Cap the body: an unbounded reader plus an open port is a one-request OOM. */
const MAX_BODY_BYTES = 1048576;
const jsonRpcError = (code, message, status) => Response.json({
	jsonrpc: "2.0",
	id: null,
	error: {
		code,
		message
	}
}, { status });
/**
* Constant-time comparison, so a wrong token cannot be recovered byte by byte
* from response timing. Lengths are compared first because `timingSafeEqual`
* throws on a mismatch — which is itself a length oracle, and an unavoidable one.
*/
const tokensMatch = (a, b) => {
	const left = Buffer.from(a);
	const right = Buffer.from(b);
	return left.length === right.length && timingSafeEqual(left, right);
};
const createDaemonApp = (opts) => {
	const { config, store } = opts;
	const logger = opts.logger;
	const card = buildAgentCard(config);
	const requestHandler = new DefaultRequestHandler(card, store, new ProposalExecutor({
		store,
		...logger ? { logger } : {}
	}));
	const rpc = new JsonRpcTransportHandler(requestHandler);
	const app = new Hono();
	/** Reject an oversized body before anything reads, buffers or parses it. */
	app.use(async (c, next) => {
		if (Number(c.req.header("content-length") ?? 0) > 1048576) return Response.json({
			error: "payload_too_large",
			limit: MAX_BODY_BYTES
		}, { status: 413 });
		return await next();
	});
	app.use(localhostHostValidation());
	app.use(localhostOriginValidation());
	/**
	* The agent card is served WITHOUT the bearer check, deliberately. It holds no
	* secret — a name, a description, one URL and a skill list — and discovery has
	* to work before a peer has been given a credential, or the card cannot do the
	* one job it exists for. The A2A spec treats the well-known card as public and
	* puts the credential requirement in `securitySchemes`.
	*/
	app.get(`/${AGENT_CARD_PATH}`, (c) => c.json(card));
	/** For launchd, and for answering "is it up" without speaking A2A. */
	app.get("/health", (c) => c.json({
		ok: true,
		name: BUILD_INFO.name,
		version: BUILD_INFO.version,
		git_commit: BUILD_INFO.gitCommit,
		agent: card.name,
		authenticated: Boolean(config.token),
		tasks: store.records().length
	}));
	app.post(A2A_RPC_PATH, async (c) => {
		if (config.token) {
			const header = c.req.header("authorization") ?? "";
			const presented = header.startsWith("Bearer ") ? header.slice(7) : "";
			if (!tokensMatch(presented, config.token)) {
				logger?.warn?.("rejected an A2A request with a missing or wrong bearer token");
				return jsonRpcError(-32001, "Unauthorized: a valid bearer token is required.", 401);
			}
		}
		let body;
		try {
			body = await c.req.json();
		} catch {
			return jsonRpcError(-32700, "Parse error: the body is not JSON.", 400);
		}
		const context = new ServerCallContext({
			user: new UnauthenticatedUser(),
			requestedVersion: c.req.header("a2a-version") ?? "1.0",
			state: /* @__PURE__ */ new Map([["headers", Object.fromEntries(c.req.raw.headers)]])
		});
		try {
			const result = await rpc.handle(body, context);
			if (isAsyncGenerator(result)) return jsonRpcError(-32004, "Streaming is not served by this agent. Poll GetTask instead.", 501);
			return c.json(result);
		} catch (err) {
			logger?.error?.("A2A request failed", err);
			return jsonRpcError(-32603, "Internal error.", 500);
		}
	});
	return app;
};
const isAsyncGenerator = (value) => typeof value === "object" && value !== null && Symbol.asyncIterator in value;
//#endregion
export { A2A_RPC_PATH as a, peerFromContext as i, createDaemonApp as n, buildAgentCard as o, ProposalExecutor as r, MAX_BODY_BYTES as t };

//# sourceMappingURL=daemon-C1vvUBHc.js.map