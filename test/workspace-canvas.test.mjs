import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';
import { Agent } from '@earendil-works/pi-agent-core';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { digest } from '../src/core.mjs';
import { createRuntime } from '../src/cohort-runtime.mjs';
import { TeacherInteraction, atomicJSON, readQuestions } from '../src/teacher-interaction.mjs';
import { WorkspaceStore, taskDraft, startTask } from '../src/workspace/store.mjs';
import { WorkspaceChat } from '../src/workspace/chat.mjs';
import { WorkspaceRunner } from '../src/workspace/runner.mjs';
import { validateSelections, readSelectionImage } from '../src/workspace/canvas-context.mjs';
import { createWorkspaceAgent, observeWorkspaceAgent } from '../src/workspace/agent.mjs';
import { python } from '../src/workspace/documents.mjs';
import { normalizedPoint, selectionBounds } from '../web/canvas-selection.mjs';

const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
const call = (name, args) => ({ type: 'toolCall', id: crypto.randomUUID(), name, arguments: args });
function offline(contentFactory, before = async () => {}) {
  let turn = 0;
  return (_model, context) => {
    const stream = createAssistantMessageEventStream();
    queueMicrotask(async () => {
      try {
        await before(context);
        const content = contentFactory(turn++, context), message = { role: 'assistant', content, api: model.api, model: model.id, provider: model.provider,
          timestamp: Date.now(), stopReason: content.some(part => part.type === 'toolCall') ? 'toolUse' : 'stop',
          usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
        stream.push({ type: 'done', reason: message.stopReason, message });
      } catch (error) { stream.push({ type: 'error', reason: 'aborted', error: { role: 'assistant', content: [], api: model.api, model: model.id, provider: model.provider, timestamp: Date.now(), stopReason: 'aborted', errorMessage: error.message, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { total: 0 } } } }); }
    });
    return stream;
  };
}
async function until(check) { for (let i = 0; i < 150; i++) { const value = await check(); if (value) return value; await delay(20); } throw Error('Timed out waiting for local test state'); }
async function fixture(t) {
  const directory = await mkdtemp(join(tmpdir(), 'pi-canvas-')); t.after(() => rm(directory, { recursive: true, force: true }));
  const store = await new WorkspaceStore(directory).init(), path = join(directory, 'source.png');
  await promisify(execFile)(python, ['-c', 'from PIL import Image; import sys; im=Image.new("RGB", (40,20), "white"); im.paste("red",(20,0,40,20)); im.save(sys.argv[1])', path]);
  const sha256 = digest(await readFile(path));
  await store.mutate(null, state => {
    state.pages = ['a', 'a-long', 'ms'].map(id => ({ id, path, sha256, role: id === 'ms' ? 'scheme' : 'student', fileName: `${id}.png`, sourcePage: 1, active: true }));
    state.groups = ['a', 'a-long'].map(id => ({ id, label: id, pageIds: [id] }));
    state.schemes = [{ id: 'ms', label: 'MS', pageIds: ['ms'] }];
  });
  const selection = { pageId: 'ms', pageHash: sha256, shape: 'rectangle', rect: { x: .5, y: 0, width: .5, height: 1 } };
  return { directory, store, path, selection };
}
test('canvas coordinates survive zoom, clamping and source crops preserve exact original pixels', async t => {
  const { store, selection } = await fixture(t);
  assert.deepEqual(normalizedPoint(140, 240, { left: 100, top: 200, width: 80, height: 80 }), [.5, .5]);
  assert.deepEqual(normalizedPoint(180, 280, { left: 100, top: 200, width: 160, height: 160 }), [.5, .5]);
  assert.deepEqual(normalizedPoint(0, 900, { left: 100, top: 200, width: 80, height: 80 }), [0, 1]);
  assert.deepEqual(selectionBounds([[.6, .8], [.2, .3]]), { x: .2, y: .3, width: .39999999999999997, height: .5 });
  const [valid] = validateSelections(store.state, [selection], ['a']);
  const image = await readSelectionImage({ ...store.state.pages[2], absolute_path: store.state.pages[2].path, path: 'relative-manifest-page.png' }, valid);
  const result = await promisify(execFile)(python, ['-c', 'from PIL import Image; import io,base64,sys,json; im=Image.open(io.BytesIO(base64.b64decode(sys.argv[1]))); print(json.dumps([im.size, im.getpixel((0,0)), im.getpixel((19,19))]))', image.data]);
  assert.deepEqual(JSON.parse(result.stdout), [[20, 20], [255, 0, 0], [255, 0, 0]]);
  assert.throws(() => validateSelections(store.state, [{ ...selection, pageId: 'a-long' }], ['a']), /范围/);
  assert.throws(() => validateSelections(store.state, [{ ...selection, pageHash: 'changed' }], ['a']), /原页/);
  assert.throws(() => validateSelections(store.state, [{ ...selection, rect: { ...selection.rect, width: .8 } }], ['a']), /区域/);
});
test('actual Pi conversation consumes a source crop and exposes only public tool actions', async t => {
  const { store, selection } = await fixture(t); let ctl; const events = [];
  ctl = createWorkspaceAgent({ model, state: store.snapshot(), selectedIds: ['a'], goal: 'Explain the selection', selections: [selection], readPage: async () => assert.fail('Unexpected full page read'),
    streamFn: offline((turn, context) => {
      if (!turn) return [{ type: 'thinking', thinking: 'private scratchpad' }, call('read_selection', { selectionId: JSON.parse(ctl.prompt.split('Workspace snapshot:\n')[1].split('\nTeacher request:')[0]).selections[0].id })];
      assert.ok(context.messages.some(message => message.role === 'toolResult' && message.content.some(part => part.type === 'image')));
      return [{ type: 'text', text: 'Selected original inspected.' }];
    }) });
  const unsubscribe = observeWorkspaceAgent(ctl.agent, event => events.push(event));
  await ctl.agent.prompt(ctl.prompt); unsubscribe();
  assert.equal(events.filter(event => event.type === 'tool_execution_end')[0].status, 'done');
  assert.ok(!JSON.stringify(events).includes('scratchpad'));
  assert.equal(ctl.proposals.length, 0);
});
test('actual Pi asks a teacher, waits durably, respects pause, then reads the teacher-selected crop', async t => {
  const { directory, store, selection } = await fixture(t), controller = new AbortController();
  const bridge = await new TeacherInteraction(join(directory, 'interaction'), { signal: controller.signal, schemePages: [store.state.pages[2]], students: new Map([['a', [store.state.pages[0]]], ['a-long', [store.state.pages[1]]]]) }).init();
  let turns = 0, selectedId;
  const agent = new Agent({ initialState: { model, systemPrompt: 'Test original source.', tools: [] }, streamFn: offline((turn, context) => {
    turns++;
    if (!turn) return [call('ask_teacher', { question: 'Is this notation accepted?', references: [{ role: 'scheme', page: 1 }] })];
    if (turn === 1) { assert.match(JSON.stringify(context.messages), /The circled note applies/); return [call('read_teacher_selection', { selectionId: selectedId })]; }
    assert.ok(context.messages.some(message => message.role === 'toolResult' && message.content.some(part => part.type === 'image')));
    return [{ type: 'text', text: 'Clarification received.' }];
  }, () => bridge.beforeRequest('ms-review')) });
  const detach = bridge.attach(agent, 'ms-review'); t.after(detach);
  const run = agent.prompt('Inspect source');
  const question = await until(async () => (await readQuestions(bridge.directory))[0]);
  await atomicJSON(join(bridge.directory, 'control.json'), { paused: true, notes: [] });
  const [valid] = validateSelections(store.state, [selection], ['a']); selectedId = valid.id;
  await atomicJSON(join(bridge.directory, 'answers', `${question.id}.json`), { text: 'The circled note applies.', selections: [valid] });
  await until(async () => (await readFile(join(bridge.directory, 'activity.jsonl'), 'utf8')).includes('"paused"'));
  assert.equal(turns, 1); assert.ok(bridge.waitMilliseconds > 0);
  await atomicJSON(join(bridge.directory, 'control.json'), { paused: false, notes: [] });
  await run;
  assert.equal(turns, 3); assert.equal((await readQuestions(bridge.directory))[0].status, 'answered');
  assert.ok(agent.state.tools.some(tool => tool.name === 'ask_teacher'));
  assert.ok(agent.state.messages[0].toolsAdded.some(tool => tool.name === 'ask_teacher'));
});
test('teacher notes and clarification propagation preserve independent MS and student boundaries', async t => {
  const { directory, store, selection } = await fixture(t);
  const bridge = await new TeacherInteraction(join(directory, 'interaction'), { schemePages: [store.state.pages[2]], students: new Map([['a', [store.state.pages[0]]], ['a-long', [store.state.pages[1]]]]) }).init();
  assert.equal(bridge.owner('exception-a-long-Q1'), 'a-long');
  assert.equal(bridge.applies('ms-review', { groupIds: ['a'], text: 'Student mark is 99' }), false);
  assert.equal(bridge.applies('student-a-long', { groupIds: ['a'] }), false);
  assert.equal(bridge.applies('ms-review', { selections: [{ role: 'scheme' }] }), true);
  assert.throws(() => bridge.references('ms-review', [{ role: 'student', page: 1 }]), /outside/);
  await atomicJSON(join(bridge.directory, 'questions', 'other.json'), { id: 'other', status: 'answered', lane: 'student-a', question: 'A only', answer: 'Private student response', references: [{ role: 'student', page: 1 }] });
  const ms = new Agent({ initialState: { model, systemPrompt: 'Source only.', tools: [] }, streamFn: offline(() => [{ type: 'text', text: 'done' }]) });
  const detach = bridge.attach(ms, 'ms-review'); t.after(detach);
  assert.equal(await bridge.preparePrompt(ms, 'MS only'), 'MS only');
  const [valid] = validateSelections(store.state, [selection], ['a']);
  await atomicJSON(join(bridge.directory, 'control.json'), { notes: [{ id: 'note', text: 'Source clarification', groupIds: ['a'], selections: [valid] }] });
  await bridge.recordDelivery('ms-review', { messages: [] });
  assert.equal(await readFile(join(bridge.directory, 'activity.jsonl'), 'utf8').catch(() => ''), '');
  await bridge.recordDelivery('ms-review', { messages: [{ content: '[teacher-note:note]' }] });
  assert.match(await readFile(join(bridge.directory, 'activity.jsonl'), 'utf8'), /note_delivered/);
});
test('async chat keeps source selection, does not leak hidden reasoning and cannot save stale proposals or late cancellation', async t => {
  const { store, selection } = await fixture(t); let release, captured;
  const chat = new WorkspaceChat(store, { configured: () => true, model: model.id, agent: options => { captured = options; return new Promise(resolve => { release = resolve; }); } });
  await chat.start({ revision: store.state.revision, goal: 'Read this only', selectedIds: ['a'], selections: [selection] });
  assert.equal(chat.snapshot().status, 'running'); assert.equal(captured.selections[0].pageId, 'ms');
  captured.onEvent({ type: 'tool_execution_start', key: 'read', label: '查看圈选原文' });
  assert.equal(chat.snapshot().events.length, 1);
  const promise = chat.active.promise; chat.cancel(); release({ text: 'Late success', proposals: [], documents: [] }); await promise;
  assert.equal(store.state.conversation.at(-1).status, 'cancelled');
  await chat.start({ materialRevision: store.state.materialRevision, revision: 0, goal: 'Plan selected only', selectedIds: ['a'], selections: [selection] });
  const next = chat.active.promise; await store.mutate(null, state => { state.materialRevision++; });
  release({ text: 'Started', proposals: [{ goal: 'test', kind: 'assist', groupIds: ['a'], schemeId: null, after: 'review' }] }); await next;
  assert.equal(store.state.tasks.length, 0); assert.equal(store.state.conversation.at(-1).status, 'failed');
});
test('runtime pause prevents admission and cancellation releases the waiting request', async t => {
  const { directory } = await fixture(t), controller = new AbortController();
  const bridge = await new TeacherInteraction(join(directory, 'interaction'), { signal: controller.signal }).init();
  await atomicJSON(join(bridge.directory, 'control.json'), { paused: true, notes: [] });
  let provider;
  const runtime = createRuntime({ models: { streamSimple: (_model, _context, options) => { provider = options; return {}; } }, model, output: directory, controller, cap: 1, interaction: bridge });
  t.after(() => runtime.close()); const io = await runtime.io('student-a', () => 'student_grading'); io.streamFn(model, {}, {});
  const pending = provider.onPayload({ messages: [] });
  await until(() => bridge.waiting.size > 0); assert.equal(runtime.budget.requests.length, 0);
  controller.abort(); await assert.rejects(pending); assert.equal(runtime.budget.requests.length, 0);
});
test('Pi can arrange multiple batches over successive tool turns while retaining the selected scope', async t => {
  const { store } = await fixture(t);
  const ctl = createWorkspaceAgent({ model, state: store.snapshot(), selectedIds: ['a', 'a-long'], goal: 'Two separate batches', readPage: async () => assert.fail('No pages requested'),
    streamFn: offline(turn => turn < 2 ? [call('create_task_draft', { title: `Batch ${turn + 1}`, goal: 'Check sources', kind: 'assist', groupIds: [turn ? 'a-long' : 'a'], schemeId: 'ms', after: 'review' })] : [{ type: 'text', text: 'Two drafts, neither started.' }]) });
  await ctl.agent.prompt(ctl.prompt);
  assert.deepEqual(ctl.proposals.map(row => row.groupIds), [['a'], ['a-long']]);
  assert.ok(ctl.proposals.every(row => row.status === 'draft'));
});
test('runner answers are single-use, source-scoped, and preserve saved grades', async t => {
  const { directory, store, selection } = await fixture(t);
  const task = await store.mutate(null, state => { const draft = taskDraft(state, { goal: 'Review source', kind: 'grade', groupIds: ['a', 'a-long'], schemeId: 'ms', after: 'review' }); state.tasks.push(draft); return startTask(state, draft.id); });
  const bridge = await new TeacherInteraction(join(directory, 'runs', task.id, 'interaction')).init();
  await atomicJSON(join(bridge.directory, 'control.json'), { notes: [], paused: false });
  await atomicJSON(join(bridge.directory, 'questions', 'q.json'), { id: 'q', lane: 'ms-review', status: 'open', references: [{ role: 'scheme', page: 1 }], question: 'Source?', createdAt: new Date().toISOString() });
  const runner = new WorkspaceRunner(store); runner.active.set(task.id, { interaction: bridge.directory });
  await assert.rejects(runner.control(task.id, 'answer', { text: 'Wrong lane', questionId: 'q', selections: [{ ...selection, pageId: 'a' }] }), /不属于当前问题/);
  await runner.control(task.id, 'answer', { text: 'Source-only clarification', questionId: 'q', selections: [selection] });
  await assert.rejects(runner.control(task.id, 'answer', { text: 'Duplicate', questionId: 'q' }), /已提交/);
  assert.equal(store.state.tasks[0].records.length, 0);
  assert.equal(store.state.conversation.at(-1).selections[0].pageId, 'ms');
});
