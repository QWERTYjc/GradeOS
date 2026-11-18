import { uncertaintyView } from '../web/ui.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { gradingAnnotations, annotationBatches, findGradingAnnotation } from '../web/grading-annotations.mjs';
import { resolveReferences } from '../src/workspace/editable-documents.mjs';
import { publicState, emptyState } from '../src/workspace/store.mjs';
import { annotationTools } from '../src/workspace/annotation-tools.mjs';

function fixture() {
  const pages = ['a', 'b', 'c', 'ms'].map(id => ({ id, sha256: `hash-${id}`, role: id === 'ms' ? 'scheme' : 'student', sourcePage: id === 'b' ? 2 : 1, fileName: `${id}.pdf`, active: true }));
  const group = { id: 'student', label: 'Student', pageIds: ['a', 'b'] };
  const record = { id: 'r1', groupId: group.id, student: 'Student', itemId: '1a', pointId: 'm1',
    score: 1, maximum: 1, allowedAwards: [0, 1], reason: 'Full criterion met.', evidence: 'x=2', sourceText: 'x=2',
    studentPageIds: ['a', 'b'], schemePageIds: ['ms'], reviewRequired: false, originalHash: 'frozen-r1' };
  const task = { id: 't1', kind: 'grade', groups: [group], scheme: { pageIds: ['ms'] }, pages: structuredClone(pages), records: [record] };
  return { ...emptyState(), pages, groups: [group, { id: 'other', pageIds: ['c'] }], schemes: [{ id: 'scheme', pageIds: ['ms'] }], tasks: [task],
    documents: [{ id: 'guide', taskId: 't1', proposalId: 'proposal', revision: 3, hash: 'draft-v3', body: 'future instructions',
      history: [], approvals: [{ revision: 2, hash: 'adopted-v2' }] }] };
}

test('every saved point becomes a detailed comment without generating, persisting, or changing a judgement', () => {
  const state = fixture();
  state.tasks[0].records.push({ ...state.tasks[0].records[0], id: 'r2', pointId: 'a1', score: 0, reason: 'Required conclusion is absent.' });
  state.tasks[0].records.push({ ...state.tasks[0].records[0], id: 'r3', pointId: 'a2', score: null, evidence: '', reason: '', reviewRequired: true });
  const before = structuredClone(state), rows = gradingAnnotations(state, 't1', 'student');
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map(row => row.tone), ['credit', 'deduction', 'review']);
  assert.deepEqual(rows.map(row => row.score), [1, 0, null]);
  assert.match(rows[2].text, /分数待定/);
  assert.match(rows[2].text, /未提供可引用证据/);
  assert.ok(rows.every(row => row.text.includes('评分条件：x=2') && row.guide.hash === 'adopted-v2' && row.guide.revision === 2));
  assert.ok(rows.every(row => !row.text.includes('future instructions')));
  assert.deepEqual(state, before);
  assert.deepEqual(gradingAnnotations(state, 't1', 'student'), rows);
  assert.equal(rows[0].target.rect.width, 1, 'Page comments must reference the full page, not the blank marker margin');
});

test('multipage comments reference the clicked original, while sources and pupils remain isolated', () => {
  const state = fixture(), note = gradingAnnotations(state, 't1', 'student', 'b')[0];
  assert.equal(note.target.pageId, 'b');
  const [reference] = resolveReferences(state, [{ annotationId: note.id, target: note.target }], ['student']);
  assert.equal(reference.target.pageId, 'b');
  assert.equal(reference.origin, 'saved_grading_result');
  assert.equal(reference.originalHash, 'frozen-r1');
  assert.equal(reference.guide.revision, 2);
  assert.throws(() => resolveReferences(state, [{ annotationId: note.id, target: note.target }], ['other']), /范围/);
  assert.equal(findGradingAnnotation(state, note.id, 'c'), null);
  assert.equal(findGradingAnnotation(state, note.id, 'ms'), null);
  assert.equal(findGradingAnnotation(state, 'grading-forged-original'), null);
});

test('reviews remain separate, invalidate old references, and never convert an unknown to zero', () => {
  const state = fixture(), old = gradingAnnotations(state, 't1', 'student')[0];
  state.reviews.push({ id: 'stale', taskId: 't1', recordId: 'r1', originalHash: 'wrong', score: 0, reason: 'Wrong snapshot' });
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].id, old.id);
  state.reviews.push({ id: 'review1', taskId: 't1', recordId: 'r1', originalHash: 'frozen-r1', score: null, reason: 'Check original handwriting' });
  const reviewed = gradingAnnotations(state, 't1', 'student')[0];
  assert.equal(reviewed.score, null);
  assert.equal(reviewed.originalScore, 1);
  assert.equal(reviewed.tone, 'review');
  assert.match(reviewed.text, /老师复核（待定）/);
  assert.equal(findGradingAnnotation(state, old.id), null);
  assert.throws(() => resolveReferences(state, [{ annotationId: old.id, target: old.target }], ['student']), /已移除/);
  assert.equal(state.tasks[0].records[0].score, 1);
});

