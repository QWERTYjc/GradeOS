import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { emptyState } from '../src/workspace/store.mjs';
import { createWorkspaceServer } from '../src/workspace/server.mjs';
import { questionRows, resultTasks, resultContext, resultsBar, recordDetail } from '../web/results-view.mjs';
import { needsGradingMaterials, workflowView } from '../web/canvas-view.mjs';

function fixture() {
  const state = emptyState();
  state.pages = [{ id: 'a-page', sha256: 'a-hash', sourcePage: 3 }, { id: 'b-page', sha256: 'b-hash', sourcePage: 1 }];
  state.groups = [{ id: 'a', label: '答卷 A', pageIds: ['a-page'] }, { id: 'b', label: '答卷 B', pageIds: ['b-page'] }];
  const point = (id, itemId, fields = {}) => ({ id, itemId, groupId: 'a', pointId: id, student: '答卷 A', score: 1, maximum: 1,
    originalHash: id + '-hash', allowedAwards: [0, 1], studentPageIds: ['a-page'], schemePageIds: [], ...fields });
  state.tasks = [{ id: 'batch', title: '本次批改', kind: 'grade', status: 'needs_review', groups: structuredClone(state.groups),
    groupIds: ['a', 'b'], pages: structuredClone(state.pages), artifacts: [], records: [
      point('method', '1'), point('answer', '1', { score: 0 }),
      point('unknown', '2', { score: null, reviewRequired: true }),
      point('feedback', '3', { score: null, maximum: null, disposition: 'feedback_only', reviewRequired: true }),
      point('other', '1', { groupId: 'b', student: '答卷 B', studentPageIds: ['b-page'] }),
    ] }];
  return state;
}

test('question navigation separates books and preserves zero, unknown and qualitative feedback', () => {
  const state = fixture(), before = structuredClone(state);
  const rows = questionRows(state, state.tasks[0], 'a');
  assert.equal(rows[0].scoreLabel, '1 / 2'); assert.equal(rows[0].deduction, true);
  assert.equal(rows[1].scoreLabel, '待定'); assert.equal(rows[1].pending, true);
  assert.equal(rows[2].scoreLabel, '定性反馈'); assert.equal(rows[2].deduction, false);
  assert.equal(questionRows(state, state.tasks[0], 'b')[0].scoreLabel, '1 / 1');
  assert.deepEqual(state, before);
  state.tasks[0].records.push({ ...state.tasks[0].records[3], id: 'mixed-feedback', itemId: '1', reviewRequired: false });
  const mixed = questionRows(state, state.tasks[0], 'a')[0];
  assert.equal(mixed.scoreLabel, '含定性反馈'); assert.equal(mixed.unknown, false);
});

test('only a review of this exact batch and original record changes the displayed score', () => {
  const state = fixture(), task = state.tasks[0];
  state.reviews.push({ taskId: 'different', recordId: 'unknown', originalHash: 'unknown-hash', score: 0 },
    { taskId: task.id, recordId: 'unknown', originalHash: 'older-hash', score: 0 });
  assert.equal(questionRows(state, task, 'a')[1].scoreLabel, '待定');
  state.reviews.push({ taskId: task.id, recordId: 'unknown', originalHash: 'unknown-hash', score: 0 });
  const reviewed = questionRows(state, task, 'a')[1];
  assert.equal(reviewed.scoreLabel, '0 / 1'); assert.equal(reviewed.pending, false);
  assert.equal(task.records[2].score, null);
  state.reviews.push({ taskId: task.id, recordId: 'feedback', originalHash: 'feedback-hash', score: null });
  assert.equal(questionRows(state, task, 'a')[2].pending, false);
});

test('result selection survives finished tasks and labels saved partial results without claiming completion', () => {
  const state = fixture();
  for (const status of ['failed', 'cancelled', 'partial', 'interrupted', 'running']) {
    state.tasks[0].status = status;
    assert.match(resultsBar({ state }), /仅显示已保存结果/);
  }
  state.tasks[0].status = 'completed';
  assert.equal(resultTasks(state).length, 1);
  assert.doesNotMatch(workflowView({ state }), /份答卷已就绪/);
  assert.match(workflowView({ state }), /继续查看批改结果/);
  assert.equal(resultContext({ state, resultGroupId: 'b' }).items.length, 1);
  assert.deepEqual(resultContext({ state, resultGroupId: 'a', resultFilter: 'deduction' }).filtered.map(row => row.id), ['1']);
  assert.deepEqual(resultContext({ state, resultGroupId: 'a', resultFilter: 'pending' }).filtered.map(row => row.id), ['2', '3']);
});

