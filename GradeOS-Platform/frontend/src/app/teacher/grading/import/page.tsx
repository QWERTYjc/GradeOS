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
  /** 从批改结果中提取的可能的学号 */
  possibleStudentId?: string;
  /** 编辑后的学生名称（用户可修改） */
  editableName?: string;
};

/** 匹配模式 */
type MatchMode = 'name' | 'id' | 'fuzzy' | 'manual';

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
  const [editableEntries, setEditableEntries] = useState<Record<string, ResultEntry>>({});
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
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

  /**
   * 从字符串中提取可能的学号
   * 支持格式：纯数字、字母+数字组合、带学号前缀等
   */
  const extractStudentId = (str: string): string | undefined => {
    // 匹配常见的学号格式：
    // 1. 纯数字（6-12位）
    // 2. 字母+数字组合
    // 3. 带"学号"、"ID"等前缀
    const patterns = [
      /(?:学号|ID|id|学号[：:]?\s*)\s*([a-zA-Z0-9]+)/i,
      /\b([a-zA-Z]\d{6,11})\b/,
      /\b(\d{6,12})\b/,
    ];
    
    for (const pattern of patterns) {
      const match = str.match(pattern);
      if (match) {
        return match[1] || match[0];
      }
    }
    return undefined;
  };

  /**
   * 清理学生名称，移除学号等元信息
   */
  const cleanStudentName = (rawName: string): string => {
    // 移除常见的学号前缀/后缀
    return rawName
      .replace(/学号[：:]?\s*[a-zA-Z0-9]+/gi, '')
      .replace(/ID[：:]?\s*[a-zA-Z0-9]+/gi, '')
      .replace(/\d{6,12}/g, '')
      .replace(/[_-]+/g, ' ')
      .trim();
  };

  const normalizeResults = (payload: BatchGradingResponse | GradingResult[] | unknown): ResultEntry[] => {
    const rawList = Array.isArray(payload)
      ? payload
      : (payload as Record<string, unknown>)?.results || (payload as Record<string, unknown>)?.student_results || (payload as Record<string, unknown>)?.studentResults || [];
    return (rawList as Array<Record<string, unknown>>).map((item, idx) => {
      const rawStudentKey = String(
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
      
      // 提取可能的学号和清理后的名称
      const possibleStudentId = extractStudentId(rawStudentKey);
      const cleanName = cleanStudentName(rawStudentKey) || rawStudentKey;
      
      return {
        rowId: `${rawStudentKey}__${idx}`,
        studentKey: rawStudentKey,
        displayName: cleanName,
        editableName: cleanName,
        score,
        maxScore,
        possibleStudentId,
      };
    });
  };

  /**
   * 计算两个字符串的相似度（Levenshtein距离）
   */
  const calculateSimilarity = (str1: string, str2: string): number => {
    const s1 = str1.toLowerCase().trim();
    const s2 = str2.toLowerCase().trim();
    
    if (s1 === s2) return 1;
    
    const len1 = s1.length;
    const len2 = s2.length;
    const matrix: number[][] = [];
    
    for (let i = 0; i <= len1; i++) {
      matrix[i] = [i];
    }
    for (let j = 0; j <= len2; j++) {
      matrix[0][j] = j;
    }
    
    for (let i = 1; i <= len1; i++) {
      for (let j = 1; j <= len2; j++) {
        const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
        matrix[i][j] = Math.min(
          matrix[i - 1][j] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j - 1] + cost
        );
      }
    }
    
    const distance = matrix[len1][len2];
    const maxLen = Math.max(len1, len2);
    return 1 - distance / maxLen;
  };

  /**
   * 智能匹配学生
   * 优先级：
   * 1. 学号精确匹配
   * 2. 姓名精确匹配
   * 3. ID精确匹配
   * 4. 模糊匹配（相似度>0.7）
   */
  const findBestMatch = (entry: ResultEntry, availableStudents: StudentInfo[], usedIds: Set<string>): StudentInfo | null => {
    let bestMatch: StudentInfo | null = null;
    let bestScore = 0;
    
    for (const student of availableStudents) {
      // 如果该学生已经被匹配，跳过
      if (usedIds.has(student.id)) continue;
      
      let score = 0;
      const studentNameLower = student.name.toLowerCase().trim();
      const entryNameLower = (entry.editableName || entry.displayName).toLowerCase().trim();
      
      // 1. 学号精确匹配（最高优先级）
      if (entry.possibleStudentId && 
          (student.id === entry.possibleStudentId || 
           student.id.includes(entry.possibleStudentId) ||
           entry.possibleStudentId.includes(student.id))) {
        score = 100;
      }
      // 2. 姓名精确匹配
      else if (studentNameLower === entryNameLower) {
        score = 90;
      }
      // 3. ID精确匹配
      else if (student.id === entry.studentKey) {
        score = 80;
      }
      // 4. 姓名包含关系
      else if (studentNameLower.includes(entryNameLower) || entryNameLower.includes(studentNameLower)) {
        score = 70;
      }
      // 5. 模糊匹配
      else {
        const similarity = calculateSimilarity(studentNameLower, entryNameLower);
        if (similarity > 0.7) {
          score = similarity * 60;
        }
      }
      
      if (score > bestScore) {
        bestScore = score;
        bestMatch = student;
      }
    }
    
    return bestMatch;
  };

  const applyAutoMatch = (entries: ResultEntry[], availableStudents: StudentInfo[]) => {
    const nextMapping: Record<string, string> = {};
    const usedIds = new Set<string>();
    
    entries.forEach((entry) => {
      const match = findBestMatch(entry, availableStudents, usedIds);
      if (match) {
        nextMapping[entry.rowId] = match.id;
        usedIds.add(match.id);
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
      // 初始化可编辑条目
      const editableMap: Record<string, ResultEntry> = {};
      entries.forEach(entry => {
        editableMap[entry.rowId] = entry;
      });
      setEditableEntries(editableMap);
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

  /**
   * 更新条目的可编辑名称
   */
  const updateEntryName = (rowId: string, newName: string) => {
    setEditableEntries(prev => ({
      ...prev,
      [rowId]: {
        ...prev[rowId],
        editableName: newName,
      },
    }));
  };

  /**
   * 获取匹配状态信息
   */
  const getMatchInfo = (entry: ResultEntry): { type: 'exact' | 'fuzzy' | 'none'; student?: StudentInfo } => {
    const mappedId = studentMapping[entry.rowId];
    if (!mappedId) return { type: 'none' };
    
    const student = students.find(s => s.id === mappedId);
    if (!student) return { type: 'none' };
    
    const entryName = (entry.editableName || entry.displayName).toLowerCase().trim();
    const studentName = student.name.toLowerCase().trim();
    
    if (studentName === entryName) {
      return { type: 'exact', student };
    }
    return { type: 'fuzzy', student };
  };

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
              智能匹配会根据学号、姓名自动关联。您也可以手动调整。
            </p>

            <div className="mt-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <div className="flex items-center gap-2">
                <span>已匹配 {mappingStats.mappedCount} / {mappingStats.totalResults}</span>
                {mappingStats.mappedCount > 0 && (
                  <span className="text-emerald-600 text-xs">
                    ({Math.round((mappingStats.mappedCount / mappingStats.totalResults) * 100)}%)
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => applyAutoMatch(resultEntries, students)}
                  className="rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition-colors"
                >
                  一键智能匹配
                </button>
                <button
                  onClick={() => setStudentMapping({})}
                  className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:border-slate-400"
                >
                  清空匹配
                </button>
              </div>
            </div>

            <div className="mt-4 max-h-[520px] overflow-auto space-y-3 pr-1">
              {resultEntries.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-400">
                  暂无批改结果，请先加载。
                </div>
              )}
              {resultEntries.map((entry) => {
                const matchInfo = getMatchInfo(entry);
                const editableEntry = editableEntries[entry.rowId] || entry;
                const isEditing = editingRowId === entry.rowId;
                
                return (
                  <div
                    key={entry.rowId}
                    className={`rounded-xl border px-4 py-3 text-sm transition-all ${
                      matchInfo.type === 'exact' 
                        ? 'border-emerald-200 bg-emerald-50/30' 
                        : matchInfo.type === 'fuzzy'
                        ? 'border-amber-200 bg-amber-50/30'
                        : 'border-slate-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editableEntry.editableName || editableEntry.displayName}
                              onChange={(e) => updateEntryName(entry.rowId, e.target.value)}
                              onBlur={() => setEditingRowId(null)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  setEditingRowId(null);
                                  // 重新匹配
                                  applyAutoMatch(Object.values(editableEntries), students);
                                }
                              }}
                              autoFocus
                              className="flex-1 rounded-lg border border-blue-300 px-2 py-1 text-sm font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                            />
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-700 truncate">
                              {editableEntry.editableName || editableEntry.displayName}
                            </span>
                            <button
                              onClick={() => setEditingRowId(entry.rowId)}
                              className="text-[10px] text-slate-400 hover:text-blue-600 transition-colors"
                              title="编辑名称"
                            >
                              ✎
                            </button>
                          </div>
                        )}
                        {entry.possibleStudentId && (
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            检测到学号: <span className="font-mono text-blue-600">{entry.possibleStudentId}</span>
                          </div>
                        )}
                      </div>
                      <div className="text-right ml-3">
                        <div className="text-xs text-slate-500">
                          {entry.score}/{entry.maxScore || '--'}
                        </div>
                        {matchInfo.type !== 'none' && (
                          <div className={`text-[10px] ${
                            matchInfo.type === 'exact' ? 'text-emerald-600' : 'text-amber-600'
                          }`}>
                            {matchInfo.type === 'exact' ? '精确匹配' : '模糊匹配'}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="mt-3">
                      <select
                        value={studentMapping[entry.rowId] || ''}
                        onChange={(e) =>
                          setStudentMapping((prev) => ({ ...prev, [entry.rowId]: e.target.value }))
                        }
                        className={`w-full rounded-lg border px-3 py-2 text-xs focus:outline-none focus:ring-2 transition-all ${
                          studentMapping[entry.rowId]
                            ? 'border-emerald-200 bg-emerald-50 text-slate-700 focus:ring-emerald-200'
                            : 'border-slate-200 text-slate-600 focus:ring-slate-300'
                        }`}
                      >
                        <option value="">选择班级学生</option>
                        {students.map((student) => (
                          <option key={student.id} value={student.id}>
                            {student.name} (ID: {student.id})
                          </option>
                        ))}
                      </select>
                    </div>
                    {matchInfo.student && (
                      <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-600">
                        <span>✓</span>
                        <span>已匹配: {matchInfo.student.name}</span>
                      </div>
                    )}
                  </div>
                );
              })}
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
