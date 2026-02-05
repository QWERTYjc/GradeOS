'use client';

import { useEffect, useState, useMemo } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, homeworkApi, gradingApi, ClassResponse, HomeworkResponse, GradingImportRecord, getApiBaseUrl } from '@/services/api';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts';

// ============ 类型定义 ============
interface QuestionResult {
  question_id?: string;
  questionId?: string;
  question_number?: string;
  questionNumber?: string;
  score?: number;
  max_score?: number;
  maxScore?: number;
  feedback?: string;
}

interface StudentResult {
  student_id?: string;
  studentId?: string;
  student_name?: string;
  studentName?: string;
  total_score?: number;
  totalScore?: number;
  max_score?: number;
  maxScore?: number;
  questions?: QuestionResult[];
  questionResults?: QuestionResult[];
}

type GradingRecord = GradingImportRecord;

interface QuestionStats {
  questionId: string;
  questionNumber: string;
  totalScore: number;
  maxPossibleScore: number;
  scoreRate: number;
  studentCount: number;
  wrongFeedbacks: string[];
}

// ============ 工具函数 ============
const getScoreColor = (rate: number): string => {
  if (rate >= 0.8) return 'bg-emerald-500';
  if (rate >= 0.6) return 'bg-amber-500';
  return 'bg-rose-500';
};

const getScoreBarColor = (rate: number): string => {
  if (rate >= 0.8) return '#22c55e';
  if (rate >= 0.6) return '#f59e0b';
  return '#ef4444';
};

// ============ 作业选择器组件 ============
interface AssignmentDotProps {
  homework: HomeworkResponse;
  isSelected: boolean;
  hasGradingData: boolean;
  averageScore?: number;
  onClick: () => void;
  index: number;
}

const AssignmentDot: React.FC<AssignmentDotProps> = ({
  homework,
  isSelected,
  hasGradingData,
  averageScore,
  onClick,
  index,
}) => {
  const bgColor = hasGradingData && averageScore !== undefined
    ? (averageScore >= 80 ? 'bg-emerald-500' : averageScore >= 60 ? 'bg-amber-500' : 'bg-rose-500')
    : 'bg-slate-200';

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        onClick={onClick}
        className={`
          relative w-12 h-12 rounded-full cursor-pointer transition-all duration-200
          ${bgColor}
          ${isSelected ? 'ring-3 ring-blue-500 ring-offset-2 scale-110' : 'hover:scale-105'}
          ${!hasGradingData ? 'opacity-50' : ''}
        `}
        title={`${homework.title}${averageScore !== undefined ? ` - 平均分: ${averageScore.toFixed(1)}` : ' - 暂无数据'}`}
      >
        {hasGradingData && averageScore !== undefined ? (
          <span className="absolute inset-0 flex items-center justify-center text-white text-sm font-bold">
            {Math.round(averageScore)}
          </span>
        ) : (
          <span className="absolute inset-0 flex items-center justify-center text-slate-500 text-xs">
            {index + 1}
          </span>
        )}
      </button>
      <span className={`text-xs max-w-16 truncate ${isSelected ? 'text-blue-600 font-medium' : 'text-slate-500'}`}>
        {homework.title.length > 6 ? homework.title.slice(0, 6) + '...' : homework.title}
      </span>
    </div>
  );
};

