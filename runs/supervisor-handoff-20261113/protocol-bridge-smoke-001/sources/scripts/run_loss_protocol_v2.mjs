// Actual loopback A2A SDK plus upstream MCP bridge development benchmark.
// The service/receiver/tasks are ours. Upstream bridge sources remain unchanged.
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const jsonBytes = value => Buffer.from(JSON.stringify(value));
const writeNew = (name, value) => { mkdirSync(path.dirname(name), { recursive: true }); writeFileSync(name, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' }); };
const args = process.argv.slice(2);
const argument = name => { const index = args.indexOf(name); return index < 0 ? undefined : args[index + 1]; };
const output = path.resolve(argument('--output') ?? 'runs/supervisor-handoff-20261113/protocol-001');
const bankPath = path.resolve(argument('--bank') ?? 'runs/supervisor-handoff-20261113/diagnostics-smoke-001/input-bank.json');
const routeFilter = (argument('--routes') ?? 'native,amirk_typed,mgcrea_typed,mgcrea_raw').split(',');
const profiles = (argument('--profiles') ?? 'reference,placebo_identity,dropped_fact,capability_mismatch,wrong_task,constraint_loss,safe_equivalent,recovery,extraction_loss,compound_records_binding,compound_identity_constraints,compound_all').split(',');
const maxCases = Number(argument('--max-cases') ?? '0');
const allowedRoutes = ['native', 'amirk_typed', 'mgcrea_typed', 'mgcrea_raw'];
const allowedProfiles = ['reference', 'placebo_identity', 'dropped_fact', 'capability_mismatch', 'wrong_task', 'constraint_loss', 'safe_equivalent', 'recovery', 'extraction_loss', 'compound_records_binding', 'compound_identity_constraints', 'compound_all'];
assert(routeFilter.length && new Set(routeFilter).size === routeFilter.length && routeFilter.every(x => allowedRoutes.includes(x)));
assert(profiles.length && new Set(profiles).size === profiles.length && profiles.every(x => allowedProfiles.includes(x)));
assert(!existsSync(output), 'Evidence output already exists');
const bank = JSON.parse(readFileSync(bankPath));
assert.equal(bank.schema_version, 'loss_diagnostic_bank_v2');
const cases = maxCases ? bank.cases.slice(0, maxCases) : bank.cases;
const amir = path.join(root, 'external/a2a-to-mcp');
const mgcrea = path.join(root, 'external/mcp-a2a');
const sdkRequire = createRequire(path.join(amir, 'package.json'));
const sdk = await import(pathToFileURL(sdkRequire.resolve('@a2a-js/sdk')).href);
const serverSdk = await import(pathToFileURL(sdkRequire.resolve('@a2a-js/sdk/server')).href);
const { Role, TaskState, A2A_PROTOCOL_VERSION } = sdk;
const { AgentEvent, DefaultRequestHandler, InMemoryTaskStore, JsonRpcTransportHandler, defaultServerCallContextBuilder, UnauthenticatedUser } = serverSdk;
const sourcePaths = ['scripts/run_loss_protocol_v2.mjs', 'scripts/loss_protocol_receiver_v2.py', 'scripts/run_loss_benchmark_v1.py', 'scripts/run_loss_diagnostics_v2.py', 'benchmark/loss-v1/development-cases.json'];
const upstreamPaths = [
  'external/a2a-to-mcp/package-lock.json', 'external/a2a-to-mcp/dist/server.js', 'external/a2a-to-mcp/dist/tools.js',
  'external/mcp-a2a/package.json', 'external/mcp-a2a/dist/index.js', 'external/mcp-a2a/dist/server-Dd272e4l.js',
];
const sources = [...sourcePaths, ...upstreamPaths].map(name => ({ path: name, bytes: readFileSync(path.join(root, name)).length, sha256: hash(readFileSync(path.join(root, name))) }));
const sdkPackage = JSON.parse(readFileSync(path.join(amir, 'node_modules/@a2a-js/sdk/package.json')));
mkdirSync(output, { recursive: true });
writeNew(path.join(output, 'input-bank.json'), bank);
for (const source of sources) { const dest = path.join(output, 'sources', source.path); mkdirSync(path.dirname(dest), { recursive: true }); writeFileSync(dest, readFileSync(path.join(root, source.path)), { flag: 'wx' }); }
const allocation = { schema_version: 'loss_protocol_allocation_v2', started_utc: new Date().toISOString(), evidence_kind: 'fresh_protocol_development',
  notice: 'Real loopback protocol execution through installed SDK/bridges; authored deterministic Python receiver and controlled faults. No LLM or original application task, no held-out qualification.',
  bank_sha256: hash(readFileSync(bankPath)), case_instances: cases.length, profiles, routes: routeFilter,
  cells: cases.flatMap(c => profiles.flatMap(profile => routeFilter.map(route => ({ case_id: c.case_id, profile, route })))),
  sources, node: process.version, a2a_sdk: sdkPackage.version, python_executable: argument('--python') ?? 'python',
  cost_boundary: 'Episode communication includes initial send, final public reads, recovery continuation and owned upstream wire requests. Setup and diagnostic read probes are excluded and recorded separately. No cost pooling across routes.' };
writeNew(path.join(output, 'allocation.json'), allocation);

let currentLog = null;
const serviceEvents = [];
const referenceByTask = new Map();
const readonlyPolicy = { mode: 'read_only', allowed_tools: ['fixture.read_snapshot.v1'], forbidden_effects: ['restart_service', 'acknowledge_incident', 'write_snapshot'] };
const copy = value => structuredClone(value);
const canonical = value => JSON.stringify(normalize(value));
function normalize(value) {
  if (Array.isArray(value)) return value.map(normalize);
  if (value !== null && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, normalize(value[key])]));
  return value;
}
const textPart = text => ({ content: { $case: 'text', value: text }, mediaType: 'text/plain', filename: '' });
const observe = (role, request, response, extra = {}) => {
  const entry = { sequence: currentLog ? currentLog.length : serviceEvents.length, role, utc: new Date().toISOString(),
    request: request === null ? null : { raw: request.toString('utf8'), bytes: request.length, sha256: hash(request) },
    response: response === null ? null : { raw: response.toString('utf8'), bytes: response.length, sha256: hash(response) }, ...extra };
  (currentLog ?? serviceEvents).push(entry);
  return entry;
};

