// Bounded exact scalar arithmetic, not eval, a shell, or a symbolic proof engine.
// This tool has no filesystem/network/model access and contains no exam-specific rules.
const limit = 4096;
const abs = n => n < 0n ? -n : n;
function fraction(n, d = 1n) {
  if (!d) throw Error('Division by zero');
  if (d < 0n) { n = -n; d = -d; }
  let a = abs(n), b = d;
  while (b) [a, b] = [b, a % b];
  n /= a; d /= a;
  if (abs(n).toString(2).length > limit || d.toString(2).length > limit) throw Error('Arithmetic size limit');
  return { n, d };
}

export function exactArithmetic(expression) {
  if (typeof expression !== 'string' || expression.length > 1000) throw Error('Expression length limit');
  const tokens = expression.match(/\d+(?:\.\d+)?|\*\*|[()+\-*/%^]|\S/g) || [];
  if (!tokens.length || tokens.length > 160) throw Error('Expression token limit');
  let pos = 0;
  const binary = (op, a, b) => {
    if (op === '+') return fraction(a.n * b.d + b.n * a.d, a.d * b.d);
    if (op === '-') return fraction(a.n * b.d - b.n * a.d, a.d * b.d);
    if (op === '*') return fraction(a.n * b.n, a.d * b.d);
    if (op === '/') return fraction(a.n * b.d, a.d * b.n);
    if (op === '%') {
      if (a.d !== 1n || b.d !== 1n || !b.n) throw Error('Remainder requires integers and a nonzero divisor');
      return fraction(a.n % b.n);
    }
    if (b.d !== 1n || abs(b.n) > 4096n) throw Error('Power requires a bounded integer exponent');
    const exponent = abs(b.n);
    if (BigInt(Math.max(abs(a.n).toString(2).length, a.d.toString(2).length) - 1) * exponent > BigInt(limit)) throw Error('Arithmetic size limit');
    if (!a.n && !b.n) throw Error('Indeterminate zero power');
    return b.n < 0n ? fraction(a.d ** exponent, a.n ** exponent) : fraction(a.n ** exponent, a.d ** exponent);
  };
  const primary = () => {
    const token = tokens[pos++];
    if (token === '(') {
      const value = sum();
      if (tokens[pos++] !== ')') throw Error('Unmatched parentheses');
      return value;
    }
    if (!/^\d+(?:\.\d+)?$/.test(token || '')) throw Error('Only numbers and arithmetic operators are supported');
    const [whole, decimal = ''] = token.split('.');
    return fraction(BigInt(whole + decimal), 10n ** BigInt(decimal.length));
  };
  const power = () => {
    const left = primary();
    return ['^', '**'].includes(tokens[pos]) ? binary(tokens[pos++], left, unary()) : left;
  };
  const unary = () => {
    if (tokens[pos] === '+') { pos++; return unary(); }
    if (tokens[pos] === '-') { pos++; const a = unary(); return fraction(-a.n, a.d); }
    return power();
  };
  const product = () => {
    let value = unary();
    while (['*', '/', '%'].includes(tokens[pos])) value = binary(tokens[pos++], value, unary());
    return value;
  };
  const sum = () => {
    let value = product();
    while (['+', '-'].includes(tokens[pos])) value = binary(tokens[pos++], value, product());
    return value;
  };
  const value = sum();
  if (pos !== tokens.length) throw Error('Unexpected expression token');
  return value.d === 1n ? String(value.n) : `${value.n}/${value.d}`;
}

export function referenceArithmeticTool(object, text) {
  const calculations = new Map(); let sequence = 0;
  return { calculations, tool: {
    name: 'check_arithmetic', label: '核算独立校验中的算式',
    description: 'Exact bounded scalar arithmetic: integers/decimals, + - * / ^ ** %, parentheses. No variables, code, files or network. Remainder uses truncation toward zero. A numerical check is not a universal proof. Returned calculation IDs can be cited in verification.',
    parameters: object({ expressions: { type: 'array', minItems: 1, maxItems: 12, items: { ...text, maxLength: 1000 } } }),
    execute: async (_id, { expressions }) => {
      if (sequence >= 24) throw Error('Arithmetic batch limit');
      sequence++;
      const results = expressions.map((expression, index) => {
        const id = `calculation-${sequence}-${index + 1}`;
        try { const value = { id, expression, exact: exactArithmetic(expression) }; calculations.set(id, value); return value; }
        catch (error) { return { id, expression, error: error.message }; }
      });
      return { content: [{ type: 'text', text: JSON.stringify(results) }], details: {} };
    },
  } };
}
