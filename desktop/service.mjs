import { readFile, rename, writeFile } from 'node:fs/promises';
import { dirname, join, delimiter } from 'node:path';
import { fileURLToPath } from 'node:url';

// This process and its grading workers use Electron's embedded Node runtime.
const runtime = fileURLToPath(new URL('../../runtime/', import.meta.url));
const windows = process.platform === 'win32';
process.env.PI_WORKSPACE_PYTHON = join(runtime, 'python', windows ? 'python.exe' : 'bin/python3.12');
process.env.PATH = [join(runtime, 'poppler', 'bin'), process.env.PATH].filter(Boolean).join(delimiter);
process.env.POPPLER_DATADIR = join(runtime, 'poppler', 'share', 'poppler');
process.env.GRADEOS_PDF_FONT = join(runtime, 'fonts', 'NotoSansSC.ttf');
process.env.PYTHONUTF8 = '1';
process.env.PYTHONNOUSERSITE = '1';
process.env.PYTHONDONTWRITEBYTECODE = '1';
if (!windows) {
  process.env.GRADEOS_VISION_EXECUTABLE = join(runtime, 'gradeos-vision');
  process.env.FONTCONFIG_FILE = join(runtime, 'poppler', 'fonts.conf');
}

let workspace;
process.once('disconnect', async () => {
  try { await workspace?.close(); } finally { process.exit(); }
});
try {
  const { createWorkspaceServer } = await import('../src/workspace/server.mjs');
  const directory = process.argv[2], portFile = join(dirname(directory), 'desktop-port');
  // The web editor keys unsaved drafts by origin. Reuse the last port when possible.
  let port = 0;
  try {
    const saved = Number(await readFile(portFile, 'utf8'));
    if (Number.isInteger(saved) && saved >= 1024 && saved <= 65535) port = saved;
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  try {
    workspace = await createWorkspaceServer({ directory, port });
  } catch (error) {
    if (!port || error.code !== 'EADDRINUSE') throw error;
    workspace = await createWorkspaceServer({ directory, port: 0 });
  }
  const bound = workspace.server.address().port;
  workspace.server.on('workspace-signed-in', () => { if (process.connected) process.send({signedIn:true}); });
  if (bound !== port) {
    await writeFile(portFile + '.tmp', String(bound), { mode: 0o600 });
    await rename(portFile + '.tmp', portFile);
  }
  process.send({ port: bound });
} catch (error) {
  if (process.connected) process.send({ error: error.message }, () => process.exit(1));
  else process.exit(1);
}
