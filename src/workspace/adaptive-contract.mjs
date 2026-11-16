import { digest } from '../core.mjs';
import { fail } from './store.mjs';

export const object = properties => ({ type: 'object', properties, required: Object.keys(properties), additionalProperties: false });
export const text = { type: 'string', minLength: 1, maxLength: 8000 };
export const strings = { type: 'array', uniqueItems: true, items: text, maxItems: 300 };
const nullableNumber = { anyOf: [{ type: 'number', minimum: 0 }, { type: 'null' }] };
export const PLAN_SCHEMA = object({
  subject: text, examSystem: text, implementation: text,
  coverage: { type: 'array', minItems: 1, items: object({ groupId: text, status: { enum: ['complete', 'partial', 'unknown'] }, reason: text }) },
  items: { type: 'array', minItems: 1, maxItems: 500, items: object({
    id: text, groupIds: { ...strings, minItems: 1 }, question: { ...text, description: 'Self-contained original task transcription, including expressions, premises, domains, requested subparts, diagram relationships and shared dependencies. Never just a topic label, student working or a proposed solution.' },
    questionStatus: { enum: ['complete', 'partial', 'unknown'] },
    basis: { enum: ['provided_scheme', 'derived_question', 'answer_context'] },
    sourcePageIds: { ...strings, minItems: 1 },
    disposition: { enum: ['score', 'feedback_only', 'needs_material'] },
    maxScore: nullableNumber, allowedAwards: { type: 'array', uniqueItems: true, maxItems: 500, items: { type: 'number', minimum: 0 }, description: 'Allowed awards under the supplied MS or an explicitly proposed policy bounded by the printed maximum.' },
    scaleBasis: { enum: ['source', 'teacher', 'unknown'] }, scaleQuote: { type: 'string', maxLength: 2000, description: 'Exact source quotation establishing this mark-bearing unit and its maximum. The source need not enumerate a derived partial-credit policy.' }, scalePageIds: strings,
    referenceAnswer: text, criteria: { ...text, description: 'Apply the supplied MS, or explain a suggested numerical award policy including zero, full credit, and partial-credit conditions. Preserve shared printed group totals.' }, rationale: text, uncertainties: { ...strings, description: 'Concrete item-specific doubts only; absence of an official MS alone is not a scoring uncertainty.' }, webReferenceIds: strings,
  }) },
});

export const GRADE_SCHEMA = object({ items: { type: 'array', minItems: 1, maxItems: 500, items: object({
  id: text, score: nullableNumber, verdict: { enum: ['supported', 'partial', 'incorrect', 'unresolved'] },
  reason: text, evidence: { type: 'string', maxLength: 8000 }, studentPageIds: { ...strings, minItems: 1 },
  reviewRequired: { type: 'boolean' },
  uncertainties: { ...strings, description: 'Specific unresolved reading, task or award ambiguities for this item. Use an empty list when only the general provisional nature of the derived policy applies.' },
  referenceCheck: object({ status: { enum: ['consistent', 'conflict', 'not_applicable'] }, observation: { ...text, description: 'Concise check against the original task, not merely agreement with the reference. A conflict requires null score and a concrete explanation.' } }),
}) } });

