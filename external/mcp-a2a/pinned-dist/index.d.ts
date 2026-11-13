import { McpServer } from "@modelcontextprotocol/server";
import { AgentCard, ListTasksRequest, ListTasksResponse, Message, Task, TaskState } from "@a2a-js/sdk";
import { AgentExecutor, ExecutionEventBus, RequestContext, ServerCallContext, TaskStore } from "@a2a-js/sdk/server";
import "@a2a-js/sdk/client";
import { z } from "zod";
import { Hono } from "hono";
//#region src/client/auth.d.ts
/**
 * The logger every layer takes, and deliberately nothing else.
 *
 * Elsewhere in the fleet this module also holds a `TokenProvider`: a seam for
 * minting and reminting a short-lived credential, with `invalidate()` for the one
 * retryable auth failure (a 401 after expiry). There is nothing to mint here —
 * `A2A_TOKEN` is a static shared secret for this machine's loopback mesh — so a
 * provider would be indirection over a constant, and a 401 is a configuration
 * error rather than something to retry. `createA2AFetch` attaches the header.
 *
 * All methods are optional so a caller can pass `{}`; call sites use
 * `logger?.debug?.(…)`. It is threaded through `createServer` rather than being a
 * module singleton, because a singleton cannot be silenced in a test.
 */
type Logger = {
  debug?(...args: unknown[]): void;
  warn?(...args: unknown[]): void;
  error?(...args: unknown[]): void;
};
//#endregion
//#region src/config.d.ts
declare const ConfigSchema: z.ZodObject<{
  daemonUrl: z.ZodDefault<z.ZodURL>;
  agentName: z.ZodDefault<z.ZodString>;
  agentDescription: z.ZodDefault<z.ZodString>;
  token: z.ZodOptional<z.ZodString>;
  peers: z.ZodDefault<z.ZodArray<z.ZodURL>>;
  stateDir: z.ZodString;
  allowWrites: z.ZodDefault<z.ZodBoolean>;
  maxWaitSeconds: z.ZodDefault<z.ZodNumber>;
  channel: z.ZodDefault<z.ZodBoolean>;
  pollIntervalMs: z.ZodDefault<z.ZodNumber>;
  maxRetries: z.ZodDefault<z.ZodNumber>;
}, z.core.$strict>;
type Config = z.output<typeof ConfigSchema>;
export declare const resolveConfigPath: (env?: NodeJS.ProcessEnv) => string;
/**
 * The task store, which is machine state shared by two processes rather than
 * one process's private directory. `XDG_STATE_HOME` is the right home for it:
 * it survives a reboot, it is not a cache, and it is not configuration.
 *
 * ⚠ Both halves must resolve the same path or they hold two disjoint stores and
 * no task ever crosses. That is why `A2A_STATE_DIR` is deliberately NOT
 * declared as `stateEnv` in the Bastion catalog — Bastion redirects `stateEnv`
 * into each profile's own directory, which is right for a token file and wrong
 * for this.
 */
export declare const resolveStateDir: (env?: NodeJS.ProcessEnv) => string;
/**
 * Environment first, config file second, **per field** — not whole-source.
 * Docker, launchd and CI inject the environment and must keep working
 * untouched, while a one-off `A2A_ALLOW_WRITES=0` still has to beat a file that
 * says `true`. Merging field by field is the only rule that gives both.
 *
 * `loadConfig(env, path)` takes both as parameters so precedence is testable
 * without touching `process.env` — and so the suite can be pointed at a path
 * that cannot exist, rather than at the developer's own credentials.
 */
export declare const loadConfig: (env?: NodeJS.ProcessEnv, configPath?: string) => Config;
/**
 * The setup guide, as data. Returned by `a2a_auth_status` and printed to stderr
 * at startup, because the alternative — exiting with a message the client
 * swallows — is the most expensive mistake available in an MCP server.
 */
