import { uncertaintyView, escape as e, icon } from './ui.mjs';
import { documents } from './canvas-view.mjs';
import { bindSelection } from './canvas-selection.mjs';
import { DocumentEditor } from './document-editor.mjs';
import { annotationBatches, gradingAnnotations, findGradingAnnotation } from './grading-annotations.mjs';

const control = (action, label, title, disabled = false) => `<button type="button" data-pane-action="${action}" title="${e(title || label)}" aria-label="${e(title || label)}" ${disabled ? 'disabled' : ''}>${label}</button>`;
export class WorkspaceCanvas {
  constructor(root, { request, getState, onReference, toast, onChange = () => {}, onReview = () => {} }) {
    Object.assign(this, { root, request, getState, onReference, toast, onChange, onReview });
    this.panels = []; this.pending = []; this.noteDrafts = new Map(); this.mode = 'browse'; this.key = `gradeos-layout:${location.port}`;
    root.innerHTML = '<div class="workspace-panels"></div><div class="annotation-popover" hidden></div>';
    this.grid = root.querySelector('.workspace-panels'); this.popover = root.querySelector('.annotation-popover');
    this.popover.addEventListener('click', event => {
      const action = event.target.closest('[data-note-action]')?.dataset.noteAction;
      if (action) this.noteAction(action, event.target.closest('[data-note-action]').dataset.id).catch(error => this.toast(error.message));
    });
    root.addEventListener('click', event => {
      const panel = this.panels.find(row => row.id === event.target.closest('[data-pane]')?.dataset.pane);
      const node = event.target.closest('[data-pane-action]');
      if (node && panel) this.action(panel, node.dataset.paneAction, node.dataset.id).catch(error => this.toast(error.message));
    });
    window.addEventListener('beforeunload', event => { if (this.panels.some(panel => panel.editor?.dirty)) { event.preventDefault(); event.returnValue = ''; } });
    document.addEventListener('pointerdown', event => {
      if (!this.popover.hidden && !this.popover.contains(event.target) && !event.target.closest('[data-pane-action="note"]')) this.closeNote();
    });
    window.addEventListener('keydown', event => { if (event.key === 'Escape') { this.closeNote(); this.panels.forEach(panel => { panel.selection?.cancel(); if (panel.editor) panel.editor.menu.hidden = true; }); } });
    try { this.restore = JSON.parse(localStorage.getItem(this.key)); } catch { /* Start with one page. */ }
  }
  choices() {
    const state = this.getState();
    return [...documents(state).map(row => ({ value: `source:${row.id}`, label: row.role === 'scheme' ? `MS · ${row.label}` : row.role === 'question' ? `题目 · ${row.label}` : row.label, source: row })),
      ...(state.documents || []).map(row => {
        const batch = state.tasks.filter(task => task.kind === 'grade').findIndex(task => task.id === row.taskId) + 1;
        const suffix = batch && state.documents.filter(doc => doc.title === row.title).length > 1 ? ` · 批次 ${batch}` : '';
        return { value: `text:${row.id}`, label: row.title + suffix, text: row };
      })];
  }
  persist() { try { localStorage.setItem(this.key, JSON.stringify(this.panels.map(({ pageId, documentId, zoom, gradingTaskId, gradingMode }) => ({ pageId, documentId, zoom, gradingTaskId, gradingMode })))); } catch { /* Optional layout preference. */ } }
  update() {
    const state = this.getState();
    if (this.note?.row.source === 'grading' && !findGradingAnnotation(state, this.note.row.id, this.note.row.target.pageId)) this.closeNote();
    if (!this.panels.length) {
      const restored = (this.restore || []).filter(row => state.pages.some(page => page.id === row.pageId) || state.documents?.some(doc => doc.id === row.documentId)).slice(0, 4);
      this.restore = null;
      for (const item of restored) this.add(item, false);
      if (!this.panels.length && (state.pages.length || state.documents?.length)) this.add({ pageId: state.schemes[0]?.pageIds[0] || state.questions?.[0]?.pageIds[0] || state.groups[0]?.pageIds[0], documentId: !state.pages.length ? state.documents[0]?.id : null }, false);
    }
    this.root.classList.toggle('is-empty', !this.panels.length);
    if (!this.panels.length) {
      this.grid.innerHTML = `<section class="canvas-empty material-intake"><div class="intake-path" aria-label="批改流程"><span aria-current="step">1 · 准备材料</span><span>2 · 开始批改</span><span>3 · 查看结果</span></div><h1>先放入这次的答卷</h1><p>上传学生答卷即可继续，题目和 MS 都可选。</p><div class="intake-cards"><button data-action="upload-student" class="intake-student">${icon('upload')}<span><strong>上传答卷</strong><small>支持多份答卷，可在上传后调整划分</small></span><span class="intake-add">${icon('plus')}</span></button><button data-action="upload-question" class="intake-optional">${icon('file-text')}<span><strong>添加题目</strong><small>可选</small></span>${icon('plus')}</button><button data-action="upload-scheme" class="intake-optional">${icon('file-text')}<span><strong>添加 MS</strong><small>可选</small></span>${icon('plus')}</button></div><small class="intake-formats">PDF、PNG、JPEG · 单个文件最多 40 MB</small></section>`;
    }
    for (const panel of this.panels) this.renderPanel(panel);
    this.grid.dataset.count = this.panels.length; this.persist(); this.onChange();
  }
  add(item = null, render = true) {
    if (this.panels.length >= 4) { this.toast('最多同时摆放 4 个窗口；可在窗口内切换文档。'); return; }
    if (!this.panels.length) this.grid.innerHTML = '';
    if (!item) {
      const choices = this.choices(), active = this.panels.find(row => row.id === this.activeId) || this.panels[0];
      const next = choices.find(choice => choice.text ? !this.panels.some(row => row.documentId === choice.text.id) : !this.panels.some(row => choice.source.pageIds.includes(row.pageId)));
      item = next?.text ? { documentId: next.text.id } : next?.source ? { pageId: next.source.pageIds[0] } : { pageId: active?.pageId, documentId: active?.documentId };
    }
    if (!item.pageId && !item.documentId) return;
    const panel = { id: crypto.randomUUID(), zoom: 1, ...item };
    panel.root = document.createElement('section'); panel.root.className = 'workspace-pane'; panel.root.dataset.pane = panel.id;
    panel.root.innerHTML = '<div class="pane-heading"></div><div class="pane-content"></div><div class="pane-footer"></div>';
    panel.root.addEventListener('pointerdown', () => { this.activeId = panel.id; this.panels.forEach(row => row.root.classList.toggle('focused-pane', row.id === panel.id)); });
    panel.root.addEventListener('change', event => {
      if (event.target.matches('.pane-document-picker')) this.choose(panel, event.target.value).catch(error => this.toast(error.message));
      if (event.target.matches('.grading-batch-picker,.grading-mode-picker')) {
        if (event.target.matches('.grading-batch-picker')) panel.gradingTaskId = event.target.value;
        else panel.gradingMode = event.target.value;
        this.closeNote(); this.update();
      }
    });
    this.grid.append(panel.root); this.panels.push(panel); this.activeId = panel.id;
    if (render) { this.update(); panel.root.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    return panel;
  }
  async choose(panel, value) {
    if (panel.editor?.dirty) await panel.editor.save();
    const choice = this.choices().find(row => row.value === value);
    panel.pageId = choice?.source?.pageIds[0]; panel.documentId = choice?.text?.id; panel.zoom = 1;
    this.closeNote(); this.update();
  }
  async showPage(pageId, beside = false) {
    const existing = this.panels.find(row => row.pageId === pageId);
    if (existing) { this.activeId = existing.id; existing.root.scrollIntoView({ block: 'nearest', inline: 'nearest' }); return; }
    const panel = this.panels.find(row => row.id === this.activeId) || this.panels[0];
    if (beside || !panel) { this.add({ pageId }); return; }
    if (panel.editor?.dirty) await panel.editor.save();
    Object.assign(panel, { pageId, documentId: null }); this.closeNote(); this.update();
  }
  async showDocument(documentId, beside = false) {
    const existing = this.panels.find(row => row.documentId === documentId);
    if (existing) { this.activeId = existing.id; existing.root.scrollIntoView({ block: 'nearest', inline: 'nearest' }); return; }
    const panel = this.panels.find(row => row.id === this.activeId) || this.panels[0];
    if (beside || !panel) { this.add({ documentId }); return; }
    if (panel.editor?.dirty) await panel.editor.save();
    Object.assign(panel, { pageId: null, documentId }); this.closeNote(); this.update();
  }
  async showSource(pageId, besideDocument = true) {
    if (!this.getState().pages.some(page => page.id === pageId)) return;
    const source = documents(this.getState()).find(row => row.pageIds.includes(pageId));
    const panel = this.panels.find(row => source?.pageIds.includes(row.pageId)) || this.panels.find(row => row.pageId);
    if (panel) this.activeId = panel.id;
    await this.showPage(pageId, besideDocument && !panel && this.panels.length > 0 && this.panels.length < 4);
  }
  async revealRecord(record, taskId) {
    const note = gradingAnnotations(this.getState(), taskId, record.groupId).find(row => row.recordId === record.id);
    if (!note?.target) { this.toast('这条记录的原卷无法定位，请检查材料是否已调整。'); return; }
    await this.showSource(note.target.pageId, false);
    const panel = this.panels.find(row => row.pageId === note.target.pageId);
    if (!panel) return;
    panel.gradingTaskId = taskId; panel.gradingMode = 'all';
    for (const row of this.panels) row.selectedRecordId = row === panel ? record.id : null;
    this.update();
    const image = panel.root.querySelector('.canvas-paper>img');
    if (image) await image.decode().catch(() => {});
    // Only validated evidence rectangles determine a scroll target. Page-only
    // citations open the page without suggesting a precise location.
    const scroll = panel.root.querySelector('.pane-page-scroll'), paper = panel.root.querySelector('.canvas-paper');
    if (!scroll || !paper || panel.pageId !== note.target.pageId || panel.selectedRecordId !== record.id) return;
    const top = note.location === 'region' ? Math.min(...note.regions.map(region => region.rect.y)) * paper.getBoundingClientRect().height : 0;
    scroll.scrollTo({ top: Math.max(0, top - scroll.clientHeight * .25), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }
  setMode(mode) { this.panels.forEach(panel => panel.selection?.cancel()); this.closeNote(); this.mode = this.mode === mode ? 'browse' : mode; this.update(); }
  annotations(panel) {
    return [...(this.getState().annotations || []).filter(row => !row.archivedAt && (panel.documentId ? row.target.documentId === panel.documentId : row.target.pageId === panel.pageId)),
      ...this.pending.filter(row => panel.documentId ? row.target.documentId === panel.documentId : row.target.pageId === panel.pageId),
      ...this.gradingRows(panel).filter(row => panel.gradingMode !== 'hidden' && (panel.gradingMode !== 'issues' || row.hasIssue))];
  }
  gradingRows(panel) {
    if (panel.documentId) return [];
    const state = this.getState(), batches = annotationBatches(state, panel.pageId);
    const task = batches.find(task => task.id === panel.gradingTaskId) || batches.at(-1);
    const group = task?.groups.find(group => group.pageIds.includes(panel.pageId));
    return task && group ? gradingAnnotations(state, task.id, group.id, panel.pageId) : [];
  }
  renderPanel(panel) {
    const state = this.getState(), page = state.pages.find(row => row.id === panel.pageId), doc = state.documents?.find(row => row.id === panel.documentId);
    const source = documents(state).find(row => row.pageIds.includes(panel.pageId)), pageIndex = source?.pageIds.indexOf(panel.pageId);
    const heading = panel.root.querySelector('.pane-heading');
    const value = doc ? `text:${doc.id}` : `source:${source?.id}`;
    const html = `<div class="pane-document">${icon('file-text')}<select class="pane-document-picker" aria-label="窗口 ${this.panels.indexOf(panel) + 1} 的文档">${this.choices().map(choice => `<option value="${e(choice.value)}" ${choice.value === value ? 'selected' : ''}>${e(choice.label)}</option>`).join('')}</select></div>${source ? `<div class="pane-pager">${control('previous', icon('left'), '上一页', pageIndex === 0)}<span>${pageIndex + 1}<small> / ${source.pageIds.length}</small></span>${control('next', icon('right'), '下一页', pageIndex === source.pageIds.length - 1)}</div>` : '<div class="pane-editor-tools"></div>'}${this.panels.length > 1 ? control('close', icon('close'), '关闭这个窗口') : ''}`;
    if (panel.headingHTML !== html) { heading.innerHTML = html; panel.headingHTML = html; }
    heading.querySelector('select').value = value;
    const content = panel.root.querySelector('.pane-content'), key = doc ? `doc:${doc.id}` : `page:${page?.id}`;
    if (panel.contentKey !== key) {
      panel.selection?.destroy(); panel.editor?.destroy(); panel.selection = null; panel.editor = null; panel.contentKey = key; panel.pinsHTML = null;
      if (page) {
        content.innerHTML = `<div class="pane-page-scroll"><div class="canvas-paper"><img src="${page.url}" alt="${e(page.fileName)}，原文件第 ${page.sourcePage} 页" draggable="false"><canvas aria-label="在原页自由套索"></canvas><div class="annotation-pins"></div></div></div>`;
        panel.selection = bindSelection(content.querySelector('canvas'), { getPage: () => this.getState().pages.find(row => row.id === panel.pageId), getMode: () => this.mode,
          getSelections: () => this.annotations(panel).filter(row => row.source !== 'grading' || row.location === 'region')
            .sort((a, b) => Number(b.source === 'grading') - Number(a.source === 'grading'))
            .flatMap(row => (row.source === 'grading' && row.regions?.length ? row.regions : [row.target])
              .map((target,index) => ({ ...target, id: `${row.id}:${index}`, annotationId:row.id, generated: row.source === 'grading',tone:row.tone }))),
          getActiveId: () => this.note?.panel === panel ? this.note.row.id : null,
          onActivate: target => {
            const row = target && this.annotations(panel).find(row => row.id === (target.annotationId || target.id));
            if (row) this.openNote(panel, row); else this.closeNote();
          }, onHover: id => {
            for (const pin of panel.root.querySelectorAll('[data-pin]')) pin.classList.toggle('is-hovered', pin.dataset.pin === id);
          }, onInvalid: this.toast, onSelect: target => {
            const row = { id: target.id, target: { ...target, kind: 'page' }, text: '', pending: true }; this.pending.push(row);
            this.closeNote(); this.renderPins(panel);
          } });
        content.querySelector('.pane-page-scroll').addEventListener('scroll', () => { if (this.note?.panel === panel) this.closeNote(); }, { passive: true });
      } else if (doc) {
        content.innerHTML = '<div class="document-editor"></div><div class="document-annotations"></div>';
        panel.editor = new DocumentEditor(content.querySelector('.document-editor'), { id: doc.id, request: this.request, getState: this.getState, toast: this.toast, onLayout: () => this.renderPins(panel),
          onReference: this.onReference, onComment: (target, anchor) => {
            const row = { id: crypto.randomUUID(), target, text: '', pending: true }; this.pending.push(row); this.renderPins(panel); this.openNote(panel, row, anchor);
          }, onSource: number => { const scheme = this.getState().schemes.find(row => row.id === doc.schemeId); if (scheme?.pageIds[number - 1]) this.showPage(scheme.pageIds[number - 1], true).catch(error => this.toast(error.message)); } });
      }
    }
    if (page) {
      const paper = content.querySelector('.canvas-paper');
      content.querySelector('.pane-page-scroll').classList.toggle('has-grading-notes', this.gradingRows(panel).length > 0 && panel.gradingMode !== 'hidden');
      paper.style.width = `${panel.zoom * 100}%`; paper.style.maxWidth = `${800 * panel.zoom}px`;
      const canvas = content.querySelector('canvas');
      if (canvas.dataset.mode !== this.mode) {
        canvas.style.touchAction = this.mode === 'browse' ? 'auto' : 'none';
        canvas.style.cursor = this.mode === 'browse' ? 'default' : 'crosshair'; canvas.dataset.mode = this.mode;
      }
      panel.selection?.draw();
    }
    if (doc) { panel.editor?.mountControls(heading.querySelector('.pane-editor-tools')); panel.editor?.sync(doc); }
    const approval = doc?.approvals?.at(-1);
    const batch = state.tasks.filter(task => task.kind === 'grade').findIndex(task => task.id === doc?.taskId) + 1;
    const batches = page ? annotationBatches(state, page.id) : [], notes = this.gradingRows(panel);
    const selectedBatch = batches.find(task => task.id === panel.gradingTaskId) || batches.at(-1);
    const gradingControls = batches.length ? `<div class="grading-controls"><select class="grading-batch-picker" aria-label="批注所属批次">${batches.map(task => `<option value="${e(task.id)}" ${task.id === selectedBatch.id ? 'selected' : ''}>批次 ${state.tasks.filter(row => row.kind === 'grade').findIndex(row => row.id === task.id) + 1}</option>`).join('')}</select><select class="grading-mode-picker" aria-label="评分批注显示范围"><option value="all" ${!panel.gradingMode || panel.gradingMode === 'all' ? 'selected' : ''}>批注 ${notes.length}</option><option value="issues" ${panel.gradingMode === 'issues' ? 'selected' : ''}>只看疑点</option><option value="hidden" ${panel.gradingMode === 'hidden' ? 'selected' : ''}>隐藏批注</option></select></div>` : '';
    const exportGroup=selectedBatch?.groups.find(group=>group.pageIds.includes(page?.id));
    const exportLink=exportGroup?`<a class="annotation-export" href="/api/tasks/${e(selectedBatch.id)}/annotated.pdf?groupId=${e(exportGroup.id)}" target="_blank" rel="noopener" title="打开带原卷、位置框和批注正文的 PDF，可直接打印">打印 / PDF</a>`:'';
    const footerHTML = doc ? approval ? `<span>批次 ${batch} 采用 v${approval.revision}${approval.revision !== doc.revision ? ' · 当前编辑用于后续批次' : ''}</span>` : '' : `${gradingControls}${exportLink}<div>${control('zoom-out', icon('minus'), '缩小')}${control('zoom-reset', `${Math.round(panel.zoom * 100)}%`, '适合宽度')}${control('zoom-in', icon('plus'), '放大')}</div>`;
    if (panel.footerHTML !== footerHTML) { panel.root.querySelector('.pane-footer').innerHTML = footerHTML; panel.footerHTML = footerHTML; }
    this.renderPins(panel);
  }
  async approveDocument(documentId) {
    const panels = this.panels.filter(panel => panel.documentId === documentId && panel.editor);
    if (!panels.length) { await this.showDocument(documentId); this.toast('请查看评分要求后再确认。'); return; }
    let doc;
    for (const panel of panels) doc = await panel.editor.save();
    if (!doc) throw Error('文档仍在读取，请稍后确认。');
    await this.request(`/api/documents/${doc.id}/approve`, { revision: doc.revision, hash: doc.hash });
    this.toast(`已确认 v${doc.revision}，开始批改本批答卷。`);
  }
  renderPins(panel) {
    const rows = this.annotations(panel), pins = panel.root.querySelector(panel.documentId ? '.document-annotations' : '.annotation-pins');
    if (!pins) return;
    const content = rows.map((row, index) => row.source === 'grading'
      ? `<div class="annotation-pin grading-pin ${row.tone} ${row.recordId === panel.selectedRecordId ? 'selected-grading-pin' : ''}" data-pin="${e(row.id)}"><button type="button" class="grading-marker" aria-label="查看评分批注 ${e(row.label)}，${e(row.scoreLabel)}" title="${e(row.label)} · ${e(row.status)} · 点击展开页边批注" data-pane-action="note" data-id="${e(row.id)}"><span>${e(row.label.replace(' · ', ' '))}</span><small>${e(row.scoreLabel)}</small></button></div>`
      : `<div class="annotation-pin ${row.pending ? 'pending' : ''}" data-pin="${e(row.id)}"><button type="button" class="${panel.documentId ? 'annotation-marker' : 'annotation-target'}" aria-label="${row.pending ? '添加' : '查看'}注释 ${index + 1}" data-pane-action="note" data-id="${e(row.id)}" ${panel.documentId ? 'title="查看文字注释"' : ''}>${panel.documentId ? icon('message') : ''}</button><button type="button" class="annotation-remove" data-pane-action="remove-note" data-id="${e(row.id)}" aria-label="移除注释 ${index + 1}" title="移除这处圈注">×</button></div>`).join('');
    if (panel.pinsHTML !== content) { pins.innerHTML = content; panel.pinsHTML = content; }
    let gradingIndex = 0, previousGradingTop = -12;
    const paperHeight = panel.root.querySelector('.canvas-paper')?.getBoundingClientRect().height || 800;
    const gap = Math.max(32, Math.min(44, (paperHeight - 60) / Math.max(1, rows.filter(row => row.source === 'grading').length)));
    if (!panel.documentId) for (const node of pins.children) {
      const row = rows.find(row => row.id === node.dataset.pin), rect = row.target.rect;
      if (row.source === 'grading') {
        const top = row.location === 'region' ? (row.regions?.[0] || row.target).rect.y * paperHeight : 36 + gradingIndex * gap;
        node.style.left = 'calc(100% + 8px)'; node.style.top = `${Math.max(previousGradingTop + gap, top)}px`;
        previousGradingTop = Math.max(previousGradingTop + gap, top); gradingIndex++;
        continue;
      }
      node.style.left = `${rect.x * 100}%`; node.style.top = `${rect.y * 100}%`;
      node.style.width = `${rect.width * 100}%`; node.style.height = `${rect.height * 100}%`;
    }
    else {
      let previousTop = 40;
      for (const node of pins.children) {
        const row = rows.find(row => row.id === node.dataset.pin), top = panel.editor ? panel.editor.annotationTop(row.target) : 60;
        if (top === null) { node.hidden = true; continue; }
        node.hidden = top < 35 || top > panel.root.querySelector('.pane-content').clientHeight - 30;
        node.style.top = `${Math.max(previousTop, top)}px`; previousTop = Math.max(previousTop, top) + 30;
      }
    }
    for (const node of pins.children) {
      const active = this.note?.panel === panel && this.note.row.id === node.dataset.pin;
      node.classList.toggle('is-active', active); node.querySelector('[data-pane-action="note"]').setAttribute('aria-expanded', String(active));
    }
    panel.selection?.draw();
  }
  closeNote() {
    if (this.note && !this.popover.hidden && this.popover.querySelector('textarea')) this.noteDrafts.set(this.note.row.id, this.popover.querySelector('textarea').value);
    this.popover.hidden = true; this.note = null;
    for (const panel of this.panels) this.renderPins(panel);
  }
  openNote(panel, row, anchor = null) {
    this.closeNote();
    this.note = { panel, row };
    const target = row.target;
    const bounds = panel.root.querySelector(`[data-pin="${CSS.escape(row.id)}"]`)?.getBoundingClientRect() || panel.root.getBoundingClientRect();
    const x = anchor?.x ?? (bounds.right + 310 < window.innerWidth ? bounds.right + 12 : bounds.left), y = anchor?.y ?? bounds.bottom + 10;
    if (row.source === 'grading') {
      const pages = this.getState().pages;
      const links = (ids, label) => ids.map(id => `<button type="button" data-note-action="source" data-id="${e(id)}">${label} ${e(pages.find(page => page.id === id)?.sourcePage)} 页 ↗</button>`).join('');
      this.popover.innerHTML = `<div class="annotation-heading"><span>评分批注 · 第 ${target.sourcePage} 页</span><button type="button" data-note-action="close" aria-label="收起注释">×</button></div><div class="grading-note-title ${row.tone}"><strong>${e(row.label)}</strong><span>${e(row.scoreLabel)}</span></div><div class="grading-note-body">${row.basisLabel ? `<p class="muted">${e(row.basisLabel)}</p>` : ''}<section><h4>答卷依据</h4><p>${e(row.evidence || '未提供可引用证据，需核对答卷。')}</p></section><section><h4>评分条件</h4><p>${e(row.sourceText || '未提供，需核对 MS。')}</p></section><section><h4>${row.review ? `原始判定 · ${e(row.originalScoreLabel)}` : row.status}</h4><p>${e(row.reason)}</p></section>${uncertaintyView(row)}${row.review ? `<section><h4>老师复核 · ${e(row.scoreLabel)}</h4><p>${e(row.review.reason)}</p></section>` : ''}<div class="grading-source-links">${links(row.schemePageIds, 'MS')}${links(row.questionPageIds || [], '题目')}${links(row.studentPageIds.filter(id => id !== panel.pageId), '答卷')}</div><p class="grading-note-provenance">${row.guide ? `本批采用评分实施.md v${row.guide.revision} · ` : ''}来自已保存的批改结果<br>${row.location === 'region' ? (row.locationOrigin === 'inline-grading' ? `批改时同步定位 · ${row.regions.length} 处笔迹` : '按需定位的笔迹区域') : '页边批注，未定位到具体笔迹'}</p></div><div class="annotation-actions"><button type="button" data-note-action="reference">${icon('plus')}添加到对话</button><button type="button" data-note-action="review">审阅评分</button></div>`;
      this.popover.hidden = false;
      this.popover.style.left = `${Math.max(12, Math.min(window.innerWidth - 310, x - 300))}px`;
      this.popover.style.top = `${Math.max(72, Math.min(window.innerHeight - Math.min(490, this.popover.offsetHeight) - 12, bounds.top))}px`;
      this.renderPins(panel); return;
    }
    this.popover.innerHTML = `<div class="annotation-heading"><span>${target.kind === 'text' ? `文字注释 · v${target.revision}` : `第 ${target.sourcePage} 页 · ${target.shape === 'lasso' ? '套索' : '框选'}`}</span><button type="button" data-note-action="close" aria-label="收起注释">×</button></div>${target.kind === 'text' ? `<blockquote>${e(target.quote.slice(0, 160))}</blockquote>` : ''}<textarea aria-label="注释内容" placeholder="写下这处的说明…" rows="3" maxlength="8000">${e(this.noteDrafts.get(row.id) ?? row.text)}</textarea><div class="annotation-actions"><button type="button" data-note-action="reference">${icon('plus')}添加到对话</button><button type="button" class="primary" data-note-action="save">保存注释</button></div>`;
    this.popover.hidden = false;
    this.popover.style.left = `${Math.max(12, Math.min(window.innerWidth - 310, x))}px`;
    this.popover.style.top = `${Math.max(72, Math.min(window.innerHeight - 365, y))}px`;
    this.renderPins(panel);
    this.popover.querySelector('textarea').focus({ preventScroll: true });
  }
  async noteAction(action, id) {
    if (action === 'close') { this.closeNote(); return; }
    if (this.noteSaving || !this.note) return;
    if (this.note.row.source === 'grading') {
      const row = this.note.row;
      if (action === 'reference') this.onReference({ annotationId: row.id, target: row.target, comment: row.text });
      if (action === 'review') this.onReview(row.recordId);
      this.closeNote();
      if (action === 'source') await this.showPage(id, true);
      return;
    }
    const { row, panel } = this.note, text = this.popover.querySelector('textarea').value.trim();
    let saved = row; this.noteSaving = true;
    try {
      if (action === 'save' || text !== row.text) {
        if (!text) { if (action === 'save') throw Error('写下一句注释后保存。'); }
        else {
          const result = await this.request(row.pending ? '/api/annotations' : `/api/annotations/${row.id}`, { target: row.target, text }, row.pending ? 'POST' : 'PATCH');
          saved = result.annotation;
          if (row.pending) this.pending = this.pending.filter(item => item.id !== row.id);
        }
      }
      if (action === 'reference') this.onReference(saved.pending ? { target: row.target } : { annotationId: saved.id, target: saved.target, comment: text });
      if (this.note?.row.id === row.id) this.closeNote();
      this.noteDrafts.delete(row.id); this.renderPins(panel);
    } finally { this.noteSaving = false; }
  }
  async action(panel, action, id) {
    const rows = this.annotations(panel), row = rows.find(row => row.id === id);
    if (action === 'note' && row) { if (panel.editor) panel.editor.focusTarget(row.target); this.openNote(panel, row); }
    if (action === 'remove-note' && row) {
      if (row.pending) this.pending = this.pending.filter(item => item.id !== id);
      else await this.request(`/api/annotations/${id}`, { archive: true }, 'PATCH');
      if (this.note?.row.id === id) this.closeNote();
      this.noteDrafts.delete(id);
      this.renderPins(panel);
    }
    if (action === 'previous' || action === 'next') {
      const doc = documents(this.getState()).find(row => row.pageIds.includes(panel.pageId));
      panel.pageId = doc.pageIds[doc.pageIds.indexOf(panel.pageId) + (action === 'previous' ? -1 : 1)]; this.closeNote(); this.update();
    }
    if (action.startsWith('zoom')) { panel.zoom = action === 'zoom-reset' ? 1 : Math.max(.6, Math.min(2, panel.zoom + (action === 'zoom-in' ? .2 : -.2))); this.update(); }
    if (action === 'close') {
      if (panel.editor?.dirty) await panel.editor.save();
      panel.editor?.destroy(); panel.selection?.destroy(); panel.root.remove(); this.panels = this.panels.filter(row => row.id !== panel.id);
      this.activeId = this.panels[0]?.id; this.closeNote(); this.update();
    }
    if (action === 'approve') {
      await this.approveDocument(panel.documentId);
    }
  }
}
