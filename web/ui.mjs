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
export function markdown(body) {
  // Only attribute-free details/summary blocks are allowed; all other HTML stays inert.
  const inline = value => escape(value).replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, target) => target.startsWith('#')
      ? `<a href="${target}">${label}</a>` : `<span>${label}</span>`);
  const cells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
  const separator = line => line?.includes('|') && cells(line).every(cell => /^:?-{3,}:?$/.test(cell));
  const lines = String(body ?? '').replace(/\r\n/g, '\n').split('\n'), blocks = [];
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    if (!line.trim()) continue;
    if (line.trim() === '<details>' && /^<summary>[^<>]+<\/summary>$/.test(lines[index + 1]?.trim() ?? '')) {
      const end = lines.indexOf('</details>', index + 2);
      // Nested or incomplete blocks are rendered literally, never repaired as executable HTML.
      if (end >= 0 && !lines.slice(index + 2, end).some(row => row.trim() === '<details>')) {
        const title = lines[index + 1].trim().slice(9, -10);
        blocks.push(`<details class="report-details"><summary>${inline(title)}</summary>${markdown(lines.slice(index + 2, end).join('\n'))}</details>`);
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
    if (heading) { blocks.push(`<h${heading[1].length}${heading[1].length < 4 ? ` id="${escape(heading[2].toLowerCase().replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu, '').replace(/\s/g, '-'))}"` : ''}>${inline(heading[2])}</h${heading[1].length}>`); continue; }
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
}
