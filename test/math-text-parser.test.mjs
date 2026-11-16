import assert from 'node:assert/strict';
import { test } from 'node:test';
import katex from 'katex';

import { findMathSourceSpans, splitMathText } from '../web/math-text-parser.mjs';

test('parses all explicit delimiters without consuming adjacent prose', () => {
  const segments = splitMathText('A $x^2$ B \\(y+1\\) C $$z$$ D \\[w\\] end');
  assert.deepEqual(
    segments.filter((segment) => segment.type === 'math').map(({ value, display }) => ({ value, display })),
    [
      { value: 'x^2', display: false },
      { value: 'y+1', display: false },
      { value: 'z', display: true },
      { value: 'w', display: true },
    ],
  );
  assert.equal(segments.at(-1).value, ' end');
});

test('keeps escaped and unclosed delimiters as source text', () => {
  const segments = splitMathText('Cost \\$5 and unfinished $x + 1');
  assert.deepEqual(segments, [{ type: 'text', value: 'Cost \\$5 and unfinished $x + 1' }]);
});

test('recognizes conservative balanced bare LaTeX only', () => {
  const segments = splitMathText('结果为 \\frac{1}{2}，version_1 stays prose and x^{2} renders.');
  const math = segments.filter((segment) => segment.type === 'math').map((segment) => segment.value);
  assert.deepEqual(math, ['\\frac{1}{2}', 'x^{2}']);
  assert.match(segments.filter((segment) => segment.type === 'text').map((segment) => segment.value).join(''), /version_1/);
});

test('rejects unbalanced bare commands and supports multiline display math', () => {
  const segments = splitMathText('bad \\frac{1}{2 then\n\\[a+b\\]');
  assert.equal(segments[0].type, 'text');
  assert.match(segments[0].value, /\\frac/);
  assert.deepEqual(segments.at(-1), {
    type: 'math',
    value: 'a+b',
    raw: '\\[a+b\\]',
    display: true,
  });
});

test('recognizes a closed multiline environment but preserves an unclosed one', () => {
  const closed = '\\begin{aligned}\na &= b \\\\\nc &= d\n\\end{aligned}';
  assert.deepEqual(splitMathText(closed), [{
    type: 'math',
    value: closed,
    raw: closed,
    display: true,
  }]);
  assert.deepEqual(splitMathText('\\begin{aligned} a &= b'), [{
    type: 'text',
    value: '\\begin{aligned} a &= b',
  }]);
});

test('keeps nested environments together and rejects incomplete bare scripts', () => {
  const nested = [
    '\\begin{array}{rl}',
    '{\\left|\\begin{array}{ll}1&2\\\\3&4\\end{array}\\right|}&=2',
    '\\end{array}',
  ].join('');

  assert.deepEqual(splitMathText(nested), [
    { type: 'math', value: nested, raw: nested, display: true },
  ]);
  assert.deepEqual(splitMathText('value \\sin^ {2}(x)'), [
    { type: 'text', value: 'value \\sin^ {2}(x)' },
  ]);
});

test('renders OCR-style calculus notation while preserving the original source as raw text', () => {
  const samples = [
    ['pi/2', '\\frac{\\pi}{2}'],
    ['sin^2(h/2)', '\\sin^2(\\frac{h}{2})'],
    ['lim_{h->0}', '\\lim_{h\\to 0}'],
    [
      '(f(pi/2+h)-f(pi/2))/h',
      '\\frac{f(\\frac{\\pi}{2}+h)-f(\\frac{\\pi}{2})}{h}',
    ],
  ];

  samples.forEach(([raw, value]) => {
    assert.deepEqual(splitMathText(raw), [{
      type: 'math',
      value,
      raw,
      display: false,
    }]);
  });
});

