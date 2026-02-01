'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, statisticsApi } from '@/services/api';
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

export default function TeacherStatisticsPage() {
  const [stats, setStats] = useState<ClassStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState<Array<{ id: string; name: string }>>([]);
  const [selectedClass, setSelectedClass] = useState<string>('');
  const { user } = useAuthStore();

  useEffect(() => {
    if (!user?.id) return;
    let active = true;
    classApi.getTeacherClasses(user.id)
      .then((items) => {
        if (!active) return;
        const mapped = items.map((cls) => ({ id: cls.class_id, name: cls.class_name }));
        setClasses(mapped);
        if (!selectedClass && mapped.length) {
          setSelectedClass(mapped[0].id);
        }
      })
      .catch((error) => {
        console.error('Failed to load classes', error);
        setClasses([]);
      });
    return () => {
      active = false;
    };
  }, [user?.id, selectedClass]);

  useEffect(() => {
    if (!selectedClass) return;
    let active = true;
    
    setLoading(true);
    statisticsApi.getClassStatistics(selectedClass)
      .then((data) => {
        if (!active) return;
        const className = classes.find((c) => c.id === selectedClass)?.name || '';
        setStats({ ...data, class_name: className });
      })
      .catch((error) => {
        console.error('Failed to load statistics', error);
        setStats(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedClass, classes]);

  const distributionData = stats ? Object.entries(stats.score_distribution).map(([range, count]) => ({
    range,
    count
  })) : [];

  const pieData = stats ? [
    { name: '???', value: stats.submitted_count },
    { name: '???', value: stats.total_students - stats.submitted_count }
  ] : [];

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* ???? */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">?? ??????</h1>
            <p className="text-slate-500 text-sm mt-1">???????????????</p>
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
            {/* KPI ?? */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">????</p>
                <p className="text-2xl font-bold text-slate-800">{stats.total_students}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">???</p>
                <p className="text-2xl font-bold text-blue-600">{stats.average_score}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">???</p>
                <p className="text-2xl font-bold text-green-500">{(stats.pass_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="text-xs font-bold text-slate-400 uppercase mb-1">??/??</p>
                <p className="text-2xl font-bold text-slate-800">{stats.max_score}/{stats.min_score}</p>
              </div>
            </div>

            {/* ???? */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* ???? */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-bold text-slate-800 mb-6">?? ????</h3>
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

              {/* ???? */}
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-bold text-slate-800 mb-6">?? ????</h3>
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
                    ???<span className="font-bold text-green-500">{stats.submitted_count}</span> / {stats.total_students} ?
                  </p>
                </div>
              </div>
            </div>

            {/* ?????? */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-bold text-slate-800 mb-4">?? ????????</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(stats.score_distribution ? Object.entries(stats.score_distribution).slice(0, 3) : []).map(([range], index) => (
                  <div key={range} className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-slate-500 font-bold">{String(index + 1).padStart(2, '0')}</span>
                      <span className="font-medium text-slate-800">{range} ??</span>
                    </div>
                    <p className="text-sm text-slate-500">????????????</p>
                  </div>
                ))}
              </div>
            </div>

            {/* ???? */}
            <div className="bg-slate-900 rounded-xl p-6 text-white">
              <h3 className="font-bold mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm">AI</span>
                ??????
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <p className="text-white/80 text-sm">????????????????????</p>
                </div>
                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <p className="text-white/80 text-sm">?????????????????????</p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
