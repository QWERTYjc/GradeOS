'use client';

import React, { useState, useContext, useMemo } from 'react';
import { useConsoleStore, StudentResult, QuestionResult } from '@/store/consoleStore';
import clsx from 'clsx';
import { ArrowLeft, ChevronDown, ChevronUp, CheckCircle, XCircle, Download, GitMerge, AlertCircle, Layers, FileText, Info, X } from 'lucide-react';
import { CrownOutlined, BarChartOutlined, UsergroupAddOutlined, CheckCircleOutlined, ExclamationCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { Popover } from 'antd';
import { motion } from 'framer-motion';
import { RubricOverview } from './RubricOverview';
import { AppContext, AppContextType } from '../bookscan/AppContext';
import { MathText } from '@/components/common/MathText';

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
        : (percentage >= 60 ? 'text-green-600' : 'text-red-600');
    const typeMeta = (() => {
        if (!normalizedType) return null;
        if (normalizedType === 'choice') return { label: 'Choice', className: 'border-blue-200 text-blue-600' };
        if (normalizedType === 'objective') return { label: 'Objective', className: 'border-emerald-200 text-emerald-600' };
        if (normalizedType === 'subjective') return { label: 'Subjective', className: 'border-amber-200 text-amber-600' };
        return { label: normalizedType, className: 'border-slate-200 text-slate-500' };
    })();

    return (
        <div className="border-l-2 border-slate-200 pl-4 py-3 space-y-2">
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-700">第 {questionLabel} 题</span>
                    {question.isCrossPage && (
                        <span className="text-[10px] px-2 py-0.5 rounded-sm border border-purple-200 text-purple-600 flex items-center gap-1 uppercase tracking-wide">
                            <Layers className="w-3 h-3" />
                            跨页
                        </span>
                    )}
                    {typeMeta && (
                        <span className={clsx(
                            "text-[10px] px-2 py-0.5 rounded-sm border uppercase tracking-wide",
                            typeMeta.className
                        )}>
                            {typeMeta.label}
                        </span>
                    )}
                    {isAssist && (
                        <span className="text-[10px] px-2 py-0.5 rounded-sm border border-slate-200 text-slate-500 uppercase tracking-wide">
                            Assist
                        </span>
                    )}
                </div>
                <span className={clsx('text-sm font-semibold', scoreClass)}>
                    {scoreLabel}
                </span>
            </div>

            {question.pageIndices && question.pageIndices.length > 0 && (
                <div className="text-[11px] text-slate-400 flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    页面: {question.pageIndices.map(p => p + 1).join(', ')}
                </div>
            )}

            {question.studentAnswer && (
                <div className="text-[11px] text-slate-500">
                    <span className="font-semibold mr-1">Answer:</span>
                    <MathText className="text-slate-600" text={question.studentAnswer} />
                </div>
            )}

            {showScoringDetails ? (
                question.scoringPointResults && question.scoringPointResults.length > 0 ? (
                <div className="mt-2 space-y-2">
                    <div className="text-[10px] uppercase tracking-[0.3em] font-bold text-slate-400 mb-1">评分步骤</div>
                    {question.scoringPointResults.map((spr, idx) => (
                        <div key={idx} className="flex items-start gap-3 text-xs py-3 border-b border-slate-200/70">
                            <div className="mt-0.5">
                                {spr.awarded > 0 ? (
                                    <CheckCircle className="w-3.5 h-3.5 text-slate-500" />
                                ) : (
                                    <XCircle className="w-3.5 h-3.5 text-slate-400" />
                                )}
                            </div>
                            <div className="flex-1">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="font-semibold text-slate-700">
                                        <span className="inline-flex items-center justify-center min-w-[2rem] px-1.5 py-0.5 mr-1.5 text-[10px] font-bold rounded-sm bg-slate-100 text-slate-600 border border-slate-200">
                                            步骤 {idx + 1}
                                        </span>
                                        {spr.pointId && (
                                            <span className="text-slate-500 mr-1">[{spr.pointId}]</span>
                                        )}
                                        [{spr.awarded}/{spr.maxPoints ?? spr.scoringPoint?.score ?? 0}]{' '}
                                        <MathText
                                            className="text-slate-700"
                                            text={spr.scoringPoint?.description || spr.description || "N/A"}
                                        />
                                    </span>
                                    <Popover
                                        title={<span className="font-bold text-gray-800">批改标准 [{spr.pointId || spr.scoringPoint?.pointId}]</span>}
                                        content={
                                            <div className="max-w-xs space-y-2">
                                                <div className="text-sm p-3 bg-gray-50 rounded-md border border-gray-100">
                                                    <span className="font-bold text-blue-600 mr-2">标准要求:</span>
                                                    {spr.scoringPoint?.description || spr.description}
                                                </div>
                                                <div className="flex items-center justify-between text-xs px-1">
                                                    <span className="text-gray-500">满分值: <span className="font-bold text-gray-700">{spr.maxPoints ?? spr.scoringPoint?.score ?? 0}</span></span>
                                                    <span className={clsx(
                                                        "px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase",
                                                        spr.scoringPoint?.isRequired ? "bg-slate-100 text-slate-600" : "bg-slate-100 text-slate-600"
                                                    )}>
                                                        {spr.scoringPoint?.isRequired ? "关键指标" : "普通指标"}
                                                    </span>
                                                </div>
                                            </div>
                                        }
                                        trigger="hover"
                                        placement="right"
                                    >
                                        <Info className="w-3.5 h-3.5 text-gray-400 hover:text-gray-600 cursor-help transition-colors ml-1" />
                                    </Popover>
                                </div>
                                <div className="mt-1 text-[11px] text-slate-600">
                                    <span className="font-semibold mr-1">判定:</span>
                                    {spr.decision || (spr.awarded > 0 ? '得分' : '不得分')}
                                    {spr.reason && (
                                        <span className="text-slate-500 ml-2">
                                            理由: <MathText className="text-slate-500" text={spr.reason} />
                                        </span>
                                    )}
                                </div>
                                {spr.reviewAdjusted && (
                                    <div className="mt-1 text-[11px] text-indigo-600">
                                        <span className="font-semibold mr-1">复核修正:</span>
                                        {spr.reviewReason || '逻辑复核已调整该评分点'}
                                        {spr.reviewBefore && (
                                            <span className="text-slate-500 ml-1">
                                                (原: {spr.reviewBefore.decision || '—'} {spr.reviewBefore.awarded ?? '-'} 分)
                                            </span>
                                        )}
                                    </div>
                                )}
                                {spr.evidence && (
                                    <div className="mt-1 text-[11px] text-slate-600">
                                        <span className="font-semibold mr-1">原文:</span>
                                        <MathText className="text-slate-600" text={normalizeEvidenceText(spr.evidence)} />
                                    </div>
                                )}
                                {spr.rubricReference ? (
                                    <div className="mt-1 text-[11px] text-slate-500">
                                        <span className="font-semibold mr-1">引用标准:</span>
                                        <MathText className="text-slate-500" text={spr.rubricReference} />
                                        {spr.rubricReferenceSource === 'system' && (
                                            <span className="ml-1 text-[10px] text-slate-400">(系统补全)</span>
                                        )}
                                    </div>
                                ) : (
                                    <div className="mt-1 text-[11px] text-amber-600">
                                        <span className="font-semibold mr-1">引用标准缺失:</span>该步骤未返回 rubric ref
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            ) : question.scoringPoints && question.scoringPoints.length > 0 ? (
                <div className="mt-2 space-y-1">
                    {question.scoringPoints.map((sp, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs">
                            {sp.isCorrect ? (
                                <CheckCircle className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                            ) : (
                                <XCircle className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />
                            )}
                            <div className="flex-1">
                                <span className={clsx(
                                    sp.isCorrect ? 'text-green-700' : 'text-red-700'
                                )}>
                                    [{sp.score}/{sp.maxScore}] {sp.description}
                                </span>
                                {sp.explanation && (
                                    <p className="text-gray-500 mt-0.5">{sp.explanation}</p>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
                ) : (
                    <div className="mt-2 text-xs text-amber-600">
                        评分步骤缺失：模型未返回逐条评分结果
                    </div>
                )
            ) : (
                <div className="mt-2 text-xs text-slate-500">
                    {isAssist ? 'Assist mode: no scoring details.' : 'Choice question: no analysis.'}
                </div>
            )}

            {showScoringDetails && question.reviewSummary && (
                <div className="mt-2 px-2 py-2 bg-indigo-50/70 border-l-2 border-indigo-300">
                    <div className="text-[10px] font-bold text-indigo-600 mb-0.5">逻辑复核</div>
                    <p className="text-slate-600 text-[11px] leading-relaxed"><MathText className="text-slate-600" text={question.reviewSummary} /></p>
                </div>
            )}
            {showScoringDetails && !question.reviewSummary && question.reviewCorrections && question.reviewCorrections.length > 0 && (
                <div className="mt-2 px-2 py-2 bg-indigo-50/70 border-l-2 border-indigo-300">
                    <div className="text-[10px] font-bold text-indigo-600 mb-0.5">逻辑复核</div>
                    <ul className="text-slate-600 text-[11px] leading-relaxed space-y-1">
                        {question.reviewCorrections.map((c, idx) => (
                            <li key={`${c.pointId}-${idx}`}>
                                [{c.pointId}] {c.reviewReason || '已修正评分逻辑'}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {question.feedback && (!isChoice || isAssist) && (
                <p className="mt-2 text-xs text-sky-700/80 pb-2 border-b border-slate-200/60 italic">
                    <span className="font-semibold mr-1">总结:</span>
                    <MathText className="text-sky-700/80" text={question.feedback} />
                </p>
            )}
            {showScoringDetails && (question.rubricRefs && question.rubricRefs.length > 0 ? (
                <div className="text-[11px] text-slate-500">
                    <span className="font-semibold mr-1">引用标准:</span>
                    <MathText className="text-slate-500" text={question.rubricRefs.join(", ")} />
                </div>
            ) : (
                <div className="text-[11px] text-amber-600">
                    <span className="font-semibold mr-1">引用标准缺失:</span>模型未返回 rubric ref
                </div>
            ))}

            {showScoringDetails && question.typoNotes && question.typoNotes.length > 0 && (
                <div className="mt-2 text-[11px] text-rose-700">
                    <span className="font-semibold mr-1">Typos:</span>
                    <MathText className="text-rose-700" text={question.typoNotes.join(", ")} />
                </div>
            )}

            {showScoringDetails && (question.selfCritique ? (
                <div className="mt-2 px-2 py-2 bg-slate-50/80 border-l-2 border-slate-300">
                    <div className="text-[10px] font-bold text-slate-500 mb-0.5">
                        自白
                        {typeof question.selfCritiqueConfidence === 'number' && (
                            <span className="ml-1 text-[10px] text-slate-400">
                                (置信度 {(question.selfCritiqueConfidence * 100).toFixed(0)}%)
                            </span>
                        )}
                    </div>
                    <p className="text-slate-600 text-[11px] leading-relaxed"><MathText className="text-slate-600" text={question.selfCritique} /></p>
                </div>
            ) : (
                <div className="mt-2 px-2 py-2 bg-amber-50/70 border-l-2 border-amber-300">
                    <div className="text-[10px] font-bold text-amber-600 mb-0.5">
                        自白缺失
                        {typeof question.selfCritiqueConfidence === 'number' && (
                            <span className="ml-1 text-[10px] text-amber-500">
                                (置信度 {(question.selfCritiqueConfidence * 100).toFixed(0)}%)
                            </span>
                        )}
                    </div>
                    <p className="text-slate-600 text-[11px] leading-relaxed">模型未返回自白内容。</p>
                </div>
            ))}

            {!isAssist && question.confidence !== undefined && question.confidence < 0.8 && (
                <div className="mt-1 text-xs text-yellow-600 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    置信度较低 ({(question.confidence * 100).toFixed(0)}%)，建议人工复核
                    {question.confidenceReason && (
                        <span className="text-[11px] text-slate-500 ml-1">({question.confidenceReason})</span>
                    )}
                </div>
            )}
            {!isAssist && question.confidence === undefined && (
                <div className="mt-1 text-xs text-slate-400">置信度：模型未提供</div>
            )}

            {question.mergeSource && question.mergeSource.length > 0 && (
                <div className="mt-1 text-xs text-purple-500 flex items-center gap-1">
                    <GitMerge className="w-3 h-3" />
                    合并自: {question.mergeSource.join(', ')}
                </div>
            )}
        </div>
    );
};

const ResultCard: React.FC<ResultCardProps> = ({ result, rank, onExpand, isExpanded }) => {
    const isAssist = (result.gradingMode || '').startsWith('assist') || result.maxScore <= 0;
    const percentage = !isAssist && result.maxScore > 0 ? (result.score / result.maxScore) * 100 : 0;

    let barColor = 'from-slate-400 to-slate-500';
    let toneClass = 'result-chip-muted';
    let gradeLabel = '待提升';

    if (isAssist) {
        barColor = 'from-slate-300 to-slate-400';
        toneClass = 'result-chip-muted';
        gradeLabel = 'Assist';
    } else if (percentage >= 85) {
        barColor = 'from-emerald-400 to-emerald-600';
        toneClass = 'result-chip-elite';
        gradeLabel = '优秀';
    } else if (percentage >= 70) {
        barColor = 'from-sky-400 to-blue-600';
        toneClass = 'result-chip-strong';
        gradeLabel = '良好';
    } else if (percentage >= 60) {
        barColor = 'from-amber-400 to-orange-500';
        toneClass = 'result-chip-pass';
        gradeLabel = '及格';
    } else {
        barColor = 'from-rose-400 to-red-600';
        toneClass = 'result-chip-risk';
        gradeLabel = '不及格';
    }

    const crossPageCount = result.questionResults?.filter(q => q.isCrossPage).length || 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 180, damping: 20, delay: Math.min(rank, 6) * 0.04 }}
            className={clsx(
                'result-row',
                result.needsConfirmation && 'result-row-alert'
            )}
        >
            <div className={clsx('result-rank', rank <= 3 && 'result-rank-top')}>{rank}</div>

            <div className="result-main">
                <div className="result-name">{result.studentName}</div>
                <div className="result-meta">
                    <span className={clsx('result-chip', toneClass)}>{gradeLabel}</span>
                    {result.totalRevisions !== undefined && result.totalRevisions > 0 && (
                        <span className="result-chip result-chip-info">
                            <GitMerge className="w-3 h-3" />
                            {result.totalRevisions} 次修正
                        </span>
                    )}
                    {crossPageCount > 0 && (
                        <span className="result-chip result-chip-info">
                            <Layers className="w-3 h-3" />
                            {crossPageCount} 道跨页
                        </span>
                    )}
                    {result.needsConfirmation && (
                        <span className="result-chip result-chip-warn">
                            <AlertCircle className="w-3 h-3" />
                            待确认
                        </span>
                    )}
                </div>
                {result.startPage !== undefined && result.endPage !== undefined && (
                    <div className="result-pages">
                        <FileText className="w-3 h-3" />
                        页面 {result.startPage + 1} - {result.endPage + 1}
                        {result.confidence !== undefined && (
                            <span>置信度 {(result.confidence * 100).toFixed(0)}%</span>
                        )}
                    </div>
                )}
            </div>

            <div className="result-score">
                <span className="result-score-value">{isAssist ? 'N/A' : result.score}</span>
                <span className="result-score-max">{isAssist ? '' : `/ ${result.maxScore}`}</span>
            </div>

            <div className="result-bar">
                <div
                    className={clsx('result-bar-fill bg-gradient-to-r', barColor)}
                    style={{ width: `${percentage}%` }}
                />
            </div>

            <div className="result-percent">{isAssist ? 'Assist' : `${percentage.toFixed(1)}%`}</div>

            {result.questionResults && result.questionResults.length > 0 && (
                <button
                    onClick={onExpand}
                    className="result-expand"
                >
                    {isExpanded ? (
                        <ChevronUp className="w-4 h-4" />
                    ) : (
                        <ChevronDown className="w-4 h-4" />
                    )}
                </button>
            )}
        </motion.div>
    );
};

const normalizeQuestionId = (questionId: string) => {
    const raw = (questionId || '').toString().trim();
    if (!raw) return 'unknown';
    return raw
        .replace(/^第\s*/i, '')
        .replace(/^q\s*/i, '')
        .replace(/\s*题$/i, '')
        .replace(/\s+/g, '')
        .replace(/[。．\.,，、]+$/g, '');
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
            return {
                ...items[0],
                questionId: normalizeQuestionId(items[0].questionId)
            };
        }

        const mergedPointsMap = new Map<string, any>();
        const mergedPageIndices = new Set<number>();
        const mergedSources = new Set<string>();
        const mergedRubricRefs = new Set<string>();
        const mergedSelfCritique = new Set<string>();
        const mergedConfidenceReasons = new Set<string>();
        const mergedTypoNotes = new Set<string>();
        const selfCritiqueConfidenceValues: number[] = [];
        const confidenceValues: number[] = [];
        let mergedQuestionType = '';
        let mergedStudentAnswer = '';
        let mergedScore = 0;
        let mergedMaxScore = 0;
        let mergedFeedback = '';
        let hasPointDetails = false;

        items.forEach((item, itemIndex) => {
            mergedMaxScore = Math.max(mergedMaxScore, item.maxScore || 0);
            if (item.feedback && !mergedFeedback) {
                mergedFeedback = item.feedback;
            }
            if (item.questionType && !mergedQuestionType) {
                mergedQuestionType = item.questionType;
            }
            if (item.studentAnswer && !mergedStudentAnswer) {
                mergedStudentAnswer = item.studentAnswer;
            }
            if (typeof item.confidence === 'number') {
                confidenceValues.push(item.confidence);
            }
            if (typeof item.selfCritiqueConfidence === 'number') {
                selfCritiqueConfidenceValues.push(item.selfCritiqueConfidence);
            }
            (item.rubricRefs || []).forEach((ref) => mergedRubricRefs.add(ref));
            if (item.selfCritique) mergedSelfCritique.add(item.selfCritique);
            if (item.confidenceReason) mergedConfidenceReasons.add(item.confidenceReason);
            (item.typoNotes || []).forEach((note) => mergedTypoNotes.add(note));
            (item.pageIndices || []).forEach((idx) => mergedPageIndices.add(idx));
            (item.mergeSource || []).forEach((src) => mergedSources.add(src));

            const pointResults = item.scoringPointResults || [];
            if (pointResults.length > 0) {
                hasPointDetails = true;
                pointResults.forEach((point, pointIndex) => {
                    const pointKey = (point.pointId || point.description || point.scoringPoint?.description || `${itemIndex}-${pointIndex}`)
                        .toString()
                        .trim();
                    const existing = mergedPointsMap.get(pointKey);
                    const incomingScore = point.awarded ?? 0;
                    const existingScore = existing?.awarded ?? 0;
                    const incomingEvidence = point.evidence || '';
                    const existingEvidence = existing?.evidence || '';

                    if (
                        !existing ||
                        incomingScore > existingScore ||
                        (incomingScore === existingScore && incomingEvidence.length > existingEvidence.length)
                    ) {
                        mergedPointsMap.set(pointKey, point);
                    }
                });
            }
        });

        const mergedPoints = Array.from(mergedPointsMap.values());
        if (hasPointDetails && mergedPoints.length > 0) {
            mergedScore = mergedPoints.reduce((sum, p) => sum + (p.awarded ?? 0), 0);
        } else {
            mergedScore = Math.max(...items.map((item) => item.score || 0));
        }

        const mergedQuestion: QuestionResult = {
            questionId: normalizedId !== 'unknown' ? normalizedId : (items.find(i => i.questionId)?.questionId || 'unknown'),
            score: mergedScore,
            maxScore: mergedMaxScore || Math.max(...items.map((item) => item.maxScore || 0)),
            feedback: mergedFeedback || items[0].feedback,
            questionType: mergedQuestionType || items[0].questionType,
            studentAnswer: mergedStudentAnswer || items[0].studentAnswer,
            confidence: confidenceValues.length > 0 ? Math.min(...confidenceValues) : undefined,
            confidenceReason: mergedConfidenceReasons.size > 0 ? Array.from(mergedConfidenceReasons).join('；') : undefined,
            selfCritique: mergedSelfCritique.size > 0 ? Array.from(mergedSelfCritique).join('；') : undefined,
            selfCritiqueConfidence: selfCritiqueConfidenceValues.length > 0 ? Math.min(...selfCritiqueConfidenceValues) : undefined,
            rubricRefs: mergedRubricRefs.size > 0 ? Array.from(mergedRubricRefs) : undefined,
            typoNotes: mergedTypoNotes.size > 0 ? Array.from(mergedTypoNotes) : undefined,
            pageIndices: Array.from(mergedPageIndices).sort((a, b) => a - b),
            isCrossPage: items.some((item) => item.isCrossPage),
            mergeSource: Array.from(mergedSources),
            scoringPointResults: mergedPoints.length > 0 ? mergedPoints : items[0].scoringPointResults,
            scoringPoints: items[0].scoringPoints
        };

        return mergedQuestion;
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

    // 安全地从 AppContext 获取数据，如果不存在则使用默认值
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
    const scoredResults = sortedResults.filter(
        (r) => !(r.gradingMode || '').startsWith('assist') && r.maxScore > 0
    );
    const scoredCount = scoredResults.length;
    const avgScore = scoredCount > 0
        ? scoredResults.reduce((sum, r) => sum + r.score, 0) / scoredCount
        : 0;
    const highestScore = scoredCount > 0
        ? Math.max(...scoredResults.map((r) => r.score))
        : 0;
    const passCount = scoredResults.filter(r => (r.score / r.maxScore) >= 0.6).length;
    const needsConfirmCount = sortedResults.filter(r => r.needsConfirmation).length;
    const totalCrossPageQuestions = crossPageQuestions.length;
    const hasScores = scoredCount > 0;

    const handleExportCSV = () => {
        const headers = ['排名', '学生', '得分', '满分', '得分率', '等级'];
        const rows = sortedResults.map((r, idx) => {
            const isAssist = (r.gradingMode || '').startsWith('assist') || r.maxScore <= 0;
            const percentage = !isAssist && r.maxScore > 0 ? (r.score / r.maxScore) * 100 : 0;
            let grade = isAssist ? 'Assist' : '待提升';
            if (!isAssist && percentage >= 85) grade = '优秀';
            else if (!isAssist && percentage >= 70) grade = '良好';
            else if (!isAssist && percentage >= 60) grade = '及格';
            else if (!isAssist) grade = '不及格';
            return [
                idx + 1,
                r.studentName,
                isAssist ? 'N/A' : r.score,
                isAssist ? '' : r.maxScore,
                isAssist ? 'N/A' : `${percentage.toFixed(1)}%`,
                grade
            ];
        });

        const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n');
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `批改结果_${new Date().toLocaleDateString()}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

    const handleViewDetail = (student: StudentResult) => {
        const index = sortedResults.findIndex((r) => r.studentName === student.studentName);
        setDetailViewIndex(index >= 0 ? index : 0);
    };

    const handleSelectStudent = (index: number) => {
        setDetailViewIndex(index);
    };

    // === Split View (Detail Mode) ===
    if (detailViewStudent) {
        const isAssist = (detailViewStudent.gradingMode || '').startsWith('assist') || detailViewStudent.maxScore <= 0;
        const percentage = !isAssist && detailViewStudent.maxScore > 0
            ? (detailViewStudent.score / detailViewStudent.maxScore) * 100
            : 0;
        let gradeLabel = isAssist ? 'Assist' : '待提升';
        let gradeColor = isAssist ? 'text-slate-500' : 'text-red-600';
        if (!isAssist && percentage >= 85) { gradeLabel = '优秀'; gradeColor = 'text-emerald-600'; }
        else if (!isAssist && percentage >= 70) { gradeLabel = '良好'; gradeColor = 'text-blue-600'; }
        else if (!isAssist && percentage >= 60) { gradeLabel = '及格'; gradeColor = 'text-yellow-600'; }

        const hasBoundary = detailViewStudent.startPage !== undefined && detailViewStudent.endPage !== undefined;
        const startPage = detailViewStudent.startPage ?? 0;
        const endPage = detailViewStudent.endPage !== undefined ? detailViewStudent.endPage : startPage;
        const totalPages = hasBoundary ? Math.max(0, endPage - startPage + 1) : 0;
        const questionPageIndices = detailViewStudent.questionResults?.flatMap((q) => q.pageIndices || []) || [];
        const uniqueQuestionPages = Array.from(new Set(questionPageIndices))
            .filter((p) => Number.isFinite(p))
            .sort((a, b) => a - b);
        const rangePages = totalPages > 0
            ? Array.from({ length: totalPages }, (_, idx) => startPage + idx)
            : [];
        const pageIndices = Array.from(new Set([...rangePages, ...uniqueQuestionPages]))
            .filter((p) => Number.isFinite(p))
            .sort((a, b) => a - b);
        const studentSummary = detailViewStudent.studentSummary;
        const selfAudit = detailViewStudent.selfAudit;
        const knowledgePoints = studentSummary?.knowledgePoints || [];
        const sortedPoints = [...knowledgePoints].sort((a, b) => (a.ratio ?? 0) - (b.ratio ?? 0));
        const displayPoints = sortedPoints.slice(0, 6);
        const improvementSuggestions = studentSummary?.improvementSuggestions || [];
        const auditIssues = selfAudit?.issues || [];

        return (
            <div className="h-full min-h-0 flex flex-col">
                {/* Header */}
                <div className="neo-panel border-b border-slate-200 px-6 py-3 flex items-center justify-between shrink-0 z-10">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setDetailViewIndex(null)}
                            className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-500"
                        >
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                        <div>
                            <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2 console-display">
                                {detailViewStudent.studentName}
                                <span className={clsx("text-sm px-2 py-0.5 rounded-sm bg-gray-100 font-medium", gradeColor)}>
                                    {gradeLabel}
                                </span>
                            </h2>
                            <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-2">
                                <span>
                                    总分: <b className="text-gray-700">{isAssist ? 'N/A' : detailViewStudent.score}</b>
                                    {isAssist ? '' : `/${detailViewStudent.maxScore}`}
                                </span>
                                <span className="w-1 h-1 bg-gray-300 rounded-full"></span>
                                <span>页面: {startPage + 1} - {endPage + 1}</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            disabled={detailViewIndex === 0}
                            onClick={() => handleSelectStudent(Math.max(0, (detailViewIndex ?? 0) - 1))}
                            className="p-2 rounded-md border border-slate-200 hover:bg-white disabled:opacity-40"
                        >
                            <ChevronDown className="w-4 h-4 rotate-90" />
                        </button>
                        <select
                            value={detailViewIndex ?? 0}
                            onChange={(e) => handleSelectStudent(Number(e.target.value))}
                            className="text-sm font-medium text-gray-700 bg-white/80 border border-slate-200 rounded-md px-3 py-1.5"
                        >
                            {sortedResults.map((student, idx) => (
                                <option key={`${student.studentName}-${idx}`} value={idx}>
                                    {idx + 1}. {student.studentName}
                                </option>
                            ))}
                        </select>
                        <button
                            disabled={detailViewIndex === sortedResults.length - 1}
                            onClick={() => handleSelectStudent(Math.min(sortedResults.length - 1, (detailViewIndex ?? 0) + 1))}
                            className="p-2 rounded-md border border-slate-200 hover:bg-white disabled:opacity-40"
                        >
                            <ChevronDown className="w-4 h-4 -rotate-90" />
                        </button>
                    </div>
                </div>

                {/* Content - Split View */}
                <div className="flex-1 min-h-0 overflow-hidden flex">
                    {/* Left: Image Gallery */}
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto p-5 border-r border-slate-200 custom-scrollbar space-y-4">
                        {pageIndices.length === 0 && (
                            <div className="text-gray-400 flex flex-col items-center justify-center h-full">
                                <FileText className="w-12 h-12 mb-2 opacity-50" />
                                <p>未找到该学生的页面</p>
                            </div>
                        )}
                        {pageIndices.map((pageIndex) => {
                            const imageUrl = uploadedImages[pageIndex] || currentSession?.images[pageIndex]?.url;
                            return (
                                <div key={pageIndex} className="student-page-card">
                                    <div className="student-page-label">第 {pageIndex + 1} 页</div>
                                    {imageUrl ? (
                                        <img
                                            src={imageUrl}
                                            alt={`Page ${pageIndex + 1}`}
                                            className="student-page-image"
                                        />
                                    ) : (
                                        <div className="student-page-missing">
                                            <FileText className="w-6 h-6 opacity-40" />
                                            <span>图像缺失</span>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Right: Results Detail */}
                    <div className="w-1/2 h-full min-h-0 overflow-y-auto bg-white/80 p-6 custom-scrollbar">
                        <div className="max-w-xl mx-auto space-y-6">
                            <div className="flex items-center justify-center py-6 border-b border-slate-200">
                                <div className="text-center">
                                    <div className={clsx(
                                        "text-5xl font-black mb-2 bg-gradient-to-br bg-clip-text text-transparent",
                                        isAssist
                                            ? "from-slate-400 to-slate-600"
                                            : percentage >= 85 ? "from-emerald-400 to-green-600" :
                                                percentage >= 60 ? "from-yellow-400 to-amber-600" :
                                                    "from-red-400 to-rose-600"
                                    )}>
                                        {isAssist ? 'N/A' : detailViewStudent.score}
                                    </div>
                                    <div className="text-sm text-gray-400 font-medium uppercase tracking-wider">Total Score</div>
                                </div>
                            </div>

                            {studentSummary && (
                                <div className="border border-slate-200 rounded-xl p-4 bg-white/90 space-y-3">
                                    <div className="text-xs font-bold text-slate-500 uppercase tracking-[0.3em]">学生总结</div>
                                    <p className="text-sm text-slate-700">{studentSummary.overall}</p>
                                    {displayPoints.length > 0 && (
                                        <div className="space-y-1">
                                            <div className="text-[11px] font-semibold text-slate-500">知识点掌握</div>
                                            <div className="grid gap-2">
                                                {displayPoints.map((point, idx) => (
                                                    <div key={`${point.pointId}-${idx}`} className="flex items-center justify-between text-xs text-slate-600">
                                                        <span className="truncate max-w-[240px]">{point.description || `题目 ${point.questionId}`}</span>
                                                        <span className="text-slate-400">{((point.ratio ?? 0) * 100).toFixed(0)}%</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {improvementSuggestions.length > 0 && (
                                        <div className="space-y-1">
                                            <div className="text-[11px] font-semibold text-slate-500">改进建议</div>
                                            <ul className="text-xs text-slate-600 space-y-1">
                                                {improvementSuggestions.slice(0, 5).map((item, idx) => (
                                                    <li key={`${item}-${idx}`}>{item}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            )}

                            {selfAudit && (
                                <div className="border border-amber-200 rounded-xl p-4 bg-amber-50/60 space-y-3">
                                    <div className="text-xs font-bold text-amber-600 uppercase tracking-[0.3em]">批改自白</div>
                                    <div className="text-sm text-slate-700">
                                        {selfAudit.summary}
                                        {typeof selfAudit.confidence === 'number' && (
                                            <span className="ml-2 text-xs text-amber-600">
                                                置信度 {(selfAudit.confidence * 100).toFixed(0)}%
                                            </span>
                                        )}
                                    </div>
                                    {auditIssues.length > 0 && (
                                        <ul className="text-xs text-amber-700 space-y-1">
                                            {auditIssues.slice(0, 5).map((issue, idx) => (
                                                <li key={`${issue.issueType}-${idx}`}>{issue.message}</li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            )}

                            <div className="space-y-4">
                                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-[0.3em] flex items-center gap-2">
                                    <Layers className="w-4 h-4" />
                                    批改详情
                                </h3>
                                {detailViewStudent.questionResults?.map((q, idx) => (
                                    <div key={idx} className="border border-slate-200 bg-white/80">
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

    // === Grid View (Original) ===
    if (results.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <RocketOutlined className="text-4xl mb-4 opacity-40" />
                <p>暂无批改结果</p>
                <button
                    onClick={() => setCurrentTab('process')}
                    className="mt-4 text-blue-500 hover:underline flex items-center gap-1"
                >
                    <ArrowLeft className="w-4 h-4" />
                    返回批改过程
                </button>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-6 space-y-6 results-shell">
            {showClassReport && (
                <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm flex items-center justify-center">
                    <div className="w-[90vw] max-w-3xl bg-white rounded-2xl shadow-2xl p-6 space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-bold text-slate-900">班级结果总结</h3>
                            <button onClick={() => setShowClassReport(false)} className="p-2 rounded-full hover:bg-slate-100">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        {classReport ? (
                            <div className="space-y-4">
                                <p className="text-sm text-slate-700">{classReport.summary}</p>
                                <div className="grid grid-cols-2 gap-4 text-sm text-slate-600">
                                    <div>平均分: {classReport.averageScore?.toFixed(1)}</div>
                                    <div>平均得分率: {classReport.averagePercentage?.toFixed(1)}%</div>
                                    <div>及格率: {((classReport.passRate ?? 0) * 100).toFixed(1)}%</div>
                                    <div>学生数: {classReport.totalStudents}</div>
                                </div>
                                {classReport.weakPoints && classReport.weakPoints.length > 0 && (
                                    <div>
                                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-[0.3em] mb-2">薄弱知识点</div>
                                        <ul className="text-sm text-slate-600 space-y-1">
                                            {classReport.weakPoints.slice(0, 6).map((point, idx) => (
                                                <li key={`${point.pointId}-${idx}`}>{point.description}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {classReport.strongPoints && classReport.strongPoints.length > 0 && (
                                    <div>
                                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-[0.3em] mb-2">优势知识点</div>
                                        <ul className="text-sm text-slate-600 space-y-1">
                                            {classReport.strongPoints.slice(0, 6).map((point, idx) => (
                                                <li key={`${point.pointId}-${idx}`}>{point.description}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-sm text-slate-400">暂无班级总结数据</div>
                        )}
                    </div>
                </div>
            )}
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3 console-display console-shimmer">
                    <RocketOutlined />
                    批改结果概览
                </h2>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setShowClassReport(true)}
                        className="text-sm text-slate-600 hover:text-indigo-600 flex items-center gap-2 transition-colors bg-white/70 border border-slate-200 hover:border-indigo-200 px-3 py-1.5 rounded-md"
                    >
                        <BarChartOutlined />
                        班级报告
                    </button>
                    <button
                        onClick={handleExportCSV}
                        className="text-sm text-slate-600 hover:text-emerald-600 flex items-center gap-2 transition-colors bg-white/70 border border-slate-200 hover:border-emerald-200 px-3 py-1.5 rounded-md"
                    >
                        <Download className="w-4 h-4" />
                        导出 CSV
                    </button>
                    <button
                        onClick={() => setCurrentTab('process')}
                        className="text-sm text-slate-500 hover:text-blue-600 flex items-center gap-2 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        返回批改过程
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <div className="metric-tile">
                    <UsergroupAddOutlined />
                    <div className="metric-value">{totalStudents}</div>
                    <div className="metric-label">总学生数</div>
                </div>
                <div className="metric-tile">
                    <BarChartOutlined />
                    <div className="metric-value">{hasScores ? avgScore.toFixed(1) : 'N/A'}</div>
                    <div className="metric-label">平均分</div>
                </div>
                <div className="metric-tile">
                    <CrownOutlined />
                    <div className="metric-value">{hasScores ? highestScore : 'N/A'}</div>
                    <div className="metric-label">最高分</div>
                </div>
                <div className="metric-tile">
                    <CheckCircleOutlined />
                    <div className="metric-value">
                        {hasScores ? ((passCount / scoredCount) * 100).toFixed(0) : 'N/A'}{hasScores ? '%' : ''}
                    </div>
                    <div className="metric-label">及格率</div>
                </div>
                {totalCrossPageQuestions > 0 && (
                    <div className="metric-tile">
                        <Layers className="w-5 h-5" />
                        <div className="metric-value">{totalCrossPageQuestions}</div>
                        <div className="metric-label">跨页题目</div>
                    </div>
                )}
                {needsConfirmCount > 0 && (
                    <div className="metric-tile">
                        <ExclamationCircleOutlined />
                        <div className="metric-value">{needsConfirmCount}</div>
                        <div className="metric-label">待确认</div>
                    </div>
                )}
            </div>

            <div className="space-y-6">
                <div className="neo-panel p-0 overflow-hidden results-table overflow-x-auto">
                    <div className="results-table-header">
                        <span>学生</span>
                        <span>得分 / 满分</span>
                        <span>进度</span>
                        <span>状态</span>
                        <span>批改批注</span>
                        <span>交互</span>
                    </div>
                    <div>
                        {sortedResults.map((result, index) => (
                            <div
                                key={`${result.studentName}-${index}`}
                                onClick={() => handleViewDetail(result)}
                                className="cursor-pointer"
                            >
                                <ResultCard
                                    result={result}
                                    rank={index + 1}
                                    isExpanded={false}
                                    onExpand={() => { }}
                                />
                            </div>
                        ))}
                    </div>
                </div>

                {crossPageQuestions.length > 0 && (
                    <div className="neo-panel p-4">
                        <div className="flex items-center gap-2 text-slate-700 font-semibold mb-3">
                            <Layers className="w-4 h-4" />
                            识别到的跨页题目
                        </div>
                        <div className="space-y-2">
                            {crossPageQuestions.map((cpq, idx) => (
                                <div key={idx} className="result-cross-row">
                                    <span className="font-semibold text-slate-700">第 {cpq.questionId} 题</span>
                                    <span className="text-slate-500">
                                        分布在页 {cpq.pageIndices.map(p => p + 1).join(', ')}
                                    </span>
                                    {cpq.confidence < 0.8 && (
                                        <span className="text-amber-600 text-[10px] uppercase tracking-widest">建议复核</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                <RubricOverview />
            </div>
        </div>
    );
};

export default ResultsView;