test('archived documents allow fresh grading intake while active batches and saved results keep their workflow', () => {
  const state = emptyState();
  state.documents = [{ id: 'notes', kind: 'document' }];
  assert.equal(needsGradingMaterials(state), true);
  for (const status of ['draft', 'running', 'needs_review']) {
    state.tasks = [{ kind: 'grade', status }];
    assert.equal(needsGradingMaterials(state), false);
  }
  state.tasks = [{ kind: 'grade', status: 'completed', artifacts: [{ id: 'report' }] }];
  assert.equal(needsGradingMaterials(state), false);
  state.tasks = [];
  state.pages = [{ id: 'source' }];
  assert.equal(needsGradingMaterials(state), true);
});

test('report-only workspaces remain readable instead of asking for unrelated student uploads', () => {
  const state = emptyState(); state.documents = [{ id: 'report', kind: 'artifact', title: '已有报告' }];
  assert.equal(workflowView({ state }, [{ documentId: 'report' }]), '');
});

test('finishing review stays unavailable until every required point in the batch is resolved', () => {
  const state = fixture();
  assert.match(resultsBar({ state }), /data-action="complete-review"[^>]*disabled/);
  state.reviews.push({ taskId: 'batch', recordId: 'unknown', originalHash: 'unknown-hash', score: 0 },
    { taskId: 'batch', recordId: 'feedback', originalHash: 'feedback-hash', score: null });
  assert.doesNotMatch(resultsBar({ state }), /data-action="complete-review"[^>]*disabled/);
});

test('the evidence panel uses owned unchanged source pages, escapes prose and preserves review drafts', () => {
  const state = fixture(), record = { ...state.tasks[0].records[0], taskId: 'batch', reason: '<img src=x onerror=alert(1)>', evidence: '$x^2$' };
  const html = recordDetail({ state }, record, { score: 0, reason: '尚未保存的复核依据' });
  assert.match(html, /data-action="record-source"[^>]*data-id="a-page"/);
  assert.match(html, /尚未保存的复核依据/); assert.match(html, /value="0" selected/);
  assert.match(html, /report-math/); assert.doesNotMatch(html, /<img src=x/);
  state.groups[0].pageIds = ['b-page'];
  assert.doesNotMatch(recordDetail({ state }, record), /data-action="record-source"/);
  assert.match(recordDetail({ state }, record), /原卷无法定位/);
});

test('results assets are served with executable module types without contacting a model', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-results-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const app = await createWorkspaceServer({ directory, port: 0, configured: () => false, agent: () => assert.fail('Reading results must not call a model') });
  t.after(() => app.close());
  const base = `http://127.0.0.1:${app.server.address().port}`;
  for (const [path, type] of [['results-view.mjs', 'text/javascript'], ['results.css', 'text/css'], ['grading-annotations.mjs', 'text/javascript'], ['annotation-layout.mjs','text/javascript'], ['annotation-card.mjs','text/javascript'], ['grading-result.mjs','text/javascript'], ['page-stream.mjs','text/javascript']]) {
    const response = await fetch(`${base}/${path}`);
    assert.equal(response.status, 200); assert.match(response.headers.get('content-type'), new RegExp(type));
    assert.ok((await response.text()).length > 100);
  }
});

test('library preserves frozen student ownership, deduplicates editable reports and keeps loose documents separate', async () => {
  const { librarySections } = await import('../web/grading-library.mjs');
  const task = { id: 't', title: '批次', groups: [{ id: 'a', label: '甲' }, { id: 'b', label: '乙' }],
    artifacts: [{ id: 'personal', groupId: 'a', title: '同名' }, { id: 'unknown', title: '甲' }], records: [{ groupId: 'b' }] };
  const sections = librarySections({ tasks: [task], documents: [
    { taskId: 't', artifactId: 'personal', title: '已编辑', id: 'edited' },
    { id: 'old', title: '甲', folder: '讲评' }, { id: 'loose', title: '甲' }] });
  const batch = sections.find(section => section.title === '批次');
  assert.deepEqual(batch.rows.map(row => [row.id, row.groupLabel]), [['edited','甲'], ['unknown',null], ['b','乙']]);
  assert.deepEqual(sections.filter(section => section !== batch).map(section => section.title), ['讲评','未关联批次']);
});

test('regrouping noncontiguous pages preserves unique ownership and original target order', async () => {
  const { assignPages } = await import('../web/materials.mjs');
  const groups = [{ id: 'a', pageIds: ['1','2'] }, { id: 'b', pageIds: ['3','4'] }];
  const assigned = assignPages(groups, new Set(['1','3']), 'b', '');
  assert.deepEqual(assigned.map(group => group.pageIds), [['2'],['3','4','1']]);
  const split = assignPages(groups, new Set(['1','2','4']), '', '丙');
  assert.deepEqual(split.map(group => group.pageIds), [['3'],['1','2','4']]);
  assert.equal(split[1].label, '丙');
  assert.throws(() => assignPages(groups, new Set(['stale']), '', ''));
});
