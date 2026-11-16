import test from 'node:test';
import assert from 'node:assert/strict';
import {conciseFeedbackIds, focusedFeedbackPacket, expandFocusedFeedback} from '../src/focused-feedback.mjs';
import {validateFeedback, renderStudentFeedback} from '../src/student-feedback.mjs';
import {exceptionProbeFixture} from '../src/exception-probe-fixture.mjs';
import {digest} from '../src/core.mjs';

function ordinary(id='Fir-input', evidence='x = 3') {
  const f=exceptionProbeFixture();
  f.frozen.artifact.items=f.frozen.artifact.items.filter(row=>row.item_id==='Fir-input');
  f.primary.items=f.primary.items.filter(row=>row.item_id==='Fir-input');
  f.frozen.artifact.items[0].item_id=id;f.primary.items[0].item_id=id;
  const p=f.primary.items[0].point_decisions[0];
  p.evidence=evidence;p.reason='Full criterion met.';p.reason_encoding='explicit_full_credit_attestation';
  return {grade:f.primary,frozen:f.frozen};
}
const raw=()=>({summary:'原记录中的已知得分与证据均保留，按具体失分点安排练习。',strengths:[],priorities:[],items:[]});

test('three equivalent representations retain original scores and full point tables with labeled fixed commentary',()=>{
  for(const [id,evidence] of [['First','x = 3'],['源乙','输入为三'],['Neutral.iii','3 = x']]) {
    const {grade,frozen}=ordinary(id,evidence),before=digest(grade);
    assert.deepEqual(conciseFeedbackIds(grade,frozen),[id]);
    const packet=focusedFeedbackPacket(grade,frozen);
    assert.deepEqual(packet.required_commentary_ids,[]);
    assert.equal(packet.items[0].recorded_observations[0].evidence,evidence);
    const feedback={...validateFeedback(expandFocusedFeedback(raw(),grade,frozen),grade,frozen),version:3,fixed_commentary_ids:[id]};
    const report=renderStudentFeedback('owner',grade,frozen,feedback);
    assert.ok(report.includes(evidence));assert.ok(report.includes(frozen.artifact.items[0].scoring_points[0].condition));
    assert.ok(report.includes('固定简述'));assert.equal(digest(grade),before);
  }
});
test('same IDs with adverse, exceptional, uncertain or substantive judgments cannot lose commentary',()=>{
  const mutations=[
    (g)=>{g.items[0].score=0;g.items[0].point_decisions[0].score=0;g.items[0].point_decisions[0].relation='unmet';},
    (g)=>{g.items[0].point_decisions[0].relation='exception';g.items[0].point_decisions[0].rule_ref='G1';},
    (g)=>{g.items[0].score=null;g.items[0].review_required=true;g.items[0].point_decisions[0].score=null;},
    (g,f)=>{f.artifact.unresolved_notes=['The source is ambiguous.'];},
    (g,f)=>{f.artifact.items[0].uncertainties=['Unreadable symbol.'];},
    (g)=>{g.source_issues=[{item_id:g.items[0].item_id,observation:'Conflict'}];},
    (g)=>{delete g.items[0].point_decisions[0].reason_encoding;g.items[0].point_decisions[0].reason='A substantive explanation remains.';},
  ];
  for(const mutate of mutations){const {grade,frozen}=ordinary();mutate(grade,frozen);
    assert.deepEqual(conciseFeedbackIds(grade,frozen),[]);
    assert.throws(()=>expandFocusedFeedback(raw(),grade,frozen),/Missing substantive/);
    assert.ok(focusedFeedbackPacket(grade,frozen).items[0].points);
  }
});
test('unrelated partial/exception records retain the complete packet, and new review concerns override fixed text',()=>{
  const f=exceptionProbeFixture();assert.equal(focusedFeedbackPacket(f.primary,f.frozen).items.filter(i=>i.points).length,f.primary.items.length);
  const {grade,frozen}=ordinary();const model={...raw(),items:[['Fir-input','需人工核实记录之间的矛盾。','回看原卷。','存在新的反馈疑点。']]};
  const expanded=validateFeedback(expandFocusedFeedback(model,grade,frozen),grade,frozen);
  assert.equal(expanded.items[0].review_recommended,true);
  assert.equal(expanded.items[0].assessment,model.items[0][1]);
  assert.throws(()=>validateFeedback(expandFocusedFeedback({...model,items:[...model.items,...model.items]},grade,frozen),grade,frozen),/coverage|duplicate/);
});