test('segments the screenshot-style limit expression without absorbing surrounding prose', () => {
  const source = [
    'Use lim_{h->0} (f(pi/2+h)-f(pi/2))/h',
    'or sin^2(h/2), then compare with pi/2.',
  ].join(' ');
  const math = splitMathText(source)
    .filter((segment) => segment.type === 'math')
    .map(({ raw, value }) => ({ raw, value }));

  assert.deepEqual(math, [
    { raw: 'lim_{h->0}', value: '\\lim_{h\\to 0}' },
    {
      raw: '(f(pi/2+h)-f(pi/2))/h',
      value: '\\frac{f(\\frac{\\pi}{2}+h)-f(\\frac{\\pi}{2})}{h}',
    },
    { raw: 'sin^2(h/2)', value: '\\sin^2(\\frac{h}{2})' },
    { raw: 'pi/2', value: '\\frac{\\pi}{2}' },
  ]);
  assert.equal(
    splitMathText(source).filter((segment) => segment.type === 'text').map(({ value }) => value).join(''),
    'Use   or , then compare with .',
  );
});

test('keeps ordinary English, Chinese, paths, dates, and weak slash patterns as prose', () => {
  const prose = [
    'The pilot described a limitation and a single option; sin (a moral failing) stays prose.',
    'Keep path/to/file, and/or, 2026/08/20, x/2, f(x), 中文“和/或” unchanged.',
    '提交日期 [2026/08/20]、[20/8/26]；区间标签 [1/2/3] 和 [1/2] 保持原文。',
  ].join(' ');

  assert.deepEqual(splitMathText(prose), [{ type: 'text', value: prose }]);
});

test('renders complete OCR-style working lines as single conservative math segments', () => {
  const formulas = [
    {
      raw: '= -(pi/2+h)cos h + pi/2 sin pi/2',
      value: '= -(\\frac{\\pi}{2}+h)\\cos h + \\frac{\\pi}{2} \\sin \\frac{\\pi}{2}',
    },
    {
      raw: '= pi/2[-2sin(h/2)sin(-h/2)] - hcos h = pi sin^2(h/2) - hcos h = RHS',
      value: [
        '= \\frac{\\pi}{2}[-2\\sin(\\frac{h}{2})\\sin(-\\frac{h}{2})]',
        '- h \\cos h = \\pi \\sin^2(\\frac{h}{2}) - h \\cos h = \\mathrm{RHS}',
      ].join(' '),
    },
    {
      raw: "f'(pi/2) = lim_{h->0} {f(pi/2+h)-f(pi/2)}/h = lim_{h->0} (pi sin^2(h/2)-hcos h)/h",
      value: [
        "f'(\\frac{\\pi}{2}) = \\lim_{h\\to 0}",
        '\\frac{f(\\frac{\\pi}{2}+h)-f(\\frac{\\pi}{2})}{h}',
        '= \\lim_{h\\to 0} \\frac{\\pi \\sin^2(\\frac{h}{2})-h \\cos h}{h}',
      ].join(' '),
    },
    {
      raw: '= 1/2 lim_{h->0} pi sin(h/2) . lim_{h->0} sin(h/2)/(h/2) - lim_{h->0} cos h = -1',
      value: [
        '= \\frac{1}{2} \\lim_{h\\to 0} \\pi \\sin(\\frac{h}{2})',
        '\\cdot \\lim_{h\\to 0} \\frac{\\sin(\\frac{h}{2})}{\\frac{h}{2}}',
        '- \\lim_{h\\to 0} \\cos h = -1',
      ].join(' '),
    },
  ];

  formulas.forEach(({ raw, value }) => {
    assert.deepEqual(splitMathText(raw), [{ type: 'math', value, raw, display: false }]);
    assert.doesNotThrow(() => katex.renderToString(value, {
      displayMode: false,
      output: 'htmlAndMathml',
      strict: 'error',
      throwOnError: true,
      trust: false,
    }));
  });
});

