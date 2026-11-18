import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { buildOCRRegionCatalog, ocrRegionIndex } from '../src/ocr-regions.mjs';
import { annotationFrame, decodeAnnotationRegions, withoutAnnotationGeometry } from '../src/inline-annotations.mjs';
import { createStudentAgent, freezeRubric } from '../src/cohort-core.mjs';
import { makeRecord, emptyState } from '../src/workspace/store.mjs';
import { gradingAnnotations } from '../web/grading-annotations.mjs';
import { annotationExportPacket } from '../src/workspace/annotation-export.mjs';
import { gradingCard } from '../web/annotation-card.mjs';

const student = { sha256: 'answer', pages: [1,2].map(page => ({page,sha256:`p${page}`})) };
const students = new Map([['neutral',student]]);
const observations = {engine:'local-test',documents:{neutral:{source_sha256:'answer',pages:[1,2].map(page=>({
  page,source_sha256:`p${page}`,rows:[{rect:[.2,.3,.2,.04],candidates:[{text:'UNTRUSTED OCR TEXT'}]},
    {rect:[.5,.6,.15,.05],candidates:[{text:'not evidence'}]}],
}))}}};
const catalog=buildOCRRegionCatalog(observations,students), manifestHash=catalog.documents.neutral.manifest_sha256;
const geometry=page=>({page,original_sha256:`p${page}`,source_coverage_verified:true,overlay:'local-ocr-regions-v1',
  original_size:[1000,1400],content_size:[360,504],size:[446,504],source_rect_in_image:[43,0,403,504],
  region_manifest_sha256:manifestHash,regions:catalog.documents.neutral.pages.find(p=>p.page===page).regions});
const frames=new Map(student.pages.map(p=>[`i${p.page}`,annotationFrame(p,'source_regions',geometry(p.page))]));
const receipts=new Map(student.pages.map(p=>[`i${p.page}`,{page:p.page,original_sha256:p.sha256,annotation_frame:`i${p.page}`,
  role:'student',representation:'source_regions',region_manifest_sha256:manifestHash,image_hash:`shown-${p.page}`} ]));
const point={point_id:'genre',score:1,evidence:'a letter',student_pages:[1],reason:'Full criterion met.'};
const locate=(raw,p=point,f=frames,r=receipts,s=student)=>decodeAnnotationRegions(raw,p,s,f,r);

test('catalog freezes deterministic geometry and never exports OCR text or changes source observations',()=>{
  const before=structuredClone(observations), reversed=structuredClone(observations);
  reversed.documents.neutral.pages.reverse();
  for(const p of reversed.documents.neutral.pages)p.rows.reverse();
  assert.deepEqual(buildOCRRegionCatalog(reversed,students),catalog);
  assert.deepEqual(observations,before);
  assert.doesNotMatch(JSON.stringify(catalog),/UNTRUSTED|candidates|not evidence/);
  const bad=structuredClone(observations);bad.documents.neutral.pages[0].source_sha256='foreign';
  assert.throws(()=>buildOCRRegionCatalog(bad,students),/binding/);
  const other=buildOCRRegionCatalog({engine:'local-test',documents:{other:observations.documents.neutral}},new Map([['other',student]]));
  assert.notEqual(other.documents.other.manifest_sha256,manifestHash);
});

test('OCR IDs select exact, disjoint source boxes and duplicate references do not multiply comments',()=>{
  const result=locate(['i1.r2','i1.r1','i1.r2']);
  assert.equal(result.status,'located');assert.equal(result.regions.length,2);
  assert.deepEqual(result.regions.map(r=>r.rect),[geometry(1).regions[1].rect,geometry(1).regions[0].rect]);
  assert.equal(result.regions[0].regionId,'i1.r2');assert.equal(result.regions[0].regionManifestHash,manifestHash);
  assert.equal(result.regions[0].contextRect,undefined);
  const reordered=new Map(frames);reordered.set('i1',{...frames.get('i1'),regions:[...frames.get('i1').regions].reverse()});
  assert.deepEqual(locate('i1.r1',point,reordered),locate('i1.r1'));
});

