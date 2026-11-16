import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { digest } from './core.mjs';
import { StudentRegistry, validateFrozenRubric, parseConcurrency } from './cohort-core.mjs';
import { createRuntime, freezeJson } from './cohort-runtime.mjs';
import { FEEDBACK_PROMPT, FEEDBACK_SCHEMA, runStudentFeedback } from './student-feedback.mjs';
import { COMPACT_FEEDBACK_PROMPT, COMPACT_FEEDBACK_SCHEMA } from './compact-feedback.mjs';
import {randomUUID} from 'node:crypto';

const { values } = parseArgs({ options: { source: { type: 'string' }, output: { type: 'string' },
  cap: { type: 'string', default: '2' }, concurrency: { type: 'string' },
  execute: { type: 'boolean', default: false }, env: { type: 'string' },
  mode:{type:'string',default:'detailed-v1'},'isolate-student-cache':{type:'boolean',default:false} } });
if (!values.source || !values.output) throw Error('Required: --source completed-cohort --output new-feedback-directory');
const source = resolve(values.source); const output = resolve(values.output);
const cap = Number(values.cap); const concurrency = parseConcurrency(values.concurrency);
const mode=values.mode;if(!['detailed-v1','compact-v2'].includes(mode))throw Error('Unknown feedback mode');
const compact=mode==='compact-v2';const studentCacheNamespace=values['isolate-student-cache']?randomUUID():null;
if (!(cap > 0 && cap <= 2)) throw Error('Invalid feedback budget');
const sourcePlan = JSON.parse(await readFile(resolve(source, 'plan.json'), 'utf8'));
const sourceSummary = JSON.parse(await readFile(resolve(source, 'summary.json'), 'utf8'));
if (sourceSummary.active_agents_at_summary !== 0 || !['submitted','partial_completed'].includes(sourceSummary.status)) throw Error('Source cohort not terminal');
const frozenFile = async path => {
  const bytes = await readFile(path);
  if (digest(bytes) !== (await readFile(path.replace(/\.json$/, '.sha256'), 'utf8')).trim()) throw Error('Frozen source file changed');
  return { value: JSON.parse(bytes.toString('utf8')), sha256: digest(bytes) };
};
const rubricFile = await frozenFile(resolve(source, 'rubric.json'));
const frozen = validateFrozenRubric(rubricFile.value, sourcePlan.scheme);
const ids = Object.keys(sourcePlan.students);
const registry = new StudentRegistry(ids, concurrency);
if (sourceSummary.students.length !== ids.length || new Set(sourceSummary.students.map(row => row.student_id)).size !== ids.length || sourceSummary.students.some(row => !ids.includes(row.student_id))) throw Error('Source roster mismatch');
const grades = new Map(); const bindings = [];
for (const id of ids) {
  const sourceRow = sourceSummary.students.find(row => row.student_id === id);
  if (sourceRow.status !== 'submitted') { bindings.push({ student_id: id, source_status: sourceRow.status }); continue; }
  const path = resolve(source, `student-${id}`, 'grading.json');
  const file = await frozenFile(path);
  if (file.value.rubric_hash !== frozen.hash) throw Error('Grade rubric differs');
  grades.set(id, file.value); bindings.push({ student_id: id, source_status: 'submitted', grading_path: path, grading_sha256: file.sha256 });
}
const models = createModels(); models.setProvider(openrouterProvider());
if (!['openai/gpt-6.1-terra','openai/gpt-6.1-sol'].includes(sourcePlan.model.id)) throw Error('Unsupported inherited route');
const model = models.getModel('openrouter', sourcePlan.model.id);
await mkdir(output, { recursive: false });
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const hashes = {};
for (const name of ['src/student-feedback.mjs','src/compact-feedback.mjs','src/run-student-feedback.mjs','src/core.mjs','src/cohort-core.mjs','src/cohort-runtime.mjs','package-lock.json']) hashes[name] = digest(await readFile(resolve(root,name)));
await freezeJson(output, 'plan.json', { mode: 'feedback-only frozen-result replay', created_at: new Date().toISOString(), source,
  source_summary_sha256: digest(await readFile(resolve(source,'summary.json'))), source_hashes: hashes,
  rubric_hash: frozen.hash, rubric_file_sha256: rubricFile.sha256, student_sources: bindings,
  feedback_mode:mode,student_cache_namespace:studentCacheNamespace,
  prompt_sha256: digest(compact?COMPACT_FEEDBACK_PROMPT:FEEDBACK_PROMPT), schema_sha256: digest(compact?COMPACT_FEEDBACK_SCHEMA:FEEDBACK_SCHEMA), model, reasoning: 'low',
  provider: { only: ['openai'], allow_fallbacks: false, require_parameters: true, data_collection: 'deny' },
  cap_usd: cap, concurrency, max_requests: ids.length * 2, max_output_tokens: compact?4096:8192, network_retries: 0,
  new_grading_calls: 0, new_ms_calls: 0, source_images_supplied: 0, official_labels_supplied: false,
  question: 'Complete source-bound summaries and item feedback; no score or grading-accuracy change claimed' });
