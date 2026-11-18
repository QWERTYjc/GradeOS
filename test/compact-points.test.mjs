import test from 'node:test';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {exceptionProbeFixture} from '../src/exception-probe-fixture.mjs';
import {expandCompactPoints,decodePointState,decodeCompactPageRefs} from '../src/compact-points.mjs';
import {createStudentAgent,freezeRubric} from '../src/cohort-core.mjs';
import {digest} from '../src/core.mjs';

const f=exceptionProbeFixture();
test('explicit page numbers and inclusive ranges decode without choosing evidence or scores',()=>{
  const student={pages:[1,2,3,4,5,6,7].map(page=>({page}))};
  for(const [raw,expected]of [[3,[3]],['3',[3]],['4-6',[4,5,6]],[' 1, 3-4, 7 ',[1,3,4,7]],['7, 2',[7,2]],[[2,4],[2,4]]])assert.deepEqual(decodeCompactPageRefs(raw,student),expected);
  for(const bad of ['',0,-1,8,2.5,'0','01','2.5','3 or 4','3/4','4-2','1,1','1-3,3','8','1-99999999','-1','page 3',null,{},'2;3'])assert.throws(()=>decodeCompactPageRefs(bad,student));
});
const code=p=>p.relation==='met'?'m':`${{unmet:'u',uncertain:'q',exception:'x'}[p.relation]}:${{none:'n',inherited:'i',current:'c',mixed:'m',unknown:'u'}[p.error_origin]}${p.relation==='exception'?':'+p.rule_ref:''}`;
const rawFrom=grade=>({items:grade.items.map(i=>({id:i.item_id,route:i.selected_route,review:i.review_required,
  p:i.point_decisions.map(p=>[p.point_id,p.score,p.evidence,p.student_pages,code(p),p.reason])})),review_notes:grade.review_notes,source_issues:[]});

test('six-cell codec preserves explicit decisions, evidence, reasons and page ownership across all states',()=>{
  const raw=rawFrom(f.primary),before=digest(raw),expanded=expandCompactPoints(raw,f.frozen,f.student);
  assert.equal(digest(raw),before);
  for(const item of f.primary.items)assert.deepEqual(expanded.items.find(i=>i.item_id===item.item_id),item);
  assert.deepEqual(decodePointState('q:c'),['uncertain','current','']);
  assert.deepEqual(decodePointState('x:m:G2'),['exception','mixed','G2']);
});
test('missing/reordered identity, invalid state, zero met, unknown without null and unsupported partial awards fail closed',()=>{
  for(const mutate of [r=>r.items.pop(),r=>r.items[0].p=[],r=>r.items[0].p[0].push('extra'),r=>r.items[0].p[0][4]='met',r=>r.items[0].p[0][4]='m',r=>r.items[0].p[0][4]='q:u',r=>r.items[0].p[0][0]='foreign',r=>r.items[0].p[0][1]=.5,r=>r.items[0].p[0][5]='']){
    const raw=rawFrom(f.primary);mutate(raw);assert.throws(()=>expandCompactPoints(raw,f.frozen,f.student));
  }
  for(const s of ['u','x:n:G1','x:i:missing','m:c','q:u:G1'])assert.throws(()=>decodePointState(s));
});
test('renamed equivalent evidence and source-authorized fractions retain full explicit judgments',()=>{
  const frozen=structuredClone(f.frozen),raw=rawFrom(f.primary);
  const source=frozen.artifact.items[0];source.scoring_points[0].allowed_awards=[0,.5,1];
  raw.items[0].p[0]=['credit',.5,'Source partially identified; required second element absent',[1],'m','The source explicitly permits this partial level.'];
  assert.equal(expandCompactPoints(raw,frozen,f.student).items[0].score,.5);
  const renamed=raw.items[1];renamed.p[0][2]='7+5+5+5+5=27';
  assert.equal(expandCompactPoints(raw,frozen,f.student).items[1].point_decisions[0].evidence,renamed.p[0][2]);
});

