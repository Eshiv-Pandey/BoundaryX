// Authored A2A 1.0 port of the official number-guessing Carol application.
// Original: a2aproject/a2a-samples@6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3
// See docs/research/source-evidence/reference-continuation/port/change-map.json.
// No model calls. Original bridge/SDK/source checkouts are not modified.
import { randomInt, randomUUID } from 'node:crypto';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const sdk = path.join(root, 'external', 'a2a-to-mcp', 'node_modules', '@a2a-js', 'sdk', 'dist');
const { Role, TaskState, AGENT_CARD_PATH, A2A_PROTOCOL_VERSION, A2A_VERSION_HEADER } = await import(pathToFileURL(path.join(sdk, 'index.js')));
const { AgentEvent, DefaultRequestHandler, InMemoryTaskStore, JsonRpcTransportHandler, UnauthenticatedUser, defaultServerCallContextBuilder, validateVersion } = await import(pathToFileURL(path.join(sdk, 'server', 'index.js')));
const { UnsupportedOperationError } = await import(pathToFileURL(path.join(sdk, 'errors', 'index.js')));

function textPart(text) {
  return { content: { $case: 'text', value: text }, mediaType: 'text/plain', filename: '', metadata: undefined };
}

function messageText(message) {
  return (message?.parts ?? []).filter(part => part.content?.$case === 'text').map(part => part.content.value).join('\n');
}

function parseJson(text) {
  try { return { success: true, value: JSON.parse(text) }; }
  catch { return { success: false, value: undefined }; }
}

function shuffleInPlace(items) {
  for (let i = items.length - 1; i > 0; i--) {
    const other = randomInt(i + 1);
    [items[i], items[other]] = [items[other], items[i]];
  }
}

function buildVisualisation(history) {
  if (!history.length) return 'No guesses yet.';
  const lines = ['Guesses so far:'];
  for (let i = 0; i < history.length; i++) {
    const entry = history[i];
    if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) throw new TypeError('History visualisation requires dictionary entries, as in the original application');
    const guess = Object.hasOwn(entry, 'guess') ? entry.guess : '?';
    const response = Object.hasOwn(entry, 'response') ? entry.response : '?';
    lines.push(` ${String(i + 1).padStart(2)}. ${String(guess).padStart(3)} -> ${String(response)}`);
  }
  return lines.join('\n');
}

function processHistoryPayload(rawText) {
  const parsed = parseJson(rawText);
  if (!parsed.success) return buildVisualisation([]);
  if (parsed.value && typeof parsed.value === 'object' && !Array.isArray(parsed.value) && parsed.value.action === 'shuffle') {
    const history = Array.isArray(parsed.value.history) ? parsed.value.history : [];
    shuffleInPlace(history);
    return JSON.stringify(history);
  }
  if (Array.isArray(parsed.value)) return buildVisualisation(parsed.value);
  return buildVisualisation([]);
}

export class CarolReferenceExecutor {
  // Deliberately global to the executor, matching original Carol._last_history.
  // It is not changed to a per-task map by this port.
  lastHistory = [];
  taskContexts = new Map();

  async execute(context, eventBus) {
    const taskId = context.taskId;
    const contextId = context.contextId;
    const rawText = messageText(context.userMessage);
    this.taskContexts.set(taskId, contextId);
    // The modern SDK requires the first published event to be task/message.
    eventBus.publish(AgentEvent.task(context.task ?? {
      id: taskId, contextId,
      status: { state: TaskState.TASK_STATE_SUBMITTED, message: undefined, timestamp: new Date().toISOString() },
      artifacts: [], history: [context.userMessage], metadata: undefined,
    }));

    // This is the original application-specific dispatch guard, unchanged.
    // Nonempty does not itself enforce equality/referential integrity.
    const isFollowup = Boolean(context.userMessage?.referenceTaskIds?.length);
    if (isFollowup) {
      if (rawText.toLowerCase().startsWith('well done')) {
        this.publishStatus(eventBus, taskId, contextId, TaskState.TASK_STATE_COMPLETED);
        return;
      }
      shuffleInPlace(this.lastHistory);
      this.publishArtifact(eventBus, taskId, contextId, JSON.stringify(this.lastHistory));
      this.publishStatus(eventBus, taskId, contextId, TaskState.TASK_STATE_INPUT_REQUIRED);
      return;
    }

    const responseText = rawText ? processHistoryPayload(rawText) : 'Invalid input.';
    // Parse again, preserving the original's distinct local/global lists:
    // process_history_payload shuffles its parse, _last_history keeps another.
    const parsed = parseJson(rawText);
    if (parsed.success && parsed.value && typeof parsed.value === 'object' && !Array.isArray(parsed.value) && parsed.value.action === 'shuffle') {
      const history = parsed.value.history ?? [];
      if (Array.isArray(history)) this.lastHistory = history;
    }
    this.publishArtifact(eventBus, taskId, contextId, responseText);
    this.publishStatus(eventBus, taskId, contextId, TaskState.TASK_STATE_INPUT_REQUIRED);
  }

  publishArtifact(eventBus, taskId, contextId, text) {
    eventBus.publish(AgentEvent.artifactUpdate({ taskId, contextId,
      artifact: { artifactId: randomUUID(), name: '', description: '', parts: [textPart(text)], metadata: undefined },
      append: false, lastChunk: true, metadata: undefined }));
  }

