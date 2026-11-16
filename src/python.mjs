import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

export const projectRoot = fileURLToPath(new URL('../', import.meta.url));

export function pythonExecutable() {
  if (process.env.PI_WORKSPACE_PYTHON) return process.env.PI_WORKSPACE_PYTHON;
  const local = join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return existsSync(local) ? local : 'python3';
}
