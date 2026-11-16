import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {createModels,createAssistantMessageEventStream,validateToolArguments} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {freezeRubric} from '../src/cohort-core.mjs';
import {digest} from '../src/core.mjs';
import {sourceBoundFeedbackSchema,sourceBoundFeedbackPacket,expandSourceBoundFeedback,feedbackFacts} from '../src/source-bound-feedback.mjs';
import {SOURCE_BOUND_REPORT_SCHEMA,expandSourceBoundReport,sourceReportFacts} from '../src/source-bound-report.mjs';
import {createFeedbackAgent,validateFeedback,renderStudentFeedback} from '../src/student-feedback.mjs';
import {createReporting} from '../src/cohort-reporting.mjs';
import {ResultsStore} from '../src/results-store.mjs';
import {renderReportMarkdown} from '../src/report-markdown.mjs';
import {freezeJson} from '../src/cohort-runtime.mjs';
import {experimentModel,HYDROGEN_ID} from '../src/experiment-models.mjs';

const models=createModels();models.setProvider(openrouterProvider());const model=experimentModel(models,HYDROGEN_ID);
function fixture(names=['Alpha','Beta','Gamma','Delta'],domain='Parameter u belongs to [-4,4], including zero.'){
 const [a,b,c,d]=names;
 const source=(id,max,condition,depends=[])=>({point_id:id,max_score:max,allowed_awards:[0,max],award_type:'credit',condition,source_text:condition,source_pages:[1],depends_on:depends});
 const rule=(id,parent,points,related=[])=>({item_id:id,question_id:parent,max_score:points.reduce((n,p)=>n+p.max_score,0),criteria:'Apply the stated source conditions.',source_pages:[1],related_item_ids:related,requires_source_image:false,image_reason:'',uncertainties:[],scoring_points:points,routes:[{route_id:'normal',point_ids:points.map(p=>p.point_id),description:'Complete source route.'}]});
 const rules=[rule(a,'Group',[source('basis',1,domain)]),rule(b,'Group',[source('method',1,'State the argument.'),source('conclusion',1,'Use the parameter domain to justify the conclusion.',['method'])],[a]),rule(c,'Other',[source('evidence',.5,'Identify the cited document.')]),rule(d,'Other',[source('follow',1,'Credit the inherited-input method under this local exception.')])];
 rules[1].scoring_points.push(source('alternative',2,'An alternative valid source route.'));rules[1].routes.push({route_id:'alternative',point_ids:['alternative'],description:'Exclusive alternative.'});
 const scheme={sha256:digest(rules),pages:[{page:1}]};
 const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items:rules},scheme,new Set([1]));
 const decision=(id,score,relation='met',reason='Full criterion met.')=>({point_id:id,score,relation,reason,evidence:'Saved answer evidence.',student_pages:[1],error_origin:'none',rule_ref:'',...(relation==='met'?{reason_encoding:'explicit_full_credit_attestation'}:{})});
 const items=rules.map(r=>({item_id:r.item_id,question_id:r.question_id,max_score:r.max_score,score:0,selected_route:'normal',review_required:false,student_pages:[1],scheme_pages:[1],reason:'Saved model interpretation.',point_decisions:[]}));
 Object.assign(items[0],{score:1,point_decisions:[decision('basis',1)]});
 Object.assign(items[1],{score:1,point_decisions:[decision('method',1),decision('conclusion',0,'unmet','Divide by u without checking whether u is zero.')]});
 Object.assign(items[2],{score:null,review_required:true,point_decisions:[decision('evidence',null,'uncertain','The source is ambiguous.')]});
 Object.assign(items[3],{score:1,review_required:true,point_decisions:[decision('follow',1,'exception','Saved local exception interpretation.')]});
 const grade={rubric_hash:frozen.hash,protocol:'evidence-v4',items,total_score:null,max_score:4.5,status:'review_required',review_notes:[],source_issues:[]};
 const raw={strengths:[{item_id:a,point_id:'basis'}],priorities:[{item_id:b,point_id:'conclusion'}],items:{[b]:{point_id:'conclusion',action:'check_scope',review:'none'},[c]:{point_id:'evidence',action:'inspect_source',review:'evidence_check'},[d]:{point_id:'follow',action:'check_scope',review:'source_check'}},additional_items:[]};
 return {frozen,grade,raw,names,scheme};
}
const check=(schema,raw)=>validateToolArguments({name:'submit',parameters:schema},{type:'toolCall',id:'call',name:'submit',arguments:raw});
function build(f){const built=expandSourceBoundFeedback(f.raw,f.grade,f.frozen);return {...validateFeedback(built.feedback,f.grade,f.frozen),version:5,generation_mode:'source-bound-v5',...built.metadata};}
function records(f){return [{student_id:'owner',grade:f.grade,feedback:build(f)}];}
function analysis(f){return {result_set_hash:'set',analysis_hash:'analysis',cohort_context:{unique_answer_sources:1},gradeos_global_logic_audit:{issue_count:0},gradeos_class_report:{average_score:null,score_distribution:{},pass_rate:0},coverage:{requested_records:1,scored_records:0},harness_repeatability:{score_distribution:{},items:f.grade.items.map(i=>({item_id:i.item_id,max_score:i.max_score,mean_score_rate:i.score===null?null:i.score/i.max_score,score_distribution:i.score===null?{}:{[i.score]:1},unknown_count:i.score===null?1:0,varies:false}))},methods:[]};}
function reportRaw(f){return {result_set_hash:'set',analysis_hash:'analysis',analysis_sections:['gradeos.class_report','gradeos.global_logic_audit','harness.repeatability'].map(method_id=>({method_id,evidence_refs:[`owner/${f.names[1]}`]})),review_priorities:[{evidence_refs:[`owner/${f.names[2]}`]}],learning_observations:[{kind:'non_full',evidence_refs:[`owner/${f.names[1]}`],action:'check_scope'}]};}
const refs=f=>new Set(f.names.map(id=>`owner/${id}`));

