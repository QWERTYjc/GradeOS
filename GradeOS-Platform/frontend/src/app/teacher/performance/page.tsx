'use client';

import { useEffect, useState, useMemo } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, homeworkApi, gradingApi, ClassResponse, HomeworkResponse, GradingImportRecord } from '@/services/api';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  Cell,
} from 'recharts';

// ============ 类型定义 ============
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
  }>;
}

// 使用 API 中的 GradingImportRecord 类型
type GradingRecord = GradingImportRecord;

interface TrendDataPoint {
  name: string;
  date: string;
  average: number;
  max: number;
  min: number;
  studentCount: number;
  assignmentId?: string;
}

interface StudentProgress {
  student_id: string;
  student_name: string;
  scores: Array<{ assignmentId: string; score: number; maxScore: number; date: string }>;
  trend: 'improving' | 'stable' | 'regressing';
  improvementRate: number;
  latestScore: number;
  averageScore: number;
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

// ============ 工具函数 ============
const getScoreColor = (score: number, maxScore: number = 100): string => {
  const pct = (score / maxScore) * 100;
  if (pct >= 80) return 'bg-emerald-500';
  if (pct >= 60) return 'bg-amber-500';
  return 'bg-rose-500';
};

const getTrendIcon = (trend: 'improving' | 'stable' | 'regressing'): string => {
  switch (trend) {
    case 'improving': return '↑';
    case 'regressing': return '↓';
    default: return '→';
  }
};

const getTrendColor = (trend: 'improving' | 'stable' | 'regressing'): string => {
  switch (trend) {
    case 'improving': return 'text-emerald-600';
    case 'regressing': return 'text-rose-600';
    default: return 'text-slate-600';
  }
};

// ============ 小圆片选择器组件 ============
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
    ? getScoreColor(averageScore)
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
  const [allStudentResults, setAllStudentResults] = useState<Map<string, StudentResult[]>>(new Map());
  
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
        setSelectedHomework('');
      })
      .catch((err) => {
        console.error('加载作业失败', err);
        setHomeworks([]);
      });
    return () => { active = false; };
  }, [selectedClass]);

  // 加载批改历史并获取每个批次的统计数据
  useEffect(() => {
    if (!selectedClass) return;
    let active = true;
    setHistoryLoading(true);
    
    gradingApi.getGradingHistory({ class_id: selectedClass })
      .then(async (data) => {
        if (!active) return;
        const records = data.records || [];
        
        // 为每个批次加载详细统计数据
        const recordsWithStats: GradingRecord[] = await Promise.all(
          records.map(async (record) => {
            if (record.status === 'revoked' || !record.batch_id) {
              return record;
            }
            try {
              const results = await gradingApi.getResultsReviewContext(record.batch_id);
              const studentResults = results.student_results || [];
              
              // 保存学生结果用于后续分析
              if (studentResults.length > 0) {
                setAllStudentResults(prev => {
                  const newMap = new Map(prev);
                  newMap.set(record.batch_id, studentResults);
                  return newMap;
                });
              }
              
              // 计算统计数据
              const scores = studentResults
                .map((s: StudentResult) => s.total_score ?? 0)
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
      return;
    }
    
    const latestRecord = gradingHistory.find(r => 
      r.assignment_id === selectedHomework && r.status !== 'revoked'
    );
    
    if (!latestRecord?.batch_id) {
      setStudentResults([]);
      return;
    }
    
    // 优先使用缓存的结果
    const cached = allStudentResults.get(latestRecord.batch_id);
    if (cached) {
      setStudentResults(cached);
      return;
    }
    
    let active = true;
    setLoading(true);
    setError(null);
    
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
  }, [selectedHomework, gradingHistory, allStudentResults]);

  // 获取作业对应的批改记录
  const getHomeworkGradingRecord = (homeworkId: string): GradingRecord | undefined => {
    return gradingHistory.find(r => 
      r.assignment_id === homeworkId && r.status !== 'revoked'
    );
  };

  // 跨批次趋势数据（使用真实统计数据）
  const trendData = useMemo<TrendDataPoint[]>(() => {
    if (gradingHistory.length === 0) return [];
    
    const sorted = [...gradingHistory]
      .filter(r => r.status !== 'revoked' && r.statistics)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    
    return sorted.slice(-10).map((record) => ({
      name: record.assignment_title || '未命名',
      date: new Date(record.created_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }),
      average: record.statistics?.average_score ?? 0,
      max: record.statistics?.max_score ?? 0,
      min: record.statistics?.min_score ?? 0,
      studentCount: record.student_count,
      assignmentId: record.assignment_id,
    }));
  }, [gradingHistory]);

  // 计算进步/退步趋势
  const progressAnalysis = useMemo(() => {
    if (trendData.length < 2) return null;
    
    const recent = trendData.slice(-3);
    const earlier = trendData.slice(0, Math.min(3, trendData.length - 3));
    
    if (earlier.length === 0) return null;
    
    const recentAvg = recent.reduce((sum, d) => sum + d.average, 0) / recent.length;
    const earlierAvg = earlier.reduce((sum, d) => sum + d.average, 0) / earlier.length;
    const change = recentAvg - earlierAvg;
    
    return {
      trend: change > 2 ? 'up' as const : change < -2 ? 'down' as const : 'stable' as const,
      change: Math.abs(change).toFixed(1),
      recentAvg: recentAvg.toFixed(1),
      earlierAvg: earlierAvg.toFixed(1),
    };
  }, [trendData]);

  // 学生进步追踪
  const studentProgressData = useMemo<StudentProgress[]>(() => {
    if (allStudentResults.size === 0) return [];
    
    const studentMap = new Map<string, StudentProgress>();
    
    // 按时间顺序处理每个批次
    const sortedRecords = [...gradingHistory]
      .filter(r => r.status !== 'revoked' && allStudentResults.has(r.batch_id))
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    
    sortedRecords.forEach(record => {
      const results = allStudentResults.get(record.batch_id) || [];
      results.forEach((result: StudentResult) => {
        const studentId = result.student_id || 'unknown';
        const studentName = result.student_name || '未知学生';
        
        if (!studentMap.has(studentId)) {
          studentMap.set(studentId, {
            student_id: studentId,
            student_name: studentName,
            scores: [],
            trend: 'stable',
            improvementRate: 0,
            latestScore: 0,
            averageScore: 0,
          });
        }
        
        const student = studentMap.get(studentId)!;
        student.scores.push({
          assignmentId: record.assignment_id || record.batch_id,
          score: result.total_score ?? 0,
          maxScore: result.max_score ?? 100,
          date: record.created_at,
        });
      });
    });
    
    // 计算每个学生的趋势
    studentMap.forEach((student) => {
      if (student.scores.length >= 2) {
        const half = Math.floor(student.scores.length / 2);
        const firstHalf = student.scores.slice(0, half);
        const secondHalf = student.scores.slice(half);
        
        const firstAvg = firstHalf.reduce((sum, s) => sum + (s.score / s.maxScore * 100), 0) / firstHalf.length;
        const secondAvg = secondHalf.reduce((sum, s) => sum + (s.score / s.maxScore * 100), 0) / secondHalf.length;
        
        student.improvementRate = secondAvg - firstAvg;
        student.trend = student.improvementRate > 5 ? 'improving' : 
                       student.improvementRate < -5 ? 'regressing' : 'stable';
      }
      
      student.latestScore = student.scores.length > 0 
        ? (student.scores[student.scores.length - 1].score / student.scores[student.scores.length - 1].maxScore * 100)
        : 0;
      student.averageScore = student.scores.length > 0
        ? student.scores.reduce((sum, s) => sum + (s.score / s.maxScore * 100), 0) / student.scores.length
        : 0;
    });
    
    return Array.from(studentMap.values()).sort((a, b) => b.averageScore - a.averageScore);
  }, [allStudentResults, gradingHistory]);

  // 需要关注的学生（持续低分或显著退步）
  const alertStudents = useMemo(() => {
    const classAvg = studentProgressData.length > 0
      ? studentProgressData.reduce((sum, s) => sum + s.averageScore, 0) / studentProgressData.length
      : 0;
    
    return {
      underperforming: studentProgressData.filter(s => s.averageScore < classAvg * 0.7),
      regressing: studentProgressData.filter(s => s.trend === 'regressing' && s.improvementRate < -10),
      improving: studentProgressData.filter(s => s.trend === 'improving' && s.improvementRate > 10),
    };
  }, [studentProgressData]);

  // 计算班级报告（选中作业时）
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
    
    const distribution: Record<string, number> = {
      '0-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0,
    };
    
    scores.forEach(score => {
      const pct = (score / (studentResults[0]?.max_score || 100)) * 100;
      if (pct < 60) distribution['0-59']++;
      else if (pct < 70) distribution['60-69']++;
      else if (pct < 80) distribution['70-79']++;
      else if (pct < 90) distribution['80-89']++;
      else distribution['90-100']++;
    });
    
    return {
      total_students: studentResults.length,
      average_score: Math.round(avg * 10) / 10,
      max_score: max,
      min_score: min,
      score_distribution: distribution,
    };
  }, [studentResults]);

  const sortedStudents = useMemo(() => {
    return [...studentResults].sort((a, b) => (b.total_score ?? 0) - (a.total_score ?? 0));
  }, [studentResults]);

  // ============ 渲染 ============
  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Teaching Cockpit</p>
            <h1 className="text-2xl font-semibold text-slate-900">教师端成绩看板</h1>
            <p className="text-sm text-slate-500">全维度学情画像，驱动精准讲评与教学决策。</p>
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

        {/* 作业小圆片选择器 */}
        {homeworks.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm text-slate-600 font-medium">选择作业:</span>
              <button
                onClick={() => setSelectedHomework('')}
                className={`px-3 py-1.5 rounded-lg text-sm transition-all cursor-pointer ${
                  !selectedHomework
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                全部概览
              </button>
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

        {/* 全部作业视图 - 跨批次趋势分析 */}
        {!selectedHomework && (
          <>
            {/* 趋势概览卡片 */}
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">批改次数</p>
                <p className="mt-3 text-3xl font-semibold text-slate-900">
                  {gradingHistory.filter(r => r.status !== 'revoked').length}
                </p>
                <p className="mt-2 text-xs text-slate-500">累计批改记录</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">总批改人次</p>
                <p className="mt-3 text-3xl font-semibold text-blue-600">
                  {gradingHistory.filter(r => r.status !== 'revoked').reduce((sum, r) => sum + r.student_count, 0)}
                </p>
                <p className="mt-2 text-xs text-slate-500">学生作业批改总数</p>
              </div>
              {progressAnalysis && (
                <>
                  <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-400">成绩趋势</p>
                    <p className={`mt-3 text-3xl font-semibold ${
                      progressAnalysis.trend === 'up' ? 'text-emerald-600' :
                      progressAnalysis.trend === 'down' ? 'text-rose-600' : 'text-slate-600'
                    }`}>
                      {progressAnalysis.trend === 'up' ? '↑' : progressAnalysis.trend === 'down' ? '↓' : '→'}
                      {progressAnalysis.change}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      {progressAnalysis.trend === 'up' ? '整体进步' : 
                       progressAnalysis.trend === 'down' ? '需关注' : '保持稳定'}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-900 p-5 text-white">
                    <p className="text-xs uppercase tracking-[0.3em] text-white/40">近期平均</p>
                    <p className="mt-3 text-3xl font-semibold">{progressAnalysis.recentAvg}</p>
                    <p className="mt-2 text-xs text-white/50">vs 早期 {progressAnalysis.earlierAvg}</p>
                  </div>
                </>
              )}
            </div>

            {/* 成绩趋势图 */}
            {historyLoading ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 flex items-center justify-center h-80">
                <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : trendData.length > 0 ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">成绩趋势分析</h2>
                    <p className="text-xs text-slate-400">跨作业平均分变化趋势（真实数据）</p>
                  </div>
                  {progressAnalysis && (
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      progressAnalysis.trend === 'up' ? 'bg-emerald-50 text-emerald-600' :
                      progressAnalysis.trend === 'down' ? 'bg-rose-50 text-rose-600' : 
                      'bg-slate-100 text-slate-600'
                    }`}>
                      {progressAnalysis.trend === 'up' ? '整体进步' : 
                       progressAnalysis.trend === 'down' ? '整体退步' : '保持稳定'}
                    </span>
                  )}
                </div>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                      <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <Tooltip 
                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.12)' }}
                        formatter={(value: number, name: string) => [value.toFixed(1), name]}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="average" name="平均分" stroke="#2563EB" strokeWidth={3} dot={{ fill: '#2563EB', strokeWidth: 2 }} />
                      <Line type="monotone" dataKey="max" name="最高分" stroke="#10B981" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                      <Line type="monotone" dataKey="min" name="最低分" stroke="#F59E0B" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center py-12">
                <p className="text-slate-500">暂无趋势数据</p>
                <p className="text-xs text-slate-400 mt-2">完成作业批改后，趋势图将显示在这里</p>
              </div>
            )}

            {/* 学生进步追踪 */}
            {studentProgressData.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">学生进步追踪</h2>
                
                {/* 预警区域 */}
                {(alertStudents.underperforming.length > 0 || alertStudents.regressing.length > 0) && (
                  <div className="mb-6 grid gap-3 md:grid-cols-2">
                    {alertStudents.underperforming.length > 0 && (
                      <div className="p-4 rounded-xl bg-rose-50 border border-rose-200">
                        <p className="text-sm font-medium text-rose-700 mb-2">⚠️ 持续低分学生 ({alertStudents.underperforming.length}人)</p>
                        <div className="flex flex-wrap gap-2">
                          {alertStudents.underperforming.slice(0, 5).map(s => (
                            <span key={s.student_id} className="px-2 py-1 bg-white rounded text-xs text-rose-600">
                              {s.student_name} ({s.averageScore.toFixed(0)}分)
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {alertStudents.regressing.length > 0 && (
                      <div className="p-4 rounded-xl bg-amber-50 border border-amber-200">
                        <p className="text-sm font-medium text-amber-700 mb-2">📉 显著退步学生 ({alertStudents.regressing.length}人)</p>
                        <div className="flex flex-wrap gap-2">
                          {alertStudents.regressing.slice(0, 5).map(s => (
                            <span key={s.student_id} className="px-2 py-1 bg-white rounded text-xs text-amber-600">
                              {s.student_name} (↓{Math.abs(s.improvementRate).toFixed(0)})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* 进步学生 */}
                {alertStudents.improving.length > 0 && (
                  <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200">
                    <p className="text-sm font-medium text-emerald-700 mb-2">🎉 显著进步学生 ({alertStudents.improving.length}人)</p>
                    <div className="flex flex-wrap gap-2">
                      {alertStudents.improving.slice(0, 8).map(s => (
                        <span key={s.student_id} className="px-2 py-1 bg-white rounded text-xs text-emerald-600">
                          {s.student_name} (↑{s.improvementRate.toFixed(0)})
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 学生列表 */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100">
                        <th className="text-left py-3 px-2 font-medium text-slate-500">学生</th>
                        <th className="text-center py-3 px-2 font-medium text-slate-500">平均分</th>
                        <th className="text-center py-3 px-2 font-medium text-slate-500">最新分</th>
                        <th className="text-center py-3 px-2 font-medium text-slate-500">趋势</th>
                        <th className="text-center py-3 px-2 font-medium text-slate-500">变化</th>
                      </tr>
                    </thead>
                    <tbody>
                      {studentProgressData.slice(0, 15).map((student, idx) => (
                        <tr key={student.student_id} className="border-b border-slate-50 hover:bg-slate-50">
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-2">
                              <span className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-xs text-slate-500">
                                {idx + 1}
                              </span>
                              <span className="font-medium text-slate-800">{student.student_name}</span>
                            </div>
                          </td>
                          <td className="text-center py-3 px-2">
                            <span className={`font-semibold ${student.averageScore >= 60 ? 'text-slate-800' : 'text-rose-600'}`}>
                              {student.averageScore.toFixed(1)}
                            </span>
                          </td>
                          <td className="text-center py-3 px-2 text-slate-600">
                            {student.latestScore.toFixed(1)}
                          </td>
                          <td className="text-center py-3 px-2">
                            <span className={`text-lg ${getTrendColor(student.trend)}`}>
                              {getTrendIcon(student.trend)}
                            </span>
                          </td>
                          <td className="text-center py-3 px-2">
                            <span className={`text-xs font-medium px-2 py-1 rounded ${
                              student.improvementRate > 5 ? 'bg-emerald-100 text-emerald-700' :
                              student.improvementRate < -5 ? 'bg-rose-100 text-rose-700' :
                              'bg-slate-100 text-slate-600'
                            }`}>
                              {student.improvementRate > 0 ? '+' : ''}{student.improvementRate.toFixed(1)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {/* 选中作业视图 - 详细分析 */}
        {selectedHomework && (
          <>
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : studentResults.length > 0 ? (
              <>
                {/* KPI 卡片 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-1">学生人数</p>
                    <p className="text-2xl font-bold text-slate-800">{classReport.total_students}</p>
                  </div>
                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-1">平均分</p>
                    <p className="text-2xl font-bold text-blue-600">{classReport.average_score?.toFixed(1) || '-'}</p>
                  </div>
                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-1">最高分</p>
                    <p className="text-2xl font-bold text-emerald-600">{classReport.max_score || '-'}</p>
                  </div>
                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-1">最低分</p>
                    <p className="text-2xl font-bold text-amber-600">{classReport.min_score || '-'}</p>
                  </div>
                </div>

                {/* 分数分布 */}
                {classReport.score_distribution && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6">
                    <h3 className="font-bold text-slate-800 mb-6">成绩分布</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={Object.entries(classReport.score_distribution).map(([range, count]) => ({ range, count }))}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                          <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} allowDecimals={false} />
                          <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                            {Object.entries(classReport.score_distribution).map(([range], index) => (
                              <Cell key={`cell-${index}`} fill={['#ef4444', '#f59e0b', '#8b5cf6', '#3b82f6', '#22c55e'][index]} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* 学生成绩列表 */}
                <div className="bg-white rounded-xl border border-slate-200 p-6">
                  <h3 className="font-bold text-slate-800 mb-4">学生成绩排名</h3>
                  <div className="space-y-2">
                    {sortedStudents.map((student, idx) => {
                      const pct = student.max_score ? ((student.total_score ?? 0) / student.max_score * 100) : 0;
                      return (
                        <div key={student.student_id || idx} className="flex items-center gap-4 p-3 rounded-lg hover:bg-slate-50">
                          <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                            idx < 3 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
                          }`}>
                            {idx + 1}
                          </span>
                          <div className="flex-1">
                            <p className="font-medium text-slate-800">{student.student_name || '未知学生'}</p>
                            <div className="mt-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div 
                                className={`h-full rounded-full ${getScoreColor(pct)}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-slate-800">{student.total_score ?? 0}</p>
                            <p className="text-xs text-slate-400">/ {student.max_score ?? 100}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
                <div className="text-5xl mb-4">📊</div>
                <p className="text-slate-500">该作业暂无批改数据</p>
                <p className="text-sm text-slate-400 mt-2">完成批改后，数据将显示在这里</p>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
