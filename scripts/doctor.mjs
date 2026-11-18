import { spawnSync } from 'node:child_process';
import { pythonExecutable } from '../src/python.mjs';

const checks = [
  ['Node >=22.19', Number(process.versions.node.split('.')[0]) > 22 || (Number(process.versions.node.split('.')[0]) === 22 && Number(process.versions.node.split('.')[1]) >= 19)],
  ['Python >=3.11, Pillow, NumPy, pypdf, reportlab', spawnSync(pythonExecutable(), ['-c', 'import sys, PIL, numpy, pypdf, reportlab; assert sys.version_info >= (3, 11)'], { stdio: 'ignore' }).status === 0],
  ...['pdfinfo', 'pdftoppm'].map(command => [command, spawnSync(command, ['-v'], { stdio: 'ignore' }).status === 0]),
];
for (const [name, ok] of checks) console.log(`${ok ? 'OK' : 'MISSING'} ${name}`);
console.log(`Model credential: ${process.env.OPENROUTER_API_KEY ? 'configured' : 'not configured (offline work is available)'}`);
process.exitCode = checks.every(([, ok]) => ok) ? 0 : 1;
