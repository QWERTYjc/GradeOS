import test from 'node:test';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream,getCurrentTools,validateToolArguments} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {freezeRubric,createStudentAgent} from '../src/cohort-core.mjs';
import {digest} from '../src/core.mjs';
import {COMPACT_POINTS_SCHEMA} from '../src/compact-points.mjs';
import {completeGradingSchema,mergeGradingCorrection,gradingCorrectionSchema,gradingCorrectionContext,gradingCorrectionTools,GRADING_CORRECTION_TOOLS,requireGradingCorrectionTool} from '../src/submission-contract.mjs';
import {MS_WRITE_SCHEMA,expandMSItems} from '../src/rubric-contract.mjs';

const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-sol');
const call=(name,args)=>[{type:'toolCall',id:crypto.randomUUID(),name,arguments:args}];
function fakeStream(next){let count=0;return (_model,context,options)=>{
  if(++count>12)throw Error('Unexpected offline correction loop');
  const content=next(context,options),stream=createAssistantMessageEventStream();
  queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;
};}
function fixture(ids=['Main','Prior','Earlier','Unrelated']){
  const scheme={sha256:'neutral-source',pages:[1,2,3,4].map(page=>({page,role:'scheme',sha256:`ms-${page}`}))};
  const student={sha256:'neutral-answer',pages:[1,2,3,4,5,6].map(page=>({page,role:'student',sha256:`student-${page}`}))};
  const items=ids.map((id,index)=>({item_id:id,question_id:id,max_score:2,criteria:index===3?'UNRELATED_SOURCE_CANARY':'Identify document type and its author.',source_pages:[index===0?2:1],related_item_ids:index<2?[ids[index+1]]:[],requires_source_image:index===0,image_reason:index===0?'Inspect the original heading layout.':'',uncertainties:[],
    scoring_points:[{point_id:'criterion',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'Letter AND author Mira: 2; one attribute: 1.',source_text:'Letter AND author Mira: 2; one attribute: 1.',source_pages:[index===0?2:1],depends_on:[]}],routes:[{route_id:'r',point_ids:['criterion'],description:'Document attributes.'}]}));
  const frozen=freezeRubric({general_instructions:[{text:'Use complete source qualifications and accept equivalent wording.',source_pages:[1]}],unresolved_notes:[],items},scheme,new Set([1,2,3,4]));
  const raw={items:ids.map((id,index)=>({id,route:'r',review:index===0,p:[['criterion',2,index===3?'UNRELATED_EVIDENCE_CANARY':'A letter written by Mira.',[index===0?2:index===3?5:index===1?1:3],'m','=']]})),review_notes:['Check the marked item.'],source_issues:[]};
  return {scheme,student,frozen,raw};
}
const patch=(raw,items,metadata={})=>({submission_hash:digest(raw),items:structuredClone(items),review_notes:null,source_issues:null,...metadata});
const fixedItem=raw=>{const item=structuredClone(raw.items[0]);item.p[0][5]='Both stated attributes satisfy the complete source criterion; preserve its review flag.';return item;};
const pixels=async page=>({type:'image',mimeType:'image/png',data:Buffer.from(`${page.role}-original-${page.page}`).toString('base64')});
const checkpoint=context=>context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='text').map(p=>{try{return JSON.parse(p.text);}catch{return null;}}).find(p=>p?.kind==='host_grading_checkpoint');
const images=context=>context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image').map(p=>Buffer.from(p.data,'base64').toString());
const makeAgent=(f,next,extra={})=>createStudentAgent({model,...f,protocol:'evidence-v4',reasonStyle:'brief-full-credit',readImage:pixels,log:async()=>{},persist:async()=>{},streamFn:fakeStream(next),...extra});

