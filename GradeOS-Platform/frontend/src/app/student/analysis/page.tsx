'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, gradingApi, ClassResponse, GradingHistoryDetailResponse, GradingHistoryResponse } from '@/services/api';

type WrongQuestionEntry = {
  id: string;
  questionId: string;
  score: number;
  maxScore: number;
  feedback: string;
  studentAnswer: string;
  scoringPointResults: Array<{
    point_id?: string;
    description?: string;
    awarded: number;
    max_points?: number;
    evidence: string;
  }>;
  pageIndices: number[];
  sourceImportId: string;
};

type SummaryStats = {
  totalQuestions: number;
  wrongQuestions: number;
  totalScore: number;
  totalMax: number;
};

type FocusStat = {
  questionId: string;
  wrongCount: number;
  totalCount: number;
  ratio: number;
};

const captureFlow = [
  { title: '拍照即录', detail: '扫描试卷或作业，自动识别题号与答案。' },
  { title: '智能标签', detail: '基于知识点与错误类型自动分类。' },
  { title: '举一反三', detail: '推送同类题型与变式练习。' },
  { title: '一键重测', detail: '即时生成针对性重测卷。' },
];

const tagLibrary = ['二次函数', '电路等效', '审题', '计算粗心', '图像分析', '实验设计'];

const recommendedDrills = [
  { id: 'r-01', title: '电路并联等效专项', count: 6, duration: '15 分钟' },
  { id: 'r-02', title: '受力分析基础巩固', count: 5, duration: '12 分钟' },
  { id: 'r-03', title: '顶点式转换练习', count: 8, duration: '18 分钟' },
];

const extractQuestions = (result: Record<string, any>) => {
  return (
    result.questionResults ||
    result.question_results ||
    result.questions ||
    result.questionDetails ||
    result.question_details ||
    []
  );
};