export declare const setupInstructions: (config: Config,
/**
 * What the caller has already established. `a2a_auth_status` probes the daemon
 * before calling this, and a list that tells you to start something already
 * running makes every other step in it less believable.
 */
known?: {
  daemonReachable?: boolean;
}) => string[];
//#endregion
//#region src/store/tasks.d.ts
/**
 * Which way the task is going, from this machine's point of view.
 *
 * `inbound`  — a peer asked us to do something. Arrives through the daemon and
 *              is a PROPOSAL: a local agent may choose to act on it.
 * `outbound` — we asked a peer to do something. Recorded by `a2a_send_message`
 *              as a local mirror of the peer's own task, so `a2a_list_tasks`
 *              can answer "what did I delegate" without polling every peer.
 */
type Direction = "inbound" | "outbound";
/** The record format. `version` so the layout can change without guessing. */
type TaskRecord = {
  version: 1;
  direction: Direction;
  /** Base URL of the other side: who sent it (inbound) or who we sent it to. */
  peer: string;
  createdAt: string;
  updatedAt: string;
  /** The A2A `Task`, in its wire (JSON) form — never our own dialect. */
  task: Record<string, unknown>;
};
/** `taskId -> mtimeMs`, the cheap change token the long-poll compares. */
type StoreSnapshot = Map<string, number>;
type StoreChange = {
  taskId: string;
  kind: "created" | "updated";
  record: TaskRecord;
};
type FileTaskStoreOptions = {
  stateDir: string;
  /**
   * The direction stamped on a task this store creates and has never seen
   * before. The daemon's store is `inbound` — everything it is asked to create
   * came from a peer. The stdio server records outbound tasks explicitly.
   */
  defaultDirection: Direction;
  /** The peer stamped on a newly created record when the caller names none. */
  defaultPeer?: string;
  logger?: Logger;
};
/**
 * A `TaskStore` on disk, one JSON file per task, shared by both processes.
 *
 * Deliberately not SQLite: `node:sqlite` is still experimental on Node 22, a
 * second copy of the data would need migrating, and the volumes here are a
 * handful of tasks. What the filesystem gives for free is the part that matters
 * — an atomic `rename` is a publish, so a reader in the other process never
 * sees a partial record.
 *
 * ⚠ The one thing it does not give is a cross-process lock. The SDK's
 * `ResultManager` serialises writes within a process, and the two processes here
 * touch a task at different points in its life (the daemon creates it, the stdio
 * server answers it), so the read-modify-write window is narrow rather than
 * closed. A genuinely concurrent write to the same task can lose the earlier of
 * the two. That is a known limitation, written down rather than papered over.
 *
 * `ServerCallContext` is accepted because the interface requires it and ignored
 * because this store has one tenant and one owner by construction: it is a
 * single user's machine, reachable only over loopback. A multi-user deployment
 * would need `context.user` folded into the path, which is exactly the change
 * that also needs real per-peer auth.
 */
