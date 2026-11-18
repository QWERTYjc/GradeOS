import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { get } from 'node:http';
import { createWorkspaceServer } from '../src/workspace/server.mjs';
import { makeRecord, WorkspaceStore } from '../src/workspace/store.mjs';

// Minimal actual PDF, used only for the local upload/rendering contract.
function pdf() {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 600] /Contents 4 0 R >>', '<< /Length 0 >>\nstream\n\nendstream',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 600] /Contents 6 0 R >>', '<< /Length 0 >>\nstream\n\nendstream',
  ];
  let text = '%PDF-1.4\n'; const offsets = [0];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(text)); text += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(text);
  text += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(text);
}
test('three real PDF upload roles remain separate and qualitative review can complete without inventing a score', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-three-materials-'));
  const app = await createWorkspaceServer({ directory, port: 0, configured: () => false });
  t.after(async () => { await app.close(); await rm(directory, { recursive: true, force: true }); });
  const base = `http://127.0.0.1:${app.server.address().port}`;
  let state = await (await fetch(base + '/api/state')).json(); const token = state.token;
  for (const role of ['student', 'question', 'scheme']) {
    const response = await fetch(`${base}/api/uploads?role=${role}&name=${role}.pdf`, { method: 'POST', headers: { 'X-Workspace-Token': token }, body: pdf() });
    assert.equal(response.status, 201); state = await response.json();
  }
  assert.equal(state.groups.length, 1); assert.equal(state.questions.length, 1); assert.equal(state.schemes.length, 1);
  assert.equal(state.pages.length, 6); assert.equal(state.groups[0].pageIds.length, 2);
  const write = (path, body) => fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token }, body: JSON.stringify({ revision: state.revision, ...body }) });
  const response = await write('/api/tasks', { groupIds: [state.groups[0].id], questionId: state.questions[0].id, schemeId: null, after: 'review' });
  assert.equal(response.status, 200); state = await response.json();
  assert.equal(state.createdTaskId, state.tasks[0].id);
  assert.equal(state.tasks[0].kind, 'grade'); assert.equal(state.tasks[0].goal, '批改所选答卷');
  assert.equal(state.tasks[0].supplementalInstructions, '');
  const taskId = state.tasks[0].id;
  assert.equal(state.tasks[0].scheme, null); assert.equal(state.tasks[0].question.pageIds.length, 2);
  await app.store.mutate(null, snapshot => {
    snapshot.tasks[0].status = 'needs_review'; snapshot.tasks[0].records = [{ id: 'qualitative', originalHash: 'original', score: null, allowedAwards: [], reviewRequired: true, disposition: 'feedback_only' }];
  });
  state = await (await fetch(base + '/api/state')).json();
  assert.equal((await write(`/api/tasks/${taskId}/review-complete`, {})).status, 422);
  const review = await write('/api/reviews', { taskId, recordId: 'qualitative', originalHash: 'original', score: null, reason: '已确认定性反馈，不赋分。' });
  assert.equal(review.status, 200); state = await review.json();
  const complete = await write(`/api/tasks/${taskId}/review-complete`, {});
  assert.equal(complete.status, 200); state = await complete.json();
  assert.equal(state.tasks[0].status, 'completed'); assert.equal(state.tasks[0].records[0].score, null);
});
test('an occupied port cannot recover or rewrite another live workspace', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-occupied-port-'));
  const app = await createWorkspaceServer({ directory, port: 0, configured: () => false });
  t.after(async () => { await app.close(); await rm(directory, { recursive: true, force: true }); });
  await app.store.mutate(null, state => { state.tasks.push({ id: 'active-task', status: 'running' }); });
  const before = app.store.snapshot();
  await assert.rejects(createWorkspaceServer({ directory, port: app.server.address().port }), { code: 'EADDRINUSE' });
  assert.deepEqual((await new WorkspaceStore(directory).init()).snapshot(), before);
});
test('HTTP upload → split → draft → review persists; rejects cross-origin/stale/invalid writes', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-http-'));
  const app = await createWorkspaceServer({ directory, port: 0, configured: () => false });
  t.after(async () => { await app.close(); await rm(directory, { recursive: true, force: true }); });
  const base = `http://127.0.0.1:${app.server.address().port}`;
  let state = await (await fetch(`${base}/api/state`)).json();
  const token = state.token;
  const mutate = (path, body, method = 'POST', extra = {}) => fetch(base + path, { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token, ...extra }, body: JSON.stringify({ revision: state.revision, ...body }) });
  assert.equal((await fetch(`${base}/api/tasks`, { method: 'POST', body: '{}' })).status, 403);
  assert.equal((await mutate('/api/tasks', {}, 'POST', { Origin: 'https://untrusted.example' })).status, 403);
  const foreignHostStatus = await new Promise((resolve, reject) => {
    get(`${base}/api/state`, { headers: { Host: 'untrusted.example' } }, response => { response.resume(); resolve(response.statusCode); }).on('error', reject);
  });
  assert.equal(foreignHostStatus, 403);
  const upload = await fetch(`${base}/api/uploads?role=student&name=synthetic.pdf`, { method: 'POST', headers: { 'X-Workspace-Token': token }, body: pdf() });
  assert.equal(upload.status, 201); state = await upload.json();
  assert.equal(state.pages.length, 2); assert.equal(state.groups.length, 1);
  assert.equal((await fetch(base + state.pages[0].url)).headers.get('content-type'), 'image/png');
  const groups = state.pages.map((page, index) => ({ id: `s${index}`, label: `Student ${index}`, pageIds: [page.id] }));
  let result = await mutate('/api/materials', { groups }, 'PATCH'); assert.equal(result.status, 200); state = await result.json();
  assert.equal((await mutate('/api/materials', { groups, revision: 0 }, 'PATCH')).status, 409);
  result = await mutate('/api/tasks', { title: 'Check first', goal: 'Check first only', kind: 'assist', groupIds: ['s0'], schemeId: null, after: 'review' });
  assert.equal(result.status, 200); state = await result.json();
  assert.deepEqual(state.tasks[0].groupIds, ['s0']); assert.equal(state.tasks[0].status, 'draft');
  assert.equal((await mutate('/api/agent', { selectedIds: ['s0'], goal: 'Check pages' })).status, 424);
  const taskId = state.tasks[0].id;
  await app.store.mutate(null, snapshot => {
    const task = snapshot.tasks[0]; task.status = 'needs_review';
    task.records = [makeRecord(task, task.groups[0], { item_id: 'Q1', review_required: true }, { point_id: 'M1', score: null, student_pages: [1], reason: 'unclear' }, { max_score: 1, allowed_awards: [0, 1], source_pages: [] }, 'grade', 'rubric')];
  });
  state = await (await fetch(`${base}/api/state`)).json();
  const record = state.tasks[0].records[0];
  const review = { taskId, recordId: record.id, originalHash: record.originalHash, score: 1, reason: 'Original shows the evidence.' };
  result = await mutate('/api/reviews', review); assert.equal(result.status, 200); state = await result.json();
  assert.equal(state.tasks[0].records[0].score, null);
  result = await mutate('/api/reviews', { ...review, score: null, reason: 'Return to pending.' }); state = await result.json();
  assert.equal((await mutate(`/api/tasks/${taskId}/review-complete`, {})).status, 422);
  assert.equal((await mutate('/api/reviews', { ...review, score: 10 })).status, 422);
  assert.equal(state.reviews.length, 2);
  for (const path of ['/', '/app.mjs', '/style.css', '/assets/icons/upload.svg']) assert.equal((await fetch(base + path)).status, 200);
});

