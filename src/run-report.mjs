import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { digest } from './core.mjs';
import { controlledAgent, validateFrozenRubric } from './cohort-core.mjs';
import { ResultsStore } from './results-store.mjs';
import { createRuntime, freezeJson, readImage } from './cohort-runtime.mjs';
import { createSourceInspection } from './report-context.mjs';
import { createReporting, REPORTING_INSTRUCTIONS } from './cohort-reporting.mjs';
import { renderReportMarkdown } from './report-markdown.mjs';

const { values } = parseArgs({ options: { source: { type: 'string' }, output: { type: 'string' },
  execute: { type: 'boolean', default: false }, cap: { type: 'string', default: '1' }, env: { type: 'string' } } });
if (!values.source || !values.output) throw Error('Required: --source completed-cohort --output new-report-directory');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(values.source); const output = resolve(values.output); const cap = Number(values.cap);
if (!Number.isFinite(cap) || cap <= 0 || cap > 1) throw Error('Invalid reporting budget');
const sourcePlan = JSON.parse(await readFile(resolve(source, 'plan.json'), 'utf8'));
const sourceSummary = JSON.parse(await readFile(resolve(source, 'summary.json'), 'utf8'));
if (sourceSummary.active_agents_at_summary !== 0 || !['submitted','partial_completed'].includes(sourceSummary.status)) throw Error('Source cohort not terminal');
const rubricBytes = await readFile(resolve(source, 'rubric.json'));
if (digest(rubricBytes) !== (await readFile(resolve(source, 'rubric.sha256'), 'utf8')).trim()) throw Error('Frozen MS file changed');
const rubric = validateFrozenRubric(JSON.parse(rubricBytes.toString('utf8')), sourcePlan.scheme);
const studentIds = Object.keys(sourcePlan.students);
if (sourceSummary.students.length !== studentIds.length || new Set(sourceSummary.students.map(r => r.student_id)).size !== studentIds.length || sourceSummary.students.some(r => !studentIds.includes(r.student_id))) throw Error('Source task roster mismatch');
await mkdir(output, { recursive: false });
await freezeJson(output, 'rubric.json', rubric);
const store = new ResultsStore(resolve(output, 'results'), studentIds, [source]); await store.init();
for (const row of sourceSummary.students) {
  if (row.status === 'submitted') {
    const gradingPath = resolve(source, `student-${row.student_id}`, 'grading.json');
    const feedbackPath = row.feedback_status === 'submitted' ? resolve(source, `feedback-${row.student_id}`, 'feedback.json') : null;
    await store.publish(row.student_id, { status: row.status, rubric_hash: rubric.hash, grading_path: gradingPath,
      grading_sha256: (await readFile(gradingPath.replace(/\.json$/, '.sha256'), 'utf8')).trim(),
      answer_sha256: sourcePlan.students[row.student_id].sha256, writer: 'previous_pi_student_submit_grading', imported_from: source,
      feedback_status: row.feedback_status ?? 'unavailable', feedback_path: feedbackPath,
      feedback_sha256: feedbackPath ? (await readFile(feedbackPath.replace(/\.json$/, '.sha256'), 'utf8')).trim() : null });
  } else await store.publish(row.student_id, { status: row.status, failure: row.failure ?? null, rubric_hash: rubric.hash });
}
await store.seal(sourceSummary.students, rubric.hash);
const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', sourcePlan.model.id);
const hashes = {};
for (const name of ['src/core.mjs','src/rubric-contract.mjs','src/point-evidence.mjs','src/report-context.mjs','src/cohort-core.mjs','src/cohort-runtime.mjs','src/results-store.mjs','src/cohort-reporting.mjs','src/report-markdown.mjs','src/run-report.mjs','scripts/python/analytics.py', 'src/python.mjs', 'scripts/python/gradeos_analysis.py','package-lock.json']) hashes[name] = digest(await readFile(resolve(root,name)));
await mkdir(resolve(output,'source-files'));
for (const name of Object.keys(hashes)) { const target=resolve(output,'source-files',name);await mkdir(dirname(target),{recursive:true});await writeFile(target,await readFile(resolve(root,name)),{flag:'wx'}); }
const gradeosHashes = {};
for (const name of ['scripts/python/analytics.py','scripts/python/gradeos_analysis.py']) gradeosHashes[name] = digest(await readFile(resolve(root,name)));
await freezeJson(output, 'plan.json', { mode: 'reporting-only replay of previously committed Pi student results',
  created_at: new Date().toISOString(), source, source_summary_sha256: digest(await readFile(resolve(source,'summary.json'))),
  model, reasoning: 'low', prompt_hash: digest(REPORTING_INSTRUCTIONS), source_hashes: hashes, gradeos_source_hashes: gradeosHashes,
  cap_usd: cap, max_requests: 24, output_policy:'model/context capacity and available task funds', network_retries: 0, new_grading_calls: 0, new_ms_compilation_calls: 0,
  result_set_hash: store.sealed.result_set_hash, rubric_hash: rubric.hash, students: studentIds,
  provider: { only: ['openai'], allow_fallbacks: false, require_parameters: true, data_collection: 'deny' },
  labels_in_model_context: false, previous_grading_cost_usd: sourceSummary.provider_reported_cost_usd });
