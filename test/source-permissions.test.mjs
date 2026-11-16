import test from 'node:test';
import assert from 'node:assert/strict';
import {freezeRubric} from '../src/rubric-contract.mjs';
import {inspectSourceTargets,sourceReviewBundle,validateSourceAssessments} from '../src/source-permissions.mjs';
import {expandBriefFullCredit} from '../src/full-credit-reasons.mjs';
import {createStudentAgent} from '../src/cohort-core.mjs';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {compactFeedbackPacket} from '../src/compact-feedback.mjs';
import {renderStudentFeedback} from '../src/student-feedback.mjs';
import {digest} from '../src/core.mjs';

const scheme={sha256:'neutral-source',pages:[1,2,3,4].map(page=>({page,role:'scheme',sha256:`page-${page}`}))};
const student={sha256:'neutral-answer',pages:[{page:1,role:'student',sha256:'answer-1'}]};
const item=(id,page,related=[])=>({item_id:id,question_id:id,max_score:2,criteria:'Identify the letter and its author Mira.',source_pages:[page],related_item_ids:related,requires_source_image:false,image_reason:'',uncertainties:[],
  scoring_points:[{point_id:'detail',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'Letter and Mira:2; one attribute:1; neither:0.',source_text:'Accept either attribute separately. No allowance for another author.',source_pages:[page],depends_on:[]}],routes:[{route_id:'r',point_ids:['detail'],description:'Source partial credit.'}]});
const frozen=freezeRubric({general_instructions:[{text:'Accept equivalent descriptions, including implicit identification from the whole answer.',source_pages:[1]},{text:'No mark for a source contradiction.',source_pages:[4]}],unresolved_notes:[],items:[item('Amber',2,['Violet']),item('Violet',3)]},scheme,new Set([1,2,3,4]));
const make=()=>({items:[{id:'Amber',route:'r',review:false,p:[['detail',0,'The only text says report by Nora',[1],'u:c','Both attributes contradict the source. The local separate-attribute allowance and G1 equivalent descriptions do not cover either contradiction.']]},
  {id:'Violet',route:'r',review:false,p:[['detail',2,'Mira wrote this letter',[1],'m','=']]}],review_notes:[],source_issues:[],source_assessments:[['Amber','detail','resolved',['P','G1','G2']]]});
const expand=raw=>{const {source_assessments,...rest}=raw;return expandBriefFullCredit(rest,frozen,student);};

