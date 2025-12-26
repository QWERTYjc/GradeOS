'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar
} from 'recharts';

interface DiagnosisReport {
  student_id: string;
  report_period: string;
  overall_assessment: {
    mastery_score: number;
    improvement_rate: number;
    consistency_score: number;
  };
  progress_trend: Array<{ date: string; score: number; average: number }>;
  knowledge_map: Array<{
    knowledge_area: string;
    mastery_level: number;
    weak_points: string[];
    strengths: string[];
  }>;
  error_patterns: {
    most_common_error_types: Array<{ type: string; count: number; percentage: number }>;
  };
  personalized_insights: string[];
}

export default function StudentReportPage() {
  const [report, setReport] = useState<DiagnosisReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 模拟加载报告数据
    setTimeout(() => {
      setReport({
        student_id: 'S20240101',
        report_period: '2024年12月',
        overall_assessment: {
          mastery_score: 0.785,
          improvement_rate: 0.045,
          consistency_score: 82
        },
        progress_trend: [
          { date: '12-01', score: 72, average: 70 },
          { date: '12-05', score: 74, average: 71 },
          { date: '12-10', score: 75, average: 71 },
          { date: '12-15', score: 78, average: 72 },
          { date: '12-20', score: 79, average: 73 },
          { date: '12-25', score: 82, average: 74 }
        ],
        knowledge_map: [
          { knowledge_area: '二次函数', mastery_level: 0.75, weak_points: ['顶点式', '平移'], strengths: ['图像绘制'] },
          { knowledge_area: '不等式', mastery_level: 0.82, weak_points: ['边界条件'], strengths: ['基本运算', '解集表示'] },
          { knowledge_area: '解析几何', mastery_level: 0.68, weak_points: ['圆与直线', '切线'], strengths: ['直线方程'] },
          { knowledge_area: '三角函数', mastery_level: 0.78, weak_points: ['诱导公式'], strengths: ['基本定义', '图像'] },
          { knowledge_area: '数列', mastery_level: 0.72, weak_points: ['递推公式'], strengths: ['等差等比'] }
        ],
        error_patterns: {
          most_common_error_types: [
            { type: '概念错误', count: 8, percentage: 40 },
            { type: '计算错误', count: 5, percentage: 25 },
            { type: '审题错误', count: 4, percentage: 20 },
            { type: '理解偏差', count: 3, percentage: 15 }
          ]
        },
        personalized_insights: [
          '你在代数运算方面表现稳定，近期正确率提升明显，建议继续保持当前学习节奏',
          '几何直觉需要加强，特别是圆与直线的位置关系判断，建议多做图形变换练习',
          '审题时注意关键条件的提取，近期有 4 次因遗漏条件导致的失分',
          '建议每周安排 2-3 次专项训练，重点攻克二次函数顶点式相关题型'
        ]
      });
      setLoading(false);
    }, 1500);
  }, []);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center h-96 gap-4">
          <div className="w-12 h-12 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-500 font-medium">深度聚合多维学习数据，正在校准成长曲线...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (!report) {
    return (
      <DashboardLayout>
        <div className="bg-white rounded-2xl p-12 text-center">
          <p className="text-slate-500">无法加载报告数据</p>
        </div>
      </DashboardLayout>
    );
  }

  const radarData = report.knowledge_map.map(km => ({
    subject: km.knowledge_area,
    score: km.mastery_level * 100
  }));

  const errorPatternData = report.error_patterns.most_common_error_types.map(ep => ({
    name: ep.type,
    count: ep.count
  }));

  return (
    <DashboardLayout>
      <div className="space-y-8 max-w-6xl mx-auto">
        {/* 页面标题 */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">📈 阶段性成长评估报告</h1>
            <p className="text-slate-500 text-sm mt-1">数据周期：{report.report_period}</p>
          </div>
          <div className="bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium">
            ID: {report.student_id}
          </div>
        </div>

        {/* KPI 卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">综合掌握度</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-slate-800">{(report.overall_assessment.mastery_score * 100).toFixed(1)}</span>
              <span className="text-slate-400 text-sm">%</span>
            </div>
            <p className="text-xs text-green-500 mt-2">↑ 较上月 +1.2%</p>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">学习进步率</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-green-500">+{(report.overall_assessment.improvement_rate * 100).toFixed(1)}</span>
              <span className="text-slate-400 text-sm">%</span>
            </div>
            <p className="text-xs text-green-500 mt-2">稳步增长中</p>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">专注稳定性</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-blue-600">{report.overall_assessment.consistency_score}</span>
              <span className="text-slate-400 text-sm">/100</span>
            </div>
            <p className="text-xs text-blue-500 mt-2">状态评级：良</p>
          </div>
          <div className="bg-slate-900 rounded-2xl p-6 text-white">
            <p className="text-xs font-bold text-white/40 uppercase tracking-wider mb-2">分析题目数</p>
            <span className="text-3xl font-bold">42</span>
            <p className="text-xs text-white/40 mt-2">本月累计</p>
          </div>
        </div>

        {/* 学习轨迹图 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-bold text-slate-800">📊 学习轨迹与班级基准</h3>
              <p className="text-xs text-slate-400 mt-1">展示你的表现与班级平均水平的对比趋势</p>
            </div>
            <div className="flex gap-4 text-xs text-slate-500">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-blue-600 rounded-full" />
                个人得分
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-slate-300 rounded-full" />
                班级平均
              </div>
            </div>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={report.progress_trend}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis hide domain={[60, 100]} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                <Area type="monotone" dataKey="average" stroke="#e2e8f0" fill="transparent" strokeWidth={2} strokeDasharray="5 5" />
                <Area type="monotone" dataKey="score" stroke="#2563EB" strokeWidth={3} fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 能力雷达 & 错因分布 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h3 className="font-bold text-slate-800 mb-2">🎯 多维能力雷达</h3>
            <p className="text-xs text-slate-400 mb-6">反映你在不同知识板块的分布平衡度</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#F1F5F9" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 11 }} />
                  <Radar name="掌握度" dataKey="score" stroke="#2563EB" fill="#2563EB" fillOpacity={0.2} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h3 className="font-bold text-slate-800 mb-2">🔍 错因分布透视</h3>
            <p className="text-xs text-slate-400 mb-6">统计你在学习中频繁出现的错误行为类型</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={errorPatternData} layout="vertical" margin={{ left: 20 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={80} tick={{ fill: '#475569', fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none' }} />
                  <Bar dataKey="count" fill="#3B82F6" radius={[0, 8, 8, 0]} barSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* AI 洞察 */}
        <div className="bg-slate-900 rounded-2xl p-8 text-white">
          <div className="flex items-center gap-4 mb-8">
            <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center text-sm font-bold">AI</div>
            <div>
              <h3 className="text-xl font-bold">专家级教育洞察</h3>
              <p className="text-white/40 text-xs mt-1">由深度认知引擎生成</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {report.personalized_insights.map((insight, idx) => (
              <div key={idx} className="flex gap-4 p-5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
                <span className="text-blue-400 font-bold text-lg">0{idx + 1}</span>
                <p className="text-white/80 text-sm leading-relaxed">{insight}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
