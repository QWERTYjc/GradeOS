import test from 'node:test';
import assert from 'node:assert/strict';
import {createModels,createAssistantMessageEventStream,getCurrentTools} from '@earendil-works/pi-ai';
import {openrouterProvider} from '@earendil-works/pi-ai/providers/openrouter';
import {createStudentAgent,StudentRegistry,freezeRubric} from '../src/cohort-core.mjs';
import {digest} from '../src/core.mjs';
import {validateSelfReviewRevisions,mergeSelfReviewCorrection} from '../src/submission-contract.mjs';

const models=createModels();models.setProvider(openrouterProvider());const model=models.getModel('openrouter','openai/gpt-6-luna');
const call=(name,args)=>({type:'toolCall',id:crypto.randomUUID(),name,arguments:structuredClone(args)});
function stream(next){let turns=0;return (_model,context,options)=>{
  if(++turns>10)throw Error('Unexpected self-review loop');
  const s=createAssistantMessageEventStream();
  Promise.resolve().then(()=>next(context,turns,options)).then(value=>{
    const result=Array.isArray(value)?{content:value,stopReason:'toolUse'}:value;
    s.push({type:'done',reason:result.stopReason,message:{role:'assistant',...result,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,
      usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}});
  }).catch(error=>s.push({type:'error',reason:'error',error:{role:'assistant',content:[],stopReason:'error',errorMessage:error.message,timestamp:Date.now(),api:model.api,provider:model.provider,model:model.id,usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}}}));
  return s;
};}
function fixture(ids=['A','B','C','D'],evidence='A letter by Mira.'){
  const scheme={sha256:'neutral-source',pages:[{page:1,role:'scheme'}]},student={sha256:digest(ids),pages:ids.map((_,i)=>({page:i+1,role:'student'}))};
  const frozen=freezeRubric({general_instructions:[{text:'Accept equivalent expressions. Illegible evidence is unknown.',source_pages:[1]}],unresolved_notes:[],items:ids.map(id=>({
    question_id:id,item_id:id,max_score:2,criteria:'Identify the document type and author.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
    scoring_points:[{point_id:'attributes',max_score:2,allowed_awards:[0,1,2],award_type:'credit',condition:'Letter by Mira:2; exactly one correct attribute:1; neither:0.',source_text:'Letter by Mira:2; exactly one correct attribute:1; neither:0.',source_pages:[1],depends_on:[]}],routes:[{route_id:'r',point_ids:['attributes'],description:'Source attributes'}],
  }))},scheme,new Set([1]));
  const raw={items:ids.map((id,i)=>({id,route:'r',review:false,p:[['attributes',2,evidence,[i+1],'m','=']]})),review_notes:[],source_issues:[]};
  return {scheme,student,frozen,raw};
}
function build(f,next){
  const primaries=[],finals=[],submissions=[],events=[];
  const child=createStudentAgent({model,...f,protocol:'evidence-v4',reasonStyle:'brief-full-credit',selfReview:true,
    readImage:async p=>({type:'text',text:`ORIGINAL ${p.role} page ${p.page}: own student ${f.student.sha256}`}),log:async e=>events.push(e),
    persistPrimary:async(g,r)=>primaries.push({grade:structuredClone(g),raw:structuredClone(r)}),persist:async g=>finals.push(g),persistSubmission:async r=>submissions.push(r),streamFn:stream(next)});
  return {child,primaries,finals,submissions,events};
}
const readingRevisions=(f,items)=>items.flatMap(item=>item.p.filter(p=>{
  const old=f.raw.items.find(i=>i.id===item.id)?.p.find(q=>q[0]===p[0]);
  return !old||old[2]!==p[2]||JSON.stringify(old[3])!==JSON.stringify(p[3]);
}).map(p=>({item_id:item.id,point_id:p[0],page:p[3][0],location:'Document heading and author line',observed:p[2],basis:'The visible original heading and author line support this reading; the saved observation is replaced.'})));
const review=(f,items=[])=>({items,review_notes:null,source_issues:null,checked_item_ids:f.raw.items.map(i=>i.id),summary:'Checked all source conditions and original observations; only local changes are included.',evidence_revisions:readingRevisions(f,items)});

