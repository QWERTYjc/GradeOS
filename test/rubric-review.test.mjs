import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { freezeRubric, validateFrozenRubric, validatePointDecisions } from '../src/rubric-contract.mjs';
import { applyMSReview } from '../src/ms-review.mjs';
import { createStudentAgent } from '../src/cohort-core.mjs';

const scheme = {sha256:'neutral-source',pages:[{page:1},{page:2}]};
const student = {pages:[{page:3}]};
const readImage = async page => ({type:'image',mimeType:'image/png',data:`original-${page.page}`});
const log = async () => {};
const models = createModels(); models.setProvider(openrouterProvider()); const model = models.getModel('openrouter','openai/gpt-6.1-terra');
const point = (id,condition,value=1,deps=[]) => ({point_id:id,max_score:value,allowed_awards:[0,value],award_type:'credit',condition,depends_on:deps,source_text:condition,source_pages:[1]});
function rawRubric(id='Essay-a') {
  return {general_instructions:[{text:'Accept equivalent support and valid alternative methods.',source_pages:[2]}],unresolved_notes:[],items:[{
    item_id:id,question_id:'Essay',max_score:3,criteria:'Source and supported inference, or equivalent integrated explanation.',source_pages:[1],related_item_ids:[],
    requires_source_image:false,image_reason:'',uncertainties:[],
    scoring_points:[point('origin','Identify provenance'),point('inference','Explain the supported inference',2,['origin']),point('integrated','Integrated valid provenance and inference',3)],
    routes:[{route_id:'separate',point_ids:['origin','inference'],description:'Separate explanation'},
      {route_id:'integrated',point_ids:['integrated'],description:'Equivalent integrated explanation'}],
  }]};
}
const candidate = raw => freezeRubric(raw ?? rawRubric(),scheme,new Set([1,2]));
const review = id => ({summary:'All source pages checked including general scope.',item_checks:[{item_id:id ?? 'Essay-a',verdict:'verified',source_pages:[1],note:'Rules preserved'}],
  revised_items:[],removed_items:[],general_instructions:null,unresolved_notes:null});
const gradeRow = () => ({item_id:'Essay-a',question_id:'Essay',score:3,max_score:3,scheme_pages:[1],student_pages:[3],reason:'Evidence supports both criteria.',review_required:false,
  selected_route:'separate',point_decisions:[{point_id:'origin',score:1,evidence:'Source named',student_pages:[3],reason:'Provenance identified'},
    {point_id:'inference',score:2,evidence:'Supported conclusion explained',student_pages:[3],reason:'Valid inference from source'}]});
