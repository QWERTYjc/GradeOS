import { escape as e, icon, button as b, iconButton as ib, pageById, recordScoreText } from './ui.mjs';
import { materialView, equalGroups, movedGroups, assignPages, intakeView, historyLibrary } from './materials.mjs';
import { taskForm, taskFormInput, refreshTaskSetup, submitTaskSetup, artifactContent } from './tasks.mjs';
import { documents, questions, pendingRecords, allRecords, header, toolbar, historyView, statusView, contextChips, questionView, workflowView, needsGradingMaterials } from './canvas-view.mjs';
import { WorkspaceCanvas } from './workspace-canvas.mjs';
import { findGradingAnnotation } from './grading-annotations.mjs';
import { resultTasks, resultContext, resultsOutline, recordDetail, reviewForRecord } from './results-view.mjs';

const app = document.querySelector('#app'), dialog = document.querySelector('#dialog'), uploadInput = document.querySelector('#upload-input');
const ctx = { state: null, token: '', selected: new Set(), selections: [], references: [], mode: 'browse', zoom: 1, pageId: null,
  scopeAll: true, intakeStep: 1, pickedPages: new Set(),
  command: '', undo: [], sorting: false, materialRole: 'student', busy: false, historyOpen: false,
  targetTaskId: null, questionId: null, peekQuestionId: null, seenQuestions: new Set(), uploadRole: 'student',
  resultsOpen: false, resultTaskId: null, resultGroupId: null, resultRecordId: null, resultFilter: 'all', resultReport: null, resultOutline: false };
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
  const previousDocuments = ctx.state ? new Set((ctx.state.documents || []).map(row => row.id)) : null;
  ctx.state = state;
  ctx.references = ctx.references.filter(ref => !ref.annotationId || state.annotations?.some(note => note.id === ref.annotationId && !note.archivedAt)
    || findGradingAnnotation(state, ref.annotationId, ref.target?.pageId));
  const incomingDocument = previousDocuments && state.documents?.find(row => !previousDocuments.has(row.id) && row.actor === 'agent' && row.kind === 'marking_guide');
  if (incomingDocument && surface) queueMicrotask(() => surface.showDocument(incomingDocument.id, surface.panels.length < 2).catch(error => toast(error.message)));
  ctx.selected = new Set([...ctx.selected].filter(id => state.groups.some(group => group.id === id)));
  if (!state.pages.some(page => page.id === ctx.pageId)) ctx.pageId = state.schemes[0]?.pageIds[0] || state.questions?.[0]?.pageIds[0] || state.groups[0]?.pageIds[0];
  if (ctx.targetTaskId && !state.tasks.some(task => task.id === ctx.targetTaskId && task.status === 'running')) { ctx.targetTaskId = null; ctx.questionId = null; }
  const pending = questions(state);
  const incoming = pending.find(row => !ctx.seenQuestions.has(row.id));
  pending.forEach(row => ctx.seenQuestions.add(row.id));
  if (incoming) { ctx.peekQuestionId = incoming.id; const page = incoming.references.find(ref => ref.pageId)?.pageId; if (page) { ctx.pageId = page; surface?.showPage(page).catch(error => toast(error.message)); } }
  if (ctx.questionId && !pending.some(row => row.id === ctx.questionId)) ctx.questionId = null;
}
async function refresh() {
  const response = await fetch('/api/state'); if (!response.ok) throw Error('工作区连接已中断。'); setState(await response.json());
}
async function request(path, body = {}, method = 'POST') {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': ctx.token }, body: JSON.stringify({ revision: ctx.state.revision, materialRevision: ctx.state.materialRevision, ...body }) });
  const result = await response.json();
  if (!response.ok) { if (response.status === 409) { await refresh(); render(); } throw Error(result.error || '操作未完成。'); }
  setState(result); render(); return result;
}
function frame() {
  app.innerHTML = `<header class="canvas-header" id="workspace-header"></header><main class="canvas-workspace" aria-label="材料画布"><section class="workflow-stage" id="workflow-stage" aria-label="当前批改阶段" hidden></section><div class="canvas-toolbar" id="canvas-toolbar"></div><div class="canvas-stage"><aside class="results-outline" id="results-outline" aria-label="批改题目导航" hidden></aside><div class="multi-canvas" id="multi-canvas"></div><aside class="record-panel" id="record-panel" aria-label="评分审阅" hidden></aside></div></main>
    <aside class="question-peek" id="question-peek" aria-label="待确认问题" hidden></aside>
    <section class="conversation-panel" id="conversation-panel" aria-label="对话与处理过程" hidden></section><div class="collaboration-dock"><div class="agent-status" id="agent-status" aria-live="polite"></div>
      <form id="composer" class="composer"><div class="composer-context" id="composer-context"></div><textarea id="composer-input" name="goal" rows="1" maxlength="8000" aria-label="补充批改要求或提问" placeholder="补充批改要求，或针对材料提问…"></textarea>
      <div class="composer-toolbar"><div class="composer-left">${ib('upload', '添加材料', 'plus')}${b('scope', '全部答卷', { className: 'scope-button', attrs: 'id="scope-button" title="对话涉及的答卷"' })}</div><div class="composer-right"><span class="composer-agent">GradeOS</span><button type="submit" class="send-button" id="send-button" aria-label="发送要求">${icon('arrow-up')}</button></div></div></form></div>`;
  surface = new WorkspaceCanvas(document.querySelector('#multi-canvas'), { request, getState: () => ctx.state, onReference: addReference, toast, onChange: renderWorkflow, onReview: id => showRecord(id).catch(error => toast(error.message)),
    onResultDocument: () => { closeRecord(); ctx.resultReport='grading-result'; ctx.resultOutline=false; renderResults(); renderWorkflow(); } });
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
  ctx.references.push(reference);
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
function renderWorkflow() {
  const intake = surface && !surface.intake.hidden;
  html(surface.intake, intake ? intakeView(ctx) : '');
  const toolbarNode = document.querySelector('#canvas-toolbar');
  html(toolbarNode, toolbar(ctx, needsGradingMaterials(ctx.state) || surface?.prepareBatch));
  toolbarNode.hidden = intake;
  document.querySelector('.collaboration-dock').hidden = intake;
  const workflow = document.querySelector('#workflow-stage');
  html(workflow, intake ? '' : workflowView(ctx, surface?.panels || []));
  workflow.hidden = !workflow.innerHTML;
}
function renderResults() {
  app.classList.toggle('results-open', ctx.resultsOpen);
  app.classList.toggle('result-outline-open', ctx.resultsOpen && ctx.resultOutline);
  const outline = document.querySelector('#results-outline'); outline.hidden = !ctx.resultsOpen || Boolean(ctx.resultReport);
  if (ctx.resultsOpen) html(outline, resultsOutline(ctx));
}
function alignmentGuide() {
  const guides = (ctx.state.documents || []).filter(doc => doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running'));
  if (ctx.targetTaskId) return guides.find(doc => doc.taskId === ctx.targetTaskId);
  return guides.find(doc => ctx.references.some(ref => ref.target.documentId === doc.id))
    || guides.find(doc => surface.panels.find(panel => panel.id === surface.activeId)?.documentId === doc.id)
    || guides.findLast(doc => surface.panels.some(panel => panel.documentId === doc.id)) || guides.at(-1);
}
function render() {
  if (!ctx.state) return;
  app.classList.toggle('conversation-open', ctx.historyOpen);
  renderResults();
  html(document.querySelector('#workspace-header'), header(ctx));
  surface.update();
  html(document.querySelector('#composer-context'), contextChips(ctx));
  const aligning = alignmentGuide();
  document.querySelector('#composer-input').placeholder = ctx.questionId ? '回复这一处问题…' : ctx.recordContextId ? '针对这个评分点，写下你的问题…' : ctx.selections.length || ctx.references.length ? '针对引用内容，说说你的要求…' : aligning ? '和 Agent 对齐这次的评分要求…' : ctx.targetTaskId ? '给当前批改补充说明…' : ctx.resultsOpen ? '针对答卷提问，或圈选原卷补充说明…' : '补充批改要求，或针对材料提问…';
  document.querySelector('#scope-button').innerHTML = `${ctx.scopeAll ? '全部答卷' : ctx.selected.size ? `${ctx.selected.size} 份答卷` : '仅评分标准'}${icon('down')}`;
  html(document.querySelector('#agent-status'), statusView(ctx));
  const peek = document.querySelector('#question-peek'); html(peek, questionView(ctx)); peek.hidden = !peek.innerHTML;
  renderHistory(); updateSend();
}
function openDialog(title, content, className = '') {
  dialog.className = className;
  dialog.innerHTML = `<div class="dialog-header"><h2>${e(title)}</h2>${ib('close-dialog', '关闭', 'close')}</div><div class="dialog-alert" role="alert"></div><div class="dialog-body">${content}</div>`;
  if (!dialog.open) dialog.showModal();
}
const closeDialog = () => dialog.close();
function openMaterials() {
  openDialog('材料与答卷划分', `<div class="material-upload">${b('upload-student', '添加答卷', { symbol: 'plus', className: 'outline' })}${b('upload-scheme', '添加评分标准', { className: 'quiet' })}${b('upload-question', '添加题目', { className: 'quiet' })}</div>${b('new-document', '新建文档', { className: 'quiet' })}${historyLibrary(ctx.state)}${materialView(ctx)}`, 'materials-drawer');
}
function showPage(id) { if (pageById(ctx.state, id)) { ctx.pageId = id; return surface.showPage(id); } }
function openTask(task = null) { if (ctx.busy) { toast('材料正在读取，请稍候。'); return; } modalTaskId = task?.id || null; modalSelections = task?.selections || ctx.selections; const selected = ctx.selected; ctx.selected = new Set(scope()); openDialog(task?.kind === 'assist' ? '修改安排' : '开始批改', taskForm(ctx, task, { allowStart: true }), 'task-setup-dialog'); ctx.selected = selected; }
async function savePartition(groups, remember = true) {
  const before = structuredClone(ctx.state.groups); await request('/api/materials', { groups }, 'PATCH');
  if (remember) ctx.undo = [...ctx.undo, before].slice(-30);
  ctx.pickedPages.clear();
  if (!surface.intake.hidden) { closeDialog(); renderWorkflow(); }
  else openMaterials();
}
function reviewList(taskId = null) {
  const records = taskId ? allRecords(ctx.state).filter(row => row.taskId === taskId) : pendingRecords(ctx.state);
  openDialog(taskId ? '评分记录' : '需要你确认', `${(ctx.state.documents || []).filter(doc => doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running')).map(doc => `<div class="guide-inbox"><span>${e(doc.title)} · 等待编辑与确认</span>${b('open-document', '打开文档', { attrs: `data-id="${e(doc.id)}"` })}</div>`).join('')}${questions(ctx.state).map(question => `<button class="review-list-row" data-action="open-question" data-id="${e(question.id)}"><span class="amber-dot"></span><span>${e(question.question)}</span>${icon('right')}</button>`).join('')}${records.map(record => `<button class="review-list-row" data-action="open-record" data-id="${e(record.id)}"><span><strong>${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}</strong><small>${e(record.reason)}</small></span><span class="review-score">${e(recordScoreText(record))}${record.uncertainties?.length ? '<small>有待核实项</small>' : ''}</span>${icon('right')}</button>`).join('') || '<p class="muted">当前没有待处理评分。</p>'}${!taskId ? `<details class="all-records"><summary>全部评分记录</summary>${allRecords(ctx.state).map(record => b('open-record', `${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}`, { className: 'record-link', attrs: `data-id="${e(record.id)}"` })).join('')}</details>` : ''}`, 'review-drawer');
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
async function showRecord(id) {
  const record = allRecords(ctx.state).find(row => row.id === id); if (!record) return;
  captureReviewDraft(); reviewRecord = record; closeDialog(); ctx.peekQuestionId = null;
  ctx.resultTaskId = record.taskId; ctx.resultGroupId = record.groupId; ctx.resultRecordId = id;
  ctx.resultReport = null; ctx.resultOutline = false;
  if (ctx.state.groups.some(group => group.id === record.groupId)) { ctx.scopeAll = false; ctx.selected = new Set([record.groupId]); }
  if (ctx.recordContextId !== id) ctx.recordContextId = null;
  const panel = document.querySelector('#record-panel'); panel.hidden = false;
  panel.innerHTML = recordDetail(ctx, record, reviewDrafts.get(`${record.taskId}:${record.id}:${record.originalHash}`));
  panel.scrollTop = 0; render();
  document.querySelector('.result-question[aria-current]')?.scrollIntoView({ block: 'nearest' });
  await surface.revealRecord(record, record.taskId);
}
async function openResults(taskId = null, groupId = null) {
  closeDialog(); closeRecord(); ctx.resultsOpen = true; ctx.historyOpen = false;
  ctx.resultTaskId = taskId || ctx.resultTaskId; ctx.resultGroupId = groupId || ctx.resultGroupId;
  const { task, group, items } = resultContext(ctx);
  if (!task) { ctx.resultsOpen = false; render(); return; }
  ctx.resultTaskId = task.id; ctx.resultGroupId = group?.id; ctx.resultFilter = 'all'; ctx.resultReport = null;
  render();
  const record = task.records.find(row => row.id === ctx.resultRecordId && row.groupId === group?.id) || items[0]?.records[0];
  if (record) await showRecord(record.id);
  else {
    ctx.resultRecordId = null;
    const artifact = task.artifacts.find(row => row.groupId === group?.id) || task.artifacts.find(row => !row.groupId);
    if (artifact) { await openArtifact(task.id, artifact.id, false); ctx.resultReport = artifact.id; }
    else if (group?.pageIds[0]) await surface.showSource(group.pageIds[0]);
    render();
  }
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
  closeDialog(); await surface.showDocument(result.document.id, beside && surface.panels.length < 2); render();
}

async function upload(files) {
  if (!files?.length || ctx.busy) return;
  ctx.busy = true; updateSend(); renderWorkflow(); const role = ctx.uploadRole;
  try {
    for (const [index, file] of [...files].entries()) {
      if (role === 'document' || /\.(md|txt|csv|json)$/i.test(file.name)) { const result = await request('/api/documents', { title: file.name, body: await file.text() }); await surface.showDocument(result.document.id, surface.panels.length < 2); continue; }
      toast(`正在读取 ${file.name}（${index + 1}/${files.length}）…`);
      const response = await fetch(`/api/uploads?role=${role}&name=${encodeURIComponent(file.name)}`, { method: 'POST', headers: { 'X-Workspace-Token': ctx.token }, body: file });
      const state = await response.json(); if (!response.ok) throw Error(state.error);
      const previous = new Set(ctx.state.pages.map(page => page.id)); setState(state);
      ctx.pageId = state.pages.find(page => !previous.has(page.id))?.id || ctx.pageId; ctx.undo = [];
    }
    closeDialog(); render(); if (role !== 'document' && surface.intake.hidden) await showPage(ctx.pageId); toast(role === 'document' ? '文档已导入，可以直接编辑。' : '材料已保存，可以检查页面分组。');
  } finally { ctx.busy = false; uploadInput.value = ''; pendingFiles = null; render(); }
}
async function submitMessage() {
  if (ctx.state.chat && !ctx.targetTaskId) { await request('/api/chat/cancel'); return; }
  const goal = ctx.command.trim(); if (!goal || sending) return;
  sending = true; updateSend();
  try {
    const guide = alignmentGuide();
    if (ctx.targetTaskId && (ctx.questionId || guide?.taskId !== ctx.targetTaskId)) {
      const task = ctx.state.tasks.find(row => row.id === ctx.targetTaskId);
      await request(`/api/tasks/${task.id}/${ctx.questionId ? 'answer' : 'note'}`, { text: goal, questionId: ctx.questionId, groupIds: task.groupIds, selections: ctx.selections, references: ctx.references });
      toast(ctx.questionId ? '回复已提交，等待 agent 接收。' : '补充已排队，将在下一次处理时送达。');
      ctx.questionId = null; ctx.targetTaskId = null; ctx.peekQuestionId = null;
    } else { await request('/api/chat', { goal, selectedIds: scope(), selections: ctx.selections, references: ctx.references, recordId: ctx.recordContextId, documentId: guide?.id }); ctx.targetTaskId = null; ctx.historyOpen = true; }
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
    surface.intake.querySelector('h1')?.setAttribute('tabindex','-1'); surface.intake.querySelector('h1')?.focus({preventScroll:true});
  },
  'prepare-materials': () => {
    closeRecord(); ctx.resultsOpen = false; ctx.historyOpen = false; surface.readDocuments = false; surface.prepareBatch = true;
    surface.closeNote(); render(); surface.intake.querySelector('button')?.focus();
  },
  'close-dialog': closeDialog, materials: () => {
    if (!surface.intake.hidden) { ctx.intakeStep=1; renderWorkflow(); surface.intake.scrollTop=0; }
    else openMaterials();
  }, scope: openMaterials,
  'group-result': element => { surface.prepareBatch = false; surface.readDocuments = true; return openResults(element.dataset.task, element.dataset.id); },
  'organize-documents': () => {
    const docs = ctx.state.documents.filter(doc => !doc.taskId);
    const folders = [...new Set(docs.map(doc => doc.folder).filter(Boolean))];
    openDialog('整理历史文档', `<form id="folder-form" class="form"><label>分类名称<input name="folder" maxlength="80" list="history-folders" placeholder="例如：课后讲评（留空移回未关联批次）"><datalist id="history-folders">${folders.map(folder => `<option value="${e(folder)}"></option>`).join('')}</datalist></label><fieldset class="scope-picker"><legend>选择文档</legend>${docs.map(doc => `<label><input type="checkbox" name="documentIds" value="${e(doc.id)}"><span>${e(doc.title)}</span><small>${e(doc.folder)}</small></label>`).join('')}</fieldset><button type="submit" class="primary">保存分类</button></form>`);
  },
  'assign-pages': () => openDialog('将选中页分到答卷', `<form id="assign-form" class="form"><label>目标答卷<select name="target"><option value="">新建答卷</option>${ctx.state.groups.map(group => `<option value="${e(group.id)}">${e(group.label)}</option>`).join('')}</select></label><label>新答卷名称<input name="label" maxlength="80" value="答卷 ${ctx.state.groups.length + 1}"></label><button type="submit" class="primary">归入答卷</button></form>`),
  history: () => { ctx.historyOpen = !ctx.historyOpen; if (ctx.historyOpen) closeRecord(); render(); },
  results: element => { surface.prepareBatch = false; surface.readDocuments = true; return openResults(element.dataset.id); },
  'leave-results': () => { closeRecord(); ctx.resultsOpen = false; ctx.resultOutline = false; render(); },
  'grading-document': () => surface.showResults(ctx.resultTaskId,ctx.resultGroupId),
  'result-outline': () => { ctx.resultOutline = !ctx.resultOutline; if (ctx.resultOutline) closeRecord(); renderResults(); renderWorkflow(); },
  'result-filter': async element => { ctx.resultFilter = element.dataset.id; const { filtered } = resultContext(ctx); renderResults(); if (filtered.length) await showRecord((filtered.find(item => item.records.some(row => row.id === ctx.resultRecordId)) || filtered[0]).records[0].id); else closeRecord(); },
  'result-question': element => { const item = resultContext(ctx).items.find(row => row.id === element.dataset.id); if (item) return showRecord(item.records[0].id); },
  'result-source': () => { const { task, items } = resultContext(ctx); const record = task?.records.find(row => row.id === ctx.resultRecordId) || items[0]?.records[0]; if (record) return showRecord(record.id); },
  'result-report': async element => { await openArtifact(element.dataset.task, element.dataset.id, false); ctx.resultReport = element.dataset.id; render(); },
  'record-source': element => surface.showSource(element.dataset.id),
  'previous-result': () => stepResult(-1), 'next-result': () => stepResult(1),
  upload: () => openDialog('添加材料', `<div class="upload-choices">${b('upload-student', '上传答卷', { className: 'primary', symbol: 'upload' })}${b('upload-scheme', '上传评分标准', { className: 'outline', symbol: 'file-text' })}${b('upload-question', '上传题目', { className: 'outline', symbol: 'file-text' })}${b('upload-document', '导入文本文件', { className: 'quiet' })}${b('new-document', '新建文档', { className: 'quiet' })}</div><p class="muted">PDF、PNG 或 JPEG · 单个文件最多 40 MB</p>`),
  'upload-student': () => { ctx.uploadRole = 'student'; uploadInput.accept = '.pdf,.png,.jpg,.jpeg'; return pendingFiles ? upload(pendingFiles) : uploadInput.click(); },
  'upload-scheme': () => { ctx.uploadRole = 'scheme'; uploadInput.accept = '.pdf,.png,.jpg,.jpeg'; return pendingFiles ? upload(pendingFiles) : uploadInput.click(); },
  'upload-question': () => { ctx.uploadRole = 'question'; uploadInput.accept = '.pdf,.png,.jpg,.jpeg'; return pendingFiles ? upload(pendingFiles) : uploadInput.click(); },
  'rename-project': () => openDialog('作业名称', `<form id="project-form" class="form"><label>名称<input name="title" value="${e(ctx.state.title)}" maxlength="80" required></label><button class="primary" type="submit">保存</button></form>`),
  'material-role': element => { ctx.materialRole = element.dataset.role || 'student'; surface.intake.hidden ? openMaterials() : renderWorkflow(); },
  'select-all': () => { ctx.scopeAll = false; ctx.selected = new Set(ctx.selected.size === ctx.state.groups.length ? [] : ctx.state.groups.map(group => group.id)); openMaterials(); render(); },
  sorting: () => { ctx.sorting = !ctx.sorting; surface.intake.hidden ? openMaterials() : renderWorkflow(); },
  undo: async () => { const previous = ctx.undo.pop(); if (previous) await savePartition(previous, false); },
  'equal-split': () => openDialog('按人数均分', `<form id="split-form" class="form"><label>学生人数<input name="count" type="number" min="1" max="${ctx.state.groups.reduce((n, group) => n + group.pageIds.length, 0)}" value="${ctx.state.groups.length}" required></label><p class="muted">先均分，再调整分界。可撤销。</p><button class="primary" type="submit">应用划分</button></form>`),
  'file-split': () => {
    const sources = new Map();
    for (const id of ctx.state.groups.flatMap(group => group.pageIds)) {
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
  }, 'event-page': element => showPage(element.dataset.id),
  'previous-page': () => pageStep(-1), 'next-page': () => pageStep(1),
  browse: () => { surface.setMode('browse'); ctx.mode = surface.mode; render(); },
  lasso: () => { surface.setMode('lasso'); ctx.mode = surface.mode; render(); }, rectangle: () => { surface.setMode('rectangle'); ctx.mode = surface.mode; render(); },
  compare: () => { surface.add(); render(); },
  'remove-reference': element => { ctx.references.splice(Number(element.dataset.id), 1); render(); },
  'reference-location': element => { const target = ctx.references[Number(element.dataset.id)]?.target; if (target) return target.kind === 'text' ? surface.showDocument(target.documentId) : showPage(target.pageId); },
  'open-document': element => { closeDialog(); return surface.showDocument(element.dataset.id, surface.panels.length < 2); },
  'new-document': () => openDialog('新建文档', `<form id="new-document-form" class="form"><label>文档名称<input name="title" value="未命名.md" required maxlength="100"></label><label>用途<select name="schemeId"><option value="">普通文档</option>${ctx.state.schemes.map(scheme => `<option value="${e(scheme.id)}">${e(scheme.label)} · 评分实施说明</option>`).join('')}</select></label><button type="submit" class="primary">创建并编辑</button></form>`),
  'upload-document': () => { ctx.uploadRole = 'document'; uploadInput.accept = '.md,.txt,.csv,.json'; uploadInput.click(); },
  'zoom-in': () => { ctx.zoom = Math.min(1.8, ctx.zoom + .1); render(); }, 'zoom-out': () => { ctx.zoom = Math.max(.6, ctx.zoom - .1); render(); }, 'zoom-reset': () => { ctx.zoom = 1; render(); },
  'remove-selection': element => { ctx.selections = ctx.selections.filter(row => row.id !== element.dataset.id); render(); },
  'selection-page': element => showPage(ctx.selections.find(row => row.id === element.dataset.id)?.pageId),
  'restore-selection': element => { const selection = ctx.state.conversation.find(row => row.id === element.dataset.message)?.selections?.find(row => row.id === element.dataset.id); if (selection) { if (!ctx.selections.some(row => row.id === selection.id) && ctx.selections.length < 8) ctx.selections.push(selection); const group = ctx.state.groups.find(group => group.pageIds.includes(selection.pageId)); if (group && !ctx.scopeAll) ctx.selected.add(group.id); showPage(selection.pageId); } },
  'manual-task': () => openTask(), 'edit-task': element => openTask(ctx.state.tasks.find(task => task.id === element.dataset.id)),
  'start-task': async element => { await request(`/api/tasks/${element.dataset.id}/start`); ctx.targetTaskId = null; ctx.historyOpen = false; closeDialog(); render(); },
  'approve-guide': element => surface.approveDocument(element.dataset.id),
  'pause-task': element => request(`/api/tasks/${element.dataset.id}/pause`), 'resume-task': element => request(`/api/tasks/${element.dataset.id}/resume`),
  'cancel-task': element => request(`/api/tasks/${element.dataset.id}/cancel`), 'stop-chat': () => request('/api/chat/cancel'),
  'target-task': element => { ctx.targetTaskId = element.dataset.id; ctx.questionId = null; ctx.historyOpen = false; render(); document.querySelector('#composer-input').focus(); },
  'clear-target': () => { ctx.targetTaskId = null; ctx.questionId = null; render(); },
  'clear-record-context': () => { ctx.recordContextId = null; render(); },
  reviews: () => reviewList(), 'task-reviews': element => openResults(element.dataset.id),
  'open-question': element => { closeDialog(); ctx.peekQuestionId = element.dataset.id; const question = questions(ctx.state).find(row => row.id === element.dataset.id); showPage(question.references.find(ref => ref.pageId)?.pageId); render(); },
  'dismiss-question': () => { ctx.peekQuestionId = null; render(); },
  'reply-question': element => { const question = questions(ctx.state).find(row => row.id === element.dataset.id); ctx.questionId = question.id; ctx.targetTaskId = question.taskId; ctx.historyOpen = false; render(); document.querySelector('#composer-input').focus(); },
  'open-record': element => showRecord(element.dataset.id), 'close-record': closeRecord,
  'ask-record': () => { ctx.recordContextId = reviewRecord.id; ctx.scopeAll = false; ctx.selected = new Set([reviewRecord.groupId]); ctx.targetTaskId = null; ctx.questionId = null; closeRecord(); render(); document.querySelector('#composer-input').focus(); },
  'complete-review': element => request(`/api/tasks/${element.dataset.id}/review-complete`),
  artifact: element => openArtifact(element.dataset.task, element.dataset.id),
};
function pageStep(step) { const doc = documents(ctx.state).find(doc => doc.pageIds.includes(ctx.pageId)); if (doc) showPage(doc.pageIds[doc.pageIds.indexOf(ctx.pageId) + step]); }
document.addEventListener('click', event => { const element = event.target.closest('[data-action]'); if (element && !element.disabled && actions[element.dataset.action]) Promise.resolve().then(() => actions[element.dataset.action](element)).catch(error => toast(error.message)); });
document.addEventListener('change', event => {
  if (event.target.matches('[data-pick-page]')) {
    const id = event.target.dataset.pickPage;
    event.target.checked ? ctx.pickedPages.add(id) : ctx.pickedPages.delete(id);
    const control = surface.intake.querySelector('[data-action="assign-pages"]');
    control.disabled = !ctx.pickedPages.size; control.textContent = ctx.pickedPages.size ? `分组（${ctx.pickedPages.size} 页）` : '分组选中页';
  }
  if (event.target.matches('#assign-form select')) event.target.form.elements.label.disabled = Boolean(event.target.value);
  if (event.target.id === 'result-task') openResults(event.target.value).catch(error => toast(error.message));
  if (event.target.id === 'result-group') openResults(ctx.resultTaskId, event.target.value).catch(error => toast(error.message));
  if (event.target.closest('#task-form')) refreshTaskSetup(event.target.closest('#task-form'), ctx.state);
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
    if (form.id === 'assign-form') return savePartition(assignPages(ctx.state.groups, ctx.pickedPages, data.get('target'), data.get('label') || ''));
    if (form.id === 'split-form') return savePartition(equalGroups(ctx.state.groups, Number(data.get('count'))));
    if (form.id === 'rename-group-form') { const groups = structuredClone(ctx.state.groups); groups.find(group => group.id === form.dataset.id).label = String(data.get('label')); return savePartition(groups); }
    if (form.id === 'new-document-form') { const result = await request('/api/documents', { title: String(data.get('title')), schemeId: data.get('schemeId') || null, body: '' }); closeDialog(); await surface.showDocument(result.document.id, surface.panels.length < 2); }
    if (form.id === 'project-form') { await request('/api/project', { title: String(data.get('title')) }, 'PATCH'); closeDialog(); }
    if (form.id === 'task-form') {
      form.dataset.submitting = 'true';
      for (const submit of form.querySelectorAll('[type="submit"]')) submit.disabled = true;
      try {
        await submitTaskSetup({ request, input: { ...taskFormInput(data), selections: modalSelections, references: ctx.references }, taskId: modalTaskId, start: startGrading, onSaved: id => { modalTaskId = id; } });
        surface.prepareBatch = false; surface.readDocuments = true; ctx.intakeStep = 1; ctx.intakeDraft = null; closeDialog(); ctx.historyOpen = !startGrading; ctx.targetTaskId = null; render();
      } finally { delete form.dataset.submitting; if (form.isConnected) refreshTaskSetup(form, ctx.state); }
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
document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files') || dragPage) event.preventDefault(); });
document.addEventListener('drop', event => { event.preventDefault(); if (event.dataTransfer.files.length) { pendingFiles = [...event.dataTransfer.files];
    const role = event.target.closest('[data-upload-role]')?.dataset.uploadRole;
    if (role && !ctx.busy) { ctx.uploadRole = role; upload(pendingFiles).catch(error => toast(error.message)); }
    else if (!ctx.busy) actions.upload();
    return; } const target = event.target.closest('[data-page-id]'); if (dragPage && target) { const groups = movedGroups(ctx.state.groups, dragPage, target.dataset.pageId); if (groups) savePartition(groups).catch(error => toast(error.message)); } dragPage = null; });
document.addEventListener('dragend', () => { dragPage = null; });
for (const [name, delta] of [['page-left', -1], ['page-right', 1]]) actions[name] = element => { const ids = ctx.state.groups.flatMap(group => group.pageIds), target = ids[ids.indexOf(element.dataset.id) + delta]; if (target) return savePartition(movedGroups(ctx.state.groups, element.dataset.id, target)); };
let polling = false;
window.addEventListener('resize', () => { if (ctx.state && document.querySelector('#composer')) render(); });
setInterval(async () => { if (document.hidden || polling || sending || ctx.busy) return; polling = true; try { const before = JSON.stringify([ctx.state?.revision, ctx.state?.chat, ctx.state?.liveTasks]); await refresh(); if (JSON.stringify([ctx.state.revision, ctx.state.chat, ctx.state.liveTasks]) !== before) render(); } catch { /* Keep the canvas and unsent input intact during reconnects. */ } finally { polling = false; } }, 900);
try {
  await refresh(); frame(); render();
  if (resultTasks(ctx.state).length && !ctx.state.tasks.some(task => ['running', 'draft'].includes(task.status))) await openResults();
} catch (error) { app.innerHTML = `<section class="empty"><h1>工作区暂时无法打开</h1><p>${e(error.message)}</p><a href="/">重新加载</a></section>`; }
