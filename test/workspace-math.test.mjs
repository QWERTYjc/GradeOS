import assert from 'node:assert/strict';
import { test } from 'node:test';
import { markdown } from '../web/ui.mjs';
import { mathParts } from '../web/report-math.mjs';

const unescape = text => text.replace(/&(amp|lt|gt|quot|#39);/g, (_match, key) => ({ amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'" }[key]));
const formulas = html => [...html.matchAll(/data-math-source="([^"]*)" data-source-start="(\d+)" data-source-end="(\d+)"/g)]
  .map(([, raw, start, end]) => ({ raw: unescape(raw), start: Number(start), end: Number(end) }));
const verifySources = (body, html = markdown(body)) => {
  for (const { raw, start, end } of formulas(html)) assert.equal(body.slice(start, end), raw);
  return html;
};

test('fractions, combined scripts, integrals and multiline matrices produce semantic MathML', () => {
  const source = String.raw`# 数学反馈
## 依据
分数 $\frac{a+b}{2}$；上下标 \(x_i^2\)。
\[
\int_0^1 x^2\,\mathrm{d}x = \frac{1}{3}
\]
$$
\begin{pmatrix}
1 & 2 \\
3 & 4
\end{pmatrix}
$$
## 建议
保留每个评分点的原文。`;
  const html = verifySources(source);
  for (const tag of ['mfrac', 'msubsup', 'mtable', 'mtr', 'mtd']) assert.match(html, new RegExp(`<${tag}[ >]`));
  assert.match(html, /∫/); assert.equal((html.match(/<math /g) ?? []).length, 4);
  assert.equal((html.match(/<h2 /g) ?? []).length, 2);
  assert.doesNotMatch(html, /report-math-fallback/);
});

test('formula pipes, underscores and stars do not split tables or become emphasis', () => {
  const source = String.raw`| 评分点 | 完整依据 | 分值 |
|---|---|---:|
| Q1/M1 | $\left|\begin{matrix}a&b\\c&d\end{matrix}\right|$，$x_i * y_i$ | 1 / 2 |`;
  const html = verifySources(source);
  assert.equal((html.match(/<td[ >]/g) ?? []).length, 3);
  assert.equal(formulas(html).length, 2); assert.match(html, /<mtable/);
  assert.doesNotMatch(html, /<em>|report-math-fallback/);
});

test('bare OCR working cannot swallow neighboring legacy scoring-ledger columns', () => {
  const source = '| 评分点 | 得分 | 答卷证据 | 原始理由 | MS 条件 | 答卷页 | 定位 |\n|---|---|---|---|---|---|---|\n| 1/m1 | 1 / 1 | (2−3x)^5=32−240x+720x² | Full criterion met. | Expand (2−3x)^5. | 2 | 1 处 |';
  const html = verifySources(source);
  assert.equal((html.match(/<td[ >]/g) ?? []).length, 7);
  assert.match(html, /<td>1\/m1<\/td><td>1 \/ 1<\/td>/);
  assert.match(html, /<td>Full criterion met\.<\/td>/);
  assert.ok(formulas(html).length > 0); assert.ok(formulas(html).every(row => !row.raw.includes('|')));
});

test('inline code, longer fences, links, prices and document identifiers stay literal', () => {
  const inlineCode = String.fromCharCode(96) + String.raw`$\frac{1}{2}$ **literal**` + String.fromCharCode(96);
  const source = String.raw`成本 $0.012，报告 $0.03；范围 $5-$10。
总分 74 / 100；版本 version_1；路径 https://example.test/x_i?f=1
代码 ${inlineCode}。
[原始 x_i](#source_x_i)
~~~tex
$$\frac{3}{4}$$
## 不是章节
~~~~
最后 $\frac{5}{6}$。`;
  const html = verifySources(source);
  assert.equal(formulas(html).length, 1); assert.doesNotMatch(html, /<h2|<strong>/);
  assert.match(html, /href="#source_x_i"/); assert.match(html, /\$0\.012/);
  assert.match(html, /<pre><code>\$\$/); assert.match(html, /总分 74 \/ 100/);
});

test('legacy Unicode calculus and scripts retain exact source, including serialized delimiters', () => {
  const source = String.raw`先算 ∫₀^(π/4)(3cosx−sinx)/(3sinx+cosx)dx，再写 π + (3/2)ln2。
矩阵幂 (A²)^2000，公式 \\(x^2\\)，重复 $x^2$ 与 $x^2$。`;
  const parts = mathParts(source);
  assert.equal(parts.map(part => part.type === 'math' ? part.raw : part.value).join(''), source);
  const html = verifySources(source);
  assert.ok(formulas(html).length >= 5); assert.match(html, /<msup/); assert.match(html, /<mfrac/);
  const repeated = formulas(html).filter(row => row.raw === '$x^2$');
  assert.equal(repeated.length, 2); assert.notEqual(repeated[0].start, repeated[1].start);
});

test('a later formula does not claim an identical substring inside an earlier identifier', () => {
  const source = 'version_x^{2} is an identifier; 结果为 x^{2}。';
  const parts = mathParts(source), html = verifySources(source);
  assert.equal(parts[0].type, 'text'); assert.match(parts[0].value, /^version_x\^\{2\}/);
  assert.equal(formulas(html).length, 1); assert.equal(formulas(html)[0].start, source.lastIndexOf('x^{2}'));
});

test('bare multi-digit and signed script values stay together instead of leaking digits onto the baseline', () => {
  const source = 'The terms x^2000 and y_12 and z^-1 remain exact evidence; version_12 stays text.';
  const html = verifySources(source);
  assert.deepEqual(formulas(html).map(row => row.raw), ['x^2000', 'y_12', 'z^-1']);
  assert.match(html, /<mn>2000<\/mn>/); assert.match(html, /<mn>12<\/mn>/);
  assert.match(html, /version_12 stays text/);
});

test('legacy determinant notation renders rows while ragged grids and code remain source', () => {
  const source = '行列式 det[1,2,3;s+1,4,5;s,6,7]；另一写法 det[i j k; -2 0 -1; 2 -1 1]。不完整 det[1,2;3]；`det[1,2;3,4]` 为代码。';
  const html = verifySources(source);
  assert.equal((html.match(/<mtable/g) ?? []).length, 2);
  assert.equal((html.match(/<mtr/g) ?? []).length, 6);
  assert.match(html, /不完整 det\[1,2;3\]/); assert.match(html, /<code>det\[1,2;3,4\]<\/code>/);
  assert.match(markdown('det[x^20,2;3,x_12]'), /<msup><mi>x<\/mi><mn>20<\/mn><\/msup>/);
});

test('escaped determinant bars render square grids without changing evidence or table columns', () => {
  const source = String.raw`## Evidence
First \|3 5;u+2 7\|, then \|a_12,2,3;4,b^20,6;7,8,c\|.
| Criterion | Evidence | Score |
|---|---|---:|
| P/m | \|p q;r s\| | 1 / 2 |`;
  const html = verifySources(source);
  assert.equal((html.match(/<mtable/g) ?? []).length, 3);
  assert.equal((html.match(/<mo fence="true" stretchy="true">∣/g) ?? []).length, 6);
  assert.equal((html.match(/<mtr/g) ?? []).length, 7);
  assert.equal((html.match(/<td[ >]/g) ?? []).length, 3);
  assert.equal(formulas(html).length, 3);
  assert.doesNotMatch(html, /report-math-fallback/);
  assert.match(html, /<mn>12<\/mn>/); assert.match(html, /<mn>20<\/mn>/);
  for (const source of [String.raw`\|a b;c\|`, String.raw`\|a b;c d;e f\|`, String.raw`\|one two;three four\|`, String.raw`\|x\|`, '`\\|a b;c d\\|`', String.raw`$\|a b;c d\|$`]) {
    assert.doesNotMatch(verifySources(source), /<mtable/);
  }
});

test('determinant fractions include only their bounded denominator and preserve neighboring prose', () => {
  const source = String.raw`x=\|3 5;u+2 7\|/(4(3)^2-2(3)+9); y=det[a,b;c,d]/7. Continue reviewing.`;
  const html = verifySources(source);
  assert.equal((html.match(/<mfrac/g) ?? []).length, 2);
  assert.equal((html.match(/<mtable/g) ?? []).length, 2);
  assert.doesNotMatch(html, /report-math-fallback/);
  assert.equal(formulas(html)[0].raw, String.raw`\|3 5;u+2 7\|/(4(3)^2-2(3)+9)`);
  assert.equal(formulas(html)[1].raw, 'det[a,b;c,d]/7');
  for (const suffix of ['/(a+b', '/(ordinary text)', '/3x', '/(a/b)', '/(a^(b+c))']) {
    const raw = 'det[a,b;c,d]' + suffix;
    assert.equal(formulas(verifySources(raw))[0].raw, 'det[a,b;c,d]');
  }
});

test('bare power chains nest rightward while explicit grouping, scripts and source remain unchanged', () => {
  const examples = [
    ["g''=3t(4t^2-5)e^-t^2<0", "g''=3t(4t^2-5)e^{-t^{2}}<0"],
    ['y=a^b^3', 'y=a^{b^{3}}'],
    ['y=a^-b^-c^12', 'y=a^{-b^{-c^{12}}}'],
    ['y=2^3^4', 'y=2^{3^{4}}'],
    ['y=x_i^20+(a^b)^2', 'y=x_i^{20}+(a^b)^2'],
  ];
  for (const [source, expected] of examples) {
    assert.equal(mathParts(source)[0].value, expected);
    assert.doesNotMatch(verifySources(source), /report-math-fallback/);
  }
  assert.equal(mathParts('$a^{-b}{}^2$')[0].value, 'a^{-b}{}^2');
  assert.match(verifySources('$a^b^2$'), /report-math-fallback/);
  assert.match(verifySources('`y=a^-b^2`'), /<code>y=a\^-b\^2<\/code>/);
  assert.match(verifySources('y=x' + '^2'.repeat(1000)), /report-math-fallback/);
});

test('source positions survive collapsed evidence, CRLF, code, links and token-like input', () => {
  const source = ['## Evidence', 'Prefix \uE0000\uE001 and `x_i` [MS](#ms-page-2)', '<details>', '<summary>完整依据</summary>', '', String.raw`$\frac{1}{2}$，$\frac{1}{2}$`, '', '</details>', '## Next', String.raw`\[x_i^2\]`].join('\r\n');
  const html = verifySources(source);
  assert.equal(formulas(html).length, 3); assert.match(html, /<details/); assert.match(html, /href="#ms-page-2"/);
});

test('unsupported and unsafe commands retain escaped original evidence without active HTML', () => {
  for (const formula of [String.raw`$\notACommand{a}$`, String.raw`$\frac{1}{$`, String.raw`$\href{javascript:alert(1)}{x}$`, String.raw`$\htmlClass{evil}{x}$`, String.raw`$\def\a{\a}\a$`, String.raw`$\text{<script>alert(1)</script>}\notACommand$`]) {
    const html = verifySources(formula);
    assert.match(html, /report-math-fallback/); assert.equal(formulas(html)[0].raw, formula);
    assert.doesNotMatch(html, /<script|<a |class="evil"|<img/);
  }
  assert.equal(markdown(String.raw`$\href{https://example.test}{x}$`), String.raw`<p>$\href{https://example.test}{x}$</p>`);
});

test('formula headings have stable unique anchors and summaries do not duplicate math source', () => {
  const source = '## $x_i$\n\n<details>\n<summary>完整依据</summary>\n\n### $x_i$\n\n</details>\n\n## $x_i$';
  const html = verifySources(source), ids = [...html.matchAll(/<h\d id="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(ids, ['x_i', 'x_i-1', 'x_i-2']); assert.equal(formulas(html).length, 3);
});
