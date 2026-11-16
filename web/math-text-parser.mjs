// Ported without runtime TypeScript from GradeOS-old frontend/src/components/common/mathTextParser.ts.
// GPL-3.0-only. Source SHA-256: c94a63f35231c9720bbe2404b9d15fe1739d2badf435e87fedb1d1c134d47381
// Local adaptation: keep complete numeric subscripts/superscripts in bare OCR text.
const MATH_DELIMITERS = [
    {
        open: '$$',
        close: '$$',
        display: true
    },
    {
        open: '\\[',
        close: '\\]',
        display: true
    },
    {
        open: '\\(',
        close: '\\)',
        display: false
    },
    {
        open: '$',
        close: '$',
        display: false
    }
];
const BARE_COMMANDS = new Set([
    'alpha',
    'approx',
    'bar',
    'beta',
    'cap',
    'cdot',
    'cdots',
    'cos',
    'cup',
    'delta',
    'div',
    'dots',
    'equiv',
    'exists',
    'forall',
    'frac',
    'gamma',
    'geq',
    'hat',
    'iff',
    'implies',
    'in',
    'infty',
    'int',
    'lambda',
    'leftarrow',
    'leq',
    'lim',
    'ln',
    'log',
    'mp',
    'nabla',
    'neq',
    'notin',
    'omega',
    'partial',
    'phi',
    'pi',
    'pm',
    'prod',
    'psi',
    'rightarrow',
    'sigma',
    'sin',
    'sqrt',
    'subset',
    'sum',
    'supset',
    'tan',
    'text',
    'theta',
    'times',
    'to',
    'vec'
]);
const BARE_ENVIRONMENTS = new Set([
    'aligned',
    'alignedat',
    'array',
    'bmatrix',
    'cases',
    'equation',
    'gathered',
    'matrix',
    'pmatrix',
    'smallmatrix',
    'split',
    'vmatrix',
    'Vmatrix'
]);
const BARE_SCRIPT_RE = /\b[A-Za-z](?:[_^](?:\{[^{}\n]+\}|[+\-]?\d+|[A-Za-z]))+(?:[+\-*/=][A-Za-z0-9_^{}()[\].]+)*/y;
const OCR_EXPRESSION_RE = /^[A-Za-z0-9_{}()[\].,+\-*/^>\s]+$/;
const OCR_FORMULA_LINE_RE = /^[A-Za-z0-9_{}()[\].,+\-*/^>=<\\|;\s']+$/;
const GROUP_CLOSE_TO_OPEN = {
    ')': '(',
    ']': '[',
    '}': '{'
};
const MAX_OCR_MATH_SOURCE_LENGTH = 4_096;
const MAX_OCR_FRACTION_COUNT = 256;
const MAX_OCR_GROUP_DEPTH = 64;
const OCR_GREEK_WORDS = [
    'alpha',
    'beta',
    'gamma',
    'delta',
    'epsilon',
    'varepsilon',
    'varsigma',
    'zeta',
    'eta',
    'theta',
    'vartheta',
    'iota',
    'kappa',
    'lambda',
    'mu',
    'nu',
    'xi',
    'omicron',
    'rho',
    'sigma',
    'tau',
    'upsilon',
    'phi',
    'varphi',
    'chi',
    'psi',
    'omega',
    'Gamma',
    'Delta',
    'Theta',
    'Lambda',
    'Xi',
    'Pi',
    'Sigma',
    'Upsilon',
    'Phi',
    'Psi',
    'Omega'
];
const OCR_UNICODE_SYMBOLS = {
    'α': 'alpha',
    'β': 'beta',
    'γ': 'gamma',
    'δ': 'delta',
    'ε': 'varepsilon',
    'ϵ': 'epsilon',
    'ζ': 'zeta',
    'η': 'eta',
    'θ': 'theta',
    'ϑ': 'vartheta',
    'ι': 'iota',
    'κ': 'kappa',
    'λ': 'lambda',
    'μ': 'mu',
    'ν': 'nu',
    'ξ': 'xi',
    'ο': 'omicron',
    'π': 'pi',
    'ρ': 'rho',
    'σ': 'sigma',
    'ς': 'varsigma',
    'τ': 'tau',
    'υ': 'upsilon',
    'φ': 'varphi',
    'ϕ': 'phi',
    'χ': 'chi',
    'ψ': 'psi',
    'ω': 'omega',
    'Γ': 'Gamma',
    'Δ': 'Delta',
    'Θ': 'Theta',
    'Λ': 'Lambda',
    'Ξ': 'Xi',
    'Π': 'Pi',
    'Σ': 'Sigma',
    'Υ': 'Upsilon',
    'Φ': 'Phi',
    'Ψ': 'Psi',
    'Ω': 'Omega',
    '∫': '\\int ',
    '∑': '\\sum ',
    '∏': '\\prod ',
    '√': 'sqrt ',
    '∞': 'infty',
    '−': '-',
    '–': '-',
    '×': '\\times ',
    '·': '\\cdot ',
    '÷': '\\div ',
    '≤': '\\leq ',
    '≥': '\\geq ',
    '≠': '\\neq ',
    '≈': '\\approx ',
    '→': '->',
    '⇒': '\\implies '
};
const OCR_UNICODE_SCRIPTS = {
    '₀': '0',
    '₁': '1',
    '₂': '2',
    '₃': '3',
    '₄': '4',
    '₅': '5',
    '₆': '6',
    '₇': '7',
    '₈': '8',
    '₉': '9',
    '₊': '+',
    '₋': '-',
    '⁰': '0',
    '¹': '1',
    '²': '2',
    '³': '3',
    '⁴': '4',
    '⁵': '5',
    '⁶': '6',
    '⁷': '7',
    '⁸': '8',
    '⁹': '9',
    '⁺': '+',
    '⁻': '-',
    'ⁿ': 'n',
    'ⁱ': 'i'
};
const OCR_COMPACT_FUNCTION_RE = /^(?:sin|cos|tan|ln|log|arcsin|arccos|arctan|asin|acos|atan)[A-Za-z]$/;
const OCR_NAMED_WORDS = [
    'arcsin',
    'arccos',
    'arctan',
    'asin',
    'acos',
    'atan',
    'lim',
    'log',
    'ln',
    'pi',
    'infty',
    ...OCR_GREEK_WORDS
];
const OCR_NAMED_WORD_SET = new Set(OCR_NAMED_WORDS);
const OCR_NAMED_WORD_RE = new RegExp(`(^|[^A-Za-z])(${OCR_NAMED_WORDS.join('|')})(?![A-Za-z])`, 'g');
const BARE_ARGUMENT_COMMANDS = new Set([
    'bar',
    'frac',
    'hat',
    'sqrt',
    'text',
    'vec'
]);
const normalizeOcrSymbolRun = (raw)=>raw.replace(/[₀-₉₊₋]+/g, (script)=>`_{${Array.from(script).map((c)=>OCR_UNICODE_SCRIPTS[c]).join('')}}`).replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿⁱ]+/g, (script)=>`^{${Array.from(script).map((c)=>OCR_UNICODE_SCRIPTS[c]).join('')}}`).replace(/[α-ωϵϑϕΓΔΘΛΞΠΣΥΦΨΩ∫∑∏√∞−–×·÷≤≥≠≈→⇒]/g, (symbol, offset, source)=>{
        const replacement = OCR_UNICODE_SYMBOLS[symbol] ?? symbol;
        if (!/^[A-Za-z]+$/.test(replacement)) return replacement;
        const before = /[A-Za-z]/.test(source[offset - 1] || '') ? ' ' : '';
        const after = /[A-Za-z]/.test(source[offset + 1] || '') ? ' ' : '';
        return `${before}${replacement}${after}`;
    });