test('renamed/reordered mixed-credit groups preserve exact facts, null/fractional awards, and every original point',()=>{
 for(const names of [['Alpha','Beta','Gamma','Delta'],['文书甲','文书乙','待查','跟随'],['Source.Z','Source.A','Source.?','Source.+']]){
  const f=fixture(names);if(names[0]!=='Alpha'){f.grade.items.reverse();f.frozen.artifact.items.reverse();}
  const before=digest(f.grade),feedback=build(f),report=expandSourceBoundReport(reportRaw(f),records(f),analysis(f),refs(f));
  assert.deepEqual(feedback.fact_counts,{full:2,non_full:1,unknown:1,review:2});assert.match(feedback.summary,/总分待定/);
  assert.match(report.executive_summary,/2项记录为满分、1项未获满额、1项待定/);
  assert.equal(digest(f.grade),before);
  const markdown=renderStudentFeedback('owner',f.grade,f.frozen,feedback);
  for(const item of f.grade.items)for(const point of item.point_decisions){assert.ok(markdown.includes(point.reason));assert.ok(markdown.includes(point.evidence));}
  assert.ok(markdown.includes('0.5'));assert.ok(markdown.includes('不作为已验证的推荐解法'));
 }
});
test('wrong full-credit sets, positive focus hiding loss, unknown normalization and exception-as-mastery fail',()=>{
 const f=fixture();
 for(const mutate of [r=>r.items.Beta.point_id='method',r=>r.items.Beta.point_id='alternative',r=>r.items.Gamma.review='none',r=>r.items.Gamma.action='reconstruct',r=>r.items.Delta.action='verify_result',r=>r.strengths=[{item_id:'Delta',point_id:'follow'}],r=>r.priorities=[{item_id:'Alpha',point_id:'basis'}]]){
  const raw=structuredClone(f.raw);mutate(raw);assert.throws(()=>expandSourceBoundFeedback(raw,f.grade,f.frozen));
 }
 for(const id of ['Beta','Gamma','Delta']){const raw=reportRaw(f);raw.learning_observations=[{kind:'full_credit',evidence_refs:[`owner/${id}`],action:'verify_result'}];assert.throws(()=>expandSourceBoundReport(raw,records(f),analysis(f),refs(f)));}
 const malformed=structuredClone(f);malformed.grade.items[1].selected_route='alternative';assert.throws(()=>feedbackFacts(malformed.grade,malformed.frozen));
});
test('recommendations retain full source scope and related context, never promote unsafe grader algebra',()=>{
 for(const domain of ['Parameter u includes zero.','Parameter u explicitly excludes zero.','文书可以是信函或报告；须说明来源。','For code, input may be the empty array. '+ 'Preserve this qualification. '.repeat(30)]){
  const f=fixture(undefined,domain),feedback=build(f),source=feedback.source_focus.Beta;
  assert.equal(source.related_context[0].points[0].source_text,domain);
  assert.equal(source.prerequisite_points[0].condition,'State the argument.');
  assert.ok(source.point.condition.includes('parameter domain'));
  for(const key of ['assessment','next_step'])assert.ok(!feedback.items.find(i=>i.item_id==='Beta')[key].includes('Divide by u'));
  const markdown=renderStudentFeedback('owner',f.grade,f.frozen,feedback);assert.ok(markdown.includes(domain));assert.ok(markdown.includes('Divide by u without checking whether u is zero.'));
 }
});
test('zero, attempted-but-wrong and ambiguous evidence never become a causal or blank diagnosis',()=>{
 for(const evidence of ['No writing recorded.','A complete but wrong argument.','Illegible answer; identity unresolved.']){
  const f=fixture();f.grade.items[1].point_decisions[1].evidence=evidence;
  const feedback=build(f),report=expandSourceBoundReport(reportRaw(f),records(f),analysis(f),refs(f));
  assert.equal(feedback.items.find(i=>i.item_id==='Beta').assessment.includes('空白'),false);
  assert.equal(report.learning_observations.some(s=>/未作答|没有时间|策略不足|态度/.test(s)),false);
 }
 const f=fixture(),raw=structuredClone(f.raw);raw.summary='时间分配不足，所以未完成。';assert.throws(()=>expandSourceBoundFeedback(raw,f.grade,f.frozen));
 for(const field of ['title','executive_summary','limitations','notes']){const r=reportRaw(f);r[field]='An invented explanation.';assert.throws(()=>expandSourceBoundReport(r,records(f),analysis(f),refs(f)));}
});
test('both strict schemas reject prose/JSON debris, foreign references, extra solutions and causal action IDs',()=>{
 const f=fixture(),schema=sourceBoundFeedbackSchema(f.grade,f.frozen);check(schema,f.raw);check(SOURCE_BOUND_REPORT_SCHEMA,reportRaw(f));
 for(const mutate of [r=>r.items.Beta.next_step='Divide by u.',r=>r.items.Beta.action='lack_of_time',r=>r.items.Beta.review='},next_step:{',r=>r.items.Foreign=r.items.Beta]){
  const r=structuredClone(f.raw);mutate(r);assert.throws(()=>check(schema,r));assert.throws(()=>expandSourceBoundFeedback(r,f.grade,f.frozen));
 }
 const r=reportRaw(f);r.learning_observations[0].evidence_refs=['foreign/Beta'];assert.throws(()=>expandSourceBoundReport(r,records(f),analysis(f),refs(f)));
});
test('feedback schema and validator agree for mixed partial, zero, null and exception focus points',()=>{
 for(const names of [['Alpha','Beta','Gamma','Delta'],['来源甲','未完成','未知','跟随']]){
  const f=fixture(names),[,b,c,d]=names;
  f.frozen.artifact.items[1].scoring_points[0].allowed_awards=[0,.5,1];
  f.frozen.artifact.items[1].scoring_points[0].condition='One credit for the complete argument, half credit for the explicitly permitted partial argument.';
  f.frozen=freezeRubric(f.frozen.artifact,f.scheme,new Set([1]));f.grade.rubric_hash=f.frozen.hash;
  f.grade.items[1].point_decisions[0].score=.5;f.grade.items[1].score=.5;
  const schema=sourceBoundFeedbackSchema(f.grade,f.frozen);
  for(const [point,action,review,valid] of [['method','verify_result','none',true],['conclusion','verify_result','none',false],['conclusion','reconstruct','none',true],['conclusion','inspect_source','none',false],['conclusion','inspect_source','evidence_check',true]]){
   const raw=structuredClone(f.raw);raw.items[b]={point_id:point,action,review};raw.priorities=[];
   if(valid){check(schema,raw);expandSourceBoundFeedback(raw,f.grade,f.frozen);}else{assert.throws(()=>check(schema,raw));assert.throws(()=>expandSourceBoundFeedback(raw,f.grade,f.frozen));}
  }
  for(const [id,action,review] of [[c,'reconstruct','source_check'],[c,'inspect_source','none'],[d,'verify_result','source_check']]){
   const raw=structuredClone(f.raw);Object.assign(raw.items[id],{action,review});assert.throws(()=>check(schema,raw));assert.throws(()=>expandSourceBoundFeedback(raw,f.grade,f.frozen));
  }
 }
});
test('real Pi feedback persists a bound report in one call and Hydrogen wire retains the closed schema',async()=>{
 const f=fixture();let saved,calls=0,wire;
 const agent=createFeedbackAgent({model,grade:f.grade,frozen:f.frozen,mode:'source-bound-v5',persist:async x=>saved=x,log:async()=>{},streamFn:(_m,context)=>{
  calls++;const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content:[{type:'toolCall',id:'submission',name:'submit_student_feedback',arguments:f.raw}],timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{total:0}}}}));return stream;
 }});
 await agent.agent.prompt(agent.initialPrompt);assert.ok(saved);assert.equal(calls,1);assert.equal(saved.generation_mode,'source-bound-v5');assert.equal(saved.grade_hash,digest(f.grade));
 const result=await models.streamSimple(model,{systemPrompt:'Choose bound references.',messages:[{role:'user',timestamp:1,content:JSON.stringify(sourceBoundFeedbackPacket(f.grade,f.frozen))}],tools:[{name:'submit_student_feedback',description:'Submit',parameters:sourceBoundFeedbackSchema(f.grade,f.frozen)}]},{apiKey:'local-test-only',maxRetries:0,onPayload:p=>{wire=p;throw Error('Offline serialization only');}}).result();
 assert.equal(result.stopReason,'error');assert.deepEqual(wire.tools[0].function.parameters,sourceBoundFeedbackSchema(f.grade,f.frozen));
});
test('main report consumes immutable records, omits inherited free summaries, rejects false selections before persistence',async()=>{
 const f=fixture(),directory=await mkdtemp(resolve(tmpdir(),'source-report-'));
 try{
  const store=new ResultsStore(resolve(directory,'results'),['owner']);await store.init();
  const feedback=build(f);feedback.summary='DO_NOT_PROPAGATE_UNCHECKED_SUMMARY';
  await freezeJson(directory,'grade.json',f.grade);await freezeJson(directory,'feedback.json',feedback);
  await store.publish('owner',{status:'submitted',rubric_hash:f.frozen.hash,grading_path:resolve(directory,'grade.json'),grading_sha256:digest(await readFile(resolve(directory,'grade.json'))),answer_sha256:'source',feedback_status:'submitted',feedback_path:resolve(directory,'feedback.json'),feedback_sha256:digest(await readFile(resolve(directory,'feedback.json')))});
  await store.seal([{student_id:'owner',status:'submitted'}],f.frozen.hash);
  const reporting=createReporting({store,ensureSealed:async()=>store.sealed,getRubric:()=>f.frozen,context:{unique_answer_sources:1},output:directory,log:async()=>{},analyzeOverride:bundle=>({...analysis(f),analysis_hash:undefined,result_set_hash:bundle.result_set_hash}),economy:true,lean:true,sourceBound:true});
  const view=await reporting.prefetchFirstResults();assert.ok(!JSON.stringify(view).includes('DO_NOT_PROPAGATE_UNCHECKED_SUMMARY'));
  assert.ok(view.content.some(part=>part.type==='text'&&part.text.includes('"evidence_ref_prefix":"owner/"')));
  reporting.transformContext([{role:'toolResult',...view}]);reporting.onModelResponse();
  const submit=reporting.tools.find(t=>t.name==='submit_cohort_report');const raw=reportRaw(f);raw.result_set_hash=store.sealed.result_set_hash;raw.analysis_hash=reporting.getAnalysis().analysis_hash;
  const bad=structuredClone(raw);bad.learning_observations[0].kind='full_credit';bad.learning_observations[0].action='verify_result';
  await assert.rejects(submit.execute('bad',bad),/contradicts/);assert.equal(reporting.getResult(),null);
  for(const ref of ['owner:Beta','foreign/Beta','owner/Absent']){
    const wrong=structuredClone(raw);wrong.analysis_sections[0].evidence_refs=[ref];
    await assert.rejects(submit.execute('wrong-ref',wrong),/Unbound source report evidence/);assert.equal(reporting.getResult(),null);
  }
  await submit.execute('valid',raw);assert.ok(reporting.getResult());assert.ok((await readFile(resolve(directory,'REPORT.zh-CN.md'),'utf8')).includes('未获分本身不说明'));
 }finally{await rm(directory,{recursive:true,force:true});}
});

