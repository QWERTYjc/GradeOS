import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { ResultsStore } from '../src/results-store.mjs';
import { createReporting } from '../src/cohort-reporting.mjs';
import { createCoordinator, freezeRubric } from '../src/cohort-core.mjs';
import { freezeJson } from '../src/cohort-runtime.mjs';
import { digest } from '../src/core.mjs';

const raw = { general_instructions: [], items: [{ question_id: 'X', item_id: 'X(b)', max_score: 2,
  criteria: 'Credit a supported step; do not repair invalid work.', source_pages: [1], related_item_ids: [],
  requires_source_image: false, image_reason: '', uncertainties: [] }], unresolved_notes: [] };
const scheme = { sha256: 'unrelated-source', pages: [{ page: 1 }] };
const frozen = freezeRubric(raw, scheme, new Set([1]));
const grade = () => ({ items: [{ question_id: 'X', item_id: 'X(b)', score: 1, max_score: 2,
  reason: 'Supported first step only.', student_pages: [1], scheme_pages: [1], review_required: false }],
  total_score: 1, max_score: 2, rubric_hash: frozen.hash, status: 'provisional', review_notes: [] });
async function publish(store, directory, id) {
  const path = resolve(directory, `${id}-grade.json`); await freezeJson(directory, `${id}-grade.json`, grade());
  await store.publish(id, { status: 'submitted', rubric_hash: frozen.hash, grading_path: path,
    grading_sha256: digest(await readFile(path)), answer_sha256: 'same-answer' });
}
const mockAnalysis = bundle => ({ result_set_hash: bundle.result_set_hash, cohort_context: bundle.cohort_context,
  methods: [], coverage: { requested_records: bundle.records.length, scored_records: bundle.records.length },
  gradeos_class_report: { average_score: 1, pass_rate: 0, score_distribution: { D: bundle.records.length } },
  gradeos_global_logic_audit: { issue_count: 0 }, gradeos_student_summaries: [],
  harness_repeatability: { score_distribution: { 1: bundle.records.length }, population_sd: 0,
    constant_items: 1, item_count: 1, items: [{ item_id: 'X(b)', mean_score_rate: 0.5, score_distribution: { 1: bundle.records.length }, varies: false }] } });
function reportArgs(reporting, store) { return { title: 'Evidence report', executive_summary: 'Frozen results reviewed.',
  result_set_hash: store.sealed.result_set_hash, analysis_hash: reporting.getAnalysis().analysis_hash,
  analysis_sections: ['gradeos.class_report','gradeos.global_logic_audit','harness.repeatability'].map(method_id => ({ method_id, interpretation: 'One supported item judgment.', evidence_refs: ['a/X(b)'] })),
  review_priorities: [], learning_observations: [], limitations: ['Repeated answer; no topic mapping.'] }; }
