import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import { createModels, createAssistantMessageEventStream, validateToolArguments } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { StudentRegistry, freezeRubric, validateFrozenRubric, createCoordinator, createStudentAgent, parseConcurrency } from '../src/cohort-core.mjs';
import { isolateStudentCache, schemeOverviewReader } from '../src/cohort-runtime.mjs';
import { Budget, digest } from '../src/core.mjs';
import { MS_WRITE_SCHEMA, expandMSItems } from '../src/rubric-contract.mjs';

test('shared MS overview preserves the whole frame and checks its original before reuse',async t=>{
  const dir=await mkdtemp(join(tmpdir(),'ms-overview-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  // A 96 × 48 page with exactly white outer padding and a single ink pixel.
  const source=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAGAAAAAwCAIAAABhdOiYAAAAiUlEQVR4nO3WsQ2AMAwAwYSejmHYf7EwAXmJlrvWSvOypcy11uDdsZkhULNBQaAgUBDoU6D7vOrhX0z/oD0nFgQKAgWBgkBBoCBQECgIFAQKAgWBgkBBoCBQECgIFAQKAgWBgkBBoCBQECgIFAQKAgWBgkBBoCBQECgIFAQKAgWBgkBBoCDQ2HsAJn8GsrlmuWEAAAAASUVORK5CYII=','base64');
  const page={absolute_path:join(dir,'source.png'),sha256:digest(source)};
  const get=schemeOverviewReader(dir,32);
  await writeFile(page.absolute_path,Buffer.from('changed'));
  await assert.rejects(get(page),/Original page changed/);
  await writeFile(page.absolute_path,source);
  const first=get(page);
  assert.equal(get(page),first);
  const bytes=Buffer.from((await first).data,'base64');
  assert.deepEqual([bytes.readUInt32BE(16),bytes.readUInt32BE(20)],[32,16]);
  assert.deepEqual(await readFile(join(dir,`ms-32-${page.sha256}.png`)),bytes);
  assert.deepEqual(await readFile(page.absolute_path),source);
});

function msWrite(items) {
  return {items:items.map(i=>({q:i.question_id,id:i.item_id,max:i.max_score,criteria:i.criteria,pages:i.source_pages,
    related:i.related_item_ids,visual:i.requires_source_image,why:i.image_reason,uncertainties:i.uncertainties,
    points:i.scoring_points.map(p=>({id:p.point_id,max:p.max_score,awards:p.allowed_awards,type:p.award_type,condition:p.condition,depends:p.depends_on,source:p.source_text,pages:p.source_pages})),
    routes:i.routes.map(r=>({id:r.route_id,points:r.point_ids,description:r.description}))}))};
}

const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
const scheme = { sha256: 'source-bound', pages: [{ page: 1, role: 'scheme' }] };
const student = { pages: [{ page: 1, role: 'student' }] };
const rawRubric = () => ({ general_instructions: [{ text: 'Accept equivalent methods; do not repair submitted evidence.', source_pages: [1] }],
  items: [{ question_id: 'B', item_id: 'B(ii)', max_score: 2, criteria: 'One method mark for a supported transformation; one accuracy mark for the correct final value.',
    source_pages: [1], related_item_ids: [], requires_source_image: false, image_reason: '', uncertainties: [] }], unresolved_notes: [] });
const answer = () => ({ items: [{ question_id: 'B', item_id: 'B(ii)', max_score: 2, score: 1, scheme_pages: [1], student_pages: [1], reason: 'Method supported; final differs.', review_required: false }], review_notes: [] });
const sourceReview = () => ({summary:'Checked original source and staged rules',item_checks:[{item_id:'B(ii)',verdict:'verified',source_pages:[1],note:'Source supports rules'}],revised_items:[],removed_items:[],general_instructions:null,unresolved_notes:null});
let callId = 0;
const call = (name, args) => ({ type: 'toolCall', id: `tool-${++callId}`, name, arguments: args });
const log = async () => {};
const readImage = async page => ({ type: 'image', mimeType: 'image/png', data: `${page.role}-IMAGE-ONLY` });
function fakeStream(turns, observations) {
  return (_model, context) => {
    observations.push(structuredClone(context));
    const content = turns.shift() ?? [{ type: 'text', text: 'Stopped.' }];
    const stream = createAssistantMessageEventStream();
    const message = { role: 'assistant', content, api: model.api, provider: model.provider, model: model.id, timestamp: Date.now(),
      stopReason: content.some(x => x.type === 'toolCall') ? 'toolUse' : 'stop',
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
    queueMicrotask(() => stream.push({ type: 'done', reason: message.stopReason, message })); return stream;
  };
}
test('30 distinct student tasks are bounded, isolated on failure, and never duplicated', async () => {
  const ids = Array.from({ length: 30 }, (_, i) => `student-${i}`); const registry = new StudentRegistry(ids, 4);
  let active = 0; let peak = 0; const invoked = [];
  const pending = registry.dispatch(ids, 3, async id => {
    invoked.push(id); active++; peak = Math.max(peak, active);
    await new Promise(resolve => setTimeout(resolve, 2)); active--;
    if (id === 'student-7') throw Error('isolated failure');
    return { status: 'submitted' };
  });
  await assert.rejects(registry.dispatch(['student-0'], 1, () => assert.fail()), /already attempted/);
  const rows = await pending;
  assert.equal(peak, 3); assert.equal(invoked.length, 30); assert.equal(new Set(invoked).size, 30);
  assert.equal(rows.filter(x => x.status === 'failed').length, 1); assert.equal(rows.filter(x => x.status === 'submitted').length, 29); assert.equal(registry.terminal(), true);
});
test('default concurrency has no fixed ceiling while explicit limits remain enforceable', async () => {
  const ids = Array.from({ length: 30 }, (_, i) => `s${i}`); const registry = new StudentRegistry(ids);
  let active = 0; let peak = 0;
  await registry.dispatch(ids, 30, async () => {
    active++; peak = Math.max(peak, active); await new Promise(resolve => setTimeout(resolve, 2)); active--;
    return { status: 'submitted' };
  });
  assert.equal(peak, 30); assert.equal(registry.terminal(), true);
  assert.equal(parseConcurrency(undefined), null); assert.equal(parseConcurrency('unlimited'), null);
  assert.equal(parseConcurrency('30'), 30);
  for (const value of ['0','-1','4.5','Infinity','invalid']) assert.throws(() => parseConcurrency(value));
  await assert.rejects(new StudentRegistry(['x'], 1).dispatch(['x'], 2, async () => ({ status: 'submitted' })), /concurrency/);
});
test('unlimited coordinator advertises no maximum in the model tool schema', () => {
  const main = createCoordinator({ model, scheme, studentIds: ['x','y'], reusedRubric: freezeRubric(rawRubric(),scheme,new Set([1])),
    readImage, log, streamFn: fakeStream([], []), persistRubric: async () => {}, executeStudent: async () => {}, persistCohort: async () => {} });
  const field = main.agent.state.tools.find(tool => tool.name === 'grade_students').parameters.properties.concurrency;
  assert.equal('maximum' in field, false);
  assert.match(main.initialPrompt, /No host concurrency ceiling/);
});
test('student cache namespace preserves shared system prefix and original evidence, and remains stable within a lane', () => {
  const base = { messages: [{ role:'system',content:'Shared MS and instructions' },
    {role:'user',content:[{type:'text',text:'Own answer'},{type:'image_url',image_url:{url:'data:image/png;base64,owned'}}]}] };
  const one = isolateStudentCache(structuredClone(base),'run-a/student-x');
  const two = isolateStudentCache(structuredClone(base),'run-a/student-y');
  assert.deepEqual(one.messages[0],base.messages[0]); assert.deepEqual(two.messages[0],base.messages[0]);
  assert.deepEqual(one.messages[1].content.slice(1),base.messages[1].content);
  assert.notEqual(one.messages[1].content[0].text,two.messages[1].content[0].text);
  const next = structuredClone(base); next.messages.push({role:'assistant',content:'Read next page'});
  assert.deepEqual(isolateStudentCache(next,'run-a/student-x').messages[1],one.messages[1]);
  assert.equal(isolateStudentCache({messages:[{role:'user',content:'Own reason'}]},'run-a/feedback-x').messages[0].content[1].text,'Own reason');
  assert.throws(() => isolateStudentCache(structuredClone(base),'bad\ncontent'), /namespace/);
});
test('global cancellation stops queued children instead of scoring them zero', async () => {
  const registry = new StudentRegistry(['a', 'b', 'c'], 1); const controller = new AbortController();
  const rows = await registry.dispatch(['a', 'b', 'c'], 1, async () => { controller.abort(); return { status: 'submitted' }; }, controller.signal);
  assert.deepEqual(rows.map(r => r.status), ['submitted', 'cancelled', 'cancelled']);
  assert.equal(rows[1].total_score, undefined);
});
test('one shared synchronous budget prevents concurrent over-admission and retains unknown reservations', async () => {
  const budget = new Budget({ cap: 0.1 });
  const results = await Promise.allSettled([1,2,3].map(async lane => budget.admit(0.04, { lane })));
  assert.equal(results.filter(x => x.status === 'fulfilled').length, 2);
  assert.equal(results.filter(x => x.status === 'rejected').length, 1);
  assert.equal(budget.chargedOrReserved, 0.08);
});
test('MS freeze requires full source coverage, unique items and bound relations', () => {
  assert.throws(() => freezeRubric(rawRubric(), scheme, new Set()));
  for (const change of [r => r.items.push({ ...r.items[0] }), r => { r.items[0].related_item_ids = ['foreign']; }, r => { r.items[0].source_pages = [9]; }]) {
    const raw = rawRubric(); change(raw); assert.throws(() => freezeRubric(raw, scheme, new Set([1])));
  }
  const raw = rawRubric(); const frozen = freezeRubric(raw, scheme, new Set([1])); raw.items[0].criteria = 'mutated';
  assert.notEqual(frozen.artifact.items[0].criteria, 'mutated');
});
test('fresh child receives text rubric and own pages, with zero automatic MS image transfer', async () => {
  const observations = []; let grade;
  const child = createStudentAgent({ model, scheme, student, frozen: freezeRubric(rawRubric(), scheme, new Set([1])), readImage, log,
    persist: async value => { grade = value; }, streamFn: fakeStream([[call('read_student_pages', { pages: [1] })], [call('submit_grading', answer())]], observations) });
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(grade.total_score, 1); assert.deepEqual(grade.source_image_pages_delivered, []);
  assert.equal(JSON.stringify(observations).includes('scheme-IMAGE-ONLY'), false);
  assert.equal(JSON.stringify(observations).includes('student-IMAGE-ONLY'), true);
  assert.equal(observations.length, 2);
});
test('known rubric uncertainty is inherited without repeated model submissions or altered awards', async () => {
  const raw=rawRubric();raw.items[0].uncertainties=['The source connector remains ambiguous'];
  const submitted=answer(),before=structuredClone(submitted),observations=[];let grade;
  const child=createStudentAgent({model,scheme,student,frozen:freezeRubric(raw,scheme,new Set([1])),readImage,log,
    persist:async value=>{grade=value;},streamFn:fakeStream([[call('read_student_pages',{pages:[1]})],[call('submit_grading',submitted)]],observations)});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(observations.length,2);assert.equal(grade.items[0].review_required,true);assert.equal(grade.status,'review_required');
  for(const key of ['score','reason','student_pages','scheme_pages'])assert.deepEqual(grade.items[0][key],before.items[0][key]);
  assert.deepEqual(submitted,before);
});
test('required diagram is requested on demand before a child may submit', async () => {
  const raw = rawRubric(); raw.items[0].requires_source_image = true; raw.items[0].image_reason = 'Spatial diagram';
  let grade; const observations = [];
  const child = createStudentAgent({ model, scheme, student, frozen: freezeRubric(raw, scheme, new Set([1])), readImage, log,
    persist: async value => { grade = value; }, streamFn: fakeStream([
      [call('read_student_pages', { pages: [1] })], [call('submit_grading', answer())],
      [call('read_ms_pages', { pages: [1] })], [call('submit_grading', answer())],
    ], observations) });
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(grade.total_score, 1); assert.deepEqual(grade.source_image_pages_delivered, [1]);
  assert.ok(child.agent.state.messages.some(x => x.role === 'toolResult' && x.isError));
});
test('frozen item omission or changed maximum cannot be accepted', async () => {
  for (const mutate of [a => { a.items = []; }, a => { a.items[0].max_score = 4; }, a => { a.items[0].item_id = 'foreign'; }]) {
    const invalid = answer(); mutate(invalid); let saves = 0;
    const child = createStudentAgent({ model, scheme, student, frozen: freezeRubric(rawRubric(), scheme, new Set([1])), readImage, log,
      persist: async () => { saves++; }, streamFn: fakeStream([[call('read_student_pages', { pages: [1] })], [call('submit_grading', invalid)]], []) });
    await child.agent.prompt(await child.initialPrompt([])); assert.equal(saves, 0);
  }
});
test('actual Pi main reuses compilation prefix for self-review, then compacts and preserves scoped rereads', async () => {
  const observations = []; const order = []; const raw = rawRubric();
  raw.items[0].scoring_points = [{ point_id:'credit',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'Supported transformation and value',depends_on:[],source_text:raw.items[0].criteria,source_pages:[1] }];
  raw.items[0].routes = [{route_id:'standard',point_ids:['credit'],description:'Original method'}];
  const main = createCoordinator({ model, scheme, studentIds: ['a', 'b'], concurrencyLimit: 2, readImage, log,
    signal: new AbortController().signal,
    persistCandidate: async () => order.push('draft'),
    persistReview: async ({review}) => {order.push('review');assert.equal(review.review_mode,'coordinator');},
    persistRubric: async () => order.push('freeze'), persistCohort: async () => order.push('finish'),
    executeStudent: async (id, frozen, seed) => { order.push(id); assert.ok(frozen.verification); assert.equal(frozen.artifact.items[0].criteria,raw.items[0].criteria); frozen.artifact.items[0].criteria = 'local mutation'; assert.deepEqual(seed, []); return { status: 'submitted' }; },
    streamFn: fakeStream([[call('read_ms_pages', { pages: [1] })], [call('write_rubric_items',msWrite(raw.items)),call('prepare_ms_review',{general_instructions:raw.general_instructions,unresolved_notes:raw.unresolved_notes})],
      [call('submit_ms_review',sourceReview())],
      [call('inspect_ms',{item_ids:['B(ii)'],pages:[1],question:'Confirm the original notation for this selected item.'}),call('grade_students',{student_ids:['b','a'],concurrency:2,initial_ms_pages:[]})],
      [call('finish_cohort',{})]], observations) });
  await main.agent.prompt(main.initialPrompt);
  assert.deepEqual(order,['draft','review','freeze','b','a','finish']); assert.ok(main.getResult());
  assert.equal(JSON.stringify(observations[1]).includes('scheme-IMAGE-ONLY'),true);
  assert.equal(JSON.stringify(observations[2]).includes('scheme-IMAGE-ONLY'),true);
  assert.equal(JSON.stringify(observations[3]).includes('scheme-IMAGE-ONLY'),false);
  assert.equal(JSON.stringify(observations[4]).includes('scheme-IMAGE-ONLY'),true);
  const serialized=[];
  for (const [index,expected] of [[1,1],[2,1],[3,0],[4,1]]) {
    let wire;
    await models.streamSimple(model,observations[index],{apiKey:'local-test-only',maxRetries:0,
      onPayload: payload => { wire = payload; throw Error('Intentional stop before HTTP'); }}).result();
    const images = wire.messages.flatMap(message => Array.isArray(message.content) ? message.content : []).filter(part => part.type === 'image_url');
    assert.equal(images.length,expected);
    serialized.push(wire);
    if(index<3)continue;
    const published = wire.messages.find(message => message.role === 'tool' && typeof message.content === 'string' && message.content.includes('reviewed_rubric_overview'));
    assert.ok(published, 'The actual provider request retains reviewed navigation');
    assert.deepEqual(JSON.parse(published.content).cohort, {
      students: ['a','b'].map(student_id => ({student_id,status:index === 3 ? 'pending' : 'submitted'})),
      concurrency_limit: 2,
    });
    assert.ok(JSON.stringify(wire.messages).includes('Students:'), 'Keep the initial user task as well as current host state');
  }
  assert.deepEqual(serialized[1].messages.slice(0,serialized[0].messages.length),serialized[0].messages,'Review appends to the same provider prefix');
  assert.deepEqual(serialized[1].tools,serialized[0].tools,'The tool prefix remains stable');
  assert.equal(JSON.stringify(observations[2]).includes('student-IMAGE-ONLY'),false);
  const checkpoint=observations[2].messages.find(m=>m.role==='toolResult'&&m.toolName==='prepare_ms_review');
  assert.equal(JSON.stringify(checkpoint).includes(raw.items[0].criteria),false,'Do not duplicate the full candidate');
});

test('cold context retains user constraints and host identities across unknown IDs, partial batches and renamed rosters', async () => {
  for (const ids of [['learner_Z9','pupil_R4'],Array.from({length:30},(_,i)=>`opaque_${i}_x7`)]) {
    const observations=[];const raw=rawRubric();
    raw.items[0].scoring_points=[{point_id:'rule',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:raw.items[0].criteria,depends_on:[],source_text:raw.items[0].criteria,source_pages:[1]}];
    raw.items[0].routes=[{route_id:'original',point_ids:['rule'],description:'Source path'}];
    const main=createCoordinator({model,scheme,studentIds:ids,readImage,log,
      persistCandidate:async()=>{},persistReview:async()=>{},persistRubric:async()=>{},persistCohort:async()=>{},
      executeStudent:async()=>({status:'submitted'}),
      streamFn:fakeStream([
        [call('read_ms_pages',{pages:[1]})],
        [call('write_rubric_items',msWrite(raw.items)),call('prepare_ms_review',{general_instructions:raw.general_instructions,unresolved_notes:[]})],
        [call('submit_ms_review',sourceReview())],
        [call('grade_students',{student_ids:['not_registered'],concurrency:1,initial_ms_pages:[]})],
        [call('grade_students',{student_ids:[ids[0]],concurrency:1,initial_ms_pages:[]})],
        [call('grade_students',{student_ids:ids.slice(1),concurrency:ids.length,initial_ms_pages:[]})],
        [call('finish_cohort',{})],
      ],observations)});
    const constraint='Teacher constraint: preserve unresolved entries for review.';
    await main.agent.prompt(main.initialPrompt+'\n'+constraint);
    assert.ok(main.getResult());
    assert.equal(main.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,1);
    for(const [index,firstStatus,restStatus] of [[3,'pending','pending'],[4,'pending','pending'],[5,'submitted','pending'],[6,'submitted','submitted']]) {
      const context=observations[index];
      assert.ok(JSON.stringify(context).includes(constraint));
      assert.equal(JSON.stringify(context).includes('scheme-IMAGE-ONLY'),false);
      const result=context.messages.find(m=>m.role==='toolResult'&&m.toolName==='submit_ms_review');
      const snapshot=JSON.parse(result.content[0].text).cohort;
      assert.deepEqual(snapshot,{students:ids.map((student_id,i)=>({student_id,status:i===0?firstStatus:restStatus})),concurrency_limit:null});
    }
    const original=main.agent.state.messages.find(m=>m.role==='toolResult'&&m.toolName==='submit_ms_review');
    assert.ok(JSON.parse(original.content[0].text).reviewed_rubric, 'Compaction must not mutate the persisted original result');
  }
});

test('self-review must consume its checkpoint, cover all items and persist uncertainty before dispatch', async () => {
  const raw=rawRubric();raw.items[0].scoring_points=[{point_id:'credit',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:raw.items[0].criteria,depends_on:[],source_text:raw.items[0].criteria,source_pages:[1]}];
  raw.items[0].routes=[{route_id:'original',point_ids:['credit'],description:'Source route'}];
  const revised=structuredClone(raw.items[0]);revised.uncertainties=['Connector scope is unclear'];revised.requires_source_image=true;revised.image_reason='Check the unclear source connector';
  const uncertain=sourceReview();uncertain.revised_items=[revised];uncertain.item_checks[0].verdict='uncertain';uncertain.item_checks[0].note='Connector scope needs review';
  const phases=[],contexts=[],order=[];let savedCandidate,savedReview;let imageReads=0;
  const generated=fakeStream([
    [call('read_ms_pages',{pages:[1]})],
    [call('write_rubric_items',msWrite(raw.items)),call('prepare_ms_review',{general_instructions:raw.general_instructions,unresolved_notes:[]}),call('submit_ms_review',sourceReview()),call('grade_students',{student_ids:['learner'],concurrency:1,initial_ms_pages:[]})],
    [call('submit_ms_review',{...sourceReview(),item_checks:[]})],
    [call('submit_ms_review',uncertain)],
    [call('grade_students',{student_ids:['learner'],concurrency:1,initial_ms_pages:[1]}),call('finish_cohort',{})],
  ],contexts);
  const main=createCoordinator({model,scheme,studentIds:['learner'],log,
    readImage:async page=>{imageReads++;return readImage(page);},
    persistCandidate:async value=>{savedCandidate=structuredClone(value);order.push('candidate');},
    persistReview:async value=>{savedReview=structuredClone(value);order.push('review');},
    persistRubric:async value=>{assert.equal(value.verification.status,'review_required');order.push('freeze');},persistCohort:async()=>order.push('finish'),
    executeStudent:async(_id,frozen,pages)=>{order.push('student');assert.equal(frozen.verification.review_mode,'coordinator');assert.deepEqual(pages,[1]);assert.ok(frozen.artifact.items[0].uncertainties.length);return {status:'submitted'};},
    streamFn:(...args)=>{phases.push(main.getMSPhase());return generated(...args);}});
  await main.agent.prompt(main.initialPrompt);
  assert.ok(main.getResult());assert.equal(imageReads,1);
  assert.deepEqual(order,['candidate','review','freeze','student','finish']);
  assert.deepEqual(phases,['ms_compilation','ms_compilation','ms_verification','ms_verification',null]);
  assert.equal(main.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,3);
  assert.deepEqual(savedCandidate.artifact.items[0].uncertainties,[]);
  assert.equal(savedReview.review.candidate_hash,savedCandidate.hash);
  assert.equal(savedReview.review.review_mode,'coordinator');
  assert.notEqual(savedReview.frozen.hash,savedCandidate.hash);
});

test('source references allow declared general rules and reject unrelated MS pages', async () => {
  const expanded = { ...scheme, pages: [1,2,3].map(page => ({ page, role: 'scheme' })) };
  const raw = rawRubric(); raw.general_instructions[0].source_pages = [2];
  const bad = answer(); bad.items[0].scheme_pages = [1,3];
  const good = answer(); good.items[0].scheme_pages = [1,2];
  let saved;
  const child = createStudentAgent({ model, scheme: expanded, student, frozen: freezeRubric(raw, expanded, new Set([1,2,3])), readImage, log,
    persist: async value => { saved = value; }, streamFn: fakeStream([[call('read_student_pages', { pages: [1] })], [call('submit_grading', bad)], [call('submit_grading', good)]], []) });
  await child.agent.prompt(await child.initialPrompt([]));
  assert.deepEqual(saved.items[0].scheme_pages, [1,2]);
  assert.ok(child.agent.state.messages.some(x => x.role === 'toolResult' && x.isError));
});

test('short MS fields preserve complete source truth across renamed and multilingual variants',()=>{
  for(const [id,page,condition] of [['Archive',1,'The record must contain both a date and a signature.'],['文书乙',7,'记录必须同时有日期和签名。'],['Control.Z',11,'Require a signature AND a date on the record.']]){
    const doc={sha256:'neutral-source',pages:[{page},{page:page+1}]};
    const point=(point_id,max_score,depends_on=[])=>({point_id,max_score,allowed_awards:[0,max_score/2,max_score],award_type:'credit',condition,depends_on,source_text:`Source: ${condition}`,source_pages:[page]});
    const original={question_id:id,item_id:id,max_score:3,criteria:'Record verification by either approved route',source_pages:[page],related_item_ids:[],requires_source_image:true,image_reason:'The connector scope is unclear',uncertainties:['Two lines may share a connector; preserve source review'],
      scoring_points:[point('common',1),point('written',2,['common']),point('digital',2,['common'])],
      routes:[{route_id:'written',point_ids:['common','written'],description:'Signed written record'},{route_id:'digital',point_ids:['common','digital'],description:'Authenticated digital record'}]};
    const raw=msWrite([original]);
    const checked=value=>validateToolArguments({name:'write_rubric_items',parameters:MS_WRITE_SCHEMA},call('write_rubric_items',value));
    checked(raw);assert.deepEqual(expandMSItems(raw),[original]);
    const freeze=value=>freezeRubric({general_instructions:[],unresolved_notes:[],items:expandMSItems(value)},doc,new Set(doc.pages.map(p=>p.page)));
    assert.deepEqual(freeze(raw).artifact.items[0],original);
    for(const mutate of [v=>delete v.items[0].points[0].condition,v=>delete v.items[0].uncertainties,v=>{v.items[0].points[0].foreign='not a source field';}]){
      const bad=structuredClone(raw);mutate(bad);assert.throws(()=>checked(bad));assert.throws(()=>expandMSItems(bad));
    }
    for(const mutate of [v=>{v.items[0].points[0].pages=[page+1];},v=>{v.items[0].points[0].awards=[.5,1];},v=>{v.items[0].points[0].depends=['written'];}]){
      const bad=structuredClone(raw);mutate(bad);checked(bad);assert.throws(()=>freeze(bad));
    }
    const changed=structuredClone(raw);changed.items[0].points[0].condition='Either date OR signature suffices.';
    assert.notEqual(freeze(changed).hash,freeze(raw).hash,'Short transport must preserve a meaning-changing condition, never normalize it away');
    const roundTrip=expandMSItems(raw);roundTrip[0].scoring_points[0].source_text='changed locally';assert.notEqual(raw.items[0].points[0].source,'changed locally');
  }
});

test('actual Pi main stages more than four complete items without a fixed phase token quota',async()=>{
  const raw=rawRubric();
  const point={point_id:'record',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'A record includes both required source entries.',depends_on:[],source_text:'Both entries: 2; one: 1.',source_pages:[1]};
  raw.items=Array.from({length:6},(_,i)=>({...raw.items[0],question_id:`Document-${i}`,item_id:`Document-${i}`,scoring_points:[structuredClone(point)],routes:[{route_id:'source',point_ids:['record'],description:'Source record'}]}));
  const review={...sourceReview(),item_checks:raw.items.map(i=>({item_id:i.item_id,verdict:'verified',source_pages:[1],note:'Both source entries checked'}))};
  const observations=[];let candidate;
  const main=createCoordinator({model,scheme,studentIds:['learner'],readImage,log,
    persistCandidate:async value=>{candidate=value;},persistReview:async()=>{},persistRubric:async()=>{},persistCohort:async()=>{},
    executeStudent:async(_id,frozen)=>{assert.deepEqual(frozen.artifact.items,raw.items);return {status:'submitted'};},
    streamFn:fakeStream([[call('read_ms_pages',{pages:[1]})],[call('write_rubric_items',msWrite(raw.items)),call('prepare_ms_review',{general_instructions:raw.general_instructions,unresolved_notes:[]})],[call('submit_ms_review',review)],[call('grade_students',{student_ids:['learner'],concurrency:1,initial_ms_pages:[]}),call('finish_cohort',{})]],observations)});
  const tool=main.agent.state.tools.find(t=>t.name==='write_rubric_items');
  assert.equal('maxItems' in tool.parameters.properties.items,false);assert.match(tool.description,/no fixed item-count or phase token quota/);assert.match(main.initialPrompt,/model response capacity/);
  await main.agent.prompt(main.initialPrompt);
  assert.ok(main.getResult());assert.deepEqual(candidate.artifact.items,raw.items);assert.equal(main.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,0);
  assert.equal(JSON.stringify(observations[2]).includes('scheme-IMAGE-ONLY'),true,'Same main context still contains original pages at review');
  let wire;await models.streamSimple(model,observations[1],{apiKey:'local-test-only',maxRetries:0,onPayload:payload=>{wire=payload;throw Error('Intentional stop before HTTP');}}).result();
  const transmitted=wire.tools.find(t=>t.function?.name==='write_rubric_items').function.parameters;
  assert.deepEqual(transmitted,MS_WRITE_SCHEMA);assert.equal('maxItems' in transmitted.properties.items,false);
});

test('saved rubric reuse rejects changed content, source or source-page ownership', () => {
  const saved = freezeRubric(rawRubric(), scheme, new Set([1]));
  assert.equal(validateFrozenRubric(saved, scheme).hash, saved.hash);
  assert.throws(() => validateFrozenRubric(saved, { ...scheme, sha256: 'another-source' }), /mismatch/);
  const changed = structuredClone(saved); changed.artifact.items[0].max_score = 3;
  assert.throws(() => validateFrozenRubric(changed, scheme), /mismatch/);
  assert.throws(() => validateFrozenRubric(saved, { ...scheme, pages: [{ page: 2 }] }), /Invalid source pages/);
});

test('actual Pi replay delegates with the saved rubric and cannot publish or mutate it', async () => {
  const saved = freezeRubric(rawRubric(), scheme, new Set([1])); const observations = []; const invocations = [];
  const main = createCoordinator({ model, scheme, studentIds: ['x','y'], concurrencyLimit: 2, reusedRubric: saved,
    readImage: async () => assert.fail('Replay must not automatically reread MS images'), log,
    persistRubric: async () => assert.fail('Replay must not compile MS'), persistCohort: async () => {},
    executeStudent: async (id, frozen) => { invocations.push(id); assert.equal(frozen.hash, saved.hash); frozen.artifact.items[0].criteria = 'local mutation'; return { status: 'submitted' }; },
    streamFn: fakeStream([[call('grade_students', { student_ids: ['y','x'], concurrency: 2, initial_ms_pages: [] })], [call('finish_cohort', {})]], observations) });
  await main.agent.prompt(main.initialPrompt);
  assert.deepEqual(invocations, ['y','x']); assert.ok(main.getResult());
  assert.equal(main.getRubric().hash, saved.hash); assert.equal(main.getRubric().artifact.items[0].criteria, rawRubric().items[0].criteria);
  assert.equal(main.agent.state.tools.some(x => ['prepare_ms_review','submit_ms_review'].includes(x.name)), false);
  assert.equal(main.agent.state.tools.some(x => x.name === 'read_ms_pages'), false);
  assert.equal(JSON.stringify(observations).includes('scheme-IMAGE-ONLY'), false);
});
