import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { freezeRubric, createStudentAgent } from '../src/cohort-core.mjs';
import { expandCompactPoints, COMPACT_POINTS_SCHEMA } from '../src/compact-points.mjs';
import { inlineAnnotationSchema, splitInlineAnnotations, annotationFrame, attachInlineAnnotations, withoutAnnotationGeometry, annotationEvidenceHash } from '../src/inline-annotations.mjs';
import { mergeGradingCorrection } from '../src/submission-contract.mjs';
import { digest } from '../src/core.mjs';
import { makeRecord, emptyState } from '../src/workspace/store.mjs';
import { gradingAnnotations } from '../web/grading-annotations.mjs';

const student={sha256:'neutral-answer',pages:[{page:1,sha256:'p1'},{page:2,sha256:'p2'}]},scheme={sha256:'neutral-ms',pages:[{page:1,sha256:'ms1'}]};
const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items:[{question_id:'Example',item_id:'K',max_score:1,criteria:'Identify the document genre.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
  scoring_points:[{point_id:'genre',max_score:1,allowed_awards:[0,1],award_type:'A',condition:'Identify a letter.',source_text:'letter',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['genre'],description:'Any equivalent description.'}]}]},scheme,new Set([1]));
const raw=(boxes=[['i1',100,200,300,100]])=>({items:[{id:'K',route:'r',review:false,p:[['genre',1,'a letter',[1],'m','Correct genre',boxes]]}],review_notes:[],source_issues:[]});
const geometry={page:1,original_sha256:'p1',pixel_identity_verified:true,original_size:[1000,1200],size:[800,800],bbox:[100,200,900,1000]};
const frames=new Map([['i1',annotationFrame(student.pages[0],'exact_white_margin_trim',geometry)],['o1',annotationFrame(student.pages[0],'original')],['i2',annotationFrame(student.pages[1],'original')]]);
const receipts=new Map([['one',{annotation_frame:'i1',role:'student',page:1,representation:'exact_white_margin_trim',original_sha256:'p1',image_hash:'delivered-image'}]]);
const expand=input=>{const split=splitInlineAnnotations(input);return attachInlineAnnotations(expandCompactPoints(split.grading,frozen,student),split.annotations,student,frames,receipts);};

test('inline locations preserve the exact six-cell grading authority and restore crop coordinates',()=>{
  const input=raw(),before=structuredClone(input),grade=expand(input),point=grade.items[0].point_decisions[0];
  assert.deepEqual(withoutAnnotationGeometry(grade),expandCompactPoints(splitInlineAnnotations(input).grading,frozen,student));
  assert.deepEqual(input,before);
  assert.equal(point.annotation.status,'located');
  assert.deepEqual(point.annotation.regions[0].rect,{x:.18,y:.3,width:.24,height:1/15});
  assert.equal(point.annotation.regions[0].pageHash,'p1');
  assert.equal(point.annotation.regions[0].imageHash,'delivered-image');
  assert.equal(point.annotation.evidence_hash,annotationEvidenceHash(point));
  assert.equal(inlineAnnotationSchema(COMPACT_POINTS_SCHEMA).properties.items.items.properties.p.items.minItems,6);
});

test('renamed IDs, reordered language and equivalent layouts do not let coordinates decide a score',()=>{
  for(const [id,evidence,box] of [['Renamed','This is a personal letter',['i1',500,50,150,30]],['文体','一封信',['i1',10,800,350,100]],['Different-Layout','LETTER',['i1',200,400,200,50]]]){
    const rubric=structuredClone(frozen);rubric.artifact.items[0].item_id=id;
    const input=raw([box]);input.items[0].id=id;input.items[0].p[0][2]=evidence;
    const split=splitInlineAnnotations(input),base=expandCompactPoints(split.grading,rubric,student);
    assert.deepEqual(withoutAnnotationGeometry(attachInlineAnnotations(structuredClone(base),split.annotations,student,frames,receipts)),base);
  }
});

test('foreign/undelivered frames, broad boxes and invalid bounds degrade only the annotation',()=>{
  for(const boxes of [[['i99',100,200,300,30]],[['i2',100,200,300,30]],[['o1',100,200,300,30]],[['i1',900,0,200,30]],[['i1',0,0,1000,1000]],[['i1',0,0,1,1]],[['i1',null,0,100,100]],'wrong']){
    const point=expand(raw(boxes)).items[0].point_decisions[0];
    assert.equal(point.score,1);assert.equal(point.evidence,'a letter');
    assert.equal(point.annotation.status,'invalid');assert.deepEqual(point.annotation.regions,[]);
  }
  const input=raw();input.items[0].p[0].pop();
  assert.equal(expand(input).items[0].point_decisions[0].annotation.status,'missing');
});

