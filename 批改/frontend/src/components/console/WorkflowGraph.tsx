'use client';

import React, { useMemo, useState } from 'react';
import { useConsoleStore, WorkflowNode, GradingAgent } from '@/store/consoleStore';
import clsx from 'clsx';

// 状态颜色映射
const statusColors = {
    pending: {
        bg: 'bg-gray-100',
        border: 'border-gray-300',
        text: 'text-gray-500',
        dot: 'bg-gray-400'
    },
    running: {
        bg: 'bg-blue-50',
        border: 'border-blue-400',
        text: 'text-blue-700',
        dot: 'bg-blue-500 animate-pulse'
    },
    completed: {
        bg: 'bg-green-50',
        border: 'border-green-400',
        text: 'text-green-700',
        dot: 'bg-green-500'
    },
    failed: {
        bg: 'bg-red-50',
        border: 'border-red-400',
        text: 'text-red-700',
        dot: 'bg-red-500'
    }
};

interface AgentCardProps {
    agent: GradingAgent;
    onClick: () => void;
    isSelected: boolean;
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, onClick, isSelected }) => {
    const colors = statusColors[agent.status];

    return (
        <div
            onClick={onClick}
            className={clsx(
                'p-3 rounded-lg border-2 cursor-pointer transition-all duration-200',
                'hover:shadow-md hover:scale-[1.02]',
                colors.bg, colors.border,
                isSelected && 'ring-2 ring-blue-500 ring-offset-2'
            )}
        >
            <div className="flex items-center justify-between mb-2">
                <span className={clsx('font-medium text-sm', colors.text)}>
                    {agent.label}
                </span>
                <div className={clsx('w-2 h-2 rounded-full', colors.dot)} />
            </div>

            {agent.progress !== undefined && agent.status === 'running' && (
                <div className="w-full bg-gray-200 rounded-full h-1.5 mb-2">
                    <div
                        className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${agent.progress}%` }}
                    />
                </div>
            )}

            {agent.output && (
                <div className="text-xs text-gray-600">
                    得分: <span className="font-semibold">{agent.output.score}</span>/{agent.output.maxScore}
                </div>
            )}
        </div>
    );
};

interface ParallelContainerProps {
    node: WorkflowNode;
    onAgentClick: (agentId: string) => void;
    selectedAgentId: string | null;
}

const ParallelContainer: React.FC<ParallelContainerProps> = ({
    node,
    onAgentClick,
    selectedAgentId
}) => {
    const colors = statusColors[node.status];
    const agents = node.children || [];

    return (
        <div className={clsx(
            'rounded-xl border-2 p-4 transition-all duration-300',
            colors.bg, colors.border,
            'min-w-[200px]'
        )}>
            <div className="flex items-center gap-2 mb-3">
                <div className={clsx('w-3 h-3 rounded-full', colors.dot)} />
                <span className={clsx('font-semibold', colors.text)}>{node.label}</span>
                {agents.length > 0 && (
                    <span className="text-xs text-gray-500 ml-auto">
                        {agents.filter(a => a.status === 'completed').length}/{agents.length}
                    </span>
                )}
            </div>

            {agents.length === 0 ? (
                <div className="text-sm text-gray-400 italic">
                    等待学生识别...
                </div>
            ) : (
                <div className="max-h-[240px] overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-gray-300">
                    {agents.map(agent => (
                        <AgentCard
                            key={agent.id}
                            agent={agent}
                            onClick={() => onAgentClick(agent.id)}
                            isSelected={selectedAgentId === agent.id}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

interface NodeCardProps {
    node: WorkflowNode;
    onClick: () => void;
    isSelected: boolean;
}

const NodeCard: React.FC<NodeCardProps> = ({ node, onClick, isSelected }) => {
    const colors = statusColors[node.status];

    return (
        <div
            onClick={onClick}
            className={clsx(
                'px-4 py-3 rounded-xl border-2 cursor-pointer transition-all duration-200',
                'hover:shadow-lg hover:scale-[1.02] min-w-[120px]',
                colors.bg, colors.border,
                isSelected && 'ring-2 ring-blue-500 ring-offset-2'
            )}
        >
            <div className="flex items-center gap-2">
                <div className={clsx('w-3 h-3 rounded-full', colors.dot)} />
                <span className={clsx('font-semibold', colors.text)}>{node.label}</span>
            </div>
            {node.message && (
                <p className="text-xs text-gray-500 mt-1 truncate max-w-[150px]">
                    {node.message}
                </p>
            )}
        </div>
    );
};

export const WorkflowGraph: React.FC = () => {
    const {
        workflowNodes,
        selectedNodeId,
        selectedAgentId,
        setSelectedNodeId,
        setSelectedAgentId
    } = useConsoleStore();

    return (
        <div className="w-full overflow-x-auto py-6">
            <div className="flex items-start gap-4 px-4 min-w-max">
                {workflowNodes.map((node, index) => (
                    <React.Fragment key={node.id}>
                        {/* 节点或并行容器 */}
                        {node.isParallelContainer ? (
                            <ParallelContainer
                                node={node}
                                onAgentClick={setSelectedAgentId}
                                selectedAgentId={selectedAgentId}
                            />
                        ) : (
                            <NodeCard
                                node={node}
                                onClick={() => setSelectedNodeId(node.id)}
                                isSelected={selectedNodeId === node.id}
                            />
                        )}

                        {/* 连接线 */}
                        {index < workflowNodes.length - 1 && (
                            <div className="flex items-center self-center">
                                <div className="w-8 h-0.5 bg-gray-300" />
                                <div className="w-0 h-0 border-t-4 border-b-4 border-l-6 border-t-transparent border-b-transparent border-l-gray-300" />
                            </div>
                        )}
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
};

export default WorkflowGraph;
