document.documentElement.classList.toggle('embedded-grading', new URLSearchParams(location.search).has('embedded'));
import { escape as e, icon, button, iconButton, pageById, markdown } from './ui.mjs';
import { materialView, equalGroups, movedGroups } from './materials.mjs';
import { taskView, taskForm, taskFormInput, refreshTaskSetup, artifactContent } from './tasks.mjs';
import { reviewView, reviewItems } from './review.mjs';

// A running pre-canvas server can keep its existing UI until its owner restarts it.
// Avoid breaking another local grading run when the shared static files change.
const canvasAvailable = await fetch('/api/state').then(response => response.json()).then(state => Object.hasOwn(state, 'documents')).catch(() => false);
if (canvasAvailable) {
  for (const href of ['/canvas.css', '/workspace-canvas.css', '/document-reader.css', '/results.css']) {
    const stylesheet = document.createElement('link'); stylesheet.rel = 'stylesheet'; stylesheet.href = href;
    await new Promise((resolve, reject) => { stylesheet.onload = resolve; stylesheet.onerror = reject; document.head.append(stylesheet); });
  }
  await import('./canvas-app.mjs');
} else {
const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
const uploadInput = document.querySelector('#upload-input');
const ctx = {
  state: null, token: '', tab: ['materials', 'tasks', 'review'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'materials',
  selected: new Set(), command: '', undo: [], sorting: false, materialRole: 'student',
  activeTaskId: null, taskList: false, reviewTaskId: null, reviewIndex: 0, reviewAll: false,
  reviewDrafts: {}, sourcePage: { student: 0, scheme: 0 }, busy: false, uploadRole: 'student',
};
let modalTaskId = null, toastTimer, dragPage, agentScope = [], agentQuestion = '', askingRecord = null;
const toast = message => {
  const element = document.querySelector('#toast'); element.textContent = message; element.classList.add('visible');
  const alert = dialog.querySelector('.dialog-alert'); if (alert) alert.textContent = message;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => element.classList.remove('visible'), 6000);
};
const setState = state => {
  if (state.token) ctx.token = state.token;
  ctx.state = state;
  const valid = new Set(state.groups.map(group => group.id));
  ctx.selected = new Set([...ctx.selected].filter(id => valid.has(id)));
  if (!ctx.activeTaskId) ctx.activeTaskId = state.tasks.at(-1)?.id;
};
async function request(path, body, method = 'POST') {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': ctx.token }, body: JSON.stringify({ revision: ctx.state.revision, ...body }) });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 409) await refresh();
    throw Error(result.error || '操作未完成。');
  }
  setState(result); return result;
}
async function refresh() {
  const response = await fetch('/api/state');
  if (!response.ok) throw Error('无法读取工作区。');
  const state = await response.json(); setState(state);
}
function navigate(tab) {
  ctx.tab = tab; location.hash = tab; render(); window.scrollTo({ top: 0, behavior: 'instant' });
}
function render() {
  if (!ctx.state) return;
  const tabs = [['materials', '材料'], ['tasks', '任务'], ['review', '审阅']];
  app.innerHTML = `<header class="app-header"><div class="brand-line"><a class="wordmark" href="#materials" aria-label="GradeOS 材料工作区">Grade<span>OS</span></a><span class="header-divider"></span>${button('rename-project', e(ctx.state.title), { className: 'project-name', attrs: 'title="修改作业名称"' })}</div>
    <nav aria-label="工作区">${tabs.map(([tab, label]) => `<button data-action="tab" data-tab="${tab}" class="nav-tab ${ctx.tab === tab ? 'active' : ''}" aria-current="${ctx.tab === tab ? 'page' : 'false'}">${label}</button>`).join('')}</nav>
    <div class="header-actions">${ctx.tab === 'materials' ? button('upload', '上传', { className: 'outline', symbol: 'plus' }) : ctx.tab === 'tasks' ? button('task-list', '全部任务', { className: 'text-button blue' }) : ''}${button('settings', 'GradeOS', { className: 'edition muted' })}</div></header>
    <main class="${ctx.tab === 'materials' ? 'with-dock' : ''}">${ctx.tab === 'materials' ? materialView(ctx) : ctx.tab === 'tasks' ? taskView(ctx) : reviewView(ctx)}</main>`;
}
function openDialog(title, content, className = '') {
  dialog.className = className;
  dialog.innerHTML = `<div class="dialog-header"><h2>${e(title)}</h2>${iconButton('close-dialog', '关闭', 'close')}</div><div class="dialog-alert" role="alert"></div><div class="dialog-body">${content}</div>`;
  if (!dialog.open) dialog.showModal();
}
function closeDialog() { dialog.close(); askingRecord = null; }
function selectScope(task = null) { return task?.groupIds || (ctx.selected.size ? [...ctx.selected] : ctx.state.groups.map(group => group.id)); }
function openAssistant(initial = '', record = null) {
  askingRecord = record;
  const task = ctx.tab === 'review' ? reviewItems(ctx).task : ctx.state.tasks.find(item => item.id === ctx.activeTaskId);
  agentScope = record ? [record.groupId] : selectScope(ctx.tab === 'materials' ? null : task);
  agentQuestion = initial;
  const messages = ctx.state.conversation.filter(message => JSON.stringify(message.selectedIds) === JSON.stringify(agentScope));
  openDialog('与 GradeOS 协作', `<div class="assistant-scope">${record ? `${e(record.student)} · ${e(record.itemId)}${record.pointId ? ` / ${e(record.pointId)}` : ''}` : `${agentScope.length} 份答卷`}</div>
    <div class="messages">${messages.length ? messages.map(message => `<div class="message ${message.role}">${markdown(message.text)}</div>`).join('') : '<p class="muted assistant-hint">直接说明想完成的事。任务安排会先保存为草稿。</p>'}</div>
    ${!ctx.state.agentReady ? '<p class="notice">尚未连接模型。仍可手动安排任务。</p>' : ''}
    <form id="assistant-form"><textarea name="goal" aria-label="发送给 GradeOS 的要求" rows="4" placeholder="例如：分三批处理，每批完成后等我审阅…" maxlength="8000" required>${e(initial)}</textarea><div class="form-actions">${button('manual-task', '手动安排', { className: 'text-button' })}<button class="primary" type="submit" ${ctx.busy ? 'disabled' : ''}>发送</button></div></form>`, 'assistant-drawer');
}
async function askAgent(goal) {
  if (!ctx.state.agentReady) { openAssistant(goal, askingRecord); toast('模型尚未配置，可以先手动安排任务。'); return; }
  const scope = dialog.classList.contains('assistant-drawer') && dialog.open ? agentScope : [...ctx.selected];
  if (!scope.length) throw Error('先选择任务涉及的答卷。');
  ctx.busy = true; render();
  const submit = dialog.querySelector('#assistant-form button[type="submit"]');
  if (submit) { submit.disabled = true; submit.textContent = '正在处理…'; }
  const previousIds = new Set(ctx.state.tasks.map(task => task.id));
  try {
    await request('/api/agent', { selectedIds: scope, goal, recordId: askingRecord?.id });
    ctx.command = '';
    const added = ctx.state.tasks.filter(task => !previousIds.has(task.id));
    if (added.length) { ctx.activeTaskId = added.at(-1).id; ctx.taskList = added.length > 1; closeDialog(); navigate('tasks'); toast(`已保存 ${added.length} 个任务安排，尚未开始。`); }
    else { ctx.busy = false; openAssistant('', askingRecord); }
  } finally { ctx.busy = false; render(); const currentSubmit = dialog.querySelector('#assistant-form button[type="submit"]'); if (currentSubmit) { currentSubmit.disabled = false; currentSubmit.textContent = '发送'; } }
}
async function savePartition(groups, remember = true) {
  const before = structuredClone(ctx.state.groups);
  await request('/api/materials', { groups }, 'PATCH');
  if (remember) { ctx.undo.push(before); ctx.undo = ctx.undo.slice(-30); }
  render();
}
async function upload(files) {
  if (!files.length || ctx.busy) return;
  const role = ctx.uploadRole;
  ctx.busy = true; render();
  try {
    for (const [index, file] of [...files].entries()) {
      toast(`正在读取 ${file.name}（${index + 1}/${files.length}）…`);
      const response = await fetch(`/api/uploads?role=${role}&name=${encodeURIComponent(file.name)}`, { method: 'POST', headers: { 'X-Workspace-Token': ctx.token }, body: file });
      const result = await response.json();
      if (!response.ok) throw Error(result.error);
      setState(result); ctx.undo = []; render();
    }
    ctx.materialRole = role; closeDialog(); navigate('materials'); toast('材料已保存，可以调整页序与答卷边界。');
  } finally { ctx.busy = false; uploadInput.value = ''; render(); }
}
function openTaskForm(task = null) {
  modalTaskId = task?.id || null;
  openDialog(task ? '修改任务' : '安排任务', taskForm(ctx, task));
}