if (!values.execute) { console.log(JSON.stringify({ status: 'preflight_only', output, students: ids.length, eligible: grades.size })); process.exit(0); }
if (values.env) process.loadEnvFile(resolve(values.env));
if (!process.env.OPENROUTER_API_KEY) throw Error('OpenRouter credential missing');
const controller = new AbortController();
process.once('SIGINT', () => controller.abort(Error('User cancellation')));
const runtime = createRuntime({ models, model, output, cap, controller, maxRequests: ids.length * 2, maxOutputTokens: compact?4096:8192,studentCacheNamespace });
const started = Date.now(); let failure = null;
try {
  await registry.dispatch(ids, concurrency ?? ids.length, async id => {
    if (!grades.has(id)) return { status: 'failed', failure: 'Original grading unavailable; no feedback invented' };
    return runStudentFeedback({ runtime, model, id, grade: grades.get(id), frozen,mode,
      sourcePath: bindings.find(row => row.student_id === id).grading_path });
  }, controller.signal);
} catch (error) { failure = error.message; }
finally {
  runtime.close();
  const rows = [...registry.rows.values()];
  const summary = { status: rows.every(row => row.status === 'submitted') ? 'submitted' : 'partial_completed',
    failure, elapsed_seconds: (Date.now()-started)/1000, ...runtime.totals(runtime.budget.requests),
    students: rows, requests: runtime.budget.requests, active_agents_at_summary: runtime.active.size,
    cost_receipts_complete: runtime.budget.requests.every(row => row.status === 'provider_reported'),
    new_grading_calls: 0, new_ms_calls: 0, original_scores_unchanged: true };
  await freezeJson(output, 'summary.json', summary);
  const lines = ['# 学生个人批改报告', '', '*Pi Agent · 基于冻结批改结果的反馈补充*', '',
    `已生成 **${rows.filter(row => row.status === 'submitted').length} / ${ids.length}** 份个人报告。每份包含总体评价、已有表现、练习计划、逐题判分说明和教师复核提示。`, '',
    `本批来源是同一答卷的重复批改任务，编号用于区分运行，不代表 ${ids.length} 名真实学生。`, '',
    '| 新增费用（USD） | 平均每个请求任务（USD） | 耗时 | 模型调用 |', '| ---: | ---: | ---: | ---: |',
    `| $${summary.provider_reported_cost_usd.toFixed(8)} | $${(summary.provider_reported_cost_usd / ids.length).toFixed(8)} | ${summary.elapsed_seconds.toFixed(3)} 秒 | ${summary.admitted_requests} |`, '',
    `仅包含此次反馈补充，未重新批改或整理 MS；未知费用请求数 ${summary.unknown_cost_requests}。原分数保持不变；新增建议不代表评分准确率提升。`, '',
    '| 任务 | 原分数 | 反馈建议复核小项 | 个人报告 |', '| --- | ---: | --- | --- |',
    ...rows.map(row => `| ${row.student_id} | ${grades.get(row.student_id)?.total_score ?? '待复核'} / ${grades.get(row.student_id)?.max_score ?? '未知'} | ${row.recommended_review_items?.join('、') || '—'} | ${row.report_path ? `[阅读报告](${row.report_path})` : row.status} |`), '',
    `[执行与费用回执](${resolve(output,'summary.json')}) · [冻结运行计划](${resolve(output,'plan.json')})`, '',
    '反馈来自原批改理由与已整理的 MS，本阶段未重新查看原答卷图片。每份报告保留原始理由和引用页码，便于教师回到来源核查。', ''];
  await writeFile(resolve(output, 'REPORT.zh-CN.md'), lines.join('\n'));
  console.log(JSON.stringify({ status: summary.status, output, cost_usd: summary.provider_reported_cost_usd, completed: rows.filter(row => row.status === 'submitted').length }));
  if (summary.status !== 'submitted') process.exitCode = 2;
}
