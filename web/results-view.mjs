import { escape as e, button as b, iconButton as ib, markdown, recordScoreText, recordBasisText, statuses } from './ui.mjs';
import { gradingAnnotations } from './grading-annotations.mjs';

export const resultTasks = state => state.tasks.filter(task => task.kind === 'grade' && (task.records?.length || task.artifacts?.length));
export const reviewForRecord = (state, taskId, record) => state.reviews.findLast(review => review.taskId === taskId && review.recordId === record.id && review.originalHash === record.originalHash);
export const recordPending = (record, review) => Boolean(record.reviewRequired && (!review || (review.score == null && record.disposition !== 'feedback_only')));

export function questionRows(state, task, groupId) {
  const items = new Map();
  for (const record of task?.records || []) {
    if (record.groupId !== groupId) continue;
    const review = reviewForRecord(state, task.id, record), score = review ? review.score : record.score;
    if (!items.has(record.itemId)) items.set(record.itemId, { id: record.itemId, records: [], pending: false, deduction: false, unknown: false, feedbackOnly: true, hasFeedback: false, score: 0, maximum: 0, knownMaximum: true });
    const item = items.get(record.itemId);
    item.records.push(record);
    item.pending ||= recordPending(record, review);
    item.feedbackOnly &&= record.disposition === 'feedback_only';
    item.hasFeedback ||= record.disposition === 'feedback_only';
    item.unknown ||= record.disposition !== 'feedback_only' && !Number.isFinite(score);
    item.knownMaximum &&= record.disposition === 'feedback_only' || Number.isFinite(record.maximum);
    if (Number.isFinite(score)) item.score += score;
    if (Number.isFinite(record.maximum)) item.maximum += record.maximum;
    item.deduction ||= Number.isFinite(score) && Number.isFinite(record.maximum) && score < record.maximum;
  }
  return [...items.values()].map(item => ({ ...item,
    tone: item.pending || (item.unknown && !item.feedbackOnly) ? 'pending' : item.deduction ? 'deduction' : item.feedbackOnly ? 'feedback' : 'credit',
    scoreLabel: item.feedbackOnly ? '定性反馈' : item.unknown ? '待定' : item.hasFeedback ? '含定性反馈' : `${Number(item.score.toFixed(4))}${item.knownMaximum ? ` / ${Number(item.maximum.toFixed(4))}` : ' 分'}`,
  }));
}

export function resultContext(ctx) {
  const tasks = resultTasks(ctx.state), task = tasks.find(row => row.id === ctx.resultTaskId) || tasks.at(-1);
  const group = task?.groups.find(row => row.id === ctx.resultGroupId) || task?.groups[0];
  const items = questionRows(ctx.state, task, group?.id);
  const filtered = items.filter(item => ctx.resultFilter === 'pending' ? item.pending || (item.unknown && !item.feedbackOnly) : ctx.resultFilter === 'deduction' ? item.deduction : true);
  return { tasks, task, group, items, filtered };
}

export function resultsBar(ctx) {
  const { tasks, task, group, items } = resultContext(ctx);
  if (!task) return '';
  const partial = !['completed', 'needs_review'].includes(task.status);
  const reports = task.artifacts.filter(artifact => !artifact.groupId || artifact.groupId === group?.id);
  const selectedRecord = task.records.find(record => record.id === ctx.resultRecordId);
  const pending = task.records.filter(record => recordPending(record, reviewForRecord(ctx.state, task.id, record))).length;
  return `<div class="results-identity"><span class="results-eyebrow">批改结果</span><select id="result-task" aria-label="批改批次">${tasks.map(row => `<option value="${e(row.id)}" ${row.id === task.id ? 'selected' : ''}>${e(row.title)}</option>`).join('')}</select><span class="result-status ${partial ? 'incomplete' : ''}">${e(statuses[task.status] || '状态未知')}${partial ? ' · 仅显示已保存结果' : ''}</span>${partial ? '' : `<a class="result-complete" href="/cloud-publish.html?task=${encodeURIComponent(task.id)}" target="_top">发布给学生</a>`}${task.status === 'needs_review' ? b('complete-review', '完成审阅', { className: 'result-complete', disabled: pending > 0, attrs: `data-id="${e(task.id)}" title="${pending ? `还有 ${pending} 个评分点需要确认` : '将这一批标记为已完成'}"` }) : ''}</div>
    <div class="results-controls"><label class="result-student"><span>答卷</span><select id="result-group" aria-label="查看哪份答卷">${task.groups.map(row => `<option value="${e(row.id)}" ${row.id === group?.id ? 'selected' : ''}>${e(row.label)}</option>`).join('')}</select></label><span class="results-count">${items.length} 个题目</span><div class="result-view-actions">${b('result-source', '原卷批注', { className: ctx.resultReport ? 'quiet' : 'result-active', disabled: !items.length, attrs: 'aria-pressed="' + !ctx.resultReport + '"' })}${b('grading-document', '评分明细', { className: ctx.resultReport === 'grading-result' ? 'result-active' : 'quiet', disabled: !items.length })}${reports.map(artifact => b('result-report', artifact.groupId ? '个人报告' : '汇总报告', { className: ctx.resultReport === artifact.id ? 'result-active' : 'quiet', attrs: `data-task="${e(task.id)}" data-id="${e(artifact.id)}" aria-pressed="${ctx.resultReport === artifact.id}"` })).join('')}</div>${selectedRecord && !ctx.resultReport ? b('result-outline', '题目目录', { className: 'result-outline-toggle', attrs: `aria-expanded="${Boolean(ctx.resultOutline)}"` }) : ''}</div>`;
}

