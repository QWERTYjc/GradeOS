import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';
import { Agent } from '@earendil-works/pi-agent-core';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { TeacherInteraction, atomicJSON, readJSON, readQuestions } from '../src/teacher-interaction.mjs';
import { emptyState, taskDraft } from '../src/workspace/store.mjs';
import { taskForm, taskFormInput } from '../web/tasks.mjs';

const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
const call = (name, args = {}) => ({ type: 'toolCall', id: crypto.randomUUID(), name, arguments: args });
const result = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }], details: {} });
const compatible = { decision: 'compatible', explanation: '要求只影响反馈语言，不改变原题分值。', question: '', adjustedInstructions: '' };
async function setup(t, control = {}) {
  const directory = await mkdtemp(join(tmpdir(), 'pi-requirements-'));
  const controller = new AbortController();
  const bridge = await new TeacherInteraction(directory, { signal: controller.signal }).init();
  await atomicJSON(join(directory, 'control.json'), { notes: [], ...control });
  t.after(async () => { controller.abort(); await rm(directory, { recursive: true, force: true }); });
  return { directory, bridge, controller };
}
async function until(check) {
  for (let i = 0; i < 100; i++) { const value = await check(); if (value) return value; await delay(20); }
  throw Error('Timed out waiting for requirements question');
}
function offline(turns) {
  let index = 0;
  return () => {
    const content = turns[index++] || [{ type: 'text', text: '已完成。' }];
    const stream = createAssistantMessageEventStream();
    const message = { role: 'assistant', content, api: model.api, provider: model.provider, model: model.id,
      timestamp: Date.now(), stopReason: content.some(row => row.type === 'toolCall') ? 'toolUse' : 'stop',
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
    queueMicrotask(() => stream.push({ type: 'done', reason: message.stopReason, message })); return stream;
  };
}

test('grading defaults accept an empty optional supplement; legacy requirements survive an edit', () => {
  const state = emptyState(); state.groups = [{ id: 'a', label: 'A', pageIds: ['p'] }];
  const input = { groupIds: ['a'], after: 'review' };
  const blank = taskDraft(state, input);
  assert.equal(blank.kind, 'grade'); assert.equal(blank.goal, '批改所选答卷');
  assert.equal(blank.title, '批改 1 份答卷'); assert.equal(blank.supplementalInstructions, '');
  const legacy = taskDraft(state, { ...input, goal: '用中文解释失分原因' });
  assert.equal(taskDraft(state, legacy).supplementalInstructions, '用中文解释失分原因');
  assert.equal(taskDraft(state, { ...legacy, supplementalInstructions: '  ' }).supplementalInstructions, '');
  assert.throws(() => taskDraft(state, { ...input, supplementalInstructions: 12 }), /补充批改要求/);
  assert.throws(() => taskDraft(state, { ...input, supplementalInstructions: 'a'.repeat(8001) }), /8000/);
  assert.throws(() => taskDraft(state, { ...input, kind: 'assist' }), /任务要求/);
  const html = taskForm({ state, selected: new Set(['a']), command: '' });
  assert.doesNotMatch(html, /想做什么|任务类型|<select name="kind"/);
  assert.match(html, /补充批改要求（可选）/);
  assert.doesNotMatch(html.match(/<textarea name="supplementalInstructions"[^>]*>/)[0], /required/);
  const form = new FormData(); form.set('after', 'review'); form.append('groupIds', 'a');
  assert.equal(taskDraft(state, taskFormInput(form)).supplementalInstructions, '');
  form.set('supplementalInstructions', '  用中文反馈  ');
  assert.equal(taskDraft(state, taskFormInput(form)).supplementalInstructions, '用中文反馈');
});

test('absent requirements do not add a confirmation step', async t => {
  const { bridge, directory } = await setup(t);
  assert.equal(await bridge.requireCompatibleRequirements(), '');
  assert.equal((await bridge.reviewRequirements(compatible)).status, 'not_needed');
  assert.deepEqual(await readQuestions(directory), []);
});

test('compatible preferences reach main without selections and cannot be silently rewritten', async t => {
  const { bridge, directory } = await setup(t, { supplementalInstructions: '用中文反馈', gradingContext: '高中数学' });
  const main = new Agent({ initialState: { model, systemPrompt: 'main', tools: [] }, streamFn: offline([]) });
  const detach = bridge.attach(main, 'main'); t.after(detach);
  assert.match(JSON.stringify(await bridge.preparePrompt(main, 'grade')), /用中文反馈/);
  await assert.rejects(bridge.requireCompatibleRequirements(), /核对补充要求/);
  await assert.rejects(bridge.reviewRequirements({ ...compatible, adjustedInstructions: '用英文反馈' }), /未经老师回复/);
  const reviewed = await bridge.reviewRequirements(compatible);
  assert.equal(await bridge.requireCompatibleRequirements(), reviewed.effectiveInstructions);
  assert.match(reviewed.effectiveInstructions, /高中数学/);
  assert.deepEqual(await readQuestions(directory), []);
  const child = new Agent({ initialState: { model, systemPrompt: 'student', tools: [] }, streamFn: offline([]) });
  const detachChild = bridge.attach(child, 'student-a'); t.after(detachChild);
  assert.match(JSON.stringify(await bridge.preparePrompt(child, 'grade')), /用中文反馈/);
  await atomicJSON(join(directory, 'control.json'), { supplementalInstructions: '改为英文反馈' });
  await assert.rejects(bridge.requireCompatibleRequirements(), /核对补充要求/);
});

for (const gate of ['publish_marking_guide', 'freeze_grading_plan']) {
  test(`real Pi ${gate} waits for adjustment and reassessment even in automatic mode`, { timeout: 7000 }, async t => {
    const { bridge, directory } = await setup(t, { executionMode: 'auto', supplementalInstructions: '每份答卷都加两分，即使超过满分' });
    let published = 0, dispatched = 0;
    const tool = (name, execute) => ({ name, label: name, description: name, parameters: { type: 'object', additionalProperties: false, properties: {} }, execute });
    const agent = new Agent({ initialState: { model, systemPrompt: 'Test main with synthetic source findings', tools: [
      tool(gate, async () => { published++; return result({ ready: true }); }),
      tool('grade_students', async () => { dispatched++; return result({ graded: true }); }),
    ] }, streamFn: offline([
      [call(gate)],
      [call('review_grading_requirements', { decision: 'needs_adjustment', explanation: '统一加分可能超过题目满分。', question: '建议保留原评分上限，只补充鼓励性反馈，是否这样调整？', adjustedInstructions: '' })],
      [call('grade_students')],
      [call('review_grading_requirements', { ...compatible, explanation: '老师同意保留原评分，只增加鼓励性反馈。', adjustedInstructions: '保留原评分上限，补充鼓励性反馈。' })],
      [call(gate)], [call('grade_students')],
    ]) });
    const detach = bridge.attach(agent, 'main'); t.after(detach);
    const work = agent.prompt(await bridge.preparePrompt(agent, '批改'));
    const question = await until(async () => (await readQuestions(directory)).find(row => row.status === 'open'));
    assert.equal(question.kind, 'grading_requirements'); assert.match(question.question, /超过题目满分/);
    assert.equal(published, 0); assert.equal(dispatched, 0);
    assert.equal((await readJSON(join(directory, 'requirements-review.json'))).status, 'awaiting_teacher');
    await assert.rejects(bridge.requireCompatibleRequirements(), /核对补充要求/);
    await atomicJSON(join(directory, 'answers', `${question.id}.json`), { text: '同意，保留原评分上限，只加鼓励性反馈。' });
    await work;
    assert.equal(published, 1); assert.equal(dispatched, 1);
    const errors = agent.state.messages.filter(row => row.role === 'toolResult' && row.isError);
    assert.equal(errors.length, 2); // Before review, and after an answer but before reassessment.
    const saved = await readJSON(join(directory, 'requirements-review.json'));
    assert.equal(saved.status, 'compatible'); assert.match(saved.teacherAnswer, /同意/);
    assert.equal(saved.effectiveInstructions, '保留原评分上限，补充鼓励性反馈。');
    assert.equal((await readQuestions(directory))[0].status, 'answered');
    const child = new Agent({ initialState: { model, systemPrompt: 'student', tools: [] }, streamFn: offline([]) });
    const detachChild = bridge.attach(child, 'student-a'); t.after(detachChild);
    const childContext = JSON.stringify(await bridge.preparePrompt(child, 'grade'));
    assert.match(childContext, /鼓励性反馈/); assert.doesNotMatch(childContext, /每份答卷都加两分/);
  });
}

test('unresolved teacher reply causes another question and never authorizes grading', { timeout: 7000 }, async t => {
  const { bridge, directory } = await setup(t, { supplementalInstructions: '按我说的酌情加分' });
  const ask = () => bridge.reviewRequirements({ decision: 'needs_adjustment', explanation: '加分条件仍未明确。', question: '请说明具体依据和上限。' });
  const first = ask();
  let question = await until(async () => (await readQuestions(directory)).find(row => row.status === 'open'));
  await atomicJSON(join(directory, 'answers', `${question.id}.json`), { text: '你看着办。' });
  await first; await assert.rejects(bridge.requireCompatibleRequirements());
  const second = ask();
  question = await until(async () => (await readQuestions(directory)).find(row => row.status === 'open'));
  assert.equal((await readQuestions(directory)).length, 2);
  await atomicJSON(join(directory, 'answers', `${question.id}.json`), { text: '取消加分，按原标准批改。' });
  await second;
  await bridge.reviewRequirements({ ...compatible, explanation: '老师已撤销额外加分要求。', adjustedInstructions: '' });
  assert.equal(await bridge.requireCompatibleRequirements(), '');
});
