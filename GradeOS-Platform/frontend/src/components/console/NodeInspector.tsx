'use client';

import React from 'react';
import { useConsoleStore, WorkflowNode, GradingAgent } from '@/store/consoleStore';
import clsx from 'clsx';
import { X, Activity, CheckCircle, XCircle, Clock, FileText, Users, BookOpen, AlertTriangle, Brain, GitMerge, Shield, Target } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const statusIcons = {
    pending: Clock,
    running: Activity,
    completed: CheckCircle,
    failed: XCircle
};

const statusLabels = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败'
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
        // 自我成长系统状态
        parsedRubric,
        batchProgress,
        studentBoundaries,
        selfEvolving,
    } = useConsoleStore();

    // 获取选中的节点
    const selectedNode = workflowNodes.find(n => n.id === selectedNodeId);

    // 获取选中的 Agent
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

    // 关闭面板
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

    return (
        <AnimatePresence>
            {(selectedNode || selectedAgent) && (
                <motion.div
                    initial={{ opacity: 0, x: 20, scale: 0.95 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, x: 20, scale: 0.95 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    className={clsx(
                        'bg-white/80 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/50',
                        'transition-all duration-300 ease-out flex flex-col',
                        className
                    )}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between p-5 border-b border-gray-100/50">
                        <div className="flex items-center gap-4">
                            <div className={clsx(
                                'p-2.5 rounded-xl shadow-sm bg-white',
                                status === 'running' && 'ring-2 ring-blue-100'
                            )}>
                                <StatusIcon className={clsx(
                                    'w-5 h-5',
                                    status === 'pending' && 'text-gray-400',
                                    status === 'running' && 'text-blue-500 animate-spin',
                                    status === 'completed' && 'text-emerald-500',
                                    status === 'failed' && 'text-red-500'
                                )} />
                            </div>
                            <div>
                                <h3 className="font-bold text-gray-800 text-lg">
                                    {selectedAgent?.label || selectedNode?.label}
                                </h3>
                                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mt-0.5">
                                    {statusLabels[status]}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={handleClose}
                            className="p-2 rounded-lg hover:bg-gray-100/50 text-gray-400 hover:text-gray-600 transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Content */}
                    <div className="p-5 space-y-6 overflow-y-auto custom-scrollbar flex-1">
                        {/* Agent 详情 */}
                        {selectedAgent && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="space-y-6"
                            >
                                {/* 进度 */}
                                {selectedAgent.progress !== undefined && (
                                    <div className="bg-gray-50/50 rounded-xl p-4 border border-gray-100">
                                        <div className="flex justify-between items-end mb-2">
                                            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">处理进度</label>
                                            <span className="text-sm font-bold text-blue-600">{selectedAgent.progress}%</span>
                                        </div>
                                        <div className="w-full bg-gray-200/50 rounded-full h-2 overflow-hidden">
                                            <motion.div
                                                className="bg-blue-500 h-full rounded-full"
                                                initial={{ width: 0 }}
                                                animate={{ width: `${selectedAgent.progress}%` }}
                                                transition={{ type: 'spring', stiffness: 50 }}
                                            />
                                        </div>
                                    </div>
                                )}

                                {/* 输出结果 */}
                                {selectedAgent.output && (
                                    <div className="bg-gradient-to-br from-blue-50/80 to-indigo-50/80 rounded-xl p-5 border border-blue-100/50 shadow-sm">
                                        <label className="text-xs font-semibold text-blue-600/80 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                            <Activity className="w-3.5 h-3.5" />
                                            批改结果
                                        </label>
                                        <div className="flex items-baseline gap-2 mb-3">
                                            <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
                                                {selectedAgent.output.score}
                                            </span>
                                            <span className="text-sm font-medium text-gray-500">
                                                / {selectedAgent.output.maxScore} 分
                                            </span>
                                        </div>
                                        {selectedAgent.output.feedback && (
                                            <p className="text-sm text-gray-600 leading-relaxed bg-white/50 p-3 rounded-lg border border-white/50">
                                                {selectedAgent.output.feedback}
                                            </p>
                                        )}

                                        {/* 自我修正统计 */}
                                        {selectedAgent.output.totalRevisions !== undefined && selectedAgent.output.totalRevisions > 0 && (
                                            <div className="mt-3 flex items-center gap-2 bg-indigo-100/50 px-3 py-2 rounded-lg border border-indigo-100">
                                                <GitMerge className="w-4 h-4 text-indigo-600" />
                                                <span className="text-sm font-medium text-indigo-700">
                                                    触发了 {selectedAgent.output.totalRevisions} 次自我修正（LangGraph Critique）
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* 错误信息 */}
                                {selectedAgent.error && (
                                    <div className="bg-red-50/80 border border-red-100 rounded-xl p-4">
                                        <label className="text-xs font-bold text-red-600 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                                            <AlertTriangle className="w-3.5 h-3.5" />
                                            错误信息
                                        </label>
                                        <div className="space-y-2">
                                            {selectedAgent.error.details?.map((detail, i) => (
                                                <div key={i} className="text-sm text-red-700 bg-red-100/50 rounded px-2 py-1">
                                                    {detail}
                                                </div>
                                            ))}
                                            {selectedAgent.error.message && !selectedAgent.error.details && (
                                                <div className="text-sm text-red-700 break-words">
                                                    {selectedAgent.error.message}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* 判例引用 */}
                                {selfEvolving.recentExemplars.length > 0 && (
                                    <div className="bg-gradient-to-br from-amber-50/80 to-orange-50/80 rounded-xl p-5 border border-amber-100/50 shadow-sm">
                                        <label className="text-xs font-bold text-amber-600 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                            <Brain className="w-3.5 h-3.5" />
                                            参考判例 ({selfEvolving.recentExemplars.length})
                                        </label>
                                        <div className="space-y-2">
                                            {selfEvolving.recentExemplars.map((exemplar, idx) => (
                                                <div key={idx} className="bg-white/60 rounded-lg p-2.5 text-sm border border-amber-100/50">
                                                    <div className="flex justify-between items-center mb-1">
                                                        <span className="font-bold text-gray-700">Similarity: {(exemplar.similarity * 100).toFixed(0)}%</span>
                                                        <span className="text-xs font-medium text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">
                                                            {exemplar.score} 分
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-gray-500 line-clamp-2">{exemplar.description}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* 日志 */}
                                {selectedAgent.logs && selectedAgent.logs.length > 0 && (
                                    <div>
                                        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                                            <FileText className="w-3.5 h-3.5" />
                                            执行日志
                                        </label>
                                        <div className="bg-slate-900 rounded-xl p-4 max-h-[200px] overflow-y-auto custom-scrollbar shadow-inner border border-slate-800">
                                            <div className="space-y-1.5 font-mono text-xs">
                                                {selectedAgent.logs.map((log, i) => (
                                                    <motion.div
                                                        key={i}
                                                        initial={{ opacity: 0, x: -10 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        className={clsx(
                                                            "break-all pl-2 border-l-2",
                                                            log.includes('错误') ? 'text-red-400 border-red-500' : 'text-emerald-400 border-emerald-500'
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
                                    <div className="bg-gray-50/80 rounded-xl p-4 border border-gray-100">
                                        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">当前状态</label>
                                        <p className="text-sm text-gray-700 leading-relaxed">{selectedNode.message}</p>
                                    </div>
                                )}

                                {/* 评分标准解析节点 */}
                                {selectedNode.id === 'rubric_parse' && parsedRubric && (
                                    <div className="bg-gradient-to-br from-purple-50/80 to-indigo-50/80 rounded-xl p-5 border border-purple-100/50 shadow-sm">
                                        <label className="text-xs font-bold text-purple-600 uppercase tracking-wider flex items-center gap-1.5 mb-4">
                                            <BookOpen className="w-3.5 h-3.5" />
                                            评分标准概览
                                        </label>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                                                <div className="text-2xl font-black text-purple-600">{parsedRubric.totalQuestions}</div>
                                                <div className="text-xs font-medium text-purple-400 mt-1">题目数量</div>
                                            </div>
                                            <div className="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                                                <div className="text-2xl font-black text-indigo-600">{parsedRubric.totalScore}</div>
                                                <div className="text-xs font-medium text-indigo-400 mt-1">总分</div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* 学生识别节点 */}
                                {selectedNode.id === 'index' && studentBoundaries.length > 0 && (
                                    <div className="space-y-3">
                                        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
                                            <Users className="w-3.5 h-3.5" />
                                            识别结果 ({studentBoundaries.length})
                                        </label>
                                        <div className="max-h-[240px] overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                            {studentBoundaries.map((boundary, idx) => (
                                                <motion.div
                                                    key={idx}
                                                    initial={{ opacity: 0, x: -10 }}
                                                    animate={{ opacity: 1, x: 0 }}
                                                    transition={{ delay: idx * 0.05 }}
                                                    className={clsx(
                                                        'p-3 rounded-xl border text-sm transition-all hover:scale-[1.02]',
                                                        boundary.needsConfirmation
                                                            ? 'bg-yellow-50/80 border-yellow-200 shadow-sm'
                                                            : 'bg-emerald-50/50 border-emerald-100'
                                                    )}
                                                >
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="font-bold text-gray-800">{boundary.studentKey}</span>
                                                        {boundary.needsConfirmation && (
                                                            <AlertTriangle className="w-4 h-4 text-yellow-500 animate-pulse" />
                                                        )}
                                                    </div>
                                                    <div className="flex justify-between items-center text-xs text-gray-500">
                                                        <span>Page {boundary.startPage + 1} - {boundary.endPage + 1}</span>
                                                        <span className={clsx(
                                                            "font-medium px-1.5 py-0.5 rounded",
                                                            boundary.confidence > 0.8 ? "bg-emerald-100 text-emerald-700" : "bg-yellow-100 text-yellow-700"
                                                        )}>
                                                            {(boundary.confidence * 100).toFixed(0)}% Conf.
                                                        </span>
                                                    </div>
                                                </motion.div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* 批次进度信息 */}
                                {batchProgress && selectedNode.id === 'grading' && (
                                    <div className="bg-gradient-to-br from-blue-50/80 to-cyan-50/80 rounded-xl p-5 border border-blue-100/50 shadow-sm">
                                        <label className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-3 block">批次处理进度</label>
                                        <div className="flex justify-between items-end mb-2">
                                            <span className="text-2xl font-black text-blue-600">
                                                Batch {batchProgress.batchIndex + 1}
                                            </span>
                                            <span className="text-sm font-medium text-blue-400 mb-1">
                                                / {batchProgress.totalBatches}
                                            </span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 mt-4">
                                            <div className="bg-emerald-100/50 rounded-lg p-2 text-center border border-emerald-100">
                                                <div className="text-lg font-bold text-emerald-600">{batchProgress.successCount}</div>
                                                <div className="text-[10px] text-emerald-500 uppercase tracking-wider">成功</div>
                                            </div>
                                            <div className="bg-red-100/50 rounded-lg p-2 text-center border border-red-100">
                                                <div className="text-lg font-bold text-red-600">{batchProgress.failureCount}</div>
                                                <div className="text-[10px] text-red-500 uppercase tracking-wider">失败</div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* 自我成长系统状态 */}
                                {selectedNode.id === 'grading' && (
                                    <div className="space-y-4">
                                        {/* 校准配置 */}
                                        {selfEvolving.calibration && (
                                            <div className="bg-gradient-to-br from-indigo-50/80 to-violet-50/80 rounded-xl p-5 border border-indigo-100/50 shadow-sm">
                                                <label className="text-xs font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                                    <Target className="w-3.5 h-3.5" />
                                                    教师校准配置
                                                </label>
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="text-sm font-medium text-gray-600">Profile ID</span>
                                                    <span className="text-sm font-bold text-indigo-700">{selfEvolving.calibration.profileId}</span>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span className="text-sm font-medium text-gray-600">严格度</span>
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-20 bg-gray-200 rounded-full h-1.5 overflow-hidden">
                                                            <div
                                                                className="bg-indigo-500 h-full rounded-full"
                                                                style={{ width: `${(selfEvolving.calibration.strictnessLevel / 2) * 100}%` }}
                                                            />
                                                        </div>
                                                        <span className="text-xs font-bold text-indigo-600">{selfEvolving.calibration.strictnessLevel.toFixed(1)}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        {/* 规则补丁状态 */}
                                        {selfEvolving.activePatches.length > 0 && (
                                            <div className="bg-gradient-to-br from-emerald-50/80 to-teal-50/80 rounded-xl p-5 border border-emerald-100/50 shadow-sm">
                                                <label className="text-xs font-bold text-emerald-600 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                                                    <Shield className="w-3.5 h-3.5" />
                                                    活跃规则补丁 ({selfEvolving.activePatches.length})
                                                </label>
                                                <div className="space-y-2">
                                                    {selfEvolving.activePatches.map((patch, idx) => (
                                                        <div key={idx} className="bg-white/60 rounded-lg p-2.5 text-sm border border-emerald-100/50">
                                                            <div className="flex justify-between items-center mb-1">
                                                                <span className="font-bold text-gray-700">{patch.patchId}</span>
                                                                <span className={clsx(
                                                                    "text-[10px] px-1.5 py-0.5 rounded font-medium uppercase",
                                                                    patch.status === 'testing' ? "bg-yellow-100 text-yellow-700" : "bg-emerald-100 text-emerald-700"
                                                                )}>
                                                                    {patch.status}
                                                                </span>
                                                            </div>
                                                            <div className="text-xs text-gray-500 truncate">{patch.description}</div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* 并行容器统计 */}
                                {selectedNode.isParallelContainer && selectedNode.children && (
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="bg-blue-50/50 rounded-xl p-4 text-center border border-blue-100 hover:bg-blue-50 transition-colors">
                                            <div className="text-3xl font-black text-blue-600">
                                                {selectedNode.children.length}
                                            </div>
                                            <div className="text-xs font-medium text-blue-400 mt-1 uppercase tracking-wider">总任务数</div>
                                        </div>
                                        <div className="bg-emerald-50/50 rounded-xl p-4 text-center border border-emerald-100 hover:bg-emerald-50 transition-colors">
                                            <div className="text-3xl font-black text-emerald-600">
                                                {selectedNode.children.filter(c => c.status === 'completed').length}
                                            </div>
                                            <div className="text-xs font-medium text-emerald-400 mt-1 uppercase tracking-wider">已完成</div>
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </div>
                </motion.div >
            )}
        </AnimatePresence >
    );
};

export default NodeInspector;
