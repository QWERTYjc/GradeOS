import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

export const projectRoot = fileURLToPath(new URL('../', import.meta.url));

export function pythonExecutable() {
  if (process.env.PI_WORKSPACE_PYTHON) return process.env.PI_WORKSPACE_PYTHON;
  const local = join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return existsSync(local) ? local : 'python3';
}


// Document helpers need their runtime, fonts, and OS paths, never model credentials.
export function helperEnvironment() {
  const names = ['PATH', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LOCALAPPDATA',
    'POPPLER_DATADIR', 'FONTCONFIG_FILE', 'GRADEOS_PDF_FONT', 'PYTHONUTF8', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE'];
  return Object.fromEntries(names.filter(name => process.env[name]).map(name => [name, process.env[name]]));
}
