'use client';

import React, { useState, useContext, useMemo, useEffect, useCallback } from 'react';
import { useConsoleStore, StudentResult, QuestionResult } from '@/store/consoleStore';
import clsx from 'clsx';
import { ArrowLeft, ChevronDown, ChevronUp, CheckCircle, XCircle, Download, GitMerge, AlertCircle, Layers, FileText, Info, X, AlertTriangle, BookOpen, ListOrdered, Pencil, Loader2 } from 'lucide-react';
import { CrownOutlined, BarChartOutlined, UsergroupAddOutlined, CheckCircleOutlined, ExclamationCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { Popover } from 'antd';
import { motion, AnimatePresence } from 'framer-motion';
import { RubricOverview } from './RubricOverview';
import { AppContext, AppContextType } from '../bookscan/AppContext';
import { MathText } from '@/components/common/MathText';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { gradingApi } from '@/services/api';
import { renderAnnotationsToBase64 } from '@/services/annotationApi';
import type { VisualAnnotation } from '@/types/annotation';

interface ResultCardProps {
    result: StudentResult;
    rank: number;
    onExpand: () => void;
    isExpanded: boolean;
}

const normalizeEvidenceText = (text?: string) => {
    if (!text) return '';
    return text.replace(/^【原文引用】\s*/, '').trim();
};

const LOW_CONFIDENCE_THRESHOLD = 0.7;

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

const normalizeRubricDraft = (raw: any): ParsedRubricDraft => {
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

const splitParagraphs = (text: string) => {
    const normalized = text.replace(/\r\n/g, '\n').trim();
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

const QuestionDetail: React.FC<{ question: QuestionResult; gradingMode?: string }> = ({ question, gradingMode }) => {
    const percentage = question.maxScore > 0 ? (question.score / question.maxScore) * 100 : 0;
    const questionLabel = question.questionId === 'unknown' ? '未识别' : question.questionId;
    const normalizedType = (question.questionType || '').toLowerCase();
    const isChoice = ['choice', 'single_choice', 'multiple_choice', 'mcq'].includes(normalizedType);
    const isAssist = (gradingMode || '').startsWith('assist')
        || (question.maxScore <= 0 && !(question.scoringPointResults?.length || question.scoringPoints?.length));
    const reviewReasons = question.reviewReasons || [];
    const isLowConfidence = !isAssist && (
        reviewReasons.includes('low_confidence')
        || (question.confidence !== undefined && question.confidence < LOW_CONFIDENCE_THRESHOLD)
    );
    const confessionText = question.selfCritique
        || question.honestyNote
        || question.confidenceReason
        || '证据不足，建议复核。';
    const showScoringDetails = !isAssist && !isChoice;
    const hasDetails = Boolean(question.studentAnswer)
        || (showScoringDetails && ((question.scoringPointResults?.length || 0) > 0 || (question.scoringPoints?.length || 0) > 0));
    const [detailsOpen, setDetailsOpen] = useState(false);
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
                {isLowConfidence && question.confidence !== undefined && (
                    <div className={clsx("flex items-center gap-1.5", question.confidence < 0.8 ? "text-amber-600" : "text-emerald-600")}>
                        {question.confidence < 0.8 ? <AlertCircle className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
                        Confidence: <span className="font-mono font-semibold">{(question.confidence * 100).toFixed(0)}%</span>
                    </div>
                )}
            </div>

            {detailsOpen && (
                <>
                    {question.studentAnswer && (
                        <div className="rounded-md p-3 border border-slate-200 bg-white">
                            <span className="text-[11px] font-semibold text-slate-500 mb-1 block">Student Answer</span>
                            <div className="space-y-2">
                                {renderParagraphs(question.studentAnswer)}
                            </div>
                        </div>
                    )}

                    {showScoringDetails ? (
                        question.scoringPointResults && question.scoringPointResults.length > 0 ? (
                            <div className="mt-3 space-y-2">
                                <div className="text-xs font-semibold text-slate-500">评分步骤</div>
                                {question.scoringPointResults.map((spr, idx) => (
                                    <div key={idx} className="rounded-md border border-slate-200 p-3">
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="space-y-1">
                                                <div className="text-xs text-slate-700 font-medium leading-relaxed">
                                                    {spr.pointId && <span className="font-mono text-slate-400 mr-2 text-[10px]">[{spr.pointId}]</span>}
                                                    <MathText className="inline" text={spr.scoringPoint?.description || spr.description || "N/A"} />
                                                    <Popover
                                                        title={<span className="font-semibold">评分标准详情</span>}
                                                        content={
                                                            <div className="max-w-xs text-xs space-y-2 p-1">
                                                                <div className="font-medium text-slate-700">{spr.scoringPoint?.description || spr.description}</div>
                                                                <div className="flex justify-between text-slate-500">
                                                                    <span>Max: {spr.maxPoints ?? spr.scoringPoint?.score ?? 0}</span>
                                                                    <span>{spr.scoringPoint?.isRequired ? 'Required' : 'Optional'}</span>
                                                                </div>
                                                            </div>
                                                        }
                                                    >
                                                        <Info className="w-3 h-3 inline ml-1.5 text-slate-300 hover:text-blue-400 cursor-help" />
                                                    </Popover>
                                                </div>
                                                <div className="text-[11px] text-slate-500">
                                                    判定: {spr.decision || (spr.awarded > 0 ? '得分' : '不得分')}
                                                    {spr.reason && <span className="ml-1 opacity-75">- {spr.reason}</span>}
                                                </div>
                                            </div>
                                            <div className={clsx("font-mono font-semibold text-sm whitespace-nowrap", spr.awarded > 0 ? "text-emerald-600" : "text-slate-400")}>
                                                {spr.awarded}/{spr.maxPoints ?? spr.scoringPoint?.score ?? 0}
                                            </div>
                                        </div>
                                    </div>
                                ))}
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
                                Scores available but step breakdown missing.
                            </div>
                        )
                    ) : (
                        <div className="mt-2 text-xs text-slate-500 italic">
                            {isAssist ? 'No scoring breakdown in Assist mode.' : 'No detailed analysis for this question type.'}
                        </div>
                    )}

                </>
            )}
            {isLowConfidence && (
                <div className="mt-3 p-3 rounded-md border border-amber-200 bg-amber-50">
                    <div className="text-[11px] font-semibold text-amber-700 mb-1">自白提示</div>
                    <p className="text-xs text-amber-800 leading-relaxed">
                        <MathText text={confessionText} />
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

const ResultCard: React.FC<ResultCardProps> = ({ result, rank, onExpand, isExpanded }) => {
    const isAssist = (result.gradingMode || '').startsWith('assist') || result.maxScore <= 0;
    const percentage = !isAssist && result.maxScore > 0 ? (result.score / result.maxScore) * 100 : 0;

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
        <div
            className={clsx(
                'grid grid-cols-[56px_1fr_auto] items-center gap-4 px-4 py-3 border-b border-slate-100 hover:bg-slate-50/60 transition',
                result.needsConfirmation && 'bg-amber-50/50'
            )}
            onClick={() => onExpand?.()}
        >
            <div className="h-10 w-10 rounded-md border border-slate-200 bg-slate-50 text-slate-700 font-mono font-bold text-sm flex items-center justify-center">
                {rank}
            </div>

            <div className="min-w-0">
                <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-slate-900 truncate">{result.studentName}</h3>
                    <span className="text-[11px] font-medium text-slate-500">{gradeLabel}</span>
                </div>
                <div className="mt-1 text-[11px] text-slate-500 flex flex-wrap gap-3">
                    {pageRange && <span>Pages {pageRange}</span>}
                    {result.totalRevisions !== undefined && result.totalRevisions > 0 && (
                        <span>Revisions {result.totalRevisions}</span>
                    )}
                    {crossPageCount > 0 && <span>Cross-page {crossPageCount}</span>}
                    {result.needsConfirmation && <span className="text-amber-600">Needs confirmation</span>}
                </div>
            </div>

            <div className="text-right">
                {isAssist ? (
                    <div className="text-xs font-semibold text-slate-500">Assist</div>
                ) : (
                    <div className="text-lg font-bold text-slate-900">
                        {result.score.toFixed(1)}<span className="text-xs text-slate-400">/{result.maxScore}</span>
                    </div>
                )}
                {!isAssist && (
                    <div className="text-[11px] text-slate-500">{percentage.toFixed(0)}%</div>
                )}
            </div>
        </div>
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

export const ResultsView: React.FC = () => {
    const {
        finalResults,
        workflowNodes,
        crossPageQuestions,
        uploadedImages,
        setCurrentTab,
        classReport,
        submissionId,
        pendingReview,
        reviewFocus,
        setReviewFocus
    } = useConsoleStore();
    const bookScanContext = useContext(AppContext) as AppContextType | null;
    const sessions = bookScanContext?.sessions || [];
    const currentSessionId = bookScanContext?.currentSessionId || null;
    const currentSession = sessions.find((s: any) => s.id === currentSessionId);

    const [detailViewIndex, setDetailViewIndex] = useState<number | null>(null);
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

    // 批注渲染状态
    const [showAnnotations, setShowAnnotations] = useState(false);
    const [annotatedImages, setAnnotatedImages] = useState<Map<number, string>>(new Map());
    const [annotationLoading, setAnnotationLoading] = useState<Set<number>>(new Set());
    // 使用 ref 跟踪已处理的页面，避免 useEffect 无限循环
    const renderedPagesRef = React.useRef<Set<string>>(new Set());

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
                scoringPointResults: (q as any).scoringPointResults
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

    const totalStudents = sortedResults.length;
    const scoredResults = sortedResults.filter(r => !(r.gradingMode || '').startsWith('assist') && r.maxScore > 0);
    const scoredCount = scoredResults.length;
    const avgScore = scoredCount > 0 ? scoredResults.reduce((sum, r) => sum + r.score, 0) / scoredCount : 0;
    const highestScore = scoredCount > 0 ? Math.max(...scoredResults.map((r) => r.score)) : 0;
    const passCount = scoredResults.filter(r => (r.score / r.maxScore) >= 0.6).length;
    const needsConfirmCount = sortedResults.filter(r => r.needsConfirmation).length;
    const totalCrossPageQuestions = crossPageQuestions.length;
    const hasScores = scoredCount > 0;
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

    // 批注渲染函数 - 调用后端 API 生成带批注的图片
    const renderAnnotationsForPage = useCallback(async (pageIdx: number, imageUrl: string, studentKey: string) => {
        // 使用 studentKey + pageIdx 作为唯一标识，避免重复渲染
        const renderKey = `${studentKey}-${pageIdx}`;
        
        // 如果已经处理过，跳过
        if (renderedPagesRef.current.has(renderKey)) return;
        
        // 标记为已处理（立即标记，防止并发调用）
        renderedPagesRef.current.add(renderKey);
        
        // 标记为加载中
        setAnnotationLoading(prev => new Set(prev).add(pageIdx));
        
        try {
            // 从当前学生的批改结果中提取该页的批注
            const student = detailViewStudent;
            if (!student) return;
            
            // 收集该页的所有批注
            const pageAnnotations: VisualAnnotation[] = [];
            
            // 从 questionResults 中提取批注
            student.questionResults?.forEach(q => {
                // 检查该题目是否在当前页
                const questionPages = q.pageIndices || [];
                if (!questionPages.includes(pageIdx) && questionPages.length > 0) return;
                
                // 从 scoringPointResults 中提取批注信息
                q.scoringPointResults?.forEach((spr: any, idx: number) => {
                    // 如果有坐标信息，创建批注
                    if (spr.bounding_box || spr.boundingBox) {
                        const bbox = spr.bounding_box || spr.boundingBox;
                        const pointId = spr.point_id || spr.pointId || `${q.questionId}.${idx + 1}`;
                        const awarded = spr.awarded ?? spr.score ?? 0;
                        const maxPoints = spr.max_points || spr.maxPoints || 1;
                        
                        // 根据得分点类型和得分情况确定批注类型
                        let annotationType: string;
                        if (awarded >= maxPoints) {
                            // 满分 - 使用勾选或 A/M mark
                            if (pointId.startsWith('M')) {
                                annotationType = 'm_mark';
                            } else if (pointId.startsWith('A')) {
                                annotationType = 'a_mark';
                            } else {
                                annotationType = 'step_check';
                            }
                        } else if (awarded > 0) {
                            // 部分得分
                            annotationType = 'partial_check';
                        } else {
                            // 零分
                            annotationType = 'step_cross';
                        }
                        
                        pageAnnotations.push({
                            annotation_type: annotationType,
                            bounding_box: bbox,
                            text: pointId,
                            color: awarded > 0 ? '#00AA00' : '#FF0000',
                        } as VisualAnnotation);
                    }
                });
                
                // 添加分数批注（如果有坐标）
                if ((q as any).scoreBoundingBox) {
                    pageAnnotations.push({
                        annotation_type: 'score',
                        bounding_box: (q as any).scoreBoundingBox,
                        text: `${q.score}/${q.maxScore}`,
                        color: '#FF6600',
                    } as VisualAnnotation);
                }
            });
            
            // 获取图片的 base64
            let imageBase64 = imageUrl;
            if (imageUrl.startsWith('data:')) {
                imageBase64 = imageUrl.split(',')[1] || imageUrl;
            } else if (imageUrl.startsWith('http')) {
                // 如果是 URL，需要先获取图片
                const response = await fetch(imageUrl);
                const blob = await response.blob();
                const reader = new FileReader();
                imageBase64 = await new Promise((resolve) => {
                    reader.onload = () => {
                        const result = reader.result as string;
                        resolve(result.split(',')[1] || result);
                    };
                    reader.readAsDataURL(blob);
                });
            }
            
            // 如果有批注坐标，直接渲染
            if (pageAnnotations.length > 0) {
                const result = await renderAnnotationsToBase64(imageBase64, pageAnnotations);
                if (result.success && result.image_base64) {
                    setAnnotatedImages(prev => {
                        const next = new Map(prev);
                        next.set(pageIdx, `data:image/png;base64,${result.image_base64}`);
                        return next;
                    });
                    return;
                }
            }
            
            // 如果没有批注坐标但有评分标准，调用 annotate-and-render API
            if (parsedRubric?.questions && parsedRubric.questions.length > 0) {
                const { annotateAndRender } = await import('@/services/annotationApi');
                
                // 构建评分标准
                const rubrics = parsedRubric.questions.map(q => ({
                    question_id: q.questionId,
                    max_score: q.maxScore,
                    question_text: q.questionText || '',
                    standard_answer: q.standardAnswer || '',
                    scoring_points: (q.scoringPoints || []).map(sp => ({
                        description: sp.description,
                        score: sp.score || 1,
                        point_id: sp.pointId || '',
                        is_required: sp.isRequired ?? true,
                    })),
                    grading_notes: q.gradingNotes || '',
                }));
                
                try {
                    const blob = await annotateAndRender(imageBase64, rubrics, pageIdx);
                    const reader = new FileReader();
                    const dataUrl = await new Promise<string>((resolve) => {
                        reader.onload = () => resolve(reader.result as string);
                        reader.readAsDataURL(blob);
                    });
                    
                    setAnnotatedImages(prev => {
                        const next = new Map(prev);
                        next.set(pageIdx, dataUrl);
                        return next;
                    });
                    return;
                } catch (err) {
                    console.error('调用 annotate-and-render API 失败:', err);
                }
            }
            
            // 如果是 Assist 模式且没有批注数据，生成演示批注
            const isAssistMode = (student.gradingMode || '').startsWith('assist') || student.maxScore <= 0;
            if (isAssistMode && pageAnnotations.length === 0) {
                console.log('Assist 模式：生成演示批注');
                // 生成一些演示批注来展示功能
                const demoAnnotations: VisualAnnotation[] = [
                    {
                        annotation_type: 'step_check',
                        bounding_box: { x: 0.15, y: 0.25, width: 0.03, height: 0.03 },
                        text: 'M1',
                        color: '#00AA00',
                    } as VisualAnnotation,
                    {
                        annotation_type: 'step_check',
                        bounding_box: { x: 0.15, y: 0.35, width: 0.03, height: 0.03 },
                        text: 'M2',
                        color: '#00AA00',
                    } as VisualAnnotation,
                    {
                        annotation_type: 'step_cross',
                        bounding_box: { x: 0.15, y: 0.45, width: 0.03, height: 0.03 },
                        text: 'A1',
                        color: '#FF0000',
                    } as VisualAnnotation,
                    {
                        annotation_type: 'score',
                        bounding_box: { x: 0.85, y: 0.15, width: 0.1, height: 0.05 },
                        text: '3/4',
                        color: '#FF6600',
                    } as VisualAnnotation,
                    {
                        annotation_type: 'comment',
                        bounding_box: { x: 0.7, y: 0.55, width: 0.25, height: 0.08 },
                        text: '演示批注',
                        color: '#0066CC',
                    } as VisualAnnotation,
                ];
                
                try {
                    const result = await renderAnnotationsToBase64(imageBase64, demoAnnotations);
                    if (result.success && result.image_base64) {
                        setAnnotatedImages(prev => {
                            const next = new Map(prev);
                            next.set(pageIdx, `data:image/png;base64,${result.image_base64}`);
                            return next;
                        });
                    }
                } catch (err) {
                    console.error('渲染演示批注失败:', err);
                }
            }
        } catch (error) {
            console.error('渲染批注失败:', error);
        } finally {
            setAnnotationLoading(prev => {
                const next = new Set(prev);
                next.delete(pageIdx);
                return next;
            });
        }
    }, [detailViewStudent, parsedRubric]);

    // 当开启批注显示时，渲染当前学生的所有页面
    useEffect(() => {
        if (!showAnnotations || !detailViewStudent) return;
        
        // 获取学生唯一标识
        const studentKey = detailViewStudent.studentName || `student-${detailViewIndex}`;
        
        const pages = new Set<number>();
        if (detailViewStudent.startPage !== undefined) {
            const start = detailViewStudent.startPage;
            const end = detailViewStudent.endPage ?? start;
            for (let i = start; i <= end; i++) pages.add(i);
        }
        detailViewStudent.questionResults?.forEach(q => {
            (q.pageIndices || []).forEach(p => pages.add(p));
        });
        
        // 如果没有找到任何页面信息，默认使用第一页（索引 0）
        if (pages.size === 0) {
            pages.add(0);
        }
        
        const uniquePages = Array.from(pages).filter(p => Number.isFinite(p));
        
        uniquePages.forEach(pageIdx => {
            const imageUrl = uploadedImages[pageIdx] || currentSession?.images[pageIdx]?.url;
            if (imageUrl) {
                renderAnnotationsForPage(pageIdx, imageUrl, studentKey);
            }
        });
    }, [showAnnotations, detailViewStudent, detailViewIndex, uploadedImages, currentSession, renderAnnotationsForPage]);

    // 当切换学生或关闭批注时，清理已渲染的图片缓存
    useEffect(() => {
        if (!showAnnotations) {
            // 关闭批注时清理
            setAnnotatedImages(new Map());
            renderedPagesRef.current.clear();
        }
    }, [showAnnotations]);

    // 切换学生时清理该学生的渲染缓存
    useEffect(() => {
        // 切换学生时，清理 annotatedImages 但保留 ref（ref 会通过 studentKey 区分）
        setAnnotatedImages(new Map());
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
                                            <img src={imageUrl} alt={`Page ${pageIdx + 1}`} className="w-full h-auto" />
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
        const pageIndices = detailViewStudent.questionResults?.flatMap(q => q.pageIndices || []) || [];
        const fallbackPages: number[] = [];
        if (detailViewStudent.startPage !== undefined) {
            const start = detailViewStudent.startPage;
            const end = detailViewStudent.endPage ?? start;
            for (let i = start; i <= end; i += 1) {
                fallbackPages.push(i);
            }
        }
        const uniquePages = Array.from(new Set([...pageIndices, ...fallbackPages]))
            .filter(p => Number.isFinite(p))
            .sort((a, b) => a - b);
        const auditItems = (detailViewStudent.questionResults || []).filter((q) => (
            Boolean(q.selfCritique)
            || Boolean(q.reviewSummary)
            || Boolean(q.honestyNote)
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
        const studentAudit = detailViewStudent.selfAudit;

        return (
            <div className="h-full min-h-0 flex flex-col bg-white">
                {/* Navigation Header */}
                <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0 z-20">
                    <div className="flex items-center gap-4">
                        <SmoothButton onClick={() => setDetailViewIndex(null)} variant="ghost" size="sm" className="!p-2">
                            <ArrowLeft className="w-5 h-5 text-slate-500" />
                        </SmoothButton>
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
                </div>

                <div className="flex-1 min-h-0 overflow-hidden flex">
                    {/* Image Panel */}
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-white">
                        {/* 批注开关 */}
                        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
                                答题图片
                            </span>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <span className="text-xs text-slate-500">显示批注</span>
                                <div className="relative">
                                    <input
                                        type="checkbox"
                                        checked={showAnnotations}
                                        onChange={(e) => {
                                            setShowAnnotations(e.target.checked);
                                            if (!e.target.checked) {
                                                setAnnotatedImages(new Map());
                                            }
                                        }}
                                        className="sr-only peer"
                                    />
                                    <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-500"></div>
                                </div>
                                <Pencil className="w-3.5 h-3.5 text-slate-400" />
                            </label>
                        </div>
                        {uniquePages.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>No pages found for this student.</span>
                            </div>
                        )}
                        {uniquePages.map((pageIdx, pageIdxIndex) => {
                            const originalImageUrl = uploadedImages[pageIdx] || currentSession?.images[pageIdx]?.url;
                            const annotatedImageUrl = annotatedImages.get(pageIdx);
                            const isLoading = annotationLoading.has(pageIdx);
                            const displayImageUrl = showAnnotations && annotatedImageUrl ? annotatedImageUrl : originalImageUrl;
                            const isLastPage = pageIdxIndex === uniquePages.length - 1;
                            return (
                                <div key={pageIdx} className={clsx("pb-6 border-b border-slate-100/80 space-y-2", isLastPage && "border-b-0 pb-0")}>
                                    <div className="flex items-center justify-between">
                                        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
                                            Page {pageIdx + 1}
                                        </div>
                                        {showAnnotations && isLoading && (
                                            <div className="flex items-center gap-1 text-xs text-blue-500">
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                                渲染中...
                                            </div>
                                        )}
                                        {showAnnotations && annotatedImageUrl && !isLoading && (
                                            <div className="flex items-center gap-1 text-xs text-emerald-500">
                                                <Pencil className="w-3 h-3" />
                                                已批注
                                            </div>
                                        )}
                                    </div>
                                    {displayImageUrl ? (
                                        <img src={displayImageUrl} alt={`Page ${pageIdx + 1}`} className="w-full h-auto" />
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

                            {/* 🔥 批改透明度区块 - 显示第一次批改、自白、逻辑复核 */}
                            {(detailViewStudent.draftQuestionDetails || detailViewStudent.selfReport || detailViewStudent.logicReviewedAt) && (
                                <div className="border border-blue-100 bg-blue-50/30 rounded-xl p-4 space-y-4">
                                    <div className="flex items-center gap-2 text-blue-700 font-semibold text-sm">
                                        <AlertCircle className="w-4 h-4" />
                                        批改透明度
                                    </div>

                                    {/* 第一次批改 vs 最终结果对比 */}
                                    {detailViewStudent.draftTotalScore !== undefined && detailViewStudent.draftTotalScore !== detailViewStudent.score && (
                                        <div className="bg-white rounded-lg p-3 border border-blue-100">
                                            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400 mb-2">分数变化</div>
                                            <div className="flex items-center gap-3">
                                                <div className="text-center">
                                                    <div className="text-lg font-bold text-slate-400 line-through">
                                                        {detailViewStudent.draftTotalScore}
                                                    </div>
                                                    <div className="text-[10px] text-slate-400">初次批改</div>
                                                </div>
                                                <div className="text-slate-300">→</div>
                                                <div className="text-center">
                                                    <div className="text-lg font-bold text-emerald-600">
                                                        {detailViewStudent.score}
                                                    </div>
                                                    <div className="text-[10px] text-emerald-600">逻辑复核后</div>
                                                </div>
                                                <div className={clsx(
                                                    "ml-auto px-2 py-1 rounded text-xs font-semibold",
                                                    detailViewStudent.score > detailViewStudent.draftTotalScore
                                                        ? "bg-emerald-100 text-emerald-700"
                                                        : "bg-rose-100 text-rose-700"
                                                )}>
                                                    {detailViewStudent.score > detailViewStudent.draftTotalScore ? '+' : ''}
                                                    {(detailViewStudent.score - detailViewStudent.draftTotalScore).toFixed(1)}
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* 自白报告 */}
                                    {detailViewStudent.selfReport && (
                                        <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                                            <div className="text-[10px] uppercase tracking-[0.2em] text-amber-600 mb-2 flex items-center gap-1">
                                                <AlertTriangle className="w-3 h-3" />
                                                AI 自白报告
                                            </div>
                                            {detailViewStudent.selfReport.overallStatus && (
                                                <div className="text-xs text-amber-800 mb-2">
                                                    状态: {detailViewStudent.selfReport.overallStatus}
                                                </div>
                                            )}
                                            {detailViewStudent.selfReport.overallConfidence !== undefined && (
                                                <div className="text-xs text-amber-800 mb-2">
                                                    整体置信度: {(detailViewStudent.selfReport.overallConfidence * 100).toFixed(0)}%
                                                </div>
                                            )}
                                            {detailViewStudent.selfReport.highRiskQuestions && detailViewStudent.selfReport.highRiskQuestions.length > 0 && (
                                                <div className="mt-2">
                                                    <div className="text-[10px] text-amber-600 font-semibold mb-1">高风险题目:</div>
                                                    <div className="space-y-1">
                                                        {detailViewStudent.selfReport.highRiskQuestions.map((item, idx) => (
                                                            <div key={idx} className="text-xs text-amber-700 flex items-start gap-2">
                                                                <span className="font-mono text-amber-500">Q{item.questionId}</span>
                                                                <span>{item.description}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            {detailViewStudent.selfReport.issues && detailViewStudent.selfReport.issues.length > 0 && (
                                                <div className="mt-2">
                                                    <div className="text-[10px] text-amber-600 font-semibold mb-1">问题:</div>
                                                    <div className="space-y-1">
                                                        {detailViewStudent.selfReport.issues.map((item, idx) => (
                                                            <div key={idx} className="text-xs text-amber-700">
                                                                {item.questionId && <span className="font-mono text-amber-500 mr-1">Q{item.questionId}:</span>}
                                                                {item.message}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* 逻辑复核时间 */}
                                    {detailViewStudent.logicReviewedAt && (
                                        <div className="text-[11px] text-slate-500 flex items-center gap-2">
                                            <CheckCircle className="w-3 h-3 text-emerald-500" />
                                            逻辑复核完成于: {new Date(detailViewStudent.logicReviewedAt).toLocaleString('zh-CN')}
                                        </div>
                                    )}

                                    {/* 第一次批改详情（可展开） */}
                                    {detailViewStudent.draftQuestionDetails && detailViewStudent.draftQuestionDetails.length > 0 && (
                                        <details className="bg-white rounded-lg border border-slate-200">
                                            <summary className="px-3 py-2 text-xs font-semibold text-slate-600 cursor-pointer hover:bg-slate-50">
                                                查看初次批改详情 ({detailViewStudent.draftQuestionDetails.length} 题)
                                            </summary>
                                            <div className="px-3 pb-3 space-y-2 max-h-60 overflow-y-auto">
                                                {detailViewStudent.draftQuestionDetails.map((dq, idx) => {
                                                    const finalQ = detailViewStudent.questionResults?.find(q => q.questionId === dq.questionId);
                                                    const scoreChanged = finalQ && finalQ.score !== dq.score;
                                                    return (
                                                        <div key={idx} className={clsx(
                                                            "text-xs p-2 rounded border",
                                                            scoreChanged ? "border-amber-200 bg-amber-50/50" : "border-slate-100"
                                                        )}>
                                                            <div className="flex items-center justify-between">
                                                                <span className="font-mono text-slate-500">Q{dq.questionId}</span>
                                                                <div className="flex items-center gap-2">
                                                                    <span className={clsx(scoreChanged && "line-through text-slate-400")}>
                                                                        {dq.score}/{dq.maxScore}
                                                                    </span>
                                                                    {scoreChanged && finalQ && (
                                                                        <>
                                                                            <span className="text-slate-300">→</span>
                                                                            <span className="font-semibold text-emerald-600">
                                                                                {finalQ.score}/{finalQ.maxScore}
                                                                            </span>
                                                                        </>
                                                                    )}
                                                                </div>
                                                            </div>
                                                            {dq.selfCritique && (
                                                                <div className="mt-1 text-[11px] text-amber-700 italic">
                                                                    自白: {dq.selfCritique}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </details>
                                    )}
                                </div>
                            )}

                            <div className="border-b border-slate-100 pb-4">
                                <div className="flex items-center justify-between gap-4">
                                    <div className="text-sm font-semibold text-slate-700">Audit Query</div>
                                    <button
                                        type="button"
                                        onClick={() => setAuditOpen((prev) => !prev)}
                                        className="text-[11px] font-semibold text-slate-400 hover:text-slate-700 transition-colors"
                                    >
                                        {auditOpen ? 'Hide' : 'Open'}
                                    </button>
                                </div>
                                {auditOpen && (
                                    <div className="mt-3 space-y-3">
                                        <div className="text-[11px] text-slate-500">
                                            {auditItems.length > 0 ? `${auditItems.length} audit entries` : 'No audit entries'}
                                        </div>
                                        <input
                                            value={auditQuery}
                                            onChange={(event) => setAuditQuery(event.target.value)}
                                            className="w-full border-b border-slate-200 bg-transparent px-0 py-2 text-sm text-slate-700 focus:border-slate-700 focus:outline-none"
                                            placeholder="Search question id or keywords"
                                        />
                                        {(studentAudit?.summary || studentAudit?.honestyNote) && (
                                            <div className="space-y-1">
                                                <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Overall</div>
                                                <div className="space-y-1">
                                                    {renderParagraphs(studentAudit.summary || studentAudit.honestyNote || '')}
                                                </div>
                                            </div>
                                        )}
                                        {auditQueryValue ? (
                                            filteredAuditItems.length > 0 ? (
                                                <div className="space-y-4">
                                                    {filteredAuditItems.map((q, idx) => {
                                                        const tags = Array.from(new Set([...(q.reviewReasons || []), ...(q.auditFlags || [])]));
                                                        return (
                                                            <div key={`${q.questionId || idx}`} className="border-b border-slate-100 pb-3 last:border-b-0">
                                                                <div className="text-xs font-semibold text-slate-700">Q{q.questionId || idx + 1}</div>
                                                                {q.selfCritique && (
                                                                    <div className="mt-2 space-y-1">
                                                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Self-critique</div>
                                                                        <div className="space-y-1">
                                                                            {renderParagraphs(q.selfCritique)}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                {q.reviewSummary && (
                                                                    <div className="mt-2 space-y-1">
                                                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Logic Review</div>
                                                                        <div className="space-y-1">
                                                                            {renderParagraphs(q.reviewSummary)}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                {q.reviewCorrections && q.reviewCorrections.length > 0 && (
                                                                    <div className="mt-2 space-y-1 text-xs text-slate-600">
                                                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Corrections</div>
                                                                        <div className="space-y-1">
                                                                            {q.reviewCorrections.map((c) => (
                                                                                <div key={`${q.questionId}-${c.pointId || 'point'}`} className="flex items-start gap-2">
                                                                                    <span className="font-mono text-slate-400">{c.pointId || '-'}</span>
                                                                                    <span>{c.reviewReason || 'Review adjustment'}</span>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                {q.honestyNote && (
                                                                    <div className="mt-2 space-y-1">
                                                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Honesty Note</div>
                                                                        <div className="space-y-1">
                                                                            {renderParagraphs(q.honestyNote)}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                {tags.length > 0 && (
                                                                    <div className="mt-2 flex flex-wrap gap-2">
                                                                        {tags.map((tag) => (
                                                                            <span key={`${q.questionId}-${tag}`} className="text-[10px] text-slate-500 border border-slate-200 px-2 py-1">
                                                                                {tag}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            ) : (
                                                <div className="text-xs text-slate-400">No matches for current query.</div>
                                            )
                                        ) : (
                                            <div className="text-xs text-slate-400">Enter a query to view audit details.</div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Questions */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <Layers className="w-4 h-4 text-slate-500" />
                                    <h3 className="text-sm font-semibold text-slate-700">Analysis Detail</h3>
                                </div>
                                {detailViewStudent.questionResults?.map((q, idx) => (
                                    <div key={idx} className="border-b border-slate-100 pb-4 last:border-b-0">
                                        <QuestionDetail question={q} gradingMode={detailViewStudent.gradingMode} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // === Helpers ===
    const handleSelectStudent = (index: number) => setDetailViewIndex(index);
    const handleViewDetail = (student: StudentResult) => {
        const index = sortedResults.findIndex(r => r.studentName === student.studentName);
        setDetailViewIndex(index >= 0 ? index : 0);
    };

    // === Dashboard View ===
    if (results.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
                <div className="p-8 flex flex-col items-center gap-4">
                    <RocketOutlined className="text-4xl opacity-50" />
                    <p className="font-medium">暂无批改结果</p>
                    <SmoothButton onClick={() => setCurrentTab('process')} variant="ghost">
                        <ArrowLeft className="w-4 h-4 mr-2" /> 返回批改过程
                    </SmoothButton>
                </div>
            </div>
        );
    }

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
                        <SmoothButton variant="secondary" size="sm">
                            <Download className="w-4 h-4 mr-2" /> 导出 CSV
                        </SmoothButton>
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

                <div className="bg-white">
                    {sortedResults.map((result, index) => (
                        <div key={`${result.studentName}-${index}`} onClick={() => handleViewDetail(result)} className="cursor-pointer">
                            <ResultCard result={result} rank={index + 1} isExpanded={false} onExpand={() => { }} />
                        </div>
                    ))}
                </div>
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

            <RubricOverview />
        </div>
    );
};

export default ResultsView;
