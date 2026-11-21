import { archiveSourceBody, batchInputs } from './grading-library.mjs';
import { escape as e, icon, button as b, iconButton as ib, pageById, recordScoreText, prefersReducedMotion, composerModelKey, composerModelSelect, savedComposerModel, setComposerModel } from './ui.mjs';
import { materialView, equalGroups, movedGroups, assignPages, intakeView, historyLibrary, pendingPages, uploadSources, uploadsView } from './materials.mjs';
import { taskForm, taskFormInput, refreshTaskSetup, submitTaskSetup, artifactContent } from './tasks.mjs';
import { documents, questions, pendingRecords, allRecords, header, toolbar, historyView, statusView, contextChips, questionView, workflowView, needsGradingMaterials, cohortHeading, cohortTools, processDetails } from './canvas-view.mjs';
import { WorkspaceCanvas } from './workspace-canvas.mjs';
import { findGradingAnnotation, gradingAnnotations } from './grading-annotations.mjs';
import { resultTasks, resultContext, firstResultPage, resultsOutline, recordDetail, reviewForRecord, cohortResults, cohortEntries } from './results-view.mjs';

const app = document.querySelector('#app'), dialog = document.querySelector('#dialog'), uploadInput = document.querySelector('#upload-input');
const embedded = document.documentElement.classList.contains('embedded-grading');
const fieldDocument = embedded ? window.frameElement?.ownerDocument : document;
const ctx = { embedded, state: null, token: '', selected: new Set(), selections: [], references: [], mode: 'browse', zoom: 1, pageId: null,
  scopeAll: true, uploadGrouping: 'file', intakeStep: 1, pickedPages: new Set(),
  command: '', undo: [], sorting: false, materialRole: 'student', busy: false, historyOpen: false,
  targetTaskId: null, questionId: null, peekQuestionId: null, seenQuestions: new Set(), uploadRole: 'student',
  resultsOpen: false, resultDetail: false, cohortExpanded: new Set(), cohortFilter: 'all', cohortQuery: '', cohortChat: false, resultTaskId: null, resultGroupId: null, resultRecordId: null, resultFilter: 'all', resultReport: null, resultOutline: false };
