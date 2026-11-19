import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, rm, readFile, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { CloudPublisher, releasePayload } from '../src/workspace/cloud-publisher.mjs';

function source() {
  const group = { id: 'paper', label: '合成答卷', pageIds: ['page'] };
  const record = {
    id: 'a',
    groupId: 'paper',
    itemId: '一',
    pointId: '单位',
    score: 2,
    maximum: 4,
    originalHash: 'a'.repeat(64),
    reason: '内部原判',
    evidence: '内部证据',
  };
  return {
    groups: [group],
    pages: [{ id: 'page', active: true }],
    reviews: [],
    tasks: [
      {
        id: 'exam',
        title: '合成测验',
        kind: 'grade',
        status: 'completed',
        groups: [group],
        records: [record],
      },
    ],
  };
}
const data = {
  title: '单元一',
  date: '2026-01-10',
  baseVersion: 0,
  bindings: [{ paperId: 'paper', studentId: 'student-1', note: '公开评语' }],
};
test('release only teacher-selected fields and source-matched reviews, retaining pending and qualitative states', () => {
  const state = source(),
    record = state.tasks[0].records[0];
  const points = () => releasePayload(state, 'exam', data).papers[0].points;
  assert.equal(points()[0].score, 2);
  record.reviewRequired = true;
  assert.deepEqual([points()[0].state, points()[0].score], ['pending', null]);
  state.reviews.push({ taskId: 'other', recordId: 'a', originalHash: record.originalHash, score: 0 });
  assert.equal(points()[0].score, null);
  state.reviews.push({
    taskId: 'exam',
    recordId: 'a',
    originalHash: record.originalHash,
    score: 0,
    reason: '私有复核说明',
  });
  assert.equal(points()[0].score, 0);
  assert.doesNotMatch(JSON.stringify(releasePayload(state, 'exam', data)), /内部|私有/);
  record.disposition = 'feedback_only';
  assert.deepEqual([points()[0].state, points()[0].score, points()[0].max], ['feedback', null, null]);
  state.groups[0] = { ...state.groups[0], pageIds: [] };
  assert.throws(() => points());
  state.tasks[0].status = 'cancelled';
  assert.throws(() => points());
});
test('acknowledgement loss persists a frozen release across a workbench restart', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'gradeos-cloud-contract-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const state = source(),
    store = { directory: dir, snapshot: () => structuredClone(state) },
    code = 'a'.repeat(40);
  const received = [];
  let drop = true;
  const server = createServer(async (req, res) => {
    const chunks = [];
    for await (const part of req) chunks.push(part);
    const body = JSON.parse(Buffer.concat(chunks));
    if (req.url === '/api/pair') {
      res.end(JSON.stringify({ token: 'synthetic-token', classroom: { id: 'class', name: '合成班' } }));
      return;
    }
    assert.equal(req.headers.authorization, 'Bearer synthetic-token');
    received.push(body);
    if (drop) {
      drop = false;
      res.destroy();
      return;
    }
    res.end(JSON.stringify({ id: 'release', version: 1, replayed: true }));
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((r) => server.close(r)));
  const client = new CloudPublisher(store);
  await client.route('POST', 'pair', { pairing: 'http://127.0.0.1:' + server.address().port + '#' + code });
  assert.doesNotMatch(JSON.stringify(await client.route('GET', 'status')), /synthetic-token/);
  const { signature } = await client.route('POST', 'preview/exam', data);
  state.tasks[0].records[0].score = 1;
  await assert.rejects(client.route('POST', 'publish/exam', { ...data, signature }), /重新预览/);
  state.tasks[0].records[0].score = 2;
  await assert.rejects(client.route('POST', 'publish/exam', { ...data, signature }), /网络/);
  state.tasks[0].records[0].score = 0;
  const reopened = new CloudPublisher(store);
  assert.equal((await reopened.route('GET', 'status')).tasks[0].queued, true);
  assert.equal((await reopened.route('POST', 'retry/exam', {})).version, 1);
  assert.deepEqual(received[1], received[0]);
  assert.equal(received[1].papers[0].points[0].score, 2);
  assert.equal((await stat(join(dir, 'cloud-publisher.json'))).mode & 0o777, 0o600);
  assert.deepEqual(JSON.parse(await readFile(join(dir, 'cloud-publisher.json'))).outbox, {});
});
