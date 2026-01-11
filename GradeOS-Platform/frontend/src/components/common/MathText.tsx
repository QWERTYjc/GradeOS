'use client';

import React from 'react';

interface MathTextProps {
  text?: string | null;
  className?: string;
}

export function MathText({ text, className }: MathTextProps) {
  if (!text) {
    return null;
  }
  return <span className={className}>{text}</span>;
}
