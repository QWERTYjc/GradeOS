import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {CohortProgress} from '../src/cohort-progress.mjs';

async function fixture(t,ids=['one']){
  const directory=await mkdtemp(join(tmpdir(),'pi-progress-'));const messages=[];let time=1000;
  const progress=new CohortProgress({directory,studentIds:ids,reusedRubric:true,reasonStyle:'brief-full-credit',clock:()=>time,writeLine:s=>messages.push(s)});
  t.after(async()=>{progress.stop();await progress.queue;await rm(directory,{recursive:true,force:true});});
  return {directory,progress,messages,advance:n=>time+=n,snapshot:async()=>JSON.parse(await readFile(join(directory,'progress.json'),'utf8'))};
}
const req=(number,lane,phase,cost=null)=>({number,lane,phase,status:cost===null?'unknown':'provider_reported',...(cost===null?{}:{cost_usd:cost})});
const summary=(students,requests,extra={})=>({status:'submitted',elapsed_seconds:80,elapsed_including_image_preparation_seconds:81,students,requests,admitted_requests:requests.length,unknown_cost_requests:requests.filter(r=>r.status==='unknown').length,provider_reported_cost_usd:requests.reduce((n,r)=>n+(r.cost_usd??0),0),cost_receipts_complete:requests.every(r=>r.status==='provider_reported'),report_submitted:false,...extra});

test('concurrent students count grade persistence separately from feedback completion and preserve receipt ownership',async t=>{
  const f=await fixture(t,['a','a-b']);await f.progress.start();
  await Promise.all([f.progress.observe({type:'request_admitted',request:req(1,'student-a','student_grading')}),f.progress.observe({type:'request_admitted',request:req(2,'student-a-b','student_grading')})]);
  await f.progress.observe({type:'request_terminal',request:req(1,'student-a','student_grading',.03)});
  await f.progress.observe({type:'grading_result_saved',student_id:'a',review_status:'provisional'});
  await f.progress.observe({type:'request_admitted',request:req(3,'feedback-a','student_feedback')});
  const s=await f.snapshot();assert.equal(s.counts.grading_saved,1);assert.equal(s.counts.completed,0);assert.equal(s.requests.in_flight,2);assert.equal(s.settled_cost_usd,.03);assert.equal(s.students[1].status,'grading');
  assert.deepEqual(new Set(s.active_phases),new Set(['student_grading','student_feedback']));
  await f.progress.observe({type:'request_terminal',request:req(1,'student-a','student_grading',.03)});assert.equal((await f.snapshot()).settled_cost_usd,.03);
});
test('unknown billed cost is never displayed as a free successful run and heartbeat gives no invented percentage or ETA',async t=>{
  const f=await fixture(t);await f.progress.start();await f.progress.observe({type:'request_admitted',request:req(1,'student-one','student_grading')});
  f.advance(45000);await f.progress.heartbeat();assert.match(f.messages.at(-1),/仍在批改答卷.*45秒.*已结算/);assert.doesNotMatch(f.messages.at(-1),/%|预计|剩余/);
  await f.progress.observe({type:'request_terminal',request:req(1,'student-one','student_grading')});
  await f.progress.finish(summary([{student_id:'one',status:'failed'}],[req(1,'student-one','student_grading')],{status:'incomplete'}));
  const s=await f.snapshot();assert.equal(s.status,'failed');assert.equal(s.cost_complete,false);assert.equal(s.requests.unknown_cost,1);assert.match(s.message,/费用待确认/);assert.doesNotMatch(s.message,/实付/);assert.equal(f.progress.timer,null);
});
test('refreshable progress reveals no raw answer content, provider key, private reasoning or untrusted error text',async t=>{
  const f=await fixture(t);await f.progress.start();
  await f.progress.observe({type:'assistant_message',message:{content:'SENSITIVE_REASONING'}});
  await f.progress.observe({type:'request_admitted',request:{...req(1,'student-one','student_grading'),api_key:'SECRET',body:'STUDENT_CONTENT'}});
  await f.progress.observe({type:'request_rejected_before_send',reason:'SECRET_IN_ERROR'});
  const data=await readFile(join(f.directory,'progress.json'),'utf8');assert.doesNotMatch(data,/SENSITIVE|SECRET|STUDENT_CONTENT/);
});
test('completion links only existing artifacts, preserves null and review state, and ignores late events',async t=>{
  const f=await fixture(t);await f.progress.start();
  await mkdir(join(f.directory,'feedback-one'));await writeFile(join(f.directory,'feedback-one/REPORT.zh-CN.md'),'# Saved report');
  await f.progress.finish(summary([{student_id:'one',status:'submitted',total_score:null,review_status:'review_required',feedback_status:'submitted'}],[],{report_submitted:true}));
  const s=await f.snapshot();assert.equal(s.status,'completed');assert.equal(s.students[0].total_score,null);assert.equal(s.counts.review_required,1);assert.equal(s.counts.completed,1);assert.equal(s.reports.length,1);assert.match(s.reports[0].url,/^file:/);assert.match(f.messages.join('\n'),/本份总分：待定/);
  await f.progress.observe({type:'request_admitted',request:req(8,'main','reporting')});assert.deepEqual(await f.snapshot(),s);
});
test('partial feedback and cancelled work retain saved grades without claiming all reports are complete',async t=>{
  const f=await fixture(t,['a','b']);await f.progress.start();
  await f.progress.observe({type:'grading_result_saved',student_id:'a',review_status:'provisional'});
  await f.progress.finish(summary([{student_id:'a',status:'submitted',feedback_status:'failed',total_score:7},{student_id:'b',status:'cancelled'}],[req(1,'student-a','student_grading',.02)],{status:'partial_completed'}),{cancelled:true});
  const s=await f.snapshot();assert.equal(s.status,'cancelled');assert.equal(s.counts.grading_saved,1);assert.equal(s.counts.completed,0);assert.equal(s.counts.failed,1);assert.equal(s.counts.cancelled,1);assert.match(s.next_action,/不会自动重新批改/);
});
test('preflight explains that no model ran and gives the next concrete action',async t=>{
  const f=await fixture(t);await f.progress.preflight();const s=await f.snapshot();assert.equal(s.status,'preflight');assert.equal(s.requests.admitted,0);assert.match(s.message,/未调用模型、未产生费用/);assert.match(s.next_action,/新输出目录.*--execute/);assert.equal(f.progress.timer,null);
});