function consume(reporting,...results) {
  reporting.transformContext(results.map(result=>({role:'toolResult',...result})));
  reporting.onModelResponse();
}
test('automatic first batch adapts to context capacity and all 30 persisted owners still require delivery',async()=>{
  const directory=await mkdtemp(resolve(tmpdir(),'pi-lean-thirty-'));
  try {
    const ids=Array.from({length:30},(_,i)=>i===0?'a':`student-${i}`);
    const store=new ResultsStore(resolve(directory,'results'),ids);await store.init();
    for(const id of ids){const value=grade();value.items[0].reason='Evidence. '.repeat(3500);
      const path=resolve(directory,`${id}.json`);await freezeJson(directory,`${id}.json`,value);
      await store.publish(id,{status:'submitted',rubric_hash:frozen.hash,grading_path:path,grading_sha256:digest(await readFile(path)),answer_sha256:'same-source'});
    }
    await store.seal(ids.map(student_id=>({student_id,status:'submitted'})),frozen.hash);
    const reporting=createReporting({store,economy:true,lean:true,ensureSealed:async()=>store.sealed,getRubric:()=>frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:mockAnalysis});
    const by=Object.fromEntries(reporting.tools.map(t=>[t.name,t]));
    const first=await reporting.prefetchFirstResults();const records=JSON.parse(first.content[0].text).records;
    assert.equal(records.length,2);assert.ok(reporting.views.pending()[0].textBytes<150000);
    assert.deepEqual(reporting.getReadIds(),[]);
    await assert.rejects(by.submit_cohort_report.execute('early',reportArgs(reporting,store)),/Read every/);
    consume(reporting,first);
    await assert.rejects(by.submit_cohort_report.execute('incomplete',reportArgs(reporting,store)),/Read every/);
    let batch=ids.slice(0,2);
    for(let offset=2;offset<ids.length;offset+=2){
      await by.save_report_notes.execute('notes',{student_ids:batch,observations:['Saved source judgments; no award changes.'],evidence_refs:['a/X(b)']});
      batch=ids.slice(offset,offset+2);
      const next=await by.read_cohort_results.execute('next',{student_ids:batch});consume(reporting,next);
    }
    assert.equal(reporting.getReadIds().length,30);
    await by.submit_cohort_report.execute('done',reportArgs(reporting,store));
    assert.equal(reporting.getResult().records_read.length,30);
  } finally {await rm(directory,{recursive:true,force:true});}
});
test('combined results and analytics must reach a later model response before submission',async()=>{
  const directory=await mkdtemp(resolve(tmpdir(),'pi-economy-gate-'));
  try{
    const store=new ResultsStore(resolve(directory,'results'),['a']);await store.init();await publish(store,directory,'a');
    await store.seal([{student_id:'a',status:'submitted'}],frozen.hash);
    const reporting=createReporting({store,ensureSealed:async()=>store.sealed,getRubric:()=>frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:mockAnalysis,economy:true});
    const by=Object.fromEntries(reporting.tools.map(t=>[t.name,t]));assert.equal(by.analyze_cohort,undefined);
    const read=await by.read_cohort_results.execute('r',{student_ids:['a']});assert.ok(JSON.parse(read.content[0].text).analysis);
    await assert.rejects(by.submit_cohort_report.execute('early',reportArgs(reporting,store)),/Read every/);
    consume(reporting,read);await by.submit_cohort_report.execute('valid',reportArgs(reporting,store));assert.ok(reporting.getResult());
  }finally{await rm(directory,{recursive:true,force:true});}
});
for(const lean of [false,true]) test(`Pi coordinator finishes after durable writes: lean=${lean}`,async()=>{
  const directory=await mkdtemp(resolve(tmpdir(),'pi-economy-loop-'));
  try{
    const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
    const store=new ResultsStore(resolve(directory,'results'),['a']);await store.init();let main,turn=0,persisted=false;
    const reporting=createReporting({store,economy:true,lean,ensureSealed:async()=>store.seal([...main.registry.rows.values()],frozen.hash),getRubric:()=>frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:mockAnalysis});
    const script=[()=>['grade_students',{student_ids:['a'],concurrency:1,initial_ms_pages:[]}],...(!lean?[()=>['read_cohort_results',{student_ids:['a']}]]:[]),()=>['submit_cohort_report',reportArgs(reporting,store)]];
    main=createCoordinator({model,scheme,reusedRubric:frozen,studentIds:['a'],reporting,log:async()=>{},readImage:async()=>assert.fail(),persistRubric:async()=>assert.fail(),
      executeStudent:async()=>{await publish(store,directory,'a');return{status:'submitted'};},persistCohort:async()=>{assert.ok(await readFile(resolve(directory,'report.json')));persisted=true;},
      streamFn:()=>{const [name,args]=script[turn++]();const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content:[{type:'toolCall',id:`e-${turn}`,name,arguments:args}],api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;}});
    await main.agent.prompt(main.initialPrompt);assert.equal(turn,lean?2:3);assert.ok(persisted);assert.ok(main.getResult());assert.deepEqual(reporting.getReadIds(),['a']);
  }finally{await rm(directory,{recursive:true,force:true});}
});
test('failed cohort persistence after report saving cannot mark the coordinator complete',async()=>{
  const directory=await mkdtemp(resolve(tmpdir(),'pi-economy-durability-'));
  try{
    const store=new ResultsStore(resolve(directory,'results'),['a']);await store.init();let main;
    const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
    const reporting=createReporting({store,economy:true,ensureSealed:async()=>store.seal([...main.registry.rows.values()],frozen.hash),getRubric:()=>frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:mockAnalysis});
    main=createCoordinator({model,scheme,reusedRubric:frozen,studentIds:['a'],reporting,log:async()=>{},readImage:async()=>assert.fail(),persistRubric:async()=>assert.fail(),streamFn:()=>assert.fail('No model calls'),
      executeStudent:async()=>{await publish(store,directory,'a');return{status:'submitted'};},persistCohort:async()=>{throw Error('Synthetic disk failure');}});
    const by=Object.fromEntries(main.agent.state.tools.map(t=>[t.name,t]));
    await by.grade_students.execute('dispatch',{student_ids:['a'],concurrency:1,initial_ms_pages:[]});
    const read=await by.read_cohort_results.execute('read',{student_ids:['a']});consume(reporting,read);
    await assert.rejects(by.submit_cohort_report.execute('report',reportArgs(reporting,store)),/disk failure/);
    assert.ok(reporting.getResult());assert.equal(main.getResult(),null);
  }finally{await rm(directory,{recursive:true,force:true});}
});