export declare class FileTaskStore implements TaskStore {
  private readonly dir;
  private readonly defaultDirection;
  private readonly defaultPeer;
  private readonly logger;
  constructor(opts: FileTaskStoreOptions);
  /** Whether this store can be written, for `a2a_auth_status` to report. */
  diagnose(): {
    dir: string;
    writable: boolean;
    error?: string;
  };
  private pathFor;
  save(task: Task, _context?: ServerCallContext): Promise<void>;
  load(taskId: string, _context?: ServerCallContext): Promise<Task | undefined>;
  /**
   * The SDK's listing, for a peer calling `ListTasks` against us. Offset
   * pagination through an opaque `pageToken`: the store is a directory scan
   * either way, so a cursor would buy nothing but a way to be wrong.
   */
  list(params: ListTasksRequest, _context?: ServerCallContext): Promise<ListTasksResponse>;
  /** Create or replace a record, stamping direction and peer explicitly. */
  put(task: Task, meta: {
    direction: Direction;
    peer: string;
  }): TaskRecord;
  /** One record, or undefined. Never throws on a hostile id. */
  get(taskId: string): TaskRecord | undefined;
  /** One record or a typed 404 — for a tool that must report a miss. */
  require(taskId: string): TaskRecord;
  /**
   * Append a status change, and optionally a message and an artifact, to a task
   * that already exists. This is the write `a2a_respond_to_task` performs: the
   * deliberate, separate act of answering a proposal.
   */
  applyResponse(taskId: string, update: {
    state: TaskState;
    message?: Message;
    artifactText?: string;
    artifactName?: string;
  }): TaskRecord;
  /** Every record, newest change first. Bounded, so a runaway directory cannot hang a tool. */
  records(filter?: {
    direction?: Direction;
  }): TaskRecord[];
  /** `taskId -> mtimeMs`. The change token: one `stat` per task, no parsing. */
  snapshot(): StoreSnapshot;
  /** What changed against a baseline snapshot, with the records attached. */
  changesSince(baseline: StoreSnapshot, filter?: {
    direction?: Direction;
  }): StoreChange[];
  /**
   * The same, between two snapshots the caller already holds.
   *
   * This exists because a poller that advances its baseline needs the SAME
   * snapshot it compared against to become the next baseline. Taking a fresh one
   * afterwards loses any write that landed in between — a lost wakeup, whose
   * symptom is a task sitting unanswered while an agent waits out its full
   * timeout, and which is invisible in a test because the window is microseconds.
   */
  changesBetween(baseline: StoreSnapshot, current: StoreSnapshot, filter?: {
    direction?: Direction;
  }): StoreChange[];
  delete(taskId: string): boolean;
  private ids;
  private readRecord;
  private writeRecord;
}
/** The state as the numeric enum, read from the record's wire form. */
export declare const readState: (record: TaskRecord) => TaskState;
//#endregion
//#region src/channel.d.ts
/**
 * The experimental capability an interactive Claude Code session looks for, and
 * the notification it delivers.
 *
 * This is the one measured path that reaches a WAITING agent without parking a
 * tool call: a generic `notifications/message` is swallowed by both Claude Code
 * and Codex, and the MCP `instructions` field is ignored when no tool is needed.
 * `claude/channel` is a true push, verified end to end.
 *
 * ⚠ It is a research preview, Claude Code only, and needs Anthropic auth (not
 * Bedrock, Vertex or Foundry). So it is an ENHANCEMENT over `a2a_wait_for_task`
 * and never the only route — the long-poll has to work standalone, and does.
 *
 * ⚠ Delivery also needs the session to have opted in:
 *     claude --dangerously-load-development-channels server:a2a
 *   and confirm the dialog. Do NOT also pass `--channels` for the same entry —
 *   the bypass is per-entry and the `--channels` copy is refused as not on the
 *   allowlist. In `-p` mode the debug log reads `pollChannel=false
 *   nonInteractive=true` and nothing is delivered, so a non-interactive test
 *   looks like a bug that isn't one.
 */
export declare const CHANNEL_CAPABILITY = "claude/channel";
export declare const CHANNEL_NOTIFICATION = "notifications/claude/channel";
/**
 * Declared before the transport is connected, because `registerCapabilities`
 * refuses to run afterwards — it has to be part of the `initialize` result.
 */
export declare const declareChannelCapability: (server: McpServer) => void;
type ChannelWatcher = {
  /** Stop polling. Called on shutdown; also what the tests use. */
  stop(): void;
  /** How many notifications have been emitted — the assertion a test can make. */
  emitted(): number;
};
/**
 * Watch the store and push each newly arrived inbound task into the session.
 *
 * The poll is a `readdir` plus one `stat` per task, deliberately rather than
 * `fs.watch`: on macOS `fs.watch` is FSEvents-backed, it coalesces, and it does
 * not reliably report a `rename` over an existing name — which is exactly how
 * every record here is written, because an atomic replace is what keeps the other
 * process from reading a half-written file. Stat polling sees the mtime change no
 * matter how the file got there. At a one-second interval over a handful of files
 * the cost is not measurable, and the timer is `unref`'d so it never holds the
 * process open.
 */