test('slow progress writes cannot lose a subsequent request receipt or change model input',async t=>{
  const {createRuntime}=await import('../src/cohort-runtime.mjs');
  const f=await fixture(t);let notifyEntered,release;const entered=new Promise(r=>notifyEntered=r),blocked=new Promise(r=>release=r);
  const events=[],payloads=[];const source={messages:[{role:'user',content:[{type:'text',text:'Source-bound test input'}]}]};
  const model={cost:{input:1,output:5}};
  const models={streamSimple:async(_model,_context,options)=>{payloads.push(await options.onPayload(structuredClone(source)));return {};}};
  const runtime=createRuntime({models,model,output:f.directory,cap:1,controller:new AbortController(),structuredOutput:false,progress:{observe:async e=>{events.push(e);if(e.type==='request_terminal'&&e.request.number===1){notifyEntered();await blocked;}}}});
  t.after(()=>runtime.close());const io=await runtime.io('student-one',()=> 'student_grading');let observer;
  io.attach({subscribe:fn=>{observer=fn;return ()=>{};}});
  const message=cost=>({role:'assistant',stopReason:'toolUse',usage:{cost:{totalFromProvider:true,total:cost}}});
  await io.streamFn(model,{},{});const first=observer({type:'message_end',message:message(.02)});await entered;
  await io.streamFn(model,{},{});release();await first;
  await observer({type:'message_end',message:message(.03)});
  assert.deepEqual(runtime.budget.requests.map(r=>r.cost_usd),[.02,.03]);
  assert.deepEqual(events.filter(e=>e.type==='request_terminal').map(e=>e.request.number),[1,2]);
  assert.deepEqual(payloads[0],payloads[1]);assert.deepEqual(payloads[0].messages,source.messages);
});
