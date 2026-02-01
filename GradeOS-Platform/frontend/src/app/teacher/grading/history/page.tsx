'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, gradingApi, ClassResponse, GradingImportRecord } from '@/services/api';

export default function GradingHistoryPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [records, setRecords] = useState<GradingImportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterClass, setFilterClass] = useState<string>('');
  const [error, setError] = useState('');
  const [revokingId, setRevokingId] = useState<string | null>(null);

  useEffect(() => {
    const teacherId = user?.id || 't-001';
    classApi
      .getTeacherClasses(teacherId)
      .then((data) => setClasses(data))
      .catch(() => setClasses([]));
  }, [user]);

  const fetchHistory = (classId?: string) => {
    setLoading(true);
    gradingApi
      .getGradingHistory({
        class_id: classId || undefined,
        teacher_id: user?.id || undefined,
      })
      .then((data) => {
        setRecords(data.records);
        setError('');
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '加载批改历史失败');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHistory(filterClass);
  }, [filterClass, user?.id]);

  const handleRevoke = async (importId: string) => {
    setRevokingId(importId);
    try {
      await gradingApi.revokeGradingImport(importId);
      fetchHistory(filterClass);
    } catch (err) {
      setError(err instanceof Error ? err.message : '撤回失败');
    } finally {
      setRevokingId(null);
    }
  };

  const statusLabel = (record: GradingImportRecord) => {
    return record.status === 'revoked' ? '已撤回' : '已导入';
  };

  const filteredRecords = useMemo(() => records, [records]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">History</p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-2xl font-semibold text-slate-800">批改历史</h1>
              <button
                onClick={() => router.push('/teacher/grading/import')}
                className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800"
              >
                导入批改结果
              </button>
            </div>
            <p className="text-sm text-slate-500">
              查看已导入的批改记录，支持按班级筛选与撤回记录。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilterClass('')}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${!filterClass ? 'bg-emerald-500 text-white' : 'border border-slate-200 text-slate-600'
                }`}
            >
              全部班级
            </button>
            {classes.map((cls) => (
              <button
                key={cls.class_id}
                onClick={() => setFilterClass(cls.class_id)}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${filterClass === cls.class_id
                    ? 'bg-emerald-500 text-white'
                    : 'border border-slate-200 text-slate-600'
                  }`}
              >
                {cls.class_name}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">批改时间</th>
                  <th className="px-4 py-3">班级 / 作业</th>
                  <th className="px-4 py-3">涉及学生</th>
                  <th className="px-4 py-3">状态</th>
                  <th className="px-4 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td className="px-4 py-4 text-slate-500" colSpan={5}>
                      加载中...
                    </td>
                  </tr>
                )}
                {!loading && filteredRecords.length === 0 && (
                  <tr>
                    <td className="px-4 py-6 text-center text-slate-400" colSpan={5}>
                      暂无批改记录
                    </td>
                  </tr>
                )}
                {filteredRecords.map((record) => (
                  <tr key={record.import_id} className="border-b border-slate-100">
                    <td className="px-4 py-4 text-slate-700">{record.created_at}</td>
                    <td className="px-4 py-4 text-slate-700">
                      <div className="font-semibold">{record.class_name || record.class_id}</div>
                      <div className="text-xs text-slate-400">{record.assignment_title || '未绑定作业'}</div>
                    </td>
                    <td className="px-4 py-4 text-slate-700">{record.student_count}</td>
                    <td className="px-4 py-4 text-slate-700">{statusLabel(record)}</td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => router.push(`/teacher/grading/history/${record.import_id}`)}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                        >
                          查看详情
                        </button>
                        <button
                          onClick={() => router.push(`/grading/results-review/${record.batch_id || record.import_id}`)}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                        >
                          人工确认
                        </button>
                        {record.status !== 'revoked' && (
                          <button
                            onClick={() => handleRevoke(record.import_id)}
                            disabled={revokingId === record.import_id}
                            className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-600 hover:border-rose-300 disabled:opacity-60"
                          >
                            {revokingId === record.import_id ? '撤回中...' : '撤回'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
