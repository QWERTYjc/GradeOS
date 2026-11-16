import { escape as e, icon, button, iconButton, empty, pageById } from './ui.mjs';

export function materialView(ctx) {
  const { state, selected, sorting, materialRole = 'student' } = ctx;
  if (!state.pages.length) return empty('把答卷放在这里', '上传 PDF 或照片，再按学生划分答卷。',
    `${button('upload-student', '上传答卷', { className: 'primary', symbol: 'upload' })}${button('upload-scheme', '上传评分标准', { className: 'text-button' })}${button('upload-question', '上传题目', { className: 'text-button' })}`) + '<div class="drop-hint">也可以直接拖入文件</div>';
  const schemeMode = materialRole !== 'student';
  const roleLabel = materialRole === 'question' ? '题目' : '评分标准';
  const groups = schemeMode ? (materialRole === 'question' ? state.questions || [] : state.schemes) : state.groups;
  const pageCount = groups.reduce((sum, group) => sum + group.pageIds.length, 0);
  return `<section class="materials content">
    <div class="section-toolbar"><div class="title-line"><h1>${schemeMode ? roleLabel : '答卷'}</h1><span class="muted">${groups.length} 份 · ${pageCount} 页</span></div>
      <div class="toolbar-actions">${!schemeMode && groups.length ? `<details class="menu"><summary>划分 ${icon('down')}</summary><div class="menu-items">${button('equal-split', '按人数均分')}${button('file-split', '按文件分卷')}${button('select-all', selected.size === groups.length ? '取消全选' : '选择全部')}</div></details>
        ${button('sorting', '排序', { className: sorting ? 'soft active' : 'text-button', symbol: 'swap' })}${iconButton('undo', '撤销上次划分', 'undo', ctx.undo.length ? '' : 'disabled')}` : ''}
        ${[['student', '答卷'], ['question', '题目'], ['scheme', '评分标准']].map(([role, label]) => button('material-role', label, { className: materialRole === role ? 'soft active' : 'text-button blue', attrs: `data-role="${role}"` })).join('')}
      </div>
    </div>
    ${!groups.length ? empty(schemeMode ? `添加${roleLabel}` : '添加答卷', schemeMode ? (materialRole === 'question' ? '题目用于理解任务和推导评分依据，可不提供 MS。' : '上传原始评分条文，批改时将结合题目理解并保留来源。') : '上传后可调整页序和学生边界。', button(schemeMode ? `upload-${materialRole}` : 'upload-student', '上传材料', { className: 'primary' })) : ''}
    <div class="groups">${groups.map((group, groupIndex) => `<section class="answer-group ${selected.has(group.id) && !schemeMode ? 'selected' : ''}" data-group-id="${e(group.id)}">
      <div class="group-heading">${!schemeMode ? `<label class="group-check"><input type="checkbox" data-group="${e(group.id)}" ${selected.has(group.id) ? 'checked' : ''}><span>${e(group.label)}</span></label>` : `<strong>${e(group.label)}</strong>`}
        <span class="muted">${group.pageIds.length} 页</span>${!schemeMode ? iconButton('rename-group', '修改答卷名称', 'edit', `data-id="${e(group.id)}"`) : ''}
      </div>
      <div class="page-grid">${group.pageIds.map((pageId, index) => {
        const page = pageById(state, pageId);
        return `<div class="page-tile" data-page-id="${e(pageId)}" ${sorting && !schemeMode ? 'draggable="true"' : ''}>
          <button class="page-image" data-action="page" data-id="${e(pageId)}" aria-label="打开 ${e(group.label)} 第 ${index + 1} 页"><img src="${page.url}" alt="${e(page.fileName)}，原文件第 ${page.sourcePage} 页" loading="lazy" draggable="false"><span class="page-number">${index + 1}</span></button>
          ${!schemeMode ? `<div class="page-tools">${sorting ? `${iconButton('page-left', '向前移动一页', 'left', `data-id="${e(pageId)}"`)}${iconButton('page-right', '向后移动一页', 'right', `data-id="${e(pageId)}"`)}` : index > 0 ? button('split-page', '在此页前分卷', { attrs: `data-id="${e(pageId)}"`, className: 'small' }) : ''}</div>` : ''}
        </div>`;
      }).join('')}</div>
      ${!schemeMode && groupIndex < groups.length - 1 ? `<div class="boundary">${button('merge-next', icon('column-width'), { className: 'boundary-handle', attrs: `data-id="${e(group.id)}" title="移除此分界，合并下一份答卷" aria-label="合并 ${e(group.label)} 与下一份答卷"` })}</div>` : ''}
    </section>`).join('')}</div>
  </section>
  ${!schemeMode && state.groups.length ? `<form class="command-dock" id="material-command"><span class="scope">${selected.size ? `已选 ${selected.size} 份` : '选择答卷'}</span><input name="goal" aria-label="补充批改要求" placeholder="补充批改要求（可选）…" value="${e(ctx.command)}" ${!selected.size ? 'disabled' : ''} maxlength="8000">${button('manual-task', '', { className: 'icon-button', symbol: 'form', attrs: 'title="手动安排任务" aria-label="手动安排任务"', disabled: !selected.size })}<button type="submit" class="primary" ${!selected.size || ctx.busy ? 'disabled' : ''}>${ctx.busy ? '正在安排…' : '安排任务'}</button></form>` : ''}`;
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
