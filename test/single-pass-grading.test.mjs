import test from 'node:test';
import assert from 'node:assert/strict';
import { validateToolArguments } from '@earendil-works/pi-ai';
import { singlePassSchema, singlePassPrompt, decodeSinglePassSubmission } from '../src/single-pass-grading.mjs';
import { splitInlineAnnotations, attachInlineAnnotations, annotationFrame, withoutAnnotationGeometry } from '../src/inline-annotations.mjs';
import { expandCompactPoints } from '../src/compact-points.mjs';
import { freezeRubric } from '../src/cohort-core.mjs';

const scheme = { sha256: 'neutral-ms', pages: [{ page: 1, sha256: 'ms1' }] };
const student = { sha256: 'neutral-answer', pages: [{ page: 1, sha256: 'p1' }, { page: 2, sha256: 'p2' }] };
const frozen = freezeRubric({ general_instructions: [], unresolved_notes: [], items: [{
  question_id: 'Document', item_id: 'kind', max_score: 1, criteria: 'Identify a letter.', source_pages: [1],
  related_item_ids: [], requires_source_image: false, image_reason: '', uncertainties: [],
  scoring_points: [{ point_id: 'genre', max_score: 1, allowed_awards: [0, 1], award_type: 'A',
    condition: 'Identify a letter.', source_text: 'letter', source_pages: [1], depends_on: [] }],
  routes: [{ route_id: 'r', point_ids: ['genre'], description: 'Equivalent wording.' }],
}] }, scheme, new Set([1]));
const frames = new Map([['i1', annotationFrame(student.pages[0], 'original')]]);
const receipts = new Map([['p1', { annotation_frame: 'i1', role: 'student', page: 1,
  representation: 'original', original_sha256: 'p1', image_hash: 'delivered' }]]);
const make = ([id,e,p,l,s,j,r]) => ({ observations:{kind:{[id]:l==='absent'?{absent:p}:{t:e,p,l}}},items: { kind: { route: 'r', review: s === null, p: { [id]: {s,j,r} } } }, review_notes: [], source_issues: [] });

test('evidence-first wire preserves every judgment under equivalent wording, IDs, and layout changes', () => {
  for (const [id, text, rect] of [['kind', 'a letter', [20, 30, 200, 50]], ['renamed', 'personal correspondence', [600, 750, 250, 40]], ['文类', '一封私人信', [400, 80, 300, 60]]]) {
    const rubric = structuredClone(frozen); rubric.artifact.items[0].item_id = id;
    const raw = make(['genre', text, [1], [['i1', ...rect]], 1, 'm', 'Correct genre.']);
    raw.items = { [id]: raw.items.kind }; raw.observations = {[id]:raw.observations.kind};
    const before = structuredClone(raw);
    const split = splitInlineAnnotations(decodeSinglePassSubmission(raw, { inlineAnnotations: true }));
    const grade = expandCompactPoints(split.grading, rubric, student);
    const annotated = attachInlineAnnotations(structuredClone(grade), split.annotations, student, frames, receipts);
    assert.deepEqual(raw, before);
    assert.deepEqual(withoutAnnotationGeometry(annotated), grade);
    assert.equal(annotated.items[0].point_decisions[0].annotation.status, 'located');
  }
});

test('malformed or absent location never moves a numeric field into the score', () => {
  for (const location of [9, {}, true, [['i1', 900, 0, 300, 20]], 'unlocated: overlapping strokes']) {
    const split = splitInlineAnnotations(decodeSinglePassSubmission(make(['genre', 'a poem', [1], location, 0, 'u:c', 'It is not a letter.']), { inlineAnnotations: true }));
    const grade = attachInlineAnnotations(expandCompactPoints(split.grading, frozen, student), split.annotations, student, frames, receipts);
    const point = grade.items[0].point_decisions[0];
    assert.equal(point.score, 0); assert.equal(point.evidence, 'a poem'); assert.equal(point.annotation.regions.length, 0);
  }
  const missing = make(['genre', 'a letter', [1], [], 1, 'm', 'Correct genre.']);
  delete missing.observations.kind.genre.l;
  assert.throws(() => decodeSinglePassSubmission(missing, { inlineAnnotations: true }), /literal observation/);
});

