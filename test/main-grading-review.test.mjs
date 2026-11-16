import test from 'node:test';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {createCoordinator,freezeRubric,StudentRegistry} from '../src/cohort-core.mjs';
import {createMainGradingReview} from '../src/main-grading-review.mjs';
import {createReportContext} from '../src/report-context.mjs';
import {expandBriefFullCredit} from '../src/full-credit-reasons.mjs';
import {validateGrade,digest} from '../src/core.mjs';

function fixture(names=['Letter','Writer','Unknown']){
  const scheme={sha256:'neutral-ms',pages:[{page:1}]},student={sha256:'neutral-paper',pages:[1,2,3].map(page=>({page}))};
  const frozen=freezeRubric({general_instructions:[{text:'Accept equivalent wording. Unreadable work is unresolved, not absent.',source_pages:[1]}],unresolved_notes:[],items:names.map((id,index)=>({
    question_id:id,item_id:id,max_score:2,criteria:'Document type and author.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
    scoring_points:[{point_id:'p',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'Letter by Mira earns two; either attribute earns one.',source_text:'2: letter and Mira; 1: either; 0: neither',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['p'],description:'Attributes'}],
  }))},scheme,new Set([1]));
  frozen.verification={final_rubric_hash:frozen.hash,source_sha256:scheme.sha256,review_hash:digest('neutral test verification')};
  const raw={items:names.map((id,i)=>({id,route:'r',review:false,p:[['p',2,'Correct.',[i+1],'m','=']]})),review_notes:[],source_issues:[]};
  const primary={...validateGrade(expandBriefFullCredit(raw,frozen,student),{documents:{scheme,student}},new Set(['scheme:1','student:1','student:2','student:3'])),rubric_hash:frozen.hash,source_issues:[],student_pages_delivered:[1,2,3]};
  return {frozen,scheme,student,primary,raw};
}
const consume=(views,r)=>{views.transform([{role:'toolResult',...r}]);views.confirmDelivery();};
function setup(f=fixture(),extra={}){
  const views=createReportContext(),saved=[],final=[];
  const review=createMainGradingReview({getRubric:()=>f.frozen,scheme:f.scheme,students:new Map([['s',f.student]]),views,
    readImage:async page=>({type:'image',mimeType:'image/png',data:`original-${page.page}`}),log:async()=>{},
    persist:async(id,name,value)=>{saved.push(value);return{path:name,hash:digest(value)};},onFinalized:async()=>{},...extra});
  review.register({id:'s',primary:f.primary,primaryPath:'immutable-primary',finalize:async grade=>final.push(grade)});
  const tools=Object.fromEntries(review.tools.map(t=>[t.name,t]));
  const submit=ids=>({student_id:'s',primary_hash:digest(f.primary),checked_item_ids:ids,revised_items:[],new_source_issues:[],notes:['Checked all supplied conditions and the literal observations.']});
  return {f,views,saved,final,review,tools,submit};
}
test('ordinary full-credit coverage gates final persistence; read and submit in one response cannot attest review',async()=>{
  const s=setup(),packet=await s.review.prefetch();
  assert.equal(JSON.parse(packet.content[0].text).items.length,3);
  await assert.rejects(s.tools.submit_grading_review.execute('early',s.submit(['Letter','Writer','Unknown'])),/subsequent/);
  assert.equal(s.final.length,0);consume(s.views,packet);
  const next=await s.tools.submit_grading_review.execute('one',s.submit(['Letter']));
  assert.equal(s.review.hasPending(),true);assert.equal(s.final.length,0);
  assert.deepEqual(JSON.parse(next.content[0].text).remaining_item_ids,['Writer','Unknown']);
  assert.equal(s.views.pending().filter(v=>v.kind==='grading_review').length,1);consume(s.views,packet);
  await s.tools.submit_grading_review.execute('rest',s.submit(['Writer','Unknown']));
  assert.equal(s.final.length,1);assert.deepEqual(s.final[0].items,s.f.primary.items);
  assert.equal(s.final[0].main_grading_review.checked_point_count,3);assert.equal(s.review.hasPending(),false);
  await assert.rejects(s.tools.submit_grading_review.execute('again',s.submit(['Letter'])),/completed/);
});
test('generic complete-item patches preserve alternatives and unknown, require consumed owner pages and reject stale/foreign claims',async()=>{
  for(const names of [['Letter','Writer','Unknown'],['文体','作者','待查'],['A.ii','C','Drawing']]){
    const s=setup(fixture(names)),packet=await s.review.prefetch();consume(s.views,packet);const before=digest(s.f.primary);
    const patch=s.submit(names),changed=structuredClone(s.f.raw.items);
    changed[0].p[0]=['p',0,'A receipt by Kian.',[1],'u:c','Neither required attribute is present.'];
    changed[1].p[0]=['p',1,'A letter; author illegible.',[2],'m','Only document type is established.'];
    changed[2].review=true;changed[2].p[0]=['p',null,'[illegible]',[3],'q:u','The required attributes cannot be read.'];patch.revised_items=changed;
    await assert.rejects(s.tools.submit_grading_review.execute('no-images',patch),/original answer/);
    await assert.rejects(s.tools.inspect_student_answer.execute('other',{student_id:'foreign',item_ids:names,pages:[1],question:'Identify the actual document.'}),/Unknown/);
    const image=await s.tools.inspect_student_answer.execute('read',{student_id:'s',item_ids:names,pages:[1,2,3],question:'Check document type and author without completing unreadable words.'});
    await assert.rejects(s.tools.submit_grading_review.execute('same-response',patch),/subsequent/);consume(s.views,image);
    await assert.rejects(s.tools.submit_grading_review.execute('stale',{...patch,primary_hash:'stale'}),/Stale/);
    const invalid=structuredClone(patch);invalid.revised_items[0].p[0][1]=1;
    await assert.rejects(s.tools.submit_grading_review.execute('invalid-score',invalid));assert.equal(s.saved.length,0);
    await s.tools.submit_grading_review.execute('valid',patch);
    assert.deepEqual(s.final[0].items.map(i=>i.score),[0,1,null]);assert.equal(s.final[0].total_score,null);assert.equal(s.final[0].status,'review_required');
    assert.equal(digest(s.f.primary),before);assert.equal(s.saved[0].changes.length,3);
    assert.deepEqual(s.final[0].main_grading_review.inspected_answer_pages,[1,2,3]);
  }
});
test('student registry cannot seal while primary awaits review',async()=>{
  const registry=new StudentRegistry(['s']);await registry.dispatch(['s'],1,async()=>({status:'awaiting_review'}));
  assert.equal(registry.terminal(),false);assert.equal(registry.rows.get('s').status,'awaiting_review');
  registry.rows.get('s').status='submitted';assert.equal(registry.terminal(),true);
});
test('image notes retain the uncommitted full ledger and the observations used for later patches',async()=>{
  const s=setup(),packet=await s.review.prefetch();consume(s.views,packet);
  const image=await s.tools.inspect_student_answer.execute('image',{student_id:'s',item_ids:['Letter'],pages:[1],question:'What document type and author are actually present?'});consume(s.views,image);
  const binding={path:'notes.json',hash:'notes-hash',observations:['A receipt by Kian; neither requested attribute.']};
  s.views.checkpoint(binding,['grading_review']);
  const replay=s.views.transform([packet,image].map(r=>({role:'toolResult',...r})));
  assert.equal(replay[0].content[0].text,packet.content[0].text);
  assert.equal(replay[1].content.some(c=>c.type==='image'),false);
  assert.deepEqual(JSON.parse(replay[1].content[0].text).checkpoint.observations,binding.observations);
  const args=s.submit(['Letter']);args.revised_items=[{id:'Letter',route:'r',review:false,p:[['p',0,'A receipt by Kian.',[1],'u:c','Neither required attribute.']]}];
  const next=await s.tools.submit_grading_review.execute('commit',args);
  assert.deepEqual(JSON.parse(next.content[0].text).remaining_item_ids,['Writer','Unknown']);
  assert.equal(s.views.pending().filter(v=>v.kind==='grading_review').length,1);
  assert.equal(s.saved[0].changes[0].after.score,0);
});
test('thirty reviews checkpoint full ledgers and images while retaining immutable evidence paths',async()=>{
  const f=fixture(),views=createReportContext(),students=new Map(Array.from({length:30},(_,i)=>[`s${i}`,f.student]));let finalized=0;
  const review=createMainGradingReview({getRubric:()=>f.frozen,scheme:f.scheme,students,views,readImage:async()=>{},log:async()=>{},persist:async(id,name,value)=>({path:`${id}/${name}`,hash:digest(value)}),onFinalized:async()=>{}});
  for(const id of students.keys())review.register({id,primary:f.primary,primaryPath:`${id}/primary`,finalize:async()=>{finalized++;}});
  const submit=review.tools.find(t=>t.name==='submit_grading_review');let packet=await review.prefetch();const messages=[];
  for(const id of students.keys()){
    messages.push({role:'toolResult',...packet});views.transform(messages);views.confirmDelivery();
    packet=await submit.execute('review',{student_id:id,primary_hash:digest(f.primary),checked_item_ids:f.primary.items.map(i=>i.item_id),revised_items:[],new_source_issues:[],notes:['All conditions checked.']});
    assert.ok(views.pending().filter(v=>v.kind==='grading_review').length<=1);
  }
  assert.equal(finalized,30);assert.equal(views.pending().length,0);
  const replay=JSON.stringify(views.transform(messages));assert.ok(replay.length<30000);assert.ok(replay.includes('primary'));
});
test('actual Pi main keeps the same agent for dispatch, substantive review and final completion',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-sol');
  const f=fixture(),views=createReportContext();let coordinator,turn=0,grade,cohort;
  const review=createMainGradingReview({getRubric:()=>f.frozen,scheme:f.scheme,students:new Map([['s',f.student]]),views,readImage:async()=>{},log:async()=>{},persist:async(_id,name,v)=>({path:name,hash:digest(v)}),onFinalized:async()=>{}});
  const streamFn=(_model,context)=>{
    turn++;const stream=createAssistantMessageEventStream();let name,args;
    if(turn===1){name='grade_students';args={student_ids:['s'],concurrency:1,initial_ms_pages:[]};}
    else if(turn===2){assert.ok(JSON.stringify(context).includes('Letter by Mira'));name='submit_grading_review';args={student_id:'s',primary_hash:digest(f.primary),checked_item_ids:f.primary.items.map(i=>i.item_id),revised_items:[],new_source_issues:[],notes:['All point conditions checked.']};}
    else {assert.equal(turn,3);assert.ok(grade);name='finish_cohort';args={};}
    queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content:[{type:'toolCall',id:`call-${turn}`,name,arguments:args}],timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;
  };
  coordinator=createCoordinator({model,streamFn,scheme:f.scheme,studentIds:['s'],reusedRubric:f.frozen,readImage:async()=>{},log:async()=>{},persistRubric:async()=>{},persistCohort:async c=>cohort=c,gradingReview:review,
    reporting:{views,tools:[],onModelResponse:()=>views.confirmDelivery(),getResult:()=>true},
    executeStudent:async id=>{review.register({id,primary:f.primary,primaryPath:'primary',finalize:async g=>{grade=g;Object.assign(coordinator.registry.rows.get(id),{status:'submitted'});}});return{student_id:id,status:'awaiting_review'};}});
  await coordinator.agent.prompt(coordinator.initialPrompt);
  assert.equal(turn,3,coordinator.agent.state.errorMessage);assert.equal(cohort.students[0].status,'submitted');assert.equal(grade.main_grading_review.checked_point_count,3);
});
