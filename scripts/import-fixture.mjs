import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, readFile, rename, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { parseArgs } from 'node:util';
import { pythonExecutable, projectRoot } from '../src/python.mjs';
import { WorkspaceStore } from '../src/workspace/store.mjs';
import { importUpload } from '../src/workspace/documents.mjs';
import { digest } from '../src/core.mjs';

const { values } = parseArgs({ options: { fixture: { type: 'string', default: 'm2' }, data: { type: 'string' } } });
if (!values.data) throw Error('Required: --data new-workspace-directory (existing workspaces are never overwritten)');
const directory = resolve(values.data);
// Reserve a fresh workspace exclusively before any preparation; never race a running workspace.
await mkdir(directory, { recursive: false });
const temporary = await mkdtemp(join(tmpdir(), 'pi-fixture-'));
try {
  await promisify(execFile)(pythonExecutable(), [join(projectRoot, 'scripts/fixtures.py'), 'prepare', '--fixture', values.fixture, '--output', join(temporary, 'prepared')], { cwd: projectRoot, timeout: 180000, maxBuffer: 1024 * 1024 });
  const prepared = join(temporary, 'prepared');
  const uploads = JSON.parse(await readFile(join(prepared, 'uploads.json'), 'utf8'));
  const store = await new WorkspaceStore(directory).init();
  for (const upload of uploads) {
    const bytes = await readFile(join(prepared, upload.path));
    if (digest(bytes) !== upload.sha256) throw Error('Prepared input hash mismatch');
    await importUpload(store, { bytes, name: `${upload.role}.pdf`, role: upload.role });
  }
  console.log(JSON.stringify({ directory, pages: store.state.pages.length, groups: store.state.groups.length, labels_loaded: false, model_requests: 0 }));
} catch (error) {
  // Retain partially imported material for inspection, without masquerading as a complete import.
  await rename(directory, `${directory}.failed-${Date.now()}`);
  throw error;
} finally {
  await rm(temporary, { recursive: true, force: true });
}
