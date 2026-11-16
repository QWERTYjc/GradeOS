import test from 'node:test';
import assert from 'node:assert/strict';
import {freezeRubric} from '../src/rubric-contract.mjs';
import {expandCompactPoints} from '../src/compact-points.mjs';
import {validateGrade,digest} from '../src/core.mjs';
import {independentSourceTargets,independentSourcePacket,applyIndependentSourceReview,createIndependentSourceReviewer} from '../src/independent-source-review.mjs';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';

const scheme={sha256:'source',pages:[{page:1,role:'scheme'}]},student={sha256:'answers',pages:[1,2].map(page=>({page,role:'student'}))};
const frozen=freezeRubric({general_instructions:[{text:'Equivalent descriptions qualify. Do not invent an author.',source_pages:[1]}],unresolved_notes:[],items:[{item_id:'Neutral',question_id:'Neutral',max_score:2,criteria:'One mark each for identifying letter and Mira.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
  scoring_points:[{point_id:'type',condition:'Identify the document as letter.'},{point_id:'author',condition:'The author is Mira.'}].map(p=>({...p,max_score:1,allowed_awards:[0,1],award_type:'credit',source_text:p.condition,source_pages:[1],depends_on:[]})),routes:[{route_id:'r',point_ids:['type','author'],description:'Two independent marks.'}]}]},scheme,new Set([1]));
const base=expandCompactPoints({items:[{id:'Neutral',route:'r',review:false,p:[['type',0,'I left the type box empty',[1],'u:c','No explicit type'],['author',1,'Mira',[1],'m','Full criterion met.']]}],review_notes:[],source_issues:[]},frozen,student);
const primary={...validateGrade(base,{documents:{scheme,student}},new Set(['scheme:1','student:1','student:2'])),rubric_hash:frozen.hash,source_issues:[]};
const packet=independentSourcePacket(primary,frozen,scheme,student);
const decision=()=>({checks:[{item_id:'Neutral',point_id:'type',score:1,evidence:'Continuation names the type as letter',student_pages:[2],state:'m',reason:'Continuation supplies the required type; a blank first box does not negate this evidence.',outcome:'resolved',source_refs:['P','G1'],source_quote:'Identify the document as letter.'}]});

test('independent target coverage cannot be removed by primary resolved claims or changed labels',()=>{
  const p=structuredClone(primary);p.items[0].point_decisions[0].source_assessment={outcome:'resolved'};
  assert.deepEqual(independentSourceTargets(p,frozen),[{item_id:'Neutral',point_id:'type'}]);
  p.items[0].point_decisions[0].score=null;p.items[0].point_decisions[0].relation='uncertain';
  assert.equal(independentSourceTargets(p,frozen).length,1);
  p.items[0].point_decisions[1].relation='exception';assert.equal(independentSourceTargets(p,frozen).length,2);
});
test('source-supported restoration retains raw primary and non-target evidence without changing the source',()=>{
  const before=digest(primary),source=digest(frozen);const final=applyIndependentSourceReview(decision(),packet,primary,frozen,scheme,student,new Set([1,2]));
  assert.equal(digest(primary),before);assert.equal(digest(frozen),source);assert.equal(final.total_score,2);
  assert.equal(final.items[0].point_decisions[0].primary_score,0);
  assert.deepEqual(final.items[0].point_decisions[1],primary.items[0].point_decisions[1]);
  assert.equal(final.independent_source_review.changes.length,1);assert.equal(final.items[0].review_required,true);
});
test('uncertain source and uncertain handwriting remain distinct and cannot become forced zero',()=>{
  for(const outcome of ['unresolved_source','unresolved_evidence']){
    const raw=decision(),c=raw.checks[0];Object.assign(c,{score:null,state:'q:u',outcome,reason:'The essential source or observation remains indeterminate.'});
    const final=applyIndependentSourceReview(raw,packet,primary,frozen,scheme,student,new Set([1,2]));
    assert.equal(final.total_score,null);assert.equal(final.source_issues.length,outcome==='unresolved_source'?1:0);
    c.score=0;assert.throws(()=>applyIndependentSourceReview(raw,packet,primary,frozen,scheme,student,new Set([1,2])),/contradicts/);
  }
});
test('missing targets, foreign points, changed bindings, invented source quotes and undelivered evidence fail closed',()=>{
  for(const mutate of [r=>r.checks=[],r=>r.checks.push(r.checks[0]),r=>r.checks[0].point_id='author',r=>r.checks[0].source_quote='A fictional allowance',r=>r.checks[0].source_refs=['P','G9'],r=>r.checks[0].state='u:c']){
    const raw=decision();mutate(raw);assert.throws(()=>applyIndependentSourceReview(raw,packet,primary,frozen,scheme,student,new Set([1,2])));
  }
  assert.throws(()=>applyIndependentSourceReview(decision(),{...packet,primary_hash:'wrong'},primary,frozen,scheme,student,new Set([1,2])),/binding/);
  assert.throws(()=>applyIndependentSourceReview(decision(),packet,primary,frozen,scheme,student,new Set([1])),/prior model input/);
});
test('a fresh Pi reviewer receives original source and scoped answer pages, with remaining context gated until the next input',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');let calls=0,saved;const contexts=[];
  const child=createIndependentSourceReviewer({model,packet,primary,frozen,scheme,student,log:async()=>{},readImage:async p=>({type:'image',mimeType:'image/png',data:`${p.role}-${p.page}`}),persist:async r=>saved=r,
    streamFn:(_m,ctx)=>{contexts.push(structuredClone(ctx));calls++;const call=(name,args)=>({type:'toolCall',id:`${calls}-${name}`,name,arguments:args});
      const content=calls===1?[call('read_student_pages',{pages:[2]}),call('submit_source_review',decision())]:[call('submit_source_review',decision())];
      const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;}});
  await child.agent.prompt(await child.initialPrompt());assert.equal(calls,2);assert.deepEqual(saved,decision());assert.equal(child.getResult().grade.total_score,2);
  assert.equal(contexts[0].messages.find(m=>m.role==='user').content.filter(p=>p.type==='image').length,2);
  assert.equal(child.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,1);
  let wire;await models.streamSimple(model,contexts[1],{apiKey:'offline',maxRetries:0,onPayload:p=>{wire=p;throw Error('Before HTTP');}}).result();
  assert.equal(JSON.stringify(wire).includes('source_delivery'),false);assert.equal(wire.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url').length,3);
});
