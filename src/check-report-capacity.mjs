// Offline harness/serialization check. Scripted assistant responses are not paid model judgments.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {parseArgs} from 'node:util';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {createCoordinator,validateFrozenRubric} from './cohort-core.mjs';
import {createReporting} from './cohort-reporting.mjs';
import {ResultsStore} from './results-store.mjs';
import {freezeJson,readImage,redactImages} from './cohort-runtime.mjs';
import {digest,wireEstimate} from './core.mjs';

const {values}=parseArgs({options:{source:{type:'string'},output:{type:'string'},'economy-reporting':{type:'boolean',default:false}}});
const economy=values['economy-reporting'];
if (!values.source||!values.output) throw Error('Required --source terminal-cohort --output new-directory');
const source=resolve(values.source),output=resolve(values.output);
const load=async name=>JSON.parse(await readFile(resolve(source,name),'utf8'));
const prior=await load('summary.json');assert.equal(prior.active_agents_at_summary,0);assert.equal(prior.status,'submitted');
const plan=await load('plan.json');const frozen=validateFrozenRubric(await load('rubric.json'),plan.scheme);
const template=await load('student-001/grading.json'),feedbackTemplate=await load('feedback-001/feedback.json');
assert.equal(digest(await readFile(resolve(source,'student-001/grading.json'))),(await readFile(resolve(source,'student-001/grading.sha256'),'utf8')).trim());
await mkdir(output,{recursive:false});
const sourceHashes={};
for (const name of ['core.mjs','cohort-core.mjs','cohort-reporting.mjs','report-context.mjs','cohort-runtime.mjs','results-store.mjs','rubric-contract.mjs','report-markdown.mjs','check-report-capacity.mjs']) sourceHashes[name]=digest(await readFile(new URL(name,import.meta.url)));
await freezeJson(output,'plan.json',{source,mode:'offline capacity simulation',economy_reporting:economy,source_hashes:sourceHashes,provider_calls:0,
  labels_loaded:false,grading_dispatch_concurrency:30,scenarios:['normal10','inspection10','stress5'],
  statement:'Source grades are copied for serialized body sizes; no accuracy claim or new model grading is performed.'});
