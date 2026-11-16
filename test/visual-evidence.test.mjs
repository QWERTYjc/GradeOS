import test from 'node:test';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {createStudentAgent,freezeRubric} from '../src/cohort-core.mjs';
import {VISUAL_EVIDENCE_PROMPT} from '../src/point-evidence.mjs';
import {digest} from '../src/core.mjs';

const models=createModels();models.setProvider(openrouterProvider());
const model=models.getModel('openrouter','openai/gpt-6-luna');
const call=(name,args)=>[{type:'toolCall',id:crypto.randomUUID(),name,arguments:args}];
function fixture(ids=['Record','Title']){
  const scheme={sha256:'neutral-scheme',pages:[{page:1,role:'scheme'}]};
  const student={sha256:'neutral-student',pages:[1,2].map(page=>({page,role:'student'}))};
  const items=ids.map((id,index)=>({item_id:id,question_id:id,max_score:1,criteria:index?'Copy the title.':'Read the catalogue number.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
    scoring_points:[{point_id:'entry',max_score:1,allowed_awards:[0,1],award_type:'credit',condition:index?'The literal title is Unclear.':'The catalogue number is 47.',source_text:index?'Title: Unclear.':'Catalogue number: 47.',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['entry'],description:'Read the entry.'}]}));
  const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items},scheme,new Set([1]));
  const raw={items:ids.map((id,index)=>({id,route:'r',review:false,p:[['entry',1,index?'Unclear':'47',[index?1:2],'m','=']]})),review_notes:[],source_issues:[]};
  return {scheme,student,frozen,raw};
}
function agentFor(f,next,extra={}){
  let turns=0;const originalReads=[];
  const ctl=createStudentAgent({model,...f,protocol:'evidence-v4',reasonStyle:'brief-full-credit',log:async()=>{},persist:async()=>{},
    readInitialStudentImage:async p=>({type:'image',mimeType:'image/png',data:Buffer.from(`initial-${p.page}`).toString('base64')}),
    readImage:async p=>{originalReads.push(p.page);return {type:'image',mimeType:'image/png',data:Buffer.from(`original-${p.page}`).toString('base64')};},
    streamFn:(_model,context)=>{
      assert.ok(++turns<=4,'Unexpected model loop');
      const content=next(context,turns),stream=createAssistantMessageEventStream();
      queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{total:0}}}}));return stream;
    },...extra});
  return {...ctl,originalReads};
}
// Scripted turns verify the harness contract and actual context delivery. Real
// prompt behavior is measured separately with a paid neutral-image probe and M2.
test('targeted reinspection delivers only the requested original page before a supported submission',async()=>{
  for(const [ids,evidence] of [[['Record','Title'],'47'],[['记录','标题'],'四十七'],[['Renamed-Z','Adjacent'],'catalogue: forty-seven']]){
    const f=fixture(ids);f.raw.items[0].p[0][2]=evidence;let saved;
    const ctl=agentFor(f,(context,turn)=>{
      const text=JSON.stringify(context);assert.ok(text.includes(JSON.stringify(VISUAL_EVIDENCE_PROMPT).slice(1,-1)));
      if(turn===1)return call('read_student_pages',{pages:[2],question:'Distinguish the final character in the catalogue entry.'});
      const parts=context.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]);
      assert.ok(parts.some(p=>p.type==='image'&&p.data===Buffer.from('original-2').toString('base64')));
      return call('submit_grading',f.raw);
    },{persist:async g=>saved=g});
    await ctl.agent.prompt(await ctl.initialPrompt([]));
    assert.ok(saved,ctl.agent.state.errorMessage);
    assert.deepEqual(ctl.originalReads,[2]);assert.equal(saved.total_score,2);
    assert.equal(saved.items[0].point_decisions[0].evidence,evidence);assert.equal(saved.items[1].point_decisions[0].evidence,'Unclear');
    assert.ok(saved.image_delivery_receipts.some(r=>r.page===2&&r.representation==='original'));
  }
});
test('unresolved visual evidence stays null and cannot become zero through local correction',async()=>{
  const f=fixture(),raw=structuredClone(f.raw);raw.items[0].review=true;raw.items[0].p[0]=['entry',0,'The last character could be 1 or 7.',[2],'q:u','The page cannot determine the catalogue number.'];
  let saved,submitted;
  const ctl=agentFor(f,(context,turn)=>{
    if(turn===1)return call('read_student_pages',{pages:[2],question:'Can the obscured catalogue suffix be determined from the original?'});
    if(turn===2)return call('submit_grading',raw);
    assert.match(JSON.stringify(context),/requires null/);
    assert.ok(JSON.stringify(context).includes(JSON.stringify(VISUAL_EVIDENCE_PROMPT).slice(1,-1)));
    const item=structuredClone(raw.items[0]);item.p[0][1]=null;
    return call('correct_grading',{submission_hash:digest(raw),items:[item],review_notes:null,source_issues:null});
  },{persist:async g=>saved=g,persistSubmission:async r=>submitted=r});
  await ctl.agent.prompt(await ctl.initialPrompt([]));
  assert.ok(saved,ctl.agent.state.errorMessage);
  assert.equal(saved.total_score,null);assert.equal(saved.items[0].review_required,true);
  assert.equal(saved.items[0].point_decisions[0].relation,'uncertain');assert.deepEqual(submitted.items[1],raw.items[1]);
  assert.deepEqual(ctl.originalReads,[2]);
});
test('clear meaning-changing controls retain their explicit zero without compulsory rereads',async()=>{
  for(const value of ['41','74']){
    const f=fixture();f.raw.items[0].p[0]=['entry',0,value,[2],'u:c','The clearly readable entry differs from the required catalogue number.'];let saved;
    const ctl=agentFor(f,()=>call('submit_grading',f.raw),{persist:async g=>saved=g});
    await ctl.agent.prompt(await ctl.initialPrompt([]));assert.equal(saved.total_score,1);assert.deepEqual(ctl.originalReads,[]);
    assert.equal(saved.items[0].score,0);assert.equal(saved.items[1].score,1);
  }
});
