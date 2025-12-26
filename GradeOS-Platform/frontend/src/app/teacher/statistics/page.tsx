'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
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
  Cell
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

const COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#6b7280'];

export default function TeacherStatisticsPage() {
  const [stats, setStats] = useState<ClassStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedClass, setSelectedClass] = useState('c-001');

  const classes = [
    { id: 'c-001', name: 'Advanced Physics 2024' },
    { id: 'c-002', name: 'Mathematics Grade 11' }
  ];

  useEffect(() => {
    setLoading(true);
    // 模拟加载统计数据
    setTimeout(() => {
      setStats({
        class_id: selectedClass,
        class_name: classes.find(c => c.id === selectedClass)?.name || '',
        total_students: 32,
        submitted_count: 28,
        graded_count: 28,
        average_score: 82.5,
        max_score: 98,
        min_score: 65,
        pass_rate: 0.875,
        score_distribution: {
          '90-100': 8,
          '80-89': 12,
          '70-79': 5,
          '60-69': 3,
          '0-59': 0
        }
      });
      setLoading(false);
    }, 800);
  }, [selectedClass]);

  const distributionData = stats ? Object.entries(stats.score_distribution).map(([range, count]) => ({
    range,
    count
  })) : [];

  const pieData = stats ? [
    { name: '已提交', value: stats.submitted_count },
    { name: '未提交', value: stats.total_students - stats.submitted_count }
  ] : [];

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">📊 班级学情分析</h1>
            <p className="text-slate-500 text-sm mt-1">实时监控班级学习状态与成绩分布</p>
          </div>
          <div className="flex gap-2">
            {classes.map(cls => (
              <button
                key={cls.id}
                onClick={() => setSelectedClass(cls.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  selectedClass === cls.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cls.name}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : stats && (
          <>
            {/* KPI 卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">班级人数</p>
                <p className="text-2xl font-bold text-slate-800">{stats.total_students}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">平均分</p>
                <p className="text-2xl font-bold text-blue-600">{stats.average_score}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">及格率</p>
                <p className="text-2xl font-bold text-green-500">{(stats.pass_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">最高/最低</p>
                <p className="text-2xl font-bold text-slate-800">{stats.max_score}/{stats.min_score}</p>
              </div>
            </div>

            {/* 图表区域 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 成绩分布 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-bold text-slate-800 mb-6">📈 成绩分布</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={distributionData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                      <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                      <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* 提交情况 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-bold text-slate-800 mb-6">📋 提交情况</h3>
                <div className="h-64 flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {pieData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={index === 0 ? '#22c55e' : '#e2e8f0'} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="text-center mt-4">
                  <p className="text-sm text-slate-500">
                    已提交 <span className="font-bold text-green-500">{stats.submitted_count}</span> / {stats.total_students} 人
                  </p>
                </div>
              </div>
            </div>

            {/* 常见错误分析 */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-bold text-slate-800 mb-4">🔍 班级常见错误类型</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-red-50 rounded-xl border border-red-100">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-red-500 font-bold">01</span>
                    <span className="font-medium text-slate-800">概念理解错误</span>
                  </div>
                  <p className="text-sm text-slate-500">占比 35%，主要集中在二次函数顶点式</p>
                </div>
                <div className="p-4 bg-amber-50 rounded-xl border border-amber-100">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-amber-500 font-bold">02</span>
                    <span className="font-medium text-slate-800">计算失误</span>
                  </div>
                  <p className="text-sm text-slate-500">占比 28%，符号运算和分数计算</p>
                </div>
                <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-blue-500 font-bold">03</span>
                    <span className="font-medium text-slate-800">审题不清</span>
                  </div>
                  <p className="text-sm text-slate-500">占比 20%，遗漏关键条件</p>
                </div>
              </div>
            </div>

            {/* 教学建议 */}
            <div className="bg-slate-900 rounded-xl p-6 text-white">
              <h3 className="font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm">AI</span>
                教学优化建议
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <p className="text-white/80 text-sm">建议在下节课重点复习二次函数顶点式的推导过程，强调配方法的应用</p>
                </div>
                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <p className="text-white/80 text-sm">针对计算失误较多的学生，可安排专项计算训练，提高运算准确率</p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