test('renders matrix working and inline feedback formulas from the result screenshots', () => {
  const fullLines = [
    '(A-I)(A^2+A+I) = (A-I)0',
    'A^3 = I',
    '(A^{1000}+(A^{-1})^{2000})^{-1} = [(A^3)^{333}\\cdot A+(A^2)^{2000}]^{-1}',
    '= (I\\cdot A+(A^3)^{666}\\cdot A^2)^{-1} = (A^2+A)^{-1}',
  ];
  fullLines.forEach((source) => {
    const segments = splitMathText(source);
    assert.equal(segments.length, 1);
    assert.equal(segments[0].type, 'math');
    assert.doesNotThrow(() => katex.renderToString(segments[0].value, {
      displayMode: false,
      output: 'htmlAndMathml',
      strict: 'error',
      throwOnError: true,
      trust: false,
    }));
  });

  const mixed = splitMathText(
    '把第9题面积计算中 [-x^2/(2e) + 2x/e]_0^1 与指数积分项的数值分步重算一遍。',
  );
  assert.equal(mixed.filter((segment) => segment.type === 'math').length, 1);
  assert.equal(mixed.find((segment) => segment.type === 'math')?.raw, '[-x^2/(2e) + 2x/e]_0^1');

  const commands = splitMathText('A\\cdot A^2 = I \\implies A^{-1} = A^2');
  assert.deepEqual(commands, [{
    type: 'math',
    value: 'A\\cdot A^2 = I \\implies A^{-1} = A^2',
    raw: 'A\\cdot A^2 = I \\implies A^{-1} = A^2',
    display: false,
  }]);
});

test('preserves authoritative LaTeX commands on OCR-style formula lines', () => {
  const cases = [
    '= \\sin(x)+1',
    '= \\pi/2',
    '= \\sqrt{x}+1',
  ];
  for (const source of cases) {
    const segments = splitMathText(source);
    assert.equal(segments.length, 1);
    assert.equal(segments[0].type, 'math');
    assert.equal(segments[0].value, source);
    const html = katex.renderToString(segments[0].value, {
      output: 'htmlAndMathml',
      throwOnError: true,
      trust: false,
    });
    assert.doesNotMatch(html, /mspace newline/);
    if (source.includes('sin')) assert.match(html, /class="mop"/);
    if (source.includes('pi')) assert.match(html, /π/);
  }

  const mixedCases = [
    ['= pi/2 + \\sin(x)', '= \\frac{\\pi}{2} + \\sin(x)'],
    ['= sqrt(x)+\\cos(x)', '= \\sqrt{x}+\\cos(x)'],
    ['= \\lim_{h->0} f(h)', '= \\lim_{h\\to 0} f(h)'],
    ['= \\frac{pi}{2}', '= \\frac{\\pi}{2}'],
    ['= \\text{pi/2}', '= \\text{pi/2}'],
    ['= \\text{RHS}', '= \\text{RHS}'],
    ['= \\text{x/y}', '= \\text{x/y}'],
  ];
  for (const [source, expected] of mixedCases) {
    const segments = splitMathText(source);
    assert.equal(segments.length, 1);
    assert.equal(segments[0].type, 'math');
    assert.equal(segments[0].value, expected);
    const html = katex.renderToString(segments[0].value, {
      output: 'htmlAndMathml',
      throwOnError: true,
      trust: false,
    });
    assert.doesNotMatch(html, /mspace newline/);
  }
});