if (!values.execute) { console.log(JSON.stringify({ status: 'preflight_only', records: studentIds.length, output })); process.exit(0); }
if (values.env) process.loadEnvFile(resolve(values.env));
if (!process.env.OPENROUTER_API_KEY) throw Error('OpenRouter credential missing');
const controller = new AbortController(); const runtime = createRuntime({ models, model, output, cap, controller, maxRequests: 24 });
process.once('SIGINT', () => controller.abort(Error('User cancellation')));
const io = await runtime.io('main', () => 'reporting');
const reporting = createReporting({ store, output, getRubric: () => rubric, ensureSealed: async () => store.sealed,
  context: { unique_answer_sources: new Set(Object.values(sourcePlan.students).map(doc => doc.sha256)).size, requested_students: studentIds.length },
  log: io.log, signal: controller.signal });
const inspect=createSourceInspection({getRubric:()=>rubric,scheme:sourcePlan.scheme,readImage,views:reporting.views,log:io.log});
const main = controlledAgent({ model, streamFn: io.streamFn, prompt: REPORTING_INSTRUCTIONS, tools: [...reporting.tools,inspect],
  transformContext:reporting.transformContext,onModelResponse:reporting.onModelResponse,
  finished: () => Boolean(reporting.getResult()), log: io.log });
const started = Date.now(); let failure = null; const unsubscribe = io.attach(main.agent);
try { await runtime.run(main.agent, `All tasks are terminal. Read every saved result and analyze them, then submit the Chinese report. Student IDs: ${JSON.stringify(studentIds)}. Do not run grading or MS compilation.`, io.directory); }
catch (error) { failure = error.message; }
finally {
  unsubscribe(); runtime.close();
  const summary = { status: reporting.getResult() ? 'submitted' : 'incomplete', failure: failure || main.agent.state.errorMessage || null,
    elapsed_seconds: (Date.now()-started)/1000, records_read: reporting.getReadIds(),
    result_set_hash: store.sealed.result_set_hash, source_cohort: source, new_grading_calls: 0,
    active_agents_at_summary: runtime.active.size, continuations: main.getContinuations(),
    ...runtime.totals(runtime.budget.requests), requests: runtime.budget.requests,
    cost_receipts_complete: runtime.budget.requests.every(r => r.status === 'provider_reported') };
  await writeFile(resolve(output,'summary.json'), JSON.stringify(summary,null,2)+'\n');
  if (reporting.getResult()) await writeFile(resolve(output,'REPORT.zh-CN.md'),
    renderReportMarkdown(reporting.getResult(), reporting.getAnalysis(), { output, index: store.sealed, summary, sourceSummary, sourceCohort: source }));
  console.log(JSON.stringify({ status: summary.status, output, records_read: summary.records_read.length, cost_usd: summary.provider_reported_cost_usd, requests: summary.admitted_requests }));
  if (!reporting.getResult()) process.exitCode = 2;
}
