import { escape as e, icon, button, statuses, empty, markdown } from './ui.mjs';

const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
export function progressMetrics(progress) {
  if (!progress) return '';
  const parts = [];
  if (finite(progress.elapsedSeconds)) {
    const seconds = Math.floor(progress.elapsedSeconds);
    parts.push(`已用 ${seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`}`);
  }
  if (finite(progress.settledCostUsd)) parts.push(`已结算 $${progress.settledCostUsd.toFixed(5)}`);
  if (progress.unknownCostRequests > 0) parts.push('另有费用待确认');
  return parts.length ? `<p class="muted">${parts.map(e).join(' · ')}</p>` : '';
}

export function taskView(ctx) {
  const { state } = ctx;
  const task = state.tasks.find(item => item.id === ctx.activeTaskId);
  if (!task || ctx.taskList) {
    if (!state.tasks.length) return empty('安排批改', '选好答卷即可安排批改，也可以补充批改要求。', `${button('manual-task', '安排批改', { className: 'primary' })}${button('assistant', '补充要求', { className: 'text-button' })}`);
    return `<section class="task-list content narrow"><div class="section-toolbar"><h1>任务</h1>${button('manual-task', '新任务', { className: 'text-button blue', symbol: 'plus' })}</div>
      ${[...state.tasks].reverse().map(item => `<button class="task-row" data-action="open-task" data-id="${e(item.id)}"><div><strong>${e(item.title)}</strong><span class="muted">${item.groupIds.length} 份答卷 · ${item.kind === 'grade' ? '批改' : '自由任务'}</span></div><span class="task-status ${item.status === 'running' ? 'blue' : ''}">${e(statuses[item.status] || item.status)}</span>${icon('right')}</button>`).join('')}</section>`;
  }
  const stale = task.status === 'draft' && task.materialRevision !== state.materialRevision;
  const remaining = state.groups.filter(group => !task.groupIds.includes(group.id)).length;
  return `<section class="task-detail content narrow"><div class="eyebrow">${e(statuses[task.status] || task.status)} · ${task.kind === 'grade' ? '整卷批改' : '自由任务'}</div>
    <div class="task-title"><h1>${e(task.title)}</h1>${task.status === 'draft' ? button('edit-task', '', { className: 'icon-button', symbol: 'edit', attrs: 'aria-label="修改任务"' }) : ''}</div>
    ${task.goal !== task.title ? `<p class="goal-text">${e(task.goal)}</p>` : ''}
    ${task.supplementalInstructions ? `<p class="goal-text">补充批改要求：${e(task.supplementalInstructions)}</p>` : ''}
    <dl class="task-fields"><div><dt>材料</dt><dd>${button('task-materials', `${task.groups.length} 份答卷 · ${task.pageCount} 页`, { className: 'text-button blue' })}</dd></div>
      ${task.kind === 'grade' ? `<div><dt>评分标准</dt><dd>${button(task.status === 'draft' ? 'edit-task' : 'show-scheme', e(task.scheme?.label || '选择评分标准'), { className: 'text-button blue' })}</dd></div>` : ''}
      <div><dt>完成后</dt><dd>${task.status === 'draft' ? button('edit-task', task.after === 'review' ? '等我审阅' : '保存成果', { className: 'text-button' }) : task.after === 'review' ? '等我审阅' : '保存成果'}</dd></div>
    </dl>
    ${task.status === 'draft' ? `<p class="muted remaining">其余 ${remaining} 份不在本任务范围内</p>${stale ? '<p class="notice">材料已改变，请修改任务以更新范围。</p>' : ''}<div class="task-actions">${button('edit-task', '修改安排', { className: 'text-button blue' })}${button('start-task', task.kind === 'grade' ? `开始这 ${task.groups.length} 份` : '开始任务', { className: 'primary', disabled: stale || ctx.busy })}</div>` : ''}
    ${task.status === 'running' ? `<div class="run-progress" role="status" aria-live="polite"><div class="title-line"><span class="spinner"></span><span>${task.kind === 'assist' ? 'GradeOS 正在处理任务' : e(task.progress?.phase || '正在处理')}</span></div>${task.kind === 'grade' ? `<p class="muted">评分已保存 ${task.progress?.completed ?? 0}/${task.groups.length} 份${finite(task.progress?.feedbackCompleted) ? ` · 个人报告可读 ${task.progress.feedbackCompleted}/${task.groups.length} 份` : ''}</p><progress aria-label="已保存评分的答卷份数" value="${task.progress?.completed ?? 0}" max="${task.groups.length}"></progress>` : ''}${progressMetrics(task.progress)}${button('cancel-task', task.progress?.stopping ? '正在停止…' : '停止任务', { className: 'text-button', disabled: task.progress?.stopping })}</div>` : progressMetrics(task.progress)}
    ${task.error ? `<p class="notice">${e(task.error)}</p>` : ''}
    ${task.records.length ? `<div class="result-line"><span>${task.records.length} 条评分依据</span>${button('review-task', '打开审阅', { className: 'primary' })}</div>` : ''}
    ${task.artifacts.length ? `<div class="artifacts"><h2>成果</h2>${task.artifacts.map(artifact => `<button class="artifact-row" data-action="artifact" data-id="${e(artifact.id)}">${icon('file-text')}<span>${e(artifact.title)}</span>${icon('right')}</button>`).join('')}${task.kind === 'assist' && task.status === 'needs_review' ? button('review-complete', '完成审阅', { className: 'text-button blue' }) : ''}</div>` : ''}
    <button class="quiet-composer" data-action="assistant">${icon('message')}<span>给 GradeOS 补充要求…</span></button>
  </section>`;
}

export function taskForm(ctx, task = null, { allowStart = false } = {}) {
  const selected = new Set(task?.groupIds || [...ctx.selected]);
  const mode = task ? task.executionMode || 'review' : 'auto';
  const supplement = task ? task.supplementalInstructions ?? task.goal ?? '' : ctx.command || '';
  const schemeId = task ? task.schemeId : ctx.state.schemes[0]?.id;
  const questionId = task ? task.questionId : ctx.state.questions?.[0]?.id;
  const selectedGroups = ctx.state.groups.filter(group => selected.has(group.id));
  const canStart = allowStart && task?.kind !== 'assist';
  return `<form id="task-form" class="form task-setup"><input type="hidden" name="kind" value="${task?.kind === 'assist' ? 'assist' : 'grade'}">
    ${task?.title ? `<input type="hidden" name="title" value="${e(task.title)}">` : ''}
    <details class="setup-materials" ${selectedGroups.length ? '' : 'open'}><summary><span><strong data-setup-count>${selectedGroups.length} 份答卷 · ${selectedGroups.reduce((sum, group) => sum + group.pageIds.length, 0)} 页</strong><small data-setup-materials>题目：${e((ctx.state.questions || []).find(row => row.id === questionId)?.label || '无')} · MS：${e(ctx.state.schemes.find(row => row.id === schemeId)?.label || '无')}</small></span><span class="setup-edit">调整材料与范围</span></summary>
    <div class="setup-material-fields"><fieldset class="scope-picker"><legend>本次批改的答卷</legend>${ctx.state.groups.map(group => `<label><input type="checkbox" name="groupIds" value="${e(group.id)}" ${selected.has(group.id) ? 'checked' : ''}><span>${e(group.label)}</span><span class="muted">${group.pageIds.length} 页</span></label>`).join('') || '<p class="muted">请先上传答卷。</p>'}</fieldset>
    <div class="form-columns"><label>题目（可选）<select name="questionId"><option value="">无</option>${(ctx.state.questions || []).map(question => `<option value="${e(question.id)}" ${questionId === question.id ? 'selected' : ''}>${e(question.label)}</option>`).join('')}</select></label>
    <label>Marking scheme（可选）<select name="schemeId"><option value="">无</option>${ctx.state.schemes.map(scheme => `<option value="${e(scheme.id)}" ${schemeId === scheme.id ? 'selected' : ''}>${e(scheme.label)}</option>`).join('')}</select></label></div></div></details>
    ${task?.kind === 'assist' ? `<label>任务说明<textarea name="goal" required maxlength="8000" rows="3">${e(task.goal)}</textarea></label>` : ''}
    <label>补充批改要求（可选）<textarea name="supplementalInstructions" maxlength="8000" rows="3" placeholder="例如：高中数学，DSE；用中文解释失分原因。留空也可以。">${e(supplement)}</textarea></label>
    <details class="setup-options"><summary>更多设置<span>${mode === 'auto' ? '自动继续' : '先确认再批改'}${task?.allowWebSearch ? ' · 可联网' : ''}</span></summary><div class="setup-option-fields">
    ${task?.gradingContext ? `<label>已有学科与考试信息<textarea name="gradingContext" maxlength="4000" rows="2">${e(task.gradingContext)}</textarea></label>` : ''}
    <label>批改方式<select name="executionMode"><option value="review" ${mode === 'review' ? 'selected' : ''}>先让我确认评分要求，再批改</option><option value="auto" ${mode === 'auto' ? 'selected' : ''}>自动继续批改</option></select></label>
    <label class="research-option"><input type="checkbox" name="allowWebSearch" ${task?.allowWebSearch ? 'checked' : ''}>允许联网查阅参考资料</label>${ctx.state.researchAvailable ? '' : '<p class="muted">当前未连接检索服务。</p>'}
    <label>完成后<select name="after"><option value="review" ${task?.after !== 'stop' ? 'selected' : ''}>等我审阅结果</option><option value="stop" ${task?.after === 'stop' ? 'selected' : ''}>保存结果</option></select></label></div></details>
    <div class="setup-footer"><p class="setup-mode-hint" data-setup-mode>${taskModeHint(mode)}</p>${canStart && !ctx.state.agentReady ? '<p class="setup-connection-note">模型尚未连接，可以先保存草稿。</p>' : ''}
    <div class="form-actions">${canStart ? `<button type="submit" name="intent" value="save" class="quiet" ${selectedGroups.length ? '' : 'disabled'}>保存草稿</button><button type="submit" name="intent" value="start" class="primary" ${selectedGroups.length && ctx.state.agentReady ? '' : 'disabled'}>开始批改</button>` : `<button class="primary" type="submit" name="intent" value="save" ${selectedGroups.length ? '' : 'disabled'}>保存安排</button>`}</div></div></form>`;
}

export const taskModeHint = mode => mode === 'auto' ? '准备好评分要求后自动批改；有具体疑问时会询问你。' : '先准备评分要求，等你确认后再批改答卷。';

export function refreshTaskSetup(form, state) {
  const input = taskFormInput(new FormData(form));
  const groups = state.groups.filter(group => input.groupIds.includes(group.id));
  form.querySelector('[data-setup-count]').textContent = `${groups.length} 份答卷 · ${groups.reduce((sum, group) => sum + group.pageIds.length, 0)} 页`;
  form.querySelector('[data-setup-materials]').textContent = `题目：${(state.questions || []).find(row => row.id === input.questionId)?.label || '无'} · MS：${state.schemes.find(row => row.id === input.schemeId)?.label || '无'}`;
  form.querySelector('[data-setup-mode]').textContent = taskModeHint(input.executionMode);
  form.querySelector('.setup-options summary span').textContent = `${input.executionMode === 'auto' ? '自动继续' : '先确认再批改'}${input.allowWebSearch ? ' · 可联网' : ''}`;
  for (const submit of form.querySelectorAll('[type="submit"]')) submit.disabled = !groups.length || (submit.value === 'start' && !state.agentReady);
}

export function taskFormInput(data) {
  const kind = data.get('kind') === 'assist' ? 'assist' : 'grade';
  return { kind, ...(data.get('title') ? { title: String(data.get('title')) } : {}), ...(kind === 'assist' ? { goal: String(data.get('goal') || '').trim() } : {}),
    supplementalInstructions: String(data.get('supplementalInstructions') || '').trim(),
    after: data.get('after'), executionMode: data.get('executionMode') || 'review',
    groupIds: data.getAll('groupIds'), schemeId: data.get('schemeId') || null,
    questionId: data.get('questionId') || null, gradingContext: String(data.get('gradingContext') || '').trim(),
    allowWebSearch: data.get('allowWebSearch') === 'on' };
}

// Keep a saved draft when starting fails, so a retry uses the same batch.
export async function submitTaskSetup({ request, input, taskId = null, start = false, onSaved = () => {} }) {
  const saved = await request(taskId ? `/api/tasks/${taskId}` : '/api/tasks', input, taskId ? 'PATCH' : 'POST');
  const savedId = taskId || saved.createdTaskId;
  if (!savedId) throw Error('批改草稿已保存，请从任务记录中打开后继续。');
  onSaved(savedId);
  if (start) await request(`/api/tasks/${savedId}/start`);
  return savedId;
}

export const artifactContent = artifact => `<article class="prose">${markdown(artifact.body)}</article>`;
