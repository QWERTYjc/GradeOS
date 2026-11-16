import { escape as e, markdown } from './ui.mjs';
import { sourceText } from './report-math.mjs';

let readerId = 0;
const searchKey = value => String(value).normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');

// Older saved reports contain one point ledger without question headings. Group its
// explicit item/point keys for reading only; the Markdown and every cell stay intact.
export function groupPointLedger(article) {
  if (article.querySelectorAll(':scope > h2').length > 1) return;
  const used = new Set([...article.querySelectorAll('[id]')].map(node => node.id));
  const heading = (level, label) => {
    const node = document.createElement(`h${level}`); node.textContent = label;
    const base = searchKey(label) || 'section'; let id = base, n = 1;
    while (used.has(id)) id = `${base}-${n++}`;
    used.add(id); node.id = id; return node;
  };
  for (const wrapper of article.querySelectorAll(':scope > .report-table')) {
    if (wrapper.querySelector('th')?.textContent.trim() !== '评分点') continue;
    const groups = new Map(), rows = [...wrapper.querySelectorAll('tbody tr')];
    if (!rows.length || rows.some(row => !/^[^/]+\/[^/]+$/.test(row.cells[0]?.textContent.trim()))) continue;
    for (const row of rows) {
      const item = row.cells[0].textContent.trim().split('/')[0];
      if (!groups.has(item)) groups.set(item, []);
      groups.get(item).push(row);
    }
    if (groups.size < 2) continue;
    const fragment = document.createDocumentFragment(); fragment.append(heading(2, '逐题评分记录'));
    for (const [item, cells] of groups) {
      const group = wrapper.cloneNode(false), table = document.createElement('table'), body = document.createElement('tbody');
      table.append(wrapper.querySelector('thead').cloneNode(true), body); body.append(...cells); group.append(table);
      fragment.append(heading(3, item), group);
    }
    wrapper.replaceWith(fragment);
  }
}

