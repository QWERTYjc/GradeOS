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
    <div className="flex h-screen w-full flex-col overflow-hidden bg-slate-50">
      {/* Header */}
      <header className="flex flex-none items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">批改结果确认</h1>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="font-mono">Run: {batchId}</span>
              <span>·</span>
              <span>{status || "running"}</span>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => router.push(`/console?batchId=${batchId}`)}
            className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            返回
          </button>
          <button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
          >
            确认无误
          </button>
          <button
            onClick={handleSubmitUpdate}
            disabled={isSubmitting}
            className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-60"
          >
            提交修正
          </button>
        </div>
      </header>

      {/* Main Content Split View */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Pane: Images */}
        <div className="flex w-1/2 flex-col border-r border-slate-200 bg-slate-100/50">
          <div className="flex flex-none items-center justify-between border-b border-slate-200 px-4 py-3 bg-white/50 backdrop-blur-sm">
            <h2 className="text-sm font-semibold text-slate-700">学生作答 ({pageIndices.length} 页)</h2>
            <div className="text-xs text-slate-500 font-medium">
              {currentStudent.studentName}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-8">
            <div className="mx-auto max-w-3xl space-y-6">
              {pageIndices.length === 0 ? (
                <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-slate-300 text-sm text-slate-400">
                  无图片数据
                </div>
              ) : (
                pageIndices.map((pageIndex) => (
                  <div key={pageIndex} className="relative overflow-hidden rounded-sm shadow-sm transition-shadow hover:shadow-md bg-white">
                    {answerImages[pageIndex] ? (
                      <img
                        src={answerImages[pageIndex]}
                        alt={`Page ${pageIndex + 1}`}
                        className="w-full object-contain"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-[800px] w-full items-center justify-center bg-slate-100 text-slate-400">No Image</div>
                    )}
                    <div className="absolute top-2 left-2 rounded bg-black/50 px-2 py-0.5 text-[10px] text-white">
                      P{pageIndex + 1}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Pane: Results Form */}
        <div className="flex w-1/2 flex-col bg-white">
          <div className="flex flex-none flex-col gap-4 border-b border-slate-100 px-6 py-4">
            {/* Messages */}
            {(error || successMessage) && (
              <div className={clsx(
                "rounded-md px-3 py-2 text-xs",
                error ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
              )}>
                {error || successMessage}
              </div>
            )}

            {/* Student Selector & Score */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm text-slate-500">
                  得分 <span className="text-lg font-bold text-slate-900">{totalScore}</span> <span className="text-slate-400">/ {totalMax}</span>
                </div>
                <button
                  onClick={handleRegrade}
                  disabled={isSubmitting || selectedQuestionKeys.size === 0}
                  className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 disabled:text-slate-300"
                >
                  重新批改选中项
                </button>
              </div>

              <div className="flex flex-wrap gap-2 pb-2">
                {resultsDraft.map((student, idx) => (
                  <button
                    key={`${student.studentName}-${idx}`}
                    onClick={() => setSelectedStudentIndex(idx)}
                    className={clsx(
                      "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                      idx === selectedStudentIndex
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    )}
                  >
                    {student.studentName}
                  </button>
                ))}
              </div>
            </div>

            {/* Global Notes */}
            <div>
              <input
                value={globalNote}
                onChange={(e) => setGlobalNote(e.target.value)}
                className="w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                placeholder="说明需要重新批改的原因（全局备注）..."
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto bg-slate-50/30 p-6">
            <div className="space-y-0 divide-y divide-slate-100 border border-slate-100 bg-white shadow-sm rounded-lg overflow-hidden">
              {currentStudent.questionResults.map((q) => {
                const key = `${selectedStudentIndex}:${q.questionId}`;
                const isSelected = selectedQuestionKeys.has(key);
                const isExpanded = expandedQuestionKeys.has(key);
                return (
                  <div key={q.questionId} className={clsx("bg-white transition-colors hover:bg-slate-50/50", isSelected && "bg-rose-50/30")}>
                    <div className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        {/* Question Header */}
                        <div className="flex flex-1 flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <span className="flex h-6 w-6 items-center justify-center rounded bg-slate-100 text-[10px] font-bold text-slate-600">
                              {q.questionId}
                            </span>
                            <div className="flex items-baseline gap-1 text-sm font-medium text-slate-900">
                              <input
                                value={q.score}
                                onChange={(e) => updateQuestion(selectedStudentIndex, q.questionId, "score", Number(e.target.value))}
                                type="number"
                                className="w-12 rounded border-none bg-transparent p-0 text-right font-bold hover:bg-slate-100 focus:ring-0"
                              />
                              <span className="text-slate-400 text-xs">/ {q.maxScore}</span>
                            </div>
                          </div>
                          {/* Feedback */}
                          <div className="mt-2 text-sm text-slate-600">
                            <textarea
                              value={q.feedback}
                              onChange={(e) => updateQuestion(selectedStudentIndex, q.questionId, "feedback", e.target.value)}
                              className="w-full resize-none bg-transparent text-sm leading-relaxed focus:outline-none focus:ring-0"
                              rows={Math.max(2, Math.ceil(q.feedback.length / 50))}
                            />
                          </div>
                        </div>

                        {/* Controls */}
                        <div className="flex flex-col items-end gap-2">
                          <label className="flex cursor-pointer items-center gap-1.5 rounded-full px-2 py-1 hover:bg-rose-100/50">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelected(selectedStudentIndex, q.questionId)}
                              className="h-3.5 w-3.5 rounded border-slate-300 text-rose-500 focus:ring-rose-500"
                            />
                            <span className={clsx("text-[10px] font-medium", isSelected ? "text-rose-500" : "text-slate-400")}>
                              标记
                            </span>
                          </label>
                          <button
                            onClick={() => toggleExpanded(selectedStudentIndex, q.questionId)}
                            className="text-[10px] font-medium text-slate-400 hover:text-slate-600"
                          >
                            {isExpanded ? "收起详情" : "详情"}
                          </button>
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && (
                        <div className="mt-4 border-t border-slate-100 pt-3">
                          {/* Review Note */}
                          <div className="mb-3">
                            <label className="mb-1 block text-[10px] font-medium uppercase text-slate-400">修正说明</label>
                            <textarea
                              value={q.reviewNote}
                              onChange={(e) => updateQuestion(selectedStudentIndex, q.questionId, "reviewNote", e.target.value)}
                              className="w-full rounded border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs focus:border-emerald-500 focus:outline-none"
                              rows={2}
                              placeholder="需重改的原因..."
                            />
                          </div>

                          {/* Scoring Points */}
                          <div className="grid gap-2 text-xs text-slate-600">
                            {q.scoringPointResults?.map((spr, idx) => (
                              <div key={idx} className="flex gap-2 rounded bg-slate-50 p-2">
                                <div className={clsx("h-1.5 w-1.5 flex-none rounded-full mt-1.5", spr.awarded ? "bg-emerald-400" : "bg-slate-300")} />
                                <div className="flex-1 space-y-1">
                                  <div className="flex justify-between font-medium">
                                    <span>{spr.description || "评分点"}</span>
                                    <span>{spr.awarded}/{spr.maxPoints}</span>
                                  </div>
                                  {spr.evidence && <div className="text-slate-500">引证: {spr.evidence}</div>}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