export function resultsOutline(ctx) {
  const { task, items, filtered } = resultContext(ctx);
  if (!task) return '';
  const active = task.records.find(record => record.id === ctx.resultRecordId);
  const counts = { all: items.length, deduction: items.filter(item => item.deduction).length, pending: items.filter(item => item.pending || (item.unknown && !item.feedbackOnly)).length };
  return `<div class="result-outline-heading"><strong>逐题查看</strong><span>${items.length}</span>${ib('result-outline', '收起题目目录', 'close')}</div><div class="result-filters" role="group" aria-label="筛选题目">${[['all', '全部'], ['deduction', '失分'], ['pending', '待定']].map(([key, label]) => b('result-filter', `${label}<small>${counts[key]}</small>`, { attrs: `data-id="${key}" aria-pressed="${(ctx.resultFilter || 'all') === key}"` })).join('')}</div><nav class="result-question-list" aria-label="题目目录">${filtered.map(item => b('result-question', `<span class="question-label"><i class="result-tone ${item.tone}"></i><strong>${e(item.id)}</strong><small>${item.records.length} 个评分点</small></span><span class="question-score">${e(item.scoreLabel)}</span>`, { className: 'result-question', attrs: `data-id="${e(item.id)}" ${active?.itemId === item.id ? 'aria-current="true"' : ''} title="第 ${e(item.id)} 题 · ${e(item.scoreLabel)}"` })).join('') || '<p class="result-empty">这个范围没有题目。</p>'}</nav><div class="result-outline-footer">${b('leave-results', '返回材料画布', { symbol: 'left' })}</div>`;
}

export function recordDetail(ctx, record, draft = null) {
  const task = ctx.state.tasks.find(row => row.id === record.taskId);
  const allItems = questionRows(ctx.state, task, record.groupId), item = allItems.find(row => row.id === record.itemId);
  const items = ctx.resultsOpen ? resultContext(ctx).filtered : allItems, itemIndex = items.findIndex(row => row.id === record.itemId);
  const review = reviewForRecord(ctx.state, task.id, record), current = draft ? draft.score : review ? review.score : record.score;
  const score = review ? review.score : record.score;
  const sources = gradingAnnotations(ctx.state, task.id, record.groupId).find(row => row.recordId === record.id);
  const sourceButtons = (ids, label) => (ids || []).map(id => {
    const page = ctx.state.pages.find(row => row.id === id);
    return page ? b('record-source', `${label} · 第 ${page.sourcePage} 页 ↗`, { attrs: `data-id="${e(id)}"`, className: 'source-link' }) : '';
  }).join('');
  return `<div class="record-heading"><div><span class="results-eyebrow">评分依据</span><h2>第 ${e(record.itemId)} 题</h2></div>${ib('close-record', '收起评分依据', 'close')}</div>
    <div class="record-point-tabs" role="group" aria-label="本题评分点">${item.records.map(point => b('open-record', e(point.pointId?.toUpperCase() || '整题'), { attrs: `data-id="${e(point.id)}" aria-pressed="${point.id === record.id}"` })).join('')}</div>
    <div class="record-verdict"><strong>${e(recordScoreText(record, score))}</strong><span>${review ? '老师已复核' : recordPending(record, review) ? '需要确认' : record.disposition === 'feedback_only' ? '定性反馈' : '原始评分'}</span></div>
    ${recordBasisText(record) ? `<p class="record-basis">${e(recordBasisText(record))}</p>` : ''}
    <section class="record-section"><h3>判定理由</h3><div class="prose">${markdown(record.reason || '未提供判定理由。')}</div></section>
    <section class="record-section record-evidence"><h3>答卷证据</h3><div class="prose">${markdown(record.evidence || '尚无可引用的证据，请核对原卷。')}</div><div class="record-sources">${sourceButtons(sources?.studentPageIds, '答卷') || '<span class="muted">原卷无法定位，请检查材料是否已调整。</span>'}</div></section>
    ${record.uncertainties?.length ? `<section class="record-section record-uncertainties"><h3>待核实</h3><ul>${record.uncertainties.map(note => `<li>${e(note)}</li>`).join('')}</ul></section>` : ''}
    <details class="record-criterion"><summary>评分条件与来源</summary><div class="prose">${markdown(record.sourceText || '未提供评分条文。')}</div><div class="record-sources">${sourceButtons(sources?.schemePageIds, 'MS')}${sourceButtons(sources?.questionPageIds, '题目')}</div></details>
    <details class="record-review-edit" ${draft || recordPending(record, review) ? 'open' : ''}><summary>复核这一评分点${review ? ' · 已保存' : ''}</summary><form id="canvas-review-form"><label>老师复核<select name="score"><option value="null" ${current == null ? 'selected' : ''}>${record.disposition === 'feedback_only' ? '确认定性反馈（不赋分）' : '保留待定'}</option>${(record.allowedAwards || []).map(value => `<option value="${value}" ${value === current ? 'selected' : ''}>${value} 分</option>`).join('')}</select></label><textarea name="reason" rows="3" required maxlength="4000" aria-label="复核理由" placeholder="写下复核依据…">${e(draft?.reason ?? review?.reason ?? '')}</textarea><button type="submit" class="primary">保存复核</button></form><p class="muted">原始评分 ${e(recordScoreText(record))} 会保留。</p></details>
    <div class="record-bottom-actions">${b('ask-record', '就此问 Pi', { symbol: 'message' })}<div>${ib('previous-result', '上一题', 'left', itemIndex <= 0 ? 'disabled' : '')}${ib('next-result', '下一题', 'right', itemIndex >= items.length - 1 ? 'disabled' : '')}</div></div>`;
}
