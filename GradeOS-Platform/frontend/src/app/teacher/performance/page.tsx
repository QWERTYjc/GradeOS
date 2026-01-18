'use client';

import React, { useMemo, useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const classes = [
  { id: 'c-001', name: '高二物理 A 班' },
  { id: 'c-002', name: '高二数学 B 班' },
];

const knowledgeCoverage = [
  { name: '力学', coverage: 0.86, mastery: 0.78 },
  { name: '电学', coverage: 0.74, mastery: 0.69 },
  { name: '热学', coverage: 0.61, mastery: 0.63 },
  { name: '波动', coverage: 0.58, mastery: 0.55 },
  { name: '光学', coverage: 0.72, mastery: 0.7 },
];

const questionBreakdown = [
  { id: 'Q1', title: '牛顿第二定律辨析', accuracy: 0.92, avgScore: 4.6, fullScore: 5, tag: '核心' },
  { id: 'Q2', title: '受力分析综合题', accuracy: 0.64, avgScore: 6.4, fullScore: 10, tag: '薄弱' },
  { id: 'Q3', title: '动量守恒应用', accuracy: 0.71, avgScore: 7.1, fullScore: 10, tag: '待巩固' },
  { id: 'Q4', title: '电路综合计算', accuracy: 0.58, avgScore: 5.8, fullScore: 10, tag: '高风险' },
  { id: 'Q5', title: '功与能推导', accuracy: 0.81, avgScore: 8.1, fullScore: 10, tag: '良好' },
];

const heatmap = [
  ['函数建模', 0.9],
  ['受力建模', 0.72],
  ['图像分析', 0.66],
  ['公式推导', 0.58],
  ['实验设计', 0.62],
  ['应用迁移', 0.54],
  ['逻辑推理', 0.76],
  ['运算精准', 0.68],
];

const progressTrend = [
  { date: '09-01', classScore: 78, warning: false },
  { date: '09-08', classScore: 80, warning: false },
  { date: '09-15', classScore: 81, warning: false },
  { date: '09-22', classScore: 76, warning: true },
  { date: '09-29', classScore: 79, warning: false },
  { date: '10-06', classScore: 82, warning: false },
  { date: '10-13', classScore: 77, warning: true },
];

const alerts = [
  {
    id: 'alert-1',
    type: '退步预警',
    detail: '受力分析模块正确率连续两周低于 60%，建议专项讲评。',
  },
  {
    id: 'alert-2',
    type: '进步异常',
    detail: '电路计算小题平均分提升 18%，可安排拔高挑战题。',
  },
  {
    id: 'alert-3',
    type: '波动性提示',
    detail: '班级曲线波动显著，建议分层作业强化基础。',
  },
];

const heatColor = (value: number) => {
  if (value >= 0.8) return 'bg-emerald-500/80';
  if (value >= 0.7) return 'bg-lime-400/80';
  if (value >= 0.6) return 'bg-amber-400/80';
  return 'bg-rose-500/80';
};

export default function TeacherPerformancePage() {
  const [selectedClassId, setSelectedClassId] = useState(classes[0].id);
  const selectedClass = useMemo(
    () => classes.find((item) => item.id === selectedClassId) || classes[0],
    [selectedClassId]
  );

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Teaching Cockpit</p>
            <h1 className="text-2xl font-semibold text-slate-900">教师端成绩看板</h1>
            <p className="text-sm text-slate-500">全维度学情画像，驱动精准讲评与教学决策。</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {classes.map((cls) => (
              <button
                key={cls.id}
                onClick={() => setSelectedClassId(cls.id)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                  selectedClassId === cls.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cls.name}
              </button>
            ))}
            <span className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white">本周数据</span>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">班级平均分</p>
            <p className="mt-3 text-3xl font-semibold text-slate-900">81.6</p>
            <p className="mt-2 text-xs text-emerald-500">较上次 +2.1</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">知识点覆盖率</p>
            <p className="mt-3 text-3xl font-semibold text-blue-600">73%</p>
            <p className="mt-2 text-xs text-slate-500">覆盖 18 个核心知识点</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">异常预警</p>
            <p className="mt-3 text-3xl font-semibold text-rose-500">3</p>
            <p className="mt-2 text-xs text-slate-500">进步/退步曲线已标记</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-5 text-white">
            <p className="text-xs uppercase tracking-[0.3em] text-white/40">薄弱环节定位</p>
            <p className="mt-3 text-3xl font-semibold">精准度 ×3</p>
            <p className="mt-2 text-xs text-white/50">依据课堂试点效果估算</p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">学情进步曲线</h2>
                <p className="text-xs text-slate-400">自动抓取异常波动并生成退步预警</p>
              </div>
              <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-500">2 次异常</span>
            </div>
            <div className="mt-6 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={progressTrend}>
                  <defs>
                    <linearGradient id="colorClassScore" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563EB" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis hide domain={[65, 90]} />
                  <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.12)' }} />
                  <Area type="monotone" dataKey="classScore" stroke="#2563EB" strokeWidth={3} fill="url(#colorClassScore)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              {progressTrend
                .filter((item) => item.warning)
                .map((item) => (
                  <span key={item.date} className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs text-rose-500">
                    {item.date} 波动
                  </span>
                ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-slate-900">学情热力图</h2>
              <p className="text-xs text-slate-400">覆盖率 × 得分率综合指数</p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {heatmap.map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-slate-200 p-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{label}</span>
                      <span>{Math.round((value as number) * 100)}%</span>
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-slate-100">
                      <div
                        className={`h-2 rounded-full ${heatColor(value as number)}`}
                        style={{ width: `${Math.round((value as number) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-slate-900">异常事件速览</h2>
              <div className="mt-4 space-y-3">
                {alerts.map((alert) => (
                  <div key={alert.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="text-xs font-semibold text-rose-500">{alert.type}</div>
                    <p className="mt-2 text-sm text-slate-600">{alert.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">小题得分率拆解</h2>
              <span className="text-xs text-slate-400">{selectedClass.name}</span>
            </div>
            <div className="mt-4 space-y-4">
              {questionBreakdown.map((item) => (
                <div key={item.id} className="rounded-xl border border-slate-200 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{item.id} · {item.title}</p>
                      <p className="text-xs text-slate-400">{item.tag}</p>
                    </div>
                    <div className="text-sm text-slate-500">
                      {item.avgScore}/{item.fullScore}
                    </div>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-slate-100">
                    <div
                      className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400"
                      style={{ width: `${Math.round(item.accuracy * 100)}%` }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-slate-500">得分率 {Math.round(item.accuracy * 100)}%</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900">知识点覆盖与掌握度</h2>
            <p className="text-xs text-slate-400">覆盖率决定讲评优先级，掌握度决定复习深度</p>
            <div className="mt-5 space-y-4">
              {knowledgeCoverage.map((item) => (
                <div key={item.name} className="rounded-xl border border-slate-200 px-4 py-3">
                  <div className="flex items-center justify-between text-sm text-slate-700">
                    <span>{item.name}</span>
                    <span>覆盖 {Math.round(item.coverage * 100)}%</span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-slate-100">
                    <div
                      className="h-2 rounded-full bg-emerald-500"
                      style={{ width: `${Math.round(item.coverage * 100)}%` }}
                    />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                    <span>掌握度 {Math.round(item.mastery * 100)}%</span>
                    <span>建议：{item.mastery > 0.7 ? '精炼讲评' : '重点强化'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