const actions = {
  tab: element => navigate(element.dataset.tab),
  'close-dialog': closeDialog,
  upload: () => openDialog('添加材料', `<div class="upload-choices">${button('upload-student', '上传答卷', { className: 'primary', symbol: 'upload' })}${button('upload-scheme', '上传评分标准', { className: 'outline', symbol: 'file-text' })}${button('upload-question', '上传题目', { className: 'outline', symbol: 'file-text' })}</div><p class="muted">PDF、PNG 或 JPEG · 单个文件最多 40 MB</p>`),
  'upload-student': () => { if (!ctx.busy) { ctx.uploadRole = 'student'; uploadInput.click(); } },
  'upload-scheme': () => { if (!ctx.busy) { ctx.uploadRole = 'scheme'; uploadInput.click(); } },
  'upload-question': () => { if (!ctx.busy) { ctx.uploadRole = 'question'; uploadInput.click(); } },
  'material-role': element => { ctx.materialRole = element.dataset.role || 'student'; render(); },
  'select-all': () => { ctx.selected = new Set(ctx.selected.size === ctx.state.groups.length ? [] : ctx.state.groups.map(group => group.id)); render(); },
  sorting: () => { ctx.sorting = !ctx.sorting; render(); },
  undo: async () => { const previous = ctx.undo.at(-1); if (previous) { await savePartition(previous, false); ctx.undo.pop(); render(); } },
  'equal-split': () => openDialog('按人数均分', `<form id="split-form" class="form"><label>学生人数<input name="count" type="number" min="1" max="${ctx.state.groups.reduce((sum, group) => sum + group.pageIds.length, 0)}" value="${ctx.state.groups.length}" required></label><p class="muted">先均分，再手动调整分界。可撤销。</p><div class="form-actions"><button class="primary" type="submit">应用划分</button></div></form>`),
  'file-split': async () => {
    const groups = [];
    for (const pageId of ctx.state.groups.flatMap(group => group.pageIds)) {
      const page = pageById(ctx.state, pageId); let group = groups.at(-1);
      if (!group || group.sourceId !== page.sourceId) { group = { id: crypto.randomUUID(), sourceId: page.sourceId, label: page.fileName.replace(/\.[^.]+$/, ''), pageIds: [] }; groups.push(group); }
      group.pageIds.push(pageId);
    }
    await savePartition(groups);
  },
  'split-page': async element => {
    const groups = structuredClone(ctx.state.groups); const index = groups.findIndex(group => group.pageIds.includes(element.dataset.id));
    const group = groups[index], boundary = group.pageIds.indexOf(element.dataset.id);
    if (boundary <= 0) return;
    groups.splice(index + 1, 0, { id: crypto.randomUUID(), label: `${group.label} · 分卷`, pageIds: group.pageIds.splice(boundary) });
    await savePartition(groups); closeDialog();
  },
  'merge-next': async element => {
    const groups = structuredClone(ctx.state.groups); const index = groups.findIndex(group => group.id === element.dataset.id);
    if (!groups[index + 1]) return;
    groups[index].pageIds.push(...groups[index + 1].pageIds); groups.splice(index + 1, 1); await savePartition(groups);
  },
  'rename-group': element => {
    const group = ctx.state.groups.find(item => item.id === element.dataset.id);
    openDialog('答卷名称', `<form id="rename-group-form" data-id="${e(group.id)}" class="form"><label>名称<input name="label" value="${e(group.label)}" maxlength="80" required></label><div class="form-actions"><button type="submit" class="primary">保存</button></div></form>`);
  },
  'rename-project': () => openDialog('作业名称', `<form id="project-form" class="form"><label>名称<input name="title" value="${e(ctx.state.title)}" maxlength="80" required></label><div class="form-actions"><button type="submit" class="primary">保存</button></div></form>`),
  page: element => {
    const page = pageById(ctx.state, element.dataset.id);
    const group = ctx.state.groups.find(item => item.pageIds.includes(page.id));
    openDialog(`${page.fileName} · 第 ${page.sourcePage} 页`, `<div class="zoom-paper"><img src="${page.url}" alt="${e(page.fileName)}，第 ${page.sourcePage} 页"></div>${group?.pageIds.indexOf(page.id) > 0 && ctx.tab === 'materials' ? `<div class="form-actions">${button('split-page', '在此页前分卷', { className: 'outline', attrs: `data-id="${e(page.id)}"` })}</div>` : ''}`, 'image-dialog');
  },
  'manual-task': () => {
    const question = dialog.querySelector('#assistant-form textarea');
    if (dialog.open && question) { ctx.command = question.value; ctx.selected = new Set(agentScope); }
    openTaskForm();
  },
  'edit-task': () => openTaskForm(ctx.state.tasks.find(task => task.id === ctx.activeTaskId)),
  'open-task': element => { ctx.activeTaskId = element.dataset.id; ctx.taskList = false; navigate('tasks'); },
  'task-list': () => { ctx.taskList = true; navigate('tasks'); },
  'go-tasks': () => navigate('tasks'),
  'task-materials': () => { const task = ctx.state.tasks.find(item => item.id === ctx.activeTaskId); ctx.selected = new Set(task.groupIds); ctx.materialRole = 'student'; navigate('materials'); },
  'show-scheme': () => { ctx.materialRole = 'scheme'; navigate('materials'); },
  'start-task': async () => { ctx.busy = true; render(); try { await request(`/api/tasks/${ctx.activeTaskId}/start`, {}); } finally { ctx.busy = false; render(); } },
  'cancel-task': async () => { await request(`/api/tasks/${ctx.activeTaskId}/cancel`, {}); toast('正在取消，已完成的结果会保留。'); },
  'review-task': () => { ctx.reviewTaskId = ctx.activeTaskId; ctx.reviewIndex = 0; ctx.sourcePage = {}; navigate('review'); },
  'review-filter': () => { ctx.reviewAll = !ctx.reviewAll; ctx.reviewIndex = 0; ctx.sourcePage = {}; render(); },
  'previous-record': () => { ctx.reviewIndex = Math.max(0, ctx.reviewIndex - 1); ctx.sourcePage = {}; render(); },
  'next-record': () => { ctx.reviewIndex++; ctx.sourcePage = {}; render(); },
  'ask-record': () => openAssistant(`帮我核对 ${ctx.currentRecord.itemId}${ctx.currentRecord.pointId ? ` / ${ctx.currentRecord.pointId}` : ''} 的评分依据。`, ctx.currentRecord),
  assistant: () => openAssistant(),
  'review-complete': async () => { const taskId = ctx.tab === 'review' ? ctx.reviewTaskId : ctx.activeTaskId; await request(`/api/tasks/${taskId}/review-complete`, {}); toast('审阅已保存。可自行安排下一批。'); render(); },
  artifact: element => {
    const artifact = ctx.state.tasks.flatMap(task => task.artifacts).find(item => item.id === element.dataset.id);
    openDialog(artifact.title, `${artifactContent(artifact)}<div class="form-actions">${button('download-artifact', '下载 Markdown', { className: 'outline', attrs: `data-id="${e(artifact.id)}"` })}</div>`, 'document-dialog');
  },
  'download-artifact': element => {
    const artifact = ctx.state.tasks.flatMap(task => task.artifacts).find(item => item.id === element.dataset.id);
    const url = URL.createObjectURL(new Blob([artifact.body], { type: 'text/markdown;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = `${artifact.title.replace(/[\\/:*?"<>|]/g, '-')}.md`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
  settings: () => openDialog('Pi 尝试版本', `<div class="form"><p>${ctx.state.agentReady ? '模型已连接。' : '尚未连接模型，可先上传、划分和手动安排任务。'}</p><p class="muted">每次批改或自由任务的准入预算：$${ctx.state.runBudgetUsd}。模型费用以实际回执为准。</p><details><summary>运行设置</summary><p>在服务进程配置 OPENROUTER_API_KEY，或启动时使用 --env 指定本地凭据文件。使用 --cap 调整预算。凭据不会发送到浏览器。</p></details><p class="muted">材料、任务和审阅草稿保存在本机。此版本不发布成绩。</p></div>`),
};
for (const [action, offset] of [['page-left', -1], ['page-right', 1]]) actions[action] = async element => {
  const pages = ctx.state.groups.flatMap(group => group.pageIds); const index = pages.indexOf(element.dataset.id);
  if (!pages[index + offset]) return;
  await savePartition(movedGroups(ctx.state.groups, element.dataset.id, pages[index + offset]));
};

document.addEventListener('click', event => {
  const element = event.target.closest('[data-action]');
  if (element && !element.disabled && actions[element.dataset.action]) {
    event.preventDefault(); Promise.resolve().then(() => actions[element.dataset.action](element)).catch(error => { toast(error.message); render(); });
  }
  if (event.target === dialog) { const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeDialog(); }
});
document.addEventListener('input', event => {
  if (event.target.closest('#material-command')) ctx.command = event.target.value;
  if (event.target.closest('#review-form')) {
    const form = document.querySelector('#review-form'); const data = new FormData(form);
    const value = data.get('score'); ctx.reviewDrafts[ctx.currentRecord.id] = { score: value === 'null' || value === null ? null : Number(value), reason: data.get('reason') };
    for (const label of form.querySelectorAll('.score-option')) label.classList.toggle('selected', label.querySelector('input').checked);
  }
});
document.addEventListener('change', event => {
  if (event.target.closest('#task-form')) refreshTaskSetup(event.target.closest('#task-form'), ctx.state, event.target);
  if (event.target.matches('[data-group]')) { const id = event.target.dataset.group; event.target.checked ? ctx.selected.add(id) : ctx.selected.delete(id); render(); }
  if (event.target.id === 'review-task') { ctx.reviewTaskId = event.target.value; ctx.reviewIndex = 0; ctx.sourcePage = {}; render(); }
  if (event.target.dataset.source) { ctx.sourcePage[event.target.dataset.source] = Number(event.target.value); render(); }
});
uploadInput.addEventListener('change', () => upload(uploadInput.files).catch(error => toast(error.message)));
document.addEventListener('submit', event => {
  event.preventDefault(); const form = event.target; const data = new FormData(form);
  Promise.resolve().then(async () => {
    if (form.id === 'material-command' || form.id === 'assistant-form') return askAgent(String(data.get('goal')).trim());
    if (form.id === 'split-form') { await savePartition(equalGroups(ctx.state.groups, Number(data.get('count')))); closeDialog(); }
    if (form.id === 'rename-group-form') { const groups = structuredClone(ctx.state.groups); groups.find(group => group.id === form.dataset.id).label = String(data.get('label')); await savePartition(groups); closeDialog(); }
    if (form.id === 'project-form') { await request('/api/project', { title: String(data.get('title')) }, 'PATCH'); closeDialog(); }
    if (form.id === 'task-form') {
      const previous = new Set(ctx.state.tasks.map(task => task.id));
      await request(modalTaskId ? `/api/tasks/${modalTaskId}` : '/api/tasks', taskFormInput(data), modalTaskId ? 'PATCH' : 'POST');
      ctx.activeTaskId = modalTaskId || ctx.state.tasks.find(task => !previous.has(task.id))?.id; ctx.taskList = false; closeDialog(); navigate('tasks');
    }
    if (form.id === 'review-form') {
      const record = ctx.currentRecord, value = data.get('score');
      await request('/api/reviews', { taskId: ctx.reviewTaskId, recordId: record.id, originalHash: record.originalHash, score: value === 'null' || value === null ? null : Number(value), reason: String(data.get('reason')) });
      delete ctx.reviewDrafts[record.id]; toast('复核草稿已保存，原始评分保留。');
    }
    render();
  }).catch(error => toast(error.message));
});
document.addEventListener('dragstart', event => { const tile = event.target.closest('[data-page-id]'); if (tile && ctx.sorting) { dragPage = tile.dataset.pageId; event.dataTransfer.setData('text/plain', dragPage); } });
document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files') || dragPage) event.preventDefault(); });
document.addEventListener('drop', event => {
  event.preventDefault();
  if (event.dataTransfer.files.length) { ctx.uploadRole = ctx.materialRole; void upload(event.dataTransfer.files).catch(error => toast(error.message)); return; }
  const target = event.target.closest('[data-page-id]');
  if (dragPage && target) { const groups = movedGroups(ctx.state.groups, dragPage, target.dataset.pageId); if (groups) void savePartition(groups).catch(error => toast(error.message)); }
  dragPage = null;
});
document.addEventListener('dragend', () => { dragPage = null; });
window.addEventListener('hashchange', () => { if (['materials', 'tasks', 'review'].includes(location.hash.slice(1))) { ctx.tab = location.hash.slice(1); render(); } });
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh().then(render).catch(() => {}); });
setInterval(async () => {
  if (document.hidden || !ctx.state?.tasks.some(task => task.status === 'running') || ctx.busy) return;
  try { const revision = ctx.state.revision; await refresh(); if (revision !== ctx.state.revision && !dialog.open && !document.activeElement.matches('input, textarea, select')) render(); } catch { /* Preserve current screen during a transient disconnect. */ }
}, 2000);
try { await refresh(); render(); } catch (error) { app.innerHTML = `<div class="empty"><h1>工作区暂时无法打开</h1><p>${e(error.message)}</p><a href="/">重新加载</a></div>`; }

}