export default function StudentWrongBookPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [wrongQuestions, setWrongQuestions] = useState<WrongQuestionEntry[]>([]);
  const [summary, setSummary] = useState<SummaryStats>({
    totalQuestions: 0,
    wrongQuestions: 0,
    totalScore: 0,
    totalMax: 0,
  });
  const [focusStats, setFocusStats] = useState<FocusStat[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.id) return;
    classApi
      .getMyClasses(user.id)
      .then((data) => {
        setClasses(data);
        if (data.length > 0) {
          setSelectedClassId(data[0].class_id);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : '加载班级失败'));
  }, [user]);

  useEffect(() => {
    if (!selectedClassId || !user?.id) return;
    const loadWrongBook = async () => {
      setLoading(true);
      setError('');
      try {
        const history: GradingHistoryResponse = await gradingApi.getGradingHistory({ class_id: selectedClassId });
        const detailResponses: GradingHistoryDetailResponse[] = await Promise.all(
          history.records.map((record) => gradingApi.getGradingHistoryDetail(record.import_id))
        );
        const studentItems = detailResponses.flatMap((detail) =>
          detail.items.filter((item) => item.student_id === user.id)
        );

        const nextWrong: WrongQuestionEntry[] = [];
        const focusMap = new Map<string, FocusStat>();
        let totalQuestions = 0;
        let wrongCount = 0;
        let totalScore = 0;
        let totalMax = 0;

        studentItems.forEach((item) => {
          const result = item.result || {};
          const questions = extractQuestions(result);
          questions.forEach((question: Record<string, any>, idx: number) => {
            const score = Number(question.score ?? 0);
            const maxScore = Number(question.maxScore ?? question.max_score ?? 0);
            const questionId = String(question.questionId ?? question.question_id ?? idx + 1);
            if (maxScore > 0) {
              totalQuestions += 1;
              totalScore += score;
              totalMax += maxScore;
              const stat = focusMap.get(questionId) || {
                questionId,
                wrongCount: 0,
                totalCount: 0,
                ratio: 0,
              };
              stat.totalCount += 1;
              if (score < maxScore) {
                stat.wrongCount += 1;
              }
              focusMap.set(questionId, stat);
            }

            if (maxScore > 0 && score < maxScore) {
              wrongCount += 1;
              nextWrong.push({
                id: `${item.item_id}-${questionId}`,
                questionId,
                score,
                maxScore,
                feedback: question.feedback || '',
                studentAnswer: question.studentAnswer || question.student_answer || '',
                scoringPointResults: question.scoring_point_results || question.scoringPointResults || [],
                pageIndices: question.page_indices || question.pageIndices || [],
                sourceImportId: item.import_id,
              });
            }
          });
        });

        const focusList = Array.from(focusMap.values())
          .map((stat) => ({
            ...stat,
            ratio: stat.totalCount > 0 ? stat.wrongCount / stat.totalCount : 0,
          }))
          .sort((a, b) => b.ratio - a.ratio)
          .slice(0, 6);

        setWrongQuestions(nextWrong);
        setSummary({
          totalQuestions,
          wrongQuestions: wrongCount,
          totalScore,
          totalMax,
        });
        setFocusStats(focusList);
        setActiveId(nextWrong[0]?.id || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载错题失败');
      } finally {
        setLoading(false);
      }
    };

    loadWrongBook();
  }, [selectedClassId, user?.id]);

  const activeQuestion = useMemo(
    () => wrongQuestions.find((item) => item.id === activeId) || null,
    [wrongQuestions, activeId]
  );

  const accuracyRate = summary.totalMax > 0 ? Math.round((summary.totalScore / summary.totalMax) * 100) : 0;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Wrong Book</p>
            <h1 className="text-2xl font-semibold text-slate-900">学生错题本</h1>
            <p className="text-sm text-slate-500">自动沉淀历次作业错题，并支持深究与复盘。</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600"
            >
              {classes.map((cls) => (
                <option key={cls.class_id} value={cls.class_id}>
                  {cls.class_name}
                </option>
              ))}
            </select>
            <button
              onClick={() => router.push('/student/student_assistant')}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800"
            >
              开启深究助手
            </button>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">错题管理系统</h2>
                <p className="text-xs text-slate-400">消除机械整理，让复练更精准</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600">
                每周节省 4 小时
              </span>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {captureFlow.map((item) => (
                <div key={item.title} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-sm font-semibold text-slate-800">{item.title}</div>
                  <p className="mt-2 text-xs text-slate-500">{item.detail}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {tagLibrary.map((tag) => (
                <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">同类题推荐</h2>
            <p className="text-xs text-slate-400">举一反三，构建闭合复习回路</p>
            <div className="mt-4 space-y-3">
              {recommendedDrills.map((drill) => (
                <div key={drill.id} className="rounded-xl border border-slate-200 px-4 py-3">
                  <div className="flex items-center justify-between text-sm text-slate-700">
                    <span>{drill.title}</span>
                    <span className="text-xs text-slate-400">{drill.count} 题 · {drill.duration}</span>
                  </div>
                  <button className="mt-3 w-full rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">
                    一键生成重测卷
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Accuracy</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">{accuracyRate}%</div>
            <div className="mt-2 text-xs text-slate-500">基于总得分与满分计算</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Wrong Questions</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">{summary.wrongQuestions}</div>
            <div className="mt-2 text-xs text-slate-500">未满分题目数量</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Total Questions</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">{summary.totalQuestions}</div>
            <div className="mt-2 text-xs text-slate-500">已统计题目</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Score</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">
              {Math.round(summary.totalScore)}/{Math.round(summary.totalMax)}
            </div>
            <div className="mt-2 text-xs text-slate-500">累计得分</div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">错题列表</h2>
              <span className="text-xs text-slate-500">共 {wrongQuestions.length} 条</span>
            </div>

            <div className="mt-4 max-h-[520px] overflow-auto space-y-3 pr-2">
              {loading && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                  正在加载错题...
                </div>
              )}
              {!loading && wrongQuestions.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-400">
                  暂无错题记录。
                </div>
              )}
              {wrongQuestions.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveId(item.id)}
                  className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                    activeId === item.id
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-slate-800">Q{item.questionId}</div>
                    <div className="text-xs text-slate-500">
                      {item.score}/{item.maxScore}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-slate-500 line-clamp-2">
                    {item.feedback || item.studentAnswer || '暂无评语'}
                  </div>
                  {item.pageIndices.length > 0 && (
                    <div className="mt-2 text-[11px] text-slate-400">
                      Pages: {item.pageIndices.join(', ')}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">薄弱集中区</h2>
              <div className="mt-4 space-y-3">
                {focusStats.length === 0 && (
                  <div className="text-sm text-slate-400">暂无统计</div>
                )}
                {focusStats.map((stat) => (
                  <div key={stat.questionId} className="rounded-xl border border-slate-200 px-4 py-3">
                    <div className="flex items-center justify-between text-sm text-slate-700">
                      <span>Q{stat.questionId}</span>
                      <span>{Math.round(stat.ratio * 100)}%</span>
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-slate-100">
                      <div
                        className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400"
                        style={{ width: `${Math.round(stat.ratio * 100)}%` }}
                      />
                    </div>
                    <div className="mt-2 text-xs text-slate-500">
                      错题 {stat.wrongCount} / {stat.totalCount}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">错题详情</h2>
              {!activeQuestion && (
                <div className="mt-3 text-sm text-slate-400">选择左侧错题查看详情。</div>
              )}
              {activeQuestion && (
                <div className="mt-4 space-y-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                    <div className="font-semibold text-slate-700">Q{activeQuestion.questionId}</div>
                    <div className="mt-2 text-xs text-slate-500">
                      得分 {activeQuestion.score}/{activeQuestion.maxScore}
                    </div>
                  </div>
                  {activeQuestion.studentAnswer && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Student Answer</div>
                      <p className="mt-2 whitespace-pre-wrap">{activeQuestion.studentAnswer}</p>
                    </div>
                  )}
                  {activeQuestion.feedback && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Feedback</div>
                      <p className="mt-2 whitespace-pre-wrap">{activeQuestion.feedback}</p>
                    </div>
                  )}
                  {activeQuestion.scoringPointResults.length > 0 && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Scoring Points</div>
                      <div className="mt-3 space-y-2">
                        {activeQuestion.scoringPointResults.map((sp, idx) => (
                          <div key={`${activeQuestion.id}-${idx}`} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                            <div className="flex items-center justify-between text-xs text-slate-500">
                              <span>{sp.point_id || `P${idx + 1}`}</span>
                              <span>
                                {sp.awarded}/{sp.max_points ?? '--'}
                              </span>
                            </div>
                            <div className="mt-2 text-sm text-slate-700">{sp.description || '评分点'}</div>
                            {sp.evidence && (
                              <div className="mt-2 text-xs text-slate-500">{sp.evidence}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <button
                    onClick={() => router.push('/student/student_assistant')}
                    className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow hover:bg-slate-800"
                  >
                    深究这道题
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
