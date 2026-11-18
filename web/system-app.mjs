import { e, glyph, button, shell, home, filesPage, skillsPage, tasksPage, settingsPage, fileUrl, refMeta, fileScope, date, status, markdown } from './system-view.mjs';

const app = document.querySelector('#system-app'), dialog = document.querySelector('#system-dialog');
const ctx = { state: null, grading: null, route: 'home', threadId: null, thread: null, file: null, refs: [], skillId: null, draft: '', sending: false, query: '', filter: 'all', slide: 1, slideCount: 0 };
let token = '', pollBusy = false, toastTimer, pollTimer, lastFocus, previousActive, lastSignature = '', draftTimer;
const draftKey = 'gradeos-workbench-draft-v1';
function syncNavigation() {
  const mobile = matchMedia('(max-width:700px)').matches, open = document.body.classList.contains('nav-open');
  const sidebar = document.querySelector('.sidebar'), main = document.querySelector('#main');
  if (sidebar) sidebar.inert = mobile && !open;
  if (main) main.inert = mobile && open;
  document.querySelector('[data-action="menu"]')?.setAttribute('aria-expanded', String(open));
}
matchMedia('(max-width:700px)').addEventListener('change', syncNavigation);
function toast(message) { const node = document.querySelector('#system-toast'); node.textContent = message; node.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('visible'), 6000); const alert = dialog.querySelector('[role="alert"]'); if (alert) alert.textContent = message; }
async function api(path, body, method = 'POST') {
  const response = await fetch(path, body === undefined ? {} : { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token }, body: JSON.stringify(body) });
  const result = await response.json(); if (!response.ok) throw Error(result.error || '操作未完成。'); return result;
}
async function state() { const [system, grading] = await Promise.all([api('/api/system/state'), api('/api/state')]); ctx.state = system; ctx.grading = grading; token = grading.token; document.documentElement.dataset.motion = system.preferences.motion; }
function persistDraft() { try { localStorage.setItem(draftKey, JSON.stringify({ draft: ctx.draft, refs: ctx.refs, threadId: ctx.threadId, skillId: ctx.skillId })); } catch { /* Full or disabled browser storage does not block local server state. */ } }
function closeDialog() { dialog.close(); lastFocus?.focus?.(); }
function openDialog(title, body, className = '') {
  lastFocus = document.activeElement; dialog.className = className;
  dialog.innerHTML = `<header><h2 id="dialog-title">${e(title)}</h2>${button('close-dialog', glyph('close'), 'aria-label="关闭"', 'icon-button')}</header><div role="alert"></div><div class="dialog-content">${body}</div>`;
  if (!dialog.open) dialog.showModal();
}
function render() {
  if (!ctx.state) return;
  if (!document.querySelector('#page')) app.innerHTML = shell(ctx.state, ctx.route);
  syncNavigation();
  const page = document.querySelector('#page'), focus = document.activeElement, selection = focus?.selectionStart;
  const scrollNode = page.querySelector('.messages,.artifact-scroll,.list-page'), scroll = scrollNode?.scrollTop;
  document.querySelectorAll('a[data-route]').forEach(link => { if (link.dataset.route === ctx.route) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
  const account = document.querySelector('.account'); account.querySelector('.avatar').textContent = ctx.state.preferences.displayName.slice(0, 1); account.querySelectorAll('span')[1].textContent = ctx.state.preferences.displayName;
  if (ctx.route === 'grading' && page.querySelector('.grading-frame')) return;
  page.innerHTML = ctx.route === 'home' ? home(ctx) : ctx.route === 'files' ? filesPage(ctx) : ctx.route === 'skills' ? skillsPage(ctx) : ctx.route === 'tasks' ? tasksPage(ctx) : ctx.route === 'settings' ? settingsPage(ctx) : `<iframe class="grading-frame" title="批改工作区" src="/grading?embedded=1"></iframe>`;
  page.dataset.route = ctx.route;
  if (focus?.id && document.getElementById(focus.id)) { const next = document.getElementById(focus.id); next.focus({ preventScroll: true }); if (selection != null) next.setSelectionRange?.(selection, selection); }
  const nextScroll = page.querySelector('.messages,.artifact-scroll,.list-page'); if (nextScroll && scroll != null) nextScroll.scrollTop = scroll;
}
function navigate(route) { ctx.route = ['home', 'grading', 'files', 'skills', 'tasks', 'settings'].includes(route) ? route : 'home'; document.body.classList.remove('nav-open'); if (location.hash !== `#${ctx.route}`) history.pushState(null, '', `#${ctx.route}`); render(); }
async function openThread(id) { ctx.threadId = id; ctx.thread = await api(`/api/system/threads/${encodeURIComponent(id)}`); ctx.file = null; ctx.refs = []; ctx.draft = ''; navigate('home'); persistDraft(); }
async function openFile(id, revision, hash) {
  ctx.file = await api(`/api/system/files/${encodeURIComponent(id)}${revision ? `?revision=${revision}${hash ? `&hash=${encodeURIComponent(hash)}` : ''}` : ''}`); ctx.slide = 1;
  ctx.slideCount = ctx.file.title.endsWith('.html') ? new DOMParser().parseFromString(ctx.file.body, 'text/html').body.querySelectorAll(':scope > section').length : 0;
  if (ctx.file.threadId) { ctx.threadId = ctx.file.threadId; ctx.thread = await api(`/api/system/threads/${encodeURIComponent(ctx.threadId)}`); }
  else { ctx.threadId = null; ctx.thread = null; }
  ctx.refs = [refMeta(ctx.file)]; navigate('home'); persistDraft();
}
function showHistory() {
  openDialog('历史对话', ctx.state.threads.length ? `<div class="menu-list">${[...ctx.state.threads].reverse().map(thread => button('thread', `<span>${e(thread.title)}</span><small>${date(thread.updatedAt)}</small>`, `data-id="${e(thread.id)}"`)).join('')}</div>` : '<p class="muted">还没有对话。发送任务后会自动保存在本机。</p>');
}
function addReference(file) { if (ctx.refs.length >= 8) throw Error('最多引用 8 个文件。'); if (!ctx.refs.some(ref => ref.id === file.id && ref.hash === file.hash)) ctx.refs.push(refMeta(file)); persistDraft(); }
function sources() { openDialog('引用工作区文件', `<p class="muted">引用固定版本；新的批改结果不会替换当前引用。</p><div class="menu-list">${ctx.state.files.length ? ctx.state.files.map(file => button('reference', `<span>${e(file.title)}</span><small>${e(fileScope(file))} · v${file.revision} · ${status(file.status)}</small>`, `data-id="${e(file.id)}"`)).join('') : '<p>还没有可引用的文件。</p>'}</div>`); }
async function upload(files) {
  for (const file of files) {
    if (file.size > 2 * 1024 * 1024) throw Error(`${file.name} 超过 2 MB。`);
    const result = await api('/api/system/files', { title: file.name, body: await file.text() }); ctx.state = result; addReference(result.file);
  }
  closeDialog(); render(); toast('文件已保存到本地工作区。');
}
const actions = {
  new: () => { ctx.thread = null; ctx.threadId = null; ctx.file = null; ctx.refs = []; ctx.draft = ''; ctx.skillId = null; navigate('home'); persistDraft(); document.querySelector('#task-input')?.focus(); },
  menu: () => { document.body.classList.toggle('nav-open'); syncNavigation(); document.querySelector('.sidebar a')?.focus(); }, 'close-nav': () => { document.body.classList.remove('nav-open'); syncNavigation(); document.querySelector('[data-action="menu"]')?.focus(); },
  'close-dialog': closeDialog,
  account: () => openDialog(ctx.state.preferences.displayName, `<div class="menu-list">${button('settings', '账号与设置')}${button('history', '历史对话')}${button('help', '关于 GradeOS')}</div>`),
  settings: () => { closeDialog(); navigate('settings'); }, workspace: () => { closeDialog(); navigate('settings'); },
  help: () => openDialog('GradeOS', '<p>本地工作区，连接你的模型服务。文件、对话和任务保存在本机。</p><p>工作台处理通用任务；批改保留独立的材料、评分和复核流程。两者通过文件版本衔接。</p><p>代码采用 GPL-3.0-only。第三方依赖保留各自许可证。</p>'),
  history: showHistory,
  thread: async node => { closeDialog(); await openThread(node.dataset.id); },
  grading: () => { closeDialog(); navigate('grading'); },
  add: () => openDialog('添加到任务', `<div class="menu-list">${button('upload', '导入本地文件')}${button('sources', '引用工作区文件')}${button('choose-skill', '选择 Skill')}${button('history', '历史对话')}</div>`, 'compact-dialog'),
  sources,
  upload: () => document.querySelector('#system-upload').click(),
  reference: node => { addReference(ctx.state.files.find(file => file.id === node.dataset.id)); closeDialog(); render(); },
  'remove-ref': node => { ctx.refs.splice(Number(node.dataset.index), 1); persistDraft(); render(); },
  'choose-skill': () => openDialog('选择 Skill', `<div class="menu-list">${ctx.state.skills.filter(skill => skill.enabled).map(skill => button('select-skill', `<span>${e(skill.name)}</span><small>${e(skill.description)}</small>`, `data-id="${e(skill.id)}"`)).join('') || '<p>可在 Skills 中启用能力。</p>'}</div>`),
  'select-skill': node => { ctx.skillId = node.dataset.id; closeDialog(); persistDraft(); render(); },
  'clear-skill': () => { ctx.skillId = null; persistDraft(); render(); },
  file: async node => { closeDialog(); await openFile(node.dataset.id, node.dataset.revision, node.dataset.hash); },
  continue: node => { const file = ctx.state.files.find(file => file.id === node.dataset.id); ctx.threadId = null; ctx.thread = null; ctx.file = null; ctx.refs = [refMeta(file)]; ctx.draft = ''; navigate('home'); persistDraft(); document.querySelector('#task-input').focus(); },
  'filter-all': () => { ctx.filter = 'all'; render(); }, 'filter-grading': () => { ctx.filter = 'grading'; render(); },
  'toggle-skill': async node => { const skill = ctx.state.skills.find(skill => skill.id === node.dataset.id); ctx.state = await api(`/api/system/skills/${skill.id}`, { enabled: !skill.enabled }, 'PATCH'); render(); },
  'import-skill': () => document.querySelector('#skill-upload').click(),
  cancel: async () => { await api('/api/system/cancel', {}); toast('已请求停止，正在保存当前状态…'); await refresh(true); },
  info: () => { const file = ctx.file, latest = ctx.state.files.find(row => row.id === file.id); openDialog('文件信息', `<dl class="file-info"><dt>名称</dt><dd>${e(file.title)}</dd><dt>当前版本</dt><dd>v${file.revision}${latest?.hash !== file.hash ? ' · 已有新版本' : ''}</dd><dt>状态</dt><dd>${status(file.status)}</dd><dt>来源</dt><dd>${file.origin === 'grading' ? '批改' : '工作台'}</dd>${file.relativePath ? `<dt>本地文件</dt><dd>${e(ctx.state.directory + '/' + file.relativePath)}</dd>` : ''}<dt>更新时间</dt><dd>${date(file.updatedAt)}</dd></dl>${latest?.hash !== file.hash ? button('file', '打开最新版本', `data-id="${e(file.id)}"`, 'outline') : ''}${file.origin !== 'grading' && file.versionCount > 1 ? `<h3>文件版本</h3><div class="version-list">${Array.from({length:file.versionCount},(_,i)=>button('file', `v${i+1}`, `data-id="${e(file.id)}" data-revision="${i+1}"`, 'outline')).join('')}</div>` : ''}<h3>引用来源</h3>${file.sources?.length ? `<div class="menu-list">${file.sources.map(ref => `${button('file', `${e(ref.title)} · v${ref.revision}`, `data-id="${e(ref.id)}" data-revision="${ref.revision}" data-hash="${e(ref.hash)}"`)}`).join('')}</div>` : '<p class="muted">没有附加来源。</p>'}`); },
  edit: () => { if (ctx.file.origin === 'grading') { toast('请在批改工作区编辑或复核原始结果。'); return; } openDialog('编辑文件', `<form id="file-editor"><label>文件名<input name="title" value="${e(ctx.file.title)}" maxlength="120" required></label><label class="sr-only" for="file-body">文件内容</label><textarea id="file-body" name="body" spellcheck="false">${e(ctx.file.body)}</textarea><div class="form-footer"><span>保存为新版本</span><button type="submit" class="primary">保存</button></div></form>`, 'editor-dialog'); },
  process: () => { const messages = ctx.thread?.messages || []; openDialog('处理过程', messages.length ? messages.map(message => `<article class="process-message"><h3>${message.role === 'user' ? '你的要求' : 'GradeOS'}</h3><div class="prose">${markdown(message.text)}</div>${message.events?.filter(event => event.type === 'tool_execution_end').map(event => `<p class="muted">${e(event.label)} · ${event.status === 'error' ? '未完成' : '完成'}</p>`).join('') || ''}</article>`).join('') : `<p>来源：${ctx.file?.origin === 'grading' ? '批改工作区' : '本地导入'}</p>${ctx.file?.origin === 'grading' ? button('grading', '打开批改', '', 'outline') : ''}`); },
  'previous-slide': () => { ctx.slide = Math.max(1, ctx.slide - 1); render(); }, 'next-slide': () => { ctx.slide = Math.min(ctx.slideCount, ctx.slide + 1); render(); },
};
document.addEventListener('click', async event => {
  const node = event.target.closest('[data-action]'); if (!node || !actions[node.dataset.action]) return;
  try { await actions[node.dataset.action](node); } catch (error) { toast(error.message); }
});
document.addEventListener('click', event => { const link = event.target.closest('a[data-route]'); if (!link) return; event.preventDefault(); if (link.dataset.route === 'home' && ctx.route === 'home') showHistory(); else navigate(link.dataset.route); });
document.addEventListener('input', event => {
  if (event.target.id === 'task-input') { ctx.draft = event.target.value; const send = document.querySelector('.send'); if (send && !ctx.state.active) send.disabled = !ctx.draft.trim(); clearTimeout(draftTimer); draftTimer = setTimeout(persistDraft, 200); }
  if (event.target.id === 'file-search') { ctx.query = event.target.value; render(); }
});
document.addEventListener('keydown', event => { if (event.target.id === 'task-input' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!ctx.sending && ctx.draft.trim() && !ctx.state.active) event.target.form.requestSubmit(); } if (event.key === 'Escape') { document.body.classList.remove('nav-open'); syncNavigation(); } });
document.addEventListener('submit', async event => {
  event.preventDefault(); const form = event.target, body = Object.fromEntries(new FormData(form));
  try {
    if (form.id === 'preferences-form') { ctx.state = await api('/api/system/preferences', body, 'PATCH'); document.documentElement.dataset.motion = ctx.state.preferences.motion; render(); toast('设置已保存。'); }
    else if (form.id === 'file-editor') { await api('/api/system/files', { ...body, id: ctx.file.id, revision: ctx.file.revision }); closeDialog(); await state(); await openFile(ctx.file.id); toast('新版本已保存。'); }
    else if (form.id === 'task-composer' && ctx.draft.trim() && !ctx.sending) {
      if (!ctx.state.connection.ready) { openDialog('连接模型', `<p>工作台尚未连接模型。文件已保存在本机，你的要求也会保留。</p>${button('settings', '查看模型设置', '', 'primary')}`); return; }
      ctx.sending = true; render();
      try { const result = await api('/api/system/chat', { goal: ctx.draft, threadId: ctx.threadId, references: ctx.refs, skillId: ctx.skillId }); ctx.state = result; ctx.threadId = result.threadId; ctx.thread = await api(`/api/system/threads/${ctx.threadId}`); ctx.draft = ''; ctx.file = null; persistDraft(); }
      finally { ctx.sending = false; render(); }
    }
  } catch (error) { toast(error.message); }
});
document.querySelector('#system-upload').addEventListener('change', async event => { try { await upload([...event.target.files]); } catch (error) { toast(error.message); } finally { event.target.value = ''; } });
document.querySelector('#skill-upload').addEventListener('change', async event => { try { const file = event.target.files[0]; if (!file) return; if (file.size > 80000) throw Error('SKILL.md 文件过大。'); const instructions = await file.text(); openDialog('导入 Skill', `<form id="skill-import-form"><label>名称<input name="name" value="${e(file.name.replace(/\.md$/i, ''))}" maxlength="60" required></label><p>导入后默认关闭，可在 Skills 中启用。</p><details><summary>查看任务指南</summary><pre>${e(instructions)}</pre></details><button type="submit" class="primary">导入</button></form>`); dialog.querySelector('form').addEventListener('submit', async event => { event.preventDefault(); try { ctx.state = await api('/api/system/skills', { name: new FormData(event.target).get('name'), instructions }); closeDialog(); render(); } catch (error) { toast(error.message); } }); } catch (error) { toast(error.message); } finally { event.target.value = ''; } });
document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files') && ctx.route !== 'grading') { event.preventDefault(); document.body.classList.add('dragging'); } });
document.addEventListener('dragleave', event => { if (!event.relatedTarget) document.body.classList.remove('dragging'); });
document.addEventListener('drop', async event => { document.body.classList.remove('dragging'); if (!event.dataTransfer.files.length || ctx.route === 'grading') return; event.preventDefault(); try { await upload([...event.dataTransfer.files]); } catch (error) { toast(error.message); } });
window.addEventListener('hashchange', () => navigate(location.hash.slice(1)));
async function refresh(force = false) {
  if (pollBusy) return; pollBusy = true;
  try {
    await state(); const signature = JSON.stringify([ctx.state.revision, ctx.grading.revision, ctx.state.active]);
    if (signature === lastSignature && !force) return; lastSignature = signature;
    if (ctx.threadId) ctx.thread = await api(`/api/system/threads/${encodeURIComponent(ctx.threadId)}`);
    const finished = previousActive && !ctx.state.active && previousActive.threadId === ctx.threadId && ctx.route === 'home'; previousActive = ctx.state.active;
    if (finished && ctx.thread?.messages.at(-1)?.fileIds?.length) await openFile(ctx.thread.messages.at(-1).fileIds.at(-1));
    else if (ctx.file && ctx.route === 'home') {
      const label = document.querySelector('.artifact-status>span');
      if (label) label.textContent = ctx.state.active?.threadId === ctx.threadId ? '正在处理…' : ctx.file.origin === 'grading' ? status(ctx.file.status) : '文件已保存';
    }
    else if (!(ctx.route === 'settings' && document.querySelector('#preferences-form')?.contains(document.activeElement))) render();
  } catch (error) { if (force) toast(error.message); }
  finally { pollBusy = false; }
}
try {
  await state();
  try { const saved = JSON.parse(localStorage.getItem(draftKey) || '{}'); ctx.draft = String(saved.draft || '').slice(0, 8000); ctx.refs = Array.isArray(saved.refs) ? saved.refs.slice(0, 8) : []; ctx.skillId = saved.skillId || null; if (saved.threadId && ctx.state.threads.some(thread => thread.id === saved.threadId)) { ctx.threadId = saved.threadId; ctx.thread = await api(`/api/system/threads/${ctx.threadId}`); } } catch { /* An invalid browser draft must not prevent startup. */ }
  navigate(location.hash.slice(1) || 'home'); pollTimer = setInterval(() => { if (!document.hidden) void refresh(); }, 1500);
  window.addEventListener('pagehide', () => { clearInterval(pollTimer); persistDraft(); });
} catch (error) { app.innerHTML = `<section class="boot"><h1>无法打开工作区</h1><p>${e(error.message)}</p><a href="/">重新连接</a></section>`; }
