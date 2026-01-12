'use client';

import React, { useMemo } from 'react';
import { useConsoleStore, WorkflowNode, GradingAgent } from '@/store/consoleStore';
import clsx from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Loader2, AlertCircle, Clock, Cpu, GitMerge, Undo2, BookOpen } from 'lucide-react';

const transition = { type: 'spring', stiffness: 400, damping: 30 };

const statusStyles = {
    pending: {
        bg: 'bg-slate-50/50',
        border: 'border-slate-200',
        text: 'text-slate-400',
        icon: <Clock className="w-5 h-5" />,
        glow: ''
    },
    running: {
        bg: 'bg-blue-50/80',
        border: 'border-blue-400',
        text: 'text-blue-600',
        icon: <Loader2 className="w-5 h-5 animate-spin" />,
        glow: 'shadow-[0_0_20px_rgba(59,130,246,0.3)] ring-2 ring-blue-400/20'
    },
    completed: {
        bg: 'bg-emerald-50/80',
        border: 'border-emerald-400',
        text: 'text-emerald-600',
        icon: <Check className="w-5 h-5" />,
        glow: 'shadow-[0_0_15px_rgba(16,185,129,0.2)]'
    },
    failed: {
        bg: 'bg-red-50/80',
        border: 'border-red-400',
        text: 'text-red-600',
        icon: <AlertCircle className="w-5 h-5" />,
        glow: 'shadow-[0_0_15px_rgba(239,68,68,0.2)]'
    }
};

const FlowingConnector = ({ active }: { active: boolean }) => (
    <div className="relative w-12 h-[2px] mx-2 flex items-center">
        <div className="absolute inset-0 bg-slate-200 rounded-full" />
        {active && (
            <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-500 to-transparent h-full rounded-full"
                initial={{ x: '-100%' }}
                animate={{ x: '100%' }}
                transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
            />
        )}
    </div>
);

const AgentCard: React.FC<{ agent: GradingAgent; onClick: () => void; isSelected: boolean }> = ({
    agent,
    onClick,
    isSelected
}) => {
    const isRunning = agent.status === 'running';
    const isCompleted = agent.status === 'completed';
    const isFailed = agent.status === 'failed';

    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ scale: 1.05, y: -2 }}
            onClick={(event) => {
                event.stopPropagation();
                onClick();
            }}
            className={clsx(
                'relative group cursor-pointer overflow-hidden rounded-lg border p-2.5 transition-all',
                'backdrop-blur-md bg-white/60',
                isSelected ? 'ring-2 ring-blue-500 border-transparent shadow-lg' : 'border-slate-200 hover:border-blue-300',
                isFailed && 'border-red-200 bg-red-50/30'
            )}
        >
            {isRunning && agent.progress !== undefined && (
                <div className="absolute bottom-0 left-0 h-1 bg-blue-500/20 w-full">
                    <motion.div
                        className="h-full bg-blue-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${agent.progress}%` }}
                    />
                </div>
            )}

            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                    <div
                        className={clsx(
                            'w-2 h-2 rounded-full shrink-0',
                            isRunning
                                ? 'bg-blue-500 animate-pulse'
                                : isCompleted
                                    ? 'bg-emerald-500'
                                    : isFailed
                                        ? 'bg-red-500'
                                        : 'bg-slate-300'
                        )}
                    />
                    <span className="text-xs font-medium text-slate-700 truncate">{agent.label}</span>
                </div>

                {agent.output && (
                    <span className="text-xs font-bold text-slate-900 bg-slate-100 px-1.5 py-0.5 rounded">
                        {agent.output.score}
                    </span>
                )}
            </div>
        </motion.div>
    );
};

