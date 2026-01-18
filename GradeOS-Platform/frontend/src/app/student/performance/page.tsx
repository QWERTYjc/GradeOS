'use client';

import React, { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';

const commonMistakes = [
  {
    title: '二次函数顶点式易错点',
    summary: '易忽略配方法中常数项符号，导致顶点坐标偏移。',
    tips: ['先写成 a(x-h)^2+k 的完整形式', '检查常数项是否反向平移'],
  },
  {
    title: '电路综合计算陷阱',
    summary: '并联电阻等效公式使用错误，漏算电流分流。',
    tips: ['画电流方向图', '先求等效电阻再代入电压'],
  },
  {
    title: '动量守恒题目条件遗漏',
    summary: '忽略“外力为零”的文字条件，造成错误建模。',
    tips: ['圈出题干中“无外力”关键词', '列式前写出系统边界'],
  },
];

const groupTraps = [
  { name: '审题跳步', value: '共性失分 27%', detail: '题干条件未完整转化为数学表达式。' },
  { name: '公式套用', value: '共性失分 21%', detail: '忽视题型变化，直接套用公式导致偏差。' },
  { name: '计算粗心', value: '共性失分 18%', detail: '符号、单位书写错误集中。' },
];

const repairChecklist = [
  '完成 3 题同类“电路等效”训练',
  '整理顶点式与一般式的转换步骤',
  '每日 10 分钟审题打卡，圈出关键词',
];

const reflectionNotes = [
  '今天重点关注了“审题跳步”，避免直接跳到公式。',
  '发现配方法容易忽略常数项，已写下提醒卡片。',
  '下一次练习先画图再列式，控制思路完整度。',
];

export default function StudentPerformancePage() {
  const [checked, setChecked] = useState<boolean[]>(repairChecklist.map(() => false));

  const toggleCheck = (index: number) => {
    setChecked((prev) => prev.map((item, idx) => (idx === index ? !item : item)));
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">No Ranking</p>
            <h1 className="text-2xl font-semibold text-slate-900">学生成绩心理减压看板</h1>
            <p className="text-sm text-slate-500">不展示位次，聚焦班级共性漏洞与自我纠错。</p>
          </div>
          <div className="rounded-full bg-emerald-50 px-4 py-2 text-xs font-semibold text-emerald-600">
            学习焦虑下降 30% · 试点样本
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">本周修补项</p>
            <p className="mt-3 text-3xl font-semibold text-slate-900">3</p>
            <p className="mt-2 text-xs text-slate-500">针对共性薄弱点生成</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">学习动力</p>
            <p className="mt-3 text-3xl font-semibold text-blue-600">自我纠错</p>
            <p className="mt-2 text-xs text-slate-500">不再以排名驱动</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-5 text-white">
            <p className="text-xs uppercase tracking-[0.3em] text-white/40">班级共性</p>
            <p className="mt-3 text-3xl font-semibold">失分陷阱 3 类</p>
            <p className="mt-2 text-xs text-white/50">已生成行动清单</p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">班级共性易错经验</h2>
                <p className="text-xs text-slate-400">来自全班匿名汇总，不包含个人排名</p>
              </div>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-600">全班共识</span>
            </div>
            <div className="mt-5 space-y-4">
              {commonMistakes.map((item) => (
                <div key={item.title} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <h3 className="text-sm font-semibold text-slate-800">{item.title}</h3>
                  <p className="mt-2 text-sm text-slate-600">{item.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.tips.map((tip) => (
                      <span key={tip} className="rounded-full bg-white px-3 py-1 text-xs text-slate-500">
                        {tip}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-slate-900">群体性失分陷阱</h2>
              <p className="text-xs text-slate-400">这些模式会拉低全班表现，请重点规避</p>
              <div className="mt-4 space-y-3">
                {groupTraps.map((trap) => (
                  <div key={trap.name} className="rounded-xl border border-slate-200 px-4 py-3">
                    <div className="flex items-center justify-between text-sm text-slate-700">
                      <span>{trap.name}</span>
                      <span className="font-semibold text-rose-500">{trap.value}</span>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">{trap.detail}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-slate-900">个人修补清单</h2>
              <p className="text-xs text-slate-400">基于班级易错点，为你生成任务</p>
              <div className="mt-4 space-y-3">
                {repairChecklist.map((task, index) => (
                  <label key={task} className="flex items-start gap-3 rounded-xl border border-slate-200 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={checked[index]}
                      onChange={() => toggleCheck(index)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600"
                    />
                    <span className={`text-sm ${checked[index] ? 'text-slate-400 line-through' : 'text-slate-700'}`}>
                      {task}
                    </span>
                  </label>
                ))}
              </div>
              <button className="mt-4 w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700">
                一键生成今日微练习
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900">自我纠错驱动记录</h2>
            <p className="text-xs text-slate-400">记录你的学习反思，强化内驱力</p>
            <div className="mt-4 space-y-3">
              {reflectionNotes.map((note, index) => (
                <div key={note} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-xs text-slate-400">#反思 {index + 1}</div>
                  <p className="mt-2 text-sm text-slate-600">{note}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-6 text-white">
            <h2 className="text-lg font-semibold">无排名安心区</h2>
            <p className="mt-2 text-sm text-white/60">你看不到任何位次，只看得到可以提升的方向。</p>
            <div className="mt-5 space-y-4">
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-4">
                <div className="text-xs text-white/40">情绪波动指数</div>
                <div className="mt-2 text-2xl font-semibold">稳定</div>
                <p className="mt-2 text-xs text-white/50">学习状态已从外部压力转向自我调节</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-4">
                <div className="text-xs text-white/40">下一步行动</div>
                <p className="mt-2 text-sm text-white/70">聚焦 2 个共性易错点，优先补齐基础。</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
