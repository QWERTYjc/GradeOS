'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { gradingApi, GradingHistoryDetailResponse, GradingImportItem } from '@/services/api';

type QuestionResult = {
  questionId?: string;
  score?: number;
  maxScore?: number;
  feedback?: string;
  typo_notes?: string[];
  confidence?: number;
  page_indices?: number[];
  scoring_point_results?: Array<{
    point_id?: string;
    description?: string;
    awarded?: number;
    max_points?: number;
    evidence?: string;
    rubric_reference?: string;
    decision?: string;
  }>;
};

export default function GradingHistoryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const importId = params?.importId as string;
  const [detail, setDetail] = useState<GradingHistoryDetailResponse | null>(null);
  const [expandedStudents, setExpandedStudents] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!importId) return;
    setLoading(true);
    gradingApi
      .getGradingHistoryDetail(importId)
      .then((data) => {
        setDetail(data);
        setError('');
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '加载详情失败');
      })
      .finally(() => setLoading(false));
  }, [importId]);

  const toggleStudent = (itemId: string) => {
    setExpandedStudents((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  };

  const items = useMemo(() => detail?.items || [], [detail]);

  const renderResultSummary = (item: GradingImportItem) => {
    const result = item.result || {};
    const score = result.score ?? result.total_score ?? 0;
    const maxScore = result.maxScore ?? result.max_score ?? result.max_total_score ?? 0;
    const percentage = maxScore ? Math.round((score / maxScore) * 100) : 0;
    return { score, maxScore, percentage };
  };

  const getQuestionResults = (item: GradingImportItem): QuestionResult[] => {
    const result = item.result || {};
    return (result.questionResults || result.question_results || []) as QuestionResult[];
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <button
            onClick={() => router.push('/teacher/grading/history')}
            className="text-xs text-slate-500 hover:text-slate-700"
          >
            ← 返回批改历史
          </button>
          <div className="mt-3 flex flex-col gap-2">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Import Detail</p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-2xl font-semibold text-slate-800">批改结果详情</h1>
              {detail && (
                <button
                  onClick={() => router.push(`/grading/results-review/${detail.record.batch_id}`)}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 hover:border-slate-300"
                >
                  进入人工确认
                </button>
              )}
            </div>
            {detail && (
              <div className="mt-2 grid gap-3 text-sm text-slate-600 md:grid-cols-3">
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-400">班级</div>
                  <div className="font-semibold text-slate-800">{detail.record.class_name}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-400">作业</div>
                  <div className="font-semibold text-slate-800">
                    {detail.record.assignment_title || '未绑定作业'}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-400">状态</div>
                  <div className="font-semibold text-slate-800">
                    {detail.record.status === 'revoked' ? '已撤回' : '已导入'}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {loading && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
              加载中...
            </div>
          )}
          {!loading && items.length === 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
              暂无学生记录
            </div>
          )}
          {items.map((item) => {
            const { score, maxScore, percentage } = renderResultSummary(item);
            const expanded = expandedStudents.has(item.item_id);
            const questionResults = getQuestionResults(item);
            const studentSummary = item.result?.studentSummary || item.result?.student_summary;
            const selfAudit = item.result?.selfAudit || item.result?.self_audit;

            return (
              <div key={item.item_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-lg font-semibold text-slate-800">{item.student_name}</div>
                    <div className="text-xs text-slate-400">状态：{item.status === 'revoked' ? '已撤回' : '已导入'}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-slate-500">得分</div>
                    <div className="text-2xl font-semibold text-slate-800">
                      {score}/{maxScore || '--'}
                    </div>
                    <div className="text-xs text-slate-400">{percentage}%</div>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                  {studentSummary?.overall && (
                    <span className="rounded-full bg-slate-100 px-3 py-1">总结：{studentSummary.overall}</span>
                  )}
                  {selfAudit?.summary && (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">自白：{selfAudit.summary}</span>
                  )}
                </div>

                <div className="mt-4">
                  <button
                    onClick={() => toggleStudent(item.item_id)}
                    className="text-xs font-semibold text-slate-600 hover:text-slate-800"
                  >
                    {expanded ? '收起题目明细' : '展开题目明细'}
                  </button>
                </div>

                {expanded && (
                  <div className="mt-4 space-y-4">
                    {questionResults.length === 0 && (
                      <div className="rounded-xl border border-dashed border-slate-200 p-4 text-xs text-slate-400">
                        暂无题目明细
                      </div>
                    )}
                    {questionResults.map((question, idx) => (
                      <div key={`${item.item_id}-q-${idx}`} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="text-sm font-semibold text-slate-700">
                            题号 {question.questionId || idx + 1}
                          </div>
                          <div className="text-xs text-slate-500">
                            {question.score ?? 0}/{question.maxScore ?? 0}
                          </div>
                        </div>
                        {question.feedback && (
                          <p className="mt-2 text-xs text-slate-600">{question.feedback}</p>
                        )}
                        {question.typo_notes && question.typo_notes.length > 0 && (
                          <div className="mt-2 text-xs text-rose-600">
                            错别字：{question.typo_notes.join('、')}
                          </div>
                        )}
                        {question.page_indices && question.page_indices.length > 0 && (
                          <div className="mt-2 text-[11px] text-slate-400">
                            页码：{question.page_indices.map((p) => p + 1).join(', ')}
                          </div>
                        )}
                        {question.scoring_point_results && question.scoring_point_results.length > 0 && (
                          <div className="mt-3 space-y-2 text-xs text-slate-600">
                            {question.scoring_point_results.map((point, pIdx) => (
                              <div key={`${item.item_id}-q-${idx}-p-${pIdx}`} className="rounded-lg border border-slate-200 bg-white p-2">
                                <div className="flex items-center justify-between">
                                  <div className="font-semibold text-slate-700">
                                    {point.point_id || `评分点 ${pIdx + 1}`}
                                  </div>
                                  <div className="text-slate-500">
                                    {point.awarded ?? 0}/{point.max_points ?? 0}
                                  </div>
                                </div>
                                {point.description && <p className="mt-1">{point.description}</p>}
                                {point.evidence && (
                                  <p className="mt-1 text-[11px] text-slate-400">证据：{point.evidence}</p>
                                )}
                                {point.rubric_reference && (
                                  <p className="mt-1 text-[11px] text-slate-400">规则：{point.rubric_reference}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </DashboardLayout>
  );
}
