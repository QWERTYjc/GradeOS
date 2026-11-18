import { escape as e, icon, button, iconButton, empty, pageById } from './ui.mjs';
import { librarySections } from './grading-library.mjs';
import { taskForm } from './tasks.mjs';

export function historyLibrary(state) {
  const sections = librarySections(state);
  const row = doc => button(doc.action, `${icon('file-text')}<span>${e(doc.title)}</span><small>${e([doc.groupLabel, doc.category, doc.version && 'v' + doc.version].filter(Boolean).join(' · '))}</small>`, { attrs: `data-id="${e(doc.id)}" data-task="${e(doc.taskId)}"` });
  return `<section class="intake-library"><div class="library-heading"><h2>历史文档 <small>${sections.reduce((n, section) => n + section.rows.length, 0)}</small></h2>${state.documents?.some(doc => !doc.taskId) ? button('organize-documents','整理文档') : ''}</div>${sections.map(section => `<section><h3>${e(section.title)}</h3>${section.rows.slice(0, 4).map(row).join('')}${section.rows.length > 4 ? `<details><summary>其余 ${section.rows.length - 4} 份文档</summary>${section.rows.slice(4).map(row).join('')}</details>` : ''}</section>`).join('') || '<p>保存的文档和批改产出会出现在这里。</p>'}</section>`;
}

export function uploadSources(state) {
  const files = new Map();
  for (const page of state.pages.filter(page => page.active !== false)) {
    if (!files.has(page.sourceId)) files.set(page.sourceId, { id: page.sourceId, name: page.fileName, role: page.role, pages: 0 });
    files.get(page.sourceId).pages++;
  }
  return [...files.values()];
}

export function pendingPages(state) {
  const owned = new Set(state.groups.flatMap(group => group.pageIds));
  return state.pages.filter(page => page.role === 'student' && page.active !== false && !owned.has(page.id));
}

export function uploadsView(state) {
  const sources = uploadSources(state);
  if (!sources.length) return '';
  const labels = { student: '学生作答', scheme: '评分标准', question: '题目' };
  return `<section class="staged-files"><header><strong>本次材料 · ${sources.length} 个文件</strong>${button('remove-uploads','清空本次材料')}</header>${sources.map(file => `<div><span>${e(file.name)}</span><small>${labels[file.role]} · ${file.pages} 页</small>${button('remove-uploads','移除',{attrs:`data-id="${e(file.id)}" aria-label="移除 ${e(file.name)}"`})}</div>`).join('')}</section>`;
}

export function intakeView(ctx) {
  const { state, intakeStep: step } = ctx;
  const pending = pendingPages(state);
  const files = uploadSources(state);
  const go = (n, label, style = 'quiet') => button('intake-step', label, { className: style, attrs: `data-step="${n}"`, disabled: ctx.busy || (n === 2 && !files.some(file => file.role === 'student')) || (n === 3 && (!state.groups.length || pending.length)) });
  const progress = ['上传材料', '页面分组', '批改说明'].map((label, i) => `<li ${i+1 === step ? 'aria-current="step"' : ''}><span>${i+1}</span>${label}</li>`).join('');
  const uploadCard = (role, label) => {
    const sources = files.filter(file => file.role === role);
    const pages = sources.reduce((sum, file) => sum + file.pages, 0);
    return `<div class="upload-slot" data-upload-role="${role}"><h2>${label}</h2>${button('upload-' + role, `${icon('upload')}<strong>${pages ? '继续添加' : '选择文件'}</strong><small>${pages ? `${sources.length} 个文件 · ${pages} 页` : 'PDF 或照片、扫描图'}</small>`, { disabled: ctx.busy })}</div>`;
  };
  let body;
  if (step === 1) {
    body = `<h1>准备批改材料</h1><div class="upload-pair">${uploadCard('student','学生作答')}${uploadCard('scheme','评分标准（可选）')}</div>
      <div class="upload-extras"><label>导入作答后 <select id="upload-grouping"><option value="manual">先放入待分组页</option><option value="file" ${ctx.uploadGrouping === 'file' ? 'selected' : ''}>每个文件作为一份答卷</option></select></label>${button('upload-question', '添加题目' + (state.questions.length ? ` · ${state.questions.length} 份` : '（可选）'), { disabled: ctx.busy })}</div>
      ${uploadsView(state)}<footer>${go(2,'页面分组 →','primary')}</footer>${historyLibrary(state)}`;
  } else if (step === 2) {
    body = `<h1>按学生划分答卷</h1>${materialView(ctx, true)}<footer>${go(1,'返回上传材料')}${go(3,'检查批改说明 →','primary')}</footer>`;
  } else {
    const groupIds = state.groups.map(group => group.id);
    const draft = ctx.intakeDraft && { ...ctx.intakeDraft, groupIds: ctx.intakeDraft.materialRevision === state.materialRevision ? ctx.intakeDraft.groupIds : groupIds };
    body = `<h1>批改说明</h1>${taskForm({ ...ctx, selected: new Set(groupIds) }, draft, { allowStart: true })}<footer>${go(2,'返回页面分组')}</footer>`;
  }
  return `<section class="grading-intake"><ol class="intake-steps" aria-label="批改准备步骤">${progress}</ol>${body}</section>`;
}

