import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { createStudentAgent, createCoordinator, freezeRubric } from '../src/cohort-core.mjs';
import { deferUnreviewedExceptions, scriptedStudentReport, validateReplayGuide, gradingSourcePages } from '../src/scripted-grading.mjs';
import { exceptionProbeFixture } from '../src/exception-probe-fixture.mjs';
import { digest } from '../src/core.mjs';

const models=createModels();models.setProvider(openrouterProvider());
const model=models.getModel('openrouter','openai/gpt-6-luna');
const scheme={sha256:'source',pages:[{page:1,sha256:'ms'}]},student={sha256:'answer',pages:[{page:1,sha256:'answer1'}]};
const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items:[{question_id:'Example',item_id:'Genre',max_score:1,criteria:'Identify a letter.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],scoring_points:[{point_id:'type',max_score:1,allowed_awards:[0,1],award_type:'A',condition:'Identify a letter.',source_text:'letter',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['type'],description:'Equivalent wording is allowed.'}]}]},scheme,new Set([1]));
const raw={observations:{Genre:{type:{t:'a personal letter',p:[1]}}},items:{Genre:{route:'r',review:false,p:{type:{s:1,j:'m',r:'='}}}},review_notes:[],source_issues:[]};
frozen.verification={final_rubric_hash:frozen.hash,source_sha256:scheme.sha256,review_hash:digest('neutral source review')};
const guide={proposalId:'approved',revision:2,body:'Accept equivalent genre names.',hash:digest('Accept equivalent genre names.'),rubricHash:frozen.hash,sourceHash:scheme.sha256,method:'teacher'};
const image=async page=>({type:'image',mimeType:'image/png',data:page.sha256});
const log=async()=>{};

for(const invalid of [false,true])test(`single-pass grading ${invalid?'retains failure without retry':'submits once with the confirmed guide and all pages'}`,async()=>{
  let calls=0,context,saved;
  const child=createStudentAgent({model,frozen,scheme,student,readImage:image,log,singlePass:true,markingGuide:guide,protocol:'evidence-v4',reasonStyle:'brief-full-credit',persist:async value=>{saved=value;},
    streamFn:(_model,ctx)=>{
      calls++;context=structuredClone(ctx);
      const stream=createAssistantMessageEventStream();
      const submission=structuredClone(raw);if(invalid)submission.items.Genre.p.type.s=7;
      queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',content:[{type:'toolCall',id:'one',name:'submit_grading',arguments:submission}],usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{total:0}}}}));return stream;
    }});
  await child.agent.prompt(await child.initialPrompt([1]));
  assert.equal(calls,1);assert.equal(child.getContinuations(),0);
  assert.deepEqual(child.agent.state.tools.map(t=>t.name),['submit_grading']);
  assert.equal(context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image').length,2);
  assert.ok(JSON.stringify(context).includes(guide.hash));
  const content=context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]);
  const answerIndex=content.findIndex(p=>p.type==='image'&&p.data==='answer1');
  const rubricIndex=content.findIndex(p=>p.type==='text'&&p.text.startsWith('Frozen rubric ('));
  const guideIndex=content.findIndex(p=>p.type==='text'&&p.text.startsWith('Teacher-confirmed execution document'));
  const msIndex=content.findIndex(p=>p.type==='image'&&p.data==='ms');
  assert.ok(answerIndex>=0&&answerIndex<rubricIndex&&rubricIndex<guideIndex&&guideIndex<msIndex);
  assert.equal(child.agent.state.systemPrompt.includes(frozen.artifact.items[0].criteria),false);
  assert.equal(content.filter(p=>p.type==='text'&&p.text.includes(guide.body)).length,1);
  assert.ok(content[rubricIndex].text.includes(JSON.stringify(frozen.artifact)));
  if(invalid){assert.equal(saved,undefined);assert.equal(child.getResult(),null);}else assert.equal(saved.total_score,1);
});

test('no model review does not silently approve any positive exception or zero unknown marks',()=>{
  const f=exceptionProbeFixture(),before=digest(f.primary);
  const grade=deferUnreviewedExceptions(f.primary,f.frozen,f.scheme,f.student);
  assert.equal(digest(f.primary),before);assert.equal(grade.total_score,null);
  assert.equal(grade.exception_review.targets.length,9);
  for(const item of grade.items)for(const point of item.point_decisions){
    const original=f.primary.items.find(i=>i.item_id===item.item_id).point_decisions.find(p=>p.point_id===point.point_id);
    if(original.score>0&&original.relation==='exception'){
      assert.equal(point.score,null);assert.equal(point.primary_score,original.score);assert.equal(item.review_required,true);
    }else assert.deepEqual(point,original);
  }
  const report=scriptedStudentReport('neutral',grade,f.frozen,null);
  assert.match(report,/待定/);
  for(const item of grade.items)for(const point of item.point_decisions)assert.ok(report.includes(point.evidence.replaceAll('|','\\|').replaceAll('\n',' ')));
});

test('confirmed guide cannot drift in source, rubric or text on replay',()=>{
  assert.deepEqual(validateReplayGuide(guide,frozen),guide);
  for(const change of [{hash:'different'},{body:'Edited after approval'},{rubricHash:'other'},{sourceHash:'other'}])assert.throws(()=>validateReplayGuide({...guide,...change},frozen));
});
test('approved compilation removes only duplicate MS images and keeps all visual or unresolved sources',()=>{
  const source={...scheme,pages:[1,2,3,4].map(page=>({page,sha256:`page-${page}`}))};
  const f=structuredClone(frozen);f.artifact.general_instructions=[{text:'General rule',source_pages:[2]}];
  f.artifact.items[0].requires_source_image=true;f.artifact.items[0].source_pages=[3];
  assert.deepEqual(gradingSourcePages(f,source,guide),[2,3]);
  f.artifact.items[0].requires_source_image=false;f.artifact.items[0].uncertainties=['Read layout'];
  assert.deepEqual(gradingSourcePages(f,source,guide),[2,3]);
  for(const g of [null,undefined])assert.deepEqual(gradingSourcePages(f,source,g),[1,2,3,4]);
  assert.deepEqual(gradingSourcePages(f,source,guide,true),[1,2,3,4]);
  f.artifact.unresolved_notes=['Scope of source ambiguity unknown'];
  assert.deepEqual(gradingSourcePages(f,source,guide),[1,2,3,4]);
  assert.throws(()=>gradingSourcePages(frozen,scheme,{...guide,hash:'changed'}));
});

test('withholding an exception propagates uncertainty through explicit dependencies, not unrelated points',()=>{
  const f=exceptionProbeFixture(),source=f.primary.items.find(i=>i.item_id==='Oak');
  const criterion=f.frozen.artifact.items.find(i=>i.item_id==='Oak');
  for(const [id,dependency]of [['later','credit'],['last','later'],['independent',null]]) {
    criterion.scoring_points.push({...structuredClone(criterion.scoring_points[0]),point_id:id,depends_on:dependency?[dependency]:[]});
    criterion.routes[0].point_ids.push(id);criterion.max_score++;
    source.point_decisions.push({...structuredClone(source.point_decisions[0]),point_id:id,relation:'met',rule_ref:'',error_origin:'none',reason:'Unambiguous ordinary award'});
    source.max_score++;source.score++;
  }
  const grade=deferUnreviewedExceptions(f.primary,f.frozen,f.scheme,f.student);
  const points=grade.items.find(i=>i.item_id==='Oak').point_decisions;
  for(const id of ['credit','later','last'])assert.equal(points.find(p=>p.point_id===id).score,null);
  assert.equal(points.find(p=>p.point_id==='independent').score,1);
  assert.equal(grade.exception_review.dependent_targets.length,2);
  assert.equal(source.point_decisions.find(p=>p.point_id==='last').score,1);
});

test('preparation coordinator exposes no grading or model-reporting tools',()=>{
  const coordinator=createCoordinator({model,scheme,studentIds:['one'],reusedRubric:frozen,prepareOnly:true,readImage:image,log,streamFn:()=>assert.fail('No coordinator model needed for reused MS')});
  assert.equal(coordinator.agent.state.tools.some(t=>['grade_students','finish_cohort','submit_cohort_report'].includes(t.name)),false);
  assert.equal(coordinator.getRubric().hash,frozen.hash);
});

test('scripted grading delivers complete pages in order and binds cross-page evidence in one request',async()=>{
  const {mkdtemp,writeFile,readFile,mkdir,rm}=await import('node:fs/promises');
  const {tmpdir}=await import('node:os');const {join}=await import('node:path');
  const {runScriptedGrading}=await import('../src/scripted-grading.mjs');
  const dir=await mkdtemp(join(tmpdir(),'pi-complete-pages-'));
  try {
    const pages=[],variants=[];
    for(const page of [1,2,3]) {
      const bytes=`complete-page-${page}`,path=join(dir,`page-${page}.png`);
      const gridBytes=`complete-grid-page-${page}`,gridPath=join(dir,`grid-${page}.png`);
      await writeFile(path,bytes);await writeFile(gridPath,gridBytes);
      pages.push({page,sha256:digest(bytes),absolute_path:path});
      variants.push({page,absolute_path:gridPath,sha256:digest(gridBytes),original_sha256:digest(bytes),
        size:[1064,1436],source_rect_in_image:[64,36,1064,1436],pixel_identity_verified:true,
        original_size:[1000,1400],grid:{columns:10,rows:40,version:'source-grid-v1'}});
    }
    const imageVariants={mode:'source_grid',documents:{neutral:{pages:variants}}};
    const answer={sha256:'complete-answer',pages};
    let calls=0,images,labels;
    const runtime={budget:{requests:[]},totals:()=>({admitted_requests:0}),
      io:async name=>{
        const directory=join(dir,name);await mkdir(directory);
        return {directory,log:async()=>{},attach:()=>()=>{},streamFn:(_model,context)=>{
          calls++;
          const content=context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]);
          images=content.filter(p=>p.type==='image');
          labels=content.filter(p=>p.type==='text'&&p.text.startsWith('student physical PDF page')).map(p=>p.text);
          const submission=structuredClone(raw);
          submission.observations.Genre.type={p:[1,3],l:['i1.I38:J40','i3.A1:C3'],t:'a personal\nletter'};
          const stream=createAssistantMessageEventStream();
          queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),
            api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',
            content:[{type:'toolCall',id:'one',name:'submit_grading',arguments:submission}],
            usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{total:0}}}}));
          return stream;
        }};
      },run:async(agent,prompt)=>agent.prompt(prompt)};
    const result=await runScriptedGrading({runtime,output:dir,frozen,guide,scheme,students:new Map([['neutral',answer]]),model,imageVariants,inlineAnnotations:true});
    assert.equal(result.status,'submitted');assert.equal(calls,1);
    assert.deepEqual(images.map(p=>Buffer.from(p.data,'base64').toString()),[1,2,3].map(p=>`complete-grid-page-${p}`));
    assert.deepEqual(labels,[1,2,3].map(p=>`student physical PDF page ${p}; annotation frame i${p}`));
    const grade=JSON.parse(await readFile(join(dir,'student-neutral/grading.json')));
    assert.deepEqual(grade.student_pages_delivered,[1,2,3]);
    assert.deepEqual(grade.image_delivery_receipts.map(p=>p.page),[1,2,3]);
    const point=grade.items[0].point_decisions[0];
    assert.equal(point.evidence,'a personal\nletter');
    assert.equal(point.annotation.status,'located');
    assert.deepEqual(point.annotation.regions.map(p=>p.page),[1,3]);
  }finally{await rm(dir,{recursive:true,force:true});}
});

test('fragmented page loaders are rejected before a model request',async()=>{
  const child=createStudentAgent({model,frozen,scheme,student,protocol:'evidence-v4',singlePass:true,
    readImage:image,readInitialStudentImage:async p=>[await image(p),await image(p)],log,
    streamFn:()=>assert.fail('No request for fragmented pages')});
  await assert.rejects(child.initialPrompt([]),/one complete image/);
  assert.throws(()=>createStudentAgent({model,frozen,scheme,student,initialStudentImageMode:'fragmented',
    readImage:image,log,streamFn:()=>assert.fail('No request for unsupported representation')}),/Unsupported answer image/);
});
