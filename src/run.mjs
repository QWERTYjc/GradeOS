import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { readFile, writeFile, mkdir, rename, appendFile, open } from 'node:fs/promises';
import { resolve, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { createGrader, Budget, digest, wireEstimate, SYSTEM_PROMPT, SUBMIT_SCHEMA } from './core.mjs';
import {outputBudget} from './output-budget.mjs';

const { values } = parseArgs({ options: {
  input: { type: 'string' }, output: { type: 'string' }, env: { type: 'string' },
  model: { type: 'string', default: 'openai/gpt-6.1-terra' },
  execute: { type: 'boolean', default: false }, cap: { type: 'string', default: '1' },
} });
if (!values.input || !values.output) throw Error('Required: --input prepared-directory --output new-run-directory [--execute]');
const input = resolve(values.input);
const output = resolve(values.output);
const manifest = JSON.parse(await readFile(resolve(input, 'manifest.json'), 'utf8'));
if (Object.keys(manifest.documents).sort().join(',') !== 'scheme,student') throw Error('Exactly two input roles are allowed');
for (const doc of Object.values(manifest.documents)) {
  for (const page of doc.pages) {
    const path = resolve(input, page.path);
    if (!path.startsWith(input + sep)) throw Error('Page path outside input directory');
    const bytes = await readFile(path);
    if (digest(bytes) !== page.sha256) throw Error('Page integrity mismatch');
  }
}
const cap = Number(values.cap);
if (!Number.isFinite(cap) || cap <= 0 || cap > 5) throw Error('Experiment cap must be between zero and five USD');
const models = createModels();
models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', values.model);
if (!model || !model.input.includes('image')) throw Error('Unknown model or no image support');
if (!['openai/gpt-6.1-terra', 'openai/gpt-6.1-sol'].includes(model.id)) throw Error('This experiment is qualified only for Terra/Sol; explicitly qualify another model first');
await mkdir(output, { recursive: false });
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sourceHashes = {};
for (const path of ['src/core.mjs', 'src/output-budget.mjs', 'src/run.mjs', 'scripts/python/prepare.py', 'package-lock.json']) sourceHashes[path] = digest(await readFile(resolve(root, path)));
const plan = {
  mode: 'full-cold fixture', created_at: new Date().toISOString(), model,
  source_hashes: sourceHashes, manifest, prompt_hash: digest(SYSTEM_PROMPT), schema_hash: digest(SUBMIT_SCHEMA),
  reasoning: 'low', temperature: null, seed: null, explicit_cache: false,
  provider: { only: ['openai'], allow_fallbacks: false, require_parameters: true, data_collection: 'deny' },
  library: { core: '1.5.2', ai: '1.5.2' }, cap_usd: cap,
  max_requests: 24, output_policy:'model/context capacity and available task funds', deadline_seconds: 900,
  network_retries: 0, max_premature_stop_continuations: 2, workers: 1, request_concurrency: 1,
  labels_in_model_context: false, runs: 1, completion: 'validated durable submit_grading',
  comparison: 'Exploratory comparison only: historical Codex model route, images and prompt differ.',
};
await writeFile(resolve(output, 'plan.json'), JSON.stringify(plan, null, 2) + '\n', { flag: 'wx' });
if (!values.execute) {
  console.log(JSON.stringify({ status: 'preflight_only', output, page_count: Object.values(manifest.documents).reduce((n, x) => n + x.pages.length, 0) }));
  process.exit(0);
}
if (values.env) process.loadEnvFile(resolve(values.env));
if (!process.env.OPENROUTER_API_KEY) throw Error('OPENROUTER_API_KEY missing');
const budget = new Budget({ cap });
const started = Date.now();
let currentRequest = null;
let failed = null;
const log = event => appendFile(resolve(output, 'events.jsonl'), JSON.stringify({ at: new Date().toISOString(), ...event }) + '\n');
const redactImages = value => JSON.parse(JSON.stringify(value, (k, v) => {
  if (k === 'data' && typeof v === 'string' && v.length > 1000) return `<base64 sha256=${digest(v)}>`;
  if (k === 'url' && typeof v === 'string' && v.startsWith('data:image/')) return `<image sha256=${digest(v)}>`;
  return v;
}));
const streamFn = (selectedModel, context, options) => models.streamSimple(selectedModel, context, {
  ...options, apiKey: process.env.OPENROUTER_API_KEY, maxRetries: 0,
  maxTokens: model.maxTokens, timeoutMs: 180000,
  onPayload: async (payload) => {
    payload.provider = plan.provider;
    payload.usage = { include: true };
    // Exact endpoint group; no model or provider rescue after a failure.
    for (const message of payload.messages) for (const part of Array.isArray(message.content) ? message.content : []) {
      if (part.type === 'image_url') part.image_url.detail = 'high';
    }
    const estimate = wireEstimate(payload);
    if (estimate.inputTokenReserve >= 272000) throw Error('Conservative input reservation reaches long-context price tier');
    const allowance=outputBudget({model,payload,inputTokens:estimate.inputTokenReserve,prices:model.cost,available:budget.available()});
    const reserve=allowance.reservation.input_usd+allowance.reservation.output_usd;
    currentRequest = budget.admit(reserve, {...estimate,max_output_tokens:allowance.tokens,output_allowance:allowance});
    await writeFile(resolve(output, `request-${currentRequest.number}.json`), JSON.stringify(redactImages(payload)), { flag: 'wx' });
    await log({ type: 'request_admitted', request: currentRequest });
    return payload;
  },
  onResponse: async response => {
    if (currentRequest) currentRequest.http_status = response.status;
    await log({ type: 'http_response', number: currentRequest?.number, status: response.status });
  },
  onProviderStreamEvent: async chunk => {
    if (chunk && typeof chunk === 'object' && (chunk.usage || chunk.provider)) {
      if (chunk.provider && currentRequest) currentRequest.actual_provider = chunk.provider;
      await log({ type: 'provider_receipt', number: currentRequest?.number, id: chunk.id, model: chunk.model, provider: chunk.provider, usage: chunk.usage });
    }
  },
});
const grader = createGrader({ manifest, model, streamFn, log,
  readPage: async (_doc, page) => {
    const bytes = await readFile(resolve(input, page.path));
    if (digest(bytes) !== page.sha256) throw Error('Input page changed after preflight');
    return bytes.toString('base64');
  },
  persist: async result => {
    const data = JSON.stringify(result, null, 2) + '\n';
    const handle = await open(resolve(output, 'grading.pending.json'), 'wx');
    try { await handle.writeFile(data); await handle.sync(); } finally { await handle.close(); }
    await writeFile(resolve(output, 'grading.sha256'), digest(data) + '\n', { flag: 'wx' });
    // The grading filename is the commit marker. A sidecar failure cannot publish a grade.
    await rename(resolve(output, 'grading.pending.json'), resolve(output, 'grading.json'));
  },
});
grader.agent.subscribe(async event => {
  if (event.type === 'message_end' && event.message.role === 'assistant') {
    if (currentRequest) {
      budget.settle(currentRequest, event.message);
      await log({ type: 'request_terminal', request: currentRequest });
      console.log(JSON.stringify({ request: currentRequest.number, stop: event.message.stopReason, usage: event.message.usage, pages: grader.getCoverage().length }));
      currentRequest = null;
    }
    await log({ type: 'assistant_message', message: event.message });
  }
  if (event.type === 'tool_execution_end') await log({ type: event.type, tool: event.toolName, is_error: event.isError, details: event.result?.details });
});
const timer = setTimeout(() => grader.agent.abort(), 900000);
process.once('SIGINT', () => grader.agent.abort());
try {
  const counts = Object.fromEntries(Object.entries(manifest.documents).map(([k, d]) => [k, d.pages.length]));
  await grader.agent.prompt(`Grade this complete submission. Available PDF page counts: ${JSON.stringify(counts)}. Page numbers are one-based physical PDF pages. Read all pages in batches, then submit every scored subpart. No external files or prior scores are available.`);
} catch (error) {
  failed = error instanceof Error ? error.message : String(error);
} finally {
  clearTimeout(timer);
  const result = grader.getResult();
  const summary = {
    status: result ? 'submitted' : 'incomplete', elapsed_seconds: (Date.now() - started) / 1000,
    failure: failed || grader.agent.state.errorMessage || null,
    continuations: grader.getContinuations(), coverage: grader.getCoverage(),
    requests: budget.requests, charged_or_reserved_usd: budget.chargedOrReserved,
    provider_reported_cost_usd: budget.requests.filter(x => x.status === 'provider_reported').reduce((n, x) => n + x.cost_usd, 0),
    unknown_cost_requests: budget.requests.filter(x => x.status === 'unknown').length,
    cost_receipts_complete: budget.requests.length > 0 && budget.requests.every(x => x.status === 'provider_reported'),
    admission_cap_exceeded: budget.chargedOrReserved > cap,
    request_count_meaning: 'admitted provider calls; not an independent count of physical network POSTs',
    semantic_coverage: 'not established by page delivery; independent item evaluation required',
    total_score: result?.total_score ?? null, max_score: result?.max_score ?? null,
  };
  await writeFile(resolve(output, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
  await writeFile(resolve(output, 'transcript.json'), JSON.stringify(redactImages(grader.agent.state.messages), null, 2) + '\n');
  console.log(JSON.stringify({ status: summary.status, output, requests: budget.requests.length, provider_reported_cost_usd: summary.provider_reported_cost_usd, total_score: summary.total_score }));
  if (!result) process.exitCode = 2;
}
