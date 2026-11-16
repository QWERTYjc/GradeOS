import { digest } from './core.mjs';
import { evidenceWithSourcePages } from './shared-evidence.mjs';

const text = value => String(value ?? '').replace(/\r?\n/g, ' ').replaceAll('|', '\\|');
const score = value => value == null ? '待定' : String(value);
const pages = values => values?.length ? values.join('、') : '未记录';
const anchor = value => String(value).toLowerCase().replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu, '').replace(/\s/g, '-');
const itemLink = id => `[${text(id)}](#${anchor(id)})`;
const table = (head, rows) => [`| ${head.join(' | ')} |`, `| ${head.map(() => '---').join(' | ')} |`, ...rows.map(row => `| ${row.join(' | ')} |`), ''];
const relations = { met: '满足', unmet: '不满足', exception: '按源规则例外给分', uncertain: '待确定' };
const origins = { none: '无', local: '本步骤', current: '本步骤', inherited: '前序步骤传递', propagated: '前序步骤传递', mixed: '当前与前序步骤均有问题', unclear: '未确定', uncertain: '未确定' };

function sourceLines(source) {
  return [`- **评分条件**：${text(source.condition)}`, `- **MS 原文**（第 ${pages(source.source_pages)} 页）：${text(source.source_text)}`,
    `- **给分规则**：${text(source.award_type)}；允许分值 ${source.allowed_awards?.join(' / ') ?? '未单列'}；前置评分点 ${source.depends_on?.length ? source.depends_on.map(text).join('、') : '无'}`];
}