export function materialView(ctx, wizard = false) {
  const { state, selected, sorting, materialRole = 'student' } = ctx;
  if (!state.pages.length) return empty('把答卷放在这里', '上传 PDF 或照片，再按学生划分答卷。',
    `${button('upload-student', '上传答卷', { className: 'primary', symbol: 'upload' })}${button('upload-scheme', '上传评分标准', { className: 'text-button' })}${button('upload-question', '上传题目', { className: 'text-button' })}`) + '<div class="drop-hint">也可以直接拖入文件</div>';
  const schemeMode = materialRole !== 'student';
  const roleLabel = materialRole === 'question' ? '题目' : '评分标准';
  const pending = schemeMode ? [] : pendingPages(state);
  const groups = schemeMode ? (materialRole === 'question' ? state.questions || [] : state.schemes) : [...state.groups, ...(pending.length ? [{ id: '', label: '待分组页', pageIds: pending.map(page => page.id) }] : [])];
  const pageCount = groups.reduce((sum, group) => sum + group.pageIds.length, 0);
  return `<section class="materials content">
    <div class="section-toolbar"><div class="title-line"><h1>${schemeMode ? roleLabel : '答卷'}</h1><span class="muted">${schemeMode ? groups.length : state.groups.length} 份 · ${pageCount} 页${pending.length ? ` · ${pending.length} 页待分组` : ''}</span></div>
      <div class="toolbar-actions">${!schemeMode && groups.length ? `<details class="menu"><summary>划分 ${icon('down')}</summary><div class="menu-items">${button('equal-split', '按人数均分')}${button('file-split', '按文件分卷')}${wizard ? '' : button('select-all', selected.size === groups.length ? '取消全选' : '选择全部')}</div></details>
        ${wizard ? button('assign-pages', ctx.pickedPages.size ? `分组（${ctx.pickedPages.size} 页）` : '分组选中页', { className: 'soft', disabled: !ctx.pickedPages.size }) : ''}
        ${button('sorting', '排序', { className: sorting ? 'soft active' : 'text-button', symbol: 'swap' })}${iconButton('undo', '撤销上次划分', 'undo', ctx.undo.length ? '' : 'disabled')}` : ''}
        ${[['student', '答卷'], ['question', '题目'], ['scheme', '评分标准']].map(([role, label]) => button('material-role', label, { className: materialRole === role ? 'soft active' : 'text-button blue', attrs: `data-role="${role}"` })).join('')}
      </div>
    </div>
    ${!groups.length ? empty(schemeMode ? `添加${roleLabel}` : '添加答卷', schemeMode ? (materialRole === 'question' ? '题目用于理解任务和推导评分依据，可不提供 MS。' : '上传原始评分条文，批改时将结合题目理解并保留来源。') : '上传后可调整页序和学生边界。', button(schemeMode ? `upload-${materialRole}` : 'upload-student', '上传材料', { className: 'primary' })) : ''}
    ${wizard && pending.length ? `<div class="pending-help"><span>勾选同一位学生的页面，再点「分组选中页」。</span>${button('group-pending','将全部待分组页归为一份')}</div>` : ''}
    <div class="groups">${groups.map((group, groupIndex) => `<section class="answer-group ${selected.has(group.id) && !schemeMode ? 'selected' : ''}" data-group-id="${e(group.id)}">
      <div class="group-heading">${!schemeMode && !wizard && group.id ? `<label class="group-check"><input type="checkbox" data-group="${e(group.id)}" ${selected.has(group.id) ? 'checked' : ''}><span>${e(group.label)}</span></label>` : `<strong>${e(group.label)}</strong>`}
        <span class="muted">${group.pageIds.length} 页</span>${!schemeMode && group.id ? iconButton('rename-group', '修改答卷名称', 'edit', `data-id="${e(group.id)}"`) : ''}
      </div>
      <div class="page-grid">${group.pageIds.map((pageId, index) => {
        const page = pageById(state, pageId);
        return `<div class="page-tile" data-page-id="${e(pageId)}" ${sorting && !schemeMode && group.id ? 'draggable="true"' : ''}>
          ${wizard && !schemeMode ? `<label class="pick-page"><input type="checkbox" data-pick-page="${e(pageId)}" aria-label="选择 ${e(group.label)} 第 ${index+1} 页" ${ctx.pickedPages.has(pageId) ? 'checked' : ''}></label>` : ''}
          <button class="page-image" data-action="page" data-id="${e(pageId)}" aria-label="打开 ${e(group.label)} 第 ${index + 1} 页"><img src="${page.url}" alt="${e(page.fileName)}，原文件第 ${page.sourcePage} 页" loading="lazy" draggable="false"><span class="page-number">${index + 1}</span></button>
          ${wizard ? `<small class="original-page" title="${e(page.fileName)} · 原页 ${page.sourcePage}">${e(page.fileName)} · p${page.sourcePage}</small>` : ''}
          ${!schemeMode && group.id ? `<div class="page-tools">${sorting ? `${iconButton('page-left', '向前移动一页', 'left', `data-id="${e(pageId)}"`)}${iconButton('page-right', '向后移动一页', 'right', `data-id="${e(pageId)}"`)}` : index > 0 ? button('split-page', '在此页前分卷', { attrs: `data-id="${e(pageId)}"`, className: 'small' }) : ''}</div>` : ''}
        </div>`;
      }).join('')}</div>
      ${!schemeMode && groupIndex < state.groups.length - 1 ? `<div class="boundary">${button('merge-next', icon('column-width'), { className: 'boundary-handle', attrs: `data-id="${e(group.id)}" title="移除此分界，合并下一份答卷" aria-label="合并 ${e(group.label)} 与下一份答卷"` })}</div>` : ''}
    </section>`).join('')}</div>
  </section>
  ${!wizard && !schemeMode && state.groups.length ? `<form class="command-dock" id="material-command"><span class="scope">${selected.size ? `已选 ${selected.size} 份` : '选择答卷'}</span><input name="goal" aria-label="补充批改要求" placeholder="补充批改要求（可选）…" value="${e(ctx.command)}" ${!selected.size ? 'disabled' : ''} maxlength="8000">${button('manual-task', '', { className: 'icon-button', symbol: 'form', attrs: 'title="手动安排任务" aria-label="手动安排任务"', disabled: !selected.size })}<button type="submit" class="primary" ${!selected.size || ctx.busy ? 'disabled' : ''}>${ctx.busy ? '正在安排…' : '安排任务'}</button></form>` : ''}`;
}