const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter',plan.model.id);
const ids=Array.from({length:30},(_,i)=>`capacity-${String(i+1).padStart(2,'0')}`);
const scenarioResults=[];
for (const scenario of ['normal','inspection','stress']) {
  const directory=resolve(output,scenario);await mkdir(directory);
  const store=new ResultsStore(resolve(directory,'results'),ids);await store.init();
  const sourceHashes=new Map();
  const longest=template.items.reduce((a,b)=>a.reason.length>b.reason.length?a:b).reason;
  for (const [index,id] of ids.entries()) {
    if (scenario==='stress'&&index===29) {await store.publish(id,{status:'failed',failure:'Synthetic transport failure; not a zero score',rubric_hash:frozen.hash});continue;}
    const grade=structuredClone(template);
    for (const item of grade.items) item.reason=`Capacity record ${id}: ${scenario==='stress'?longest:item.reason}`;
    if (scenario==='stress'&&index===28) {
      grade.items[0].score=null;grade.items[0].review_required=true;grade.items[0].point_decisions[0].score=null;
      Object.assign(grade.items[0].point_decisions[0],{relation:'uncertain',error_origin:'unknown',rule_ref:'',reason:'Synthetic unreadable required symbol.'});
      grade.total_score=null;grade.status='review_required';grade.questions.find(q=>q.question_id===grade.items[0].question_id).score=null;
      grade.review_notes.push('Synthetic unknown score must not become zero.');
      grade.source_issues.push({item_id:grade.items[0].item_id,observation:'Synthetic unresolved source conflict',blocks_award:true});
    }
    const feedback=structuredClone(feedbackTemplate);feedback.student_id=id;feedback.grade_hash=digest(grade);
    feedback.summary=`Capacity-only replay for ${id}. ${feedback.summary}`;
    await freezeJson(directory,`${id}-grade.json`,grade);await freezeJson(directory,`${id}-feedback.json`,feedback);
    const gradePath=resolve(directory,`${id}-grade.json`);const hash=digest(await readFile(gradePath));sourceHashes.set(gradePath,hash);
    await store.publish(id,{status:'submitted',rubric_hash:frozen.hash,grading_path:gradePath,grading_sha256:hash,
      answer_sha256:plan.students['001'].sha256,feedback_status:'submitted',feedback_path:resolve(directory,`${id}-feedback.json`),
      feedback_sha256:digest(await readFile(resolve(directory,`${id}-feedback.json`)))});
  }
  let main;const events=[];const log=async event=>events.push(event);
  const reporting=createReporting({store,output:directory,getRubric:()=>frozen,economy,context:{requested_students:30,unique_answer_sources:1,simulation:'Offline capacity only'},log,
    ensureSealed:async()=>{if (!main.registry.terminal()) throw Error('Wait for all students');return store.seal([...main.registry.rows.values()],frozen.hash);}});
  const script=[];let callNumber=0;
  const call=(name,args)=>({type:'toolCall',id:`capacity-call-${++callNumber}`,name,arguments:args});
  const refs=batch=>frozen.artifact.items.slice(0,4).map(item=>`${batch[0]}/${item.item_id}`);
  const sourceItems=frozen.artifact.items.slice(0,4).map(i=>i.item_id);
  const sourcePages=[...new Set([...frozen.artifact.items.slice(0,4).flatMap(i=>i.source_pages),...frozen.artifact.general_instructions.flatMap(i=>i.source_pages)])].slice(0,4);
  const notes=batch=>({student_ids:batch,observations:scenario==='stress'?Array.from({length:6},(_,i)=>`Capacity observation ${i+1}: `+'Preserve original scores, unknowns and source review. '.repeat(8).slice(0,350)):
    ['The delivered student records and their item reasons were inspected. Retain all review states and retrieve detailed points when needed.'],evidence_refs:refs(batch)});
  script.push(()=>[call('grade_students',{student_ids:ids,concurrency:30,initial_ms_pages:[]})]);
  const batchSize=scenario==='stress'?5:10;
  const batches=Array.from({length:Math.ceil(ids.length/batchSize)},(_,i)=>ids.slice(i*batchSize,i*batchSize+batchSize));
  for (const [batchIndex,batch] of batches.entries()) {
    script.push(()=>[call('read_cohort_results',{student_ids:batch}),...(!economy&&batchIndex===0?[call('analyze_cohort',{})]:[]),
      ...(scenario==='stress'&&batchIndex===0?[call('save_report_notes',notes(batch))]:[])]);
    if (scenario==='stress'&&batchIndex===0) script.push(()=>[call('read_cohort_results',{student_ids:batches[1]})]);
    if (scenario!=='normal') {
      script.push(()=>[call('read_point_evidence',{evidence_refs:refs(batch)}),call('inspect_ms',{item_ids:sourceItems,pages:sourcePages,question:'Inspect the selected source notation and compare it with the saved point evidence.'})]);
      if (scenario==='stress'&&batchIndex===0) script.push(()=>[call('inspect_ms',{item_ids:sourceItems,pages:[21],question:'Synthetic unrelated-page negative control.'})]);
    }
    script.push(()=>[call('save_report_notes',notes(batch))]);
  }
  if(!economy)script.push(()=>[call('analyze_cohort',{})]);
  script.push(()=>[call('submit_cohort_report',{title:'Offline capacity proof, not model grading',executive_summary:'Thirty scripted records were consumed with bounded context; this does not measure model judgment.',
    result_set_hash:store.sealed.result_set_hash,analysis_hash:reporting.getAnalysis().analysis_hash,
    analysis_sections:['gradeos.class_report','gradeos.global_logic_audit','harness.repeatability'].map(method_id=>({method_id,interpretation:'Actual local deterministic analysis; original point records remain retrievable.',evidence_refs:[refs(batches[0])[0]]})),
    review_priorities:[],learning_observations:['Simulated records are not a real class.'],limitations:['Offline serialization and retention check only; no paid model responses.']})]);
  if(!economy)script.push(()=>[call('finish_cohort',{})]);
  let turn=0;const requests=[];let failed=null;
  const streamFn=(selected,context,options)=>{
    const stream=createAssistantMessageEventStream();
    (async()=>{
      let payload;
      // Exercise Pi's real OpenRouter serializer. onPayload aborts BEFORE any HTTP, unconditionally.
      await models.streamSimple(selected,context,{...options,apiKey:'offline-no-network',maxRetries:0,maxTokens:12000,onPayload:p=>{
        p.provider={only:['openai'],allow_fallbacks:false,require_parameters:true,data_collection:'deny'};p.usage={include:true};
        for (const message of p.messages) for (const part of Array.isArray(message.content)?message.content:[]) if (part.type==='image_url') part.image_url.detail='high';
        payload=p;throw Error('Offline serialization: stop before network');}}).result();
      assert.ok(payload);const estimate=wireEstimate(payload);
      requests.push({number:turn+1,...estimate,headroom:272000-estimate.inputTokenReserve,admitted:estimate.inputTokenReserve<272000});
      await writeFile(resolve(directory,`request-${turn+1}.json`),JSON.stringify(redactImages(payload)));
      assert.ok(estimate.inputTokenReserve<272000,`Capacity exceeded at ${scenario} request ${turn+1}`);
      assert.ok(script[turn],`Unexpected turn ${turn+1}`);const content=script[turn++]();
      stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}});
    })().catch(error=>{failed=error.message;stream.push({type:'error',reason:'error',error:{role:'assistant',content:[],timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'error',errorMessage:error.message,usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}});});
    return stream;
  };
  main=createCoordinator({model,streamFn,scheme:plan.scheme,reusedRubric:frozen,studentIds:ids,reporting,readImage,log,
    executeStudent:async id=>({status:store.records.get(id).status}),persistRubric:async()=>assert.fail('No compilation'),persistCohort:value=>freezeJson(directory,'cohort.json',value)});
  await main.agent.prompt(main.initialPrompt);
  await writeFile(resolve(directory,'transcript.json'),JSON.stringify(redactImages(main.agent.state.messages),null,2));
  const errors=main.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).map(m=>({tool:m.toolName,content:m.content}));
  const complete=Boolean(main.getResult()&&reporting.getResult());
  assert.ok(!failed&&complete,failed??JSON.stringify(errors));assert.equal(reporting.getReadIds().length,30);
  assert.equal(errors.length,scenario==='stress'?3:0,JSON.stringify(errors));
  for (const [path,hash] of sourceHashes) assert.equal(digest(await readFile(path)),hash);
  const summary={scenario,status:'passed',model_calls:0,provider_cost_usd:0,report_batch_size:batchSize,grading_dispatch_concurrency:30,records_read:reporting.getReadIds().length,
    original_point_count:[...store.records.values()].filter(r=>r.status==='submitted').length*template.items.reduce((n,i)=>n+i.point_decisions.length,0),
    notes:reporting.getResult().notes,source_views:reporting.getResult().source_views,actual_analytics_hash:reporting.getAnalysis().analysis_hash,
    requests,peak_reservation:Math.max(...requests.map(r=>r.inputTokenReserve)),peak_images:Math.max(...requests.map(r=>r.images)),
    expected_errors:errors,original_grades_unchanged:true,limits:'Scripted assistant behavior; no evidence of model summarization quality, live30-student throughput, or billable token counts.'};
  await freezeJson(directory,'summary.json',summary);await writeFile(resolve(directory,'events.jsonl'),events.map(e=>JSON.stringify(e)).join('\n')+'\n');
  scenarioResults.push({scenario,peak_reservation:summary.peak_reservation,peak_images:summary.peak_images,requests:requests.length});
}
await freezeJson(output,'summary.json',{source,mode:'offline actual-Pi context and provider serialization',model_calls:0,scenarios:scenarioResults});
console.log(JSON.stringify({output,scenarios:scenarioResults}));
