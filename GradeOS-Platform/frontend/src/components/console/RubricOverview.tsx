'use client';

import React, { useState } from 'react';
import { useConsoleStore } from '@/store/consoleStore';
import { BookOpen, ListOrdered, AlertCircle, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp, ShieldAlert, Eye, HelpCircle } from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';

// LLM 直接生成的自白（极短）
interface LLMConfession {
  risks?: string[];
  uncertainties?: string[];
  blindSpots?: string[];
  needsReview?: string[];
  confidence?: number;
  selfReviewed?: boolean;
  selfReviewApplied?: boolean;
}

// 题目级自白
interface QuestionConfession {
  risk?: string;
  uncertainty?: string;
}

const RubricQuestionCard = ({ q }: { q: any }) => {
  const [expanded, setExpanded] = useState(false);
  const confession: QuestionConfession = q.confession || {};
  const hasConfession = confession.risk || confession.uncertainty;

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
          {hasConfession && (
            <span className="text-[10px] text-amber-600 bg-amber-50 px-1 py-0.5 rounded flex items-center gap-0.5">
              <ShieldAlert className="w-2.5 h-2.5" />
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
      </div>

      {/* 题目级自白（极短） */}
      {hasConfession && (
        <div className="text-[10px] text-amber-700 bg-amber-50/50 rounded p-1.5 border border-amber-100">
          {confession.risk && <div className="flex items-center gap-1"><ShieldAlert className="w-2.5 h-2.5" /> {confession.risk}</div>}
          {confession.uncertainty && <div className="flex items-center gap-1"><HelpCircle className="w-2.5 h-2.5" /> {confession.uncertainty}</div>}
        </div>
      )}

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
  const [showConfession, setShowConfession] = useState(true);
  const [showLLMConfession, setShowLLMConfession] = useState(true);

  if (!parsedRubric || !parsedRubric.questions || parsedRubric.questions.length === 0) {
    return (
      <div className="p-6 flex items-center justify-center text-slate-400 text-sm gap-2">
        <BookOpen className="w-4 h-4 opacity-50" />
        Rubric not available yet.
      </div>
    );
  }

  const anyRubric: any = parsedRubric as any;
  const totalQuestions = Number(
    anyRubric.totalQuestions ?? anyRubric.total_questions ?? (Array.isArray(anyRubric.questions) ? anyRubric.questions.length : 0)
  );
  const totalScore = Number(
    anyRubric.totalScore
      ?? anyRubric.total_score
      ?? (Array.isArray(anyRubric.questions)
        ? anyRubric.questions.reduce((sum: number, q: any) => sum + Number(q.maxScore ?? q.max_score ?? 0), 0)
        : 0)
  );

  // LLM 直接生成的自白（极短）
  const llmConfession: LLMConfession = parsedRubric.confession || {};
  const hasLLMConfession = (llmConfession.risks?.length || 0) > 0 ||
    (llmConfession.uncertainties?.length || 0) > 0 ||
    (llmConfession.blindSpots?.length || 0) > 0 ||
    (llmConfession.needsReview?.length || 0) > 0;
  
  // 规则检查生成的报告（兼容旧版）
  const confession = parsedRubric.parseConfession;
  const confessionReport = (parsedRubric as any).confession_report || (parsedRubric as any).confessionReport;
  const confessionReportItems = Array.isArray(confessionReport?.items) ? confessionReport.items : [];
  const hasConfessionReport = confessionReport?.version === 'confession_report_v1' && confessionReportItems.length > 0;

  return (
    <div className="border-t border-slate-100 pt-6">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100/60">
        <div className="text-slate-800 font-bold text-lg flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-slate-700" />
          Rubric Overview
        </div>
        <div className="text-xs font-semibold text-slate-500">
          {totalQuestions} questions · {totalScore} points
        </div>
      </div>

      {/* LLM 直接生成的自白（极短，优先显示） */}
      {hasLLMConfession && (
        <div className="mb-4 border border-amber-200 bg-amber-50/30 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between p-3 cursor-pointer hover:bg-amber-50/50 transition-colors"
            onClick={() => setShowLLMConfession(!showLLMConfession)}
          >
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-600" />
              <span className="text-sm font-semibold text-amber-800">AI 自白</span>
              {llmConfession.selfReviewed && (
                <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-700">
                  已自动复核
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-amber-600">置信度:</span>
                <div className="w-16 h-2 bg-amber-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${(llmConfession.confidence || 1) >= 0.9
                      ? 'bg-emerald-500'
                      : (llmConfession.confidence || 1) >= 0.7
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                      }`}
                    style={{ width: `${(llmConfession.confidence || 1) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-amber-700">
                  {((llmConfession.confidence || 1) * 100).toFixed(0)}%
                </span>
              </div>
              {showLLMConfession ? <ChevronUp className="w-4 h-4 text-amber-600" /> : <ChevronDown className="w-4 h-4 text-amber-600" />}
            </div>
          </div>

          {showLLMConfession && (
            <div className="p-3 pt-0 space-y-2">
              {/* 风险 */}
              {llmConfession.risks && llmConfession.risks.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-semibold text-amber-800 flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3" /> 风险
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {llmConfession.risks.map((risk, idx) => (
                      <span key={`llm-risk-${idx}-${risk.substring(0, 10)}`} className="text-[10px] px-2 py-1 bg-rose-100 text-rose-700 rounded-full">
                        {risk}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 不确定点 */}
              {llmConfession.uncertainties && llmConfession.uncertainties.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-semibold text-amber-800 flex items-center gap-1">
                    <HelpCircle className="w-3 h-3" /> 不确定
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {llmConfession.uncertainties.map((u, idx) => (
                      <span key={`llm-uncertainty-${idx}-${u.substring(0, 10)}`} className="text-[10px] px-2 py-1 bg-amber-100 text-amber-700 rounded-full">
                        {u}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 可能遗漏 */}
              {llmConfession.blindSpots && llmConfession.blindSpots.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-semibold text-amber-800 flex items-center gap-1">
                    <Eye className="w-3 h-3" /> 可能遗漏
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {llmConfession.blindSpots.map((b, idx) => (
                      <span key={`llm-blindspot-${idx}-${b.substring(0, 10)}`} className="text-[10px] px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                        {b}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 建议复核 */}
              {llmConfession.needsReview && llmConfession.needsReview.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-semibold text-amber-800 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> 建议复核
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {llmConfession.needsReview.map((n, idx) => (
                      <span key={`llm-needsreview-${idx}-${n.substring(0, 10)}`} className="text-[10px] px-2 py-1 bg-purple-100 text-purple-700 rounded-full">
                        {n}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 独立自白报告（一次独立 LLM call） */}
      {hasConfessionReport && (
        <div className="mb-4 border border-slate-200 bg-white rounded-lg overflow-hidden">
          <div className="flex items-center justify-between p-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-slate-700" />
              <span className="text-sm font-semibold text-slate-800">独立自白报告</span>
              {confessionReport?.honesty?.grade && (
                <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                  诚实度 {String(confessionReport.honesty.grade)}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              {confessionReport?.riskScore !== undefined || confessionReport?.risk_score !== undefined ? (
                <span>risk {Number(confessionReport.riskScore ?? confessionReport.risk_score).toFixed(2)}</span>
              ) : null}
              {confessionReport?.overallConfidence !== undefined || confessionReport?.overall_confidence !== undefined ? (
                <span>conf {Number(confessionReport.overallConfidence ?? confessionReport.overall_confidence).toFixed(2)}</span>
              ) : null}
            </div>
          </div>
          <div className="p-3 space-y-2">
            {confessionReportItems.slice(0, 8).map((item: any, idx: number) => (
              <div key={idx} className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-2">
                <div className="font-semibold text-slate-800">
                  [{String(item?.severity || 'warning').toUpperCase()}] {String(item?.issue_type || item?.issueType || 'issue')}
                </div>
                {item?.action && <div className="mt-1 text-slate-600">{String(item.action)}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 规则检查生成的报告（兼容旧版） */}
      {confession && (
        <div className="mb-4 border border-blue-200 bg-blue-50/30 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between p-3 cursor-pointer hover:bg-blue-50/50 transition-colors"
            onClick={() => setShowConfession(!showConfession)}
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-semibold text-blue-800">解析质量报告</span>
              <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-semibold ${confession.overallStatus === 'ok'
                ? 'bg-emerald-100 text-emerald-700'
                : confession.overallStatus === 'caution'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-rose-100 text-rose-700'
                }`}>
                {confession.overallStatus === 'ok' ? '✓ 正常' : confession.overallStatus === 'caution' ? '⚠ 需注意' : '⚠ 需复核'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-blue-600">置信度:</span>
                <div className="w-16 h-2 bg-blue-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${confession.overallConfidence >= 0.8
                      ? 'bg-emerald-500'
                      : confession.overallConfidence >= 0.6
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                      }`}
                    style={{ width: `${confession.overallConfidence * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-blue-700">
                  {(confession.overallConfidence * 100).toFixed(0)}%
                </span>
              </div>
              {showConfession ? <ChevronUp className="w-4 h-4 text-blue-600" /> : <ChevronDown className="w-4 h-4 text-blue-600" />}
            </div>
          </div>

          {showConfession && (
            <div className="p-3 pt-0 space-y-3">
              {/* 摘要 */}
              <div className="text-xs text-blue-700 bg-white/50 rounded p-2">
                {confession.summary}
              </div>

              {/* 问题列表 */}
              {confession.issues && confession.issues.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-800 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    问题 ({confession.issues.length})
                  </div>
                  <div className="space-y-1">
                    {confession.issues.map((issue, idx) => (
                      <div
                        key={`conf-issue-${issue.questionId || 'general'}-${idx}-${issue.message?.substring(0, 10) || ''}`}
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
              {confession.uncertainties && confession.uncertainties.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-800">
                    不确定性 ({confession.uncertainties.length})
                  </div>
                  <div className="space-y-1">
                    {confession.uncertainties.map((uncertainty, idx) => (
                      <div key={`conf-uncertainty-${idx}-${uncertainty.substring(0, 10)}`} className="text-xs text-blue-600 bg-white/50 rounded p-2 pl-4 border-l-2 border-blue-300">
                        • {uncertainty}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 质量检查 */}
              {confession.qualityChecks && confession.qualityChecks.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-800">质量检查</div>
                  <div className="grid grid-cols-2 gap-2">
                    {confession.qualityChecks.map((check, idx) => (
                      <div
                        key={`conf-check-${idx}-${check.check?.substring(0, 15) || ''}`}
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
              {confession.generatedAt && (
                <div className="text-[10px] text-blue-500 text-right">
                  生成于 {new Date(confession.generatedAt).toLocaleString('zh-CN')}
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