test('same agent keeps original context, saves primary once, and emits only changed items after a separate response',async()=>{
  for(const [ids,evidence] of [[['A','B','C','D'],'Mira wrote this letter.'],[['甲','乙','丙','丁'],'作者Mira；文体信件。'],[['Section-Y','Part-X','Doc-Z','Note-Q'],'Letter\nAuthor: Mira']]){
    const f=fixture(ids,evidence);let firstContext,turnCount=0;const edits=structuredClone(f.raw.items.slice(1));
    edits[0].p[0]=['attributes',1,'Letter; no author named.',[2],'m','Only document type is established.'];
    edits[1].p[0]=['attributes',0,'Receipt by Kian.',[3],'u:c','Neither required attribute is correct.'];
    edits[2].review=true;edits[2].p[0]=['attributes',null,'[illegible required text]',[4],'q:u','Cannot establish either attribute.'];
    let built;built=build(f,(context,turn)=>{
      turnCount=turn;
      if(turn===1){firstContext=structuredClone(context);return[call('submit_grading',f.raw)];}
      assert.equal(turn,2);assert.equal(built.primaries.length,1);assert.equal(built.finals.length,0);assert.equal(built.child.getPhase(),'student_self_review');
      assert.deepEqual(context.messages.slice(0,firstContext.messages.length),firstContext.messages);
      assert.deepEqual(getCurrentTools(context.messages).map(t=>t.name),getCurrentTools(firstContext.messages).map(t=>t.name));
      const schema=getCurrentTools(context.messages).find(t=>t.name==='submit_self_review').parameters;
      assert.equal(schema.properties.submission_hash,undefined);
      assert.equal(schema.required.includes('submission_hash'),false);
      assert.match(JSON.stringify(context),/ORIGINAL student page 4/);
      return[call('submit_self_review',review(f,edits))];
    });
    await built.child.agent.prompt(await built.child.initialPrompt([]));
    assert.equal(turnCount,2,built.child.agent.state.errorMessage);assert.equal(built.finals.length,1);assert.equal(built.primaries[0].grade.total_score,8);
    const final=built.finals[0];assert.deepEqual(final.items.map(i=>i.score),[2,1,0,null]);assert.equal(final.total_score,null);
    assert.deepEqual(final.items[0],built.primaries[0].grade.items[0]);assert.deepEqual(built.primaries[0].raw,f.raw);
    assert.equal(final.self_review.mode,'same_student_agent');assert.equal(final.self_review.independent,false);assert.equal(final.self_review.changes.length,3);
    assert.equal(final.self_review.primary_grade_hash,digest(built.primaries[0].grade));assert.equal(built.submissions.length,1);
    assert.equal(final.self_review.draft_submission_hash,digest(f.raw));
  }
});
test('same-response attestation is rejected; a later no-change self-review preserves every ordinary full-credit point',async()=>{
  const f=fixture();let turns=0;const s=build(f,(context,turn)=>{
    turns=turn;if(turn===1)return[call('submit_grading',f.raw),call('submit_self_review',review(f))];
    assert.match(JSON.stringify(context),/subsequent model response/);return[call('submit_self_review',review(f))];
  });
  await s.child.agent.prompt(await s.child.initialPrompt([]));assert.equal(turns,2);assert.equal(s.primaries.length,1);assert.equal(s.finals.length,1);
  assert.deepEqual(s.finals[0].items,s.primaries[0].grade.items);assert.equal(s.finals[0].self_review.checked_point_count,4);
});
test('stale or incomplete review cannot finalize; a failed self-review keeps the primary, not a published score',async()=>{
  for(const mutate of [a=>a.checked_item_ids.pop(),a=>a.submission_hash='0'.repeat(64),a=>{a.items=[{...fixture().raw.items[0],id:'foreign'}];}]){
    const f=fixture();let seenError=false;const s=build(f,(context,turn)=>{
      if(turn===1)return[call('submit_grading',f.raw)];
      if(turn===2){const args=review(f);mutate(args);return[call('submit_self_review',args)];}
      seenError=context.messages.some(m=>m.role==='toolResult'&&m.isError);return{content:[],stopReason:'error',errorMessage:'Synthetic provider stop after rejected review'};
    });
    await s.child.agent.prompt(await s.child.initialPrompt([]));assert.ok(seenError);assert.equal(s.finals.length,0);assert.equal(s.child.getResult(),null);assert.equal(s.child.getPrimary().total_score,8);
  }
});
test('invalid semantic revisions leave the accepted primary intact and can be locally corrected',async()=>{
  const f=fixture();const patch=structuredClone(f.raw.items[0]);patch.p[0][1]=0;patch.p[0][4]='m';patch.p[0][5]='Neither attribute is correct.';
  const s=build(f,(context,turn)=>{
    if(turn===1)return[call('submit_grading',f.raw)];
    if(turn===2)return[call('submit_self_review',review(f,[patch]))];
    assert.equal(s.finals.length,0);assert.equal(s.child.getPrimary().total_score,8);assert.ok(context.messages.some(m=>m.role==='toolResult'&&m.isError));
    const corrected=structuredClone(patch);corrected.p[0][4]='u:c';return[call('submit_self_review',review(f,[corrected]))];
  });
  await s.child.agent.prompt(await s.child.initialPrompt([]));assert.equal(s.finals[0].total_score,6);assert.equal(s.primaries[0].grade.total_score,8);
});
test('existing initial correction is completed before self-review, and final review can retain unknown',async()=>{
  const f=fixture();f.raw.items[0].review=true;const valid=structuredClone(f.raw);valid.items[0].p[0]=['attributes',null,'Unreadable.',[1],'q:u','Required attributes are indeterminate.'];
  const s=build(f,(_context,turn)=>{
    if(turn===1)return[call('submit_grading',f.raw)];
    if(turn===2)return[call('correct_grading',{submission_hash:digest(f.raw),items:[valid.items[0]],review_notes:null,source_issues:null})];
    assert.equal(s.primaries.length,1);return[call('submit_self_review',review(f))];
  });
  await s.child.agent.prompt(await s.child.initialPrompt([]));assert.equal(s.finals.length,1,s.child.agent.state.errorMessage);assert.equal(s.finals[0].total_score,null);assert.equal(s.finals[0].items[0].review_required,true);
  assert.equal(s.finals[0].self_review.draft_submission_hash,digest(valid));
});
test('parallel student tasks enter self-review together without coordinator review calls', {timeout:4000},async()=>{
  const registry=new StudentRegistry(['student_a','student_b']);let entered=0,active=0,peak=0,release;
  const bothReviewing=new Promise(resolve=>release=resolve);
  await registry.dispatch(['student_a','student_b'],2,async id=>{
    const f=fixture([id+'1',id+'2',id+'3',id+'4']);const s=build(f,async(_context,turn)=>{
      if(turn===1)return[call('submit_grading',f.raw)];
      active++;entered++;peak=Math.max(peak,active);if(entered===2)release();await bothReviewing;active--;
      return[call('submit_self_review',review(f))];
    });
    await s.child.agent.prompt(await s.child.initialPrompt([]));assert.equal(s.finals.length,1);return{status:'submitted',total_score:s.finals[0].total_score};
  });
  assert.equal(peak,2);assert.equal(registry.terminal(),true);
});

