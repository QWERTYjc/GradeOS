import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

const readJson = async path => { try { return JSON.parse(await readFile(path, 'utf8')); } catch { return null; } };
const nonnegative = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
const phaseLabels = { preparing: '准备材料', coordination: '安排批改', ms_compilation: '整理评分标准',
  ms_verification: '核对评分标准', student_grading: '批改答卷', exception_review: '核对例外给分',
  source_permission_review: '核对源规则', student_feedback: '生成个人反馈', reporting: '整理汇总报告' };

// Project local artifacts only. Completion, review and billing remain independent.
export async function collectGradingProgress({ task, output, summary, gradingSaved, records, rubricReady, final }) {
  const candidate = await readJson(join(output, 'progress.json'));
  const expected = new Set(task.groups.map(group => group.id));
  const valid = candidate?.version === 1 && candidate.students?.length === expected.size
    && new Set(candidate.students.map(row => row.id)).size === expected.size
    && candidate.students.every(row => expected.has(row.id));
  const live = valid ? candidate : null;
  const students = summary?.students ?? live?.students?.map(row => ({ ...row, student_id: row.id })) ?? [];
  const artifacts = [];
  for (const group of task.groups) {
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(group.id)) continue;
    const student = students.find(row => row.student_id === group.id);
    if (student?.feedback_status !== 'submitted') continue;
    try {
      const body = await readFile(join(output, `feedback-${group.id}/REPORT.zh-CN.md`), 'utf8');
      artifacts.push({ id: `${task.id}-student-${group.id}`, title: `${group.label} · 个人报告`, body,
        groupId: group.id, references: records.filter(record => record.groupId === group.id).map(record => record.id) });
    } catch { /* A submitted but missing file is not advertised as readable. */ }
  }
  if (final && summary?.report_submitted) {
    try {
      const body = await readFile(join(output, 'REPORT.zh-CN.md'), 'utf8');
      artifacts.unshift({ id: `${task.id}-report`, title: '汇总报告', body, references: records.map(record => record.id) });
    } catch { /* No fabricated report link. */ }
  }
  const fallback = rubricReady ? gradingSaved === task.groups.length ? '整理报告' : '批改答卷' : '整理评分标准';
  const active = [...new Set((live?.active_phases ?? []).map(phase => phaseLabels[phase]).filter(Boolean))];
  const elapsed = nonnegative(summary?.elapsed_including_preparation_seconds ?? summary?.elapsed_including_image_preparation_seconds ?? summary?.elapsed_seconds ?? live?.elapsed_seconds);
  const settledCost = nonnegative(summary?.provider_reported_cost_usd ?? live?.settled_cost_usd);
  const unknownCostRequests = nonnegative(summary?.unknown_cost_requests ?? live?.requests?.unknown_cost);
  return { artifacts, progress: {
    // Existing consumers use completed for grades persisted, never estimated work or model tokens.
    completed: gradingSaved, total: task.groups.length,
    feedbackCompleted: artifacts.filter(artifact => artifact.groupId).length,
    phase: live?.status === 'stopping' ? '停止任务并保存结果' : active.length ? active.join('、') : phaseLabels[live?.phase] ?? fallback,
    stopping: live?.status === 'stopping', elapsedSeconds: elapsed, settledCostUsd: settledCost,
    unknownCostRequests, costComplete: Boolean(final && summary?.cost_receipts_complete),
  } };
}
