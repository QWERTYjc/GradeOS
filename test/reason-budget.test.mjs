import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {requestOutputLimit,GRADING_CORRECTION_TOOLS,requireGradingCorrectionTool} from '../src/submission-contract.mjs';
import {createRuntime} from '../src/cohort-runtime.mjs';
import {Budget,wireEstimate} from '../src/core.mjs';
const correction={kind:'grading_correction',submission_hash:'a'.repeat(64),point_count:2};
const model={id:'neutral',cost:{input:1.5,output:7.5}};
const payload=()=>({model:'neutral',messages:[{role:'user',content:[{type:'text',text:'x'.repeat(96000)},...Array.from({length:28},()=>({type:'image_url',image_url:{url:'data:image/png;base64,synthetic',detail:'high'}}))]}],tools:[]});
test('only live host correction state receives a scaled ceiling; other work and malformed state do not',()=>{
 assert.equal(requestOutputLimit(16000,'student_grading','student-neutral'),16000);
 assert.equal(requestOutputLimit(16000,'student_grading','student-neutral',correction),4096);
 assert.equal(requestOutputLimit(16000,'student_grading','student-neutral',{...correction,point_count:12}),7168);
 assert.equal(requestOutputLimit(16000,'student_grading','student-neutral',{...correction,point_count:100}),16000);
 assert.equal(requestOutputLimit(2000,'student_grading','student-neutral',correction),2000);
 for(const [phase,lane,value] of [['reporting','main',correction],['student_grading','feedback-neutral',correction],['student_grading','student-neutral',{...correction,submission_hash:'stale'}],['student_grading','student-neutral',{...correction,point_count:0}]])assert.throws(()=>requestOutputLimit(16000,phase,lane,value));
});
test('actual provider limit and input/output reservation agree; correction fits same cap and full resubmission cannot bypass it',async()=>{
 for(const small of [false,true]){
 const output=await mkdtemp(join(tmpdir(),'reason-budget-'));let attempted,forwarded;
 const runtime=createRuntime({models:{streamSimple:async(_m,_c,options)=>{forwarded=options;const wire=payload();if(small)wire.tools=GRADING_CORRECTION_TOOLS.map(name=>({type:'function',function:{name}}));wire.max_tokens=options.maxTokens;attempted=wire;return options.onPayload(wire);}},model,output,cap:.54,controller:new AbortController(),phaseOutputLimits:{student_grading:16000},structuredOutput:false});
 try{
 const prior=runtime.budget.admit(.374121,{});runtime.budget.settle(prior,{usage:{cost:{totalFromProvider:true,total:.1616319}}});
 const io=await runtime.io('student-neutral',()=> 'student_grading');const options=small?{gradingCorrectionRequest:correction}:{};
 if(small){
  const wire=await io.streamFn(model,{},options);assert.equal(wire.max_tokens,4096);assert.equal(forwarded.maxTokens,4096);assert.equal(forwarded.gradingCorrectionRequest,undefined);
  assert.equal(wire.tool_choice,'required');
  const r=runtime.budget.requests[1];assert.equal(r.max_output_tokens,4096);assert.equal(r.normal_max_output_tokens,16000);assert.equal(r.request_kind,'grading_correction');
  assert.equal(r.inputTokenReserve,wireEstimate(wire).inputTokenReserve);assert.equal(r.images,28);
  assert.equal(r.reservation.output_usd,4096*7.5/1e6);assert.equal(r.reserve_usd,r.reservation.input_usd+r.reservation.output_usd);
  assert.ok(runtime.budget.chargedOrReserved<=.54);assert.deepEqual(wire.messages,payload().messages);
 }else{
  await assert.rejects(io.streamFn(model,{},options),/Budget reservation limit/);assert.equal(attempted.max_tokens,16000);
  const failed=JSON.parse(await readFile(join(io.directory,'rejected-request.json'),'utf8'));
  assert.equal(failed.admission.max_output_tokens,16000);assert.equal(failed.admission.reservation.output_usd,.12);
  assert.ok(failed.admission.reserve_usd>failed.admission.available_usd);assert.equal(failed.admission.admitted_requests,1);assert.equal(runtime.budget.requests.length,1);
 }
 }finally{runtime.close();await rm(output,{recursive:true,force:true});}
 }
});
test('correction wire requires a matching dynamic declaration and preserves all original-page choices',()=>{
 const tools=GRADING_CORRECTION_TOOLS.map(name=>({type:'function',function:{name}}));
 const wire={tools};assert.equal(requireGradingCorrectionTool(wire,correction),wire);assert.equal(wire.tool_choice,'required');assert.equal(wire.tools,tools);
 assert.throws(()=>requireGradingCorrectionTool({tools:[...tools,{function:{name:'submit_grading'}}]},correction));
 assert.throws(()=>requireGradingCorrectionTool({tools:tools.slice(1)},correction));
 const normal={tools:[...tools,{function:{name:'submit_grading'}}]};requireGradingCorrectionTool(normal);assert.equal(normal.tool_choice,undefined);
});
test('missing receipts retain reservations and stop over-admission; each limit has a distinct diagnosis',()=>{
 const b=new Budget({cap:.1,maxRequests:2});const row=b.admit(.08,{});b.settle(row,{usage:{cost:{total:0,totalFromProvider:false}}});assert.equal(b.chargedOrReserved,.08);assert.throws(()=>b.admit(.03,{}),/Budget reservation/);
 const count=new Budget({cap:1,maxRequests:0});assert.throws(()=>count.admit(.01,{}),/Request count/);
 const elapsed=new Budget({cap:1,deadlineMs:-1});assert.throws(()=>elapsed.admit(.01,{}),/Deadline/);
});
test('main report admission reuses only verified prefix tokens and reserves full cache-write rates',async()=>{
 const output=await mkdtemp(join(tmpdir(),'report-budget-'));
 const mainModel={id:'neutral-report',cost:{input:2,cacheRead:.1,cacheWrite:2.5,output:10},contextWindow:1000000};
 let listener,phase='coordination';
 const wire={model:mainModel.id,tools:[],messages:[{role:'user',content:'a'.repeat(100000)}]};
 const runtime=createRuntime({models:{streamSimple:async(_m,_c,options)=>{
   const sent=structuredClone(wire);sent.max_tokens=options.maxTokens;
   await options.onPayload(sent);await options.onResponse({status:200});
   await options.onProviderStreamEvent({usage:{prompt_tokens:10000}});return sent;
 }},model:mainModel,output,cap:.30,controller:new AbortController(),phaseOutputLimits:{coordination:4096,reporting:4096},structuredOutput:false});
 try{
  const io=await runtime.io('main',()=>phase);io.attach({subscribe:f=>{listener=f;return()=>{};}});
  await io.streamFn(mainModel,{});
  await listener({type:'message_end',message:{role:'assistant',stopReason:'toolUse',usage:{input:3000,cacheRead:5000,cacheWrite:2000,output:200,totalTokens:10200,cost:{totalFromProvider:true,total:.01}}}});
  phase='reporting';wire.messages.push({role:'assistant',content:'Read immutable results.'},{role:'user',content:'b'.repeat(12000)});
  const sent=await io.streamFn(mainModel,{}),r=runtime.budget.requests[1];
  assert.equal(r.input_context_estimate.method,'receipt_plus_append_bound');
  assert.equal(r.reservation.input_usd,r.cost_input_token_reserve*2.5/1e6);
  assert.equal(r.reservation.output_usd,4096*10/1e6);
  assert.ok(wireEstimate(sent).inputTokenReserve*2.5/1e6+r.reservation.output_usd>.29);
  assert.ok(r.reserve_usd<.10);assert.equal(r.input_context_estimate.anchorInputTokens,10000);
  await listener({type:'message_end',message:{role:'assistant',stopReason:'toolUse',usage:{input:3000,cacheRead:5000,cacheWrite:2000,output:200,totalTokens:10200,cost:{totalFromProvider:true,total:.012}}}});
  assert.ok(Math.abs(runtime.budget.chargedOrReserved-.022)<1e-12);
 }finally{runtime.close();await rm(output,{recursive:true,force:true});}
});
