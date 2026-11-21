import { batchReport, reportSummaryMarkdown } from './grading-library.mjs';
import { gradingModel, effortLabel } from './grading-models.mjs';
import { escape as e, icon, button as b, iconButton as ib, markdown, statuses } from './ui.mjs';
import { progressMetrics } from './tasks.mjs';
import { cohortSummary, resultTasks, resultsBar, recordPending, reviewForRecord } from './results-view.mjs';

export const documents = state => [...state.schemes.map(row => ({ ...row, role: 'scheme' })), ...(state.questions || []).map(row => ({ ...row, role: 'question' })), ...state.groups.map(row => ({ ...row, role: 'student' }))];
export const questions = state => state.tasks.filter(task => task.status === 'running').flatMap(task => (task.interaction?.questions || []).filter(row => row.status === 'open').map(row => ({ ...row, taskId: task.id })));
export const pendingRecords = state => state.tasks.flatMap(task => task.records.filter(record => {
  const review = record.originalHash ? reviewForRecord(state, task.id, record)
    : state.reviews.findLast(row => row.recordId === record.id && (!row.taskId || row.taskId === task.id) && !row.originalHash);
  return recordPending(record, review);
}).map(record => ({ ...record, taskId: task.id })));
export const allRecords = state => state.tasks.flatMap(task => task.records.map(record => ({ ...record, taskId: task.id })));
const attr = id => `data-id="${e(id)}"`;
const lassoIcon = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path stroke-dasharray="2.5 2.5" d="M6 17C2 15 2 8 6 5S17 3 20 7S20 17 15 18S7 18 6 15"/><path d="M6 15c-3 2-2 6 1 6 2 0 3-2 1-3"/></svg>';
export const modeLabel = mode => mode === 'auto' ? '自动继续' : '先确认再批改';
export const guideForTask = (state, task) => state.documents?.find(row => row.taskId === task.id && row.proposalId);
export function gradingStage(state, task) {
  if (task.status === 'draft') return 'draft';
  if (task.status === 'needs_review') return 'review';
  if (task.status !== 'running') return 'done';
  const guide = guideForTask(state, task);
  if (guide?.approvals.length) return 'grading';
  return guide ? 'align' : 'prepare';
}
export function needsGradingMaterials(state) {
  return !state.chat && !resultTasks(state).length &&
    !state.tasks.some(task => task.kind === 'grade' && ['draft', 'running', 'needs_review'].includes(task.status));
}
export function workflowView(ctx, panels = []) {
  if (ctx.resultsOpen) return resultsBar(ctx, ctx.embedded ? workspaceControls(ctx, true) : '');
  const task = ['running', 'draft', 'needs_review'].map(status => ctx.state.tasks.findLast(row => row.kind === 'grade' && row.status === status)).find(Boolean);
  if (!task && resultTasks(ctx.state).length) return `<div class="workflow-copy"><h1>继续查看批改结果</h1><p>原卷批注、逐题依据与报告已保存在工作区。</p></div><div class="workflow-action">${b('results', '查看结果', { className: 'primary' })}${b('prepare-materials', '开始新批改', { className: 'quiet' })}</div>`;
  if (!task && !ctx.state.groups.length && ctx.state.pages.length)
    return `<div class="workflow-copy"><div class="workflow-path" aria-label="批改流程"><span aria-current="step">准备材料</span><i>›</i><span>开始批改</span><i>›</i><span>查看结果</span></div><h1>接着添加学生答卷</h1><p>已上传的材料会保留在这里。</p></div><div class="workflow-action">${b('upload-student', '上传答卷', { className: 'primary', disabled: ctx.busy })}</div>`;
  const standalone = !task && ctx.state.documents?.find(row => row.kind === 'marking_guide' && panels.some(panel => panel.documentId === row.id));
  if (!task && !standalone) {
    if (!ctx.state.groups.length) return '';
    return `<div class="workflow-copy"><div class="workflow-path" aria-label="批改流程"><span aria-current="step">准备材料</span><i>›</i><span>开始批改</span><i>›</i><span>查看结果</span></div><h1>${ctx.state.groups.length} 份答卷已就绪</h1><p>可以直接开始，也可以再添加题目或 MS。</p></div><div class="workflow-action">${b('materials', '调整材料', { className: 'workflow-secondary' })}${b('manual-task', '开始批改', { className: 'primary', disabled: ctx.busy })}</div>`;
  }
  const stage = task ? gradingStage(ctx.state, task) : 'standalone', guide = task ? guideForTask(ctx.state, task) : standalone;
  const automatic = task?.executionMode === 'auto', opened = guide && panels.some(panel => panel.documentId === guide.id);
  const titles = { standalone: '先对齐评分要求', draft: automatic ? '准备好后，按要求批改' : '先整理评分要求', prepare: '正在整理评分要求', align: automatic ? '按授权采用评分要求' : '请确认这次怎么批改', grading: '正在批改答卷', review: '批改完成，请审阅结果' };
  const descriptions = {
    standalone: '这份实施说明会在批改前采用。可以直接编辑，也可以让 Agent 调整。',
    draft: automatic ? '开始后，Agent 整理实施说明并继续批改；遇到疑点仍会询问。' : 'Agent 先整理评分实施文档。你调整并确认后，才会开始批改答卷。',
    prepare: automatic ? '阅读材料并整理评分要求，随后按本批授权继续。' : '阅读材料并整理可编辑的评分要求。答卷尚未开始批改。',
    align: automatic ? '将固定当前版本，用于本批次每份答卷。' : '直接编辑说明，或在对话中提出调整。确认后才会派发答卷。',
    grading: `本批采用评分实施 v${guide?.approvals.at(-1)?.revision || task?.interaction?.guide?.approvedRevision || 1} · 已保存 ${task?.progress?.completed || 0}/${task?.groupIds.length || 0} 份`,
    review: '查看待定项和评分依据，再完成这一批。',
  };
  const active = stage === 'review' ? 2 : 1;
  let action = '';
  if (stage === 'standalone') action = b('manual-task', '安排批改', { className: 'workflow-secondary' });
  if (stage === 'draft') action = b('edit-task', '继续批改设置', { className: 'primary', attrs: attr(task.id) });
  if (stage === 'align' && !automatic) action = opened ? b('approve-guide', `确认并批改 ${task.groupIds.length} 份`, { className: 'primary', attrs: attr(guide.id), disabled: Boolean(ctx.state.chat) }) : b('open-document', '查看评分实施', { className: 'primary', attrs: attr(guide.id) });
  if (stage === 'grading' && guide) action = b('open-document', '查看采用的说明', { className: 'workflow-secondary', attrs: attr(guide.id) });
  if (stage === 'review') action = b('results', '查看批改结果', { className: 'primary', attrs: attr(task.id) });
  return `<div class="workflow-copy"><div class="workflow-path" aria-label="批改阶段">${['准备材料', '开始批改', '查看结果'].map((label, index) => `<span ${index === active ? 'aria-current="step"' : ''}>${label}</span>`).join('<i>›</i>')}${task ? `<small>${task.groupIds.length} 份 · ${modeLabel(task.executionMode)}</small>` : ''}</div><h1>${titles[stage]}</h1><p>${descriptions[stage]}</p></div><div class="workflow-action">${action}</div>`;
}

