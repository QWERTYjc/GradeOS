'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { gradingApi } from '@/services/api';

interface StudentResult {
  student_id?: string;
  student_name?: string;
  total_score?: number;
  max_score?: number;
  questions?: Array<{
    question_id?: string;
    question_number?: string;
    score?: number;
    max_score?: number;
    feedback?: string;
    scoring_points?: Array<{
      point_id?: string;
      description?: string;
      score?: number;
      max_score?: number;
      is_correct?: boolean;
    }>;
  }>;
  page_indices?: number[];
}

interface ClassReport {
  total_students?: number;
  average_score?: number;
  max_score?: number;
  min_score?: number;
  score_distribution?: Record<string, number>;
  weak_points?: Array<{
    question_id?: string;
    question_number?: string;
    error_rate?: number;
    common_errors?: string[];
  }>;
}

export default function TeachingCockpitPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const batchId = searchParams.get('batchId') || '';
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [studentResults, setStudentResults] = useState<StudentResult[]>([]);
  const [answerImages, setAnswerImages] = useState<string[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<StudentResult | null>(null);
  const [inputBatchId, setInputBatchId] = useState(batchId);

  // 计算班级报告
  const classReport = useMemo<ClassReport>(() => {
    if (studentResults.length === 0) return {};
    
    const scores = studentResults
      .map(s => s.total_score ?? 0)
      .filter(s => s > 0);
    
    if (scores.length === 0) return { total_students: studentResults.length };
    
    const total = scores.reduce((a, b) => a + b, 0);
    const avg = total / scores.length;
    const max = Math.max(...scores);
    const min = Math.min(...scores);
    
    // 分数分布
    const distribution: Record<string, number> = {
      '0-59': 0,
      '60-69': 0,
      '70-79': 0,
      '80-89': 0,
      '90-100': 0,
    };
    
    scores.forEach(score => {
      const pct = (score / (studentResults[0]?.max_score || 100)) * 100;
      if (pct < 60) distribution['0-59']++;
      else if (pct < 70) distribution['60-69']++;
      else if (pct < 80) distribution['70-79']++;
      else if (pct < 90) distribution['80-89']++;
      else distribution['90-100']++;
    });
    
    // 薄弱点分析
    const questionStats: Record<string, { total: number; correct: number; errors: string[] }> = {};
    
    studentResults.forEach(student => {
      student.questions?.forEach(q => {
        const qId = q.question_number || q.question_id || 'unknown';
        if (!questionStats[qId]) {
          questionStats[qId] = { total: 0, correct: 0, errors: [] };
        }
        questionStats[qId].total++;
        if (q.score === q.max_score) {
          questionStats[qId].correct++;
        } else if (q.feedback) {
          questionStats[qId].errors.push(q.feedback);
        }
      });
    });
    
    const weakPoints = Object.entries(questionStats)
      .map(([qId, stats]) => ({
        question_id: qId,
        question_number: qId,
        error_rate: stats.total > 0 ? (stats.total - stats.correct) / stats.total : 0,
        common_errors: [...new Set(stats.errors)].slice(0, 3),
      }))
      .filter(wp => wp.error_rate > 0.3)
      .sort((a, b) => b.error_rate - a.error_rate)
      .slice(0, 5);
    
    return {
      total_students: studentResults.length,
      average_score: Math.round(avg * 10) / 10,
      max_score: max,
      min_score: min,
      score_distribution: distribution,
      weak_points: weakPoints,
    };
  }, [studentResults]);

  const fetchResults = async (id: string) => {
    if (!id) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await gradingApi.getResultsReviewContext(id);
      setStudentResults(data.student_results || []);
      setAnswerImages(data.answer_images || []);
      if (data.student_results?.length > 0) {
        setSelectedStudent(data.student_results[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载批改结果失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (batchId) {
      setInputBatchId(batchId);
      fetchResults(batchId);
    }
  }, [batchId]);

  const handleSearch = () => {
    if (inputBatchId) {
      router.push(`/teacher/cockpit?batchId=${inputBatchId}`);
      fetchResults(inputBatchId);
    }
  };

  // 按分数排序的学生列表
  const sortedStudents = useMemo(() => {
    return [...studentResults].sort((a, b) => (b.total_score ?? 0) - (a.total_score ?? 0));
  }, [studentResults]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Teaching Cockpit</p>
            <h1 className="text-2xl font-semibold text-slate-800">批改结果分析</h1>
            <p className="text-sm text-slate-500">
              查看和分析 AI 批改结果，了解班级整体表现和薄弱环节。
            </p>
          </div>
          
          {/* 批次 ID 输入 */}
          <div className="flex gap-3">
            <input
              type="text"
              value={inputBatchId}
              onChange={(e) => setInputBatchId(e.target.value)}
              placeholder="输入批次 ID (batch_id)"
              className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
            <button
              onClick={handleSearch}
              disabled={loading || !inputBatchId}
              className="rounded-lg bg-emerald-500 px-6 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              {loading ? '加载中...' : '查询'}
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        {studentResults.length > 0 && (
          <>
            {/* 班级概览 */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-400">学生人数</p>
                <p className="text-2xl font-bold text-slate-800">{classReport.total_students}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-400">平均分</p>
                <p className="text-2xl font-bold text-emerald-600">{classReport.average_score ?? '-'}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-400">最高分</p>
                <p className="text-2xl font-bold text-blue-600">{classReport.max_score ?? '-'}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-400">最低分</p>
                <p className="text-2xl font-bold text-orange-600">{classReport.min_score ?? '-'}</p>
              </div>
            </div>

            {/* 分数分布 */}
            {classReport.score_distribution && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="mb-4 text-lg font-semibold text-slate-800">分数分布</h2>
                <div className="flex items-end gap-2 h-32">
                  {Object.entries(classReport.score_distribution).map(([range, count]) => {
                    const maxCount = Math.max(...Object.values(classReport.score_distribution!));
                    const height = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    return (
                      <div key={range} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full bg-emerald-500 rounded-t transition-all"
                          style={{ height: `${height}%`, minHeight: count > 0 ? '8px' : '0' }}
                        />
                        <span className="text-xs text-slate-500">{range}</span>
                        <span className="text-xs font-semibold text-slate-700">{count}人</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 薄弱点分析 */}
            {classReport.weak_points && classReport.weak_points.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="mb-4 text-lg font-semibold text-slate-800">薄弱环节分析</h2>
                <div className="space-y-3">
                  {classReport.weak_points.map((wp, idx) => (
                    <div key={idx} className="flex items-center gap-4 rounded-lg border border-slate-100 p-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-100 text-orange-600 font-semibold">
                        {wp.question_number}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-slate-700">
                          错误率: {Math.round(wp.error_rate * 100)}%
                        </p>
                        {wp.common_errors.length > 0 && (
                          <p className="text-xs text-slate-500 mt-1">
                            常见错误: {wp.common_errors.join('; ')}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 学生列表和详情 */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* 学生列表 */}
              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 p-4">
                  <h2 className="text-lg font-semibold text-slate-800">学生成绩排名</h2>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {sortedStudents.map((student, idx) => (
                    <div
                      key={student.student_id || idx}
                      onClick={() => setSelectedStudent(student)}
                      className={`flex items-center gap-3 border-b border-slate-100 p-3 cursor-pointer hover:bg-slate-50 ${
                        selectedStudent?.student_id === student.student_id ? 'bg-emerald-50' : ''
                      }`}
                    >
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
                        idx < 3 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'
                      }`}>
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-slate-700">
                          {student.student_name || `学生 ${idx + 1}`}
                        </p>
                        <p className="text-xs text-slate-400">
                          ID: {student.student_id || '-'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-emerald-600">
                          {student.total_score ?? '-'}
                        </p>
                        <p className="text-xs text-slate-400">
                          / {student.max_score ?? '-'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 学生详情 */}
              <div className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 p-4">
                  <h2 className="text-lg font-semibold text-slate-800">
                    {selectedStudent?.student_name || '学生详情'}
                  </h2>
                  {selectedStudent && (
                    <p className="text-sm text-slate-500">
                      总分: {selectedStudent.total_score} / {selectedStudent.max_score}
                    </p>
                  )}
                </div>
                <div className="max-h-96 overflow-y-auto p-4">
                  {selectedStudent?.questions?.map((q, idx) => (
                    <div key={idx} className="mb-4 rounded-lg border border-slate-100 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-slate-700">
                          题目 {q.question_number || q.question_id || idx + 1}
                        </span>
                        <span className={`font-bold ${
                          q.score === q.max_score ? 'text-emerald-600' : 'text-orange-600'
                        }`}>
                          {q.score} / {q.max_score}
                        </span>
                      </div>
                      {q.feedback && (
                        <p className="text-sm text-slate-600 mb-2">{q.feedback}</p>
                      )}
                      {q.scoring_points && q.scoring_points.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {q.scoring_points.map((sp, spIdx) => (
                            <div key={spIdx} className="flex items-center gap-2 text-xs">
                              <span className={`w-4 h-4 rounded-full flex items-center justify-center ${
                                sp.is_correct ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'
                              }`}>
                                {sp.is_correct ? '✓' : '✗'}
                              </span>
                              <span className="text-slate-600">{sp.description}</span>
                              <span className="ml-auto text-slate-500">
                                {sp.score}/{sp.max_score}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {!selectedStudent && (
                    <p className="text-center text-slate-400 py-8">
                      请从左侧选择一个学生查看详情
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {!loading && studentResults.length === 0 && batchId && (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-sm">
            <p className="text-slate-400">未找到批改结果</p>
          </div>
        )}

        {!batchId && (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-sm">
            <p className="text-slate-500 mb-2">请输入批次 ID 查询批改结果</p>
            <p className="text-xs text-slate-400">
              测试批次: 68996b25-b310-4d7d-ad0a-7c2ef47e9f93
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
