'use client';

import React, { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';

const contributions = [
  {
    id: 'c-001',
    title: '圆与直线位置关系经典题',
    author: '匿名同学 A',
    tags: ['解析几何', '经典', '详解'],
    likes: 36,
    summary: '通过判别式快速判断相切/相交，并给出几何解释。',
  },
  {
    id: 'c-002',
    title: '力学能守恒变式题',
    author: '匿名同学 B',
    tags: ['力学', '变式', '巧解'],
    likes: 28,
    summary: '用能量流向图替代复杂受力分析，效率提升。',
  },
  {
    id: 'c-003',
    title: '概率统计快速计算',
    author: '匿名同学 C',
    tags: ['概率', '简洁', '思路'],
    likes: 22,
    summary: '利用对称性减少枚举，节省一半计算量。',
  },
];

const trendingTags = ['解析几何', '函数', '力学', '数列', '电学', '立体几何'];

export default function CrowdboardPage() {
  const [selectedTag, setSelectedTag] = useState('');

  const filtered = selectedTag
    ? contributions.filter((item) => item.tags.includes(selectedTag))
    : contributions;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Open Knowledge</p>
            <h1 className="text-2xl font-semibold text-slate-900">好题众筹公告栏</h1>
            <p className="text-sm text-slate-500">班级内部开源知识库，让好题好解被共享。</p>
          </div>
          <button className="rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
            上传我的好题
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">本月新增</p>
            <p className="mt-3 text-3xl font-semibold text-slate-900">214 条</p>
            <p className="mt-2 text-xs text-slate-500">学生原创解析沉淀</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">共享覆盖率</p>
            <p className="mt-3 text-3xl font-semibold text-blue-600">92%</p>
            <p className="mt-2 text-xs text-slate-500">资源透明度提升</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-5 text-white">
            <p className="text-xs uppercase tracking-[0.3em] text-white/40">协作社区</p>
            <p className="mt-3 text-3xl font-semibold">开放共创</p>
            <p className="mt-2 text-xs text-white/50">教育资源更均衡</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">热门标签</h2>
              <p className="text-xs text-slate-400">按知识点快速浏览贡献</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedTag('')}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  selectedTag === '' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                全部
              </button>
              {trendingTags.map((tag) => (
                <button
                  key={tag}
                  onClick={() => setSelectedTag(tag)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    selectedTag === tag ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {filtered.map((item) => (
              <div key={item.id} className="rounded-xl border border-slate-200 p-4 hover:shadow-sm transition">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-blue-600">{item.author}</span>
                  <span className="text-xs text-slate-400">👍 {item.likes}</span>
                </div>
                <h3 className="mt-2 text-sm font-semibold text-slate-800">{item.title}</h3>
                <p className="mt-2 text-xs text-slate-500">{item.summary}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500">
                      {tag}
                    </span>
                  ))}
                </div>
                <button className="mt-4 w-full rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">
                  查看解析
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900">上传好题指南</h2>
            <ol className="mt-4 space-y-3 text-sm text-slate-600">
              <li>1. 拍照或输入题目原文，突出关键条件。</li>
              <li>2. 描述解题思路与关键技巧，尽量简明。</li>
              <li>3. 标注知识点标签，便于他人检索。</li>
            </ol>
            <button className="mt-5 w-full rounded-xl bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-600">
              一键生成上传模板
            </button>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-6 text-white">
            <h2 className="text-lg font-semibold">班级共创故事</h2>
            <p className="mt-2 text-sm text-white/60">
              通过好题众筹，班级同学每月平均贡献 200+ 条解析，资源共享让每个人都站在集体智慧的肩膀上。
            </p>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-4">
                <div className="text-xs text-white/40">资源透明度</div>
                <div className="mt-2 text-2xl font-semibold">显著提升</div>
                <p className="mt-2 text-xs text-white/50">家庭背景差距被缩小</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-4">
                <div className="text-xs text-white/40">讨论活跃度</div>
                <div className="mt-2 text-2xl font-semibold">+68%</div>
                <p className="mt-2 text-xs text-white/50">班级学术氛围更浓</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
