import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {createReportContext,createSourceInspection,rubricOverview} from '../src/report-context.mjs';
import {createReporting} from '../src/cohort-reporting.mjs';
import {freezeRubric} from '../src/rubric-contract.mjs';
import {ResultsStore} from '../src/results-store.mjs';
import {freezeJson} from '../src/cohort-runtime.mjs';
import {digest} from '../src/core.mjs';

const scheme={sha256:'neutral-book',pages:[1,2,3,4,5,6].map(page=>({page}))};
const frozen=freezeRubric({general_instructions:[{text:'Follow the supplied conditions.',source_pages:[2]}],unresolved_notes:[],items:[
  {item_id:'alpha',question_id:'Problem-X',max_score:2,criteria:'Unabridged criterion with equivalent methods.',source_pages:[1,3],requires_source_image:false,image_reason:'',uncertainties:[],related_item_ids:['beta']},
  {item_id:'beta',question_id:'Problem-Y',max_score:1,criteria:'Independent relation.',source_pages:[4],requires_source_image:false,image_reason:'',uncertainties:[],related_item_ids:[]},
]},scheme,new Set([1,2,3,4,5,6]));
const consume=(views,results)=>{views.transform(results.map(r=>({role:'toolResult',...r})));views.confirmDelivery();};
test('source navigation is not the full rubric; scoped views allow own/related/general pages and reject unrelated/full-book requests',async()=>{
  const views=createReportContext();const inspected=[];
  const tool=createSourceInspection({getRubric:()=>frozen,scheme,views,readImage:async page=>{inspected.push(page.page);return{type:'image',mimeType:'image/png',data:`page-${page.page}`};},log:async()=>{}});
  assert.equal(JSON.stringify(rubricOverview(frozen)).includes('Unabridged criterion'),false);
  for (const args of [{item_ids:['missing'],pages:[1]},{item_ids:['alpha'],pages:[5]},{item_ids:['alpha'],pages:[1,2,3,4,5]}])
    await assert.rejects(tool.execute('bad',{...args,question:'Clarify the source condition.'}));
  assert.equal(inspected.length,0);
  const result=await tool.execute('source',{item_ids:['alpha'],pages:[1,2,3,4],question:'Clarify the permitted related method and source convention.'});
  assert.deepEqual(inspected,[1,2,3,4]);assert.equal(result.content.filter(x=>x.type==='image').length,4);
  assert.throws(()=>views.checkpoint({path:'notes',hash:'hash'}),/subsequent/);
  consume(views,[result]);views.checkpoint({path:'notes',hash:'hash'});
  const before=JSON.stringify(result);const compact=views.transform([{role:'toolResult',...result}]);
  assert.equal(compact[0].content.some(x=>x.type==='image'),false);
  assert.equal(JSON.stringify(result),before);
  const repeated=await tool.execute('reread',{item_ids:['alpha'],pages:[1],question:'Recheck the original equation after comparing saved point evidence.'});
  assert.equal(repeated.content.filter(x=>x.type==='image').length,1);
});
test('checkpoint requires a delivered view, limits active memory, and never mutates raw evidence',()=>{
  const views=createReportContext();const view=views.add('points',[{type:'text',text:'literal evidence'}],{path:'immutable-grade'});
  assert.throws(()=>views.checkpoint({hash:'not-delivered'}),/subsequent/);
  views.transform([{role:'toolResult',...view}]);
  assert.throws(()=>views.checkpoint({hash:'not-yet-answered'}),/subsequent/);
  views.confirmDelivery();views.checkpoint({hash:'notes'});
  assert.equal(view.content[0].text,'literal evidence');
  assert.throws(()=>views.add('points',[{type:'text',text:'x'.repeat(150001)}],{}),/request fewer/i);
});
test('repeated immutable analytics collapse only after the later copy has reached a model response',()=>{
  const views=createReportContext();const content=[{type:'text',text:'Full authoritative aggregate with all issue counts'}];
  const first=views.add('analysis',content,{counts:'unchanged'});consume(views,[first]);views.checkpoint({hash:'notes-one'});
  const second=views.add('analysis',content,{counts:'unchanged'});
  const messages=[first,second].map(r=>({role:'toolResult',...r}));
  const before=views.transform(messages);
  assert.equal(before[1].content[0].text,content[0].text);
  assert.equal(before[0].content[0].text.includes('same_content_as'),false);
  views.confirmDelivery();const after=views.transform(messages);
  assert.equal(JSON.parse(after[0].content[0].text).same_content_as,second.details.context_view_id);
  assert.equal(after[1].content[0].text,content[0].text);
});
test('batch notes preserve nulls, failed students, review conflicts and source hashes while full point evidence remains retrievable',async()=>{
  const dir=await mkdtemp(resolve(tmpdir(),'pi-report-memory-'));
  try {
    const grade={rubric_hash:frozen.hash,total_score:null,max_score:3,status:'review_required',review_notes:['Unresolved symbol'],source_issues:[{item_id:'alpha',observation:'Source conflict',blocks_award:true}],
      items:[{item_id:'alpha',question_id:'Problem-X',score:null,max_score:2,review_required:true,reason:'Cannot resolve the required symbol.',student_pages:[1],scheme_pages:[1],point_decisions:[{point_id:'own',score:null,evidence:'a[unreadable]',reason:'Indeterminate',student_pages:[1]}]},
        {item_id:'beta',question_id:'Problem-Y',score:1,max_score:1,review_required:false,reason:'Independent valid condition.',student_pages:[2],scheme_pages:[4]}]};
    await freezeJson(dir,'grade.json',grade);const hash=digest(await readFile(resolve(dir,'grade.json')));
    const store=new ResultsStore(resolve(dir,'results'),['pupil-a','pupil-b']);await store.init();
    await store.publish('pupil-a',{status:'submitted',rubric_hash:frozen.hash,grading_path:resolve(dir,'grade.json'),grading_sha256:hash,feedback_status:'failed',feedback_failure:'Unfinished feedback'});
    await store.publish('pupil-b',{status:'failed',rubric_hash:frozen.hash,failure:'Transport failed'});
    await store.seal([{student_id:'pupil-a',status:'submitted'},{student_id:'pupil-b',status:'failed'}],frozen.hash);
    const reporting=createReporting({store,ensureSealed:async()=>store.sealed,getRubric:()=>frozen,context:{},output:dir,log:async()=>{}});
    const tools=Object.fromEntries(reporting.tools.map(t=>[t.name,t]));
    const read=await tools.read_cohort_results.execute('read',{student_ids:['pupil-a','pupil-b']});
    const notes={student_ids:['pupil-a','pupil-b'],observations:['One unresolved symbol; another student has no numerical result.'],evidence_refs:['pupil-a/alpha']};
    await assert.rejects(tools.save_report_notes.execute('premature',notes),/subsequent/);
    await assert.rejects(tools.read_point_evidence.execute('premature',{evidence_refs:['pupil-a/alpha']}),/Read valid/);
    await assert.rejects(tools.read_cohort_results.execute('another',{student_ids:['pupil-a']}),/save_report_notes/);
    reporting.transformContext([{role:'toolResult',...read}]);reporting.onModelResponse();
    await assert.rejects(tools.save_report_notes.execute('foreign',{...notes,evidence_refs:['pupil-b/alpha']}),/bind/);
    await tools.save_report_notes.execute('save',notes);
    const compact=reporting.transformContext([{role:'toolResult',...read}]);const records=JSON.parse(compact[0].content[0].text).retained.records;
    assert.equal(records[0].result.total_score,null);assert.deepEqual(records[0].result.items[0],['alpha',null,2,true]);
    assert.deepEqual(records[0].result.source_issues,grade.source_issues);assert.equal(records[0].grading_sha256,hash);
    assert.equal(records[0].feedback_status,'failed');assert.equal(records[1].result,null);assert.equal(records[1].failure,'Transport failed');
    const points=await tools.read_point_evidence.execute('retrieve',{evidence_refs:['pupil-a/alpha']});
    assert.equal(JSON.parse(points.content[0].text).items[0].grading.point_decisions[0].evidence,'a[unreadable]');
    assert.equal(digest(await readFile(resolve(dir,'grade.json'))),hash);
  } finally {await rm(dir,{recursive:true,force:true});}
});
