import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { digest } from '../src/core.mjs';
import { exactArithmetic, referenceArithmeticTool } from '../src/workspace/reference-arithmetic.mjs';
import { applyReferenceReview, taskOnlyInput, createReferenceDeriver } from '../src/workspace/reference-audit.mjs';
import { validateAdaptiveGrade, object, text } from '../src/workspace/adaptive-contract.mjs';
import { adaptiveRecords, adaptiveReport } from '../src/workspace/adaptive-runtime.mjs';

function candidate() {
  const plan = { subject: 'mixed', examSystem: 'unknown', implementation: 'Suggested policy',
    coverage: [{ groupId: 'book', status: 'complete', reason: 'All visible tasks included.' }],
    items: ['alpha', 'beta'].map(id => ({ id, groupIds: ['book'], question: 'Find the value satisfying the stated relation.', questionStatus: 'complete',
      basis: 'answer_context', sourcePageIds: ['page'], scalePageIds: ['page'], scaleBasis: 'source', scaleQuote: '[2 marks]', disposition: 'score',
      maxScore: 2, allowedAwards: [0, 1, 2], referenceAnswer: 'CANDIDATE_ANSWER_POISON', criteria: 'CANDIDATE_POLICY_POISON', rationale: 'A derived policy.', uncertainties: [], webReferenceIds: [] })) };
  return { version: 1, plan, sourceHash: 'source', hash: digest(plan) };
}
function audit(c, statuses = ['confirmed', 'confirmed']) {
  const derivation = { inputHash: digest(taskOnlyInput(c)), items: c.plan.items.map(i => ({ id: i.id, status: 'established' })) };
  const review = { candidateHash: c.hash, derivationHash: digest(derivation), items: c.plan.items.map((i, index) => ({ id: i.id, status: statuses[index], sourceFaithful: true,
    referenceAnswer: statuses[index] === 'confirmed' ? i.referenceAnswer : 'Independently checked relation.', criteria: statuses[index] === 'confirmed' ? i.criteria : 'Complete valid reasoning earns full credit; substantive incomplete progress earns partial credit.',
    findings: statuses[index] === 'confirmed' ? [] : ['The candidate transformation contradicts an original condition.'], checks: [{ method: 'Reverse substitution', observation: 'The checked relation satisfies the original premises.' }] })) };
  return { derivation, review };
}
const group = { id: 'book', label: 'Student', pageIds: ['page'] };
const raw = () => ({ items: ['alpha', 'beta'].map(id => ({ id, score: 2, verdict: 'supported', reason: 'The visible work satisfies the criterion.', evidence: 'Actual work.',
  studentPageIds: ['page'], reviewRequired: false, uncertainties: [], referenceCheck: { status: 'consistent', observation: 'The original conditions hold.' } })) });

test('exact calculator preserves algebraic equivalence, signs and rational arithmetic', () => {
  assert.equal(exactArithmetic('0.1+0.2'), '3/10');
  assert.equal(exactArithmetic('2^-3'), '1/8');
  assert.equal(exactArithmetic('-2^2'), '-4');
  assert.equal(exactArithmetic('(-2)^2'), '4');
  assert.equal(exactArithmetic('2^3^2'), '512');
  assert.equal(exactArithmetic('19%7'), '5');
  for (let n = -9; n < 10; n++) {
    assert.equal(exactArithmetic(`(${n}+2)*3`), exactArithmetic(`${n}*3+6`));
    assert.notEqual(exactArithmetic(`(${n}+2)*3`), exactArithmetic(`${n}*3-6`));
  }
});

test('calculator refuses code, resource exhaustion, undefined and unsupported arithmetic', () => {
  for (const expression of ['process.env', 'constructor.constructor("return process")()', '1/0', '0^0', '2^999999', '9^4096', '2^(1/2)', '1;2', '1 2', '(1+2', 'sin(0)', '1.5%2']) {
    assert.throws(() => exactArithmetic(expression), undefined, expression);
  }
});

test('failed arithmetic is retained as an error and cannot be cited as a successful check', async () => {
  const { tool, calculations } = referenceArithmeticTool(object, text);
  const result = JSON.parse((await tool.execute('', { expressions: ['9/4', '1/0'] })).content[0].text);
  assert.equal(result[0].exact, '9/4'); assert.ok(result[1].error);
  assert.equal(calculations.size, 1); assert.ok(!calculations.has(result[1].id));
});

