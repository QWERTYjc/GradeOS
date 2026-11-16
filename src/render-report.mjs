import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { renderReportMarkdown } from './report-markdown.mjs';

// Offline presentation refresh; no provider imports, credentials or model requests.
const { values } = parseArgs({ options: { 'report-dir': { type: 'string' } } });
if (!values['report-dir']) throw Error('Required: --report-dir existing-report-directory');
const output = resolve(values['report-dir']);
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const json = async (name, optional = false) => {
  try { return JSON.parse(await readFile(resolve(output, name), 'utf8')); }
  catch (error) { if (optional && error.code === 'ENOENT') return undefined; throw error; }
};
const frozen = async name => {
  const bytes = await readFile(resolve(output, name));
  const expected = (await readFile(resolve(output, name.replace(/\.json$/, '.sha256')), 'utf8')).trim();
  if (sha256(bytes) !== expected) throw Error(`Frozen artifact changed: ${name}`);
  return JSON.parse(bytes.toString('utf8'));
};
const [report, analysis, index, summary, costs, presentation] = await Promise.all([
  frozen('report.json'), frozen('gradeos-analysis.json'), frozen('results/index.json'),
  json('summary.json', true), json('cost-accounting.json', true), json('report-presentation.json', true),
]);
if (report.analysis_hash !== analysis.analysis_hash || report.result_set_hash !== analysis.result_set_hash ||
    report.result_set_hash !== index.result_set_hash) throw Error('Report evidence binding differs');
const sourceCohort = summary?.source_cohort;
const sourceSummary = sourceCohort ? JSON.parse(await readFile(resolve(sourceCohort, 'summary.json'), 'utf8')) : undefined;
const result = renderReportMarkdown(report, analysis, { output, index, summary, costs, sourceSummary, sourceCohort, presentation });
await writeFile(resolve(output, 'REPORT.zh-CN.md'), result);
console.log(JSON.stringify({ report: resolve(output, 'REPORT.zh-CN.md'), records: report.records_read.length,
  changed_artifact: 'Markdown presentation only', model_calls: 0 }));
