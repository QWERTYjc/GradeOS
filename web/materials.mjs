import { escape as e, icon, button, iconButton, empty } from './ui.mjs';
import { archiveLabels, archiveOwners, librarySections } from './grading-library.mjs';
import { taskForm } from './tasks.mjs';

export function historyLibrary(state) {
  const sections = librarySections(state, true).sort((a,b) => Number(Boolean(b.taskId)) - Number(Boolean(a.taskId)));
  const count = sections.reduce((total, section) => total + section.rows.length, 0);
  if (!count) return '';
  const row = doc => button(doc.action, `${icon('file-text')}<span>${e(doc.title)}</span><small>${e([doc.category, doc.version > 1 && 'v' + doc.version].filter(Boolean).join(' · '))}</small>`, { className:'history-file', attrs: `data-id="${e(doc.id)}" data-task="${e(doc.taskId || '')}"` });
  const folder = (title, meta, content, open = false) => `<details class="library-section"${open ? ' open' : ''}><summary>${icon('right')}<span>${e(title)}</span><small>${e(meta)}</small></summary><div class="history-contents">${content}</div></details>`;
  function batch(section) {
    const owners = archiveOwners(section.rows);
    return Object.entries(archiveLabels).map(([key,label]) => {
      const entries = owners[key];
      if (!entries.length) return '';
      const body = key === 'students' ? entries.map(student => folder(student.label,
        student.disambiguator ? '答卷 ' + student.disambiguator : student.rows.length, student.rows.map(row).join(''))).join('') : entries.map(row).join('');
      return folder(label, entries.length, body);
    }).join('');
  }
  return `<section class="intake-library"><div class="library-heading"><h2>批改归档 <small>${count}</small></h2>${sections.some(section => !section.taskId) ? button('organize-documents', '整理文档') : ''}</div>
    ${sections.map((section, index) => folder(section.title, section.rows.length + ' 项',
      section.taskId || section.rows.some(file => file.input) ? batch(section) : section.rows.map(row).join(''), Boolean(index === 0 && section.taskId))).join('')}</section>`;
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
  const categories = Object.entries(labels).map(([role, label]) => {
    const files = sources.filter(file => file.role === role);
    if (!files.length) return '';
    const rows = files.map(file => `<div class="staged-file">${icon('file-text')}<span>${e(file.name)}</span><small>${file.pages} 页</small>${iconButton('remove-uploads', `移出 ${file.name}`, 'close', `data-id="${e(file.id)}"`)}</div>`).join('');
    return `<details class="staged-category"${sources.length <= 5 ? ' open' : ''}><summary>${label}<small>${files.length}</small></summary>${rows}</details>`;
  }).join('');
  return `<section class="staged-files"><header><h2>已导入 <small>${sources.length} 个文件</small></h2>${button('remove-uploads', '全部移出')}</header>
    ${categories}</section>`;
}

function uploadStation(files, ctx) {
  const studentFiles = files.filter(file => file.role === 'student');
  const progress = ctx.uploadProgress;
  const auxiliary = (role, label) => {
    const count = files.filter(file => file.role === role).length;
    return button('upload-' + role, `${icon('file-text')}<span>${label}</span><small>${count ? `${count} 份` : '可选'}</small>${icon('plus')}`, { className: 'reference-upload', attrs: `data-upload-role="${role}"`, disabled: ctx.busy });
  };
  return `<div class="upload-station" data-upload-role="student">
    <div class="upload-copy">
    ${button('upload-student', `${icon('upload')}${studentFiles.length ? '继续添加答卷' : '选择答卷文件'}`, { className: 'station-pick', disabled: ctx.busy })}
    <p>或将全班答卷拖到这里</p></div>
  </div>
  <details class="intake-import-options"><summary>导入选项</summary><div class="upload-config"><details class="format-note"><summary>支持的文件格式</summary><p>未加密的 PDF，以及 PNG、JPEG、WebP、TIFF、BMP 图像。每个文件最多 40 MB、300 页。</p></details>
    <label>答卷分组<select id="upload-grouping"><option value="file" ${ctx.uploadGrouping !== 'manual' ? 'selected' : ''}>每个文件一份答卷</option><option value="manual" ${ctx.uploadGrouping === 'manual' ? 'selected' : ''}>导入后手动分组</option></select></label></div></details>
  ${progress ? `<div role="status" class="upload-progress"><progress max="${progress.total}" value="${progress.index}"></progress><span>正在导入 ${progress.index + 1} / ${progress.total} · ${e(progress.name)}</span></div>` : ''}
  <div class="reference-uploads">${auxiliary('scheme', '评分标准')}${auxiliary('question', '题目')}</div>`;
}