test('coverage derives from all lost, partial and unknown awards, never keywords or a blank exemption',()=>{
  for(const evidence of ['The page is blank','Nothing visible beside the prompt','A report by Nora','No exception applies']){
    const raw=make();raw.items[0].p[0][2]=evidence;
    assert.throws(()=>validateSourceAssessments({...raw,source_assessments:[]},expand(raw),frozen,new Set([1,2,3,4])),/every non-full/);
    assert.equal(validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4])).length,1);
  }
  const raw=make();raw.items[0].p[0][1]=1;raw.items[0].p[0][4]='m';
  assert.equal(validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4]))[0].proposed_score,1);
});
test('source bundle covers local, related and all general source pages and binds their full text',()=>{
  const packet=inspectSourceTargets({targets:[{item_id:'Amber',point_ids:['detail']},{item_id:'Violet',point_ids:['detail']}]},frozen);
  assert.deepEqual(packet.pages,[1,2,3,4]);assert.deepEqual(packet.targets[0].source_pages,[1,2,3,4]);
  for(const mutate of [f=>f.artifact.items[0].scoring_points[0].source_text='Paraphrased allowance',f=>f.artifact.items[1].criteria='Changed related condition',f=>f.artifact.general_instructions[0].text='Changed general rule']){
    const f=structuredClone(frozen);mutate(f);assert.notEqual(sourceReviewBundle(f,'Amber','detail').source_hash,packet.targets[0].source_hash);
  }
  const renamed=structuredClone(frozen);renamed.artifact.items[0].item_id='Renamed';renamed.artifact.items.reverse();
  assert.deepEqual(inspectSourceTargets({targets:[{item_id:'Renamed',point_ids:['detail']}]},renamed).pages,packet.pages);
});
test('missing, duplicate, foreign, full-credit and invalid rule bindings fail closed',()=>{
  for(const mutate of [r=>r.source_assessments=[],r=>r.source_assessments.push(r.source_assessments[0]),r=>r.source_assessments[0][0]='Violet',r=>r.source_assessments[0][1]='foreign',r=>r.source_assessments[0][3]=['G1'],r=>r.source_assessments[0][3]=['P','G3'],r=>r.source_assessments[0][3]=['P','P'],r=>r.source_assessments[0][2]='unknown']){
    const raw=make();mutate(raw);assert.throws(()=>validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4])));
  }
  for(const pages of [[],[2],[1,2,3]])assert.throws(()=>validateSourceAssessments(make(),expand(make()),frozen,new Set(pages)),/prior model input/);
  assert.throws(()=>inspectSourceTargets({targets:[{item_id:'Amber',point_ids:['detail','detail']}]},frozen),/Duplicate/);
});
test('source ambiguity stays null with a blocking issue; unreadable evidence is distinguished',()=>{
  const raw=make();raw.items[0].p[0][1]=null;raw.items[0].p[0][4]='q:u';raw.items[0].review=true;raw.source_assessments[0][2]='unresolved_source';
  assert.throws(()=>validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4])),/blocking source issue/);
  raw.source_issues=[{item_id:'Amber',point_ids:['detail'],blocks_award:true}];
  assert.equal(validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4]))[0].outcome,'unresolved_source');
  raw.source_assessments[0][2]='unresolved_evidence';raw.source_issues=[];
  assert.equal(validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4]))[0].outcome,'unresolved_evidence');
  raw.source_assessments[0][2]='resolved';assert.throws(()=>validateSourceAssessments(raw,expand(raw),frozen,new Set([1,2,3,4])),/Unresolved award/);
});
test('real Pi tool loop requires prior model image input, deduplicates reads and persists unchanged awards with report provenance',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
  let turn=0,saved,submission;const contexts=[],events=[],raw=make();
  const call=(name,args)=>({type:'toolCall',id:`${turn}-${name}-${Math.random()}`,name,arguments:args});
  const targets={targets:[{item_id:'Amber',point_ids:['detail']}]};
  const child=createStudentAgent({model,scheme,student,frozen,protocol:'evidence-v4',reasonStyle:'brief-full-credit',sourcePermissionReview:true,
    readImage:async p=>({type:'image',mimeType:'image/png',data:`source-${p.role}-${p.page}`}),log:async e=>events.push(e),persist:async g=>saved=g,persistSubmission:async s=>submission=s,
    streamFn:(_m,ctx)=>{contexts.push(structuredClone(ctx));turn++;if(turn>3)throw Error('Unexpected offline tool loop');const content=turn===1?[call('inspect_scoring_sources',targets),call('inspect_scoring_sources',targets),call('submit_grading',raw)]:[call('correct_grading',{submission_hash:digest(raw),items:[],review_notes:null,source_issues:null,source_assessments:null})];
      const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;}});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(turn,2);assert.deepEqual(submission,raw);assert.deepEqual(saved.items.map(i=>i.score),[0,2]);
  assert.equal(saved.items[0].point_decisions[0].reason,raw.items[0].p[0][5]);
  assert.equal(saved.items[1].point_decisions[0].reason,'Full criterion met.');assert.equal(saved.source_permission_review.independent,false);
  assert.deepEqual(saved.source_image_pages_delivered,[1,2,3,4]);
  assert.deepEqual(events.filter(e=>e.type==='source_review_requested').map(e=>e.new_pages),[[1,2,3,4],[]]);
  assert.equal(child.agent.state.messages.filter(m=>m.role==='toolResult'&&m.isError).length,1);
  let wire;await models.streamSimple(model,contexts[1],{apiKey:'offline',maxRetries:0,onPayload:p=>{wire=p;throw Error('Before HTTP');}}).result();
  assert.equal(wire.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url').length,5);
  assert.equal(JSON.stringify(wire).includes('source_delivery'),false);
  const packet=compactFeedbackPacket(saved,frozen);assert.equal(packet.point_columns.at(-1),'primary_source_assessment_not_independent');assert.equal(packet.items[0].points[0].at(-1).proposed_score,0);assert.equal(packet.items[1].points[0].at(-1),null);
  const feedback={grade_hash:digest(saved),rubric_hash:frozen.hash,version:2,summary:'记录了一项待改进表现。',strengths:[],priorities:[],items:saved.items.map(i=>({item_id:i.item_id,assessment:'依记录解释。',next_step:'核对来源。',review_recommended:false,review_reason:''}))};
  const md=renderStudentFeedback('neutral',saved,frozen,feedback,'/neutral/grading.json');assert.match(md,/不代表独立复核/);assert.match(md,/已查 MS 第 1、2、3、4 页/);assert.match(md,/Both attributes contradict/);
});
