'use client';

import React, { useEffect, useRef, useState } from 'react';

interface FocusModeProps {
  question: string;
  onAnswer: (answer: string) => void;
  onExit: () => void;
  isLoading?: boolean;
}

const FocusMode: React.FC<FocusModeProps> = ({
  question,
  onAnswer,
  onExit,
  isLoading = false,
}) => {
  const [answer, setAnswer] = useState('');
  const [showHint, setShowHint] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onExit();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onExit]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (answer.trim() && !isLoading) {
      onAnswer(answer.trim());
      setAnswer('');
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-white p-8 animate-fadeIn">
      <button
        onClick={onExit}
        className="absolute right-6 top-6 p-2 text-black/40 transition-colors hover:text-black/70"
        title="Press ESC to exit focus mode"
      >
        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <div className="absolute left-6 top-6 flex items-center gap-2 text-black/40">
        <div className="h-2 w-2 animate-pulse rounded-full bg-black" />
        <span className="text-xs font-medium uppercase tracking-[0.3em]">Focus Mode</span>
      </div>

      <div className="mb-16 w-full max-w-3xl text-center">
        <div className="text-4xl font-light leading-relaxed text-black md:text-5xl">
          {question}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="w-full max-w-2xl">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type your reasoning here..."
            className="min-h-[120px] w-full rounded-2xl border-2 border-black/10 bg-white/80 p-6 text-xl text-black transition-all duration-300 placeholder:text-black/40 focus:border-black focus:bg-white focus:outline-none resize-none"
            disabled={isLoading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />

          <button
            type="submit"
            disabled={!answer.trim() || isLoading}
            className={`absolute bottom-4 right-4 rounded-xl px-6 py-2 text-sm font-semibold uppercase tracking-[0.2em] transition-all ${
              answer.trim() && !isLoading
                ? 'bg-black text-white hover:bg-black/90'
                : 'bg-black/10 text-black/30 cursor-not-allowed'
            }`}
          >
            {isLoading ? 'Thinking' : 'Submit'}
          </button>
        </div>

        <div className="mt-4 text-center">
          <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-black/40">
            <button
              type="button"
              onClick={() => setShowHint(!showHint)}
              className="transition-colors hover:text-black/70"
            >
              {showHint ? 'Hide hint' : 'Need a hint?'}
            </button>
            <button
              type="button"
              onClick={() => onAnswer("I don't know yet. Please explain step-by-step, then ask a simpler question.")}
              className="transition-colors hover:text-black/70"
            >
              I don't know
            </button>
          </div>

          {showHint && (
            <div className="mt-4 rounded-xl bg-black/5 p-4 text-sm text-black/70 animate-fadeIn">
              Try explaining the concept in your own words. The reasoning path matters more than the final answer.
            </div>
          )}
        </div>
      </form>

      <div className="absolute bottom-8 text-xs text-black/40">
        Press <kbd className="rounded border border-black/10 bg-black/5 px-2 py-1 font-mono">Shift + Enter</kbd> to
        add a new line, <kbd className="rounded border border-black/10 bg-black/5 px-2 py-1 font-mono">Enter</kbd> to
        submit.
      </div>
    </div>
  );
};

export default FocusMode;
