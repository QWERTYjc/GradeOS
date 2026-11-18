import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, rm, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {createModels} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {experimentModel, experimentProvider, HYDROGEN_ID, CARBON_ID} from '../src/experiment-models.mjs';
import {createRuntime} from '../src/cohort-runtime.mjs';
import {COMPACT_POINTS_SCHEMA} from '../src/compact-points.mjs';

function catalog(){const models=createModels();models.setProvider(openrouterProvider());return models;}
test('existing models retain their catalog metadata and route; new candidate cannot silently select a different model',()=>{
  const models=catalog();
  for(const id of ['openai/gpt-6.1-terra','openai/gpt-6.1-sol','openai/gpt-6-luna']) {
    assert.deepEqual(experimentModel(models,id),models.getModel('openrouter',id));
    assert.deepEqual(experimentProvider(id),{only:['openai'],allow_fallbacks:false,require_parameters:true,data_collection:'deny'});
  }
  assert.throws(()=>experimentModel(models,'google/guess'),/not configured/);
  assert.throws(()=>experimentProvider('google/guess'),/no declared/);
});
test('actual Pi OpenRouter serialization keeps Hydrogen low reasoning, image and canonical tool schema before network',async()=>{
  const models=catalog(),model=experimentModel(models,HYDROGEN_ID);let wire;
  const schema=structuredClone(COMPACT_POINTS_SCHEMA);
  const result=await models.streamSimple(model,{systemPrompt:'Neutral evidence only.',messages:[{role:'user',timestamp:1,content:[{type:'text',text:'Read this source.'},{type:'image',mimeType:'image/png',data:'synthetic-no-network'}]}],tools:[{name:'submit_grading',description:'Submit evidence.',parameters:schema}]},
    {apiKey:'local-test-only',maxRetries:0,maxTokens:16000,reasoning:'low',onPayload:payload=>{wire=payload;throw Error('Local wire inspection; do not send');}}).result();
  assert.equal(result.stopReason,'error');assert.equal(wire.model,HYDROGEN_ID);
  assert.deepEqual(wire.reasoning,{effort:'low'});
  assert.equal(wire.tools[0].function.name,'submit_grading');
  assert.deepEqual(wire.tools[0].function.parameters,schema);
  assert.deepEqual(schema,COMPACT_POINTS_SCHEMA);
  assert.equal(wire.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url').length,1);
  assert.ok(wire.max_tokens===16000||wire.max_completion_tokens===16000);
});
test('runtime records and sends the declared Google route with unchanged privacy, retries and image fidelity',async()=>{
  const output=await mkdtemp(resolve(tmpdir(),'pi-hydrogen-wire-'));
  const model=experimentModel(catalog(),HYDROGEN_ID),provider=experimentProvider(model.id);let sent,opts;
  const runtime=createRuntime({models:{streamSimple:async(_m,_c,options)=>{opts=options;sent=await options.onPayload({model:model.id,messages:[{role:'user',content:[{type:'image_url',image_url:{url:'data:image/png;base64,synthetic'}}]}]});return{};}},model,output,cap:0.8,controller:new AbortController(),provider,structuredOutput:false});
  try {
    const io=await runtime.io('student-neutral',()=> 'student_grading');await io.streamFn(model,{},{});
    assert.deepEqual(sent.provider,{only:['google-vertex/global'],allow_fallbacks:false,require_parameters:true,data_collection:'deny'});
    assert.equal(opts.maxRetries,0);assert.equal(sent.messages[0].content[0].image_url.detail,'high');
    assert.equal(sent.messages[0].content[0].image_url.url,'data:image/png;base64,synthetic');
    const saved=JSON.parse(await readFile(resolve(io.directory,'request-1.json'),'utf8'));assert.deepEqual(saved.provider,provider);
    assert.equal(runtime.budget.requests.length,1);
  } finally {runtime.close();await rm(output,{recursive:true,force:true});}
});

test('Terra, Sol and Luna retain image input, low reasoning and the same grading contract in native Pi wire',async()=>{
  const models=catalog();
  for(const id of ['openai/gpt-6.1-terra','openai/gpt-6.1-sol','openai/gpt-6.2-sol','openai/gpt-6-luna']){
    const model=experimentModel(models,id);let wire;
    await models.streamSimple(model,{systemPrompt:'Neutral source-bound grading.',messages:[{role:'user',timestamp:1,content:[{type:'image',mimeType:'image/png',data:'synthetic-no-network'}]}],tools:[{name:'submit_grading',description:'Submit complete evidence.',parameters:structuredClone(COMPACT_POINTS_SCHEMA)}]},
      {apiKey:'local-test-only',maxRetries:0,maxTokens:16000,reasoning:'low',onPayload:payload=>{wire=payload;throw Error('Inspect only; no network');}}).result();
    assert.equal(wire.model,id);assert.deepEqual(wire.reasoning,{effort:'low'});
    assert.deepEqual(wire.tools[0].function.parameters,COMPACT_POINTS_SCHEMA);
    assert.equal(wire.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url').length,1);
  }
});

test('Luna keeps high detail and the cached prefix through self-review and on-demand source images',async()=>{
  const output=await mkdtemp(resolve(tmpdir(),'pi-luna-high-detail-')),registry=catalog();
  const model=experimentModel(registry,'openai/gpt-6-luna'),payloads=[];
  const image=(data,detail)=>({type:'image_url',image_url:{url:`data:image/png;base64,${data}`,...(detail?{detail}:{})}});
  const messages=[{role:'developer',content:'Shared source rules.'},{role:'user',content:[
    {type:'text',text:'Complete answer and selected MS pages.'},image('answer-native','original'),image('scheme-native'),
  ]}];
  const initial=structuredClone(messages);
  const models={streamSimple:async(selected,context,options)=>{
    const payload=await options.onPayload({model:selected.id,messages:structuredClone(context.messages),reasoning:{effort:options.reasoning}});
    payloads.push(structuredClone(payload));return{};
  }};
  const runtime=createRuntime({models,model,output,cap:1,controller:new AbortController(),studentCacheNamespace:'neutral-high-detail',structuredOutput:false});
  try{
    let phase='student_grading';const io=await runtime.io('student-neutral',()=>phase);
    await io.streamFn(model,{messages},{reasoning:'low'});
    phase='student_self_review';messages.push({role:'assistant',content:'Primary draft saved.'});
    await io.streamFn(model,{messages},{reasoning:'low'});
    messages.push({role:'user',content:[{type:'text',text:'Requested original source page.'},image('source-reinspection','original')]});
    await io.streamFn(model,{messages},{reasoning:'low'});
    assert.deepEqual(messages.slice(0,initial.length),initial,'wire policy must not rewrite the retained source messages');
    for(const [index,payload] of payloads.entries()){
      const parts=payload.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url');
      assert.deepEqual(parts.map(p=>p.image_url.detail),Array(index===2?3:2).fill('high'));
      assert.deepEqual(parts.map(p=>p.image_url.url),['data:image/png;base64,answer-native','data:image/png;base64,scheme-native',...(index===2?['data:image/png;base64,source-reinspection']:[])]);
      assert.deepEqual(payload.reasoning,{effort:'low'});assert.deepEqual(payload.provider,experimentProvider(model.id));
      assert.deepEqual(payload.messages.slice(0,payloads[0].messages.length),payloads[0].messages);
      const saved=JSON.parse(await readFile(resolve(io.directory,`request-${index+1}.json`),'utf8'));
      assert.deepEqual(saved.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url').map(p=>p.image_url.detail),parts.map(p=>p.image_url.detail));
    }
    assert.equal(runtime.budget.requests.length,3);
  }finally{runtime.close();await rm(output,{recursive:true,force:true});}
});

test('mixed main and worker calls use their own prices under one aggregate budget and reject model drift',async()=>{
  const output=await mkdtemp(resolve(tmpdir(),'pi-mixed-models-')),registry=catalog();
  const model=experimentModel(registry,'openai/gpt-6.1-sol'),workerModel=experimentModel(registry,'openai/gpt-6-luna');
  const payloads=[];
  const models={streamSimple:async(selected,_context,options)=>{
    const wire=await options.onPayload({model:selected.id,messages:[{role:'user',content:'Neutral source evidence.'}]});
    payloads.push(wire);return {};
  }};
  const runtime=createRuntime({models,model,workerModel,provider:experimentProvider(model.id),workerProvider:experimentProvider(workerModel.id),output,cap:.015,maxOutputTokens:1000,controller:new AbortController(),structuredOutput:false});
  try{
    const main=await runtime.io('main',()=> 'ms_compilation'),child=await runtime.io('student-renamed',()=> 'student_grading');
    await main.streamFn(model,{},{});await child.streamFn(workerModel,{},{});
    const [parent,worker]=runtime.budget.requests;
    assert.equal(parent.configured_model,model.id);assert.equal(worker.configured_model,workerModel.id);
    assert.deepEqual(payloads.map(x=>x.model),[model.id,workerModel.id]);
    assert.equal(parent.reservation.output_usd,.01);assert.equal(worker.reservation.output_usd,.0005);
    // A cold request can be billed at cache-write rates; reserve that higher price.
    assert.ok(Math.abs(parent.reservation.input_usd/parent.cost_input_token_reserve-2.5/1e6)<1e-15);
    assert.ok(Math.abs(worker.reservation.input_usd/worker.cost_input_token_reserve-.125/1e6)<1e-15);
    assert.equal(runtime.budget.chargedOrReserved,parent.reserve_usd+worker.reserve_usd);
    await main.streamFn(model,{},{});assert.ok(runtime.budget.chargedOrReserved<=.015);await assert.rejects(main.streamFn(model,{},{}),/Budget reservation/);
    assert.throws(()=>child.streamFn(model,{},{}),/declared lane model/);
    assert.equal(runtime.budget.requests.length,3);assert.equal(payloads.length,3);
    runtime.budget.settle(parent,{model:model.id,usage:{cost:{totalFromProvider:true,total:.003}}});
    runtime.budget.settle(worker,{model:workerModel.id,usage:{cost:{totalFromProvider:true,total:.0002}}});
    assert.equal(runtime.totals(runtime.budget.requests).provider_reported_cost_usd,.0032);
    assert.equal(runtime.totals(runtime.budget.requests).unknown_cost_requests,1);
  }finally{runtime.close();await rm(output,{recursive:true,force:true});}
});

test('single-pass Luna uses the declared endpoint parameters without loosening provider privacy or routing',async()=>{
  const output=await mkdtemp(resolve(tmpdir(),'pi-luna-parameters-')),registry=catalog();
  const model=experimentModel(registry,'openai/gpt-6-luna');let sent;
  const models={streamSimple:async(_model,_context,options)=>{
    sent=await options.onPayload({model:model.id,max_completion_tokens:16000,messages:[{role:'system',content:'Common rubric'}],
      tools:[{type:'function',function:{name:'submit_grading',parameters:COMPACT_POINTS_SCHEMA}}]});return{};
  }};
  const runtime=createRuntime({models,model,output,cap:.1,controller:new AbortController(),singlePassGrading:true,coldCacheNamespace:'neutral-arm-a',structuredOutput:false});
  try {
    const io=await runtime.io('student-neutral',()=> 'student_grading');await io.streamFn(model,{},{});
    assert.equal(sent.max_tokens,16000);assert.equal('max_completion_tokens' in sent,false);assert.equal('parallel_tool_calls' in sent,false);
    assert.deepEqual(sent.tool_choice,{type:'function',function:{name:'submit_grading'}});
    assert.equal(sent.tools[0].function.strict,true);
    assert.deepEqual(sent.provider,experimentProvider(model.id));
    assert.match(sent.messages[0].content,/^Execution namespace neutral-arm-a/);
  }finally{runtime.close();await rm(output,{recursive:true,force:true});}
});


test('Carbon and Hydrogen retain low and medium reasoning in actual Pi wire, with identical source schemas',async()=>{
 const models=catalog();
 for(const id of [CARBON_ID,HYDROGEN_ID])for(const effort of ['low','medium']){
  const model=experimentModel(models,id);let wire;
  await models.streamSimple(model,{messages:[{role:'user',timestamp:1,content:[{type:'image',mimeType:'image/png',data:'synthetic-no-network'}]}],tools:[{name:'submit_grading',description:'Complete evidence.',parameters:COMPACT_POINTS_SCHEMA}]},
   {apiKey:'local-test-only',reasoning:effort,maxRetries:0,onPayload:p=>{wire=p;throw Error('Offline wire only');}}).result();
  assert.equal(wire.model,id);assert.deepEqual(wire.reasoning,{effort});assert.deepEqual(wire.tools[0].function.parameters,COMPACT_POINTS_SCHEMA);
  assert.ok((wire.max_tokens??wire.max_completion_tokens)>24000);assert.deepEqual(experimentProvider(id).only,['google-vertex/global']);
 }
});