export function intakeView(ctx) {
  const { state, intakeStep: step } = ctx;
  const pending = pendingPages(state);
  const files = uploadSources(state);
  const titles = ['导入批改材料', '按学生划分答卷', '确认批改说明'];
  const go = (n, label, style = 'quiet') => button('intake-step', label, { className: style, attrs: `data-step="${n}"`, disabled: ctx.busy || (n === 2 && !files.some(file => file.role === 'student')) || (n === 3 && (!state.groups.length || pending.length)) });
  const progress = ['导入材料', '答卷分组', '批改说明'].map((label, i) => `<li ${i + 1 === step ? 'aria-current="step"' : ''}>${i + 1 < step ? go(i + 1, label) : `<span>${label}</span>`}</li>`).join('');
  let body;
  if (step === 1) {
    body = `${uploadStation(files, ctx)}${files.some(file => file.role === 'student') ? `<footer class="intake-continue">${go(2, `检查答卷分组 ${icon('right')}`, 'primary')}</footer>` : ''}${uploadsView(state)}${ctx.embedded ? '<a class="project-files-link" href="/#files" target="_top">查看项目文件 ↗</a>' : historyLibrary(state)}`;
  } else if (step === 2) {
    body = `<footer class="group-next">${go(1, '返回材料')}${go(3, `检查批改说明 ${icon('right')}`, 'primary')}</footer>${materialView(ctx, true)}`;
  } else {
    const batches = state.tasks.filter(task => task.kind === 'grade' && task.status !== 'draft');
    const filed = new Set(batches.flatMap(task => task.groupIds || []));
    const fresh = state.groups.filter(group => !filed.has(group.id));
    const groupIds = (fresh.length ? fresh : state.groups).map(group => group.id);
    const source = (documents, role) => {
      const used = new Set(batches.map(batch => batch[role]?.id));
      const candidates = fresh.length ? documents.filter(doc => !used.has(doc.id)) : documents;
      return candidates.length === 1 ? candidates[0] : null;
    };
    const draft = ctx.intakeDraft && { ...ctx.intakeDraft, groupIds: ctx.intakeDraft.materialRevision === state.materialRevision ? ctx.intakeDraft.groupIds : groupIds };
    body = `${taskForm({ ...ctx, selected: new Set(groupIds) }, draft, { allowStart:true, scheme:source(state.schemes, 'scheme'), question:source(state.questions || [], 'question') })}<footer>${go(2, '返回答卷分组')}</footer>`;
  }
  return `<section class="grading-intake intake-step-${step}"><ol class="intake-steps" aria-label="批改准备步骤">${progress}</ol><h1>${titles[step - 1]}</h1>${body}</section>`;
}

