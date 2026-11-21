import { batchReport, reportSummaryMarkdown } from '../../web/grading-library.mjs';
import { cohortResults, cohortSummary } from '../../web/results-view.mjs';

const resultTime = task => task.finishedAt || task.completedAt || task.updatedAt || task.createdAt || '';

export function hasGradingOutput(task) {
  if (batchReport(task)?.body.trim()) return true;
  const students = new Set((task.groups || []).map(group => group.id));
  return task.records?.some(record => students.has(record.groupId))
    || task.artifacts?.some(file => students.has(file.groupId) && typeof file.body === 'string' && file.body.trim());
}

function classExcerpt(state, task) {
  const report = batchReport(task);
  if (!report) return '';
  const saved = state.documents?.findLast(doc => doc.taskId === task.id && doc.artifactId === report.id && doc.groupId == null && doc.revision > 1);
  const summary = reportSummaryMarkdown(saved ? saved.body : report.body)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/^(?:>\s*|[-*+]\s+)/gm, '')
    .replace(/\*\*|__|`/g, '').replace(/\s+/g, ' ').trim();
  const excerpt = Array.from(summary.slice(0, 242)).slice(0, 121);
  return excerpt.length > 120 ? excerpt.slice(0, 120).join('').trimEnd() + '…' : excerpt.join('');
}

export function recentGradingResults(state) {
  const terminal = state.tasks.filter(task => task.kind === 'grade' && ['completed','needs_review'].includes(task.status))
    .sort((a, b) => resultTime(b).localeCompare(resultTime(a)));
  const results = [];
  for (const task of terminal) {
    if (!hasGradingOutput(task)) continue;
    const {recorded, pending, scored, mean, maximum, commonDeduction} = cohortSummary(cohortResults(state, task), task);
    const excerpt = classExcerpt(state, task) || (commonDeduction ? `第 ${commonDeduction.id} 题有 ${commonDeduction.count} 份答卷失分。` : '');
    results.push({id:task.id, title:task.title, status:task.status, completedAt:task.finishedAt || task.completedAt || null,
      submissionCount:task.groups?.length ?? task.groupIds?.length, excerpt, recorded, pending, scored, mean, maximum});
    if (results.length === 6) break;
  }
  return results;
}
