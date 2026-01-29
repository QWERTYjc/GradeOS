"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { gradingApi } from "@/services/api";
import { buildWsUrl } from "@/services/ws";
import { MathText } from "@/components/common/MathText";

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
  { id: "rubric_review", label: "Rubric Review" },
  { id: "grade_batch", label: "Student Grading" },
  { id: "logic_review", label: "Logic Review" },
  { id: "review", label: "Results Review" },
  { id: "export", label: "Export" },
];

const normalizeRubric = (raw: Record<string, unknown>): ParsedRubricDraft => {
  const rawQuestions = (raw?.questions as Array<Record<string, unknown>>) || [];
  const questions: RubricQuestionDraft[] = rawQuestions.map((q, idx: number) => {
    const questionId = String(q.questionId || q.question_id || q.id || idx + 1);
    const scoringPoints = ((q.scoringPoints as Array<Record<string, unknown>>) || (q.scoring_points as Array<Record<string, unknown>>) || []).map((sp, spIdx: number) => ({
      pointId: String(sp.pointId || sp.point_id || `${questionId}.${spIdx + 1}`),
      description: String(sp.description || ""),
      expectedValue: String(sp.expectedValue || sp.expected_value || ""),
      score: Number(sp.score ?? sp.maxScore ?? 0),
      isRequired: Boolean(sp.isRequired ?? sp.is_required ?? true),
      keywords: Array.isArray(sp.keywords)
        ? sp.keywords.map((k: unknown) => String(k))
        : typeof sp.keywords === "string"
          ? sp.keywords.split(",").map((v: string) => v.trim()).filter(Boolean)
          : [],
    }));

    const alternativeSolutions = ((q.alternativeSolutions as Array<Record<string, unknown>>) || (q.alternative_solutions as Array<Record<string, unknown>>) || []).map((alt) => ({
      description: (alt.description as string) || "",
      scoringCriteria: (alt.scoringCriteria || alt.scoring_criteria) as string || "",
      note: (alt.note as string) || "",
    }));

    return {
      questionId,
      maxScore: Number(q.maxScore ?? q.max_score ?? 0),
      questionText: String(q.questionText || q.question_text || ""),
      standardAnswer: String(q.standardAnswer || q.standard_answer || ""),
      gradingNotes: String(q.gradingNotes || q.grading_notes || ""),
      reviewNote: String(q.reviewNote || q.review_note || ""),
      scoringPoints,
      alternativeSolutions,
      criteria: Array.isArray(q.criteria) ? q.criteria : [],
      sourcePages: Array.isArray(q.sourcePages) ? q.sourcePages : Array.isArray(q.source_pages) ? q.source_pages : [],
    };
  });

  const totalQuestions = Number(raw?.totalQuestions ?? raw?.total_questions ?? questions.length);
  const totalScore = Number(
    raw?.totalScore ?? raw?.total_score ?? questions.reduce((sum, q) => sum + (q.maxScore || 0), 0)
  );

  return {
    totalQuestions,
    totalScore,
    generalNotes: String(raw?.generalNotes || raw?.general_notes || ""),
    rubricFormat: String(raw?.rubricFormat || raw?.rubric_format || "standard"),
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

export default function RubricReviewPage({ params }: { params: { batchId: string } }) {
  const router = useRouter();
  const { batchId } = params;
  const [rubricImages, setRubricImages] = useState<string[]>([]);
  const [rubricDraft, setRubricDraft] = useState<ParsedRubricDraft | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [globalNote, setGlobalNote] = useState("");
  const [compactView, setCompactView] = useState(true);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [streamText, setStreamText] = useState("");
  const streamBufferRef = useRef("");
  const streamFlushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    streamBufferRef.current = "";
    setStreamText("");
    if (streamFlushTimerRef.current) {
      clearTimeout(streamFlushTimerRef.current);
      streamFlushTimerRef.current = null;
    }
    const socket = new WebSocket(buildWsUrl(`/api/batch/ws/${batchId}`));
    const flushStream = () => {
      streamFlushTimerRef.current = null;
      setStreamText(streamBufferRef.current);
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "llm_stream_chunk" && message.nodeId === "rubric_parse") {
          const chunk = message.chunk || "";
          if (!chunk) return;
          const combined = streamBufferRef.current + chunk;
          streamBufferRef.current = combined.length > 12000 ? combined.slice(-12000) : combined;
          if (!streamFlushTimerRef.current) {
            streamFlushTimerRef.current = setTimeout(flushStream, 200);
          }
        }
      } catch (err) {
        console.warn("Failed to parse WS message", err);
      }
    };

    return () => {
      socket.close();
      if (streamFlushTimerRef.current) {
        clearTimeout(streamFlushTimerRef.current);
        streamFlushTimerRef.current = null;
      }
    };
  }, [batchId]);

  const toggleSelected = useCallback((questionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  }, []);

  const toggleExpanded = useCallback((questionId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  }, []);

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

  const addScoringPoint = useCallback((questionId: string) => {
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
  }, []);

  const removeScoringPoint = useCallback((questionId: string, index: number) => {
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
  }, []);

  const handleApprove = async () => {
    if (!batchId) return;
    setIsSubmitting(true);
    setSuccessMessage(null);
    setError(null);
    try {
      await gradingApi.submitRubricReview({ batch_id: batchId, action: "approve" });
      setSuccessMessage("已确认解析结果，批改流程继续进行。");
      router.push(`/console?batchId=${batchId}`);
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
      rubric_review_completed: "rubric_review",
      rubric_review_skipped: "rubric_review",
      grade_batch_completed: "grade_batch",
      cross_page_merge_completed: "grade_batch",
      index_merge_completed: "grade_batch",
      logic_review_completed: "logic_review",
      logic_review_skipped: "logic_review",
      review_completed: "review",
      completed: "export",
    };
    const stepId = mapping[currentStage] || "rubric_parse";
    const idx = workflowSteps.findIndex((s) => s.id === stepId);
    return idx >= 0 ? idx : 0;
  }, [currentStage]);

  const rubricImageItems = useMemo(() => {
    if (rubricImages.length === 0) return null;
    return rubricImages.map((img, idx) => (
      <div key={idx} className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="mb-2 text-xs font-semibold text-slate-500">Page {idx + 1}</div>
        <div className="aspect-[3/4] overflow-hidden rounded-xl bg-slate-50">
          <img
            src={img}
            alt={`Rubric page ${idx + 1}`}
            className="h-full w-full object-contain"
            loading="lazy"
            decoding="async"
          />
        </div>
      </div>
    ));
  }, [rubricImages]);

  const questionCards = useMemo(() => {
    if (!rubricDraft) return [];
    return rubricDraft.questions.map((q) => {
      const isSelected = selectedIds.has(q.questionId);
      const isExpanded = expandedIds.has(q.questionId);
      return (
        <div
          key={q.questionId}
          className={clsx(
            "rounded-2xl border border-slate-200 bg-white shadow-sm",
            compactView ? "p-4" : "p-6"
          )}
        >
          {compactView ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                    {q.questionId}
                  </div>
                  <div>
                    <div className="text-[10px] font-semibold text-slate-500">满分 {q.maxScore}</div>
                    <div className="text-xs font-semibold text-slate-800">题目 {q.questionId}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleExpanded(q.questionId)}
                    className="text-[10px] font-semibold text-slate-500 hover:text-slate-700"
                  >
                    {isExpanded ? "收起详情" : "展开详情"}
                  </button>
                  <label className="flex items-center gap-2 cursor-pointer rounded-full border border-slate-200 px-2 py-1 text-[10px] font-medium text-slate-500 hover:border-rose-200 hover:bg-rose-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelected(q.questionId)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-rose-500 focus:ring-rose-500"
                    />
                    <span className={clsx(isSelected ? "text-rose-500" : "text-slate-500")}>标记问题</span>
                  </label>
                </div>
              </div>

              <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">题目内容</div>
                <div className="mt-1 text-[13px] font-semibold text-slate-800 leading-snug">
                  <MathText className="whitespace-pre-wrap" text={q.questionText || "—"} />
                </div>
                <ul className="mt-3 space-y-1 text-[11px] text-slate-600 leading-snug list-disc pl-4">
                  {q.standardAnswer && (
                    <li>
                      标准答案：<MathText className="whitespace-pre-wrap" text={q.standardAnswer} />
                    </li>
                  )}
                  {q.gradingNotes && (
                    <li>
                      备注：<MathText className="whitespace-pre-wrap" text={q.gradingNotes} />
                    </li>
                  )}
                  {q.criteria && q.criteria.length > 0 && (
                    <li>评分要点：{q.criteria.join(" · ")}</li>
                  )}
                </ul>

                {q.scoringPoints.length > 0 && (
                  <div className="mt-3">
                    <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">评分点</div>
                    <div className="mt-2 space-y-1 text-[11px] text-slate-600 leading-snug">
                      {q.scoringPoints.map((sp) => (
                        <div key={sp.pointId} className="flex items-start gap-2">
                          <span className="font-mono text-slate-400">{sp.pointId}</span>
                          <span className="flex-1">
                            {sp.description || "—"}
                            {sp.expectedValue ? ` | 期望: ${sp.expectedValue}` : ""}
                            {sp.keywords && sp.keywords.length > 0 ? ` | 关键词: ${sp.keywords.join(", ")}` : ""}
                          </span>
                          <span className="font-semibold text-slate-700">{sp.score}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {isExpanded && (
                <div className="rounded-xl border border-slate-200 bg-white/80 p-3 space-y-3">
                  <div>
                    <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">解析问题备注</label>
                    <textarea
                      value={q.reviewNote}
                      onChange={(e) => updateQuestion(q.questionId, "reviewNote", e.target.value)}
                      className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                      rows={2}
                      placeholder="说明这题解析哪里有问题，便于重解析。"
                    />
                  </div>
                  {q.alternativeSolutions.length > 0 && (
                    <div className="text-[11px] text-slate-600 leading-snug">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">替代解法</div>
                      <ul className="mt-2 list-disc pl-4 space-y-1">
                        {q.alternativeSolutions.map((alt, idx) => (
                          <li key={`${q.questionId}-alt-${idx}`}>
                            <MathText className="whitespace-pre-wrap" text={alt.description} />
                            {alt.scoringCriteria ? ` | 评分条件: ${alt.scoringCriteria}` : ""}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="text-[11px] text-slate-500">
                    来源页：{q.sourcePages.length > 0 ? q.sourcePages.map((p) => p + 1).join(", ") : "未标注"}
                  </div>
                  {q.sourcePages.length > 0 && (
                    <div className="grid grid-cols-2 gap-2">
                      {q.sourcePages.map((pageIndex) => (
                        <div key={`${q.questionId}-page-${pageIndex}`} className="rounded-lg border border-slate-200 bg-white p-2">
                          <div className="text-[10px] text-slate-400 mb-1">Page {pageIndex + 1}</div>
                          {rubricImages[pageIndex] ? (
                            <img
                              src={rubricImages[pageIndex]}
                              alt={`Evidence ${pageIndex + 1}`}
                              className="h-28 w-full object-contain"
                              loading="lazy"
                              decoding="async"
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
          ) : (
            <>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-sm font-bold text-slate-700">
                    {q.questionId}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-500">满分 {q.maxScore}</div>
                    <div className="text-sm font-semibold text-slate-800">题目 {q.questionId}</div>
                  </div>
                </div>

                <label className="flex items-center gap-2 cursor-pointer rounded-full border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:border-rose-200 hover:bg-rose-50 transition-colors">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleSelected(q.questionId)}
                    className="h-4 w-4 rounded border-slate-300 text-rose-500 focus:ring-rose-500"
                  />
                  <span className={clsx(isSelected ? "text-rose-500" : "text-slate-500")}>标记问题</span>
                </label>
              </div>

              <div className="mt-5 grid gap-4">
                <div>
                  <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">题目内容</label>
                  <textarea
                    value={q.questionText}
                    onChange={(e) => updateQuestion(q.questionId, "questionText", e.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                    rows={2}
                  />
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">标准答案</label>
                    <textarea
                      value={q.standardAnswer}
                      onChange={(e) => updateQuestion(q.questionId, "standardAnswer", e.target.value)}
                      className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                      rows={2}
                    />
                  </div>
                  <div>
                    <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">满分</label>
                    <input
                      value={q.maxScore}
                      onChange={(e) => updateQuestion(q.questionId, "maxScore", Number(e.target.value))}
                      type="number"
                      className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">备注</label>
                  <textarea
                    value={q.gradingNotes}
                    onChange={(e) => updateQuestion(q.questionId, "gradingNotes", e.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="text-[11px] uppercase tracking-[0.2em] text-slate-400">解析问题备注</label>
                  <textarea
                    value={q.reviewNote}
                    onChange={(e) => updateQuestion(q.questionId, "reviewNote", e.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
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
                                loading="lazy"
                                decoding="async"
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
            </>
          )}
        </div>
      );
    });
  }, [
    rubricDraft,
    selectedIds,
    expandedIds,
    toggleSelected,
    toggleExpanded,
    updateQuestion,
    updateScoringPoint,
    addScoringPoint,
    removeScoringPoint,
    rubricImages,
    compactView,
  ]);

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
    <div className="flex h-screen w-full flex-col overflow-hidden bg-slate-50">
      {/* Header */}
      <header className="flex flex-none items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">批改标准解析确认</h1>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="font-mono">Run: {batchId}</span>
              <span>·</span>
              <span>{status || "running"}</span>
            </div>
          </div>
          {/* Stream Log Indicator */}
          <div className="h-8 max-w-[400px] overflow-hidden rounded-lg bg-slate-50 px-3 py-2 text-[10px] text-slate-400">
            {streamText ? (
              <span className="animate-pulse text-emerald-600">AI: {streamText.slice(-60)}</span>
            ) : (
              "Waiting for activity..."
            )}
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
            <h2 className="text-sm font-semibold text-slate-700">标准原件 ({rubricImages.length} 页)</h2>
            <div className="flex gap-2">
              {workflowSteps.map((step, idx) => (
                <div
                  key={step.id}
                  className={clsx(
                    "h-1.5 w-1.5 rounded-full",
                    idx <= stepIndex ? "bg-emerald-500" : "bg-slate-300"
                  )}
                  title={step.label}
                />
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-8">
            <div className="mx-auto max-w-3xl space-y-6">
              {rubricImages.length === 0 ? (
                <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-slate-300 text-sm text-slate-400">
                  无图片数据
                </div>
              ) : (
                rubricImages.map((img, idx) => (
                  <div key={idx} className="relative overflow-hidden rounded-sm shadow-sm transition-shadow hover:shadow-md bg-white">
                    <img
                      src={img}
                      alt={`Page ${idx + 1}`}
                      className="w-full object-contain"
                      loading="lazy"
                    />
                    <div className="absolute top-2 left-2 rounded bg-black/50 px-2 py-0.5 text-[10px] text-white">
                      P{idx + 1}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Pane: Rubric Form */}
        <div className="flex w-1/2 flex-col bg-white">
          <div className="flex flex-none flex-col gap-4 border-b border-slate-100 bg-white px-6 py-5">
            {/* Messages */}
            {(error || successMessage) && (
              <div className={clsx(
                "rounded-md px-3 py-2 text-xs",
                error ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
              )}>
                {error || successMessage}
              </div>
            )}

            {/* Global Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-slate-500">
                共 {rubricDraft.totalQuestions} 题，总分 <span className="font-semibold text-slate-900">{rubricDraft.totalScore}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCompactView((prev) => !prev)}
                  className={clsx(
                    "rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                    compactView
                      ? "border-slate-200 bg-slate-100 text-slate-600 hover:border-slate-300"
                      : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:border-emerald-300"
                  )}
                >
                  {compactView ? "切换到编辑模式" : "切换到紧凑模式"}
                </button>
                <button
                  onClick={handleReparse}
                  disabled={isSubmitting || selectedIds.size === 0}
                  className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 disabled:text-slate-300"
                >
                  重新解析选中项 ({selectedIds.size})
                </button>
              </div>
            </div>

            {/* Global Notes for Reparse */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <label className="mb-1 block text-[10px] font-medium uppercase text-slate-400">总体备注</label>
                <input
                  value={rubricDraft.generalNotes}
                  onChange={(e) => setRubricDraft({ ...rubricDraft, generalNotes: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                  placeholder="扣分规则等..."
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-medium uppercase text-slate-400">重解析说明</label>
                <input
                  value={globalNote}
                  onChange={(e) => setGlobalNote(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                  placeholder="告诉AI哪里解析错了..."
                />
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto bg-slate-50 p-8">
            <div className="space-y-8">
              {questionCards}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