test('changing a saved reading requires original-page grounds; rejection keeps the draft and original context',async()=>{
  const f=fixture(['Record-Z']);f.raw.items[0].p[0]=['attributes',0,'Receipt by Kian.',[1],'u:c','Neither required attribute is present.'];
  const patch={id:'Record-Z',route:'r',review:false,p:[['attributes',2,'Letter by Mira.',[1],'m','Both required attributes are visible in the heading.']]};
  let original;const s=build(f,(context,turn)=>{
    if(turn===1){original=structuredClone(context.messages);return[call('submit_grading',f.raw)];}
    if(turn===2)return[call('submit_self_review',{...review(f,[patch]),evidence_revisions:[]})];
    assert.equal(s.finals.length,0);assert.equal(s.child.getPrimary().total_score,0);
    assert.deepEqual(context.messages.slice(0,original.length),original);
    assert.match(JSON.stringify(context),/Changed readings need original-page/);
    return[call('submit_self_review',review(f,[patch]))];
  });
  await s.child.agent.prompt(await s.child.initialPrompt([]));
  assert.equal(s.finals.length,1,s.child.agent.state.errorMessage);
  const grounded=s.finals[0].self_review.evidence_revisions[0];
  assert.equal(grounded.before.evidence,'Receipt by Kian.');assert.equal(grounded.after.evidence,'Letter by Mira.');
  assert.equal(grounded.page,1);assert.equal(s.events.filter(e=>e.type==='read_pages').length,0);
});

