import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { digest } from '../src/core.mjs';
import { WorkspaceStore, emptyState, replacePartition, taskDraft, startTask, saveReview, makeRecord, publicState } from '../src/workspace/store.mjs';
import { createWorkspaceAgent } from '../src/workspace/agent.mjs';
import { prepareTaskInput, experimentRoot } from '../src/workspace/documents.mjs';
import { equalGroups, movedGroups } from '../web/materials.mjs';
import { WorkspaceRunner } from '../src/workspace/runner.mjs';

function fixture() {
  const state = emptyState();
  state.pages = Array.from({ length: 8 }, (_, i) => ({ id: `p${i}`, role: 'student', active: true, fileName: 'test.pdf', sourceId: 'source', sourcePage: i + 1 }));
  state.pages.push({ id: 'ms', role: 'scheme', active: true, fileName: 'scheme.pdf', sourceId: 'scheme', sourcePage: 1 });
  state.groups = [{ id: 'a', label: 'A', pageIds: ['p0', 'p1', 'p2', 'p3'] }, { id: 'b', label: 'B', pageIds: ['p4', 'p5', 'p6', 'p7'] }];
  state.schemes = [{ id: 'ms', label: 'Standard', pageIds: ['ms'] }];
  return state;
}
const draft = (state, values = {}) => taskDraft(state, { title: 'Only A', goal: 'Grade only A and wait for review.', kind: 'grade', groupIds: ['a'], schemeId: 'ms', after: 'review', ...values });
async function temporary(t) {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-workspace-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  return directory;
}
test('partition never loses, duplicates or admits a foreign/source page; manual labels survive', () => {
  for (const pages of [['p0'], ['p0', 'p0', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'], ['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'ms']]) {
    const state = fixture(); assert.throws(() => replacePartition(state, [{ id: 'x', pageIds: pages }]));
    assert.equal(state.materialRevision, 0);
  }
  const state = fixture(); const reordered = movedGroups(state.groups, 'p3', 'p4');
  replacePartition(state, reordered);
  assert.deepEqual(state.groups[0].pageIds, ['p0', 'p1', 'p2', 'p4']);
  assert.equal(state.groups[0].label, 'A');
  assert.equal(state.materialRevision, 1);
  const split = equalGroups(state.groups, 3);
  assert.deepEqual(split.map(group => group.pageIds.length), [3, 3, 2]);
  assert.equal(new Set(split.flatMap(group => group.pageIds)).size, 8);
});
test('task starts once with an immutable selected-only source snapshot; edits invalidate older drafts', () => {
  const state = fixture(); const task = draft(state); state.tasks.push(task);
  const started = startTask(state, task.id);
  assert.deepEqual(started.groups.map(group => group.id), ['a']);
  assert.equal(started.pages.length, 5);
  assert.ok(!started.pages.some(page => page.id === 'p4'));
  assert.throws(() => startTask(state, task.id), /重复/);
  replacePartition(state, [{ id: 'a', pageIds: ['p0', 'p1'] }, { id: 'b', pageIds: ['p2', 'p3', 'p4', 'p5', 'p6', 'p7'] }]);
  assert.equal(started.groups[0].pageIds.length, 4);
  const stale = draft(state); state.tasks.push(stale);
  replacePartition(state, state.groups);
  assert.throws(() => startTask(state, stale.id), /材料/);
});
test('same student cannot be admitted twice concurrently, while disjoint batches remain independent', () => {
  const state = fixture(); const first = draft(state), overlap = draft(state), independent = draft(state, { groupIds: ['b'] });
  state.tasks.push(first, overlap, independent); startTask(state, first.id);
  assert.throws(() => startTask(state, overlap.id), /已有批改任务/);
  startTask(state, independent.id);
  assert.equal(state.tasks.filter(task => task.status === 'running').length, 2);
});
test('reviews preserve original unknown marks, allowed fractions and append-only corrections', () => {
  const state = fixture(), task = draft(state); state.tasks.push(task);
  const record = makeRecord(task, task.groups[0], { item_id: 'Q1', review_required: true },
    { point_id: 'M1', score: null, student_pages: [1], reason: 'uncertain' },
    { max_score: 1, allowed_awards: [0, 0.5, 1], source_pages: [1] }, 'gradehash', 'rubrichash');
  task.records.push(record);
  assert.equal(record.score, null);
  const input = { taskId: task.id, recordId: record.id, originalHash: record.originalHash, score: 0.5, reason: 'Source permits half a mark.' };
  saveReview(state, input); saveReview(state, { ...input, score: null, reason: 'Needs another look.' });
  assert.equal(state.reviews.length, 2); assert.equal(task.records[0].score, null);
  assert.throws(() => saveReview(state, { ...input, originalHash: 'wrong' }), /改变/);
  for (const score of [2, -1, 0.2, '1', NaN]) assert.throws(() => saveReview(state, { ...input, score }));
});
test('atomic persistence rejects stale writers and reloads drafts and reviews', async t => {
  const directory = await temporary(t), store = await new WorkspaceStore(directory).init();
  const results = await Promise.allSettled([store.mutate(0, state => { state.title = 'first'; }), store.mutate(0, state => { state.title = 'stale'; })]);
  assert.equal(results.filter(result => result.status === 'fulfilled').length, 1);
  assert.equal((await new WorkspaceStore(directory).init()).state.title, 'first');
  await assert.rejects(store.mutate(1, state => { state.title = 'failed'; throw Error('no save'); }));
  assert.equal(store.state.title, 'first');
});
test('server restart does not automatically retry previously running paid work', async t => {
  const directory = await temporary(t), store = await new WorkspaceStore(directory).init();
  await store.mutate(0, state => { Object.assign(state, fixture()); const task = draft(state); state.tasks.push(task); startTask(state, task.id); });
  const runner = new WorkspaceRunner(store); await runner.recover();
  assert.equal(store.state.tasks[0].status, 'interrupted'); assert.equal(runner.active.size, 0);
});
test('real cohort preflight accepts selected-only grouped manifests and preserves original page hashes', async t => {
  const directory = await temporary(t), store = await new WorkspaceStore(directory).init(), state = fixture();
  for (const page of state.pages) {
    page.path = join(directory, `${page.id}.png`);
    const bytes = Buffer.from(`immutable-image-${page.id}`); page.sha256 = digest(bytes); await writeFile(page.path, bytes);
  }
  const task = draft(state); state.tasks.push(task); const started = startTask(state, task.id);
  const input = await prepareTaskInput(store, started);
  const manifest = JSON.parse(await readFile(input.manifest, 'utf8'));
  assert.deepEqual(manifest.students.map(row => row.id), ['a']);
  const prepared = JSON.parse(await readFile(join(manifest.students[0].input, 'manifest.json'), 'utf8'));
  assert.equal(prepared.documents.student.pages[0].source_page, 1);
  assert.equal(prepared.documents.student.pages[0].sha256, state.pages[0].sha256);
  await promisify(execFile)(process.execPath, [join(experimentRoot, 'src/run-cohort.mjs'), '--manifest', input.manifest, '--output', input.output, '--student-protocol', 'evidence-v4'], { cwd: experimentRoot });
  const plan = JSON.parse(await readFile(join(input.output, 'plan.json'), 'utf8'));
  assert.deepEqual(Object.keys(plan.students), ['a']);
  assert.equal(plan.students.a.pages.length, 4); assert.equal(plan.labels_in_model_context, false);
  const exposed = publicState({ ...state, tasks: [started] }, false);
  assert.ok(!JSON.stringify(exposed).includes(directory));
});