export declare const startChannelWatcher: (opts: {
  server: McpServer;
  store: FileTaskStore;
  config: Config;
  logger?: Logger;
}) => ChannelWatcher;
//#endregion
//#region src/client/peer.d.ts
type PeerClientOptions = {
  stateDir: string;
  /** Peers named in the configuration, offered before anything is discovered. */
  configuredPeers: string[];
  /** Our own daemon's base URL — peer zero, reachable by the same code path. */
  daemonUrl: string;
  token: string | undefined;
  maxRetries: number;
  userAgent: string;
  fetch?: typeof fetch;
  logger?: Logger;
};
type PeerSummary = {
  url: string;
  name: string;
  description: string;
  /** Whether this is our own daemon rather than somebody else's agent. */
  self: boolean;
  configured: boolean;
  cachedAt: string | undefined;
};
/**
 * Everything the stdio tools do to somebody else's agent.
 *
 * Discovery, the card cache, and one A2A client per peer. The SDK's
 * `ClientFactory` picks a transport by reading the peer's own card, which is why
 * a card is fetched before a message is ever sent: `supportedInterfaces` is what
 * says whether this peer speaks JSON-RPC, HTTP+JSON or gRPC, and at which URL.
 */
export declare class PeerClient {
  private readonly cache;
  private readonly resolver;
  private readonly factory;
  private readonly opts;
  /** One client per peer URL. Cheap to build, but it also caches the card. */
  private readonly clients;
  /** The same authenticating, retrying fetch the SDK transports get. */
  private readonly rpcFetch;
  constructor(opts: PeerClientOptions);
  /** Fetch a peer's card, cache it, and return it. Always refetches. */
  discover(url: string): Promise<AgentCard>;
  /** The card from cache, or a fresh fetch when nothing is cached yet. */
  card(url: string): Promise<AgentCard>;
  /**
   * Known peers without touching the network: the configured list, our own
   * daemon, and everything discovered so far. A peer with no cached card is
   * still listed — that it is unknown is the useful part of the answer.
   */
  peers(): PeerSummary[];
  /**
   * Send a message to a peer, returning both what it answered with and the
   * message we sent.
   *
   * The sent message is handed back because the answer often does not contain it.
   * Measured against this implementation: with `polling: true` the client sets
   * `returnImmediately`, and the acknowledgement is then the executor's first
   * snapshot — published before the store merged the request into the task's
   * history — so `task.history` comes back EMPTY. A mirror built from that alone
   * would record a task with no record of what was asked, which is most of what a
   * mirror is for.
   */
  sendMessage(url: string, args: {
    text: string;
    taskId?: string;
    contextId?: string;
    metadata?: Record<string, unknown>;
  }): Promise<{
    result: Task | Message;
    sent: Message;
  }>;
  getTask(url: string, taskId: string, historyLength?: number): Promise<Task>;
  cancelTask(url: string, taskId: string): Promise<Task>;
  setPushNotificationConfig(url: string, args: {
    taskId: string;
    id: string;
    url: string;
    token?: string;
  }): Promise<unknown>;
  deletePushNotificationConfig(url: string, args: {
    taskId: string;
    id: string;
  }): Promise<void>;
  /**
   * One raw A2A JSON-RPC call, for the escape hatch: an RPC nobody wrapped stays
   * reachable without a code change.
   *
   * It goes through the same authenticating `fetch` as everything else, and the
   * URL comes from the peer's own card rather than being composed — a peer is
   * free to serve the binding at any path, and guessing `/a2a/v1` would work
   * against this implementation and quietly fail against others.
   */
  rawRpc(url: string, method: string, params: Record<string, unknown>): Promise<unknown>;
  /**
   * Is a peer answering at all? Used by `a2a_auth_status` against our own
   * daemon, where "is it running" is the first question and an exception is the
   * wrong way to answer it.
   */
  probe(url: string): Promise<{
    reachable: boolean;
    card?: AgentCard;
    error?: string;
  }>;
  private clientFor;
  /**
   * One place where a thrown SDK error becomes an `A2AApiError` carrying a
   * remedy. Without it every tool would surface the SDK's own message, which
   * says what the transport saw and nothing about what to do.
   */
  private call;
}
/** A trailing slash makes two spellings of one peer, and two cache entries. */
export declare const normalizeBase: (url: string) => string;
//#endregion
//#region src/server.d.ts
export declare const SERVER_NAME: string;
export declare const SERVER_VERSION: string;
export declare const USER_AGENT: string;
type CreateServerOptions = {
  config: Config;
  /** The one seam the suite replaces: real tools, real SDK, no network. */
  fetch?: typeof fetch;
  logger?: Logger;
  /**
   * Skip the background channel watcher. On by default in production and off in
   * tests, where a timer that outlives the test is a flake generator.
   */
  watchChannel?: boolean;
};
type CreatedServer = {
  server: McpServer;
  store: FileTaskStore;
  peers: PeerClient;
  /** undefined when the channel is disabled or `watchChannel` is false. */
  channel: ChannelWatcher | undefined;
};
/**
 * A pure factory: it reads no environment, opens no socket, and starts nothing
 * but the channel watcher the caller asks for. Everything below `config.ts`
 * receives its dependencies, which is what lets the test harness drive real
 * tools through the real SDK against a mocked `fetch`.
 */