test('score-only reinterpretation keeps literal evidence and needs a reason, not another image or rewritten observation',async()=>{
  const f=fixture(['Registro-T'],'Una carta escrita por Mira.');f.raw.items[0].p[0]=['attributes',0,'Una carta escrita por Mira.',[1],'u:c','The source was not recognized.'];
  const patch=structuredClone(f.raw.items[0]);patch.p[0][1]=2;patch.p[0][4]='m';patch.p[0][5]='=';
  const s=build(f,(context,turn)=>{
    if(turn===1)return[call('submit_grading',f.raw)];
    if(turn===2)return[call('submit_self_review',review(f,[patch]))];
    assert.match(JSON.stringify(context),/explicit short scoring reason/);
    patch.p[0][5]='The Spanish wording identifies both attributes; the rubric accepts equivalent expressions.';
    return[call('submit_self_review',review(f,[patch]))];
  });
  await s.child.agent.prompt(await s.child.initialPrompt([]));
  assert.equal(s.finals.length,1,s.child.agent.state.errorMessage);assert.equal(s.finals[0].total_score,2);
  assert.deepEqual(s.finals[0].self_review.evidence_revisions,[]);
  assert.equal(s.finals[0].items[0].point_decisions[0].evidence,f.raw.items[0].p[0][2]);
});

test('grounding rejects foreign, undelivered and duplicate citations but harmless unchanged-point grounds do not block submission',()=>{
  const f=fixture(['Document-Q']);const revised=structuredClone(f.raw);
  revised.items[0].p[0]=['attributes',1,'A letter; author field is empty.',[1],'m','Only the document type is established.'];
  const grounds=readingRevisions(f,revised.items);
  for(const mutate of [g=>g[0].page=2,g=>g[0].point_id='other',g=>g.push({...g[0]}),g=>g[0].observed=' ',g=>g[0].location=' ',g=>g[0].basis=' ']){
    const bad=structuredClone(grounds);mutate(bad);assert.throws(()=>validateSelfReviewRevisions(f.raw,revised,bad,new Set([1,2])));
  }
  assert.throws(()=>validateSelfReviewRevisions(f.raw,revised,grounds,new Set()),/delivered original/);
  assert.deepEqual(validateSelfReviewRevisions(f.raw,f.raw,grounds,new Set([1])),[]);
  const bound=validateSelfReviewRevisions(f.raw,revised,grounds,new Set([1]));
  assert.equal(bound.length,1);assert.equal(revised.items[0].p[0][1],1);
});

