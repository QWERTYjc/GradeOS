import test from 'node:test';
import assert from 'node:assert/strict';
import {freezeRubric} from '../src/rubric-contract.mjs';
import {expandSharedEvidence,evidenceWithSourcePages} from '../src/shared-evidence.mjs';
import {compactFeedbackPacket} from '../src/compact-feedback.mjs';
import {digest} from '../src/core.mjs';

const scheme={sha256:'source',pages:[{page:1}]},student={sha256:'answer',pages:[1,2,3].map(page=>({page}))};
const frozen=freezeRubric({general_instructions:[],unresolved_notes:[],items:['Alpha','Beta','Gamma'].map(id=>({
  item_id:id,question_id:id,max_score:2,criteria:'Identify a letter by Mira. Judge the two attributes independently.',source_pages:[1],related_item_ids:[],requires_source_image:false,image_reason:'',uncertainties:[],
  scoring_points:['type','author'].map((id,i)=>({point_id:id,max_score:1,allowed_awards:[0,1],award_type:'A',condition:i?'Author Mira':'Type letter',source_text:i?'Author Mira':'Type letter',source_pages:[1],depends_on:[]})),
  routes:[{route_id:'r',point_ids:['type','author'],description:'Two independent identifications.'}],
}))},scheme,new Set([1]));
const make=()=>({items:[
  {id:'Alpha',route:'r',review:false,e:[['a','Letter by Mira',[1]]],p:[['type',1,['a'],'m','Correct document type.'],['author',1,['a'],'m','Correct author.']]},
  {id:'Beta',route:'r',review:false,e:[['a','Letter by Nora',[2]]],p:[['type',1,['a'],'m','Type matches.'],['author',0,['a'],'u:c','The writer is not the source author.']]},
  {id:'Gamma',route:'r',review:true,e:[['x','Letter',[3]],['y','Author [unreadable]',[3]]],p:[['type',1,['x'],'m','Type is legible.'],['author',null,['x','y'],'q:u','The author cannot be established.']]},
],review_notes:[],source_issues:[]});

test('shared observations expand without changing awards, reasons, ownership or nulls; downstream retains full evidence',()=>{
  const raw=make(),hash=digest(raw),result=expandSharedEvidence(raw,frozen,student);
  assert.equal(hash,digest(raw));assert.deepEqual(result.items.map(i=>i.score),[2,1,null]);
  assert.equal(result.items[0].point_decisions[0].evidence,'Letter by Mira');
  assert.equal(result.items[1].point_decisions[1].score,0);
  assert.equal(result.items[1].point_decisions[0].evidence,'Letter by Nora');
  const unknown=result.items[2].point_decisions[1];assert.equal(unknown.evidence,'Letter\nAuthor [unreadable]');
  assert.deepEqual(unknown.evidence_refs,['x','y']);assert.deepEqual(unknown.student_pages,[3]);
  const packet=compactFeedbackPacket({...result,rubric_hash:frozen.hash},frozen);
  assert.equal(packet.items[2].points[1][5],'[x; 答卷页 3] Letter\n[y; 答卷页 3] Author [unreadable]');
  assert.equal(packet.items[2].points[1][6],unknown.reason);
});
test('missing, duplicate, foreign, unused and out-of-page evidence fail closed without repairing references',()=>{
  const mutations=[r=>r.items[0].p[0][2]=[],r=>r.items[0].p[0][2]=['a','a'],r=>r.items[0].p[0][2]=['x'],
    r=>r.items[0].e.push(['a','Changed answer',[1]]),r=>r.items[0].e.push(['b','Letter by Mira',[1]]),
    r=>r.items[0].e.push(['b','Unused observation',[1]]),r=>r.items[0].e[0][2]=[99],
    r=>r.items[0].e[0][1]=' ',r=>r.items[0].p[0][4]='',r=>r.items[0].p[0].push('extra'),
    r=>r.items[0].p[0][1]=0,r=>r.items[2].p[1][1]=1,r=>r.items[2].review=false,r=>r.items[0].p.pop()];
  for(const mutate of mutations){const raw=make();mutate(raw);assert.throws(()=>expandSharedEvidence(raw,frozen,student));}
});
test('ID renaming, bank order and equivalent wording do not change decisions; separate page identities are not deduplicated',()=>{
  for(const literal of ['Letter by Mira','Mira wrote the letter','作者Mira；文体为信件']){
    const raw=make();raw.items[0].e[0]=['renamed',literal,[1]];
    raw.items[0].p.forEach(p=>p[2]=['renamed']);raw.items[2].e.reverse();
    const grade=expandSharedEvidence(raw,frozen,student);
    assert.deepEqual(grade.items.map(i=>i.score),[2,1,null]);
    assert.equal(grade.items[0].point_decisions[1].evidence,literal);
  }
  const raw=make();raw.items[0].e.push(['b','Letter by Mira',[2]]);raw.items[0].p[1][2]=['b'];
  const grade=expandSharedEvidence(raw,frozen,student);assert.deepEqual(grade.items[0].point_decisions.map(p=>p.student_pages),[[1],[2]]);
});
test('multi-page references preserve every literal observation and its binding independently of flattened page union',()=>{
  const raw=make();raw.items[0].e.push(['b','Continued: author Mira',[2]]);raw.items[0].p[1][2]=['a','b'];
  const grade=expandSharedEvidence(raw,frozen,student),item=grade.items[0];
  assert.deepEqual(item.point_decisions[1].student_pages,[1,2]);
  assert.deepEqual(item.evidence_bank.map(e=>e.student_pages),[[1],[2]]);
  assert.equal(item.point_decisions[1].evidence,'Letter by Mira\nContinued: author Mira');
  assert.equal(evidenceWithSourcePages(item,item.point_decisions[1]),'[a; 答卷页 1] Letter by Mira\n[b; 答卷页 2] Continued: author Mira');
  const packet=compactFeedbackPacket({...grade,rubric_hash:frozen.hash},frozen);
  assert.equal(packet.items[0].points[1][5],evidenceWithSourcePages(item,item.point_decisions[1]));
  item.point_decisions[1].student_pages=[1];assert.throws(()=>evidenceWithSourcePages(item,item.point_decisions[1]));
});
