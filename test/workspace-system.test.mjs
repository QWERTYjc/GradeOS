import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createWorkspaceServer } from '../src/workspace/server.mjs';
import { addDocument, saveDocument } from '../src/workspace/editable-documents.mjs';
import { SystemStore } from '../src/workspace/system-store.mjs';

async function setup(t, options = {}) {
  const directory = await mkdtemp(join(tmpdir(), 'gradeos-system-'));
  const app = await createWorkspaceServer({ directory, port: 0, configured: () => false, ...options });
  t.after(async () => { await app.close(); await rm(directory, { recursive: true, force: true }); });
  const base = `http://127.0.0.1:${app.server.address().port}`, token = (await (await fetch(base + '/api/state')).json()).token;
  const request = (path, body, method = 'POST', headers = {}) => fetch(base + '/api/system' + path, body === undefined ? undefined : { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token, ...headers }, body: JSON.stringify(body) });
  return { app, base, directory, request };
}
test('system shell, local settings, skill toggles and files persist; mutations retain same-origin token protection', async t => {
  const { app, base, directory, request } = await setup(t);
  assert.match(await (await fetch(base)).text(), /system-app\.mjs/);
  assert.match(await (await fetch(base + '/grading')).text(), /app\.mjs/);
  assert.equal((await fetch(base + '/api/system/preferences', { method: 'PATCH', body: '{}' })).status, 403);
  assert.equal((await request('/preferences', { displayName: 'No' }, 'PATCH', { Origin: 'https://untrusted.example' })).status, 403);
  assert.equal((await request('/preferences', { displayName: '本地测试', workspaceName: '测试工作区', motion: 'reduce' }, 'PATCH')).status, 200);
  let response = await request('/files', { title: '分析.md', body: '原文' }); assert.equal(response.status, 201); const file = (await response.json()).file;
  assert.equal(await readFile(join(directory, file.relativePath), 'utf8'), '原文');
  assert.equal((await request('/files', { id: file.id, revision: 1, title: '分析.md', body: '新版本' })).status, 201);
  assert.equal((await request('/files', { id: file.id, revision: 1, title: '分析.md', body: '旧请求' })).status, 409);
  assert.equal((await (await request(`/files/${file.id}?revision=1`)).json()).body, '原文');
  assert.equal((await request('/files', { title: '../escape.md', body: 'x' })).status, 422);
  assert.equal((await request('/chat', { goal: 'hello' })).status, 424);
  assert.equal((await request('/skills', { name: '本地能力', instructions: 'Summarize selected files.' })).status, 201);
  const skill = app.system.store.state.skills.at(-1); assert.equal(skill.enabled, false);
  await request(`/skills/${skill.id}`, { enabled: true }, 'PATCH');
  const reopened = await new SystemStore(directory, app.store).init();
  assert.equal(reopened.state.preferences.displayName, '本地测试'); assert.equal(reopened.state.files[0].revision, 2); assert.equal(reopened.state.skills.at(-1).enabled, true);
});
test('general tasks read frozen source versions and isolate conversation history from grading and other chats', async t => {
  let captured, unblock; const ready = new Promise(resolve => { unblock = resolve; });
  const { app, request } = await setup(t, { configured: () => true, systemAgent: async args => {
    captured = args; await ready; const source = await args.readFile(args.catalog[0].id);
    assert.equal(source.body, '未完成，待判定');
    const output = await args.saveFile({ title: '讲义.md', body: '仅引用已保存来源；未定项仍待复核。' });
    return { text: `已保存 ${output.title}` };
  } });
  let source;
  await app.store.mutate(null, state => { source = addDocument(state, { title: '批改阶段报告.md', body: '未完成，待判定' }); state.conversation.push({ role: 'user', text: 'PRIVATE_GRADING_TRANSCRIPT' }); });
  await app.system.store.mutate(state => { state.threads.push({ id: 'other-chat', title: 'other', messages: [{ role: 'user', text: 'UNRELATED_CHAT' }] }); });
  const ref = app.system.store.catalog()[0];
  const response = await request('/chat', { goal: '生成教辅', references: [ref] }); assert.equal(response.status, 202); const threadId = (await response.json()).threadId;
  await app.store.mutate(null, state => saveDocument(state, source.id, { revision: 1, body: '较新的结果' }));
  unblock(); await app.system.active.promise;
  assert.equal(captured.references[0].body, '未完成，待判定'); assert.deepEqual(captured.history, []);
  assert.ok(!JSON.stringify(captured.catalog).includes('PRIVATE_GRADING_TRANSCRIPT'));
  const output = app.system.store.state.files[0]; assert.equal(output.sources[0].hash, ref.hash); assert.equal(output.sources[0].revision, 1);
  const pinned = await (await request(`/files/${encodeURIComponent(ref.id)}?revision=1&hash=${ref.hash}`)).json(); assert.equal(pinned.body, '未完成，待判定');
  assert.equal((await request(`/files/${encodeURIComponent(ref.id)}?revision=2&hash=${ref.hash}`)).status, 409);
  assert.equal(output.status, 'completed');
  const thread = await (await request(`/threads/${threadId}`)).json(); assert.equal(thread.messages.at(-1).status, 'completed'); assert.deepEqual(thread.messages.at(-1).fileIds, [output.id]);
  await request('/files', { id: output.id, revision: 1, title: output.title, body: '手动修订' }); assert.equal(app.system.store.state.files[0].sources[0].hash, ref.hash);
  const stale = { ...ref, hash: 'invalid' }; assert.equal((await request('/chat', { goal: 'x', references: [stale] })).status, 409);
});
test('invalid skill does not strand a running task; cancellation and recovery are honest terminal states', async t => {
  const { app, request, directory } = await setup(t, { configured: () => true, systemAgent: async ({ controller }) => new Promise((_resolve, reject) => controller.signal.addEventListener('abort', () => reject(Error('cancelled')), { once: true })) });
  assert.equal((await request('/chat', { goal: 'x', skillId: 'missing' })).status, 422); assert.equal(app.system.active, null); assert.equal(app.system.store.state.threads.length, 0);
  const response = await request('/chat', { goal: 'cancel test' }); assert.equal(response.status, 202); const entry = app.system.active;
  assert.equal((await request('/chat', { goal: 'parallel' })).status, 409);
  assert.equal((await request('/cancel', {})).status, 202); await entry.promise;
  assert.equal(app.system.store.state.threads[0].messages.at(-1).status, 'cancelled');
  await app.system.store.mutate(state => { state.threads[0].messages.at(-1).status = 'running'; });
  const restored = await new SystemStore(directory, app.store).init(); await restored.recover(); assert.equal(restored.state.threads[0].messages.at(-1).status, 'interrupted');
});
test('HTML preview is sandboxed and cannot execute scripts or request remote content; download preserves bytes', async t => {
  const { request } = await setup(t);
  const body = '<section>本地</section><script>fetch("https://untrusted.example")</script>';
  const file = (await (await request('/files', { title: 'slides.html', body })).json()).file;
  const preview = await request(`/files/${file.id}?preview=1&slide=1`);
  assert.match(preview.headers.get('content-security-policy'), /sandbox; default-src 'none'/);
  assert.ok(!preview.headers.get('content-security-policy').includes('allow-scripts'));
  const download = await request(`/files/${file.id}?download=1`); assert.match(download.headers.get('content-disposition'), /^attachment;/); assert.equal(await download.text(), body);
});