test('qualitative feedback is labelled separately from an unresolved score before and after review', () => {
  const state = fixture(), record = state.tasks[0].records[0];
  Object.assign(record, { score: null, maximum: null, allowedAwards: [], disposition: 'feedback_only', reviewRequired: true,
    basis: 'answer_context', basisLabel: '从本份答卷恢复题意 · 建议评分' });
  const before = structuredClone(state);
  let note = gradingAnnotations(state, 't1', 'student')[0];
  assert.equal(note.scoreLabel, '定性反馈');
  assert.equal(note.originalScoreLabel, '定性反馈');
  assert.equal(note.basisLabel, '依据本份答卷内容 · 建议批改');
  assert.doesNotMatch(note.text, /待定|定性反馈 分/);
  assert.deepEqual(state, before);
  state.reviews.push({ id: 'qualitative-review', taskId: 't1', recordId: record.id, originalHash: record.originalHash, score: null, reason: 'Confirmed explanation' });
  note = gradingAnnotations(state, 't1', 'student')[0];
  assert.equal(note.score, null);
  assert.match(note.text, /老师复核（定性反馈）/);
  record.disposition = 'needs_material';
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].scoreLabel, '待定');
  Object.assign(record, { disposition: 'score', score: 0, maximum: 2, allowedAwards: [0, 1, 2] });
  state.reviews = [];
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].scoreLabel, '0 / 2 分');
});

test('batch isolation, repartitioning and changed source bytes cannot silently reuse annotations', () => {
  const state = fixture();
  const second = structuredClone(state.tasks[0]); second.id = 't2'; second.records[0].id = 'r-new'; second.records[0].score = 0;
  state.tasks.push(second);
  assert.deepEqual(annotationBatches(state, 'a').map(task => task.id), ['t1', 't2']);
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].score, 1);
  assert.equal(gradingAnnotations(state, 't2', 'student')[0].score, 0);
  state.pages[0].sha256 = 'changed';
  assert.equal(gradingAnnotations(state, 't1', 'student', 'a').length, 0);
  assert.equal(gradingAnnotations(publicState(state, false), 't1', 'student', 'a').length, 0);
  state.groups = [{ id: 'student', pageIds: ['c'] }];
  assert.deepEqual(gradingAnnotations(state, 't1', 'student'), []);
});

test('missing location stays unplaced and cross-scope page IDs cannot become invented anchors', () => {
  const state = fixture();
  state.tasks[0].records[0].studentPageIds = ['c', 'missing'];
  const note = gradingAnnotations(state, 't1', 'student')[0];
  assert.equal(note.target, null);
  assert.match(note.text, /答卷页：未定位/);
  assert.deepEqual(gradingAnnotations(state, 't1', 'student', 'a'), []);
  assert.throws(() => resolveReferences(state, [{ annotationId: note.id }], ['student']), /引用内容不存在/);
});

test('the assistant can read saved evidence in scope and has no coordinate-writing tool', async () => {
  const state=fixture(), before=structuredClone(state);
  const tools=annotationTools({state, selectedIds:['student']});
  assert.deepEqual(tools.map(tool=>tool.name),['read_annotation_points']);
  const result=await tools[0].execute('',{taskId:'t1', pageId:'a'});
  assert.deepEqual(JSON.parse(result.content[0].text),[{n:1,point:'1a · M1',evidence:'x=2',regionIds:[]}]);
  await assert.rejects(tools[0].execute('',{taskId:'t1',pageId:'c'}),/范围/);
  assert.deepEqual(state,before);
});

test('specific doubts survive annotation projection and render as escaped review notes', () => {
  const state = fixture(), record = state.tasks[0].records[0];
  record.uncertainties = ['Possible <symbol> ambiguity'];
  const before = structuredClone(state);
  const note = gradingAnnotations(state, 't1', 'student')[0];
  assert.deepEqual(note.uncertainties, record.uncertainties);
  assert.match(note.text, /待核实：Possible <symbol> ambiguity/);
  assert.match(uncertaintyView(note), /Possible &lt;symbol&gt; ambiguity/);
  assert.equal(uncertaintyView({}), '');
  assert.deepEqual(state, before);
});


test('specific-doubt filtering excludes ordinary provisional scores', () => {
  const state = fixture(), record = state.tasks[0].records[0];
  Object.assign(record, { basis: 'answer_context', disposition: 'score', reviewRequired: true, uncertainties: [] });
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].hasIssue, false);
  record.score = 0;
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].hasIssue, false, 'An unambiguous wrong answer is not an uncertain judgment.');
  record.uncertainties = ['Check this faint sign.'];
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].hasIssue, true);
  record.uncertainties = []; record.score = null;
  assert.equal(gradingAnnotations(state, 't1', 'student')[0].hasIssue, true);
});
