import test from 'node:test';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream,validateToolArguments,getCurrentTools} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {namedFeedbackSchema,expandNamedFeedback,focusedFeedbackPacket} from '../src/focused-feedback.mjs';
import {createFeedbackAgent,validateFeedback,renderStudentFeedback} from '../src/student-feedback.mjs';
import {exceptionProbeFixture} from '../src/exception-probe-fixture.mjs';
import {conciseValidationContext,requireFeedbackSubmission} from '../src/submission-contract.mjs';
import {digest} from '../src/core.mjs';
import {experimentModel,HYDROGEN_ID} from '../src/experiment-models.mjs';

const models=createModels();models.setProvider(openrouterProvider());const model=experimentModel(models,HYDROGEN_ID);
const check=(schema,args)=>validateToolArguments({name:'submit_student_feedback',parameters:schema},{type:'toolCall',id:'c',name:'submit_student_feedback',arguments:args});
function feedbackFixture(){
 const f=exceptionProbeFixture();
 const grade=f.primary;
 const full=grade.items.find(i=>i.item_id==='Fir-input').point_decisions[0];full.reason_encoding='explicit_full_credit_attestation';full.reason='Full criterion met.';
 const packet=focusedFeedbackPacket(grade,f.frozen);
 const raw={summary:'依据本次保存的作答记录安排复核与练习。',strengths:[],priorities:[],items:Object.fromEntries(packet.required_commentary_ids.map(id=>[id,{assessment:'根据保存记录核对条件与证据。',next_step:'逐点核对所引用的条件。',review_reason:grade.items.find(i=>i.item_id===id).review_required?'记录要求复核，保留不确定性。':''}])),additional_items:[]};
 return {...f,grade,raw};
}
test('grade-bound named contract rejects the historical failure classes and keeps exact coverage',()=>{
 const {grade,frozen,raw}=feedbackFixture(),schema=namedFeedbackSchema(grade,frozen),before=digest(grade);
 assert.deepEqual(check(schema,raw),raw);
 assert.deepEqual(schema.properties.items.required,Object.keys(raw.items));
 for(const mutate of [r=>r.items=[],r=>delete r.items.Oak,r=>r.items.Foreign=r.items.Oak,r=>r.items.Oak=['Oak','a','b','c'],r=>r.items.Oak.next_step='文'.repeat(181),r=>r.items.Oak.review_reason='']){
  const bad=structuredClone(raw);mutate(bad);assert.throws(()=>check(schema,bad));
 }
 const result=validateFeedback(expandNamedFeedback(raw,grade,frozen),grade,frozen);
 assert.equal(result.items.length,grade.items.length);assert.equal(digest(grade),before);
 const report=renderStudentFeedback('neutral',grade,frozen,result);
 for(const item of grade.items) for(const p of item.point_decisions) assert.ok(report.includes(p.evidence));
});
test('renamed IDs, reordered input and translated evidence preserve contract meaning; full-credit concerns remain possible',()=>{
 for(const [id,evidence] of [['Alpha','A recorded statement.'],['中文条目','已保存的证据。'],['Other.ii','Line one\nLine two']]){
  const {grade,frozen,raw}=feedbackFixture();
  grade.items.find(i=>i.item_id==='Oak').item_id=id; frozen.artifact.items.find(i=>i.item_id==='Oak').item_id=id;
  grade.items.find(i=>i.item_id===id).point_decisions[0].evidence=evidence;
  raw.items[id]=raw.items.Oak;delete raw.items.Oak;grade.items.reverse();
  raw.additional_items=[{item_id:'Fir-input',assessment:'保存记录出现新的疑点。',next_step:'请核对来源。',review_reason:'需查阅原材料确认。'}];
  const schema=namedFeedbackSchema(grade,frozen);check(schema,raw);
  const result=validateFeedback(expandNamedFeedback(raw,grade,frozen),grade,frozen);
  assert.equal(result.items.find(i=>i.item_id==='Fir-input').review_recommended,true);
  assert.throws(()=>expandNamedFeedback({...raw,additional_items:[...raw.additional_items,...raw.additional_items]},grade,frozen),/duplicate/);
  assert.throws(()=>expandNamedFeedback({...raw,additional_items:[{...raw.additional_items[0],item_id:id}]},grade,frozen),/Unbound/);
 }
});
test('actual Pi tool schema and forced feedback submission survive Hydrogen wire serialization without a paid call',async()=>{
 const {grade,frozen,raw}=feedbackFixture();const schema=namedFeedbackSchema(grade,frozen);let wire;
 const result=await models.streamSimple(model,{systemPrompt:'Neutral feedback.',messages:[{role:'user',timestamp:1,content:'Write saved feedback.'}],tools:[{name:'submit_student_feedback',description:'Submit',parameters:schema}]},{apiKey:'local-test-only',maxRetries:0,reasoning:'low',onPayload:payload=>{wire=requireFeedbackSubmission(payload,'student_feedback');throw Error('Pre-network inspection only');}}).result();
 assert.equal(result.stopReason,'error');assert.deepEqual(wire.tools[0].function.parameters,schema);
 assert.deepEqual(wire.tool_choice,{type:'function',function:{name:'submit_student_feedback'}});
 check(wire.tools[0].function.parameters,raw);
 const grading={tools:[{function:{name:'read_ms_pages'}},{function:{name:'submit_grading'}}]};
 assert.equal(requireFeedbackSubmission(grading,'student_grading'),grading);assert.equal(grading.tool_choice,undefined);
 assert.throws(()=>requireFeedbackSubmission(grading,'student_feedback'));
});
test('schema-error context keeps all diagnostics without echoing args, and does not mutate audit or ordinary errors',()=>{
 for(const prefix of ['Validation failed for tool "submit"','Invalid arguments for tool "submit"']){
 const original=[{role:'assistant',content:[{type:'toolCall',arguments:{evidence:'preserve me'}}]},{role:'toolResult',isError:true,content:[{type:'text',text:prefix+':\n  - items.Alpha.next_step: expected at most 180 characters\n\nReceived arguments:\n'+JSON.stringify({large:'x'.repeat(2000)})}]}];
 const hash=digest(original), projected=conciseValidationContext(original);
 assert.equal(digest(original),hash);assert.deepEqual(projected[0],original[0]);
 assert.match(projected[1].content[0].text,/items.Alpha.next_step/);assert.doesNotMatch(projected[1].content[0].text,/Received arguments/);
 }
 const ordinary=[{role:'toolResult',isError:true,content:[{type:'text',text:'Evidence contains Received arguments: as source text.'}]}];assert.deepEqual(conciseValidationContext(ordinary),ordinary);
});
function fakeStream(next){return (_model,context,options)=>{
 const content=next(context,options);const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;
};}
const call=(name,args)=>[{type:'toolCall',id:Math.random().toString(),name,arguments:args}];
test('actual Pi named feedback persists complete immutable-bound feedback in one tool call',async()=>{
 const f=feedbackFixture();let saved,turns=0;
 const ctl=createFeedbackAgent({model,grade:f.grade,frozen:f.frozen,mode:'focused-v4',persist:async r=>saved=r,log:async()=>{},streamFn:fakeStream(()=>{turns++;return call('submit_student_feedback',f.raw);})});
 await ctl.agent.prompt(ctl.initialPrompt);assert.equal(turns,1);assert.equal(saved.version,4);assert.equal(saved.items.length,f.grade.items.length);assert.equal(saved.grade_hash,digest(f.grade));
});
test('all ordinary full-credit items permit empty required commentary, while null awards always require review text',()=>{
 const f=feedbackFixture();const id='Fir-input';
 const grade={...f.grade,items:f.grade.items.filter(i=>i.item_id===id)};
 const frozen={...f.frozen,artifact:{...f.frozen.artifact,items:f.frozen.artifact.items.filter(i=>i.item_id===id)}};
 const raw={summary:'本次已保存的条件均有对应证据。',strengths:[],priorities:[],items:{},additional_items:[]};
 check(namedFeedbackSchema(grade,frozen),raw);
 const expanded=validateFeedback(expandNamedFeedback(raw,grade,frozen),grade,frozen);assert.equal(expanded.items.length,1);
 grade.items[0].score=null;grade.items[0].point_decisions[0].score=null;
 const unknown={...raw,items:{[id]:{assessment:'记录中的证据尚不能确定。',next_step:'核查原始材料。',review_reason:''}}};
 assert.throws(()=>check(namedFeedbackSchema(grade,frozen),unknown));
 unknown.items[id].review_reason='该点仍未确定。';check(namedFeedbackSchema(grade,frozen),unknown);
 assert.equal(validateFeedback(expandNamedFeedback(unknown,grade,frozen),grade,frozen).items[0].review_recommended,true);
});
test('protocol-only prose is rejected across renamed/quoted/reordered keys; explanations about code remain valid',()=>{
 for(const id of ['Delta','中文条目','Other.iii']){
  const f=feedbackFixture();f.grade.items.find(i=>i.item_id==='Oak').item_id=id;f.frozen.artifact.items.find(i=>i.item_id==='Oak').item_id=id;f.raw.items[id]=f.raw.items.Oak;delete f.raw.items.Oak;
  for(const fragment of [`},${id}:{assessment:`,` } , "${id}" : { "review_reason" : `,'}},strengths:[{observation:']){
   const bad=structuredClone(f.raw);bad.items[id].review_reason=fragment;
   assert.throws(()=>validateFeedback(expandNamedFeedback(bad,f.grade,f.frozen),f.grade,f.frozen),/serialized field structure/);
  }
  for(const prose of ['请解释 items: {} 在程序中表示什么，不能只给语法片段。','The source code contains {assessment: 1}; verify its effect before drawing conclusions.','记录的结果与来源不一致，请核对。']){
   const good=structuredClone(f.raw);good.items[id].review_reason=prose;
   assert.equal(validateFeedback(expandNamedFeedback(good,f.grade,f.frozen),f.grade,f.frozen).items.find(i=>i.item_id===id).review_reason,prose);
  }
 }
});
