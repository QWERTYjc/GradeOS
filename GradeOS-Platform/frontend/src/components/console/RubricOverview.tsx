'use client';

import React from 'react';
import { useConsoleStore } from '@/store/consoleStore';
import { GlassCard } from '@/components/design-system/GlassCard';
import { BookOpen, ListOrdered } from 'lucide-react';

export function RubricOverview() {
  const parsedRubric = useConsoleStore((state) => state.parsedRubric);

  if (!parsedRubric || !parsedRubric.questions || parsedRubric.questions.length === 0) {
    return (
      <GlassCard className="p-6 flex items-center justify-center">
        <div className="text-slate-400 text-sm flex items-center gap-2">
          <BookOpen className="w-4 h-4 opacity-50" />
          Rubric not available yet.
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100/60">
        <div className="text-slate-800 font-bold text-lg flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-indigo-500" />
          Rubric Overview
        </div>
        <div className="text-xs font-semibold text-slate-500 px-2 py-1 bg-slate-100/50 rounded-md ring-1 ring-slate-100">
          {parsedRubric.totalQuestions} questions · {parsedRubric.totalScore} points
        </div>
      </div>
      <div className="space-y-3">
        {parsedRubric.questions.map((q) => (
          <div key={q.questionId} className="rounded-xl border border-slate-100 bg-white/40 p-3 hover:bg-white/60 transition-colors">
            <div className="flex items-center justify-between">
              <div className="text-sm font-bold text-slate-700">
                Q{q.questionId}
              </div>
              <div className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded ml-2">
                {q.maxScore} pts
              </div>
            </div>
            {q.questionText && (
              <div className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">{q.questionText}</div>
            )}
            {q.scoringPoints?.length ? (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {q.scoringPoints.slice(0, 3).map((sp) => (
                  <span
                    key={`${q.questionId}-${sp.pointId}`}
                    className="text-[10px] rounded-md bg-slate-50 border border-slate-100 px-2 py-1 text-slate-600 font-medium flex items-center gap-1"
                  >
                    <ListOrdered className="w-3 h-3 text-slate-400" />
                    {sp.pointId || 'Point'} · {sp.score} pts
                  </span>
                ))}
                {q.scoringPoints.length > 3 && (
                  <span className="text-[10px] text-slate-400 self-center font-medium">+{q.scoringPoints.length - 3} more</span>
                )}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
