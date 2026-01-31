'use client';

import React, { useState } from 'react';
import { useConsoleStore } from '@/store/consoleStore';
import { BookOpen, ListOrdered, AlertCircle, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';

const RubricQuestionCard = ({ q }: { q: any }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <GlassCard
      className="flex flex-col gap-2 p-3 cursor-pointer transition-all h-full"
      hoverEffect={true}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">Q{q.questionId}</span>
          <span className="text-xs font-semibold text-slate-500">{q.maxScore} pts</span>
        </div>
        {expanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
      </div>

      {q.questionText && (
        <div className={clsx("text-xs text-slate-600 leading-relaxed", !expanded && "line-clamp-2")}>
          {q.questionText}
        </div>
      )}

      <AnimatePresence>
        {expanded && q.scoringPoints?.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 space-y-1.5 border-t border-slate-100 pt-2"
          >
            {q.scoringPoints.map((sp: any) => (
              <div key={`${q.questionId}-${sp.pointId}`} className="text-[10px] bg-slate-50 p-1.5 rounded border border-slate-100">
                <div className="flex items-center justify-between font-medium text-slate-700 mb-0.5">
                  <span className="flex items-center gap-1">
                    <ListOrdered className="w-3 h-3 text-slate-400" />
                    Pt {sp.pointId}
                  </span>
                  <span>{sp.score} pts</span>
                </div>
                <div className="text-slate-500 leading-snug">{sp.description}</div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {!expanded && q.scoringPoints?.length > 0 && (
        <div className="mt-auto pt-2 flex items-center gap-1.5">
          <span className="text-[10px] text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">
            {q.scoringPoints.length} scoring points
          </span>
        </div>
      )}
    </GlassCard>
  );
};

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
              <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-semibold ${selfReport.overallStatus === 'ok'
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
                    className={`h-full rounded-full transition-all ${selfReport.overallConfidence >= 0.8
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
                        className={`text-xs p-2 rounded flex items-start gap-2 ${issue.severity === 'high'
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
                        className={`text-xs p-2 rounded flex items-start gap-2 ${check.passed
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
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {parsedRubric.questions.map((q) => (
          <RubricQuestionCard key={q.questionId} q={q} />
        ))}
      </div>
    </div>
  );
}