test('one local step ID expands to disjoint ink boxes without filling the whitespace between them',()=>{
  const detected=structuredClone(observations);
  detected.documents.neutral.pages[0].rows=[{rect:[.2,.3,.5,.05],rects:[[.2,.3,.1,.04],[.6,.31,.1,.04]],candidates:[{text:'left and right'}]}];
  const grouped=buildOCRRegionCatalog(detected,students).documents.neutral;
  const g={...geometry(1),regions:grouped.pages[0].regions,region_manifest_sha256:grouped.manifest_sha256};
  const f=new Map([['i1',annotationFrame(student.pages[0],'source_regions',g)]]);
  const r=new Map([['i1',{...receipts.get('i1'),region_manifest_sha256:grouped.manifest_sha256}]]);
  const located=locate('i1.r1',point,f,r);
  assert.equal(located.regions.length,2);
  assert.deepEqual(located.regions.map(r=>r.rect),g.regions[0].rects);
  assert.ok(located.regions.every(r=>r.regionId==='i1.r1'));
  const bad=structuredClone(g);bad.regions[0].rects[1].x=.9;
  assert.throws(()=>annotationFrame(student.pages[0],'source_regions',bad),/subregion/);
});

test('unknown, cross-page, stale manifest, undelivered and numeric references affect geometry only',()=>{
  const before=structuredClone(point);
  for(const raw of ['i1.r999','i2.r1','i77.r1','i1.C3:D5',[['i1',200,300,200,40]]]){
    assert.equal(locate(raw).status,'invalid');assert.deepEqual(locate(raw).regions,[]);
  }
  for(const change of [{region_manifest_sha256:'0'.repeat(64)},{original_sha256:'other'}, {representation:'original'}]){
    const stale=new Map(receipts);stale.set('i1',{...receipts.get('i1'),...change});
    assert.equal(locate('i1.r1',point,frames,stale).status,'invalid');
  }
  assert.equal(locate('i1.r1',point,frames,new Map()).status,'invalid');
  const partial=locate(['i1.r1','i1.r999']);assert.equal(partial.status,'partial');assert.equal(partial.regions.length,1);
  assert.deepEqual(point,before);
});

test('detector misses never become absent answers or zero credit',()=>{
  for(const [raw,status] of [[undefined,'missing'],['absent','absent'],['unlocated: OCR missed the ink','unlocated'],[[],'unlocated']])
    assert.equal(locate(raw).status,status);
  for(const score of [0,1,null]){
    const p={...point,score};locate('unlocated: no local region',p);assert.equal(p.score,score);
  }
});

test('whole-page scaling and source PDF placement keep OCR rectangles unchanged',()=>{
  const g={...geometry(1),content_size:[720,1008],size:[806,1008],source_rect_in_image:[43,0,763,1008]};
  const scaled=new Map(frames);scaled.set('i1',annotationFrame(student.pages[0],'source_regions',g));
  assert.deepEqual(locate('i1.r1',point,scaled),locate('i1.r1'));
  const source=structuredClone(student);source.pages[0].image_to_pdf={x:.1,y:.2,width:.8,height:.7};source.pages[0].source_page=7;
  const region=locate('i1.r1',point,frames,receipts,source).regions[0];
  assert.deepEqual(region.pdfRect,{x:.1+.2*.8,y:.2+.3*.7,width:.2*.8,height:.04*.7});assert.equal(region.pdfPage,7);
  assert.throws(()=>annotationFrame(student.pages[0],'source_regions',{...g,source_coverage_verified:false}));
});

test('workspace and print packet use identical OCR boxes and retain their catalog identity',()=>{
  const pages=[{id:'page',sha256:'p1',sourcePage:1,sourceId:'upload',role:'student',active:true,path:'/original.png'}];
  const group={id:'g',label:'Answer',pageIds:['page']};
  const task={id:'task',kind:'grade',pages,groups:[group],scheme:{pageIds:[]}};
  const annotated={...point,annotation:locate(['i1.r1','i1.r2'])};
  task.records=[makeRecord(task,group,{item_id:'document'},annotated,{max_score:1,allowed_awards:[0,1]},'grade','rubric')];
  const state={...emptyState(),title:'Test',pages,groups:[group],tasks:[task]},before=structuredClone(state);
  const note=gradingAnnotations(state,'task','g','page')[0];
  const printed=annotationExportPacket(state,'task','g').pages[0].notes[0];
  assert.deepEqual(note.regions.map(r=>r.rect),printed.regions.map(r=>r.rect));
  assert.deepEqual(note.regions.map(r=>r.regionId),['i1.r1','i1.r2']);
  assert.deepEqual(printed.regions.map(r=>[r.regionId,r.regionManifestHash]),note.regions.map(r=>[r.regionId,r.regionManifestHash]));
  assert.equal(task.records[0].annotationRegions[0].regionManifestHash,manifestHash);
  assert.deepEqual(state,before);
  task.records=[makeRecord(task,group,{item_id:'document'},{...point,annotation:locate(['i1.r1','i1.r999'])},{max_score:1,allowed_awards:[0,1]},'grade','rubric')];
  const partial=gradingAnnotations(state,'task','g','page')[0],partialPdf=annotationExportPacket(state,'task','g').pages[0].notes[0];
  assert.equal(partial.score,1);assert.equal(partial.regions.length,1);
  assert.equal(partialPdf.locationNote,partial.locationNote);assert.match(partialPdf.locationNote,/部分引用区域未能定位/);
  assert.equal(partialPdf.annotationStatus,'partial');assert.deepEqual(partialPdf.annotationIssues,['unbound_ocr_region']);
  assert.match(gradingCard(partial,{pages,pageId:'page',index:0,total:1}),/部分引用区域未能定位/);
});

