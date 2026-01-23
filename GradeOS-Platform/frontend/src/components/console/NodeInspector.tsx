'use client';

import React from 'react';
import { useConsoleStore, GradingAgent, WorkflowNode } from '@/store/consoleStore';
import clsx from 'clsx';
import { X, Activity, CheckCircle2, XCircle, Clock, FileText, Users, BookOpen, AlertTriangle, GitMerge, Shield, Target, Sparkles, BrainCircuit } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassCard } from '@/components/design-system/GlassCard';

const statusIcons = {
    pending: Clock,
    running: Activity,
    completed: CheckCircle2,
    failed: XCircle
};

const statusLabels = {
    pending: 'Pending',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed'
};

const statusColors = {
    pending: 'text-slate-400 bg-slate-100/50 border-slate-200',
    running: 'text-blue-500 bg-blue-50/50 border-blue-200',
    completed: 'text-emerald-500 bg-emerald-50/50 border-emerald-200',
    failed: 'text-red-500 bg-red-50/50 border-red-200'
};

interface NodeInspectorProps {
    className?: string;
}

export const NodeInspector: React.FC<NodeInspectorProps> = ({ className }) => {
    const {
        workflowNodes,
        selectedNodeId,
        selectedAgentId,
        setSelectedNodeId,
        setSelectedAgentId,
        parsedRubric,
        batchProgress,
        studentBoundaries,
    } = useConsoleStore();

    // 
    const selectedNode = workflowNodes.find(n => n.id === selectedNodeId);

    // 
    let selectedAgent: GradingAgent | undefined;
    if (selectedAgentId) {
        for (const node of workflowNodes) {
            if (node.children) {
                const agent = node.children.find(a => a.id === selectedAgentId);
                if (agent) {
                    selectedAgent = agent;
                    break;
                }
            }
        }
    }

    // 
    const handleClose = () => {
        setSelectedNodeId(null);
        setSelectedAgentId(null);
    };

    const StatusIcon = selectedAgent
        ? statusIcons[selectedAgent.status]
        : selectedNode
            ? statusIcons[selectedNode.status]
            : Clock;

    const status = selectedAgent?.status || selectedNode?.status || 'pending';
    const statusStyle = statusColors[status];

    return (
        <AnimatePresence>
            {(selectedNode || selectedAgent) && (
                <motion.div
                    initial={{ opacity: 0, x: 40, scale: 0.95 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, x: 40, scale: 0.95 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 28 }}
                    className={clsx(
                        'flex flex-col h-full',
                        className
                    )}
                >
                    <GlassCard
                        className="h-full flex flex-col !p-0 overflow-hidden !bg-white/80 ring-1 ring-white/60 shadow-2xl"
                        hoverEffect={false}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between p-5 border-b border-slate-100/60 bg-white/40 backdrop-blur-md sticky top-0 z-10">
                            <div className="flex items-center gap-4">
                                <motion.div
                                    initial={{ scale: 0.8, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    className={clsx(
                                        'p-2.5 rounded-xl shadow-sm ring-1 ring-inset',
                                        statusStyle
                                    )}
                                >
                                    <StatusIcon className={clsx(
                                        'w-5 h-5',
                                        status === 'running' && 'animate-spin-slow'
                                    )} />
                                </motion.div>
                                <div>
                                    <motion.h3
                                        layoutId="inspector-title"
                                        className="font-bold text-slate-800 text-lg tracking-tight"
                                    >
                                        {selectedAgent?.label || selectedNode?.label}
                                    </motion.h3>
                                    <div className="flex items-center gap-2 mt-1">
                                        <span className={clsx(
                                            "text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider",
                                            status === 'running' ? 'bg-blue-100 text-blue-600' :
                                                status === 'completed' ? 'bg-emerald-100 text-emerald-600' :
                                                    status === 'failed' ? 'bg-red-100 text-red-600' :
                                                        'bg-slate-100 text-slate-500'
                                        )}>
                                            {statusLabels[status]}
                                        </span>
                                        {selectedAgent && (
                                            <span className="text-[10px] bg-indigo-50 text-indigo-500 px-2 py-0.5 rounded-full font-medium border border-indigo-100">
                                                Agent
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={handleClose}
                                className="p-2 rounded-full hover:bg-slate-100/50 text-slate-400 hover:text-slate-600 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="p-5 space-y-6 overflow-y-auto custom-scrollbar flex-1 bg-gradient-to-b from-transparent to-slate-50/30">
                            {/* Agent 详情 */}
                            {selectedAgent && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="space-y-6"
                                >
                                    {/* 进度 */}
                                    {selectedAgent.progress !== undefined && (
                                        <div className="bg-white/50 rounded-2xl p-4 border border-slate-100 shadow-sm">
                                            <div className="flex justify-between items-end mb-2">
                                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                                                    <Activity className="w-3 h-3" /> 处理进度
                                                </label>
                                                <span className="text-sm font-bold text-blue-600">{selectedAgent.progress}%</span>
                                            </div>
                                            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                                                <motion.div
                                                    className="bg-gradient-to-r from-blue-400 to-indigo-500 h-full rounded-full"
                                                    initial={{ width: 0 }}
                                                    animate={{ width: `${selectedAgent.progress}%` }}
                                                    transition={{ type: 'spring', stiffness: 50 }}
                                                />
                                            </div>
                                        </div>
                                    )}

                                    {/* 输出结果 */}
                                    {selectedAgent.output && (
                                        <div className="bg-gradient-to-br from-white via-blue-50/20 to-indigo-50/20 rounded-2xl p-1 border border-blue-100/50 shadow-sm relative overflow-hidden">
                                            <div className="absolute top-0 right-0 p-3 opacity-10">
                                                <Target className="w-24 h-24 text-blue-500" />
                                            </div>
                                            <div className="bg-white/40 backdrop-blur-sm rounded-xl p-5">
                                                <label className="text-xs font-bold text-blue-600 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                                    <Sparkles className="w-3.5 h-3.5 fill-blue-600/20" />
                                                    批改结果
                                                </label>
                                                <div className="flex items-baseline gap-2 mb-4">
                                                    <span className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 tracking-tight">
                                                        {selectedAgent.output.score}
                                                    </span>
                                                    <span className="text-sm font-semibold text-slate-400">
                                                        / {selectedAgent.output.maxScore} 分
                                                    </span>
                                                </div>

                                                {selectedAgent.status === 'running' && selectedAgent.output.streamingText && (
                                                    <div className="mt-4">
                                                        <label className="text-[10px] font-bold text-blue-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                                                            <BrainCircuit className="w-3 h-3" />
                                                            实时 AI 思考内容...
                                                        </label>
                                                        <div className="text-sm text-slate-600 leading-relaxed bg-white/70 p-4 rounded-xl border border-blue-100/40 font-mono text-[13px] max-h-[200px] overflow-y-auto custom-scrollbar shadow-inner">
                                                            {selectedAgent.output.streamingText}
                                                            <span className="inline-block w-1.5 h-4 bg-blue-500 ml-1 animate-pulse align-middle" />
                                                        </div>
                                                    </div>
                                                )}

                                                {selectedAgent.output.feedback && (
                                                    <div className="mt-4 p-4 bg-white/60 rounded-xl border border-slate-100/80">
                                                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 block">综合评分反馈</label>
                                                        <p className="text-sm text-slate-700 leading-relaxed">
                                                            {selectedAgent.output.feedback}
                                                        </p>
                                                    </div>
                                                )}

                                                {/* 题目得分详情 */}
                                                {selectedAgent.output.questionResults && selectedAgent.output.questionResults.length > 0 && (
                                                    <div className="mt-5 space-y-3">
                                                        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider pl-1">题目明细</div>
                                                        <div className="grid grid-cols-1 gap-2">
                                                            {selectedAgent.output.questionResults.map((q, idx) => (
                                                                <div key={idx} className="bg-white/80 hover:bg-white rounded-lg p-3 border border-slate-100 hover:border-blue-200 transition-all shadow-sm flex items-center justify-between group">
                                                                    <div className="flex items-center gap-3">
                                                                        <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 ring-1 ring-blue-100 px-2 py-1 rounded-md min-w-[3rem] text-center">
                                                                            {q.questionId}
                                                                        </span>
                                                                    </div>
                                                                    <div className="flex items-baseline gap-1.5">
                                                                        <span className={clsx(
                                                                            "font-bold text-base",
                                                                            q.score === q.maxScore ? "text-emerald-600" :
                                                                                q.score === 0 ? "text-red-500" : "text-amber-500"
                                                                        )}>
                                                                            {q.score}
                                                                        </span>
                                                                        <span className="text-xs text-slate-300">/ {q.maxScore}</span>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* 自我修正统计 */}
                                                {selectedAgent.output.totalRevisions !== undefined && selectedAgent.output.totalRevisions > 0 && (
                                                    <div className="mt-4 flex items-center gap-2.5 bg-violet-50/50 px-3 py-2.5 rounded-lg border border-violet-100 text-violet-700">
                                                        <GitMerge className="w-4 h-4" />
                                                        <span className="text-xs font-medium">
                                                            触发了 <strong className="text-violet-800">{selectedAgent.output.totalRevisions}</strong> 次自我修正（LangGraph Critique）
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {(selectedAgent.output?.reviewSummary || selectedAgent.output?.selfAudit) && (
                                        <div className="bg-amber-50/50 border border-amber-100/80 rounded-2xl p-5 relative overflow-hidden">
                                            <div className="absolute -right-6 -top-6 text-amber-500/10">
                                                <Shield className="w-24 h-24" />
                                            </div>
                                            <label className="text-xs font-bold text-amber-600/90 uppercase tracking-wider flex items-center gap-1.5 mb-4 relative z-10">
                                                <Shield className="w-3.5 h-3.5" />
                                                逻辑复核
                                            </label>
                                            {selectedAgent.output?.reviewSummary && (
                                                <div className="grid grid-cols-3 gap-3 text-center mb-4 relative z-10">
                                                    <div className="bg-white/80 rounded-xl p-2.5 border border-amber-100 shadow-sm">
                                                        <div className="text-lg font-black text-amber-600">
                                                            {selectedAgent.output.reviewSummary.totalQuestions ?? '-'}
                                                        </div>
                                                        <div className="text-[10px] text-amber-400 font-bold uppercase tracking-wider mt-0.5">题目数</div>
                                                    </div>
                                                    <div className="bg-white/80 rounded-xl p-2.5 border border-amber-100 shadow-sm">
                                                        <div className="text-lg font-black text-amber-600">
                                                            {selectedAgent.output.reviewSummary.averageConfidence !== undefined
                                                                ? `${Math.round(selectedAgent.output.reviewSummary.averageConfidence * 100)}%`
                                                                : '-'}
                                                        </div>
                                                        <div className="text-[10px] text-amber-400 font-bold uppercase tracking-wider mt-0.5">平均置信度</div>
                                                    </div>
                                                    <div className="bg-white/80 rounded-xl p-2.5 border border-amber-100 shadow-sm">
                                                        <div className="text-lg font-black text-amber-600">
                                                            {selectedAgent.output.reviewSummary.lowConfidenceCount ?? 0}
                                                        </div>
                                                        <div className="text-[10px] text-amber-400 font-bold uppercase tracking-wider mt-0.5">低置信题</div>
                                                    </div>
                                                </div>
                                            )}
                                            {selectedAgent.output?.selfAudit && (
                                                <div className="space-y-3 relative z-10">
                                                    {((selectedAgent.output.selfAudit.overallComplianceGrade ?? (selectedAgent.output.selfAudit as any).overall_compliance_grade) !== undefined) && (
                                                        <div className="text-[11px] font-semibold text-amber-700 bg-amber-100/50 rounded-lg px-3 py-2 border border-amber-200/40">
                                                            合规评分：{Math.round(selectedAgent.output.selfAudit.overallComplianceGrade ?? (selectedAgent.output.selfAudit as any).overall_compliance_grade)} / 7
                                                        </div>
                                                    )}
                                                    {selectedAgent.output.selfAudit.summary && (
                                                        <p className="text-xs text-amber-800/80 leading-relaxed bg-amber-100/40 p-3 rounded-xl border border-amber-200/40">
                                                            {selectedAgent.output.selfAudit.summary}
                                                        </p>
                                                    )}
                                                    {(selectedAgent.output.selfAudit.uncertaintiesAndConflicts || (selectedAgent.output.selfAudit as any).uncertainties_and_conflicts) && (
                                                        <div className="space-y-1.5">
                                                            {(selectedAgent.output.selfAudit.uncertaintiesAndConflicts || (selectedAgent.output.selfAudit as any).uncertainties_and_conflicts || []).slice(0, 3).map((issue: any, idx: number) => (
                                                                <div key={`conflict-${idx}`} className="bg-white/60 border border-amber-100 rounded-lg px-3 py-2 text-xs text-amber-700 flex items-start gap-2">
                                                                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0 opacity-70" />
                                                                    <span>{issue.issue || issue.impact || '存在未披露的不确定性'}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {selectedAgent.output.selfAudit.issues && selectedAgent.output.selfAudit.issues.length > 0 && (
                                                        <div className="space-y-1.5">
                                                            {selectedAgent.output.selfAudit.issues.map((issue, idx) => (
                                                                <div key={idx} className="bg-white/60 border border-amber-100 rounded-lg px-3 py-2 text-xs text-amber-700 flex items-start gap-2">
                                                                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0 opacity-70" />
                                                                    <span>{issue.message || issue.issueType || (issue as any).issue_type}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* 错误信息 */}
                                    {selectedAgent.error && (
                                        <div className="bg-red-50/60 border border-red-100 rounded-2xl p-5">
                                            <label className="text-xs font-bold text-red-600 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                                <AlertTriangle className="w-3.5 h-3.5" />
                                                错误信息
                                            </label>
                                            <div className="space-y-2">
                                                {selectedAgent.error.details?.map((detail, i) => (
                                                    <div key={i} className="text-xs font-medium text-red-700 bg-red-100/50 rounded-lg px-3 py-2">
                                                        {detail}
                                                    </div>
                                                ))}
                                                {selectedAgent.error.message && !selectedAgent.error.details && (
                                                    <div className="text-sm text-red-700 break-words bg-red-100/30 p-3 rounded-lg">
                                                        {selectedAgent.error.message}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}


                                    {/* 日志 */}
                                    {selectedAgent.logs && selectedAgent.logs.length > 0 && (
                                        <div>
                                            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                                <FileText className="w-3.5 h-3.5" />
                                                执行日志
                                            </label>
                                            <div className="bg-slate-900 rounded-2xl p-4 max-h-[240px] overflow-y-auto custom-scrollbar shadow-inner border border-slate-800 ring-1 ring-white/10">
                                                <div className="space-y-2 font-mono text-[11px] leading-relaxed">
                                                    {selectedAgent.logs.map((log, i) => (
                                                        <motion.div
                                                            key={i}
                                                            initial={{ opacity: 0, x: -10 }}
                                                            animate={{ opacity: 1, x: 0 }}
                                                            className={clsx(
                                                                "break-all pl-3 border-l-2 py-0.5",
                                                                log.includes('错误') ? 'text-red-400 border-red-500 bg-red-500/10 rounded-r' : 'text-emerald-400/90 border-emerald-500/50 hover:bg-slate-800/50 rounded-r'
                                                            )}
                                                        >
                                                            {log}
                                                        </motion.div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </motion.div>
                            )}

                            {/* Node 详情 */}
                            {selectedNode && !selectedAgent && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="space-y-6"
                                >
                                    {selectedNode.message && (
                                        <div className="bg-slate-50/80 rounded-2xl p-5 border border-slate-200/60 shadow-sm">
                                            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">当前状态</label>
                                            <p className="text-sm text-slate-600 leading-relaxed font-medium">{selectedNode.message}</p>
                                        </div>
                                    )}

                                    {/* 评分标准解析节点 */}
                                    {selectedNode.id === 'rubric_parse' && parsedRubric && (
                                        <div className="bg-gradient-to-br from-purple-50/50 via-purple-50/30 to-indigo-50/30 rounded-2xl p-5 border border-purple-100/80 shadow-sm">
                                            <label className="text-xs font-bold text-purple-600 uppercase tracking-wider flex items-center gap-1.5 mb-5">
                                                <BookOpen className="w-3.5 h-3.5" />
                                                评分标准概览
                                            </label>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="bg-white/70 rounded-xl p-4 text-center shadow-sm ring-1 ring-purple-100/50">
                                                    <div className="text-3xl font-black text-purple-600 tracking-tight">{parsedRubric.totalQuestions}</div>
                                                    <div className="text-[10px] font-bold text-purple-400 uppercase tracking-wider mt-1">题目数量</div>
                                                </div>
                                                <div className="bg-white/70 rounded-xl p-4 text-center shadow-sm ring-1 ring-indigo-100/50">
                                                    <div className="text-3xl font-black text-indigo-600 tracking-tight">{parsedRubric.totalScore}</div>
                                                    <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider mt-1">总分</div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* 学生识别节点 */}
                                    {selectedNode.id === 'index' && studentBoundaries.length > 0 && (
                                        <div className="space-y-3">
                                            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 pl-1">
                                                <Users className="w-3.5 h-3.5" />
                                                识别结果 ({studentBoundaries.length})
                                            </label>
                                            <div className="max-h-[300px] overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                                {studentBoundaries.map((boundary, idx) => (
                                                    <motion.div
                                                        key={idx}
                                                        initial={{ opacity: 0, x: -10 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        transition={{ delay: idx * 0.03 }}
                                                        className={clsx(
                                                            'p-3.5 rounded-xl border text-sm transition-all hover:scale-[1.01]',
                                                            boundary.needsConfirmation
                                                                ? 'bg-amber-50/80 border-amber-200 shadow-sm'
                                                                : 'bg-white/80 border-slate-100 hover:border-blue-200 hover:shadow-sm'
                                                        )}
                                                    >
                                                        <div className="flex items-center justify-between mb-1.5">
                                                            <span className="font-bold text-slate-700">{boundary.studentKey}</span>
                                                            {boundary.needsConfirmation && (
                                                                <div className="flex items-center gap-1 text-[10px] uppercase font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">
                                                                    <AlertTriangle className="w-3 h-3" />
                                                                    Review Needed
                                                                </div>
                                                            )}
                                                        </div>
                                                        <div className="flex justify-between items-center text-xs text-slate-500">
                                                            <span className="font-medium bg-slate-100 px-2 py-0.5 rounded-md text-slate-600">
                                                                Page {boundary.startPage + 1} - {boundary.endPage + 1}
                                                            </span>
                                                            <span className={clsx(
                                                                "font-bold px-1.5 py-0.5 rounded-md",
                                                                boundary.confidence > 0.8 ? "text-emerald-600 bg-emerald-50" : "text-amber-600 bg-amber-50"
                                                            )}>
                                                                {(boundary.confidence * 100).toFixed(0)}% Conf.
                                                            </span>
                                                        </div>
                                                    </motion.div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* 处理进度信息 */}
                                    {batchProgress && selectedNode.id === 'grade_batch' && (
                                        <div className="bg-gradient-to-br from-blue-50/60 to-cyan-50/60 rounded-2xl p-5 border border-blue-100/50 shadow-sm relative overflow-hidden">
                                            <div className="absolute top-0 right-0 p-3 opacity-5">
                                                <Activity className="w-32 h-32 text-blue-500" />
                                            </div>
                                            <label className="text-xs font-bold text-blue-600/80 uppercase tracking-wider mb-4 block relative z-10">处理进度</label>
                                            <div className="flex justify-between items-end mb-3 relative z-10">
                                                <div className="flex flex-col">
                                                    <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-600 tracking-tight">
                                                        Run {batchProgress.batchIndex + 1}
                                                    </span>
                                                    <span className="text-xs font-bold text-blue-400 mt-1 uppercase tracking-wider">Current Run</span>
                                                </div>

                                                <div className="flex flex-col items-end">
                                                    <span className="text-2xl font-bold text-slate-400 mb-1">
                                                        / {batchProgress.totalBatches}
                                                    </span>
                                                    <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">Total</span>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-3 mt-5 relative z-10">
                                                <div className="bg-emerald-50/80 rounded-xl p-3 text-center border border-emerald-100/50">
                                                    <div className="text-2xl font-black text-emerald-600">{batchProgress.successCount}</div>
                                                    <div className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider mt-1">成功</div>
                                                </div>
                                                <div className="bg-red-50/80 rounded-xl p-3 text-center border border-red-100/50">
                                                    <div className="text-2xl font-black text-red-600">{batchProgress.failureCount}</div>
                                                    <div className="text-[10px] font-bold text-red-500 uppercase tracking-wider mt-1">失败</div>
                                                </div>
                                            </div>
                                        </div>
                                    )}



                                    {/* 并行容器统计 */}
                                    {selectedNode.isParallelContainer && selectedNode.children && (
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="bg-blue-50/40 rounded-2xl p-5 text-center border border-blue-100 hover:bg-blue-50/60 transition-colors group">
                                                <div className="text-4xl font-black text-blue-600 group-hover:scale-110 transition-transform duration-300">
                                                    {selectedNode.children.length}
                                                </div>
                                                <div className="text-xs font-bold text-blue-400 mt-2 uppercase tracking-wider">总任务数</div>
                                            </div>
                                            <div className="bg-emerald-50/40 rounded-2xl p-5 text-center border border-emerald-100 hover:bg-emerald-50/60 transition-colors group">
                                                <div className="text-4xl font-black text-emerald-600 group-hover:scale-110 transition-transform duration-300">
                                                    {selectedNode.children.filter(c => c.status === 'completed').length}
                                                </div>
                                                <div className="text-xs font-bold text-emerald-400 mt-2 uppercase tracking-wider">已完成</div>
                                            </div>
                                        </div>
                                    )}
                                </motion.div>
                            )}
                        </div>
                    </GlassCard>
                </motion.div >
            )}
        </AnimatePresence >
    );
};

export default NodeInspector;
