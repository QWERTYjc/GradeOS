"use client";

import React, { use, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { gradingApi } from "@/services/api";

type ScoringPointResultDraft = {
  pointId?: string;
  description?: string;
  awarded?: number;
  maxPoints?: number;
  evidence?: string;
  rubricReference?: string;
  decision?: string;
};

type QuestionResultDraft = {
  questionId: string;
  score: number;
  maxScore: number;
  feedback: string;
  confidence?: number;
  typoNotes?: string[];
  pageIndices?: number[];
  scoringPointResults?: ScoringPointResultDraft[];
  reviewNote: string;
};

type StudentResultDraft = {
  studentName: string;
  score: number;
  maxScore: number;
  startPage?: number;
  endPage?: number;
  questionResults: QuestionResultDraft[];
};

type ResultsReviewContext = {
  batch_id: string;
  status?: string;
  current_stage?: string;
  student_results: Array<Record<string, any>>;
  answer_images: string[];
};

const normalizeResults = (raw: Array<Record<string, any>>): StudentResultDraft[] => {
  if (!Array.isArray(raw)) return [];
  return raw.map((student) => {
    const questionResults = Array.isArray(student.questionResults || student.question_results)
      ? (student.questionResults || student.question_results).map((q: any, idx: number) => ({
        questionId: String(q.questionId || q.question_id || idx + 1),
        score: Number(q.score ?? 0),
        maxScore: Number(q.maxScore ?? q.max_score ?? 0),
        feedback: q.feedback || "",
        confidence: q.confidence,
        typoNotes: q.typoNotes || q.typo_notes || [],
        pageIndices: q.pageIndices || q.page_indices || [],
        scoringPointResults: (q.scoringPointResults || q.scoring_point_results || []).map((spr: any) => ({
          pointId: spr.pointId || spr.point_id,
          description: spr.description || spr.scoringPoint?.description || spr.scoring_point?.description,
          awarded: spr.awarded ?? spr.score ?? 0,
          maxPoints: spr.maxPoints ?? spr.max_points ?? spr.scoringPoint?.score ?? spr.scoring_point?.score ?? 0,
          evidence: spr.evidence || "",
          rubricReference: spr.rubricReference || spr.rubric_reference,
          decision: spr.decision || spr.result || spr.judgement || spr.judgment,
        })),
        reviewNote: "",
      }))
      : [];

    return {
      studentName: student.studentName || student.student_name || "Unknown",
      score: Number(student.score ?? student.total_score ?? 0),
      maxScore: Number(student.maxScore ?? student.max_score ?? student.max_total_score ?? 0),
      startPage: student.startPage ?? student.start_page,
      endPage: student.endPage ?? student.end_page,
      questionResults,
    };
  });
};

const buildOverridePayload = (draft: StudentResultDraft[]) => {
  return draft.map((student) => ({
    studentKey: student.studentName,
    questionResults: student.questionResults.map((q) => ({
      questionId: q.questionId,
      score: q.score,
      feedback: q.feedback,
    })),
  }));
};

export default function ResultsReviewPage({ params }: { params: Promise<{ batchId: string }> }) {
  const router = useRouter();
  const { batchId } = use(params);
  const [answerImages, setAnswerImages] = useState<string[]>([]);
  const [resultsDraft, setResultsDraft] = useState<StudentResultDraft[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [selectedStudentIndex, setSelectedStudentIndex] = useState(0);
  const [selectedQuestionKeys, setSelectedQuestionKeys] = useState<Set<string>>(new Set());
  const [expandedQuestionKeys, setExpandedQuestionKeys] = useState<Set<string>>(new Set());
  const [globalNote, setGlobalNote] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    gradingApi
      .getResultsReviewContext(batchId)
      .then((data: ResultsReviewContext) => {
        if (!active) return;
        setStatus(data.status || null);
        setCurrentStage(data.current_stage || null);
        setResultsDraft(normalizeResults(data.student_results || []));
        const images = (data.answer_images || []).map((img) =>
          img.startsWith("data:") ? img : `data:image/jpeg;base64,${img}`
        );
        setAnswerImages(images);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load results context.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [batchId]);

  const updateQuestion = useCallback(
    (studentIndex: number, questionId: string, field: keyof QuestionResultDraft, value: any) => {
      setResultsDraft((prev) =>
        prev.map((student, idx) => {
          if (idx !== studentIndex) return student;
          return {
            ...student,
            questionResults: student.questionResults.map((q) =>
              q.questionId === questionId ? { ...q, [field]: value } : q
            ),
          };
        })
      );
    },
    []
  );

  const toggleSelected = (studentIndex: number, questionId: string) => {
    const key = `${studentIndex}:${questionId}`;
    setSelectedQuestionKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const toggleExpanded = (studentIndex: number, questionId: string) => {
    const key = `${studentIndex}:${questionId}`;
    setExpandedQuestionKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const currentStudent = resultsDraft[selectedStudentIndex];

  const pageIndices = useMemo(() => {
    if (!currentStudent) return [];
    if (currentStudent.startPage !== undefined && currentStudent.endPage !== undefined) {
      const pages = [];
      for (let i = currentStudent.startPage; i <= currentStudent.endPage; i += 1) {
        pages.push(i);
      }
      return pages;
    }
    const fromQuestions = new Set<number>();
    currentStudent.questionResults.forEach((q) => {
      (q.pageIndices || []).forEach((page) => fromQuestions.add(page));
    });
    return Array.from(fromQuestions).sort((a, b) => a - b);
  }, [currentStudent]);

  const handleApprove = async () => {
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    try {
      await gradingApi.submitResultsReview({ batch_id: batchId, action: "approve" });
      setSuccessMessage("已确认批改结果，流程继续进行。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitUpdate = async () => {
    if (!resultsDraft.length) return;
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    try {
      await gradingApi.submitResultsReview({
        batch_id: batchId,
        action: "update",
        results: buildOverridePayload(resultsDraft),
      });
      setSuccessMessage("已提交修正结果，流程继续进行。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegrade = async () => {
    if (!resultsDraft.length || selectedQuestionKeys.size === 0) return;
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    const regradeItems: Array<Record<string, any>> = [];
    const noteLines: string[] = [];
    const trimmedGlobal = globalNote.trim();
    if (trimmedGlobal) noteLines.push(trimmedGlobal);

    resultsDraft.forEach((student, sIdx) => {
      student.questionResults.forEach((q) => {
        const key = `${sIdx}:${q.questionId}`;
        if (!selectedQuestionKeys.has(key)) return;
        const note = q.reviewNote.trim();
        if (note) {
          noteLines.push(`${student.studentName} Q${q.questionId}: ${note}`);
        }
        regradeItems.push({
          student_key: student.studentName,
          question_id: q.questionId,
          page_indices: q.pageIndices || [],
          notes: note,
        });
      });
    });

    try {
      await gradingApi.submitResultsReview({
        batch_id: batchId,
        action: "regrade",
        regrade_items: regradeItems,
        notes: noteLines.join("\n"),
      });
      setSuccessMessage("已提交重新批改请求，请稍后刷新查看结果。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50">
        <div className="text-slate-500 text-sm">Loading results review...</div>
      </div>
    );
  }

  if (!currentStudent) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50">
        <div className="text-slate-500 text-sm">No grading results available.</div>
      </div>
    );
  }

  const totalScore = currentStudent.questionResults.reduce((sum, q) => sum + (q.score || 0), 0);
  const totalMax = currentStudent.questionResults.reduce((sum, q) => sum + (q.maxScore || 0), 0);

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-slate-50 via-sky-50 to-amber-50">
      <div className="mx-auto max-w-[1400px] px-6 py-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Results Review</p>
            <h1 className="text-3xl font-semibold text-slate-900">批改结果确认</h1>
            <div className="mt-2 text-sm text-slate-500">
              Batch: {batchId} · Status: {status || "running"} · Stage: {currentStage || "review"}
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => router.push(`/console?batchId=${batchId}`)}
              className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:border-slate-400"
            >
              回到批改流程
            </button>
            <button
              onClick={handleApprove}
              disabled={isSubmitting}
              className="rounded-full bg-emerald-500 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-emerald-600 disabled:opacity-60"
            >
              确认无误
            </button>
            <button
              onClick={handleSubmitUpdate}
              disabled={isSubmitting}
              className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800 disabled:opacity-60"
            >
              提交修正
            </button>
          </div>
        </header>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}
        {successMessage && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {successMessage}
          </div>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <section className="rounded-3xl border border-slate-200 bg-white/70 p-4 shadow-xl backdrop-blur">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-800">学生作答原图</h2>
                <p className="text-xs text-slate-500">{pageIndices.length} pages</p>
              </div>
              <div className="text-xs text-slate-400">
                当前学生：{currentStudent.studentName}
              </div>
            </div>
            <div className="max-h-[760px] overflow-y-auto space-y-4 pr-2">
              {pageIndices.length === 0 && (
                <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
                  未找到该学生答题页
                </div>
              )}
              {pageIndices.map((pageIndex) => (
                <div key={pageIndex} className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                  <div className="mb-2 text-xs font-semibold text-slate-500">Page {pageIndex + 1}</div>
                  <div className="aspect-[3/4] overflow-hidden rounded-xl bg-slate-50">
                    {answerImages[pageIndex] ? (
                      <img src={answerImages[pageIndex]} alt={`Answer page ${pageIndex + 1}`} className="h-full w-full object-contain" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-slate-400">No image</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-xl backdrop-blur">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-800">批改结果</h2>
                  <p className="text-xs text-slate-500">
                    合计 {totalScore}/{totalMax} · 当前学生 {selectedStudentIndex + 1}/{resultsDraft.length}
                  </p>
                </div>
                <button
                  onClick={handleRegrade}
                  disabled={isSubmitting || selectedQuestionKeys.size === 0}
                  className="rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-600 hover:border-slate-400 disabled:opacity-50"
                >
                  重新批改所选
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {resultsDraft.map((student, idx) => (
                  <button
                    key={`${student.studentName}-${idx}`}
                    onClick={() => setSelectedStudentIndex(idx)}
                    className={clsx(
                      "rounded-full px-3 py-1 text-xs font-semibold",
                      idx === selectedStudentIndex
                        ? "bg-emerald-500 text-white"
                        : "border border-slate-200 text-slate-600"
                    )}
                  >
                    {student.studentName}
                  </button>
                ))}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <label className="text-xs font-semibold text-slate-500">问题说明（用于重新批改）</label>
                <textarea
                  value={globalNote}
                  onChange={(e) => setGlobalNote(e.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                  rows={3}
                  placeholder="说明哪些题目有问题、需要关注的证据或评分点。"
                />
              </div>

              <div className="max-h-[620px] overflow-y-auto space-y-4 pr-2">
                {currentStudent.questionResults.map((q) => {
                  const key = `${selectedStudentIndex}:${q.questionId}`;
                  const isSelected = selectedQuestionKeys.has(key);
                  const isExpanded = expandedQuestionKeys.has(key);
                  return (
                    <div key={q.questionId} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-800">
                            题号 {q.questionId} · {q.score}/{q.maxScore} 分
                          </div>
                          {q.pageIndices && q.pageIndices.length > 0 && (
                            <div className="text-xs text-slate-400">页码：{q.pageIndices.map((p) => p + 1).join(", ")}</div>
                          )}
                        </div>
                        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelected(selectedStudentIndex, q.questionId)}
                            className="h-4 w-4 rounded border-slate-300 text-slate-900"
                          />
                          有问题
                        </label>
                      </div>

                      <div className="mt-4 grid gap-3">
                        <div className="grid gap-3 lg:grid-cols-2">
                          <div>
                            <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">得分</label>
                            <input
                              value={q.score}
                              onChange={(e) => updateQuestion(selectedStudentIndex, q.questionId, "score", Number(e.target.value))}
                              type="number"
                              className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            />
                          </div>
                          <div>
                            <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">满分</label>
                            <div className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                              {q.maxScore}
                            </div>
                          </div>
                        </div>
                        <div>
                          <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">评语</label>
                          <textarea
                            value={q.feedback}
                            onChange={(e) => updateQuestion(selectedStudentIndex, q.questionId, "feedback", e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            rows={2}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">问题备注</label>
                          <textarea
                            value={q.reviewNote}
                            onChange={(e) => updateQuestion(selectedStudentIndex, q.questionId, "reviewNote", e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            rows={2}
                            placeholder="说明该题需要重新批改的原因。"
                          />
                        </div>
                      </div>

                      <div className="mt-4">
                        <button
                          onClick={() => toggleExpanded(selectedStudentIndex, q.questionId)}
                          className="text-xs font-semibold text-slate-600 hover:text-slate-800"
                        >
                          {isExpanded ? "收起评分依据" : "展开评分依据"}
                        </button>
                        {isExpanded && (
                          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-3">
                            {q.scoringPointResults && q.scoringPointResults.length > 0 ? (
                              q.scoringPointResults.map((spr, idx) => (
                                <div key={`${q.questionId}-spr-${idx}`} className="rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-600">
                                  <div className="flex items-center justify-between">
                                    <span className="font-semibold text-slate-700">
                                      {spr.pointId || `评分点 ${idx + 1}`}
                                    </span>
                                    <span>
                                      {spr.awarded ?? 0}/{spr.maxPoints ?? 0}
                                    </span>
                                  </div>
                                  {spr.description && <div className="mt-1">{spr.description}</div>}
                                  {spr.evidence && <div className="mt-1 text-[11px] text-slate-500">证据：{spr.evidence}</div>}
                                  {spr.rubricReference && (
                                    <div className="mt-1 text-[11px] text-slate-500">引用标准：{spr.rubricReference}</div>
                                  )}
                                  {spr.decision && (
                                    <div className="mt-1 text-[11px] text-slate-500">判断：{spr.decision}</div>
                                  )}
                                </div>
                              ))
                            ) : (
                              <div className="text-xs text-slate-400">暂无评分依据</div>
                            )}
                            {q.typoNotes && q.typoNotes.length > 0 && (
                              <div className="text-xs text-rose-600">错别字：{q.typoNotes.join("、")}</div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
