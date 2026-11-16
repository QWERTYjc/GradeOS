// Independent text-semantic probe, not a handwriting benchmark. Gold is never sent to the model.
import {readFile,mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {parseArgs} from 'node:util';
import {createModels} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {createRuntime,freezeJson} from './cohort-runtime.mjs';
import {digest} from './core.mjs';
import {exceptionProbeFixture} from './exception-probe-fixture.mjs';
import {exceptionTargets,reviewPacket,createExceptionReviewer,applyExceptionReview} from './exception-review.mjs';

const {values}=parseArgs({options:{output:{type:'string'},env:{type:'string'},execute:{type:'boolean',default:false}}});
if(!values.output) throw Error('Required --output new directory');
const output=resolve(values.output);await mkdir(output,{recursive:false});
const f=exceptionProbeFixture(),targets=exceptionTargets(f.primary);
const expected={Oak:'confirmed',Birch:'confirmed',Cedar:'confirmed',Ash:'rejected',Fir:'rejected',Elm:'confirmed',Willow:'unresolved',Maple:'unresolved',Yew:'rejected'};
await freezeJson(output,'posthoc-gold.json',expected);
const sourceHashes={};for(const name of ['exception-review.mjs','exception-probe-fixture.mjs','probe-exception-review.mjs','cohort-runtime.mjs']) sourceHashes[name]=digest(await readFile(new URL(name,import.meta.url)));
const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
await freezeJson(output,'plan.json',{mode:'Synthetic text semantics, no M2 content',model,reasoning:'low',cap_usd:.15,max_requests:6,source_hashes:sourceHashes,labels_in_model_context:false,images:0,
  scope:'3 equivalent valid inherited exceptions, new local operation and same-part-origin negatives, explicit local f.t. positive, ambiguous f.t., unreadable current step, inapplicable numerical rule'});
if(!values.execute){console.log(JSON.stringify({status:'preflight',output}));process.exit(0);}
if(values.env) process.loadEnvFile(resolve(values.env));
if(!process.env.OPENROUTER_API_KEY) throw Error('Credential missing');
const runtime=createRuntime({models,model,output,cap:.15,maxRequests:6,controller:new AbortController(),maxOutputTokens:4096});
const started=Date.now(),checks=[];let failure=null;
try{
  for(let start=0;start<targets.length;start+=4){
    const io=await runtime.io(`probe-${start/4+1}`,()=> 'exception_semantic_probe');
    const packet=reviewPacket(f.primary,f.frozen,f.scheme,f.student,targets.slice(start,start+4));
    await freezeJson(io.directory,'packet.json',packet);
    const reviewer=createExceptionReviewer({model,streamFn:io.streamFn,packet,scheme:f.scheme,student:f.student,readImage:f.loadImage,log:io.log,persist:result=>freezeJson(io.directory,'review.json',result)});
    const unsubscribe=io.attach(reviewer.agent);
    try{await runtime.run(reviewer.agent,await reviewer.initialPrompt(),io.directory);}finally{unsubscribe();}
    if(!reviewer.getResult())throw Error(reviewer.agent.state.errorMessage||'No valid review');
    checks.push(...reviewer.getResult().checks);
  }
  await freezeJson(output,'grading.json',applyExceptionReview(f.primary,f.frozen,f.scheme,f.student,checks,{hash:digest(checks)}));
}catch(error){failure=error.message;}finally{runtime.close();}
const summary={status:failure?'incomplete':'submitted',failure,elapsed_seconds:(Date.now()-started)/1000,...runtime.totals(runtime.budget.requests),requests:runtime.budget.requests,active_agents_at_summary:runtime.active.size};
await freezeJson(output,'summary.json',summary);
if(failure||runtime.active.size||runtime.budget.requests.some(r=>r.status!=='provider_reported')){console.log(JSON.stringify(summary));process.exit(2);}
const gold=JSON.parse(await readFile(resolve(output,'posthoc-gold.json'),'utf8'));
const evaluations=checks.map(c=>({item_id:c.item_id,expected:gold[c.item_id],actual:c.verdict,pass:c.verdict===gold[c.item_id]}));
await freezeJson(output,'evaluation.json',{checks:evaluations,matched:evaluations.filter(c=>c.pass).length,total:evaluations.length});
console.log(JSON.stringify({status:summary.status,matched:evaluations.filter(c=>c.pass).length,total:evaluations.length,cost_usd:summary.provider_reported_cost_usd,elapsed_seconds:summary.elapsed_seconds,output}));
if(evaluations.some(c=>!c.pass))process.exitCode=3;