class ReceiverExecutor {
  async execute(context, bus) {
    const { taskId, contextId, userMessage } = context;
    const input = JSON.parse(userMessage.parts[0].content.value);
    let result;
    if (input.operation === 'probe_read' || input.operation === 'recover_read') {
      const source = referenceByTask.get(input.task_id);
      const usable = !!source && input.tool_binding === 'fixture.read_snapshot.v1';
      if (input.operation === 'probe_read') result = { status: usable ? 'read_usable' : 'read_refused', usable,
        task_id: input.task_id, tool_binding: input.tool_binding, records: usable ? copy(source.records) : null };
      else {
        if (!usable || !context.task) result = { status: 'recovery_refused', task_id: input.task_id, target: null, answer: null };
        else { const restored = copy(input.observation); restored.records = copy(source.records); result = this.receive(restored); }
      }
    } else {
      result = this.receive(input.observation);
    }
    const task = context.task ?? { id: taskId, contextId, status: { state: TaskState.TASK_STATE_SUBMITTED, timestamp: new Date().toISOString() }, history: [userMessage], artifacts: [] };
    bus.publish(AgentEvent.task(task));
    bus.publish(AgentEvent.artifactUpdate({ taskId, contextId, artifact: { artifactId: randomUUID(), name: 'receiver-result', description: '', parts: [textPart(JSON.stringify(result))], extensions: [] }, append: false, lastChunk: true }));
    // Missing input is a live continuation, not a completed task acknowledgement.
    const state = result.status === 'missing_fact' ? TaskState.TASK_STATE_INPUT_REQUIRED : TaskState.TASK_STATE_COMPLETED;
    bus.publish(AgentEvent.statusUpdate({ taskId, contextId, status: { state, timestamp: new Date().toISOString(), message: { messageId: randomUUID(), taskId, contextId, role: Role.ROLE_AGENT, parts: [textPart(result.status)], extensions: [], referenceTaskIds: [] } } }));
  }
  receive(observation) {
    const run = spawnSync(allocation.python_executable, ['-B', path.join(root, 'scripts/loss_protocol_receiver_v2.py')], { input: JSON.stringify(observation), encoding: 'utf8', windowsHide: true, timeout: 10000, maxBuffer: 2 * 1024 * 1024 });
    if (run.status !== 0) throw new Error(`Python receiver failed: ${run.stderr ?? run.error}`);
    return JSON.parse(run.stdout);
  }
  async cancelTask(taskId, bus) { bus.publish(AgentEvent.statusUpdate({ taskId, contextId: '', status: { state: TaskState.TASK_STATE_CANCELED } })); }
}