test('local item updates preserve all omitted data across renamed, reordered and multilingual inputs',()=>{
  for(const ids of [['A','B','C','D'],['标题','作者','原始','其他'],['X.ii','Y','Z','Essay']]){
    const f=fixture(ids);f.raw.items.reverse();const before=digest(f.raw),item=structuredClone(f.raw.items[1]);item.p[0][2]='文体与作者的完整证据。';item.p[0][5]='The explicit attributes meet the source criterion.';
    const merged=mergeGradingCorrection({raw:f.raw},patch(f.raw,[item]),f.frozen);
    assert.equal(digest(f.raw),before);for(const old of f.raw.items)assert.deepEqual(merged.items.find(i=>i.id===old.id),old.id===item.id?item:old);
    assert.deepEqual(merged.review_notes,f.raw.review_notes);assert.deepEqual(merged.source_issues,f.raw.source_issues);
    assert.deepEqual(mergeGradingCorrection({raw:f.raw},patch(f.raw,[],{review_notes:[]}),f.frozen).review_notes,[]);
  }
});
test('stale hashes, unknown IDs, duplicate IDs, missing metadata and foreign fields cannot mutate drafts',()=>{
  const f=fixture(),pending={raw:f.raw};const before=digest(f.raw);
  for(const mutate of [c=>c.submission_hash='0'.repeat(64),c=>c.items[0].id='Foreign',c=>c.items.push(c.items[0]),c=>delete c.review_notes,c=>c.extra='unauthorized',c=>c.source_issues='drop']){
    const c=patch(f.raw,[fixedItem(f.raw)]);mutate(c);assert.throws(()=>mergeGradingCorrection(pending,c,f.frozen));assert.equal(digest(f.raw),before);
  }
});
test('actual Pi local correction keeps complete related sources and only bound images for lists, numbers and ranges',async()=>{
  for(const [index,ids] of [['Main','Prior','Earlier','Unrelated'],['题目','先前','更早','无关'],['R.iii','K','J','Unrelated prose']].entries()){
    const f=fixture(ids);let turn=0,saved,submitted;const contexts=[];
    for(const row of f.raw.items)for(const point of row.p){
      if(index===1)point[3]=point[3][0];
      if(index===2)point[3]=point[3][0]===3?'2-3':point[3].join(',');
    }
    const ctl=makeAgent(f,(context,options)=>{
      contexts.push(structuredClone(context));turn++;
      if(turn===1){assert.equal(options.gradingCorrectionRequest,undefined);return call('submit_grading',f.raw);}
      const p=checkpoint(context);assert.ok(p);assert.deepEqual(p.items.map(i=>i.item_id),ids.slice(0,3));
      assert.deepEqual(p.rejected_items,f.raw.items.slice(0,3));assert.equal(JSON.stringify(context).includes('UNRELATED_SOURCE_CANARY'),false);assert.equal(JSON.stringify(context).includes('UNRELATED_EVIDENCE_CANARY'),false);
      assert.deepEqual(images(context).sort(),['scheme-original-2','student-original-1','student-original-2','student-original-3']);
      assert.equal(options.gradingCorrectionRequest.point_count,1);assert.deepEqual(getCurrentTools(context.messages).map(t=>t.name).sort(),GRADING_CORRECTION_TOOLS.toSorted());
      return call('correct_grading',patch(f.raw,[fixedItem(f.raw)]));
    },{persist:async g=>saved=g,persistSubmission:async raw=>submitted=raw});
    await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,2,ctl.agent.state.errorMessage);assert.equal(saved.total_score,8);assert.equal(saved.items[0].review_required,true);
    assert.deepEqual(submitted.items.slice(1),f.raw.items.slice(1));assert.equal(saved.items[0].point_decisions[0].reason,fixedItem(f.raw).p[0][5]);
  }
});
test('partial proposals retain stable tools across metadata-only and missing-item corrections; only complete merged ledgers save',async()=>{
  for(const ids of [['Main','Prior','Earlier','Unrelated'],['条甲','条乙','条丙','条丁']]){
    const f=fixture(ids);f.raw.items.forEach(i=>i.review=false);const partial={...structuredClone(f.raw),items:[f.raw.items[0]]};let turn=0,saved,correctionTools;
    const ctl=makeAgent(f,context=>{
      turn++;if(turn===1)return call('submit_grading',partial);
      assert.equal(saved,undefined);assert.match(JSON.stringify(context),/Draft retained, not accepted/);
      assert.ok(getCurrentTools(context.messages).some(t=>t.name==='correct_grading'));
      if(turn===2){correctionTools=structuredClone(getCurrentTools(context.messages));return call('correct_grading',patch(partial,[]));}
      assert.deepEqual(getCurrentTools(context.messages),correctionTools);
      if(turn===3)return call('correct_grading',patch(partial,[f.raw.items[1]]));
      const merged=mergeGradingCorrection({raw:partial},patch(partial,[f.raw.items[1]]),f.frozen);
      return call('correct_grading',patch(merged,f.raw.items.slice(2)));
    },{persist:async g=>saved=g});
    await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,4,ctl.agent.state.errorMessage);assert.equal(saved.items.length,4);assert.equal(saved.total_score,8);
    for(const item of f.raw.items)assert.equal(saved.items.find(i=>i.item_id===item.id).point_decisions[0].evidence,item.p[0][2]);
  }
});
test('whole-ledger schemas bind only identities and coverage; transformed, partial-credit and unknown judgments remain available',()=>{
  for(const ids of [['Alpha','Beta','Gamma','Other'],['条甲','条乙','待查','无关'],['Archive.ii','Section-B','Document-X','Other prose']]){
    const f=fixture(ids),before=digest(COMPACT_POINTS_SCHEMA),schema=completeGradingSchema(COMPACT_POINTS_SCHEMA,f.frozen);
    const validate=raw=>validateToolArguments({name:'submit',parameters:schema},{name:'submit',type:'toolCall',id:'c',arguments:raw});
    for(const [score,state,review] of [[2,'m',false],[1,'m',false],[0,'u:c',false],[null,'q:u',true]]){
      const raw=structuredClone(f.raw);raw.items.reverse();raw.items[0].review=review;raw.items[0].p[0][1]=score;raw.items[0].p[0][4]=state;
      validate(raw);
    }
    for(const mutate of [r=>r.items=[],r=>r.items.push(r.items[0]),r=>r.items[0].id='Foreign']){
      const raw=structuredClone(f.raw);mutate(raw);assert.throws(()=>validate(raw));
    }
    assert.equal(digest(COMPACT_POINTS_SCHEMA),before);
    const local=gradingCorrectionSchema(schema);assert.equal(local.properties.items.minItems,0);
    const tools=GRADING_CORRECTION_TOOLS.map(name=>({name,description:'Tool',parameters:name==='correct_grading'?local:{type:'object',properties:{submission_hash:{type:'string'}}}}));
    const bound=gradingCorrectionTools(tools).find(t=>t.name==='correct_grading');
    const check=args=>validateToolArguments(bound,{name:bound.name,type:'toolCall',id:'fix',arguments:args});
    check(patch(f.raw,[]));check(patch(f.raw,[f.raw.items[1]]));check(patch(f.raw,f.raw.items.slice(1)));
  }
});
test('non-reason contradictions support local changed judgments; unrelated records stay untouched',async()=>{
  for(const [score,state,review,reason] of [[0,'u:c',false,'Neither required attribute is present.'],[null,'q:u',true,'The author is obscured; credit cannot be determined.'],[1,'m',false,'Only the document type is supported; the author is missing.']]){
    const f=fixture();f.raw.items[0].review=false;f.raw.items[0].p[0]=['criterion',2,'The document attributes are incomplete.',[2],'u:c','The full criterion is not met.'];let turn=0,saved,submitted;
    const correction=structuredClone(f.raw.items[0]);correction.review=review;correction.p[0][1]=score;correction.p[0][4]=state;correction.p[0][5]=reason;
    const ctl=makeAgent(f,context=>{turn++;if(turn===1)return call('submit_grading',f.raw);assert.equal(checkpoint(context).targets[0].item_id,'Main');return call('correct_grading',patch(f.raw,[correction]));},{persist:async g=>saved=g,persistSubmission:async raw=>submitted=raw});
    await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,2,ctl.agent.state.errorMessage);assert.equal(saved.items[0].score,score);assert.deepEqual(submitted.items.slice(1),f.raw.items.slice(1));
    assert.equal(saved.items[0].review_required,review);if(score===null)assert.equal(saved.total_score,null);
  }
});
test('every merged correction revalidates page ownership, point coverage, allowed awards and review requirements',async()=>{
  for(const mutate of [r=>r.p[0][3]=[99],r=>r.p[0][1]=3,r=>r.p=[],r=>r.route='Foreign',r=>r.p[0][2]='',r=>{r.p[0][1]=null;r.p[0][4]='q:u';r.review=false;}]){
    const f=fixture();let turn=0,saved;const bad=fixedItem(f.raw);mutate(bad);
    const ctl=makeAgent(f,()=>{turn++;if(turn===1)return call('submit_grading',f.raw);if(turn===2)return call('correct_grading',patch(f.raw,[bad]));throw Error('Expected rejected correction.');},{persist:async g=>saved=g});
    await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(saved,undefined);assert.equal(ctl.getResult(),null);
  }
});
test('stale correction leaves the current draft available; original images outside a checkpoint remain accessible',async()=>{
  const f=fixture();let turn=0,saved;const ctl=makeAgent(f,context=>{
    turn++;if(turn===1)return call('submit_grading',f.raw);
    if(turn===2)return call('correct_grading',{...patch(f.raw,[fixedItem(f.raw)]),submission_hash:'0'.repeat(64)});
    if(turn===3){assert.equal(saved,undefined);assert.match(JSON.stringify(context),/No matching pending grading submission/);assert.equal(checkpoint(context).submission_hash,digest(f.raw));return call('reopen_grading',{submission_hash:'0'.repeat(64),reason:'Try an obsolete draft identity.'});}
    if(turn===4){assert.equal(saved,undefined);assert.equal(checkpoint(context).submission_hash,digest(f.raw));return call('read_ms_pages',{pages:[4]});}
    if(turn===5){assert.ok(images(context).includes('scheme-original-4'));return call('read_student_pages',{pages:[6],question:'Inspect the original heading of the supplemental page.'});}
    assert.ok(images(context).includes('student-original-6'));return call('correct_grading',patch(f.raw,[fixedItem(f.raw)]));
  },{persist:async g=>saved=g});
  await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,6,ctl.agent.state.errorMessage);assert.deepEqual(saved.source_image_pages_delivered,[2,4]);
});
test('rejected item corrections advance the draft hash; accepted results cannot be amended',async()=>{
  const f=fixture();let turn=0,saved;const bad=fixedItem(f.raw);bad.p[0][1]=3;const merged=mergeGradingCorrection({raw:f.raw},patch(f.raw,[bad]),f.frozen);
  const ctl=makeAgent(f,context=>{
    turn++;if(turn===1)return call('submit_grading',f.raw);if(turn===2)return call('correct_grading',patch(f.raw,[bad]));
    assert.equal(checkpoint(context).submission_hash,digest(merged));return call('correct_grading',patch(merged,[fixedItem(f.raw)]));
  },{persist:async g=>saved=g});
  await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,3,ctl.agent.state.errorMessage);assert.equal(saved.total_score,8);
  const before=digest(saved),tool=ctl.agent.state.tools.find(t=>t.name==='correct_grading');
  await assert.rejects(tool.execute('late',patch(merged,[fixedItem(f.raw)])));assert.equal(digest(saved),before);
});
test('interactive instructions, unknown context ownership and explicit reopen retain full original context',async()=>{
  const f=fixture();let turn=0,saved;const ctl=makeAgent(f,(context,options)=>{
    turn++;if(turn===1)return call('submit_grading',f.raw);
    if(turn===2){assert.ok(checkpoint(context));return call('reopen_grading',{submission_hash:digest(f.raw),reason:'Need to compare the full source context.'});}
    assert.equal(options.gradingCorrectionRequest,undefined);assert.equal(checkpoint(context),undefined);assert.ok(JSON.stringify(context).includes('UNRELATED_SOURCE_CANARY'));
    const raw=structuredClone(f.raw);raw.items[0]=fixedItem(raw);return call('submit_grading',raw);
  },{persist:async g=>saved=g});
  await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,3,ctl.agent.state.errorMessage);assert.equal(saved.total_score,8);
  const messages=ctl.agent.state.messages,tools=ctl.agent.state.tools;
  for(const extra of [{role:'user',content:'Teacher instruction that must remain.'},{role:'system',content:'Changed instruction.'},{role:'system',content:'',sections:{source:'Updated source.'}}]){
    const input=[...messages,extra];const pending={raw:f.raw,targets:[{item_id:'Main'}],toolCallId:messages.find(m=>m.role==='toolResult').toolCallId};
    assert.equal(gradingCorrectionContext(input,{pending,...f,tools,bindings:new Map()}),input);
  }
});
test('global notes require review metadata while unrelated full-credit reasons remain short',async()=>{
  const f=fixture();f.frozen.artifact.unresolved_notes=['A cross-document convention remains unresolved.'];f.raw.items.forEach(i=>i.review=false);f.raw.review_notes=[];let turn=0,saved;
  const ctl=makeAgent(f,()=>{turn++;return turn===1?call('submit_grading',f.raw):call('correct_grading',patch(f.raw,[],{review_notes:['The source concern remains for review; the recorded explicit conditions are separately supported.']}));},{persist:async g=>saved=g});
  await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,2,ctl.agent.state.errorMessage);assert.equal(saved.status,'review_required');assert.equal(saved.total_score,8);
  assert.ok(saved.items.every(i=>i.point_decisions[0].reason_encoding==='explicit_full_credit_attestation'));
});
test('Terra and Luna wire tools stay identical across draft hashes while checkpoints advance and host validation remains authoritative',async()=>{
  const f=fixture();let turn=0;const contexts=[];const bad=fixedItem(f.raw);bad.p[0][1]=3;
  const merged=mergeGradingCorrection({raw:f.raw},patch(f.raw,[bad]),f.frozen);
  const ctl=makeAgent(f,(context,options)=>{
    contexts.push({context:structuredClone(context),options});turn++;
    return turn===1?call('submit_grading',f.raw):turn===2?call('correct_grading',patch(f.raw,[bad])):call('correct_grading',patch(merged,[fixedItem(f.raw)]));
  });
  await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(turn,3,ctl.agent.state.errorMessage);
  assert.notEqual(checkpoint(contexts[1].context).submission_hash,checkpoint(contexts[2].context).submission_hash);
  for(const id of ['openai/gpt-6.1-terra','openai/gpt-6-luna']){
    const wires=[];
    for(const {context,options} of contexts.slice(1)){
      const result=await models.streamSimple(models.getModel('openrouter',id),context,{apiKey:'local-test-only',maxRetries:0,reasoning:'low',onPayload:p=>{wires.push(requireGradingCorrectionTool(p,options.gradingCorrectionRequest));throw Error('Offline serialization only');}}).result();
      assert.equal(result.stopReason,'error');
    }
    assert.deepEqual(wires[0].tools,wires[1].tools);
    for(const wire of wires){
      assert.equal(wire.tool_choice,'auto');assert.deepEqual(wire.tools.map(t=>t.function.name).sort(),GRADING_CORRECTION_TOOLS.toSorted());
      assert.equal(JSON.stringify(wire.tools).includes(digest(f.raw)),false);assert.equal(JSON.stringify(wire.tools).includes(digest(merged)),false);
      const tool=wire.tools.find(t=>t.function.name==='correct_grading').function;
      assert.deepEqual(tool.parameters.properties.submission_hash,{type:'string',minLength:64,maxLength:64});
      validateToolArguments({name:tool.name,parameters:tool.parameters},{name:tool.name,type:'toolCall',id:'check',arguments:patch(f.raw,[fixedItem(f.raw)])});
      assert.throws(()=>mergeGradingCorrection({raw:merged},patch(f.raw,[fixedItem(f.raw)]),f.frozen),/No matching/);
    }
  }
});
test('truncated local correction cannot save a partial or inferred result',async()=>{
  const f=fixture();let turn=0,saved;const ctl=makeAgent(f,()=>[],{persist:async g=>saved=g,streamFn:()=>{
    turn++;const content=turn===1?call('submit_grading',f.raw):call('correct_grading',patch(f.raw,[fixedItem(f.raw)]));const stream=createAssistantMessageEventStream();const stopReason=turn===1?'toolUse':'length';
    queueMicrotask(()=>stream.push({type:'done',reason:stopReason,message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason,usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{total:0}}}}));return stream;
  }});
  await ctl.agent.prompt(await ctl.initialPrompt([2]));assert.equal(saved,undefined);assert.equal(ctl.getResult(),null);
});
test('explicit MS source references preserve full qualifications and canonical values without inferred defaults',()=>{
  for(const [id,source] of [['Letter','Both document type AND author must be correct.'],['中文','文体和作者均正确才给分。'],['Archive.z','The title and its author are both required.']]){
    const f=fixture(),item=f.frozen.artifact.items[1];item.item_id=id;item.related_item_ids=[];item.source_pages=[1];const p=item.scoring_points[0];p.source_text=source;p.condition=source;
    const raw={items:[{q:item.question_id,id,max:item.max_score,criteria:item.criteria,pages:item.source_pages,related:[],visual:false,why:'',uncertainties:[],points:[{id:p.point_id,max:p.max_score,awards:p.allowed_awards,type:p.award_type,condition:null,depends:[],source:source,pages:[1]}],routes:[{id:'r',points:[p.point_id],description:item.routes[0].description}]}]};
    validateToolArguments({name:'write_rubric_items',parameters:MS_WRITE_SCHEMA},{name:'write_rubric_items',type:'toolCall',id:'ms',arguments:raw});assert.deepEqual(expandMSItems(raw),[item]);
    const changed=structuredClone(raw);changed.items[0].points[0].source='Either attribute is enough.';assert.notEqual(expandMSItems(changed)[0].scoring_points[0].condition,source);
    for(const mutate of [r=>delete r.items[0].points[0].condition,r=>r.items[0].points[0].source='',r=>r.items[0].points[0].awards=[],r=>r.items[0].points[0].pages=[99]]){
      const bad=structuredClone(raw);mutate(bad);assert.throws(()=>freezeRubric({general_instructions:[],unresolved_notes:[],items:expandMSItems(bad)},f.scheme,new Set([1,2,3,4])));
    }
    raw.items[0].uncertainties=['The association of the caption with the author is unclear.'];raw.items[0].visual=true;raw.items[0].why='Inspect source layout.';
    const expanded=expandMSItems(raw)[0];assert.equal(expanded.requires_source_image,true);assert.equal(expanded.uncertainties.length,1);
  }
});
