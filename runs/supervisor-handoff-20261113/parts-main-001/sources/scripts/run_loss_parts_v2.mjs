// Fresh representation-survival experiment using the unchanged upstream fixture.
// The recorder rewrites only discovery endpoint URLs to its loopback proxy.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const arg = name => args[args.indexOf(name) + 1];
const output = path.resolve(args.includes('--output') ? arg('--output') : 'runs/supervisor-handoff-20261113/parts-001');
const repetitions = Number(args.includes('--repetitions') ? arg('--repetitions') : '3');
assert(Number.isInteger(repetitions) && repetitions >= 1 && repetitions <= 10);
assert(!existsSync(output), 'Existing evidence output refused');
mkdirSync(output, { recursive: true });
const amir = path.join(root, 'external/a2a-to-mcp'), mg = path.join(root, 'external/mcp-a2a');
const hash = value => createHash('sha256').update(value).digest('hex');
const write = (name, value) => { mkdirSync(path.dirname(name), { recursive: true }); writeFileSync(name, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' }); };
const normalize = value => Array.isArray(value) ? value.map(normalize) : value !== null && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, normalize(value[key])])) : value;
const same = (a, b) => JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
const specifications = [
  { id: 'text', command: 'task: benchmark-survival', expected: { text: 'lavivrus-kramhcneb', mediaType: 'text/plain' }, payload_key: 'text', requirement: 'Exact text artifact; text utility is separate from full metadata fidelity' },
  { id: 'data', command: 'data: benchmark-survival', expected: { data: { answer: 42, echo: 'benchmark-survival' }, mediaType: 'application/json' }, payload_key: 'data', requirement: 'Structured data answer and echo' },
  { id: 'file', command: 'file', expected: { url: 'https://example.invalid/files/report.pdf', filename: 'report.pdf', mediaType: 'application/pdf' }, payload_key: 'url', requirement: 'File URI, name and media type; file bytes are not fetched' },
  { id: 'image', command: 'image', expected: { raw: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', filename: 'pixel.png', mediaType: 'image/png' }, payload_key: 'raw', requirement: 'Exact inline PNG bytes, name and media type' },
];
const routesList = ['native', 'amirk_typed', 'mgcrea_typed', 'mgcrea_raw'];
const sourceNames = ['scripts/run_loss_parts_v2.mjs', 'external/a2a-to-mcp/package-lock.json',
  'external/a2a-to-mcp/fixtures/agent/cli.ts', 'external/a2a-to-mcp/fixtures/agent/index.ts',
  'external/a2a-to-mcp/fixtures/agent/executor.ts', 'external/a2a-to-mcp/fixtures/agent/card.ts',
  'external/a2a-to-mcp/fixtures/agent/http.ts', 'external/a2a-to-mcp/fixtures/agent/commands.ts',
  'external/a2a-to-mcp/dist/server.js', 'external/a2a-to-mcp/dist/tools.js', 'external/a2a-to-mcp/dist/parts.js',
  'external/mcp-a2a/dist/cli.js', 'external/mcp-a2a/dist/server-Dd272e4l.js', 'external/mcp-a2a/package.json'];
const sources = sourceNames.map(name => ({ path: name, bytes: readFileSync(path.join(root, name)).length, sha256: hash(readFileSync(path.join(root, name))) }));
for (const source of sources) { const dest = path.join(output, 'sources', source.path); mkdirSync(path.dirname(dest), { recursive: true }); writeFileSync(dest, readFileSync(path.join(root, source.path)), { flag: 'wx' }); }
const allocation = { schema_version: 'loss_parts_allocation_v2', started_utc: new Date().toISOString(), repetitions, specifications, routes: routesList,
  cells: specifications.flatMap(spec => Array.from({ length: repetitions }, (_, repetition) => routesList.map(route => ({ case_id: spec.id, repetition, route }))).flat()), sources,
  scope: 'Unchanged deterministic upstream fixture over real A2A/MCP. Prespecified artifact survival, not LLM tasks or a population prevalence estimate. Each repetition is a new task, not an independent application family.',
  recovery_policy: 'Adaptive development selected after parts-smoke-001: if a mgcrea typed authoritative read fails the declared required representation, call public raw GetTask once on the same returned task/context. Raw GetTask eligibility is fixed before this allocation; no repeat SendMessage, new task or repaired upstream source.',
  recorder_intervention: 'Own proxy forwards all RPC bytes unchanged and rewrites supportedInterfaces URLs only in agent-card discovery. No model, business operation, remote URL fetch or source repair.' };
write(path.join(output, 'allocation.json'), allocation);
let fixture, proxy, bridge, client, stdio;
let fixtureOut = '', fixtureErr = '', bridgeErr = '', current = null;
const setup = [], records = [];
const record = (role, request, response, extra = {}) => (current ?? setup).push({ role, ...extra, utc: new Date().toISOString(),
  request: request == null ? null : { raw: request.toString('utf8'), bytes: request.length, sha256: hash(request) },
  response: response == null ? null : { raw: response.toString('utf8'), bytes: response.length, sha256: hash(response) } });
const nativeRpc = async (url, method, params) => {
  const request = Buffer.from(JSON.stringify({ jsonrpc: '2.0', id: randomUUID(), method, params }));
  const response = await fetch(url + '/a2a', { method: 'POST', headers: { 'content-type': 'application/json', 'A2A-Version': '1.0' }, body: request, signal: AbortSignal.timeout(10000) });
  const raw = Buffer.from(await response.arrayBuffer()); record('native_client', request, raw, { method, status: response.status });
  assert.equal(response.status, 200); const body = JSON.parse(raw); assert(!body.error, JSON.stringify(body)); return body.result.task ?? body.result;
};
const message = command => ({ role: 'ROLE_USER', messageId: randomUUID(), parts: [{ text: command }] });

try {
  fixture = spawn(process.execPath, ['--import', 'tsx', 'fixtures/agent/cli.ts', '--port', '0'], { cwd: amir, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  fixture.stdout.on('data', chunk => { fixtureOut += chunk.toString(); }); fixture.stderr.on('data', chunk => { fixtureErr += chunk.toString(); });
  const fixtureUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('upstream fixture startup deadline')), 10000);
    fixture.once('error', reject); fixture.once('exit', code => reject(new Error('fixture exited ' + code)));
    fixture.stdout.on('data', () => { const match = fixtureOut.match(/listening on (http:\/\/\S+)/); if (match) { clearTimeout(timer); resolve(match[1]); } });
  });
  let proxyUrl;
  proxy = createServer(async (req, res) => {
    try {
      const chunks = []; for await (const chunk of req) chunks.push(chunk);
      const request = Buffer.concat(chunks);
      const response = await fetch(fixtureUrl + req.url, { method: req.method, headers: { 'content-type': 'application/json', 'A2A-Version': '1.0' }, ...(request.length ? { body: request } : {}), signal: AbortSignal.timeout(10000) });
      const upstreamBytes = Buffer.from(await response.arrayBuffer());
      let outgoing = upstreamBytes;
      if (req.url === '/.well-known/agent-card.json') {
        const card = JSON.parse(upstreamBytes); for (const iface of card.supportedInterfaces) iface.url = proxyUrl + new URL(iface.url).pathname;
        outgoing = Buffer.from(JSON.stringify(card));
      }
      record('recorder_proxy', request, outgoing, { method: req.method, path: req.url, status: response.status, upstream_response_sha256: hash(upstreamBytes), rpc_response_bytes_unchanged: req.url === '/a2a' ? outgoing.equals(upstreamBytes) : null });
      res.statusCode = response.status; res.setHeader('content-type', response.headers.get('content-type') ?? 'application/json'); res.end(outgoing);
    } catch (error) { record('recorder_error', null, Buffer.from(String(error.stack ?? error))); res.statusCode = 500; res.end(String(error)); }
  });
  await new Promise(resolve => proxy.listen(0, '127.0.0.1', resolve)); proxyUrl = `http://127.0.0.1:${proxy.address().port}`;
  const routes = { native: {
    send: command => nativeRpc(proxyUrl, 'SendMessage', { message: message(command) }),
    get: receipt => nativeRpc(proxyUrl, 'GetTask', { id: receipt.id, historyLength: 0 }),
    receipt: result => ({ id: result.id, contextId: result.contextId }),
  } };
  const { createBridge } = await import(pathToFileURL(path.join(amir, 'dist/server.js')).href);
  bridge = await createBridge({ agents: { fixture: { cardUrl: proxyUrl + '/.well-known/agent-card.json' } } });
  const address = await bridge.listen(0, '127.0.0.1');
  const mcpRpc = async (method, params, notification = false) => {
    const request = Buffer.from(JSON.stringify({ jsonrpc: '2.0', ...(notification ? {} : { id: randomUUID() }), method, params }));
    const response = await fetch(address.url, { method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream', 'mcp-protocol-version': '2025-11-25' }, body: request, signal: AbortSignal.timeout(10000) });
    const raw = Buffer.from(await response.arrayBuffer()); record('mcp_http', request, raw, { method, status: response.status });
    if (notification) return null;
    let body; try { body = JSON.parse(raw); } catch { body = JSON.parse(raw.toString().split('\n').find(line => line.startsWith('data:')).slice(5)); }
    assert(!body.error, JSON.stringify(body)); return body.result;
  };
  await mcpRpc('initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'part-survival-benchmark', version: '2' } });
  await mcpRpc('notifications/initialized', {}, true); write(path.join(output, 'amir-discovery.json'), await mcpRpc('tools/list', {}));
  const amTool = async (name, arguments_) => { const value = await mcpRpc('tools/call', { name, arguments: arguments_ }); assert(!value.isError, JSON.stringify(value)); return value; };
  routes.amirk_typed = { send: command => amTool('a2a_send_message', { agent: 'fixture', text: command }),
    get: receipt => amTool('a2a_get_task', { agent: 'fixture', taskHandle: receipt.id, historyLength: 0 }),
    receipt: value => ({ id: value.structuredContent.taskHandle, contextId: value.structuredContent.contextHandle }) };
  const req = createRequire(path.join(mg, 'package.json'));
  const { Client } = await import(pathToFileURL(req.resolve('@modelcontextprotocol/client')).href);
  const { StdioClientTransport } = await import(pathToFileURL(req.resolve('@modelcontextprotocol/client/stdio')).href);
  const configPath = path.join(output, 'mgcrea-config.json');
  write(configPath, { daemonUrl: proxyUrl, peers: [proxyUrl], stateDir: path.join(output, 'mgcrea-state'), allowWrites: true, channel: false, maxRetries: 0 });
  stdio = new StdioClientTransport({ command: process.execPath, args: [path.join(mg, 'dist/cli.js')], cwd: mg,
    env: { ...process.env, A2A_CONFIG: configPath, A2A_TOKEN: '', A2A_ALLOW_WRITES: '1', A2A_CHANNEL: '0', A2A_MAX_RETRIES: '0', A2A_STATE_DIR: path.join(output, 'mgcrea-state') }, stderr: 'pipe' });
  const originalSend = stdio.send.bind(stdio);
  stdio.send = async (packet, ...rest) => { record('mcp_stdio_request', Buffer.from(JSON.stringify(packet)), null); return originalSend(packet, ...rest); };
  client = new Client({ name: 'part-survival-benchmark', version: '2' }); await client.connect(stdio);
  const originalReceive = stdio.onmessage;
  stdio.onmessage = (packet, ...rest) => { record('mcp_stdio_response', null, Buffer.from(JSON.stringify(packet))); originalReceive(packet, ...rest); };
  stdio.stderr?.on('data', chunk => { bridgeErr += chunk.toString(); });
  write(path.join(output, 'mgcrea-discovery.json'), await client.listTools());
  const mgTool = async (name, arguments_) => { const value = await client.callTool({ name, arguments: arguments_ }, undefined, { timeout: 10000 }); assert(!value.isError, JSON.stringify(value)); return value.structuredContent ?? JSON.parse(value.content[0].text); };
  routes.mgcrea_typed = { send: command => mgTool('a2a_send_message', { url: proxyUrl, text: command }),
    get: receipt => mgTool('a2a_get_task', { task_id: receipt.id, refresh: true, history_length: 0 }),
    receipt: value => ({ id: value.task.id, contextId: value.task.context_id }) };
  routes.mgcrea_raw = { send: async command => { const value = await mgTool('a2a_request', { url: proxyUrl, method: 'SendMessage', params: { message: message(command) } }); return value.result.task ?? value.result; },
    get: async receipt => { const value = await mgTool('a2a_request', { url: proxyUrl, method: 'GetTask', params: { id: receipt.id, historyLength: 0 } }); return value.result.task ?? value.result; },
    receipt: routes.native.receipt };

  for (const spec of specifications) for (let repetition = 0; repetition < repetitions; repetition++) for (const routeName of routesList) {
    current = []; const began = performance.now();
    const cell = { schema_version: 'loss_parts_cell_v2', case_id: spec.id, route: routeName, repetition, spec,
      episode_id: `${spec.id}--r${repetition}--${routeName}`, execution_status: 'unknown', required_representation_survived: null };
    try {
      const route = routes[routeName]; const initial = await route.send(spec.command); const receipt = route.receipt(initial);
      assert(receipt.id && receipt.contextId, 'Initial receipt must include task/context');
      let final;
      for (let attempt = 0; attempt < 10; attempt++) {
        final = await route.get(receipt);
        const state = routeName === 'amirk_typed' ? final.structuredContent.a2aState : routeName === 'mgcrea_typed' ? final.state : final.status.state;
        if (state === 'TASK_STATE_COMPLETED' || state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      cell.initial = initial; cell.receipt = receipt; cell.final = final;
      let observed;
      if (routeName === 'native' || routeName === 'mgcrea_raw') observed = final.artifacts?.[0]?.parts?.[0] ?? null;
      else if (routeName === 'mgcrea_typed') observed = final.artifacts?.[0] ?? null;
      else {
        const block = final.content.find(block => block._meta?.['io.github.amirk-s/a2a']?.artifactId);
        const metadata = block?._meta?.['io.github.amirk-s/a2a'];
        if (block?.type === 'text') observed = metadata?.partKind === 'data' ? { data: JSON.parse(block.text), mediaType: metadata.mediaType } : { text: block.text, mediaType: metadata?.mediaType };
        else if (block?.type === 'resource_link') observed = { url: block.uri, filename: block.name, mediaType: block.mimeType };
        else if (block?.type === 'image') observed = { raw: block.data, filename: metadata?.filename, mediaType: block.mimeType };
        else observed = block ?? null;
      }
      cell.observed_artifact_projection = observed;
      cell.field_checks = Object.fromEntries(Object.entries(spec.expected).map(([key, value]) => [key, same(observed?.[key], value)]));
      cell.required_representation_survived = Object.values(cell.field_checks).every(Boolean);
      cell.required_payload_survived = cell.field_checks[spec.payload_key];
      cell.recovery = { eligible: routeName === 'mgcrea_typed' && !cell.required_representation_survived, status: 'not_applicable' };
      cell.initial_wire = [...current];
      if (cell.recovery.eligible) {
        const beganRecovery = performance.now();
        const recoveredTask = await routes.mgcrea_raw.get(receipt);
        assert.equal(recoveredTask.id, receipt.id, 'Recovery raw read changed task');
        assert.equal(recoveredTask.contextId, receipt.contextId, 'Recovery raw read changed context');
        cell.recovery.final_public_task = recoveredTask;
        cell.recovery.observed_artifact = recoveredTask.artifacts?.[0]?.parts?.[0] ?? null;
        cell.recovery.field_checks = Object.fromEntries(Object.entries(spec.expected).map(([key, value]) => [key, same(cell.recovery.observed_artifact?.[key], value)]));
        cell.recovery.status = Object.values(cell.recovery.field_checks).every(Boolean) ? 'pass' : 'fail';
        cell.recovery.wall_ms = performance.now() - beganRecovery;
        cell.recovery.wire = current.slice(cell.initial_wire.length);
      }
      cell.execution_status = 'recorded';
    } catch (error) { cell.execution_status = 'execution_error'; cell.error = error.stack ?? String(error); }
    cell.wall_ms = performance.now() - began; cell.wire = current; current = null;
    write(path.join(output, 'cells', cell.episode_id + '.json'), cell); records.push(cell);
  }
} finally {
  current = null; await client?.close(); await stdio?.close(); await bridge?.close();
  if (proxy) { proxy.closeAllConnections(); await new Promise(resolve => proxy.close(resolve)); }
  if (fixture) { fixture.kill(); if (fixture.exitCode === null) await new Promise(resolve => { fixture.once('exit', resolve); setTimeout(resolve, 5000); }); }
  write(path.join(output, 'lifecycle.json'), { fixture_stdout: fixtureOut, fixture_stderr: fixtureErr, bridge_stderr: bridgeErr,
    fixture_pid: fixture?.pid, fixture_exit_code: fixture?.exitCode, fixture_exit_signal: fixture?.signalCode,
    fixture_exited: fixture?.exitCode !== null || fixture?.signalCode !== null, proxy_closed: proxy ? !proxy.listening : null, setup_wire: setup });
}
const result = { schema_version: 'loss_parts_result_v2', status: records.length === allocation.cells.length && records.every(c => c.execution_status === 'recorded') ? 'complete' : 'complete_with_errors',
  attempted: records.length, allocated: allocation.cells.length, model_calls: 0, repetitions,
  by_route: Object.fromEntries(routesList.map(route => [route, Object.fromEntries(specifications.map(spec => { const cells = records.filter(c => c.route === route && c.case_id === spec.id);
    return [spec.id, { attempts: cells.length, representation_pass: cells.filter(c => c.required_representation_survived === true).length, representation_fail: cells.filter(c => c.required_representation_survived === false).length, unknown: cells.filter(c => c.required_representation_survived === null).length,
      payload_pass: cells.filter(c => c.required_payload_survived === true).length,
      field_pass: cells.reduce((sum, c) => sum + Object.values(c.field_checks ?? {}).filter(Boolean).length, 0), field_eligible: cells.length * Object.keys(spec.expected).length,
      recovery_eligible: cells.filter(c => c.recovery?.eligible).length, recovery_pass: cells.filter(c => c.recovery?.status === 'pass').length }]; }))])),
  completed_utc: new Date().toISOString(), changed_sources: sources.filter(s => hash(readFileSync(path.join(root, s.path))) !== s.sha256), scope: allocation.scope };
write(path.join(output, 'results.json'), result);
const files = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? files(path.join(dir, e.name)) : [path.join(dir, e.name)]);
write(path.join(output, 'manifest.json'), { files: files(output).sort().map(p => ({ path: path.relative(output, p).replaceAll('\\', '/'), bytes: readFileSync(p).length, sha256: hash(readFileSync(p)) })) });
console.log(JSON.stringify(result));
if (result.status !== 'complete' || result.changed_sources.length) process.exitCode = 1;