test('task-only lane has no student answer, proposed policy, original image or teacher context', () => {
  const c = candidate(); c.studentAnswers = 'STUDENT_POISON'; c.teacherNote = 'TEACHER_POISON';
  const input = taskOnlyInput(c); assert.deepEqual(Object.keys(input.tasks[0]), ['id', 'question', 'questionStatus']);
  const models = createModels(); models.setProvider(openrouterProvider());
  const ctl = createReferenceDeriver({ model: models.getModel('openrouter', 'openai/gpt-6.1-terra'), candidate: c, streamFn: () => { throw Error('No calls in contract test'); } });
  assert.doesNotMatch(ctl.prompt, /POISON|sourcePageIds|maxScore|groupIds/);
  assert.deepEqual(ctl.agent.state.tools.map(t => t.name), ['check_arithmetic', 'submit_derivations']);
});

test('source-bound correction is immutable, visible and preserves printed marks', () => {
  const c = candidate(), original = structuredClone(c), { derivation, review } = audit(c, ['corrected', 'confirmed']);
  const checked = applyReferenceReview(c, derivation, review);
  assert.deepEqual(c, original); assert.notEqual(c.hash, checked.hash);
  assert.equal(checked.plan.items[0].maxScore, 2); assert.deepEqual(checked.plan.items[0].allowedAwards, [0, 1, 2]);
  assert.match(checked.plan.items[0].uncertainties[0], /标准校核已修正/);
  assert.deepEqual(checked.plan.items[1].uncertainties, []);
  const grade = validateAdaptiveGrade(raw(), checked, group, new Set(['page']));
  const records = adaptiveRecords({ id: 'task' }, group, grade, checked);
  assert.equal(records[0].referenceVerification.status, 'corrected');
  assert.match(adaptiveReport(group, grade, checked, new Map()), /标准校核已修正/);
  const changed = structuredClone(c); changed.plan.items[0].question += 'Changed conditions.';
  assert.throws(() => applyReferenceReview(changed, derivation, review), /题干不匹配/);
  assert.throws(() => applyReferenceReview(c, derivation, { ...review, candidateHash: 'old' }), /候选标准不匹配/);
});

test('unresolved standard blocks only its own award and cannot be converted into full marks', () => {
  const c = candidate(), { derivation, review } = audit(c, ['unresolved', 'confirmed']);
  const checked = applyReferenceReview(c, derivation, review), submission = raw();
  assert.throws(() => validateAdaptiveGrade(submission, checked, group, new Set(['page'])), /校核仍有未决冲突/);
  Object.assign(submission.items[0], { score: null, verdict: 'unresolved' });
  const grade = validateAdaptiveGrade(submission, checked, group, new Set(['page']));
  assert.equal(grade.totalScore, null); assert.equal(grade.knownScore, 2);
  assert.equal(grade.items[1].score, 2); assert.equal(grade.items[0].maxScore, 2);
  assert.ok(grade.items[0].uncertainties.length);
});

test('student-reported conflict cannot be ignored even if upstream verification passed', () => {
  const c = candidate(), { derivation, review } = audit(c), checked = applyReferenceReview(c, derivation, review), submission = raw();
  submission.items[0].referenceCheck = { status: 'conflict', observation: 'Reverse substitution contradicts the task.' };
  assert.throws(() => validateAdaptiveGrade(submission, checked, group, new Set(['page'])), /标准冲突/);
  Object.assign(submission.items[0], { score: null, verdict: 'unresolved' });
  const grade = validateAdaptiveGrade(submission, checked, group, new Set(['page']));
  assert.match(grade.items[0].uncertainties.join(' '), /Reverse substitution/);
  assert.equal(grade.items[1].score, 2);
});

test('missing independent derivation or source mismatch cannot be promoted to verified', () => {
  const c = candidate(), { derivation, review } = audit(c);
  derivation.items[0].status = 'unresolved'; review.derivationHash = digest(derivation);
  assert.throws(() => applyReferenceReview(c, derivation, review), /未完成独立推导/);
  derivation.items[0].status = 'established'; review.derivationHash = digest(derivation); review.items[0].sourceFaithful = false;
  assert.throws(() => applyReferenceReview(c, derivation, review), /原题核验/);
});

test('a corrected answer cannot be accepted silently under confirmed status', () => {
  const c = candidate(), { derivation, review } = audit(c);
  review.items[0].referenceAnswer = 'A different verified result';
  assert.throws(() => applyReferenceReview(c, derivation, review), /缺少修正标记/);
  review.items[0].referenceAnswer = c.plan.items[0].referenceAnswer;
  review.items[0].criteria = 'Changed scoring condition';
  assert.throws(() => applyReferenceReview(c, derivation, review), /缺少修正标记/);
});
