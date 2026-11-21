import { archiveLabels, archiveOwners, omitFiledGuides } from './grading-library.mjs';
import { escape as e, markdown, statuses, composerModelSelect, savedComposerModel } from './ui.mjs';
import { gradingModel, recommendedChatIds } from './grading-models.mjs';
export { e, markdown };
export const glyph = name => {
  const paths = {
    overview: '<rect x="3" y="3" width="7" height="7" rx="1.3"/><rect x="14" y="3" width="7" height="7" rx="1.3"/><rect x="3" y="14" width="7" height="7" rx="1.3"/><rect x="14" y="14" width="7" height="7" rx="1.3"/>',
    layers: '<path d="m3 8 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 18l9 5 9-5"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M7.5 3v4m9-4v4m-13 3h17"/>',
    forward: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    chat: '<path d="M20 12a7 7 0 0 1-7 7H8l-5 3 1.4-5A8 8 0 1 1 20 12Z"/>',
    history: '<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6m3-4v6l4 2"/>',
    settings: '<path d="M4 6h7m5 0h4M4 12h3m5 0h8M4 18h9m5 0h2"/><circle cx="13.5" cy="6" r="2.5"/><circle cx="9.5" cy="12" r="2.5"/><circle cx="15.5" cy="18" r="2.5"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
    file: '<path d="M6 3h8l5 5v13H6zM14 3v6h5M9 13h7m-7 4h5"/>',
    teaching: '<path d="M3 5c4-1 6 0 9 2 3-2 5-3 9-2v13c-4-1-6 0-9 2-3-2-5-3-9-2V5Zm9 2v13"/>',
    slides: '<rect x="3" y="4" width="18" height="13" rx="1"/><path d="M12 17v4m-4 0h8m-6-13 5 3-5 3z"/>',
    tables: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M10 10v10"/>',
    code: '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-14-3 18"/>',
    'panel-close':'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16m7-11-3 3 3 3"/>',
    'panel-open':'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16m4-11 3 3-3 3"/>',
    home: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
    grading: '<path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10l-7-7Z"/><path d="M13 3v7h7M8 15l2 2 4-4"/>',
    skills: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><path d="M17.5 3v7M14 6.5h7"/>',
    tasks: '<path d="m3 7 2 2 3-4m-5 12 2 2 3-4m3-8h10m-10 10h10"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', arrow: '<path d="M12 19V5m-6 6 6-6 6 6"/>', down: '<path d="m7 10 5 5 5-5"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>', folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3Z"/>', menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>', left: '<path d="m14 6-6 6 6 6"/>', right: '<path d="m10 6 6 6-6 6"/>' };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.plus}</svg>`;
};
export const button = (action, label, attrs = '', className = '') => `<button type="button" data-action="${action}" class="${className}" ${attrs}>${label}</button>`;
export const quickGoogleLink = account => account?.googleLaunch
  ? `<a class="quick-google" href="/auth/google/start/${e(account.googleLaunch)}" target="_blank" rel="noopener noreferrer" data-quick-google><span class="provider-icon"><img alt="" width="18" height="18" src="/assets/brand/google-g.png"></span><span>使用 Google 账号登录</span></a>` : '';
export const passwordLoginButton = () => button('cloud-password',
  '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 3.5a5.5 5.5 0 0 0-5.1 7.5L3 17.4V21h3.5v-2.3h2.3v-2.3h2l2.4-2.4a5.5 5.5 0 1 0 1.3-10.5Z"/><circle cx="16" cy="7.7" r=".9"/></svg><span>使用账号密码登录</span>', '', 'auth-password');
export const date = value => value ? new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
export const status = value => statuses[value] || ({ confirmed: '已确认', draft: '草稿' }[value]) || '已保存';
export const fileUrl = file => `/api/system/files/${encodeURIComponent(file.id)}?revision=${file.revision}&hash=${encodeURIComponent(file.hash)}`;
export const refMeta = file => ({ id: file.id, title: file.title, revision: file.revision, hash: file.hash });
export const routes = { home: '教师助手', grading: '批改', files: '文件', skills: '技能库', settings: '账号设置' };
const wordmark = '<span class="gradeos-wordmark">Grade<span>OS</span></span>';
const unreadDot = '<span class="unread-dot"><span class="sr-only">未读</span></span>';
function navLink(route, label, icon = '', unread = false) {
  return `<a href="#${e(route)}" data-route="${e(route)}">${icon ? glyph(icon) : ''}<span class="nav-label">${e(label)}</span>${unread ? unreadDot : ''}</a>`;
}
export function sidebarRecent(results = [], isRead = () => false) {
  if (!results.length) return '';
  return `<h2>最近批次</h2>${results.slice(0, 3).map(batch =>
    navLink('grading/' + encodeURIComponent(batch.id), batch.title || '未命名批次', '', !isRead(batch.id))).join('')}`;
}
export function shell(state, route) {
  const { displayName } = state.preferences;
  return `<workspace-field aria-hidden="true" data-scene="${e(route)}"></workspace-field>
  <aside class="workspace-sidebar" id="workspace-sidebar" aria-label="工作区侧栏">
    <div class="sidebar-heading">
      <a href="#home" data-route="home" class="wordmark" aria-label="GradeOS 教师助手">${wordmark}</a>
      ${button('close-navigation', glyph('panel-close'), 'aria-label="收起侧栏" title="收起侧栏"', 'nav-dismiss')}
    </div>
    <nav class="work-nav" aria-label="主导航">
      ${navLink('home','教师助手','teaching')}
      <details class="grading-nav" open><summary>${glyph('grading')}<span>批改</span>${glyph('down')}</summary>
        <div class="nav-subpages" role="group" aria-label="批改">${navLink('grading','批改概览')}${navLink('grading/intake','开始批改')}${navLink('grading/history','批改历史')}
          <div class="nav-recents"></div>
        </div></details>
      ${navLink('files','文件','folder')}${navLink('skills','技能库','skills')}
    </nav>
    ${button('account', `<span class="avatar">${e(Array.from(displayName)[0] || '')}</span><span class="account-name">${e(displayName)}</span>${glyph('settings')}`, `aria-haspopup="dialog" aria-label="${e(displayName)}，账号与设置" title="账号与设置"`, 'account')}
  </aside>
  <dialog id="navigation-drawer" aria-label="工作区导航"></dialog>
  <main id="main" tabindex="-1"><header class="mobile-masthead">
    ${button('open-navigation', glyph('panel-open'), 'aria-label="展开侧栏" title="展开侧栏" aria-controls="workspace-sidebar" aria-expanded="false"', 'nav-trigger')}
    <a href="#home" data-route="home" class="wordmark" aria-label="GradeOS 教师助手">${wordmark}</a>
  </header><div id="page"></div></main>`;
}
export function composer(ctx) {
  const busy = Boolean(ctx.state.active && ctx.state.active.threadId === ctx.threadId);
  const references = `<div id="reference-chips" class="reference-chips">${ctx.refs.map((ref, index) => button('remove-ref', `${e(ref.title)} <span>v${ref.revision}</span>${glyph('close')}`, `data-index="${index}" aria-label="移除引用 ${e(ref.title)}"`, 'source-chip')).join('')}${ctx.skillId ? button('clear-skill', e(ctx.state.skills.find(skill => skill.id === ctx.skillId)?.name || ''), '', 'source-chip') : ''}</div>`;
  return `<form id="task-composer" class="task-composer">${ctx.file ? '' : references}
    <textarea id="task-input" name="goal" aria-label="任务要求" placeholder="${ctx.file ? '继续调整这份文件…' : ctx.thread ? '继续补充要求…' : '写下教学任务，或拖入参考文件…'}" rows="2" maxlength="8000">${e(ctx.draft)}</textarea>
    <div class="composer-tools"><div>${button('add', glyph('plus'), 'aria-label="添加文件或 Skill" aria-haspopup="dialog"', 'icon-button')}${ctx.file ? references : button('sources', `${glyph('folder')}<span>引用文件</span>`, 'aria-label="引用工作区文件"', 'scope')}</div>
      <div class="composer-submit">${composerModelSelect(ctx.state, ctx.composerModelId ?? savedComposerModel(ctx.state.modelCatalog))}<button type="${busy ? 'button' : 'submit'}" ${busy ? 'data-action="cancel"' : ''} class="send" aria-label="${busy ? '停止任务' : '发送任务'}" ${(!busy && (!ctx.draft.trim() || ctx.state.active)) || ctx.sending ? 'disabled' : ''}>${glyph(busy ? 'stop' : 'arrow')}</button></div></div></form>`;
}
export function home(ctx) {
  if (ctx.file) return artifact(ctx);
  const active = ctx.state.active;
  const historyButton = button('history', glyph('history') + '<span>工作记录</span>', 'aria-label="工作记录"', 'workflow-action');
  if (!ctx.thread) {
    const resume = active ? button('thread', '返回进行中的任务 ' + glyph('right'), `data-id="${e(active.threadId)}"`, 'workflow-action')
      : ctx.resume ? button('resume', ctx.resume.startsWith('file/') ? '返回上次文件' : '继续上次任务', '', 'workflow-action') : '';
    return `<section class="dashboard assistant-start"><div class="assistant-landing">
      <h1>教师助手</h1>${composer(ctx)}
      <div class="assistant-links">${historyButton}${resume}</div></div></section>`;
  }
  const messages = ctx.thread.messages;
  return `<section class="conversation workflow"><header class="workflow-header"><h1>教师助手</h1><div>${historyButton}${button('new',glyph('plus')+'<span>新任务</span>','aria-label="新任务"','workflow-action')}</div></header>
    <div class="messages" id="messages" role="region" aria-label="任务执行记录" tabindex="0"><div class="workflow-journal">${messages.map((message,index) =>
      messageView(message.id === active?.id ? {...message,...active} : message, ctx, index === messages.length - 1)).join('')}</div></div>
    <div class="conversation-composer">${composer(ctx)}</div></section>`;
}
function emptyState(icon, title, detail, action = '') {
  return `<div class="empty-state"><div class="empty-icon">${glyph(icon)}</div><h2>${title}</h2><p>${detail}</p>${action}</div>`;
}
function executionLog(message) {
  const rows = [], calls = new Map();
  for (const event of message.events || []) {
    if (event.type === 'progress_note') { rows.push({note:event.text}); continue; }
    if (!['tool_execution_start','tool_execution_end'].includes(event.type)) continue;
    const previous = event.key && calls.get(event.key);
    if (previous) Object.assign(previous,event);
    else { const step = {...event}; rows.push(step); if (event.key) calls.set(event.key,step); }
  }
  const live = message.status === 'running';
  const last = rows.at(-1);
  const label = live ? (last?.status === 'running' ? last.label : '正在处理')
    : ({completed:'已完成', failed:'执行失败', cancelled:'已停止', interrupted:'执行已中断'}[message.status] || '执行记录');
  const elapsed = Date.parse(message.completedAt) - Date.parse(message.startedAt);
  const seconds = Math.round(elapsed / 1000);
  const duration = seconds >= 1 ? (seconds >= 60 ? `${Math.floor(seconds/60)} 分 ${seconds%60} 秒` : `${seconds} 秒`) : '';
  const actions = rows.filter(row => !row.note).length;
  const meta = [duration, actions ? actions + ' 项操作' : ''].filter(Boolean).join(' · ');
  const caption = `<span class="execution-mark${live ? ' is-live' : ''}" aria-hidden="true"></span><span>${e(label)}</span>${meta ? `<small>${e(meta)}</small>` : ''}`;
  if (!rows.length) return `<div class="execution-status">${caption}</div>`;
  return `<details class="execution-log" ${live ? 'open' : ''}><summary>${caption}${glyph('down')}</summary>
    <ol>${rows.map(row => row.note ? `<li class="execution-note prose">${markdown(row.note)}</li>`
      : `<li>${glyph(({list_files:'folder',read_file:'file',save_file:'file'})[row.tool] || 'tasks')}<span>${e(row.label || '处理当前步骤')}</span><small>${row.status === 'error' ? '失败' : row.status === 'done' ? '完成' : live ? '进行中' : '未完成'}</small></li>`).join('')}</ol></details>`;
}
function fileLinks(files, className) {
  if (!files?.length) return '';
  return `<div class="${className}">${files.map(file => {
    const route = ['file', encodeURIComponent(file.id), file.revision, file.hash].filter(Boolean).join('/');
    return `<a class="workflow-file" href="#${e(route)}" data-route="${e(route)}">${glyph('file')}<span>${e(file.title)}</span>${glyph('right')}</a>`;
  }).join('')}</div>`;
}
export function messageView(message, ctx, last = false) {
  if (message.role === 'user') return `<article class="workflow-instruction" data-message="${e(message.id)}">
    <p class="instruction-meta">你的要求${message.createdAt ? `<time datetime="${e(message.createdAt)}">${e(date(message.createdAt))}</time>` : ''}</p>
    <div class="instruction-body">${e(message.text)}</div>${fileLinks(message.references, 'instruction-files')}</article>`;
  const files = message.outputs || (message.fileIds || []).map(id => ctx.state.files.find(file => file.id === id)).filter(Boolean);
  const retry = last && !ctx.state.active && ['failed','cancelled','interrupted'].includes(message.status);
  return `<article class="workflow-result" data-message="${e(message.id)}">${executionLog(message)}
    ${message.text ? `<div class="workflow-answer prose">${markdown(message.text)}</div>` : ''}${fileLinks(files, 'workflow-outputs')}
    ${retry ? button('retry-instruction', '重试此任务', `data-id="${e(message.id)}"`, 'workflow-action') : ''}</article>`;
}
function gradingFileLink(file) {
  const task = encodeURIComponent(file.taskId || '-');
  let key, id, label;
  if (file.id.startsWith('document:')) { key = 'document'; id = file.id.slice(9); label = '打开当前文档'; }
  else if (file.id.startsWith('artifact:') && file.taskId) { key = 'artifact'; id = file.id.slice(('artifact:' + file.taskId + ':').length); label = '打开报告'; }
  else if (file.id.startsWith('result:') && file.groupId) { key = 'group'; id = file.groupId; label = '复核答卷'; }
  else return '';
  const route = 'grading/' + task + '/' + key + '/' + encodeURIComponent(id);
  return `<a class="button" href="#${e(route)}" data-route="${e(route)}">${label}</a>`;
}
export function artifact(ctx) {
  const file = ctx.file, ext = file.title.match(/\.([^.]+)$/)?.[1].toLowerCase();
  return `<section class="artifact"><header class="page-header"><h1>${e(file.title)}</h1><div>${button('info', '文件信息')}${file.origin === 'grading' ? gradingFileLink(file) : button('edit', '编辑')}<a class="button" href="${fileUrl(file)}&download=1">导出</a></div></header>
    <div class="artifact-scroll">${ext === 'html' ? `<iframe class="artifact-preview" title="${e(file.title)} 预览" sandbox src="${fileUrl(file)}&preview=1${ctx.slideCount > 1 ? `&slide=${ctx.slide}` : ''}"></iframe>${ctx.slideCount > 1 ? `<div class="pagination">${button('previous-slide', glyph('left'), `aria-label="上一页" ${ctx.slide <= 1 ? 'disabled' : ''}`)}<span>${ctx.slide} / ${ctx.slideCount}</span>${button('next-slide', glyph('right'), `aria-label="下一页" ${ctx.slide >= ctx.slideCount ? 'disabled' : ''}`)}</div>` : ''}` : `<article class="document-paper prose">${file.origin === 'grading' || ['md', 'txt'].includes(ext) ? markdown(file.body) : `<pre><code>${e(file.body)}</code></pre>`}</article>`}</div>
    <div class="artifact-dock"><div class="artifact-status"><span>${ctx.state.active?.threadId === ctx.threadId ? '正在处理…' : file.origin === 'grading' ? status(file.status) : '文件已保存'}</span>${ctx.threadId ? button('thread', '返回任务记录', `data-id="${e(ctx.threadId)}"`) : button('process', '查看过程')}</div>${composer(ctx)}</div></section>`;
}
export function listPage(title, actions, body) { return `<section class="list-page"><header class="page-header"><h1>${title}</h1><div>${actions}</div></header>${body}</section>`; }
export function fileScope(file) {
  return file.origin === 'grading' ? [file.taskTitle || file.folder || '未归档', file.groupLabel, file.category || '文档'].filter(Boolean).join(' · ') : '教师助手';
}

function workspaceCategory(file) {
  if (file.kind === 'presentation' || /\.(html?|pptx?|key)$/i.test(file.title)) return '演示文稿';
  if (file.kind === 'table' || /\.(csv|tsv|xlsx?|ods)$/i.test(file.title)) return '表格与数据';
  if (/\.(ya?ml|jsonl?|toml|xml|[cm]?[jt]sx?|py|css|sh|sql)$/i.test(file.title)) return '代码与配置';
  if (/\.(md|txt|pdf|docx?|rtf|odt)$/i.test(file.title)) return '文档与讲义';
  return '其他文件';
}
const archiveTime = rows => rows.reduce((latest, file) => latest > (file.updatedAt || '') ? latest : (file.updatedAt || ''), '');

function archiveFileRow(file, reference = false) {
  const attrs = `data-id="${e(file.id)}"`;
  const description = file.input ? `${file.category} · ${file.documentId ? 'v' + file.revision : file.pages.length + ' 页'}`
    : file.origin === 'grading' ? `${file.category || '文档'}${file.revision > 1 ? ' · v' + file.revision : ''}`
    : `${date(file.updatedAt)}${file.revision > 1 ? ' · v' + file.revision : ''}`;
  const title = `<span class="archive-file-icon">${glyph(file.input ? 'grading' : file.kind === 'table' ? 'tables' : 'file')}</span><span class="archive-name"><strong>${e(file.title)}</strong><small>${e(description)}</small></span>`;
  return `<div class="archive-file file-row">${button(reference ? 'reference' : file.input ? 'archive-source' : 'file', title, attrs, 'archive-file-open file-name')}${file.input || reference ? '' : button('continue', glyph('chat'), `${attrs} aria-label="引用并处理 ${e(file.title)}" title="引用并处理"`, 'archive-continue')}</div>`;
}

function archiveFolder(ctx, path, label, icon, meta, renderRows, autoOpen, level) {
  const id = JSON.stringify(path);
  const open = ctx.archiveFolders?.get(id) ?? autoOpen;
  return `<section class="archive-folder archive-${level}">${button(ctx.archiveAction || 'archive-toggle',
    `<span class="archive-folder-icon">${glyph(icon)}</span><span class="archive-name"><strong>${e(label)}</strong>${meta ? `<small>${e(meta)}</small>` : ''}</span><span class="archive-chevron">${glyph('right')}</span>`,
    `data-id="${e(id)}" aria-expanded="${Boolean(open)}"`, 'archive-toggle')}${open ? `<div class="archive-contents">${renderRows()}</div>` : ''}</section>`;
}

function archiveTree(ctx, files, reference = false) {
  const term = (ctx.query || '').trim().toLocaleLowerCase();
  const matches = file => !term || [file.title, fileScope(file), file.taskId, file.groupId, file.revision && 'v' + file.revision, file.owner === 'scheme' ? 'MS 评分标准' : '', file.owner === 'student' ? '学生答卷' : '', file.owner === 'class' ? '班级文件' : '', file.category, file.category === '汇总报告' ? archiveLabels.reports : file.category === '题目原件' ? archiveLabels.questions : '', file.origin !== 'grading' ? workspaceCategory(file) : '']
    .join(' ').toLocaleLowerCase().includes(term);
  const batches = new Map(), loose = new Map(), workspace = [];
  const visible = omitFiledGuides(files, files.filter(file => file.input), file => file.id.startsWith('document:') ? file.id.slice(9) : null);
  for (const file of visible) {
    if (file.origin !== 'grading') { if (matches(file)) workspace.push(file); continue; }
    const map = file.taskId ? batches : loose, id = file.taskId || file.folder || '';
    if (!map.has(id)) map.set(id, []);
    map.get(id).push(file);
  }
  const byLatest = ([,a],[,b]) => archiveTime(b).localeCompare(archiveTime(a));
  const fileRows = rows => rows.map(file => archiveFileRow(file, reference)).join('');
  const batchNames = new Map();
  for (const rows of batches.values()) batchNames.set(rows[0].taskTitle, (batchNames.get(rows[0].taskTitle) || 0) + 1);
  function categories(matching, taskId, title) {
    const owners = archiveOwners(matching);
    return Object.keys(archiveLabels).map(key => {
      const items = owners[key];
      if (!items.length) return '';
      const path = [taskId,key], students = key === 'students';
      const showStudents = () => {
        return items.map(group => {
          const meta = group.disambiguator ? `答卷 ${group.disambiguator}` : `${group.rows.length} 项`;
          return archiveFolder(ctx, [...path, group.id], group.label, 'grading', meta, () => fileRows(group.rows), Boolean(term && items.length <= 6), 'student');
        }).join('');
      };
      return archiveFolder(ctx, path, archiveLabels[key], students ? 'layers' : key === 'scheme' ? 'teaching' : 'folder',
        String(items.length), students ? showStudents : () => fileRows(items), Boolean(term && items.length <= 12 && !title.toLocaleLowerCase().includes(term)), 'category');
    }).join('');
  }
  const batchRows = [...batches].sort(byLatest).map(([taskId, rows], index) => {
    const matching = rows.filter(matches);
    if (!matching.length) return '';
    const count = rows.filter(file => !file.input).length;
    const submissions = new Set(rows.filter(file => file.groupId).map(file => file.groupId)).size;
    const title = rows[0].taskTitle || '未命名批次';
    const meta = [date(archiveTime(rows)), batchNames.get(title) > 1 ? '批次 ' + taskId.slice(0, 8) : null, count ? `${count} 项产出` : null, submissions ? `${submissions} 份答卷` : null].filter(Boolean).join(' · ');
    if (ctx.fileBatchId === taskId) return categories(matching, taskId, title);
    return archiveFolder(ctx, [taskId], title, 'folder', meta, () => categories(matching, taskId, title), Boolean(term || index === 0), 'batch');
  }).join('');
  const looseRows = [...loose].sort(byLatest).map(([folder, rows]) => {
    const matching = rows.filter(matches);
    if (!matching.length) return '';
    if (!folder && matching.length <= 8) return fileRows(matching);
    return archiveFolder(ctx, ['loose',folder], folder || '未关联批次的文件', 'folder', String(matching.length), () => matching.some(file => file.input) ? categories(matching, ['loose',folder], folder) : fileRows(matching), Boolean(term), 'batch');
  }).join('');
  const section = (title, content) => content ? `<section class="archive-section"><h2>${title}</h2>${content}</section>` : '';
  if (ctx.fileBatchId) return batchRows;
  const byType = new Map();
  for (const file of workspace) {
    const kind = workspaceCategory(file);
    if (!byType.has(kind)) byType.set(kind, []);
    byType.get(kind).push(file);
  }
  const workspaceRows = [...byType].map(([kind,rows]) => archiveFolder(ctx, ['workspace',kind], kind, 'folder',
    rows.length + ' 项', () => fileRows(rows), Boolean(term), 'category')).join('');
  return section('批改批次', batchRows) + section('其他批改文件', looseRows) + section('助手文件', workspaceRows);
}

export function referenceTree(files, query, archiveFolders) {
  return archiveTree({query, archiveFolders, archiveAction:'reference-folder'}, [...files].sort((a,b) => (b.updatedAt || '').localeCompare(a.updatedAt || '')), true)
    || '<p class="muted">没有匹配的文件。</p>';
}

export function filesPage(ctx) {
  const files = [...ctx.state.files,...(ctx.state.archiveInputs || [])]
    .filter(file => ctx.fileBatchId ? file.taskId === ctx.fileBatchId : ctx.filter === 'all' || file.origin === ctx.filter)
    .sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''));
  const tabs = [['all','全部'],['grading','批改归档'],['workspace','助手文件']];
  const search = `<label class="search-control">${glyph('search')}<input id="file-search" type="search" placeholder="搜索${ctx.fileBatchId ? '本批次文件' : '批次、学生或文件'}" aria-label="搜索文件" value="${e(ctx.query)}"></label>`;
  const tree = archiveTree({...ctx, archiveFolders:ctx.query.trim() ? ctx.archiveSearchFolders : ctx.archiveFolders}, files);
  if (ctx.fileBatchId) {
    const title = ctx.grading.tasks.find(task => task.id === ctx.fileBatchId)?.title || files[0]?.taskTitle || '批次文件';
    const empty = ctx.query ? '没有匹配的文件。' : '本批次暂无归档文件。';
    return listPage(e(title), '<a href="#files" data-route="files" class="text-link">全部文件</a>',
      `<div class="list-tools archive-tools">${search}</div><div class="file-list archive-tree">${tree || `<p class="dashboard-empty">${empty}</p>`}</div>`);
  }
  const controls = `<div class="list-tools archive-tools"><div class="segments">${tabs.map(([key,label]) => button('file-filter', label, `data-filter="${key}" aria-pressed="${ctx.filter === key}"`)).join('')}</div>${search}</div>`;
  const empty = ctx.query || ctx.filter !== 'all' ? emptyState('search', '没有匹配的文件', '试试其他关键词或文件来源。') : emptyState('folder', '文件库还是空的', '文本文件可直接拖入这里。');
  return listPage('文件', button('upload', `${glyph('plus')} 导入文件`, '', 'primary'), `${controls}<div class="file-list archive-tree">${tree || empty}</div>`);
}
export function skillsPage(ctx) {
  return listPage('技能库', button('import-skill', `${glyph('plus')} 导入技能`, '', 'primary'), `<div class="skill-list">${ctx.state.skills.map(skill => `<article class="skill-row"><span class="skill-icon">${glyph(skill.builtin ? skill.id : 'skills')}</span><div class="skill-text"><h2>${e(skill.name)}</h2><p>${e(skill.description)}</p></div><button type="button" role="switch" aria-checked="${skill.enabled}" aria-label="启用 ${e(skill.name)}" data-action="toggle-skill" data-id="${e(skill.id)}" class="switch"><span></span></button></article>`).join('')}</div>`);
}
const taskTime = task => [task.createdAt, task.startedAt, task.completedAt, task.updatedAt]
  .reduce((latest, value) => value > latest ? value : latest, '');
