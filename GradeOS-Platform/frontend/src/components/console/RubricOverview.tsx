'use client';

import React, { useState } from 'react';
import { useConsoleStore } from '@/store/consoleStore';
import { BookOpen, ListOrdered, AlertCircle, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';

export function RubricOverview() {
  const parsedRubric = useConsoleStore((state) => state.parsedRubric);
  const [showSelfReport, setShowSelfReport] = useState(true);

  if (!parsedRubric || !parsedRubric.questions || parsedRubric.questions.length === 0) {
    return (
      <div className="p-6 flex items-center justify-center text-slate-400 text-sm gap-2">
        <BookOpen className="w-4 h-4 opacity-50" />
        Rubric not available yet.
      </div>
    );
  }

  const selfReport = parsedRubric.parseSelfReport;

  return (
    <div className="border-t border-slate-100 pt-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100/60">
        <div className="text-slate-800 font-bold text-lg flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-slate-700" />
          Rubric Overview
        </div>
        <div className="text-xs font-semibold text-slate-500">
          {parsedRubric.totalQuestions} questions · {parsedRubric.totalScore} points
        </div>
      </div>

      {/* 解析自白报告 */}
      {selfReport && (
        <div className="mb-4 border border-blue-200 bg-blue-50/30 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between p-3 cursor-pointer hover:bg-blue-50/50 transition-colors"
            onClick={() => setShowSelfReport(!showSelfReport)}
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-semibold text-blue-800">解析质量报告</span>
              <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-semibold ${
                selfReport.overallStatus === 'ok'
                  ? 'bg-emerald-100 text-emerald-700'
                  : selfReport.overallStatus === 'caution'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-rose-100 text-rose-700'
              }`}>
                {selfReport.overallStatus === 'ok' ? '✓ 正常' : selfReport.overallStatus === 'caution' ? '⚠ 需注意' : '⚠ 需复核'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-blue-600">置信度:</span>
                <div className="w-16 h-2 bg-blue-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      selfReport.overallConfidence >= 0.8
                        ? 'bg-emerald-500'
                        : selfReport.overallConfidence >= 0.6
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                    }`}
                    style={{ width: `${selfReport.overallConfidence * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-blue-700">
                  {(selfReport.overallConfidence * 100).toFixed(0)}%
                </span>
              </div>
              {showSelfReport ? <ChevronUp className="w-4 h-4 text-blue-600" /> : <ChevronDown className="w-4 h-4 text-blue-600" />}
            </div>
          </div>

          {showSelfReport && (
            <div className="p-3 pt-0 space-y-3">
              {/* 摘要 */}
              <div className="text-xs text-blue-700 bg-white/50 rounded p-2">
                {selfReport.summary}
              </div>

              {/* 问题列表 */}
              {selfReport.issues && selfReport.issues.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-800 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    问题 ({selfReport.issues.length})
                  </div>
                  <div className="space-y-1">
                    {selfReport.issues.map((issue, idx) => (
                      <div
                        key={idx}
                        className={`text-xs p-2 rounded flex items-start gap-2 ${
                          issue.severity === 'high'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : issue.severity === 'medium'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-blue-50 text-blue-700 border border-blue-200'
                        }`}
                      >
                        {issue.severity === 'high' ? (
                          <XCircle className="w-3 h-3 shrink-0 mt-0.5" />
                        ) : (
                          <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1">
                          {issue.questionId && (
                            <span className="font-mono font-semibold mr-1">Q{issue.questionId}:</span>
                          )}
                          {issue.message}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 不确定性 */}
              {selfReport.uncertainties && selfReport.uncertainties.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-800">
                    不确定性 ({selfReport.uncertainties.length})
                  </div>
                  <div className="space-y-1">
                    {selfReport.uncertainties.map((uncertainty, idx) => (
                      <div key={idx} className="text-xs text-blue-600 bg-white/50 rounded p-2 pl-4 border-l-2 border-blue-300">
                        • {uncertainty}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 质量检查 */}
              {selfReport.qualityChecks && selfReport.qualityChecks.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-800">质量检查</div>
                  <div className="grid grid-cols-2 gap-2">
                    {selfReport.qualityChecks.map((check, idx) => (
                      <div
                        key={idx}
                        className={`text-xs p-2 rounded flex items-start gap-2 ${
                          check.passed
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {check.passed ? (
                          <CheckCircle className="w-3 h-3 shrink-0 mt-0.5" />
                        ) : (
                          <XCircle className="w-3 h-3 shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1">
                          <div className="font-semibold">{check.check}</div>
                          {check.detail && <div className="text-[10px] opacity-80 mt-0.5">{check.detail}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 生成时间 */}
              {selfReport.generatedAt && (
                <div className="text-[10px] text-blue-500 text-right">
                  生成于 {new Date(selfReport.generatedAt).toLocaleString('zh-CN')}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      <div className="space-y-3">
        {parsedRubric.questions.map((q) => (
          <div key={q.questionId} className="border-b border-slate-100 pb-3 last:border-b-0">
            <div className="flex items-center justify-between">
              <div className="text-sm font-bold text-slate-700">
                Q{q.questionId}
              </div>
              <div className="text-xs font-semibold text-slate-500">
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
                    className="text-[10px] border border-slate-200 px-2 py-1 text-slate-600 font-medium flex items-center gap-1"
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
    </div>
  );
}
