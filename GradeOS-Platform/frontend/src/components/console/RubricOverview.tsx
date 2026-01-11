'use client';

import React from 'react';
import { useConsoleStore } from '@/store/consoleStore';

export function RubricOverview() {
  const parsedRubric = useConsoleStore((state) => state.parsedRubric);

  if (!parsedRubric || !parsedRubric.questions || parsedRubric.questions.length === 0) {
    return (
      <div className="neo-panel p-4">
        <div className="text-slate-500 text-sm">Rubric not available yet.</div>
      </div>
    );
  }

  return (
    <div className="neo-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-slate-700 font-semibold">Rubric Overview</div>
        <div className="text-xs text-slate-500">
          {parsedRubric.totalQuestions} questions · {parsedRubric.totalScore} points
        </div>
      </div>
      <div className="space-y-3">
        {parsedRubric.questions.map((q) => (
          <div key={q.questionId} className="rounded-xl border border-slate-200 bg-white/70 p-3">
            <div className="text-sm font-semibold text-slate-800">
              Q{q.questionId} · {q.maxScore} pts
            </div>
            {q.questionText && (
              <div className="text-xs text-slate-500 mt-1">{q.questionText}</div>
            )}
            {q.scoringPoints?.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {q.scoringPoints.slice(0, 3).map((sp) => (
                  <span
                    key={`${q.questionId}-${sp.pointId}`}
                    className="text-[11px] rounded-full bg-slate-100 px-2 py-1 text-slate-600"
                  >
                    {sp.pointId || 'Point'} · {sp.score} pts
                  </span>
                ))}
                {q.scoringPoints.length > 3 && (
                  <span className="text-[11px] text-slate-400">+{q.scoringPoints.length - 3} more</span>
                )}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
