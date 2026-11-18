import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {outputBudget} from '../src/output-budget.mjs';
import {Budget} from '../src/core.mjs';
import {createRuntime} from '../src/cohort-runtime.mjs';

const model={id:'neutral',maxTokens:200000,contextWindow:1000000,cost:{input:1.5,cacheWrite:2,output:7.5}};
const allowance=extra=>outputBudget({model,payload:{max_tokens:model.maxTokens},inputTokens:1000,prices:model.cost,available:1,...extra});
test('native capacity, actual serializer ceiling, context and funds independently bound the final wire',()=>{
  for(const args of [{available:3},{payload:{max_tokens:40000}},{inputTokens:990000,available:10},{available:.1}]){
    const p=args.payload??{max_tokens:model.maxTokens},a=allowance({...args,payload:p});
    assert.equal(p.max_tokens,a.tokens);assert.ok(a.reservation.input_usd+a.reservation.output_usd<=(args.available??1));
  }
  assert.equal(allowance({available:3}).tokens,200000);
  assert.equal(allowance({payload:{max_tokens:40000}}).tokens,40000);
  assert.equal(allowance({inputTokens:990000,available:10}).tokens,9999);
  assert.ok(allowance().tokens>16000);
  assert.throws(()=>allowance({payload:{max_tokens:5,max_completion_tokens:6}}),/Conflicting/);
  for(const prices of [{output:1},{input:1,output:NaN},{input:1,output:2,cacheWrite:-1}])assert.throws(()=>allowance({prices}),/prices/);
  assert.throws(()=>allowance({available:.0001}),e=>e.code==='OUTPUT_BUDGET_LIMIT');
});
test('declared siblings retain funds before startup; coordinator can dispatch another batch and closed balances can be reused',()=>{
  const b=new Budget({cap:3});b.allocateScopes(['main','student-a','student-b']);
  const a=b.admit(1,{budget_scope:'student-a'});b.settle(a,{usage:{cost:{totalFromProvider:true,total:1}}});b.closeScope('student-a');
  assert.equal(b.available('main'),1);assert.equal(b.available('student-b'),1);
  const main=b.admit(1,{budget_scope:'main'});b.settle(main,{usage:{cost:{totalFromProvider:true,total:.1}}});
  assert.ok(Math.abs(b.available('student-b')-1)<1e-12);assert.throws(()=>b.admit(1.1,{budget_scope:'student-b'}),e=>e.code==='STUDENT_BUDGET_LIMIT');
  const child=b.admit(b.available('student-b'),{budget_scope:'student-b'});b.settle(child,{usage:{cost:{totalFromProvider:true,total:.2}}});b.closeScope('student-b');
  assert.ok(Math.abs(b.available('main')-1.7)<1e-12);
  b.allocateScopes(['student-b','main','student-a']);assert.equal(b.available('student-a'),0);
  assert.throws(()=>b.allocateScopes(['foreign']),/already allocated/);
});
test('unknown reservations survive scope closure; explicit student amounts do not cap coordinator funds',()=>{
  const b=new Budget({cap:1,scopeCap:.1});b.allocateScopes(['main','student-a','student-b']);
  const a=b.admit(.1,{budget_scope:'student-a'});b.settle(a,{usage:{cost:{totalFromProvider:false,total:0}}});b.closeScope('student-a');
  assert.equal(b.chargedOrReserved,.1);assert.equal(b.available('student-b'),.1);assert.ok(b.available('main')>.1);
  assert.throws(()=>b.admit(.1001,{budget_scope:'student-b'}),e=>e.code==='STUDENT_BUDGET_LIMIT');
});
test('standalone student work does not protect an unused coordinator share',()=>{
 const runtime=createRuntime({model,models:{},output:tmpdir(),cap:1,controller:new AbortController()});
 try{
  runtime.allocateStudentBudgets(['a','b'],{reserveCoordinator:false});
  assert.equal(runtime.budget.scopes.has('main'),false);assert.equal(runtime.budget.available('student-a'),.5);
  const row=runtime.budget.admit(.5,{budget_scope:'student-a'});runtime.budget.settle(row,{usage:{cost:{totalFromProvider:true,total:.1}}});runtime.finishStudentBudget('a');
  assert.equal(runtime.budget.available('student-b'),.9);
 }finally{runtime.close();}
});
test('concurrent real runtime admissions retain sibling funds, while one scope failure leaves its sibling runnable',async()=>{
  const output=await mkdtemp(join(tmpdir(),'native-output-')),controller=new AbortController();
  const runtime=createRuntime({model,models:{streamSimple:(_m,c,o)=>o.onPayload({model:model.id,max_tokens:o.maxTokens,messages:[{role:'user',content:c.large?'x'.repeat(250000):'neutral evidence'}]})},output,cap:1,controller,structuredOutput:false});
  try{
    runtime.allocateStudentBudgets(['a','b']);
    const a=await runtime.io('student-a',()=> 'student_grading'),b=await runtime.io('student-b',()=> 'student_grading');
    await assert.rejects(a.streamFn(model,{large:true}),e=>e.code==='STUDENT_BUDGET_LIMIT');assert.equal(controller.signal.aborted,false);
    const wires=await Promise.all([a.streamFn(model,{}),b.streamFn(model,{})]);
    assert.equal(runtime.budget.requests.length,2);assert.ok(wires.every(w=>w.max_tokens>16000));assert.ok(runtime.budget.chargedOrReserved<1);
    assert.ok(runtime.budget.available('main')>0);
  }finally{runtime.close();await rm(output,{recursive:true,force:true});}
});
