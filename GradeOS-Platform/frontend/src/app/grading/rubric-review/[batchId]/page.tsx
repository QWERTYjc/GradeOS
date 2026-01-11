"use client";

import React, { use, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { gradingApi } from "@/services/api";

type RubricScoringPointDraft = {
  pointId: string;
  description: string;
  expectedValue?: string;
  score: number;
  isRequired: boolean;
  keywords: string[];
};

type RubricAlternativeSolutionDraft = {
  description: string;
  scoringCriteria?: string;
  note?: string;
};

type RubricQuestionDraft = {
  questionId: string;
  maxScore: number;
  questionText: string;
  standardAnswer: string;
  gradingNotes: string;
  reviewNote: string;
  scoringPoints: RubricScoringPointDraft[];
  alternativeSolutions: RubricAlternativeSolutionDraft[];
  criteria: string[];
  sourcePages: number[];
};

type ParsedRubricDraft = {
  totalQuestions: number;
  totalScore: number;
  generalNotes: string;
  rubricFormat: string;
  questions: RubricQuestionDraft[];
};

const workflowSteps = [
  { id: "rubric_parse", label: "Rubric Parse" },
  { id: "grade_batch", label: "Batch Grading" },
  { id: "cross_page_merge", label: "Cross-Page Merge" },
  { id: "logic_review", label: "Logic Review" },
  { id: "index_merge", label: "Result Merge" },
  { id: "export", label: "Export" },
];

const normalizeRubric = (raw: any): ParsedRubricDraft => {
  const rawQuestions = raw?.questions || [];
  const questions: RubricQuestionDraft[] = rawQuestions.map((q: any, idx: number) => {
    const questionId = String(q.questionId || q.question_id || q.id || idx + 1);
    const scoringPoints = (q.scoringPoints || q.scoring_points || []).map((sp: any, spIdx: number) => ({
      pointId: String(sp.pointId || sp.point_id || `${questionId}.${spIdx + 1}`),
      description: sp.description || "",
      expectedValue: sp.expectedValue || sp.expected_value || "",
      score: Number(sp.score ?? sp.maxScore ?? 0),
      isRequired: Boolean(sp.isRequired ?? sp.is_required ?? true),
      keywords: Array.isArray(sp.keywords)
        ? sp.keywords
        : typeof sp.keywords === "string"
          ? sp.keywords.split(",").map((v: string) => v.trim()).filter(Boolean)
          : [],
    }));

    const alternativeSolutions = (q.alternativeSolutions || q.alternative_solutions || []).map((alt: any) => ({
      description: alt.description || "",
      scoringCriteria: alt.scoringCriteria || alt.scoring_criteria || "",
      note: alt.note || "",
    }));

    return {
      questionId,
      maxScore: Number(q.maxScore ?? q.max_score ?? 0),
      questionText: q.questionText || q.question_text || "",
      standardAnswer: q.standardAnswer || q.standard_answer || "",
      gradingNotes: q.gradingNotes || q.grading_notes || "",
      reviewNote: q.reviewNote || q.review_note || "",
      scoringPoints,
      alternativeSolutions,
      criteria: q.criteria || [],
      sourcePages: q.sourcePages || q.source_pages || [],
    };
  });

  const totalQuestions = Number(raw?.totalQuestions ?? raw?.total_questions ?? questions.length);
  const totalScore = Number(
    raw?.totalScore ?? raw?.total_score ?? questions.reduce((sum, q) => sum + (q.maxScore || 0), 0)
  );

  return {
    totalQuestions,
    totalScore,
    generalNotes: raw?.generalNotes || raw?.general_notes || "",
    rubricFormat: raw?.rubricFormat || raw?.rubric_format || "standard",
    questions,
  };
};

const buildRubricPayload = (draft: ParsedRubricDraft) => ({
  totalQuestions: draft.questions.length,
  totalScore: draft.questions.reduce((sum, q) => sum + (q.maxScore || 0), 0),
  generalNotes: draft.generalNotes,
  rubricFormat: draft.rubricFormat,
  questions: draft.questions.map((q) => ({
    questionId: q.questionId,
    maxScore: q.maxScore,
    questionText: q.questionText,
    standardAnswer: q.standardAnswer,
    gradingNotes: q.gradingNotes,
    criteria: q.criteria,
    sourcePages: q.sourcePages,
    scoringPoints: q.scoringPoints.map((sp) => ({
      pointId: sp.pointId,
      description: sp.description,
      expectedValue: sp.expectedValue,
      score: sp.score,
      isRequired: sp.isRequired,
      keywords: sp.keywords,
    })),
    alternativeSolutions: q.alternativeSolutions.map((alt) => ({
      description: alt.description,
      scoringCriteria: alt.scoringCriteria,
      note: alt.note,
    })),
  })),
});

export default function RubricReviewPage({ params }: { params: Promise<{ batchId: string }> }) {
  const router = useRouter();
  const { batchId } = use(params);
  const [rubricImages, setRubricImages] = useState<string[]>([]);
  const [rubricDraft, setRubricDraft] = useState<ParsedRubricDraft | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [globalNote, setGlobalNote] = useState("");
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [streamText, setStreamText] = useState("");

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    gradingApi
      .getRubricReviewContext(batchId)
      .then((data) => {
        if (!active) return;
        setStatus(data.status || null);
        setCurrentStage(data.current_stage || null);
        const parsed = normalizeRubric(data.parsed_rubric || {});
        setRubricDraft(parsed);
        const images = (data.rubric_images || []).map((img) =>
          img.startsWith("data:") ? img : `data:image/jpeg;base64,${img}`
        );
        setRubricImages(images);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load rubric context.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [batchId]);

  useEffect(() => {
    const wsBase = process.env.NEXT_PUBLIC_WS_BASE_URL || "ws://127.0.0.1:8001";
    const socket = new WebSocket(`${wsBase}/batch/ws/${batchId}`);

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "llm_stream_chunk" && message.nodeId === "rubric_parse") {
          const chunk = message.chunk || "";
          if (!chunk) return;
          setStreamText((prev) => {
            const combined = prev + chunk;
            return combined.length > 12000 ? combined.slice(-12000) : combined;
          });
        }
      } catch (err) {
        console.warn("Failed to parse WS message", err);
      }
    };

    return () => {
      socket.close();
    };
  }, [batchId]);

  const toggleSelected = (questionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  };

  const toggleExpanded = (questionId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  };

  const updateQuestion = useCallback((questionId: string, field: keyof RubricQuestionDraft, value: any) => {
    setRubricDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        questions: prev.questions.map((q) => (q.questionId === questionId ? { ...q, [field]: value } : q)),
      };
    });
  }, []);

  const updateScoringPoint = useCallback(
    (questionId: string, index: number, field: keyof RubricScoringPointDraft, value: any) => {
      setRubricDraft((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          questions: prev.questions.map((q) => {
            if (q.questionId !== questionId) return q;
            const scoringPoints = q.scoringPoints.map((sp, idx) =>
              idx === index ? { ...sp, [field]: value } : sp
            );
            return { ...q, scoringPoints };
          }),
        };
      });
    },
    []
  );

  const addScoringPoint = (questionId: string) => {
    setRubricDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        questions: prev.questions.map((q) => {
          if (q.questionId !== questionId) return q;
          const nextIndex = q.scoringPoints.length + 1;
          const newPoint: RubricScoringPointDraft = {
            pointId: `${questionId}.${nextIndex}`,
            description: "",
            expectedValue: "",
            score: 0,
            isRequired: true,
            keywords: [],
          };
          return { ...q, scoringPoints: [...q.scoringPoints, newPoint] };
        }),
      };
    });
  };

  const removeScoringPoint = (questionId: string, index: number) => {
    setRubricDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        questions: prev.questions.map((q) => {
          if (q.questionId !== questionId) return q;
          const scoringPoints = q.scoringPoints.filter((_, idx) => idx !== index);
          return { ...q, scoringPoints };
        }),
      };
    });
  };

  const handleApprove = async () => {
    if (!batchId) return;
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    try {
      await gradingApi.submitRubricReview({ batch_id: batchId, action: "approve" });
      setSuccessMessage("已确认解析结果，批改流程继续进行。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitUpdate = async () => {
    if (!batchId || !rubricDraft) return;
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    try {
      await gradingApi.submitRubricReview({
        batch_id: batchId,
        action: "update",
        parsed_rubric: buildRubricPayload(rubricDraft),
      });
      setSuccessMessage("已提交修正，批改流程继续进行。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReparse = async () => {
    if (!batchId || selectedIds.size === 0) return;
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    const noteLines: string[] = [];
    const trimmedGlobal = globalNote.trim();
    if (trimmedGlobal) {
      noteLines.push(trimmedGlobal);
    }
    if (rubricDraft) {
      rubricDraft.questions.forEach((q) => {
        if (!selectedIds.has(q.questionId)) return;
        const note = q.reviewNote.trim();
        if (note) {
          noteLines.push(`Q${q.questionId}: ${note}`);
        }
      });
    }
    try {
      await gradingApi.submitRubricReview({
        batch_id: batchId,
        action: "reparse",
        selected_question_ids: Array.from(selectedIds),
        notes: noteLines.join("\n"),
      });
      setSuccessMessage("已提交重解析请求，请稍后刷新查看结果。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  const stepIndex = useMemo(() => {
    if (!currentStage) return 0;
    const mapping: Record<string, string> = {
      rubric_parse_completed: "rubric_parse",
      rubric_review_completed: "rubric_parse",
      rubric_review_skipped: "rubric_parse",
      grade_batch_completed: "grade_batch",
      cross_page_merge_completed: "cross_page_merge",
      logic_review_completed: "logic_review",
      index_merge_completed: "index_merge",
      completed: "export",
    };
    const stepId = mapping[currentStage] || "rubric_parse";
    const idx = workflowSteps.findIndex((s) => s.id === stepId);
    return idx >= 0 ? idx : 0;
  }, [currentStage]);

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50">
        <div className="text-slate-500 text-sm">Loading rubric review...</div>
      </div>
    );
  }

  if (!rubricDraft) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50">
        <div className="text-slate-500 text-sm">No rubric data available.</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-slate-50 via-sky-50 to-amber-50">
      <div className="mx-auto max-w-[1400px] px-6 py-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Rubric Review</p>
            <h1 className="text-3xl font-semibold text-slate-900">
              批改标准解析确认
            </h1>
            <div className="mt-2 text-sm text-slate-500">
              Batch: {batchId} · Status: {status || "running"}
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
                <h2 className="text-lg font-semibold text-slate-800">批改标准原图</h2>
                <p className="text-xs text-slate-500">{rubricImages.length} pages</p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>Workflow Preview</span>
                <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              </div>
            </div>
            <div className="flex flex-col gap-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-3">
                <div className="flex flex-wrap gap-3">
                  {workflowSteps.map((step, idx) => (
                    <div
                      key={step.id}
                      className={clsx(
                        "flex items-center gap-2 rounded-full border px-3 py-1 text-xs",
                        idx <= stepIndex
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-slate-200 bg-slate-50 text-slate-400"
                      )}
                    >
                      <span className="h-2 w-2 rounded-full bg-current opacity-70"></span>
                      {step.label}
                    </div>
                  ))}
                </div>
                <div className="mt-3 text-xs text-slate-500">当前阶段：{currentStage || "waiting for review"}</div>
              </div>

              <div className="max-h-[640px] overflow-y-auto space-y-4 pr-2">
                {rubricImages.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
                    No rubric images available.
                  </div>
                )}
                {rubricImages.map((img, idx) => (
                  <div key={idx} className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="mb-2 text-xs font-semibold text-slate-500">Page {idx + 1}</div>
                    <div className="aspect-[3/4] overflow-hidden rounded-xl bg-slate-50">
                      <img src={img} alt={`Rubric page ${idx + 1}`} className="h-full w-full object-contain" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-xl backdrop-blur">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-800">解析结果</h2>
                  <p className="text-xs text-slate-500">
                    {rubricDraft.totalQuestions} 题 · {rubricDraft.totalScore} 分
                  </p>
                </div>
                <button
                  onClick={handleReparse}
                  disabled={isSubmitting || selectedIds.size === 0}
                  className="rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-600 hover:border-slate-400 disabled:opacity-50"
                >
                  重新验证所选
                </button>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <label className="text-xs font-semibold text-slate-500">总体备注 / 扣分规则</label>
                <textarea
                  value={rubricDraft.generalNotes}
                  onChange={(e) => setRubricDraft({ ...rubricDraft, generalNotes: e.target.value })}
                  className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                  rows={3}
                />
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <label className="text-xs font-semibold text-slate-500">问题说明（用于重解析）</label>
                <textarea
                  value={globalNote}
                  onChange={(e) => setGlobalNote(e.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                  rows={3}
                  placeholder="说明哪些解析项有问题、希望如何修正。"
                />
              </div>

              <div className="max-h-[620px] overflow-y-auto space-y-4 pr-2">
                {rubricDraft.questions.map((q) => {
                  const isSelected = selectedIds.has(q.questionId);
                  const isExpanded = expandedIds.has(q.questionId);
                  return (
                    <div key={q.questionId} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-800">
                            题号 {q.questionId} · {q.maxScore} 分
                          </div>
                          <div className="text-xs text-slate-400">可勾选有问题并添加备注</div>
                        </div>
                        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelected(q.questionId)}
                            className="h-4 w-4 rounded border-slate-300 text-slate-900"
                          />
                          有问题
                        </label>
                      </div>

                      <div className="mt-4 grid gap-3">
                        <div>
                          <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">题目内容</label>
                          <textarea
                            value={q.questionText}
                            onChange={(e) => updateQuestion(q.questionId, "questionText", e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            rows={2}
                          />
                        </div>
                        <div className="grid gap-3 lg:grid-cols-2">
                          <div>
                            <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">标准答案</label>
                            <textarea
                              value={q.standardAnswer}
                              onChange={(e) => updateQuestion(q.questionId, "standardAnswer", e.target.value)}
                              className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                              rows={2}
                            />
                          </div>
                          <div>
                            <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">满分</label>
                            <input
                              value={q.maxScore}
                              onChange={(e) => updateQuestion(q.questionId, "maxScore", Number(e.target.value))}
                              type="number"
                              className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">备注</label>
                          <textarea
                            value={q.gradingNotes}
                            onChange={(e) => updateQuestion(q.questionId, "gradingNotes", e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            rows={2}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">解析问题备注</label>
                          <textarea
                            value={q.reviewNote}
                            onChange={(e) => updateQuestion(q.questionId, "reviewNote", e.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                            rows={2}
                            placeholder="说明这题解析哪里有问题，便于重解析。"
                          />
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="flex items-center justify-between">
                          <div className="text-xs font-semibold text-slate-500">评分点</div>
                          <button
                            onClick={() => addScoringPoint(q.questionId)}
                            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:border-slate-400"
                          >
                            添加评分点
                          </button>
                        </div>
                        <div className="mt-3 space-y-3">
                          {q.scoringPoints.map((sp, idx) => (
                            <div key={sp.pointId} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                              <div className="flex items-center justify-between">
                                <div className="text-xs font-semibold text-slate-600">点 {sp.pointId}</div>
                                <button
                                  onClick={() => removeScoringPoint(q.questionId, idx)}
                                  className="text-[11px] text-rose-500 hover:text-rose-600"
                                >
                                  删除
                                </button>
                              </div>
                              <div className="mt-2 grid gap-2">
                                <input
                                  value={sp.description}
                                  onChange={(e) => updateScoringPoint(q.questionId, idx, "description", e.target.value)}
                                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                                  placeholder="评分点描述"
                                />
                                <div className="grid gap-2 md:grid-cols-3">
                                  <input
                                    value={sp.expectedValue}
                                    onChange={(e) => updateScoringPoint(q.questionId, idx, "expectedValue", e.target.value)}
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                                    placeholder="期望值"
                                  />
                                  <input
                                    value={sp.score}
                                    onChange={(e) => updateScoringPoint(q.questionId, idx, "score", Number(e.target.value))}
                                    type="number"
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                                    placeholder="分值"
                                  />
                                  <input
                                    value={sp.keywords.join(", ")}
                                    onChange={(e) =>
                                      updateScoringPoint(
                                        q.questionId,
                                        idx,
                                        "keywords",
                                        e.target.value
                                          .split(",")
                                          .map((v) => v.trim())
                                          .filter(Boolean)
                                      )
                                    }
                                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                                    placeholder="关键词"
                                  />
                                </div>
                                <label className="flex items-center gap-2 text-xs text-slate-500">
                                  <input
                                    type="checkbox"
                                    checked={sp.isRequired}
                                    onChange={(e) => updateScoringPoint(q.questionId, idx, "isRequired", e.target.checked)}
                                    className="h-4 w-4 rounded border-slate-300 text-slate-900"
                                  />
                                  必要项
                                </label>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="mt-4">
                        <button
                          onClick={() => toggleExpanded(q.questionId)}
                          className="text-xs font-semibold text-slate-600 hover:text-slate-800"
                        >
                          {isExpanded ? "收起解析依据" : "展开解析依据"}
                        </button>
                        {isExpanded && (
                          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div className="text-[11px] text-slate-500">
                              来源页：{q.sourcePages.length > 0 ? q.sourcePages.map((p) => p + 1).join(", ") : "未标注"}
                            </div>
                            {q.sourcePages.length > 0 && (
                              <div className="mt-3 grid grid-cols-2 gap-2">
                                {q.sourcePages.map((pageIndex) => (
                                  <div key={`${q.questionId}-page-${pageIndex}`} className="rounded-lg border border-slate-200 bg-white p-2">
                                    <div className="text-[10px] text-slate-400 mb-1">Page {pageIndex + 1}</div>
                                    {rubricImages[pageIndex] ? (
                                      <img
                                        src={rubricImages[pageIndex]}
                                        alt={`Evidence ${pageIndex + 1}`}
                                        className="h-32 w-full object-contain"
                                      />
                                    ) : (
                                      <div className="text-xs text-slate-400">No image</div>
                                    )}
                                  </div>
                                ))}
                              </div>
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

        <div className="mt-8 rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-xl">
          <h3 className="text-sm font-semibold text-slate-700">实时解析流</h3>
          <div className="mt-3 max-h-[240px] overflow-y-auto whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">
            {streamText || "Waiting for AI streams..."}
          </div>
        </div>
      </div>
    </div>
  );
}
