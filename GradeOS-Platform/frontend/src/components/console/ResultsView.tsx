'use client';

import React, { useState, useContext, useMemo, useEffect, useCallback } from 'react';
import { useConsoleStore, StudentResult, QuestionResult } from '@/store/consoleStore';
import clsx from 'clsx';
import { ArrowLeft, ChevronDown, ChevronUp, CheckCircle, XCircle, Download, GitMerge, AlertCircle, Layers, FileText, Info, X, Sparkles, AlertTriangle, BookOpen, ListOrdered } from 'lucide-react';
import { CrownOutlined, BarChartOutlined, UsergroupAddOutlined, CheckCircleOutlined, ExclamationCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { Popover } from 'antd';
import { motion, AnimatePresence } from 'framer-motion';
import { RubricOverview } from './RubricOverview';
import { AppContext, AppContextType } from '../bookscan/AppContext';
import { MathText } from '@/components/common/MathText';
import { GlassCard } from '@/components/design-system/GlassCard';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { gradingApi } from '@/services/api';

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
    const showScoringDetails = !isAssist && !isChoice;
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
        <div className="pl-4 py-4 space-y-3 hover:bg-slate-50/50 transition-colors rounded-r-xl border-l-2 border-slate-100 hover:border-blue-400">
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                    <span className="font-bold text-slate-700 text-sm">第 {questionLabel} 题</span>
                    {question.isCrossPage && (
                        <span className="text-[10px] px-2 py-0.5 rounded border border-purple-200 text-purple-600 bg-purple-50 flex items-center gap-1 uppercase tracking-wide font-bold">
                            <Layers className="w-3 h-3" />
                            跨页
                        </span>
                    )}
                    {typeMeta && (
                        <span className={clsx(
                            "text-[10px] px-2 py-0.5 rounded border uppercase tracking-wide font-bold",
                            typeMeta.className
                        )}>
                            {typeMeta.label}
                        </span>
                    )}
                    {isAssist && (
                        <span className="text-[10px] px-2 py-0.5 rounded border border-slate-200 text-slate-500 bg-slate-50 uppercase tracking-wide font-bold">
                            Assist
                        </span>
                    )}
                </div>
                <span className={clsx('text-sm font-black font-mono', scoreClass)}>
                    {scoreLabel}
                </span>
            </div>

            {/* Meta Info */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
                {question.pageIndices && question.pageIndices.length > 0 && (
                    <div className="flex items-center gap-1.5">
                        <FileText className="w-3 h-3" />
                        Pages: <span className="font-mono text-slate-500">{question.pageIndices.map(p => p + 1).join(', ')}</span>
                    </div>
                )}
                {!isAssist && question.confidence !== undefined && (
                    <div className={clsx("flex items-center gap-1.5", question.confidence < 0.8 ? "text-amber-500" : "text-emerald-500")}>
                        {question.confidence < 0.8 ? <AlertCircle className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
                        Confidence: <span className="font-mono font-bold">{(question.confidence * 100).toFixed(0)}%</span>
                    </div>
                )}
            </div>

            {question.studentAnswer && (
                <div className="bg-slate-50/80 rounded-lg p-3 border border-slate-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 mb-1 block tracking-wider">Student Answer</span>
                    <div className="space-y-2">
                        {renderParagraphs(question.studentAnswer)}
                    </div>
                </div>
            )}

            {showScoringDetails ? (
                question.scoringPointResults && question.scoringPointResults.length > 0 ? (
                    <div className="mt-3 space-y-2">
                        <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 pl-1">评分步骤</div>
                        {question.scoringPointResults.map((spr, idx) => (
                            <div key={idx} className="group relative pl-4 border-l border-slate-200 py-1 hover:border-blue-300 transition-colors">
                                <div className="absolute -left-[5px] top-2.5 w-2.5 h-2.5 rounded-full bg-white border-2 border-slate-200 group-hover:border-blue-400 transition-colors" />
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
                                        <div className="text-[11px] text-slate-500 bg-slate-50 inline-block px-1.5 py-0.5 rounded border border-slate-100">
                                            判定: {spr.decision || (spr.awarded > 0 ? '得分' : '不得分')}
                                            {spr.reason && <span className="ml-1 opacity-75">- {spr.reason}</span>}
                                        </div>
                                    </div>
                                    <div className={clsx("font-mono font-bold text-sm whitespace-nowrap", spr.awarded > 0 ? "text-emerald-600" : "text-slate-300")}>
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
                    <div className="mt-2 text-xs text-amber-600 bg-amber-50 px-2 py-1.5 rounded border border-amber-100 flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Scores available but step breakdown missing.
                    </div>
                )
            ) : (
                <div className="mt-2 text-xs text-slate-400 italic">
                    {isAssist ? 'No scoring breakdown in Assist mode.' : 'No detailed analysis for this question type.'}
                </div>
            )}

            {showScoringDetails && (question.reviewSummary || (question.reviewCorrections && question.reviewCorrections.length > 0)) && (
                <div className="mt-3 p-3 bg-indigo-50/50 rounded-lg border border-indigo-100 shadow-sm">
                    <div className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <Sparkles className="w-3 h-3" /> 逻辑复核
                    </div>
                    {question.reviewSummary ? (
                        <p className="text-indigo-900/80 text-[11px] leading-relaxed"><MathText text={question.reviewSummary} /></p>
                    ) : (
                        <ul className="text-indigo-900/80 text-[11px] leading-relaxed space-y-1">
                            {question.reviewCorrections?.map((c, idx) => (
                                <li key={`${c.pointId}-${idx}`}>[{c.pointId}] {c.reviewReason || 'Logic adjustment applied.'}</li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            {question.feedback && (!isChoice || isAssist) && (
                <div className="mt-3 pt-3 border-t border-slate-100">
                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Feedback</div>
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
                'grid grid-cols-[56px_1fr_auto] items-center gap-4 px-4 py-3 border-b border-slate-200/70 hover:bg-slate-50/60 transition',
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
                    <span className="text-[10px] font-semibold tracking-wide text-slate-500 uppercase">{gradeLabel}</span>
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
        rubricDraft.questions.forEach((q) => {
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
            <div className="h-full min-h-0 flex flex-col bg-slate-50">
                <div className="bg-white/80 backdrop-blur-md border-b border-slate-200/60 px-6 py-4 flex items-center justify-between shrink-0 z-20">
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
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-slate-100/50">
                        {rubricImages.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>暂无批改标准图片</span>
                            </div>
                        ) : (
                            rubricImages.map((img, idx) => (
                                <GlassCard key={idx} className="overflow-hidden p-0 bg-white" hoverEffect={false}>
                                    <div className="px-4 py-2 border-b border-slate-100 bg-white/50 backdrop-blur-sm text-xs font-bold text-slate-500 flex justify-between">
                                        <span>Page {idx + 1}</span>
                                    </div>
                                    <img src={img} alt={`Rubric page ${idx + 1}`} className="w-full h-auto" />
                                </GlassCard>
                            ))
                        )}
                    </div>

                    <div className="w-1/2 h-full min-h-0 overflow-y-auto bg-white p-8 custom-scrollbar">
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
                                    {rubricDraft.questions.map((q) => {
                                        const isSelected = rubricSelectedIds.has(q.questionId);
                                        const isExpanded = rubricExpandedIds.has(q.questionId);
                                        return (
                                            <GlassCard
                                                key={q.questionId}
                                                className={clsx(
                                                    "p-4 border border-slate-100 !bg-white shadow-sm",
                                                    isSelected && "ring-1 ring-rose-200 bg-rose-50/30"
                                                )}
                                                hoverEffect={false}
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
                                                                {q.scoringPoints.map((sp) => (
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
                                            </GlassCard>
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
                <div className="h-full min-h-0 flex flex-col bg-slate-50">
                    <div className="bg-white/80 backdrop-blur-md border-b border-slate-200/60 px-6 py-4 flex items-center justify-between shrink-0 z-20">
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
            <div className="h-full min-h-0 flex flex-col bg-slate-50">
                <div className="bg-white/80 backdrop-blur-md border-b border-slate-200/60 px-6 py-4 flex items-center justify-between shrink-0 z-20">
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
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-slate-100/50">
                        <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-[0.2em]">
                            <span>学生作答</span>
                            <span>{reviewStudent.studentName}</span>
                        </div>
                        {reviewPageIndices.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>暂无作答图片</span>
                            </div>
                        ) : (
                            reviewPageIndices.map((pageIdx) => {
                                const imageUrl = uploadedImages[pageIdx] || currentSession?.images[pageIdx]?.url;
                                return (
                                    <GlassCard key={pageIdx} className="overflow-hidden p-0 bg-white" hoverEffect={false}>
                                        <div className="px-4 py-2 border-b border-slate-100 bg-white/50 backdrop-blur-sm text-xs font-bold text-slate-500 flex justify-between">
                                            <span>Page {pageIdx + 1}</span>
                                        </div>
                                        {imageUrl ? (
                                            <img src={imageUrl} alt={`Page ${pageIdx + 1}`} className="w-full h-auto" />
                                        ) : (
                                            <div className="p-10 text-center text-slate-400">Image missing</div>
                                        )}
                                    </GlassCard>
                                );
                            })
                        )}
                    </div>

                    <div className="w-1/2 h-full min-h-0 overflow-y-auto bg-white p-8 custom-scrollbar">
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
                                        <GlassCard
                                            key={q.questionId}
                                            className={clsx(
                                                "p-4 border border-slate-100 !bg-white shadow-sm",
                                                isSelected && "ring-1 ring-rose-200 bg-rose-50/30"
                                            )}
                                            hoverEffect={false}
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
                                        </GlassCard>
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

        return (
            <div className="h-full min-h-0 flex flex-col bg-slate-50">
                {/* Navigation Header */}
                <div className="bg-white/80 backdrop-blur-md border-b border-slate-200/60 px-6 py-4 flex items-center justify-between shrink-0 z-20">
                    <div className="flex items-center gap-4">
                        <SmoothButton onClick={() => setDetailViewIndex(null)} variant="ghost" size="sm" className="!p-2">
                            <ArrowLeft className="w-5 h-5 text-slate-500" />
                        </SmoothButton>
                        <div>
                            <h2 className="text-xl font-bold text-slate-800 flex items-center gap-3">
                                {detailViewStudent.studentName}
                                <span className={clsx("text-xs px-2 py-0.5 rounded font-bold uppercase tracking-wider bg-slate-100 text-slate-500 border border-slate-200")}>
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
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto p-6 border-r border-slate-200 custom-scrollbar space-y-6 bg-slate-100/50">
                        {uniquePages.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                                <FileText className="w-10 h-10 opacity-30" />
                                <span>No pages found for this student.</span>
                            </div>
                        )}
                        {uniquePages.map(pageIdx => {
                            const imageUrl = uploadedImages[pageIdx] || currentSession?.images[pageIdx]?.url;
                            return (
                                <GlassCard key={pageIdx} className="overflow-hidden p-0 bg-white" hoverEffect={false}>
                                    <div className="px-4 py-2 border-b border-slate-100 bg-white/50 backdrop-blur-sm text-xs font-bold text-slate-500 flex justify-between">
                                        <span>Page {pageIdx + 1}</span>
                                    </div>
                                    {imageUrl ? <img src={imageUrl} alt={`Page ${pageIdx + 1}`} className="w-full h-auto" /> : <div className="p-10 text-center text-slate-400">Image missing</div>}
                                </GlassCard>
                            )
                        })}
                    </div>

                    {/* Details Panel */}
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto bg-white p-8 custom-scrollbar">
                        <div className="max-w-2xl mx-auto space-y-8">
                            {/* Score Header */}
                            <div className="text-center pb-8 border-b border-slate-100">
                                <div className="text-6xl font-black text-slate-800 tracking-tighter mb-1">
                                    {isAssist ? '--' : detailViewStudent.score}
                                    {!isAssist && <span className="text-2xl text-slate-300 font-bold ml-1">/ {detailViewStudent.maxScore}</span>}
                                </div>
                                <div className="text-sm font-bold text-slate-400 uppercase tracking-[0.2em]">{isAssist ? 'Assisted Grading' : 'Total Score'}</div>
                            </div>

                            {detailViewStudent.selfAudit && (
                                <GlassCard className="p-4 border border-slate-100 bg-slate-50/80" hoverEffect={false}>
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Confession</div>
                                        {detailViewStudent.selfAudit.overallComplianceGrade !== undefined && (
                                            <div className="text-xs font-semibold text-slate-500">
                                                合规评分 {Math.round(detailViewStudent.selfAudit.overallComplianceGrade)} / 7
                                            </div>
                                        )}
                                    </div>
                                    {detailViewStudent.selfAudit.summary && (
                                        <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                                            {detailViewStudent.selfAudit.summary}
                                        </p>
                                    )}
                                    {detailViewStudent.selfAudit.uncertaintiesAndConflicts && detailViewStudent.selfAudit.uncertaintiesAndConflicts.length > 0 && (
                                        <ul className="mt-3 space-y-1 text-[11px] text-slate-500 list-disc pl-4">
                                            {detailViewStudent.selfAudit.uncertaintiesAndConflicts.slice(0, 4).map((item, idx) => (
                                                <li key={`confession-${idx}`}>
                                                    {item.issue || item.impact || '存在未披露的不确定性'}
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </GlassCard>
                            )}

                            {/* Questions */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <Layers className="w-4 h-4 text-blue-500" />
                                    <h3 className="text-sm font-black text-slate-800 uppercase tracking-wider">Analysis Detail</h3>
                                </div>
                                {detailViewStudent.questionResults?.map((q, idx) => (
                                    <GlassCard key={idx} className="p-0 overflow-hidden !bg-white border-none shadow-sm ring-1 ring-slate-100" hoverEffect={false}>
                                        <QuestionDetail question={q} gradingMode={detailViewStudent.gradingMode} />
                                    </GlassCard>
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
                <GlassCard className="p-8 flex flex-col items-center gap-4">
                    <RocketOutlined className="text-4xl opacity-50" />
                    <p className="font-medium">暂无批改结果</p>
                    <SmoothButton onClick={() => setCurrentTab('process')} variant="ghost">
                        <ArrowLeft className="w-4 h-4 mr-2" /> 返回批改过程
                    </SmoothButton>
                </GlassCard>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-6 space-y-8 custom-scrollbar">
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
                            <GlassCard className="p-6 space-y-4 shadow-2xl">
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
                                            <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
                                                <div className="text-xl font-black text-slate-700">{classReport.averageScore?.toFixed(1)}</div>
                                                <div className="text-[10px] font-bold text-slate-400 uppercase mt-1">Avg Score</div>
                                            </div>
                                            <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
                                                <div className="text-xl font-black text-slate-700">{classReport.averagePercentage?.toFixed(1)}%</div>
                                                <div className="text-[10px] font-bold text-slate-400 uppercase mt-1">Avg Rate</div>
                                            </div>
                                            <div className="bg-emerald-50 rounded-xl p-3 text-center border border-emerald-100">
                                                <div className="text-xl font-black text-emerald-600">{((classReport.passRate ?? 0) * 100).toFixed(1)}%</div>
                                                <div className="text-[10px] font-bold text-emerald-500 uppercase mt-1">Pass Rate</div>
                                            </div>
                                            <div className="bg-blue-50 rounded-xl p-3 text-center border border-blue-100">
                                                <div className="text-xl font-black text-blue-600">{classReport.totalStudents}</div>
                                                <div className="text-[10px] font-bold text-blue-500 uppercase mt-1">Students</div>
                                            </div>
                                        </div>
                                        <p className="text-sm text-slate-600 leading-relaxed bg-white/50 p-4 rounded-xl border border-slate-100">
                                            {classReport.summary}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="text-center py-10 text-slate-400">暂无分析数据</div>
                                )}
                            </GlassCard>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Dashboard Header */}
            <div className="border border-slate-200/80 bg-white/90">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 px-6 py-5 border-b border-slate-200/70">
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 grid place-items-center rounded-lg bg-slate-900 text-white">
                            <RocketOutlined className="text-lg" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900 tracking-tight">批改总览</h2>
                            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">Grading Overview</p>
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
                            <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">
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

                <div className="border border-slate-200/80 bg-white">
                    {sortedResults.map((result, index) => (
                        <div key={`${result.studentName}-${index}`} onClick={() => handleViewDetail(result)} className="cursor-pointer">
                            <ResultCard result={result} rank={index + 1} isExpanded={false} onExpand={() => { }} />
                        </div>
                    ))}
                </div>
            </div>

{/* Cross Page Alerts */}
            {crossPageQuestions.length > 0 && (
                <div className="border border-slate-200/80 bg-white p-4">
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