function batchPreview(result, isRead) {
  const route = 'grading/' + encodeURIComponent(result.id);
  const metrics = [];
  if (Number.isInteger(result.submissionCount)) metrics.push(`${result.submissionCount} 份答卷`);
  if (result.pending) metrics.push(`${result.pending} 份待确认`);
  const hasMean = Number.isFinite(result.mean);
  if (!hasMean && result.recorded && !result.pending) metrics.push(`${result.recorded} 份有评分记录`);
  const coverage = result.scored < result.submissionCount ? `${result.scored} 份` : '';
  const scoreLabel = result.scored > 1 ? (coverage ? `${coverage}均分` : '均分') : (coverage ? '已定 1 份' : '');
  return `<li><a class="result-preview" href="#${e(route)}" data-route="${e(route)}">
    <span class="preview-meta">${result.completedAt ? `<time datetime="${e(result.completedAt)}">${e(date(result.completedAt))}</time>` : ''}<span class="task-state" data-status="${e(result.status)}">${e(status(result.status))}</span></span>
    <strong class="preview-title">${e(result.title || '未命名批次')}${isRead(result.id) ? '' : unreadDot}</strong>
    ${result.excerpt ? `<span class="preview-excerpt">${e(result.excerpt)}</span>` : ''}
    <span class="preview-foot"><span class="preview-figures">${hasMean ? `<span class="preview-mean">${scoreLabel ? `<small>${e(scoreLabel)}</small> ` : ''}<b>${e(result.mean)} / ${e(result.maximum)}</b></span>` : ''}<span>${metrics.map(e).join(' · ')}</span></span>${glyph('forward')}</span>
  </a></li>`;
}