  publishStatus(eventBus, taskId, contextId, state) {
    eventBus.publish(AgentEvent.statusUpdate({ taskId, contextId,
      status: { state, message: undefined, timestamp: new Date().toISOString() }, metadata: undefined }));
  }

  async cancelTask(taskId, eventBus) {
    this.publishStatus(eventBus, taskId, this.taskContexts.get(taskId) ?? '', TaskState.TASK_STATE_CANCELED);
  }
}

function buildCard(baseUrl) {
  return {
    name: 'Carol reference-continuation port',
    description: 'Authored A2A 1.0 port of official no-model Carol; nonempty references dispatch follow-up. Development only.',
    supportedInterfaces: [{ url: `${baseUrl}/a2a`, protocolBinding: 'JSONRPC', tenant: '', protocolVersion: A2A_PROTOCOL_VERSION }],
    version: 'development-port-0',
    provider: { organization: 'Local research port of a2aproject/a2a-samples', url: 'https://github.com/a2aproject/a2a-samples/tree/6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3/samples/python/agents/number_guessing_game' },
    capabilities: { streaming: false, pushNotifications: false, extensions: [], extendedAgentCard: false },
    defaultInputModes: ['text/plain'], defaultOutputModes: ['text/plain'], securitySchemes: {}, securityRequirements: [], signatures: [],
    skills: [{ id: 'history_visualiser', name: 'Guess History Visualiser', description: 'Formats supplied guess/response history.', tags: ['visualisation', 'demo'], examples: ['[{"guess":25,"response":"Go higher"}]'], inputModes: ['text/plain'], outputModes: ['text/plain'], securityRequirements: [] },
      { id: 'history_shuffler', name: 'Guess History Shuffler', description: 'Shuffles supplied history and accepts task-referencing follow-ups.', tags: ['shuffling', 'demo'], examples: ['{"action":"shuffle","history":[{"guess":25,"response":"Go higher"}]}'], inputModes: ['text/plain'], outputModes: ['text/plain'], securityRequirements: [] }],
  };
}

export async function startCarolReferenceAgent({ port = 0 } = {}) {
  const card = buildCard('http://127.0.0.1:0');
  const executor = new CarolReferenceExecutor();
  const handler = new DefaultRequestHandler(card, new InMemoryTaskStore(), executor);
  const transport = new JsonRpcTransportHandler(handler);
  const writeJson = (response, status, object) => {
    response.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
    response.end(JSON.stringify(object));
  };
  const server = createServer((request, response) => {
    void (async () => {
      const pathname = new URL(request.url ?? '/', 'http://127.0.0.1').pathname;
      if (request.method === 'GET' && pathname === `/${AGENT_CARD_PATH}`) return writeJson(response, 200, await handler.getAgentCard());
      if (request.method !== 'POST' || pathname !== '/a2a') return writeJson(response, 404, { error: 'No declared route' });
      let raw = '';
      for await (const chunk of request) {
        raw += chunk.toString('utf8');
        if (Buffer.byteLength(raw) > 1024 * 1024) throw new Error('Body exceeds local development request limit');
      }
      let body;
      try { body = JSON.parse(raw); }
      catch { return writeJson(response, 400, { jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Invalid JSON payload' } }); }
      try {
        const context = defaultServerCallContextBuilder({ user: new UnauthenticatedUser(), headers: request.headers,
          requestedVersion: request.headers[A2A_VERSION_HEADER.toLowerCase()] ?? A2A_PROTOCOL_VERSION });
        validateVersion(context.requestedVersion, card, 'JSONRPC');
        if (body.method === 'SendStreamingMessage' || body.method === 'SubscribeToTask') throw new UnsupportedOperationError('Original Carol advertises no streaming');
        const result = await transport.handle(body, context);
        if (result?.[Symbol.asyncIterator]) throw new UnsupportedOperationError('No streaming operation is declared by this port');
        writeJson(response, 200, result);
      } catch (error) {
        writeJson(response, 200, { jsonrpc: '2.0', id: body.id ?? null, error: JsonRpcTransportHandler.mapToJSONRPCError(error) });
      }
    })().catch(error => writeJson(response, 500, { jsonrpc: '2.0', id: null, error: JsonRpcTransportHandler.mapToJSONRPCError(error) }));
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;
  card.supportedInterfaces[0].url = `${baseUrl}/a2a`;
  return { url: baseUrl, cardUrl: `${baseUrl}/${AGENT_CARD_PATH}`, executor, server,
    close: () => new Promise((resolve, reject) => { server.closeAllConnections(); server.close(error => error ? reject(error) : resolve()); }) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const index = process.argv.indexOf('--port');
  const port = index < 0 ? 0 : Number(process.argv[index + 1]);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('--port expects integer 0..65535');
  const agent = await startCarolReferenceAgent({ port });
  console.log(JSON.stringify({ role: 'authored-development-Carol-port', pid: process.pid, url: agent.url, card_url: agent.cardUrl, source_commit: '6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3', sdk: 'pinned AmirK-S @a2a-js/sdk 1.1.0', model_calls: 0 }));
  let closing = false;
  const close = () => { if (closing) return; closing = true; void agent.close().then(() => process.exit(0), error => { console.error(error); process.exit(1); }); };
  process.on('SIGINT', close); process.on('SIGTERM', close);
}
