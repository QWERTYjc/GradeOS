import katex from '../node_modules/katex/dist/katex.mjs';
import { splitMathText } from './math-text-parser.mjs';

const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

// Older reports use det[a,b;c,d], det[a b;c d] and Markdown-escaped
// \|a b;c d\|. Only square grids of simple scalar expressions qualify.
// TeX segments, code, ragged grids and prose are never reinterpreted as matrices.
function determinantParts(source) {
  const parts = []; let cursor = 0;
  for (const match of source.matchAll(/(?<![\w\\])(?:det\[([^\[\]\n]{1,2048})\]|\\\|([^|\n]{1,2048})\\\|)/g)) {
    if (match.index < cursor) continue;
    const rows = (match[1] ?? match[2]).split(';').map(row => row.trim().split(row.includes(',') ? /\s*,\s*/ : /\s+/));
    if (rows.length < 2 || rows.length > 12 || rows.some(row => row.length !== rows.length)) continue;
    if (rows.some(row => row.some(cell => !/^[+\-−]?(?:\d+(?:\.\d+)?|[A-Za-z])(?:[_^](?:\d+|[A-Za-z]))?(?:[+\-−*/](?:\d+(?:\.\d+)?|[A-Za-z])(?:[_^](?:\d+|[A-Za-z]))?)*$/.test(cell)))) continue;
    if (match.index > cursor) parts.push({ type: 'text', value: source.slice(cursor, match.index) });
    const cellText = cell => cell.replace(/([_^])([+\-]?\d+)/g, '$1{$2}');
    let value = `\\begin{vmatrix}${rows.map(row => row.map(cellText).join(' & ')).join(' \\\\ ')}\\end{vmatrix}`;
    cursor = match.index + match[0].length;
    // Keep an adjacent, explicitly bounded scalar denominator with the grid.
    // Unbalanced groups or non-scalar text stay outside the formula untouched.
    if (source[cursor] === '/') {
      const tail = source.slice(cursor + 1, cursor + 2049);
      let end = 0, depth = 0;
      if (tail[0] === '(') {
        for (let i = 0; i < tail.length && tail[i] !== '\n'; i++) {
          if (tail[i] === '(') depth++;
          if (tail[i] === ')' && --depth === 0) { end = i + 1; break; }
        }
      } else end = /^\d+(?:\.\d+)?(?!\w|\.\d)/.exec(tail)?.[0].length ?? 0;
      const denominator = tail.slice(tail[0] === '(' ? 1 : 0, tail[0] === '(' ? end - 1 : end);
      if (end && /^[\dA-Za-z()+\-*.\s^_]+$/.test(denominator) && !/[A-Za-z]{2}|[_^](?![+\-]?\d+|[A-Za-z])/.test(denominator)) {
        value = `\\dfrac{${value}}{${cellText(denominator)}}`; cursor += 1 + end;
      }
    }
    parts.push({ type: 'math', raw: source.slice(match.index, cursor), display: false, value });
  }
  if (cursor < source.length) parts.push({ type: 'text', value: source.slice(cursor) });
  return parts;
}