const isEscaped = (input, index)=>{
    let backslashes = 0;
    for(let cursor = index - 1; cursor >= 0 && input[cursor] === '\\'; cursor -= 1){
        backslashes += 1;
    }
    return backslashes % 2 === 1;
};
const normalizeSerializedDelimiters = (input)=>input.replace(/\\\\\(/g, '\\(').replace(/\\\\\)/g, '\\)').replace(/\\\\\[/g, '\\[').replace(/\\\\\]/g, '\\]');
const openingDelimiterAt = (input, index)=>MATH_DELIMITERS.find((delimiter)=>input.startsWith(delimiter.open, index) && !isEscaped(input, index));
const closingDelimiterIndex = (input, startIndex, delimiter)=>{
    for(let index = startIndex; index < input.length; index += 1){
        if (input.startsWith(delimiter.close, index) && !isEscaped(input, index)) return index;
    }
    return -1;
};
const hasBalancedGroups = (value)=>{
    const stack = [];
    const pairs = {
        '}': '{',
        ')': '(',
        ']': '['
    };
    for(let index = 0; index < value.length; index += 1){
        const character = value[index];
        if (isEscaped(value, index)) continue;
        if (character === '{' || character === '(' || character === '[') stack.push(character);
        if (character in pairs && stack.pop() !== pairs[character]) return false;
    }
    return stack.length === 0;
};
const hasWordBoundaryBefore = (input, index)=>index === 0 || !/[A-Za-z0-9_]/.test(input[index - 1]);
const matchingGroupEnd = (input, startIndex, open, close)=>{
    if (input[startIndex] !== open) return -1;
    let depth = 0;
    for(let index = startIndex; index < input.length; index += 1){
        if (input[index] === '\n' || input[index] === '\r') return -1;
        if (isEscaped(input, index)) continue;
        if (input[index] === open) depth += 1;
        if (input[index] === close) {
            depth -= 1;
            if (depth === 0) return index + 1;
            if (depth < 0) return -1;
        }
    }
    return -1;
};
const normalizeOcrSymbols = (raw)=>{
    let cursor = 0;
    let value = '';
    let syntax = '';
    while(cursor < raw.length){
        const textStart = raw.indexOf('\\text{', cursor);
        const symbolRun = normalizeOcrSymbolRun(raw.slice(cursor, textStart < 0 ? raw.length : textStart));
        value += symbolRun;
        syntax += symbolRun;
        if (textStart < 0) break;
        const textEnd = matchingGroupEnd(raw, textStart + '\\text'.length, '{', '}');
        if (textEnd < 0) {
            value += raw.slice(textStart);
            syntax += raw.slice(textStart);
            break;
        }
        value += raw.slice(textStart, textEnd);
        syntax += '\\text{T}';
        cursor = textEnd;
    }
    return {
        value,
        syntax
    };
};
const matchingGroupStart = (input, closeIndex)=>{
    const close = input[closeIndex];
    const open = GROUP_CLOSE_TO_OPEN[close];
    if (!open) return -1;
    let depth = 0;
    for(let index = closeIndex; index >= 0; index -= 1){
        if (input[index] === close) depth += 1;
        if (input[index] === open) {
            depth -= 1;
            if (depth === 0) return index;
            if (depth < 0) return -1;
        }
    }
    return -1;
};
const topLevelSlashIndex = (value)=>{
    const stack = [];
    for(let index = 0; index < value.length; index += 1){
        const character = value[index];
        if (character === '(' || character === '[' || character === '{') stack.push(character);
        if (character in GROUP_CLOSE_TO_OPEN) stack.pop();
        if (character === '/' && stack.length === 0) return index;
    }
    return -1;
};
const plainAtomStartBefore = (value, endIndex)=>{
    let cursor = endIndex - 1;
    while(cursor >= 0 && /\s/.test(value[cursor]))cursor -= 1;
    if (cursor < 0) return -1;
    if (value[cursor] in GROUP_CLOSE_TO_OPEN) {
        const groupStart = matchingGroupStart(value, cursor);
        if (groupStart < 0) return -1;
        if (value[groupStart] !== '(') return groupStart;
        const functionPrefix = /(?:\b(?:sqrt|sin|cos|tan|ln|log|asin|acos|atan|arcsin|arccos|arctan)|\b[A-Za-z])(?:(?:')|[_^](?:\{[^{}\n]+\}|\([^()\n]+\)|[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z])))*\s*$/.exec(value.slice(0, groupStart));
        return functionPrefix?.index ?? groupStart;
    }
    const atomMatch = /(?:[A-Za-z]+(?:')*|\d+(?:\.\d+)?)\s*$/.exec(value.slice(0, cursor + 1));
    return atomMatch?.index ?? -1;
};
const leftFractionAtomStart = (value, slashIndex)=>{
    let atomEnd = slashIndex;
    while(atomEnd > 0){
        const scriptArgumentStart = plainAtomStartBefore(value, atomEnd);
        if (scriptArgumentStart < 0) return -1;
        let markerIndex = scriptArgumentStart - 1;
        while(markerIndex >= 0 && /\s/.test(value[markerIndex]))markerIndex -= 1;
        if (value[markerIndex] === '+' || value[markerIndex] === '-') {
            markerIndex -= 1;
            while(markerIndex >= 0 && /\s/.test(value[markerIndex]))markerIndex -= 1;
        }
        if (markerIndex < 0 || value[markerIndex] !== '^' && value[markerIndex] !== '_') {
            break;
        }
        atomEnd = markerIndex;
    }
    return plainAtomStartBefore(value, atomEnd);
};
const rightFractionAtomEnd = (value, slashIndex)=>{
    let cursor = slashIndex + 1;
    while(cursor < value.length && /\s/.test(value[cursor]))cursor += 1;
    if (cursor >= value.length) return -1;
    let end = cursor;
    if (value[cursor] === '(' || value[cursor] === '[' || value[cursor] === '{') {
        const close = {
            '(': ')',
            '[': ']',
            '{': '}'
        }[value[cursor]];
        end = matchingGroupEnd(value, cursor, value[cursor], close);
        if (end < 0) return -1;
    } else {
        const atomMatch = /^(?:[A-Za-z]+(?:')*|\d+(?:\.\d+)?)/.exec(value.slice(cursor));
        if (!atomMatch) return -1;
        end = cursor + atomMatch[0].length;
    }
    const consumeSuffixes = ()=>{
        while(value[end] === "'")end += 1;
        while(value[end] === '^' || value[end] === '_'){
            const argumentStart = end + 1;
            if (value[argumentStart] === '{' || value[argumentStart] === '(') {
                const open = value[argumentStart];
                const close = open === '{' ? '}' : ')';
                const argumentEnd = matchingGroupEnd(value, argumentStart, open, close);
                if (argumentEnd < 0) return false;
                end = argumentEnd;
                continue;
            }
            const argumentMatch = /^[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z])/.exec(value.slice(argumentStart));
            if (!argumentMatch) return false;
            end = argumentStart + argumentMatch[0].length;
            while(value[end] === "'")end += 1;
        }
        return true;
    };
    if (!consumeSuffixes()) return -1;
    if (value[end] === '(') {
        const functionEnd = matchingGroupEnd(value, end, '(', ')');
        if (functionEnd < 0) return -1;
        end = functionEnd;
        if (!consumeSuffixes()) return -1;
    }
    return end;
};
const unwrapFractionAtom = (value)=>{
    const trimmed = value.trim();
    if (!trimmed || !'([{'.includes(trimmed[0])) return trimmed;
    const close = {
        '(': ')',
        '[': ']',
        '{': '}'
    }[trimmed[0]];
    return matchingGroupEnd(trimmed, 0, trimmed[0], close) === trimmed.length ? trimmed.slice(1, -1) : trimmed;
};
const formatSlashFractions = (value)=>{
    const slashIndex = topLevelSlashIndex(value);
    if (slashIndex >= 0) {
        const numeratorStart = leftFractionAtomStart(value, slashIndex);
        const denominatorEnd = rightFractionAtomEnd(value, slashIndex);
        if (numeratorStart >= 0 && denominatorEnd > slashIndex) {
            const numerator = unwrapFractionAtom(value.slice(numeratorStart, slashIndex));
            const denominator = unwrapFractionAtom(value.slice(slashIndex + 1, denominatorEnd));
            return `${formatSlashFractions(value.slice(0, numeratorStart))}\\frac{${formatSlashFractions(numerator)}}{${formatSlashFractions(denominator)}}${formatSlashFractions(value.slice(denominatorEnd))}`;
        }
    }
    let output = '';
    let cursor = 0;
    while(cursor < value.length){
        const open = value[cursor];
        if (open !== '(' && open !== '[' && open !== '{') {
            output += open;
            cursor += 1;
            continue;
        }
        const close = {
            '(': ')',
            '[': ']',
            '{': '}'
        }[open];
        const end = matchingGroupEnd(value, cursor, open, close);
        if (end < 0) {
            output += open;
            cursor += 1;
            continue;
        }
        output += `${open}${formatSlashFractions(value.slice(cursor + 1, end - 1))}${close}`;
        cursor = end;
    }
    return output;
};
const formatSquareRoots = (value)=>{
    let output = '';
    let cursor = 0;
    while(cursor < value.length){
        if (value.startsWith('sqrt', cursor) && (cursor === 0 || !/[A-Za-z_]/.test(value[cursor - 1]))) {
            let argumentStart = cursor + 'sqrt'.length;
            while(argumentStart < value.length && /\s/.test(value[argumentStart]))argumentStart += 1;
            const open = value[argumentStart];
            if (open === '(' || open === '{') {
                const close = open === '(' ? ')' : '}';
                const end = matchingGroupEnd(value, argumentStart, open, close);
                if (end > argumentStart) {
                    output += `\\sqrt{${formatSquareRoots(value.slice(argumentStart + 1, end - 1))}}`;
                    cursor = end;
                    continue;
                }
            }
            const atomMatch = /^[+\-]?(?:[A-Za-z]+(?:')*|\d+(?:\.\d+)?)(?:(?:')|[_^](?:\{[^{}\n]+\}|\([^()\n]+\)|[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z])))*/.exec(value.slice(argumentStart));
            if (atomMatch) {
                output += `\\sqrt{${atomMatch[0]}}`;
                cursor = argumentStart + atomMatch[0].length;
                continue;
            }
            const groupStart = cursor + 'sqrt'.length;
            const end = matchingGroupEnd(value, groupStart, '(', ')');
            if (end > groupStart) {
                output += `\\sqrt{${formatSquareRoots(value.slice(groupStart + 1, end - 1))}}`;
                cursor = end;
                continue;
            }
        }
        output += value[cursor];
        cursor += 1;
    }
    return output;
};
const isWithinOcrFormattingBudget = (raw)=>{
    if (raw.length > MAX_OCR_MATH_SOURCE_LENGTH) return false;
    let fractionCount = 0;
    let depth = 0;
    let maxDepth = 0;
    for (const character of raw){
        if (character === '/') fractionCount += 1;
        if (character === '(' || character === '[' || character === '{') {
            depth += 1;
            maxDepth = Math.max(maxDepth, depth);
        } else if (character === ')' || character === ']' || character === '}') {
            depth = Math.max(0, depth - 1);
        }
        if (fractionCount > MAX_OCR_FRACTION_COUNT || maxDepth > MAX_OCR_GROUP_DEPTH) {
            return false;
        }
    }
    return true;
};
const formatNamedOcrWords = (value)=>value.replace(OCR_NAMED_WORD_RE, (_match, prefix, name)=>{
        const command = name.startsWith('arc') ? name : [
            'asin',
            'acos',
            'atan'
        ].includes(name) ? `arc${name.slice(1)}` : name;
        return `${prefix}\\${command}`;
    });
// Bare OCR powers associate to the right: a^-b^2 means a^{-(b^2)}.
// Explicit TeX bypasses OCR formatting; its grouping remains authoritative.
const groupBarePowerChains = (value)=>value.replace(/\^[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z])(?:\^[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z]))+/g,
    (chain)=>{
        const powers = chain.slice(1).split('^');
        return powers.length > MAX_OCR_GROUP_DEPTH ? chain : `^{${powers.reduceRight((power, base)=>`${base}^{${power}}`)}}`;
    });
const formatOcrMath = (raw)=>{
    if (!isWithinOcrFormattingBudget(raw)) return null;
    const explicitCommands = [];
    const protectCommand = (command)=>{
        const token = `\uE000${explicitCommands.length}\uE001`;
        explicitCommands.push(command);
        return token;
    };
    let commandProtected = '';
    for(let cursor = 0; cursor < raw.length;){
        const commandMatch = /^\\([A-Za-z]+)/.exec(raw.slice(cursor));
        if (!commandMatch) {
            commandProtected += raw[cursor];
            cursor += 1;
            continue;
        }
        let commandEnd = cursor + commandMatch[0].length;
        if (commandMatch[1] === 'text' && raw[commandEnd] === '{') {
            const textEnd = matchingGroupEnd(raw, commandEnd, '{', '}');
            if (textEnd > commandEnd) commandEnd = textEnd;
        }
        commandProtected += protectCommand(raw.slice(cursor, commandEnd));
        cursor = commandEnd;
    }
    const restoreCommands = (value)=>explicitCommands.reduce((restored, command, index)=>restored.replace(`\uE000${index}\uE001`, command), value);
    const withFractions = formatSlashFractions(groupBarePowerChains(commandProtected));
    const withRoots = formatSquareRoots(withFractions);
    const withNamedWords = formatNamedOcrWords(withRoots);
    return restoreCommands(withNamedWords.replace(/([_^])\(([^()\n]+)\)/g, '$1{$2}').replace(/([_^])([+\-]?(?:\d+(?:\.\d+)?|[A-Za-z]))/g, (match, operator, script)=>script.length > 1 ? `${operator}{${script}}` : match).replace(/\s*(?:->|→)\s*/g, '\\to ').replace(/(^|[^A-Za-z\\])(arcsin|arccos|arctan|asin|acos|atan|sin|cos|tan|ln|log)([A-Za-z])(?=$|[^A-Za-z])/g, (_match, prefix, name, argument)=>{
        const command = [
            'asin',
            'acos',
            'atan'
        ].includes(name) ? `arc${name.slice(1)}` : name;
        return `${prefix}\\${command} ${argument}`;
    }).replace(/\b([A-Za-z])(?=(?:sin|cos|tan)\b)/g, '$1 ').replace(/(^|[^\\A-Za-z])(sin|cos|tan)\b/g, '$1\\$2').replace(/\b(RHS|LHS)\b/g, '\\mathrm{$1}').replace(/\s+\.\s+/g, ' \\cdot '));
};
const isAllowedFormulaWord = (word)=>word.length === 1 || BARE_COMMANDS.has(word) || OCR_NAMED_WORD_SET.has(word) || OCR_COMPACT_FUNCTION_RE.test(word) || [
        'sqrt',
        'RHS',
        'LHS'
    ].includes(word) || /^(?:d|dx|dy|dt|du|dv|dw|dz)$/.test(word) || /^[A-Za-z](?:sin|cos|tan)$/.test(word);
const isAllowedInlineFormulaWord = (word)=>word.length === 1 || OCR_NAMED_WORD_SET.has(word) || [
        'sqrt',
        'sin',
        'cos',
        'tan',
        'RHS',
        'LHS'
    ].includes(word) || OCR_COMPACT_FUNCTION_RE.test(word) || /^(?:dx|dy|dt|du|dv|dw|dz)$/.test(word) || /^[A-Za-z](?:sin|cos|tan)$/.test(word);
const hasBroadOcrFormulaLead = (trimmed)=>{
    if (!/^[=A-Za-z0-9([{\\+\-]/.test(trimmed)) return false;
    return trimmed.startsWith('=') || /^[A-Za-z](?:')?\(/.test(trimmed) && trimmed.includes('=') || /(?:[=^_]|\\[A-Za-z]+|->|→)/.test(trimmed) || /^(?:pi|infty)$/.test(trimmed) || /[+\-*/]/.test(trimmed) && /(?:^|[^A-Za-z])(?:pi|sqrt|sin|cos|tan|ln|log)(?:[A-Za-z])?(?![A-Za-z])/.test(trimmed);
};
const hasUnsafeFormulaSyntax = (value)=>{
    const withoutSafeDots = value.replace(/\d+\.\d+/g, '0').replace(/\s+\.\s+/g, ' * ');
    return /\.\s*\./.test(value) || withoutSafeDots.includes('.') || /[_^]\(\s*[([{]/.test(value) || /[_^](?!\{[^{}\n]+\}|\([^()\n]+\)|[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z]))/.test(value) || /[_^](?:sin|cos|tan|ln|log|asin|acos|atan|arcsin|arccos|arctan)\s*\(/.test(value) || /[_^][+\-][A-Za-z]{2,}/.test(value) || /\bd\^(?:\{?\d+\}?)\s*[A-Za-z]+(?:'|[_^][^\s/()]+)*(?:\([^()\n]+\))?\s*\//.test(value) || /\bd[A-Za-z]\s*\/\s*d[A-Za-z]\^(?:\{?\d+\}?)/.test(value) || /=\s*=/.test(value) || /[+*/^]\s*[+*/^=]/.test(value) || /-\s*[*\/^=]/.test(value) || /=\s*[*\/^>]/.test(value);
};
const formatOcrFormulaCandidate = (raw)=>{
    if (!isWithinOcrFormattingBudget(raw)) return null;
    const normalized = normalizeOcrSymbols(raw);
    const trimmed = normalized.syntax.trim();
    if (!hasBroadOcrFormulaLead(trimmed) && !/[α-ωΓΔΘΛΞΠΣΥΦΨΩ∫∑∏√∞]/.test(raw) || !OCR_FORMULA_LINE_RE.test(trimmed) || !hasBalancedGroups(trimmed) || hasUnsafeFormulaSyntax(trimmed) || /\bsqrt\s+[+\-]?(?:[A-Za-z]+(?:')*|\d+(?:\.\d+)?)(?:(?:')|[_^](?:\{[^{}\n]+\}|\([^()\n]+\)|[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z])))*\s*\(/.test(trimmed) || /^=\s*\d{1,4}\s*\/\s*\d{1,2}\s*\/\s*\d{1,4}\s*$/.test(trimmed) || /\/\//.test(trimmed) || /[+\-*/^=]\s*$/.test(trimmed) || /^=\s*[*/^]/.test(trimmed)) return null;
    const words = trimmed.match(/[A-Za-z]+/g) || [];
    if (!words.every(isAllowedFormulaWord)) return null;
    const value = formatOcrMath(normalized.value);
    if (value === null || /(^|[^\\A-Za-z])sqrt\b/.test(value)) return null;
    return value;
};
const consumeOcrFormulaLine = (input, startIndex)=>{
    if (startIndex > 0 && input[startIndex - 1] !== '\n' && input[startIndex - 1] !== '\r') {
        return null;
    }
    const lineBreak = input.indexOf('\n', startIndex);
    const rawLine = input.slice(startIndex, lineBreak < 0 ? input.length : lineBreak);
    const raw = rawLine.trimEnd();
    if (!raw) return null;
    const value = formatOcrFormulaCandidate(raw);
    if (value === null) return null;
    return {
        end: startIndex + raw.length,
        value
    };
};
const consumeInlineOcrFormula = (input, startIndex)=>{
    if (!hasWordBoundaryBefore(input, startIndex) || !/[A-Za-z0-9([α-ωΓΔΘΛΞΠΣΥΦΨΩ∫∑∏√∞]/.test(input[startIndex])) return null;
    const candidateWindow = input.slice(startIndex, startIndex + MAX_OCR_MATH_SOURCE_LENGTH + 1);
    const lineBreak = candidateWindow.indexOf('\n');
    if (!/[=α-ωΓΔΘΛΞΠΣΥΦΨΩ∫∑∏√∞₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹]/.test(lineBreak < 0 ? candidateWindow : candidateWindow.slice(0, lineBreak))) return null;
    let cursor = startIndex;
    while(cursor < input.length && cursor - startIndex <= MAX_OCR_MATH_SOURCE_LENGTH){
        const character = input[cursor];
        if (/[A-Za-z]/.test(character)) {
            let wordEnd = cursor + 1;
            while(wordEnd < input.length && /[A-Za-z]/.test(input[wordEnd]))wordEnd += 1;
            if (!isAllowedInlineFormulaWord(input.slice(cursor, wordEnd))) break;
            cursor = wordEnd;
        } else if (character === '\\') {
            const command = /^\\([A-Za-z]+)/.exec(input.slice(cursor));
            if (!command || !BARE_COMMANDS.has(command[1])) break;
            cursor += command[0].length;
        } else if (/[0-9_{}()[\],+\-*/^>=<| \t']/.test(character) || character in OCR_UNICODE_SYMBOLS || character in OCR_UNICODE_SCRIPTS || character === '.' && /\d/.test(input[cursor - 1]) && /\d/.test(input[cursor + 1] || '')) {
            cursor += 1;
        } else {
            break;
        }
    }
    const raw = input.slice(startIndex, cursor).trimEnd();
    if (!/[=α-ωΓΔΘΛΞΠΣΥΦΨΩ∫∑∏√∞₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹]/.test(raw)) return null;
    const value = formatOcrFormulaCandidate(raw);
    return value === null ? null : {
        end: startIndex + raw.length,
        value
    };
};
const rejectedFormulaLineEnd = (input, startIndex)=>{
    if (startIndex > 0 && input[startIndex - 1] !== '\n' && input[startIndex - 1] !== '\r') {
        return -1;
    }
    const lineBreak = input.indexOf('\n', startIndex);
    const end = lineBreak < 0 ? input.length : lineBreak;
    const raw = input.slice(startIndex, end);
    const trimmed = raw.trimStart();
    const hasFormulaLead = trimmed.startsWith('=') || /^[A-Za-z](?:')?\(/.test(trimmed) && trimmed.includes('=') || !isWithinOcrFormattingBudget(raw) && (hasBroadOcrFormulaLead(trimmed) || /[α-ωΓΔΘΛΞΠΣΥΦΨΩ∫∑∏√∞]/.test(trimmed));
    return hasFormulaLead ? end : -1;
};
const consumeLimitCandidate = (input, startIndex)=>{
    if (!hasWordBoundaryBefore(input, startIndex) || !input.startsWith('lim_{', startIndex)) {
        return null;
    }
    const groupStart = startIndex + 'lim_'.length;
    const end = matchingGroupEnd(input, groupStart, '{', '}');
    if (end < 0 || /[A-Za-z0-9_]/.test(input[end] || '')) return null;
    const subscript = input.slice(groupStart + 1, end - 1);
    if (!/^[A-Za-z][A-Za-z0-9_]*\s*(?:->|→)\s*[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z]+|∞)$/.test(subscript)) {
        return null;
    }
    const raw = input.slice(startIndex, end);
    const value = formatOcrMath(raw);
    return value === null ? null : {
        end,
        value
    };
};
const consumeTrigCandidate = (input, startIndex)=>{
    if (!hasWordBoundaryBefore(input, startIndex)) return null;
    const prefixMatch = /^(?:sin|cos|tan)(?:\^(?:\d+|\{\d+\}))?\(/.exec(input.slice(startIndex));
    if (!prefixMatch) return null;
    const groupStart = startIndex + prefixMatch[0].length - 1;
    const end = matchingGroupEnd(input, groupStart, '(', ')');
    if (end < 0 || /[A-Za-z0-9_]/.test(input[end] || '')) return null;
    const raw = input.slice(startIndex, end);
    if (!OCR_EXPRESSION_RE.test(raw) || !hasBalancedGroups(raw)) return null;
    const value = formatOcrMath(raw);
    return value === null ? null : {
        end,
        value
    };
};
const consumePiFractionCandidate = (input, startIndex)=>{
    if (!hasWordBoundaryBefore(input, startIndex)) return null;
    const match = /^pi\s*\/\s*\d+(?:\.\d+)?(?![A-Za-z0-9_/])/.exec(input.slice(startIndex));
    if (!match) return null;
    const end = startIndex + match[0].length;
    const value = formatOcrMath(match[0]);
    return value === null ? null : {
        end,
        value
    };
};
const consumeDifferenceQuotientCandidate = (input, startIndex)=>{
    if (input[startIndex] !== '(') return null;
    const numeratorEnd = matchingGroupEnd(input, startIndex, '(', ')');
    if (numeratorEnd < 0) return null;
    const denominatorMatch = /^\s*\/\s*([A-Za-z][A-Za-z0-9_]*|\d+(?:\.\d+)?)/.exec(input.slice(numeratorEnd));
    if (!denominatorMatch) return null;
    const end = numeratorEnd + denominatorMatch[0].length;
    if (/[A-Za-z0-9_/]/.test(input[end] || '')) return null;
    const numerator = input.slice(startIndex + 1, numeratorEnd - 1);
    const raw = input.slice(startIndex, end);
    const hasFunctionDifference = /\b[A-Za-z]\s*\(/.test(numerator) && /[+\-]/.test(numerator);
    if (!hasFunctionDifference || !OCR_EXPRESSION_RE.test(raw) || !hasBalancedGroups(raw)) return null;
    const value = formatOcrMath(raw);
    return value === null ? null : {
        end,
        value
    };
};
const consumeBracketedOcrExpressionCandidate = (input, startIndex)=>{
    if (input[startIndex] !== '[') return null;
    const groupEnd = matchingGroupEnd(input, startIndex, '[', ']');
    if (groupEnd < 0) return null;
    let end = groupEnd;
    while(input[end] === '_' || input[end] === '^'){
        const scriptMatch = /^(?:[_^])(?:\{[^{}\n]+\}|\([^()\n]+\)|[+\-]?(?:\d+(?:\.\d+)?|[A-Za-z]))/.exec(input.slice(end));
        if (!scriptMatch) return null;
        end += scriptMatch[0].length;
    }
    const raw = input.slice(startIndex, end);
    if (!/[\/_^=]/.test(raw) || !/[A-Za-z_^=]/.test(raw) || !OCR_EXPRESSION_RE.test(raw) || !hasBalancedGroups(raw) || hasUnsafeFormulaSyntax(raw)) return null;
    const words = raw.match(/[A-Za-z]+/g) || [];
    if (!words.every(isAllowedFormulaWord)) return null;
    const value = formatOcrMath(raw);
    return value === null ? null : {
        end,
        value
    };
};
const consumeOcrMathCandidate = (input, startIndex)=>consumeInlineOcrFormula(input, startIndex) || consumeLimitCandidate(input, startIndex) || consumeTrigCandidate(input, startIndex) || consumePiFractionCandidate(input, startIndex) || consumeBracketedOcrExpressionCandidate(input, startIndex) || consumeDifferenceQuotientCandidate(input, startIndex);
const consumeBareCommand = (input, startIndex)=>{
    const commandMatch = /^\\([A-Za-z]+)/.exec(input.slice(startIndex));
    if (!commandMatch) return startIndex;
    if (commandMatch[1] === 'begin') {
        const environmentMatch = /^\\begin\{([A-Za-z*]+)\}/.exec(input.slice(startIndex));
        const environment = environmentMatch?.[1];
        if (!environmentMatch || !environment || !BARE_ENVIRONMENTS.has(environment)) {
            return startIndex;
        }
        const open = `\\begin{${environment}}`;
        const close = `\\end{${environment}}`;
        let environmentDepth = 1;
        let environmentCursor = startIndex + environmentMatch[0].length;
        while(environmentCursor < input.length){
            const nextOpen = input.indexOf(open, environmentCursor);
            const nextClose = input.indexOf(close, environmentCursor);
            if (nextClose < 0) return startIndex;
            if (nextOpen >= 0 && nextOpen < nextClose) {
                environmentDepth += 1;
                environmentCursor = nextOpen + open.length;
                continue;
            }
            environmentDepth -= 1;
            environmentCursor = nextClose + close.length;
            if (environmentDepth === 0) return environmentCursor;
        }
        return startIndex;
    }
    if (!BARE_COMMANDS.has(commandMatch[1])) return startIndex;
    let cursor = startIndex + commandMatch[0].length;
    let depth = 0;
    while(cursor < input.length){
        const character = input[cursor];
        if (character === '{' || character === '(' || character === '[') depth += 1;
        if (character === '}' || character === ')' || character === ']') {
            depth -= 1;
            if (depth < 0) return startIndex;
        }
        if (depth === 0 && !/[A-Za-z0-9_^{()[\]}+\-*/=.,\\]/.test(character)) break;
        cursor += 1;
    }
    const candidate = input.slice(startIndex, cursor);
    if (candidate.length === commandMatch[0].length) {
        return BARE_ARGUMENT_COMMANDS.has(commandMatch[1]) ? startIndex : cursor;
    }
    return !/[_^]$/.test(candidate) && hasBalancedGroups(candidate) ? cursor : startIndex;
};
const splitBareMath = (value)=>{
    const segments = [];
    let textStart = 0;
    let index = 0;
    const appendMath = (start, end, formattedValue)=>{
        if (start > textStart) segments.push({
            type: 'text',
            value: value.slice(textStart, start)
        });
        const raw = value.slice(start, end);
        segments.push({
            type: 'math',
            value: formattedValue ?? raw,
            raw,
            display: raw.startsWith('\\begin{')
        });
        index = end;
        textStart = end;
    };
    while(index < value.length){
        if (value[index] === '\\' && !isEscaped(value, index)) {
            const end = consumeBareCommand(value, index);
            if (end > index) {
                appendMath(index, end);
                continue;
            }
        }
        const formulaLine = consumeOcrFormulaLine(value, index);
        if (formulaLine) {
            appendMath(index, formulaLine.end, formulaLine.value);
            continue;
        }
        const rejectedLineEnd = rejectedFormulaLineEnd(value, index);
        if (rejectedLineEnd > index) {
            let commandCursor = index;
            while(commandCursor < rejectedLineEnd){
                const commandStart = value.indexOf('\\', commandCursor);
                if (commandStart < 0 || commandStart >= rejectedLineEnd) break;
                if (!isEscaped(value, commandStart)) {
                    const commandEnd = consumeBareCommand(value, commandStart);
                    if (commandEnd > commandStart && commandEnd <= rejectedLineEnd) {
                        appendMath(commandStart, commandEnd);
                        commandCursor = commandEnd;
                        continue;
                    }
                }
                commandCursor = commandStart + 1;
            }
            index = rejectedLineEnd;
            continue;
        }
        const ocrCandidate = consumeOcrMathCandidate(value, index);
        if (ocrCandidate) {
            appendMath(index, ocrCandidate.end, ocrCandidate.value);
            continue;
        }
        BARE_SCRIPT_RE.lastIndex = index;
        const scriptMatch = BARE_SCRIPT_RE.exec(value);
        if (scriptMatch?.index === index && hasBalancedGroups(scriptMatch[0])) {
            appendMath(index, index + scriptMatch[0].length, scriptMatch[0].replace(/([_^])([+\-]?\d{2,}|[+\-]\d+)/g, '$1{$2}'));
            continue;
        }
        index += 1;
    }
    if (textStart < value.length) segments.push({
        type: 'text',
        value: value.slice(textStart)
    });
    return segments;
};
export const splitMathText = (input)=>{
    const normalized = normalizeSerializedDelimiters(input);
    const segments = [];
    let textStart = 0;
    let index = 0;
    const appendText = (end)=>{
        if (end <= textStart) return;
        segments.push(...splitBareMath(normalized.slice(textStart, end)));
    };
    while(index < normalized.length){
        const delimiter = openingDelimiterAt(normalized, index);
        if (!delimiter) {
            index += 1;
            continue;
        }
        const contentStart = index + delimiter.open.length;
        const contentEnd = closingDelimiterIndex(normalized, contentStart, delimiter);
        if (contentEnd < 0) {
            index += delimiter.open.length;
            continue;
        }
        appendText(index);
        const raw = normalized.slice(index, contentEnd + delimiter.close.length);
        segments.push({
            type: 'math',
            value: normalized.slice(contentStart, contentEnd),
            raw,
            display: delimiter.display
        });
        index = contentEnd + delimiter.close.length;
        textStart = index;
    }
    appendText(normalized.length);
    return segments;
};
const serializedDelimiterVariant = (raw)=>{
    if (raw.startsWith('\\(') && raw.endsWith('\\)')) {
        return `\\\\(${raw.slice(2, -2)}\\\\)`;
    }
    if (raw.startsWith('\\[') && raw.endsWith('\\]')) {
        return `\\\\[${raw.slice(2, -2)}\\\\]`;
    }
    return null;
};
export const findMathSourceSpans = (input)=>{
    let cursor = 0;
    const spans = [];
    splitMathText(input).forEach((segment)=>{
        const candidates = segment.type === 'math' ? [
            segment.raw,
            serializedDelimiterVariant(segment.raw)
        ].filter((candidate)=>Boolean(candidate)) : [
            segment.value
        ];
        const located = candidates.map((candidate)=>({
                candidate,
                start: input.indexOf(candidate, cursor)
            })).filter(({ start })=>start >= 0).sort((left, right)=>left.start - right.start)[0];
        if (!located) return;
        const end = located.start + located.candidate.length;
        if (segment.type === 'math') spans.push({
            start: located.start,
            end
        });
        cursor = end;
    });
    return spans;
};
