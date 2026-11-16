import test from 'node:test';
import assert from 'node:assert/strict';
import { createModels, createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { freezeRubric } from '../src/rubric-contract.mjs';
import { expandPointEvidence } from '../src/point-evidence.mjs';
import { createStudentAgent } from '../src/cohort-core.mjs';
import { digest } from '../src/core.mjs';

const scheme={sha256:'neutral-source',pages:[{page:1},{page:2}]};
const student={pages:Array.from({length:11},(_,index)=>({page:index+1}))};
function rubric(id='Linear-K') {
  return freezeRubric({general_instructions:[{text:'Correct application to an inherited erroneous input may receive method credit. A new wrong operation is not exempt.',source_pages:[2]}],unresolved_notes:[],
    items:[{question_id:'Task-K',item_id:id,max_score:1,criteria:'Apply the specified affine operation correctly.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
      scoring_points:[{point_id:'operation',max_score:1,allowed_awards:[0,1],award_type:'M',condition:'Correct application of four times the input plus seven.',source_text:'4t+7',source_pages:[1],depends_on:[]}],
      routes:[{route_id:'normal',point_ids:['operation'],description:'Equivalent valid expressions accepted.'}]}]},scheme,new Set([1,2]));
}
const submission=(id='Linear-K')=>({items:[{id,route:'normal',review:false,p:[['operation',1,'4×3+7=19',[1],'met','none','','Correct application.']]}],review_notes:[]});

test('compact submission preserves point evidence and judgment while deriving only fixed identity and arithmetic',()=>{
  const raw=submission();const before=digest(raw);const result=expandPointEvidence(raw,rubric(),student);
  assert.equal(digest(raw),before);assert.equal(result.items[0].score,1);assert.equal(result.items[0].max_score,1);
  assert.equal(result.items[0].question_id,'Task-K');assert.equal(result.items[0].point_decisions[0].evidence,raw.items[0].p[0][2]);
  assert.equal(result.items[0].point_decisions[0].reason,raw.items[0].p[0][7]);
  assert.deepEqual(result.items[0].scheme_pages,[1]);assert.deepEqual(result.items[0].student_pages,[1]);
});
test('equivalent notation, language and neutral identity changes preserve the binding without textual matching',()=>{
  for (const [id,evidence] of [['Renamed','7+4(3)=19'],['另题','四倍3加7等于19'],['Order-Z','t=3; 4t=12; then +7 gives19']]) {
    const raw=submission(id);raw.items[0].p[0][2]=evidence;
    assert.equal(expandPointEvidence(raw,rubric(id),student).items[0].score,1);
  }
});
test('known unmet conditions, current errors called met, unknown rules and malformed tuples cannot grant credit',()=>{
  for (const mutate of [p=>p[4]='unmet',p=>p[5]='current',p=>{p[4]='exception';p[5]='inherited';p[6]='G99';},p=>p.pop(),p=>p[3]=[99]]) {
    const raw=submission();mutate(raw.items[0].p[0]);assert.throws(()=>expandPointEvidence(raw,rubric(),student));
  }
});
test('valid inherited exceptions retain source citations; new-error exceptions require explicit review',()=>{
  const raw=submission();const p=raw.items[0].p[0];
  p[2]='Using own earlier t=5: 4×5+7=27';p[4]='exception';p[5]='inherited';p[6]='G1';p[7]='G1 permits the inherited value; the current affine operation is correct.';
  assert.deepEqual(expandPointEvidence(raw,rubric(),student).items[0].scheme_pages,[1,2]);
  p[5]='mixed';assert.throws(()=>expandPointEvidence(raw,rubric(),student),/requires review/);
  raw.items[0].review=true;assert.equal(expandPointEvidence(raw,rubric(),student).items[0].review_required,true);
});
test('uncertain observations stay null and unrelated criteria are never changed by another point conflict',()=>{
  const frozen=rubric();const other=structuredClone(frozen.artifact.items[0]);other.item_id='Genre-L';other.question_id='Language';
  other.scoring_points[0].condition='Identify the document as a letter.';other.scoring_points[0].source_text='letter';frozen.artifact.items.push(other);
  const raw=submission();raw.items.push({...structuredClone(raw.items[0]),id:'Genre-L'});
  raw.items[0].review=true;raw.items[0].p[0]=['operation',null,'4×3+7=1[illegible]',[1],'uncertain','unknown','','Final value cannot be read.'];
  raw.items[1].p[0][2]='letter';const result=expandPointEvidence(raw,frozen,student);
  assert.equal(result.items[0].score,null);assert.equal(result.items[1].score,1);
  raw.items[0].p[0][1]=0;assert.throws(()=>expandPointEvidence(raw,frozen,student),/requires null/);
});
test('actual Pi compact path receives the complete book before its first model call and preserves the raw submission',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');
  let saved,rawSaved,context;let calls=0;const raw=submission();
  const child=createStudentAgent({model,scheme,student,frozen:rubric(),protocol:'evidence-v3',log:async()=>{},
    readImage:async page=>({type:'image',mimeType:'image/png',data:`student-${page.page}`}),persist:async value=>saved=value,persistSubmission:async value=>rawSaved=value,
    streamFn:(_model,ctx)=>{calls++;context=structuredClone(ctx);const stream=createAssistantMessageEventStream();
      queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',
        content:[{type:'toolCall',id:'submit',name:'submit_grading',arguments:raw}],usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;}});
  await child.agent.prompt(await child.initialPrompt([]));
  assert.equal(calls,1);assert.deepEqual(saved.student_pages_delivered,student.pages.map(p=>p.page));assert.deepEqual(rawSaved,raw);assert.equal(saved.submission_hash,digest(raw));
  const content=context.messages.find(m=>m.role==='user').content;assert.equal(content.filter(p=>p.type==='image').length,11);
  let payload;await models.streamSimple(model,context,{apiKey:'local-test-only',maxRetries:0,onPayload:p=>{payload=p;throw Error('Stop before HTTP');}}).result();
  assert.equal(payload.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(p=>p.type==='image_url').length,11);
});