export function validatePlan(raw, task, delivered, webReferences = new Map()) {
  const plan = structuredClone(raw), ids = new Set(), selected = new Set(task.groupIds);
  fail(plan.items?.length && plan.coverage?.length === selected.size, '需要逐份说明题目覆盖情况。');
  fail(new Set(plan.coverage.map(row => row.groupId)).size === selected.size && plan.coverage.every(row => selected.has(row.groupId)), '覆盖范围与任务不符。');
  const sourcePages = new Map(task.pages.map(page => [page.id, page]));
  const shared = new Set([...(task.scheme?.pageIds || []), ...(task.question?.pageIds || [])]);
  // Source preparation sees question/MS pages first. Answer-only preparation must inspect
  // each selected book, and its recovered questions never become another book's authority.
  const required = shared.size ? shared : new Set(task.groups.flatMap(group => group.pageIds));
  fail([...required].every(id => delivered.has(id)), '先阅读完整题目和标准；仅答卷模式需逐份阅读。');
  for (const item of plan.items) {
    fail(typeof item.id === 'string' && item.id.trim() && !ids.has(item.id), '题目标识重复或无效。'); ids.add(item.id);
    fail(item.groupIds?.length && new Set(item.groupIds).size === item.groupIds.length && item.groupIds.every(id => selected.has(id)), '题目适用范围无效。');
    const own = new Set(task.groups.filter(group => item.groupIds.includes(group.id)).flatMap(group => group.pageIds));
    const refs = [...item.sourcePageIds, ...item.scalePageIds];
    fail(item.sourcePageIds.length, `评分项 ${item.id} 缺少原页引用。`);
    const unknown = [...new Set(refs.filter(id => !sourcePages.has(id)))];
    fail(!unknown.length, `评分项 ${item.id} 引用了不存在的页面 ID：${unknown.join('、')}。请从材料清单复制准确的页面 ID，修正该项后重新准备方案。`);
    const unread = [...new Set(refs.filter(id => !delivered.has(id)))];
    fail(!unread.length, `评分项 ${item.id} 引用了未阅读页面：${unread.join('、')}。请先阅读这些原页。`);
    fail(refs.every(id => shared.has(id) || (item.groupIds.length === 1 && own.has(id))), `评分项 ${item.id} 的原页归属不正确；答卷内依据只能用于其所属答卷。`);
    const roles = item.sourcePageIds.map(id => sourcePages.get(id)?.role);
    fail(item.basis === 'provided_scheme' ? roles.includes('scheme') : item.basis === 'derived_question' ? roles.includes('question') : item.basis === 'answer_context' && item.groupIds.length === 1 && roles.includes('student'), '评分依据类型与来源不符。');
    // Retrieved snippets can inform research, never silently become an official MS.
    fail(item.webReferenceIds.every(id => webReferences.get(id)?.opened), '联网依据必须实际打开，搜索摘要不能作为评分依据。');
    if (item.disposition === 'score') {
      fail(item.questionStatus === 'complete', '题意不完整时不能给数值评分。');
      fail(Number.isFinite(item.maxScore) && item.maxScore > 0, '数值评分需要有依据的满分。');
      fail(item.allowedAwards.length >= 2 && item.allowedAwards.includes(0) && item.allowedAwards.includes(item.maxScore)
        && new Set(item.allowedAwards).size === item.allowedAwards.length
        && item.allowedAwards.every(value => Number.isFinite(value) && value >= 0 && value <= item.maxScore), '给分范围无效。');
      fail(item.scaleQuote.trim(), '请记录该评分单元满分的原文依据。');
      if (item.scaleBasis === 'source') fail(item.scalePageIds.length > 0, '请引用标有分值的原页。');
      else fail(item.scaleBasis === 'teacher' && (task.acceptedGradingRequirements ?? `${task.supplementalInstructions ?? task.goal}\n${task.gradingContext || ''}`).includes(item.scaleQuote), '教师给分范围必须引用本批已核对的要求原文。');
    } else {
      fail(['feedback_only', 'needs_material'].includes(item.disposition) && item.maxScore === null && item.allowedAwards.length === 0, '不能评分的题目保留空分值，不能记零或编造满分。');
      if (item.disposition === 'needs_material') fail(item.uncertainties.length > 0, '请说明当前无法确定的具体内容。');
    }
  }
  fail(task.groupIds.every(id => plan.items.some(item => item.groupIds.includes(id))), '每份答卷必须有明确处理结论。');
  const sourceHash = digest(task.pages.map(({ id, sha256, role }) => ({ id, sha256, role })));
  return { version: 1, sourceHash, hash: digest({ plan, sourceHash }), plan };
}