for(const [protocol,imageMode] of [['evidence-v4','exact_white_margin_trim'],['evidence-v5','exact_white_margin_trim'],['evidence-v4','resized_overview']])test(`${protocol}/${imageMode}: inline source issue cannot cite a just-requested image; later delivery permits one atomic submission`,async()=>{
  const scheme={sha256:'scheme',pages:[{page:1,role:'scheme',sha256:'scheme-page'}]},student={sha256:'student',pages:[{page:1,role:'student',sha256:'student-page'}]};
  const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items:[{item_id:'K',question_id:'K',max_score:1,criteria:'Interpret a source-dependent symbol.',source_pages:[1],related_item_ids:[],requires_source_image:true,image_reason:'Unresolved symbol',uncertainties:[],
    scoring_points:[{point_id:'p',max_score:1,allowed_awards:[0,1],award_type:'A',condition:'Identify the required symbol.',source_text:'Ambiguous source notation',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['p'],description:'One source-dependent mark.'}]}]},scheme,new Set([1]));
  const issue={item_id:'K',point_ids:['p'],scheme_pages:[1],observation:'Source symbol unresolved.',impact:'Cannot decide required symbol.',blocks_award:true};
  const raw={items:[{id:'K',route:'r',review:true,p:[['p',null,'Written mark is visible but source requirement unclear',[1],'q:u','Source ambiguity prevents an award.']]}],review_notes:[],source_issues:[issue]};
  if(protocol==='evidence-v5'){const row=raw.items[0],p=row.p[0];row.e=[['a',p[2],p[3]]];row.p=[[p[0],p[1],['a'],p[4],p[5]]];}
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');let turn=0,saved,rawSaved;const contexts=[];
  const call=(name,args)=>({type:'toolCall',id:`${turn}-${name}`,name,arguments:args});
  const child=createStudentAgent({model,scheme,student,frozen,protocol,log:async()=>{},readImage:async p=>({type:'image',mimeType:'image/png',data:`original-${p.role}`}),
    readInitialStudentImage:async()=>({type:'image',mimeType:'image/png',data:'exact-trim-student'}),initialStudentImageMode:imageMode,
    persist:async result=>{saved=result;},persistSubmission:async result=>{rawSaved=result;},streamFn:(_m,ctx)=>{
      contexts.push(structuredClone(ctx));const first=turn++===0;
      if(turn>3)throw Error('Unexpected offline tool loop');
      const content=first?[call('read_ms_pages',{pages:[1]}),call('submit_grading',raw)]:protocol==='evidence-v4'?[call('correct_grading',{submission_hash:digest(raw),items:[],review_notes:null,source_issues:null})]:[call('submit_grading',raw)];
      const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;
    }});
  const initial=await child.initialPrompt([]);
  if(imageMode==='resized_overview'){
    const text=JSON.stringify(initial);assert.match(text,/proportionally resized/);assert.match(text,/complete original page/);assert.doesNotMatch(text,/retained at its original resolution/);
    const original=await child.agent.state.tools.find(t=>t.name==='read_student_pages').execute('inspect',{pages:[1],question:'Unclear small symbol'});
    assert.equal(original.content.find(p=>p.type==='image').data,'original-student');
  }
  await child.agent.prompt(initial);
  assert.equal(turn,2);assert.deepEqual(rawSaved,raw);assert.equal(saved.total_score,null);assert.equal(saved.source_issues.length,1);
  assert.equal(child.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,1);
  assert.deepEqual(saved.source_image_pages_delivered,[1]);assert.deepEqual(saved.student_pages_delivered,[1]);
  assert.equal(saved.image_delivery_receipts.filter(r=>r.role==='student')[0].representation,imageMode);
  let wire;await models.streamSimple(model,contexts[1],{apiKey:'offline',maxRetries:0,onPayload:p=>{wire=p;throw Error('Before HTTP');}}).result();
  const images=wire.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url');
  assert.equal(images.length,2);assert.equal(JSON.stringify(wire).includes('source_delivery'),false);
  assert.equal(saved.point_decisions,undefined);
});


test('optional local inspection preserves original-page binding and rejects invalid or multiple-page crops',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());
  const student={...f.student,pages:f.student.pages.map(p=>({...p,sha256:`page-${p.page}`}))};
  const calls=[];const child=createStudentAgent({model:models.getModel('openrouter','openai/gpt-6.1-terra'),frozen:f.frozen,scheme:f.scheme,student,
    protocol:'evidence-v4',log:async()=>{},persist:async()=>{},readImage:async p=>({type:'image',data:`whole-${p.page}`,mimeType:'image/png'}),
    readStudentRegion:async(p,region)=>{calls.push({page:p.page,region});return {type:'image',data:'native-region',mimeType:'image/png'};}});
  const tool=child.agent.state.tools.find(t=>t.name==='read_student_pages');
  const page=student.pages[0].page;
  const result=await tool.execute('local',{pages:[page],question:'Distinguish the faint stroke at the selected location',region:[100,200,300,400]});
  const image=result.content.find(p=>p.type==='image');assert.equal(image.data,'native-region');
  assert.equal(image.source_delivery.original_sha256,`page-${page}`);assert.equal(image.source_delivery.representation,'source_region');
  assert.deepEqual(image.source_delivery.region,[100,200,300,400]);
  assert.match(result.content[0].text,/omitted content is not absent/);
  const full=await tool.execute('full',{pages:[page],question:'Inspect full-page layout context'});
  assert.equal(full.content.find(p=>p.type==='image').data,`whole-${page}`);
  for(const region of [[],[0,0,0,10],[-1,0,2,2],[900,0,101,20],[0,0,1.5,10]])
    await assert.rejects(tool.execute('bad',{pages:[page],question:'Read the ambiguous stroke',region}),/Region requires/);
  if(student.pages.length>1)await assert.rejects(tool.execute('many',{pages:student.pages.slice(0,2).map(p=>p.page),question:'Read the ambiguous stroke',region:[0,0,500,500]}),/Region requires/);
  assert.equal(calls.length,1);
});