export declare const createServer: (opts: CreateServerOptions) => CreatedServer;
//#endregion
//#region src/card.d.ts
/** Where the daemon serves the JSON-RPC binding. Advertised in the card. */
export declare const A2A_RPC_PATH = "/a2a/v1";
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
export declare const buildAgentCard: (config: Config) => AgentCard;
//#endregion
//#region src/daemon.d.ts
/** Cap the body: an unbounded reader plus an open port is a one-request OOM. */
export declare const MAX_BODY_BYTES: number;
export declare const createDaemonApp: (opts: {
  config: Config;
  store: FileTaskStore;
  logger?: Logger;
}) => Hono;
//#endregion
//#region src/executor.d.ts
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
export declare class ProposalExecutor implements AgentExecutor {
  private readonly store;
  private readonly logger;
  constructor(opts: {
    store: FileTaskStore;
    logger?: Logger;
  });
  execute: (requestContext: RequestContext, eventBus: ExecutionEventBus) => Promise<void>;
  /**
   * A peer withdrawing a request. Honoured unconditionally: nothing was running,
   * so there is nothing that can refuse to stop.
   */
  cancelTask: (taskId: string, eventBus: ExecutionEventBus) => Promise<void>;
}
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
export declare const peerFromContext: (context: ServerCallContext | undefined) => string;
//#endregion
//#region src/client/fetch.d.ts
type A2AFetchOptions = {
  fetch?: typeof fetch;
  /** Shared bearer for this machine's loopback mesh. Omitted when unset. */
  token?: string | undefined;
  maxRetries: number;
  userAgent: string;
  logger?: Logger;
};
/**
 * The one `fetch` every outbound A2A call goes through, injected into the SDK's
 * transports as `fetchImpl`.
 *
 * It exists rather than being handed the global `fetch` for three reasons: the
 * bearer token belongs on every request and nowhere in the SDK's call surface;
 * retry policy is ours to own; and it is the seam the test suite replaces, which
 * is what lets tools be driven end to end through the real SDK with no network.
 *
 * A 401 is deliberately NOT retried. Unlike an OAuth deployment there is no
 * token to remint — the shared secret is static — so retrying only turns one
 * clear failure into three slow ones.
 */
