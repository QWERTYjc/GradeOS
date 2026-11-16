import { spawn } from 'node:child_process';
import { projectRoot, pythonExecutable } from '../src/python.mjs';

const child = spawn(pythonExecutable(), process.argv.slice(2), { cwd: projectRoot, stdio: 'inherit' });
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => child.kill(signal));
