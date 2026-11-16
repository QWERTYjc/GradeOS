import { uncertaintyView, escape as e, iconButton, button, latestReview, recordScoreText, recordBasisText, empty, pageById } from './ui.mjs';

export function reviewItems(ctx) {
  const tasks = ctx.state.tasks.filter(task => task.records.length);
  const task = tasks.find(item => item.id === ctx.reviewTaskId) || tasks.at(-1);
  if (!task) return { task: null, records: [] };
  ctx.reviewTaskId = task.id;
  const records = ctx.reviewAll ? task.records : task.records.filter(record => record.reviewRequired || latestReview(ctx.state, record.id));
  return { task, records: records.length ? records : task.records };
}
function sourcePane(ctx, record, role) {
  const pageIds = role === 'student' ? record.studentPageIds : [...record.schemePageIds, ...(record.questionPageIds || [])];
  const index = Math.min(ctx.sourcePage[role] || 0, Math.max(0, pageIds.length - 1));
  const page = pageById(ctx.state, pageIds[index]);
  const label = role === 'student' ? '学生答卷' : '评分依据原页';
  return `<section class="source-pane"><header><strong>${label}${page ? ` · 第 ${page.sourcePage} 页` : ''}</strong><div class="source-controls">${pageIds.length > 1 ? `<select aria-label="${label}页码" data-source="${role}">${pageIds.map((id, i) => `<option value="${i}" ${i === index ? 'selected' : ''}>第 ${pageById(ctx.state, id)?.sourcePage} 页</option>`).join('')}</select>` : ''}${page ? iconButton('page', `放大${label}`, 'zoom-in', `data-id="${e(page.id)}"`) : ''}</div></header>
    <div class="source-paper">${page ? `<img src="${page.url}" alt="${e(label)}，${e(page.fileName)}，第 ${page.sourcePage} 页">` : '<p class="muted">此记录未提供原页引用。</p>'}</div>
  </section>`;
}
export function reviewView(ctx) {
  const { task, records } = reviewItems(ctx);
  if (!task || !records.length) return empty('暂时没有评分需要审阅', '批改任务完成后，可在这里对照原卷和评分条文。', button('go-tasks', '查看任务', { className: 'primary' }));
  ctx.reviewIndex = Math.min(ctx.reviewIndex, records.length - 1);
  const record = records[ctx.reviewIndex];
  ctx.currentRecord = record;
  const saved = latestReview(ctx.state, record.id);
  const canReviewScore = record.allowedAwards.length > 0 || record.disposition === 'feedback_only';
  const draft = ctx.reviewDrafts[record.id] || { score: saved ? saved.score : record.score, reason: saved?.reason || record.reason };
  return `<section class="review content"><div class="review-toolbar"><div class="title-line"><h1>${e(record.student)} · ${e(record.itemId)}${record.pointId ? ` / ${e(record.pointId)}` : ''}</h1><select id="review-task" aria-label="审阅哪个任务">${ctx.state.tasks.filter(item => item.records.length).map(item => `<option value="${e(item.id)}" ${item.id === task.id ? 'selected' : ''}>${e(item.title)}</option>`).join('')}</select></div>
    <div class="review-navigation">${button('review-filter', ctx.reviewAll ? '全部评分' : '需复核', { className: 'text-button muted' })}${iconButton('previous-record', '上一项', 'left', ctx.reviewIndex === 0 ? 'disabled' : '')}<span>${ctx.reviewIndex + 1} / ${records.length}</span>${iconButton('next-record', '下一项', 'right', ctx.reviewIndex >= records.length - 1 ? 'disabled' : '')}</div></div>
    ${recordBasisText(record) ? `<p class="muted">${e(recordBasisText(record))}</p>` : ''}<div class="source-grid">${sourcePane(ctx, record, 'student')}${sourcePane(ctx, record, 'scheme')}</div>
    <div class="evidence-line"><details><summary>查看评分依据</summary><div><p>${e(record.evidence)}</p><p>${e(record.sourceText)}</p><p class="muted">${e(record.reason)}</p></div></details>${button('ask-record', '询问 GradeOS', { className: 'text-button blue', symbol: 'message' })}</div>
    ${uncertaintyView(record)}<form id="review-form" class="review-form"><div class="review-score"><span>原判断 <strong class="${record.score === null ? 'amber' : ''}">${e(recordScoreText(record))}</strong></span><span class="divider"></span><span>复核</span><div class="score-options">${[...record.allowedAwards, null].map(value => `<label class="score-option ${value === draft.score ? 'selected' : ''}"><input type="radio" name="score" value="${value === null ? 'null' : value}" ${value === draft.score ? 'checked' : ''}><span>${value === null ? (record.disposition === 'feedback_only' ? '确认定性反馈（不赋分）' : '待定') : `${value} 分`}</span></label>`).join('')}</div>${saved ? '<span class="saved-state">已存草稿</span>' : ''}</div>
    ${!canReviewScore ? '<p class="notice">评分范围尚未确定，请先核对评分标准；原判断保留。</p>' : ''}
    <div class="review-save"><label for="review-reason" class="muted">理由</label><input id="review-reason" name="reason" value="${e(draft.reason)}" maxlength="4000" required placeholder="填写本次复核理由"><button type="submit" class="primary" ${ctx.busy || !canReviewScore ? 'disabled' : ''}>保存复核</button></div></form>
    ${task.status === 'needs_review' ? `<div class="review-finish">${button('review-complete', '结束本批审阅', { className: 'text-button blue' })}</div>` : ''}
  </section>`;
}