export function equalGroups(groups, count) {
  const pages = groups.flatMap(group => group.pageIds);
  if (!Number.isInteger(count) || count < 1 || count > pages.length) throw Error('人数必须在 1 和页面数之间。');
  let offset = 0;
  return Array.from({ length: count }, (_, index) => {
    const size = Math.floor(pages.length / count) + (index < pages.length % count ? 1 : 0);
    const group = { id: crypto.randomUUID(), label: `答卷 ${String(index + 1).padStart(2, '0')}`, pageIds: pages.slice(offset, offset + size) };
    offset += size; return group;
  });
}

export function movedGroups(groups, pageId, destinationId) {
  const pages = groups.flatMap(group => group.pageIds);
  const from = pages.indexOf(pageId), to = pages.indexOf(destinationId);
  if (from < 0 || to < 0 || from === to) return null;
  pages.splice(to, 0, ...pages.splice(from, 1));
  let offset = 0;
  return groups.map(group => { const next = { ...group, pageIds: pages.slice(offset, offset + group.pageIds.length) }; offset += group.pageIds.length; return next; });
}

export function assignPages(groups, selected, targetId, label, unassigned = []) {
  const pages = [...groups.flatMap(group => group.pageIds), ...unassigned].filter(id => selected.has(id));
  if (!pages.length || pages.length !== selected.size) throw Error('页面已变化，请重新选择。');
  if (targetId && !groups.some(group => group.id === targetId)) throw Error('目标答卷已变化。');
  const next = groups.map(group => ({ ...group, pageIds: group.pageIds.filter(id => !selected.has(id)) }));
  const target = next.find(group => group.id === targetId);
  if (target) {
    const original = groups.find(group => group.id === targetId).pageIds;
    target.pageIds = [...original, ...pages.filter(id => !original.includes(id))];
  }
  else next.push({ id: crypto.randomUUID(), label: label.trim() || '新答卷', pageIds: pages });
  return next.filter(group => group.pageIds.length);
}
