import test from 'node:test';
import assert from 'node:assert/strict';
import {freezeRubric} from '../src/rubric-contract.mjs';
import {compactPromptForReasons,expandBriefFullCredit,FULL_CREDIT_ATTESTATION} from '../src/full-credit-reasons.mjs';
import {COMPACT_POINTS_PROMPT,expandCompactPoints} from '../src/compact-points.mjs';
import {createStudentAgent} from '../src/cohort-core.mjs';
import {createModels,createAssistantMessageEventStream} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {digest,validateGrade} from '../src/core.mjs';
import {compactFeedbackPacket} from '../src/compact-feedback.mjs';
import {renderStudentFeedback} from '../src/student-feedback.mjs';

const scheme={sha256:'scheme',pages:[{page:1,role:'scheme'}]},student={sha256:'student',pages:[{page:1,role:'student'}]};
const frozen=freezeRubric({general_instructions:[{text:'Earlier mistaken input may carry only when explicitly permitted by the point.',source_pages:[1]}],unresolved_notes:[],items:[{item_id:'Blue',question_id:'Blue',max_score:2,criteria:'Identify a letter and its author Mira, one mark each.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
  scoring_points:[{point_id:'identify',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'Identify letter and Mira for2; only one for1.',source_text:'Identify letter and Mira for2; only one for1.',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['identify'],description:'Source-authorized partial credit.'}]}]},scheme,new Set([1]));