test('absent, ambiguous, incorrect and unlocated evidence remain distinct without fabricated marks', () => {
  for (const [text, location, score, state, reason, status] of [
    ['Answer left blank', 'absent', 0, 'u:c', 'Required genre not supplied.', 'absent'],
    ['The word is unreadable', 'unlocated: overlapping strokes', null, 'q:u', 'Cannot determine genre.', 'unlocated'],
    ['a poem', [['i1', 80, 90, 200, 40]], 0, 'u:c', 'Wrong genre.', 'located'],
  ]) {
    const split = splitInlineAnnotations(decodeSinglePassSubmission(make(['genre', text, [1], location, score, state, reason]), { inlineAnnotations: true }));
    const point = attachInlineAnnotations(expandCompactPoints(split.grading, frozen, student), split.annotations, student, frames, receipts).items[0].point_decisions[0];
    assert.equal(point.score, score); assert.equal(point.annotation.status, status);
  }
});

test('both one-pass arms use observation before judgment with no unavailable repair tools', () => {
  for (const inlineAnnotations of [false, true]) {
    const prompt = singlePassPrompt({ inlineAnnotations });
    assert.doesNotMatch(prompt, /read_student_pages|read_ms_pages|correct_grading|reopen_grading|Geometry is optional/);
    assert.match(prompt, /Write observations FIRST/);
    const schema = singlePassSchema({ frozen, student, inlineAnnotations });
    assert.deepEqual(schema.properties.items.required, ['kind']);
    assert.deepEqual(schema.properties.items.properties.kind.properties.p.required, ['genre']);
    assert.deepEqual(schema.$defs.decision.required,['r','j','s']);
    assert.deepEqual(schema.properties.observations.properties.kind.required,['genre']);
    assert.deepEqual(Object.keys(schema.properties)[0],'observations');
  }
  const plain = {observations:{kind:{genre:{t:'a letter',p:[1]}}},items:{kind:{route:'r',review:false,p:{genre:{s:1,j:'m',r:'Correct genre.'}}}},review_notes:[],source_issues:[]};
  assert.equal(expandCompactPoints(decodeSinglePassSubmission(plain), frozen, student).items[0].score, 1);
});

test('actual Pi schema validation rejects omitted inventory and accepts the named source-bound ledger', () => {
  const parameters = singlePassSchema({ frozen, student, inlineAnnotations: true });
  const tool = { name: 'submit_grading', description: 'Submit all points.', parameters };
  const input = make(['genre', 'a letter', [1], [['i1', 20, 30, 200, 50]], 1, 'm', '=']);
  const check = arguments_ => validateToolArguments(tool, { type: 'toolCall', id: 'once', name: tool.name, arguments: arguments_ });
  assert.deepEqual(check(input), input);
  const withoutItem = structuredClone(input); delete withoutItem.items.kind;
  const withoutPoint = structuredClone(input); delete withoutPoint.items.kind.p.genre;
  const withoutLocation = structuredClone(input); delete withoutLocation.observations.kind.genre.l;
  const foreignPoint = structuredClone(input); foreignPoint.items.kind.p.other = foreignPoint.items.kind.p.genre;
  const placeholderState = structuredClone(input); placeholderState.items.kind.p.genre.j = 'u:N';
  const inventedRule = structuredClone(input); inventedRule.items.kind.p.genre.j = 'x:i:G99';
  for (const bad of [withoutItem, withoutPoint, withoutLocation, foreignPoint, placeholderState, inventedRule]) assert.throws(() => check(bad));
});

test('source proof points require a substantive explanation without changing allowed awards',()=>{
  const proof=structuredClone(frozen);proof.artifact.items[0].scoring_points[0].award_type='proof';
  const tool={name:'submit_grading',parameters:singlePassSchema({student,frozen:proof,inlineAnnotations:true,annotationGrid:true})};
  const input=make(['genre','The conclusion is asserted.',[1],['i1.A1:B2'],1,'m','=']);
  assert.throws(()=>validateToolArguments(tool,{name:tool.name,arguments:input}));
  input.items.kind.p.genre.r='The displayed relation establishes the required inference.';
  assert.doesNotThrow(()=>validateToolArguments(tool,{name:tool.name,arguments:input}));
  assert.equal(input.items.kind.p.genre.s,1);
});

