import { mathParts, renderMath } from './report-math.mjs';

export const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
export const icon = name => `<img class="icon" src="/assets/icons/${name}.svg" alt="" aria-hidden="true">`;
export const button = (action, label, { className = '', attrs = '', symbol = '', disabled = false } = {}) => `<button type="button" class="${className}" data-action="${action}" ${attrs} ${disabled ? 'disabled' : ''}>${symbol ? icon(symbol) : ''}${label}</button>`;
export const iconButton = (action, label, symbol, attrs = '') => button(action, '', { className: 'icon-button', symbol, attrs: `aria-label="${escape(label)}" title="${escape(label)}" ${attrs}` });
export const scoreText = value => typeof value === 'number' && Number.isFinite(value) ? `${value} 分` : '待判定';
export const recordScoreText = (record, score = record.score) => typeof score === 'number' && Number.isFinite(score)
  ? `${score}${Number.isFinite(record.maximum) ? ` / ${record.maximum}` : ''} 分`
  : record.disposition === 'feedback_only' ? '定性反馈' : '待定';
export const recordBasisText = record => record.basis === 'answer_context' ? '依据本份答卷内容 · 建议批改' : record.basisLabel;
export const uncertaintyView = record => record.uncertainties?.length
  ? `<section class="record-uncertainties"><strong>待核实</strong><ul>${record.uncertainties.map(note => `<li>${escape(note)}</li>`).join('')}</ul></section>` : '';
