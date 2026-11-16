import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { Agent } from '@earendil-works/pi-agent-core';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { digest } from '../src/core.mjs';
import { freezeRubric, createCoordinator } from '../src/cohort-core.mjs';
import { applyMSReview } from '../src/ms-review.mjs';
import { TeacherInteraction, atomicJSON, readJSON } from '../src/teacher-interaction.mjs';
import { WorkspaceStore, emptyState, taskDraft, startTask, executionMode } from '../src/workspace/store.mjs';
import { WorkspaceRunner } from '../src/workspace/runner.mjs';
import { WorkspaceChat } from '../src/workspace/chat.mjs';
import { createWorkspaceServer } from '../src/workspace/server.mjs';
import { addDocument, saveDocument, readDocument, addAnnotation, updateAnnotation, resolveReferences } from '../src/workspace/editable-documents.mjs';
import { validateGuideApproval, markingGuideMarkdown } from '../src/marking-guide.mjs';
import { createWorkspaceAgent } from '../src/workspace/agent.mjs';
import { bindSelection } from '../web/canvas-selection.mjs';

const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
const call = (name, args) => ({ type: 'toolCall', id: crypto.randomUUID(), name, arguments: args });
function offline(turns) {
  return () => {
    const stream = createAssistantMessageEventStream(), content = turns.shift() || [{ type: 'text', text: 'Done' }];
    const message = { role: 'assistant', content, api: model.api, model: model.id, provider: model.provider, timestamp: Date.now(),
      stopReason: content.some(part => part.type === 'toolCall') ? 'toolUse' : 'stop', usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { total: 0 } } };
    queueMicrotask(() => stream.push({ type: 'done', reason: message.stopReason, message })); return stream;
  };
}
async function until(check) { for (let i = 0; i < 150; i++) { if (await check()) return; await delay(20); } throw Error('Local fixture timed out'); }
const fixture = () => ({ ...emptyState(), pages: ['a', 'b', 'ms'].map(id => ({ id, role: id === 'ms' ? 'scheme' : 'student', sha256: digest(id), fileName: `${id}.png`, sourcePage: 1 })),
  groups: ['a', 'b'].map(id => ({ id, label: id, pageIds: [id] })), schemes: [{ id: 'ms', label: 'MS', pageIds: ['ms'] }] });
const scheme = { sha256: 'source-only', pages: [{ page: 1, role: 'scheme' }] };
const frozen = () => freezeRubric({ general_instructions: [{ text: 'Use the source conditions.', source_pages: [1] }], unresolved_notes: [],
  items: [{ question_id: 'R', item_id: 'R(a)', max_score: 1, criteria: 'Explain the required relation.', source_pages: [1], related_item_ids: [], requires_source_image: false, image_reason: '', uncertainties: [],
    scoring_points: [{ point_id: 'P', max_score: 1, award_type: 'A', source_text: 'Explain the relation', condition: 'An explanation of the required relation', allowed_awards: [0, 1], depends_on: [], source_pages: [1] }],
    routes: [{ route_id: 'ordinary', point_ids: ['P'], description: 'One complete explanation' }] }] }, scheme, new Set([1]));
async function temporary(t) { const directory = await mkdtemp(join(tmpdir(), 'pi-documents-')); t.after(() => rm(directory, { force: true, recursive: true })); return directory; }

