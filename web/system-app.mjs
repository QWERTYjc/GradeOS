import { composerModelKey, setComposerModel } from './ui.mjs';
import { gradingModel, recommendedChatIds } from './grading-models.mjs';
import { archiveSourceBody } from './grading-library.mjs';
import './workspace-field.mjs';
import './interface-motion.mjs';
import './batch-previews.mjs';
import { routes, e, glyph, button, quickGoogleLink, passwordLoginButton, shell, sidebarRecent, home, composer, gradingOverview, gradingHistory, filesPage, referenceTree, skillsPage, settingsPage, fileUrl, refMeta, fileScope, date, status, markdown } from './system-view.mjs';

const app = document.querySelector('#system-app'), dialog = document.querySelector('#system-dialog');
const ctx = { state: null, grading: null, route: 'home', threadId: null, thread: null, file: null, refs: [], skillId: null, draft: '', sending: false, query: '', archiveFolders: new Map(), archiveSearchFolders: new Map(), filter: 'all', taskId: null, slide: 1, slideCount: 0 };
let previousMarkup = '', contextKey = '', navigationId = 0, composing = false;
let waitingForGoogle = false;
const drafts = new Map();
const journalPositions = new Map(), expandedSteps = new Map(), renderedMessages = new WeakMap();
let previewOffset = 0, historyOffset = 0;
let pageTransition;
let token = '', pollBusy = false, toastTimer, lastFocus, lastSignature = '', draftTimer;
const draftKey = 'gradeos-workbench-draft-v1';
const narrowSidebar = matchMedia('(max-width: 700px)');
const sidebarKey = 'gradeos-sidebar-collapsed';
let desktopCollapsed = false, recentMarkup = '';
try { desktopCollapsed = localStorage.getItem(sidebarKey) === 'true'; } catch {}
const readBatches = new Set();
const readKey = id => 'gradeos-read-batch/' + encodeURIComponent(ctx.state.directory) + '/' + encodeURIComponent(id);
function batchIsRead(id) {
  const key = readKey(id);
  if (readBatches.has(key)) return true;
  try { return localStorage.getItem(key) === '1'; } catch { return false; }
}
document.addEventListener('gradeos-result-viewed', event => {
  if (!event.target.matches?.('.grading-frame') || !ctx.state || !event.detail || batchIsRead(event.detail)) return;
  const key = readKey(event.detail);
  readBatches.add(key);
  try { localStorage.setItem(key, '1'); } catch {}
  render();
});
window.addEventListener('storage', event => {
  if (ctx.state && event.key?.startsWith('gradeos-read-batch/')) render();
});
function syncSidebar() {
  const drawer = app.querySelector('#navigation-drawer');
  const rail = app.querySelector('.workspace-sidebar');
  const trigger = app.querySelector('.nav-trigger');
  const closed = !narrowSidebar.matches && desktopCollapsed;
  app.toggleAttribute('data-sidebar-collapsed', closed);
  rail.inert = closed;
  trigger.setAttribute('aria-controls', narrowSidebar.matches ? drawer.id : rail.id);
  trigger.setAttribute('aria-expanded', String(narrowSidebar.matches ? drawer.open : !closed));
}
function setSidebarCollapsed(collapsed) {
  desktopCollapsed = collapsed;
  try { localStorage.setItem(sidebarKey, String(collapsed)); } catch {}
  syncSidebar();
  app.querySelector(collapsed ? '.nav-trigger' : '.nav-dismiss').focus({preventScroll:true});
}
function closeNavigation() {
  const drawer = app.querySelector('#navigation-drawer');
  if (drawer?.open) { drawer.close(); syncSidebar(); }
}
function setupNavigation() {
  const gradingGroup = app.querySelector('.grading-nav');
  try { gradingGroup.open = localStorage.getItem('gradeos-grading-expanded') !== 'false'; } catch {}
  gradingGroup.addEventListener('toggle', () => {
    try { localStorage.setItem('gradeos-grading-expanded', String(gradingGroup.open)); } catch {}
  });
  const drawer = app.querySelector('#navigation-drawer');
  const rail = app.querySelector('.workspace-sidebar');
  const main = app.querySelector('#main');
  const placeSidebar = () => {
    if (narrowSidebar.matches) drawer.append(rail);
    else {
      closeNavigation();
      main.before(rail);
    }
    syncSidebar();
  };
  placeSidebar();
  narrowSidebar.addEventListener('change', placeSidebar);
  drawer.addEventListener('cancel', event => { event.preventDefault(); closeNavigation(); });
  drawer.addEventListener('click', event => { if (event.target === drawer) closeNavigation(); });
}
function toast(message) { const node = document.querySelector('#system-toast'); node.textContent = message; node.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('visible'), 6000); const alert = dialog.querySelector('[role="alert"]'); if (alert) alert.textContent = message; }
async function api(path, body, method = 'POST') {
  const response = await fetch(path, body === undefined ? {} : { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token }, body: JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok) throw Object.assign(Error(result.error || '操作未完成。'), {status:response.status});
  return result;
}
function syncMotion() {
  const value = ctx.state.preferences.motion;
  if (document.documentElement.dataset.motion === value) return;
  document.documentElement.dataset.motion = value;
  try { localStorage.setItem('gradeos-interface-motion', value); } catch {}
  const frame = document.querySelector('.grading-frame');
  if (frame?.contentDocument) frame.contentDocument.documentElement.dataset.motion = value;
}
async function state(full = true) {
  const [system, grading] = await Promise.all([api('/api/system/state'), full ? api('/api/state?summary=1') : null]);
  if (!ctx.state || system.revision > ctx.state.revision ||
      (system.revision === ctx.state.revision && (system.gradingRevision || 0) >= (ctx.state.gradingRevision || 0))) ctx.state = system;
  if (grading) acceptGrading(grading);
  else if (system.gradingRevision > ctx.grading?.revision) acceptGrading(await api('/api/state?summary=1'));
  syncMotion();
}
function acceptGrading(grading) {
  if (ctx.grading && grading.revision < ctx.grading.revision) return;
  ctx.grading = grading;
  token = grading.token;
}
function rememberDraft() {
  if (!contextKey) return;
  const defaultRefs = ctx.file ? [refMeta(ctx.file)] : [];
  if (!ctx.draft && !ctx.skillId && JSON.stringify(ctx.refs) === JSON.stringify(defaultRefs)) drafts.delete(contextKey);
  else drafts.set(contextKey, { draft:ctx.draft, refs:ctx.refs, skillId:ctx.skillId });
}
function persistDraft() {
  rememberDraft();
  try { localStorage.setItem(draftKey, JSON.stringify({ drafts:Object.fromEntries(drafts), resume:ctx.resume })); } catch {}
}
function restoreDrafts() {
  try {
    const saved = JSON.parse(localStorage.getItem(draftKey) || '{}');
    const entries = saved.drafts ? Object.entries(saved.drafts) : [[saved.threadId ? 'thread/' + encodeURIComponent(saved.threadId) : 'home', saved]];
    for (const [key, value] of entries) if (value && typeof value === 'object') {
      drafts.set(key, { draft:String(value.draft || '').slice(0, 8000), refs:Array.isArray(value.refs) ? value.refs.slice(0, 8) : [], skillId:value.skillId || null });
    }
    const resume = saved.resume || (saved.threadId && 'thread/' + encodeURIComponent(saved.threadId));
    if (typeof resume === 'string' && /^(file|thread)\//.test(resume)) ctx.resume = resume;
  } catch { /* A damaged draft must not block access to the workbench. */ }
}
function activate(key, file = null, thread = null) {
  if (key !== contextKey) {
    rememberDraft();
    const saved = drafts.get(key);
    ctx.draft = saved?.draft || '';
    ctx.refs = saved?.refs || (file ? [refMeta(file)] : []);
    ctx.skillId = saved?.skillId || null;
    contextKey = key;
  }
  ctx.file = file; ctx.thread = thread; ctx.threadId = thread?.id || null;
  if (key !== 'home') ctx.resume = key;
  persistDraft();
}
function closeDialog() { if (dialog.open) { dialog.close(); lastFocus?.focus?.(); } }
function openDialog(title, body, className = '') {
  lastFocus = document.activeElement; dialog.className = className;
  dialog.innerHTML = `<header><h2 id="dialog-title">${e(title)}</h2>${button('close-dialog', glyph('close'), 'aria-label="关闭"', 'icon-button')}</header><div role="alert"></div><div class="dialog-content">${body}</div>`;
  if (!dialog.open) dialog.showModal();
}
function updateAssistant(page, markup) {
  const next = document.createElement('template');
  next.innerHTML = markup;
  for (const selector of ['.assistant-links','#reference-chips','.composer-model','.send']) {
    const current = page.querySelector(selector), replacement = next.content.querySelector(selector);
    if (current && replacement && current.outerHTML !== replacement.outerHTML) current.replaceWith(replacement);
  }
  const input = page.querySelector('#task-input');
  if (input && input.value !== ctx.draft) input.value = ctx.draft;
  const journal = page.querySelector('.workflow-journal');
  if (!journal) return;
  const messages = new Map([...journal.children].map(node => [node.dataset.message, node]));
  for (const row of next.content.querySelectorAll('[data-message]')) {
    const key = row.dataset.message, prior = messages.get(key), log = row.querySelector('.execution-log');
    if (log && expandedSteps.has(key)) log.open = expandedSteps.get(key);
    const markup = row.outerHTML;
    if (prior && (renderedMessages.get(prior) ?? prior.outerHTML) === markup) { renderedMessages.set(prior, markup); continue; }
    renderedMessages.set(row, markup);
    if (!prior) journal.append(row);
    else {
      const refocus = prior.contains(document.activeElement) && document.activeElement.matches('summary');
      prior.replaceWith(row);
      if (refocus) log?.querySelector('summary')?.focus({preventScroll:true});
    }
  }
}
function render() {
  if (!ctx.state) return;
  if (!document.querySelector('#page')) {
    app.innerHTML = shell(ctx.state, ctx.route);
    setupNavigation();
  }
  const page = document.querySelector('#page'), focus = document.activeElement, selection = focus?.selectionStart, selectionEnd = focus?.selectionEnd;
  const scrollSelector = '.messages,.artifact-scroll,.list-page,.dashboard';
  const scrollNode = page.querySelector(scrollSelector);
  const beforeScroll = scrollNode?.scrollTop || 0;
  const gradingIndex = ctx.route === 'grading' && !ctx.taskId && !ctx.intakeView && !ctx.gradingFile;
  let viewKey = ctx.route;
  if (gradingIndex) viewKey = ctx.gradingHistory ? 'grading-history' : 'grading-overview';
  else if (ctx.route === 'grading') viewKey = ['grading', ctx.intakeView || ctx.taskId, ctx.gradingFile?.key, ctx.gradingFile?.id].filter(Boolean).join('/');
  else if (ctx.route === 'files' && ctx.fileBatchId) viewKey = 'files/' + ctx.fileBatchId;
  else if (ctx.route === 'home') viewKey = ctx.file || ctx.thread ? contextKey : 'dashboard';
  const changedView = page.dataset.view !== viewKey;
  if (!changedView && composing) return;
  const onJournal = scrollNode?.id === 'messages';
  const atEnd = onJournal && scrollNode.scrollHeight - scrollNode.clientHeight - beforeScroll < 48;
  if (changedView && onJournal) journalPositions.set(page.dataset.view, {top:beforeScroll, atEnd});
  const reading = ctx.route === 'home' && (ctx.file || ctx.thread);
  const recents = ctx.grading.recentResults || [];
  const recent = sidebarRecent(recents, batchIsRead);
  if (recent !== recentMarkup) { app.querySelector('.nav-recents').innerHTML = recent; recentMarkup = recent; }
  let activeRoute = reading && ctx.file ? 'files' : ctx.route;
  if (ctx.route === 'grading') {
    if (ctx.intakeView) activeRoute = 'grading/intake';
    else if (ctx.gradingHistory) activeRoute = 'grading/history';
    else if (ctx.taskId) activeRoute = recents.slice(0, 3).some(task => task.id === ctx.taskId) ? 'grading/' + encodeURIComponent(ctx.taskId) : 'grading/history';
  }
  const field = app.querySelector('workspace-field');
  const scene = reading ? 'reader' : ctx.route === 'grading' && !changedView && field.dataset.scene === 'intake' ? 'intake' : ctx.route;
  if (field.dataset.scene !== scene) field.dataset.scene = scene;
  document.querySelectorAll('.work-nav a[data-route]').forEach(link => {
    if (link.dataset.route === activeRoute) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  const account = app.querySelector('.account');
  const name = ctx.state.account?.user?.name || ctx.state.preferences.displayName;
  account.title = name + '，账号与设置';
  account.toggleAttribute('data-current', ctx.route === 'settings');
  account.querySelector('.account-name').textContent = name;
  account.setAttribute('aria-label', name + '，账号与设置');
  account.querySelector('.avatar').textContent = Array.from(name)[0] || '';
  const batchTitle = ctx.taskId && ctx.grading.tasks.find(task => task.id === ctx.taskId)?.title;
  const title = reading ? (ctx.file?.title || ctx.thread.title) : ctx.intakeView ? '开始批改' : ctx.gradingHistory ? '批改历史' : batchTitle || routes[ctx.route];
  document.title = `${title} · GradeOS`;
  const views = { home, files: filesPage, skills: skillsPage, settings: settingsPage };
  const gradingParams = new URLSearchParams({ embedded:'1' });
  if (ctx.intakeView) gradingParams.set('view', ctx.intakeView);
  if (ctx.taskId) gradingParams.set('task', ctx.taskId);
  if (ctx.gradingFile) gradingParams.set(ctx.gradingFile.key, ctx.gradingFile.id);
  const markup = gradingIndex ? (ctx.gradingHistory ? gradingHistory(ctx, batchIsRead) : gradingOverview(ctx, batchIsRead)) : ctx.route === 'grading'
    ? `<iframe class="grading-frame" title="批改工作区" src="/grading?${e(gradingParams)}"></iframe>`
    : views[ctx.route](ctx);
  if (markup === previousMarkup && !changedView) return;
  previousMarkup = markup;
  if (page.dataset.view === 'grading-overview') previewOffset = page.querySelector('.preview-track')?.scrollLeft || 0;
  if (page.dataset.view === 'grading-history') historyOffset = beforeScroll;
  if (!changedView && (viewKey === 'dashboard' || viewKey.startsWith('thread/'))) {
    updateAssistant(page, markup);
  } else if (!changedView && ctx.route === 'files') {
    const template = document.createElement('template');
    template.innerHTML = markup;
    page.querySelector('.file-list').replaceChildren(...template.content.querySelector('.file-list').childNodes);
    for (const tab of page.querySelectorAll('[data-action="file-filter"]')) tab.setAttribute('aria-pressed', String(tab.dataset.filter === ctx.filter));
  } else {
    page.innerHTML = markup;
  }
  if (changedView) for (const log of page.querySelectorAll('.execution-log')) {
    const key = log.closest('[data-message]').dataset.message;
    if (expandedSteps.has(key)) log.open = expandedSteps.get(key);
  }
  page.dataset.view = viewKey;
  page.dataset.route = ctx.route;
  if (viewKey === 'grading-overview' && previewOffset) page.querySelector('.preview-track')?.scrollTo({left:previewOffset, behavior:'instant'});
  if (viewKey === 'grading-history' && changedView) page.querySelector('.grading-history').scrollTop = historyOffset;
  if (changedView && !pageTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches && document.documentElement.dataset.motion !== 'reduce') {
    page.firstElementChild?.animate([{ opacity: .45, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 240, easing: 'cubic-bezier(.2,.7,.25,1)' });
  }
  if (changedView && scrollNode) document.querySelector('#main').focus({preventScroll:true});
  if (!changedView) {
    let next = focus?.id && document.getElementById(focus.id);
    if (!next && focus?.dataset.route) next = [...page.querySelectorAll('a[data-route]')].find(link => link.dataset.route === focus.dataset.route);
    if (!next && focus?.dataset.action) {
      next = [...page.querySelectorAll('[data-action]')].find(node => node.dataset.action === focus.dataset.action && node.dataset.id === focus.dataset.id && node.dataset.filter === focus.dataset.filter);
    }
    if (next && !focus.isConnected) {
      next.focus({ preventScroll: true });
      if (selection != null) next.setSelectionRange?.(selection, selectionEnd ?? selection);
    }
  }
  const scroller = page.querySelector(scrollSelector);
  if (scroller?.id === 'messages') {
    const position = changedView ? journalPositions.get(viewKey) : {top:beforeScroll,atEnd};
    scroller.scrollTop = !position || position.atEnd ? scroller.scrollHeight : position.top;
  } else if (scroller && !changedView && scrollNode) scroller.scrollTop = beforeScroll;
  if (scroller && scroller !== scrollNode) field.primeScroll?.(scroller);
}
const filePath = (id, revision, hash) => ['file', encodeURIComponent(id), revision, hash].filter(Boolean).join('/');
async function navigate(path, { replace = false } = {}) {
  closeNavigation();
  if (path.split('/')[0] === 'tasks') path = 'grading/history';
  const visit = ++navigationId, from = ctx.route;
  const [section, rawId, revision, hash] = path.split('/');
  const route = Object.hasOwn(routes, section) ? section : 'home';
  let nextPath = route, taskId = null;
  const batchId = route === 'grading' && rawId && !['history','intake','materials','-'].includes(rawId) ? decodeURIComponent(rawId) : null;
  const frameRevision = Number(document.querySelector('.grading-frame')?.dataset.gradingRevision || 0);
  if (frameRevision > ctx.grading.revision || (batchId && !ctx.grading.tasks.some(task => task.id === batchId))) {
    acceptGrading(await api('/api/state?summary=1'));
    if (visit !== navigationId) return;
  }
  if (section === 'file' || section === 'thread') {
    const encoded = encodeURIComponent(decodeURIComponent(rawId || ''));
    let file = null, thread = null;
    if (section === 'file') {
      const query = new URLSearchParams();
      if (revision) query.set('revision', revision);
      if (hash) query.set('hash', hash);
      file = await api('/api/system/files/' + encoded + (query.size ? '?' + query : ''));
      if (visit !== navigationId) return;
      if (file.threadId) thread = await api('/api/system/threads/' + encodeURIComponent(file.threadId));
      nextPath = filePath(file.id, file.revision, file.hash);
    } else {
      thread = await api('/api/system/threads/' + encoded);
      nextPath = 'thread/' + encoded;
    }
    if (visit !== navigationId) return;
    activate(nextPath, file, thread);
    ctx.slide = 1;
    ctx.slideCount = file && /\.html$/i.test(file.title) ? new DOMParser().parseFromString(file.body, 'text/html').body.querySelectorAll(':scope > section').length : 0;
  } else if (route === 'home') activate('home');
  else if (batchId && ctx.grading.tasks.some(task => task.id === batchId)) {
    taskId = batchId; nextPath += '/' + encodeURIComponent(taskId);
  }
  const fileBatchId = route === 'files' && rawId === 'batch' && revision ? decodeURIComponent(revision) : null;
  if (fileBatchId !== ctx.fileBatchId) ctx.query = '';
  ctx.fileBatchId = fileBatchId;
  if (ctx.fileBatchId) nextPath = 'files/batch/' + encodeURIComponent(ctx.fileBatchId);
  ctx.gradingFile = null;
  if (route === 'grading' && ['document','artifact','group'].includes(revision) && hash) {
    const id = decodeURIComponent(hash);
    taskId = rawId === '-' ? null : decodeURIComponent(rawId);
    ctx.gradingFile = {key:revision, id};
    nextPath = ['grading', encodeURIComponent(taskId || '-'), revision, encodeURIComponent(id)].join('/');
  }
  ctx.gradingHistory = route === 'grading' && rawId === 'history' && !ctx.gradingFile;
  if (ctx.gradingHistory) { nextPath = 'grading/history'; taskId = null; }
  ctx.intakeView = route === 'grading' && ['intake', 'materials'].includes(rawId) ? rawId : null;
  if (ctx.intakeView) nextPath = 'grading/' + ctx.intakeView;
  ctx.route = route; ctx.taskId = taskId;
  if (location.hash !== '#' + nextPath) history[replace ? 'replaceState' : 'pushState'](null, '', '#' + nextPath);
  const animate = document.startViewTransition && from !== route && document.querySelector('#page') &&
    !matchMedia('(prefers-reduced-motion: reduce)').matches && document.documentElement.dataset.motion !== 'reduce';
  pageTransition?.skipTransition();
  if (animate) {
    const transition = document.startViewTransition(() => { if (visit === navigationId) render(); });
    pageTransition = transition;
    void transition.finished.finally(() => { if (pageTransition === transition) pageTransition = null; });
    await transition.updateCallbackDone;
  } else render();
  if (route === 'settings' && ctx.state.account?.user) {
    void api('/api/system/account/refresh', {}).then(updated => {
      if (visit !== navigationId) return;
      const changed = JSON.stringify(updated.account) !== JSON.stringify(ctx.state.account);
      ctx.state = updated;
      if (changed && !dialog.open && !document.activeElement.matches('input,select,textarea')) render();
    }).catch(()=>{});
  }
  if (from === 'grading' && route !== from) void refresh(true);
}
const openThread = id => navigate('thread/' + encodeURIComponent(id));
const openFile = (id, revision, hash) => navigate(filePath(id, revision, hash));
function showHistory() {
  const items = [...ctx.state.threads.map(thread => ({...thread, action:'thread', status:thread.lastMessage?.status})),
    ...ctx.grading.tasks.filter(task => task.kind && task.kind !== 'grade').map(task => ({...task,action:'grading'}))];
  const updated = item => item.updatedAt || item.completedAt || item.createdAt || '';
  items.sort((a,b) => updated(b).localeCompare(updated(a)));
  openDialog('工作记录', items.length ? `<div class="menu-list">${items.map(item =>
    button(item.action, `<span>${e(item.title)}</span><small>${[status(item.status), date(updated(item))].filter(Boolean).join(' · ')}</small>`, `data-id="${e(item.id)}"`)).join('')}</div>` : '<p class="muted">还没有工作记录。</p>');
}
function addReference(file) {
  if (ctx.refs.some(ref => ref.id === file.id && ref.revision === file.revision && ref.hash === file.hash)) return false;
  if (ctx.refs.length >= 8) throw Error('最多引用 8 个文件。');
  ctx.refs.push(refMeta(file)); persistDraft(); return true;
}
const referenceFolders = new Map();
function updateReferenceList() {
  const list = dialog.querySelector('#archive-reference-list'), input = dialog.querySelector('#archive-reference-search');
  if (list && input) {
    const guideRefs = (ctx.state.archiveInputs || []).filter(file => file.documentId && file.referenceable);
    list.innerHTML = referenceTree([...ctx.state.files, ...guideRefs], input.value, referenceFolders);
  }
}
function sources() {
  referenceFolders.clear();
  openDialog('引用工作区文件', `<label class="search-control">${glyph('search')}<input id="archive-reference-search" type="search" aria-label="查找引用文件" placeholder="搜索批次、学生或文件"></label><div class="archive-tree" id="archive-reference-list"></div>`, 'archive-dialog');
  updateReferenceList();
}
async function sourcePreview(node) {
  const file = ctx.state.archiveInputs?.find(file => file.id === node.dataset.id);
  if (!file) throw Error('原件已更新，请重新打开批次。');
  const body = await archiveSourceBody(file);
  openDialog(file.title, `<p class="archive-provenance">${e(file.documentId ? file.taskTitle : fileScope(file))}</p>${body}`, 'archive-source-dialog');
}
async function upload(files) {
  if (!files.length) return;
  const failures = [];
  let saved = 0, attached = 0;
  const attach = ctx.route === 'home' ? contextKey : null;
  for (const file of files) {
    try {
      if (file.size > 2 * 1024 * 1024) throw Error('超过文本文件的 2 MB 上限。');
      if (/\.(pdf|png|jpe?g|webp|tiff?|bmp)$/i.test(file.name)) throw Error('请在批改空间导入 PDF 或作答图片。');
      let body;
      try { body = new TextDecoder('utf-8', { fatal:true, ignoreBOM:true }).decode(await file.arrayBuffer()); }
      catch { throw Error('此文件无法读取为 UTF-8 文本。'); }
      const result = await api('/api/system/files', { title:file.name, body });
      ctx.state = result;
      saved++;
      if (attach && contextKey === attach && ctx.refs.length < 8 && addReference(result.file)) attached++;
    } catch (error) { failures.push({ name:file.name, reason:error.message }); }
  }
  closeDialog(); render();
  if (attached && attach === contextKey && ctx.route === 'home') focusComposer();
  const summary = `已导入 ${saved} 份${attach && saved ? `，本次附加 ${attached} 份引用` : ''}。${attach && attached < saved ? '其余文件已保存在文件库。' : ''}`;
  if (failures.length) {
    openDialog('导入结果', `<p>${summary}以下 ${failures.length} 份需要处理。</p><ul class="import-errors">${failures.map(file => `<li><strong>${e(file.name)}</strong><span>${e(file.reason)}</span></li>`).join('')}</ul>${button('grading', '打开批改材料导入', 'data-id="intake"', 'outline')}`);
  } else toast(summary);
}
function focusComposer() {
  document.querySelector('#task-input')?.focus();
}
const connectionApis = [
  ['openai-completions','OpenAI 兼容 · Chat Completions','https://api.openai.com/v1'],
  ['openai-responses','OpenAI · Responses','https://api.openai.com/v1'],
  ['anthropic-messages','Anthropic · Messages','https://api.anthropic.com'],
  ['google-generative-ai','Google · Gemini','https://generativelanguage.googleapis.com/v1beta'],
];
const connectionUrls = [
  ['OpenRouter','https://openrouter.ai/api/v1'],['OpenAI',connectionApis[0][2]],['Anthropic',connectionApis[2][2]],
  ['Google Gemini',connectionApis[3][2]],['DeepSeek','https://api.deepseek.com'],['Groq','https://api.groq.com/openai/v1'],['xAI','https://api.x.ai/v1']
];
async function showModelSuggestions(form) {
  const list = form.querySelector('#known-models');
  const baseUrl = form.elements.baseUrl.value;
  list.replaceChildren();
  if (!connectionUrls.some(([,url])=>url === baseUrl.replace(/\/+$/,''))) return;
  try {
    const rows = await api('/api/system/model-suggestions?baseUrl=' + encodeURIComponent(baseUrl));
    if (!form.isConnected || form.elements.baseUrl.value !== baseUrl) return;
    for (const {id,name} of rows) list.append(new Option(name,id));
  } catch { /* Any custom model ID can be entered directly. */ }
}
function manualModelEntry(form) {
  const menu = form.querySelector('[data-model-menu]'), input = form.elements.modelId;
  menu.hidden = true; menu.disabled = true; input.hidden = false; input.required = true;
  form.querySelector('[data-model-label]').htmlFor = input.id;
}
async function readConnectionModels(node) {
  const form = node.form, {api:protocol, baseUrl, apiKey, modelId:input} = form.elements;
  if (!baseUrl.reportValidity() || !apiKey.reportValidity()) return;
  const status = form.querySelector('[data-read-status]'), menu = form.querySelector('[data-model-menu]');
  const generation = Number(form.dataset.readGeneration || 0);
  const current = () => form.isConnected && dialog.open && generation === Number(form.dataset.readGeneration || 0);
  node.disabled = true; status.textContent = '正在读取…';
  try {
    const {models} = await api('/api/system/connections/discover', {id:form.dataset.connectionId, api:protocol.value, baseUrl:baseUrl.value, apiKey:apiKey.value});
    if (!current()) return;
    if (!models.length) { manualModelEntry(form); status.textContent = '服务商未列出可用模型，可以手动填写。'; return; }
    const placeholder = new Option('请选择模型', ''); placeholder.disabled = true;
    const manual = new Option('手动填写模型 ID…',''); manual.dataset.manual = '';
    const list = input.value && !models.includes(input.value) ? [input.value,...models] : models;
    menu.replaceChildren(placeholder, ...list.map(id=>new Option(id,id)), manual);
    if (input.value) menu.value = input.value; else menu.selectedIndex = 0;
    input.required = false; input.hidden = true; menu.disabled = false; menu.hidden = false;
    form.querySelector('[data-model-label]').htmlFor = menu.id;
    status.textContent = '已读取 ' + models.length + ' 个模型。'; menu.focus();
  } catch (error) {
    if (current()) { manualModelEntry(form); status.textContent = error.message; }
  } finally { if (current()) node.disabled = false; }
}
function editConnection(node) {
  const item = ctx.state.connections.find(row => row.id === node.dataset.id);
  openDialog(item ? '编辑模型连接' : '添加模型连接', `<form id="connection-form" data-connection-id="${e(item?.id || '')}" autocomplete="off">
    <label>API 协议<select name="api">${connectionApis.map(([id,name])=>`<option value="${id}" ${id===item?.api?'selected':''}>${name}</option>`).join('')}</select></label>
    <label>API 基础网址<input type="url" list="provider-urls" name="baseUrl" value="${e(item?.baseUrl || connectionApis[0][2])}" required spellcheck="false"></label>
    <datalist id="provider-urls">${connectionUrls.map(([name,url])=>`<option value="${url}">${name}</option>`).join('')}</datalist>
    <label>API Key<input type="password" name="apiKey" autocomplete="new-password" spellcheck="false" ${item ? 'placeholder="已保存，留空以保留"' : 'required'}></label>
    <div class="connection-model-field"><div class="connection-model-heading"><label data-model-label for="connection-model-id">模型</label>${button('read-connection-models','读取模型','','text-link')}</div>
      <input id="connection-model-id" list="known-models" name="modelId" value="${e(item?.modelId || '')}" placeholder="手动填写模型 ID" required spellcheck="false" maxlength="240">
      <select data-model-menu id="connection-model-list" required hidden disabled></select><datalist id="known-models"></datalist>
      <small data-read-status role="status" aria-live="polite"></small></div>
    <details class="connection-options"><summary>连接名称与预算</summary>
      <label>连接名称<input name="name" value="${e(item?.name || '')}" placeholder="默认使用网址域名" maxlength="100"></label>
      <p>每百万 token 的预算预留费率（美元）。留空采用 Pi 目录价格，未收录的模型按输入 5、输出 25 预留。</p>
      <label>输入<input name="inputRate" type="number" min="0" max="10000" step="any" value="${e(item?.inputRate)}"></label>
      <label>输出<input name="outputRate" type="number" min="0" max="10000" step="any" value="${e(item?.outputRate)}"></label>
    </details>
    <div class="form-footer"><span>${item ? button('remove-connection','移除连接','data-id="'+e(item.id)+'"') : ''}</span><button class="primary" type="submit">保存连接</button></div>
  </form>`);
  void showModelSuggestions(dialog.querySelector('#connection-form'));
}
async function accountAction(path, body = {}) {
  ctx.state = await api('/api/system/account/' + path, body);
  if (!ctx.state.modelCatalog.chatIds.includes(ctx.composerModelId)) ctx.composerModelId = undefined;
  closeDialog(); render();
}
function showCloudLogin(password = false) {
  const account = ctx.state.account, joining = e(account.origin + '/login#activate');
  const form = `<form id="cloud-login-form" class="auth-password-form">
    <label>教师登录名<input name="login" autocomplete="username" maxlength="120" required></label>
    <label>密码<input type="password" name="password" autocomplete="current-password" maxlength="200" required></label>
    <p data-form-error role="alert"></p><button class="primary" type="submit">登录</button></form>`;
  const options = `<div class="account-methods">${quickGoogleLink(account)}${passwordLoginButton()}</div>`;
  const footer = password ? button('cloud-login','返回登录方式','','auth-link')
    : `首次使用？ <a href="${joining}" target="_blank" rel="noopener noreferrer">使用学校邀请码激活</a>`;
  openDialog(password ? '账号密码登录' : '登录你的账号', (password ? form : options) + '<p class="auth-foot">' + footer + '</p>', 'auth-dialog');
  dialog.querySelector('header').insertAdjacentHTML('afterbegin','<div class="auth-wordmark"><span class="gradeos-wordmark">Grade<span>OS</span></span> <small>Cloud</small></div>');
  if (password) dialog.querySelector('[name=login]').focus();
}
const actions = {
  'cloud-login':()=>showCloudLogin(),
  'cloud-password':()=>showCloudLogin(true),
  'cloud-refresh':()=>accountAction('refresh'),
  'cloud-logout':()=>accountAction('logout'),
  'use-cloud':()=>accountAction('mode',{mode:'cloud'}),
  'use-local':()=>accountAction('mode',{mode:'local'}),
  'router-key':()=>openDialog('自带 OpenRouter 密钥', `<form id="router-key-form"><label>API Key<input name="apiKey" type="password" autocomplete="off" required spellcheck="false"></label>
    <p>密钥保存在本机，聊天和批改直接使用你的 OpenRouter 账户。</p><p data-form-error role="alert"></p>
    <div class="form-footer"><span>${ctx.state.account.hasSavedKey ? button('clear-router-key','移除已保存的密钥') : ''}</span><button class="primary" type="submit">保存密钥</button></div></form>`),
  'clear-router-key':()=>accountAction('openrouter',{apiKey:''}),
  'chat-models':()=>openDialog('选择聊天模型', `<form id="chat-models-form"><fieldset class="chat-model-list"><legend>在聊天菜单中显示</legend>
    ${recommendedChatIds.map(id=>`<label><input type="checkbox" name="model" value="${e(id)}" ${ctx.state.modelCatalog.chatIds.includes(id)?'checked':''}>${e(gradingModel(id).name)}</label>`).join('')}
    </fieldset><p data-form-error role="alert"></p><div class="form-footer"><span></span><button class="primary" type="submit">保存选择</button></div></form>`),
  'edit-connection':editConnection,
  'read-connection-models':readConnectionModels,
  'default-connection':async node => { ctx.state = await api('/api/system/default-model',{id:node.dataset.id},'PATCH'); render(); toast('已更新默认模型。'); },
  'remove-connection':node => openDialog('移除模型连接',`<p>今后使用此连接的批改草稿需要重新选择模型。</p><div class="form-footer">${button('close-dialog','取消')}${button('confirm-remove-connection','移除连接','data-id="'+e(node.dataset.id)+'"','primary')}</div>`),
  'confirm-remove-connection':async node => { ctx.state = await api('/api/system/connections/'+encodeURIComponent(node.dataset.id),{},'DELETE'); closeDialog(); render(); toast('模型连接已移除。'); },
  new: async () => { await navigate('home'); focusComposer(); },
  resume: () => navigate(ctx.resume),
  'close-dialog': closeDialog,
  'open-navigation': () => {
    if (!narrowSidebar.matches) return setSidebarCollapsed(false);
    const drawer = app.querySelector('#navigation-drawer');
    drawer.showModal();
    syncSidebar();
    (drawer.querySelector('[aria-current="page"]') || drawer.querySelector('.work-nav a')).focus({preventScroll:true});
  },
  'close-navigation': () => narrowSidebar.matches ? closeNavigation() : setSidebarCollapsed(true),
  account: () => { closeNavigation(); openDialog(ctx.state.account?.user?.name || ctx.state.preferences.displayName, `<div class="menu-list">${ctx.state.account?.user ? '' : button('cloud-login','登录 GradeOS Cloud')}${button('settings', '账号与设置')}${button('history', '工作记录')}${button('help', '关于 GradeOS')}</div>`); },
  settings: () => { closeDialog(); navigate('settings'); }, workspace: () => { closeDialog(); navigate('settings'); },
  help: () => openDialog('GradeOS', '<p>本地工作区，连接你的模型服务。文件、对话和任务保存在本机。</p><p>教师助手可以引用批改报告，继续准备教案、讲义或课堂练习。</p><p>代码采用 GPL-3.0-only。第三方依赖保留各自许可证。</p>'),
  history: showHistory,
  'retry-instruction': node => {
    const messages = ctx.thread?.messages || [], previous = messages.at(-2);
    if (messages.at(-1)?.id !== node.dataset.id || previous?.role !== 'user') return;
    return submitInstruction(previous.text, previous.references || [], previous.skillId, previous.modelId);
  },
  thread: async node => { closeDialog(); await openThread(node.dataset.id); },
  grading: node => { closeDialog(); navigate('grading' + (node.dataset.id ? '/' + node.dataset.id : '')); },
  add: () => openDialog('添加到任务', `<div class="menu-list">${button('upload', '导入本地文件')}${button('sources', '引用工作区文件')}${button('choose-skill', '选择 Skill')}${button('history', '工作记录')}</div>`, 'compact-dialog'),
  sources,
  upload: () => document.querySelector('#system-upload').click(),
  reference: node => {
    const file = ctx.state.files.find(file => file.id === node.dataset.id);
    const guide = !file && ctx.state.archiveInputs?.find(input => input.id === node.dataset.id && input.referenceable);
    if (!file && !guide) throw Error('引用已更新，请重新查找文件。');
    addReference(file || {...guide, id:'document:' + guide.documentId});
    closeDialog(); render();
  },
  'remove-ref': node => { ctx.refs.splice(Number(node.dataset.index), 1); persistDraft(); render(); },
  'choose-skill': () => openDialog('选择 Skill', `<div class="menu-list">${ctx.state.skills.filter(skill => skill.enabled).map(skill => button('select-skill', `<span>${e(skill.name)}</span><small>${e(skill.description)}</small>`, `data-id="${e(skill.id)}"`)).join('') || '<p>可在 Skills 中启用能力。</p>'}</div>`),
  'select-skill': node => { ctx.skillId = node.dataset.id; closeDialog(); persistDraft(); render(); },
  'clear-skill': () => { ctx.skillId = null; persistDraft(); render(); },
  file: async node => { closeDialog(); await openFile(node.dataset.id, node.dataset.revision, node.dataset.hash); },
  continue: async node => { const file = ctx.state.files.find(file => file.id === node.dataset.id); await navigate('home'); addReference(file); render(); focusComposer(); },
  'archive-toggle': node => {
    const folders = ctx.query.trim() ? ctx.archiveSearchFolders : ctx.archiveFolders;
    folders.set(node.dataset.id, node.getAttribute('aria-expanded') !== 'true');
    render();
  },
  'reference-folder': node => {
    referenceFolders.set(node.dataset.id, node.getAttribute('aria-expanded') !== 'true');
    updateReferenceList();
    [...dialog.querySelectorAll('[data-action="reference-folder"]')].find(button => button.dataset.id === node.dataset.id)?.focus({preventScroll:true});
  },
  'archive-source': sourcePreview,
  'archive-guide-document': node => {
    closeDialog();
    return navigate(['grading', encodeURIComponent(node.dataset.task || '-'), 'document', encodeURIComponent(node.dataset.id)].join('/'));
  },
  'file-filter': node => { ctx.filter = node.dataset.filter; render(); },
  'toggle-skill': async node => { const skill = ctx.state.skills.find(skill => skill.id === node.dataset.id); ctx.state = await api(`/api/system/skills/${skill.id}`, { enabled: !skill.enabled }, 'PATCH'); render(); },
  'import-skill': () => document.querySelector('#skill-upload').click(),
  cancel: async () => { await api('/api/system/cancel', {}); toast('已请求停止，正在保存当前状态…'); await refresh(true); },
  info: () => { const file = ctx.file, latest = ctx.state.files.find(row => row.id === file.id), stale = latest && (latest.revision !== file.revision || latest.hash !== file.hash); openDialog('文件信息', `<dl class="file-info"><dt>名称</dt><dd>${e(file.title)}</dd><dt>当前版本</dt><dd>v${file.revision}${stale ? ' · 已有新版本' : ''}</dd><dt>状态</dt><dd>${status(file.status)}</dd><dt>来源</dt><dd>${e(fileScope(file))}</dd>${file.relativePath ? `<dt>本地文件</dt><dd>${e(ctx.state.directory + '/' + file.relativePath)}</dd>` : ''}<dt>更新时间</dt><dd>${date(file.updatedAt)}</dd></dl>${stale ? button('file', '打开最新版本', `data-id="${e(file.id)}"`, 'outline') : ''}${(file.origin !== 'grading' || file.id.startsWith('document:')) && (latest?.versionCount || file.versionCount) > 1 ? `<h3>文件版本</h3><div class="version-list">${Array.from({length:latest?.versionCount || file.versionCount},(_,i)=>button('file', `v${i+1}`, `data-id="${e(file.id)}" data-revision="${i+1}"`, 'outline')).join('')}</div>` : ''}<h3>引用来源</h3>${file.sources?.length ? `<div class="menu-list">${file.sources.map(ref => `${button('file', `${e(ref.title)} · v${ref.revision}`, `data-id="${e(ref.id)}" data-revision="${ref.revision}" data-hash="${e(ref.hash)}"`)}`).join('')}</div>` : '<p class="muted">没有附加来源。</p>'}`); },
  edit: () => { if (ctx.file.origin === 'grading') { toast('请在批改工作区编辑或复核原始结果。'); return; } openDialog('编辑文件', `<form id="file-editor"><label>文件名<input name="title" value="${e(ctx.file.title)}" maxlength="120" required></label><label class="sr-only" for="file-body">文件内容</label><textarea id="file-body" name="body" spellcheck="false">${e(ctx.file.body)}</textarea><div class="form-footer"><span>保存为新版本</span><button type="submit" class="primary">保存</button></div></form>`, 'editor-dialog'); },
  process: () => { const messages = ctx.thread?.messages || []; openDialog('处理过程', messages.length ? messages.map(message => `<article class="process-message"><h3>${message.role === 'user' ? '你的要求' : 'GradeOS'}</h3><div class="prose">${markdown(message.text)}</div>${message.events?.filter(event => event.type === 'tool_execution_end').map(event => `<p class="muted">${e(event.label)} · ${event.status === 'error' ? '未完成' : '完成'}</p>`).join('') || ''}</article>`).join('') : `<p>来源：${ctx.file?.origin === 'grading' ? '批改工作区' : '本地导入'}</p>${ctx.file?.origin === 'grading' ? button('grading', '打开批改', ctx.file.taskId ? `data-id="${e(ctx.file.taskId)}"` : '', 'outline') : ''}`); },
  'previous-slide': () => { ctx.slide = Math.max(1, ctx.slide - 1); render(); }, 'next-slide': () => { ctx.slide = Math.min(ctx.slideCount, ctx.slide + 1); render(); },
};
document.addEventListener('click', async event => {
  if (event.target.closest('[data-quick-google]')) {
    waitingForGoogle = true;
    setTimeout(() => { closeDialog(); toast('请在系统浏览器中完成登录。'); }, 0);
    return;
  }
  const summary = event.target.closest('.execution-log summary');
  if (summary) expandedSteps.set(summary.closest('[data-message]').dataset.message, !summary.parentElement.open);
  const node = event.target.closest('[data-action]'); if (!node || !actions[node.dataset.action]) return;
  try { await actions[node.dataset.action](node); } catch (error) { toast(error.message); }
});
document.addEventListener('click', event => {
  if (event.target.closest('.skip-link')) {
    event.preventDefault(); document.querySelector('#main')?.focus(); return;
  }
  const anchor = event.target.closest('.prose a[href^="#"]');
  if (anchor) {
    event.preventDefault();
    let id = anchor.hash.slice(1); try { id = decodeURIComponent(id); } catch {}
    if (id) anchor.closest('.prose')?.querySelector('#' + CSS.escape(id))?.scrollIntoView({block:'start'});
    return;
  }
  const link = event.target.closest('a[data-route]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  navigate(link.dataset.route).catch(error => toast(error.message));
});
document.addEventListener('compositionstart', () => { composing = true; });
document.addEventListener('compositionend', event => {
  composing = false;
  if (event.target.id === 'archive-reference-search') { referenceFolders.clear(); updateReferenceList(); }
  if (event.target.id === 'file-search') { ctx.archiveSearchFolders.clear(); ctx.query = event.target.value; queueMicrotask(render); }
});
window.addEventListener('storage', event => {
  if (event.key === composerModelKey) { ctx.composerModelId = undefined; render(); }
});
document.addEventListener('change', event => {
  if (event.target.matches('[data-model-menu]')) {
    const form = event.target.form;
    if (event.target.selectedOptions[0]?.hasAttribute('data-manual')) { manualModelEntry(form); form.elements.modelId.focus(); }
    else form.elements.modelId.value = event.target.value;
  }
  if (event.target.form?.id === 'connection-form' && event.target.name === 'api') {
    const form = event.target.form, field = form.elements.baseUrl;
    if (connectionApis.some(row=>row[2]===field.value)) field.value = connectionApis.find(row=>row[0]===event.target.value)[2];
    void showModelSuggestions(form);
  }
  if (event.target.form?.id === 'connection-form' && event.target.name === 'baseUrl') {
    const form = event.target.form, url = event.target.value.replace(/\/+$/,'');
    const builtin = connectionApis.find(row=>row[2] === url);
    if (url !== connectionApis[0][2] && connectionUrls.some(row=>row[1]===url)) {
      form.elements.api.value = builtin?.[0] ?? (url === 'https://api.x.ai/v1' ? 'openai-responses' : 'openai-completions');
    }
    void showModelSuggestions(form);
  }
  if (event.target.id === 'composer-model') {
    ctx.composerModelId = event.target.value; setComposerModel(ctx.composerModelId); render();
  }
});
document.addEventListener('input', event => {
  if (event.target.form?.id === 'connection-form' && ['baseUrl','apiKey','api'].includes(event.target.name)) {
    const form = event.target.form;
    form.dataset.readGeneration = String(Number(form.dataset.readGeneration || 0) + 1);
    manualModelEntry(form); form.querySelector('[data-read-status]').textContent = '';
    form.querySelector('[data-action="read-connection-models"]').disabled = false;
  }
  if (event.target.id === 'archive-reference-search' && !event.isComposing) { referenceFolders.clear(); updateReferenceList(); }
  if (event.target.id === 'task-input') { ctx.draft = event.target.value; const send = document.querySelector('.send'); if (send && !ctx.state.active) send.disabled = !ctx.draft.trim(); clearTimeout(draftTimer); draftTimer = setTimeout(persistDraft, 200); }
  if (event.target.id === 'file-search') { ctx.archiveSearchFolders.clear(); ctx.query = event.target.value; if (!event.isComposing) render(); }
});
document.addEventListener('keydown', event => { if (event.target.id === 'task-input' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!ctx.sending && ctx.draft.trim() && !ctx.state.active) event.target.form.requestSubmit(); } });
async function submitInstruction(goal, references, skillId, modelId, clearDraft = false) {
  if (!goal.trim() || ctx.sending || ctx.state.active) return;
  if (!ctx.state.connection.ready) {
    openDialog('选择模型连接', `<p>${ctx.state.account?.user && ctx.state.account.mode === 'cloud' ? '请在账号与设置中查看 Cloud 额度，或切换到自带 API。' : '登录 GradeOS Cloud 使用账号额度，或在设置中填写自己的 API 密钥。'}</p>
      ${ctx.state.account?.user ? '' : button('cloud-login','登录 GradeOS Cloud','','primary')} ${button('settings', '账号与设置')}`);
    return;
  }
  const submittedKey = contextKey, visit = navigationId;
  ctx.sending = true; render();
  try {
    const result = await api('/api/system/chat', {modelId:modelId || undefined, goal, threadId:ctx.threadId, references, skillId});
    ctx.state = result;
    const destination = 'thread/' + encodeURIComponent(result.threadId);
    if (destination !== submittedKey && !drafts.has(destination)) drafts.set(destination, {draft:'',refs:references,skillId});
    if (clearDraft) {
      if (contextKey === submittedKey && ctx.draft === goal) { ctx.draft = ''; persistDraft(); }
      else if (drafts.get(submittedKey)?.draft === goal) { drafts.get(submittedKey).draft = ''; persistDraft(); }
    }
    if (visit === navigationId) {
      await openThread(result.threadId);
      const journal = document.querySelector('#messages');
      if (journal && contextKey === destination) journal.scrollTop = journal.scrollHeight;
    }
  } finally { ctx.sending = false; render(); }
}
document.addEventListener('submit', async event => {
  event.preventDefault(); const form = event.target, body = Object.fromEntries(new FormData(form));
  try {
    if (['cloud-login-form','router-key-form','chat-models-form'].includes(form.id)) {
      const submit = form.querySelector('[type=submit]'), errorBox = form.querySelector('[data-form-error]');
      submit.disabled = true; errorBox.textContent = '';
      try {
        if (form.id === 'cloud-login-form') await accountAction('login', body);
        else if (form.id === 'router-key-form') await accountAction('openrouter',{apiKey:body.apiKey.trim()});
        else await accountAction('models',{ids:new FormData(form).getAll('model')});
      } catch (error) { errorBox.textContent = error.message; }
      finally { submit.disabled = false; }
    } else if (form.id === 'connection-form') {
      const submit = form.querySelector('[type=submit]'); submit.disabled = true;
      try { ctx.state = await api('/api/system/connections',{...body,id:form.dataset.connectionId}); form.reset(); closeDialog(); render(); toast('模型连接已保存。'); }
      finally { submit.disabled = false; }
    }
    else if (form.id === 'preferences-form') { ctx.state = await api('/api/system/preferences', body, 'PATCH'); syncMotion(); render(); toast('设置已保存。'); }
    else if (form.id === 'file-editor') {
      const { id, revision } = ctx.file, visit = navigationId;
      await api('/api/system/files', { ...body, id, revision }); closeDialog(); await state(false);
      if (visit === navigationId) await openFile(id);
      toast('新版本已保存。');
    }
    else if (form.id === 'task-composer') await submitInstruction(ctx.draft, [...ctx.refs], ctx.skillId, body.modelId, true);
  } catch (error) { toast(error.message); }
});
document.querySelector('#system-upload').addEventListener('change', async event => { try { await upload([...event.target.files]); } catch (error) { toast(error.message); } finally { event.target.value = ''; } });
document.querySelector('#skill-upload').addEventListener('change', async event => { try { const file = event.target.files[0]; if (!file) return; if (file.size > 80000) throw Error('SKILL.md 文件过大。'); const instructions = await file.text(); openDialog('导入 Skill', `<form id="skill-import-form"><label>名称<input name="name" value="${e(file.name.replace(/\.md$/i, ''))}" maxlength="60" required></label><p>导入后默认关闭，可在 Skills 中启用。</p><details><summary>查看任务指南</summary><pre>${e(instructions)}</pre></details><button type="submit" class="primary">导入</button></form>`); dialog.querySelector('form').addEventListener('submit', async event => { event.preventDefault(); try { ctx.state = await api('/api/system/skills', { name: new FormData(event.target).get('name'), instructions }); closeDialog(); render(); } catch (error) { toast(error.message); } }); } catch (error) { toast(error.message); } finally { event.target.value = ''; } });
document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files') && ctx.route !== 'grading') { event.preventDefault(); document.body.classList.add('dragging'); } });
document.addEventListener('dragleave', event => { if (!event.relatedTarget) document.body.classList.remove('dragging'); });
document.addEventListener('drop', async event => { document.body.classList.remove('dragging'); if (!event.dataTransfer.files.length || ctx.route === 'grading') return; event.preventDefault(); try { await upload([...event.dataTransfer.files]); } catch (error) { toast(error.message); } });
async function followLocation() {
  try { await navigate(location.hash.slice(1) || 'home', {replace:true}); }
  catch (error) { await navigate('home', {replace:true}); toast(error.message); }
}
window.addEventListener('hashchange', followLocation);
async function refresh(force = false) {
  if (pollBusy) return; pollBusy = true;
  try {
    const gradingIndex = ctx.route === 'grading' && !ctx.taskId && !ctx.intakeView && !ctx.gradingFile;
    if (ctx.route === 'grading' && !gradingIndex && !force) {
      const frameRevision = Number(document.querySelector('.grading-frame')?.dataset.gradingRevision || 0);
      if (frameRevision <= ctx.grading.revision) return;
    }
    const visit = navigationId;
    await state(gradingIndex || ctx.route === 'home' || force);
    if (visit !== navigationId) return;
    if (waitingForGoogle && ctx.state.account?.user) {
      waitingForGoogle = false;
      ctx.composerModelId = undefined;
      render(); toast('已登录 GradeOS Cloud。');
      return;
    }
    const signature = JSON.stringify([ctx.state.revision, ctx.state.gradingRevision ?? ctx.grading.revision, ctx.state.active, ctx.state.modelCatalog, ctx.state.account]);
    if (signature === lastSignature && !force) return; lastSignature = signature;
    if (ctx.route === 'home' && ctx.threadId) {
      const thread = await api(`/api/system/threads/${encodeURIComponent(ctx.threadId)}`);
      if (visit !== navigationId) return;
      ctx.thread = thread;
    }
    if (ctx.file && ctx.route === 'home') {
      updateAssistant(document.querySelector('#page'), composer(ctx));
      const label = document.querySelector('.artifact-status>span');
      if (label) label.textContent = ctx.state.active?.threadId === ctx.threadId ? '正在处理…' : ctx.file.origin === 'grading' ? status(ctx.file.status) : '文件已保存';
    }
    else if (!(ctx.route === 'settings' && document.querySelector('#preferences-form')?.contains(document.activeElement))) render();
  } catch (error) { if (force) toast(error.message); }
  finally { pollBusy = false; }
}
try {
  await state();
  window.addEventListener('focus', () => { if (waitingForGoogle) void refresh(true); });
  restoreDrafts();
  await followLocation(); setInterval(() => { if (!document.hidden) void refresh(); }, 1500);
  window.addEventListener('pagehide', persistDraft);
  window.addEventListener('pageshow', event => { if (event.persisted && ctx.route !== 'grading') void refresh(true); });
} catch (error) { app.innerHTML = `<section class="boot"><h1>无法打开工作区</h1><p>${e(error.message)}</p><a href="/">重新连接</a></section>`; }
