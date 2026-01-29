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
  GradingResult,
  BatchGradingResponse,
} from '@/services/api';

type ResultEntry = {
  rowId: string;
  studentKey: string;
  displayName: string;
  score: number;
  maxScore: number;
};

export default function GradingImportPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [students, setStudents] = useState<StudentInfo[]>([]);
  const [assignments, setAssignments] = useState<HomeworkResponse[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('');
  const [batchId, setBatchId] = useState('');
  const [resultEntries, setResultEntries] = useState<ResultEntry[]>([]);
  const [studentMapping, setStudentMapping] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [importedRecords, setImportedRecords] = useState<GradingImportRecord[]>([]);

  useEffect(() => {
    const teacherId = user?.id || 't-001';
    setLoading(true);
    classApi
      .getTeacherClasses(teacherId)
      .then((data) => setClasses(data))
      .catch((err) => setError(err instanceof Error ? err.message : '加载班级失败'))
      .finally(() => setLoading(false));
  }, [user]);

  useEffect(() => {
    if (!selectedClassId) {
      setStudents([]);
      setAssignments([]);
      setSelectedAssignmentId('');
      return;
    }

    classApi.getClassStudents(selectedClassId).then((data) => setStudents(data));
    homeworkApi
      .getList({ class_id: selectedClassId })
      .then((data) => setAssignments(data))
      .catch(() => setAssignments([]));
  }, [selectedClassId]);

  const normalizeResults = (payload: BatchGradingResponse | GradingResult[] | unknown): ResultEntry[] => {
    const rawList = Array.isArray(payload)
      ? payload
      : (payload as Record<string, unknown>)?.results || (payload as Record<string, unknown>)?.student_results || (payload as Record<string, unknown>)?.studentResults || [];
    return (rawList as Array<Record<string, unknown>>).map((item, idx) => {
      const studentKey = String(
        item.student_name ||
          item.studentName ||
          item.student_key ||
          item.studentKey ||
          item.student_id ||
          item.studentId ||
          `Student ${idx + 1}`
      );
      const score = Number(item.total_score ?? item.totalScore ?? item.score ?? 0);
      const maxScore = Number(
        item.max_score ?? item.maxScore ?? item.max_total_score ?? item.maxTotalScore ?? item.max_score ?? 0
      );
      return {
        rowId: `${studentKey}__${idx}`,
        studentKey,
        displayName: studentKey,
        score,
        maxScore,
      };
    });
  };

  const applyAutoMatch = (entries: ResultEntry[], availableStudents: StudentInfo[]) => {
    const nextMapping: Record<string, string> = {};
    entries.forEach((entry) => {
      const match = availableStudents.find((student) => {
        const studentName = student.name.trim().toLowerCase();
        const entryName = entry.displayName.trim().toLowerCase();
        return studentName === entryName || student.id === entry.studentKey;
      });
      if (match) {
        nextMapping[entry.rowId] = match.id;
      }
    });
    setStudentMapping(nextMapping);
  };

  const handleLoadResults = async () => {
    setError('');
    setSuccessMessage('');
    if (!selectedClassId) {
      setError('请先选择班级');
      return;
    }
    if (!batchId.trim()) {
      setError('请填写提交 ID');
      return;
    }
    setLoadingResults(true);
    try {
      const response = await gradingApi.getBatchResults(batchId.trim());
      const entries = normalizeResults(response);
      setResultEntries(entries);
      applyAutoMatch(entries, students);
    } catch (err) {
      setError(err instanceof Error ? err.message : '拉取批改结果失败');
    } finally {
      setLoadingResults(false);
    }
  };

  const mappingStats = useMemo(() => {
    const mappedIds = Object.values(studentMapping).filter(Boolean);
    const uniqueMapped = new Set(mappedIds);
    const duplicates = mappedIds.length !== uniqueMapped.size;
    return {
      mappedCount: uniqueMapped.size,
      totalResults: resultEntries.length,
      hasDuplicates: duplicates,
    };
  }, [studentMapping, resultEntries]);

  const handleSubmit = async () => {
    setError('');
    setSuccessMessage('');

    if (!selectedClassId) {
      setError('请先选择班级');
      return;
    }
    if (!batchId.trim()) {
      setError('请填写提交 ID');
      return;
    }
    if (resultEntries.length === 0) {
      setError('请先加载批改结果');
      return;
    }
    if (mappingStats.mappedCount === 0) {
      setError('请完成学生匹配');
      return;
    }
    if (mappingStats.hasDuplicates) {
      setError('同一学生被重复匹配，请调整');
      return;
    }

    const mappingPayload = resultEntries
      .filter((entry) => studentMapping[entry.rowId])
      .map((entry) => ({
        student_key: entry.studentKey,
        student_id: studentMapping[entry.rowId],
      }));
    const studentIds = mappingPayload.map((item) => item.student_id);

    setSubmitting(true);
    try {
      const response = await gradingApi.importToClasses({
        batch_id: batchId.trim(),
        targets: [
          {
            class_id: selectedClassId,
            student_ids: studentIds,
            assignment_id: selectedAssignmentId || undefined,
            student_mapping: mappingPayload,
          },
        ],
      });
      setImportedRecords(response.records);
      setSuccessMessage('批改结果已导入，可在批改历史中查看详情。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Class Export</p>
            <h1 className="text-2xl font-semibold text-slate-800">批改结果导出到班级</h1>
            <p className="text-sm text-slate-500">
              先选择班级，再匹配学生与批改结果。匹配完成后即可导入并保留历史记录。
            </p>
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

        <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Step 01</p>
                  <h2 className="text-lg font-semibold text-slate-800">选择班级</h2>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {loading && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500">
                    加载班级中...
                  </div>
                )}
                {!loading && classes.length === 0 && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500">
                    暂无可用班级，请先创建班级。
                  </div>
                )}
                {classes.map((cls) => (
                  <button
                    key={cls.class_id}
                    onClick={() => {
                      setSelectedClassId(cls.class_id);
                      setResultEntries([]);
                      setStudentMapping({});
                      setImportedRecords([]);
                    }}
                    className={`rounded-2xl border px-4 py-4 text-left transition ${
                      selectedClassId === cls.class_id
                        ? 'border-blue-300 bg-blue-50 text-blue-700'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <div className="text-sm font-semibold">{cls.class_name}</div>
                    <div className="mt-1 text-xs text-slate-500">学生人数：{cls.student_count}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Step 02</p>
              <h2 className="mt-2 text-lg font-semibold text-slate-800">输入提交 ID 并加载结果</h2>
              <div className="mt-4 grid gap-3 lg:grid-cols-[1.4fr_1fr]">
                <div>
                  <label className="text-xs font-semibold text-slate-500">提交 ID</label>
                  <input
                    value={batchId}
                    onChange={(e) => setBatchId(e.target.value)}
                    placeholder="例如：7ac5993a-50d2-4b1f-b967-faf48e0e0365"
                    className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">关联作业（可选）</label>
                  <select
                    value={selectedAssignmentId}
                    onChange={(e) => setSelectedAssignmentId(e.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                  >
                    <option value="">不绑定作业</option>
                    {assignments.map((assignment) => (
                      <option key={assignment.homework_id} value={assignment.homework_id}>
                        {assignment.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <button
                  onClick={handleLoadResults}
                  disabled={loadingResults}
                  className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800 disabled:opacity-60"
                >
                  {loadingResults ? '加载中...' : '加载批改结果'}
                </button>
                <span className="text-xs text-slate-500">
                  已加载 {resultEntries.length} 条结果
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Step 03</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-800">匹配学生</h2>
            <p className="mt-2 text-sm text-slate-500">
              按批改结果逐条选择班级学生，系统会自动尝试同名匹配。
            </p>

            <div className="mt-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <div>
                已匹配 {mappingStats.mappedCount} / {mappingStats.totalResults}
              </div>
              <button
                onClick={() => applyAutoMatch(resultEntries, students)}
                className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:border-slate-400"
              >
                重新自动匹配
              </button>
            </div>

            <div className="mt-4 max-h-[520px] overflow-auto space-y-3 pr-1">
              {resultEntries.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-400">
                  暂无批改结果，请先加载。
                </div>
              )}
              {resultEntries.map((entry) => (
                <div
                  key={entry.rowId}
                  className="rounded-xl border border-slate-200 px-4 py-3 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-slate-700">{entry.displayName}</div>
                    <div className="text-xs text-slate-500">
                      {entry.score}/{entry.maxScore || '--'}
                    </div>
                  </div>
                  <div className="mt-3">
                    <select
                      value={studentMapping[entry.rowId] || ''}
                      onChange={(e) =>
                        setStudentMapping((prev) => ({ ...prev, [entry.rowId]: e.target.value }))
                      }
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-300"
                    >
                      <option value="">选择班级学生</option>
                      {students.map((student) => (
                        <option key={student.id} value={student.id}>
                          {student.name} ({student.id})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}
            </div>
          </div>
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
                <div
                  key={record.import_id}
                  className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm"
                >
                  <div>
                    <div className="font-semibold text-slate-700">{record.class_name || record.class_id}</div>
                    <div className="text-xs text-slate-500">
                      学生 {record.student_count} · {record.assignment_title || '未绑定作业'}
                    </div>
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
