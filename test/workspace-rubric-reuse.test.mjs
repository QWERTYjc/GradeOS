import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { digest } from '../src/core.mjs';
import { freezeRubric, validateFrozenRubric } from '../src/rubric-contract.mjs';
import { prepareTaskInput } from '../src/workspace/documents.mjs';
import { WorkspaceRunner, snapshotFrozenRubric, canReuseScheme } from '../src/workspace/runner.mjs';
import { execFileSync } from 'node:child_process';
import { experimentRoot } from '../src/workspace/documents.mjs';

async function setup(t) {
  const directory = await mkdtemp(join(tmpdir(), 'pi-ms-source-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const sourceDir = join(directory, 'uploads', 'source'); await mkdir(sourceDir, { recursive: true });
  const source = Buffer.from('immutable source document'), sha256 = digest(source);
  await writeFile(join(sourceDir, 'source'), source);
  const pages = [];
  for (let n = 1; n <= 2; n++) {
    const bytes = Buffer.from(`page ${n}`), path = join(sourceDir, `p${n}.png`); await writeFile(path, bytes);
    pages.push({ id: `p${n}`, sourceId: 'source', sourcePage: n, sha256: digest(bytes), path });
  }
  await writeFile(join(sourceDir, 'manifest.json'), JSON.stringify({ sha256, pages: pages.map(p => ({ page: p.sourcePage, sha256: p.sha256 })) }));
  const scheme = { id: 'source', sha256, pageIds: pages.map(p => p.id) };
  const task = { id: 'valid', kind: 'grade', scheme, groups: [{ id: 'student', pageIds: ['p1'] }], pages };
  const frozen = freezeRubric({ general_instructions: [], unresolved_notes: [], items: [{ question_id: 'X', item_id: 'X(a)', max_score: 1,
    criteria: 'Supported method', source_pages: [1, 2], related_item_ids: [], uncertainties: [], requires_source_image: false, image_reason: '' }] },
  { sha256, pages: [{ page: 1 }, { page: 2 }] }, new Set([1, 2]));
  return { directory, sourceDir, task, frozen };
}

test('uploaded MS retains original document identity so an existing frozen rubric can be verified without compilation', async t => {
  const f = await setup(t), input = await prepareTaskInput({ directory: f.directory }, f.task);
  const cohort = JSON.parse(await readFile(input.manifest));
  const scheme = JSON.parse(await readFile(join(cohort.scheme_input, 'manifest.json'))).documents.scheme;
  assert.equal(scheme.sha256, f.task.scheme.sha256);
  assert.equal(validateFrozenRubric(f.frozen, scheme).hash, f.frozen.hash);
  const sourcePath = join(f.directory, 'existing.json'), bytes = JSON.stringify(f.frozen);
  await writeFile(sourcePath, bytes); await writeFile(join(f.directory, 'existing.sha256'), digest(bytes));
  const snapshot = await snapshotFrozenRubric(sourcePath, input.directory, scheme);
  assert.equal(await readFile(snapshot, 'utf8'), bytes);
  execFileSync(process.execPath, [join(experimentRoot, 'src/run-cohort.mjs'), '--manifest', input.manifest,
    '--output', input.output, '--rubric', snapshot], { cwd: experimentRoot, stdio: 'pipe' });
  const plan = JSON.parse(await readFile(join(input.output, 'plan.json')));
  assert.equal(plan.rubric_reuse.file_sha256, digest(bytes));
});

test('altered source, reordered pages and mismatched frozen artifacts stop before a model process starts', async t => {
  const f = await setup(t);
  await assert.rejects(prepareTaskInput({ directory: f.directory }, { ...f.task, id: 'reordered', scheme: { ...f.task.scheme, pageIds: ['p2', 'p1'] } }), /页序/);
  const rubricPath = join(f.directory, 'wrong-rubric.json');
  await writeFile(rubricPath, JSON.stringify({ ...f.frozen, hash: 'wrong' }));
  await writeFile(join(f.directory, 'wrong-rubric.sha256'), digest(await readFile(rubricPath)));
  const runner = new WorkspaceRunner({ directory: f.directory }, { rubricPath });
  const entry = { controller: new AbortController(), child: null };
  await assert.rejects(runner.execute({ ...f.task, id: 'wrong-rubric' }, entry), /Frozen rubric/);
  assert.equal(entry.child, null);
  await writeFile(join(f.sourceDir, 'source'), 'changed source');
  await assert.rejects(prepareTaskInput({ directory: f.directory }, { ...f.task, id: 'changed' }), /原件已改变/);
});

test('automatic reuse retains the selected source model, thinking effort and image quality', () => {
  const model = 'qwen/qwen4-max';
  const plan = {scheme_image_owner:'main', image_quality:'medium', model_roles:{main:{model:{id:model}}}, reasoning:'high'};
  assert.ok(canReuseScheme(plan, model, 'high'));
  assert.ok(!canReuseScheme(plan, 'qwen/qwen3.8-flash', 'high'));
  assert.ok(!canReuseScheme(plan, model, 'low'));
  for (const override of [{scheme_image_owner:null}, {image_quality:'high'}, {rubric_reuse:{}}]) {
    assert.ok(!canReuseScheme({...plan, ...override}, model, 'high'));
  }
});