export declare const createA2AFetch: (opts: A2AFetchOptions) => typeof fetch;
//#endregion
//#region src/client/errors.d.ts
/**
 * One class per failure mode, and the remedy kept separate from the message:
 * the message says what happened, the remedy is the half a model should act on.
 * `toFailure()` lifts it to a top-level field so it is not buried inside an
 * upstream envelope, where it gets skimmed past.
 */
export declare class A2AApiError extends Error {
  /** Typed `string`, not the literal, so a subclass can override it. */
  readonly name: string;
  readonly status: number;
  readonly remedy: string | undefined;
  readonly errors: unknown;
  constructor(message: string, opts: {
    status: number;
    remedy?: string;
    errors?: unknown;
  });
}
/**
 * The local daemon did not answer. Far and away the most common failure here,
 * and the one whose remedy is least guessable — so it gets its own class and
 * spells out all three causes.
 */
export declare class DaemonUnreachableError extends A2AApiError {
  readonly name = "DaemonUnreachableError";
  constructor(daemonUrl: string, cause: unknown);
}
/** A peer's agent card could not be fetched or did not parse. */
export declare class PeerUnreachableError extends A2AApiError {
  readonly name = "PeerUnreachableError";
  constructor(url: string, cause: unknown);
}
/** A task id that is not ours, or not a legal store key. */
export declare class TaskNotFoundError extends A2AApiError {
  readonly name = "TaskNotFoundError";
  constructor(taskId: string);
}
/**
 * A task id arriving from a peer is used as a filename, so it is validated
 * before it ever reaches the filesystem. `../../.ssh/id_rsa` is a task id as far
 * as the wire format is concerned.
 */
export declare class InvalidTaskIdError extends A2AApiError {
  readonly name = "InvalidTaskIdError";
  constructor(taskId: string);
}
/**
 * The shared store cannot be written.
 *
 * This is a THROW AT WRITE TIME, never at construction, and that is the whole
 * point of it existing. Creating the directory eagerly meant an unwritable home —
 * a read-only or sandboxed HOME, an `A2A_STATE_DIR` whose parent does not permit
 * creation — killed the server during startup, which the client reports as a bare
 * "MCP error -32000: Connection closed" with stderr swallowed. The server now
 * comes up, every read answers empty, `a2a_auth_status` reports the directory as
 * unwritable, and only a tool that genuinely needs to write says so.
 */
export declare class StoreUnwritableError extends A2AApiError {
  readonly name = "StoreUnwritableError";
  constructor(dir: string, cause: unknown);
}
/** Thrown when a write path is reached while A2A_ALLOW_WRITES is off. */
export declare class WritesDisabledError extends Error {
  readonly name = "WritesDisabledError";
  constructor(what: string);
}
//#endregion
//#region src/client/shape.d.ts
type Rec = Record<string, unknown>;
/**
 * `TASK_STATE_INPUT_REQUIRED` → `input_required`. The short form is what the
 * tools take as an argument and what they return, so a model never has to know
 * the protobuf spelling — and `stateFromShort` is the only place the mapping
 * back lives.
 */
export declare const shortState: (state: TaskState) => string;
export declare const SHORT_STATES: readonly ["submitted", "working", "completed", "failed", "canceled", "input_required", "rejected", "auth_required"];
type ShortState = (typeof SHORT_STATES)[number];
export declare const stateFromShort: (short: ShortState) => TaskState;
/** Every text part of a message, joined. The half a model almost always wants. */
export declare const messageText: (message: Message | undefined) => string;
/**
 * One row of `a2a_list_tasks` / `a2a_wait_for_task`. Deliberately without the
 * history and the artifact bodies: a list of twenty of these has to be readable
 * in one screen, and the counts say exactly what to call `a2a_get_task` for.
 */
