import { escape as e, icon } from './ui.mjs';
import { documents, needsGradingMaterials } from './canvas-view.mjs';
import { bindSelection } from './canvas-selection.mjs';
import { DocumentEditor } from './document-editor.mjs';
import { annotationBatches, gradingAnnotations, findGradingAnnotation } from './grading-annotations.mjs';
import {gradingCard} from './annotation-card.mjs';
import {occupancyFromRgba,relatedGradingNotes,gradingConnection,layoutPointComments,pointCommentContent,layoutGradingSymbols,symbolSvg} from './annotation-layout.mjs';
import {PageStream} from './page-stream.mjs';
import {gradingResult,resultDocument} from './grading-result.mjs';

const control = (action, label, title, disabled = false) => `<button type="button" data-pane-action="${action}" title="${e(title || label)}" aria-label="${e(title || label)}" ${disabled ? 'disabled' : ''}>${label}</button>`;
function sourceForPage(state, pageId) {
  const source = documents(state).find(row => row.pageIds.includes(pageId));
  if (source) return source;
  const page = state.pages.find(row => row.id === pageId);
  if (!page) return null;
  const siblings = state.pages.filter(row => row.sourceId === page.sourceId && row.active === page.active);
  return { id: 'upload-' + page.sourceId, label: page.fileName, role: page.role, pageIds: siblings.map(row => row.id), original: true };
}
export class WorkspaceCanvas {
  constructor(root, { request, getState, onReference, toast, onChange = () => {}, onReview = () => {}, onResultDocument = () => {} }) {
    Object.assign(this, { root, request, getState, onReference, toast, onChange, onReview, onResultDocument });
    this.panels = []; this.pending = []; this.noteDrafts = new Map(); this.mode = 'browse'; this.key = `gradeos-layout:${location.port}`;
    root.innerHTML = '<div class="workspace-panels"></div><div class="annotation-popover" role="dialog" aria-label="批注详情" tabindex="-1" hidden></div>';
    this.intake = document.createElement('div');
    this.intake.className = 'intake-surface';
    root.prepend(this.intake);
    this.readDocuments = false;
    this.grid = root.querySelector('.workspace-panels'); this.popover = root.querySelector('.annotation-popover');
    this.popover.addEventListener('click', event => {
      const action = event.target.closest('[data-note-action]')?.dataset.noteAction;
      if (action) this.noteAction(action, event.target.closest('[data-note-action]').dataset.id).catch(error => this.toast(error.message));
    });
    root.addEventListener('click', event => {
      const panel = this.eventSurface(event.target);
      const node = event.target.closest('[data-pane-action]');
      if (node && panel) this.action(panel, node.dataset.paneAction, node.dataset.id).catch(error => this.toast(error.message));
    });
    root.addEventListener('pointerover',event=>{
      const marker=event.target.closest('.grading-point-comment,.grading-symbol'),panel=marker&&this.eventSurface(marker);
      if(panel){panel.hoveredId=marker.dataset.id;panel.selection?.draw();}
      const result=event.target.closest('[data-result-point]');if(result)this.hoverResult(result.dataset.resultPoint);
    });
    root.addEventListener('pointerout',event=>{
      const marker=event.target.closest('.grading-point-comment,.grading-symbol'),panel=marker&&this.eventSurface(marker);
      if(panel&&!marker.contains(event.relatedTarget)){panel.hoveredId=null;panel.selection?.draw();}
      const result=event.target.closest('[data-result-point]');if(result&&!result.contains(event.relatedTarget))this.hoverResult(null);
    });
    window.addEventListener('beforeunload', event => { if (this.panels.some(panel => panel.editor?.dirty)) { event.preventDefault(); event.returnValue = ''; } });
    document.addEventListener('click', event => {
      if (!this.popover.hidden && !event.composedPath().includes(this.popover) && !event.target.closest('[data-pane-action="note"],.canvas-paper canvas')) this.closeNote();
    });
    window.addEventListener('keydown', event => { if (event.key === 'Escape') { this.closeNote(true); this.allSurfaces().forEach(panel => { panel.selection?.cancel(); if (panel.editor) panel.editor.menu.hidden = true; }); } });
    window.addEventListener('resize',()=>requestAnimationFrame(()=>{for(const panel of this.panels)this.renderPanel(panel);this.positionNote();}));
    // Opening details or another document changes the available width without
    // a window resize. Refit the page and its point column together.
    this.layoutObserver=new ResizeObserver(([entry])=>{
      const width=entry.contentRect.width;
      if(Math.abs(width-(this.layoutWidth??0))<1)return;
      this.layoutWidth=width;
      requestAnimationFrame(()=>{for(const panel of this.panels)this.renderPanel(panel);this.positionNote();});
    });
    this.layoutObserver.observe(this.grid);
    this.popover.addEventListener('toggle',()=>this.positionNote(),true);
    try { this.restore = JSON.parse(localStorage.getItem(this.key)); } catch { /* Start with one page. */ }
  }
  allSurfaces(){return this.panels.flatMap(p=>p.stream?[...p.stream.views.values()]:[p]);}
  eventSurface(node){const panel=this.panels.find(p=>p.id===node.closest('[data-pane]')?.dataset.pane);return panel?.stream?.views.get(node.closest('[data-page-surface]')?.dataset.pageSurface)||panel;}
  hoverResult(id){for(const view of this.allSurfaces()){view.hoveredId=id;view.selection?.draw();}}
  async showResults(taskId,groupId){
    const active=this.panels.find(p=>p.id===this.activeId),state=this.getState();
    const answer=state.groups.some(g=>g.pageIds.includes(active?.pageId))?active:this.panels.find(p=>state.groups.some(g=>g.pageIds.includes(p.pageId)));
    const task=state.tasks.find(t=>t.id===(taskId||active?.resultTaskId))||state.tasks.findLast(t=>t.kind==='grade'&&t.records?.length&&t.groups?.some(g=>g.pageIds.includes(answer?.pageId)))||state.tasks.findLast(t=>t.kind==='grade'&&t.records?.length);
    const group=task?.groups.find(g=>g.id===(groupId||active?.resultGroupId))||task?.groups.find(g=>g.pageIds.includes(answer?.pageId))||task?.groups[0];
    if(!group)return;
    this.onResultDocument();
    const existing=this.panels.find(p=>p.resultTaskId===task.id&&p.resultGroupId===group.id);
    if(existing){this.activeId=existing.id;existing.root.scrollIntoView({block:'nearest',inline:'nearest'});return;}
    const comparison=this.panels.findLast(p=>!group.pageIds.includes(p.pageId));
    if(comparison&&this.panels.length>1){
      if(comparison.editor?.dirty)await comparison.editor.save();
      Object.assign(comparison,{pageId:null,documentId:null,resultTaskId:task.id,resultGroupId:group.id});this.closeNote();this.activeId=comparison.id;this.update();return;
    }
    this.add({resultTaskId:task.id,resultGroupId:group.id});
  }
  async showPoint(id){
    const row=findGradingAnnotation(this.getState(),id);if(!row?.target)return;
    this.closeNote();await this.showPage(row.target.pageId,true);
    const panel=this.panels.find(p=>p.stream?.views.has(row.target.pageId)),view=panel?.stream?.views.get(row.target.pageId);if(!view)return;
    view.focusedPointId=row.id;view.selection?.draw();
    const paper=view.root.querySelector('.canvas-paper'),bounds=paper.getBoundingClientRect(),region=row.regions[0]?.rect;
    if(region){const scroll=panel.stream.scroll;scroll.scrollTop+=bounds.top+region.y*bounds.height-scroll.getBoundingClientRect().top-80;}
  }
  choices() {
    const state = this.getState();
    const visibleOriginals = new Map();
    for (const panel of this.panels) {
      const source = sourceForPage(state, panel.pageId);
      if (source?.original) visibleOriginals.set(source.id, source);
    }
    return [...[...documents(state), ...visibleOriginals.values()].map(row => ({ value: `source:${row.id}`, label: row.role === 'scheme' ? `MS · ${row.label}` : row.role === 'question' ? `题目 · ${row.label}` : row.label, source: row })),
      ...state.tasks.filter(t=>t.kind==='grade'&&t.records?.length).flatMap(task=>task.groups.map(group=>({value:`result:${task.id}:${group.id}`,label:`批改结果 · ${group.label}`,result:{taskId:task.id,groupId:group.id}}))),
      ...(state.documents || []).map(row => {
        const batch = state.tasks.filter(task => task.kind === 'grade').findIndex(task => task.id === row.taskId) + 1;
        const suffix = batch && state.documents.filter(doc => doc.title === row.title).length > 1 ? ` · 批次 ${batch}` : '';
        return { value: `text:${row.id}`, label: row.title + suffix, text: row };
      })];
  }
  persist() { try { localStorage.setItem(this.key, JSON.stringify(this.panels.map(({ pageId, documentId, resultTaskId,resultGroupId,readMode,zoom, gradingTaskId, gradingMode }) => ({ pageId, documentId,resultTaskId,resultGroupId,readMode, zoom, gradingTaskId, gradingMode })))); } catch { /* Optional layout preference. */ } }
  update() {
    const state = this.getState();
    if (this.note?.row.source === 'grading' && !findGradingAnnotation(state, this.note.row.id, this.note.row.target.pageId)) this.closeNote();
    const showIntake = !this.readDocuments && (this.prepareBatch || needsGradingMaterials(state));
    this.intake.hidden = !showIntake;
    this.grid.hidden = showIntake;
    this.root.classList.toggle('is-empty', showIntake);
    if (showIntake) {
      this.onChange();
      return;
    }
    if (!this.panels.length) {
      const restored = (this.restore || []).filter(row => state.pages.some(page => page.id === row.pageId) || state.documents?.some(doc => doc.id === row.documentId)||gradingResult(state,row.resultTaskId,row.resultGroupId)).slice(0, 4);
      this.restore = null;
      for (const item of restored) this.add(item, false);
      if (!this.panels.length && (state.pages.length || state.documents?.length)) this.add({ pageId: state.schemes[0]?.pageIds[0] || state.questions?.[0]?.pageIds[0] || state.groups[0]?.pageIds[0], documentId: !state.pages.length ? state.documents[0]?.id : null }, false);
    }
    for (const panel of this.panels) this.renderPanel(panel);
    this.grid.dataset.count = this.panels.length; this.persist(); this.onChange();
  }
  add(item = null, render = true) {
    if (this.panels.length >= 4) { this.toast('最多同时摆放 4 个窗口；可在窗口内切换文档。'); return; }
    if (!this.panels.length) this.grid.innerHTML = '';
    if (!item) {
      const choices = this.choices(), active = this.panels.find(row => row.id === this.activeId) || this.panels[0];
      const next = choices.find(choice => choice.text ? !this.panels.some(row => row.documentId === choice.text.id) : choice.source&&!this.panels.some(row => choice.source.pageIds.includes(row.pageId)));
      item = next?.text ? { documentId: next.text.id } : next?.source ? { pageId: next.source.pageIds[0] } : { pageId: active?.pageId, documentId: active?.documentId };
    }
    if (!item.pageId && !item.documentId&&!item.resultTaskId) return;
    const panel = { id: crypto.randomUUID(), zoom: 1, readMode:'continuous', ...item };
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
      if(event.target.matches('.reading-mode-picker')){panel.readMode=event.target.value;this.closeNote();this.update();}
    });
    this.grid.append(panel.root); this.panels.push(panel); this.activeId = panel.id;
    if (render) { this.update(); panel.root.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    return panel;
  }
  async choose(panel, value) {
    if (panel.editor?.dirty) await panel.editor.save();
    const choice = this.choices().find(row => row.value === value);
    if(choice?.result)this.onResultDocument();
    panel.pageId = choice?.source?.pageIds[0]; panel.documentId = choice?.text?.id; panel.resultTaskId=choice?.result?.taskId;panel.resultGroupId=choice?.result?.groupId;panel.zoom = 1;
    this.closeNote(); this.update();
  }
  async showPage(pageId, beside = false) {
    const source=sourceForPage(this.getState(), pageId);
    const existing = this.panels.find(row => row.pageId === pageId)||this.panels.find(row=>source?.pageIds.includes(row.pageId));
    if (existing) { existing.pageId=pageId;this.renderPanel(existing);existing.stream?.go(pageId);this.activeId = existing.id; existing.root.scrollIntoView({ block: 'nearest', inline: 'nearest' });this.persist(); return; }
    const panel = this.panels.find(row => row.id === this.activeId) || this.panels[0];
    if(beside){const comparison=this.panels.find(p=>p.resultTaskId);if(comparison&&source?.role!=='student'){Object.assign(comparison,{pageId,documentId:null,resultTaskId:null,resultGroupId:null});this.closeNote();this.update();return;}}
    if (beside || !panel) { this.add({ pageId }); return; }
    if (panel.editor?.dirty) await panel.editor.save();
    Object.assign(panel, { pageId, documentId: null,resultTaskId:null,resultGroupId:null }); this.closeNote(); this.update();
  }
  async showDocument(documentId, beside = false) {
    this.readDocuments = true;
    const existing = this.panels.find(row => row.documentId === documentId);
    if (existing) { if (!this.intake.hidden) this.update(); this.activeId = existing.id; existing.root.scrollIntoView({ block: 'nearest', inline: 'nearest' }); return; }
    const panel = this.panels.find(row => row.id === this.activeId) || this.panels[0];
    if (beside || !panel) { this.add({ documentId }); return; }
    if (panel.editor?.dirty) await panel.editor.save();
    Object.assign(panel, { pageId: null, documentId,resultTaskId:null,resultGroupId:null }); this.closeNote(); this.update();
  }
  async showSource(pageId, besideDocument = true) {
    if (!this.getState().pages.some(page => page.id === pageId)) return;
    const source=sourceForPage(this.getState(), pageId);
    const panel=this.panels.find(row=>source?.pageIds.includes(row.pageId));
    if(panel)this.activeId=panel.id;
    const compare=source?.role!=='student'&&this.panels.some(row=>this.getState().groups.some(g=>g.pageIds.includes(row.pageId)));
    await this.showPage(pageId,compare||(besideDocument&&!panel&&this.panels.length>0&&this.panels.length<4));
  }
  clearRecordHighlight(){for(const view of this.allSurfaces()){view.focusedPointId=null;view.selection?.draw();}}
  async revealRecord(record,taskId) {
    const note=gradingAnnotations(this.getState(),taskId,record.groupId).find(row=>row.recordId===record.id);
    if(!note?.target){this.toast('这条记录的原卷无法定位，请检查材料是否已调整。');return;}
    this.closeNote();await this.showSource(note.target.pageId,false);
    const panel=this.panels.find(row=>row.pageId===note.target.pageId);if(!panel)return;
    panel.gradingTaskId=taskId;panel.gradingMode='all';panel.selectedRecordId=record.id;this.update();
    const view=panel.stream?.views.get(note.target.pageId);if(!view)return;
    const image=view.root.querySelector('.canvas-paper>img');if(image)await image.decode().catch(()=>{});
    if(panel.pageId!==note.target.pageId||panel.selectedRecordId!==record.id)return;
    view.focusedPointId=note.id;view.selection?.draw();
    const scroll=panel.stream.scroll,paper=view.root.querySelector('.canvas-paper'),box=paper.getBoundingClientRect();
    const local=note.location==='region'?Math.min(...note.regions.map(region=>region.rect.y))*box.height:0;
    scroll.scrollTo({top:Math.max(0,scroll.scrollTop+box.top-scroll.getBoundingClientRect().top+local-scroll.clientHeight*.25),behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  setMode(mode) { this.allSurfaces().forEach(panel => panel.selection?.cancel()); this.closeNote(); this.mode = this.mode === mode ? 'browse' : mode; this.update(); }
  annotations(panel) {
    return [...(this.getState().annotations || []).filter(row => !row.archivedAt && (panel.documentId ? row.target.documentId === panel.documentId : row.target.pageId === panel.pageId)),
      ...this.pending.filter(row => panel.documentId ? row.target.documentId === panel.documentId : row.target.pageId === panel.pageId),
      ...this.gradingRows(panel).filter(row => panel.gradingMode !== 'hidden' && (panel.gradingMode !== 'issues' || row.hasIssue))];
  }
  gradingRows(panel) {
    if (panel.documentId||panel.resultTaskId) return [];
    const state = this.getState(), batches = annotationBatches(state, panel.pageId);
    const task = batches.find(task => task.id === panel.gradingTaskId) || batches.at(-1);
    const group = task?.groups.find(group => group.pageIds.includes(panel.pageId));
    return task && group ? gradingAnnotations(state, task.id, group.id, panel.pageId) : [];
  }
  mountPage(panel,page,content) {
        content.innerHTML = `<div class="canvas-paper"><img loading="lazy" src="${page.url}" alt="${e(page.fileName)}，原文件第 ${page.sourcePage} 页" draggable="false"><canvas aria-label="在原页自由套索"></canvas><svg class="grading-leaders" aria-hidden="true"></svg><div class="annotation-pins"></div><div class="grading-symbols"></div><div class="grading-point-comments" aria-label="常显评分点"></div></div>`;
        panel.selection = bindSelection(content.querySelector('canvas'), { getPage: () => this.getState().pages.find(row => row.id === panel.pageId), getMode: () => this.mode,
          onLayout:()=>this.renderPins(panel),
          getSelections: () => this.annotations(panel).filter(row => row.source !== 'grading' || row.location === 'region')
            .sort((a, b) => Number(b.source === 'grading') - Number(a.source === 'grading'))
            .flatMap(row => (row.source === 'grading' && row.regions?.length ? row.regions : [row.target])
              .map((target,index) => ({ ...target, id: `${row.id}:${index}`, annotationId:row.id, generated: row.source === 'grading',tone:row.mark?.tone||row.tone }))),
          getActiveId: () => this.note?.panel === panel ? this.note.row.id : panel.focusedPointId,
          getHoveredId:()=>panel.hoveredId,
          onActivate: target => {
            const row = target && this.annotations(panel).find(row => row.id === (target.annotationId || target.id));
            if (row && this.note?.row.id!==row.id) this.openNote(panel, row); else this.closeNote();
          }, onHover: id => {
            for (const pin of panel.root.querySelectorAll('[data-pin]')) pin.classList.toggle('is-hovered', pin.dataset.pin === id);
          }, onInvalid: this.toast, onSelect: target => {
            const row = { id: target.id, target: { ...target, kind: 'page' }, text: '', pending: true }; this.pending.push(row);
            this.closeNote(); this.renderPins(panel);
          } });
        const image=content.querySelector('img');
        const loaded=()=>{
          if(panel.pageId!==page.id||!panel.root.isConnected)return;
          panel.imageLoaded=true;
          try {
            const pixels=document.createElement('canvas');pixels.width=image.naturalWidth;pixels.height=image.naturalHeight;
            const context=pixels.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0);
            panel.inkMask=occupancyFromRgba(context.getImageData(0,0,pixels.width,pixels.height).data,pixels.width,pixels.height);
            panel.inkPageHash=page.sha256;pixels.width=0;pixels.height=0;
          } catch { panel.inkMask=null; } // No mask: labels stay outside the page.
          panel.commentLayoutKey=null;this.renderPins(panel);
        };
        image.addEventListener('load',loaded,{once:true});
        if(image.complete&&image.naturalWidth)loaded();
  }
  renderPanel(panel) {
    const state = this.getState(), page = state.pages.find(row => row.id === panel.pageId), doc = state.documents?.find(row => row.id === panel.documentId);
    const result=panel.resultTaskId?gradingResult(state,panel.resultTaskId,panel.resultGroupId):null;
    const source = sourceForPage(state, panel.pageId), pageIndex = source?.pageIds.indexOf(panel.pageId);
    const heading = panel.root.querySelector('.pane-heading');
    const value = result?`result:${panel.resultTaskId}:${panel.resultGroupId}`:doc ? `text:${doc.id}` : `source:${source?.id}`;
    const html = `<div class="pane-document">${icon('file-text')}<select class="pane-document-picker" aria-label="窗口 ${this.panels.indexOf(panel) + 1} 的文档">${this.choices().map(choice => `<option value="${e(choice.value)}" ${choice.value === value ? 'selected' : ''}>${e(choice.label)}</option>`).join('')}</select></div>${source ? `<div class="pane-pager">${control('previous', icon('left'), '上一页', pageIndex === 0)}<span>${pageIndex + 1}<small> / ${source.pageIds.length}</small></span>${control('next', icon('right'), '下一页', pageIndex === source.pageIds.length - 1)}</div>` : '<div class="pane-editor-tools"></div>'}${this.panels.length > 1 ? control('close', icon('close'), '关闭这个窗口') : ''}`;
    if (panel.headingHTML !== html) { heading.innerHTML = html; panel.headingHTML = html; }
    heading.querySelector('select').value = value;
    if(source&&!heading.querySelector('.reading-mode-picker')){
      const picker=document.createElement('select');picker.className='reading-mode-picker';picker.setAttribute('aria-label','阅读方式');
      picker.innerHTML='<option value="continuous">连续滚动</option><option value="paged">逐页翻阅</option>';picker.value=panel.readMode;heading.insertBefore(picker,heading.querySelector('.pane-pager'));
    }
    const content=panel.root.querySelector('.pane-content'),continuous=panel.readMode==='continuous';
    const key=doc?`doc:${doc.id}`:panel.resultTaskId?`result:${panel.resultTaskId}:${panel.resultGroupId}`:continuous?`flow:${source?.id}:${source?.pageIds.join(",")}`:`page:${page?.id}`;
    if(panel.contentKey!==key){
      panel.stream?.destroy();panel.stream=null;panel.editor?.destroy();panel.editor=null;panel.contentKey=key;panel.pinsHTML=null;
      if (!page && !doc && !result) content.replaceChildren();
      if(page){panel.stream=new PageStream(this,panel,source,content,continuous);requestAnimationFrame(()=>panel.stream?.go(panel.pageId));}
      else if(doc){
        content.innerHTML = '<div class="document-editor"></div><div class="document-annotations"></div>';
        panel.editor = new DocumentEditor(content.querySelector('.document-editor'), { id: doc.id, request: this.request, getState: this.getState, toast: this.toast, onLayout: () => this.renderPins(panel),
          onReference: this.onReference, onComment: (target, anchor) => {
            const row = { id: crypto.randomUUID(), target, text: '', pending: true }; this.pending.push(row); this.renderPins(panel); this.openNote(panel, row, anchor);
          }, onSource: number => { const scheme = this.getState().schemes.find(row => row.id === doc.schemeId); if (scheme?.pageIds[number - 1]) this.showPage(scheme.pageIds[number - 1], true).catch(error => this.toast(error.message)); } });
      }
    }
    if(page)panel.stream?.update();
    if(doc){panel.editor?.mountControls(heading.querySelector('.pane-editor-tools'));panel.editor?.sync(doc);}
    if(result){
      const markup=resultDocument(result,state.pages);if(panel.resultHTML!==markup||!content.querySelector('.result-document')){
        const open=[...content.querySelectorAll('details[open]')].map(n=>n.dataset.resultPoint),top=content.querySelector('.result-document')?.scrollTop||0;
        content.innerHTML=markup;panel.resultHTML=markup;
        for(const id of open){const node=content.querySelector(`[data-result-point="${CSS.escape(id)}"]`);if(node)node.open=true;}
        content.querySelector('.result-document').scrollTop=top;
      }
    }
    const approval = doc?.approvals?.at(-1);
    const batch = state.tasks.filter(task => task.kind === 'grade').findIndex(task => task.id === doc?.taskId) + 1;
    const batches = page ? annotationBatches(state, page.id) : [], notes = this.gradingRows(panel);
    const selectedBatch = batches.find(task => task.id === panel.gradingTaskId) || batches.at(-1);
    const unlocated=notes.filter(row=>row.location!=='region'&&panel.gradingMode!=='hidden'&&(panel.gradingMode!=='issues'||row.hasIssue));
    const unlocatedMenu=unlocated.length?`<details class="unlocated-menu"><summary>未定位 ${unlocated.length}</summary><div><p>这些批注只有页码引用，没有具体笔迹位置。</p>${unlocated.map(row=>`<button type="button" class="unlocated-marker" data-pane-action="note" data-id="${e(row.id)}" aria-label="查看未定位批注 ${e(row.label)}，${e(row.scoreLabel)}" aria-expanded="false"><span>${e(row.label)}</span><span>${e(row.scoreLabel)}</span></button>`).join('')}</div></details>`:'';
    const gradingControls = batches.length ? `<div class="grading-controls"><select class="grading-batch-picker" aria-label="批注所属批次">${batches.map(task => `<option value="${e(task.id)}" ${task.id === selectedBatch.id ? 'selected' : ''}>批次 ${state.tasks.filter(row => row.kind === 'grade').findIndex(row => row.id === task.id) + 1}</option>`).join('')}</select><select class="grading-mode-picker" aria-label="评分批注显示范围"><option value="all" ${!panel.gradingMode || panel.gradingMode === 'all' ? 'selected' : ''}>批注 ${notes.length}</option><option value="issues" ${panel.gradingMode === 'issues' ? 'selected' : ''}>只看疑点</option><option value="hidden" ${panel.gradingMode === 'hidden' ? 'selected' : ''}>隐藏批注</option></select>${unlocatedMenu}</div>` : '';
    const exportGroup=selectedBatch?.groups.find(group=>group.pageIds.includes(page?.id));
    const exportLink=exportGroup?`${control('result','评分结果','打开评分结果文档')}<a class="annotation-export" href="/api/tasks/${e(selectedBatch.id)}/annotated.pdf?groupId=${e(exportGroup.id)}" target="_blank" rel="noopener" title="打开带评分总览、勾叉和简短理由的 PDF">打印 / PDF</a>`:'';
    const footerHTML = result?`<span>逐项理由与评分依据 · 点击可对照原卷</span><a href="/api/tasks/${e(result.taskId)}/result.md?groupId=${e(result.groupId)}" class="result-download">下载评分报告</a>`:doc ? approval ? `<span>批次 ${batch} 采用 v${approval.revision}${approval.revision !== doc.revision ? ' · 当前编辑用于后续批次' : ''}</span>` : '' : `${gradingControls}${exportLink}<div>${control('zoom-out', icon('minus'), '缩小')}${control('zoom-reset', `${Math.round(panel.zoom * 100)}%`, '适合宽度')}${control('zoom-in', icon('plus'), '放大')}</div>`;
    if (panel.footerHTML !== footerHTML) { panel.root.querySelector('.pane-footer').innerHTML = footerHTML; panel.footerHTML = footerHTML; }
    if(doc)this.renderPins(panel);
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
    const rows=this.annotations(panel),pins=panel.root.querySelector(panel.documentId?'.document-annotations':'.annotation-pins');
    if(!pins)return;
    const content=rows.filter(row=>row.source!=='grading').map((row,index)=>`<div class="annotation-pin ${row.pending?'pending':''}" data-pin="${e(row.id)}"><button type="button" class="${panel.documentId?'annotation-marker':'annotation-target'}" aria-label="${row.pending?'添加':'查看'}注释 ${index+1}" data-pane-action="note" data-id="${e(row.id)}" ${panel.documentId?'title="查看文字注释"':''}>${panel.documentId?icon('message'):''}</button><button type="button" class="annotation-remove" data-pane-action="remove-note" data-id="${e(row.id)}" aria-label="移除注释 ${index+1}" title="移除这处圈注">×</button></div>`).join('');
    if(panel.pinsHTML!==content){pins.innerHTML=content;panel.pinsHTML=content;}
    const paper=panel.root.querySelector('.canvas-paper')?.getBoundingClientRect();
    const obstacles=rows.filter(row=>row.source!=='grading').flatMap(row=>[row.target.rect,
      ...(paper?.width&&paper.height?[{x:Math.max(0,row.target.rect.x+row.target.rect.width-10/paper.width),y:Math.max(0,row.target.rect.y-10/paper.height),width:20/paper.width,height:20/paper.height}]:[])]);
    if(!panel.documentId&&paper?.width>0&&paper.height>0) {
      for(const node of pins.children) {
        const row=rows.find(row=>row.id===node.dataset.pin),rect=row.target.rect;
        Object.assign(node.style,{left:`${rect.x*100}%`,top:`${rect.y*100}%`,width:`${rect.width*100}%`,height:`${rect.height*100}%`});
      }
    } else if(panel.documentId) {
      let previousTop=40;
      for(const node of pins.children){
        const row=rows.find(row=>row.id===node.dataset.pin),top=panel.editor?panel.editor.annotationTop(row.target):60;
        if(top===null){node.hidden=true;continue;}
        node.hidden=top<35||top>panel.root.querySelector('.pane-content').clientHeight-30;
        node.style.top=`${Math.max(previousTop,top)}px`;previousTop=Math.max(previousTop,top)+30;
      }
    }
    for(const node of pins.children){
      const active=this.note?.panel===panel&&this.note.row.id===node.dataset.pin;
      node.classList.toggle('is-active',active);node.querySelector('[data-pane-action="note"]').setAttribute('aria-expanded',String(active));
    }
    const menuRoot=panel.parent&&panel.parent.pageId===panel.pageId?panel.parent.root:panel.root;
    for(const button of menuRoot.querySelectorAll('.unlocated-marker'))button.setAttribute('aria-expanded',String(this.note?.panel===panel&&this.note.row.id===button.dataset.id));
    const comments=panel.root.querySelector('.grading-point-comments');let commentPlacements=[];
    if(comments&&paper?.width&&paper.height&&panel.imageLoaded){
      const points=rows.filter(row=>row.source==='grading');
      const fontSize=Math.max(11,Math.min(13,paper.width/62));
      const layoutKey=JSON.stringify([panel.pageId,paper.width,paper.height,panel.inkPageHash,points.map(n=>[n.id,n.regions,pointCommentContent(n)]),obstacles,fontSize]);
      if(panel.commentLayoutKey!==layoutKey){
        const measure=document.createElement('canvas').getContext('2d');
        const family=getComputedStyle(comments).fontFamily;
        const measureText=(text,kind)=>{measure.font=`${kind==='heading'?600:400} ${fontSize}px ${family}`;return measure.measureText(text).width;};
        panel.symbolLayout=layoutGradingSymbols(points,panel.inkMask,{width:paper.width,height:paper.height,obstacles});
        const symbols=panel.root.querySelector('.grading-symbols');
        symbols.innerHTML=panel.symbolLayout.map(place=>`<button class="grading-symbol ${place.symbol.tone}" data-pane-action="note" data-id="${e(place.id)}" aria-label="${e(place.symbol.label)}：${e(points.find(p=>p.id===place.id).label)}">${symbolSvg(place.symbol)}</button>`).join('');
        for(const node of symbols.children){const place=panel.symbolLayout.find(p=>p.id===node.dataset.id);Object.assign(node.style,{left:`${place.rect.x*100}%`,top:`${place.rect.y*100}%`,width:`${place.rect.width*100}%`,height:`${place.rect.height*100}%`});}
        panel.commentLayout=layoutPointComments(points,panel.inkMask,{width:paper.width,height:paper.height,fontSize,measureText,obstacles:[...obstacles,...panel.symbolLayout.map(p=>p.rect)]});
        panel.commentLayoutKey=layoutKey;
        comments.innerHTML=panel.commentLayout.map(place=>{
          const row=points.find(r=>r.id===place.id);
          return `<button type="button" class="grading-point-comment ${row.mark.tone}" data-pane-action="note" data-id="${e(row.id)}" data-placement="${place.mode}" data-truncated="${place.truncated}" aria-label="评分点 ${e(row.label)}，${e(row.scoreLabel)}">${place.lines.map(line=>`<span class="point-comment-line ${line.kind}">${e(line.text)}</span>`).join('')}</button>`;
        }).join('');
        // Set geometry through CSSOM; the workspace CSP disallows inline HTML styles.
        for(const node of comments.children){
          const place=panel.commentLayout.find(p=>p.id===node.dataset.id);
          Object.assign(node.style,{left:`${place.rect.x*100}%`,top:`${place.rect.y*100}%`,width:`${place.width}px`,height:`${place.height}px`,minHeight:'0',fontSize:`${fontSize}px`});
          [...node.children].forEach((span,i)=>{const line=place.lines[i];Object.assign(span.style,{left:`${line.x}px`,top:`${line.y}px`,width:`${line.width+.5}px`,height:`${line.height}px`,lineHeight:`${line.height}px`});});
        }
      }
      commentPlacements=panel.commentLayout;
      for(const node of comments.children){
        const active=this.note?.row.id===node.dataset.id;
        node.classList.toggle('is-active',active);node.setAttribute('aria-expanded',String(active));
      }
      const bottom=Math.max(paper.height,...commentPlacements.map(p=>(p.rect.y+p.rect.height)*paper.height));
      const body=panel.root.querySelector('.page-surface-body');if(body)body.style.paddingBottom=`${18+bottom-paper.height}px`;
    }
    const leaders=panel.root.querySelector('.grading-leaders'),selected=this.note?.panel===panel?this.note.row:null;
    if(leaders&&paper?.width&&paper.height){
      leaders.setAttribute('viewBox',`0 0 ${paper.width} ${paper.height}`);
      const links=[...commentPlacements,...(panel.symbolLayout||[])].filter(p=>p.sourceRect).map(place=>({place,line:gradingConnection(panel.inkMask,place,paper.width,paper.height)})).filter(row=>row.line);
      leaders.innerHTML=links.map(({place,line})=>`<path class="${place.mark.tone} ${place.id===selected?.id?'is-active':''}" data-point-id="${e(place.id)}" data-distance="${line.distance}" d="${line.points.map(([x,y],i)=>`${i?'L':'M'}${x*paper.width} ${y*paper.height}`).join(' ')}"/>`).join('');
    }
    panel.selection?.draw();if(this.note?.panel===panel)this.positionNote();
  }
  closeNote(restoreFocus=false) {
    const previous=this.note;
    if (this.note && !this.popover.hidden && this.popover.querySelector('textarea')) this.noteDrafts.set(this.note.row.id, this.popover.querySelector('textarea').value);
    this.popover.hidden = true; this.note = null;
    this.root.classList.remove('has-note-rail','has-note-sheet');document.body.classList.remove('annotation-sheet-open');
    for (const panel of this.allSurfaces()){panel.focusedPointId=null;this.renderPins(panel);}
    if(restoreFocus&&previous)(previous.panel.root.querySelector(`.grading-point-comment[data-id="${CSS.escape(previous.row.id)}"], [data-pin="${CSS.escape(previous.row.id)}"] [data-pane-action="note"]`)||previous.panel.root.querySelector('.unlocated-menu summary'))?.focus({preventScroll:true});
  }
  positionNote() {
    if(!this.note||this.popover.hidden)return;
    const root=this.root.getBoundingClientRect();
    const rail=false; // Opening a record must not shrink the answer or its comparison page.
    const sheet=!rail&&window.innerWidth<=820;
    this.root.classList.toggle('has-note-rail',rail);this.root.classList.toggle('has-note-sheet',sheet);
    document.body.classList.toggle('annotation-sheet-open',sheet);
    this.popover.dataset.layout=rail?'rail':sheet?'sheet':'floating';
    this.popover.style.setProperty('--annotation-rail-height',`${root.height}px`);
    if(sheet){this.popover.style.left='12px';this.popover.style.top='auto';return;}
    const bounds=(this.note.panel.root.querySelector(`.grading-point-comment[data-id="${CSS.escape(this.note.row.id)}"], [data-pin="${CSS.escape(this.note.row.id)}"]`)||(this.note.panel.parent||this.note.panel).root.querySelector('.unlocated-menu summary'))?.getBoundingClientRect()||root;
    const width=this.popover.offsetWidth,height=this.popover.offsetHeight;
    const right=bounds.right+14;
    const left=rail?root.right-width:right+width<=window.innerWidth-16?right:Math.max(16,bounds.left-width-14);
    this.popover.style.left=`${Math.max(12,Math.min(window.innerWidth-width-12,left))}px`;
    this.popover.style.top=`${Math.max(72,Math.min(window.innerHeight-height-16,rail?Math.min(root.bottom-height,bounds.top):bounds.top))}px`;
  }
  revealNote() {
    if(!this.note||this.note.row.target.kind!=='page')return;
    if(this.note.row.source==='grading'&&this.note.row.location!=='region')return;
    const {panel,row}=this.note,scroll=(panel.parent||panel).root.querySelector('.pane-page-scroll'),paper=panel.root.querySelector('.canvas-paper');
    if(!scroll||!paper)return;
    const bounds=scroll.getBoundingClientRect(),image=paper.getBoundingClientRect(),rect=(row.regions?.[0]||row.target).rect;
    const top=image.top+rect.y*image.height,bottom=top+rect.height*image.height;
    const availableBottom=Math.min(bounds.bottom,this.popover.dataset.layout==='sheet'?this.popover.getBoundingClientRect().top-12:bounds.bottom);
    if(top<bounds.top+12||bottom>availableBottom-12)scroll.scrollTop+=top-bounds.top-Math.max(16,(availableBottom-bounds.top-Math.min(rect.height*image.height,120))/3);
  }
  openNote(panel, row, anchor = null) {
    this.closeNote();
    this.note = { panel, row };
    const target = row.target;
    if (row.source === 'grading') {
      const pages = this.getState().pages;
      const rows=this.annotations(panel).filter(row=>row.source==='grading');
      this.popover.innerHTML=gradingCard(row,{pages,pageId:panel.pageId,index:rows.findIndex(note=>note.id===row.id),total:rows.length,related:relatedGradingNotes(row,rows)});
      this.popover.classList.add('is-grading');
      this.popover.hidden = false;
      this.positionNote();this.renderPins(panel);this.popover.focus({preventScroll:true});
      requestAnimationFrame(()=>{this.positionNote();this.revealNote();});return;
    }
    this.popover.classList.remove('is-grading');
    this.popover.innerHTML = `<div class="annotation-heading"><span>${target.kind === 'text' ? `文字注释 · v${target.revision}` : `第 ${target.sourcePage} 页 · ${target.shape === 'lasso' ? '套索' : '框选'}`}</span><button type="button" data-note-action="close" aria-label="收起注释">×</button></div>${target.kind === 'text' ? `<blockquote>${e(target.quote.slice(0, 160))}</blockquote>` : ''}<textarea aria-label="注释内容" placeholder="写下这处的说明…" rows="3" maxlength="8000">${e(this.noteDrafts.get(row.id) ?? row.text)}</textarea><div class="annotation-actions"><button type="button" data-note-action="reference">${icon('plus')}添加到对话</button><button type="button" class="primary" data-note-action="save">保存注释</button></div>`;
    this.popover.hidden = false;
    this.positionNote();
    this.renderPins(panel);
    this.popover.querySelector('textarea').focus({ preventScroll: true });
    requestAnimationFrame(()=>{this.positionNote();this.revealNote();});
  }
  async noteAction(action, id) {
    if (action === 'close') { this.closeNote(true); return; }
    if (this.noteSaving || !this.note) return;
    if (this.note.row.source === 'grading') {
      const row = this.note.row;
      if(action==='point'){const other=this.annotations(this.note.panel).find(note=>note.id===id&&note.source==='grading');if(other)this.openNote(this.note.panel,other);return;}
      if(action==='previous'||action==='next') {
        const {panel}=this.note,rows=this.annotations(panel).filter(row=>row.source==='grading'),index=rows.findIndex(note=>note.id===row.id)+(action==='next'?1:-1);
        if(rows[index])this.openNote(panel,rows[index]);return;
      }
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
    if(action==='result'){const batches=annotationBatches(this.getState(),panel.pageId),task=batches.find(t=>t.id===panel.gradingTaskId)||batches.at(-1);await this.showResults(task?.id,task?.groups.find(g=>g.pageIds.includes(panel.pageId))?.id);return;}
    if(action==='result-point'){await this.showPoint(id);return;}
    if(action==='result-source'){await this.showPage(id,true);return;}
    if(action==='result-review'){this.onReview(id);return;}
    if(action==='result-item'){panel.root.querySelector(`[data-item="${CSS.escape(id)}"]`)?.scrollIntoView({block:'start',behavior:'smooth'});return;}
    if((action==='note'||action==='remove-note')&&panel.stream)panel=panel.stream.views.get(panel.pageId)||panel;
    const rows = this.annotations(panel), row = rows.find(row => row.id === id);
    if (action === 'note' && row) {
      const menu=(panel.parent||panel).root.querySelector('.unlocated-menu');if(menu)menu.open=false;
      if(this.note?.row.id===row.id){this.closeNote();return;}
      if (panel.editor) panel.editor.focusTarget(row.target);this.openNote(panel, row);
    }
    if (action === 'remove-note' && row) {
      if (row.pending) this.pending = this.pending.filter(item => item.id !== id);
      else await this.request(`/api/annotations/${id}`, { archive: true }, 'PATCH');
      if (this.note?.row.id === id) this.closeNote();
      this.noteDrafts.delete(id);
      this.renderPins(panel);
    }
    if (action === 'previous' || action === 'next') {
      const doc = sourceForPage(this.getState(), panel.pageId);
      panel.pageId = doc.pageIds[doc.pageIds.indexOf(panel.pageId) + (action === 'previous' ? -1 : 1)]; this.closeNote(); this.update();
      panel.stream?.go(panel.pageId);
    }
    if (action.startsWith('zoom')) { panel.zoom = action === 'zoom-reset' ? 1 : Math.max(.6, Math.min(2, panel.zoom + (action === 'zoom-in' ? .2 : -.2))); this.update(); }
    if (action === 'close') {
      if (panel.editor?.dirty) await panel.editor.save();
      panel.editor?.destroy(); panel.stream?.destroy();panel.selection?.destroy(); panel.root.remove(); this.panels = this.panels.filter(row => row.id !== panel.id);
      this.activeId = this.panels[0]?.id; this.closeNote(); this.update();
    }
    if (action === 'approve') {
      await this.approveDocument(panel.documentId);
    }
  }
}
