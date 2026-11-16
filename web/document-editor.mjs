import { escape as e, icon } from './ui.mjs';
import { DocumentReader } from './document-reader.mjs';
import { sourceSelection } from './report-math.mjs';

const button = (action, text, title = '') => `<button type="button" data-editor="${action}" ${title ? `title="${e(title)}"` : ''}>${text}</button>`;
export class DocumentEditor {
  constructor(root, { id, request, getState, onReference, onComment, onSource, onLayout = () => {}, toast }) {
    Object.assign(this, { root, id, request, getState, onReference, onComment, onSource, onLayout, toast });
    this.key = `gradeos-draft:${location.port}:${id}`;
    root.innerHTML = `<div class="editor-controls"><span class="save-state" role="status">读取中…</span>${button('toggle-mode', '编辑', '直接编辑这份文档')}<details class="editor-more"><summary aria-label="文档更多操作">${icon('down')}</summary><div>${button('versions', '历史版本')}<a class="document-download" href="/api/documents/${id}?download" title="下载 Markdown">导出 Markdown</a></div></details></div><div class="editor-notice" hidden></div><div class="editor-content"><textarea class="document-input" aria-label="编辑文档" spellcheck="false" placeholder="在这里直接编辑…" hidden></textarea><article class="document-preview prose"></article></div><div class="text-selection-menu" role="toolbar" aria-label="所选文字操作" hidden>${button('comment', `${icon('message')}添加注释`)}${button('reference', `${icon('plus')}添加到对话`)}</div><div class="version-popover" hidden></div>`;
    this.controls = root.querySelector('.editor-controls');
    this.input = root.querySelector('textarea'); this.preview = root.querySelector('.document-preview');
    this.reader = new DocumentReader(this.preview, { id, onLayout });
    this.menu = root.querySelector('.text-selection-menu'); this.notice = root.querySelector('.editor-notice');
    this.input.addEventListener('input', () => { this.changed(); });
    this.input.addEventListener('keydown', event => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); this.save().catch(error => this.toast(error.message)); }
    });
    this.input.addEventListener('keyup', event => { if (event.shiftKey) this.selection(event); });
    this.input.addEventListener('select', event => this.selection(event));
    this.selectionChanged = () => {
      if (document.activeElement === this.input && this.input.selectionStart !== this.input.selectionEnd) this.selection({});
    };
    document.addEventListener('selectionchange', this.selectionChanged);
    this.input.addEventListener('pointerup', event => this.selection(event));
    this.preview.addEventListener('pointerup', event => this.selection(event));
    this.preview.addEventListener('copy', event => {
      const selection = window.getSelection();
      if (!selection?.rangeCount || ![...this.preview.querySelectorAll('[data-math-source]')].some(node => selection.getRangeAt(0).intersectsNode(node))) return;
      const target = sourceSelection(this.preview, selection, this.input.value);
      if (target && event.clipboardData) { event.preventDefault(); event.clipboardData.setData('text/plain', target.quote); }
    });
    for (const node of [this.input, this.preview]) node.addEventListener('scroll', () => { this.menu.hidden = true; this.onLayout(); }, { passive: true });
    const handleClick = event => {
      const link = event.target.closest('a[href^="#ms-page-"]');
      if (link) { event.preventDefault(); this.onSource(Number(link.hash.replace('#ms-page-', ''))); return; }
      const action = event.target.closest('[data-editor]')?.dataset.editor;
      if (action) { event.preventDefault(); this.act(action).catch(error => this.toast(error.message)); }
    };
    root.addEventListener('click', handleClick);
    this.controls.addEventListener('click', event => { event.stopPropagation(); handleClick(event); });
    this.load().catch(error => this.toast(error.message));
  }
  mountControls(host) { if (host && this.controls.parentNode !== host) host.append(this.controls); }
  async load() {
    this.loading = true;
    try {
      const response = await fetch(`/api/documents/${this.id}`), document = await response.json();
      if (!response.ok) throw Error(document.error);
      if (this.destroyed) return;
      this.document = document;
      let draft; try { draft = JSON.parse(localStorage.getItem(this.key)); } catch { /* Optional local draft. */ }
      this.input.value = draft?.body ?? document.body;
      this.dirty = this.input.value !== document.body;
      if (this.dirty && draft.revision !== document.revision) this.conflict = true;
      this.reader.render(this.input.value); this.updateStatus();
      this.onLayout();
      if (this.dirty && !this.conflict) this.schedule();
    } finally { this.loading = false; }
  }
  sync(metadata) {
    if (!metadata || this.loading || this.saving || !this.document) return;
    this.document.approvals = metadata.approvals;
    if (metadata.revision !== this.document.revision) {
      if (this.dirty) { this.conflict = true; this.updateStatus(); }
      else this.load().catch(error => this.toast(error.message));
    }
  }
  changed() {
    this.dirty = this.input.value !== this.document?.body; this.selected = null; this.menu.hidden = true;
    try { localStorage.setItem(this.key, JSON.stringify({ body: this.input.value, revision: this.document.revision })); } catch { /* Server save remains available. */ }
    this.updateStatus(); this.schedule();
  }
  schedule() { clearTimeout(this.timer); this.timer = setTimeout(() => this.save().catch(error => this.toast(error.message)), 1000); }
  updateStatus() {
    const status = this.controls.querySelector('.save-state');
    status.textContent = this.conflict ? '待合并' : this.saving ? '保存中…' : this.dirty ? '未保存' : `v${this.document?.revision || 1}`;
    status.title = this.conflict ? '存在新版本，请对照后合并' : this.dirty ? '更改尚未保存' : '已自动保存';
    status.setAttribute('aria-label', this.dirty ? '文档未保存' : `已保存 · v${this.document?.revision || 1}`);
    this.notice.hidden = !this.conflict;
    if (this.conflict) this.notice.innerHTML = `另一处已更新。你的草稿保留在这里。${button('compare', '对照最新版本')}${button('merge', '将当前草稿保存为新版本')}`;
  }
  async save() {
    clearTimeout(this.timer);
    if (this.saving) { await this.saving; return this.save(); }
    if (!this.dirty || !this.document) return this.document;
    if (this.conflict) throw Error('文档有新版本，请先对照并合并。你的草稿已保留。');
    const body = this.input.value, revision = this.document.revision;
    this.saving = this.request(`/api/documents/${this.id}`, { body, revision }, 'PATCH'); this.updateStatus();
    try {
      const result = await this.saving; this.document = result.document;
      this.dirty = this.input.value !== body;
      if (!this.dirty) localStorage.removeItem(this.key);
      else { localStorage.setItem(this.key, JSON.stringify({ body: this.input.value, revision: this.document.revision })); this.schedule(); }
      return this.document;
    } catch (error) {
      if (/版本|更新/.test(error.message)) this.conflict = true;
      throw error;
    } finally { this.saving = null; this.updateStatus(); }
  }
  selection(event) {
    if (!this.document) return;
    let start, end;
    if (!this.input.hidden) { start = this.input.selectionStart; end = this.input.selectionEnd; }
    else {
      const selection = window.getSelection(), quote = selection?.toString();
      if (!quote || !this.preview.contains(selection.anchorNode) || !this.preview.contains(selection.focusNode)) return;
      const target = sourceSelection(this.preview, selection, this.input.value);
      if (!target) { this.selected = null; this.menu.hidden = true; this.toast('这段文字包含格式或重复内容，请切到“编辑”后选取。'); return; }
      ({ start, end } = target);
    }
    if (start === end) { this.menu.hidden = true; return; }
    this.selected = { start, end, quote: this.input.value.slice(start, end) };
    const bounds = this.root.getBoundingClientRect();
    this.anchor = { x: event.clientX || bounds.left + 80,
      y: event.clientY || bounds.top + Math.max(65, Math.min(bounds.height - 80, this.annotationTop({ ...this.selected, revision: this.document.revision }) + 28)) };
    this.menu.hidden = false;
    this.menu.style.left = `${Math.max(10, Math.min(window.innerWidth - 275, this.anchor.x - 80))}px`;
    this.menu.style.top = `${Math.max(70, Math.min(window.innerHeight - 160, this.anchor.y + 12))}px`;
  }
  async target() {
    const selected = this.selected, document = await this.save();
    if (!selected || document.body.slice(selected.start, selected.end) !== selected.quote) throw Error('文字已改变，请重新选择。');
    return { kind: 'text', documentId: this.id, title: document.title, revision: document.revision, documentHash: document.hash, ...selected };
  }
  async act(action) {
    if (action === 'toggle-mode') action = this.input.hidden ? 'edit' : 'preview';
    if (action === 'edit' || action === 'preview') {
      this.input.hidden = action !== 'edit'; this.preview.hidden = action !== 'preview'; this.reader.shell.hidden = action !== 'preview'; this.menu.hidden = true;
      if (action === 'preview') this.reader.render(this.input.value);
      this.controls.querySelector('[data-editor="toggle-mode"]').textContent = action === 'edit' ? '完成编辑' : '编辑';
      this.controls.querySelector('[data-editor="toggle-mode"]').setAttribute('aria-pressed', String(action === 'edit'));
      if (action === 'edit') this.input.focus({ preventScroll: true });
      this.onLayout();
    }
    if (action === 'reference') { this.onReference({ target: await this.target() }); this.menu.hidden = true; }
    if (action === 'comment') { this.onComment(await this.target(), this.anchor); this.menu.hidden = true; }
    if (action === 'versions' || action === 'compare') {
      this.controls.querySelector('details').open = false;
      const popup = this.root.querySelector('.version-popover');
      if (action === 'versions' && !popup.hidden) { popup.hidden = true; return; }
      const response = await fetch(`/api/documents/${this.id}`), latest = await response.json();
      popup.hidden = false;
      popup.innerHTML = `<div class="version-heading"><strong>${action === 'compare' ? '最新版本 · 对照后合并到编辑区' : '文档版本'}</strong>${button('close-versions', '×')}</div><select aria-label="选择历史版本">${latest.versions.toReversed().map(version => `<option value="${version.revision}">v${version.revision} · ${version.actor === 'agent' ? 'Agent' : '老师'} · ${e(new Date(version.at).toLocaleString())}</option>`).join('')}</select><pre></pre>`;
      popup.querySelector('pre').textContent = latest.body;
      popup.querySelector('select').addEventListener('change', async event => {
        const response = await fetch(`/api/documents/${this.id}?revision=${event.target.value}`);
        popup.querySelector('pre').textContent = (await response.json()).body;
      });
    }
    if (action === 'close-versions') this.root.querySelector('.version-popover').hidden = true;
    if (action === 'merge') {
      const response = await fetch(`/api/documents/${this.id}`), latest = await response.json();
      this.document = latest; this.conflict = false; this.dirty = true; await this.save();
      this.root.querySelector('.version-popover').hidden = true;
    }
  }
  focusTarget(target) {
    this.act('edit'); this.input.focus({ preventScroll: true });
    if (target.revision === this.document?.revision) {
      this.input.setSelectionRange(target.start, target.end);
      this.input.scrollTop = Math.max(0, this.sourceTop(target.start) - this.input.clientHeight / 3);
      this.onLayout();
    } else this.toast(`这条注释引用 v${target.revision}，原文已保留，可在版本中对照。`);
  }
  annotationTop(target) {
    if (!this.document) return 60;
    const parent = this.root.getBoundingClientRect();
    if (!this.preview.hidden) {
      if (target.revision === this.document.revision) {
        const formula = [...this.preview.querySelectorAll('[data-math-source]')].find(node => target.start >= Number(node.dataset.sourceStart) && target.start < Number(node.dataset.sourceEnd));
        if (formula) return formula.getClientRects().length ? formula.getBoundingClientRect().top - parent.top : null;
      }
      const walker = document.createTreeWalker(this.preview, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const start = walker.currentNode.textContent.indexOf(target.quote);
        if (start < 0) continue;
        if (!walker.currentNode.parentElement.getClientRects().length) return null;
        const range = document.createRange(); range.setStart(walker.currentNode, start); range.setEnd(walker.currentNode, start + 1);
        return range.getBoundingClientRect().top - parent.top;
      }
      return 60;
    }
    const start = target.revision === this.document.revision ? target.start : this.input.value.indexOf(target.quote);
    if (start < 0) return 60;
    return this.sourceTop(start) + this.input.getBoundingClientRect().top - parent.top - this.input.scrollTop;
  }
  sourceTop(start) {
    const mirror = document.createElement('div'), computed = getComputedStyle(this.input);
    for (const property of ['font', 'line-height', 'letter-spacing', 'word-spacing', 'padding', 'white-space', 'word-break', 'overflow-wrap', 'tab-size', 'text-indent', 'text-transform', 'text-align', 'direction']) mirror.style.setProperty(property, computed.getPropertyValue(property));
    Object.assign(mirror.style, { position: 'absolute', visibility: 'hidden', boxSizing: 'border-box', width: `${this.input.clientWidth}px`, left: '0', top: '0', pointerEvents: 'none' });
    mirror.textContent = this.input.value.slice(0, start);
    const marker = document.createElement('span'), character = String.fromCodePoint(this.input.value.codePointAt(start) ?? 0x200b);
    marker.textContent = character;
    // Include the rest of this line so a word wrapping across the marker has
    // the same layout as the textarea. Later lines cannot affect its position.
    const lineEnd = this.input.value.indexOf('\n', start);
    mirror.append(marker, this.input.value.slice(start + character.length, lineEnd < 0 ? undefined : lineEnd)); this.root.append(mirror);
    const top = marker.getBoundingClientRect().top - mirror.getBoundingClientRect().top;
    mirror.remove(); return top;
  }
  destroy() { this.destroyed = true; clearTimeout(this.timer); this.reader.destroy(); this.menu.hidden = true; this.controls.remove(); document.removeEventListener('selectionchange', this.selectionChanged); }
}
