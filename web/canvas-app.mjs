import { uncertaintyView, escape as e, icon, button as b, iconButton as ib, pageById, latestReview, recordScoreText, recordBasisText } from './ui.mjs';
import { materialView, equalGroups, movedGroups } from './materials.mjs';
import { taskForm, taskFormInput, refreshTaskSetup, submitTaskSetup, artifactContent } from './tasks.mjs';
import { documents, questions, pendingRecords, allRecords, header, toolbar, historyView, statusView, contextChips, questionView, workflowView } from './canvas-view.mjs';
import { WorkspaceCanvas } from './workspace-canvas.mjs';
import { findGradingAnnotation } from './grading-annotations.mjs';

const app = document.querySelector('#app'), dialog = document.querySelector('#dialog'), uploadInput = document.querySelector('#upload-input');
const ctx = { state: null, token: '', selected: new Set(), selections: [], references: [], mode: 'browse', zoom: 1, pageId: null,
  scopeAll: true,
  command: '', undo: [], sorting: false, materialRole: 'student', busy: false, historyOpen: false,
  targetTaskId: null, questionId: null, peekQuestionId: null, seenQuestions: new Set(), uploadRole: 'student' };
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
  app.innerHTML = `<header class="canvas-header" id="workspace-header"></header><main class="canvas-workspace" aria-label="材料画布"><section class="workflow-stage" id="workflow-stage" aria-label="当前批改阶段" hidden></section><div class="canvas-toolbar" id="canvas-toolbar"></div><div class="multi-canvas" id="multi-canvas"></div></main>
    <aside class="question-peek" id="question-peek" aria-label="待确认问题" hidden></aside><aside class="record-panel" id="record-panel" aria-label="评分审阅" hidden></aside>
    <section class="conversation-panel" id="conversation-panel" aria-label="对话与处理过程" hidden></section><div class="collaboration-dock"><div class="agent-status" id="agent-status" aria-live="polite"></div>
      <form id="composer" class="composer"><div class="composer-context" id="composer-context"></div><textarea id="composer-input" name="goal" rows="1" maxlength="8000" aria-label="补充批改要求或提问" placeholder="补充批改要求，或针对材料提问…"></textarea>
      <div class="composer-toolbar"><div class="composer-left">${ib('upload', '添加材料', 'plus')}${b('scope', '全部答卷', { className: 'scope-button', attrs: 'id="scope-button" title="对话涉及的答卷"' })}</div><div class="composer-right"><span class="composer-agent">GradeOS <span>Pi</span></span><button type="submit" class="send-button" id="send-button" aria-label="发送要求">${icon('arrow-up')}</button></div></div></form></div>`;
  surface = new WorkspaceCanvas(document.querySelector('#multi-canvas'), { request, getState: () => ctx.state, onReference: addReference, toast, onChange: renderWorkflow, onReview: showRecord });
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
  const workflow = document.querySelector('#workflow-stage'); html(workflow, workflowView(ctx, surface?.panels || [])); workflow.hidden = !workflow.innerHTML;
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
  html(document.querySelector('#workspace-header'), header(ctx));
  html(document.querySelector('#canvas-toolbar'), toolbar(ctx));
  const hasMaterials = ctx.state.pages.length > 0 || ctx.state.documents.length > 0;
  document.querySelector('#canvas-toolbar').hidden = !hasMaterials;
  document.querySelector('.collaboration-dock').hidden = !hasMaterials;
  surface.update();
  renderWorkflow();
  html(document.querySelector('#composer-context'), contextChips(ctx));
  const aligning = alignmentGuide();
  document.querySelector('#composer-input').placeholder = ctx.questionId ? '回复这一处问题…' : ctx.selections.length || ctx.references.length ? '针对引用内容，说说你的要求…' : aligning ? '和 Agent 对齐这次的评分要求…' : ctx.targetTaskId ? '给当前批改补充说明…' : '补充批改要求，或针对材料提问…';
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
  openDialog('材料与答卷划分', `<div class="material-upload">${b('upload-student', '添加答卷', { symbol: 'plus', className: 'outline' })}${b('upload-scheme', '添加评分标准', { className: 'quiet' })}${b('upload-question', '添加题目', { className: 'quiet' })}</div>${b('new-document', '新建文档', { className: 'quiet' })}<div class="documents-list">${(ctx.state.documents || []).map(doc => b('open-document', `${icon('file-text')}${e(doc.title)}<span>v${doc.revision} · 可编辑</span>`, { attrs: `data-id="${e(doc.id)}"` })).join('')}</div>${materialView(ctx)}`, 'materials-drawer');
}
function showPage(id) { if (pageById(ctx.state, id)) { ctx.pageId = id; return surface.showPage(id); } }
function openTask(task = null) { if (ctx.busy) { toast('材料正在读取，请稍候。'); return; } modalTaskId = task?.id || null; modalSelections = task?.selections || ctx.selections; const selected = ctx.selected; ctx.selected = new Set(scope()); openDialog(task?.kind === 'assist' ? '修改安排' : '开始批改', taskForm(ctx, task, { allowStart: true }), 'task-setup-dialog'); ctx.selected = selected; }
async function savePartition(groups, remember = true) {
  const before = structuredClone(ctx.state.groups); await request('/api/materials', { groups }, 'PATCH');
  if (remember) ctx.undo = [...ctx.undo, before].slice(-30);
  openMaterials();
}
function reviewList(taskId = null) {
  const records = taskId ? allRecords(ctx.state).filter(row => row.taskId === taskId) : pendingRecords(ctx.state);
  openDialog(taskId ? '评分记录' : '需要你确认', `${(ctx.state.documents || []).filter(doc => doc.proposalId && !doc.approvals.length && ctx.state.tasks.some(task => task.id === doc.taskId && task.status === 'running')).map(doc => `<div class="guide-inbox"><span>${e(doc.title)} · 等待编辑与确认</span>${b('open-document', '打开文档', { attrs: `data-id="${e(doc.id)}"` })}</div>`).join('')}${questions(ctx.state).map(question => `<button class="review-list-row" data-action="open-question" data-id="${e(question.id)}"><span class="amber-dot"></span><span>${e(question.question)}</span>${icon('right')}</button>`).join('')}${records.map(record => `<button class="review-list-row" data-action="open-record" data-id="${e(record.id)}"><span><strong>${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}</strong><small>${e(record.reason)}</small></span><span class="review-score">${e(recordScoreText(record))}${record.uncertainties?.length ? '<small>有待核实项</small>' : ''}</span>${icon('right')}</button>`).join('') || '<p class="muted">当前没有待处理评分。</p>'}${!taskId ? `<details class="all-records"><summary>全部评分记录</summary>${allRecords(ctx.state).map(record => b('open-record', `${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}`, { className: 'record-link', attrs: `data-id="${e(record.id)}"` })).join('')}</details>` : ''}`, 'review-drawer');
}
function showRecord(id) {
  const record = allRecords(ctx.state).find(row => row.id === id); if (!record) return;
  reviewRecord = record; closeDialog(); ctx.peekQuestionId = null;
  showPage(record.studentPageIds[0] || record.schemePageIds[0]);
  const review = latestReview(ctx.state, record.id), current = review ? review.score : record.score;
  const panel = document.querySelector('#record-panel'); panel.hidden = false;
  panel.innerHTML = `<div class="peek-heading"><strong>${e(record.student)} · ${e(record.itemId)} ${e(record.pointId || '')}</strong>${ib('close-record', '关闭审阅', 'close')}</div><p class="record-original">${record.disposition === 'feedback_only' ? '原始反馈' : '原始评分'} <strong>${e(recordScoreText(record))}</strong></p>${recordBasisText(record) ? `<p class="muted">${e(recordBasisText(record))}</p>` : ''}<p class="record-reason">${e(record.reason)}</p>${uncertaintyView(record)}${record.sourceText ? `<details><summary>评分条文</summary><p>${e(record.sourceText)}</p></details>` : ''}<div class="record-sources">${record.studentPageIds.map((id, index) => b('event-page', `答卷 · 第 ${pageById(ctx.state, id)?.sourcePage ?? index + 1} 页 ↗`, { attrs: `data-id="${e(id)}"`, className: 'source-link' })).join('')}${record.schemePageIds.map((id, index) => b('event-page', `MS · 第 ${pageById(ctx.state, id)?.sourcePage ?? index + 1} 页 ↗`, { attrs: `data-id="${e(id)}"`, className: 'source-link' })).join('')}${(record.questionPageIds || []).map(id => b('event-page', `题目 · 第 ${pageById(ctx.state, id)?.sourcePage} 页 ↗`, { attrs: `data-id="${e(id)}"`, className: 'source-link' })).join('')}</div>
    <form id="canvas-review-form"><label>老师复核<select name="score"><option value="null" ${current === null ? 'selected' : ''}>${record.disposition === 'feedback_only' ? '确认定性反馈（不赋分）' : '保留待定'}</option>${record.allowedAwards.map(score => `<option value="${score}" ${score === current ? 'selected' : ''}>${score} 分</option>`).join('')}</select></label><textarea name="reason" rows="2" required maxlength="4000" aria-label="复核理由" placeholder="写下复核依据…">${e(review?.reason || '')}</textarea><div class="peek-actions">${b('ask-record', '问 GradeOS', { className: 'quiet' })}<button type="submit" class="primary">保存复核</button></div></form>${review ? '<p class="muted">已保存老师复核，原始评分保留。</p>' : ''}`;
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
    closeDialog(); render(); if (role !== 'document') await showPage(ctx.pageId); toast(role === 'document' ? '文档已导入，可以直接编辑。' : '材料已上传。可在“材料”中划分答卷。');
  } finally { ctx.busy = false; uploadInput.value = ''; pendingFiles = null; updateSend(); renderWorkflow(); }
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
  'close-dialog': closeDialog, materials: openMaterials, scope: openMaterials,
  history: () => { ctx.historyOpen = !ctx.historyOpen; render(); },
  upload: () => openDialog('添加材料', `<div class="upload-choices">${b('upload-student', '上传答卷', { className: 'primary', symbol: 'upload' })}${b('upload-scheme', '上传评分标准', { className: 'outline', symbol: 'file-text' })}${b('upload-question', '上传题目', { className: 'outline', symbol: 'file-text' })}${b('upload-document', '导入文本文件', { className: 'quiet' })}${b('new-document', '新建文档', { className: 'quiet' })}</div><p class="muted">PDF、PNG 或 JPEG · 单个文件最多 40 MB</p>`),
  'upload-student': () => { ctx.uploadRole = 'student'; uploadInput.accept = '.pdf,.png,.jpg,.jpeg'; return pendingFiles ? upload(pendingFiles) : uploadInput.click(); },
  'upload-scheme': () => { ctx.uploadRole = 'scheme'; uploadInput.accept = '.pdf,.png,.jpg,.jpeg'; return pendingFiles ? upload(pendingFiles) : uploadInput.click(); },
  'upload-question': () => { ctx.uploadRole = 'question'; uploadInput.accept = '.pdf,.png,.jpg,.jpeg'; return pendingFiles ? upload(pendingFiles) : uploadInput.click(); },
  'rename-project': () => openDialog('作业名称', `<form id="project-form" class="form"><label>名称<input name="title" value="${e(ctx.state.title)}" maxlength="80" required></label><button class="primary" type="submit">保存</button></form>`),
  'material-role': element => { ctx.materialRole = element.dataset.role || 'student'; openMaterials(); },
  'select-all': () => { ctx.scopeAll = false; ctx.selected = new Set(ctx.selected.size === ctx.state.groups.length ? [] : ctx.state.groups.map(group => group.id)); openMaterials(); render(); },
  sorting: () => { ctx.sorting = !ctx.sorting; openMaterials(); },
  undo: async () => { const previous = ctx.undo.pop(); if (previous) await savePartition(previous, false); },
  'equal-split': () => openDialog('按人数均分', `<form id="split-form" class="form"><label>学生人数<input name="count" type="number" min="1" max="${ctx.state.groups.reduce((n, group) => n + group.pageIds.length, 0)}" value="${ctx.state.groups.length}" required></label><p class="muted">先均分，再调整分界。可撤销。</p><button class="primary" type="submit">应用划分</button></form>`),
  'file-split': () => { const groups = []; for (const id of ctx.state.groups.flatMap(group => group.pageIds)) { const page = pageById(ctx.state, id); let group = groups.at(-1); if (!group || group.sourceId !== page.sourceId) { group = { id: crypto.randomUUID(), sourceId: page.sourceId, label: page.fileName.replace(/\.[^.]+$/, ''), pageIds: [] }; groups.push(group); } group.pageIds.push(id); } return savePartition(groups); },
  'split-page': element => { const groups = structuredClone(ctx.state.groups), index = groups.findIndex(group => group.pageIds.includes(element.dataset.id)), group = groups[index], boundary = group.pageIds.indexOf(element.dataset.id); if (boundary > 0) { groups.splice(index + 1, 0, { id: crypto.randomUUID(), label: `${group.label} · 分卷`, pageIds: group.pageIds.splice(boundary) }); return savePartition(groups); } },
  'merge-next': element => { const groups = structuredClone(ctx.state.groups), index = groups.findIndex(group => group.id === element.dataset.id); if (groups[index + 1]) { groups[index].pageIds.push(...groups[index + 1].pageIds); groups.splice(index + 1, 1); return savePartition(groups); } },
  'rename-group': element => { const group = ctx.state.groups.find(group => group.id === element.dataset.id); openDialog('答卷名称', `<form id="rename-group-form" data-id="${e(group.id)}" class="form"><label>名称<input name="label" value="${e(group.label)}" maxlength="80" required></label><button class="primary" type="submit">保存</button></form>`); },
  page: element => { closeDialog(); showPage(element.dataset.id); }, 'event-page': element => showPage(element.dataset.id),
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
  reviews: () => reviewList(), 'task-reviews': element => reviewList(element.dataset.id),
  'open-question': element => { closeDialog(); ctx.peekQuestionId = element.dataset.id; const question = questions(ctx.state).find(row => row.id === element.dataset.id); showPage(question.references.find(ref => ref.pageId)?.pageId); render(); },
  'dismiss-question': () => { ctx.peekQuestionId = null; render(); },
  'reply-question': element => { const question = questions(ctx.state).find(row => row.id === element.dataset.id); ctx.questionId = question.id; ctx.targetTaskId = question.taskId; ctx.historyOpen = false; render(); document.querySelector('#composer-input').focus(); },
  'open-record': element => showRecord(element.dataset.id), 'close-record': () => { document.querySelector('#record-panel').hidden = true; reviewRecord = null; },
  'ask-record': () => { ctx.recordContextId = reviewRecord.id; ctx.scopeAll = false; ctx.selected = new Set([reviewRecord.groupId]); ctx.targetTaskId = null; ctx.questionId = null; document.querySelector('#record-panel').hidden = true; render(); document.querySelector('#composer-input').focus(); },
  'complete-review': element => request(`/api/tasks/${element.dataset.id}/review-complete`),
  artifact: async element => { const artifact = ctx.state.tasks.find(task => task.id === element.dataset.task)?.artifacts.find(row => row.id === element.dataset.id); if (!artifact) return; if (typeof artifact.body === 'string') { const result = await request('/api/documents', { artifactId: artifact.id, taskId: element.dataset.task }); ctx.historyOpen = false; await surface.showDocument(result.document.id, surface.panels.length < 2); render(); } else openDialog(artifact.title, artifactContent(artifact), 'artifact-dialog'); },
};
function pageStep(step) { const doc = documents(ctx.state).find(doc => doc.pageIds.includes(ctx.pageId)); if (doc) showPage(doc.pageIds[doc.pageIds.indexOf(ctx.pageId) + step]); }
document.addEventListener('click', event => { const element = event.target.closest('[data-action]'); if (element && !element.disabled && actions[element.dataset.action]) Promise.resolve().then(() => actions[element.dataset.action](element)).catch(error => toast(error.message)); });
document.addEventListener('change', event => {
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
    if (form.id === 'split-form') return savePartition(equalGroups(ctx.state.groups, Number(data.get('count'))));
    if (form.id === 'rename-group-form') { const groups = structuredClone(ctx.state.groups); groups.find(group => group.id === form.dataset.id).label = String(data.get('label')); return savePartition(groups); }
    if (form.id === 'new-document-form') { const result = await request('/api/documents', { title: String(data.get('title')), schemeId: data.get('schemeId') || null, body: '' }); closeDialog(); await surface.showDocument(result.document.id, surface.panels.length < 2); }
    if (form.id === 'project-form') { await request('/api/project', { title: String(data.get('title')) }, 'PATCH'); closeDialog(); }
    if (form.id === 'task-form') {
      form.dataset.submitting = 'true';
      for (const submit of form.querySelectorAll('[type="submit"]')) submit.disabled = true;
      try {
        await submitTaskSetup({ request, input: { ...taskFormInput(data), selections: modalSelections, references: ctx.references }, taskId: modalTaskId, start: startGrading, onSaved: id => { modalTaskId = id; } });
        closeDialog(); ctx.historyOpen = !startGrading; ctx.targetTaskId = null; render();
      } finally { delete form.dataset.submitting; if (form.isConnected) refreshTaskSetup(form, ctx.state); }
    }
    if (form.id === 'canvas-review-form') { const value = data.get('score'); await request('/api/reviews', { taskId: reviewRecord.taskId, recordId: reviewRecord.id, originalHash: reviewRecord.originalHash, score: value === 'null' ? null : Number(value), reason: String(data.get('reason')) }); showRecord(reviewRecord.id); toast('复核已保存，原始评分保留。'); }
  }).catch(error => toast(error.message));
});
document.addEventListener('dragstart', event => { const tile = event.target.closest('[data-page-id]'); if (tile && ctx.sorting) { dragPage = tile.dataset.pageId; event.dataTransfer.setData('text/plain', dragPage); } });
document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files') || dragPage) event.preventDefault(); });
document.addEventListener('drop', event => { event.preventDefault(); if (event.dataTransfer.files.length) { pendingFiles = [...event.dataTransfer.files]; actions.upload(); return; } const target = event.target.closest('[data-page-id]'); if (dragPage && target) { const groups = movedGroups(ctx.state.groups, dragPage, target.dataset.pageId); if (groups) savePartition(groups).catch(error => toast(error.message)); } dragPage = null; });
document.addEventListener('dragend', () => { dragPage = null; });
for (const [name, delta] of [['page-left', -1], ['page-right', 1]]) actions[name] = element => { const ids = ctx.state.groups.flatMap(group => group.pageIds), target = ids[ids.indexOf(element.dataset.id) + delta]; if (target) return savePartition(movedGroups(ctx.state.groups, element.dataset.id, target)); };
let polling = false;
window.addEventListener('resize', () => { if (ctx.state && document.querySelector('#composer')) render(); });
setInterval(async () => { if (document.hidden || polling || sending || ctx.busy) return; polling = true; try { const before = JSON.stringify([ctx.state?.revision, ctx.state?.chat, ctx.state?.liveTasks]); await refresh(); if (JSON.stringify([ctx.state.revision, ctx.state.chat, ctx.state.liveTasks]) !== before) render(); } catch { /* Keep the canvas and unsent input intact during reconnects. */ } finally { polling = false; } }, 900);
try { await refresh(); frame(); render(); } catch (error) { app.innerHTML = `<section class="empty"><h1>工作区暂时无法打开</h1><p>${e(error.message)}</p><a href="/">重新加载</a></section>`; }