const card = { name: 'Interoperability benchmark controlled receiver', description: allocation.notice,
  supportedInterfaces: [{ url: 'http://127.0.0.1:0/a2a', protocolBinding: 'JSONRPC', protocolVersion: A2A_PROTOCOL_VERSION, tenant: '' }],
  version: '2.0.0', capabilities: { streaming: false, pushNotifications: false }, defaultInputModes: ['text/plain'], defaultOutputModes: ['text/plain'],
  skills: [{ id: 'finite-readonly-task', name: 'Finite read-only task', description: 'Execute provided JSON observation; optional task-bound snapshot reread', tags: ['development'], examples: [], inputModes: ['text/plain'], outputModes: ['text/plain'], securityRequirements: [] }] };
const handler = new DefaultRequestHandler(card, new InMemoryTaskStore(), new ReceiverExecutor());
const transport = new JsonRpcTransportHandler(handler);
const http = createServer(async (req, res) => {
  try {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const requestBytes = Buffer.concat(chunks);
    let response;
    if (req.method === 'GET' && req.url === '/.well-known/agent-card.json') response = card;
    else if (req.method === 'POST' && req.url === '/a2a') {
      const context = defaultServerCallContextBuilder({ user: new UnauthenticatedUser(), headers: req.headers, requestedVersion: req.headers['a2a-version'] ?? A2A_PROTOCOL_VERSION });
      response = await transport.handle(JSON.parse(requestBytes), context);
      if (response?.[Symbol.asyncIterator]) throw new Error('This nonstreaming allocation forbids an SSE result');
    } else { res.statusCode = 404; response = { error: 'route absent' }; }
    const raw = jsonBytes(response);
    observe('native_service_wire', requestBytes, raw, { method: req.method, path: req.url, status: res.statusCode, headers: { 'a2a-version': req.headers['a2a-version'] ?? null } });
    res.setHeader('content-type', 'application/json'); res.end(raw);
  } catch (error) {
    const raw = jsonBytes({ error: String(error.stack ?? error) });
    observe('native_service_error', null, raw); res.statusCode = 500; res.end(raw);
  }
});
await new Promise((resolve, reject) => { http.once('error', reject); http.listen(0, '127.0.0.1', resolve); });
const nativeUrl = `http://127.0.0.1:${http.address().port}`;
card.supportedInterfaces[0].url = nativeUrl + '/a2a';
const nativeRpc = async (method, params) => {
  const packet = { jsonrpc: '2.0', id: randomUUID(), method, params };
  const request = jsonBytes(packet);
  const response = await fetch(nativeUrl + '/a2a', { method: 'POST', headers: { 'content-type': 'application/json', 'A2A-Version': '1.0' }, body: request, signal: AbortSignal.timeout(15000) });
  const raw = Buffer.from(await response.arrayBuffer());
  observe('native_client_wire', request, raw, { method, status: response.status });
  assert.equal(response.status, 200);
  const value = JSON.parse(raw); assert(!value.error, JSON.stringify(value)); return value.result.task ?? value.result;
};
const userMessage = (payload, receipt) => ({ messageId: randomUUID(), role: 'ROLE_USER', parts: [{ text: JSON.stringify(payload) }], ...(receipt ? { taskId: receipt.id, contextId: receipt.contextId } : {}) });

let amirBridge, mgServer, mgClient;
const routes = {};
routes.native = { async send(payload, receipt) { return nativeRpc('SendMessage', { message: userMessage(payload, receipt) }); },
  async get(receipt) { return nativeRpc('GetTask', { id: receipt.id, historyLength: 0 }); },
  receipt(task) { assert(task.id && task.contextId); return { id: task.id, contextId: task.contextId }; },
  decode(task) { return task.artifacts?.at(-1)?.parts?.[0]?.text; } };