export function validateAdaptiveGrade(raw, frozen, group, delivered) {
  const expected = frozen.plan.items.filter(item => item.groupIds.includes(group.id));
  fail(group.pageIds.every(id => delivered.has(id)), '先阅读完整的本份答卷。');
  fail(raw.items?.length === expected.length && new Set(raw.items.map(item => item.id)).size === expected.length, '需要覆盖本份答卷的所有评分项目。');
  const items = raw.items.map(result => {
    const criterion = expected.find(item => item.id === result.id);
    fail(criterion, '未知题目。');
    fail(result.studentPageIds?.length && result.studentPageIds.every(id => group.pageIds.includes(id) && delivered.has(id)), '不能引用另一份答卷或未阅读页面。');
    fail(result.score === null || (criterion.disposition === 'score' && criterion.allowedAwards.includes(result.score)), '无依据的分值或超出冻结给分范围。');
    fail(result.score === null || (result.verdict !== 'unresolved' && result.evidence.trim()), '数值评分需要明确、可定位的答卷依据。');
    fail(criterion.disposition !== 'needs_material' || (result.score === null && result.verdict === 'unresolved'), '材料不足的题不能自动定论。');
    fail(!criterion.referenceVerification?.blocking || (result.score === null && result.verdict === 'unresolved'), '标准校核仍有未决冲突，只能保留该项待定。');
    if (criterion.referenceVerification) fail(result.referenceCheck && ['consistent', 'conflict'].includes(result.referenceCheck.status) && result.referenceCheck.observation?.trim(), '请核对已校核标准与原题的一致性。');
    fail(result.referenceCheck?.status !== 'conflict' || (result.score === null && result.verdict === 'unresolved'), '发现评分标准冲突时不能继续给分，需单独说明疑点。');
    const reportedUncertainties = result.uncertainties ?? [];
    fail(Array.isArray(reportedUncertainties) && reportedUncertainties.every(note => typeof note === 'string' && note.trim()), '逐项疑点必须是具体文字说明。');
    const uncertainties = [...new Set([...criterion.uncertainties, ...reportedUncertainties,
      ...(result.referenceCheck?.status === 'conflict' ? [`评分标准冲突：${result.referenceCheck.observation}`] : []),
      ...(result.verdict === 'unresolved' && !reportedUncertainties.length ? [result.reason] : [])])];
    return { ...result, maxScore: criterion.maxScore, basis: criterion.basis, uncertainties,
      reviewRequired: result.reviewRequired || result.score === null || criterion.basis !== 'provided_scheme' || uncertainties.length > 0 };
  });
  const coverage = frozen.plan.coverage.find(row => row.groupId === group.id);
  const complete = coverage.status === 'complete' && items.every(item => item.score !== null);
  return { planHash: frozen.hash, groupId: group.id, items, coverage,
    totalScore: complete ? items.reduce((sum, item) => sum + item.score, 0) : null,
    maximum: complete ? items.reduce((sum, item) => sum + item.maxScore, 0) : null,
    knownScore: items.some(item => item.score !== null) ? items.reduce((sum, item) => sum + (item.score ?? 0), 0) : null,
    provisional: items.some(item => item.basis !== 'provided_scheme'),
    reviewRequired: !complete || items.some(item => item.reviewRequired) };
}

export function adaptiveGuideMarkdown(frozen) {
  const basis = { provided_scheme: '用户提供的 MS', derived_question: '根据题目推导 · 建议标准', answer_context: '依据本份答卷内容 · 建议标准' };
  const disposition = { score: '评分', feedback_only: '定性反馈', needs_material: '暂不能确定' };
  const lines = ['# 评分实施说明', '', frozen.plan.implementation, '', `学科：${frozen.plan.subject}`, `考试体系：${frozen.plan.examSystem}`, '',
    '推导标准不代表官方评分。题意、满分或给分依据不足时保留待定或仅提供定性反馈。', ''];
  for (const item of frozen.plan.items) lines.push(`## ${item.id}`, '', `依据：${basis[item.basis]}`, `处理：${disposition[item.disposition]}；满分：${item.maxScore ?? '未确定'}`,
    `适用答卷：${item.groupIds.join('、')}`, '', item.question, '', `参考解答：${item.referenceAnswer}`, '', `评分条件：${item.criteria}`, '',
    `依据说明：${item.rationale}`, `分值来源：${item.scaleQuote || '未确定'}`, `原页：${item.sourcePageIds.join('、')}`, `联网引用：${item.webReferenceIds.join('、') || '无'}`,
    ...(item.referenceVerification ? [`标准独立校核：${{ confirmed: '已核对', corrected: '已修正，保留复核说明', unresolved: '未确定，该项暂不赋分' }[item.referenceVerification.status]}`, ...item.referenceVerification.checks.map(check => `- ${check.method}：${check.observation}`)] : []),
    ...item.uncertainties.map(note => `- 待确认：${note}`), '');
  for (const row of frozen.plan.coverage) lines.push(`- ${row.groupId} 覆盖情况：${row.status}。${row.reason}`);
  return lines.join('\n');
}