test('renders conservative full-line algebra beyond the screenshot fixture', () => {
  const formulas = [
    ['= x/2 + 1', '= \\frac{x}{2} + 1'],
    ['= sqrt(x)+1', '= \\sqrt{x}+1'],
    ['= x^2/2+y^2', '= \\frac{x^2}{2}+y^2'],
    ['= x^{2}/2', '= \\frac{x^{2}}{2}'],
    ['= (x+y)^2/2', '= \\frac{(x+y)^2}{2}'],
    ['= x_1/2', '= \\frac{x_1}{2}'],
    ['= x/y^2', '= \\frac{x}{y^2}'],
    ['= x^-2/2', '= \\frac{x^{-2}}{2}'],
    ['= x_-1/2', '= \\frac{x_{-1}}{2}'],
    ['= sin^{-1}(x)/2', '= \\frac{\\sin^{-1}(x)}{2}'],
    ["= f''(x)/2", "= \\frac{f''(x)}{2}"],
    ["= x''/2", "= \\frac{x''}{2}"],
    ["= f_n''(x)/2", "= \\frac{f_n''(x)}{2}"],
    ["= x/f_1'(y)", "= \\frac{x}{f_1'(y)}"],
    ['= sin^(-1)(x)/2', '= \\frac{\\sin^{-1}(x)}{2}'],
    ['= asin(x)/2', '= \\frac{\\arcsin(x)}{2}'],
    ['= sqrt x + 1', '= \\sqrt{x} + 1'],
    ['= sqrt -x + 1', '= \\sqrt{-x} + 1'],
    ['= sqrt{x}+1', '= \\sqrt{x}+1'],
    ['= sqrt(f^(-1)(x))+1', '= \\sqrt{f^{-1}(x)}+1'],
    ['= lim h->0', '= \\lim h\\to 0'],
    ['= x^(2)+1', '= x^{2}+1'],
    ['= x^2y+1', '= x^2y+1'],
    ['= x^-2y+1', '= x^{-2}y+1'],
    ['= x^-2.5+1', '= x^{-2.5}+1'],
    ['= log(x)+1', '= \\log(x)+1'],
    ['= ln(x)+1', '= \\ln(x)+1'],
    ['= log_2(x)/2', '= \\frac{\\log_2(x)}{2}'],
    ['= alpha/2+beta', '= \\frac{\\alpha}{2}+\\beta'],
    ['= theta^2', '= \\theta^2'],
    ['= dy/dx', '= \\frac{dy}{dx}'],
    ['= d/dx f(x)', '= \\frac{d}{dx} f(x)'],
    ['= d^2/dx^2 f(x)', '= \\frac{d^2}{dx^2} f(x)'],
    ['= 2pi', '= 2\\pi'],
    ['= pi2', '= \\pi2'],
    ['= 2asin(x)', '= 2\\arcsin(x)'],
    ['= 2alpha', '= 2\\alpha'],
    ['= x_alpha', '= x_\\alpha'],
    ['= x_pi', '= x_\\pi'],
    ['= x_{sin(x)}', '= x_{\\sin(x)}'],
    ['= x^{log(x)}', '= x^{\\log(x)}'],
    ['= x^{-alpha}', '= x^{-\\alpha}'],
    ['= x^(-alpha)', '= x^{-\\alpha}'],
  ];

  formulas.forEach(([raw, value]) => {
    assert.deepEqual(splitMathText(raw), [{ type: 'math', value, raw, display: false }]);
    assert.doesNotThrow(() => katex.renderToString(value, {
      displayMode: false,
      output: 'htmlAndMathml',
      strict: 'error',
      throwOnError: true,
      trust: false,
    }));
  });
});

test('keeps unsafe or prose-like full lines out of automatic math rendering', () => {
  const proseLines = [
    '= ordinary English',
    '= path/to/file',
    '= 2026/08/20',
    '= 20/08/2026',
    '= 08/20/2026',
    '= 20/8/26',
    '= 1/2/3',
    '= version_1',
    '= x//2',
    '= x/',
    '= sqrt(x',
    '= x + hello',
    '= x + * y',
    '= x/*2',
    '= x = = y',
    '= ..',
    '= x^((2))+1',
    '= sin^((-1))(x)/2',
    '= x_',
    '= x__2',
    '= x_^2',
    '= x^_2',
    '= x^(sin(x))+1',
    '= x_(f(n))',
    '= sqrt f(x)',
    '= sqrt sin(x)',
    '= sqrt arcsin(x)+1',
    "= sqrt f'(x)+1",
    "= sqrt x''(y)+1",
    '= sqrt log_2(x)',
    '= sqrt -f(x)+1',
    '= sqrt f^(-1)(x)+1',
    '= d^2y/dx^2',
    '= d^2 y/dx^2',
    '= d^2 f(x)/dx^2',
    '= d^2 sin(x)/dx^2',
    '= d^2 alpha/dx^2',
    '= x_sin(x)+1',
    '= x^log(x)+1',
    '= x_asin(x)+1',
    '= sin^cos(x)',
    '= x^-alpha+1',
    '= x_-pi+1',
    '= x^-sin(x)+1',
    '= log_-alpha(x)',
    '= alphabet',
    '= do/it',
    'Keep x/2 and sqrt(x) as examples.',
  ];

  proseLines.forEach((source) => {
    assert.deepEqual(splitMathText(source), [{ type: 'text', value: source }]);
  });
});