const make=()=>({items:[{id:'Blue',route:'r',review:false,p:[['identify',2,'Letter written by Mira',[1],'m','=']]}],review_notes:[],source_issues:[]});
test('ordinary full-credit attestation retains every source field and is an explicit reversible model claim',()=>{
  const raw=make(),hash=digest(raw),result=expandBriefFullCredit(raw,frozen,student),point=result.items[0].point_decisions[0];
  assert.equal(digest(raw),hash);assert.equal(point.score,2);assert.equal(point.evidence,raw.items[0].p[0][2]);assert.deepEqual(point.student_pages,[1]);
  assert.equal(point.reason,FULL_CREDIT_ATTESTATION);assert.equal(point.reason_encoding,'explicit_full_credit_attestation');
  assert.equal(compactPromptForReasons(),COMPACT_POINTS_PROMPT);
  assert.match(compactPromptForReasons('brief-full-credit'),/never change a score or review flag/);
});
test('an item review flag is preserved when an ordinary full point uses an explicit attestation',()=>{
  const raw=make();raw.items[0].review=true;
  const detailed=structuredClone(raw);detailed.items[0].p[0][5]=FULL_CREDIT_ATTESTATION;
  assert.throws(()=>expandBriefFullCredit(raw,frozen,student));
  const expanded=expandBriefFullCredit(raw,frozen,student,{allowReviewedItemAttestation:true}),expected=expandCompactPoints(detailed,frozen,student);
  const plain=structuredClone(expanded);delete plain.items[0].point_decisions[0].reason_encoding;
  assert.deepEqual(plain,expected);
  assert.equal(validateGrade(expanded,{documents:{scheme,student}},new Set(['scheme:1','student:1'])).status,'review_required');
});
test('partial, zero, null, exceptions and source disputes cannot use the full-credit shorthand',()=>{
  for(const change of [r=>r.items[0].p[0][1]=1,r=>{r.items[0].p[0][1]=0;r.items[0].p[0][4]='u:c';},
    r=>{r.items[0].p[0][1]=null;r.items[0].p[0][4]='q:u';r.items[0].review=true;},r=>r.items[0].p[0][4]='x:i:G1',
    r=>r.source_issues.push({item_id:'Blue'}),r=>r.items[0].p[0][0]='foreign',r=>r.items[0].p[0][2]='']){
    const raw=make();change(raw);assert.throws(()=>expandBriefFullCredit(raw,frozen,student));
  }
  for(const mutate of [f=>f.artifact.items[0].uncertainties.push('Unclear source.')]){
    const f=structuredClone(frozen);mutate(f);assert.throws(()=>expandBriefFullCredit(make(),f,student));
  }
});
test('detailed reasons for loss, uncertainty and exceptions pass through verbatim, including authorized partial credit',()=>{
  for(const [score,state,review,reason] of [[1,'m',false,'The type is letter but the author is missing; only one requirement is met.'],[0,'u:c',false,'Both source-required attributes contradict the observation.'],[null,'q:u',true,'The required name is obscured, so whether Mira is present cannot be established.'],[2,'x:i:G1',false,'Earlier input is wrong; supplied G1 applies only when the point authorizes it. Current reasoning requires source review.']]){
    const raw=make();raw.items[0].p[0][1]=score;raw.items[0].p[0][4]=state;raw.items[0].p[0][5]=reason;raw.items[0].review=review;
    assert.deepEqual(expandBriefFullCredit(raw,frozen,student),expandCompactPoints(raw,frozen,student));
  }
});
test('equivalent evidence and renamed identifiers retain complete observations without host scoring',()=>{
  for(const evidence of ['Mira wrote this letter','Letter\nAuthor Mira','作者Mira；文体信件']){
    const raw=make();raw.items[0].p[0][2]=evidence;
    assert.equal(expandBriefFullCredit(raw,frozen,student).items[0].point_decisions[0].evidence,evidence);
  }
  const f=structuredClone(frozen),r=make();f.artifact.items[0].item_id=r.items[0].id='Renamed';
  f.artifact.items[0].scoring_points[0].point_id=f.artifact.items[0].routes[0].point_ids[0]=r.items[0].p[0][0]='alternate';
  assert.equal(expandBriefFullCredit(r,f,student).items[0].score,2);
});
test('actual Pi submission saves raw shorthand and complete grade, feedback packet and report without another model call',async()=>{
  const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6.1-terra');let saved,submission,turns=0;
  const child=createStudentAgent({model,frozen,scheme,student,protocol:'evidence-v4',reasonStyle:'brief-full-credit',readImage:async()=>({type:'text',text:'Letter written by Mira'}),log:async()=>{},
    persist:async g=>saved=g,persistSubmission:async r=>submission=r,streamFn:()=>{turns++;const stream=createAssistantMessageEventStream();queueMicrotask(()=>stream.push({type:'done',reason:'toolUse',message:{role:'assistant',content:[{type:'toolCall',id:'submit',name:'submit_grading',arguments:make()}],timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,stopReason:'toolUse',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));return stream;}});
  await child.agent.prompt(await child.initialPrompt([]));assert.equal(turns,1);assert.deepEqual(submission,make());
  assert.equal(saved.items[0].point_decisions[0].reason,FULL_CREDIT_ATTESTATION);assert.equal(saved.reason_style,'brief-full-credit');
  const packet=compactFeedbackPacket(saved,frozen);assert.equal(packet.items[0].points[0][5],'Letter written by Mira');assert.equal(packet.items[0].points[0][6],FULL_CREDIT_ATTESTATION);
  const feedback={grade_hash:digest(saved),rubric_hash:frozen.hash,version:2,summary:'所列证据满足两项条件。',strengths:[],priorities:[],items:[{item_id:'Blue',assessment:'记录的文体与作者均正确。',next_step:'保持核对来源。',review_recommended:false,review_reason:''}]};
  const md=renderStudentFeedback('one',saved,frozen,feedback,'/neutral/grading.json');
  assert.match(md,/Letter written by Mira/);assert.match(md,/Identify letter and Mira/);assert.match(md,/Full criterion met/);
});

test('global notes remain review-visible without expanding unrelated full-credit explanations',()=>{
  const f=structuredClone(frozen);f.artifact.unresolved_notes=['A separate source convention needs review.'];
  const raw=make();raw.review_notes=['Keep the convention under review; the cited complete point is independently supported.'];
  const expanded=expandBriefFullCredit(raw,f,student);
  assert.equal(expanded.items[0].point_decisions[0].reason,FULL_CREDIT_ATTESTATION);
  assert.deepEqual(expanded.review_notes,raw.review_notes);
  const grade=validateGrade(expanded,{documents:{scheme,student}},new Set(['scheme:1','student:1']));
  assert.equal(grade.status,'review_required');
  raw.items[0].review=true;
  assert.throws(()=>expandBriefFullCredit(raw,f,student));
  const reviewed=expandBriefFullCredit(raw,f,student,{allowReviewedItemAttestation:true});
  assert.equal(reviewed.items[0].review_required,true);
  assert.equal(reviewed.items[0].point_decisions[0].reason,FULL_CREDIT_ATTESTATION);
  assert.equal(validateGrade(reviewed,{documents:{scheme,student}},new Set(['scheme:1','student:1'])).status,'review_required');
});