const reviewDrafts = new Map();
let surface, modalTaskId, modalSelections = [], dragPage, toastTimer, pendingFiles, sending = false, reviewRecord = null;
const toast = message => {
  const node = document.querySelector('#toast'); node.textContent = message; node.classList.add('visible');
  const alert = dialog.querySelector('.dialog-alert'); if (alert) alert.textContent = message;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('visible'), 6000);
};
const scope = () => ctx.scopeAll ? ctx.state.groups.map(group => group.id) : [...ctx.selected];
function setState(state) {
  if (state.token) ctx.token = state.token;
  const wasFollowing = ctx.processId && ctx.state?.tasks.some(task => task.id === ctx.processId && task.status === 'running');
  if (embedded && state.revision !== ctx.state?.revision) window.frameElement.dataset.gradingRevision = state.revision;
  ctx.state = state;
  if (wasFollowing && resultTasks(state).some(task => task.id === ctx.processId && ['completed','needs_review'].includes(task.status))) {
    ctx.resultTaskId = ctx.processId; ctx.processId = null; ctx.resultsOpen = true; ctx.resultDetail = false;
    ctx.returnCohortProcess = null; ctx.recordContextId = null; ctx.scopeAll = true; ctx.selected.clear();
    rosterTaskId = null;
  }
  ctx.references = ctx.references.filter(ref => !ref.annotationId || state.annotations?.some(note => note.id === ref.annotationId && !note.archivedAt)
    || findGradingAnnotation(state, ref.annotationId, ref.target?.pageId));
  ctx.selected = new Set([...ctx.selected].filter(id => state.groups.some(group => group.id === id)));
  if (!state.pages.some(page => page.id === ctx.pageId)) ctx.pageId = state.schemes[0]?.pageIds[0] || state.questions?.[0]?.pageIds[0] || state.groups[0]?.pageIds[0];
  if (ctx.processId && state.tasks.some(task => task.id === ctx.processId && task.status === 'running')) ctx.targetTaskId = ctx.processId;
  if (ctx.targetTaskId && !state.tasks.some(task => task.id === ctx.targetTaskId && task.status === 'running')) { ctx.targetTaskId = null; ctx.questionId = null; }
  const pending = questions(state);
  const incoming = pending.find(row => !ctx.seenQuestions.has(row.id));
  pending.forEach(row => ctx.seenQuestions.add(row.id));
  if (incoming) { ctx.peekQuestionId = incoming.id; const page = incoming.references.find(ref => ref.pageId)?.pageId; if (page && !ctx.processId && !ctx.resultsOpen) { ctx.pageId = page; surface?.showPage(page).catch(error => toast(error.message)); } }
  if (ctx.questionId && !pending.some(row => row.id === ctx.questionId)) ctx.questionId = null;
}
async function refresh() {
  const response = await fetch('/api/state'); if (!response.ok) throw Error('工作区连接已中断。'); setState(await response.json());
}
async function request(path, body = {}, method = 'POST') {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': ctx.token }, body: JSON.stringify({ revision: ctx.state.revision, materialRevision: ctx.state.materialRevision, ...body }) });
  const result = await response.json();
  if (!response.ok) { if (response.status === 409) { await refresh(); render(); } throw Error(result.error || '操作未完成。'); }
  if (path.endsWith('/approve') && result.documents?.some(doc => doc.taskId === ctx.returnProcessId && path === `/api/documents/${doc.id}/approve`)) ctx.processId = ctx.returnProcessId;
  setState(result); render(); return result;
}
function frame() {
  app.innerHTML = `<header class="canvas-header" id="workspace-header"></header><main class="canvas-workspace" aria-label="材料画布"><section class="workflow-stage" id="workflow-stage" aria-label="当前批改阶段" hidden></section><div class="canvas-toolbar" id="canvas-toolbar"></div><section id="batch-process" hidden aria-label="全班答卷" tabindex="-1"><div class="cohort-sheet"><header id="cohort-heading"></header><div id="cohort-meta"></div><div class="cohort-tools"><div id="cohort-tools"></div><label class="cohort-search"><svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="m13 13 4 4" stroke="currentColor" stroke-width="1.6"/></svg><input id="cohort-search" type="search" aria-label="查找答卷名称" placeholder="查找" autocomplete="off"></label></div><div id="cohort-roster"></div></div></section><div class="canvas-stage"><aside class="results-outline" id="results-outline" aria-label="批改题目导航" hidden></aside><div class="multi-canvas" id="multi-canvas"></div><p id="unlocated-source" hidden>这条评分的原卷暂时无法定位。</p><aside class="record-panel" id="record-panel" aria-label="评分审阅" hidden></aside></div></main>
    <aside class="question-peek" id="question-peek" aria-label="待确认问题" hidden></aside>
    <section class="conversation-panel" id="conversation-panel" aria-label="对话与处理过程" hidden></section><div class="collaboration-dock"><div class="agent-status" id="agent-status" aria-live="polite"></div>
      <form id="composer" class="composer"><div class="composer-context" id="composer-context"></div><textarea id="composer-input" name="goal" rows="1" maxlength="8000" aria-label="补充批改要求或提问" placeholder="补充批改要求，或针对材料提问…"></textarea>
      <div class="composer-toolbar"><div class="composer-left">${ib('upload', '添加材料', 'plus')}${b('scope', '全部答卷', { className: 'scope-button', attrs: 'id="scope-button" title="对话涉及的答卷"' })}</div><div class="composer-right"><span id="composer-model-slot"></span><button type="submit" class="send-button" id="send-button" aria-label="发送要求">${icon('arrow-up')}</button></div></div></form></div>`;
  surface = new WorkspaceCanvas(document.querySelector('#multi-canvas'), { request, getState: () => ctx.state, onReference: addReference, toast, onChange: renderWorkflow, onReview: id => showRecord(id).catch(error => toast(error.message)),
    onResultDocument: () => { closeRecord(); ctx.resultReport='grading-result'; ctx.resultOutline=false; renderResults(); renderWorkflow(); } });
  const process = document.querySelector('#batch-process'), controls = process.querySelector('.cohort-tools');
  new IntersectionObserver(([entry]) => {
    controls.toggleAttribute('data-stuck', !entry.isIntersecting && entry.boundingClientRect.bottom < entry.rootBounds?.top);
  }, {root:process}).observe(document.querySelector('#cohort-meta'));
  const input = document.querySelector('#composer-input');
  input.addEventListener('input', () => { ctx.command = input.value; resizeInput(); updateSend(); });
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!document.querySelector('#send-button').disabled) input.form.requestSubmit(); } });
}
function resizeInput() { const input = document.querySelector('#composer-input'); input.style.height = '24px'; input.style.height = `${Math.min(128, input.scrollHeight)}px`; }
function updateSend() {
  const busyChat = Boolean(ctx.state.chat) && !ctx.targetTaskId;
  const send = document.querySelector('#send-button');
  send.disabled = sending || ctx.busy || (!busyChat && !ctx.command.trim());
  send.setAttribute('aria-label', busyChat ? '停止回复' : '发送要求'); send.innerHTML = icon(busyChat ? 'stop' : 'arrow-up');
}
const rendered = new WeakMap();
function html(node, value) { if (rendered.get(node) !== value) { node.innerHTML = value; rendered.set(node, value); } }
function addReference(reference) {
  if (ctx.references.length >= 8) { toast('一次最多引用 8 处内容。'); return; }
  ctx.references.push(reference); ctx.detailChat = true;
  const group = ctx.state.groups.find(group => group.pageIds.includes(reference.target?.pageId));
  if (group && !ctx.scopeAll) ctx.selected.add(group.id);
  render(); document.querySelector('#composer-input').focus({ preventScroll: true });
}
function renderHistory() {
  const node = document.querySelector('#conversation-panel'); node.hidden = !ctx.historyOpen;
  if (!ctx.historyOpen) return;
  const scroll = node.querySelector('#conversation-scroll'), oldTop = scroll?.scrollTop, atEnd = !scroll || scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 50;
  const opened = [...node.querySelectorAll('details')].map((item, index) => item.open ? index : -1);
  html(node, historyView(ctx));
  [...node.querySelectorAll('details')].forEach((item, index) => { item.open = opened.includes(index); });
  const next = node.querySelector('#conversation-scroll'); next.scrollTop = atEnd ? next.scrollHeight : oldTop;
}
let rosterRows = [], rosterTaskId = null, returnCohortFocus = null;
const rosterNodes = new Map();
function renderRoster() {
  const node = document.querySelector('#cohort-roster');
  const focused = node.contains(document.activeElement) ? document.activeElement : null;
  const groupId = focused?.closest('[data-student]')?.dataset.student;
  const entries = cohortEntries(rosterRows, ctx), visible = new Set(entries.map(([id]) => id));
  for (const [id, previous] of rosterNodes) {
    if (!visible.has(id)) { previous.node.remove(); rosterNodes.delete(id); }
  }
  let cursor = node.firstElementChild;
  for (const [id, markup] of entries) {
    let entry = rosterNodes.get(id);
    if (entry?.markup !== markup) {
      const template = document.createElement('template'); template.innerHTML = markup;
      const next = template.content.firstElementChild;
      if (entry) {
        const resources = next.querySelector('.student-resources');
        if (resources && entry.node.querySelector('.student-resources')?.open) resources.open = true;
        if (cursor === entry.node) cursor = next;
        entry.node.replaceWith(next);
      }
      entry = { node: next, markup }; rosterNodes.set(id, entry);
    }
    if (cursor !== entry.node) node.insertBefore(entry.node, cursor);
    cursor = entry.node.nextElementSibling;
  }
  if (focused && !focused.isConnected) {
    const row = rosterNodes.get(groupId)?.node;
    const replacement = focused.matches('summary') ? row?.querySelector('.student-resources summary')
      : [...(row || node).querySelectorAll('[data-action]')].find(button => button.dataset.action === focused.dataset.action && button.dataset.id === focused.dataset.id);
    replacement?.focus({preventScroll:true});
  }
}
function renderCohort(task, process) {
  if (rosterTaskId !== task.id) {
    returnCohortFocus = null;
    rosterTaskId = task.id; ctx.cohortExpanded.clear(); ctx.cohortReadAll = false; ctx.cohortQuery = ''; ctx.cohortFilter = 'all'; ctx.cohortChat = false;
    const viewport = document.querySelector('#batch-process');
    viewport.scrollTop = 0;
    fieldDocument?.querySelector('workspace-field')?.primeScroll?.(viewport);
  }
  rosterRows = cohortResults(ctx.state, task);
  const heading = document.querySelector('#cohort-heading'), moreOpen = heading.querySelector('.cohort-more')?.open;
  html(heading, cohortHeading(ctx, task, rosterRows, process));
  if (moreOpen && heading.querySelector('.cohort-more')) heading.querySelector('.cohort-more').open = true;
  const meta = document.querySelector('#cohort-meta');
  const opened = meta.querySelector('details')?.open;
  html(meta, process ? processDetails(ctx, task) : '');
  if (opened && meta.querySelector('details')) meta.querySelector('details').open = true;
  const tools = document.querySelector('#cohort-tools'), focus = tools.contains(document.activeElement) && document.activeElement;
  html(tools, cohortTools(ctx, rosterRows));
  const search = document.querySelector('#cohort-search');
  if (search.value !== ctx.cohortQuery) search.value = ctx.cohortQuery;
  if (focus && !focus.isConnected) {
    const next = focus.id ? document.getElementById(focus.id) : tools.querySelector(`[data-action="${focus.dataset.action}"]`);
    next?.focus({preventScroll:true});
  }
  renderRoster();
  if (embedded && !process && window.frameElement.dataset.viewedBatch !== task.id) {
    window.frameElement.dataset.viewedBatch = task.id;
    window.frameElement.dispatchEvent(new CustomEvent('gradeos-result-viewed', {bubbles:true, detail:task.id}));
  }
}
function renderWorkflow() {
  const process = ctx.state.tasks.find(task => task.id === ctx.processId);
  if (process?.status === 'running') ctx.targetTaskId = process.id;
  const overview = process || (ctx.resultsOpen && !ctx.resultDetail && resultContext(ctx).task);
  const processNode = document.querySelector('#batch-process');
  processNode.hidden = !overview;
  app.classList.toggle('cohort-open', Boolean(overview));
  if (overview) {
    surface.intake.hidden = true;
    renderCohort(overview, Boolean(process));
  }
  document.querySelector('.canvas-stage').hidden = Boolean(overview);
  const intake = !overview && surface && !surface.intake.hidden;
  const field = fieldDocument?.querySelector('workspace-field');
  const scene = intake && ctx.intakeStep === 1 ? 'intake' : 'grading';
  if (field && field.dataset.scene !== scene) field.dataset.scene = scene;
  html(surface.intake, intake ? intakeView(ctx) : '');
  const toolbarNode = document.querySelector('#canvas-toolbar');
  html(toolbarNode, toolbar(ctx, needsGradingMaterials(ctx.state) || surface?.prepareBatch));
  toolbarNode.hidden = intake || Boolean(overview) || Boolean(ctx.resultsOpen && ctx.resultDetail && !ctx.detailTools);
  const dock = document.querySelector('.collaboration-dock');
  dock.hidden = intake || Boolean(overview ? !ctx.cohortChat : ctx.resultsOpen && ctx.resultDetail && !ctx.detailChat);
  app.classList.toggle('detail-chat-closed', !overview && ctx.resultsOpen && ctx.resultDetail && dock.hidden);
  const workflow = document.querySelector('#workflow-stage');
  html(workflow, intake || overview ? '' : workflowView(ctx, surface?.panels || []));
  workflow.hidden = !workflow.innerHTML;
  const view = overview ? 'cohort' : intake ? 'intake-' + ctx.intakeStep : ctx.resultsOpen ? 'result' : 'canvas';
  if (app.dataset.gradingView !== view) {
    const scrollers = overview ? [processNode] : intake ? [surface.intake]
      : app.querySelectorAll('.pane-page-scroll, .document-preview:not([hidden]), #record-panel:not([hidden])');
    for (const scroller of scrollers) if (scroller.clientHeight) field?.primeScroll?.(scroller);
    if (app.dataset.gradingView && !prefersReducedMotion()) {
      const title = overview ? processNode.querySelector('.cohort-head') : intake ? surface.intake.querySelector('h1') : workflow;
      title?.animate([{opacity:.7, transform:'translateY(5px)'}, {opacity:1, transform:'none'}],
        {duration:260, easing:'cubic-bezier(.2,.8,.2,1)'});
    }
    app.dataset.gradingView = view;
  }
}
function renderResults() {
  const detail = ctx.resultsOpen && ctx.resultDetail;
  app.classList.toggle('results-open', detail);
  const unlocated = detail && !ctx.resultReport && ctx.missingSource;
  document.querySelector('#unlocated-source').hidden = !unlocated;
  document.querySelector('#multi-canvas').hidden = Boolean(unlocated);
  app.classList.toggle('result-outline-open', detail && ctx.resultOutline);
  const outline = document.querySelector('#results-outline'); outline.hidden = !detail || Boolean(ctx.resultReport);
  if (detail) html(outline, resultsOutline(ctx));
}
function alignmentGuide() {
  const guides = (ctx.state.documents || []).filter(doc => doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running'));
  if (ctx.targetTaskId) return guides.find(doc => doc.taskId === ctx.targetTaskId);
  return guides.find(doc => ctx.references.some(ref => ref.target.documentId === doc.id))
    || guides.find(doc => surface.panels.find(panel => panel.id === surface.activeId)?.documentId === doc.id)
    || guides.findLast(doc => surface.panels.some(panel => panel.documentId === doc.id)) || guides.at(-1);
}
function render() {
  if (!ctx.state || ctx.submittingSetup) return;
  app.classList.toggle('conversation-open', ctx.historyOpen);
  renderResults();
  html(document.querySelector('#workspace-header'), header(ctx));
  if (ctx.processId || (ctx.resultsOpen && !ctx.resultDetail)) renderWorkflow(); else surface.update();
  html(document.querySelector('#composer-context'), contextChips(ctx));
  const aligning = alignmentGuide();
  const noteTask = ctx.targetTaskId && (ctx.processId || ctx.questionId || aligning?.taskId !== ctx.targetTaskId)
    ? ctx.state.tasks.find(task => task.id === ctx.targetTaskId) : null;
  html(document.querySelector('#composer-model-slot'), composerModelSelect(ctx.state,
    ctx.composerModelId ?? savedComposerModel(ctx.state.modelCatalog), noteTask ? noteTask.modelConfig?.mainModel || noteTask.modelId || ctx.state.defaultGradingConfig?.mainModel : null));
  document.querySelector('#composer-input').placeholder = ctx.questionId ? '回复这一处问题…' : ctx.recordContextId ? '针对这个评分点，写下你的问题…' : ctx.selections.length || ctx.references.length ? '针对引用内容，说说你的要求…' : aligning ? '和 Agent 对齐这次的评分要求…' : ctx.targetTaskId ? '给当前批改补充说明…' : ctx.resultsOpen ? '针对答卷提问，或圈选原卷补充说明…' : '补充批改要求，或针对材料提问…';
  document.querySelector('#scope-button').innerHTML = `${ctx.scopeAll ? '全部答卷' : ctx.selected.size ? `${ctx.selected.size} 份答卷` : '仅评分标准'}${icon('down')}`;
  html(document.querySelector('#agent-status'), statusView(ctx));
  const peek = document.querySelector('#question-peek'); html(peek, questionView(ctx)); peek.hidden = !peek.innerHTML;
  renderHistory(); updateSend();
}
function openDialog(title, content, className = '') {
  dialog.className = className;
  dialog.innerHTML = `<div class="dialog-header"><h2 id="grading-dialog-title">${e(title)}</h2>${ib('close-dialog', '关闭', 'close')}</div><div class="dialog-alert" role="alert"></div><div class="dialog-body">${content}</div>`;
  if (!dialog.open) dialog.showModal();
}
const closeDialog = () => dialog.close();
dialog.addEventListener('close', () => { pendingFiles = null; });
function openMaterials() {
  openDialog('材料与答卷划分', `<div class="material-upload">${b('upload-student', '添加答卷', { symbol: 'plus', className: 'outline' })}${b('upload-scheme', '添加评分标准', { className: 'quiet' })}${b('upload-question', '添加题目', { className: 'quiet' })}</div>${b('new-document', '新建文档', { className: 'quiet' })}${uploadsView(ctx.state)}${historyLibrary(ctx.state)}${materialView(ctx)}`, 'materials-drawer');
}
function revealCanvas() {
  if (ctx.processId) { ctx.returnProcessId = ctx.processId; ctx.processId = null; }
  if (ctx.resultsOpen && !ctx.resultDetail) ctx.resultsOpen = false;
  surface.readDocuments = true;
  render();
}
function showDocument(id, beside = false) {
  revealCanvas(); return surface.showDocument(id, beside);
}
function showPage(id) {
  if (pageById(ctx.state, id)) { revealCanvas(); ctx.pageId = id; return surface.showPage(id); }
}
function openTask(task = null) { if (ctx.busy) { toast('材料正在读取，请稍候。'); return; } modalTaskId = task?.id || null; modalSelections = task?.selections || ctx.selections; const selected = ctx.selected; ctx.selected = new Set(scope()); openDialog(task?.kind === 'assist' ? '修改安排' : '开始批改', taskForm(ctx, task, { allowStart: true }), 'task-setup-dialog'); ctx.selected = selected; }
async function savePartition(groups, remember = true) {
  const before = structuredClone(ctx.state.groups);
  const assigned = new Set(groups.flatMap(group => group.pageIds));
  const unassignedPageIds = ctx.state.pages.filter(page => page.role === 'student' && page.active !== false && !assigned.has(page.id)).map(page => page.id);
  await request('/api/materials', { groups, unassignedPageIds }, 'PATCH');
  if (remember) ctx.undo = [...ctx.undo, before].slice(-30);
  ctx.pickedPages.clear();
  if (!surface.intake.hidden) { closeDialog(); renderWorkflow(); }
  else openMaterials();
}
function reviewList() {
  const taskId = ctx.processId || (ctx.resultsOpen && ctx.resultTaskId);
  const inScope = row => !taskId || row.taskId === taskId;
  const records = pendingRecords(ctx.state).filter(inScope);
  openDialog('需要你确认', `${(ctx.state.documents || []).filter(doc => inScope(doc) && doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running' && task.executionMode !== 'auto')).map(doc => `<div class="guide-inbox"><span>${e(doc.title)} · 等待编辑与确认</span>${b('open-document', '打开文档', { attrs: `data-id="${e(doc.id)}"` })}</div>`).join('')}${questions(ctx.state).filter(inScope).map(question => `<button class="review-list-row" data-action="open-question" data-id="${e(question.id)}"><span class="amber-dot"></span><span>${e(question.question)}</span>${icon('right')}</button>`).join('')}${records.map(record => `<button class="review-list-row" data-action="open-record" data-id="${e(record.id)}"><span><strong>${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}</strong><small>${e(record.reason)}</small></span><span class="review-score">${e(recordScoreText(record))}${record.uncertainties?.length ? '<small>有待核实项</small>' : ''}</span>${icon('right')}</button>`).join('') || '<p class="muted">当前没有待处理评分。</p>'}<details class="all-records"><summary>全部评分记录</summary>${allRecords(ctx.state).filter(inScope).map(record => b('open-record', `${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}`, { className: 'record-link', attrs: `data-id="${e(record.id)}"` })).join('')}</details>`, 'review-drawer');
}
function captureReviewDraft() {
  const form = document.querySelector('#canvas-review-form');
  if (!reviewRecord || !form) return;
  const data = new FormData(form), value = data.get('score');
  const review = reviewForRecord(ctx.state, reviewRecord.taskId, reviewRecord), score = value === 'null' ? null : Number(value), reason = String(data.get('reason'));
  const key = `${reviewRecord.taskId}:${reviewRecord.id}:${reviewRecord.originalHash}`;
  if (score === (review ? review.score : reviewRecord.score) && reason === (review?.reason || '')) reviewDrafts.delete(key);
  else reviewDrafts.set(key, { score, reason });
}
function closeRecord() {
  captureReviewDraft(); document.querySelector('#record-panel').hidden = true; reviewRecord = null;
  surface?.clearRecordHighlight();
}
async function showRecord(id, taskId = null) {
  const record = allRecords(ctx.state).find(row => row.id === id && (!taskId || row.taskId === taskId)); if (!record) return;
  ctx.resultDetail = true; ctx.resultsOpen = true; ctx.processId = null; surface.readDocuments = true;
  captureReviewDraft(); reviewRecord = record; closeDialog(); ctx.peekQuestionId = null;
  ctx.resultTaskId = record.taskId; ctx.resultGroupId = record.groupId; ctx.resultRecordId = id;
  ctx.resultReport = null; ctx.resultOutline = false;
  ctx.missingSource = !gradingAnnotations(ctx.state, record.taskId, record.groupId).find(row => row.recordId === record.id)?.target;
  if (ctx.state.groups.some(group => group.id === record.groupId)) { ctx.scopeAll = false; ctx.selected = new Set([record.groupId]); }
  if (ctx.recordContextId !== id) ctx.recordContextId = null;
  const panel = document.querySelector('#record-panel'); panel.hidden = false;
  panel.innerHTML = recordDetail(ctx, record, reviewDrafts.get(`${record.taskId}:${record.id}:${record.originalHash}`));
  panel.scrollTop = 0; render();
  document.querySelector('.result-question[aria-current]')?.scrollIntoView({ block: 'nearest' });
  if (!ctx.missingSource) await surface.revealRecord(record, record.taskId);
}
async function openResults(taskId = null, groupId = null, {preferSource = false, resumeRoster = false} = {}) {
  ctx.processId = null; ctx.targetTaskId = null; ctx.questionId = null; ctx.detailChat = false; ctx.detailTools = false; ctx.missingSource = false;
  closeDialog(); closeRecord(); ctx.resultsOpen = true; ctx.historyOpen = false;
  ctx.resultTaskId = taskId || ctx.resultTaskId; ctx.resultGroupId = groupId || ctx.resultGroupId;
  surface.readDocuments = true; surface.prepareBatch = false; ctx.resultDetail = Boolean(groupId);
  const { task, group, items } = resultContext(ctx);
  if (!task) { ctx.resultsOpen = false; render(); return; }
  ctx.resultTaskId = task.id; ctx.resultGroupId = group?.id; ctx.resultFilter = 'all'; ctx.resultReport = null;
  if (!ctx.resultDetail) {
    if (!resumeRoster) rosterTaskId = null;
    ctx.scopeAll = true; ctx.selected.clear(); ctx.recordContextId = null;
    render();
    return;
  }
  ctx.scopeAll = false;
  ctx.selected = new Set(ctx.state.groups.some(row => row.id === group?.id) ? [group.id] : []);
  ctx.recordContextId = null;
  const personalReport = group && task.artifacts.find(artifact => artifact.groupId === group.id && typeof artifact.body === 'string');
  if (personalReport && !preferSource) {
    ctx.resultRecordId = null; ctx.resultReport = personalReport.id; ctx.resultOutline = false;
    await openArtifact(task.id, personalReport.id, false);
    return;
  }
  if (items.length && !preferSource) {
    ctx.resultRecordId = null; ctx.resultReport = 'grading-result'; ctx.resultOutline = false;
    render();
    return surface.showResults(task.id, group.id, false);
  }
  render();
  const record = task.records.find(row => row.id === ctx.resultRecordId && row.groupId === group?.id) || items[0]?.records[0];
  if (record) await showRecord(record.id, task.id);
  else {
    ctx.resultRecordId = null;
    const artifact = group && task.artifacts.find(row => row.groupId === group.id);
    const page = firstResultPage(ctx.state, task, group);
    if (page && (preferSource || !artifact)) await surface.showSource(page, false);
    else if (artifact) { await openArtifact(task.id, artifact.id, false); ctx.resultReport = artifact.id; }
    else ctx.missingSource = true;
    render();
  }
}
async function changeReadingView(control) {
  const { id, value } = control;
  if (id === 'result-group') await openResults(ctx.resultTaskId, value);
  else if (value === 'source') await openResults(ctx.resultTaskId, ctx.resultGroupId, {preferSource:true});
  else if (value === 'grading-result') await surface.showResults(ctx.resultTaskId, ctx.resultGroupId);
  else {
    const artifactId = value.slice('report:'.length);
    await openArtifact(ctx.resultTaskId, artifactId, false);
    ctx.resultReport = artifactId;
    render();
  }
  if (document.activeElement === document.body) document.getElementById(id)?.focus({preventScroll:true});
}
async function stepResult(delta) {
  const { filtered } = resultContext(ctx);
  const index = filtered.findIndex(item => item.records.some(row => row.id === ctx.resultRecordId));
  if (filtered[index + delta]) await showRecord(filtered[index + delta].records[0].id);
}
async function openArtifact(taskId, artifactId, beside = true) {
  const artifact = ctx.state.tasks.find(task => task.id === taskId)?.artifacts.find(row => row.id === artifactId);
  if (!artifact) return;
  if (typeof artifact.body !== 'string') { openDialog(artifact.title, artifactContent(artifact), 'artifact-dialog'); return; }
  const result = await request('/api/documents', { artifactId, taskId });
  ctx.historyOpen = false; closeRecord();
  closeDialog(); await showDocument(result.document.id, beside && surface.panels.length < 2); render();
}

async function importTextFile(file) {
  if (file.size > 480000) throw Error('可编辑文档最多支持 120,000 字。');
  const bytes = await file.arrayBuffer();
  let body;
  try { body = new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch { throw Error('请选择 UTF-8 文本文件。'); }
  if (body.includes('\0')) throw Error('请选择文本文件。');
  const result = await request('/api/documents', { title: file.name, body });
  return result.document.id;
}

function pickUpload(role) {
  if (ctx.busy) return;
  ctx.uploadRole = role;
  if (pendingFiles && dialog.open && dialog.classList.contains('drop-choice')) {
    const files = pendingFiles;
    pendingFiles = null;
    return upload(files);
  }
  uploadInput.accept = role === 'document' ? '' : '.pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp';
  uploadInput.click();
}

async function upload(selection) {
  if (!selection?.length || ctx.busy) return;
  const files = [...selection], role = ctx.uploadRole, failures = [];
  const previous = new Set(ctx.state.pages.map(page => page.id));
  let saved = 0, lastDocumentId;
  ctx.busy = true;
  updateSend();
  try {
    for (let index = 0; index < files.length; index++) {
      const file = files[index];
      ctx.uploadProgress = { index, total: files.length, name: file.name };
      renderWorkflow();

      const group = [];
      if (ctx.state.batchUploads && role !== 'document') {
        const pdf = /\.pdf$/i.test(file.name);
        const type = pdf ? /\.pdf$/i : /\.(png|jpe?g)$/i;
        for (const candidate of files.slice(index, index + (pdf ? 2 : 3))) {
          if (!type.test(candidate.name) || candidate.size > 2 * 1024 * 1024) break;
          group.push(candidate);
        }
      }
      if (group.length > 1) {
        const body = new FormData();
        for (const item of group) body.append('files', item);
        const query = new URLSearchParams({role, grouping: ctx.uploadGrouping});
        try {
          const response = await fetch(`/api/uploads/batch?${query}`, { method: 'POST', headers: { 'X-Workspace-Token': ctx.token }, body });
          const receipt = await response.json();
          if (!response.ok) throw Error(receipt.error || '导入未完成。');
          for (const item of receipt.results) {
            if (item.message) failures.push(item);
            else { saved++; ctx.undo = []; }
          }
        } catch (error) {
          failures.push(...group.map(item => ({ name: item.name, message: error.message })));
        }
        index += group.length - 1;
        continue;
      }
      try {
        if (role === 'document') lastDocumentId = await importTextFile(file);
        else {
          const query = new URLSearchParams({ receipt: '1', role, grouping: ctx.uploadGrouping, name: file.name });
          const response = await fetch(`/api/uploads?${query}`, { method: 'POST', headers: { 'X-Workspace-Token': ctx.token }, body: file });
          const state = await response.json();
          if (!response.ok) throw Error(state.error || '导入未完成。');
          ctx.undo = [];
        }
        saved++;
      } catch (error) {
        failures.push({ name: file.name, message: error.message });
      }
    }
    if (saved && role !== 'document') {
      await refresh();
      ctx.pageId = ctx.state.pages.find(page => !previous.has(page.id))?.id || ctx.pageId;
    }
    closeDialog();
    if (lastDocumentId) await showDocument(lastDocumentId, surface.panels.length < 2);
    if (failures.length) {
      openDialog('导入结果', `<p class="import-summary">已导入 ${saved} 个文件，${failures.length} 个文件需要检查。</p><ul class="import-failures">${failures.map(row => `<li><strong>${e(row.name)}</strong><span>${e(row.message)}</span></li>`).join('')}</ul>`);
      toast(`已导入 ${saved} / ${files.length} 个文件。`);
    } else {
      if (role !== 'document' && surface.intake.hidden && !ctx.processId) openMaterials();
      toast(`已导入 ${saved} 个${role === 'document' ? '文档' : '材料文件'}。`);
    }
  } finally {
    ctx.busy = false; ctx.uploadProgress = null; uploadInput.value = ''; pendingFiles = null; render();
  }
}
async function submitMessage() {
  if (ctx.state.chat && !ctx.targetTaskId) { await request('/api/chat/cancel'); return; }
  const goal = ctx.command.trim(); if (!goal || sending) return;
  sending = true; updateSend();
  try {
    const guide = alignmentGuide();
    if (ctx.targetTaskId && (ctx.processId || ctx.questionId || guide?.taskId !== ctx.targetTaskId)) {
      const task = ctx.state.tasks.find(row => row.id === ctx.targetTaskId);
      await request(`/api/tasks/${task.id}/${ctx.questionId ? 'answer' : 'note'}`, { text: goal, questionId: ctx.questionId, groupIds: task.groupIds, selections: ctx.selections, references: ctx.references });
      toast(ctx.questionId ? '回复已提交，等待 agent 接收。' : '补充已排队，将在下一次处理时送达。');
      ctx.questionId = null; ctx.targetTaskId = null; ctx.peekQuestionId = null;
    } else { await request('/api/chat', { modelId:document.querySelector('#composer-model').value || undefined, goal, selectedIds: scope(), selections: ctx.selections, references: ctx.references, recordId: ctx.recordContextId, documentId: guide?.id }); ctx.targetTaskId = null; ctx.historyOpen = true; }
    ctx.command = ''; ctx.selections = []; ctx.references = []; ctx.recordContextId = null;
    document.querySelector('#composer-input').value = ''; resizeInput(); render();
  } finally { sending = false; updateSend(); }
}
const actions = {
  'intake-step': element => {
    const setup = surface.intake.querySelector('#task-form');
    if (setup) ctx.intakeDraft = { ...taskFormInput(new FormData(setup)), materialRevision: ctx.state.materialRevision };
    ctx.intakeStep = Number(element.dataset.step); ctx.pickedPages.clear(); modalTaskId = null; modalSelections = ctx.selections;
    renderWorkflow(); surface.intake.scrollTop = 0;
    if (!prefersReducedMotion()) {
      surface.intake.firstElementChild?.animate([{ opacity: .4, transform: 'translateY(5px)' }, { opacity: 1, transform: 'none' }], { duration: 190, easing: 'ease-out' });
    }
    surface.intake.querySelector('h1')?.setAttribute('tabindex','-1'); surface.intake.querySelector('h1')?.focus({preventScroll:true});
  },
  'show-process': element => {
    ctx.processId = element.dataset.id; ctx.returnProcessId = ctx.processId; ctx.historyOpen = false; ctx.resultsOpen = false; render();
    if (ctx.processId === rosterTaskId && returnCohortFocus?.isConnected) {
      returnCohortFocus.focus({preventScroll:true}); returnCohortFocus = null;
    }
  },
  'prepare-materials': () => {
    if (ctx.processId) { try { sessionStorage.setItem('gradeos-dismissed-process', ctx.processId); } catch {} }
    if (embedded && window.parent.location.hash !== '#grading/intake') { window.parent.location.hash = 'grading/intake'; return; }
    ctx.targetTaskId = null; ctx.processId = null; ctx.intakeStep = 1;
    closeRecord(); ctx.resultsOpen = false; ctx.historyOpen = false; surface.readDocuments = false; surface.prepareBatch = true;
    surface.closeNote(); render(); surface.intake.querySelector('button')?.focus();
  },
  'close-dialog': closeDialog, materials: () => {
    if (!ctx.processId && !surface.intake.hidden) { ctx.intakeStep=1; renderWorkflow(); surface.intake.scrollTop=0; }
    else openMaterials();
  }, scope: openMaterials,
  'detail-tools': () => { ctx.detailTools = !ctx.detailTools; renderWorkflow(); },
  'detail-chat': () => { ctx.detailChat = !ctx.detailChat; renderWorkflow(); if (ctx.detailChat) document.querySelector('#composer-input').focus(); },
  'cohort-read-all': () => {
    const viewport = document.querySelector('#batch-process');
    const edge = viewport.querySelector('.cohort-tools').getBoundingClientRect().bottom;
    const row = [...viewport.querySelectorAll('[data-student]')].find(el => el.getBoundingClientRect().bottom > edge + 1);
    const offset = row ? edge - row.getBoundingClientRect().top : 0;
    ctx.cohortReadAll = !ctx.cohortReadAll; ctx.cohortExpanded.clear(); renderWorkflow();
    const next = rosterNodes.get(row?.dataset.student)?.node;
    if (next && offset >= -1) {
      const rect = next.getBoundingClientRect();
      viewport.scrollTop += rect.top - edge + (offset < rect.height ? offset : 0);
    }
  },
  'cohort-reset': () => { ctx.cohortQuery = ''; ctx.cohortFilter = 'all'; renderWorkflow(); document.querySelector('#cohort-search')?.focus(); },
  'cohort-expand': element => {
    const id = element.dataset.id;
    if (ctx.cohortExpanded.has(id)) ctx.cohortExpanded.delete(id); else ctx.cohortExpanded.add(id);
    renderRoster();
  },
  'cohort-back': async () => {
    const groupId = ctx.resultGroupId;
    if (ctx.returnCohortProcess === ctx.resultTaskId) {
      closeRecord(); ctx.processId = ctx.resultTaskId; ctx.resultsOpen = false; ctx.resultDetail = false; ctx.scopeAll = true; ctx.selected.clear(); render();
    } else await openResults(ctx.resultTaskId, null, {resumeRoster:Boolean(returnCohortFocus)});
    const row = [...document.querySelectorAll('[data-student]')].find(node => node.dataset.student === groupId);
    const origin = returnCohortFocus?.isConnected ? returnCohortFocus : returnCohortFocus && row?.querySelector('button');
    (origin || document.querySelector('#batch-process')).focus({preventScroll:true});
    returnCohortFocus = null;
  },
  'cohort-point': element => { returnCohortFocus = element; ctx.returnCohortProcess = ctx.processId; return showRecord(element.dataset.id, rosterTaskId); },
  'cohort-source': async element => {
    const row = rosterRows.find(row => row.group.id === element.dataset.id); if (!row) return;
    returnCohortFocus = element;
    ctx.returnCohortProcess = ctx.processId;
    if (row.items.length) return openResults(rosterTaskId, row.group.id, {preferSource:true});
    const task = ctx.state.tasks.find(task => task.id === rosterTaskId);
    const id = firstResultPage(ctx.state, task, row.group);
    if (!id) { toast('这份答卷的原页暂时无法定位。'); return; }
    if (resultTasks(ctx.state).includes(task)) {
      closeRecord(); ctx.resultTaskId = task.id; ctx.resultGroupId = row.group.id; ctx.resultRecordId = null;
      ctx.resultReport = null; ctx.resultDetail = true; ctx.resultsOpen = true; ctx.missingSource = false;
    } else {
      ctx.returnProcessId = task.id; ctx.resultsOpen = false;
    }
    ctx.processId = null; surface.readDocuments = true; render(); await surface.showSource(id, false);
  },
  'cohort-report': async element => {
    returnCohortFocus = element;
    ctx.returnCohortProcess = ctx.processId; ctx.processId = null; ctx.resultTaskId = rosterTaskId; ctx.resultGroupId = element.dataset.group || null;
    ctx.resultsOpen = true; ctx.resultDetail = true; ctx.resultReport = element.dataset.id; surface.readDocuments = true; closeRecord(); render();
    await openArtifact(rosterTaskId, element.dataset.id, false);
  },
  'cohort-discuss': () => { ctx.cohortChat = !ctx.cohortChat; renderWorkflow(); if (ctx.cohortChat) document.querySelector('#composer-input').focus(); },
  'archive-guide-document': element => { closeDialog(); return showDocument(element.dataset.id); },
  'history-source': async element => {
    const file = batchInputs(ctx.state).find(input => input.id === element.dataset.id);
    if (!file) throw Error('未找到这份批次材料。');
    openDialog(file.title, await archiveSourceBody(file), 'archive-source-dialog');
  },
  'group-result': element => { surface.prepareBatch = false; surface.readDocuments = true; return openResults(element.dataset.task, element.dataset.id); },
  'organize-documents': () => {
    const docs = ctx.state.documents.filter(doc => !doc.taskId);
    const folders = [...new Set(docs.map(doc => doc.folder).filter(Boolean))];
    openDialog('整理历史文档', `<form id="folder-form" class="form"><label>分类名称<input name="folder" maxlength="80" list="history-folders" placeholder="例如：课后讲评（留空移回未关联批次）"><datalist id="history-folders">${folders.map(folder => `<option value="${e(folder)}"></option>`).join('')}</datalist></label><fieldset class="scope-picker"><legend>选择文档</legend>${docs.map(doc => `<label><input type="checkbox" name="documentIds" value="${e(doc.id)}"><span>${e(doc.title)}</span><small>${e(doc.folder)}</small></label>`).join('')}</fieldset><button type="submit" class="primary">保存分类</button></form>`);
  },
  'group-pending': () => { ctx.pickedPages = new Set(pendingPages(ctx.state).map(page => page.id)); actions['assign-pages'](); },
  'remove-uploads': element => {
    const files = uploadSources(ctx.state).filter(file => !element.dataset.id || file.id === element.dataset.id);
    openDialog('移出本次材料', `<form id="remove-uploads-form" class="form">${files.map(file => `<input type="hidden" name="source" value="${e(file.id)}">`).join('')}<p>将${files.length === 1 ? e(files[0].name) : `这 ${files.length} 个文件`}从本次材料移出。未引用的原文件会删除，历史批次使用的原页会保留。</p><button class="primary">确认移出</button></form>`);
  },
  'assign-pages': () => openDialog('将选中页分到答卷', `<form id="assign-form" class="form"><label>目标答卷<select name="target"><option value="">新建答卷</option>${ctx.state.groups.map(group => `<option value="${e(group.id)}">${e(group.label)}</option>`).join('')}</select></label><label>新答卷名称<input name="label" maxlength="80" value="答卷 ${ctx.state.groups.length + 1}"></label><button type="submit" class="primary">归入答卷</button></form>`),
  history: () => { ctx.historyOpen = !ctx.historyOpen; if (ctx.historyOpen) closeRecord(); render(); },
  results: element => { ctx.returnCohortProcess = null; surface.prepareBatch = false; surface.readDocuments = true; return openResults(element.dataset.id); },
  'leave-results': () => { closeRecord(); ctx.resultsOpen = false; ctx.resultDetail = false; ctx.resultOutline = false; render(); },
  'result-outline': () => { ctx.resultOutline = !ctx.resultOutline; if (ctx.resultOutline) closeRecord(); renderResults(); renderWorkflow(); },
  'result-filter': async element => { ctx.resultFilter = element.dataset.id; const { filtered } = resultContext(ctx); renderResults(); if (filtered.length) await showRecord((filtered.find(item => item.records.some(row => row.id === ctx.resultRecordId)) || filtered[0]).records[0].id); else closeRecord(); },
  'result-question': element => { const item = resultContext(ctx).items.find(row => row.id === element.dataset.id); if (item) return showRecord(item.records[0].id); },
  'record-source': element => { ctx.missingSource = false; renderResults(); return surface.showSource(element.dataset.id); },
  'previous-result': () => stepResult(-1), 'next-result': () => stepResult(1),
  upload: () => openDialog(pendingFiles ? `导入 ${pendingFiles.length} 个文件` : '添加材料', `<div class="upload-choices">${b('upload-student', '学生作答', { className: 'primary', symbol: 'upload' })}${b('upload-scheme', '评分标准', { className: 'outline' })}${b('upload-question', '题目', { className: 'outline' })}${b('upload-document', '可编辑文本', { className: 'quiet' })}${pendingFiles ? '' : b('new-document', '新建空白文档', { className: 'quiet' })}</div><p class="muted">答卷、题目和评分标准支持 PDF 与扫描图。其他 UTF-8 文本可作为文档编辑。</p>`, pendingFiles ? 'drop-choice' : ''),
  'upload-student': () => pickUpload('student'),
  'upload-scheme': () => pickUpload('scheme'),
  'upload-question': () => pickUpload('question'),
  'rename-project': () => openDialog('作业名称', `<form id="project-form" class="form"><label>名称<input name="title" value="${e(ctx.state.title)}" maxlength="80" required></label><button class="primary" type="submit">保存</button></form>`),
  'material-role': element => { ctx.materialRole = element.dataset.role || 'student'; surface.intake.hidden ? openMaterials() : renderWorkflow(); },
  'select-all': () => { ctx.scopeAll = false; ctx.selected = new Set(ctx.selected.size === ctx.state.groups.length ? [] : ctx.state.groups.map(group => group.id)); openMaterials(); render(); },
  sorting: () => { ctx.sorting = !ctx.sorting; surface.intake.hidden ? openMaterials() : renderWorkflow(); },
  undo: async () => { const previous = ctx.undo.pop(); if (previous) await savePartition(previous, false); },
  'equal-split': () => openDialog('按人数均分', `<form id="split-form" class="form"><label>学生人数<input name="count" type="number" min="1" max="${ctx.state.pages.filter(page => page.role === 'student' && page.active !== false).length}" value="${ctx.state.groups.length || 1}" required></label><p class="muted">先均分，再调整分界。可撤销。</p><button class="primary" type="submit">应用划分</button></form>`),
  'file-split': () => {
    const sources = new Map();
    for (const id of ctx.state.pages.filter(page => page.role === 'student' && page.active !== false).map(page => page.id)) {
      const page = pageById(ctx.state, id);
      if (!sources.has(page.sourceId)) sources.set(page.sourceId, { id: crypto.randomUUID(), label: page.fileName.replace(/\.[^.]+$/, ''), pageIds: [] });
      sources.get(page.sourceId).pageIds.push(id);
    }
    for (const group of sources.values()) group.pageIds.sort((a, b) => pageById(ctx.state, a).sourcePage - pageById(ctx.state, b).sourcePage);
    return savePartition([...sources.values()]);
  },
  'split-page': element => { const groups = structuredClone(ctx.state.groups), index = groups.findIndex(group => group.pageIds.includes(element.dataset.id)), group = groups[index], boundary = group.pageIds.indexOf(element.dataset.id); if (boundary > 0) { groups.splice(index + 1, 0, { id: crypto.randomUUID(), label: `${group.label} · 分卷`, pageIds: group.pageIds.splice(boundary) }); return savePartition(groups); } },
  'merge-next': element => { const groups = structuredClone(ctx.state.groups), index = groups.findIndex(group => group.id === element.dataset.id); if (groups[index + 1]) { groups[index].pageIds.push(...groups[index + 1].pageIds); groups.splice(index + 1, 1); return savePartition(groups); } },
  'rename-group': element => { const group = ctx.state.groups.find(group => group.id === element.dataset.id); openDialog('答卷名称', `<form id="rename-group-form" data-id="${e(group.id)}" class="form"><label>名称<input name="label" value="${e(group.label)}" maxlength="80" required></label><button class="primary" type="submit">保存</button></form>`); },
  page: element => {
    if (surface.intake.hidden) { closeDialog(); return showPage(element.dataset.id); }
    const page = pageById(ctx.state, element.dataset.id);
    if (page) openDialog(`${page.fileName} · 第 ${page.sourcePage} 页`, `<img class="intake-preview" src="${e(page.url)}" alt="页面预览">`, 'intake-preview-dialog');
  }, 'event-page': element => {
    if (ctx.processId) {
      const page = pageById(ctx.state, element.dataset.id);
      if (page) openDialog(page.fileName, `<img class="intake-preview" src="${e(page.url)}" alt="原页">`, 'intake-preview-dialog');
      return;
    }
    return showPage(element.dataset.id);
  },
  'previous-page': () => pageStep(-1), 'next-page': () => pageStep(1),
  browse: () => { surface.setMode('browse'); ctx.mode = surface.mode; render(); },
  lasso: () => { surface.setMode('lasso'); ctx.mode = surface.mode; render(); }, rectangle: () => { surface.setMode('rectangle'); ctx.mode = surface.mode; render(); },
  compare: () => { surface.add(); render(); },
  'remove-reference': element => { ctx.references.splice(Number(element.dataset.id), 1); render(); },
  'reference-location': element => { const target = ctx.references[Number(element.dataset.id)]?.target; if (target) return target.kind === 'text' ? showDocument(target.documentId) : showPage(target.pageId); },
  'open-document': element => { closeDialog(); return showDocument(element.dataset.id, surface.panels.length < 2); },
  'new-document': () => openDialog('新建文档', `<form id="new-document-form" class="form"><label>文档名称<input name="title" value="未命名.md" required maxlength="100"></label><label>用途<select name="schemeId"><option value="">普通文档</option>${ctx.state.schemes.map(scheme => `<option value="${e(scheme.id)}">${e(scheme.label)} · 评分实施说明</option>`).join('')}</select></label><button type="submit" class="primary">创建并编辑</button></form>`),
  'upload-document': () => pickUpload('document'),
  'zoom-in': () => { ctx.zoom = Math.min(1.8, ctx.zoom + .1); render(); }, 'zoom-out': () => { ctx.zoom = Math.max(.6, ctx.zoom - .1); render(); }, 'zoom-reset': () => { ctx.zoom = 1; render(); },
  'remove-selection': element => { ctx.selections = ctx.selections.filter(row => row.id !== element.dataset.id); render(); },
  'selection-page': element => showPage(ctx.selections.find(row => row.id === element.dataset.id)?.pageId),
  'restore-selection': element => { const selection = ctx.state.conversation.find(row => row.id === element.dataset.message)?.selections?.find(row => row.id === element.dataset.id); if (selection) { if (!ctx.selections.some(row => row.id === selection.id) && ctx.selections.length < 8) ctx.selections.push(selection); const group = ctx.state.groups.find(group => group.pageIds.includes(selection.pageId)); if (group && !ctx.scopeAll) ctx.selected.add(group.id); showPage(selection.pageId); } },
  'manual-task': () => openTask(), 'edit-task': element => openTask(ctx.state.tasks.find(task => task.id === element.dataset.id)),
  'start-task': async element => {
    const id = element.dataset.id;
    await request(`/api/tasks/${id}/start`);
    ctx.processId = id; ctx.returnProcessId = id; ctx.targetTaskId = null; ctx.historyOpen = false;
    closeDialog(); render();
    if (embedded) window.parent.location.hash = 'grading/' + encodeURIComponent(id);
  },
  'approve-guide': element => surface.approveDocument(element.dataset.id),
  'pause-task': element => request(`/api/tasks/${element.dataset.id}/pause`), 'resume-task': element => request(`/api/tasks/${element.dataset.id}/resume`),
  'cancel-task': element => request(`/api/tasks/${element.dataset.id}/cancel`), 'stop-chat': () => request('/api/chat/cancel'),
  'target-task': element => { ctx.cohortChat = true; ctx.detailChat = true; ctx.targetTaskId = element.dataset.id; ctx.questionId = null; ctx.historyOpen = false; render(); document.querySelector('#composer-input').focus(); },
  'clear-target': () => { ctx.targetTaskId = null; ctx.questionId = null; render(); },
  'clear-record-context': () => { ctx.recordContextId = null; render(); },
  reviews: () => reviewList(), 'task-reviews': element => openResults(element.dataset.id),
  'open-question': element => { closeDialog(); ctx.peekQuestionId = element.dataset.id; const question = questions(ctx.state).find(row => row.id === element.dataset.id); showPage(question.references.find(ref => ref.pageId)?.pageId); render(); },
  'dismiss-question': () => { ctx.peekQuestionId = null; render(); },
  'reply-question': element => { ctx.cohortChat = true; ctx.detailChat = true; const question = questions(ctx.state).find(row => row.id === element.dataset.id); ctx.questionId = question.id; ctx.targetTaskId = question.taskId; ctx.historyOpen = false; render(); document.querySelector('#composer-input').focus(); },
  'open-record': element => showRecord(element.dataset.id), 'close-record': closeRecord,
  'ask-record': () => { ctx.detailChat = true; ctx.recordContextId = reviewRecord.id; ctx.scopeAll = false; ctx.selected = new Set([reviewRecord.groupId]); ctx.targetTaskId = null; ctx.questionId = null; closeRecord(); render(); document.querySelector('#composer-input').focus(); },
  'complete-review': element => request(`/api/tasks/${element.dataset.id}/review-complete`),
  artifact: element => openArtifact(element.dataset.task, element.dataset.id),
};
function pageStep(step) { const doc = documents(ctx.state).find(doc => doc.pageIds.includes(ctx.pageId)); if (doc) showPage(doc.pageIds[doc.pageIds.indexOf(ctx.pageId) + step]); }
document.addEventListener('click', event => {
  const element = event.target.closest('[data-action]'), more = document.querySelector('.cohort-more[open]');
  if (more && (!more.contains(event.target) || element)) {
    if (more.contains(document.activeElement)) more.querySelector('summary').focus({preventScroll:true});
    more.open = false;
  }
  if (element && !element.disabled && actions[element.dataset.action]) Promise.resolve().then(() => actions[element.dataset.action](element)).catch(error => toast(error.message));
});
document.addEventListener('keydown', event => {
  const more = event.target.closest('.cohort-more[open]');
  if (more && event.key === 'Escape') {
    more.open = false; more.querySelector('summary').focus({preventScroll:true});
  }
});
document.addEventListener('input', event => {
  if (event.target.id === 'cohort-search') { ctx.cohortQuery = event.target.value; renderRoster(); }
});
window.addEventListener('storage', event => {
  if (event.key === composerModelKey) { ctx.composerModelId = undefined; render(); }
});
document.addEventListener('change', event => {
  if (event.target.id === 'composer-model') {
    ctx.composerModelId = event.target.value; setComposerModel(ctx.composerModelId); render(); document.querySelector('#composer-model')?.focus({preventScroll:true});
  }
  if (event.target.id === 'cohort-filter') { ctx.cohortFilter = event.target.value; renderWorkflow(); }
  if (event.target.id === 'upload-grouping') ctx.uploadGrouping = event.target.value;
  if (event.target.matches('[data-pick-page]')) {
    const id = event.target.dataset.pickPage;
    event.target.checked ? ctx.pickedPages.add(id) : ctx.pickedPages.delete(id);
    const control = surface.intake.querySelector('[data-action="assign-pages"]');
    control.disabled = !ctx.pickedPages.size; control.textContent = ctx.pickedPages.size ? `分组（${ctx.pickedPages.size} 页）` : '分组选中页';
  }
  if (event.target.matches('#assign-form select')) event.target.form.elements.label.disabled = Boolean(event.target.value);
  if (event.target.id === 'result-task') {
    const more = event.target.closest('.cohort-more');
    if (more) { more.open = false; more.querySelector('summary').focus({preventScroll:true}); }
    openResults(event.target.value).catch(error => toast(error.message));
  }
  if (event.target.matches('#result-group, #result-view')) changeReadingView(event.target).catch(error => toast(error.message));
  if (event.target.closest('#task-form')) refreshTaskSetup(event.target.closest('#task-form'), ctx.state, event.target);
  if (event.target.id === 'document-picker') showPage(documents(ctx.state).find(doc => doc.id === event.target.value)?.pageIds[0]);
  if (event.target.matches('[data-group]')) { ctx.scopeAll = false; const id = event.target.dataset.group; event.target.checked ? ctx.selected.add(id) : ctx.selected.delete(id); render(); }
});
uploadInput.addEventListener('change', () => upload(uploadInput.files).catch(error => toast(error.message)));
document.addEventListener('submit', event => {
  event.preventDefault(); const form = event.target, data = new FormData(form);
  const startGrading = event.submitter?.value === 'start';
  if (form.dataset.submitting) return;
  Promise.resolve().then(async () => {
    if (form.id === 'composer') return submitMessage();
    if (form.id === 'folder-form') {
      await request('/api/document-folder', { folder: data.get('folder'), documentIds: data.getAll('documentIds') }, 'PATCH');
      if (surface.intake.hidden) openMaterials(); else closeDialog();
      return;
    }
    if (form.id === 'remove-uploads-form') {
      await request('/api/uploads', { sourceIds: data.getAll('source') }, 'DELETE');
      ctx.undo = []; ctx.pickedPages.clear(); ctx.intakeStep = 1;
      const active = new Set(ctx.state.pages.filter(page => page.active !== false).map(page => page.id));
      ctx.selections = ctx.selections.filter(selection => active.has(selection.pageId));
      ctx.references = ctx.references.filter(ref => !ref.target?.pageId || active.has(ref.target.pageId));
      if (surface.intake.hidden || ctx.processId) openMaterials(); else closeDialog();
      render(); return;
    }
    if (form.id === 'assign-form') return savePartition(assignPages(ctx.state.groups, ctx.pickedPages, data.get('target'), data.get('label') || '', pendingPages(ctx.state).map(page => page.id)));
    if (form.id === 'split-form') return savePartition(equalGroups([...ctx.state.groups, {pageIds: pendingPages(ctx.state).map(page => page.id)}], Number(data.get('count'))));
    if (form.id === 'rename-group-form') { const groups = structuredClone(ctx.state.groups); groups.find(group => group.id === form.dataset.id).label = String(data.get('label')); return savePartition(groups); }
    if (form.id === 'new-document-form') { const result = await request('/api/documents', { title: String(data.get('title')), schemeId: data.get('schemeId') || null, body: '' }); closeDialog(); await showDocument(result.document.id, surface.panels.length < 2); }
    if (form.id === 'project-form') { await request('/api/project', { title: String(data.get('title')) }, 'PATCH'); closeDialog(); }
    if (form.id === 'task-form') {
      form.dataset.submitting = 'true';
      for (const submit of form.querySelectorAll('[type="submit"]')) submit.disabled = true;
      ctx.submittingSetup = true;
      try {
        const taskId = await submitTaskSetup({ request, input: { ...taskFormInput(data), selections: modalSelections, references: ctx.references }, taskId: modalTaskId, start: startGrading, onSaved: id => { modalTaskId = id; } });
        if (startGrading) { ctx.processId = taskId; ctx.returnProcessId = taskId; }
        surface.prepareBatch = false; surface.readDocuments = true; ctx.intakeStep = 1; ctx.intakeDraft = null; closeDialog(); ctx.historyOpen = !startGrading; ctx.targetTaskId = null; render();
        if (embedded) window.parent.location.hash = startGrading ? 'grading/' + encodeURIComponent(taskId) : 'grading/history';
      } finally { ctx.submittingSetup = false; delete form.dataset.submitting; render(); if (form.isConnected) refreshTaskSetup(form, ctx.state); }
    }
    if (form.id === 'canvas-review-form') {
      const value = data.get('score'), record = reviewRecord;
      form.dataset.submitting = 'true'; form.querySelector('[type="submit"]').disabled = true;
      try {
        await request('/api/reviews', { taskId: record.taskId, recordId: record.id, originalHash: record.originalHash, score: value === 'null' ? null : Number(value), reason: String(data.get('reason')) });
        reviewDrafts.delete(`${record.taskId}:${record.id}:${record.originalHash}`);
        if (reviewRecord?.id === record.id) { reviewRecord = null; await showRecord(record.id); }
        toast('复核已保存，原始评分保留。');
      } finally { delete form.dataset.submitting; form.querySelector('[type="submit"]').disabled = false; }
    }
  }).catch(error => toast(error.message));
});
document.addEventListener('dragstart', event => { const tile = event.target.closest('[data-page-id]'); if (tile && ctx.sorting) { dragPage = tile.dataset.pageId; event.dataTransfer.setData('text/plain', dragPage); } });
let dragSlot;
function highlightSlot(slot) {
  if (dragSlot === slot) return;
  dragSlot?.classList.remove('drop-active'); dragSlot = slot; dragSlot?.classList.add('drop-active');
}
document.addEventListener('dragover', event => {
  if (event.dataTransfer.types.includes('Files')) {
    event.preventDefault();
    highlightSlot(ctx.busy ? null : event.target.closest('[data-upload-role]'));
  } else if (dragPage) event.preventDefault();
});
document.addEventListener('dragleave', event => {
  if (!dragSlot?.contains(event.relatedTarget)) highlightSlot(null);
});
document.addEventListener('drop', event => {
  event.preventDefault(); highlightSlot(null);
  if (event.dataTransfer.files.length) {
    if (ctx.busy) return;
    const files = [...event.dataTransfer.files], role = event.target.closest('[data-upload-role]')?.dataset.uploadRole;
    if (role) { ctx.uploadRole = role; upload(files).catch(error => toast(error.message)); }
    else { pendingFiles = files; actions.upload(); }
    return;
  } const target = event.target.closest('[data-page-id]'); if (dragPage && target) { const groups = movedGroups(ctx.state.groups, dragPage, target.dataset.pageId); if (groups) savePartition(groups).catch(error => toast(error.message)); } dragPage = null; });
document.addEventListener('dragend', () => { dragPage = null; });
for (const [name, delta] of [['page-left', -1], ['page-right', 1]]) actions[name] = element => { const ids = ctx.state.groups.flatMap(group => group.pageIds), target = ids[ids.indexOf(element.dataset.id) + delta]; if (target) return savePartition(movedGroups(ctx.state.groups, element.dataset.id, target)); };
let polling = false;
window.addEventListener('resize', () => { if (ctx.state && document.querySelector('#composer')) render(); });
setInterval(async () => { if (document.hidden || polling || sending || ctx.busy) return; polling = true; try { const before = JSON.stringify([ctx.state?.revision, ctx.state?.chat, ctx.state?.liveTasks, ctx.state?.modelCatalog]); await refresh(); if (JSON.stringify([ctx.state.revision, ctx.state.chat, ctx.state.liveTasks, ctx.state.modelCatalog]) !== before) render(); } catch { /* Keep the canvas and unsent input intact during reconnects. */ } finally { polling = false; } }, 900);
try {
  await refresh();
  const params = new URLSearchParams(location.search);
  const linkedTask = ctx.state.tasks.find(task => task.id === params.get('task'));
  const latest = (linkedTask?.kind === 'grade' && linkedTask) || ctx.state.tasks.findLast(task => task.kind === 'grade' && task.status === 'running')
    || ctx.state.tasks.findLast(task => task.kind === 'grade');
  let dismissed;
  try { dismissed = sessionStorage.getItem('gradeos-dismissed-process'); } catch {}
  if (latest && (latest.status === 'running' || ((linkedTask || latest.id !== dismissed) && ['failed','partial','interrupted','cancelled'].includes(latest.status)))) {
    ctx.processId = latest.id; ctx.returnProcessId = latest.id;
  }
  frame();
  const linkedDocument = ctx.state.documents.find(doc => doc.id === params.get('document') && (doc.taskId || null) === params.get('task'));
  const linkedArtifact = linkedTask?.artifacts?.find(artifact => artifact.id === params.get('artifact'));
  const linkedGroup = linkedTask?.groups?.find(group => group.id === params.get('group'));
  if (linkedDocument) await showDocument(linkedDocument.id);
  else if (linkedArtifact) await openArtifact(linkedTask.id, linkedArtifact.id, false);
  else if (linkedGroup && resultTasks(ctx.state).includes(linkedTask)) await openResults(linkedTask.id, linkedGroup.id);
  else if (['intake', 'materials'].includes(params.get('view'))) {
    ctx.processId = null; ctx.targetTaskId = null;
    ctx.intakeStep = params.get('view') === 'materials' && ctx.state.groups.length ? 2 : 1;
    surface.prepareBatch = true;
    render();
  }
  else if (linkedTask?.status === 'draft') { render(); openTask(linkedTask); }
  else if (linkedTask?.kind === 'assist') {
    ctx.processId = null; ctx.historyOpen = true; render();
    document.querySelector(`[data-history-task="${CSS.escape(linkedTask.id)}"]`)?.scrollIntoView({block:'nearest'});
  }
  else if (!ctx.processId && linkedTask) {
    if (resultTasks(ctx.state).some(task => task.id === linkedTask.id)) await openResults(linkedTask.id);
    else { ctx.processId = linkedTask.id; ctx.returnProcessId = linkedTask.id; render(); }
  }
  else if (!ctx.processId && resultTasks(ctx.state).length && !ctx.state.tasks.some(task => ['running', 'draft'].includes(task.status))) await openResults();
  else render();
} catch (error) { app.innerHTML = `<section class="empty"><h1>工作区暂时无法打开</h1><p>${e(error.message)}</p><a href="/">重新加载</a></section>`; }