let counter = 0;
const tool = (name,args) => ({type:'toolCall',name,id:`t-${++counter}`,arguments:args});
function stream(turns,contexts=[]) {
  return (_model,context) => {
    contexts.push(structuredClone(context)); const content = turns.shift() ?? [{type:'text',text:'No valid result'}];
    const s = createAssistantMessageEventStream(); const stopReason = content.some(c => c.type==='toolCall') ? 'toolUse' : 'stop';
    queueMicrotask(() => s.push({type:'done',reason:stopReason,message:{role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason,
      usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));
    return s;
  };
}

test('alternative routes retain the source maximum instead of adding alternative credit', () => {
  const frozen = candidate(); assert.equal(frozen.artifact.version,2);
  assert.equal(frozen.artifact.items[0].scoring_points.reduce((n,p)=>n+p.max_score,0),6);
  assert.equal(frozen.artifact.items[0].max_score,3);
  const row = gradeRow(); validatePointDecisions(row,frozen.artifact.items[0],student);
  row.selected_route = 'integrated'; row.point_decisions = [{point_id:'integrated',score:3,evidence:'Integrated supported explanation',student_pages:[3],reason:'Both conditions satisfied'}];
  validatePointDecisions(row,frozen.artifact.items[0],student);
  row.point_decisions.push(gradeRow().point_decisions[0]);
  assert.throws(()=>validatePointDecisions(row,frozen.artifact.items[0],student),/route/);
});
test('neutral identifiers, point order and equivalent source wording preserve the structural contract', () => {
  for (const [id,text,reverse] of [['Source-Z','Explain the supported inference',false],['论证乙','说明材料所支持的推论',true],['Appendix.4','State the inference justified by this source.',false]]) {
    const raw = rawRubric(id); raw.items[0].scoring_points[1].condition = text;
    if (reverse) { raw.items[0].scoring_points.reverse(); raw.items[0].routes[0].point_ids.reverse(); }
    const frozen = candidate(raw); const row=gradeRow(); row.item_id=id;
    validatePointDecisions(row,frozen.artifact.items[0],student);
    assert.equal(applyMSReview(review(id),frozen,scheme,new Set([1,2])).frozen.hash,frozen.hash);
  }
});
test('hard negatives cannot award dependent credit or foreign evidence merely because point IDs match', () => {
  const item=candidate().artifact.items[0];
  for (const mutate of [r=>{r.point_decisions[0].score=0;r.score=2;},r=>{r.point_decisions[1].student_pages=[2];},r=>{r.point_decisions[1].point_id='integrated';},r=>{r.score=2;}]) {
    const row=gradeRow();mutate(row);assert.throws(()=>validatePointDecisions(row,item,student));
  }
});
test('ambiguous evidence propagates unknown, while unrelated valid source items are unaffected', () => {
  const raw=rawRubric();const unrelated=structuredClone(raw.items[0]);unrelated.item_id='Science-Z';unrelated.question_id='Science';raw.items.push(unrelated);
  const frozen=candidate(raw);const row=gradeRow();row.point_decisions[1].score=null;row.score=null;row.review_required=true;
  validatePointDecisions(row,frozen.artifact.items[0],student);
  row.score=1;assert.throws(()=>validatePointDecisions(row,frozen.artifact.items[0],student),/unknown/);
  validatePointDecisions(gradeRow(),frozen.artifact.items[1],student);
});
test('cycles, missing routes and unbound point sources fail before any reviewer or student runs', () => {
  for (const mutate of [r=>r.items[0].scoring_points[0].depends_on.push('inference'),r=>r.items[0].routes.pop(),
    r=>r.items[0].scoring_points[0].source_pages.push(2),r=>r.items[0].routes[0].point_ids.pop()]) {
    const raw=rawRubric();mutate(raw);assert.throws(()=>candidate(raw));
  }
});
test('source review covers every item and source page, binds corrected versions and retains uncertainty', () => {
  const original=candidate();const hash=original.hash;
  assert.throws(()=>applyMSReview(review(),original,scheme,new Set([1])),/complete/);
  const missing=review();missing.item_checks=[];assert.throws(()=>applyMSReview(missing,original,scheme,new Set([1,2])),/Incomplete/);
  const revised=review();revised.revised_items=[structuredClone(original.artifact.items[0])];
  revised.revised_items[0].criteria='Source-supported correction to interpretation';
  revised.item_checks[0].verdict='corrected';
  const result=applyMSReview(revised,original,scheme,new Set([1,2]));
  assert.notEqual(result.frozen.hash,hash);assert.equal(original.hash,hash);assert.equal(result.frozen.verification.candidate_hash,hash);
  assert.equal(validateFrozenRubric(result.frozen,scheme).hash,result.frozen.hash);
  assert.throws(()=>validateFrozenRubric(original,scheme),/source verification/);
  const corrupt=structuredClone(result.frozen);corrupt.verification.final_rubric_hash=hash;
  assert.throws(()=>validateFrozenRubric(corrupt,scheme),/verification/);
  const uncertain=review();uncertain.item_checks[0].verdict='uncertain';uncertain.item_checks[0].note='Ambiguous source scope';
  const unresolved=applyMSReview(uncertain,original,scheme,new Set([1,2]));
  assert.equal(unresolved.review.status,'review_required');assert.deepEqual(unresolved.frozen.artifact.items[0].uncertainties,['Ambiguous source scope']);
});
test('source issues require delivered original pages and preserve frozen rules and review state', async () => {
  const frozen=applyMSReview(review(),candidate(),scheme,new Set([1,2])).frozen;const originalHash=frozen.hash;let saved;
  const issue={item_id:'Essay-a',point_ids:['origin'],scheme_pages:[1],observation:'Original condition has unclear scope',impact:'Cannot resolve origin credit',blocks_award:true};
  const valid=gradeRow();valid.score=null;valid.review_required=true;valid.point_decisions.forEach(p=>p.score=null);
  const child=createStudentAgent({model,scheme,student,frozen,readImage,log,persist:async value=>saved=value,
    streamFn:stream([[tool('report_ms_issue',issue)], [tool('read_ms_pages',{pages:[1]}),tool('read_student_pages',{pages:[3]}),tool('report_ms_issue',issue)],
      [tool('submit_grading',{items:[gradeRow()],review_notes:[]})], [tool('submit_grading',{items:[valid],review_notes:['Source scope needs review']})]])});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.ok(saved);assert.equal(saved.total_score,null);assert.equal(saved.source_issues.length,1);assert.equal(frozen.hash,originalHash);
  assert.equal(child.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,2);
});

test('fractional awards require explicit source permission and source issues may cite read general rules', async () => {
  const raw=rawRubric();const row=gradeRow();row.point_decisions[1].score=0.5;row.score=1.5;
  assert.throws(()=>validatePointDecisions(row,raw.items[0],student),/point award/);
  raw.items[0].scoring_points[1].allowed_awards=[0,0.5,2];
  validatePointDecisions(row,candidate(raw).artifact.items[0],student);
  const frozen=applyMSReview(review(),candidate(),scheme,new Set([1,2])).frozen;let saved;
  const issue={item_id:'Essay-a',point_ids:[],scheme_pages:[2],observation:'General source instruction is ambiguous',impact:'Scope requires checking',blocks_award:false};
  const answer=gradeRow();answer.review_required=true;
  const child=createStudentAgent({model,scheme,student,frozen,readImage,log,persist:async value=>saved=value,
    streamFn:stream([[tool('read_ms_pages',{pages:[2]}),tool('read_student_pages',{pages:[3]}),tool('report_ms_issue',issue)],
      [tool('submit_grading',{items:[answer],review_notes:['General scope review']})]])});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(saved.source_issues[0].scheme_pages[0],2);assert.equal(saved.status,'review_required');
});
