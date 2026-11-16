// Frozen-stage real-model probe. Evaluator expectations are not accepted as input.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { parseArgs } from 'node:util';
import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { createRuntime, freezeJson } from '../src/cohort-runtime.mjs';
import { digest } from '../src/core.mjs';
import { experimentModel, experimentProvider } from '../src/experiment-models.mjs';
import { createReferenceDeriver, createReferenceReviewer, applyReferenceReview, taskOnlyInput } from '../src/workspace/reference-audit.mjs';

const { values } = parseArgs({ options: { input: { type: 'string' }, output: { type: 'string' }, env: { type: 'string' } } });
if (!values.input || !values.output) throw Error('input and output are required');
if (values.env) process.loadEnvFile(resolve(values.env));
const { candidate, pages } = JSON.parse(await readFile(resolve(values.input), 'utf8'));
const output = resolve(values.output); await mkdir(output, { recursive: true });
await writeFile(join(output, 'attempt.json'), JSON.stringify({ startedAt: new Date().toISOString(), inputHash: digest({ candidate, pages }) }), { flag: 'wx' });
const models = createModels(); models.setProvider(openrouterProvider());
const model = experimentModel(models, 'openai/gpt-6.1-terra'), controller = new AbortController();
const runtime = createRuntime({ models, model, output, cap: 2, controller, maxRequests: 32, maxOutputTokens: 16000, structuredOutput: false, provider: experimentProvider(model.id) });
let failure = null, checked = null;
try {
  const dIO = await runtime.io('reference-derivation', () => 'adaptive_reference_derivation', { isolated: true });
  await freezeJson(dIO.directory, 'task-only-input.json', taskOnlyInput(candidate));
  const d = createReferenceDeriver({ model, streamFn: dIO.streamFn, candidate, log: dIO.log });
  const detachD = dIO.attach(d.agent);
  try { await runtime.run(d.agent, d.prompt, dIO.directory); } finally { detachD(); }
  const derivation = d.getResult(); if (!derivation) throw Error('No independent derivation submitted');
  await freezeJson(dIO.directory, 'derivation.json', derivation);
  const rIO = await runtime.io('reference-review', () => 'adaptive_reference_review', { isolated: true });
  const r = createReferenceReviewer({ model, streamFn: rIO.streamFn, candidate, derivation, pages, log: rIO.log,
    readPage: async page => {
      const bytes = await readFile(page.path); if (digest(bytes) !== page.sha256) throw Error('Source changed');
      return { type: 'image', mimeType: 'image/png', data: bytes.toString('base64') };
    } });
  const detachR = rIO.attach(r.agent);
  try { await runtime.run(r.agent, r.prompt, rIO.directory); } finally { detachR(); }
  const review = r.getResult(); if (!review) throw Error('No reference verification submitted');
  await freezeJson(rIO.directory, 'reference-review.json', review);
  checked = applyReferenceReview(candidate, derivation, review);
  await freezeJson(output, 'verified-candidate.json', checked);
} catch (error) { failure = error.message; }
finally {
  runtime.close();
  const summary = { status: failure ? 'failed' : 'submitted', failure, ...runtime.totals(runtime.budget.requests),
    results: checked?.plan.items.map(item => ({ id: item.id, verification: item.referenceVerification })) || [], finishedAt: new Date().toISOString() };
  await freezeJson(output, 'summary.json', summary);
  console.log(JSON.stringify({ ...summary, results: summary.results.map(i => ({ id: i.id, status: i.verification.status })) }, null, 2));
  if (failure) process.exitCode = 1;
}
