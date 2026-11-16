import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { mkdtemp, rm, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { createFeedbackAgent, validateFeedback, renderStudentFeedback } from '../src/student-feedback.mjs';
import { freezeRubric } from '../src/cohort-core.mjs';
import { digest } from '../src/core.mjs';
import { ResultsStore } from '../src/results-store.mjs';
import { freezeJson } from '../src/cohort-runtime.mjs';
import { createReporting } from '../src/cohort-reporting.mjs';
import {compactFeedbackPacket,expandCompactFeedback} from '../src/compact-feedback.mjs';
import {exceptionProbeFixture} from '../src/exception-probe-fixture.mjs';

function fixture(id = 'R(ii)', criterion = 'One mark for identifying the source and one for its relevance.') {
  const frozen = freezeRubric({ general_instructions: [], unresolved_notes: [], items: [{ item_id: id, question_id: 'R',
    max_score: 2, criteria: criterion, source_pages: [1], related_item_ids: [], requires_source_image: false,
    image_reason: '', uncertainties: [] }] }, { sha256: 'neutral-source', pages: [{ page: 1 }] }, new Set([1]));
  const grade = { rubric_hash: frozen.hash, items: [{ item_id: id, question_id: 'R', max_score: 2, score: 1,
    reason: 'Source identified; relevance not supported.', student_pages: [2], scheme_pages: [1], review_required: false }],
    total_score: 1, max_score: 2, review_notes: [], status: 'provisional' };
  const raw = { summary: '原记录显示能识别来源，但相关性说明不足。建议补写来源与论点之间的联系，再逐句核查证据。',
    strengths: [{ observation: '能够识别材料来源。', item_ids: [id] }],
    priorities: [{ action: '补写来源与论点的联系。', success_check: '能指出哪条材料支持哪项论点。', item_ids: [id] }],
    items: [{ item_id: id, criterion: '识别来源并说明其相关性。', assessment: '记录支持来源识别，相关性说明缺少支持。',
      next_step: '将论点与材料逐条对应。', review_recommended: false, review_reason: '' }] };
  return { frozen, grade, raw };
}
test('compact feedback retains every source/evidence judgment once, including repeated point ids and exception authority',()=>{
  const f=exceptionProbeFixture();f.primary.official_reference='PRIVATE-GOLDEN';
  const before=digest(f.primary),packet=compactFeedbackPacket(f.primary,f.frozen);
  assert.equal(digest(f.primary),before);assert.equal(JSON.stringify(packet).includes('PRIVATE-GOLDEN'),false);
  assert.equal(packet.items.length,f.primary.items.length);
  for(const item of f.primary.items){
    const row=packet.items.find(i=>i.id===item.item_id);assert.equal(row.reason,undefined);
    const source=f.frozen.artifact.items.find(i=>i.item_id===item.item_id);
    assert.equal(row.criterion,source.criteria);assert.deepEqual(row.selected_route,source.routes.find(r=>r.route_id===item.selected_route));
    for(const p of item.point_decisions){const cells=row.points.find(t=>t[0]===p.point_id);
      assert.equal(cells[1],p.score);assert.equal(cells[5],p.evidence);assert.equal(cells[6],p.reason);assert.equal(cells[9],p.rule_ref);}
  }
  assert.equal(packet.general_rules[0].text,f.frozen.artifact.general_instructions[0].text);
});
test('compact feedback cannot omit items, add scores, hide null/review, or guess identity by position',()=>{
  const {frozen,grade,raw}=fixture();
  const compact={...raw,items:[[raw.items[0].item_id,raw.items[0].assessment,raw.items[0].next_step,'']]};
  for(const mutate of [r=>r.items[0].push('2'),r=>r.total_score=2,r=>r.items[0][0]='other',r=>r.items=[]]){
    const bad=structuredClone(compact);mutate(bad);assert.throws(()=>validateFeedback(expandCompactFeedback(bad,grade),grade,frozen));
  }
  grade.items[0].score=null;grade.items[0].review_required=true;compact.strengths=[];
  assert.throws(()=>validateFeedback(expandCompactFeedback(compact,grade),grade,frozen),/review/);
  compact.items[0][3]='原来源许可不明，保留待定。';
  assert.equal(validateFeedback(expandCompactFeedback(compact,grade),grade,frozen).items[0].review_recommended,true);
});
test('compact actual Pi feedback submits model commentary while rendering original complete source criteria',async()=>{
  const {frozen,grade,raw}=fixture();const compact={...raw,items:[[raw.items[0].item_id,raw.items[0].assessment,raw.items[0].next_step,'']]};
  let saved,calls=0,ctx;const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
  const child=createFeedbackAgent({model,grade,frozen,mode:'compact-v2',log:async()=>{},persist:async f=>{saved=f;},streamFn:(_m,context)=>{
    calls++;ctx=context;const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',content:[{type:'toolCall',id:'compact',name:'submit_student_feedback',arguments:compact}],usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;
  }});
  await child.agent.prompt(child.initialPrompt);assert.equal(calls,1);assert.equal(saved.version,2);assert.equal(saved.items[0].assessment,compact.items[0][1]);
  assert.ok(renderStudentFeedback('x',grade,frozen,saved).includes(frozen.artifact.items[0].criteria));
  assert.equal(JSON.stringify(ctx).includes('Frozen shared MS:'),false);
});

test('feedback cannot introduce awards, foreign evidence or incomplete coverage', () => {
  const { frozen, grade, raw } = fixture();
  for (const mutate of [x => x.total_score = 2, x => x.items[0].score = 2, x => x.items = [],
    x => x.items.push({ ...x.items[0] }), x => x.items[0].item_id = 'elsewhere',
    x => x.strengths[0].item_ids = ['elsewhere']]) {
    const candidate = structuredClone(raw); mutate(candidate);
    assert.throws(() => validateFeedback(candidate, grade, frozen));
  }
  assert.equal(grade.total_score, 1);
});
test('null and flagged awards retain review; a zero score cannot support a strength', () => {
  const { frozen, grade, raw } = fixture();
  grade.items[0].score = null; grade.items[0].review_required = true;
  assert.throws(() => validateFeedback(raw, grade, frozen), /review/);
  raw.items[0].review_recommended = true; raw.items[0].review_reason = '原记录无法确认。'; raw.strengths = [];
  assert.equal(validateFeedback(raw, grade, frozen).items[0].review_recommended, true);
  grade.items[0].score = 0; raw.strengths = [{ observation: 'Unsupported', item_ids: ['R(ii)'] }];
  assert.throws(() => validateFeedback(raw, grade, frozen), /positive/);
});
test('neutral identifier and equivalent criterion variants preserve feedback bindings without score changes', () => {
  for (const [id, criterion] of [['Z.4','Identify the source; explain why it is relevant.'],
    ['源-乙','说明材料来源及其与论点的关系。'], ['other(iii)','Relevance and provenance may be stated in either order.']]) {
    const { frozen, grade, raw } = fixture(id, criterion); const before = digest(grade);
    const feedback = validateFeedback(raw, grade, frozen);
    assert.equal(feedback.grade_hash, before); assert.equal(digest(grade), before);
    assert.ok(renderStudentFeedback('x', grade, frozen, feedback).includes('1 / 2'));
  }
});
test('identical item identifiers cannot override changed rubric meaning or changed frozen grades', () => {
  const a = fixture(); const b = fixture('R(ii)', 'No credit without both source and relevance.');
  assert.throws(() => validateFeedback(a.raw, a.grade, b.frozen), /rubric binding/);
  const feedback = validateFeedback(a.raw, a.grade, a.frozen);
  a.grade.items[0].score = 0; a.grade.total_score = 0;
  assert.throws(() => renderStudentFeedback('x', a.grade, a.frozen, feedback), /source mismatch/);
});
test('actual Pi feedback loop receives only own grade and cannot mutate it or read posthoc fields', async () => {
  const { frozen, grade, raw } = fixture(); grade.official_reference = 'PRIVATE-GOLDEN';
  const before = digest(grade); let saved; let context;
  const models = createModels(); models.setProvider(openrouterProvider()); const model = models.getModel('openrouter','openai/gpt-6.1-terra');
  const streamFn = (_model, packet) => {
    context = structuredClone(packet);
    const stream = createAssistantMessageEventStream();
    queueMicrotask(() => stream.push({ type: 'done', reason: 'toolUse', message: { role: 'assistant', timestamp: Date.now(),
      api: model.api, provider: model.provider, model: model.id, stopReason: 'toolUse',
      content: [{ type: 'toolCall', id: 'submit', name: 'submit_student_feedback', arguments: raw }],
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } } }));
    return stream;
  };
  const child = createFeedbackAgent({ model, streamFn, grade, frozen, log: async () => {}, persist: async value => { saved = value; } });
  await child.agent.prompt(child.initialPrompt);
  assert.ok(saved); assert.equal(digest(grade), before);
  assert.equal(JSON.stringify(context).includes('PRIVATE-GOLDEN'), false);
  assert.deepEqual(child.agent.state.tools.map(tool => tool.name), ['submit_student_feedback']);
});
test('shared results read feedback only when content and original grade binding match', async () => {
  const directory = await mkdtemp(resolve(tmpdir(),'pi-feedback-binding-'));
  try {
    const { frozen, grade, raw } = fixture(); const feedback = validateFeedback(raw, grade, frozen);
    await freezeJson(directory,'grading.json',grade); await freezeJson(directory,'feedback.json',feedback);
    const store = new ResultsStore(resolve(directory,'results'),['x']); await store.init();
    await store.publish('x',{ status:'submitted',rubric_hash:frozen.hash,grading_path:resolve(directory,'grading.json'),
      grading_sha256:digest(await readFile(resolve(directory,'grading.json'))),feedback_status:'submitted',
      feedback_path:resolve(directory,'feedback.json'),feedback_sha256:digest(await readFile(resolve(directory,'feedback.json'))) });
    await store.seal([{student_id:'x',status:'submitted'}],frozen.hash);
    assert.equal((await store.read(['x']))[0].feedback.summary,raw.summary);
    const reporting = createReporting({ store, ensureSealed: async () => store.sealed, getRubric: () => frozen,
      context: { unique_answer_sources: 1 }, output: directory, log: async () => {} });
    const readTool = reporting.tools.find(tool => tool.name === 'read_cohort_results');
    const delivered = JSON.parse((await readTool.execute('read',{student_ids:['x']})).content[0].text).records[0];
    assert.equal(delivered.feedback.summary, raw.summary);
    assert.equal(delivered.result.total_score, grade.total_score);
    await writeFile(resolve(directory,'feedback.json'),'{}');
    await assert.rejects(store.read(['x']), /Feedback content hash/);
  } finally { await rm(directory,{recursive:true,force:true}); }
});
