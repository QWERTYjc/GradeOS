import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile, readFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { emptyState, taskDraft, startTask, WorkspaceStore } from '../src/workspace/store.mjs';
import { createAdaptiveCoordinator, createAdaptiveStudent } from '../src/workspace/adaptive-agents.mjs';
import { validatePlan, validateAdaptiveGrade } from '../src/workspace/adaptive-contract.mjs';
import { createGradingResearch, publicAddress, referenceURL } from '../src/workspace/grading-research.mjs';
import { runAdaptiveGrading, usesAdaptiveGrading, adaptiveRecords, adaptiveReport } from '../src/workspace/adaptive-runtime.mjs';
import { WorkspaceRunner } from '../src/workspace/runner.mjs';
import { prepareTaskInput } from '../src/workspace/documents.mjs';
import { atomicJSON } from '../src/teacher-interaction.mjs';
import { digest } from '../src/core.mjs';
import { applyReferenceReview, taskOnlyInput } from '../src/workspace/reference-audit.mjs';
import { taskForm } from '../web/tasks.mjs';
import { materialView } from '../web/materials.mjs';
import { createWorkspaceAgent } from '../src/workspace/agent.mjs';

function task({ scheme = false, question = true, groups = ['a'] } = {}) {
  const state = emptyState();
  state.pages = [...(scheme ? [{ id: 'ms', role: 'scheme' }] : []), ...(question ? [{ id: 'qp', role: 'question' }] : []), ...groups.map(id => ({ id: `page-${id}`, role: 'student' }))].map(page => ({ ...page, sourcePage: 1, sourceId: page.id, sha256: digest(page.id) }));
  state.groups = groups.map(id => ({ id, label: id, pageIds: [`page-${id}`] }));
  if (scheme) state.schemes.push({ id: 'ms', label: 'Standard', pageIds: ['ms'] });
  if (question) state.questions.push({ id: 'qp', label: 'Questions', pageIds: ['qp'] });
  const draft = taskDraft(state, { kind: 'grade', goal: '按材料批改', groupIds: groups, schemeId: scheme ? 'ms' : null, questionId: question ? 'qp' : null, after: 'stop', executionMode: 'auto' });
  state.tasks.push(draft);
  return { state, task: startTask(state, draft.id) };
}
const criterion = (overrides = {}) => ({ id: 'part-alpha', groupIds: ['a'], question: 'Find the quantity described in the printed task.', questionStatus: 'complete', basis: 'derived_question', sourcePageIds: ['qp'], disposition: 'score', maxScore: 2, allowedAwards: [0, 1, 2], scaleBasis: 'source', scaleQuote: '[2 marks]', scalePageIds: ['qp'], referenceAnswer: 'An independently established reference solution.', criteria: 'Correct method and supported conclusion; equivalent methods accepted.', rationale: 'The question fixes the total; this credit policy is derived, not official.', uncertainties: [], webReferenceIds: [], ...overrides });
const plan = (items = [criterion()], coverage = [{ groupId: 'a', status: 'complete', reason: 'The complete question is supplied.' }]) => ({ subject: 'quantitative', examSystem: 'unknown', implementation: 'Check task meaning before scoring.', items, coverage });
const decision = (overrides = {}) => ({ id: 'part-alpha', score: 2, verdict: 'supported', reason: 'The recorded work satisfies the criterion.', evidence: 'Literal work on the page.', studentPageIds: ['page-a'], reviewRequired: false, uncertainties: [], referenceCheck: { status: 'consistent', observation: 'The visible reasoning satisfies the original task.' }, ...overrides });
function reviewed(value) {
  const derivation = { inputHash: digest(taskOnlyInput(value)), items: value.plan.items.map(i => ({ id: i.id, status: 'established' })) };
  return applyReferenceReview(value, derivation, { candidateHash: value.hash, derivationHash: digest(derivation), items: value.plan.items.map(i => ({
    id: i.id, status: 'confirmed', sourceFaithful: true, referenceAnswer: i.referenceAnswer, criteria: i.criteria, checks: [{ method: 'Independent relation', observation: 'The conclusion satisfies the stated relation.' }], findings: [] })) });
}
const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
const toolCall = (name, args) => ({ type: 'toolCall', id: crypto.randomUUID(), name, arguments: args });
function stream(next) {
  return (selectedModel, context) => {
    const content = next(context, selectedModel);
    const result = createAssistantMessageEventStream();
    const message = { role: 'assistant', content, api: selectedModel.api, provider: selectedModel.provider, model: selectedModel.id, timestamp: Date.now(),
      stopReason: content.some(part => part.type === 'toolCall') ? 'toolUse' : 'stop', usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
    queueMicrotask(() => result.push({ type: 'done', reason: message.stopReason, message })); return result;
  };
}
const image = async () => ({ type: 'image', mimeType: 'image/png', data: 'synthetic' });

test('all four material combinations can start; question pages never enter student partitions', () => {
  for (const scheme of [true, false]) for (const question of [true, false]) {
    const f = task({ scheme, question });
    assert.equal(f.task.status, 'running');
    assert.deepEqual(f.task.groups[0].pageIds, ['page-a']);
    assert.equal(usesAdaptiveGrading(f.task), !scheme || question);
    assert.equal(f.task.pages.length, 1 + Number(scheme) + Number(question));
  }
});

test('question-derived plans stay provisional; missing maxima cannot produce invented scores', () => {
  const f = task().task;
  const frozen = validatePlan(plan(), f, new Set(['qp']));
  const grade = validateAdaptiveGrade({ items: [decision()] }, frozen, f.groups[0], new Set(['page-a']));
  assert.equal(grade.provisional, true); assert.equal(grade.reviewRequired, true); assert.equal(grade.totalScore, 2);
  for (const override of [{ maxScore: null }, { scalePageIds: [] }, { scaleQuote: '' }, { allowedAwards: [0, 3] }, { questionStatus: 'partial' }, { basis: 'provided_scheme' }]) {
    assert.throws(() => validatePlan(plan([criterion(override)]), f, new Set(['qp'])));
  }
  const qualitative = validatePlan(plan([criterion({ disposition: 'feedback_only', maxScore: null, allowedAwards: [], scaleBasis: 'unknown', scalePageIds: [], scaleQuote: '' })]), f, new Set(['qp']));
  assert.throws(() => validateAdaptiveGrade({ items: [decision({ score: 0 })] }, qualitative, f.groups[0], new Set(['page-a'])));
  const feedback = validateAdaptiveGrade({ items: [decision({ score: null })] }, qualitative, f.groups[0], new Set(['page-a']));
  assert.equal(feedback.totalScore, null); assert.equal(feedback.maximum, null);
});

test('question and supplied MS are both required source context before official criteria freeze', () => {
  const f = task({ scheme: true }).task;
  const raw = plan([criterion({ basis: 'provided_scheme', sourcePageIds: ['ms', 'qp'], scalePageIds: ['ms'], rationale: 'Apply the supplied criterion to the original question.' })]);
  assert.throws(() => validatePlan(raw, f, new Set(['ms'])), /完整/);
  assert.throws(() => validatePlan(raw, f, new Set(['qp'])), /完整/);
  const frozen = validatePlan(raw, f, new Set(['ms', 'qp']));
  const grade = validateAdaptiveGrade({ items: [decision()] }, frozen, f.groups[0], new Set(['page-a']));
  assert.equal(grade.provisional, false); assert.equal(grade.totalScore, 2);
});

test('conversation planner passes the selected question and teacher context into an executable no-MS draft', async () => {
  const f = task().state;
  let called = false;
  const ctl = createWorkspaceAgent({ model, state: f, selectedIds: ['a'], goal: '根据题目批改，不提供 MS', readPage: image,
    streamFn: stream(() => {
      if (called) return [{ type: 'text', text: '已保存草稿。' }]; called = true;
      return [toolCall('create_task_draft', { title: 'Question grading', goal: '按题目推导评分依据', kind: 'grade', groupIds: ['a'], schemeId: null, questionId: 'qp', gradingContext: 'General science', allowWebSearch: false, after: 'review' })];
    }) });
  await ctl.agent.prompt(ctl.prompt);
  assert.equal(ctl.proposals.length, 1); assert.equal(ctl.proposals[0].questionId, 'qp');
  assert.equal(ctl.proposals[0].schemeId, null); assert.equal(ctl.proposals[0].gradingContext, 'General science');
});

test('source and award invariants survive renamed IDs, reordered pages and other subject criteria', () => {
  for (const [itemId, pageId, criterionText] of [['renamed', 'different', 'A valid alternative method.'], ['文段', '原页', '论证与所给文本相关。'], ['z-17', 'p-8', 'Use compatible units and state assumptions.']]) {
    const f = task().task; f.question.pageIds = [pageId]; f.pages[0].id = pageId;
    const raw = plan([criterion({ id: itemId, sourcePageIds: [pageId], scalePageIds: [pageId], criteria: criterionText })]);
    const frozen = validatePlan(raw, f, new Set([pageId]));
    const valid = { items: [decision({ id: itemId })] };
    assert.equal(validateAdaptiveGrade(valid, frozen, f.groups[0], new Set(['page-a'])).totalScore, 2);
    for (const bad of [{ score: 3 }, { score: 1.5 }, { studentPageIds: ['page-b'] }, { evidence: '' }, { verdict: 'unresolved' }]) {
      assert.throws(() => validateAdaptiveGrade({ items: [decision({ id: itemId, ...bad })] }, frozen, f.groups[0], new Set(['page-a', 'page-b'])));
    }
  }
});

test('answer-only recovery is per book and incomplete coverage cannot become a whole-paper total', () => {
  const f = task({ question: false, groups: ['a', 'b'] }).task;
  const items = f.groups.map(group => criterion({ id: group.id, groupIds: [group.id], basis: 'answer_context', sourcePageIds: group.pageIds, scalePageIds: group.pageIds }));
  const raw = plan(items, f.groups.map(group => ({ groupId: group.id, status: 'partial', reason: 'Only visible tasks can be identified.' })));
  const seen = new Set(['page-a', 'page-b']);
  const frozen = validatePlan(raw, f, seen);
  const grade = validateAdaptiveGrade({ items: [decision({ id: 'a' })] }, frozen, f.groups[0], seen);
  assert.equal(grade.totalScore, null); assert.equal(grade.knownScore, 2);
  const cross = structuredClone(raw); cross.items[0].sourcePageIds = ['page-b'];
  assert.throws(() => validatePlan(cross, f, seen), /归属/);
  const shared = structuredClone(raw); shared.items[0].groupIds = ['a', 'b'];
  assert.throws(() => validatePlan(shared, f, seen));
});

test('unidentifiable work remains unresolved and never receives a fabricated zero', () => {
  const f = task({ question: false }).task;
  const frozen = validatePlan(plan([criterion({ basis: 'answer_context', sourcePageIds: ['page-a'], questionStatus: 'unknown', disposition: 'needs_material', maxScore: null, allowedAwards: [], scaleBasis: 'unknown', scaleQuote: '', scalePageIds: [], uncertainties: ['The task cannot be identified from this work.'] })], [{ groupId: 'a', status: 'unknown', reason: 'No question can be identified.' }]), f, new Set(['page-a']));
  const grade = validateAdaptiveGrade({ items: [decision({ score: null, verdict: 'unresolved' })] }, frozen, f.groups[0], new Set(['page-a']));
  assert.equal(grade.totalScore, null);
  assert.throws(() => validateAdaptiveGrade({ items: [decision({ score: 0 })] }, frozen, f.groups[0], new Set(['page-a'])));
  assert.throws(() => validateAdaptiveGrade({ items: [decision({ score: null, verdict: 'incorrect' })] }, frozen, f.groups[0], new Set(['page-a'])));
});

test('teacher scales use agreed requirements and cannot reuse withdrawn or superseded instructions', () => {
  const f = task().task;
  f.supplementalInstructions = '每题一分';
  f.acceptedGradingRequirements = '每题两分，按 0、1、2 分计分。';
  const raw = plan([criterion({ scaleBasis: 'teacher', scaleQuote: '每题两分', scalePageIds: [] })]);
  assert.equal(validatePlan(raw, f, new Set(['qp'])).plan.items[0].maxScore, 2);
  const original = structuredClone(raw); original.items[0].scaleQuote = '每题一分';
  assert.throws(() => validatePlan(original, f, new Set(['qp'])), /已核对/);
  f.acceptedGradingRequirements = '';
  assert.throws(() => validatePlan(raw, f, new Set(['qp'])), /已核对/);
});

test('web research is bounded, stores provenance and cannot elevate a search snippet to a rubric source', async () => {
  let calls = 0; const events = [];
  const research = createGradingResearch({ enabled: true, key: 'offline-test', persist: async event => events.push(event),
    fetchImpl: async () => { calls++; return { ok: true, json: async () => ({ web: { results: [{ url: 'https://example.org/exam', title: 'Official instruction candidate', description: 'Check the edition.' }] } }) }; },
    readReference: async () => 'An externally retrieved text, not an uploaded marking scheme.' });
  const [ref] = await research.search('public examination criteria');
  const f = task().task, raw = plan([criterion({ webReferenceIds: [ref.id] })]);
  assert.throws(() => validatePlan(raw, f, new Set(['qp']), research.references), /实际打开/);
  await research.open(ref.id); validatePlan(raw, f, new Set(['qp']), research.references);
  assert.equal(events[1].reference.contentHash.length, 64);
  await assert.rejects(research.open('not-returned'));
  await assert.rejects(research.search('student@example.org'));
  for (let i = 1; i < 6; i++) await research.search('public syllabus');
  await assert.rejects(research.search('one more query')); assert.equal(calls, 6);
  await assert.rejects(createGradingResearch({ enabled: false }).search('public question'));
  for (const ip of ['127.0.0.1', '10.0.0.1', '169.254.169.254', '192.168.1.1', '100.64.0.1', '::1']) assert.equal(publicAddress(ip), false);
  assert.equal(publicAddress('8.8.8.8'), true);
  for (const url of ['http://example.org', 'https://127.0.0.1', 'https://user:pass@example.org', 'https://example.org:8443']) assert.throws(() => referenceURL(url));
});

test('actual Pi coordinator requires prior page delivery, later review and adopted guide before dispatch', async () => {
  const f = task().task; let step = 0, candidate, published = 0, dispatched = 0;
  const ctl = createAdaptiveCoordinator({ model, task: f, readPage: image, research: createGradingResearch({ enabled: false }),
    persistCandidate: async () => {}, verifyPlan: async value => { candidate = reviewed(value); return candidate; }, persistPlan: async () => {}, publishGuide: async () => { published++; return { hash: 'approved', revision: 1, method: 'automatic' }; },
    executeStudent: async () => { dispatched++; return { status: 'submitted' }; },
    streamFn: stream(() => {
      const header = plan(); delete header.items;
      return [
        [toolCall('grade_students', { groupIds: ['a'], concurrency: 1 })],
        [toolCall('read_pages', { pageIds: ['qp'] }), toolCall('read_grading_competency', { name: 'quantitative' }), toolCall('stage_plan_items', { items: [criterion()] }), toolCall('prepare_grading_plan', header)],
        [toolCall('prepare_grading_plan', header)],
        [toolCall('freeze_grading_plan', { candidateHash: candidate?.hash || 'none', sourceReview: 'Checked the complete source, scale, criterion and limits.' })],
        [toolCall('grade_students', { groupIds: ['a'], concurrency: 1 })],
        [toolCall('grade_students', { groupIds: ['a'], concurrency: 1 })],
        [toolCall('finish_grading', {})],
      ][step++] || [{ type: 'text', text: 'done' }];
    }) });
  await ctl.agent.prompt(ctl.prompt);
  assert.equal(published, 1); assert.equal(dispatched, 1); assert.ok(ctl.getResult());
  const errors = ctl.agent.state.messages.filter(row => row.role === 'toolResult' && row.isError);
  assert.equal(errors.length, 3); // early dispatch, same-turn source citation, repeated student
});

test('actual Pi student has no other book, cannot submit before page delivery, and saves once', async () => {
  const f = task({ groups: ['a', 'b'] }).task;
  const frozen = validatePlan(plan([criterion({ groupIds: ['a', 'b'] })], f.groupIds.map(groupId => ({ groupId, status: 'complete', reason: 'Shared printed paper.' }))), f, new Set(['qp']));
  let step = 0, saves = 0;
  const ctl = createAdaptiveStudent({ model, task: f, group: f.groups[0], frozen, readPage: image, save: async () => { saves++; },
    streamFn: stream(() => [
      [toolCall('read_pages', { pageIds: ['page-b'] })],
      [toolCall('read_pages', { pageIds: ['page-a'] }), toolCall('submit_grading', { items: [decision()] })],
      [toolCall('submit_grading', { items: [decision()] })],
    ][step++] || [{ type: 'text', text: 'done' }]) });
  assert.ok(!ctl.prompt.includes('page-b'));
  await ctl.agent.prompt(ctl.prompt); assert.equal(saves, 1); assert.ok(ctl.getResult());
});

test('adaptive student cannot fetch a marking scheme by its known page ID', async () => {
  const f = task({scheme:true}).task;
  const value = validatePlan(plan([criterion({basis:'provided_scheme',sourcePageIds:['ms','qp'],scalePageIds:['ms']})]), f, new Set(['ms','qp']));
  const child = createAdaptiveStudent({model, task:f, group:f.groups[0], frozen:value, streamFn:stream(() => []), readPage:image});
  assert.ok(!JSON.parse(child.prompt).sources.some(page => page.role === 'scheme'));
  const reader = child.agent.state.tools.find(tool => tool.name === 'read_pages');
  await assert.rejects(reader.execute('attempt', {pageIds:['ms']}), /范围/);
});

test('new task form preserves explicitly absent MS and exposes three separate upload roles', () => {
  const f = task({ scheme: true }).state;
  const html = taskForm({ state: f, selected: new Set(['a']), command: '' }, { ...f.tasks[0], schemeId: null });
  assert.ok(!html.includes('value="ms" selected')); assert.match(html, /name="questionId"/); assert.match(html, /name="allowWebSearch"/);
  const material = materialView({ state: f, selected: new Set(), sorting: false, materialRole: 'question', undo: [] });
  assert.match(material, /Questions/); assert.ok(!material.includes('data-group="qp"'));
});

test('adaptive runtime persists adopted guide, original records and provisional report through the real Pi loop', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'pi-adaptive-runtime-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const store = await new WorkspaceStore(directory).init(); const f = task();
  f.task.supplementalInstructions = '用中文反馈';
  for (const page of f.task.pages) { page.path = join(directory, `${page.id}.png`); const bytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC', 'base64'); page.sha256 = digest(bytes); await writeFile(page.path, bytes); }
  f.state.pages = f.task.pages; f.state.tasks[0] = f.task;
  await store.mutate(null, state => Object.assign(state, f.state));
  const input = await prepareTaskInput(store, f.task);
  const entry = { controller: new AbortController(), interaction: join(input.directory, 'interaction') };
  await mkdir(entry.interaction); await atomicJSON(join(entry.interaction, 'control.json'), { executionMode: 'auto', paused: false, notes: [], supplementalInstructions: f.task.supplementalInstructions });
  const runner = new WorkspaceRunner(store); runner.active.set(f.task.id, entry);
  let mainStep = 0, studentStep = 0;
  const localModels = createModels(); localModels.setProvider(openrouterProvider());
  localModels.streamSimple = stream((context, selectedModel) => {
    const main = context.systemPrompt?.includes('main GradeOS') || context.messages.some(row => row.role === 'system' && JSON.stringify(row).includes('main GradeOS'));
    assert.equal(selectedModel.id, main ? 'openai/gpt-6.2-sol' : 'openai/gpt-6.1-terra');
    const system = context.systemPrompt || JSON.stringify(context.messages.find(row => row.role === 'system'));
    if (system.includes('independently establish reference solutions')) {
      assert.doesNotMatch(JSON.stringify(context.messages), /用中文反馈/);
      assert.deepEqual((context.tools || context.messages.flatMap(message => message.toolsAdded || [])).map(tool => tool.name), ['check_arithmetic', 'submit_derivations']);
      return [toolCall('submit_derivations', { items: [{ id: 'part-alpha', status: 'established', referenceAnswer: criterion().referenceAnswer, checks: [{ method: 'Reverse check', observation: 'Substitution satisfies the task.' }], calculationIds: [], limitations: [] }] })];
    }
    if (system.includes('independent verification step')) {
      const read = context.messages.some(row => row.role === 'toolResult' && row.toolName === 'read_pages');
      return read ? [toolCall('submit_reference_review', { items: [{ id: 'part-alpha', status: 'confirmed', sourceFaithful: true, referenceAnswer: criterion().referenceAnswer, criteria: criterion().criteria, checks: [{ method: 'Source check', observation: 'Original statement and derived relation agree.' }], calculationIds: [], findings: [] }] })] : [toolCall('read_pages', { pageIds: ['qp'] })];
    }
    if (!main) {
      assert.match(JSON.stringify(context.messages), /用中文反馈/);
      return studentStep++ === 0 ? [toolCall('read_pages', { pageIds: ['page-a'] })] : [toolCall('submit_grading', { items: [decision()] })];
    }
    const candidateMessage = context.messages.findLast(row => row.role === 'toolResult' && row.toolName === 'prepare_grading_plan' && !row.isError);
    const candidateHash = candidateMessage ? JSON.parse(candidateMessage.content[0].text).candidateHash : 'not-yet';
    const header = plan(); delete header.items;
    return [
      [toolCall('read_pages', { pageIds: ['qp'] }), toolCall('read_grading_competency', { name: 'quantitative' })],
      [toolCall('review_grading_requirements', { decision: 'compatible', explanation: '反馈语言不改变分值。', question: '', adjustedInstructions: '' })],
      [toolCall('stage_plan_items', { items: [criterion()] }), toolCall('prepare_grading_plan', header)],
      [toolCall('freeze_grading_plan', { candidateHash, sourceReview: 'Source and scale reviewed.' })],
      [toolCall('grade_students', { groupIds: ['a'], concurrency: 1 })],
      [toolCall('finish_grading', {})],
    ][mainStep++] || [{ type: 'text', text: 'done' }];
  });
  await runAdaptiveGrading({ store, task: f.task, input, entry, runner, models: localModels });
  const saved = store.state.tasks[0];
  assert.equal(saved.status, 'needs_review', JSON.stringify(JSON.parse(await readFile(join(input.output, 'main/transcript.json'), 'utf8')).filter(row => row.role === 'toolResult' && row.isError))); assert.equal(saved.records.length, 1);
  assert.equal(saved.records[0].basis, 'derived_question'); assert.deepEqual(saved.records[0].questionPageIds, ['qp']);
  assert.match(saved.artifacts[0].body, /推导标准/);
  assert.equal(store.state.documents.find(row => row.kind === 'marking_guide').approvals[0].method, 'automatic');
  assert.match(store.state.documents.find(row => row.kind === 'marking_guide').body, /本批已核对的补充要求/);
  assert.equal(JSON.parse(await readFile(join(input.output, 'summary.json'), 'utf8')).status, 'submitted');
  const runPlan = JSON.parse(await readFile(join(input.output, 'adaptive-run.json'), 'utf8'));
  assert.equal(runPlan.model, 'openai/gpt-6.2-sol');
  assert.equal(runPlan.workerModel, 'openai/gpt-6.1-terra');
  assert.equal((await new WorkspaceStore(directory).init()).state.tasks[0].records.length, 1);
});


test('embedded marked questions score with derived criteria while doubts remain local', () => {
  const f = task({ question: false }).task;
  const shared = { basis: 'answer_context', sourcePageIds: ['page-a'], scalePageIds: ['page-a'] };
  const frozen = validatePlan(plan([
    criterion({ ...shared, id: 'shared-group', maxScore: 4, allowedAwards: [0, 1, 2, 3, 4], scaleQuote: '(a) and (b): [4 marks]', uncertainties: ['The final symbol has two plausible readings.'] }),
    criterion({ ...shared, id: 'other-subject', question: 'Explain the causal relation shown in the task.' }),
  ]), f, new Set(['page-a']));
  const raw = { items: [decision({ id: 'shared-group', score: 3, verdict: 'partial', uncertainties: ['The final symbol has two plausible readings.'] }), decision({ id: 'other-subject' })] };
  const before = structuredClone(raw);
  const grade = validateAdaptiveGrade(raw, frozen, f.groups[0], new Set(['page-a']));
  assert.equal(grade.totalScore, 5);
  assert.equal(grade.maximum, 6, 'Keep the printed group total exactly once.');
  assert.equal(grade.provisional, true);
  assert.deepEqual(grade.items.map(item => item.uncertainties.length), [1, 0]);
  const records = adaptiveRecords(f, f.groups[0], grade, frozen);
  assert.deepEqual(records[0].uncertainties, grade.items[0].uncertainties);
  assert.equal(records[1].reviewRequired, true, 'Provisional status is distinct from concrete uncertainty.');
  assert.match(adaptiveReport(f.groups[0], grade, frozen, new Map()), /待核实：The final symbol/);
  assert.deepEqual(raw, before, 'Normalization must preserve raw model output.');
  raw.items[0] = decision({ id: 'shared-group', score: null, verdict: 'unresolved', reason: 'The reading prevents a defensible award.' });
  const unresolved = validateAdaptiveGrade(raw, frozen, f.groups[0], new Set(['page-a']));
  assert.equal(unresolved.totalScore, null);
  assert.equal(unresolved.knownScore, 2);
  assert.equal(unresolved.items[1].score, 2);
});


test('invalid source references identify the exact item and bad ID without relaxing ownership', () => {
  const f = task({ question: false, groups: ['a', 'b'] }).task;
  const valid = f.groups.map(group => criterion({ id: group.id, groupIds: [group.id], basis: 'answer_context', sourcePageIds: group.pageIds, scalePageIds: group.pageIds }));
  const coverage = f.groups.map(group => ({ groupId: group.id, status: 'complete', reason: 'Complete embedded task.' }));
  const invalid = structuredClone(valid); invalid[0].scalePageIds = ['page-typo'];
  assert.throws(() => validatePlan(plan(invalid, coverage), f, new Set(['page-a', 'page-b'])), /评分项 a.*不存在.*page-typo/);
  invalid[0].scalePageIds = ['page-b'];
  assert.throws(() => validatePlan(plan(invalid, coverage), f, new Set(['page-a', 'page-b'])), /评分项 a.*归属/);
  assert.doesNotThrow(() => validatePlan(plan(valid, coverage), f, new Set(['page-a', 'page-b'])));
});