export class DocumentReader {
  constructor(article, { id, onLayout = () => {} } = {}) {
    this.article = article; this.onLayout = onLayout; this.prefix = `reader-${++readerId}-`;
    this.key = `gradeos-reading:${location.port}:${id}`;
    try { this.saved = JSON.parse(localStorage.getItem(this.key)) || {}; } catch { this.saved = {}; }
    this.mode = this.saved.mode === 'full' ? 'full' : 'chapters';
    this.shell = document.createElement('div'); this.shell.className = 'document-reader';
    article.replaceWith(this.shell);
    this.shell.innerHTML = `<aside class="reader-outline" id="${this.prefix}outline" aria-label="文档目录"><div class="reader-outline-heading"><strong>目录</strong><button type="button" data-reader="close" aria-label="关闭目录">×</button></div><label class="reader-search"><span class="sr-only">查找章节或题号</span><input type="search" placeholder="查找章节或题号" aria-label="查找章节或题号"></label><nav class="reader-toc" aria-label="章节与小节"></nav><p class="reader-search-status" role="status"></p></aside><button type="button" class="reader-scrim" data-reader="close" aria-label="关闭目录遮罩" tabindex="-1"></button><div class="reader-main"><div class="reader-toolbar"><button type="button" class="reader-menu" data-reader="menu" aria-controls="${this.prefix}outline" aria-expanded="false">目录</button><div class="reader-location"><span class="reader-current"></span><small class="reader-position"></small></div><button type="button" class="reader-mode" data-reader="mode" aria-pressed="false">阅读全文</button><div class="reader-paging"><button type="button" data-reader="previous" aria-label="上一章" title="上一章">‹</button><button type="button" data-reader="next" aria-label="下一章" title="下一章">›</button></div></div></div>`;
    this.main = this.shell.querySelector('.reader-main'); this.main.append(article);
    this.nav = this.shell.querySelector('.reader-outline'); this.toc = this.shell.querySelector('.reader-toc');
    this.search = this.shell.querySelector('input'); this.toolbar = this.shell.querySelector('.reader-toolbar');
    this.shell.addEventListener('click', event => this.click(event));
    this.search.addEventListener('input', () => this.renderOutline());
    this.search.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); this.toc.querySelector('[data-anchor]')?.focus(); }
      if (event.key === 'Enter' && this.search.value) { event.preventDefault(); this.toc.querySelector('[data-anchor]')?.click(); }
    });
    this.shell.addEventListener('keydown', event => {
      if (event.key === 'Escape' && this.shell.classList.contains('outline-open')) { event.preventDefault(); this.closeOutline(true); }
    });
    this.onScroll = () => {
      if (this.frame) return;
      this.frame = requestAnimationFrame(() => { this.frame = null; this.trackPosition(); });
    };
    article.addEventListener('scroll', this.onScroll, { passive: true });
    this.onToggle = () => { this.onScroll(); this.onLayout(); };
    article.addEventListener('toggle', this.onToggle, true);
    this.resize = new ResizeObserver(() => {
      this.compact = this.shell.clientWidth < 740;
      this.shell.classList.toggle('reader-compact', this.compact); this.updateMenu(); this.onLayout();
    });
    this.resize.observe(this.shell);
  }
  render(body) {
    const restore = this.current?.anchor ?? this.saved.anchor;
    this.article.innerHTML = markdown(body); groupPointLedger(this.article);
    const nodes = [...this.article.childNodes], boundaries = nodes.filter(node => node.nodeName === 'H2');
    this.chapters = []; this.entries = []; this.targets = new Map();
    let section;
    for (const node of nodes) {
      if (!section || node.nodeName === 'H2' && this.chapters.length && section.querySelector(':scope > h2')) {
        section = document.createElement('section'); section.className = 'reader-chapter'; this.article.append(section);
        this.chapters.push({ node: section, index: this.chapters.length, children: [] });
      }
      section.append(node);
    }
    for (const chapter of this.chapters) {
      const first = chapter.node.querySelector(':scope > h2') ?? chapter.node.querySelector('h1,h2,h3');
      chapter.title = first ? sourceText(first) : '正文';
      for (const heading of chapter.node.querySelectorAll('h1,h2,h3,h4')) {
        const anchor = heading.id || `heading-${this.targets.size + 1}`;
        heading.dataset.readerAnchor = anchor; heading.id = this.prefix + anchor; heading.tabIndex = -1;
        const entry = { anchor, heading, chapter, label: sourceText(heading) };
        this.targets.set(anchor, entry);
        if (heading === first) { chapter.entry = entry; this.entries.push(entry); }
        else if (heading.nodeName === 'H3' || !first && heading.nodeName === 'H2') {
          entry.child = true; chapter.children.push(entry); this.entries.push(entry);
        }
      }
      // A plain document has no headings and needs no navigation chrome.
      if (!chapter.entry && this.targets.size) chapter.entry = [...this.targets.values()].find(row => row.chapter === chapter);
    }
    this.structured = boundaries.length > 0 && this.entries.length > 1;
    this.shell.classList.toggle('reader-structured', this.structured);
    for (const paragraph of this.article.querySelectorAll('p')) {
      const links = [...paragraph.querySelectorAll('a')];
      const remainder = [...paragraph.childNodes].filter(node => node.nodeName !== 'A').map(node => node.textContent).join('');
      if (links.length >= 3 && /^[\s·|•]*$/.test(remainder) && links.every(link => {
        try { return this.targets.has(decodeURIComponent(link.hash.slice(1))); } catch { return false; }
      })) paragraph.classList.add('reader-inline-toc');
    }
    const target = this.targets.get(restore) ?? this.chapters[0]?.entry;
    this.current = target; this.active = target?.chapter.index ?? 0;
    this.applyVisibility(); this.renderOutline(); this.updateToolbar();
    if (target && restore) this.navigate(target.anchor, { focus: false, close: false });
    else this.article.scrollTop = 0;
  }
  applyVisibility() {
    for (const chapter of this.chapters) chapter.node.hidden = this.structured && this.mode === 'chapters' && chapter.index !== this.active;
  }
  renderOutline() {
    const query = searchKey(this.search.value);
    const links = entry => `<button type="button" class="reader-entry${entry.child ? ' reader-subentry' : ''}" data-anchor="${e(entry.anchor)}"${this.current?.anchor === entry.anchor ? ' aria-current="location"' : ''}><span>${e(entry.label)}</span>${query && entry.child ? `<small>${e(entry.chapter.title)}</small>` : ''}</button>`;
    const matches = query ? this.entries.filter(entry => searchKey(entry.label).includes(query)) : this.entries;
    this.toc.innerHTML = query ? matches.map(links).join('') : this.chapters.map(chapter => {
      if (!chapter.entry) return '';
      return `<div class="reader-toc-group">${links(chapter.entry)}${chapter.children.length ? `<details${chapter.index === this.active ? ' open' : ''}><summary>${chapter.children.length} 个小节</summary>${chapter.children.map(links).join('')}</details>` : ''}</div>`;
    }).join('');
    this.shell.querySelector('.reader-search-status').textContent = query ? matches.length ? `${matches.length} 个匹配章节或小节` : '未找到章节或题号，试试其他关键词。' : '';
  }
  updateMenu() {
    this.shell.querySelector('[data-reader="menu"]').setAttribute('aria-expanded', String(!this.compact || this.shell.classList.contains('outline-open')));
  }
  updateToolbar() {
    const chapter = this.chapters[this.active]; if (!chapter) return;
    this.shell.querySelector('.reader-current').textContent = this.current?.child ? `${chapter.title} / ${this.current.label}` : chapter.title;
    this.shell.querySelector('.reader-position').textContent = `${this.active + 1} / ${this.chapters.length} 章`;
    const mode = this.shell.querySelector('[data-reader="mode"]');
    mode.textContent = this.mode === 'full' ? '分章阅读' : '阅读全文';
    mode.setAttribute('aria-pressed', String(this.mode === 'full'));
    mode.title = this.mode === 'full' ? '每次只阅读一章' : '连续显示整份文档，便于全文查找';
    this.shell.querySelector('[data-reader="previous"]').disabled = this.active === 0;
    this.shell.querySelector('[data-reader="next"]').disabled = this.active === this.chapters.length - 1;
    for (const node of this.toc.querySelectorAll('[data-anchor]')) {
      if (node.dataset.anchor === this.current?.anchor) node.setAttribute('aria-current', 'location'); else node.removeAttribute('aria-current');
    }
    this.updateMenu();
  }
  persist() {
    try { localStorage.setItem(this.key, JSON.stringify({ mode: this.mode, anchor: this.current?.anchor })); } catch { /* Optional reading preference. */ }
  }
  trackPosition() {
    if (this.shell.hidden || !this.entries.length) return;
    const top = this.article.getBoundingClientRect().top + 50;
    const visible = this.entries.filter(entry => !entry.chapter.node.hidden && entry.heading.getClientRects().length);
    let current = visible[0];
    for (const entry of visible) {
      if (entry.heading.getBoundingClientRect().top <= top) current = entry; else break;
    }
    if (!current || current === this.current) return;
    const changedChapter = current.chapter.index !== this.active;
    this.current = current; this.active = current.chapter.index;
    if (changedChapter) this.renderOutline();
    this.updateToolbar(); this.persist();
  }
  navigate(anchor, { focus = true, close = true } = {}) {
    const target = this.targets.get(anchor); if (!target) return false;
    const changedChapter = target.chapter.index !== this.active;
    this.current = target; this.active = target.chapter.index; this.applyVisibility();
    for (let parent = target.heading.parentElement; parent && parent !== this.article; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
    if (changedChapter) this.renderOutline();
    if (close) this.closeOutline();
    this.updateToolbar();
    const element = target === target.chapter.entry ? target.chapter.node : target.heading;
    this.article.scrollTop += element.getBoundingClientRect().top - this.article.getBoundingClientRect().top - 20;
    if (focus) target.heading.focus({ preventScroll: true });
    this.persist(); this.onLayout(); return true;
  }
  closeOutline(focus = false) {
    this.shell.classList.remove('outline-open'); this.updateMenu();
    if (focus) this.shell.querySelector('[data-reader="menu"]').focus();
  }
  click(event) {
    const jump = event.target.closest('[data-anchor]');
    if (jump) { this.navigate(jump.dataset.anchor); return; }
    const link = event.target.closest('a[href^="#"]');
    if (link && !link.hash.startsWith('#ms-page-')) {
      event.preventDefault();
      let anchor; try { anchor = decodeURIComponent(link.hash.slice(1)); } catch { return; }
      this.navigate(anchor);
      return;
    }
    const action = event.target.closest('[data-reader]')?.dataset.reader;
    if (action === 'menu') {
      this.shell.classList.toggle('outline-open'); this.updateMenu();
      if (this.shell.classList.contains('outline-open')) this.search.focus();
    }
    if (action === 'close') this.closeOutline(true);
    if (action === 'mode') {
      this.mode = this.mode === 'full' ? 'chapters' : 'full';
      if (this.current) this.navigate(this.current.anchor, { focus: false });
    }
    if (action === 'previous' || action === 'next') {
      const chapter = this.chapters[this.active + (action === 'previous' ? -1 : 1)];
      if (chapter?.entry) this.navigate(chapter.entry.anchor);
    }
  }
  destroy() {
    this.persist(); this.resize.disconnect(); cancelAnimationFrame(this.frame);
    this.article.removeEventListener('scroll', this.onScroll); this.article.removeEventListener('toggle', this.onToggle, true);
  }
}
