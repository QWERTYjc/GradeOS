import test from 'node:test';
import assert from 'node:assert/strict';
import {exceptionProbeFixture} from '../src/exception-probe-fixture.mjs';
import {exceptionTargets,exceptionRequests,reviewPacket,validateExceptionReview,applyExceptionReview,createExceptionReviewer} from '../src/exception-review.mjs';
import {digest} from '../src/core.mjs';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';

const f=exceptionProbeFixture();
const packet=id=>reviewPacket(f.primary,f.frozen,f.scheme,f.student,[{item_id:id,point_id:'credit'}]);
function check(id='Oak',verdict='confirmed') {
  const p=packet(id),d=p.evidence.find(i=>i.item_id===id).point_decisions[0];
  const local=['Fir','Elm','Willow','Yew'].includes(id);
  return {item_id:id,point_id:'credit',verdict,rule_ref:d.rule_ref,scope:d.rule_ref==='P'?'local_explicit':'earlier_part',
    source_quote:d.rule_ref==='P'?p.items.find(i=>i.item_id===id).scoring_points[0].condition:p.general_rules[0].text,source_pages:[1],
    errors:[{origin_item_id:local?id:`${id}-input`,origin_point_id:'credit',description:'Literal wrong input or operation.',student_pages:[p.student_pages[local?1:0]],covered:verdict==='confirmed'?'yes':verdict==='rejected'?'no':'unknown',permission:'Source scope checked.'}],
    current_step_valid:verdict==='unresolved'?null:true,reason:'Source-bound independent judgment.'};
}
test('review packets include only affected/related evidence and original page bindings',()=>{
  const p=packet('Oak');assert.deepEqual(p.items.map(i=>i.item_id),['Oak-input','Oak']);
  assert.deepEqual(p.student_pages,[1,2]);assert.deepEqual(p.source_pages,[1]);assert.equal(exceptionTargets(f.primary).length,9);
  assert.equal(JSON.stringify(p).includes('posthoc'),false);
});
test('changed rubric bindings and missing primary points fail before source review',()=>{
  for(const mutate of [p=>p.rubric_hash='foreign',p=>p.items.pop(),p=>p.items[0].point_decisions=[]]){
    const p=structuredClone(f.primary);mutate(p);assert.throws(()=>reviewPacket(p,f.frozen,f.scheme,f.student));
  }
});
test('exception receipt ownership cannot overlap for prefix-related student identifiers',()=>{
  const receipts=['exception-a-1','exception-a-b-1','exception-a-2','student-a'].map(lane=>({lane}));
  assert.deepEqual(exceptionRequests(receipts,'a').map(r=>r.lane),['exception-a-1','exception-a-2']);
  assert.deepEqual(exceptionRequests(receipts,'a-b').map(r=>r.lane),['exception-a-b-1']);
});
test('valid inherited and explicitly allowed same-part exceptions survive with independent prerequisites',()=>{
  for (const id of ['Oak','Birch','Cedar','Elm']) assert.doesNotThrow(()=>validateExceptionReview({checks:[check(id)]},packet(id),f.scheme,f.student));
});
test('partial permission, invented citations, wrong origin pages and ambiguous zero are rejected',()=>{
  for (const mutate of [c=>c.errors[0].covered='unknown',c=>c.source_quote='fabricated',c=>c.errors[0].student_pages=[18],c=>c.current_step_valid=false]) {
    const c=check();mutate(c);assert.throws(()=>validateExceptionReview({checks:[c]},packet('Oak'),f.scheme,f.student));
  }
  assert.throws(()=>validateExceptionReview({checks:[check('Fir')]},packet('Fir'),f.scheme,f.student),/Earlier-part/);
  const c=check('Willow','rejected');c.errors[0].covered='unknown';assert.throws(()=>validateExceptionReview({checks:[c]},packet('Willow'),f.scheme,f.student),/Ambiguous/);
});
test('review preserves raw proposals and all non-target awards; unresolved remains null throughout totals',()=>{
  const before=digest(f.primary);const checks=exceptionTargets(f.primary).map(t=>check(t.item_id,['Willow','Maple'].includes(t.item_id)?'unresolved':['Ash','Fir','Yew'].includes(t.item_id)?'rejected':'confirmed'));
  const final=applyExceptionReview(f.primary,f.frozen,f.scheme,f.student,checks,{hash:'bound-review'});
  assert.equal(digest(f.primary),before);assert.equal(final.total_score,null);
  assert.equal(final.items.find(i=>i.item_id==='Willow').score,null);assert.equal(final.items.find(i=>i.item_id==='Ash').score,0);
  for (const i of f.primary.items.filter(i=>i.item_id.endsWith('-input'))) assert.deepEqual(final.items.find(j=>j.item_id===i.item_id),i);
  assert.equal(final.source_issues.length,2);assert.equal(final.exception_review.changes.length,5);
  assert.throws(()=>applyExceptionReview(f.primary,f.frozen,f.scheme,f.student,checks.slice(1),{hash:'x'}),/Incomplete/);
});
test('actual independent Pi exception review delivers scoped original images and stops after durable submission',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
  let saved,context,calls=0;const raw={checks:[check()]};
  const reviewer=createExceptionReviewer({model,packet:packet('Oak'),scheme:f.scheme,student:f.student,log:async()=>{},
    readImage:async page=>({type:'image',mimeType:'image/png',data:`${page.role}-${page.page}`}),persist:async result=>{saved=result;},
    streamFn:(_model,ctx)=>{calls++;context=structuredClone(ctx);const stream=createAssistantMessageEventStream();
      queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',
        content:[{type:'toolCall',id:'submit',name:'submit_exception_review',arguments:raw}],usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;}});
  await reviewer.agent.prompt(await reviewer.initialPrompt());assert.equal(calls,1);assert.deepEqual(saved,raw);assert.deepEqual(reviewer.getResult(),saved);
  const content=context.messages.find(m=>m.role==='user').content;assert.equal(content.filter(p=>p.type==='image').length,3);
  assert.equal(JSON.stringify(content).includes('Yew'),false);assert.equal(JSON.stringify(content).includes('reference_total'),false);
});
