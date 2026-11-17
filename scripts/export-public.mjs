// Create a code-only snapshot. This never changes GitHub visibility or rewrites history.
import { execFileSync } from 'node:child_process';
import { readFile, writeFile, mkdir, lstat } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { createHash } from 'node:crypto';

const destination = process.argv[2];
if (!destination) throw Error('Usage: node scripts/export-public.mjs NEW_OUTPUT_DIRECTORY');
const root = resolve(import.meta.dirname, '..'), output = resolve(destination);
await mkdir(output, { recursive: false, mode: 0o700 });
const paths = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], { cwd: root }).toString().split('\0').filter(Boolean);
const excluded = path => /^(?:evals\/(?:fixtures|medly)\/|runs\/|\.workspace|\.env(?:$|\.(?!example$)))/.test(path);
const suspicious = [ /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, /\b(?:sk-or-v1-|sk-proj-|ghp_|github_pat_)[A-Za-z0-9_-]{24,}\b/, /\bAKIA[A-Z0-9]{16}\b/ ];
const manifest = [], omitted = [], findings = [];
for (const path of [...new Set(paths)].sort()) {
  if (excluded(path)) { omitted.push(path); continue; }
  const source = join(root, path); if (!(await lstat(source)).isFile()) throw Error(`Unsupported source entry: ${path}`);
  const bytes = await readFile(source), text = bytes.toString('utf8');
  if (suspicious.some(pattern => pattern.test(text))) findings.push(path);
  const target = join(output, path); await mkdir(dirname(target), { recursive: true }); await writeFile(target, bytes);
  manifest.push({ path, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
}
if (findings.length) throw Error(`Potential credentials require review (values redacted): ${findings.join(', ')}`);
await writeFile(join(output, 'PUBLIC_SOURCE_MANIFEST.json'), JSON.stringify({ format: 1, license: 'GPL-3.0-only', gitHistoryIncluded: false, excludedEvaluationFiles: omitted.length, files: manifest }, null, 2) + '\n');
console.log(JSON.stringify({ output, files: manifest.length, excludedEvaluationFiles: omitted.length, credentialPatternMatches: findings.length, gitHistoryIncluded: false }));
