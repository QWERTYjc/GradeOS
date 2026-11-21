import { escape as e, button as b, iconButton as ib, markdown, recordScoreText, recordBasisText, statuses } from './ui.mjs';
import { gradingAnnotations } from './grading-annotations.mjs';
import { studentSummaryMarkdown } from './grading-library.mjs';

export const resultTasks = state => state.tasks.filter(task => task.kind === 'grade' && (task.records?.length || task.artifacts?.length));
export const reviewForRecord = (state, taskId, record) => state.reviews.findLast(review => review.taskId === taskId && review.recordId === record.id && review.originalHash === record.originalHash);
export const recordPending = (record, review) => Boolean(record.reviewRequired && (!review || (review.score == null && record.disposition !== 'feedback_only')));

function aggregateQuestions(records, getReview) {
  const items = new Map();
  for (const record of records) {
    const review = getReview(record), score = review ? review.score : record.score;
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

export function questionRows(state, task, groupId) {
  return aggregateQuestions((task?.records || []).filter(record => record.groupId === groupId), record => reviewForRecord(state, task.id, record));
}

const unresolved = item => item.pending || item.unknown;
const rounded = value => Number(value.toFixed(4));

export function cohortResults(state, task) {
  const reviews = new Map(), records = new Map(), reports = new Map();
  const progress = new Map((task.progress?.students || []).map(row => [row.id, row.status]));
  const labels = { waiting: '等待批改', grading: '批改中', feedback: '生成反馈中', failed: '批改未完成', cancelled: '已停止' };
  for (const review of state.reviews || []) {
    if (review.taskId === task.id) reviews.set(JSON.stringify([review.recordId, review.originalHash]), review);
  }
  const getReview = record => reviews.get(JSON.stringify([record.id, record.originalHash]));
  for (const record of task.records || []) {
    if (!records.has(record.groupId)) records.set(record.groupId, []);
    records.get(record.groupId).push(record);
  }
  for (const artifact of task.artifacts || []) {
    if (!reports.has(artifact.groupId)) reports.set(artifact.groupId, []);
    const owned = reports.get(artifact.groupId);
    if (artifact.groupId && artifact.id === `${task.id}-student-${artifact.groupId}`) owned.unshift(artifact);
    else owned.push(artifact);
  }
  return (task.groups || []).map(group => {
    const points = records.get(group.id) || [], items = aggregateQuestions(points, getReview);
    const pending = items.filter(unresolved), deductions = items.filter(item => item.deduction);
    const numeric = items.filter(item => !item.feedbackOnly);
    const activity = progress.get(group.id);
    let score = null, maximum = null;
    let scoreLabel = (task.status === 'running' || ['failed', 'cancelled'].includes(activity) ? labels[activity] : '') || '暂无评分';
    if (items.length) {
      if (pending.length) scoreLabel = '待确认';
      else if (!numeric.length) scoreLabel = '定性反馈';
      else {
        score = rounded(numeric.reduce((sum, item) => sum + item.score, 0));
        maximum = numeric.every(item => item.knownMaximum) ? rounded(numeric.reduce((sum, item) => sum + item.maximum, 0)) : null;
        scoreLabel = maximum === null ? `${score} 分` : `${score} / ${maximum}`;
      }
    }
    for (const item of items) {
      const representative = item.records.find(record => {
        const review = getReview(record), score = review ? review.score : record.score;
        if (unresolved(item)) return recordPending(record, review) || (record.disposition !== 'feedback_only' && !Number.isFinite(score));
        return item.deduction && Number.isFinite(score) && Number.isFinite(record.maximum) && score < record.maximum;
      }) || item.records[0];
      item.recordId = representative.id;
      item.excerpt = getReview(representative)?.reason || representative.uncertainties?.[0] || representative.reason || '';
    }
    const focus = pending[0] || deductions[0] || items[0];
    const note = focus?.excerpt || '';
    return {group, items, pending, deductions, score, maximum, scoreLabel, focus, note, reports: reports.get(group.id) || [],
      tone: pending.length ? 'pending' : items.length ? 'saved' : 'unavailable'};
  });
}

export function cohortSummary(rows, task) {
  const unfinished = new Set((task.progress?.students || [])
    .filter(student => ['waiting', 'grading', 'failed', 'cancelled'].includes(student.status))
    .map(student => student.id));
  const scored = rows.filter(row => row.score !== null && row.maximum > 0 &&
    !unfinished.has(row.group.id) && !row.items.some(item => item.hasFeedback));
  const maximum = scored.length && scored.every(row => row.maximum === scored[0].maximum) ? scored[0].maximum : null;
  const mean = maximum === null ? null : rounded(scored.reduce((sum, row) => sum + row.score, 0) / scored.length);
  const deductions = new Map();
  for (const row of rows) {
    for (const item of row.deductions) {
      if (!unresolved(item) && item.knownMaximum && !item.feedbackOnly) {
        if (!deductions.has(item.id)) deductions.set(item.id, []);
        deductions.get(item.id).push(item.excerpt.trim());
      }
    }
  }
  let commonDeduction = null;
  for (const [id, notes] of deductions) {
    if (notes.length > (commonDeduction?.count ?? 1)) commonDeduction = { id, count: notes.length };
  }
  if (commonDeduction) {
    const frequencies = new Map();
    for (const note of deductions.get(commonDeduction.id)) {
      if (!note || note.length > 80) continue;
      const count = (frequencies.get(note) || 0) + 1;
      frequencies.set(note, count);
      if (count > commonDeduction.count / 2) {
        commonDeduction.excerpt = note;
        break;
      }
    }
  }
  return {
    total: rows.length, recorded: rows.filter(row => row.items.length).length,
    pending: rows.filter(row => row.pending.length).length, scored: scored.length, mean, maximum, commonDeduction,
  };
}

const studentSummaries = new WeakMap();
function learningSummary(reports) {
  for (const report of reports) {
    const source = report.currentSummary ?? report.body;
    if (typeof source !== 'string') continue;
    let cached = studentSummaries.get(report);
    if (!cached || cached.source !== source) {
      const summary = report.currentSummary ?? studentSummaryMarkdown(source);
      cached = { source, html: summary ? markdown(summary) : '' };
      studentSummaries.set(report, cached);
    }
    if (cached.html) return cached.html;
  }
  return '';
}

export function cohortEntries(rows, ctx) {
  const query = (ctx.cohortQuery || '').trim().toLocaleLowerCase();
  const filtered = rows.filter(row => (!query || row.group.label.toLocaleLowerCase().includes(query))
    && (ctx.cohortFilter === 'pending' ? row.pending.length : ctx.cohortFilter === 'deduction' ? row.deductions.length : true));
  if (!filtered.length) return [[null, `<div class="cohort-no-matches"><h3>${rows.length ? '没有符合条件的答卷' : '本批没有学生答卷'}</h3>${query || ctx.cohortFilter !== 'all' ? b('cohort-reset', '显示全部答卷', {className:'cohort-link'}) : ''}</div>`]];
  return filtered.map(row => {
    const {group, items, scoreLabel, focus, note, reports} = row;
    const id = e(group.id), name = e(group.label);
    const source = Boolean(items.length || group.pageIds?.length);
    const hasDetails = source || reports.length > 0;
    const personal = learningSummary(reports);
    const expanded = hasDetails && Boolean(ctx.cohortReadAll && (items.length || personal)) !== Boolean(ctx.cohortExpanded?.has(group.id));
    const student = `<span class="student-name">${name}</span><span class="student-score ${row.tone}"><strong>${e(scoreLabel)}</strong></span>`;
    const heading = hasDetails ? b('cohort-expand', student, {
      className:'student-toggle', attrs:`data-id="${id}" aria-expanded="${expanded}" aria-controls="cohort-detail-${id}"`,
    }) : `<span class="student-static">${student}</span>`;
    const summary = personal ? `<div class="cohort-summary student-learning-summary${expanded ? ' expanded' : ''}" aria-label="${name}的学习总结">${personal}</div>`
      : !expanded && focus && note ? `<p class="cohort-summary"><span>${e(focus.id)}</span> ${e(note)}</p>` : '';
    let details = '';
    if (expanded) {
      const links = [
        source ? b('cohort-source', '查看原卷', {attrs:`data-id="${id}"`}) : '',
        ...reports.map(report => b('cohort-report', e(reports.length === 1 ? '个人报告' : report.title || '个人报告'), {
          attrs:`data-id="${e(report.id)}" data-group="${id}" title="${e(report.title || '个人报告')}"`,
        })),
      ].join('');
      const resources = `<div class="student-actions">${links}</div>`;
      const questions = items.map(item => {
        const suggested = item.pending && !item.unknown && !item.feedbackOnly;
        return b('cohort-point', `<span class="cohort-item-label">${e(item.id)}</span><span class="cohort-item-note">${e(item.excerpt)}</span><span class="cohort-item-score">${suggested ? '建议 ' : ''}${e(item.scoreLabel)}${item.feedbackOnly && item.pending ? '<small>待确认</small>' : ''}</span>`,
          {attrs:`data-id="${e(item.recordId)}" title="查看第 ${e(item.id)} 题评分依据"`});
      }).join('');
      details = `${questions ? `<div class="cohort-items" aria-label="${name}的逐题评分">${questions}</div>` : ''}${ctx.cohortReadAll && (items.length || personal) ? `<details class="student-resources"><summary aria-label="${name}的原卷与报告">原卷与报告</summary>${resources}</details>` : resources}`;
    }
    return [group.id, `<article class="cohort-student" data-student="${id}"><h3 class="student-top">${heading}</h3>${summary}${hasDetails ? `<div id="cohort-detail-${id}"${expanded ? '' : ' hidden'}>${details}</div>` : ''}</article>`];
  });
}

export function resultContext(ctx) {
  const tasks = resultTasks(ctx.state), task = tasks.find(row => row.id === ctx.resultTaskId) || tasks.at(-1);
  const group = task?.groups.find(row => row.id === ctx.resultGroupId) || task?.groups[0];
  const items = questionRows(ctx.state, task, group?.id);
  const filtered = items.filter(item => ctx.resultFilter === 'pending' ? item.pending || (item.unknown && !item.feedbackOnly) : ctx.resultFilter === 'deduction' ? item.deduction : true);
  return { tasks, task, group, items, filtered };
}

export function firstResultPage(state, task, group) {
  return group?.pageIds?.find(id => {
    const page = state.pages?.find(row => row.id === id);
    const hash = task.pageHashes?.[id] || task.pages?.find(row => row.id === id)?.sha256;
    const moved = state.groups?.some(row => row.id !== group.id && row.pageIds.includes(id));
    return page && !moved && (page.active !== false || Boolean(hash)) && (!hash || page.sha256 === hash);
  });
}

export function resultsBar(ctx, workspaceActions = '') {
  const { tasks, task, group, items } = resultContext(ctx);
  if (!task) return '';
  const partial = !['completed', 'needs_review'].includes(task.status);
  const currentReport = task.artifacts.find(artifact => artifact.id === ctx.resultReport);
  const classReport = Boolean(currentReport && !currentReport.groupId);
  const reports = task.artifacts.filter(artifact => !artifact.groupId || (!classReport && artifact.groupId === group?.id));
  const pending = task.records.filter(record => recordPending(record, reviewForRecord(ctx.state, task.id, record))).length;
  const noPoints = classReport || !items.length;
  const sourceUnavailable = classReport || (!items.length && !firstResultPage(ctx.state, task, group));
  const views = [
    `<option value="source" ${!ctx.resultReport ? 'selected' : ''} ${sourceUnavailable ? 'disabled' : ''}>${items.length ? '原卷批注' : '原卷'}</option>`,
    `<option value="grading-result" ${ctx.resultReport === 'grading-result' ? 'selected' : ''} ${noPoints ? 'disabled' : ''}>评分明细</option>`,
    ...reports.map(report => {
      const sameScope = reports.filter(row => row.groupId === report.groupId);
      const label = sameScope.length > 1 && report.title ? report.title : report.groupId ? '个人报告' : '汇总报告';
      return `<option value="report:${e(report.id)}" ${report.id === ctx.resultReport ? 'selected' : ''}>${e(label)}</option>`;
    }),
  ];
  const groupOptions = task.groups.map(row => `<option value="${e(row.id)}" ${!classReport && row.id === group?.id ? 'selected' : ''}>${e(row.label)}</option>`);
  if (classReport) groupOptions.unshift(`<option value="" selected disabled>全班 · ${task.groups.length} 份</option>`);

  const taskOptions = tasks.map(row => `<option value="${e(row.id)}" ${row.id === task.id ? 'selected' : ''}>${e(row.title)}</option>`);
  const completion = task.status === 'needs_review' ? b('complete-review', '完成审阅', {
    disabled: pending > 0, attrs: `data-id="${e(task.id)}" title="${pending ? `还有 ${pending} 个评分点需要确认` : '将这一批标记为已完成'}"`,
  }) : '';
  const outline = !ctx.resultReport && items.length ? b('result-outline', ctx.resultOutline ? '收起题目目录' : '题目目录', {
    className:'result-outline-toggle', attrs:`aria-expanded="${Boolean(ctx.resultOutline)}"`,
  }) : '';
  return `<nav class="result-reading-bar" aria-label="批改结果导航">
    ${b('cohort-back', '全班总览', {className:'cohort-back', symbol:'left'})}
    <select id="result-group" aria-label="查看哪份答卷">${groupOptions.join('')}</select>
    <select id="result-view" aria-label="查看内容">${views.join('')}</select>
    <details class="cohort-more detail-more"><summary>更多</summary><div>
      <label class="detail-batch">批改批次<select id="result-task" aria-label="批改批次">${taskOptions.join('')}</select></label>
      ${partial ? '' : `<span class="detail-status">${e(statuses[task.status] || '状态未知')}</span>`}
      ${partial ? '' : `<a class="result-complete" href="/cloud-publish.html?task=${encodeURIComponent(task.id)}" target="_top">发布给学生</a>`}
      ${completion}${outline}
      ${b('detail-tools', ctx.detailTools ? '收起画布工具' : '画布工具', {attrs:`aria-expanded="${Boolean(ctx.detailTools)}"`})}
      ${workspaceActions}
    </div></details>
  </nav>${partial ? `<p class="cohort-notice">${e(statuses[task.status] || '状态未知')} · 仅显示已保存结果</p>` : ''}`;
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