test('failed tasks remain missing, not zero scores or complete grading',()=>{
 const f=fixture(),raw=reportRaw(f);raw.analysis_sections.forEach(s=>s.evidence_refs=[]);raw.review_priorities=[];raw.learning_observations=[];
 const records=[{student_id:'owner',status:'failed',grade:null,feedback:null}];
 const report=expandSourceBoundReport(raw,records,analysis(f),new Set());
 assert.match(report.executive_summary,/0份有数值总分/);assert.match(report.analysis_sections[2].interpretation,/0份保存了评分结果/);assert.equal(report.executive_summary.includes('0分'),false);
});

test('cross-student review pairs retain exact ownership rather than a Cartesian reconstruction',()=>{
 const f=fixture(),a=analysis(f),raw=reportRaw(f);
 raw.analysis_sections.forEach(s=>s.evidence_refs=[]);raw.learning_observations=[];raw.review_priorities=[{evidence_refs:['first/Gamma','second/Delta']}];
 const paired=[{student_id:'first',grade:f.grade,feedback:build(f)},{student_id:'second',grade:f.grade,feedback:build(f)}];
 const report=expandSourceBoundReport(raw,paired,a,new Set(['first/Gamma','second/Delta']));
 assert.deepEqual(report.review_priorities[0].evidence_refs,['first/Gamma','second/Delta']);
 report.records_read=['first','second'];const markdown=renderReportMarkdown(report,a);assert.ok(markdown.includes('first/Gamma'));assert.ok(markdown.includes('second/Delta'));assert.equal(markdown.includes('second/Gamma'),false);
});
