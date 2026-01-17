'use client';

import React, { useState, useContext, useMemo } from 'react';
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

    let barColor = 'from-slate-400 to-slate-500';
    let gradeLabel = '待提升';
    let gradeBadgeColor = 'bg-slate-100 text-slate-600';

    if (isAssist) {
        barColor = 'from-slate-300 to-slate-400';
        gradeLabel = 'Assist';
        gradeBadgeColor = 'bg-slate-50 text-slate-500 border-slate-200';
    } else if (percentage >= 85) {
        barColor = 'from-emerald-400 to-emerald-600';
        gradeLabel = '优秀';
        gradeBadgeColor = 'bg-emerald-50 text-emerald-600 border-emerald-100';
    } else if (percentage >= 70) {
        barColor = 'from-blue-400 to-indigo-600';
        gradeLabel = '良好';
        gradeBadgeColor = 'bg-blue-50 text-blue-600 border-blue-100';
    } else if (percentage >= 60) {
        barColor = 'from-amber-400 to-orange-500';
        gradeLabel = '及格';
        gradeBadgeColor = 'bg-amber-50 text-amber-600 border-amber-100';
    } else {
        barColor = 'from-rose-400 to-red-600';
        gradeLabel = '不及格';
        gradeBadgeColor = 'bg-red-50 text-red-600 border-red-100';
    }

    const crossPageCount = result.questionResults?.filter(q => q.isCrossPage).length || 0;

    const rankStyle = rank <= 3
        ? 'from-amber-200 to-amber-400 text-amber-900 ring-amber-200/70'
        : 'from-slate-100 to-slate-200 text-slate-600 ring-slate-200/70';

    return (
        <GlassCard
            className={clsx(
                'group relative overflow-hidden hover:z-10 transition-all duration-300',
                result.needsConfirmation && 'ring-2 ring-amber-400/50 shadow-[0_0_15px_rgba(251,191,36,0.2)]'
            )}
            hoverEffect={true}
        >
            <div className={clsx('absolute inset-y-0 left-0 w-1.5 bg-gradient-to-b', barColor)} />
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r from-blue-50/40 via-white/60 to-emerald-50/30" />

            <div className="relative flex items-center gap-4 p-4">
                <div className={clsx(
                    'w-10 h-10 flex items-center justify-center rounded-xl font-black font-mono text-sm shrink-0 shadow-sm ring-1',
                    'bg-gradient-to-br',
                    rankStyle
                )}>
                    {rank}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-bold text-slate-800 text-base truncate">{result.studentName}</h3>
                        <span className={clsx(
                            "text-[10px] px-2 py-0.5 rounded-full border border-transparent font-bold uppercase tracking-wide",
                            gradeBadgeColor
                        )}>
                            {gradeLabel}
                        </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-[10px] font-medium text-slate-400">
                        {result.totalRevisions !== undefined && result.totalRevisions > 0 && (
                            <span className="flex items-center gap-1 bg-violet-50 text-violet-600 px-2 py-0.5 rounded-full border border-violet-100">
                                <GitMerge className="w-3 h-3" /> {result.totalRevisions} revisions
                            </span>
                        )}
                        {crossPageCount > 0 && (
                            <span className="flex items-center gap-1 bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full border border-purple-100">
                                <Layers className="w-3 h-3" /> {crossPageCount} cross-page
                            </span>
                        )}
                        {result.needsConfirmation && (
                            <span className="flex items-center gap-1 bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full border border-amber-100">
                                <AlertCircle className="w-3 h-3" /> Needs Review
                            </span>
                        )}
                        {result.startPage !== undefined && (
                            <span className="flex items-center gap-1 px-2 py-0.5 bg-slate-50 rounded-full border border-slate-100">
                                <FileText className="w-3 h-3" /> Pages {result.startPage + 1}-{result.endPage !== undefined ? result.endPage + 1 : '?'}
                            </span>
                        )}
                    </div>
                </div>

                <div className="flex flex-col items-end gap-2 min-w-[150px]">
                    <div className="flex items-baseline gap-1.5">
                        <span className={clsx(
                            "text-2xl font-black font-mono tracking-tight",
                            isAssist ? "text-slate-400" : "text-transparent bg-clip-text bg-gradient-to-r " + barColor
                        )}>
                            {isAssist ? 'N/A' : result.score}
                        </span>
                        {!isAssist && <span className="text-xs font-bold text-slate-300">/ {result.maxScore}</span>}
                    </div>

                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden ring-1 ring-slate-50">
                        <motion.div
                            className={clsx('h-full bg-gradient-to-r', barColor)}
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ duration: 1, ease: 'easeOut' }}
                        />
                    </div>
                </div>

                {result.questionResults && result.questionResults.length > 0 && (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onExpand();
                        }}
                        className="p-2 -mr-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-blue-500 transition-colors"
                    >
                        {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    </button>
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

export const ResultsView: React.FC = () => {
    const { finalResults, workflowNodes, crossPageQuestions, uploadedImages, setCurrentTab, classReport } = useConsoleStore();
    const bookScanContext = useContext(AppContext) as AppContextType | null;
    const sessions = bookScanContext?.sessions || [];
    const currentSessionId = bookScanContext?.currentSessionId || null;
    const currentSession = sessions.find((s: any) => s.id === currentSessionId);

    const [detailViewIndex, setDetailViewIndex] = useState<number | null>(null);
    const [showClassReport, setShowClassReport] = useState(false);

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
            <div className="relative overflow-hidden rounded-3xl border border-slate-200/60 bg-white/70 p-6 md:p-8 shadow-[0_30px_80px_-60px_rgba(15,23,42,0.45)]">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-50/80 via-white/70 to-emerald-50/60" />
                <div className="relative space-y-6">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="relative">
                                <div className="absolute -inset-1 rounded-2xl bg-blue-500/20 blur" />
                                <div className="relative p-3 bg-slate-900 text-white rounded-2xl shadow-lg shadow-slate-900/20">
                                    <RocketOutlined className="text-xl" />
                                </div>
                            </div>
                            <div>
                                <h2 className="text-2xl font-black text-slate-900 tracking-tight">批改结果</h2>
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-[0.2em]">Grading Overview</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <SmoothButton onClick={() => setShowClassReport(true)} variant="secondary" size="sm">
                                <BarChartOutlined className="mr-2" /> 班级报告
                            </SmoothButton>
                            <SmoothButton variant="secondary" size="sm">
                                <Download className="w-4 h-4 mr-2" /> 导出 CSV
                            </SmoothButton>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                        {metrics.map((metric) => (
                            <GlassCard
                                key={metric.label}
                                className={clsx(
                                    'relative overflow-hidden rounded-2xl border p-4 text-left',
                                    metric.surface
                                )}
                                hoverEffect={false}
                            >
                                <div className={clsx('absolute -right-8 -top-8 h-20 w-20 rounded-full blur-2xl', metric.glow)} />
                                <div className="relative flex items-center justify-between">
                                    <div className="text-[11px] font-bold text-slate-500 uppercase tracking-[0.2em]">{metric.label}</div>
                                    <metric.icon className={clsx('text-lg', metric.accent)} />
                                </div>
                                <div className="relative mt-3 text-2xl font-black text-slate-800">
                                    {metric.value}
                                </div>
                            </GlassCard>
                        ))}
                    </div>
                </div>
            </div>

            {/* Results List */}
            <div className="space-y-4">
                <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-2">
                        <ListOrdered className="w-5 h-5 text-slate-400" />
                        <h3 className="font-bold text-slate-700">学生列表</h3>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 bg-white/70 px-2 py-0.5 rounded-full border border-slate-100">
                            {totalStudents} students
                        </span>
                    </div>
                    {totalCrossPageQuestions > 0 && (
                        <span className="text-[10px] font-bold uppercase tracking-widest text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-100">
                            {totalCrossPageQuestions} cross-page
                        </span>
                    )}
                </div>

                <div className="space-y-3 rounded-2xl border border-slate-100/80 bg-white/70 p-3 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.5)]">
                    {sortedResults.map((result, index) => (
                        <div key={`${result.studentName}-${index}`} onClick={() => handleViewDetail(result)} className="cursor-pointer">
                            <ResultCard result={result} rank={index + 1} isExpanded={false} onExpand={() => { }} />
                        </div>
                    ))}
                </div>
            </div>

            {/* Cross Page Alerts */}
            {crossPageQuestions.length > 0 && (
                <GlassCard className="p-5 border-l-4 border-l-purple-500 bg-purple-50/30">
                    <div className="flex items-center gap-2 text-purple-700 font-bold mb-3">
                        <Layers className="w-5 h-5" />
                        跨页题目识别 (Cross-page Questions)
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {crossPageQuestions.map((cpq, idx) => (
                            <div key={idx} className="bg-white/60 p-3 rounded-lg border border-purple-100 flex items-center justify-between">
                                <span className="font-bold text-slate-700 text-sm">Question {cpq.questionId}</span>
                                <div className="flex items-center gap-3">
                                    <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">
                                        Pages {cpq.pageIndices.map(p => p + 1).join(', ')}
                                    </span>
                                    {cpq.confidence < 0.8 && (
                                        <span className="text-[10px] font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded flex items-center gap-1">
                                            <AlertTriangle className="w-3 h-3" /> Check
                                        </span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </GlassCard>
            )}

            <RubricOverview />
        </div>
    );
};

export default ResultsView;