test('fails long OCR fraction chains to text without overflowing the call stack', () => {
  const source = `= ${Array.from({ length: 10_000 }, () => 'x/x').join('+')}`;
  assert.doesNotThrow(() => splitMathText(source));
  assert.deepEqual(splitMathText(source), [{ type: 'text', value: source }]);
});

test('quarantines unsafe OCR lines while still rendering conservative LaTeX commands', () => {
  for (const source of [
    '= \\frac{x}{2}+1',
    '= x + \\sqrt{y}',
    '= \\sin(x)+1',
  ]) {
    const segments = splitMathText(source);
    assert.ok(segments.some((segment) => segment.type === 'math'));
    assert.doesNotMatch(
      segments.filter((segment) => segment.type === 'text').map((segment) => segment.value).join(''),
      /\\(?:frac|sqrt|sin)/,
    );
  }

  const mixed = splitMathText('= x^(sin(x)) + \\frac{1}{2}');
  assert.deepEqual(
    mixed.filter((segment) => segment.type === 'math').map((segment) => segment.value),
    ['\\frac{1}{2}'],
  );
  assert.match(
    mixed.filter((segment) => segment.type === 'text').map((segment) => segment.value).join(''),
    /x\^\(sin\(x\)\)/,
  );
  assert.deepEqual(splitMathText('= C:\\path'), [{ type: 'text', value: '= C:\\path' }]);
});

test('maps serialized math delimiters back to their original source offsets', () => {
  const source = 'before \\\\(x^2\\\\) after';
  const spans = findMathSourceSpans(source);
  assert.deepEqual(spans, [{ start: 7, end: 16 }]);
  assert.equal(source.slice(spans[0].start, spans[0].end), '\\\\(x^2\\\\)');
});

test('does not absorb a prose prefix into an OCR-style formula segment', () => {
  const source = 'Apply formula: = pi/2 sin pi/2';
  const segments = splitMathText(source);

  assert.deepEqual(segments[0], { type: 'text', value: 'Apply formula: = ' });
  assert.equal(segments.some((segment) => segment.type === 'math' && segment.raw === source), false);
  assert.equal(segments.filter((segment) => segment.type === 'math').length, 2);
});

test('scans long non-formula lines without quadratic line-prefix work', () => {
  const source = ' '.repeat(50_000);
  const startedAt = performance.now();

  assert.deepEqual(splitMathText(source), [{ type: 'text', value: source }]);
  assert.ok(
    performance.now() - startedAt < 2_000,
    'plain OCR lines should be scanned in bounded linear time',
  );
});

test('renders Unicode OCR integrals, bounds, fractions, and compact functions', () => {
  const cases = [
    ['4(3sinx+cosx)+(3cosx−sinx);', '4(3\\sin x+\\cos x)+(3\\cos x-\\sin x);'],
    [
      '4∫₀^(π/4)dx + ∫₀^(π/4)(3cosx−sinx)/(3sinx+cosx)dx',
      '4\\int _{0}^{\\frac{\\pi}{4}}dx + \\int _{0}^{\\frac{\\pi}{4}}\\frac{3\\cos x-\\sin x}{3\\sin x+\\cos x}dx',
    ],
    ['π + [ln|3sinx+cosx|]₀^(π/4)', '\\pi + [\\ln|3\\sin x+\\cos x|]_{0}^{\\frac{\\pi}{4}}'],
    ['π + (3/2)ln2', '\\pi + (\\frac{3}{2})\\ln2'],
    ['∫₁² x² dx', '\\int _{1}^{2} x^{2} dx'],
    ['α² + β² = γ²', '\\alpha^{2} + \\beta^{2} = \\gamma^{2}'],
    ['ε + ϵ + φ + ϕ + ς = σ', '\\varepsilon + \\epsilon + \\varphi + \\phi + \\varsigma = \\sigma'],
    ['θ + φ', '\\theta + \\varphi'],
    ['sinπ + cosθ = 0', '\\sin \\pi + \\cos \\theta = 0'],
    ['xπ = 2π', 'x \\pi = 2\\pi'],
    ['y = 2√2', 'y = 2\\sqrt{2}'],
  ];

  for (const [raw, value] of cases) {
    assert.deepEqual(splitMathText(raw), [{ type: 'math', value, raw, display: false }]);
    const html = katex.renderToString(value, {
      output: 'htmlAndMathml', strict: 'error', throwOnError: true, trust: false,
    });
    assert.doesNotMatch(html, /mspace newline/);
  }
});