if (routeFilter.includes('amirk_typed')) {
  const { createBridge } = await import(pathToFileURL(path.join(amir, 'dist/server.js')).href);
  amirBridge = await createBridge({ agents: { receiver: { cardUrl: nativeUrl + '/.well-known/agent-card.json' } } });
  const address = await amirBridge.listen(0, '127.0.0.1');
  const mcpUrl = address.url ?? `http://127.0.0.1:${address.port}/mcp`;
  const rpc = async (method, params, notification = false) => {
    const packet = { jsonrpc: '2.0', ...(notification ? {} : { id: randomUUID() }), method, params };
    const request = jsonBytes(packet);
    const response = await fetch(mcpUrl.endsWith('/mcp') ? mcpUrl : mcpUrl + '/mcp', { method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream', 'mcp-protocol-version': '2025-11-25' }, body: request, signal: AbortSignal.timeout(15000) });
    const raw = Buffer.from(await response.arrayBuffer());
    observe('mcp_client_wire', request, raw, { method, status: response.status });
    if (notification) return null;
    let value;
    try { value = JSON.parse(raw); } catch { const event = raw.toString('utf8').split('\n').find(line => line.startsWith('data:')); value = JSON.parse(event.slice(5)); }
    assert(!value.error, JSON.stringify(value)); return value.result;
  };
  const init = await rpc('initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'supervisor-benchmark-v2', version: '2.0.0' } });
  assert.equal(init.protocolVersion, '2025-11-25');
  await rpc('notifications/initialized', {}, true);
  const tools = await rpc('tools/list', {});
  writeNew(path.join(output, 'amirk-discovery.json'), tools);
  const tool = async (name, arguments_) => { const value = await rpc('tools/call', { name, arguments: arguments_ }); assert(!value.isError, JSON.stringify(value)); return value; };
  routes.amirk_typed = {
    async send(payload, receipt) { return tool('a2a_send_message', { agent: 'receiver', text: JSON.stringify(payload), ...(receipt ? { taskHandle: receipt.task_handle, contextHandle: receipt.context_handle } : {}) }); },
    async get(receipt) { return tool('a2a_get_task', { agent: 'receiver', taskHandle: receipt.task_handle, historyLength: 0 }); },
    receipt(task) { const meta = task.structuredContent; assert(meta?.taskHandle, JSON.stringify(task)); return { task_handle: meta.taskHandle, context_handle: meta.contextHandle, id: meta.taskHandle, contextId: meta.contextHandle }; },
    decode(task) { return task.content?.filter(x => x.type === 'text').map(x => x.text).find(x => x.startsWith('{') && x.includes('task_id')); },
  };
}

if (routeFilter.some(r => r.startsWith('mgcrea'))) {
  const req = createRequire(path.join(mgcrea, 'package.json'));
  const { createServer: createMcpServer } = await import(pathToFileURL(path.join(mgcrea, 'dist/index.js')).href);
  const { Client } = await import(pathToFileURL(req.resolve('@modelcontextprotocol/client')).href);
  const config = { daemonUrl: nativeUrl, agentName: 'benchmark', agentDescription: 'controlled', peers: [nativeUrl], stateDir: path.join(output, 'mgcrea-state'), allowWrites: true, maxWaitSeconds: 10, channel: false, pollIntervalMs: 100, maxRetries: 0 };
  mgServer = createMcpServer({ config, watchChannel: false }).server;
  class LinkedTransport {
    async start() {}
    async send(packet) { const other = this.peer; queueMicrotask(() => other.onmessage?.(copy(packet))); }
    async close() { this.onclose?.(); }
  }
  const clientTransport = new LinkedTransport(), serverTransport = new LinkedTransport();
  clientTransport.peer = serverTransport; serverTransport.peer = clientTransport;
  // Actual MCP SDK framed messages, logged at both sides of the linked transport.
  for (const [transport_, role] of [[clientTransport, 'mcp_client_message'], [serverTransport, 'mcp_server_message']]) {
    const original = transport_.send.bind(transport_);
    transport_.send = async (packet, ...rest) => { observe(role, role === 'mcp_client_message' ? jsonBytes(packet) : null, role === 'mcp_server_message' ? jsonBytes(packet) : null); return original(packet, ...rest); };
  }
  mgClient = new Client({ name: 'supervisor-benchmark-v2', version: '2.0.0' }, { capabilities: {} });
  await mgServer.connect(serverTransport); await mgClient.connect(clientTransport);
  writeNew(path.join(output, 'mgcrea-discovery.json'), await mgClient.listTools());
  const tool = async (name, arguments_) => { const body = await mgClient.callTool({ name, arguments: arguments_ }, undefined, { timeout: 15000 }); assert(!body.isError, JSON.stringify(body)); return body.structuredContent ?? JSON.parse(body.content[0].text); };
  routes.mgcrea_typed = {
    async send(payload, receipt) { return tool('a2a_send_message', { url: nativeUrl, text: JSON.stringify(payload), ...(receipt ? { task_id: receipt.id, context_id: receipt.contextId } : {}) }); },
    async get(receipt) { return tool('a2a_get_task', { task_id: receipt.id, refresh: true, history_length: 0 }); },
    receipt(task) { assert(task.task?.id && task.task?.context_id, JSON.stringify(task)); return { id: task.task.id, contextId: task.task.context_id }; },
    decode(task) { return task.artifacts?.at(-1)?.text; },
  };
  routes.mgcrea_raw = {
    async send(payload, receipt) { const value = await tool('a2a_request', { url: nativeUrl, method: 'SendMessage', params: { message: userMessage(payload, receipt) } }); assert(!value.error, JSON.stringify(value)); return value.result.task ?? value.result; },
    async get(receipt) { const value = await tool('a2a_request', { url: nativeUrl, method: 'GetTask', params: { id: receipt.id, historyLength: 0 } }); assert(!value.error, JSON.stringify(value)); return value.result.task ?? value.result; },
    receipt: routes.native.receipt, decode: routes.native.decode,
  };
}

const sourceObservation = c => ({ task: copy(c.task), records: copy(c.records), tool_binding: 'fixture.read_snapshot.v1', runtime_policy: copy(readonlyPolicy), episode_budget: copy(bank.episode_budget) });
function converted(c, profile) {
  const source = sourceObservation(c), sent = copy(source);
  if (profile === 'extraction_loss') delete sent.records;
  const received = copy(sent);
  if (['dropped_fact', 'recovery', 'compound_records_binding', 'compound_all'].includes(profile)) delete received.records;
  if (['capability_mismatch', 'compound_records_binding', 'compound_all'].includes(profile)) received.tool_binding = 'fixture.restart_service.v1';
  if (['wrong_task', 'compound_identity_constraints', 'compound_all'].includes(profile)) { received.task.task_id = 'decoy-' + received.task.task_id; received.task.target = 'decoy/' + received.task.target; }
  if (['constraint_loss', 'compound_identity_constraints', 'compound_all'].includes(profile)) received.task.constraints = {};
  if (profile === 'safe_equivalent') received.records.reverse();
  if (profile === 'placebo_identity') received.annotation = 'Placebo envelope decoration; task payload unchanged.';
  return { source, sent, received };
}
const results = [];
let failures = 0;
try {
  for (const c of cases) {
    referenceByTask.set(c.task.task_id, sourceObservation(c));
    for (const profile of profiles) for (const routeName of routeFilter) {
      const route = routes[routeName], observation = converted(c, profile);
      const episodeId = `${c.case_id}--${profile}--${routeName}`;
      currentLog = [];
      const began = performance.now();
      const cell = { schema_version: 'loss_protocol_cell_v2', episode_id: episodeId, case_id: c.case_id, family_id: c.family_id, route: routeName, profile,
        observation, task_completion: 'unknown', service_result: null, initial_public_result: null, final_public_result: null, receipt: null, recovery: { eligible: profile === 'recovery', status: 'not_applicable' },
        evidence_scope: routeName.startsWith('mgcrea') ? 'actual MCP SDK in-memory transport and real A2A HTTP; authored receiver' : routeName === 'native' ? 'real A2A HTTP through installed SDK; authored receiver' : 'real MCP HTTP and A2A HTTP through unmodified upstream bridge; authored receiver' };
      try {
        const initial = await route.send({ operation: 'evaluate', observation: observation.received });
        cell.initial_public_result = initial;
        const receipt = route.receipt(initial); cell.receipt = receipt;
        let final = await route.get(receipt);
        let decoded = route.decode(final);
        assert(decoded, `No public receiver result: ${JSON.stringify(final)}`);
        const first = JSON.parse(decoded); cell.initial_service_result = first;
        if (profile === 'recovery') {
          if (first.status === 'missing_fact') {
            const resumed = await route.send({ operation: 'recover_read', observation: observation.received, task_id: observation.received.task.task_id, tool_binding: observation.received.tool_binding }, receipt);
            cell.recovery_acknowledgement = resumed;
            const newReceipt = route.receipt(resumed);
            assert.equal(newReceipt.id, receipt.id, 'Recovery changed the publicly returned task');
            final = await route.get(receipt); decoded = route.decode(final);
          }
          cell.recovery.status = 'fail';
        }
        cell.final_public_result = final;
        cell.service_result = JSON.parse(decoded);
        const result = cell.service_result;
        cell.grade_checks = { answer: result.status === 'completed' && JSON.stringify(result.answer) === JSON.stringify(c.gold.expected_answer),
          original_task: result.task_id === c.gold.expected_task_id, original_target: result.target === c.gold.expected_target,
          public_final_read: true, original_public_receipt: true };
        // Compare objects canonically in Python during independent regrading.
        cell.grade_checks.answer = result.status === 'completed' && canonical(result.answer) === canonical(c.gold.expected_answer);
        cell.task_completion = Object.values(cell.grade_checks).every(Boolean) ? 'pass' : 'fail';
        if (profile === 'recovery') cell.recovery.status = cell.task_completion;
      } catch (error) {
        cell.execution_error = error.stack ?? String(error); failures++;
      }
      const episodeWire = currentLog; cell.wall_ms = performance.now() - began; currentLog = [];
      // Actual task-bound snapshot read probes are isolated from episode costs.
      const probes = [];
      for (const [label, wire] of [['reference', observation.source], ['receiver', observation.received]]) {
        try { const probe = await route.send({ operation: 'probe_read', task_id: wire.task.task_id, tool_binding: wire.tool_binding });
          const receipt = route.receipt(probe), final = await route.get(receipt), decoded = JSON.parse(route.decode(final));
          probes.push({ label, request: { task_id: wire.task.task_id, tool_binding: wire.tool_binding }, receipt, final, decoded });
        } catch (error) { probes.push({ label, error: String(error.stack ?? error) }); }
      }
      cell.capability_probes = probes; cell.probe_wire = currentLog; cell.episode_wire = episodeWire;
      currentLog = null;
      writeNew(path.join(output, 'cells', episodeId + '.json'), cell); results.push(cell);
      if (results.length % 24 === 0) console.log(JSON.stringify({ progress: results.length, allocated: allocation.cells.length, protocol_errors: failures }));
    }
  }
} finally {
  currentLog = null;
  await mgClient?.close(); await mgServer?.close(); await amirBridge?.close();
  http.closeAllConnections(); await new Promise(resolve => http.close(resolve));
  writeNew(path.join(output, 'setup-wire.json'), serviceEvents);
}
const changedSources = sources.filter(source => hash(readFileSync(path.join(root, source.path))) !== source.sha256);
const summary = { schema_version: 'loss_protocol_result_v2', status: failures || changedSources.length ? 'complete_with_errors' : 'complete',
  attempted_cells: results.length, allocated_cells: allocation.cells.length, protocol_errors: failures,
  model_calls: 0, sources_changed: changedSources, service_closed: !http.listening, completed_utc: new Date().toISOString(),
  by_route: Object.fromEntries(routeFilter.map(route => [route, Object.fromEntries(profiles.map(profile => {
    const group = results.filter(c => c.route === route && c.profile === profile);
    return [profile, { attempts: group.length, pass: group.filter(c => c.task_completion === 'pass').length, fail: group.filter(c => c.task_completion === 'fail').length, unknown: group.filter(c => c.task_completion === 'unknown').length }];
  }))])), notice: allocation.notice };
writeNew(path.join(output, 'results.json'), summary);
const allFiles = directory => readdirSync(directory, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? allFiles(path.join(directory, entry.name)) : [path.join(directory, entry.name)]);
writeNew(path.join(output, 'manifest.json'), { files: allFiles(output).sort().map(name => ({ path: path.relative(output, name).replaceAll('\\', '/'), bytes: statSync(name).size, sha256: hash(readFileSync(name)) })) });
console.log(JSON.stringify(summary));
if (failures || changedSources.length) process.exitCode = 1;
