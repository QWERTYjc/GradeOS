import test from 'node:test';
import assert from 'node:assert/strict';
import { digest } from '../src/core.mjs';
import { exceptionProbeFixture } from '../src/exception-probe-fixture.mjs';
import { renderStudentFeedback } from '../src/student-report-markdown.mjs';
import { renderReportMarkdown } from '../src/report-markdown.mjs';
import { markdown } from '../web/ui.mjs';

test('student presentation preserves the complete ledger, source rules, null and review even with a neutral feedback layer', () => {
  const { primary: grade, frozen } = exceptionProbeFixture();
  grade.items[0].score = null; grade.total_score = null;
  const before = digest({ grade, frozen });
  const feedback = { grade_hash: digest(grade), rubric_hash: frozen.hash, version: 5,
    summary: '本次总分待定。先核对来源，再按评分条件复做。', strengths: [], priorities: [],
    items: grade.items.map(item => ({ item_id: item.item_id, assessment: '以已保存的评分点记录为准。', next_step: '核查本题适用条件。', review_recommended: false, review_reason: '' })) };
  const body = renderStudentFeedback('opaque-owner-id', grade, frozen, feedback);
  assert.match(body, /\*\*待定 \/ 18\*\*/);
  assert.match(body, /\| \[Oak-input\].*待定 \/ 1/);
  assert.match(body, /原批改标记需复核/);
  assert.ok(!body.split('## 学习总结')[0].includes('opaque-owner-id'));
  for (const item of grade.items) {
    assert.ok(body.includes(item.reason));
    for (const point of item.point_decisions) {
      const source = frozen.artifact.items.find(rule => rule.item_id === item.item_id).scoring_points.find(p => p.point_id === point.point_id);
      for (const fact of [point.evidence, point.reason, source.condition, source.source_text]) assert.ok(body.includes(fact), fact);
    }
  }
  for (const rule of frozen.artifact.general_instructions) assert.ok(body.includes(rule.text));
  assert.equal(digest({ grade, frozen }), before);
  const html = markdown(body);
  assert.equal((html.match(/<details class=/g) ?? []).length, grade.items.length + 1);
  assert.doesNotMatch(html, /<script/);
});

function cohort(sources = 2, requested = 2) {
  const report = { title: '批改汇总', executive_summary: '依据已保存结果。', records_read: ['a', 'b'], analysis_sections: [], review_priorities: [], learning_observations: [], limitations: [] };
  const analysis = { cohort_context: { unique_answer_sources: sources }, coverage: { requested_records: requested, scored_records: 1 },
    gradeos_class_report: { average_score: 70, pass_rate: 1, score_distribution: { B: 1 } },
    harness_repeatability: { score_distribution: { 70: 1 }, constant_items: 0, item_count: 1, population_sd: 0,
      items: [{ item_id: 'Q', max_score: 1, mean_score_rate: 0, score_distribution: { 0: 1, None: 1 }, unknown_count: 1, varies: true }] }, methods: [] };
  const index = { records: [{ student_id: 'a', feedback_status: 'failed' }, { student_id: 'b', feedback_status: 'unavailable' }] };
  return renderReportMarkdown(report, analysis, { index });
}
test('real cohort presentation separates missing values from zero and gives teacher results priority over execution metadata', () => {
  const body = cohort();
  assert.ok(body.indexOf('## 学生个人反馈') < body.indexOf('## 费用与耗时'));
  assert.match(body, /1 条有效；待定 \/ 缺失 1/);
  assert.match(body, /0 分 × 1；待定 × 1/);
  assert.doesNotMatch(body, /\*\*有波动\*\*|未见波动|### 重复评分的一致性/);
  assert.match(body, /生成未完成/); assert.match(body, /未生成/);
});
test('only multiple runs of one answer receive repeated-grading stability language', () => {
  assert.match(cohort(1), /同一答卷重复批改的稳定性/);
  assert.match(cohort(1), /不能用于推断真实班级/);
  assert.match(cohort(1), /### 重复评分的一致性/);
  assert.doesNotMatch(cohort(1, 1), /### 重复评分的一致性|### 总分分布/);
});