test('known incorrect work stays zero and unreadable/absent work stays unknown without invented marks',()=>{
  const wrong=raw();wrong.items[0].p[0].splice(1,5,0,'a poem',[1],'u:c','Wrong genre');
  const p=expand(wrong).items[0].point_decisions[0];assert.equal(p.score,0);assert.equal(p.annotation.status,'located');
  const unknown=raw([]);unknown.items[0].review=true;unknown.items[0].p[0].splice(1,5,null,'Unreadable answer',[1],'q:u','Cannot determine the words');
  const q=expand(unknown).items[0].point_decisions[0];assert.equal(q.score,null);assert.equal(q.annotation.status,'unlocated');
});

test('multiple regions remain separate and local item corrections preserve their bytes',()=>{
  const input=raw([['i1',100,200,300,30],['i1',100,600,200,40]]),point=expand(input).items[0].point_decisions[0];
  assert.equal(point.annotation.regions.length,2);
  const changedItem=structuredClone(input.items[0]);changedItem.p[0][5]='A detailed explanation';
  const fixed=mergeGradingCorrection({raw:input},{submission_hash:digest(input),items:[changedItem],review_notes:null,source_issues:null},frozen);
  assert.deepEqual(fixed.items[0].p[0][6],input.items[0].p[0][6]);
  const pages=[{id:'page',sha256:'p1',sourcePage:1,role:'student'}],group={id:'g',label:'Student',pageIds:['page']},task={id:'t',kind:'grade',pages,groups:[group],scheme:{pageIds:[]}};
  const record=makeRecord(task,group,{item_id:'K',student_pages:[1]},point,frozen.artifact.items[0].scoring_points[0],'grade-hash',frozen.hash);
  task.records=[record];
  const note=gradingAnnotations({...emptyState(),pages,groups:[group],tasks:[task]},'t','g')[0];
  assert.equal(note.regions.length,2);assert.equal(note.locationOrigin,'inline-grading');
  assert.deepEqual(note.target.rect,{x:0,y:0,width:1,height:1},'multi-region chat references include the whole original page');
  const changed=structuredClone(point);changed.evidence='different observation';
  const stale=makeRecord(task,group,{item_id:'K'},changed,{},'new-hash',frozen.hash);
  assert.equal(stale.annotationStatus,'stale');assert.deepEqual(stale.annotationRegions,[]);
});

test('actual Pi saves valid grades in one request even when optional geometry is malformed',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
  for(const boxes of [[['i1',100,200,300,30]],{x:100},[{}],true]){
  let calls=0,saved,submitted;const initialImages=[];
  const child=createStudentAgent({model,scheme,student,frozen,protocol:'evidence-v4',inlineAnnotations:true,log:async()=>{},
    readImage:async()=>assert.fail('No source reinspection needed'),readInitialStudentImage:async page=>({type:'image',mimeType:'image/png',data:`already-read-${page.page}`}),
    persist:async grade=>saved=grade,persistSubmission:async input=>submitted=input,
    streamFn:(_model,context)=>{calls++;initialImages.push(...context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image'));
      const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',
        content:[{type:'toolCall',id:'grade-and-locate',name:'submit_grading',arguments:raw(boxes)}],usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{total:0}}}}));return stream;}});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(calls,1);assert.equal(initialImages.length,2);assert.equal(submitted.items[0].p[0].length,7);
  assert.equal(saved.items[0].point_decisions[0].score,1);
  assert.equal(saved.items[0].point_decisions[0].annotation.status,Array.isArray(boxes)&&Array.isArray(boxes[0])?'located':'invalid');
  assert.equal(saved.student_pages_delivered.length,2);
  assert.equal(saved.image_delivery_receipts[0].annotation_frame,'i1');
  }
});

test('permissive annotation transport never permits malformed grading cells',()=>{
  for(const [index,value] of [[0,{}],[1,{}],[2,{}],[3,{}],[4,{}],[5,{}]]){
    const input=raw({malformed:'geometry'});input.items[0].p[0][index]=value;
    assert.throws(()=>expand(input),`grading cell ${index} must still be rejected`);
  }
});

test('native scan positions map through each page placement to the original PDF without changing awards',()=>{
  for(const mapping of [{x:.1,y:.05,width:.8,height:.9},{x:.2,y:.15,width:.6,height:.7}]) {
    const source=structuredClone(student);source.pages[0].image_to_pdf=mapping;source.pages[0].source_page=7;
    const split=splitInlineAnnotations(raw([['o1',100,200,300,100]]));
    const deliveries=new Map([['original',{annotation_frame:'o1',role:'student',page:1,representation:'original',original_sha256:'p1',image_hash:'native-image'}]]);
    const before=expandCompactPoints(split.grading,frozen,source);
    const grade=attachInlineAnnotations(structuredClone(before),split.annotations,source,frames,deliveries);
    const region=grade.items[0].point_decisions[0].annotation.regions[0];
    assert.deepEqual(region.rect,{x:.1,y:.2,width:.3,height:.1});
    assert.deepEqual(region.pdfRect,{x:mapping.x+.1*mapping.width,y:mapping.y+.2*mapping.height,width:.3*mapping.width,height:.1*mapping.height});
    assert.equal(region.pdfPage,7);
    assert.deepEqual(withoutAnnotationGeometry(grade),before);
  }
});
