'use client';

import React, { useState, useContext, useMemo, useEffect, useCallback } from 'react';
import { useConsoleStore, StudentResult, QuestionResult } from '@/store/consoleStore';
import clsx from 'clsx';
import { ArrowLeft, ChevronDown, ChevronUp, CheckCircle, XCircle, Download, GitMerge, AlertCircle, Layers, FileText, Info, X, AlertTriangle, BookOpen, ListOrdered, Loader2, Shield, Pencil, Target, BrainCircuit } from 'lucide-react';
import { CrownOutlined, BarChartOutlined, UsergroupAddOutlined, CheckCircleOutlined, ExclamationCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { Popover } from 'antd';
import { motion, AnimatePresence } from 'framer-motion';
import { RubricOverview } from './RubricOverview';
import { GlassCard } from '@/components/design-system/GlassCard';
import { AppContext, AppContextType } from '../bookscan/AppContext';
import { MathText } from '@/components/common/MathText';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { gradingApi } from '@/services/api';
import type { VisualAnnotation } from '@/types/annotation';
import AnnotationCanvas from '@/components/grading/AnnotationCanvas';
import AnnotationEditor from '@/components/grading/AnnotationEditor';

interface ResultCardProps {
    result: StudentResult;
    rank: number;
    onExpand: () => void;
    isExpanded: boolean;
}

interface ResultsViewProps {
    /** 是否默认展开题目详情（用于批改历史页面） */
    defaultExpandDetails?: boolean;
    /** 隐藏批改透明度区块 */
    hideGradingTransparency?: boolean;
    studentOnlyMode?: boolean;
    /** ????????? grading_history_id????? submissionId=batch_id? */
    annotationHistoryId?: string;
}

const LOW_CONFIDENCE_THRESHOLD = 0.7;

type ReviewReasonMeta = {
    title: string;
    hint?: string;
};

const REVIEW_REASON_META: Record<string, ReviewReasonMeta> = {
    low_confidence: {
        title: '低置信度',
        hint: '模型对给分存在不确定性，建议优先复核证据引用与评分标准是否匹配。',
    },
    full_marks_low_confidence: {
        title: '满分但置信度低',
        hint: '通常是因为缺少得分点拆分/证据/标准引用，导致虽然给了满分但不可复核；需要补齐分步明细或人工校验。',
    },
    missing_scoring_points: {
        title: '有总分但缺少得分点拆分',
        hint: '对应 “Scores available but step breakdown missing”：有题目总分，但缺少每个得分点/步骤的 awarded 明细，前端无法显示“哪一步多少分”。',
    },
    missing_rubric_reference: {
        title: '缺少评分标准引用',
        hint: '给分时未明确引用评分标准条目（rubric_reference）；需要补齐标准引用以便复核与回溯。',
    },
    missing_evidence_awarded_positive: {
        title: '给分但证据缺失',
        hint: '存在 awarded > 0 的得分点，但 evidence 为空或是占位文本；需要核验原文证据，否则该点不应得分。',
    },
    missing_evidence: {
        title: '证据缺失',
        hint: '得分点 evidence 为空或是占位文本；建议补齐可核验的原文引用。',
    },
    missing_point_id: {
        title: '得分点编号缺失',
        hint: 'scoring_point_results 缺少 point_id，导致无法与评分标准对齐定位；需要补齐编号。',
    },
    point_sum_mismatch: {
        title: '得分点之和与题目分不一致',
        hint: 'scoring_point_results.awarded 之和与题目 score 不一致；需核对各得分点并重算总分。',
    },
    score_out_of_bounds: {
        title: '分数越界',
        hint: '题目得分出现 < 0 或 > 满分的情况；需要修正到合法范围。',
    },
    zero_marks_low_confidence: {
        title: '0分但置信度低',
        hint: '该题给了0分但模型并不确定；需要核对是否漏判有效步骤或证据位置。',
    },
    alternative_solution_used: {
        title: '使用了另类解法',
        hint: '学生解法与标准步骤不同但可能正确；需要按评分标准确认是否符合给分条件。',
    },
    logic_review_adjusted: {
        title: '逻辑复核已修正',
        hint: '该题结果经过逻辑复核修正；可重点查看被修正的得分点与原因。',
    },
};

const getReviewReasonMeta = (reason: string): ReviewReasonMeta | null => {
    const key = (reason || '').trim();
    if (!key) return null;
    const direct = REVIEW_REASON_META[key];
    if (direct) return direct;

    const lower = key.toLowerCase();
    if (lower.includes('scores available') && lower.includes('step breakdown') && lower.includes('missing')) {
        return REVIEW_REASON_META.missing_scoring_points;
    }
    if (lower.includes('step breakdown') && lower.includes('missing')) {
        return REVIEW_REASON_META.missing_scoring_points;
    }
    if (lower.includes('full') && lower.includes('marks') && lower.includes('low') && lower.includes('confidence')) {
        return REVIEW_REASON_META.full_marks_low_confidence;
    }
    return null;
};

type PageAnnotation = VisualAnnotation & {
    id?: string;
    page_index?: number;
};

type AnnotationEditorPayload = {
    annotation_type: string;
    bounding_box: { x_min: number; y_min: number; x_max: number; y_max: number };
    text: string;
    color: string;
    question_id: string;
    scoring_point_id: string;
};

type ReviewQuestionDraft = {
    questionId: string;
    score: number;
    maxScore: number;
    feedback: string;
    pageIndices?: number[];
    reviewNote: string;
};

type ReviewStudentDraft = {
    studentName: string;
    score: number;
    maxScore: number;
    startPage?: number;
    endPage?: number;
    questionResults: ReviewQuestionDraft[];
};

const buildReviewDraft = (results: StudentResult[]): ReviewStudentDraft[] => (
    results.map((student) => ({
        studentName: student.studentName,
        score: student.score,
        maxScore: student.maxScore,
        startPage: student.startPage,
        endPage: student.endPage,
        questionResults: (student.questionResults || []).map((q) => ({
            questionId: q.questionId,
            score: q.score,
            maxScore: q.maxScore,
            feedback: q.feedback || '',
            pageIndices: q.pageIndices || [],
            reviewNote: '',
        })),
    }))
);

const buildResultsOverridePayload = (draft: ReviewStudentDraft[]) => (
    draft.map((student) => ({
        studentKey: student.studentName,
        questionResults: student.questionResults.map((q) => ({
            questionId: q.questionId,
            score: q.score,
            feedback: q.feedback,
        })),
    }))
);

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

type LLMConfession = {
    risks?: string[];
    uncertainties?: string[];
    blindSpots?: string[];
    needsReview?: string[];
    confidence?: number;
    selfReviewed?: boolean;
    selfReviewApplied?: boolean;
};

type QuestionConfession = {
    risk?: string;
    uncertainty?: string;
};

type RubricQuestionDraft = {
    questionId: string;
    maxScore: number;
    questionText: string;
    standardAnswer: string;
    gradingNotes: string;
    reviewNote: string;
    confession?: QuestionConfession;
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
    confession?: LLMConfession;
    selfReviewChanges?: string[];
    questions: RubricQuestionDraft[];
};

const normalizeRubricDraft = (raw: any): ParsedRubricDraft => {
    const rawQuestions = raw?.questions || [];
    const questions: RubricQuestionDraft[] = rawQuestions.map((q: any, idx: number) => {
        const questionId = String(q.questionId || q.question_id || q.id || idx + 1);
        const rawConfession = q?.confession || {};
        const confession: QuestionConfession = {
            risk: String(rawConfession.risk || ""),
            uncertainty: String(rawConfession.uncertainty || ""),
        };
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
            confession,
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

    const rawConfession = raw?.confession || {};
    const confession: LLMConfession = {
        risks: Array.isArray(rawConfession.risks) ? rawConfession.risks : [],
        uncertainties: Array.isArray(rawConfession.uncertainties) ? rawConfession.uncertainties : [],
        blindSpots: Array.isArray(rawConfession.blindSpots || rawConfession.blind_spots)
            ? (rawConfession.blindSpots || rawConfession.blind_spots)
            : [],
        needsReview: Array.isArray(rawConfession.needsReview || rawConfession.needs_review)
            ? (rawConfession.needsReview || rawConfession.needs_review)
            : [],
        confidence: Number(rawConfession.confidence ?? 1),
        selfReviewed: Boolean(rawConfession.selfReviewed ?? rawConfession.self_reviewed ?? false),
        selfReviewApplied: Boolean(rawConfession.selfReviewApplied ?? rawConfession.self_review_applied ?? false),
    };

    return {
        totalQuestions,
        totalScore,
        generalNotes: raw?.generalNotes || raw?.general_notes || "",
        rubricFormat: raw?.rubricFormat || raw?.rubric_format || "standard",
        confession,
        selfReviewChanges: Array.isArray(raw?.self_review_changes) ? raw.self_review_changes : [],
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

const formatStudentText = (text: string) => {
    const raw = (text || '').toString();
    let normalized = raw.replace(/\r\n/g, '\n').trim();
    if (!normalized) return '';

    // Heuristic formatting for OCR / single-line math solutions.
    // Only apply when the text is basically one long line (to avoid destroying intentional formatting).
    const hasBlankLines = /\n\s*\n/.test(normalized);
    const newlineCount = (normalized.match(/\n/g) || []).length;
    const looksLikeOneLine = !hasBlankLines && newlineCount <= 1;
    if (looksLikeOneLine && normalized.length > 140) {
        // Paragraph breaks for common step markers: "a) ...", "1) ...", "1. ..."
        normalized = normalized.replace(/(^|[.;])\s*([a-hA-H])\)\s*/g, (_m, sep, label) => (
            sep ? `${sep}\n\n${label}) ` : `${label}) `
        ));
        normalized = normalized.replace(/(^|[.;])\s*(\d{1,2})\)\s*/g, (_m, sep, num) => (
            sep ? `${sep}\n\n${num}) ` : `${num}) `
        ));
        normalized = normalized.replace(
            /(^|[.;])(\s*)(\d{1,2})\.\s*/g,
            (m, sep, ws, num, offset, str) => {
                // Avoid treating decimals like `53.13` as numbered steps (`13.`).
                if (sep === '.' && ws === '' && typeof offset === 'number' && offset > 0) {
                    const prev = String(str)[offset - 1];
                    if (prev >= '0' && prev <= '9') return m;
                }
                return sep ? `${sep}\n\n${num}. ` : `${num}. `;
            }
        );

        // Soft line breaks for readability.
        normalized = normalized.replace(/;\s+/g, ';\n');
        normalized = normalized.replace(/\.\s+(?=[A-Za-z(])/g, '.\n');
    }

    // Avoid excessive whitespace
    normalized = normalized.replace(/\n{3,}/g, '\n\n');
    return normalized;
};

const splitParagraphs = (text: string) => {
    const normalized = formatStudentText(text);
    if (!normalized) return [];
    return normalized.split(/\n\s*\n/).map((paragraph) => paragraph.trimEnd());
};

const renderParagraphs = (text: string) => {
    const paragraphs = splitParagraphs(text);
    if (paragraphs.length === 0) return null;
    return paragraphs.map((paragraph, idx) => (
        <p key={`para-${idx}`} className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">
            <MathText text={paragraph} />
        </p>
    ));
};

const QuestionDetail: React.FC<{ 
    question: QuestionResult; 
    gradingMode?: string; 
    defaultExpanded?: boolean;
}> = ({ question, gradingMode, defaultExpanded = false }) => {
    const percentage = question.maxScore > 0 ? (question.score / question.maxScore) * 100 : 0;
    const questionLabel = question.questionId === 'unknown' ? '未识别' : question.questionId;
    const normalizedType = (question.questionType || '').toLowerCase();
    const isChoice = ['choice', 'single_choice', 'multiple_choice', 'mcq'].includes(normalizedType);
    const isAssist = (gradingMode || '').startsWith('assist')
        || (question.maxScore <= 0 && !(question.scoringPointResults?.length || question.scoringPoints?.length));
    const reviewReasons = question.reviewReasons || [];
    const confessionItems = (question as any).confessionItems || [];
    const audit = question.audit;
    const auditConfidence = audit?.confidence ?? question.confidence;
    const auditRisks = audit?.riskFlags ?? question.auditFlags ?? [];
    const auditUncertainties = audit?.uncertainties ?? [];
    const auditNeedsReview = audit?.needsReview ?? question.needsReview ?? false;
    const isLowConfidence = !isAssist && (
        reviewReasons.includes('low_confidence')
        || (auditConfidence !== undefined && auditConfidence < LOW_CONFIDENCE_THRESHOLD)
    );
    const showScoringDetails = !isAssist && !isChoice;
    const hasDetails = Boolean(question.studentAnswer)
        || (showScoringDetails && ((question.scoringPointResults?.length || 0) > 0 || (question.scoringPoints?.length || 0) > 0));
    const [detailsOpen, setDetailsOpen] = useState(defaultExpanded);
    const [analysisOpen, setAnalysisOpen] = useState(false);
    const hasPointBreakdown = (question.scoringPointResults?.length || 0) > 0;
    const shouldCollapseStudentAnswer = Boolean(question.studentAnswer) && (
        hasPointBreakdown || (question.studentAnswer?.length || 0) > 240
    );
    const [rawAnswerOpen, setRawAnswerOpen] = useState(!shouldCollapseStudentAnswer);
    const [scoringDetailsOpen, setScoringDetailsOpen] = useState(false);
    const scoreLabel = isAssist ? 'Assist' : (question.maxScore > 0 ? `${question.score} / ${question.maxScore}` : 'N/A');
    const scoreClass = isAssist || question.maxScore <= 0
        ? 'text-slate-400'
        : (percentage >= 60 ? 'text-emerald-600' : 'text-red-500');
    const typeMeta = (() => {
        if (!normalizedType) return null;
        if (normalizedType === 'choice') return { label: 'Choice', className: 'border-blue-200 text-blue-600 bg-blue-50' };
        if (normalizedType === 'objective') return { label: 'Objective', className: 'border-emerald-200 text-emerald-600 bg-emerald-50' };
        if (normalizedType === 'subjective') return { label: 'Subjective', className: 'border-amber-200 text-amber-600 bg-amber-50' };
        return { label: normalizedType, className: 'border-slate-200 text-slate-500 bg-slate-50' };
    })();
    
    const hasAuditSignals = auditNeedsReview
        || reviewReasons.length > 0
        || confessionItems.length > 0
        || auditRisks.length > 0
        || auditUncertainties.length > 0;

    return (
        <div className="p-4 space-y-3">
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                    <span className="font-semibold text-slate-700 text-sm">第 {questionLabel} 题</span>
                    {question.isCrossPage && (
                        <span className="text-[11px] px-2 py-0.5 rounded border border-purple-200 text-purple-600 bg-purple-50 flex items-center gap-1 font-medium">
                            <Layers className="w-3 h-3" />
                            跨页
                        </span>
                    )}
                    {typeMeta && (
                        <span className={clsx(
                            "text-[11px] px-2 py-0.5 rounded border font-medium",
                            typeMeta.className
                        )}>
                            {typeMeta.label}
                        </span>
                    )}
                    {isAssist && (
                        <span className="text-[11px] px-2 py-0.5 rounded border border-slate-200 text-slate-500 bg-slate-50 font-medium">
                            Assist
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    {hasDetails && (
                        <button
                            type="button"
                            onClick={() => setDetailsOpen((prev) => !prev)}
                            className="text-[11px] font-semibold text-slate-400 hover:text-slate-700 transition-colors"
                        >
                            {detailsOpen ? 'Hide details' : 'Show details'}
                        </button>
                    )}
                    <span className={clsx('text-sm font-semibold', scoreClass)}>
                        {scoreLabel}
                    </span>
                </div>
            </div>

            {/* Meta Info */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                {question.pageIndices && question.pageIndices.length > 0 && (
                    <div className="flex items-center gap-1.5">
                        <FileText className="w-3 h-3" />
                        Pages: <span className="font-mono text-slate-500">{question.pageIndices.map(p => p + 1).join(', ')}</span>
                    </div>
                )}
                {/* 显示置信度 - 优先使用审计置信度 */}
                {(() => {
                    const displayConfidence = auditConfidence;
                    const isReviewed = (question as any).logicReviewed
                        || (question as any).logic_reviewed
                        || Boolean(question.reviewCorrections?.length || question.reviewSummary);

                    // 用户体验：批改阶段的置信度容易造成误导，只在逻辑复核后展示最终置信度。
                    if (!isReviewed) return null;
                    if (displayConfidence === undefined) return null;
                    
                    return (
                        <div className={clsx(
                            "flex items-center gap-1.5",
                            displayConfidence >= 0.8 ? "text-emerald-600" : displayConfidence >= 0.6 ? "text-amber-600" : "text-red-500"
                        )}>
                            {displayConfidence >= 0.8 ? (
                                <CheckCircle className="w-3 h-3" />
                            ) : displayConfidence >= 0.6 ? (
                                <AlertCircle className="w-3 h-3" />
                            ) : (
                                <AlertTriangle className="w-3 h-3" />
                            )}
                            置信度: <span className="font-mono font-semibold">{(displayConfidence * 100).toFixed(0)}%</span>
                            <span className="text-[9px] text-slate-400">(复核)</span>
                        </div>
                    );
                })()}
                {/* 显示评分标准引用数量 */}
                {question.rubricRefs && question.rubricRefs.length > 0 && (
                    <div className="flex items-center gap-1.5 text-blue-600">
                        <BookOpen className="w-3 h-3" />
                        引用: <span className="font-mono font-semibold">{question.rubricRefs.length} 条</span>
                    </div>
                )}
            </div>

            {detailsOpen && (
                <>
                    {/* Student OCR can be very noisy; collapse long answers (and collapse by default when step breakdown exists). */}
                    {question.studentAnswer && !shouldCollapseStudentAnswer && (
                        <div className="rounded-md p-3 border border-slate-200 bg-white">
                            <span className="text-[11px] font-semibold text-slate-500 mb-1 block">
                                {hasPointBreakdown ? 'Student Answer (OCR)' : 'Student Answer'}
                            </span>
                            <div className="space-y-2">
                                {renderParagraphs(question.studentAnswer)}
                            </div>
                        </div>
                    )}

                    {question.studentAnswer && shouldCollapseStudentAnswer && (
                        <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                            <button
                                type="button"
                                onClick={() => setRawAnswerOpen((v) => !v)}
                                className="w-full px-3 py-2 cursor-pointer hover:bg-slate-50 transition-colors flex items-center justify-between"
                            >
                                <span className="text-[11px] font-semibold text-slate-600">
                                    {hasPointBreakdown ? 'Student Answer (OCR)' : 'Student Answer'}
                                </span>
                                <ChevronDown className={clsx("w-4 h-4 text-slate-400 transition-transform", rawAnswerOpen && "rotate-180")} />
                            </button>
                            {rawAnswerOpen && (
                                <div className="px-3 pb-3">
                                    <div className="space-y-2">
                                        {renderParagraphs(question.studentAnswer)}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {(() => {
                        const pointResults = (question.scoringPointResults || []) as any[];
                        if (pointResults.length === 0) return null;

                        // Prefer backend-provided step segmentation; otherwise build a point-aligned step list.
                        let steps = (question.steps || []) as any[];
                        if (steps.length === 0) {
                            steps = pointResults.map((spr, idx) => ({
                                step_id: spr.stepId || spr.step_id || spr.pointId || spr.point_id || `S${idx + 1}`,
                                step_content: spr.stepExcerpt || spr.step_excerpt || spr.evidence || spr.description || '',
                                step_region: spr.stepRegion || spr.step_region || spr.errorRegion || spr.error_region,
                                is_correct: Number(spr.awarded ?? spr.score ?? 0) > 0,
                                mark_type: spr.markType || spr.mark_type || 'M',
                                mark_value: Number(spr.awarded ?? spr.score ?? 0),
                                feedback: spr.reason || '',
                            }));
                        }

                        const normalizeStepId = (step: any, index: number) =>
                            String(step.step_id || step.stepId || step.id || `S${index + 1}`);
                        const normalizeStepContent = (step: any) =>
                            String(step.step_content || step.stepContent || step.step_content || '');
                        const normalizeSprStepId = (spr: any) =>
                            String(spr.step_id || spr.stepId || spr.pointId || spr.point_id || '');
                        const normalizePointId = (spr: any, idx: number) =>
                            String(
                                spr.pointId
                                || spr.point_id
                                || spr.scoringPoint?.pointId
                                || spr.scoring_point?.point_id
                                || (spr.point_id ? spr.point_id : idx + 1)
                            );
                        const normalizeAwarded = (spr: any) => Number(spr.awarded ?? spr.score ?? 0);
                        const normalizeMax = (spr: any) => Number(
                            spr.maxPoints
                            ?? spr.max_points
                            ?? spr.maxScore
                            ?? spr.max_score
                            ?? spr.scoringPoint?.score
                            ?? spr.scoring_point?.score
                            ?? 0
                        );

                        const byStepId = new Map<string, any[]>();
                        const unmapped: any[] = [];
                        pointResults.forEach((spr, idx) => {
                            const sid = normalizeSprStepId(spr);
                            if (!sid) {
                                unmapped.push({ spr, idx });
                                return;
                            }
                            const list = byStepId.get(sid) || [];
                            list.push({ spr, idx });
                            byStepId.set(sid, list);
                        });

                        // 只有当至少存在一步能对齐到得分点时才展示（避免噪音）
                        if (byStepId.size === 0 && unmapped.length === 0) return null;

                        const renderPointChip = ({ spr, idx }: { spr: any; idx: number }) => {
                            const pointId = normalizePointId(spr, idx);
                            const awarded = normalizeAwarded(spr);
                            const maxPoints = normalizeMax(spr);
                            const isReviewAdjusted = spr.reviewAdjusted || spr.review_adjusted;
                            const desc = spr.scoringPoint?.description || spr.scoring_point?.description || spr.description || '';
                            const evidence = spr.evidence || '';
                            const rubricRef = spr.rubricReference || spr.rubric_reference || '';
                            const rubricRefSource = spr.rubricReferenceSource || spr.rubric_reference_source || '';
                            const needsVerify = !String(rubricRef).trim() || String(rubricRefSource).toLowerCase().startsWith('system');

                            return (
                                <Popover
                                    key={`${pointId}-${idx}`}
                                    content={
                                        <div className="max-w-xs text-xs space-y-2">
                                            <div className="font-semibold text-slate-900">
                                                [{pointId}] {desc || '评分点'}
                                            </div>
                                            <div className={clsx("text-slate-600", needsVerify && "text-amber-700")}>
                                                <span className="font-semibold">评分标准:</span> {rubricRef || '未提供评分标准引用'}
                                                {needsVerify && <span className="ml-1 font-semibold">(需校验)</span>}
                                            </div>
                                            {evidence && (
                                                <div className="text-slate-600">
                                                    <span className="font-semibold">证据:</span> {evidence}
                                                </div>
                                            )}
                                            {isReviewAdjusted && (
                                                <div className="text-amber-700 font-semibold">已被逻辑复核修正</div>
                                            )}
                                        </div>
                                    }
                                    trigger="hover"
                                    placement="top"
                                >
                                    <span className={clsx(
                                        "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-mono cursor-help transition",
                                        awarded > 0 ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-500",
                                        isReviewAdjusted ? "border-amber-200 bg-amber-50 text-amber-700" : ""
                                    )}>
                                        <span className="font-bold">{pointId}</span>
                                        <span className="opacity-70">{awarded}/{maxPoints || 1}</span>
                                        {isReviewAdjusted && <Shield className="w-3 h-3" />}
                                    </span>
                                </Popover>
                            );
                        };

                        const renderStepScoreBadge = (sid: string, related: any[], stepScore: number) => {
                            const hasRelated = related.length > 0;
                            const stepMax = related.reduce((sum, item) => sum + normalizeMax(item.spr), 0);

                            const popoverContent = hasRelated ? (
                                <div className="max-w-xs text-xs space-y-2">
                                    <div className="font-semibold text-slate-900">
                                        {sid} 得分: {stepScore}/{stepMax || 1}
                                    </div>
                                    <div className="space-y-1">
                                        {related.map(({ spr, idx }: { spr: any; idx: number }) => {
                                            const pointId = normalizePointId(spr, idx);
                                            const awarded = normalizeAwarded(spr);
                                            const maxPoints = normalizeMax(spr);
                                            const desc = spr.scoringPoint?.description || spr.scoring_point?.description || spr.description || '';
                                            const evidence = spr.evidence || '';
                                            const rubricRef = spr.rubricReference || spr.rubric_reference || '';
                                            const rubricRefSource = spr.rubricReferenceSource || spr.rubric_reference_source || '';
                                            const needsVerify = !String(rubricRef).trim() || String(rubricRefSource).toLowerCase().startsWith('system');

                                            return (
                                                <div key={`${sid}-${pointId}-${idx}`} className="text-slate-700">
                                                    <span className="font-mono font-semibold">[{pointId}]</span>{' '}
                                                    <span className="font-mono">{awarded}/{maxPoints || 1}</span>{' '}
                                                    <span className="text-slate-500">{desc || '评分点'}</span>
                                                    <div className={clsx("mt-0.5 text-slate-600", needsVerify && "text-amber-700")}>
                                                        <span className="font-semibold">标准:</span> {rubricRef || '未提供评分标准引用'}
                                                        {needsVerify && <span className="ml-1 font-semibold">(需校验)</span>}
                                                    </div>
                                                    {evidence && (
                                                        <div className="mt-0.5 text-slate-600">
                                                            <span className="font-semibold">证据:</span> {evidence}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            ) : (
                                <div className="max-w-xs text-xs text-slate-600">
                                    未对齐到任何评分点（可能是无关步骤或模型未标注）。
                                </div>
                            );

                            return (
                                <Popover content={popoverContent} trigger="hover" placement="top">
                                    <span
                                        className={clsx(
                                            "ml-2 inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-mono cursor-help transition",
                                            hasRelated
                                                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                                : "border-slate-200 bg-slate-50 text-slate-500"
                                        )}
                                    >
                                        {hasRelated ? `+${stepScore}` : "+0"}
                                    </span>
                                </Popover>
                            );
                        };

                        const renderStepLine = (step: any, index: number) => {
                            const sid = normalizeStepId(step, index);
                            const content = normalizeStepContent(step);
                            const related = byStepId.get(sid) || [];
                            const stepScore = related.reduce((sum, item) => sum + normalizeAwarded(item.spr), 0);
                            const hasRelated = related.length > 0;

                            return (
                                <div
                                    key={`${sid}-${index}`}
                                    className={clsx(
                                        "rounded-lg border p-3 bg-white",
                                        hasRelated ? "border-slate-200" : "border-slate-100"
                                    )}
                                >
                                    <div className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
                                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-900 text-white mr-2">
                                            {sid}
                                        </span>
                                        {content ? (
                                            <MathText text={formatStudentText(content)} />
                                        ) : (
                                            <span className="italic text-slate-400">（无步骤原文）</span>
                                        )}
                                        {renderStepScoreBadge(sid, related, stepScore)}
                                    </div>
                                    {hasRelated ? (
                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                            {related.map(renderPointChip)}
                                        </div>
                                    ) : (
                                        <div className="mt-2 text-[11px] text-slate-400 italic">
                                            未对齐到任何评分点（可能是无关步骤或模型未标注）。
                                        </div>
                                    )}
                                </div>
                            );
                        };

                        return (
                            <div className="mt-3 space-y-2">
                                <div className="text-xs font-semibold text-slate-500 flex items-center gap-2">
                                    <ListOrdered className="w-3.5 h-3.5" />
                                    结构化答案（逐步给分）
                                </div>
                                <div className="space-y-2">
                                    {steps.map(renderStepLine)}
                                    {unmapped.length > 0 && (
                                        <div className="rounded-lg border border-slate-200 bg-slate-50/30 p-3">
                                            <div className="text-[11px] font-semibold text-slate-600 mb-2">
                                                未标注步骤的评分点
                                            </div>
                                            <div className="flex flex-wrap gap-1.5">
                                                {unmapped.map(renderPointChip)}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })()}

                    {showScoringDetails ? (
                        question.scoringPointResults && question.scoringPointResults.length > 0 ? (
                            <div className="mt-3 space-y-2">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="text-xs font-semibold text-slate-500 flex items-center gap-2">
                                        <Target className="w-3.5 h-3.5" />
                                        评分标准对照
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setScoringDetailsOpen((v) => !v)}
                                        className="text-[11px] font-semibold text-slate-400 hover:text-slate-700 transition-colors"
                                    >
                                        {scoringDetailsOpen ? '收起' : '展开'}明细
                                    </button>
                                </div>
                                {!scoringDetailsOpen && (
                                    <div className="text-[11px] text-slate-400">
                                        鼠标悬停上方气泡可预览对应评分标准；如需查看全部得分点明细请展开。
                                    </div>
                                )}
                                {scoringDetailsOpen && question.scoringPointResults.map((spr, idx) => {
                                    // 构建评分标准引用文本（如果没有则基于 pointId 和 description 生成）
                                    const rubricRef = spr.rubricReference 
                                        || (spr as any).rubric_reference 
                                        || (spr.pointId && spr.description ? `[${spr.pointId}] ${spr.description}` : null)
                                        || (spr.scoringPoint?.description ? `[${spr.pointId || idx + 1}] ${spr.scoringPoint.description}` : null);
                                    
                                    // 是否被逻辑复核修正过
                                    const isReviewAdjusted = (spr as any).reviewAdjusted || (spr as any).review_adjusted;
                                    const reviewBefore = (spr as any).reviewBefore || (spr as any).review_before;
                                    const reviewReason = (spr as any).reviewReason || (spr as any).review_reason;
                                    
                                    return (
                                    <div key={idx} className={clsx(
                                        "rounded-lg border p-3 transition-all",
                                        isReviewAdjusted 
                                            ? "border-amber-300 bg-amber-50/50" 
                                            : spr.awarded > 0 
                                                ? "border-emerald-200 bg-emerald-50/30" 
                                                : "border-slate-200 bg-slate-50/30"
                                    )}>
                                        <div className="flex items-start justify-between gap-3">
                                            {/* 左侧：评分标准内容 */}
                                            <div className="flex-1 space-y-2">
                                                {/* 评分标准引用标签 - 放在顶部更醒目 */}
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    {spr.pointId && (
                                                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 border border-indigo-200">
                                                            得分点 {spr.pointId}
                                                        </span>
                                                    )}
                                                    {rubricRef && (
                                                        <Popover
                                                            content={
                                                                <div className="max-w-xs text-xs">
                                                                    <div className="font-semibold mb-1">评分标准引用</div>
                                                                    <div className="text-slate-600">{rubricRef}</div>
                                                                </div>
                                                            }
                                                            trigger="hover"
                                                            placement="top"
                                                        >
                                                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-200 flex items-center gap-1 cursor-help">
                                                                <BookOpen className="w-3 h-3" />
                                                                标准引用
                                                            </span>
                                                        </Popover>
                                                    )}
                                                    {isReviewAdjusted && (
                                                        <Popover
                                                            content={
                                                                <div className="max-w-xs text-xs">
                                                                    <div className="font-semibold mb-1 text-amber-700">逻辑复核修正</div>
                                                                    {reviewBefore && (
                                                                        <div className="text-slate-500 mb-1">
                                                                            原分数: {reviewBefore.awarded} → 修正: {spr.awarded}
                                                                        </div>
                                                                    )}
                                                                    {reviewReason && (
                                                                        <div className="text-slate-600">{reviewReason}</div>
                                                                    )}
                                                                </div>
                                                            }
                                                            trigger="hover"
                                                            placement="top"
                                                        >
                                                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200 flex items-center gap-1 cursor-help">
                                                                <Shield className="w-3 h-3" />
                                                                已复核
                                                            </span>
                                                        </Popover>
                                                    )}
                                                </div>
                                                
                                                {/* 评分标准描述 */}
                                                <div className="text-xs text-slate-700 leading-relaxed">
                                                    <MathText className="inline" text={spr.scoringPoint?.description || spr.description || "N/A"} />
                                                </div>
                                                
                                                {/* 判定理由 */}
                                                <div className={clsx(
                                                    "text-[11px] px-2 py-1.5 rounded",
                                                    spr.awarded > 0 ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
                                                )}>
                                                    <span className="font-semibold">
                                                        {spr.awarded > 0 ? '✓ ' : '✗ '}
                                                        {spr.decision || (spr.awarded > 0 ? '得分' : '不得分')}
                                                    </span>
                                                    {spr.reason && <span className="ml-1.5 opacity-80">— {spr.reason}</span>}
                                                </div>
                                            </div>
                                            
                                            {/* 右侧：分数 */}
                                            <div className={clsx(
                                                "flex flex-col items-center justify-center px-3 py-2 rounded-lg min-w-[60px]",
                                                spr.awarded > 0 ? "bg-emerald-500 text-white" : "bg-slate-200 text-slate-500"
                                            )}>
                                                <span className="font-mono font-bold text-lg leading-none">
                                                    {spr.awarded}
                                                </span>
                                                <span className="text-[10px] opacity-80">
                                                    / {spr.maxPoints ?? (spr as any).max_points ?? spr.scoringPoint?.score ?? spr.awarded ?? 1}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                )})}
                            </div>
                        ) : question.scoringPoints && question.scoringPoints.length > 0 ? (
                            // Fallback for simple scoring points list without rich results
                            <div className="mt-2 space-y-1">
                                {question.scoringPoints.map((sp, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-xs">
                                        {sp.isCorrect ? (
                                            <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                                        ) : (
                                            <XCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 flex-shrink-0" />
                                        )}
                                        <div className="flex-1">
                                            <span className={clsx("font-medium", sp.isCorrect ? 'text-emerald-700' : 'text-red-700')}>
                                                [{sp.score}/{sp.maxScore}] {sp.description}
                                            </span>
                                            {sp.explanation && <p className="text-slate-500 mt-0.5 ml-1">{sp.explanation}</p>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="mt-2 text-xs text-slate-500 flex items-center gap-2">
                                <AlertTriangle className="w-3.5 h-3.5 text-slate-400" />
                                已给出总分，但缺少逐项给分（得分点/步骤拆解缺失）。
                            </div>
                        )
                    ) : (
                        <div className="mt-2 text-xs text-slate-500 italic">
                            {isAssist ? 'No scoring breakdown in Assist mode.' : 'No detailed analysis for this question type.'}
                        </div>
                    )}
                    
                    {/* 自白报告区块 - 可折叠 */}
                    {hasAuditSignals && (
                        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/50 overflow-hidden">
                            <button 
                                type="button"
                                onClick={() => setAnalysisOpen(!analysisOpen)}
                                className="w-full px-3 py-2 cursor-pointer hover:bg-amber-100/50 transition-colors flex items-center justify-between"
                            >
                                <span className="text-[11px] font-semibold text-amber-700 flex items-center gap-1.5">
                                    <BrainCircuit className="w-3.5 h-3.5" />
                                    自白报告 ({confessionItems.length + reviewReasons.length + auditRisks.length + auditUncertainties.length + (auditNeedsReview ? 1 : 0)})
                                </span>
                                <ChevronDown className={clsx("w-4 h-4 text-amber-500 transition-transform", analysisOpen && "rotate-180")} />
                            </button>
                            {analysisOpen && (
                                <div className="px-3 pb-3 space-y-2">
                                    {auditNeedsReview && (
                                        <div className="text-[11px] text-rose-700 bg-rose-50 px-2 py-1.5 rounded border border-rose-200 flex items-start gap-1.5">
                                            <XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                            <span>需要人工复核</span>
                                        </div>
                                    )}
                                    {reviewReasons.length > 0 && (
                                        <div className="space-y-1">
                                            {reviewReasons.map((item, i) => {
                                                const meta = getReviewReasonMeta(item);
                                                const title = meta?.title || item;
                                                const hint = meta?.hint;
                                                const inner = (
                                                    <span className={clsx(hint && "cursor-help")}>
                                                        复核原因：{title}
                                                        {meta && (
                                                            <span className="ml-1 font-mono text-slate-400">({item})</span>
                                                        )}
                                                    </span>
                                                );

                                                return (
                                                    <div key={`rr-${i}`} className="text-[11px] text-slate-700 bg-white/70 px-2 py-1.5 rounded border border-amber-100 flex items-start gap-1.5">
                                                        <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0 opacity-70" />
                                                        {hint ? (
                                                            <Popover
                                                                content={<div className="max-w-xs text-xs text-slate-700 leading-relaxed">{hint}</div>}
                                                                trigger="hover"
                                                                placement="top"
                                                            >
                                                                {inner}
                                                            </Popover>
                                                        ) : inner}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                    {confessionItems.length > 0 && (
                                        <div className="space-y-1">
                                            {confessionItems.slice(0, 6).map((it: any, i: number) => (
                                                <div key={`ci-${i}`} className="text-[11px] text-amber-800 bg-amber-50 px-2 py-1.5 rounded border border-amber-200 flex items-start gap-1.5">
                                                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0 opacity-70" />
                                                    <span>
                                                        [{String(it?.severity || 'warning').toUpperCase()}] {String(it?.issue_type || it?.issueType || 'issue')}：{String(it?.action || '')}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {auditRisks.length > 0 && (
                                        <div className="space-y-1">
                                            {auditRisks.map((item, i) => (
                                                <div key={i} className="text-[11px] text-rose-700 bg-rose-50 px-2 py-1.5 rounded border border-rose-200 flex items-start gap-1.5">
                                                    <XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                                    <span>风险标签：{item}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {auditUncertainties.length > 0 && (
                                        <div className="space-y-1">
                                            {auditUncertainties.map((item, i) => (
                                                <div key={i} className="text-[11px] text-orange-700 bg-orange-50 px-2 py-1.5 rounded border border-orange-200 flex items-start gap-1.5">
                                                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                                    <span>{item}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                </>
            )}
            {(isLowConfidence || auditNeedsReview) && (
                <div className="mt-3 p-3 rounded-md border border-amber-200 bg-amber-50">
                    <div className="text-[11px] font-semibold text-amber-700 mb-1">自白提示</div>
                    <p className="text-xs text-amber-800 leading-relaxed">
                        <MathText text={auditUncertainties[0] || '该题存在不确定性或风险标签，建议复核。'} />
                    </p>
                </div>
            )}

            {question.feedback && (!isChoice || isAssist) && (
                <div className="mt-3 pt-3 border-t border-slate-100">
                    <div className="text-[11px] font-semibold text-slate-500 mb-1">Feedback</div>
                    <p className="text-xs text-slate-600 leading-relaxed font-medium">
                        <MathText text={question.feedback} />
                    </p>
                </div>
            )}
        </div>
    );
};

const ResultCard: React.FC<ResultCardProps> = ({ result, rank, onExpand }) => {
    const isAssist = (result.gradingMode || '').startsWith('assist') || result.maxScore <= 0;
    const percentage = !isAssist && result.maxScore > 0 ? (result.score / result.maxScore) * 100 : 0;
    const hasAuditRisk = (result.questionResults || []).some((q) => {
        const audit = q.audit;
        const confidence = audit?.confidence ?? q.confidence ?? 1;
        return Boolean(audit?.needsReview)
            || (audit?.riskFlags?.length || 0) > 0
            || ((q as any).confessionItems && (q as any).confessionItems.length > 0)
            || (q.reviewReasons && q.reviewReasons.length > 0)
            || confidence < LOW_CONFIDENCE_THRESHOLD;
    });

    let gradeLabel = '未评级';
    if (isAssist) {
        gradeLabel = 'Assist';
    } else if (percentage >= 85) {
        gradeLabel = '优秀';
    } else if (percentage >= 70) {
        gradeLabel = '良好';
    } else if (percentage >= 60) {
        gradeLabel = '及格';
    } else {
        gradeLabel = '不及格';
    }

    const crossPageCount = result.questionResults?.filter(q => q.isCrossPage).length || 0;
    const pageRange = result.pageRange || result.pages || '';

    return (
        <GlassCard
            className={clsx(
                'grid grid-cols-[56px_1fr_auto] items-center gap-4 px-4 py-3 border-b border-white/20 transition-all cursor-pointer mb-3',
                result.needsConfirmation ? 'bg-amber-50/40 border-amber-200/50' : 'bg-white/40 hover:bg-white/60'
            )}
            onClick={() => onExpand?.()}
            hoverEffect={true}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            layout
        >
            <div className='h-10 w-10 rounded-md border border-slate-200 bg-white/50 text-slate-700 font-mono font-bold text-sm flex items-center justify-center'>
                {rank}
            </div>

            <div className='min-w-0'>
                <div className='flex items-center gap-3'>
                    <h3 className='font-semibold text-slate-900 truncate'>{result.studentName}</h3>
                    <span className='text-[11px] font-medium text-slate-500'>{gradeLabel}</span>
                </div>
                <div className='mt-1 text-[11px] text-slate-500 flex flex-wrap gap-3 items-center'>
                    {pageRange && <span>Pages {pageRange}</span>}
                    {result.totalRevisions !== undefined && result.totalRevisions > 0 && (
                        <span>Revisions {result.totalRevisions}</span>
                    )}
                    {crossPageCount > 0 && <span>Cross-page {crossPageCount}</span>}
                    {result.needsConfirmation && <span className='text-amber-600 bg-amber-100/50 px-2 py-0.5 rounded-md border border-amber-200/50'>Needs verification</span>}
                    {hasAuditRisk && (
                        <span className='text-orange-600 bg-orange-100/50 px-2 py-0.5 rounded-md border border-orange-200/50 flex items-center gap-1'>
                            <AlertTriangle className='w-3 h-3' /> Audit
                        </span>
                    )}
                    {result.logicReviewedAt && (
                        <span className='text-indigo-600 bg-indigo-100/50 px-2 py-0.5 rounded-md border border-indigo-200/50 flex items-center gap-1'>
                            <Shield className='w-3 h-3' /> Logic Review
                        </span>
                    )}
                </div>
            </div>

            <div className='text-right'>
                {isAssist ? (
                    <div className='text-xs font-semibold text-slate-500'>Assist</div>
                ) : (
                    <div className='text-lg font-bold text-slate-900'>
                        {result.score.toFixed(1)}<span className='text-xs text-slate-400'>/{result.maxScore}</span>
                    </div>
                )}
                {!isAssist && (
                    <div className='text-[11px] text-slate-500'>{percentage.toFixed(0)}%</div>
                )}
            </div>
        </GlassCard>
    );
};


const normalizeQuestionId = (questionId: string) => {
    const raw = (questionId || '').toString().trim();
    if (!raw) return 'unknown';
    return raw.replace(/^第\s*/i, '').replace(/^q\s*/i, '').replace(/\s*题$/i, '').replace(/\s+/g, '').replace(/[。．\.,，、]+$/g, '');
};

const normalizeQuestionResults = (questionResults?: QuestionResult[]) => {
    if (!questionResults || questionResults.length === 0) return [];

    const byId = new Map<string, QuestionResult[]>();
    questionResults.forEach((q) => {
        const key = normalizeQuestionId(q.questionId);
        const list = byId.get(key) || [];
        list.push(q);
        byId.set(key, list);
    });

    const merged = Array.from(byId.entries()).map(([normalizedId, items]) => {
        if (items.length === 1) {
            return { ...items[0], questionId: normalizeQuestionId(items[0].questionId) };
        }
        // Basic merging logic for when multiple parts exist for same question ID
        // Simplified for brevity, prioritizing the item with highest score or most info
        const bestItem = items.reduce((prev, curr) => (curr.score > prev.score ? curr : prev), items[0]);
        return {
            ...bestItem,
            questionId: normalizedId !== 'unknown' ? normalizedId : (items[0].questionId || 'unknown'),
            isCrossPage: items.some(i => i.isCrossPage),
        };
    });

    const parseOrder = (id: string) => {
        const normalized = normalizeQuestionId(id);
        const match = normalized.match(/\d+/);
        const number = match ? Number(match[0]) : Number.MAX_SAFE_INTEGER;
        const suffix = match ? normalized.replace(match[0], '') : normalized;
        return { number, suffix };
    };

    return merged.sort((a, b) => {
        const aOrder = parseOrder(a.questionId);
        const bOrder = parseOrder(b.questionId);
        if (aOrder.number !== bOrder.number) {
            return aOrder.number - bOrder.number;
        }
        return aOrder.suffix.localeCompare(bOrder.suffix);
    });
};

export const ResultsView: React.FC<ResultsViewProps> = ({ defaultExpandDetails = false, hideGradingTransparency = false, studentOnlyMode = false, annotationHistoryId }) => {
    const {
        finalResults,
        workflowNodes,
        crossPageQuestions,
        uploadedImages,
        setUploadedImages,
        setCurrentTab,
        classReport,
        submissionId,
        reviewFocus,
        setReviewFocus,
        setFinalResults,
        status
    } = useConsoleStore();
    const annotationGradingHistoryId = annotationHistoryId || submissionId;

    const bookScanContext = useContext(AppContext) as AppContextType | null;
    const sessions = bookScanContext?.sessions || [];
    const currentSessionId = bookScanContext?.currentSessionId || null;
    const currentSession = sessions.find((s: any) => s.id === currentSessionId);

    const [detailViewIndex, setDetailViewIndex] = useState<number | null>(studentOnlyMode ? 0 : null);
    // API 备用方案状态
    const [apiFallbackLoading, setApiFallbackLoading] = useState(false);
    const [apiFallbackError, setApiFallbackError] = useState<string | null>(null);
    const apiFallbackAttemptedRef = React.useRef<Set<string>>(new Set());
    const [auditOpen, setAuditOpen] = useState(false);
    const [auditQuery, setAuditQuery] = useState('');
    const [showClassReport, setShowClassReport] = useState(false);
    const [reviewMode, setReviewMode] = useState(false);
    const [reviewDraft, setReviewDraft] = useState<ReviewStudentDraft[]>([]);
    const [reviewSelectedKeys, setReviewSelectedKeys] = useState<Set<string>>(new Set());
    const [reviewGlobalNote, setReviewGlobalNote] = useState('');
    const [reviewMessage, setReviewMessage] = useState<string | null>(null);
    const [reviewError, setReviewError] = useState<string | null>(null);
    const [reviewSubmitting, setReviewSubmitting] = useState(false);
    const [rubricOpen, setRubricOpen] = useState(false);
    const [rubricLoading, setRubricLoading] = useState(false);
    const [rubricError, setRubricError] = useState<string | null>(null);
    const [rubricImages, setRubricImages] = useState<string[]>([]);
    const [rubricDraft, setRubricDraft] = useState<any>(null);
    const [rubricSelectedIds, setRubricSelectedIds] = useState<Set<string>>(new Set());
    const [rubricExpandedIds, setRubricExpandedIds] = useState<Set<string>>(new Set());
    const [rubricGlobalNote, setRubricGlobalNote] = useState('');
    const [rubricSubmitting, setRubricSubmitting] = useState(false);
    const [rubricMessage, setRubricMessage] = useState<string | null>(null);

    // API Base - 直接使用统一的 API_BASE
    const getApiUrl = () => {
        if (process.env.NEXT_PUBLIC_API_URL) {
            return process.env.NEXT_PUBLIC_API_URL;
        }
        if (typeof window === 'undefined') return 'http://localhost:8001/api';
        const { hostname, origin } = window.location;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'http://localhost:8001/api';
        }
        if (hostname.includes('railway.app')) {
            return 'https://gradeos-production.up.railway.app/api';
        }
        console.warn('API_URL not configured, falling back to relative path /api');
        return `${origin}/api`;
    };
    const apiBase = getApiUrl().replace(/\/+$/, '');
    // 批注渲染状态 - 默认开启
    const [showAnnotations, setShowAnnotations] = useState(true);
    const [annotationGenerating, setAnnotationGenerating] = useState(false);
    const [annotationFetchLoading, setAnnotationFetchLoading] = useState(false);
    const [annotationEditMode, setAnnotationEditMode] = useState(false);
    const [annotationStatus, setAnnotationStatus] = useState<{ type: 'idle' | 'loading' | 'success' | 'error'; message: string | null }>({
        type: 'idle',
        message: null,
    });
    // 🔥 新增：存储每页的批注数据，用于 Canvas 直接渲染
    const [pageAnnotationsData, setPageAnnotationsData] = useState<Map<number, PageAnnotation[]>>(new Map());

    const updatePageAnnotations = useCallback((pageIdx: number, updater: (current: PageAnnotation[]) => PageAnnotation[]) => {
        setPageAnnotationsData((prev) => {
            const next = new Map(prev);
            const current = next.get(pageIdx) ?? [];
            next.set(pageIdx, updater(current));
            return next;
        });
    }, []);
    const [exportPdfLoading, setExportPdfLoading] = useState(false);
    const [exportStatus, setExportStatus] = useState<{ type: 'idle' | 'loading' | 'success' | 'error'; message: string | null }>({
        type: 'idle',
        message: null,
    });

    // 导出相关状态
    const [exportMenuOpen, setExportMenuOpen] = useState(false);
    const [exportLoading, setExportLoading] = useState<string | null>(null);
    const [smartExcelOpen, setSmartExcelOpen] = useState(false);
    const [smartExcelPrompt, setSmartExcelPrompt] = useState('');
    const [smartExcelTemplate, setSmartExcelTemplate] = useState<File | null>(null);
    const [smartExcelLoading, setSmartExcelLoading] = useState(false);

    const gradingNode = workflowNodes.find(n => n.id === 'grade_batch') || workflowNodes.find(n => n.id === 'grading');
    const agentResults = gradingNode?.children?.filter(c => c.status === 'completed' && c.output) || [];

    const results: StudentResult[] = finalResults.length > 0
        ? finalResults
        : agentResults.map(agent => ({
            studentName: agent.label,
            score: agent.output?.score || 0,
            maxScore: agent.output?.maxScore || 100,
            gradingMode: (agent.output as any)?.gradingMode,
            questionResults: agent.output?.questionResults?.map(q => ({
                questionId: q.questionId,
                score: q.score,
                maxScore: q.maxScore,
                feedback: (q as any).feedback || '',
                studentAnswer: (q as any).studentAnswer || (q as any).student_answer,
                questionType: (q as any).questionType || (q as any).question_type,
                confidence: (q as any).confidence,
                confidenceReason: (q as any).confidenceReason || (q as any).confidence_reason,
                selfCritique: (q as any).selfCritique || (q as any).self_critique,
                selfCritiqueConfidence: (q as any).selfCritiqueConfidence || (q as any).self_critique_confidence,
                rubricRefs: (q as any).rubricRefs || (q as any).rubric_refs,
                typoNotes: (q as any).typoNotes || (q as any).typo_notes,
                scoringPoints: (q as any).scoringPoints,
                pageIndices: (q as any).pageIndices,
                isCrossPage: (q as any).isCrossPage,
                mergeSource: (q as any).mergeSource,
                scoringPointResults: (q as any).scoringPointResults,
                audit: (q as any).audit
            })),
            startPage: (agent.output as any)?.startPage,
            endPage: (agent.output as any)?.endPage,
        }));

    const normalizedResults = useMemo(() => (
        results.map((result) => ({
            ...result,
            questionResults: normalizeQuestionResults(result.questionResults)
        }))
    ), [results]);

    const sortedResults = [...normalizedResults].sort((a, b) => b.score - a.score);
    const detailViewStudent = detailViewIndex !== null ? sortedResults[detailViewIndex] : null;
    const reviewIndex = detailViewIndex ?? 0;
    const clampedReviewIndex = reviewDraft.length > 0 ? Math.min(reviewIndex, reviewDraft.length - 1) : 0;
    const reviewStudent = reviewDraft.length > 0 ? reviewDraft[clampedReviewIndex] : null;
    const reviewPageIndices = useMemo(() => {
        if (!reviewStudent) return [];
        const pages = new Set<number>();
        if (reviewStudent.startPage !== undefined) {
            const start = reviewStudent.startPage;
            const end = reviewStudent.endPage ?? start;
            for (let i = start; i <= end; i += 1) {
                pages.add(i);
            }
        }
        reviewStudent.questionResults.forEach((q) => {
            (q.pageIndices || []).forEach((page) => pages.add(page));
        });
        return Array.from(pages).filter((p) => Number.isFinite(p)).sort((a, b) => a - b);
    }, [reviewStudent]);
    const reviewScoreSummary = useMemo(() => {
        if (!reviewStudent) {
            return { total: 0, max: 0 };
        }
        const total = reviewStudent.questionResults.reduce((sum, q) => sum + (Number(q.score) || 0), 0);
        const max = reviewStudent.questionResults.reduce((sum, q) => sum + (Number(q.maxScore) || 0), 0);
        return { total, max };
    }, [reviewStudent]);

    useEffect(() => {
        if (!reviewFocus) return;
        if (reviewFocus === 'rubric') {
            setRubricOpen(true);
        } else {
            setReviewMode(true);
        }
        setReviewFocus(null);
    }, [reviewFocus, setReviewFocus]);

    // 🔥 API 备用方案：当 WebSocket 失败时，主动调用 API 获取结果
    useEffect(() => {
        // 调试日志
        const needsResults = finalResults.length === 0;
        const needsImages = uploadedImages.length === 0;

        console.log('[API Fallback Check]', {
            submissionId,
            finalResultsLength: finalResults.length,
            uploadedImagesLength: uploadedImages.length,
            status,
            alreadyAttempted: submissionId ? apiFallbackAttemptedRef.current.has(submissionId) : false
        });

        // 条件：有 submissionId，状态为 COMPLETED，且（缺结果或缺图片），且未尝试过
        if (!submissionId || status !== 'COMPLETED' || (!needsResults && !needsImages)) {
            console.log('[API Fallback] Skipping - conditions not met');
            return;
        }
        if (apiFallbackAttemptedRef.current.has(submissionId)) {
            console.log('[API Fallback] Skipping - already attempted for this submissionId');
            return;
        }

        const fetchResultsFromApi = async () => {
            apiFallbackAttemptedRef.current.add(submissionId);
            setApiFallbackLoading(true);
            setApiFallbackError(null);

            try {
                console.log('[API Fallback] Fetching results/images for batch:', submissionId);

                // Prefer results-review context because it includes answer_images.
                let response: any;
                try {
                    response = await gradingApi.getResultsReviewContext(submissionId);
                } catch (error) {
                    console.warn('[API Fallback] results-review endpoint failed; falling back to full-results:', error);
                    response = await gradingApi.getBatchResults(submissionId);
                }

                if (needsImages) {
                    const rawImages = response?.answer_images || response?.answerImages || [];
                    if (Array.isArray(rawImages) && rawImages.length > 0) {
                        const normalizedImages = rawImages.map((img: any) => {
                            if (!img) return img;
                            const trimmed = String(img).trim();
                            if (
                                trimmed.startsWith('data:') ||
                                trimmed.startsWith('http://') ||
                                trimmed.startsWith('https://') ||
                                trimmed.startsWith('blob:') ||
                                trimmed.startsWith('/')
                            ) {
                                return trimmed;
                            }
                            return `data:image/jpeg;base64,${trimmed}`;
                        });
                        setUploadedImages(normalizedImages);
                        console.log('[API Fallback] Loaded', normalizedImages.length, 'answer images');
                    } else {
                        console.log('[API Fallback] No answer_images found in API response');
                    }
                }

                // 后端可能返回 results（camelCase）或 student_results（snake_case）
                const rawResults = (response as any).results || response.student_results || [];
                console.log('[API Fallback] Raw results:', rawResults.length, 'items');

                if (needsResults && rawResults.length > 0) {
                    // 检测数据格式（camelCase 或 snake_case）
                    const firstResult = rawResults[0];
                    const isCamelCase = 'studentName' in firstResult;
                    console.log('[API Fallback] Data format:', isCamelCase ? 'camelCase' : 'snake_case');

                    // 转换 API 响应格式到前端格式
                    const formattedResults: StudentResult[] = rawResults.map((r: any) => {
                        if (isCamelCase) {
                            // 数据已经是 camelCase 格式，直接使用
                            return {
                                studentName: r.studentName || 'Unknown',
                                score: r.score || 0,
                                maxScore: r.maxScore || 100,
                                startPage: r.startPage,
                                endPage: r.endPage,
                                pageRange: r.pageRange,
                                confidence: r.confidence,
                                needsConfirmation: r.needsConfirmation,
                                gradingMode: r.gradingMode,
                                studentSummary: r.studentSummary,
                                selfAudit: r.selfAudit,
                                questionResults: (r.questionResults || []).map((q: any) => ({
                                    questionId: q.questionId || '',
                                    score: q.score || 0,
                                    maxScore: q.maxScore || 0,
                                    feedback: q.feedback || '',
                                    confidence: q.confidence,
                                    confidenceReason: q.confidenceReason,
                                    selfCritique: q.selfCritique,
                                    selfCritiqueConfidence: q.selfCritiqueConfidence,
                                    rubricRefs: q.rubricRefs,
                                    typoNotes: q.typoNotes,
                                    pageIndices: q.pageIndices,
                                    isCrossPage: q.isCrossPage,
                                    mergeSource: q.mergeSource,
                                    audit: q.audit,
                                    scoringPointResults: (q.scoringPointResults || []).map((spr: any) => ({
                                        pointId: spr.pointId || spr.scoringPoint?.pointId,
                                        description: spr.description || spr.scoringPoint?.description || '',
                                        awarded: spr.awarded ?? 0,
                                        maxPoints: spr.maxPoints ?? spr.scoringPoint?.score ?? 0,
                                        evidence: spr.evidence || '',
                                        rubricReference: spr.rubricReference,
                                        rubricReferenceSource: spr.rubricReferenceSource,
                                        decision: spr.decision,
                                        reason: spr.reason,
                                        scoringPoint: spr.scoringPoint ? {
                                            description: spr.scoringPoint.description || '',
                                            score: spr.scoringPoint.score || 0,
                                            maxScore: spr.scoringPoint.score || 0,
                                            isCorrect: (spr.awarded ?? 0) > 0,
                                            isRequired: spr.scoringPoint.isRequired,
                                            explanation: spr.reason || spr.evidence || '',
                                        } : undefined,
                                    })),
                                })),
                            };
                        } else {
                            // snake_case 格式，需要转换
                            return {
                                studentName: r.student_name || 'Unknown',
                                score: r.total_score || 0,
                                maxScore: r.max_score || 100,
                                startPage: r.start_page,
                                endPage: r.end_page,
                                confidence: r.confidence,
                                needsConfirmation: r.needs_confirmation,
                                questionResults: (r.questions || []).map((q: any) => ({
                                    questionId: q.question_id || '',
                                    score: q.score || 0,
                                    maxScore: q.max_score || 0,
                                    feedback: q.feedback || '',
                                    confidence: q.confidence,
                                    confidenceReason: q.confidence_reason,
                                    selfCritique: q.self_critique,
                                    selfCritiqueConfidence: q.self_critique_confidence,
                                    rubricRefs: q.rubric_refs,
                                    typoNotes: q.typo_notes,
                                    pageIndices: q.page_indices,
                                    isCrossPage: q.is_cross_page,
                                    mergeSource: q.merge_source,
                                    audit: q.audit,
                                    scoringPointResults: (q.scoring_point_results || []).map((spr: any) => ({
                                        pointId: spr.point_id || spr.scoring_point?.point_id,
                                        description: spr.description || spr.scoring_point?.description || '',
                                        awarded: spr.awarded ?? 0,
                                        maxPoints: spr.max_points ?? spr.scoring_point?.score ?? 0,
                                        evidence: spr.evidence || '',
                                        rubricReference: spr.rubric_reference,
                                        rubricReferenceSource: spr.rubric_reference_source,
                                        decision: spr.decision,
                                        reason: spr.reason,
                                        scoringPoint: spr.scoring_point ? {
                                            description: spr.scoring_point.description || '',
                                            score: spr.scoring_point.score || 0,
                                            maxScore: spr.scoring_point.score || 0,
                                            isCorrect: (spr.awarded ?? 0) > 0,
                                            isRequired: spr.scoring_point.is_required,
                                            explanation: spr.reason || spr.evidence || '',
                                        } : undefined,
                                    })),
                                })),
                            };
                        }
                    });

                    console.log('[API Fallback] Successfully fetched', formattedResults.length, 'results');
                    setFinalResults(formattedResults);
                } else if (needsResults) {
                    console.log('[API Fallback] No results found in API response');
                    setApiFallbackError('API 返回空结果');
                }
            } catch (error) {
                console.error('[API Fallback] Failed to fetch results:', error);
                setApiFallbackError(error instanceof Error ? error.message : '获取结果失败');
            } finally {
                setApiFallbackLoading(false);
            }
        };

        // 延迟执行，给 WebSocket 一些时间
        const timer = setTimeout(fetchResultsFromApi, 2000);
        return () => clearTimeout(timer);
    }, [submissionId, finalResults.length, uploadedImages.length, status, setFinalResults, setUploadedImages]);

    const totalStudents = sortedResults.length;
    const scoredResults = sortedResults.filter(r => !(r.gradingMode || '').startsWith('assist') && r.maxScore > 0);
    const scoredCount = scoredResults.length;
    const avgScore = scoredCount > 0 ? scoredResults.reduce((sum, r) => sum + r.score, 0) / scoredCount : 0;
    const highestScore = scoredCount > 0 ? Math.max(...scoredResults.map((r) => r.score)) : 0;
    const passCount = scoredResults.filter(r => (r.score / r.maxScore) >= 0.6).length;
    const needsConfirmCount = sortedResults.filter(r => r.needsConfirmation).length;
    const totalCrossPageQuestions = crossPageQuestions.length;
    const hasScores = scoredCount > 0;
    const rubricCoverage = useMemo(() => {
        let total = 0;
        let withRef = 0;
        sortedResults.forEach((student) => {
            (student.questionResults || []).forEach((q) => {
                (q.scoringPointResults || []).forEach((spr) => {
                    total += 1;
                    if (spr.rubricReference) {
                        withRef += 1;
                    }
                });
            });
        });
        if (total === 0) return null;
        return withRef / total;
    }, [sortedResults]);
    const metrics = [
        {
            label: 'Total Students',
            value: totalStudents,
            icon: UsergroupAddOutlined,
            accent: 'text-blue-600',
            glow: 'bg-blue-100/70',
            surface: 'bg-white/70'
        },
        {
            label: 'Avg Score',
            value: hasScores ? avgScore.toFixed(1) : '--',
            icon: BarChartOutlined,
            accent: 'text-indigo-600',
            glow: 'bg-indigo-100/70',
            surface: 'bg-white/70'
        },
        {
            label: 'Highest',
            value: hasScores ? highestScore : '--',
            icon: CrownOutlined,
            accent: 'text-amber-600',
            glow: 'bg-amber-100/70',
            surface: 'bg-white/70'
        },
        {
            label: 'Pass Rate',
            value: hasScores ? `${((passCount / scoredCount) * 100).toFixed(0)}%` : '--',
            icon: CheckCircleOutlined,
            accent: 'text-emerald-600',
            glow: 'bg-emerald-100/70',
            surface: 'bg-white/70'
        },
    ];
    if (needsConfirmCount > 0) {
        metrics.push({
            label: 'Review Needed',
            value: needsConfirmCount,
            icon: ExclamationCircleOutlined,
            accent: 'text-amber-600',
            glow: 'bg-amber-100/70',
            surface: 'bg-amber-50/70'
        });
    }

    const ensureReviewDraft = useCallback(() => {
        setReviewDraft((prev) => (prev.length > 0 ? prev : buildReviewDraft(sortedResults)));
    }, [sortedResults]);

    // 获取存储的评分标准
    const parsedRubric = useConsoleStore((state) => state.parsedRubric);
    const rubricTotalQuestions = useMemo(() => {
        if (!parsedRubric) return null;
        const anyRubric: any = parsedRubric as any;
        const v = anyRubric.totalQuestions ?? anyRubric.total_questions;
        if (v !== undefined && v !== null && v !== '') return Number(v);
        const qs = Array.isArray(anyRubric.questions) ? anyRubric.questions : [];
        return qs.length;
    }, [parsedRubric]);
    const rubricTotalScore = useMemo(() => {
        if (!parsedRubric) return null;
        const anyRubric: any = parsedRubric as any;
        const v = anyRubric.totalScore ?? anyRubric.total_score;
        if (v !== undefined && v !== null && v !== '') return Number(v);
        const qs = Array.isArray(anyRubric.questions) ? anyRubric.questions : [];
        const sum = qs.reduce((acc: number, q: any) => acc + Number(q.maxScore ?? q.max_score ?? 0), 0);
        return Number.isFinite(sum) ? sum : null;
    }, [parsedRubric]);

    const fetchAnnotationsForStudent = useCallback(async (
        gradingHistoryId: string,
        studentKey: string,
        options?: { silent?: boolean }
    ): Promise<number> => {
        if (!gradingHistoryId || !studentKey) return 0;
        setAnnotationFetchLoading(true);
        try {
            const res = await fetch(`${apiBase}/annotations/${gradingHistoryId}/${encodeURIComponent(studentKey)}`);
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || payload?.message || '加载批注失败');
            }
            const payload = await res.json().catch(() => null);
            const annotations = Array.isArray(payload?.annotations) ? payload.annotations : [];
            if (annotations.length === 0) return 0;

            const next = new Map<number, PageAnnotation[]>();
            annotations.forEach((ann: any) => {
                const pageIndex = Number(ann.page_index);
                if (!Number.isFinite(pageIndex)) return;
                const list = next.get(pageIndex) ?? [];
                list.push({
                    id: ann.id,
                    annotation_type: ann.annotation_type,
                    bounding_box: ann.bounding_box,
                    text: ann.text || '',
                    color: ann.color,
                    question_id: ann.question_id,
                    scoring_point_id: ann.scoring_point_id,
                    page_index: pageIndex,
                } as PageAnnotation);
                next.set(pageIndex, list);
            });

            setPageAnnotationsData(next);
            return annotations.length;
        } catch (error) {
            if (!options?.silent) {
                throw error;
            }
            console.warn('加载批注失败:', error);
            return 0;
        } finally {
            setAnnotationFetchLoading(false);
        }
    }, [apiBase]);

    const handleGenerateAnnotations = useCallback(async (options?: { overwrite?: boolean }) => {
        const overwrite = Boolean(options?.overwrite);
        if (!annotationGradingHistoryId || !detailViewStudent?.studentName) {
            console.error('[批注生成] 缺少必要参数:', { submissionId, studentName: detailViewStudent?.studentName });
            setAnnotationStatus({ type: 'error', message: '缺少批改历史ID或学生姓名' });
            return;
        }
        const studentKey = detailViewStudent.studentName;
        if (overwrite) {
            // Avoid showing stale boxes while the backend deletes + regenerates.
            setPageAnnotationsData(new Map());
        }
        setAnnotationGenerating(true);
        setAnnotationStatus({ type: 'loading', message: 'AI 批注生成中...' });
        
        const url = `${apiBase}/annotations/generate`;
        const payload = {
            grading_history_id: annotationGradingHistoryId,
            student_key: studentKey,
            overwrite,
        };
        
        console.log('[批注生成] 开始请求:', { url, payload });
        
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            
            console.log('[批注生成] 响应状态:', res.status, res.statusText);
            
            const resPayload = await res.json().catch(() => null);
            console.log('[批注生成] 响应内容:', resPayload);
            
            if (!res.ok) {
                throw new Error(resPayload?.detail || resPayload?.message || `HTTP ${res.status}: ${res.statusText}`);
            }
            setShowAnnotations(true);
            const count = await fetchAnnotationsForStudent(annotationGradingHistoryId, studentKey, { silent: true });
            setAnnotationStatus({
                type: 'success',
                message: resPayload?.message || (count > 0 ? `已加载 ${count} 个批注` : '批注生成完成'),
            });
        } catch (error) {
            console.error('[批注生成] 失败:', error);
            setAnnotationStatus({
                type: 'error',
                message: error instanceof Error ? error.message : '生成批注失败',
            });
        } finally {
            setAnnotationGenerating(false);
        }
    }, [annotationGradingHistoryId, submissionId, detailViewStudent, apiBase, fetchAnnotationsForStudent]);

    const handleExportAnnotatedPdf = useCallback(async () => {
        if (!annotationGradingHistoryId || !detailViewStudent?.studentName) {
            console.error('[PDF Export] Missing params:', { annotationGradingHistoryId, studentName: detailViewStudent?.studentName });
            setExportStatus({ type: 'error', message: '缺少批改历史ID或学生姓名' });
            return;
        }
        setExportPdfLoading(true);
        setExportStatus({ type: 'loading', message: '正在导出批注版 PDF...' });

        const url = `${apiBase}/annotations/export/pdf`;
        const payload = {
            grading_history_id: annotationGradingHistoryId,
            student_key: detailViewStudent.studentName,
            include_summary: true,
        };

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const errPayload = await res.json().catch(() => null);
                throw new Error(errPayload?.detail || errPayload?.message || `HTTP ${res.status}: ${res.statusText}`);
            }

            const blob = await res.blob();
            const objUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = objUrl;

            // Prefer backend-provided filename if present.
            const disposition = res.headers.get('content-disposition') || '';
            const filenameStar = disposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
            const filenamePlain = disposition.match(/filename\s*=\s*"?([^";]+)"?/i);
            const headerFilename = filenameStar?.[1]
                ? decodeURIComponent(filenameStar[1])
                : filenamePlain?.[1];
            a.download = headerFilename || `annotated_${detailViewStudent.studentName}.pdf`;

            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(objUrl);
            setExportStatus({ type: 'success', message: '已导出批注 PDF' });
        } catch (error) {
            console.error('[PDF Export] Failed:', error);
            setExportStatus({ type: 'error', message: error instanceof Error ? error.message : '导出失败' });
        } finally {
            setExportPdfLoading(false);
        }
    }, [annotationGradingHistoryId, detailViewStudent, apiBase]);

    const handleAnnotationDelete = useCallback(async (pageIdx: number, annotationId: string) => {
        if (!annotationId) return;
        try {
            const res = await fetch(`${apiBase}/annotations/${annotationId}`, {
                method: 'DELETE',
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || payload?.message || '删除批注失败');
            }
            updatePageAnnotations(pageIdx, (current) => current.filter((ann) => ann.id !== annotationId));
            setAnnotationStatus({ type: 'success', message: '批注已删除' });
        } catch (error) {
            setAnnotationStatus({
                type: 'error',
                message: error instanceof Error ? error.message : '删除批注失败',
            });
        }
    }, [apiBase, updatePageAnnotations]);

    const handleAnnotationAdd = useCallback(async (pageIdx: number, annotation: AnnotationEditorPayload) => {
        if (!annotationGradingHistoryId || !detailViewStudent?.studentName) {
            setAnnotationStatus({ type: 'error', message: '缺少批改历史ID或学生姓名' });
            return;
        }
        try {
            const res = await fetch(`${apiBase}/annotations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    grading_history_id: annotationGradingHistoryId,
                    student_key: detailViewStudent.studentName,
                    page_index: pageIdx,
                    annotation,
                }),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || payload?.message || '添加批注失败');
            }
            const created = await res.json().catch(() => null);
            if (!created) {
                throw new Error('添加批注失败：服务端未返回批注数据');
            }
            updatePageAnnotations(pageIdx, (current) => [
                ...current,
                {
                    id: created.id,
                    annotation_type: created.annotation_type,
                    bounding_box: created.bounding_box,
                    text: created.text || '',
                    color: created.color,
                    question_id: created.question_id,
                    scoring_point_id: created.scoring_point_id,
                    page_index: pageIdx,
                } as PageAnnotation,
            ]);
            setAnnotationStatus({ type: 'success', message: '批注已添加' });
        } catch (error) {
            setAnnotationStatus({
                type: 'error',
                message: error instanceof Error ? error.message : '添加批注失败',
            });
        }
    }, [annotationGradingHistoryId, detailViewStudent, apiBase, updatePageAnnotations]);

    const handleAnnotationUpdate = useCallback(async (
        pageIdx: number,
        annotationId: string,
        updates: Partial<PageAnnotation>
    ) => {
        if (!annotationId) return;
        try {
            const res = await fetch(`${apiBase}/annotations/${annotationId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bounding_box: updates.bounding_box,
                    text: updates.text,
                    color: updates.color,
                    annotation_type: updates.annotation_type,
                }),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || payload?.message || '更新批注失败');
            }
            updatePageAnnotations(pageIdx, (current) => current.map((ann) => (
                ann.id === annotationId ? { ...ann, ...updates } : ann
            )));
        } catch (error) {
            setAnnotationStatus({
                type: 'error',
                message: error instanceof Error ? error.message : '更新批注失败',
            });
        }
    }, [apiBase, updatePageAnnotations]);

    // 当切换学生或关闭批注时，清理已渲染的图片缓存

    // When annotations are enabled, only load backend-generated annotations (VLM/LLM).
    useEffect(() => {
        if (!showAnnotations || !detailViewStudent) return;
        if (!annotationGradingHistoryId) return;

        const studentKey = detailViewStudent.studentName || `student-${detailViewIndex}`;
        let cancelled = false;

        const loadAnnotations = async () => {
            const count = await fetchAnnotationsForStudent(annotationGradingHistoryId, studentKey, { silent: true });
            if (cancelled) return;
            if (count === 0) {
                // No local estimated fallback: keep UI honest about precision.
                setAnnotationStatus((prev) => {
                    if (prev.type === 'success' || prev.type === 'error') return prev;
                    return { type: 'idle', message: '暂无 AI 批注：点击生成批注，由 VLM 自动定位。' };
                });
            }
        };

        void loadAnnotations();
        return () => {
            cancelled = true;
        };
    }, [showAnnotations, detailViewStudent, detailViewIndex, annotationGradingHistoryId, fetchAnnotationsForStudent]);

    useEffect(() => {
        if (!showAnnotations) {
            // 关闭批注时清理
            setPageAnnotationsData(new Map());
        }
    }, [showAnnotations]);

    // 切换学生时清理该学生的渲染缓存
    useEffect(() => {
        setPageAnnotationsData(new Map());
    }, [detailViewIndex]);

    useEffect(() => {
        if (reviewMode) {
            ensureReviewDraft();
        }
    }, [reviewMode, ensureReviewDraft]);

    useEffect(() => {
        if (!reviewMode) return;
        if (detailViewIndex === null && sortedResults.length > 0) {
            setDetailViewIndex(0);
        }
    }, [reviewMode, detailViewIndex, sortedResults.length]);

    useEffect(() => {
        setAuditOpen(false);
        setAuditQuery('');
    }, [detailViewIndex]);

    // ==================== 导出处理函数 ====================

    const handleExportExcel = async () => {
        if (!submissionId) return;
        setExportLoading('excel');
        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/batch/export/excel/${submissionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            if (!response.ok) throw new Error('导出失败');
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `grading_report_${submissionId}.xlsx`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('导出 Excel 失败:', error);
        } finally {
            setExportLoading(null);
            setExportMenuOpen(false);
        }
    };

    const handleSmartExcelSubmit = async () => {
        if (!submissionId || !smartExcelPrompt.trim()) return;
        setSmartExcelLoading(true);
        try {
            let templateBase64: string | undefined;
            if (smartExcelTemplate) {
                const reader = new FileReader();
                templateBase64 = await new Promise((resolve) => {
                    reader.onload = () => resolve(reader.result as string);
                    reader.readAsDataURL(smartExcelTemplate);
                });
            }

            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/batch/export/smart-excel/${submissionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: smartExcelPrompt,
                    template_base64: templateBase64,
                }),
            });
            if (!response.ok) throw new Error('生成失败');
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `grading_smart_${submissionId}.xlsx`;
            a.click();
            URL.revokeObjectURL(url);
            setSmartExcelOpen(false);
            setSmartExcelPrompt('');
            setSmartExcelTemplate(null);
        } catch (error) {
            console.error('智能 Excel 生成失败:', error);
        } finally {
            setSmartExcelLoading(false);
        }
    };

    const handleToggleReviewMode = () => {
        setReviewMessage(null);
        setReviewError(null);
        if (!reviewMode) {
            setReviewDraft(buildReviewDraft(sortedResults));
            setReviewSelectedKeys(new Set());
            setReviewGlobalNote('');
            if (detailViewIndex === null && sortedResults.length > 0) {
                setDetailViewIndex(0);
            }
        } else {
            setDetailViewIndex(null);
            setReviewSelectedKeys(new Set());
            setReviewGlobalNote('');
        }
        setReviewMode((prev) => !prev);
    };

    const updateReviewQuestion = useCallback(
        (studentIndex: number, questionId: string, field: keyof ReviewQuestionDraft, value: any) => {
            setReviewDraft((prev) =>
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

    const toggleReviewSelected = (studentIndex: number, questionId: string) => {
        const key = `${studentIndex}:${questionId}`;
        setReviewSelectedKeys((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    const handleReviewApprove = async () => {
        if (!submissionId) return;
        setReviewSubmitting(true);
        setReviewMessage(null);
        setReviewError(null);
        try {
            await gradingApi.submitResultsReview({ batch_id: submissionId, action: 'approve' });
            setReviewMessage('已确认批改结果，流程继续进行。');
        } catch (err) {
            setReviewError(err instanceof Error ? err.message : '提交失败');
        } finally {
            setReviewSubmitting(false);
        }
    };

    const handleReviewUpdate = async () => {
        if (!submissionId || reviewDraft.length === 0) return;
        setReviewSubmitting(true);
        setReviewMessage(null);
        setReviewError(null);
        try {
            await gradingApi.submitResultsReview({
                batch_id: submissionId,
                action: 'update',
                results: buildResultsOverridePayload(reviewDraft),
            });
            setReviewMessage('已提交修正结果，流程继续进行。');
        } catch (err) {
            setReviewError(err instanceof Error ? err.message : '提交失败');
        } finally {
            setReviewSubmitting(false);
        }
    };

    const handleReviewRegrade = async () => {
        if (!submissionId || reviewSelectedKeys.size === 0) return;
        setReviewSubmitting(true);
        setReviewMessage(null);
        setReviewError(null);
        const regradeItems: Array<Record<string, any>> = [];
        const noteLines: string[] = [];
        const trimmedGlobal = reviewGlobalNote.trim();
        if (trimmedGlobal) noteLines.push(trimmedGlobal);

        reviewDraft.forEach((student, sIdx) => {
            student.questionResults.forEach((q) => {
                const key = `${sIdx}:${q.questionId}`;
                if (!reviewSelectedKeys.has(key)) return;
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
                batch_id: submissionId,
                action: 'regrade',
                regrade_items: regradeItems,
                notes: noteLines.join('\n'),
            });
            setReviewMessage('已提交重新批改请求，请稍后刷新查看结果。');
        } catch (err) {
            setReviewError(err instanceof Error ? err.message : '提交失败');
        } finally {
            setReviewSubmitting(false);
        }
    };

    const loadRubricContext = useCallback(async () => {
        if (!submissionId) return;
        setRubricLoading(true);
        setRubricError(null);
        try {
            const data = await gradingApi.getRubricReviewContext(submissionId);
            const parsed = normalizeRubricDraft(data.parsed_rubric || {});
            setRubricDraft(parsed);
            
            // 同步到 consoleStore，让 RubricOverview 组件也能访问
            // 转换为 ParsedRubric 类型
            useConsoleStore.getState().setParsedRubric(parsed as any);
            
            const images = (data.rubric_images || []).map((img: string) =>
                img.startsWith('data:') ? img : `data:image/jpeg;base64,${img}`
            );
            setRubricImages(images);
        } catch (err) {
            setRubricError(err instanceof Error ? err.message : 'Failed to load rubric context.');
        } finally {
            setRubricLoading(false);
        }
    }, [submissionId]);

    useEffect(() => {
        if (rubricOpen && rubricDraft === null) {
            loadRubricContext();
        }
    }, [rubricOpen, rubricDraft, loadRubricContext]);

    // 组件初始化时自动加载 rubric 数据，让 RubricOverview 能显示
    useEffect(() => {
        if (submissionId && !useConsoleStore.getState().parsedRubric) {
            loadRubricContext();
        }
    }, [submissionId, loadRubricContext]);

    const toggleRubricSelected = useCallback((questionId: string) => {
        setRubricSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(questionId)) {
                next.delete(questionId);
            } else {
                next.add(questionId);
            }
            return next;
        });
    }, []);

    const toggleRubricExpanded = useCallback((questionId: string) => {
        setRubricExpandedIds((prev) => {
            const next = new Set(prev);
            if (next.has(questionId)) {
                next.delete(questionId);
            } else {
                next.add(questionId);
            }
            return next;
        });
    }, []);

    const updateRubricQuestion = useCallback((questionId: string, field: keyof RubricQuestionDraft, value: any) => {
        setRubricDraft((prev: ParsedRubricDraft | null) => {
            if (!prev) return prev;
            return {
                ...prev,
                questions: prev.questions.map((q) => (q.questionId === questionId ? { ...q, [field]: value } : q)),
            };
        });
    }, []);

    const updateRubricScoringPoint = useCallback(
        (questionId: string, index: number, field: keyof RubricScoringPointDraft, value: any) => {
            setRubricDraft((prev: ParsedRubricDraft | null) => {
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

    const addRubricScoringPoint = useCallback((questionId: string) => {
        setRubricDraft((prev: ParsedRubricDraft | null) => {
            if (!prev) return prev;
            return {
                ...prev,
                questions: prev.questions.map((q) => {
                    if (q.questionId !== questionId) return q;
                    const nextIndex = q.scoringPoints.length + 1;
                    const newPoint: RubricScoringPointDraft = {
                        pointId: `${questionId}.${nextIndex}`,
                        description: '',
                        expectedValue: '',
                        score: 0,
                        isRequired: true,
                        keywords: [],
                    };
                    return { ...q, scoringPoints: [...q.scoringPoints, newPoint] };
                }),
            };
        });
    }, []);

    const removeRubricScoringPoint = useCallback((questionId: string, index: number) => {
        setRubricDraft((prev: ParsedRubricDraft | null) => {
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

    const handleRubricApprove = async () => {
        if (!submissionId) return;
        setRubricSubmitting(true);
        setRubricMessage(null);
        setRubricError(null);
        try {
            await gradingApi.submitRubricReview({ batch_id: submissionId, action: 'approve' });
            setRubricMessage('已确认解析结果，批改流程继续进行。');
        } catch (err) {
            setRubricError(err instanceof Error ? err.message : '提交失败');
        } finally {
            setRubricSubmitting(false);
        }
    };

    const handleRubricUpdate = async () => {
        if (!submissionId || !rubricDraft) return;
        setRubricSubmitting(true);
        setRubricMessage(null);
        setRubricError(null);
        try {
            await gradingApi.submitRubricReview({
                batch_id: submissionId,
                action: 'update',
                parsed_rubric: buildRubricPayload(rubricDraft),
            });
            setRubricMessage('已提交修正，批改流程继续进行。');
        } catch (err) {
            setRubricError(err instanceof Error ? err.message : '提交失败');
        } finally {
            setRubricSubmitting(false);
        }
    };

    const handleRubricReparse = async () => {
        if (!submissionId || !rubricDraft || rubricSelectedIds.size === 0) return;
        setRubricSubmitting(true);
        setRubricMessage(null);
        setRubricError(null);
        const noteLines: string[] = [];
        const trimmedGlobal = rubricGlobalNote.trim();
        if (trimmedGlobal) noteLines.push(trimmedGlobal);
        rubricDraft.questions.forEach((q: RubricQuestionDraft) => {
            if (!rubricSelectedIds.has(q.questionId)) return;
            const note = q.reviewNote.trim();
            if (note) {
                noteLines.push(`Q${q.questionId}: ${note}`);
            }
        });
        try {
            await gradingApi.submitRubricReview({
                batch_id: submissionId,
                action: 'reparse',
                selected_question_ids: Array.from(rubricSelectedIds),
                notes: noteLines.join('\n'),
            });
            setRubricMessage('已提交重解析请求，请稍后刷新查看结果。');
        } catch (err) {
            setRubricError(err instanceof Error ? err.message : '提交失败');
        } finally {
            setRubricSubmitting(false);
        }
    };

    // === Helper Functions (定义在所有早期返回之前，避免 React Error #300) ===
    const handleSelectStudent = useCallback((index: number) => setDetailViewIndex(index), []);
    const handleViewDetail = useCallback((student: StudentResult) => {
        const index = sortedResults.findIndex(r => r.studentName === student.studentName);
        setDetailViewIndex(index >= 0 ? index : 0);
    }, [sortedResults]);

    // 手动重试获取结果
    const handleRetryFetch = useCallback(async () => {
        if (!submissionId) return;

        // 清除已尝试标记，允许重试
        apiFallbackAttemptedRef.current.delete(submissionId);
        setApiFallbackLoading(true);
        setApiFallbackError(null);

        try {
            console.log('[Manual Retry] Fetching results for batch:', submissionId);
            const response = await gradingApi.getBatchResults(submissionId);

            // 后端可能返回 results（camelCase）或 student_results（snake_case）
            const rawResults = (response as any).results || response.student_results || [];
            console.log('[Manual Retry] Raw results:', rawResults.length, 'items');

            if (rawResults.length > 0) {
                // 检测数据格式（camelCase 或 snake_case）
                const firstResult = rawResults[0];
                const isCamelCase = 'studentName' in firstResult;
                console.log('[Manual Retry] Data format:', isCamelCase ? 'camelCase' : 'snake_case');

                // 转换 API 响应格式到前端格式
                const formattedResults: StudentResult[] = rawResults.map((r: any) => {
                    if (isCamelCase) {
                        return {
                            studentName: r.studentName || 'Unknown',
                            score: r.score || 0,
                            maxScore: r.maxScore || 100,
                            startPage: r.startPage,
                            endPage: r.endPage,
                            pageRange: r.pageRange,
                            confidence: r.confidence,
                            needsConfirmation: r.needsConfirmation,
                            gradingMode: r.gradingMode,
                            studentSummary: r.studentSummary,
                            selfAudit: r.selfAudit,
                            questionResults: (r.questionResults || []).map((q: any) => ({
                                questionId: q.questionId || '',
                                score: q.score || 0,
                                maxScore: q.maxScore || 0,
                                feedback: q.feedback || '',
                                confidence: q.confidence,
                                confidenceReason: q.confidenceReason,
                                selfCritique: q.selfCritique,
                                selfCritiqueConfidence: q.selfCritiqueConfidence,
                                rubricRefs: q.rubricRefs,
                                typoNotes: q.typoNotes,
                                pageIndices: q.pageIndices,
                                isCrossPage: q.isCrossPage,
                                mergeSource: q.mergeSource,
                                audit: q.audit,
                                scoringPointResults: (q.scoringPointResults || []).map((spr: any) => ({
                                    pointId: spr.pointId || spr.scoringPoint?.pointId,
                                    description: spr.description || spr.scoringPoint?.description || '',
                                    awarded: spr.awarded ?? 0,
                                    maxPoints: spr.maxPoints ?? spr.scoringPoint?.score ?? 0,
                                    evidence: spr.evidence || '',
                                    rubricReference: spr.rubricReference,
                                    rubricReferenceSource: spr.rubricReferenceSource,
                                    decision: spr.decision,
                                    reason: spr.reason,
                                    scoringPoint: spr.scoringPoint ? {
                                        description: spr.scoringPoint.description || '',
                                        score: spr.scoringPoint.score || 0,
                                        maxScore: spr.scoringPoint.score || 0,
                                        isCorrect: (spr.awarded ?? 0) > 0,
                                        isRequired: spr.scoringPoint.isRequired,
                                        explanation: spr.reason || spr.evidence || '',
                                    } : undefined,
                                })),
                            })),
                        };
                    } else {
                        return {
                            studentName: r.student_name || 'Unknown',
                            score: r.total_score || 0,
                            maxScore: r.max_score || 100,
                            startPage: r.start_page,
                            endPage: r.end_page,
                            confidence: r.confidence,
                            needsConfirmation: r.needs_confirmation,
                            questionResults: (r.questions || []).map((q: any) => ({
                                questionId: q.question_id || '',
                                score: q.score || 0,
                                maxScore: q.max_score || 0,
                                feedback: q.feedback || '',
                                confidence: q.confidence,
                                confidenceReason: q.confidence_reason,
                                selfCritique: q.self_critique,
                                selfCritiqueConfidence: q.self_critique_confidence,
                                rubricRefs: q.rubric_refs,
                                typoNotes: q.typo_notes,
                                pageIndices: q.page_indices,
                                isCrossPage: q.is_cross_page,
                                mergeSource: q.merge_source,
                                audit: q.audit,
                                scoringPointResults: (q.scoring_point_results || []).map((spr: any) => ({
                                    pointId: spr.point_id || spr.scoring_point?.point_id,
                                    description: spr.description || spr.scoring_point?.description || '',
                                    awarded: spr.awarded ?? 0,
                                    maxPoints: spr.max_points ?? spr.scoring_point?.score ?? 0,
                                    evidence: spr.evidence || '',
                                    rubricReference: spr.rubric_reference,
                                    rubricReferenceSource: spr.rubric_reference_source,
                                    decision: spr.decision,
                                    reason: spr.reason,
                                    scoringPoint: spr.scoring_point ? {
                                        description: spr.scoring_point.description || '',
                                        score: spr.scoring_point.score || 0,
                                        maxScore: spr.scoring_point.score || 0,
                                        isCorrect: (spr.awarded ?? 0) > 0,
                                        isRequired: spr.scoring_point.is_required,
                                        explanation: spr.reason || spr.evidence || '',
                                    } : undefined,
                                })),
                            })),
                        };
                    }
                });

                console.log('[Manual Retry] Successfully fetched', formattedResults.length, 'results');
                setFinalResults(formattedResults);
            } else {
                setApiFallbackError('API 返回空结果');
            }
        } catch (error) {
            console.error('[Manual Retry] Failed:', error);
            setApiFallbackError(error instanceof Error ? error.message : '获取结果失败');
        } finally {
            setApiFallbackLoading(false);
        }
    }, [submissionId, setFinalResults]);

    // === Conditional Returns (所有 hooks 必须在这些返回之前定义) ===

    if (rubricOpen) {
        return (
            <div className="h-full min-h-0 flex flex-col bg-white">
                <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0 z-20">
                    <div className="flex items-center gap-4">
                        <SmoothButton
                            onClick={() => {
                                setRubricOpen(false);
                                setRubricMessage(null);
                                setRubricError(null);
                            }}
                            variant="ghost"
                            size="sm"
                            className="!p-2"
                        >
                            <ArrowLeft className="w-5 h-5 text-slate-500" />
                        </SmoothButton>
                        <div>
                            <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                                <BookOpen className="w-5 h-5 text-emerald-500" />
                                批改标准复核
                            </h2>
                            <p className="text-xs text-slate-500">对照原始批改标准进行校验与修正</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <SmoothButton
                            onClick={handleRubricApprove}
                            isLoading={rubricSubmitting}
                            variant="secondary"
                            size="sm"
                        >
                            <CheckCircle className="w-4 h-4 mr-2" /> 确认无误
                        </SmoothButton>
                        <SmoothButton
                            onClick={handleRubricUpdate}
                            isLoading={rubricSubmitting}
                            variant="primary"
                            size="sm"
                        >
                            <GitMerge className="w-4 h-4 mr-2" /> 提交修正
                        </SmoothButton>
                    </div>
                </div>

                <div className="flex-1 min-h-0 overflow-hidden flex">
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-white">
                        {rubricImages.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>暂无批改标准图片</span>
                            </div>
                        ) : (
                            rubricImages.map((img, idx) => (
                                <div key={idx} className={clsx("pb-6 border-b border-slate-100/80 space-y-2", idx === rubricImages.length - 1 && "border-b-0 pb-0")}>
                                    <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
                                        Page {idx + 1}
                                    </div>
                                    <img src={img} alt={`Rubric page ${idx + 1}`} className="w-full h-auto" />
                                </div>
                            ))
                        )}
                    </div>

                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-white p-8 custom-scrollbar">
                        <div className="max-w-2xl mx-auto space-y-6">
                            {(rubricError || rubricMessage) && (
                                <div className={clsx(
                                    "rounded-lg px-3 py-2 text-xs",
                                    rubricError ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
                                )}>
                                    {rubricError || rubricMessage}
                                </div>
                            )}
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div className="text-sm text-slate-500">
                                    共 {rubricDraft?.questions?.length ?? 0} 题，总分 <span className="font-semibold text-slate-900">{rubricDraft?.totalScore ?? 0}</span>
                                </div>
                                <SmoothButton
                                    onClick={handleRubricReparse}
                                    disabled={rubricSubmitting || rubricSelectedIds.size === 0}
                                    variant="ghost"
                                    size="sm"
                                >
                                    重新解析({rubricSelectedIds.size})
                                </SmoothButton>
                            </div>

                            <div className="grid gap-3 md:grid-cols-2">
                                <div>
                                    <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">总备注</label>
                                    <input
                                        value={rubricDraft?.generalNotes || ''}
                                        onChange={(e) => rubricDraft && setRubricDraft({ ...rubricDraft, generalNotes: e.target.value })}
                                        className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                                        placeholder="扣分规则/补充说明"
                                    />
                                </div>
                                <div>
                                    <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">重解析说明</label>
                                    <input
                                        value={rubricGlobalNote}
                                        onChange={(e) => setRubricGlobalNote(e.target.value)}
                                        className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                                        placeholder="告诉 AI 哪里解析有问题"
                                    />
                                </div>
                            </div>

                            {rubricLoading && (
                                <div className="text-sm text-slate-400">正在加载批改标准...</div>
                            )}

                            {!rubricLoading && !rubricDraft && (
                                <div className="text-sm text-slate-400">暂无批改标准数据</div>
                            )}

                            {!rubricLoading && rubricDraft && (
                                <div className="space-y-4">
                                    {rubricDraft.questions.map((q: RubricQuestionDraft) => {
                                        const isSelected = rubricSelectedIds.has(q.questionId);
                                        const isExpanded = rubricExpandedIds.has(q.questionId);
                                        return (
                                            <div
                                                key={q.questionId}
                                                className={clsx(
                                                    "py-4 border-b border-slate-100 last:border-b-0",
                                                    isSelected && "bg-rose-50/40"
                                                )}
                                            >
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
                                                        <SmoothButton
                                                            onClick={() => toggleRubricExpanded(q.questionId)}
                                                            variant="ghost"
                                                            size="sm"
                                                            className="!px-2"
                                                        >
                                                            {isExpanded ? '收起详情' : '展开详情'}
                                                        </SmoothButton>
                                                        <label className="flex items-center gap-2 cursor-pointer rounded-full border border-slate-200 px-2 py-1 text-[10px] font-medium text-slate-500 hover:border-rose-200 hover:bg-rose-50 transition-colors">
                                                            <input
                                                                type="checkbox"
                                                                checked={isSelected}
                                                                onChange={() => toggleRubricSelected(q.questionId)}
                                                                className="h-3.5 w-3.5 rounded border-slate-300 text-rose-500 focus:ring-rose-500"
                                                            />
                                                            <span className={clsx(isSelected ? "text-rose-500" : "text-slate-500")}>标记问题</span>
                                                        </label>
                                                    </div>
                                                </div>

                                                <div className="mt-3 space-y-3 text-xs text-slate-600">
                                                    <div>
                                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">题目内容</div>
                                                        <div className="mt-1 text-[13px] font-semibold text-slate-800 leading-snug">
                                                            <MathText className="whitespace-pre-wrap" text={q.questionText || '—'} />
                                                        </div>
                                                    </div>
                                                    {q.standardAnswer && (
                                                        <div>
                                                            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">标准答案</div>
                                                            <div className="mt-1 text-[12px] text-slate-700">
                                                                <MathText className="whitespace-pre-wrap" text={q.standardAnswer} />
                                                            </div>
                                                        </div>
                                                    )}
                                                    {q.gradingNotes && (
                                                        <div>
                                                            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">备注</div>
                                                            <div className="mt-1 text-[12px] text-slate-700">
                                                                <MathText className="whitespace-pre-wrap" text={q.gradingNotes} />
                                                            </div>
                                                        </div>
                                                    )}
                                                    {q.criteria && q.criteria.length > 0 && (
                                                        <div>
                                                            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">评分要点</div>
                                                            <div className="mt-1 text-[12px] text-slate-700">{q.criteria.join(' · ')}</div>
                                                        </div>
                                                    )}
                                                    {q.scoringPoints.length > 0 && (
                                                        <div>
                                                            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">评分点</div>
                                                            <div className="mt-2 space-y-1 text-[11px] text-slate-600 leading-snug">
                                                                {q.scoringPoints.map((sp: RubricScoringPointDraft) => (
                                                                    <div key={sp.pointId} className="flex items-start gap-2">
                                                                        <span className="font-mono text-slate-400">{sp.pointId}</span>
                                                                        <span className="flex-1">
                                                                            {sp.description || '—'}
                                                                            {sp.expectedValue ? ` | 期望: ${sp.expectedValue}` : ''}
                                                                            {sp.keywords && sp.keywords.length > 0 ? ` | 关键词 ${sp.keywords.join(', ')}` : ''}
                                                                        </span>
                                                                        <span className="font-semibold text-slate-700">{sp.score}</span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>

                                                <div className="mt-3">
                                                    <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">解析问题备注</label>
                                                    <textarea
                                                        value={q.reviewNote}
                                                        onChange={(e) => updateRubricQuestion(q.questionId, 'reviewNote', e.target.value)}
                                                        className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
                                                        rows={2}
                                                        placeholder="说明需要重解析的原因"
                                                    />
                                                </div>

                                                {isExpanded && q.sourcePages.length > 0 && (
                                                    <div className="mt-3 rounded-xl border border-slate-200 bg-white/80 p-3 space-y-3">
                                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">来源页</div>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            {q.sourcePages.map((pageIndex) => (
                                                                <div key={`${q.questionId}-page-${pageIndex}`} className="rounded-lg border border-slate-200 bg-white p-2">
                                                                    <div className="text-[10px] text-slate-400 mb-1">Page {pageIndex + 1}</div>
                                                                    {rubricImages[pageIndex] ? (
                                                                        <img
                                                                            src={rubricImages[pageIndex]}
                                                                            alt={`Evidence ${pageIndex + 1}`}
                                                                            className="h-28 w-full object-contain"
                                                                        />
                                                                    ) : (
                                                                        <div className="text-xs text-slate-400">No image</div>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (reviewMode) {
        if (!reviewStudent) {
            return (
                <div className="h-full min-h-0 flex flex-col bg-white">
                    <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0 z-20">
                        <div className="flex items-center gap-4">
                            <SmoothButton onClick={handleToggleReviewMode} variant="ghost" size="sm" className="!p-2">
                                <ArrowLeft className="w-5 h-5 text-slate-500" />
                            </SmoothButton>
                            <div>
                                <h2 className="text-xl font-bold text-slate-800">批改结果复核</h2>
                                <p className="text-xs text-slate-500">暂无可复核的批改数据</p>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        const selectedKeyPrefix = `${clampedReviewIndex}:`;

        return (
            <div className="h-full min-h-0 flex flex-col bg-white">
                <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0 z-20">
                    <div className="flex items-center gap-4">
                        <SmoothButton onClick={handleToggleReviewMode} variant="ghost" size="sm" className="!p-2">
                            <ArrowLeft className="w-5 h-5 text-slate-500" />
                        </SmoothButton>
                        <div>
                            <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                                <CheckCircle className="w-5 h-5 text-blue-500" />
                                批改结果复核
                            </h2>
                            <p className="text-xs text-slate-500">可以随时调整评分或发起重批</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <SmoothButton
                            onClick={handleReviewApprove}
                            isLoading={reviewSubmitting}
                            variant="secondary"
                            size="sm"
                        >
                            <CheckCircle className="w-4 h-4 mr-2" /> 确认无误
                        </SmoothButton>
                        <SmoothButton
                            onClick={handleReviewUpdate}
                            isLoading={reviewSubmitting}
                            variant="primary"
                            size="sm"
                        >
                            <GitMerge className="w-4 h-4 mr-2" /> 提交修正
                        </SmoothButton>
                    </div>
                </div>

                <div className="flex-1 min-h-0 overflow-hidden flex">
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-white">
                        <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                            <span>学生作答</span>
                            <span>{reviewStudent.studentName}</span>
                        </div>
                        {reviewPageIndices.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>暂无作答图片</span>
                            </div>
                        ) : (
                            reviewPageIndices.map((pageIdx, pageIdxIndex) => {
                                const imageUrl = uploadedImages[pageIdx] || currentSession?.images[pageIdx]?.url;
                                const isLastPage = pageIdxIndex === reviewPageIndices.length - 1;
                                return (
                                    <div key={pageIdx} className={clsx("pb-6 border-b border-slate-100/80 space-y-2", isLastPage && "border-b-0 pb-0")}>
                                        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
                                            Page {pageIdx + 1}
                                        </div>
                                        {imageUrl ? (
                                            // 检查是否是 base64 数据，如果是则添加 data URI 前缀
                                            imageUrl.startsWith('data:') || imageUrl.startsWith('/9j/') ? (
                                                <img 
                                                    src={imageUrl.startsWith('data:') ? imageUrl : `data:image/jpeg;base64,${imageUrl}`} 
                                                    alt={`Page ${pageIdx + 1}`} 
                                                    className="w-full h-auto" 
                                                />
                                            ) : (
                                                <img src={imageUrl} alt={`Page ${pageIdx + 1}`} className="w-full h-auto" />
                                            )
                                        ) : (
                                            <div className="p-10 text-center text-slate-400">Image missing</div>
                                        )}
                                    </div>
                                );
                            })
                        )}
                    </div>

                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-white p-8 custom-scrollbar">
                        <div className="max-w-2xl mx-auto space-y-6">
                            {(reviewError || reviewMessage) && (
                                <div className={clsx(
                                    "rounded-lg px-3 py-2 text-xs",
                                    reviewError ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600"
                                )}>
                                    {reviewError || reviewMessage}
                                </div>
                            )}
                            <div className="flex items-center justify-between">
                                <div className="text-sm text-slate-500">
                                    总分 <span className="text-lg font-bold text-slate-900">{reviewScoreSummary.total}</span>
                                    <span className="text-slate-400"> / {reviewScoreSummary.max}</span>
                                </div>
                                <SmoothButton
                                    onClick={handleReviewRegrade}
                                    disabled={reviewSubmitting || reviewSelectedKeys.size === 0}
                                    variant="ghost"
                                    size="sm"
                                >
                                    重新批改({reviewSelectedKeys.size})
                                </SmoothButton>
                            </div>

                            <div className="flex flex-wrap gap-2">
                                {reviewDraft.map((student, idx) => (
                                    <button
                                        key={`${student.studentName}-${idx}`}
                                        onClick={() => setDetailViewIndex(idx)}
                                        className={clsx(
                                            "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
                                            idx === clampedReviewIndex
                                                ? "bg-slate-900 text-white"
                                                : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                                        )}
                                    >
                                        {student.studentName}
                                    </button>
                                ))}
                            </div>

                            <div>
                                <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">重批说明</label>
                                <input
                                    value={reviewGlobalNote}
                                    onChange={(e) => setReviewGlobalNote(e.target.value)}
                                    className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                                    placeholder="说明需要重批的原因（全局备注）"
                                />
                            </div>

                            <div className="space-y-4">
                                {reviewStudent.questionResults.map((q) => {
                                    const key = `${selectedKeyPrefix}${q.questionId}`;
                                    const isSelected = reviewSelectedKeys.has(key);
                                    return (
                                        <div
                                            key={q.questionId}
                                            className={clsx(
                                                "py-4 border-b border-slate-100 last:border-b-0",
                                                isSelected && "bg-rose-50/40"
                                            )}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                                                        {q.questionId}
                                                    </div>
                                                    <div className="flex items-baseline gap-1 text-sm font-medium text-slate-900">
                                                        <input
                                                            value={q.score}
                                                            onChange={(e) => updateReviewQuestion(clampedReviewIndex, q.questionId, 'score', Number(e.target.value))}
                                                            type="number"
                                                            className="w-12 rounded border-none bg-transparent p-0 text-right font-bold hover:bg-slate-100 focus:ring-0"
                                                        />
                                                        <span className="text-slate-400 text-xs">/ {q.maxScore}</span>
                                                    </div>
                                                </div>
                                                <label className="flex items-center gap-2 cursor-pointer rounded-full border border-slate-200 px-2 py-1 text-[10px] font-medium text-slate-500 hover:border-rose-200 hover:bg-rose-50 transition-colors">
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => toggleReviewSelected(clampedReviewIndex, q.questionId)}
                                                        className="h-3.5 w-3.5 rounded border-slate-300 text-rose-500 focus:ring-rose-500"
                                                    />
                                                    <span className={clsx(isSelected ? "text-rose-500" : "text-slate-500")}>标记重批</span>
                                                </label>
                                            </div>

                                            <div className="mt-3">
                                                <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">评语</label>
                                                <textarea
                                                    value={q.feedback}
                                                    onChange={(e) => updateReviewQuestion(clampedReviewIndex, q.questionId, 'feedback', e.target.value)}
                                                    className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:outline-none"
                                                    rows={2}
                                                />
                                            </div>

                                            <div className="mt-3 space-y-2 text-xs text-slate-500">
                                                {q.pageIndices && q.pageIndices.length > 0 && (
                                                    <div>Pages: {q.pageIndices.map((p) => p + 1).join(', ')}</div>
                                                )}
                                                <div>
                                                    <label className="text-[10px] uppercase tracking-[0.2em] text-slate-400">重批备注</label>
                                                    <input
                                                        value={q.reviewNote}
                                                        onChange={(e) => updateReviewQuestion(clampedReviewIndex, q.questionId, 'reviewNote', e.target.value)}
                                                        className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:border-emerald-500 focus:outline-none"
                                                        placeholder="说明需要重批的原因"
                                                    />
                                                </div>
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

    // === Detail View ===
    if (detailViewStudent) {
        // (Detail View Logic - Simplified for brevity but functionally complete with improved styles)
        const isAssist = (detailViewStudent.gradingMode || '').startsWith('assist') || detailViewStudent.maxScore <= 0;

        // 🔥 修改：优先使用 startPage/endPage 范围内的所有页面，不过滤"冗余"页面
        // 确保显示学生边界内的所有页面，而不只是有题目关联的页面
        let uniquePages: number[] = [];

        if (detailViewStudent.startPage !== undefined) {
            // 有学生边界时，显示边界内的所有页面
            const start = detailViewStudent.startPage;
            const end = detailViewStudent.endPage ?? start;
            for (let i = start; i <= end; i += 1) {
                uniquePages.push(i);
            }
        } else {
            // 没有边界时，从 questionResults 中收集 pageIndices 作为回退
            const pageIndices = detailViewStudent.questionResults?.flatMap(q => q.pageIndices || []) || [];
            uniquePages = Array.from(new Set(pageIndices));
        }

        // 过滤无效值并排序
        uniquePages = uniquePages
            .filter(p => Number.isFinite(p))
            .sort((a, b) => a - b);
        const auditItems = (detailViewStudent.questionResults || []).filter((q) => (
            Boolean(q.selfCritique)
            || Boolean(q.reviewSummary)
            || Boolean(q.honestyNote)
            || Boolean((q as any).confessionItems && (q as any).confessionItems.length > 0)
            || (q.reviewCorrections && q.reviewCorrections.length > 0)
            || (q.reviewReasons && q.reviewReasons.length > 0)
            || (q.auditFlags && q.auditFlags.length > 0)
        ));
        const auditQueryValue = auditQuery.trim().toLowerCase();
        const filteredAuditItems = auditQueryValue
            ? auditItems.filter((q) => {
                const haystack = [
                    q.questionId,
                    q.selfCritique,
                    q.reviewSummary,
                    q.honestyNote,
                    ...(((q as any).confessionItems || []) as any[]).map((it: any) => `${it?.severity || ''} ${it?.issue_type || it?.issueType || ''} ${it?.action || ''}`),
                    ...(q.reviewReasons || []),
                    ...(q.auditFlags || []),
                    ...(q.reviewCorrections || []).map((c) => `${c.pointId || ''} ${c.reviewReason || ''}`),
                ]
                    .filter(Boolean)
                    .join(' ')
                    .toLowerCase();
                return haystack.includes(auditQueryValue);
            })
            : [];

        return (
            <div className="h-full min-h-0 flex flex-col bg-white">
                {/* Navigation Header */}
                <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0 z-20">
                    <div className="flex items-center gap-4">
                        {!studentOnlyMode && (
                            <SmoothButton onClick={() => setDetailViewIndex(null)} variant="ghost" size="sm" className="!p-2">
                                <ArrowLeft className="w-5 h-5 text-slate-500" />
                            </SmoothButton>
                        )}
                        <div>
                            <h2 className="text-xl font-bold text-slate-800 flex items-center gap-3">
                                {detailViewStudent.studentName}
                                <span className={clsx("text-xs px-2 py-0.5 rounded font-medium bg-slate-100 text-slate-500 border border-slate-200")}>
                                    {isAssist ? 'Assist Mode' : 'Grading'}
                                </span>
                            </h2>
                        </div>
                    </div>
                    {/* Student Switcher Controls */}
                    {!studentOnlyMode && (
                        <div className="flex items-center gap-2">
                            <SmoothButton onClick={() => handleSelectStudent(Math.max(0, (detailViewIndex ?? 0) - 1))} disabled={detailViewIndex === 0} variant="ghost" size="sm" className="!p-2">
                                <ChevronDown className="w-4 h-4 rotate-90" />
                            </SmoothButton>
                            <span className="text-sm font-bold text-slate-500 tabular-nums">
                                {(detailViewIndex ?? 0) + 1} / {totalStudents}
                            </span>
                            <SmoothButton onClick={() => handleSelectStudent(Math.min(sortedResults.length - 1, (detailViewIndex ?? 0) + 1))} disabled={detailViewIndex === sortedResults.length - 1} variant="ghost" size="sm" className="!p-2">
                                <ChevronDown className="w-4 h-4 -rotate-90" />
                            </SmoothButton>
                        </div>
                    )}
                </div>

                <div className="flex-1 min-h-0 overflow-hidden flex">
                    {/* Image Panel */}
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-white">
                        {/* 批注工具栏 */}
                        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
                                答题图片
                            </span>
                            <div className="flex items-center gap-3">
                                {/* 生成批注按钮 */}
                                <button
                                    onClick={() => void handleGenerateAnnotations()}
                                    disabled={annotationGenerating || annotationFetchLoading}
                                    className="text-[11px] text-blue-600 hover:text-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                >
                                    {annotationGenerating && <Loader2 className="w-3 h-3 animate-spin" />}
                                    {annotationGenerating ? '生成中...' : '生成批注'}
                                </button>
                                {/* 导出 PDF 按钮 */}
                                <button
                                    onClick={() => {
                                        if (annotationGenerating || annotationFetchLoading) return;
                                        const ok = window.confirm('将删除该学生现有批注并覆盖重生成，确定继续？');
                                        if (!ok) return;
                                        void handleGenerateAnnotations({ overwrite: true });
                                    }}
                                    disabled={annotationGenerating || annotationFetchLoading}
                                    className="text-[11px] text-rose-600 hover:text-rose-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                    title="覆盖重生成该学生的批注"
                                >
                                    {annotationGenerating && <Loader2 className="w-3 h-3 animate-spin" />}
                                    {annotationGenerating ? '重生成中...' : '覆盖重生成'}
                                </button>
                                <button
                                    onClick={handleExportAnnotatedPdf}
                                    disabled={exportPdfLoading}
                                    className="text-[11px] text-emerald-600 hover:text-emerald-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                >
                                    {exportPdfLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                                    {exportPdfLoading ? '导出中...' : '导出批注 PDF'}
                                </button>
                                {/* 编辑批注按钮 */}
                                <button
                                    onClick={() => {
                                        setAnnotationEditMode((prev) => {
                                            const next = !prev;
                                            if (next) {
                                                setShowAnnotations(true);
                                            }
                                            return next;
                                        });
                                    }}
                                    className={clsx(
                                        "text-[11px] font-medium flex items-center gap-1",
                                        annotationEditMode ? 'text-amber-600' : 'text-slate-500 hover:text-slate-600'
                                    )}
                                >
                                    <Pencil className="w-3 h-3" />
                                    {annotationEditMode ? '退出编辑' : '编辑批注'}
                                </button>
                                {/* 批注开关 */}
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <span className="text-xs text-slate-500">显示批注</span>
                                    <div className="relative">
                                        <input
                                            type="checkbox"
                                            checked={showAnnotations}
                                            onChange={(e) => {
                                                setShowAnnotations(e.target.checked);
                                                if (!e.target.checked) {
                                                    setPageAnnotationsData(new Map());
                                                    setAnnotationEditMode(false);
                                                }
                                            }}
                                            className="sr-only peer"
                                        />
                                        <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-500"></div>
                                    </div>
                                    <Pencil className="w-3.5 h-3.5 text-slate-400" />
                                </label>
                            </div>
                            {(annotationFetchLoading || annotationStatus.message || exportStatus.message) && (
                                <div className="flex items-center gap-3 text-[11px]">
                                    {annotationFetchLoading && (
                                        <span className="flex items-center gap-1 text-slate-500">
                                            <Loader2 className="w-3 h-3 animate-spin" />
                                            正在加载批注...
                                        </span>
                                    )}
                                    {annotationStatus.message && (
                                        <span
                                            className={clsx(
                                                "flex items-center gap-1",
                                                annotationStatus.type === 'error'
                                                    ? 'text-rose-600'
                                                    : annotationStatus.type === 'success'
                                                        ? 'text-emerald-600'
                                                        : 'text-slate-500'
                                            )}
                                        >
                                            {annotationStatus.type === 'loading' && <Loader2 className="w-3 h-3 animate-spin" />}
                                            {annotationStatus.message}
                                        </span>
                                    )}
                                    {exportStatus.message && (
                                        <span
                                            className={clsx(
                                                "flex items-center gap-1",
                                                exportStatus.type === 'error'
                                                    ? 'text-rose-600'
                                                    : exportStatus.type === 'success'
                                                        ? 'text-emerald-600'
                                                        : 'text-slate-500'
                                            )}
                                        >
                                            {exportStatus.type === 'loading' && <Loader2 className="w-3 h-3 animate-spin" />}
                                            {exportStatus.message}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                        {uniquePages.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>No pages found for this student.</span>
                            </div>
                        )}
                        {uniquePages.map((pageIdx, pageIdxIndex) => {
                            const originalImageUrl = uploadedImages[pageIdx] || currentSession?.images[pageIdx]?.url;
                            const pageAnnotations = pageAnnotationsData.get(pageIdx) || [];
                            const hasCanvasAnnotations = showAnnotations && pageAnnotations.length > 0;
                            const canEditAnnotations = showAnnotations && annotationEditMode && !!originalImageUrl;
                            const isLastPage = pageIdxIndex === uniquePages.length - 1;
                            return (
                                <div key={pageIdx} className={clsx("pb-6 border-b border-slate-100/80 space-y-2", isLastPage && "border-b-0 pb-0")}>
                                    <div className="flex items-center justify-between">
                                        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
                                            Page {pageIdx + 1}
                                        </div>
                                        {showAnnotations && hasCanvasAnnotations && (
                                            <div className="flex items-center gap-1 text-xs text-emerald-500">
                                                <Pencil className="w-3 h-3" />
                                                {annotationEditMode ? '可编辑批注' : '已标注 (Canvas)'}
                                            </div>
                                        )}
                                    </div>
                                    {/* Canvas 渲染批注 / 编辑器 */}
                                    {canEditAnnotations ? (
                                        <AnnotationEditor
                                            imageSrc={originalImageUrl}
                                            annotations={pageAnnotations.map((ann, idx) => ({
                                                id: ann.id || `temp-${pageIdx}-${idx}`,
                                                annotation_type: ann.annotation_type,
                                                bounding_box: ann.bounding_box,
                                                text: ann.text || '',
                                                color: ann.color || '#0066FF',
                                                question_id: ann.question_id || '',
                                                scoring_point_id: ann.scoring_point_id || '',
                                            }))}
                                            onAnnotationsChange={(next) => {
                                                updatePageAnnotations(pageIdx, () => next.map((ann) => ({
                                                    id: ann.id,
                                                    annotation_type: ann.annotation_type as any,
                                                    bounding_box: ann.bounding_box,
                                                    text: ann.text,
                                                    color: ann.color,
                                                    question_id: ann.question_id,
                                                    scoring_point_id: ann.scoring_point_id,
                                                    page_index: pageIdx,
                                                })));
                                            }}
                                            onAnnotationDelete={(annotationId) => {
                                                if (annotationId.startsWith('temp-')) {
                                                    updatePageAnnotations(pageIdx, (current) => current.filter((ann) => ann.id !== annotationId));
                                                    return;
                                                }
                                                handleAnnotationDelete(pageIdx, annotationId);
                                            }}
                                            onAnnotationAdd={(annotation) => {
                                                handleAnnotationAdd(pageIdx, annotation as any);
                                            }}
                                            onAnnotationUpdate={(annotationId, updates) => {
                                                if (annotationId.startsWith('temp-')) {
                                                    const safeUpdates: Partial<PageAnnotation> = {
                                                        ...updates,
                                                        annotation_type: updates.annotation_type as PageAnnotation['annotation_type'],
                                                    };
                                                    updatePageAnnotations(pageIdx, (current) => current.map((ann) => (
                                                        ann.id === annotationId ? { ...ann, ...safeUpdates } : ann
                                                    )));
                                                    return;
                                                }
                                                handleAnnotationUpdate(pageIdx, annotationId, updates as any);
                                            }}
                                            className="w-full"
                                        />
                                    ) : hasCanvasAnnotations && originalImageUrl ? (
                                        <AnnotationCanvas
                                            imageSrc={originalImageUrl}
                                            annotations={pageAnnotations}
                                            className="w-full h-auto"
                                            showText={true}
                                            onAnnotationClick={(annotation) => {
                                                console.log('[批注点击]', annotation);
                                                // 如果批注关联了题目和得分点，滚动到对应位置
                                                if (annotation.question_id) {
                                                    const questionElement = document.getElementById(`question-${annotation.question_id}`);
                                                    questionElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                                }
                                            }}
                                        />
                                    ) : originalImageUrl ? (
                                        // 检查是否是 base64 数据 URL，如果是则直接使用，否则作为普通 URL
                                        originalImageUrl.startsWith('data:') || originalImageUrl.startsWith('/9j/') ? (
                                            <img 
                                                src={originalImageUrl.startsWith('data:') ? originalImageUrl : `data:image/jpeg;base64,${originalImageUrl}`} 
                                                alt={`Page ${pageIdx + 1}`} 
                                                className="w-full h-auto" 
                                            />
                                        ) : (
                                            <img src={originalImageUrl} alt={`Page ${pageIdx + 1}`} className="w-full h-auto" />
                                        )
                                    ) : (
                                        <div className="p-10 text-center text-slate-400">Image missing</div>
                                    )}
                                </div>
                            )
                        })}
                    </div>

                    {/* Details Panel */}
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-white p-8 custom-scrollbar">
                        <div className="max-w-2xl mx-auto space-y-8">
                            {/* Score Header */}
                            <div className="text-center pb-6 border-b border-slate-100">
                                <div className="text-4xl font-semibold text-slate-800 tracking-tight mb-1">
                                    {isAssist ? '--' : detailViewStudent.score}
                                    {!isAssist && <span className="text-lg text-slate-400 font-medium ml-1">/ {detailViewStudent.maxScore}</span>}
                                </div>
                                <div className="text-xs font-medium text-slate-500 tracking-wide">{isAssist ? 'Assisted Grading' : 'Total Score'}</div>
                            </div>

                            {/* Questions */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <Layers className="w-4 h-4 text-slate-500" />
                                    <h3 className="text-sm font-semibold text-slate-700">Analysis Detail</h3>
                                </div>
                                {detailViewStudent.questionResults?.map((q, idx) => (
                                    <div key={`question-${q.questionId || 'unknown'}-${detailViewStudent.studentName}-${idx}`} className="border-b border-slate-100 pb-4 last:border-b-0">
                                        <QuestionDetail question={q} gradingMode={detailViewStudent.gradingMode} defaultExpanded={defaultExpandDetails} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // === Dashboard View ===
    if (results.length === 0) {
        // 调试日志
        console.log('[ResultsView Empty State]', {
            submissionId,
            status,
            apiFallbackLoading,
            apiFallbackError
        });

        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
                <div className="p-8 flex flex-col items-center gap-4">
                    {apiFallbackLoading ? (
                        <>
                            <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
                            <p className="font-medium text-slate-600">正在获取批改结果...</p>
                        </>
                    ) : (
                        <>
                            <RocketOutlined className="text-4xl opacity-50" />
                            <p className="font-medium">暂无批改结果</p>
                            {apiFallbackError && (
                                <p className="text-sm text-red-500">{apiFallbackError}</p>
                            )}
                            {/* 始终显示重新获取按钮（当有 submissionId 或 status 为 COMPLETED 时） */}
                            {(submissionId || status === 'COMPLETED') && (
                                <SmoothButton onClick={handleRetryFetch} variant="primary" size="sm">
                                    <Loader2 className="w-4 h-4 mr-2" /> 重新获取结果
                                </SmoothButton>
                            )}
                            <SmoothButton onClick={() => setCurrentTab('process')} variant="ghost">
                                <ArrowLeft className="w-4 h-4 mr-2" /> 返回批改过程
                            </SmoothButton>
                        </>
                    )}
                </div>
            </div>
        );
    }

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1
            }
        }
    };
    const itemVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: { opacity: 1, y: 0 }
    };

    return (
        <div className="h-full overflow-y-auto p-6 space-y-8 custom-scrollbar bg-white">
            {/* Class Report Modal */}
            <AnimatePresence>
                {showClassReport && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4"
                        onClick={() => setShowClassReport(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            className="w-full max-w-2xl"
                            onClick={e => e.stopPropagation()}
                        >
                            <div className="bg-white p-6 space-y-4">
                                <div className="flex items-center justify-between pb-4 border-b border-slate-100/60">
                                    <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                                        <BarChartOutlined className="text-blue-500" /> 班级结果分析
                                    </h3>
                                    <button onClick={() => setShowClassReport(false)} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-600 transition-colors">
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>
                                {classReport ? (
                                    <div className="space-y-6">
                                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                            <div className="bg-slate-50/60 p-3 text-center">
                                                <div className="text-xl font-black text-slate-700">{classReport.averageScore?.toFixed(1)}</div>
                                                <div className="text-[10px] font-medium text-slate-400 mt-1">Avg Score</div>
                                            </div>
                                            <div className="bg-slate-50/60 p-3 text-center">
                                                <div className="text-xl font-black text-slate-700">{classReport.averagePercentage?.toFixed(1)}%</div>
                                                <div className="text-[10px] font-medium text-slate-400 mt-1">Avg Rate</div>
                                            </div>
                                            <div className="bg-emerald-50/60 p-3 text-center">
                                                <div className="text-xl font-black text-emerald-600">{((classReport.passRate ?? 0) * 100).toFixed(1)}%</div>
                                                <div className="text-[10px] font-medium text-emerald-500 mt-1">Pass Rate</div>
                                            </div>
                                            <div className="bg-blue-50/60 p-3 text-center">
                                                <div className="text-xl font-black text-blue-600">{classReport.totalStudents}</div>
                                                <div className="text-[10px] font-medium text-blue-500 mt-1">Students</div>
                                            </div>
                                        </div>
                                        <p className="text-sm text-slate-600 leading-relaxed bg-white p-4">
                                            {classReport.summary}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="text-center py-10 text-slate-400">暂无分析数据</div>
                                )}
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Dashboard Header */}
            <div className="bg-white">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 px-6 py-5 border-b border-slate-200/70">
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 grid place-items-center rounded-lg bg-slate-900 text-white">
                            <RocketOutlined className="text-lg" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900 tracking-tight">批改总览</h2>
                            <p className="text-[11px] font-medium text-slate-500">Grading Overview</p>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                        <SmoothButton onClick={handleToggleReviewMode} variant="secondary" size="sm" disabled={!submissionId}>
                            <CheckCircle className="w-4 h-4 mr-2" /> 批改复核
                        </SmoothButton>
                        <SmoothButton onClick={() => setRubricOpen(true)} variant="secondary" size="sm" disabled={!submissionId}>
                            <BookOpen className="w-4 h-4 mr-2" /> 标准复核
                        </SmoothButton>
                        <SmoothButton onClick={() => setShowClassReport(true)} variant="secondary" size="sm">
                            <BarChartOutlined className="mr-2" /> 班级报告
                        </SmoothButton>

                        {/* 导出下拉菜单 */}
                        <div className="relative">
                            <SmoothButton
                                onClick={() => setExportMenuOpen(!exportMenuOpen)}
                                variant="secondary"
                                size="sm"
                                disabled={!submissionId}
                            >
                                <Download className="w-4 h-4 mr-2" />
                                导出
                                <ChevronDown className={clsx("w-4 h-4 ml-1 transition-transform", exportMenuOpen && "rotate-180")} />
                            </SmoothButton>

                            {exportMenuOpen && (
                                <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-50">
                                    <button
                                        onClick={handleExportExcel}
                                        disabled={exportLoading === 'excel'}
                                        className="w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-3 disabled:opacity-50"
                                    >
                                        {exportLoading === 'excel' ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <FileText className="w-4 h-4 text-slate-400" />
                                        )}
                                        <div>
                                            <div className="font-medium">Excel 统计</div>
                                            <div className="text-[10px] text-slate-400">成绩、题目、班级报告</div>
                                        </div>
                                    </button>
                                    <div className="border-t border-slate-100 my-1" />
                                    <button
                                        onClick={() => { setSmartExcelOpen(true); setExportMenuOpen(false); }}
                                        className="w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-3"
                                    >
                                        <AlertCircle className="w-4 h-4 text-blue-500" />
                                        <div>
                                            <div className="font-medium">智能 Excel</div>
                                            <div className="text-[10px] text-slate-400">AI 自定义格式 / 导入模板</div>
                                        </div>
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 divide-x divide-slate-200/70">
                    {metrics.map((metric) => (
                        <div key={metric.label} className="px-4 py-4">
                            <div className="flex items-center justify-between text-[11px] font-medium text-slate-500">
                                {metric.label}
                                <metric.icon className="text-base text-slate-400" />
                            </div>
                            <div className="mt-2 text-2xl font-black text-slate-900">
                                {metric.value}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                    <BookOpen className="h-4 w-4 text-slate-400" />
                    评分依据透明度
                </div>
                <div className="mt-3 grid gap-4 md:grid-cols-3 text-xs text-slate-600">
                    <div className="space-y-1">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">来源</div>
                        <div>
                            {parsedRubric
                                ? `解析评分标准 · ${rubricTotalQuestions ?? '--'} 题 / ${rubricTotalScore ?? '--'} 分`
                                : '未解析评分标准'}
                        </div>
                    </div>
                    <div className="space-y-1">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">去重策略</div>
                        <div>按题号归一 + 跨页题合并 + 分值纠偏</div>
                    </div>
                    <div className="space-y-1">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">评分依据摘要</div>
                        <div>
                            {rubricCoverage === null
                                ? '暂无评分点'
                                : `评分点引用覆盖 ${(rubricCoverage * 100).toFixed(0)}%`}
                        </div>
                    </div>
                </div>
            </div>

            {/* Results List */}
            <div className="space-y-4">
                <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-2">
                        <ListOrdered className="w-4 h-4 text-slate-400" />
                        <h3 className="text-sm font-semibold text-slate-700">学生列表</h3>
                        <span className="text-[11px] text-slate-500">{totalStudents} students</span>
                    </div>
                    {totalCrossPageQuestions > 0 && (
                        <span className="text-[11px] text-purple-600">{totalCrossPageQuestions} cross-page</span>
                    )}
                </div>

                <motion.div className='bg-transparent space-y-3' variants={containerVariants} initial='hidden' animate='visible'>
                    {sortedResults.map((result, index) => (
                        <motion.div key={`${result.studentName}-${index}`} variants={itemVariants} onClick={() => handleViewDetail(result)} className='cursor-pointer'>
                            <ResultCard result={result} rank={index + 1} isExpanded={false} onExpand={() => { }} />
                        </motion.div>
                    ))}
                </motion.div>
            </div>

            {/* Cross Page Alerts */}
            {crossPageQuestions.length > 0 && (
                <div className="bg-white border-t border-slate-100 pt-4">
                    <div className="flex items-center gap-2 text-slate-700 font-semibold mb-3">
                        <Layers className="w-4 h-4" />
                        跨页题提醒
                    </div>
                    <div className="space-y-2">
                        {crossPageQuestions.map((cpq, idx) => (
                            <div key={idx} className="flex items-center justify-between border-b border-slate-100 pb-2 text-sm text-slate-600">
                                <span>Question {cpq.questionId}</span>
                                <div className="flex items-center gap-3">
                                    <span className="text-xs text-slate-500">Pages {cpq.pageIndices.map(p => p + 1).join(', ')}</span>
                                    {cpq.confidence < 0.8 && (
                                        <span className="text-[10px] text-amber-600">Check</span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 智能 Excel 对话框 */}
            <AnimatePresence>
                {smartExcelOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
                        onClick={() => setSmartExcelOpen(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900">智能 Excel 生成</h3>
                                    <p className="text-xs text-slate-500 mt-0.5">用自然语言描述你想要的报表格式</p>
                                </div>
                                <button onClick={() => setSmartExcelOpen(false)} className="p-1 hover:bg-slate-100 rounded">
                                    <X className="w-5 h-5 text-slate-400" />
                                </button>
                            </div>

                            <div className="p-6 space-y-4">
                                {/* 模板上传 */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-2">
                                        导入已有 Excel 模板（可选）
                                    </label>
                                    <div className="border-2 border-dashed border-slate-200 rounded-lg p-4 text-center hover:border-blue-300 transition-colors">
                                        <input
                                            type="file"
                                            accept=".xlsx,.xls"
                                            onChange={(e) => setSmartExcelTemplate(e.target.files?.[0] || null)}
                                            className="hidden"
                                            id="excel-template-input"
                                        />
                                        <label htmlFor="excel-template-input" className="cursor-pointer">
                                            {smartExcelTemplate ? (
                                                <div className="flex items-center justify-center gap-2 text-sm text-slate-700">
                                                    <FileText className="w-5 h-5 text-green-500" />
                                                    {smartExcelTemplate.name}
                                                    <button
                                                        onClick={(e) => { e.preventDefault(); setSmartExcelTemplate(null); }}
                                                        className="text-slate-400 hover:text-red-500"
                                                    >
                                                        <X className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            ) : (
                                                <div className="text-sm text-slate-500">
                                                    <FileText className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                                                    点击上传 Excel 模板
                                                </div>
                                            )}
                                        </label>
                                    </div>
                                </div>

                                {/* 格式描述 */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-2">
                                        描述你想要的格式
                                    </label>
                                    <textarea
                                        value={smartExcelPrompt}
                                        onChange={(e) => setSmartExcelPrompt(e.target.value)}
                                        placeholder="例如：&#10;- 我需要一个包含学生姓名、总分、各题得分的表格&#10;- 按分数从高到低排序&#10;- 添加一列显示是否及格（60分以上）&#10;- 在模板的「成绩」列填入总分"
                                        className="w-full h-32 px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    />
                                </div>

                                {/* 示例提示 */}
                                <div className="bg-blue-50 rounded-lg p-3">
                                    <div className="text-xs font-medium text-blue-700 mb-1">💡 提示</div>
                                    <div className="text-xs text-blue-600 space-y-1">
                                        <p>• 如果上传了模板，AI 会尝试将数据填入对应列</p>
                                        <p>• 可以指定列名映射，如「把总分填入『成绩』列」</p>
                                        <p>• 支持添加计算列，如「添加排名列」「添加及格标记」</p>
                                    </div>
                                </div>
                            </div>

                            <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3">
                                <SmoothButton variant="secondary" size="sm" onClick={() => setSmartExcelOpen(false)}>
                                    取消
                                </SmoothButton>
                                <SmoothButton
                                    variant="primary"
                                    size="sm"
                                    onClick={handleSmartExcelSubmit}
                                    disabled={!smartExcelPrompt.trim() || smartExcelLoading}
                                >
                                    {smartExcelLoading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                            生成中...
                                        </>
                                    ) : (
                                        <>
                                            <Download className="w-4 h-4 mr-2" />
                                            生成并下载
                                        </>
                                    )}
                                </SmoothButton>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            <RubricOverview />
        </div>
    );
};

export default ResultsView;
