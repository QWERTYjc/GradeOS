import { escape as e, markdown, statuses } from './ui.mjs';
export { e, markdown };
export const glyph = name => {
  const paths = { plus: '<path d="M12 5v14M5 12h14"/>', arrow: '<path d="M12 19V5m-6 6 6-6 6 6"/>', down: '<path d="m7 10 5 5 5-5"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>', folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3Z"/>', menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>', left: '<path d="m14 6-6 6 6 6"/>', right: '<path d="m10 6 6 6-6 6"/>' };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.plus}</svg>`;
};
export const button = (action, label, attrs = '', className = '') => `<button type="button" data-action="${action}" class="${className}" ${attrs}>${label}</button>`;
export const date = value => value ? new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
export const status = value => statuses[value] || ({ confirmed: '已确认', draft: '草稿' }[value]) || '已保存';
export const fileUrl = file => `/api/system/files/${encodeURIComponent(file.id)}?revision=${file.revision}&hash=${encodeURIComponent(file.hash)}`;
export const refMeta = file => ({ id: file.id, title: file.title, revision: file.revision, hash: file.hash });
export function shell(state, route) {
  const prefs = state.preferences;
  return `<aside class="sidebar" aria-label="主导航"><a href="#home" class="wordmark">GradeOS</a>${button('new', `${glyph('plus')}<span>新对话</span>`, '', 'new-chat')}
    <nav>${[['home', '工作台'], ['grading', '批改'], ['files', '文件'], ['skills', 'Skills'], ['tasks', '任务']].map(([key, label]) => `<a href="#${key}" data-route="${key}" ${route === key ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
    ${button('account', `<span class="avatar">${e(prefs.displayName.slice(0, 1))}</span><span>${e(prefs.displayName)}</span>${glyph('down')}`, 'aria-haspopup="dialog"', 'account')}
  </aside><button class="sidebar-scrim" data-action="close-nav" aria-label="关闭导航"></button>
  <main id="main" tabindex="-1"><div class="mobile-header">${button('menu', glyph('menu'), 'aria-label="打开导航"')}<span>GradeOS</span></div><div id="page"></div></main>`;
}
export function composer(ctx) {
  const busy = ctx.state.active?.threadId === ctx.threadId;
  const references = `<div id="reference-chips" class="reference-chips">${ctx.refs.map((ref, index) => button('remove-ref', `${e(ref.title)} <span>v${ref.revision}</span>${glyph('close')}`, `data-index="${index}" aria-label="移除引用 ${e(ref.title)}"`, 'source-chip')).join('')}${ctx.skillId ? button('clear-skill', e(ctx.state.skills.find(skill => skill.id === ctx.skillId)?.name || ''), '', 'source-chip') : ''}</div>`;
  return `<form id="task-composer" class="task-composer">${ctx.file ? '' : references}
    <textarea id="task-input" name="goal" aria-label="任务要求" placeholder="${ctx.file ? '继续调整这份文件…' : '描述任务，或拖入文件'}" rows="2" maxlength="8000">${e(ctx.draft)}</textarea>
    <div class="composer-tools"><div>${button('add', glyph('plus'), 'aria-label="添加文件或 Skill" aria-haspopup="dialog"', 'icon-button')}${ctx.file ? references : button('workspace', `${glyph('folder')}<span>${e(ctx.state.preferences.workspaceName)}</span>${glyph('down')}`, 'aria-label="工作区设置"', 'scope')}</div>
      <button type="${busy ? 'button' : 'submit'}" ${busy ? 'data-action="cancel"' : ''} class="send" aria-label="${busy ? '停止任务' : '发送任务'}" ${(!busy && !ctx.draft.trim()) || ctx.sending ? 'disabled' : ''}>${glyph(busy ? 'stop' : 'arrow')}</button></div></form>`;
}
export function home(ctx) {
  if (ctx.file) return artifact(ctx);
  const messages = ctx.thread?.messages || [];
  if (!messages.length) return `<section class="welcome"><h1>今天，想完成什么？</h1>${composer(ctx)}</section>`;
  const active = ctx.state.active?.threadId === ctx.threadId ? ctx.state.active : null;
  return `<section class="conversation"><header class="page-header"><h1>${e(ctx.thread.title)}</h1>${button('history', '历史对话')}</header><div class="messages" id="messages">${messages.map(message => messageView(message.id === active?.id ? { ...message, ...active } : message, ctx)).join('')}</div><div class="conversation-composer">${composer(ctx)}</div></section>`;
}
export function messageView(message, ctx) {
  return `<article class="message ${e(message.role)}"><div class="prose">${markdown(message.text || (message.status === 'running' ? '正在处理…' : ''))}</div>${message.fileIds?.length ? `<div class="output-links">${message.fileIds.map(id => { const file = ctx.state.files.find(row => row.id === id); return file ? button('file', `${e(file.title)} ${glyph('right')}`, `data-id="${e(id)}"`, 'output-link') : ''; }).join('')}</div>` : ''}${message.events?.length ? `<details class="process"><summary>查看过程 · ${status(message.status)}</summary>${message.events.filter(event => event.type === 'tool_execution_end').map(event => `<p>${e(event.label)} · ${event.status === 'error' ? '未完成' : '完成'}</p>`).join('')}</details>` : message.status && !['completed', 'running'].includes(message.status) ? `<p class="muted">${status(message.status)}</p>` : ''}</article>`;
}
export function artifact(ctx) {
  const file = ctx.file, ext = file.title.split('.').at(-1).toLowerCase();
  return `<section class="artifact"><header class="page-header"><h1>${e(file.title)}</h1><div>${button('info', '文件信息')}${file.origin === 'grading' ? '' : button('edit', '编辑')}<a class="button" href="${fileUrl(file)}&download=1">导出</a></div></header>
    <div class="artifact-scroll">${ext === 'html' ? `<iframe class="artifact-preview" title="${e(file.title)} 预览" sandbox src="${fileUrl(file)}&preview=1${ctx.slideCount > 1 ? `&slide=${ctx.slide}` : ''}"></iframe>${ctx.slideCount > 1 ? `<div class="pagination">${button('previous-slide', glyph('left'), `aria-label="上一页" ${ctx.slide <= 1 ? 'disabled' : ''}`)}<span>${ctx.slide} / ${ctx.slideCount}</span>${button('next-slide', glyph('right'), `aria-label="下一页" ${ctx.slide >= ctx.slideCount ? 'disabled' : ''}`)}</div>` : ''}` : `<article class="document-paper prose">${['md', 'txt'].includes(ext) ? markdown(file.body) : `<pre><code>${e(file.body)}</code></pre>`}</article>`}</div>
    <div class="artifact-dock"><div class="artifact-status"><span>${ctx.state.active?.threadId === ctx.threadId ? '正在处理…' : file.origin === 'grading' ? status(file.status) : '文件已保存'}</span>${button('process', '查看过程')}</div>${composer(ctx)}</div></section>`;
}
export function listPage(title, actions, body) { return `<section class="list-page"><header class="page-header"><h1>${title}</h1><div>${actions}</div></header>${body}</section>`; }
export function filesPage(ctx) {
  const files = ctx.state.files.filter(file => (!ctx.query || file.title.toLowerCase().includes(ctx.query.toLowerCase())) && (ctx.filter !== 'grading' || file.origin === 'grading'));
  return listPage('文件', button('upload', '导入文件', '', 'outline'), `<div class="list-tools"><div class="segments">${button('filter-all', '全部', `aria-pressed="${ctx.filter !== 'grading'}"`)}${button('filter-grading', '批改产出', `aria-pressed="${ctx.filter === 'grading'}"`)}</div><input id="file-search" type="search" placeholder="查找文件" aria-label="查找文件" value="${e(ctx.query)}"></div><div class="file-list">${files.length ? `<div class="list-labels"><span>名称</span><span>来源</span><span>更新时间</span></div>${files.map(file => `<div class="file-row">${button('file', `<span>${e(file.title)}</span><small>v${file.revision} · ${status(file.status)}</small>`, `data-id="${e(file.id)}"`, 'file-name')}<span>${file.origin === 'grading' ? '批改' : '工作台'}</span><span>${date(file.updatedAt)}</span>${button('continue', '继续处理', `data-id="${e(file.id)}"`, 'row-action')}</div>`).join('')}` : `<div class="empty-state"><h2>${ctx.query ? '没有匹配的文件' : '文件会保存在这里'}</h2><p>${ctx.query ? '试试其他关键词。' : '导入本地文件，或从工作台和批改中生成成果。'}</p></div>`}</div>`);
}
export function skillsPage(ctx) {
  return listPage('Skills', button('import-skill', '导入 SKILL.md', '', 'outline'), `<p class="page-description">按任务选用的能力。启用后，工作台会在需要时使用。</p><div class="skill-list">${ctx.state.skills.map(skill => `<div class="skill-row"><div><h2>${e(skill.name)}</h2><p>${e(skill.description)}</p><span class="muted">${e(skill.format)}${skill.builtin ? '' : ' · 导入后默认关闭'}</span></div><button type="button" role="switch" aria-checked="${skill.enabled}" aria-label="启用 ${e(skill.name)}" data-action="toggle-skill" data-id="${e(skill.id)}" class="switch"><span></span></button></div>`).join('')}</div><p class="footnote">Skills 使用现有文件工具。导入任务指南不会授予终端或网络权限。</p>`);
}
export function tasksPage(ctx) {
  const general = ctx.state.threads.filter(thread => thread.lastMessage).map(thread => ({ ...thread.lastMessage, title: thread.title, origin: 'home', id: thread.id }));
  if (ctx.state.active) { const task = general.find(row => row.id === ctx.state.active.threadId); if (task) Object.assign(task, { status: 'running' }); }
  const tasks = [...general, ...ctx.grading.tasks.map(task => ({ ...task, origin: 'grading' }))].sort((a, b) => (b.startedAt || b.createdAt || '').localeCompare(a.startedAt || a.createdAt || ''));
  return listPage('任务', '', tasks.length ? `<div class="task-list">${tasks.map(task => `<div class="task-row"><div>${button(task.origin === 'grading' ? 'grading' : 'thread', e(task.title || '工作台任务'), `data-id="${e(task.id)}"`, 'task-name')}<p>${task.origin === 'grading' ? '批改' : '工作台'} · ${date(task.startedAt || task.createdAt)}</p></div><span class="task-state ${task.status === 'running' ? 'running' : ''}">${status(task.status)}</span></div>`).join('')}</div>` : '<div class="empty-state"><h2>还没有任务</h2><p>从工作台开始对话，或进入批改处理答卷。</p></div>');
}
export function settingsPage(ctx) {
  const { preferences: prefs, connection } = ctx.state;
  return listPage('设置', '', `<form id="preferences-form" class="settings-form"><section><h2>本地账号</h2><label>显示名称<input name="displayName" value="${e(prefs.displayName)}" maxlength="60" required></label><p>本地文件和工作区无需登录。</p></section><section><h2>工作区</h2><label>名称<input name="workspaceName" value="${e(prefs.workspaceName)}" maxlength="60" required></label><label>存储位置<input value="${e(ctx.state.directory)}" readonly></label><p>对话、文件和版本保存在此目录。</p></section><section><h2>模型连接</h2><div class="setting-line"><span>OpenRouter</span><span>${connection.ready ? '已连接' : '未连接'}</span></div><div class="setting-line"><span>模型</span><span>${e(connection.model)}</span></div><div class="setting-line"><span>单次任务预算上限</span><span>$${connection.cap}</span></div><p>调用模型时，所选文件内容和对话会发送给模型服务。密钥保留在本机，不显示在页面。</p>${connection.ready ? '' : '<details><summary>连接方法</summary><p>在本地项目的 .env 中配置 OPENROUTER_API_KEY，然后重启服务。此界面沿用现有模型连接。</p></details>'}</section><section><h2>外观与动效</h2><label>动效<select name="motion"><option value="system" ${prefs.motion === 'system' ? 'selected' : ''}>跟随系统</option><option value="reduce" ${prefs.motion === 'reduce' ? 'selected' : ''}>减少动态效果</option></select></label></section><div class="settings-submit"><button class="primary" type="submit">保存设置</button></div></form>`);
}
