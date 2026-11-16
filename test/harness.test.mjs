import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createAssistantMessageEventStream, createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { createGrader, validateGrade, Budget, wireEstimate, digest } from '../src/core.mjs';

const manifest = { documents: { scheme: { pages: [{ page: 1 }] }, student: { pages: [{ page: 1 }] } } };
const models = createModels(); models.setProvider(openrouterProvider());
const model = models.getModel('openrouter', 'openai/gpt-6.1-terra');
const row = { question_id: 'B', item_id: 'B(ii)', max_score: 2, score: 1, scheme_pages: [1], student_pages: [1], reason: 'Method supported; final value differs.', review_required: false };
const answer = () => ({ items: [structuredClone(row)], review_notes: [] });
const call = (name, args) => ({ type: 'toolCall', id: Math.random().toString(36).slice(2), name, arguments: args });
function fakeStream(turns, observed) {
  return (_model, context) => {
    observed.push(context);
    const content = turns.shift() ?? [{ type: 'text', text: 'Stopped.' }];
    const stream = createAssistantMessageEventStream();
    const message = { role: 'assistant', content, api: model.api, provider: model.provider, model: model.id,
      stopReason: content.some(x => x.type === 'toolCall') ? 'toolUse' : 'stop', timestamp: Date.now(),
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
    queueMicrotask(() => { stream.push({ type: 'done', reason: message.stopReason, message }); });
    return stream;
  };
}
test('real Pi loop reads both roles, persists, and ends without a paid follow-up', async () => {
  const seen = []; let saved;
  const grader = createGrader({ manifest, model, readPage: async () => 'aW1hZ2U=', persist: async x => { saved = x; },
    streamFn: fakeStream([[call('read_pages', { document: 'scheme', pages: [1] }), call('read_pages', { document: 'student', pages: [1] })], [call('submit_grading', answer())]], seen) });
  await grader.agent.prompt('Grade.');
  assert.equal(seen.length, 2); assert.equal(saved.total_score, 1); assert.equal(grader.getCoverage().length, 2);
});
test('premature stop is continued only twice and never marked complete', async () => {
  const observed = [];
  const grader = createGrader({ manifest, model, readPage: async () => '', persist: async () => assert.fail(), streamFn: fakeStream([], observed) });
  await grader.agent.prompt('Grade.');
  assert.equal(observed.length, 3); assert.equal(grader.getContinuations(), 2); assert.equal(grader.getResult(), null);
});
test('unread pages, duplicate identities, impossible awards, missing evidence fail closed', () => {
  const seen = new Set(['scheme:1', 'student:1']);
  assert.throws(() => validateGrade(answer(), manifest, new Set()));
  for (const mutate of [a => a.items.push({ ...row }), a => { a.items[0].score = 3; }, a => { a.items[0].score = false; },
    a => { a.items[0].student_pages = [2]; }, a => { a.items[0].score = null; }]) {
    const value = answer(); mutate(value); assert.throws(() => validateGrade(value, manifest, seen));
  }
  const value = answer(); value.items[0].score = null; value.items[0].review_required = true;
  assert.equal(validateGrade(value, manifest, seen).total_score, null);
});
test('budget includes unknown receipts and rejects work before admission', () => {
  const b = new Budget({ cap: 0.2 }); const first = b.admit(0.15, {});
  b.settle(first, { usage: { cost: { total: 0, totalFromProvider: false } } });
  assert.equal(b.chargedOrReserved, 0.15); assert.throws(() => b.admit(0.1, {}));
  b.settle(first, { usage: { cost: { total: 0.04, totalFromProvider: true } } });
  assert.ok(Math.abs(b.chargedOrReserved - 0.04) < 1e-12); b.admit(0.1, {});
});
test('wire admission counts images separately and file hash is byte faithful', () => {
  const result = wireEstimate({ content: [{ image_url: { url: 'data:image/png;base64,aGVsbG8=' } }] });
  assert.equal(result.images, 1); assert.ok(result.inputTokenReserve >= 4096);
  assert.equal(digest(Buffer.from('hello')), digest('hello'));
});
test('actual Pi OpenRouter adapter sends one HTTP request on a 500 with retries disabled', async () => {
  let requests = 0;
  const server = createServer((req, res) => { requests++; res.writeHead(500, { 'content-type': 'application/json' }); res.end('{"error":{"message":"synthetic failure"}}'); });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const local = { ...model, baseUrl: `http://127.0.0.1:${server.address().port}/v1` };
    const result = await models.streamSimple(local, { messages: [{ role: 'user', content: 'test', timestamp: Date.now() }] }, { apiKey: 'local-test-only', maxRetries: 0 }).result();
    assert.equal(result.stopReason, 'error'); assert.equal(requests, 1);
  } finally { server.close(); await once(server, 'close'); }
});

test('native PNG admission bounds full patch area instead of assuming old image size',()=>{
 const header=Buffer.alloc(24);Buffer.from('89504e470d0a1a0a','hex').copy(header);header.write('IHDR',12);header.writeUInt32BE(3500,16);header.writeUInt32BE(2482,20);
 const r=wireEstimate({messages:[{role:'user',content:[{type:'image_url',image_url:{url:'data:image/png;base64,'+header.toString('base64')}}]}]});
 assert.equal(r.imageTokenReserve,Math.ceil(3500/32)*Math.ceil(2482/32)*3);assert.equal(r.inputTokenReserve,r.textBytes+r.imageTokenReserve);
});