// The inherited parser normalizes OCR/serialized delimiters for display. Locate
// its results in the untouched input; never use normalized text as evidence.
function parsedMathParts(source) {
  const parts = []; let cursor = 0, searchCursor = 0;
  for (const segment of splitMathText(source)) {
    if (segment.type === 'text') {
      const start = source.indexOf(segment.value, searchCursor);
      if (start < 0) return [{ type: 'text', value: source }];
      searchCursor = start + segment.value.length; continue;
    }
    const candidates = [segment.raw];
    if (/^\\[([]/.test(segment.raw)) candidates.push(`\\${segment.raw.slice(0, -2)}\\${segment.raw.slice(-2)}`);
    const located = candidates.map(raw => ({ raw, start: source.indexOf(raw, searchCursor) }))
      .filter(row => row.start >= 0).sort((a, b) => a.start - b.start)[0];
    if (!located) continue;
    if (located.start > cursor) parts.push({ type: 'text', value: source.slice(cursor, located.start) });
    parts.push({ ...segment, raw: located.raw }); cursor = located.start + located.raw.length; searchCursor = cursor;
  }
  if (cursor < source.length) parts.push({ type: 'text', value: source.slice(cursor) });
  return parts;
}

export function mathParts(source) {
  const parts = parsedMathParts(source), explicit = []; let offset = 0;
  for (const part of parts) {
    const raw = part.type === 'math' ? part.raw : part.value;
    if (part.type === 'math' && /^(?:\$|\\+[([])/.test(raw)) explicit.push({ start: offset, end: offset + raw.length });
    offset += raw.length;
  }
  const matrices = []; offset = 0;
  for (const part of determinantParts(source)) {
    const raw = part.type === 'math' ? part.raw : part.value, end = offset + raw.length;
    if (part.type === 'math' && !explicit.some(span => span.start < end && span.end > offset)) matrices.push({ part, start: offset, end });
    offset = end;
  }
  if (!matrices.length) return parts;
  const result = []; let cursor = 0;
  for (const matrix of matrices) {
    result.push(...parsedMathParts(source.slice(cursor, matrix.start)), matrix.part); cursor = matrix.end;
  }
  return result.concat(parsedMathParts(source.slice(cursor)));
}

export function renderMath(segment, start) {
  const source = `data-math-source="${escape(segment.raw)}" data-source-start="${start}" data-source-end="${start + segment.raw.length}"`;
  try {
    if (segment.value.length > 8192) throw Error('Formula too long');
    let blocked = false;
    // Native MathML needs explicit stretching for fences such as the ∣ operator.
    const html = katex.renderToString(segment.value, {
      displayMode: segment.display, output: 'mathml', throwOnError: true,
      strict: code => code === 'unicodeTextInMathMode' ? 'ignore' : 'error',
      trust: () => { blocked = true; return false; }, maxExpand: 256, maxSize: 12, macros: {},
    }).replace(/<mo fence="true">/g, '<mo fence="true" stretchy="true">');
    if (blocked) throw Error('Unsupported command');
    return `<span class="report-math${segment.display ? ' report-math-display' : ''}" ${source} title="${escape(segment.raw)}">${html}</span>`;
  } catch {
    // Uncertain/unsupported formulas remain exact source, never a guessed result.
    return `<code class="report-math report-math-fallback" ${source} title="公式未排版，保留原文；可在编辑中核对。">${escape(segment.raw)}</code>`;
  }
}

export function sourceText(node) {
  const copy = node.cloneNode(true);
  for (const math of copy.querySelectorAll('[data-math-source]')) math.replaceWith(math.dataset.mathSource);
  return copy.textContent;
}

// Expand a selection inside a formula to its complete, original source. Mixed
// text selections must match the source exactly; ambiguous formatting stays in
// the existing source-editor flow instead of inventing character offsets.
export function sourceSelection(preview, selection, source) {
  if (!selection?.rangeCount || selection.isCollapsed || !preview.contains(selection.anchorNode) || !preview.contains(selection.focusNode)) return null;
  const range = selection.getRangeAt(0);
  const formulas = [...preview.querySelectorAll('[data-math-source]')].filter(node => range.intersectsNode(node));
  if (formulas.length === 1 && formulas[0].contains(selection.anchorNode) && formulas[0].contains(selection.focusNode)) {
    const node = formulas[0], start = Number(node.dataset.sourceStart), end = Number(node.dataset.sourceEnd);
    if (source.slice(start, end) === node.dataset.mathSource) return { start, end, quote: source.slice(start, end) };
    return null;
  }
  const quote = formulas.length ? sourceText(range.cloneContents()) : selection.toString();
  if (!quote) return null;
  const candidates = []; let start = source.indexOf(quote);
  while (start >= 0) {
    if (formulas.every(node => Number(node.dataset.sourceStart) >= start && Number(node.dataset.sourceEnd) <= start + quote.length)) candidates.push(start);
    start = source.indexOf(quote, start + 1);
  }
  return candidates.length === 1 ? { start: candidates[0], end: candidates[0] + quote.length, quote } : null;
}