test('opening a personal report preserves its frozen owner and excludes other student pages from its sources', async t => {
  const { app, base } = await setup(t);
  await app.store.mutate(null, state => {
    state.groups = [{ id: 'a', label: '后来重分的答卷', pageIds: ['later'] }];
    state.tasks.push({ id: 't', kind: 'grade', title: '练习', status: 'completed', records: [], groupIds: ['a', 'b'],
      groups: [{ id: 'a', label: '甲', pageIds: ['p1'] }, { id: 'b', label: '乙', pageIds: ['p2'] }],
      scheme: { pageIds: ['shared'] }, artifacts: [{ id: 'r', groupId: 'a', title: '反馈', body: '仅供合成测试' }] });
  });
  const file = app.system.store.catalog()[0];
  assert.deepEqual([file.groupId, file.groupLabel, file.taskTitle], ['a', '甲', '练习']);
  const { token } = await (await fetch(base + '/api/state')).json();
  const response = await fetch(base + '/api/documents', { method: 'POST', headers: { 'X-Workspace-Token': token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskId: 't', artifactId: 'r' }) });
  assert.equal(response.status, 201);
  const { document } = await response.json();
  assert.deepEqual(document.sourcePageIds, ['p1', 'shared']);
  const catalog = app.system.store.catalog();
  assert.equal(catalog.length, 1);
  const edited = app.system.store.readFile(catalog[0].id);
  assert.deepEqual([edited.groupId, edited.groupLabel, edited.category], ['a','甲','个人报告']);
});
