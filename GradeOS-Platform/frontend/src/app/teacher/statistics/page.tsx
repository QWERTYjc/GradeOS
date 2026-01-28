'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, statisticsApi, homeworkApi, ClassResponse, HomeworkResponse } from '@/services/api';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';

interface ClassStats {
  class_id: string;
  class_name: string;
  total_students: number;
  submitted_count: number;
  graded_count: number;
  average_score: number;
  max_score: number;
  min_score: number;
  pass_rate: number;
  score_distribution: Record<string, number>;
}

const DISTRIBUTION_COLORS = ['#22c55e', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444'];

export default function TeacherStatisticsPage() {
  const [stats, setStats] = useState<ClassStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [homeworks, setHomeworks] = useState<HomeworkResponse[]>([]);
  const [selectedHomework, setSelectedHomework] = useState<string>('');
  const { user } = useAuthStore();

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
      .catch((error) => {
        console.error('加载班级失败', error);
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
        setSelectedHomework(''); // 默认显示全部
      })
      .catch((error) => {
        console.error('加载作业失败', error);
        setHomeworks([]);
      });
    return () => { active = false; };
  }, [selectedClass]);

  // 加载统计数据
  useEffect(() => {
    if (!selectedClass) return;
    let active = true;
    setLoading(true);
    statisticsApi.getClassStatistics(selectedClass, selectedHomework || undefined)
      .then((data) => {
        if (!active) return;
        const className = classes.find((c) => c.class_id === selectedClass)?.class_name || '';
        setStats({ ...data, class_name: className });
      })
      .catch((error) => {
        console.error('加载统计数据失败', error);
        setStats(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [selectedClass, selectedHomework, classes]);

  const distributionData = stats ? Object.entries(stats.score_distribution).map(([range, count], index) => ({
    range,
    count,
    fill: DISTRIBUTION_COLORS[index % DISTRIBUTION_COLORS.length]
  })) : [];

  const pieData = stats ? [
    { name: '已提交', value: stats.submitted_count },
    { name: '未提交', value: Math.max(0, stats.total_students - stats.submitted_count) }
  ] : [];

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* 页面标题 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">数据统计</h1>
            <p className="text-slate-500 text-sm mt-1">查看班级成绩分布与学习情况</p>
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

        {/* 作业筛选 */}
        {homeworks.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm text-slate-600 font-medium">筛选作业:</span>
              <button
                onClick={() => setSelectedHomework('')}
                className={`px-3 py-1.5 rounded-lg text-sm transition-all cursor-pointer ${
                  !selectedHomework
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                全部作业
              </button>
              {homeworks.map(hw => (
                <button
                  key={hw.homework_id}
                  onClick={() => setSelectedHomework(hw.homework_id)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-all cursor-pointer ${
                    selectedHomework === hw.homework_id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {hw.title}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : stats ? (
          <>
            {/* KPI 卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">班级人数</p>
                <p className="text-2xl font-bold text-slate-800">{stats.total_students}</p>
                <p className="text-xs text-slate-400 mt-1">已提交 {stats.submitted_count} 人</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">平均分</p>
                <p className="text-2xl font-bold text-blue-600">{stats.average_score.toFixed(1)}</p>
                <p className="text-xs text-slate-400 mt-1">基于 {stats.graded_count} 份批改</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">及格率</p>
                <p className="text-2xl font-bold text-green-500">{(stats.pass_rate * 100).toFixed(1)}%</p>
                <p className="text-xs text-slate-400 mt-1">60分以上</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">最高/最低</p>
                <p className="text-2xl font-bold text-slate-800">{stats.max_score}/{stats.min_score}</p>
                <p className="text-xs text-slate-400 mt-1">分数区间</p>
              </div>
            </div>

            {/* 图表区域 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 成绩分布 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-bold text-slate-800 mb-6">成绩分布</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={distributionData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} allowDecimals={false} />
                      <Tooltip 
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        formatter={(value: number) => [`${value} 人`, '人数']}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {distributionData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* 提交情况 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-bold text-slate-800 mb-6">提交情况</h3>
                <div className="h-64 flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={70}
                        paddingAngle={5}
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        <Cell fill="#22c55e" />
                        <Cell fill="#e2e8f0" />
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="text-center mt-2">
                  <p className="text-sm text-slate-500">
                    提交率: <span className="font-bold text-green-500">
                      {stats.total_students > 0 ? ((stats.submitted_count / stats.total_students) * 100).toFixed(1) : 0}%
                    </span>
                  </p>
                </div>
              </div>
            </div>

            {/* 批改进度 */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-bold text-slate-800 mb-4">批改进度</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
                    <span className="text-xl font-bold text-blue-600">{stats.submitted_count}</span>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">已提交</p>
                    <p className="text-lg font-semibold text-slate-800">份作业</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
                    <span className="text-xl font-bold text-green-600">{stats.graded_count}</span>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">已批改</p>
                    <p className="text-lg font-semibold text-slate-800">份作业</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center">
                    <span className="text-xl font-bold text-amber-600">{Math.max(0, stats.submitted_count - stats.graded_count)}</span>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">待批改</p>
                    <p className="text-lg font-semibold text-slate-800">份作业</p>
                  </div>
                </div>
              </div>
              {/* 进度条 */}
              <div className="mt-6">
                <div className="flex justify-between text-sm text-slate-500 mb-2">
                  <span>批改进度</span>
                  <span>{stats.submitted_count > 0 ? ((stats.graded_count / stats.submitted_count) * 100).toFixed(1) : 0}%</span>
                </div>
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-500"
                    style={{ width: `${stats.submitted_count > 0 ? (stats.graded_count / stats.submitted_count) * 100 : 0}%` }}
                  />
                </div>
              </div>
            </div>

            {/* 分数段详情 */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-bold text-slate-800 mb-4">分数段详情</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {Object.entries(stats.score_distribution).map(([range, count], index) => (
                  <div key={range} className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center">
                    <div className="text-2xl font-bold" style={{ color: DISTRIBUTION_COLORS[index % DISTRIBUTION_COLORS.length] }}>
                      {count}
                    </div>
                    <div className="text-sm text-slate-600 mt-1">{range} 分</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {stats.graded_count > 0 ? ((count / stats.graded_count) * 100).toFixed(1) : 0}%
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI 建议 */}
            <div className="bg-slate-900 rounded-xl p-6 text-white">
              <h3 className="font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm">AI</span>
                教学建议
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {stats.pass_rate < 0.6 && (
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <p className="text-white/80 text-sm">⚠️ 及格率较低，建议针对薄弱知识点进行专项复习</p>
                  </div>
                )}
                {stats.max_score - stats.min_score > 40 && (
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <p className="text-white/80 text-sm">📊 分数差距较大，建议关注后进生的学习情况</p>
                  </div>
                )}
                {stats.submitted_count < stats.total_students && (
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <p className="text-white/80 text-sm">📝 有 {stats.total_students - stats.submitted_count} 名学生未提交，请及时提醒</p>
                  </div>
                )}
                {stats.graded_count < stats.submitted_count && (
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <p className="text-white/80 text-sm">✏️ 还有 {stats.submitted_count - stats.graded_count} 份作业待批改</p>
                  </div>
                )}
                {stats.pass_rate >= 0.8 && (
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <p className="text-white/80 text-sm">🎉 班级整体表现优秀，及格率达到 {(stats.pass_rate * 100).toFixed(1)}%</p>
                  </div>
                )}
                {stats.average_score >= 80 && (
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <p className="text-white/80 text-sm">⭐ 平均分 {stats.average_score.toFixed(1)} 分，可以适当提高难度</p>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
            <div className="text-5xl mb-4">📊</div>
            <p className="text-slate-500">暂无统计数据</p>
            <p className="text-sm text-slate-400 mt-2">请先布置作业并等待学生提交</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