test('manual intake separates uploaded files from student ownership and clears only current materials', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-manual-intake-'));
  const app = await createWorkspaceServer({directory, port: 0, configured: () => false});
  t.after(async () => { await app.close(); await rm(directory, {recursive:true, force:true}); });
  const base = 'http://127.0.0.1:' + app.server.address().port;
  let state = await (await fetch(base + '/api/state')).json();
  const headers = { 'X-Workspace-Token': state.token };
  async function upload() {
    const res = await fetch(base + '/api/uploads?role=student&name=a.pdf&grouping=manual', {method:'POST',headers,body:pdf()});
    assert.equal(res.status, 201); state = await res.json();
  }
  async function write(path, method, body) {
    const res = await fetch(base + path, {method,headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({revision:state.revision,...body})});
    assert.equal(res.status,200); state=await res.json();
  }
  await upload(); await upload();
  const [a,b,c,d] = state.pages;
  assert.equal(state.groups.length,0);
  await write('/api/materials','PATCH',{groups:[{id:'pupil',pageIds:[a.id,c.id]}],unassignedPageIds:[b.id,d.id]});
  await write('/api/tasks','POST',{groupIds:['pupil'],after:'review'});
  const frozen = state.tasks[0].groups;
  await write('/api/uploads','DELETE',{sourceIds:[a.sourceId,c.sourceId]});
  assert.deepEqual(state.groups,[]);
  assert.deepEqual(state.tasks[0].groups,frozen);
  assert.ok(state.pages.every(page=>page.active===false));
  assert.equal((await fetch(base+a.url)).status,200);
  await upload();
  const unused=state.pages.at(-1);
  await write('/api/uploads','DELETE',{sourceIds:[unused.sourceId]});
  assert.equal((await fetch(base+unused.url)).status,404);
  const {access}=await import('node:fs/promises');
  await assert.rejects(access(join(directory,'uploads',unused.sourceId)), {code:'ENOENT'});
});