test('spatial cell references are source-bound and never affect awards or repair student evidence', () => {
  const geometry = { original_sha256:'p1',pixel_identity_verified:true,original_size:[999,1400],
    size:[1063,1436],source_rect_in_image:[64,36,1063,1436],grid:{version:'source-grid-v1',columns:10,rows:40} };
  const gridFrames=new Map([['i1',annotationFrame(student.pages[0],'source_grid',geometry)]]);
  const gridReceipts=new Map([['p1',{...receipts.get('p1'),representation:'source_grid'}]]);
  const locate=l=>{
    const {grading,annotations}=splitInlineAnnotations(decodeSinglePassSubmission(make(['genre','a letter',[1],l,1,'m','=']),{inlineAnnotations:true}));
    const base=expandCompactPoints(grading,frozen,student);
    const grade=attachInlineAnnotations(structuredClone(base),annotations,student,gridFrames,gridReceipts);
    assert.deepEqual(withoutAnnotationGeometry(grade),base);
    return grade.items[0].point_decisions[0].annotation;
  };
  assert.deepEqual(locate(['i1.C17:G18']).regions[0].rect,{x:.2,y:.4,width:.5,height:.05});
  const context=locate(['i1.C17:G18']).regions[0].contextRect;
  assert.deepEqual(locate('i1.C17:G18'),locate(['i1.C17:G18']));
  assert.equal(context.x,.1); assert.equal(context.y,.375);
  assert.ok(Math.abs(context.width-.7)<1e-10);assert.ok(Math.abs(context.height-.1)<1e-10);
  const edge=locate(['i1.J40:J40']).regions[0].contextRect;
  assert.ok(edge.x+edge.width<=1 && edge.y+edge.height<=1);
  assert.equal(locate(['i1.A1:A1','i1.J40:J40']).regions.length,2);
  for(const l of [['i1.C18:A17'],['i1.A1:J41'],['i2.A1:B2'],['i1.A1:J40'],[['i1',0,0,200,100]]]) assert.equal(locate(l).status,'invalid');
  for(const l of ['i1.C18:A17','i1.A1:J41','i2.A1:B2','i1.A1:J40','not a cell']) assert.equal(locate(l).status,'invalid');
  assert.throws(()=>annotationFrame(student.pages[1],'source_grid',geometry),/source-bound/);
  const tool={name:'submit_grading',parameters:singlePassSchema({frozen,student,inlineAnnotations:true,annotationGrid:true})};
  assert.doesNotThrow(()=>validateToolArguments(tool,{name:tool.name,arguments:make(['genre','letter',[1],['i1.C17:G18'],1,'m','='])}));
  assert.match(singlePassPrompt({inlineAnnotations:true,annotationGrid:true}),/Do not estimate numeric coordinates/);
});


test('grading cannot rewrite literal ink or introduce dynamic references',()=>{
  const input=make(['genre','3k + 7',[1],['i1.C4:E5'],0,'u:c','The observed result differs from the source condition.']);
  const before=structuredClone(input);
  const decoded=decodeSinglePassSubmission(input,{inlineAnnotations:true,student});
  assert.equal(decoded.items[0].p[0][2],'3k + 7');
  assert.deepEqual(input,before);
  for(const change of [row=>row.e='3k - 7',row=>row.o=['1:2'],row=>row.o=['3:1'],row=>row.o=['1:1','1:1'],row=>row.o=[]]){
    const bad=structuredClone(input);change(bad.items.kind.p.genre);
    assert.throws(()=>decodeSinglePassSubmission(bad,{inlineAnnotations:true,student}));
  }
  const reordered={items:input.items,observations:input.observations,review_notes:[],source_issues:[]};
  assert.throws(()=>decodeSinglePassSubmission(reordered,{inlineAnnotations:true,student}),/precede/);
});