test('30 result owners publish concurrently; incomplete, duplicate and changed records fail closed', async () => {
  const directory = await mkdtemp(resolve(tmpdir(),'pi-results-'));
  try {
    const ids = Array.from({ length: 30 }, (_,i) => `s${i}`); const store = new ResultsStore(resolve(directory,'results'),ids);
    await store.init(); await assert.rejects(store.seal([], frozen.hash), /Incomplete/);
    await Promise.all(ids.map(id => publish(store,directory,id)));
    await assert.rejects(store.publish(ids[0], { status:'failed' }), /duplicate/);
    await store.seal(ids.map(student_id => ({ student_id,status:'submitted' })), frozen.hash);
    assert.equal((await store.read(ids)).length,30);
    await writeFile(resolve(directory,'s0-grade.json'),'{}');
    await assert.rejects(store.read(['s0']), /hash changed/);
  } finally { await rm(directory,{recursive:true,force:true}); }
});
test('failed result owners remain nonnumeric and reports cannot cite nonexistent evidence', async () => {
  const directory = await mkdtemp(resolve(tmpdir(),'pi-failed-'));
  try {
    const store = new ResultsStore(resolve(directory,'results'),['a','b']); await store.init(); await publish(store,directory,'a');
    await store.publish('b',{status:'failed',failure:'Transport unavailable',rubric_hash:frozen.hash});
    await store.seal([{student_id:'a',status:'submitted'},{student_id:'b',status:'failed'}],frozen.hash);
    const reporting = createReporting({store,ensureSealed:async()=>store.sealed,getRubric:()=>frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:mockAnalysis});
    const byName=Object.fromEntries(reporting.tools.map(t=>[t.name,t]));
    const analysis=await byName.analyze_cohort.execute('analysis',{});
    await assert.rejects(byName.submit_cohort_report.execute('early',reportArgs(reporting,store)),/Read every/);
    const read=await byName.read_cohort_results.execute('read',{student_ids:['a','b']});
    assert.equal(JSON.parse(read.content[0].text).records[1].result,null);
    consume(reporting,analysis,read);
    const invalid=reportArgs(reporting,store);invalid.analysis_sections[0].evidence_refs=['b/X(b)'];
    await assert.rejects(byName.submit_cohort_report.execute('bad',invalid),/Unbound/);
    await byName.submit_cohort_report.execute('good',reportArgs(reporting,store));assert.ok(reporting.getResult());
  } finally { await rm(directory,{recursive:true,force:true}); }
});
test('actual Pi coordinator cannot finish before reading shared results and submitting its report', async () => {
  const directory=await mkdtemp(resolve(tmpdir(),'pi-report-loop-'));
  try {
    const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
    const store=new ResultsStore(resolve(directory,'results'),['a']);await store.init();let main;let turn=0;const calls=[];
    const reporting=createReporting({store,ensureSealed:async()=>store.seal([...main.registry.rows.values()],frozen.hash),getRubric:()=>frozen,
      context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:mockAnalysis});
    const call=(name,args)=>({type:'toolCall',id:`t-${calls.push(name)}`,name,arguments:args});
    const streamFn=()=>{
      const content=[()=>[call('grade_students',{student_ids:['a'],concurrency:1,initial_ms_pages:[]})],
        ()=>[call('finish_cohort',{})],()=>[call('read_cohort_results',{student_ids:['a']}),call('analyze_cohort',{})],
        ()=>[call('submit_cohort_report',reportArgs(reporting,store)),call('finish_cohort',{})]][turn++]();
      const stream=createAssistantMessageEventStream();const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
      queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message}));return stream;
    };
    main=createCoordinator({model,streamFn,scheme,studentIds:['a'],concurrencyLimit:1,reusedRubric:frozen,reporting,
      readImage:async()=>assert.fail(),persistRubric:async()=>assert.fail(),persistCohort:async()=>{},log:async()=>{},
      executeStudent:async()=>{await publish(store,directory,'a');return{status:'submitted'};}});
    await main.agent.prompt(main.initialPrompt);
    assert.ok(main.getResult());assert.deepEqual(reporting.getReadIds(),['a']);
    assert.ok(main.agent.state.messages.some(m=>m.role==='toolResult'&&m.toolName==='finish_cohort'&&m.isError));
    assert.equal(calls.filter(name=>name==='submit_cohort_report').length,1);
  } finally { await rm(directory,{recursive:true,force:true}); }
});