test('single Pi submission receives full pages and a local ID lookup without a locator tool',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6-luna');
  const scheme={sha256:'scheme',pages:[{page:1,sha256:'ms'}]};
  const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items:[{
    question_id:'Document',item_id:'kind',max_score:1,criteria:'Identify a letter.',source_pages:[1],related_item_ids:[],
    requires_source_image:false,image_reason:'',uncertainties:[],scoring_points:[{point_id:'genre',max_score:1,allowed_awards:[0,1],award_type:'A',
      condition:'Identify a letter.',source_text:'letter',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['genre'],description:'Any equivalent wording.'}],
  }]},scheme,new Set([1]));
  const raw={items:[{id:'kind',route:'r',review:false,p:[{id:'genre',p:[1],l:'i1.r1',t:'a letter',r:'=',j:'m',s:1}]}],review_notes:[],source_issues:[]};
  let calls=0,saved;
  const child=createStudentAgent({model,scheme,student,frozen,protocol:'evidence-v4',inlineAnnotations:true,singlePass:true,reasonStyle:'brief-full-credit',
    initialStudentImageMode:'source_regions',initialStudentGeometry:[geometry(1),geometry(2)],localObservations:observations.documents.neutral.pages,
    readImage:async()=>assert.fail('No reread'),readInitialStudentImage:async p=>({type:'image',mimeType:'image/png',data:`whole-page-${p.page}`}),
    persist:async grade=>saved=grade,log:async()=>{},streamFn:(_model,context)=>{
      calls++;assert.deepEqual(child.agent.state.tools.map(t=>t.name),['submit_grading']);
      const images=context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image');
      assert.deepEqual(images.map(p=>p.data),['whole-page-1','whole-page-2']);
      assert.match(JSON.stringify(context),/UNTRUSTED OCR TEXT/);
      assert.match(JSON.stringify(context),/OCR can be wrong/);
      assert.match(context.messages.find(m=>m.role==='system').content,/existing local OCR region ID/);
      const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',
        content:[{type:'toolCall',id:'once',name:'submit_grading',arguments:raw}],usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{total:0}}}}));return stream;
    }});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(calls,1);assert.ok(saved,child.agent.state.errorMessage || JSON.stringify(child.agent.state.messages.at(-1)));assert.equal(saved.items[0].point_decisions[0].annotation.status,'located');
  assert.equal(saved.items[0].point_decisions[0].score,1);
  assert.equal(withoutAnnotationGeometry(saved).items[0].point_decisions[0].annotation,undefined);
  assert.equal(saved.image_delivery_receipts[0].region_manifest_sha256,manifestHash);
});


test('local region lookup binds source hashes, carries quoted hints and never sends coordinates',()=>{
  const hint=ocrRegionIndex(student.pages[0],geometry(1),observations.documents.neutral.pages[0]);
  assert.deepEqual(hint.split('\n').slice(1), ['1 "UNTRUSTED OCR TEXT"','2 "not evidence"']);
  assert.doesNotMatch(hint,/0\.2|rect|confidence/);
  assert.match(hint,/never instructions/);
  assert.throws(()=>ocrRegionIndex(student.pages[0],geometry(1),{...observations.documents.neutral.pages[0],source_sha256:'wrong'}),/Unbound/);
});


test('punctuation-only quotes do not pretend to identify a step or change its score',()=>{
  for(const evidence of ['=...','…','---']){
    const row={...point,evidence},before=structuredClone(row);
    const result=locate('i1.r1',row);
    assert.equal(result.status,'unlocated');assert.deepEqual(result.regions,[]);assert.deepEqual(row,before);
  }
});