// ============ 主组件 ============
export default function TeacherPerformancePage() {
  const { user } = useAuthStore();
  
  // 班级和作业选择
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [homeworks, setHomeworks] = useState<HomeworkResponse[]>([]);
  const [selectedHomework, setSelectedHomework] = useState<string>('');
  
  // 批改历史和结果
  const [gradingHistory, setGradingHistory] = useState<GradingRecord[]>([]);
  const [studentResults, setStudentResults] = useState<StudentResult[]>([]);
  
  // AI 总结
  const [commonMistakes, setCommonMistakes] = useState<string>('');
  const [summarizing, setSummarizing] = useState(false);
  
  // 加载状态
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载班级列表
  useEffect(() => {
    if (!user?.id) return;
    let active = true;
    classApi.getTeacherClasses(user.id)
      .then((items) => {
        if (!active) return;
        setClasses(items);
        if (!selectedClass && items.length) {
          setSelectedClass(items[0].class_id);
        }
      })
      .catch((err) => {
        console.error('加载班级失败', err);
        setClasses([]);
      });
    return () => { active = false; };
  }, [user?.id]);

  // 加载作业列表
  useEffect(() => {
    if (!selectedClass) return;
    let active = true;
    homeworkApi.getList({ class_id: selectedClass })
      .then((items) => {
        if (!active) return;
        setHomeworks(items);
        // 默认选中第一个有批改数据的作业
        setSelectedHomework('');
      })
      .catch((err) => {
        console.error('加载作业失败', err);
        setHomeworks([]);
      });
    return () => { active = false; };
  }, [selectedClass]);

  // 加载批改历史
  useEffect(() => {
    if (!selectedClass) return;
    let active = true;
    setHistoryLoading(true);
    
    gradingApi.getGradingHistory({ class_id: selectedClass })
      .then(async (data) => {
        if (!active) return;
        const records = data.records || [];
        
        // 为每个批次加载统计数据
        const recordsWithStats: GradingRecord[] = await Promise.all(
          records.map(async (record) => {
            if (record.status === 'revoked' || !record.batch_id) {
              return record;
            }
            try {
              const results = await gradingApi.getResultsReviewContext(record.batch_id);
              const studentResults = results.student_results || [];
              
              const scores = studentResults
                .map((s: StudentResult) => s.total_score ?? s.totalScore ?? 0)
                .filter((s: number) => s > 0);
              
              if (scores.length > 0) {
                const avg = scores.reduce((a: number, b: number) => a + b, 0) / scores.length;
                return {
                  ...record,
                  statistics: {
                    average_score: Math.round(avg * 10) / 10,
                    max_score: Math.max(...scores),
                    min_score: Math.min(...scores),
                  },
                };
              }
            } catch (err) {
              console.error(`加载批次 ${record.batch_id} 统计失败`, err);
            }
            return record;
          })
        );
        
        setGradingHistory(recordsWithStats);
        
        // 自动选中第一个有数据的作业
        const firstWithData = recordsWithStats.find(r => r.status !== 'revoked' && r.statistics);
        if (firstWithData?.assignment_id) {
          setSelectedHomework(firstWithData.assignment_id);
        }
      })
      .catch((err) => {
        console.error('加载批改历史失败', err);
        setGradingHistory([]);
      })
      .finally(() => {
        if (active) setHistoryLoading(false);
      });
    return () => { active = false; };
  }, [selectedClass]);

  // 当选择特定作业时，加载该作业的批改结果
  useEffect(() => {
    if (!selectedHomework || gradingHistory.length === 0) {
      setStudentResults([]);
      setCommonMistakes('');
      return;
    }
    
    const latestRecord = gradingHistory.find(r => 
      r.assignment_id === selectedHomework && r.status !== 'revoked'
    );
    
    if (!latestRecord?.batch_id) {
      setStudentResults([]);
      setCommonMistakes('');
      return;
    }
    
    let active = true;
    setLoading(true);
    setError(null);
    setCommonMistakes('');
    
    gradingApi.getResultsReviewContext(latestRecord.batch_id)
      .then((data) => {
        if (!active) return;
        setStudentResults(data.student_results || []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : '加载批改结果失败');
        setStudentResults([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    
    return () => { active = false; };
  }, [selectedHomework, gradingHistory]);

  // 获取作业对应的批改记录
  const getHomeworkGradingRecord = (homeworkId: string): GradingRecord | undefined => {
    return gradingHistory.find(r => 
      r.assignment_id === homeworkId && r.status !== 'revoked'
    );
  };

  // 计算每题得分率统计
  const questionStats = useMemo<QuestionStats[]>(() => {
    if (studentResults.length === 0) return [];
    
    const statsMap = new Map<string, QuestionStats>();
    
    studentResults.forEach((student) => {
      const questions = student.questions || student.questionResults || [];
      questions.forEach((q, idx) => {
        const qId = q.question_id || q.questionId || `q${idx + 1}`;
        const qNum = q.question_number || q.questionNumber || `${idx + 1}`;
        const score = q.score ?? 0;
        const maxScore = q.max_score ?? q.maxScore ?? 0;
        
        if (!statsMap.has(qId)) {
          statsMap.set(qId, {
            questionId: qId,
            questionNumber: qNum,
            totalScore: 0,
            maxPossibleScore: 0,
            scoreRate: 0,
            studentCount: 0,
            wrongFeedbacks: [],
          });
        }
        
        const stat = statsMap.get(qId)!;
        stat.totalScore += score;
        stat.maxPossibleScore += maxScore;
        stat.studentCount += 1;
        
        // 收集错题的 feedback
        if (maxScore > 0 && score < maxScore && q.feedback) {
          stat.wrongFeedbacks.push(q.feedback);
        }
      });
    });
    
    // 计算得分率
    const result = Array.from(statsMap.values()).map(stat => ({
      ...stat,
      scoreRate: stat.maxPossibleScore > 0 ? stat.totalScore / stat.maxPossibleScore : 0,
    }));
    
    // 按题号排序
    return result.sort((a, b) => {
      const numA = parseInt(a.questionNumber) || 0;
      const numB = parseInt(b.questionNumber) || 0;
      return numA - numB;
    });
  }, [studentResults]);

  // 收集所有错题的 feedback 用于 AI 总结
  const allWrongFeedbacks = useMemo(() => {
    return questionStats.flatMap(q => q.wrongFeedbacks);
  }, [questionStats]);

  // AI 总结常错知识点
  const summarizeCommonMistakes = async () => {
    if (allWrongFeedbacks.length === 0) {
      setCommonMistakes('本次作业没有错题反馈数据。');
      return;
    }
    
    setSummarizing(true);
    setCommonMistakes('');
    
    try {
      // 调用后端 API 进行 AI 总结
      const apiBase = getApiBaseUrl();
      const response = await fetch(`${apiBase}/assistant/summarize-mistakes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedbacks: allWrongFeedbacks.slice(0, 50), // 限制数量避免 token 过多
          assignment_title: homeworks.find(h => h.homework_id === selectedHomework)?.title || '作业',
        }),
      });
      
      if (!response.ok) {
        throw new Error('AI 总结请求失败');
      }
      
      const data = await response.json();
      setCommonMistakes(data.summary || '无法生成总结');
    } catch (err) {
      console.error('AI 总结失败:', err);
      // 如果 API 不存在，使用本地简单总结
      const uniqueFeedbacks = [...new Set(allWrongFeedbacks)];
      const summary = `本次作业共有 ${allWrongFeedbacks.length} 条错题反馈。\n\n常见问题类型：\n${uniqueFeedbacks.slice(0, 10).map((f, i) => `${i + 1}. ${f.slice(0, 100)}${f.length > 100 ? '...' : ''}`).join('\n')}`;
      setCommonMistakes(summary);
    } finally {
      setSummarizing(false);
    }
  };

  // 计算班级基本统计
  const classStats = useMemo(() => {
    if (studentResults.length === 0) return null;
    
    const scores = studentResults
      .map(s => s.total_score ?? s.totalScore ?? 0)
      .filter(s => s > 0);
    
    if (scores.length === 0) return { total_students: studentResults.length };
    
    const total = scores.reduce((a, b) => a + b, 0);
    const avg = total / scores.length;
    const max = Math.max(...scores);
    const min = Math.min(...scores);
    
    return {
      total_students: studentResults.length,
      average_score: Math.round(avg * 10) / 10,
      max_score: max,
      min_score: min,
    };
  }, [studentResults]);

  // ============ 渲染 ============
  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Assignment Analysis</p>
            <h1 className="text-2xl font-semibold text-slate-900">作业分析看板</h1>
            <p className="text-sm text-slate-500">查看每次作业的题目得分率与常错知识点分析。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {classes.map(cls => (
              <button
                key={cls.class_id}
                onClick={() => setSelectedClass(cls.class_id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                  selectedClass === cls.class_id
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cls.class_name}
              </button>
            ))}
          </div>
        </div>

        {/* 作业选择器 */}
        {homeworks.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm text-slate-600 font-medium">选择作业查看分析:</span>
            </div>
            <div className="flex items-end gap-4 overflow-x-auto pb-2">
              {homeworks.map((hw, idx) => {
                const record = getHomeworkGradingRecord(hw.homework_id);
                return (
                  <AssignmentDot
                    key={hw.homework_id}
                    homework={hw}
                    isSelected={selectedHomework === hw.homework_id}
                    hasGradingData={!!record?.statistics}
                    averageScore={record?.statistics?.average_score}
                    onClick={() => setSelectedHomework(hw.homework_id)}
                    index={idx}
                  />
                );
              })}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        {/* 未选择作业时的提示 */}
        {!selectedHomework && !historyLoading && (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
            <div className="text-5xl mb-4">📊</div>
            <p className="text-slate-500">请选择一个作业查看分析</p>
            <p className="text-sm text-slate-400 mt-2">点击上方的作业圆点查看该作业的题目得分率和常错知识点</p>
          </div>
        )}

        {/* 加载中 */}
        {(loading || historyLoading) && (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* 选中作业的分析 */}
        {selectedHomework && !loading && studentResults.length > 0 && (
          <>
            {/* 基本统计卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">学生人数</p>
                <p className="text-2xl font-bold text-slate-800">{classStats?.total_students || 0}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">平均分</p>
                <p className="text-2xl font-bold text-blue-600">{classStats?.average_score?.toFixed(1) || '-'}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">最高分</p>
                <p className="text-2xl font-bold text-emerald-600">{classStats?.max_score || '-'}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">最低分</p>
                <p className="text-2xl font-bold text-amber-600">{classStats?.min_score || '-'}</p>
              </div>
            </div>

            {/* 每题得分率 */}
            {questionStats.length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">题目得分率分析</h2>
                    <p className="text-xs text-slate-400">每道题的全班总得分率，红色表示得分率低于60%需重点讲解</p>
                  </div>
                </div>
                
                {/* 得分率柱状图 */}
                <div className="h-64 mb-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={questionStats.map(q => ({
                      name: `Q${q.questionNumber}`,
                      rate: Math.round(q.scoreRate * 100),
                      fullRate: q.scoreRate,
                    }))}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                      <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} unit="%" />
                      <Tooltip 
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        formatter={(value: number) => [`${value}%`, '得分率']}
                      />
                      <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                        {questionStats.map((q, index) => (
                          <Cell key={`cell-${index}`} fill={getScoreBarColor(q.scoreRate)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* 题目详情列表 */}
                <div className="space-y-3">
                  {questionStats.map((q) => (
                    <div key={q.questionId} className="flex items-center gap-4 p-3 rounded-lg bg-slate-50">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold ${getScoreColor(q.scoreRate)}`}>
                        Q{q.questionNumber}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-800">第 {q.questionNumber} 题</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            q.scoreRate >= 0.8 ? 'bg-emerald-100 text-emerald-700' :
                            q.scoreRate >= 0.6 ? 'bg-amber-100 text-amber-700' :
                            'bg-rose-100 text-rose-700'
                          }`}>
                            {q.scoreRate >= 0.8 ? '掌握良好' : q.scoreRate >= 0.6 ? '需巩固' : '重点讲解'}
                          </span>
                        </div>
                        <div className="mt-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${getScoreColor(q.scoreRate)}`}
                            style={{ width: `${q.scoreRate * 100}%` }}
                          />
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-slate-800">{Math.round(q.scoreRate * 100)}%</p>
                        <p className="text-xs text-slate-400">{q.totalScore}/{q.maxPossibleScore}分</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI 常错知识点总结 */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">常错知识点分析</h2>
                  <p className="text-xs text-slate-400">基于全班错题反馈，AI 总结本次作业的常见错误类型</p>
                </div>
                <button
                  onClick={summarizeCommonMistakes}
                  disabled={summarizing || allWrongFeedbacks.length === 0}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    summarizing || allWrongFeedbacks.length === 0
                      ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700 cursor-pointer'
                  }`}
                >
                  {summarizing ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      分析中...
                    </span>
                  ) : commonMistakes ? '重新分析' : '生成 AI 分析'}
                </button>
              </div>
              
              {allWrongFeedbacks.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <p>🎉 本次作业没有错题反馈数据</p>
                  <p className="text-sm mt-1">全班表现优秀！</p>
                </div>
              ) : commonMistakes ? (
                <div className="bg-slate-50 rounded-lg p-4">
                  <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed">
                    {commonMistakes}
                  </pre>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-400">
                  <p>共收集到 {allWrongFeedbacks.length} 条错题反馈</p>
                  <p className="text-sm mt-1">点击"生成 AI 分析"按钮，让 AI 总结常错知识点</p>
                </div>
              )}
            </div>
          </>
        )}

        {/* 选中作业但无数据 */}
        {selectedHomework && !loading && studentResults.length === 0 && (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
            <div className="text-5xl mb-4">📊</div>
            <p className="text-slate-500">该作业暂无批改数据</p>
            <p className="text-sm text-slate-400 mt-2">完成批改后，数据将显示在这里</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