export declare const summarizeTask: (record: TaskRecord) => Rec;
/**
 * The full task, for `a2a_get_task`. History is bounded by an argument rather
 * than by a constant, and when it is trimmed the response says so — a caller who
 * does not know 40 turns were dropped will draw conclusions from the 5 they got.
 */
export declare const describeTask: (record: TaskRecord, opts: {
  historyLength: number;
}) => Rec;
/**
 * A peer's card, for choosing whether and what to delegate to it.
 *
 * `securitySchemes`, `securityRequirements` and `signatures` are dropped: they
 * are the longest part of a real card and none of them changes which agent to
 * ask. The transport list is kept because it is what says the peer is reachable
 * at all.
 */
export declare const summarizeCard: (card: AgentCard) => Rec;
/**
 * What arrives on a `claude/channel` push, and what `a2a_wait_for_task` returns.
 *
 * The wording is load-bearing. Channel content reaches the receiving agent as
 * UNTRUSTED DATA — measured: an agent read a channel event and correctly refused
 * to act on the instruction inside it — so the event has to read as a proposal
 * with a named next step, not as a request. Anything that sounds like an order
 * is both a prompt-injection surface and a thing the receiving agent will
 * rightly ignore.
 */
export declare const proposalFor: (record: TaskRecord) => Rec;
//#endregion
//#region src/store/peers.d.ts
type PeerRecord = {
  version: 1;
  /** Base URL the card was fetched from — the key a client is created against. */
  url: string;
  fetchedAt: string;
  /** The `AgentCard`, in its wire (JSON) form. */
  card: Record<string, unknown>;
};
/**
 * The discovered-peer cache: one file per peer base URL, holding the last agent
 * card we read from it.
 *
 * It is a cache and nothing more. A card can go stale — a peer restarts with new
 * skills — so `a2a_discover_agent` always refetches, and this only spares
 * `a2a_list_agents` from making one HTTP call per peer just to name them.
 */
export declare class PeerCache {
  private readonly dir;
  private readonly logger;
  constructor(opts: {
    stateDir: string;
    logger?: Logger;
  });
  put(url: string, card: AgentCard): PeerRecord;
  get(url: string): PeerRecord | undefined;
  all(): PeerRecord[];
  forget(url: string): boolean;
  private read;
}
//#endregion
//#region src/tools/index.d.ts
type ToolContext = {
  config: Config;
  store: FileTaskStore;
  peers: PeerClient;
  /** Register the mutating tools too. Off by default — see A2A_ALLOW_WRITES. */
  allowWrites: boolean;
  logger?: Logger;
};
/**
 * All the capability decisions, in one readable place, so "why can't I call X" is
 * answered by one file.
 *
 * Two things about this server's gating are deliberately unlike the rest of the
 * fleet, and both follow from what it is:
 *
 * 1. **There is no `hasCredentials` gate on the reads.** Elsewhere a server with
 *    no API key can do nothing but explain itself. Here every read tool works
 *    with nothing configured at all — the task store is a local directory and
 *    peer discovery is an unauthenticated GET — and gating them would hide
 *    exactly the tools that diagnose a broken setup. `a2a_auth_status` reports
 *    what is missing; it does not decide what exists.
 *
 * 2. **Answering an inbound task is a WRITE.** `a2a_respond_to_task` only touches
 *    a local file, so by the usual test it is not one. It is gated anyway,
 *    because what it really does is commit this agent to another agent's request,
 *    and that is the act the whole inbound design exists to keep deliberate.
 */
export declare const registerTools: (server: McpServer, ctx: ToolContext) => void;
//#endregion
export type { ChannelWatcher, Config, CreateServerOptions, CreatedServer, Direction, PeerClientOptions, PeerSummary, StoreChange, StoreSnapshot, TaskRecord, ToolContext };
//# sourceMappingURL=index.d.ts.map