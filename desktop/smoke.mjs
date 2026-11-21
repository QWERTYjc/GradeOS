// Exercise the installed, relocated payload using synthetic documents and no model calls.
import assert from 'node:assert/strict';
import { execFileSync, fork } from 'node:child_process';
import { once } from 'node:events';
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'node:net';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

if (!process.argv[2]) throw Error('Usage: node desktop/smoke.mjs INSTALLED_EXECUTABLE [checks-directory]');
const exe = resolve(process.argv[2]), win = process.platform === 'win32';
const resources = win ? join(dirname(exe), 'resources') : resolve(dirname(exe), '../Resources');
const app = join(resources, 'app'), runtime = join(resources, 'runtime');
const checks = resolve(process.argv[3] || join(import.meta.dirname, '../runs'));
await mkdir(checks, { recursive: true });
const scratch = await mkdtemp(join(checks, 'desktop-smoke-'));
const directory = join(scratch, '教师 workspace');
const env = { ELECTRON_RUN_AS_NODE: '1', PATH: win ? join(process.env.SystemRoot, 'System32') : '/usr/bin:/bin' };
for (const name of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LOCALAPPDATA', 'USERPROFILE', 'HOME']) {
  if (process.env[name]) env[name] = process.env[name];
}
const embedded = JSON.parse(execFileSync(exe, ['-p', 'JSON.stringify({platform:process.platform, arch:process.arch})'],
  { env, encoding: 'utf8', timeout: 180000 }));
const python = join(runtime, 'python', win ? 'python.exe' : 'bin/python3.12');
const fixture = join(scratch, '合成 答卷.pdf');
execFileSync(python, ['-c', [
  'from reportlab.pdfgen import canvas', 'import sys', 'c = canvas.Canvas(sys.argv[1], pagesize=(220, 180))',
  'c.drawString(20, 90, "GradeOS synthetic PDF: 2 + 2 = 4")', 'c.rect(20, 40, 60, 20)', 'c.save()',
].join('\n'), fixture], { env: { ...env, PYTHONNOUSERSITE: '1', PYTHONDONTWRITEBYTECODE: '1' } });

let child, exited;
async function start() {
  child = fork(join(app, 'desktop/service.mjs'), [directory], { execPath: exe, env, execArgv: [],
    stdio: ['ignore', 'inherit', 'inherit', 'ipc'], windowsHide: true });
  exited = once(child, 'exit');
  const [ready] = await Promise.race([once(child, 'message', { signal: AbortSignal.timeout(180000) }),
    exited.then(([code]) => { throw Error('Installed service exited ' + code); })]);
  assert.ok(ready.port, ready.error || 'Missing local port');
  return 'http://127.0.0.1:' + ready.port;
}
async function stop() {
  if (child?.connected) child.disconnect();
  if (!exited) return;
  const deadline = setTimeout(() => child.kill('SIGKILL'), 20000);
  try { await exited; } finally { clearTimeout(deadline); }
}
try {
  let base = await start();
  assert.match(await (await fetch(base)).text(), /<title>GradeOS/);
  const { token } = await (await fetch(base + '/api/state')).json();
  const bytes = await readFile(fixture);
  for (const role of ['student', 'scheme']) {
    const response = await fetch(base + '/api/uploads?' + new URLSearchParams({ role, name: '合成材料.pdf', receipt: '1' }),
      { method: 'POST', headers: { 'x-workspace-token': token }, body: bytes });
    const receipt = await response.json();
    assert.equal(response.status, 201, JSON.stringify(receipt)); assert.equal(receipt.pages, 1);
  }
  await stop();
  const stateFile = join(directory, 'workspace.json');
  const state = JSON.parse(await readFile(stateFile, 'utf8')), group = state.groups[0];
  const page = state.pages.find(row => row.id === group.pageIds[0]);
  assert.ok(page.size[0] > 220, 'The vector PDF was not rasterized at print resolution');
  // Replay a saved synthetic review so that the normal PDF export route is exercised offline.
  const task = { id: 'synthetic', title: '合成测试', kind: 'grade', status: 'needs_review',
    groups: [group], pages: state.pages, scheme: state.schemes[0], groupIds: [group.id],
    records: [{ id: 'r', groupId: group.id, itemId: '1', pointId: 'method', score: null, maximum: 1,
      evidence: '2 + 2 = 4', reason: '合成批注', studentPageIds: [page.id], schemePageIds: [], reviewRequired: true, originalHash: 'synthetic' }] };
  state.tasks.push(task);
  await writeFile(stateFile, JSON.stringify(state));
  const originalOrigin = base;
  base = await start();
  assert.equal(base, originalOrigin, 'Desktop editor drafts need a stable origin after restart');
  const response = await fetch(base + '/api/tasks/synthetic/annotated.pdf?groupId=' + group.id);
  const result = Buffer.from(await response.arrayBuffer());
  assert.equal(response.status, 200, result.subarray(0, 200).toString());
  assert.equal(result.subarray(0, 5).toString(), '%PDF-');
  const exported = join(scratch, '批注.pdf');
  await writeFile(exported, result);
  const verify = 'from pypdf import PdfReader; import sys; p=PdfReader(sys.argv[1]); assert len(p.pages)>=2; assert "合成" in "".join(page.extract_text() for page in p.pages)';
  execFileSync(python, ['-c', verify, exported], { env: { ...env, PYTHONUTF8: '1', PYTHONNOUSERSITE: '1', PYTHONDONTWRITEBYTECODE: '1' } });
  await stop();
  const busy = createServer();
  await new Promise((ok, fail) => busy.once('error', fail).listen(Number(new URL(base).port), '127.0.0.1', ok));
  try {
    const other = await start();
    assert.notEqual(other, base);
    assert.equal((await (await fetch(other + '/api/state')).json()).pages.length, 2);
    await stop();
  } finally { await new Promise(done => busy.close(done)); }
  const { prepareTaskInput } = await import(pathToFileURL(join(app, 'src/workspace/documents.mjs')));
  const input = await prepareTaskInput({ directory }, task);
  const args = [join(app, 'src/run-cohort.mjs'), '--manifest', input.manifest, '--output', input.output,
    '--scripted', '--annotation-grid', '--json'];
  const runtimeEnv = { ...env, PI_WORKSPACE_PYTHON: python, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1', PYTHONNOUSERSITE: '1' };
  if (!win) { args.push('--local-ocr'); runtimeEnv.GRADEOS_VISION_EXECUTABLE = join(runtime, 'gradeos-vision'); }
  const plan = execFileSync(exe, args, { env: runtimeEnv, cwd: app, encoding: 'utf8', timeout: 120000 });
  assert.equal(JSON.parse(plan.trim()).status, 'preflight_only');
  console.log(JSON.stringify({ ...embedded, vectorPdfImport: true,
    savedWorkReopened: true, chinesePdfExport: true, bundledWorkerPreflight: true, modelRequests: 0, scratch }));
} finally { await stop(); }
