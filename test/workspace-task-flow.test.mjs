import test from 'node:test';
import assert from 'node:assert/strict';
import { submitTaskSetup, taskForm, taskFormInput } from '../web/tasks.mjs';
import { workflowView, pendingRecords } from '../web/canvas-view.mjs';
import { emptyState, taskDraft } from '../src/workspace/store.mjs';

test('confirmed qualitative feedback leaves the review queue while unresolved work stays pending', () => {
  const state = { tasks: [{ id: 'batch', records: [
    { id: 'feedback', disposition: 'feedback_only', reviewRequired: true },
    { id: 'unresolved', disposition: 'needs_material', reviewRequired: true },
    { id: 'reviewed-zero', disposition: 'score', reviewRequired: true },
    { id: 'unreviewed', disposition: 'score', reviewRequired: true },
  ] }], reviews: [] };
  assert.equal(pendingRecords(state).length, 4);
  state.reviews.push({ recordId: 'feedback', score: null }, { recordId: 'unresolved', score: null }, { recordId: 'reviewed-zero', score: 0 });
  const before = structuredClone(state);
  assert.deepEqual(pendingRecords(state).map(record => record.id), ['unresolved', 'unreviewed']);
  assert.deepEqual(state, before);
});

test('one action saves then starts exactly the created batch, preserving its execution mode', async () => {
  const calls = [], input = { groupIds: ['a'], executionMode: 'review', supplementalInstructions: '' };
  let savedId;
  const taskId = await submitTaskSetup({ input, start: true, onSaved: id => { savedId = id; },
    request: async (...args) => {
      calls.push(args);
      return { createdTaskId: 'our-task', tasks: [{ id: 'concurrent-task' }, { id: 'our-task' }] };
    } });
  assert.equal(taskId, 'our-task'); assert.equal(savedId, taskId);
  assert.deepEqual(calls, [['/api/tasks', input, 'POST'], ['/api/tasks/our-task/start']]);
});

test('failed start retains the saved draft and a deliberate retry cannot create another batch', async () => {
  const calls = []; let taskId = null;
  const input = { groupIds: ['a'], executionMode: 'auto' };
  await assert.rejects(submitTaskSetup({ input, start: true, onSaved: id => { taskId = id; },
    request: async (...args) => {
      calls.push(args);
      if (args[0].endsWith('/start')) throw Error('Connection unavailable');
      return { createdTaskId: 'retained' };
    } }), /Connection unavailable/);
  assert.equal(taskId, 'retained');
  await submitTaskSetup({ input, taskId, start: true, request: async (...args) => { calls.push(args); return {}; } });
  assert.equal(calls.filter(row => row[2] === 'POST').length, 1);
  assert.deepEqual(calls[2], ['/api/tasks/retained', input, 'PATCH']);
  assert.equal(calls.filter(row => row[0].endsWith('/start')).length, 2);
});

test('saving a draft does not start inference; failed persistence never starts a batch', async () => {
  const calls = [];
  await submitTaskSetup({ input: {}, request: async (...args) => { calls.push(args); return { createdTaskId: 'draft' }; } });
  assert.equal(calls.length, 1);
  await assert.rejects(submitTaskSetup({ input: {}, start: true, request: async () => { throw Error('Stale materials'); }, onSaved: () => assert.fail('No draft was saved') }), /Stale materials/);
  await assert.rejects(submitTaskSetup({ input: {}, start: true, request: async () => ({ tasks: [{ id: 'unrelated' }] }) }), /草稿已保存/);
});

test('uploaded books expose a direct grading entry and optional settings preserve older drafts', () => {
  const state = emptyState(); state.groups = [{ id: 'a', label: 'A', pageIds: ['p'] }];
  const ctx = { state, selected: new Set(['a']), command: '' };
  assert.match(workflowView(ctx), /data-action="manual-task"[^>]*>开始批改/);
  const form = taskForm(ctx, null, { allowStart: true });
  assert.match(form, /name="supplementalInstructions"/);
  assert.doesNotMatch(form, /name="gradingContext"/);
  assert.match(form, /name="intent" value="start" class="primary" disabled/);
  const existing = taskDraft(state, { groupIds: ['a'], after: 'stop', gradingContext: 'DSE 数学', supplementalInstructions: '用中文反馈', executionMode: 'auto', title: '保留原任务名称' });
  const editing = taskForm(ctx, existing, { allowStart: true });
  assert.match(editing, /name="gradingContext"[^>]*>DSE 数学/);
  assert.match(editing, /name="title" value="保留原任务名称"/);
  const data = new FormData();
  for (const [key, value] of Object.entries({ kind: 'grade', after: 'stop', executionMode: 'auto', gradingContext: existing.gradingContext, supplementalInstructions: existing.supplementalInstructions, title: existing.title })) data.set(key, value);
  data.append('groupIds', 'a');
  const saved = taskDraft(state, taskFormInput(data));
  for (const key of ['gradingContext', 'supplementalInstructions', 'title', 'executionMode', 'after']) assert.equal(saved[key], existing[key]);
});
