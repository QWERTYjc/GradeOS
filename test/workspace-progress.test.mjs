import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { collectGradingProgress } from '../src/workspace/grading-progress.mjs';
import { WorkspaceRunner } from '../src/workspace/runner.mjs';
import { WorkspaceStore } from '../src/workspace/store.mjs';
import { taskView, progressMetrics } from '../web/tasks.mjs';

async function fixture(t) {
  const output = await mkdtemp(join(tmpdir(), 'pi-workspace-progress-'));
  t.after(() => rm(output, { recursive: true, force: true }));
  const task = { id: 'task', title: '测试批改', kind: 'grade', status: 'running', goal: '测试批改',
    groupIds: ['a', 'b'], groups: [{ id: 'a', label: '答卷 A' }, { id: 'b', label: '答卷 B' }], records: [], artifacts: [], after: 'review' };
  const records = [{ id: 'ra', groupId: 'a' }, { id: 'rb', groupId: 'b' }];
  const write = async (path, value) => writeFile(join(output, path), typeof value === 'string' ? value : JSON.stringify(value));
  const project = (extra = {}) => collectGradingProgress({ task, output, records, gradingSaved: 1, rubricReady: true, final: false, ...extra });
  return { output, task, records, write, project };
}

test('personal report is available before cohort completion; saved marks, feedback and billed cost remain distinct', async t => {
  const f = await fixture(t);
  await mkdir(join(f.output, 'feedback-a')); await f.write('feedback-a/REPORT.zh-CN.md', '# A feedback');
  await f.write('REPORT.zh-CN.md', '# unfinished aggregate must not be shown');
  await f.write('progress.json', { version: 1, students: [{ id: 'a', feedback_status: 'submitted' }, { id: 'b', feedback_status: 'pending' }],
    phase: 'student_grading', active_phases: ['student_grading', 'student_feedback'], elapsed_seconds: 47.2,
    settled_cost_usd: .03, requests: { unknown_cost: 1 }, reports: [{ path: '/private/local/path' }] });
  const result = await f.project();
  assert.equal(result.progress.completed, 1); assert.equal(result.progress.feedbackCompleted, 1);
  assert.equal(result.progress.costComplete, false); assert.equal(result.progress.unknownCostRequests, 1);
  assert.equal(result.artifacts.length, 1); assert.deepEqual(result.artifacts[0].references, ['ra']);
  assert.equal(result.progress.phase, '批改答卷、生成个人反馈');
  assert.doesNotMatch(JSON.stringify(result), /private|unfinished/);
  const html = taskView({ state: { tasks: [{ ...f.task, ...result }], groups: f.task.groups }, activeTaskId: 'task' });
  assert.match(html, /评分已保存 1\/2 份 · 个人报告可读 1\/2 份/);
  assert.match(html, /已结算 \$0.03000/); assert.match(html, /另有费用待确认/);
  assert.match(html, /data-action="artifact"/); assert.doesNotMatch(html, /预计|%/);
});

test('submitted files are required, final summary wins over stale progress, and cancellation preserves artifacts', async t => {
  const f = await fixture(t);
  await mkdir(join(f.output, 'feedback-a')); await f.write('feedback-a/REPORT.zh-CN.md', '# A feedback');
  await f.write('progress.json', { version: 1, status: 'stopping', students: [{ id: 'a', feedback_status: 'submitted' }, { id: 'b', feedback_status: 'submitted' }] });
  const live = await f.project(); assert.equal(live.progress.feedbackCompleted, 1); assert.equal(live.progress.stopping, true);
  const result = await f.project({ final: true, summary: { students: [{ student_id: 'a', feedback_status: 'failed' }], report_submitted: false,
    provider_reported_cost_usd: .05, unknown_cost_requests: 0, cost_receipts_complete: true, elapsed_including_image_preparation_seconds: 100 } });
  assert.equal(result.artifacts.length, 0); assert.equal(result.progress.settledCostUsd, .05); assert.equal(result.progress.costComplete, true);
});

test('unrelated progress and missing receipts cannot impersonate the selected students or a zero-cost run', async t => {
  const f = await fixture(t);
  await f.write('progress.json', { version: 1, students: [{ id: 'wrong' }], settled_cost_usd: 0, elapsed_seconds: 999 });
  const result = await f.project(); assert.equal(result.progress.elapsedSeconds, null); assert.equal(result.progress.settledCostUsd, null);
  assert.equal(progressMetrics(result.progress), '');
  assert.doesNotMatch(progressMetrics({ elapsedSeconds: -1, settledCostUsd: NaN }), /\$|秒/);
});

test('workspace collector updates report and cost while grade count stays unchanged without endlessly bumping revisions', async t => {
  const f = await fixture(t), store = await new WorkspaceStore(join(f.output, 'workspace')).init();
  await store.mutate(null, state => { state.tasks.push(f.task); });
  const runner = new WorkspaceRunner(store);
  await runner.collect(f.task, f.output, false); const initialRevision = store.state.revision;
  await runner.collect(f.task, f.output, false); assert.equal(store.state.revision, initialRevision);
  await mkdir(join(f.output, 'feedback-a')); await f.write('feedback-a/REPORT.zh-CN.md', '# A feedback');
  await f.write('progress.json', { version: 1, students: [{ id: 'a', feedback_status: 'submitted' }, { id: 'b' }],
    active_phases: ['student_feedback'], settled_cost_usd: .02, elapsed_seconds: 40, requests: { unknown_cost: 0 } });
  await runner.collect(f.task, f.output, false);
  const task = store.state.tasks[0]; assert.equal(task.progress.completed, 0); assert.equal(task.progress.feedbackCompleted, 1);
  assert.equal(task.progress.settledCostUsd, .02); assert.equal(task.artifacts.length, 1);
  const revision = store.state.revision; await runner.collect(f.task, f.output, false); assert.equal(store.state.revision, revision);
});