const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
function stream(turns) {
  return () => {
    const content = turns.shift() || [{ type: 'text', text: 'done' }];
    const result = createAssistantMessageEventStream();
    const message = { role: 'assistant', content, api: model.api, model: model.id, provider: model.provider,
      timestamp: Date.now(), stopReason: content.some(part => part.type === 'toolCall') ? 'toolUse' : 'stop',
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
    queueMicrotask(() => result.push({ type: 'done', reason: message.stopReason, message })); return result;
  };
}
const call = (name, args) => ({ type: 'toolCall', id: crypto.randomUUID(), name, arguments: args });
test('actual upstream Pi loop proposes an editable task without starting or modifying sources', async () => {
  const state = fixture(); const initial = structuredClone(state);
  const ctl = createWorkspaceAgent({ model, state, selectedIds: ['a'], goal: '检查 A，暂不批改', readPage: async () => ({ type: 'image', mimeType: 'image/png', data: 'test' }),
    streamFn: stream([[call('create_task_draft', { title: '检查漏页', goal: '检查 A 的漏页疑点', kind: 'assist', groupIds: ['a'], schemeId: null, after: 'review' })]]) });
  await ctl.agent.prompt(ctl.prompt);
  assert.equal(ctl.proposals[0].status, 'draft'); assert.equal(ctl.proposals[0].kind, 'assist');
  assert.deepEqual(state, initial);
});
test('planning cannot read or draft work outside the teacher selection', async () => {
  const state = fixture(); let imageReads = 0;
  const ctl = createWorkspaceAgent({ model, state, selectedIds: ['a'], goal: '仅检查 A',
    readPage: async () => { imageReads++; return { type: 'image', mimeType: 'image/png', data: 'test' }; },
    streamFn: stream([
      [call('read_pages', { pageIds: ['p4'] })],
      [call('create_task_draft', { title: 'Out of scope', goal: 'Check B', kind: 'assist', groupIds: ['b'], schemeId: null, after: 'review' })],
      [call('create_task_draft', { title: '检查 A', goal: 'Check A', kind: 'assist', groupIds: ['a'], schemeId: null, after: 'review' })],
    ]) });
  await ctl.agent.prompt(ctl.prompt);
  assert.equal(imageReads, 0);
  assert.equal(ctl.proposals.length, 1); assert.deepEqual(ctl.proposals[0].groupIds, ['a']);
  assert.equal(ctl.agent.state.messages.filter(message => message.role === 'toolResult' && message.isError).length, 2);
});
test('Pi free tasks reject out-of-scope pages and cannot cite sources read in the same model turn', async () => {
  const state = fixture(); let imageReads = 0;
  const ctl = createWorkspaceAgent({ model, state, selectedIds: ['a'], goal: '检查 A', mode: 'work', readPage: async () => { imageReads++; return { type: 'image', mimeType: 'image/png', data: 'test' }; },
    streamFn: stream([
      [call('read_pages', { pageIds: ['p4'] })],
      [call('read_pages', { pageIds: ['p0'] }), call('save_document', { title: 'too early', body: 'not consumed', references: ['p0'] })],
      [call('save_document', { title: '检查清单', body: '仅检查已读原页，余页尚未核对。', references: ['p0'] })],
    ]) });
  await ctl.agent.prompt(ctl.prompt);
  assert.equal(imageReads, 1); assert.equal(ctl.documents.length, 1); assert.equal(ctl.documents[0].title, '检查清单');
  assert.equal(ctl.agent.state.messages.filter(message => message.role === 'toolResult' && message.isError).length, 2);
});