export function gradingOverview(ctx, isRead = () => false) {
  const results = ctx.grading.recentResults || [];
  return `<section class="dashboard grading-overview"><div class="dashboard-inner">
    <header class="grading-intro"><h1>批改</h1><div class="grading-destinations">
      <a href="#grading/intake" data-route="grading/intake" class="primary">${glyph('plus')}开始批改</a>
      <a href="#grading/history" data-route="grading/history">${glyph('history')}批改历史</a></div></header>
    <batch-previews><div class="section-heading"><h2 id="recent-results-title">最近批改结果</h2>
      ${results.length > 1 ? `<div class="preview-controls" hidden>
        <button type="button" data-direction="-1" aria-label="上一组批改结果" aria-controls="recent-results">${glyph('left')}</button>
        <button type="button" data-direction="1" aria-label="下一组批改结果" aria-controls="recent-results">${glyph('right')}</button>
      </div>` : ''}</div>
      ${results.length ? `<ul id="recent-results" class="preview-track" aria-labelledby="recent-results-title">${results.map(result => batchPreview(result, isRead)).join('')}</ul>` : '<p class="dashboard-empty">批改完成后，可以在这里预览结果。</p>'}
    </batch-previews></div></section>`;
}

export function gradingHistory(ctx, isRead = () => false) {
  const batches = ctx.grading.tasks.filter(task => task.kind === 'grade')
    .sort((a, b) => taskTime(b).localeCompare(taskTime(a)));
  const rows = batches.map(task => {
    const route = 'grading/' + encodeURIComponent(task.id);
    const meta = [taskTime(task) && date(taskTime(task)), Number.isInteger(task.submissionCount) ? task.submissionCount + ' 份答卷' : ''].filter(Boolean);
    return `<li><a class="batch-record" href="#${e(route)}" data-route="${e(route)}">
      <span class="batch-record-name"><strong>${e(task.title || '未命名批次')}</strong><small>${e(meta.join(' · '))}</small></span>
      ${(task.hasResult ?? ['completed','needs_review'].includes(task.status)) && !isRead(task.id) ? unreadDot : ''}<span class="task-state" data-status="${e(task.status)}">${e(status(task.status))}</span>${glyph('right')}</a></li>`;
  }).join('');
  return `<section class="dashboard grading-history"><div class="dashboard-inner">
    <header class="dashboard-heading"><h1>批改历史</h1><a class="primary" href="#grading/intake" data-route="grading/intake">${glyph('plus')} 开始批改</a></header>
    ${rows ? `<ol class="batch-records" aria-label="按最近活动排列的批改批次">${rows}</ol>` : '<p class="dashboard-empty">还没有批改记录。从「开始批改」导入第一批答卷。</p>'}
  </div></section>`;
}
export function settingsPage(ctx) {
  const {preferences:prefs, connection, connections = [], modelCatalog} = ctx.state;
  const account = ctx.state.account || {mode:'local'};
  const cloud = account.mode === 'cloud', signed = Boolean(account.user);
  const balance = account.credits?.status === 'available'
    ? '可用额度 US$' + account.credits.remaining.toLocaleString('zh-CN',{maximumFractionDigits:6})
    : ({empty:'额度已用完',unfunded:'账号尚未开通额度'}[account.credits?.status] || '暂时无法读取额度');
  const current = modelCatalog?.defaultId;
  const rows = connections.map(item => {
    const attrs = 'data-id="' + e(item.id) + '"';
    return `<div class="setting-line connection-row"><div><strong>${e(item.name)}</strong><small>${e(item.modelId)}</small></div><div>
      ${current === item.id ? '<small>默认</small>' : button('default-connection','设为默认',attrs)}
      ${button('edit-connection','编辑',attrs)}</div></div>`;
  }).join('');
  return listPage('账号设置', '', `<form id="preferences-form" class="settings-form">
    <section><h2>GradeOS Cloud</h2><div class="setting-line connection-row"><div><strong>${signed ? e(account.user.name) : '教师账号'}</strong>
      <small>${signed ? balance : '登录后可使用账号额度，并将确认的批改结果发给学生。'}</small></div>
      <div class="${signed ? '' : 'account-methods'}">${signed ? button('cloud-refresh','刷新额度') + button('cloud-logout','退出登录') : quickGoogleLink(account) + passwordLoginButton()}</div></div>
      ${signed ? '<div><a href="/cloud-publish.html">发布给学生</a></div>' : ''}</section>
    <section><h2>模型连接</h2>
      <div class="setting-line connection-row"><div><strong>Cloud 额度</strong><small>模型费用由教师的 GradeOS Cloud 账号支付</small></div>
        ${signed && cloud ? '<small>正在使用</small>' : button(signed ? 'use-cloud' : 'cloud-login',signed ? '使用 Cloud 额度' : '登录后使用')}</div>
      <div class="setting-line connection-row"><div><strong>自带 API</strong><small>使用自己的密钥，由所选服务商计费</small></div>
        ${cloud ? button('use-local','使用自带 API') : '<small>已选择</small>'}</div>
      ${!cloud ? `<div class="setting-line connection-row"><div><strong>OpenRouter</strong><small>${account.hasLocalKey ? '已连接' : '一把密钥可使用五个推荐模型'}</small></div>
        ${button('router-key',account.hasLocalKey ? '管理密钥' : '填写 API Key')}</div>${rows}
        <div>${button('edit-connection',glyph('plus')+' 添加其他 API 连接','','outline')}</div>` : ''}
      <p>模型服务会收到本次任务所需的文字和图片。</p></section>
    <section><h2>聊天模型</h2><div class="setting-line connection-row"><div><strong>在聊天中显示</strong>
      <small>${recommendedChatIds.filter(id=>modelCatalog?.chatIds?.includes(id)).map(id=>e(gradingModel(id).name)).join('、')}</small></div>
      ${button('chat-models','选择模型')}</div></section>
    <section><h2>账号与工作区</h2><label>本地显示名称<input name="displayName" value="${e(prefs.displayName)}" maxlength="60" required></label>
      <label>工作区名称<input name="workspaceName" value="${e(prefs.workspaceName)}" maxlength="60" required></label>
      <details><summary>本地存储位置</summary><p>${e(ctx.state.directory)}</p></details></section>
    <section><h2>外观</h2><label>动效<select name="motion"><option value="system" ${prefs.motion === 'system' ? 'selected' : ''}>跟随系统</option>
      <option value="reduce" ${prefs.motion === 'reduce' ? 'selected' : ''}>减少动态效果</option></select></label></section>
    <div class="settings-submit"><button class="primary" type="submit">保存设置</button></div></form>`);
}