export const statuses = { draft: '任务草稿', running: '正在进行', needs_review: '待审阅', completed: '已完成', partial: '部分完成', failed: '未完成', cancelled: '已取消', interrupted: '已中断' };
export const pageById = (state, id) => state.pages.find(page => page.id === id);
export const scopeText = ids => `已选 ${ids.length} 份`;
export function empty(title, description, actions = '') {
  return `<section class="empty"><h1>${escape(title)}</h1><p>${escape(description)}</p><div class="empty-actions">${actions}</div></section>`;
}
export const latestReview = (state, recordId) => state.reviews.findLast(review => review.recordId === recordId);
export function markdown(body, headingIds = new Set()) {
  const original = String(body ?? ''), tokens = [];
  let prefix = '\uE000'; while (original.includes(prefix)) prefix += '\uE000';
  const tokenPattern = new RegExp(`${prefix}(\\d+)\uE001`, 'g');
  const stash = (raw, html, math = null, block = false) => {
    tokens.push({ raw, html, math, block }); return `${prefix}${tokens.length - 1}\uE001`;
  };
  const rawText = text => text.replace(tokenPattern, (_match, id) => tokens[id].raw);
  // Protect code and links first, then math, before Markdown splits tables,
  // paragraphs or emphasis. Each placeholder owns the exact original bytes.
  const sourceLines = original.split('\n'), protectedLines = [];
  for (let index = 0; index < sourceLines.length; index++) {
    const line = sourceLines[index], fence = line.match(/^\s*(`{3,}|~{3,})[^`~]*$/);
    if (!fence) { protectedLines.push(line); continue; }
    const start = index, code = [], closing = new RegExp(`^\\s*${fence[1][0]}{${fence[1].length},}\\s*$`);
    while (++index < sourceLines.length && !closing.test(sourceLines[index])) code.push(sourceLines[index]);
    protectedLines.push(stash(sourceLines.slice(start, index + 1).join('\n'), `<pre><code>${escape(code.join('\n'))}</code></pre>`, null, true));
  }
  let protectedText = protectedLines.join('\n').replace(/(`+)([^\n]*?)\1(?!`)|\[([^\]\n]+)\]\(([^)\n]+)\)|https?:\/\/[^\s<>]+/g, (raw, ticks, code, label, target) => {
    if (ticks) return stash(raw, `<code>${escape(code)}</code>`);
    if (label !== undefined) return stash(raw, target.startsWith('#') ? `<a href="${escape(target)}">${escape(label)}</a>` : `<span>${escape(label)}</span>`);
    return stash(raw, escape(raw));
  });
  // Prices are not TeX delimiters. Explicit numeric formulas such as $2x$ or
  // $1/2$ remain math; a currency amount followed by prose stays plain text.
  protectedText = protectedText.replace(/\$\d[\d,]*(?:\.\d+)?/g, (raw, offset, text) => {
    if (/[\\$]/.test(text[offset - 1] ?? '') || text[offset + raw.length] === '$') return raw;
    const end = text.indexOf('$', offset + raw.length), candidate = text.slice(offset + 1, end);
    if (end >= 0 && !candidate.includes('\n') && !/[\p{Script=Han}]|\b[A-Za-z]{2,}\b/u.test(candidate.replace(/\\[A-Za-z]+/g, '')) && !/\d/.test(text[end + 1] ?? '')) return raw;
    return stash(raw, escape(raw));
  });
  const protectMath = (text, accept = () => true) => mathParts(text).map(part => part.type === 'math'
    ? part.raw.includes(prefix) || !accept(part) ? part.raw : stash(part.raw, null, part, part.display)
    : part.value).join('');
  // Delimited formulas and multiline environments own their internal pipes.
  // Bare OCR math is then confined to each Markdown line/cell, so it cannot
  // absorb an adjacent score, item key or source-evidence column.
  protectedText = protectMath(protectedText, part => /^(?:\$|\\+[([])/.test(part.raw) || /\\begin\{/.test(part.raw));
  protectedText = protectedText.split(/((?<!\\)\||\r?\n)/).map(part => /^(?:\||\r?\n)$/.test(part) ? part : protectMath(part)).join('');
  let cursor = 0, previous = 0;
  for (const match of protectedText.matchAll(tokenPattern)) {
    cursor += match.index - previous;
    const token = tokens[match[1]];
    if (token.math) token.html = renderMath(token.math, cursor);
    cursor += token.raw.length; previous = match.index + match[0].length;
  }
  // Only attribute-free details/summary blocks are allowed; all other HTML stays inert.
  const inline = value => escape(value).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
  const cells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
  const separator = line => line?.includes('|') && cells(line).every(cell => /^:?-{3,}:?$/.test(cell));
  const render = source => {
    const lines = source.replace(/\r\n/g, '\n').split('\n'), blocks = [];
    for (let index = 0; index < lines.length; index++) {
      const line = lines[index];
      if (!line.trim()) continue;
      const loneToken = [...line.trim().matchAll(tokenPattern)];
      if (loneToken.length === 1 && loneToken[0][0] === line.trim() && tokens[loneToken[0][1]].block) { blocks.push(line.trim()); continue; }
      if (line.trim() === '<details>' && /^<summary>[^<>]+<\/summary>$/.test(lines[index + 1]?.trim() ?? '')) {
        const end = lines.indexOf('</details>', index + 2);
        // Nested or incomplete blocks are rendered literally, never repaired as executable HTML.
        if (end >= 0 && !lines.slice(index + 2, end).some(row => row.trim() === '<details>')) {
          const title = lines[index + 1].trim().slice(9, -10);
          blocks.push(`<details class="report-details"><summary>${inline(title)}</summary>${render(lines.slice(index + 2, end).join('\n'))}</details>`);
          index = end; continue;
        }
      }
      if (line.includes('|') && separator(lines[index + 1])) {
        const header = cells(line), alignment = cells(lines[++index]);
        const cellTag = (cell, column, tag) => `<${tag}${alignment[column]?.endsWith(':') ? ' class="numeric"' : ''}>${inline(cell)}</${tag}>`;
        const rows = [];
        while (lines[index + 1]?.trim().startsWith('|')) rows.push(cells(lines[++index]));
        blocks.push(`<div class="report-table" tabindex="0" role="region" aria-label="报告数据表，可横向滚动"><table><thead><tr>${header.map((cell, column) => cellTag(cell, column, 'th')).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${header.map((_cell, column) => cellTag(row[column] ?? '', column, 'td')).join('')}</tr>`).join('')}</tbody></table></div>`);
        continue;
      }
      const heading = line.match(/^(#{1,4})\s+(.+)$/);
      if (heading) {
        const base = rawText(heading[2]).toLowerCase().replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu, '').replace(/\s/g, '-') || 'section';
        let id = base, suffix = 1;
        while (headingIds.has(id)) id = `${base}-${suffix++}`;
        headingIds.add(id);
        blocks.push(`<h${heading[1].length} id="${escape(id)}">${inline(heading[2])}</h${heading[1].length}>`); continue;
      }
      if (/^\s*(?:-{3,}|\*{3,})\s*$/.test(line)) { blocks.push('<hr>'); continue; }
      if (/^>\s?/.test(line)) {
        const quoted = [line.replace(/^>\s?/, '')];
        while (/^>\s?/.test(lines[index + 1] ?? '')) quoted.push(lines[++index].replace(/^>\s?/, ''));
        blocks.push(`<blockquote>${quoted.filter(Boolean).map(text => `<p>${inline(text)}</p>`).join('')}</blockquote>`); continue;
      }
      const list = line.match(/^\s*(?:([-*])|(\d+)\.)\s+(.+)$/);
      if (list) {
        const tag = list[2] ? 'ol' : 'ul', pattern = list[2] ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
        const items = [list[3]];
        while (pattern.test(lines[index + 1] ?? '')) items.push(lines[++index].match(pattern)[1]);
        blocks.push(`<${tag}>${items.map(text => `<li>${inline(text)}</li>`).join('')}</${tag}>`); continue;
      }
      blocks.push(`<p>${inline(line)}</p>`);
    }
    return blocks.join('');
  };
  return render(protectedText).replace(tokenPattern, (_match, id) => tokens[id].html);
}