test('keeps prose between OCR equations and around Unicode evaluation bounds', () => {
  const equation = '3p−q=11 and p+3q=7';
  assert.deepEqual(splitMathText(equation), [
    { type: 'math', value: '3p-q=11', raw: '3p−q=11', display: false },
    { type: 'text', value: ' and ' },
    { type: 'math', value: 'p+3q=7', raw: 'p+3q=7', display: false },
  ]);

  const explanation = 'Evaluate the integral to obtain π + [ln|u|]₁^(2√2).';
  assert.deepEqual(splitMathText(explanation), [
    { type: 'text', value: 'Evaluate the integral to obtain ' },
    {
      type: 'math', value: '\\pi + [\\ln|u|]_{1}^{2\\sqrt{2}}',
      raw: 'π + [ln|u|]₁^(2√2)', display: false,
    },
    { type: 'text', value: '.' },
  ]);
  assert.deepEqual(
    splitMathText('Use x² = 9 and y² = 16 to finish.')
      .filter((segment) => segment.type === 'text').map(({ value }) => value),
    ['Use ', ' and ', ' to finish.'],
  );
});

test('Unicode rendering keeps exact source spans for overlapping score highlights', () => {
  const source = '先算 ∫₀^(π/4)(3cosx−sinx)/(3sinx+cosx)dx，再写 π + (3/2)ln2。';
  const spans = findMathSourceSpans(source);
  assert.deepEqual(spans.map(({ start, end }) => source.slice(start, end)), [
    '∫₀^(π/4)(3cosx−sinx)/(3sinx+cosx)dx', 'π + (3/2)ln2',
  ]);
  assert.equal(
    splitMathText(source).map((segment) => segment.type === 'math' ? segment.raw : segment.value).join(''),
    source,
  );
  const partialAnchorStart = source.indexOf('3cosx');
  assert.equal(spans.filter(({ start, end }) => start < partialAnchorStart + 5 && end > partialAnchorStart).length, 1);
});

test('keeps explicit math and text commands authoritative during Unicode normalization', () => {
  const explicit = '$\\int_0^{\\pi/4}\\sin x\\,dx$';
  assert.equal(splitMathText(explicit)[0].value, '\\int_0^{\\pi/4}\\sin x\\,dx');
  const source = '= \\text{π²} + π²';
  assert.equal(splitMathText(source)[0].value, '= \\text{π²} + \\pi^{2}');
  assert.deepEqual(splitMathText('版本₂、piñata、sinister 和 path/to/file 保持原文。'), [
    { type: 'text', value: '版本₂、piñata、sinister 和 path/to/file 保持原文。' },
  ]);
});

test('bounds long Unicode OCR formula scanning without overflowing the call stack', () => {
  for (const prefix of ['', '= ']) {
    const source = `${prefix}${'π/2+'.repeat(10_000)}π`;
    assert.deepEqual(splitMathText(source), [{ type: 'text', value: source }]);
  }
  const source = 'x '.repeat(25_000);
  const startedAt = performance.now();
  assert.deepEqual(splitMathText(source), [{ type: 'text', value: source }]);
  assert.ok(performance.now() - startedAt < 2_000);
});
