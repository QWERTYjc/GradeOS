'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { analysisApi, DiagnosisReportResponse } from '@/services/api';
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

export default function StudentReportPage() {
  const { user } = useAuthStore();
  const [report, setReport] = useState<DiagnosisReportResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.id) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    analysisApi.getDiagnosisReport(user.id)
      .then((data) => {
        if (!active) return;
        setReport(data);
      })
      .catch((error) => {
        console.error('Failed to load report', error);
        if (active) setReport(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [user?.id]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center h-96 gap-4">
          <div className="w-12 h-12 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-500 font-medium">Building your progress report...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (!report) {
    return (
      <DashboardLayout>
        <div className="bg-white rounded-2xl p-12 text-center">
          <p className="text-slate-500">Unable to load report data.</p>
        </div>
      </DashboardLayout>
    );
  }

  const radarData = report.knowledge_map.map((km) => ({
    subject: km.knowledge_area,
    score: km.mastery_level * 100,
  }));

  const errorPatternData = report.error_patterns.most_common_error_types.map((ep) => ({
    name: ep.type,
    count: ep.count,
  }));

  return (
    <DashboardLayout>
      <div className="space-y-8 max-w-6xl mx-auto">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Progress Diagnostic Report</h1>
            <p className="text-slate-500 text-sm mt-1">Period: {report.report_period}</p>
          </div>
          <div className="bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium">
            ID: {report.student_id}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Mastery Score</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-slate-800">{(report.overall_assessment.mastery_score * 100).toFixed(1)}</span>
              <span className="text-slate-400 text-sm">%</span>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Improvement Rate</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-green-500">+{(report.overall_assessment.improvement_rate * 100).toFixed(1)}</span>
              <span className="text-slate-400 text-sm">%</span>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Consistency</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-blue-600">{report.overall_assessment.consistency_score}</span>
              <span className="text-slate-400 text-sm">/100</span>
            </div>
          </div>
          <div className="bg-slate-900 rounded-2xl p-6 text-white">
            <p className="text-xs font-bold text-white/40 uppercase tracking-wider mb-2">Tracked Topics</p>
            <span className="text-3xl font-bold">{report.knowledge_map.length}</span>
            <p className="text-xs text-white/40 mt-2">Current period</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-bold text-slate-800">Progress Trend</h3>
              <p className="text-xs text-slate-400 mt-1">Performance vs. class average</p>
            </div>
            <div className="flex gap-4 text-xs text-slate-500">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-blue-600 rounded-full" />
                Your Score
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-slate-300 rounded-full" />
                Class Average
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
                <YAxis hide />
                <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                <Area type="monotone" dataKey="average" stroke="#e2e8f0" fill="transparent" strokeWidth={2} strokeDasharray="5 5" />
                <Area type="monotone" dataKey="score" stroke="#2563EB" strokeWidth={3} fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h3 className="font-bold text-slate-800 mb-2">Skill Radar</h3>
            <p className="text-xs text-slate-400 mb-6">Balance across knowledge areas</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#F1F5F9" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 11 }} />
                  <Radar name="Mastery" dataKey="score" stroke="#2563EB" fill="#2563EB" fillOpacity={0.2} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h3 className="font-bold text-slate-800 mb-2">Error Pattern Breakdown</h3>
            <p className="text-xs text-slate-400 mb-6">Common error categories</p>
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

        <div className="bg-slate-900 rounded-2xl p-8 text-white">
          <div className="flex items-center gap-4 mb-8">
            <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center text-sm font-bold">AI</div>
            <div>
              <h3 className="text-xl font-bold">Personalized Insights</h3>
              <p className="text-white/40 text-xs mt-1">Generated from your latest data</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {report.personalized_insights.map((insight, idx) => (
              <div key={idx} className="flex gap-4 p-5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
                <span className="text-blue-400 font-bold text-lg">{String(idx + 1).padStart(2, '0')}</span>
                <p className="text-white/80 text-sm leading-relaxed">{insight}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
