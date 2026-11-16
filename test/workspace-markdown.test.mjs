import test from 'node:test';
import assert from 'node:assert/strict';
import { markdown } from '../web/ui.mjs';

test('actual report structures render as readable tables, quotes and lists without losing pending values or escaped pipes', () => {
  const result = markdown('# 总览\n\n> **结论**\n> 总分待定\n\n| 题号 | 分数 | 依据 |\n| --- | ---: | --- |\n| Q(a) | 待定 | x \\| y |\n\n- 核查原页\n- 保存原判\n\n[总览](#总览)');
  assert.match(result, /<table><thead>/); assert.match(result, /<td class="numeric">待定<\/td>/);
  assert.match(result, /<td>x \| y<\/td>/); assert.match(result, /<blockquote><p><strong>结论/);
  assert.match(result, /<ul><li>核查原页<\/li><li>保存原判<\/li><\/ul>/);
  assert.match(result, /href="#总览"/); assert.match(result, /id="总览"/);
});

test('untrusted report content cannot create scripts, remote images, executable links or unescaped attributes', () => {
  const result = markdown('# " onmouseover="alert(1)\n<script>evil()</script>\n![img](https://example.com/track)\n[x](javascript:alert(1))\n[x](#&quot; onclick=&quot;evil)\n| a | b |\n| --- | --- |\n| <img onerror=evil> | **ok** |');
  assert.doesNotMatch(result, /<script|<img|href="javascript:|href="https:/);
  assert.match(result, /&lt;script&gt;/); assert.match(result, /<strong>ok<\/strong>/);
  assert.doesNotMatch(result, /id=""|href="#"/);
});

test('evidence disclosure retains full contents and rejects HTML attributes or executable summaries', () => {
  const result = markdown('<details>\n<summary>完整评分依据 · 1 个评分点</summary>\n\n**条件**：x > 0\n\n- 答卷第 2 页\n\n</details>');
  assert.match(result, /<details class="report-details"><summary>完整评分依据/);
  assert.match(result, /<strong>条件<\/strong>：x &gt; 0/);
  assert.match(result, /<ul><li>答卷第 2 页/);
  const hostile = markdown('<details ontoggle="evil()">\n<summary><img src=x onerror=evil()></summary>\nsecret\n</details>');
  assert.doesNotMatch(hostile, /<details|<summary|<img/);
  assert.match(hostile, /&lt;details/);
  assert.doesNotMatch(markdown('<details>\n<summary>Unclosed</summary>\ntext'), /<details/);
});

test('report item links and heading ids follow the same punctuation and case rules', () => {
  const result = markdown('[R(ii)](#rii) · [源-乙](#源-乙)\n\n### R(ii)\n\n### 源-乙');
  assert.match(result, /href="#rii"/); assert.match(result, /id="rii"/);
  assert.match(result, /id="源-乙"/);
});

test('repeated headings retain unique anchors across collapsed evidence and later chapters', () => {
  const result = markdown('## 相同标题\n\n<details>\n<summary>依据</summary>\n\n### 相同标题\n\n</details>\n\n## 相同标题\n\n#### point\n\n#### point');
  const ids = [...result.matchAll(/ id="([^"]+)"/g)].map(match => match[1]);
  assert.equal(ids.length, new Set(ids).size);
  assert.deepEqual(ids.slice(0, 3), ['相同标题', '相同标题-1', '相同标题-2']);
  assert.ok(ids.includes('point-1'));
});

test('fenced examples remain literal and do not become chapters, disclosures or executable HTML', () => {
  for (const fence of ['```', '~~~~']) {
    const result = markdown(`## 正文\n\n${fence}md\n## 不是章节\n<details>\n<summary>不是按钮</summary>\n<script>example()</script>\n${fence}\n\n## 附录`);
    assert.equal((result.match(/<h2 /g) ?? []).length, 2);
    assert.match(result, /<pre><code>## 不是章节/);
    assert.match(result, /&lt;script&gt;example/);
    assert.doesNotMatch(result, /<details|<script/);
  }
});