test('main reads full item results first and can retrieve selected point evidence without changing awards', async () => {
  const directory=await mkdtemp(resolve(tmpdir(),'pi-point-report-'));
  try {
    const store=new ResultsStore(resolve(directory,'results'),['a']);await store.init();
    const value=grade();value.items[0].selected_route='source-route';
    value.items[0].point_decisions=[{point_id:'neutral-credit',score:1,evidence:'Saved own evidence',student_pages:[1],reason:'Supported condition'}];
    value.source_issues=[{item_id:'X(b)',observation:'Saved source uncertainty'}];
    await freezeJson(directory,'grade.json',value);const original=digest(value);
    await store.publish('a',{status:'submitted',rubric_hash:frozen.hash,grading_path:resolve(directory,'grade.json'),grading_sha256:digest(await readFile(resolve(directory,'grade.json')))});
    await store.seal([{student_id:'a',status:'submitted'}],frozen.hash);
    const reporting=createReporting({store,ensureSealed:async()=>store.sealed,getRubric:()=>frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{}});
    const tools=Object.fromEntries(reporting.tools.map(tool=>[tool.name,tool]));
    await assert.rejects(tools.read_point_evidence.execute('early',{evidence_refs:['a/X(b)']}),/Read valid/);
    const read=await tools.read_cohort_results.execute('items',{student_ids:['a']});
    const results=JSON.parse(read.content[0].text);consume(reporting,read);
    assert.equal(results.records[0].result.point_decision_count,1);
    assert.equal(results.records[0].result.columns.includes('point_decisions'),false);
    assert.equal(JSON.stringify(results).includes('Saved own evidence'),false);
    assert.equal(results.records[0].result.source_issues.length,1);
    const points=JSON.parse((await tools.read_point_evidence.execute('points',{evidence_refs:['a/X(b)']})).content[0].text);
    assert.equal(points.items[0].grading.point_decisions[0].evidence,'Saved own evidence');
    assert.equal(digest((await store.read(['a']))[0].grade),original);
    await assert.rejects(tools.read_point_evidence.execute('foreign',{evidence_refs:['a/other']}),/Read valid/);
  } finally {await rm(directory,{recursive:true,force:true});}
});
