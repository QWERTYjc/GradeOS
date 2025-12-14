'use client';

import React from 'react';
import { useConsoleStore, WorkflowNode, GradingAgent } from '@/store/consoleStore';
import clsx from 'clsx';
import { X, Activity, CheckCircle, XCircle, Clock, FileText } from 'lucide-react';

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
        setSelectedAgentId
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

    // 如果没有选中任何内容，不显示面板
    if (!selectedNode && !selectedAgent) {
        return null;
    }

    const StatusIcon = selectedAgent
        ? statusIcons[selectedAgent.status]
        : selectedNode
            ? statusIcons[selectedNode.status]
            : Clock;

    const status = selectedAgent?.status || selectedNode?.status || 'pending';

    return (
        <div className={clsx(
            'bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-gray-200',
            'transition-all duration-300 ease-out',
            className
        )}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-100">
                <div className="flex items-center gap-3">
                    <StatusIcon className={clsx(
                        'w-5 h-5',
                        status === 'pending' && 'text-gray-400',
                        status === 'running' && 'text-blue-500 animate-spin',
                        status === 'completed' && 'text-green-500',
                        status === 'failed' && 'text-red-500'
                    )} />
                    <div>
                        <h3 className="font-semibold text-gray-800">
                            {selectedAgent?.label || selectedNode?.label}
                        </h3>
                        <p className="text-xs text-gray-500">
                            {statusLabels[status]}
                        </p>
                    </div>
                </div>
                <button
                    onClick={handleClose}
                    className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                >
                    <X className="w-4 h-4 text-gray-500" />
                </button>
            </div>

            {/* Content */}
            <div className="p-4 space-y-4 max-h-[400px] overflow-y-auto">
                {/* Agent 详情 */}
                {selectedAgent && (
                    <>
                        {/* 进度 */}
                        {selectedAgent.progress !== undefined && (
                            <div>
                                <label className="text-xs text-gray-500 uppercase tracking-wide">进度</label>
                                <div className="mt-1 flex items-center gap-2">
                                    <div className="flex-1 bg-gray-200 rounded-full h-2">
                                        <div
                                            className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                                            style={{ width: `${selectedAgent.progress}%` }}
                                        />
                                    </div>
                                    <span className="text-sm font-medium text-gray-700">
                                        {selectedAgent.progress}%
                                    </span>
                                </div>
                            </div>
                        )}

                        {/* 输出结果 */}
                        {selectedAgent.output && (
                            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4">
                                <label className="text-xs text-gray-500 uppercase tracking-wide">批改结果</label>
                                <div className="mt-2 flex items-baseline gap-2">
                                    <span className="text-3xl font-bold text-blue-600">
                                        {selectedAgent.output.score}
                                    </span>
                                    <span className="text-gray-500">
                                        / {selectedAgent.output.maxScore}
                                    </span>
                                </div>
                                {selectedAgent.output.feedback && (
                                    <p className="mt-2 text-sm text-gray-600">
                                        {selectedAgent.output.feedback}
                                    </p>
                                )}
                            </div>
                        )}

                        {/* 日志 */}
                        {selectedAgent.logs && selectedAgent.logs.length > 0 && (
                            <div>
                                <label className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
                                    <FileText className="w-3 h-3" />
                                    执行日志
                                </label>
                                <div className="mt-2 bg-gray-900 rounded-lg p-3 max-h-[150px] overflow-y-auto">
                                    {selectedAgent.logs.map((log, i) => (
                                        <div key={i} className="text-xs text-green-400 font-mono">
                                            {log}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Node 详情 */}
                {selectedNode && !selectedAgent && (
                    <>
                        {selectedNode.message && (
                            <div>
                                <label className="text-xs text-gray-500 uppercase tracking-wide">状态信息</label>
                                <p className="mt-1 text-sm text-gray-700">{selectedNode.message}</p>
                            </div>
                        )}

                        {/* 如果是并行容器，显示子 Agent 统计 */}
                        {selectedNode.isParallelContainer && selectedNode.children && (
                            <div className="grid grid-cols-2 gap-3">
                                <div className="bg-blue-50 rounded-lg p-3 text-center">
                                    <div className="text-2xl font-bold text-blue-600">
                                        {selectedNode.children.length}
                                    </div>
                                    <div className="text-xs text-gray-500">总计 Agent</div>
                                </div>
                                <div className="bg-green-50 rounded-lg p-3 text-center">
                                    <div className="text-2xl font-bold text-green-600">
                                        {selectedNode.children.filter(c => c.status === 'completed').length}
                                    </div>
                                    <div className="text-xs text-gray-500">已完成</div>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default NodeInspector;
