import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { digest } from '../src/core.mjs';
import { WorkspaceStore, taskDraft, publicState } from '../src/workspace/store.mjs';
import { WorkspaceRunner } from '../src/workspace/runner.mjs';
import { reviewView } from '../web/review.mjs';

async function setup(t, agent) {
  const directory = await mkdtemp(join(tmpdir(), 'pi-workspace-runner-'));
  const previous = process.env.OPENROUTER_API_KEY;
  process.env.OPENROUTER_API_KEY = 'synthetic-test-only-no-network';
  t.after(async () => {
    if (previous === undefined) delete process.env.OPENROUTER_API_KEY;
    else process.env.OPENROUTER_API_KEY = previous;
    await rm(directory, { recursive: true, force: true });
  });
  const store = await new WorkspaceStore(directory).init();
  const pages = [];
  for (const id of ['a', 'b']) {
    const bytes = Buffer.from(`immutable-${id}`), path = join(directory, `${id}.png`);
    await writeFile(path, bytes);
    pages.push({ id, path, sha256: digest(bytes), role: 'student', sourceId: id, sourcePage: 1 });
  }
  await store.mutate(0, state => {
    state.pages = pages;
    state.groups = pages.map(page => ({ id: page.id, label: page.id, pageIds: [page.id] }));
    state.tasks.push(taskDraft(state, { kind: 'assist', groupIds: ['a'], goal: 'Check A only', after: 'review' }));
  });
  const runner = new WorkspaceRunner(store, { agent });
  t.after(() => runner.close());
  return { runner, store, taskId: store.state.tasks[0].id };
}

test('free-task runner supplies only the frozen scope and persists its document without grading', async t => {
  let called = 0;
  const f = await setup(t, async input => {
    called++;
    assert.deepEqual(input.state.groups.map(group => group.id), ['a']);
    assert.deepEqual(input.state.pages.map(page => page.id), ['a']);
    assert.deepEqual(input.records.map(record => record.id), ['own-result']);
    assert.equal(input.mode, 'work');
    return { documents: [{ id: 'doc', title: 'Source checklist', body: 'A is readable.', references: ['a'] }], usage: {} };
  });
  await f.store.mutate(null, state => {
    state.tasks.push({ id: 'old-boundary', groups: [{ id: 'a', pageIds: ['a', 'b'] }], records: [{ id: 'other-scope-result', groupId: 'a' }], status: 'completed' });
    state.tasks.push({ id: 'same-boundary', groups: [{ id: 'a', pageIds: ['a'] }], records: [{ id: 'own-result', groupId: 'a' }], status: 'completed' });
  });
  await f.runner.start(f.taskId, f.store.state.revision);
  await f.runner.active.get(f.taskId).promise;
  const task = f.store.state.tasks[0];
  assert.equal(called, 1); assert.equal(task.status, 'needs_review');
  assert.equal(task.records.length, 0); assert.equal(task.artifacts[0].title, 'Source checklist');
  const manifest = JSON.parse(await readFile(join(f.store.directory, 'runs', f.taskId, 'cohort.json'), 'utf8'));
  assert.deepEqual(manifest.students.map(student => student.id), ['a']);
  const reloaded = await new WorkspaceStore(f.store.directory).init();
  assert.equal(reloaded.state.tasks[0].artifacts[0].id, 'doc');
  await assert.rejects(f.runner.start(f.taskId, f.store.state.revision), /重复/);
});

test('cancelled free work cannot become a success if its agent resolves late', async t => {
  let agentEntered;
  const entered = new Promise(resolve => { agentEntered = resolve; });
  const f = await setup(t, async ({ controller }) => {
    agentEntered();
    await new Promise(resolve => controller.signal.addEventListener('abort', resolve, { once: true }));
    return { documents: [{ id: 'late', title: 'Late', body: 'late', references: ['a'] }], usage: {} };
  });
  await f.runner.start(f.taskId, f.store.state.revision);
  const finished = f.runner.active.get(f.taskId).promise;
  await entered; f.runner.cancel(f.taskId); await finished;
  assert.equal(f.store.state.tasks[0].status, 'cancelled');
  assert.deepEqual(f.store.state.tasks[0].artifacts, []);
});

test('review without known award choices retains the original and disables accidental replacement', async t => {
  const f = await setup(t, async () => { throw Error('unused'); });
  f.store.state.tasks[0].records.push({ id: 'unknown', student: 'A', itemId: 'Q1', score: 2, maximum: null,
    allowedAwards: [], studentPageIds: [], schemePageIds: [], reviewRequired: true, reason: 'No usable award range.' });
  const html = reviewView({ state: publicState(f.store.state, false), reviewIndex: 0, sourcePage: {}, reviewDrafts: {} });
  assert.match(html, /原判断 <strong[^>]*>2 分/);
  assert.match(html, /评分范围尚未确定/);
  assert.match(html, /disabled>保存复核/);
});
