import { digest } from './core.mjs';

export function markingGuideMarkdown(frozen, implementation, previousDraft = null) {
  if (typeof implementation !== 'string' || !implementation.trim() || implementation.length > 16000) throw Error('Write concise implementation instructions in Markdown');
  // A later batch proposes the teacher's latest document verbatim, avoiding nested copies
  // of earlier guides or silently undoing edits. It must still be confirmed for this batch.
  if (previousDraft?.body?.trim()) {
    if (previousDraft.body.length > 120000) throw Error('Implementation guide is too long');
    return previousDraft.body;
  }
  const pageText = pages => pages.map(page => `[MS 第 ${page} 页](#ms-page-${page})`).join('、');
  const lines = ['# 评分实施说明', '', '## 执行方法', '', implementation.trim(), ''];
  lines.push('## 通用规则', '');
  for (const rule of frozen.artifact.general_instructions) lines.push(`- ${rule.text || rule.instruction || rule.rule || JSON.stringify(rule)}（${pageText(rule.source_pages || [])}）`);
  if (!frozen.artifact.general_instructions.length) lines.push('原 MS 未单列通用规则；按各题条文执行。');
  for (const item of frozen.artifact.items) {
    lines.push('', `## ${item.item_id} · ${item.max_score} 分`, '', `来源：${pageText(item.source_pages)}`, '', item.criteria || '', '');
    for (const point of item.scoring_points || []) {
      lines.push(`### ${point.point_id} · ${point.award_type || ''} · ${point.max_score} 分`, '', point.source_text,
        '', `- 给分条件：${point.condition}`, `- 可给分值：${point.allowed_awards.join('、')}`,
        `- 前置条件：${point.depends_on.length ? point.depends_on.join('、') : '无额外的无条件前置评分点'}`, `- 来源：${pageText(point.source_pages)}`, '');
    }
    for (const route of item.routes || []) lines.push(`- 解题路径 ${route.route_id}：${route.point_ids.join(' → ')}${route.description ? `。${route.description}` : ''}`);
    if (item.requires_source_image) lines.push('', `> 需对照原图：${item.image_reason || '检查相关原页的图示或符号。'}`);
    for (const issue of item.uncertainties || []) lines.push('', `> 待确认：${issue}`);
  }
  lines.push('', '## 待确认与复核', '', ...(frozen.artifact.unresolved_notes.length ? frozen.artifact.unresolved_notes.map(note => `- ${note}`) : ['- 未另列全卷疑点。']),
    '- 无法辨认、来源冲突或规则不足时保留待定，并定位原页请老师确认。',
    '- 采用老师确认的这一版实施说明；保留证据和评分理由。', '');
  return lines.join('\n');
}
export function validateGuideApproval(approval, proposal) {
  if (approval?.method && !['teacher', 'automatic'].includes(approval.method)) throw Error('Invalid implementation document approval method');
  if (approval?.method === 'automatic' && proposal.executionMode !== 'auto') throw Error('This batch requires teacher confirmation before grading');
  if (!approval || approval.proposalId !== proposal.id || approval.rubricHash !== proposal.rubricHash || approval.sourceHash !== proposal.sourceHash
    || typeof approval.body !== 'string' || !approval.body.trim() || approval.body.length > 120000 || digest(approval.body) !== approval.hash
    || !Number.isInteger(approval.revision) || approval.revision < 1) throw Error('Teacher guide approval does not match the source, rubric and exact document version');
  return structuredClone(approval);
}
