'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import {
  classApi,
  gradingApi,
  homeworkApi,
  ClassResponse,
  StudentInfo,
  HomeworkResponse,
  GradingImportRecord,
} from '@/services/api';

type StudentSelectionMap = Record<string, string[]>;
type AssignmentSelectionMap = Record<string, string>;

export default function GradingImportPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);
  const [studentsByClass, setStudentsByClass] = useState<Record<string, StudentInfo[]>>({});
  const [assignmentsByClass, setAssignmentsByClass] = useState<Record<string, HomeworkResponse[]>>({});
  const [selectedStudents, setSelectedStudents] = useState<StudentSelectionMap>({});
  const [selectedAssignments, setSelectedAssignments] = useState<AssignmentSelectionMap>({});
  const [batchId, setBatchId] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [importedRecords, setImportedRecords] = useState<GradingImportRecord[]>([]);

  useEffect(() => {
    const teacherId = user?.id || 't-001';
    setLoading(true);
    classApi
      .getTeacherClasses(teacherId)
      .then((data) => {
        setClasses(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '加载班级失败');
      })
      .finally(() => setLoading(false));
  }, [user]);

  const toggleClass = (classId: string) => {
    setError('');
    setSuccessMessage('');
    setSelectedClassIds((prev) => {
      if (prev.includes(classId)) {
        const next = prev.filter((id) => id !== classId);
        return next;
      }
      return [...prev, classId];
    });

    if (!studentsByClass[classId]) {
      classApi.getClassStudents(classId).then((data) => {
        setStudentsByClass((prev) => ({ ...prev, [classId]: data }));
      });
    }

    if (!assignmentsByClass[classId]) {
      homeworkApi
        .getList({ class_id: classId })
        .then((data) => {
          setAssignmentsByClass((prev) => ({ ...prev, [classId]: data }));
        })
        .catch(() => {
          setAssignmentsByClass((prev) => ({ ...prev, [classId]: [] }));
        });
    }
  };

  const toggleStudent = (classId: string, studentId: string) => {
    setSelectedStudents((prev) => {
      const existing = new Set(prev[classId] || []);
      if (existing.has(studentId)) {
        existing.delete(studentId);
      } else {
        existing.add(studentId);
      }
      return { ...prev, [classId]: Array.from(existing) };
    });
  };

  const handleSubmit = async () => {
    setError('');
    setSuccessMessage('');
    if (!batchId.trim()) {
      setError('请填写批次 ID');
      return;
    }
    const targets = selectedClassIds.map((classId) => ({
      class_id: classId,
      student_ids: selectedStudents[classId] || [],
      assignment_id: selectedAssignments[classId] || undefined,
    }));

    if (!targets.length || targets.every((target) => target.student_ids.length === 0)) {
      setError('至少选择一个班级的学生');
      return;
    }

    if (targets.some((target) => target.student_ids.length === 0)) {
      setError('已选择的班级必须至少勾选一名学生');
      return;
    }

    setSubmitting(true);
    try {
      const response = await gradingApi.importToClasses({
        batch_id: batchId.trim(),
        targets,
      });
      setImportedRecords(response.records);
      setSuccessMessage('批改结果已导入，可在批改历史中查看详情。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedCount = useMemo(() => {
    return selectedClassIds.reduce((sum, classId) => sum + (selectedStudents[classId]?.length || 0), 0);
  }, [selectedClassIds, selectedStudents]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Class Integration</p>
            <h1 className="text-2xl font-semibold text-slate-800">批改结果导入</h1>
            <p className="text-sm text-slate-500">
              将 AI 批改任务导入到班级与指定学生，导入后可撤回且保留历史记录。
            </p>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <label className="text-xs font-semibold text-slate-500">批次 ID</label>
              <input
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                placeholder="例如：7ac5993a-50d2-4b1f-b967-faf48e0e0365"
                className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
              />
            </div>
            <div className="flex flex-col justify-end rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
              <span className="font-semibold text-slate-600">已选择学生</span>
              <span className="mt-2 text-2xl font-semibold text-slate-900">{selectedCount}</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}
        {successMessage && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {successMessage}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          {loading && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
              加载班级中...
            </div>
          )}
          {!loading && classes.length === 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
              暂无可用班级，请先创建班级。
            </div>
          )}
          {classes.map((cls) => {
            const isSelected = selectedClassIds.includes(cls.class_id);
            const students = studentsByClass[cls.class_id] || [];
            const selected = selectedStudents[cls.class_id] || [];
            const assignments = assignmentsByClass[cls.class_id] || [];
            return (
              <div key={cls.class_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-800">{cls.class_name}</h3>
                    <p className="text-xs text-slate-500">学生人数：{cls.student_count}</p>
                  </div>
                  <button
                    onClick={() => toggleClass(cls.class_id)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      isSelected ? 'bg-emerald-500 text-white' : 'border border-slate-200 text-slate-600'
                    }`}
                  >
                    {isSelected ? '已选择' : '选择班级'}
                  </button>
                </div>

                {isSelected && (
                  <div className="mt-4 space-y-4">
                    <div>
                      <label className="text-xs font-semibold text-slate-500">关联作业（可选）</label>
                      <select
                        value={selectedAssignments[cls.class_id] || ''}
                        onChange={(e) =>
                          setSelectedAssignments((prev) => ({ ...prev, [cls.class_id]: e.target.value }))
                        }
                        className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                      >
                        <option value="">不绑定作业</option>
                        {assignments.map((assignment) => (
                          <option key={assignment.homework_id} value={assignment.homework_id}>
                            {assignment.title}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500">选择学生（可多选）</span>
                        <span className="text-xs text-slate-400">已选 {selected.length}</span>
                      </div>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {students.length === 0 && (
                          <div className="rounded-lg border border-dashed border-slate-200 p-3 text-xs text-slate-400">
                            暂无学生
                          </div>
                        )}
                        {students.map((student) => (
                          <label
                            key={student.id}
                            className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600"
                          >
                            <input
                              type="checkbox"
                              checked={selected.includes(student.id)}
                              onChange={() => toggleStudent(cls.class_id, student.id)}
                              className="h-4 w-4 rounded border-slate-300 text-slate-900"
                            />
                            {student.name}
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="rounded-full bg-slate-900 px-6 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800 disabled:opacity-60"
          >
            {submitting ? '导入中...' : '提交导入'}
          </button>
          <button
            onClick={() => router.push('/teacher/grading/history')}
            className="rounded-full border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-600 hover:border-slate-400"
          >
            查看批改历史
          </button>
        </div>

        {importedRecords.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-800">导入记录</h3>
                <p className="text-xs text-slate-500">本次导入生成 {importedRecords.length} 条记录</p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {importedRecords.map((record) => (
                <div key={record.import_id} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm">
                  <div>
                    <div className="font-semibold text-slate-700">{record.class_name || record.class_id}</div>
                    <div className="text-xs text-slate-500">学生 {record.student_count} · {record.assignment_title || '未绑定作业'}</div>
                  </div>
                  <button
                    onClick={() => router.push(`/teacher/grading/history/${record.import_id}`)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                  >
                    查看详情
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