test('disjoint and ambiguous excerpts remain exact without invented scores',()=>{
  const input=make(['genre','u = 4 cos v\ndu = [unclear: positive or negative] 4 sin v dv',[1,2],['i1.C4:E5','i2.G20:J21'],null,'q:u','A decisive symbol is unclear.']);
  const decoded=decodeSinglePassSubmission(input,{inlineAnnotations:true,student}).items[0].p[0];
  assert.equal(decoded[1],null);assert.equal(decoded[2],input.observations.kind.genre.t);
  assert.deepEqual(decoded[3],[1,2]);assert.deepEqual(decoded[6],['i1.C4:E5','i2.G20:J21']);
  input.observations.kind.genre.l='unlocated: overlapping strokes';
  assert.match(decodeSinglePassSubmission(input,{inlineAnnotations:true,student}).items[0].p[0][6],/^unlocated:/);
  input.observations.kind.genre.l='absent';
  assert.throws(()=>decodeSinglePassSubmission(input,{inlineAnnotations:true,student}),/cannot be absent/);
});

test('only explicit zero-mark absence can omit literal evidence',()=>{
  const input=make(['genre','',[2],'absent',0,'u:n','No response on checked pages.']);
  const row=decodeSinglePassSubmission(input,{inlineAnnotations:true,student}).items[0].p[0];
  assert.equal(row[1],0);assert.deepEqual(row[3],[2]);assert.equal(row[6],'absent');
  const tool={name:'submit_grading',parameters:singlePassSchema({frozen,student,inlineAnnotations:true,annotationGrid:true})};
  assert.doesNotThrow(()=>validateToolArguments(tool,{name:tool.name,arguments:input}));
  for(const change of [raw=>raw.items.kind.p.genre.s=null,raw=>raw.items.kind.p.genre.s=1,raw=>raw.observations.kind.genre.absent=[99],raw=>raw.observations.kind.genre.absent=[],raw=>raw.items.kind.p.genre.j='m']){
    const bad=structuredClone(input);change(bad);
    assert.throws(()=>decodeSinglePassSubmission(bad,{inlineAnnotations:true,student}));
  }
});

test('fixed point slots survive large inventories without generated row indices',()=>{
  const input=make(['genre','3k + 7',[1],['i1.C4:E5'],0,'u:c','The observed result differs.']);
  for(let i=0;i<150;i++) {
    input.observations['item'+i]={point:{t:'literal '+i,p:[2],l:['i2.B3:D4']}};
    input.items['item'+i]={route:'r',review:false,p:{point:{s:0,j:'u:c',r:'Visible incorrect result.'}}};
  }
  const decoded=decodeSinglePassSubmission(input,{inlineAnnotations:true,student});
  for(let i=0;i<150;i++)assert.equal(decoded.items[i+1].p[0][2],'literal '+i);
  delete input.observations.item120.point;
  assert.throws(()=>decodeSinglePassSubmission(input,{inlineAnnotations:true,student}),/Missing fixed/);
});

// The live strict provider rejects description siblings on a $ref, although
// general JSON Schema validators accept them. Keep this observed wire contract.
test('schema retains strict references while source conditions live in the complete source block',()=>{
  const schema=singlePassSchema({frozen,student,inlineAnnotations:true,annotationGrid:true});
  const visit=value=>{if(!value||typeof value!=='object')return;if('$ref' in value)assert.deepEqual(Object.keys(value),['$ref']);for(const child of Object.values(value))visit(child);};
  visit(schema);
  assert.equal(JSON.stringify(schema).includes(frozen.artifact.items[0].scoring_points[0].condition),false);
});

test('source location precedes literal text and source assessment precedes score',()=>{
 const s=singlePassSchema({frozen,student,inlineAnnotations:true,annotationGrid:true});
 assert.deepEqual(s.$defs.observedPoint.anyOf[0].required,['p','l','t']);
 assert.deepEqual(s.$defs.decision.required,['r','j','s']);
});