// Presentation only: all awards, observations and source conditions come from bound records.
export function renderStudentFeedback(id, grade, frozen, feedback, sourcePath) {
  if (feedback.grade_hash !== digest(grade) || feedback.rubric_hash !== frozen.hash) throw Error('Feedback presentation source mismatch');
  const byId = new Map(feedback.items.map(row => [row.item_id, row]));
  const rules = new Map(frozen.artifact.items.map(row => [row.item_id, row]));
  const flagged = grade.items.filter(item => item.score == null || item.review_required || byId.get(item.item_id)?.review_recommended || grade.source_issues?.some(issue => issue.item_id === item.item_id));
  const full = grade.items.filter(item => item.score != null && item.score === item.max_score).length;
  const incomplete = grade.items.filter(item => item.score != null && item.score < item.max_score);
  const unknown = grade.items.filter(item => item.score == null).length;
  const state = item => item.score == null ? '分数待定' : flagged.includes(item) ? '建议复核' : item.score === item.max_score ? '满分记录' : '有未获分项';
  const lines = ['# 个人批改与学习反馈', '', '*依据本次答卷的批改记录与评分标准整理 · 待教师审阅*', '',
    ...table(['本次得分', '满分小项', '需核查的小项'], [[`**${score(grade.total_score)} / ${grade.max_score}**`, `${full} / ${grade.items.length}`, `${flagged.length} 项${unknown ? `（含 ${unknown} 项分数待定）` : ''}`]]),
    '[学习总结](#学习总结) · [下一步练习](#下一步练习) · [教师审阅](#教师审阅) · [逐题反馈](#逐题反馈) · [评分规则与来源](#评分规则与来源)', '',
    '## 学习总结', '', `> ${text(feedback.summary)}`, '',
    '### 本次已获分的表现', '',
    ...feedback.strengths.flatMap(row => {
      const recorded = row.item_ids.flatMap(itemId => {
        const selected = feedback.selection?.strengths.find(ref => ref.item_id === itemId);
        const point = grade.items.find(item => item.item_id === itemId)?.point_decisions?.find(point => point.point_id === selected?.point_id);
        return point ? [`  作答记录（${text(itemId)} / ${text(point.point_id)}）：${text(evidenceWithSourcePages(grade.items.find(item => item.item_id === itemId), point))}`, ''] : [];
      });
      return [`- **${row.item_ids.map(itemLink).join('、')}**：${text(row.observation)}`, '', ...recorded];
    }),
    ...(!feedback.strengths.length ? ['本次未单独提炼优势，可在逐题记录中查看已获分的具体步骤。'] : []), '',
    '## 下一步练习', '', '按以下顺序练习；完成标准用于检查新作答，不会自动改变本次分数。', ''];
  feedback.priorities.forEach((row, index) => lines.push(`### 练习 ${index + 1}`, '',
    `**对应题目**：${row.item_ids.map(itemLink).join('、')}`, '',
    ...row.item_ids.flatMap(itemId => feedback.source_focus?.[itemId] ? [`**对照条件**（${text(itemId)} / ${text(feedback.source_focus[itemId].point.point_id)}）：${text(feedback.source_focus[itemId].point.condition)}`, ''] : []),
    `**怎么练**：${text(row.action)}`, '', `**完成标准**：${text(row.success_check)}`, ''));
  if (!feedback.priorities.length) lines.push('本次没有单列优先练习，可先对照逐题依据复做关键步骤。', '');
  lines.push('## 教师审阅', '',
    flagged.length ? '以下事项需核对答卷原图或评分标准；原判分与反馈建议分别保留。' : '本次记录没有单独标记待复核小项，仍须由教师审阅确认。', '',
    ...(flagged.length ? table(['题目', '当前分数', '核查事项'], flagged.map(item => [itemLink(item.item_id), `${score(item.score)} / ${item.max_score}`,
      text(byId.get(item.item_id)?.review_reason || (item.score == null ? '分数待定，需核对原卷证据及适用条件。' : '原批改标记需复核。'))])) : []));
  for (const note of grade.review_notes ?? []) lines.push(`- **原批改备注**：${text(note)}`);
  for (const issue of grade.source_issues ?? []) lines.push(`- **来源疑点 ${text(issue.item_id ?? '')}**：${text(issue.description ?? issue.reason ?? JSON.stringify(issue))}`);
  lines.push('', '### 得分概览', '', `${grade.items.length} 个小项中，${incomplete.length} 项存在未获分部分${unknown ? `，${unknown} 项分数待定` : ''}。点击题号可查看该题反馈与完整依据。`, '',
    ...table(['题目', '得分', '阅读提示'], grade.items.map(item => [itemLink(item.item_id), `${score(item.score)} / ${item.max_score}`, state(item)])),
    '---', '', '## 逐题反馈', '',
    '先读本题反馈和练习建议，再展开完整评分依据。作答记录与判分解释来自当次批改，不作为已验证的推荐解法；页码均为文件物理页码。', '');
  for (const item of grade.items) {
    const row = byId.get(item.item_id), rule = rules.get(item.item_id), focus = feedback.source_focus?.[item.item_id];
    lines.push(`### ${text(item.item_id)}`, '', `**${score(item.score)} / ${item.max_score} 分** · ${state(item)}`, '',
      `答卷第 ${pages(item.student_pages)} 页 · MS 第 ${pages(item.scheme_pages)} 页`, '',
      ...(feedback.version === 1 ? [`**评分重点**：${text(row.criterion)}`, ''] : []), `**本题反馈**：${text(row.assessment)}`, '');
    if (item.score !== item.max_score || flagged.includes(item)) lines.push(`**建议练习**：${text(row.next_step)}`, '');
    if (row.review_recommended) lines.push(`> **复核提示**：${text(row.review_reason)}`, '');
    lines.push('<details>', `<summary>完整评分依据${item.point_decisions?.length ? ` · ${item.point_decisions.length} 个评分点` : ''}</summary>`, '',
      `**本题评分要求**：${text(rule.criteria)}`, '');
    if (item.score === item.max_score && !flagged.includes(item)) lines.push(`**复做建议**：${text(row.next_step)}`, '');
    if (item.selected_route) lines.push(`**采用路线**：${text(item.selected_route)}`, '',
      `**可选路线**：${(rule.routes ?? []).map(route => `${text(route.route_id)}［${route.point_ids.map(text).join('、')}］${route.description ? `：${text(route.description)}` : ''}`).join('；')}。各路线互为替代，不要求合并满足。`, '');
    for (const point of item.point_decisions ?? []) {
      const criterion = rule.scoring_points.find(source => source.point_id === point.point_id);
      lines.push(`#### ${text(point.point_id)} · ${score(point.score)} / ${criterion.max_score} · ${text(criterion.award_type)}`, '',
        ...sourceLines(criterion), `- **作答记录**（答卷第 ${pages(point.student_pages)} 页）：${text(evidenceWithSourcePages(item, point))}`,
        `- **判分记录**：${relations[point.relation] ?? '未单列'}；${text(point.reason)}`,
        ...(point.error_origin && point.error_origin !== 'none' ? [`- **原记录的错误来源**：${text(origins[point.error_origin] ?? point.error_origin)}`] : []),
        ...(point.rule_ref ? [`- **例外依据**：${text(point.rule_ref)}`] : []), '');
      if (point.source_assessment) {
        const check = point.source_assessment;
        lines.push(`**源规则核对**：${text(check.outcome)}；初判 ${score(check.proposed_score)}；规则 ${check.rule_refs.map(text).join('、')}；已查 MS 第 ${pages(check.source_pages)} 页。初判详情保留在原始记录中。`, '');
      }
      if (point.source_review) {
        const check = point.source_review;
        lines.push(`**独立源规则复核**：初判 ${score(point.primary_score)} → ${score(point.score)}；${text(check.outcome)}；依据 ${check.source_refs.map(text).join('、')}；原文摘录：${text(check.source_quote)}。`, '');
      }
      if (point.exception_review) lines.push(`**例外核查**：初判 ${score(point.primary_score)} → ${score(point.score)}；${text(point.exception_review.verdict)}。${text(point.exception_review.reason)}`, '');
    }
    if (focus) {
      lines.push(`**练习聚焦**：${text(focus.point.point_id)}（完整条件见上方对应评分点）。`, '');
      // Retain dependencies even when they are outside this item's selected scoring route.
      for (const prerequisite of focus.prerequisite_points.filter(source => !item.point_decisions?.some(point => point.point_id === source.point_id)))
        lines.push(`**前置评分点 ${text(prerequisite.point_id)}**`, '', ...sourceLines(prerequisite), '');
      for (const related of focus.related_context) {
        lines.push(`**关联来源 ${text(related.item_id)}**：${text(related.criteria)}`, '',
          '以下为来源上下文，不据此新增评分依赖。', '',
          `可选路线：${related.routes.map(route => `${text(route.route_id)}［${route.point_ids.map(text).join('、')}］`).join('；')}。各路线互为替代，不要求合并满足。`, '');
        for (const source of related.points) lines.push(`**${text(source.point_id)}**`, '', ...sourceLines(source), '');
      }
    }
    lines.push('**原批改汇总说明**', '', text(item.reason), '', '</details>', '');
  }
  lines.push('---', '', '## 评分规则与来源', '',
    '<details>', '<summary>通用规则、复核记录与原始附件</summary>', '',
    '### 通用评分规则', '', '以下编号对应各评分点引用的规则。是否适用，须结合原图、条件范围及当次判分核查。', '',
    ...frozen.artifact.general_instructions.map((rule, index) => `- **G${index + 1}**（MS 第 ${pages(rule.source_pages)} 页）：${text(rule.text)}`),
    '- **P**：该点完整源规则，包含条件、原文、给分类型、允许分值、前置条件、路线及关联上下文。', '');
  for (const note of frozen.artifact.unresolved_notes ?? []) lines.push(`- **MS 待核实事项**：${text(typeof note === 'string' ? note : JSON.stringify(note))}`);
  if (grade.reason_style === 'brief-full-credit') lines.push('“Full criterion met.”表示批改模型已确认所列证据满足完整条件的短理由。各点的原条件、作答记录和页码仍完整保留。', '');
  if (feedback.fixed_commentary_ids?.length) lines.push(`以下题目的反馈采用原记录的固定简述，未新增模型解释：${feedback.fixed_commentary_ids.map(text).join('、')}。`, '');
  if (grade.source_permission_review) lines.push(`主批改已核对 ${grade.source_permission_review.checks.length} 个点的源规则；这不代表独立复核或教师确认。`, '');
  if (grade.independent_source_review) lines.push(`独立模型已复核 ${grade.independent_source_review.targets.length} 个点，其中 ${grade.independent_source_review.changes.length} 个点的分值或关系改变；这不是教师确认。`, '');
  if (grade.exception_review) lines.push(`例外核查前总分 ${score(grade.exception_review.primary_total_score)}，核查后 ${score(grade.total_score)}；完整初稿与核查决定另行保留。`, '');
  if (grade.self_review) {
    const review = grade.self_review;
    lines.push('### 模型自查记录', '',
      `${review.independent ? '独立模型复核' : '原批改模型在同一会话中自查'}，记录覆盖 ${review.checked_point_count ?? '未单列'} 个评分点。这不是教师确认。`, '',
      ...table(['题目', '自查前', '自查后'], (review.changes ?? []).map(change => [itemLink(change.item_id), score(change.before.score), score(change.after.score)])));
  }
  lines.push('### 阅读说明', '',
    '- 本报告整理已保存的判分，未重新识读答卷图片。批改记录中的解释如与原图或 MS 冲突，应回到来源核查。',
    '- 分数待定与零分分别保留；模型自查、模型复核和教师确认是不同环节。',
    '- 学习反馈仅描述本次作答，不推断长期能力、努力程度或班级排名。', '',
    `记录编号：${text(id)}`, '',
    feedback.generation_mode === 'recorded-feedback-v1' ? '本报告按已保存得分排列练习重点，未新增模型选择或判分。' : '学习重点来自已保存反馈；排版整理未改变原判分。', '',
    sourcePath ? `[原始批改记录](${encodeURI(sourcePath).replace(/[()#]/g, c => `%${c.charCodeAt(0).toString(16)}`)})` : '', '', '</details>', '');
  return lines.join('\n');
}