test('point patches inherit untouched evidence and do not mutate primary, reject unknown/duplicate points, and preserve complete route replacement',()=>{
  const f=fixture(['Part-Y']);f.raw.items[0].p.push(['seal',1,'A round seal.',[1],'m','=']);
  const patch=structuredClone(f.raw.items[0]);patch.p=[['attributes',0,'Receipt by Kian.',[1],'u:c','Neither attribute meets the source condition.']];
  const {checked_item_ids,summary,evidence_revisions,...fields}=review(f,[patch]);
  const correction={...fields,submission_hash:digest(f.raw)};
  const before=structuredClone(f.raw),merged=mergeSelfReviewCorrection(f.raw,correction,f.frozen);
  assert.deepEqual(f.raw,before);assert.deepEqual(merged.items[0].p[1],before.items[0].p[1]);
  assert.equal(merged.items[0].p[0][1],0);assert.equal(validateSelfReviewRevisions(before,merged,evidence_revisions,new Set([1])).length,1);
  const metadata=structuredClone(correction);metadata.items[0].p=[];metadata.items[0].review=true;
  assert.deepEqual(mergeSelfReviewCorrection(f.raw,metadata,f.frozen).items[0].p,before.items[0].p);
  for(const p of [[patch.p[0],patch.p[0]],[['foreign',0,'Different text.',[1],'u:c','Wrong item.']]]){
    const invalid=structuredClone(correction);invalid.items[0].p=p;assert.throws(()=>mergeSelfReviewCorrection(f.raw,invalid,f.frozen),/distinct points/);
  }
  const different=structuredClone(correction);different.items[0].route='alternate';different.items[0].p=[['new',1,'New route evidence.',[1],'m','=']];
  assert.deepEqual(mergeSelfReviewCorrection(f.raw,different,f.frozen).items[0].p,different.items[0].p);
});

test('one point can retain distinct page grounds while missing, foreign and repeated page grounds still fail',async()=>{
  for(const ids of [['Record-R','Control-S'],['资料乙','对照甲']]){
    const f=fixture(ids),patch=structuredClone(f.raw.items[0]);
    patch.p[0][2]='A letter on the opening page, signed by Mira on the next page.';
    patch.p[0][3]=[1,2];
    const args=review(f,[patch]);
    args.evidence_revisions=[1,2].map(page=>({...args.evidence_revisions[0],page,
      location:page===1?'Opening heading':'Closing signature',observed:page===1?'Letter':'Signed by Mira'}));
    const s=build(f,(_context,turn)=>[turn===1?call('submit_grading',f.raw):call('submit_self_review',args)]);
    await s.child.agent.prompt(await s.child.initialPrompt([]));
    assert.equal(s.finals.length,1,s.child.agent.state.errorMessage);
    assert.deepEqual(s.finals[0].self_review.evidence_revisions.map(r=>r.page),[1,2]);
    assert.deepEqual(s.finals[0].items[1],s.primaries[0].grade.items[1]);
    const merged=structuredClone(f.raw);merged.items[0]=patch;
    assert.equal(validateSelfReviewRevisions(f.raw,merged,[...args.evidence_revisions].reverse(),new Set([1,2])).length,2);
    assert.throws(()=>validateSelfReviewRevisions(f.raw,merged,[],new Set([1,2])),/Changed readings need/);
    assert.throws(()=>validateSelfReviewRevisions(f.raw,merged,args.evidence_revisions,new Set([1])),/delivered original/);
    assert.throws(()=>validateSelfReviewRevisions(f.raw,merged,[...args.evidence_revisions,args.evidence_revisions[0]],new Set([1,2])),/distinct original page/);
    assert.throws(()=>validateSelfReviewRevisions(f.raw,merged,[{...args.evidence_revisions[0],page:3}],new Set([1,2,3])),/delivered original/);
  }
});
