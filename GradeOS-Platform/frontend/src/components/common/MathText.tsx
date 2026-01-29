'use client';

import React from 'react';
import katex from 'katex';

interface MathTextProps {
  text?: string | null;
  className?: string;
}

type MathSegment =
  | { type: 'text'; value: string }
  | { type: 'math'; value: string; display: boolean };

const isEscaped = (input: string, index: number) => {
  let backslashes = 0;
  let cursor = index - 1;
  while (cursor >= 0 && input[cursor] === '\\') {
    backslashes += 1;
    cursor -= 1;
  }
  return backslashes % 2 === 1;
};

const splitMathSegments = (input: string): MathSegment[] => {
  const segments: MathSegment[] = [];
  let buffer = '';
  let i = 0;

  const flushBuffer = () => {
    if (buffer) {
      segments.push({ type: 'text', value: buffer });
      buffer = '';
    }
  };

  const findClosing = (startIndex: number, delimiter: '$' | '$$') => {
    for (let idx = startIndex; idx < input.length; idx += 1) {
      if (delimiter === '$$') {
        if (input.startsWith('$$', idx) && !isEscaped(input, idx)) {
          return idx;
        }
      } else if (input[idx] === '$' && !isEscaped(input, idx)) {
        return idx;
      }
    }
    return -1;
  };

  while (i < input.length) {
    if (input[i] === '$' && !isEscaped(input, i)) {
      const isBlock = input[i + 1] === '$';
      const delimiter = isBlock ? '$$' : '$';
      const start = i + (isBlock ? 2 : 1);
      const end = findClosing(start, delimiter);

      if (end === -1) {
        buffer += input.slice(i);
        break;
      }

      flushBuffer();
      segments.push({
        type: 'math',
        value: input.slice(start, end),
        display: isBlock,
      });
      i = end + (isBlock ? 2 : 1);
      continue;
    }

    buffer += input[i];
    i += 1;
  }

  flushBuffer();
  return segments;
};

export function MathText({ text, className }: MathTextProps) {
  if (!text) {
    return null;
  }

  const segments = splitMathSegments(text);

  return (
    <span className={className}>
      {segments.map((segment, index) => {
        if (segment.type === 'text') {
          return <span key={`text-${index}`}>{segment.value}</span>;
        }
        try {
          const html = katex.renderToString(segment.value, {
            displayMode: segment.display,
            throwOnError: false,
          });
          return (
            <span
              key={`math-${index}`}
              className={segment.display ? 'math-block block' : 'math-inline'}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          );
        } catch {
          return (
            <span key={`math-${index}`} className="text-rose-500">
              {segment.value}
            </span>
          );
        }
      })}
    </span>
  );
}
