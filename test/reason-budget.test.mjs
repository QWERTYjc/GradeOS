import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {validateCorrectionRequest,GRADING_CORRECTION_TOOLS,requireGradingCorrectionTool} from '../src/submission-contract.mjs';
import {createRuntime} from '../src/cohort-runtime.mjs';
import {Budget,wireEstimate} from '../src/core.mjs';
const correction={kind:'grading_correction',submission_hash:'a'.repeat(64),point_count:2};
const model={id:'neutral',maxTokens:200000,contextWindow:1000000,cost:{input:1.5,output:7.5}};
const payload=()=>({model:'neutral',messages:[{role:'user',content:[{type:'text',text:'x'.repeat(96000)},...Array.from({length:28},()=>({type:'image_url',image_url:{url:'data:image/png;base64,synthetic',detail:'high'}}))]}],tools:[]});
test('correction state is validated without imposing a small output quota',()=>{
 assert.equal(validateCorrectionRequest('student_grading','student-neutral',correction),undefined);
 for(const [phase,lane,value] of [['reporting','main',correction],['student_grading','feedback-neutral',correction],['student_grading','student-neutral',{...correction,submission_hash:'stale'}],['student_grading','student-neutral',{...correction,point_count:0}]])assert.throws(()=>validateCorrectionRequest(phase,lane,value));
});
test('normal and local-correction wire ceilings use actual available funds, preserving tools, inputs and budget',async()=>{
 for(const local of [false,true]){
  const output=await mkdtemp(join(tmpdir(),'reason-budget-'));let forwarded;
  const runtime=createRuntime({models:{streamSimple:async(_m,_c,options)=>{forwarded=options;const wire=payload();if(local)wire.tools=GRADING_CORRECTION_TOOLS.map(name=>({type:'function',function:{name}}));wire.max_tokens=options.maxTokens;return options.onPayload(wire);}},model,output,cap:.54,controller:new AbortController(),structuredOutput:false});
  try{
   const prior=runtime.budget.admit(.374121,{});runtime.budget.settle(prior,{usage:{cost:{totalFromProvider:true,total:.1616319}}});
   const io=await runtime.io('student-neutral',()=> 'student_grading');
   const wire=await io.streamFn(model,{},local?{gradingCorrectionRequest:correction}:{}),r=runtime.budget.requests[1];
   assert.ok(wire.max_tokens>4096);assert.ok(wire.max_tokens<model.maxTokens);
   assert.equal(forwarded.maxTokens,model.maxTokens);assert.equal(forwarded.gradingCorrectionRequest,undefined);
   assert.equal(r.max_output_tokens,wire.max_tokens);assert.equal(r.request_kind,local?'grading_correction':'normal');
   assert.equal(r.reservation.output_usd,wire.max_tokens*7.5/1e6);assert.equal(r.reserve_usd,r.reservation.input_usd+r.reservation.output_usd);
   assert.ok(runtime.budget.chargedOrReserved<=.54);assert.deepEqual(wire.messages,payload().messages);
   if(local)assert.equal(wire.tool_choice,'auto');
  }finally{runtime.close();await rm(output,{recursive:true,force:true});}
 }
});
test('correction wire requires a matching dynamic declaration and preserves all original-page choices',()=>{
 const tools=GRADING_CORRECTION_TOOLS.map(name=>({type:'function',function:{name}}));
 const wire={tools};assert.equal(requireGradingCorrectionTool(wire,correction),wire);assert.equal(wire.tool_choice,'auto');assert.equal(wire.tools,tools);
 assert.throws(()=>requireGradingCorrectionTool({tools:[...tools,{function:{name:'submit_grading'}}]},correction));
 assert.throws(()=>requireGradingCorrectionTool({tools:tools.slice(1)},correction));
 const normal={tools:[...tools,{function:{name:'submit_grading'}}]};requireGradingCorrectionTool(normal);assert.equal(normal.tool_choice,undefined);
});
test('missing receipts retain reservations and stop over-admission; each limit has a distinct diagnosis',()=>{
 const b=new Budget({cap:.1,maxRequests:2});const row=b.admit(.08,{});b.settle(row,{usage:{cost:{total:0,totalFromProvider:false}}});assert.equal(b.chargedOrReserved,.08);assert.throws(()=>b.admit(.03,{}),/Budget reservation/);
 const count=new Budget({cap:1,maxRequests:0});assert.throws(()=>count.admit(.01,{}),/Request count/);
 const open=new Budget({cap:1,maxRequests:null});
 for(let n=0;n<130;n++)open.admit(.001,{});
 assert.throws(()=>open.admit(.9,{}),/Budget reservation/);
 const elapsed=new Budget({cap:1,deadlineMs:-1});assert.throws(()=>elapsed.admit(.01,{}),/Deadline/);
});
test('main report admission reuses only verified prefix tokens and reserves full cache-write rates',async()=>{
 const output=await mkdtemp(join(tmpdir(),'report-budget-'));
 const mainModel={id:'neutral-report',cost:{input:2,cacheRead:.1,cacheWrite:2.5,output:10},contextWindow:1000000,maxTokens:200000};
 let listener,phase='coordination';
 const wire={model:mainModel.id,tools:[],messages:[{role:'user',content:'a'.repeat(100000)}]};
 const runtime=createRuntime({models:{streamSimple:async(_m,_c,options)=>{
   const sent=structuredClone(wire);sent.max_tokens=options.maxTokens;
   await options.onPayload(sent);await options.onResponse({status:200});
   await options.onProviderStreamEvent({usage:{prompt_tokens:10000}});return sent;
 }},model:mainModel,output,cap:.30,controller:new AbortController(),structuredOutput:false});
 try{
  const io=await runtime.io('main',()=>phase);io.attach({subscribe:f=>{listener=f;return()=>{};}});
  await io.streamFn(mainModel,{});
  await listener({type:'message_end',message:{role:'assistant',stopReason:'toolUse',usage:{input:3000,cacheRead:5000,cacheWrite:2000,output:200,totalTokens:10200,cost:{totalFromProvider:true,total:.01}}}});
  phase='reporting';wire.messages.push({role:'assistant',content:'Read immutable results.'},{role:'user',content:'b'.repeat(12000)});
  const sent=await io.streamFn(mainModel,{}),r=runtime.budget.requests[1];
  assert.equal(r.input_context_estimate.method,'receipt_plus_append_bound');
  assert.equal(r.reservation.input_usd,r.cost_input_token_reserve*2.5/1e6);
  assert.equal(r.reservation.output_usd,sent.max_tokens*10/1e6);assert.ok(sent.max_tokens>4096);
  assert.ok(wireEstimate(sent).inputTokenReserve*2.5/1e6+r.reservation.output_usd>.29);
  assert.ok(r.reserve_usd<=.29);assert.equal(r.input_context_estimate.anchorInputTokens,10000);
  await listener({type:'message_end',message:{role:'assistant',stopReason:'toolUse',usage:{input:3000,cacheRead:5000,cacheWrite:2000,output:200,totalTokens:10200,cost:{totalFromProvider:true,total:.012}}}});
  assert.ok(Math.abs(runtime.budget.chargedOrReserved-.022)<1e-12);
 }finally{runtime.close();await rm(output,{recursive:true,force:true});}
});