const ParallelContainer: React.FC<{
    node: WorkflowNode;
    onAgentClick: (id: string) => void;
    selectedAgentId: string | null;
    batchProgress: any;
}> = ({ node, onAgentClick, selectedAgentId, batchProgress }) => {
    const styles = statusStyles[node.status];
    const agents = node.children || [];
    const isRunning = node.status === 'running';
    const isLogicReview = node.id === 'logic_review';
    const isRubricReview = node.id === 'rubric_review';
    const isRubricParse = node.id === 'rubric_parse';

    const waitLabel = isLogicReview || isRubricReview
        ? 'Waiting for reviews...'
        : isRubricParse
            ? 'Waiting for parse...'
            : 'Waiting for tasks...';

    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={clsx(
                'relative min-w-[280px] max-w-[320px] rounded-2xl border p-1 transition-all duration-500',
                styles.bg,
                styles.border,
                styles.glow,
                'backdrop-blur-xl'
            )}
        >
            {isRunning && (
                <div className="absolute -inset-[1px] rounded-2xl bg-gradient-to-r from-transparent via-blue-400/50 to-transparent opacity-50 blur-sm animate-pulse" />
            )}

            <div className="relative bg-white/40 rounded-xl p-4 overflow-hidden">
                <div className="flex items-center gap-3 mb-4">
                    <div className={clsx('p-2 rounded-lg bg-white shadow-sm', styles.text)}>
                        {isLogicReview || isRubricReview ? (
                            <Undo2 className={clsx('w-5 h-5', isRunning && 'animate-pulse')} />
                        ) : isRubricParse ? (
                            <BookOpen className={clsx('w-5 h-5', isRunning && 'animate-pulse')} />
                        ) : (
                            <Cpu className={clsx('w-5 h-5', isRunning && 'animate-pulse')} />
                        )}
                    </div>
                    <div>
                        <h3 className="font-bold text-slate-800 text-sm">{node.label}</h3>
                        <div className="text-xs text-slate-500 flex items-center gap-1">
                            {agents.length > 0 ? (
                                <>
                                    <span className="font-medium text-blue-600">{agents.length}</span>
                                    <span>active agents</span>
                                </>
                            ) : (
                                waitLabel
                            )}
                        </div>
                    </div>
                    {batchProgress && node.id === 'grade_batch' && (
                        <div className="ml-auto text-xs font-mono bg-slate-900/5 text-slate-600 px-2 py-1 rounded">
                            Batch {batchProgress.batchIndex + 1}/{batchProgress.totalBatches}
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-1 gap-2 max-h-[240px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
                    <AnimatePresence mode="popLayout">
                        {agents.length === 0 ? (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="col-span-1 py-8 text-center text-xs text-slate-400 italic border border-dashed border-slate-200 rounded-lg"
                            >
                                Waiting for tasks...
                            </motion.div>
                        ) : (
                            agents.map((agent) => (
                                <AgentCard
                                    key={agent.id}
                                    agent={agent}
                                    onClick={() => onAgentClick(agent.id)}
                                    isSelected={selectedAgentId === agent.id}
                                />
                            ))
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </motion.div>
    );
};

const NodeCard: React.FC<{
    node: WorkflowNode;
    onClick: () => void;
    isSelected: boolean;
}> = ({ node, onClick, isSelected }) => {
    const inferredStatus = node.status === 'pending' && !node.isParallelContainer ? 'completed' : node.status;
    const effectiveStatus = (node as any).isVisualCompleted ? 'completed' : inferredStatus;
    const styles = statusStyles[effectiveStatus] || statusStyles.pending;
    const isRunning = effectiveStatus === 'running';

    const isCrossPageMerge = node.id === 'cross_page_merge';
    const isLogicReview = node.id === 'logic_review';
    const nodeIcon = isCrossPageMerge
        ? <GitMerge className="w-5 h-5" />
        : isLogicReview
            ? <Undo2 className="w-5 h-5" />
            : styles.icon;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            whileHover={{ scale: 1.05, y: -5 }}
            whileTap={{ scale: 0.95 }}
            onClick={onClick}
            className={clsx(
                'relative min-w-[180px] rounded-2xl border p-1 cursor-pointer transition-all duration-300',
                styles.bg,
                styles.border,
                isSelected ? 'ring-2 ring-blue-500 ring-offset-2' : '',
                styles.glow,
                'backdrop-blur-xl group',
                isCrossPageMerge && node.status === 'completed' && 'border-purple-400 bg-purple-50/80'
            )}
        >
            <div className="relative bg-white/60 rounded-xl p-4 flex flex-col items-center text-center gap-3 overflow-hidden">
                <div
                    className={clsx(
                        'p-3 rounded-xl shadow-sm transition-transform duration-300 group-hover:scale-110',
                        'bg-white',
                        isCrossPageMerge && node.status === 'completed' ? 'text-purple-600' : styles.text
                    )}
                >
                    {nodeIcon}
                </div>

                <div>
                    <h3 className="font-bold text-slate-800 text-sm">{node.label}</h3>
                    <AnimatePresence mode="wait">
                        {node.message && (
                            <motion.p
                                key={node.message}
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -5 }}
                                className="text-[10px] text-slate-500 mt-1 max-w-[140px] truncate"
                            >
                                {node.message}
                            </motion.p>
                        )}
                    </AnimatePresence>
                </div>

                <div
                    className={clsx(
                        'absolute bottom-0 left-0 w-full h-1 opacity-0 transition-opacity duration-300',
                        isRunning ? 'opacity-100 bg-blue-500/20' : 'group-hover:opacity-100 bg-slate-200'
                    )}
                >
                    {isRunning && (
                        <motion.div
                            className="h-full bg-blue-500"
                            layoutId="node-progress"
                            transition={{ repeat: Infinity, duration: 1 }}
                        />
                    )}
                </div>
            </div>
        </motion.div>
    );
};

export const WorkflowGraph: React.FC = () => {
    const {
        workflowNodes,
        selectedNodeId,
        selectedAgentId,
        setSelectedNodeId,
        setSelectedAgentId,
        status,
        batchProgress
    } = useConsoleStore();

    const visibleNodes = useMemo(() => {
        const filteredNodes = workflowNodes;
        if (status === 'IDLE' || status === 'UPLOADING') {
            return filteredNodes.slice(0, 1);
        }
        const lastActiveIndex = filteredNodes.findLastIndex((node) => node.status !== 'pending');
        // 渐进式显示：只显示已激活的节点，不显示下一个 pending 节点
        const showIndex = lastActiveIndex === -1 ? 0 : lastActiveIndex;

        return filteredNodes.slice(0, showIndex + 1).map((node, index) => ({
            ...node,
            isVisualCompleted: index < lastActiveIndex && node.status === 'pending'
        }));
    }, [workflowNodes, status]);

    return (
        <div className="w-full h-full flex items-center justify-center overflow-x-auto py-12 px-8 scrollbar-hide">
            <div className="flex items-center">
                <AnimatePresence mode="popLayout">
                    {visibleNodes.map((node, index) => (
                        <React.Fragment key={node.id}>
                            <div className="relative z-10">
                                {node.isParallelContainer ? (
                                    <ParallelContainer
                                        node={node}
                                        onAgentClick={setSelectedAgentId}
                                        selectedAgentId={selectedAgentId}
                                        batchProgress={batchProgress}
                                    />
                                ) : (
                                    <NodeCard
                                        node={node}
                                        onClick={() => setSelectedNodeId(node.id)}
                                        isSelected={selectedNodeId === node.id}
                                    />
                                )}
                            </div>

                            {index < visibleNodes.length - 1 && (
                                <motion.div
                                    initial={{ width: 0, opacity: 0 }}
                                    animate={{ width: 'auto', opacity: 1 }}
                                    exit={{ width: 0, opacity: 0 }}
                                    transition={{ duration: 0.5 }}
                                >
                                    <FlowingConnector active={node.status === 'completed' || node.status === 'running'} />
                                </motion.div>
                            )}
                        </React.Fragment>
                    ))}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default WorkflowGraph;