export function materialView(ctx, wizard = false) {
  const { state, selected, sorting, materialRole = 'student' } = ctx;
  if (!state.pages.length) return empty('把答卷放在这里', '上传 PDF 或照片，再按学生划分答卷。',
    `${button('upload-student', '上传答卷', { className: 'primary', symbol: 'upload' })}${button('upload-scheme', '上传评分标准', { className: 'text-button' })}${button('upload-question', '上传题目', { className: 'text-button' })}`) + '<div class="drop-hint">也可以直接拖入文件</div>';
  const schemeMode = materialRole !== 'student';
  const roleLabel = materialRole === 'question' ? '题目' : '评分标准';
  const pending = schemeMode ? [] : pendingPages(state);
  const groups = schemeMode ? (materialRole === 'question' ? state.questions || [] : state.schemes) : [...(pending.length ? [{ id: '', label: '待分组页', pageIds: pending.map(page => page.id) }] : []), ...state.groups];
  const pageMap = new Map(state.pages.map(page => [page.id, page]));
  const pageCount = groups.reduce((sum, group) => sum + group.pageIds.length, 0);
  return `<section class="materials content">
    <div class="section-toolbar"><div class="title-line"><h2>${schemeMode ? roleLabel : '学生作答'}</h2><span class="muted">${schemeMode ? groups.length : state.groups.length} 份 · ${pageCount} 页${pending.length ? ` · ${pending.length} 页待分组` : ''}</span></div>
      <div class="toolbar-actions">${!schemeMode && groups.length ? `<details class="menu"><summary>划分 ${icon('down')}</summary><div class="menu-items">${button('equal-split', '按人数均分')}${button('file-split', '按文件分卷')}${wizard ? '' : button('select-all', selected.size === state.groups.length ? '取消全选' : '选择全部')}</div></details>
        ${wizard ? button('assign-pages', ctx.pickedPages.size ? `分组（${ctx.pickedPages.size} 页）` : '分组选中页', { className: 'soft', disabled: !ctx.pickedPages.size }) : ''}
        ${button('sorting', '排序', { className: sorting ? 'soft active' : 'text-button', symbol: 'swap' })}${iconButton('undo', '撤销上次划分', 'undo', ctx.undo.length ? '' : 'disabled')}` : ''}
        ${[['student', '答卷'], ['question', '题目'], ['scheme', '评分标准']].map(([role, label]) => button('material-role', label, { className: materialRole === role ? 'soft active' : 'text-button blue', attrs: `data-role="${role}" aria-pressed="${materialRole === role}"` })).join('')}
      </div>
    </div>
    ${!groups.length ? empty(schemeMode ? `添加${roleLabel}` : '添加答卷', schemeMode ? (materialRole === 'question' ? '题目用于理解任务和推导评分依据，可不提供 MS。' : '上传原始评分条文，批改时将结合题目理解并保留来源。') : '上传后可调整页序和学生边界。', button(schemeMode ? `upload-${materialRole}` : 'upload-student', '上传材料', { className: 'primary' })) : ''}
    ${wizard && pending.length ? `<div class="pending-help"><span>勾选同一位学生的页面，再点「分组选中页」。</span>${button('group-pending','将全部待分组页归为一份')}</div>` : ''}
    <div class="groups">${groups.map(group => `<section class="answer-group ${selected.has(group.id) && !schemeMode ? 'selected' : ''}" data-group-id="${e(group.id)}">
      ${wizard ? `<details class="group-fold" ${sorting || !group.id ? 'open' : ''}><summary>${icon(group.id ? 'file-text' : 'column-width')}<strong>${e(group.label)}</strong><small>${group.pageIds.length} 页</small>${icon('down')}</summary>
        ${group.id && !schemeMode ? `<div class="group-edits">${button('rename-group', '重命名', { attrs: `data-id="${e(group.id)}"` })}${group.id !== state.groups.at(-1)?.id ? button('merge-next', '合并下一份答卷', { attrs: `data-id="${e(group.id)}"` }) : ''}</div>` : ''}` : `<div class="group-heading">${!schemeMode && group.id ? `<label class="group-check"><input type="checkbox" data-group="${e(group.id)}" ${selected.has(group.id) ? 'checked' : ''}><span>${e(group.label)}</span></label>` : `<strong>${e(group.label)}</strong>`}
        <span class="muted">${group.pageIds.length} 页</span>${!schemeMode && group.id ? iconButton('rename-group', '修改答卷名称', 'edit', `data-id="${e(group.id)}"`) : ''}</div>`}
      <div class="page-grid">${group.pageIds.map((pageId, index) => {
        const page = pageMap.get(pageId);
        const sameName = group.label === page.fileName || group.label === page.fileName?.replace(/\.[^.]+$/, '');
        const sourceLabel = sameName ? `原件第 ${page.sourcePage} 页` : `${page.fileName} · 第 ${page.sourcePage} 页`;
        return `<div class="page-tile" data-page-id="${e(pageId)}" ${sorting && !schemeMode && group.id ? 'draggable="true"' : ''}>
          ${wizard && !schemeMode ? `<label class="pick-page"><input type="checkbox" data-pick-page="${e(pageId)}" aria-label="选择 ${e(group.label)} 第 ${index+1} 页" ${ctx.pickedPages.has(pageId) ? 'checked' : ''}></label>` : ''}
          <button class="page-image" data-action="page" data-id="${e(pageId)}" aria-label="打开 ${e(group.label)} 第 ${index + 1} 页"><img src="${page.url}" alt="${e(page.fileName)}，原文件第 ${page.sourcePage} 页" loading="lazy" draggable="false"><span class="page-number">${index + 1}</span></button>
          ${wizard ? `<small class="original-page" title="${e(page.fileName)} · 原页 ${page.sourcePage}">${e(sourceLabel)}</small>` : ''}
          ${!schemeMode && group.id ? `<div class="page-tools">${sorting ? `${iconButton('page-left', '向前移动一页', 'left', `data-id="${e(pageId)}"`)}${iconButton('page-right', '向后移动一页', 'right', `data-id="${e(pageId)}"`)}` : index > 0 ? button('split-page', '在此页前分卷', { attrs: `data-id="${e(pageId)}"`, className: 'small' }) : ''}</div>` : ''}
        </div>`;
      }).join('')}</div>
      ${wizard ? '</details>' : ''}
      ${!wizard && !schemeMode && group.id && group.id !== state.groups.at(-1)?.id ? `<div class="boundary">${button('merge-next', icon('column-width'), { className: 'boundary-handle', attrs: `data-id="${e(group.id)}" title="移除此分界，合并下一份答卷" aria-label="合并 ${e(group.label)} 与下一份答卷"` })}</div>` : ''}
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