function workspaceControls(ctx, inMenu = false) {
  const taskId = ctx.processId || (ctx.resultsOpen && ctx.resultTaskId);
  const inScope = row => !taskId || row.taskId === taskId;
  const pending = questions(ctx.state).filter(inScope).length + pendingRecords(ctx.state).filter(inScope).length + (ctx.state.documents || []).filter(doc => inScope(doc) && doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running' && task.executionMode !== 'auto')).length;
  const pages = ctx.state.pages.filter(page => page.active !== false).length;
  const history = ctx.state.tasks.length || ctx.state.conversation?.length || ctx.state.chat;
  const controls = [];
  if (!ctx.processId && ctx.returnProcessId) controls.push(b('show-process', '返回处理过程', {attrs:attr(ctx.returnProcessId)}));
  if (ctx.resultsOpen && !ctx.state.tasks.some(task => task.status === 'running')) controls.push(b('prepare-materials', '新批改', {className:'quiet'}));
  if (pages) controls.push(b('materials', `材料 <span class="count">${pages}</span>`, {className:'quiet'}));
  if (!ctx.resultsOpen && resultTasks(ctx.state).some(task => !inMenu || task.id !== ctx.processId)) controls.push(b('results', '批改结果', {className:'quiet'}));
  if (pending || ctx.state.reviews?.length) controls.push(b('reviews', pending ? `<span class="amber-dot"></span>待确认 ${pending}` : '审阅', {className:pending ? 'review-count' : 'quiet'}));
  if (history) controls.push(inMenu ? b('history', '对话与任务记录') : ib('history', '对话与任务记录', 'history'));
  if (inMenu) controls.push(b('rename-project', `重命名项目 · ${e(ctx.state.title)}`));
  return controls.join('');
}

export function header(ctx) {
  if (ctx.embedded && (ctx.processId || ctx.resultsOpen)) return '';
  return `<div class="brand-line"><a class="canvas-wordmark" href="/" target="_top" aria-label="GradeOS 工作台"><span class="gradeos-wordmark">Grade<span>OS</span></span></a>${b('rename-project', e(ctx.state.title), {className:'project-name'})}</div>
    <div class="header-actions">${workspaceControls(ctx)}<a class="quiet" href="/#files" target="_top">工作区文件</a></div>`;
}
export function toolbar(ctx, needsMaterials = false) {
  const tool = (mode, label, title = '') => b(mode, label, {
    className: ctx.mode === mode ? 'tool active' : 'tool',
    attrs: `aria-pressed="${ctx.mode === mode}"${title ? ` title="${title}"` : ''}`,
  });
  return `<span class="workspace-hint">${needsMaterials ? b('prepare-materials', '返回准备材料', { className: 'quiet', symbol: 'left' }) : ctx.resultsOpen ? '点击题号查看原卷与依据' : '材料与评分说明'}</span><div class="canvas-tools" role="group" aria-label="画布工具">${tool('browse', '阅读')}${tool('lasso', `${lassoIcon}套索`, '沿内容自由画一圈，松手后点击选区')}${tool('rectangle', `${icon('select')}框选`)}</div>${b('new-document', `${icon('plus')}文档`, { className: 'compare-action new-document-action' })}${b('compare', `${icon('column-width')}并排`, { className: 'compare-action', attrs: 'aria-label="并排打开文档"' })}${ctx.resultsOpen && ctx.resultDetail ? b('detail-chat', ctx.detailChat ? '收起对话' : '提问', {className:'compare-action',symbol:'message',attrs:`aria-expanded="${Boolean(ctx.detailChat)}"`}) : ''}`;
}

function eventsView(events) {
  const latest = new Map();
  for (const event of events || []) if (event.label) latest.set(event.key || event.id || `${event.type}:${event.lane}`, event);
  return [...latest.values()].slice(-12).map(event => `<li><span class="event-dot ${event.status === 'done' ? 'done' : event.status === 'error' ? 'error' : ''}"></span><span>${e(event.label)}</span>${event.pageIds?.length ? b('event-page', '原页', { className: 'source-link', attrs: attr(event.pageIds[0]) }) : ''}<span class="event-lane">${e(event.lane?.startsWith('student-') ? '答卷' : event.lane === 'ms-review' ? 'MS' : '')}</span></li>`).join('');
}
// Read the opening summary produced by renderReportMarkdown, before its tables and audit notes.
function batchSummaryView(state, task, rows) {
  const report = batchReport(task);
  const summary = report && (report.currentSummary ?? reportSummaryMarkdown(report.body));
  const {total, recorded, pending, scored, mean, maximum, commonDeduction} = cohortSummary(rows, task);
  const stats = [];
  const reviewed = report && state.reviews?.some(review => review.taskId === task.id);
  if (mean != null) {
    stats.push(`<span>${reviewed ? '复核后' : ''}${scored === 1 ? '总分' : '平均分'} <strong>${e(mean)} <small>/ ${e(maximum)}</small></strong></span>`);
    if (scored < total) stats.push(`<span>${scored} / ${total} 份已确定总分</span>`);
  } else if (recorded || !report) {
    stats.push(recorded ? `<span>${recorded} / ${total} 份已有${rows.every(row => row.items.every(item => item.feedbackOnly)) ? '文字评语' : '评分记录'}</span>`
      : `<span>${total ? `本批共 ${total} 份答卷，尚无逐题评分记录。` : '本批暂无学生答卷。'}</span>`);
  }
  if (pending) stats.push(`<span>${pending} 份待确认</span>`);
  const observation = !report && commonDeduction ? `<p>第 ${e(commonDeduction.id)} 题有 ${commonDeduction.count} 份答卷失分。${commonDeduction.excerpt ? `多份评语提到「${e(commonDeduction.excerpt)}」。` : ''}</p>` : '';
  return `<section class="batch-summary" aria-labelledby="batch-summary-title"><h2 id="batch-summary-title">${report ? '批改总结' : '评分概览'}</h2>
    ${summary ? `<div class="batch-report-prose prose">${markdown(summary)}</div>` : ''}
    ${report ? b('cohort-report', '阅读完整报告 ↗', {className:'report-read', attrs:attr(report.id)}) : ''}
    ${stats.length ? `<div class="batch-stats" aria-label="当前评分">${stats.join('')}</div>` : ''}${observation}</section>`;
}

export function cohortHeading(ctx, task, rows, process) {
  const incomplete = !['needs_review','completed'].includes(task.status);
  const status = statuses[task.status] || '状态未知';
  const batches = resultTasks(ctx.state);
  const pending = rows.some(row => row.items.some(item => item.pending));
  const controls = [], more = [];
  let phase = incomplete ? '仅显示已保存结果' : '';
  if (process) {
    const guide = guideForTask(ctx.state, task);
    const waiting = task.status === 'running' && guide && !guide.approvals.length && task.executionMode === 'review';
    phase = task.progress?.phase || '';
    if (waiting) phase = '等待老师确认评分要求';
    if (task.status === 'running' && task.interaction?.paused) phase = '已请求暂停';
    if (guide) controls.push(b('open-document', waiting ? '审阅评分要求' : '评分说明', {className: waiting ? 'primary' : '', attrs:attr(guide.id)}));
    if (task.records.length || task.artifacts.length) controls.push(b('results', '查看已保存结果', {attrs:attr(task.id), className:'cohort-link'}));
    if (task.status === 'running') {
      controls.push(b(task.interaction?.paused ? 'resume-task':'pause-task', task.interaction?.paused ? '继续处理':'暂停', {attrs:attr(task.id), disabled:task.progress?.stopping}));
      more.push(b('cancel-task', '停止任务', {attrs:attr(task.id), disabled:task.progress?.stopping}));
    } else controls.push(b('prepare-materials', '返回准备材料', {attrs:attr(task.id)}));
  } else {
    if (batches.length > 1) more.push(`<label class="cohort-switch"><span>切换批次</span><select id="result-task" aria-label="切换批改批次">${batches.map(batch => `<option value="${e(batch.id)}" ${batch.id === task.id ? 'selected' : ''}>${e(batch.title)}</option>`).join('')}</select></label>`);
    more.push(...task.artifacts.filter(artifact => !artifact.groupId && artifact !== batchReport(task)).map(artifact => b('cohort-report', e(artifact.title || '汇总报告'), {attrs:attr(artifact.id)})));
    if (task.status === 'needs_review' && !pending) controls.push(b('complete-review', '完成审阅', {className:'primary', attrs:attr(task.id)}));
  }
  const discuss = b('cohort-discuss', ctx.cohortChat ? '收起对话' : '提问', {attrs: `aria-expanded="${Boolean(ctx.cohortChat)}"`});
  if (ctx.embedded) more.push(workspaceControls(ctx, true));
  if (more.length) {
    more.push(discuss);
    controls.push(`<details class="cohort-more"><summary>更多操作</summary><div>${more.join('')}</div></details>`);
  } else controls.push(discuss);
  const links = ctx.embedded ? `<nav class="batch-breadcrumbs" aria-label="批次导航"><a href="/#grading/history" target="_top">‹ 批改历史</a><a href="/#files/batch/${encodeURIComponent(task.id)}" target="_top">批次文件 ↗</a></nav>` : '';
  return `${links}<div class="cohort-head"><div><h1>${e(task.title)}</h1>${process || incomplete ? `<p class="cohort-phase">${e([status, phase].filter(Boolean).join(' · '))}</p>` : ''}</div></div>
    ${batchSummaryView(ctx.state, task, rows)}
    ${task.error && process ? `<p class="cohort-notice" role="status">${e(ctx.state.failureReasons?.[task.id] || task.error)}</p>` : ''}
    <div class="cohort-actions">${!process && !incomplete && task.records?.length ? `<a class="cohort-open-link" href="/cloud-publish.html?task=${encodeURIComponent(task.id)}" target="_top">发布给学生</a>` : ''}${controls.join('')}</div>`;
}

export function cohortTools(ctx, rows) {
  const filters = [['all','全部答卷',rows.length], ['pending','待确认',rows.filter(row => row.pending.length).length], ['deduction','有失分',rows.filter(row => row.deductions.length).length]];
  return `<select id="cohort-filter" aria-label="筛选全班答卷">${filters.map(([key,label,count]) => `<option value="${key}" ${(ctx.cohortFilter || 'all') === key ? 'selected' : ''}>${label} · ${count}</option>`).join('')}</select>${rows.some(row => row.items.length) ? b('cohort-read-all', ctx.cohortReadAll ? '收起通读' : '逐题通读', {className:'cohort-read-all', attrs:`aria-pressed="${Boolean(ctx.cohortReadAll)}"`}) : ''}`;
}

export function processDetails(ctx, task) {
  const events = [...(task.interaction?.events || []), ...(ctx.state.liveTasks?.[task.id]?.events || [])];
  const model = task.modelConfig;
  const metrics = progressMetrics(task.progress);
  if (!events.length && !metrics && !model) return '';
  return `<details class="cohort-activity"><summary>处理记录与用量</summary>${events.length ? `<ol class="activity-list">${eventsView(events)}</ol>` : ''}${metrics}${model ? `<p class="muted">主模型 ${e(gradingModel(model.mainModel, ctx.state.modelCatalog)?.name || model.mainModel)} · ${e(effortLabel(model.mainModel, model.mainEffort))}　子模型 ${e(gradingModel(model.workerModel, ctx.state.modelCatalog)?.name || model.workerModel)} · ${e(effortLabel(model.workerModel, model.workerEffort))}</p>` : ''}</details>`;
}
export function taskCard(task, ctx) {
  const stale = task.status === 'draft' && task.materialRevision !== ctx.state.materialRevision;
  const stage = task.kind === 'grade' ? gradingStage(ctx.state, task) : null;
  const status = task.interaction?.paused && task.status === 'running' ? '暂停已请求' : ({ prepare: '整理评分要求', align: task.executionMode === 'auto' ? '准备继续' : '等待确认要求', grading: '批改中' }[stage] || statuses[task.status]);
  const events = [...(task.interaction?.events || []), ...(ctx.state.liveTasks?.[task.id]?.events || [])];
  return `<article class="conversation-task" data-history-task="${e(task.id)}"><div class="task-card-heading"><strong>${e(task.title)}</strong><span class="muted">${e(status)}</span></div>
    <p class="muted">${task.groupIds.length} 份答卷${task.kind === 'grade' ? ` · ${modeLabel(task.executionMode)}` : ''}${task.scheme ? ` · ${e(task.scheme.label)}` : ''}${task.question ? ` · ${e(task.question.label)}` : ''}${task.kind === 'grade' && !task.scheme ? ' · 按现有材料批改' : ''}</p>
    ${task.status === 'running' ? `<p class="task-phase">${e(stage === 'prepare' ? '阅读材料并整理评分要求' : stage === 'align' ? '评分实施已就绪，答卷尚未批改' : task.progress?.phase || '正在处理')}${stage === 'grading' ? ` · 已保存 ${task.progress?.completed || 0}/${task.groupIds.length} 份` : ''}</p>` : ''}
    ${events.length ? `<details class="activity-details"><summary>查看处理过程</summary><ol class="activity-list">${eventsView(events)}</ol>${progressMetrics(task.progress)}</details>` : ''}
    ${stale || task.error ? `<p class="small-notice">${e(stale ? '材料已改变，请更新范围后开始。' : task.error)}</p>` : ''}
    <div class="task-card-actions">${task.kind === 'grade' && task.status !== 'draft' ? b('show-process', '处理过程', {attrs:attr(task.id)}) : ''}${task.status === 'draft' ? `${b('edit-task', '修改安排', { attrs: attr(task.id) })}${b('start-task', task.kind === 'grade' ? task.executionMode === 'auto' ? '准备并批改' : '整理评分要求' : '开始任务', { className: 'primary', attrs: attr(task.id), disabled: stale })}` : task.status === 'running' ? `${guideForTask(ctx.state, task) ? b('open-document', '评分实施', { attrs: attr(guideForTask(ctx.state, task).id) }) : ''}${task.kind === 'grade' ? b('target-task', '补充要求', { attrs: attr(task.id) }) + b(task.interaction?.paused ? 'resume-task' : 'pause-task', task.interaction?.paused ? '继续' : '暂停', { attrs: attr(task.id) }) : ''}${b('cancel-task', '停止', { attrs: attr(task.id) })}` : ''}
    ${task.records.length ? b('task-reviews', `${task.records.length} 条评分`, { attrs: attr(task.id) }) : ''}${task.artifacts.map(artifact => b('artifact', `${icon('file-text')}${e(artifact.title)}`, { className: 'artifact-link', attrs: `data-task="${e(task.id)}" ${attr(artifact.id)}` })).join('')}
    ${task.status === 'needs_review' ? b('complete-review', '完成审阅', { attrs: attr(task.id) }) : ''}</div></article>`;
}
export function historyView(ctx) {
  const messages = ctx.state.conversation.map(row => ctx.state.chat?.id === row.id ? { ...row, ...ctx.state.chat } : row);
  const linked = new Set(messages.flatMap(row => row.taskIds || []));
  const unlinked = ctx.state.tasks.filter(task => !linked.has(task.id));
  return `<div class="conversation-heading"><strong>与 GradeOS 协作</strong>${b('manual-task', '安排任务', { className: 'quiet' })}${ib('history', '收起对话', 'close')}</div><div class="conversation-scroll" id="conversation-scroll">
    ${unlinked.filter(task => !['draft', 'running'].includes(task.status)).map(task => taskCard(task, ctx)).join('')}
    ${messages.map(row => `<article class="chat-message ${row.role}">${row.references?.some(ref => ref.target.kind === 'text') ? `<div class="message-references">${row.references.filter(ref => ref.target.kind === 'text').map(ref => b('open-document', `${icon('file-text')}${e(ref.target.title)} · v${ref.target.revision}${ref.comment ? ' · 注释' : ''}`, { className: 'reference-chip', attrs: `data-id="${e(ref.target.documentId)}" title="${e(ref.target.quote)}"` })).join('')}</div>` : ''}${row.selections?.length ? `<div class="message-references">${row.selections.map(selection => b('restore-selection', `${e(selection.role === 'scheme' ? 'MS' : selection.fileName)} · 第 ${selection.sourcePage} 页`, { className: 'reference-chip', attrs: `data-message="${e(row.id)}" ${attr(selection.id)}` })).join('')}</div>` : ''}${row.text ? `<div class="prose">${markdown(row.text)}</div>` : '<span class="muted">正在处理…</span>'}${row.status === 'running' ? '<span class="typing-dot" aria-label="正在回复"></span>' : ''}${row.events?.length ? `<details class="activity-details"><summary>处理过程 · ${new Set(row.events.map(event => event.key)).size} 步</summary><ol class="activity-list">${eventsView(row.events)}</ol></details>` : ''}${(row.taskIds || []).map(id => ctx.state.tasks.find(task => task.id === id)).filter(Boolean).map(task => taskCard(task, ctx)).join('')}</article>`).join('')}
    ${unlinked.filter(task => ['draft', 'running'].includes(task.status)).map(task => taskCard(task, ctx)).join('')}
    ${!messages.length && !ctx.state.tasks.length ? '<p class="conversation-empty">你可以随时调整安排，或圈选原页提出要求。</p>' : ''}</div>`;
}
export function statusView(ctx) {
  const task = ctx.state.tasks.find(task => task.id === ctx.targetTaskId && task.status === 'running') || ctx.state.tasks.find(task => task.status === 'running');
  if (ctx.state.chat) {
    const event = ctx.state.chat.events.at(-1);
    return `${b('history', `<span class="working-dot"></span>${e(event?.label || '正在回复…')}${icon('down')}`, { className: 'status-label' })}${ib('stop-chat', '停止回复', 'stop')}`;
  }
  const guide = (ctx.state.documents || []).find(doc => doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running'));
  if (guide) return b('open-document', `<span class="amber-dot"></span>${ctx.state.tasks.find(row => row.id === guide.taskId)?.executionMode === 'auto' ? '正在采用评分实施说明' : '可以在这里和 Agent 对齐评分要求'}${icon('right')}`, { className: 'status-label guide-ready', attrs: attr(guide.id) });
  if (task) return `${b('history', `<span class="working-dot ${task.interaction?.paused ? 'still' : ''}"></span>${e(task.interaction?.paused ? '暂停已请求，当前调用结束后暂停' : task.progress?.phase || '正在处理')}${task.kind === 'grade' && gradingStage(ctx.state, task) === 'grading' ? `<span class="muted">${task.progress?.completed || 0}/${task.groupIds.length}</span>` : ''}${icon('down')}`, { className: 'status-label' })}${task.kind === 'grade' ? ib(task.interaction?.paused ? 'resume-task' : 'pause-task', task.interaction?.paused ? '继续任务' : '暂停后续处理', task.interaction?.paused ? 'play' : 'pause', attr(task.id)) : ''}`;
  if (ctx.resultsOpen) return b('history', `${icon('history')}查看这次的批改过程${icon('down')}`, { className: 'status-label' });
  const last = ctx.state.conversation.filter(row => row.role === 'assistant').at(-1);
  return last ? b('history', `${icon('message')}<span class="reply-preview">${e(last.text.slice(0, 70))}</span>${icon('down')}`, { className: 'status-label latest-reply' }) : '';
}
export function contextChips(ctx) {
  const question = questions(ctx.state).find(row => row.id === ctx.questionId), task = ctx.state.tasks.find(task => task.id === ctx.targetTaskId && task.status === 'running');
  const record = allRecords(ctx.state).find(row => row.id === ctx.recordContextId);
  return `${record ? `<span class="reference-chip">${b('open-record', `第 ${e(record.itemId)} 题 · ${e(record.pointId?.toUpperCase() || '评分')}`, { attrs: attr(record.id) })}${ib('clear-record-context', '移除评分点引用', 'close')}</span>` : ''}${(ctx.references || []).map((ref, index) => `<span class="reference-chip">${b('reference-location', `${icon(ref.annotationId ? 'message' : 'file-text')}${e(ref.target.kind === 'text' ? `${ref.target.title} · 文字` : `${ref.target.role === 'scheme' ? 'MS' : '答卷'} · 第 ${ref.target.sourcePage} 页`)}${ref.annotationId ? ' · 注释' : ''}`, { attrs: attr(index) })}${ib('remove-reference', '移除引用', 'close', attr(index))}</span>`).join('')}${question || task ? b('clear-target', `${e(question ? '回复待确认问题' : `补充 · ${task.title}`)}${icon('close')}`, { className: 'reference-chip target-chip' }) : ''}${ctx.selections.map(selection => `<span class="reference-chip">${b('selection-page', `${icon('file-text')}${e(selection.role === 'scheme' ? 'MS' : selection.fileName)} · 第 ${selection.sourcePage} 页`, { attrs: attr(selection.id) })}${ib('remove-selection', '移除圈选引用', 'close', attr(selection.id))}</span>`).join('')}`;
}
export function questionView(ctx) {
  const question = questions(ctx.state).find(row => row.id === ctx.peekQuestionId);
  if (!question) return '';
  return `<div class="peek-heading"><span class="amber-dot"></span><strong>有一处需要你确认</strong>${ib('dismiss-question', '稍后查看', 'close')}</div><p>${e(question.question)}</p><div class="peek-actions">${question.references.filter(ref => ref.pageId).slice(0, 2).map(ref => b('event-page', `${ref.role === 'scheme' ? 'MS' : ref.role === 'question' ? '题目' : '答卷'} · 第 ${ref.page} 页 ↗`, { className: 'source-link', attrs: attr(ref.pageId) })).join('')}${b('reply-question', '回复', { className: 'primary', attrs: attr(question.id) })}</div>`;
}