test('editable documents keep exact prior revisions, reject stale writers, and bind quotes to the correct source scope', () => {
  for (const title of ['说明.md', 'Renamed.md', '其他科目.txt']) {
    const state = fixture(), document = addDocument(state, { title, body: '# 说明\n保留原文，接受符合来源的其他表述。', sourcePageIds: ['a'] });
    const start = document.body.indexOf('保留'), target = { kind: 'text', documentId: document.id, revision: 1, documentHash: document.hash, start, end: document.body.length, quote: document.body.slice(start) };
    const note = addAnnotation(state, { target, text: '请核对这个条件' });
    saveDocument(state, document.id, { revision: 1, body: document.body + '\n新增说明' });
    assert.equal(readDocument(state, document.id, 1).body, document.body);
    assert.equal(resolveReferences(state, [{ annotationId: note.id }], ['a'])[0].target.quote, target.quote);
    assert.throws(() => resolveReferences(state, [{ annotationId: note.id }], ['b']), /范围/);
    assert.throws(() => saveDocument(state, document.id, { revision: 1, body: 'overwrite' }), /新版本/);
    assert.throws(() => addAnnotation(state, { target: { ...target, quote: 'invented evidence' }, text: 'bad' }), /不一致/);
    assert.throws(() => addAnnotation(state, { target: { ...target, documentHash: 'wrong' }, text: 'bad' }), /改变/);
  }
});
test('multiple independent freehand annotations preserve drawn paths and removing one preserves the others', () => {
  const state = fixture(), points = [[.1,.2],[.15,.12],[.5,.2],[.4,.35],[.1,.2]];
  const target = { kind: 'page', pageId: 'ms', pageHash: digest('ms'), shape: 'lasso', rect: { x: .1, y: .12, width: .4, height: .23 }, points };
  const a = addAnnotation(state, { target, text: 'First condition' }), b = addAnnotation(state, { target, text: 'Second condition' });
  assert.deepEqual(a.target.points, points); assert.notEqual(a.id, b.id);
  updateAnnotation(state, a.id, { archive: true });
  assert.throws(() => resolveReferences(state, [{ annotationId: a.id }], []), /移除/);
  assert.equal(resolveReferences(state, [{ annotationId: b.id }], [])[0].comment, 'Second condition');
  assert.equal(state.annotations.length, 2);
});
test('freehand pointer gestures retain concave paths at different zoom levels instead of fitting an ellipse', () => {
  const previousWindow = globalThis.window, previousObserver = globalThis.ResizeObserver;
  globalThis.window = { devicePixelRatio: 2 }; globalThis.ResizeObserver = class { observe() {} disconnect() {} };
  try {
    const path = [[.1,.2],[.2,.1],[.65,.15],[.6,.5],[.3,.3],[.1,.2]];
    for (const scale of [1, 1.5]) {
      const handlers = new Map(), bounds = { left: 100, top: 200, width: 400 * scale, height: 600 * scale };
      const context = { setTransform() {}, clearRect() {}, setLineDash() {}, beginPath() {}, moveTo() {}, lineTo() {}, closePath() {}, fill() {}, stroke() {} };
      const canvas = { style: {}, getContext: () => context, getBoundingClientRect: () => bounds, setPointerCapture() {}, releasePointerCapture() {}, hasPointerCapture: () => false, addEventListener: (name, fn) => handlers.set(name, fn), removeEventListener: name => handlers.delete(name) };
      let selected;
      const binding = bindSelection(canvas, { getPage: () => ({ id: 'source', sha256: 'bound' }), getMode: () => 'lasso', getSelections: () => [], onSelect: result => { selected = result; } });
      const event = ([x, y]) => ({ button: 0, pointerId: 1, clientX: bounds.left + x * bounds.width, clientY: bounds.top + y * bounds.height, preventDefault() {} });
      handlers.get('pointerdown')(event(path[0])); for (const point of path.slice(1, -1)) handlers.get('pointermove')(event(point)); handlers.get('pointerup')(event(path.at(-1)));
      assert.equal(selected.shape, 'lasso'); assert.deepEqual(selected.points, path); assert.equal(selected.pageId, 'source');
      binding.destroy(); assert.equal(handlers.size, 0);
    }
  } finally { globalThis.window = previousWindow; globalThis.ResizeObserver = previousObserver; }
});
test('reusing a teacher-edited guide preserves the document verbatim instead of nesting past guides', () => {
  const prior = '# 实施说明\n老师自己的编排与原始引用。';
  assert.equal(markingGuideMarkdown(frozen(), '本批次核对完整来源。', { body: prior }), prior);
});
test('Pi document edits require a read version and respect simultaneous teacher changes', async t => {
  const store = await new WorkspaceStore(await temporary(t)).init(); let document;
  await store.mutate(null, state => { Object.assign(state, fixture()); document = addDocument(state, { body: '第一段保留。\n第二段修改。', sourcePageIds: ['ms'] }); });
  const ctl = createWorkspaceAgent({ model, state: store.snapshot(), selectedIds: [], goal: '修改第二段', readPage: async () => {},
    documentIO: { read: async id => readDocument(store.state, id), save: (id, input) => store.mutate(null, state => saveDocument(state, id, input, 'agent')), create: input => store.mutate(null, state => addDocument(state, input, 'agent')) },
    streamFn: offline([[call('read_document', { documentId: document.id })], [call('edit_document', { documentId: document.id, revision: 1, body: '第一段保留。\n第二段补充实施条件。' })]]) });
  await ctl.agent.prompt(ctl.prompt); assert.equal(readDocument(store.state, document.id).body, '第一段保留。\n第二段补充实施条件。');
  const tool = ctl.agent.state.tools.find(tool => tool.name === 'edit_document');
  await store.mutate(null, state => saveDocument(state, document.id, { revision: 2, body: '老师最新修改' }));
  await assert.rejects(tool.execute('stale', { documentId: document.id, revision: 2, body: 'overwritten' }), /新版本/);
  assert.equal(readDocument(store.state, document.id).body, '老师最新修改');
});
test('main Pi waits for an editable guide; a teacher edit is frozen for dispatch and later edits cannot change it', async t => {
  const directory = await temporary(t), store = await new WorkspaceStore(directory).init();
  const task = await store.mutate(null, state => {
    Object.assign(state, fixture()); const draft = taskDraft(state, { goal: 'Grade selected', kind: 'grade', groupIds: ['a'], schemeId: 'ms', after: 'review' });
    state.tasks.push(draft); return startTask(state, draft.id);
  });
  const interaction = join(directory, 'runs', task.id, 'interaction'), controller = new AbortController();
  t.after(() => controller.abort(Error('Fixture cleanup')));
  const bridge = await new TeacherInteraction(interaction, { signal: controller.signal, schemePages: [store.state.pages[2]], students: new Map([['a', [store.state.pages[0]]]]) }).init();
  await atomicJSON(join(interaction, 'control.json'), { notes: [], paused: false });
  const runner = new WorkspaceRunner(store); runner.active.set(task.id, { interaction });
  const childInputs = [], candidate = frozen();
  const rubric = applyMSReview({ summary: 'Synthetic source verification', item_checks: [{ item_id: 'R(a)', verdict: 'verified', source_pages: [1], note: 'Bound to fixture source' }],
    revised_items: [], removed_items: [], general_instructions: null, unresolved_notes: null }, candidate, scheme, new Set([1])).frozen;
  const main = createCoordinator({ model, scheme, studentIds: ['a'], reusedRubric: rubric, log: async () => {}, readImage: async () => assert.fail('No source reload'),
    persistRubric: async () => {}, persistCohort: async () => {}, publishMarkingGuide: (frozen, text) => bridge.publishGuide(frozen, text),
    executeStudent: async (_id, _rubric, _pages, guide) => {
      childInputs.push(guide);
      const child = new Agent({ initialState: { model, systemPrompt: 'Synthetic student', tools: [] } }); const detach = bridge.attach(child, 'student-a');
      const prompt = JSON.stringify(await bridge.preparePrompt(child, 'Grade this book')); detach();
      assert.ok(prompt.includes('老师编辑后的执行说明')); assert.ok(!prompt.includes('此后再次修改'));
      return { status: 'submitted' };
    }, streamFn: offline([[call('grade_students', { student_ids: ['a'], concurrency: 1, initial_ms_pages: [] })],
      [call('publish_marking_guide', { implementation: '先核对证据归属，再检查完整条件。' })],
      [call('grade_students', { student_ids: ['a'], concurrency: 1, initial_ms_pages: [] })], [call('finish_cohort', {})]]) });
  const work = main.agent.prompt(main.initialPrompt);
  await until(() => readJSON(join(interaction, 'guide-proposal.json')));
  await until(() => bridge.waiting.size === 1);
  assert.equal(childInputs.length, 0); assert.equal(bridge.waiting.size, 1);
  await runner.syncGuide(task);
  const doc = store.state.documents[0];
  await store.mutate(null, state => { state.executionMode = 'auto'; });
  await runner.syncGuide(task);
  assert.equal(childInputs.length, 0, 'changing a future-task preference cannot authorize an existing review batch');
  await assert.rejects(runner.approveGuide(doc.id, { revision: 1, hash: doc.hash }, 'automatic'), /老师确认/);
  assert.ok(doc.body.includes('Explain the relation')); assert.ok(doc.body.includes('#ms-page-1'));
  await store.mutate(null, state => saveDocument(state, doc.id, { revision: 1, body: doc.body + '\n老师编辑后的执行说明' }));
  await runner.syncGuide(task); assert.equal(store.state.documents[0].revision, 2);
  await assert.rejects(runner.approveGuide(doc.id, { revision: 1, hash: doc.hash }), /更新/);
  const approved = readDocument(store.state, doc.id);
  await runner.approveGuide(doc.id, { revision: 2, hash: approved.hash });
  await store.mutate(null, state => saveDocument(state, doc.id, { revision: 2, body: approved.body + '\n此后再次修改' }));
  await assert.rejects(runner.approveGuide(doc.id, { revision: 3, hash: readDocument(store.state, doc.id).hash }), /之前确认/);
  await work;
  assert.equal(childInputs.length, 1); assert.equal(childInputs[0].revision, 2);
  assert.equal(bridge.waiting.size, 0); assert.ok(main.getResult());
  const saved = await readJSON(join(interaction, 'guide-approval.json')), proposal = await readJSON(join(interaction, 'guide-proposal.json'));
  assert.equal(saved.body, approved.body);
  assert.equal(saved.method, 'teacher');
  assert.throws(() => validateGuideApproval({ ...saved, method: 'automatic' }, proposal), /requires teacher confirmation/);
  assert.throws(() => validateGuideApproval({ ...saved, body: 'changed after approval' }, proposal), /does not match/);
  assert.equal(readDocument((await new WorkspaceStore(directory).init()).state, doc.id).revision, 3);
});
test('automatic mode is explicit per task; legacy and unspecified tasks require review', () => {
  const state = fixture(), input = { goal: 'Grade selected', kind: 'grade', groupIds: ['a'], schemeId: 'ms', after: 'review' };
  const reviewed = taskDraft(state, input); state.tasks.push(reviewed);
  assert.equal(reviewed.executionMode, 'review');
  state.executionMode = 'auto';
  assert.equal(taskDraft(state, input).executionMode, 'auto');
  assert.equal(taskDraft(state, { ...input, executionMode: 'review' }).executionMode, 'review');
  assert.equal(startTask(state, reviewed.id).executionMode, 'review');
  reviewed.status = 'completed';
  const legacy = taskDraft(state, input); delete legacy.executionMode; state.tasks.push(legacy);
  assert.equal(startTask(state, legacy.id).executionMode, 'review');
  assert.throws(() => executionMode('all-access'), /授权/);
});
test('automatic authorization freezes the generated guide before the real coordinator dispatches students', async t => {
  const directory = await temporary(t), store = await new WorkspaceStore(directory).init();
  const task = await store.mutate(null, state => {
    Object.assign(state, fixture());
    const draft = taskDraft(state, { goal: 'Grade selected', kind: 'grade', groupIds: ['a'], schemeId: 'ms', after: 'review', executionMode: 'auto' });
    state.tasks.push(draft); return startTask(state, draft.id);
  });
  const interaction = join(directory, 'runs', task.id, 'interaction');
  const bridge = await new TeacherInteraction(interaction, { schemePages: [store.state.pages[2]], students: new Map([['a', [store.state.pages[0]]]]) }).init();
  await atomicJSON(join(interaction, 'control.json'), { notes: [], paused: false, executionMode: task.executionMode, supplementalInstructions: '用中文解释扣分原因。' });
  const runner = new WorkspaceRunner(store); runner.active.set(task.id, { interaction });
  const rubric = applyMSReview({ summary: 'Synthetic source verification', item_checks: [{ item_id: 'R(a)', verdict: 'verified', source_pages: [1], note: 'Bound to fixture source' }],
    revised_items: [], removed_items: [], general_instructions: null, unresolved_notes: null }, frozen(), scheme, new Set([1])).frozen;
  const children = [];
  const main = createCoordinator({ model, scheme, studentIds: ['a'], reusedRubric: rubric, log: async () => {}, readImage: async () => assert.fail('No source reload'),
    persistRubric: async () => {}, persistCohort: async () => {}, publishMarkingGuide: (frozen, text) => bridge.publishGuide(frozen, text),
    executeStudent: async (_id, _rubric, _pages, guide) => { children.push(guide); return { status: 'submitted' }; },
    streamFn: offline([[call('grade_students', { student_ids: ['a'], concurrency: 1, initial_ms_pages: [] })],
      [call('review_grading_requirements', { decision: 'compatible', explanation: '只影响反馈语言，不改变 MS 给分规则。', question: '', adjustedInstructions: '' })],
      [call('publish_marking_guide', { implementation: 'Use source-bound conditions without guessing.' })],
      [call('grade_students', { student_ids: ['a'], concurrency: 1, initial_ms_pages: [] })], [call('finish_cohort', {})]]) });
  const detach = bridge.attach(main.agent, 'main'); t.after(detach);
  const work = main.agent.prompt(await bridge.preparePrompt(main.agent, main.initialPrompt));
  await until(() => readJSON(join(interaction, 'guide-proposal.json')));
  assert.equal(children.length, 0);
  await runner.syncGuide(task);
  assert.equal(store.state.documents.length, 1); assert.equal(children.length, 0);
  await store.mutate(null, state => { state.executionMode = 'review'; });
  await runner.syncGuide(task); await work;
  assert.equal(children.length, 1); assert.equal(children[0].method, 'automatic');
  assert.match(children[0].body, /用中文解释扣分原因/);
  assert.equal(children[0].hash, store.state.documents[0].hash);
  assert.equal(children[0].body, readDocument(store.state, store.state.documents[0].id).body);
  assert.equal(store.state.documents[0].approvals[0].method, 'automatic');
  assert.ok(main.getResult());
});
test('alignment conversation gets the canonical editable document without granting dispatch authority', async t => {
  const store = await new WorkspaceStore(await temporary(t)).init(); let guide, unrelated;
  await store.mutate(null, state => {
    Object.assign(state, fixture());
    guide = addDocument(state, { title: '评分实施.md', body: 'Source-only guide', sourcePageIds: ['ms'], kind: 'marking_guide' });
    unrelated = addDocument(state, { title: 'B 答卷', body: 'B only', sourcePageIds: ['b'] });
  });
  let received;
  const chat = new WorkspaceChat(store, { model: model.id, configured: () => true, agent: async args => { received = args; return { text: 'Discussed', proposals: [] }; } });
  await chat.start({ materialRevision: 0, selectedIds: ['a'], goal: '先讨论评分要求', documentId: guide.id }); await chat.active.promise;
  assert.ok(received.goal.includes(guide.id)); assert.ok(received.goal.includes('not permission to approve or dispatch'));
  assert.equal(store.state.tasks.length, 0); assert.equal(readDocument(store.state, guide.id).revision, 1);
  await assert.rejects(chat.start({ materialRevision: 0, selectedIds: ['a'], goal: 'Read other', documentId: unrelated.id }), /范围/);
});
test('teacher text comments reach chat and stay out of unrelated student and source-only lanes', async t => {
  const store = await new WorkspaceStore(await temporary(t)).init();
  let note;
  await store.mutate(null, state => {
    Object.assign(state, fixture()); const doc = addDocument(state, { body: 'Only A evidence', sourcePageIds: ['a'] });
    note = addAnnotation(state, { text: '检查这里', target: { kind: 'text', documentId: doc.id, revision: 1, documentHash: doc.hash, start: 0, end: doc.body.length, quote: doc.body } });
  });
  let received;
  const chat = new WorkspaceChat(store, { model: model.id, configured: () => true, agent: async args => { received = args.references; return { text: 'Read', proposals: [] }; } });
  await chat.start({ materialRevision: 0, selectedIds: ['a'], goal: '针对注释处理', references: [{ annotationId: note.id }] }); await chat.active.promise;
  assert.equal(received[0].target.quote, 'Only A evidence'); assert.equal(received[0].comment, '检查这里');
  const bridge = await new TeacherInteraction(join(store.directory, 'bridge'), { schemePages: [store.state.pages[2]], students: new Map([['a', [store.state.pages[0]]], ['b', [store.state.pages[1]]]]) }).init();
  const teacherNote = { text: 'Read applicable note', groupIds: ['a', 'b'], references: received };
  assert.equal(bridge.applies('ms-review', teacherNote), false);
  assert.equal(bridge.noteContext('student-b', teacherNote).documentReferences.length, 0);
  assert.equal(bridge.noteContext('student-a', teacherNote).documentReferences[0].target.quote, 'Only A evidence');
});
test('HTTP document editing, exact-version export and annotation persistence work without a model connection', async t => {
  const directory = await temporary(t), app = await createWorkspaceServer({ directory, port: 0, configured: () => false }); t.after(() => app.close());
  const base = `http://127.0.0.1:${app.server.address().port}`, { token } = await (await fetch(base + '/api/state')).json();
  const mutate = async (path, body, method = 'POST') => {
    const response = await fetch(base + path, { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token }, body: JSON.stringify(body) });
    return { status: response.status, result: await response.json() };
  };
  const created = await mutate('/api/documents', { title: '教学计划.md', body: '# 初稿\n需要澄清的条件' });
  assert.equal(created.status, 201); const doc = created.result.document;
  const changed = await mutate(`/api/documents/${doc.id}`, { revision: 1, body: doc.body + '\n已补充说明' }, 'PATCH');
  assert.equal(changed.result.document.revision, 2);
  app.chat.active = { controller: new AbortController(), visible: { id: 'editing', events: [] }, promise: Promise.resolve() };
  const whileEditing = await mutate(`/api/documents/${doc.id}/approve`, { revision: 2, hash: changed.result.document.hash });
  app.chat.active = null;
  assert.equal(whileEditing.status, 409); assert.match(whileEditing.result.error, /仍在调整文档/);
  assert.equal((await mutate(`/api/documents/${doc.id}`, { revision: 1, body: 'stale' }, 'PATCH')).status, 409);
  const download = await fetch(`${base}/api/documents/${doc.id}?revision=1&download`);
  assert.equal(await download.text(), doc.body); assert.match(download.headers.get('content-disposition'), /attachment/);
  const annotated = await mutate('/api/annotations', { text: '这里需要具体依据', target: { kind: 'text', documentId: doc.id, revision: 1, documentHash: doc.hash, start: 5, end: doc.body.length, quote: doc.body.slice(5) } });
  assert.equal(annotated.status, 201);
  const annotationId = annotated.result.annotation.id;
  const updated = await mutate(`/api/annotations/${annotationId}`, { text: '请将这处依据写入实施文档' }, 'PATCH');
  assert.equal(updated.status, 200); assert.equal(updated.result.annotation.id, annotationId);
  assert.equal(updated.result.annotation.text, '请将这处依据写入实施文档');
  assert.equal(updated.result.conversation.length, 0, 'saving a comment must not start an agent conversation');
  assert.equal(created.result.executionMode, 'review');
  const automatic = await mutate('/api/execution-mode', { mode: 'auto', revision: updated.result.revision }, 'PATCH');
  assert.equal(automatic.result.executionMode, 'auto');
  assert.equal((await mutate('/api/execution-mode', { mode: 'unknown', revision: automatic.result.revision }, 'PATCH')).status, 422);
  assert.equal((await mutate('/api/execution-mode', { mode: 'review', revision: automatic.result.revision }, 'PATCH')).result.executionMode, 'review');
  const loaded = await new WorkspaceStore(directory).init(); assert.equal(loaded.state.annotations.length, 1); assert.equal(loaded.state.documents[0].history.length, 2);
  assert.equal(resolveReferences(loaded.state, [{ annotationId }])[0].comment, updated.result.annotation.text);
  for (const file of ['workspace-canvas.mjs', 'workspace-canvas.css', 'document-editor.mjs']) assert.equal((await fetch(`${base}/${file}`)).status, 200);
});
