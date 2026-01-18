'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useConsoleStore, WorkflowNode, GradingAgent } from '@/store/consoleStore';
import clsx from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Loader2, AlertCircle, Clock, Cpu, GitMerge, Undo2, BookOpen, UserCheck, ShieldCheck } from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';

const statusStyles = {
    pending: {
        bg: 'bg-white/40',
        border: 'border-slate-200/60',
        text: 'text-slate-400',
        icon: <Clock className="w-5 h-5" />,
        shadow: 'shadow-sm'
    },
    running: {
        bg: 'bg-blue-50/60',
        border: 'border-blue-300',
        text: 'text-blue-600',
        icon: <Loader2 className="w-5 h-5 animate-spin" />,
        shadow: 'shadow-[0_0_25px_rgba(59,130,246,0.3)] ring-1 ring-blue-400/40'
    },
    completed: {
        bg: 'bg-emerald-50/60',
        border: 'border-emerald-300',
        text: 'text-emerald-600',
        icon: <Check className="w-5 h-5" />,
        shadow: 'shadow-[0_0_20px_rgba(16,185,129,0.2)]'
    },
    failed: {
        bg: 'bg-red-50/60',
        border: 'border-red-300',
        text: 'text-red-600',
        icon: <AlertCircle className="w-5 h-5" />,
        shadow: 'shadow-[0_0_20px_rgba(239,68,68,0.2)]'
    }
};

const FlowingConnector = ({ active }: { active: boolean }) => (
    <div className="relative w-8 md:w-16 h-[2px] mx-2 flex items-center overflow-hidden rounded-full">
        <div className="absolute inset-0 bg-slate-200/80 rounded-full" />
        {active && (
            <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-500 to-transparent h-full rounded-full"
                initial={{ x: '-100%' }}
                animate={{ x: '100%' }}
                transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
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
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={(event) => {
                event.stopPropagation();
                onClick();
            }}
            className={clsx(
                'relative group cursor-pointer overflow-hidden rounded-xl border p-3 transition-all duration-300',
                'backdrop-blur-md bg-white/70 shadow-sm',
                isSelected ? 'ring-2 ring-blue-500 border-transparent shadow-md' : 'border-slate-100 hover:border-blue-200 hover:bg-white/90',
                isFailed && 'border-red-200 bg-red-50/40'
            )}
        >
            {isRunning && agent.progress !== undefined && (
                <div className="absolute bottom-0 left-0 h-0.5 bg-blue-100 w-full">
                    <motion.div
                        className="h-full bg-blue-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${agent.progress}%` }}
                    />
                </div>
            )}

            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                    <div className="relative">
                        <div
                            className={clsx(
                                'w-2 h-2 rounded-full shrink-0',
                                isRunning
                                    ? 'bg-blue-500 animate-pulse'
                                    : isCompleted
                                        ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]'
                                        : isFailed
                                            ? 'bg-red-500'
                                            : 'bg-slate-300'
                            )}
                        />
                        {isRunning && <div className="absolute inset-0 rounded-full animate-ping bg-blue-400 opacity-75" />}
                    </div>
                    <span className="text-xs font-semibold text-slate-700 truncate tracking-tight">{agent.label}</span>
                </div>

                {agent.output && (
                    <span className={clsx(
                        "text-[10px] font-bold px-1.5 py-0.5 rounded-md",
                        agent.output.score >= (agent.output.maxScore * 0.6) ? "bg-emerald-100/50 text-emerald-700" : "bg-red-100/50 text-red-700"
                    )}>
                        {agent.output.score}
                    </span>
                )}
            </div>
        </motion.div>
    );
};

const WorkerTile: React.FC<{
    agent?: GradingAgent;
    nodeLabel?: string;
    onClick?: () => void;
    isSelected?: boolean;
}> = ({ agent, nodeLabel, onClick, isSelected }) => {
    const status = agent?.status || 'pending';
    const statusColor = status === 'running'
        ? 'bg-blue-500'
        : status === 'completed'
            ? 'bg-emerald-500'
            : status === 'failed'
                ? 'bg-red-500'
                : 'bg-slate-300';

    return (
        <button
            onClick={onClick}
            type="button"
            disabled={!agent}
            className={clsx(
                "rounded-xl border border-slate-200/70 bg-white/70 px-3 py-2 shadow-sm backdrop-blur-md text-left transition",
                agent ? "cursor-pointer hover:border-blue-200 hover:bg-white/90" : "cursor-default opacity-70",
                isSelected && "ring-2 ring-blue-500 border-transparent"
            )}
        >
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <span className={clsx('h-2 w-2 rounded-full', statusColor)} />
                    <span className="text-xs font-semibold text-slate-700">
                        {agent?.label || 'Worker'}
                    </span>
                </div>
                {nodeLabel && (
                    <span className="text-[10px] uppercase tracking-wider text-slate-400">
                        {nodeLabel}
                    </span>
                )}
            </div>
        </button>
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
    const isGradeBatch = node.id === 'grade_batch';
    const [openBatchIndex, setOpenBatchIndex] = useState<number | null>(0);

    const waitLabel = isLogicReview || isRubricReview
        ? 'Waiting for reviews...'
        : isRubricParse
            ? 'Waiting for parse...'
            : 'Waiting for tasks...';

    const batchSize = 5;
    const batchGroups = useMemo(() => {
        if (!isGradeBatch || agents.length === 0) {
            return [];
        }
        const groups: Array<{ index: number; agents: GradingAgent[] }> = [];
        for (let i = 0; i < agents.length; i += batchSize) {
            groups.push({ index: Math.floor(i / batchSize), agents: agents.slice(i, i + batchSize) });
        }
        return groups;
    }, [agents, isGradeBatch]);

    useEffect(() => {
        if (!isGradeBatch) return;
        if (batchProgress?.batchIndex !== undefined) {
            setOpenBatchIndex(batchProgress.batchIndex);
        }
    }, [batchProgress?.batchIndex, isGradeBatch]);

    const getBatchStatus = (batchAgents: GradingAgent[]) => {
        if (batchAgents.some((agent) => agent.status === 'running')) return 'running';
        if (batchAgents.some((agent) => agent.status === 'failed')) return 'failed';
        if (batchAgents.length > 0 && batchAgents.every((agent) => agent.status === 'completed')) return 'completed';
        return 'pending';
    };

    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={clsx(
                'relative min-w-[280px] max-w-[340px] rounded-2xl border p-1.5 transition-all duration-500 z-0',
                styles.bg,
                styles.border,
                styles.shadow,
                'backdrop-blur-xl'
            )}
        >
            {/* Animated Glow Border */}
            {isRunning && (
                <div className="absolute -inset-[1px] rounded-2xl bg-gradient-to-tr from-transparent via-blue-400/30 to-transparent opacity-60 blur-md animate-pulse pointer-events-none" />
            )}

            <div className="relative bg-white/50 rounded-xl p-4 overflow-hidden h-full flex flex-col">
                <div className="flex items-center gap-3.5 mb-4 border-b border-slate-100/60 pb-3">
                    <div className={clsx('p-2.5 rounded-xl bg-white shadow-sm ring-1 ring-slate-100', styles.text)}>
                        {isLogicReview || isRubricReview ? (
                            <Undo2 className={clsx('w-5 h-5', isRunning && 'animate-spin-slow')} />
                        ) : isRubricParse ? (
                            <BookOpen className={clsx('w-5 h-5', isRunning && 'animate-pulse')} />
                        ) : (
                            <Cpu className={clsx('w-5 h-5', isRunning && 'animate-pulse')} />
                        )}
                    </div>
                    <div>
                        <h3 className="font-bold text-slate-800 text-sm tracking-tight">{node.label}</h3>
                        <div className="text-[11px] text-slate-500 font-medium flex items-center gap-1.5 mt-0.5">
                            {agents.length > 0 ? (
                                <span className="inline-flex items-center gap-1.5">
                                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                                    <span className="text-blue-600 font-semibold">{agents.length}</span> active agents
                                </span>
                            ) : (
                                <span className="text-slate-400 italic">{waitLabel}</span>
                            )}
                        </div>
                    </div>
                    {batchProgress && isGradeBatch && (
                        <div className="ml-auto flex flex-col items-end">
                            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Batch</span>
                            <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                                {batchProgress.batchIndex + 1}/{batchProgress.totalBatches}
                            </span>
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-1 gap-2.5 max-h-[340px] overflow-y-auto pr-1 custom-scrollbar">
                    <AnimatePresence mode="popLayout">
                        {agents.length === 0 ? (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="col-span-1 py-10 text-center flex flex-col items-center gap-2 text-slate-400 border border-dashed border-slate-200/60 rounded-xl bg-slate-50/30"
                            >
                                <Clock className="w-6 h-6 opacity-30" />
                                <span className="text-xs font-medium">Waiting for agents...</span>
                            </motion.div>
                        ) : isGradeBatch ? (
                            batchGroups.map((group) => {
                                const status = getBatchStatus(group.agents);
                                const isOpen = openBatchIndex === group.index;
                                const isActive = batchProgress?.batchIndex === group.index || status === 'running';
                                return (
                                    <motion.div
                                        key={`batch-${group.index}`}
                                        layout
                                        className={clsx(
                                            "rounded-2xl border px-3 py-3 transition-all bg-white/70",
                                            isActive ? "border-blue-300 shadow-[0_0_15px_rgba(59,130,246,0.2)]" : "border-slate-200"
                                        )}
                                    >
                                        <button
                                            type="button"
                                            onClick={() => setOpenBatchIndex(isOpen ? null : group.index)}
                                            className="w-full flex items-center justify-between text-left"
                                        >
                                            <div className="flex items-center gap-2">
                                                <span
                                                    className={clsx(
                                                        "h-2 w-2 rounded-full",
                                                        status === 'running'
                                                            ? 'bg-blue-500 animate-pulse'
                                                            : status === 'completed'
                                                                ? 'bg-emerald-500'
                                                                : status === 'failed'
                                                                    ? 'bg-red-500'
                                                                    : 'bg-slate-300'
                                                    )}
                                                />
                                                <span className="text-xs font-semibold text-slate-700">
                                                    Batch {group.index + 1}
                                                </span>
                                                <span className="text-[10px] text-slate-400">
                                                    {group.agents.length} workers
                                                </span>
                                            </div>
                                            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400">
                                                {isOpen ? 'collapse' : 'expand'}
                                            </span>
                                        </button>

                                        <AnimatePresence initial={false}>
                                            {isOpen && (
                                                <motion.div
                                                    initial={{ height: 0, opacity: 0 }}
                                                    animate={{ height: 'auto', opacity: 1 }}
                                                    exit={{ height: 0, opacity: 0 }}
                                                    className="mt-3 grid grid-cols-2 gap-2"
                                                >
                                                    {Array.from({ length: batchSize }).map((_, idx) => {
                                                        const agent = group.agents[idx];
                                                        return (
                                                            <WorkerTile
                                                                key={agent?.id || `placeholder-${group.index}-${idx}`}
                                                                agent={agent}
                                                                nodeLabel="Worker"
                                                                onClick={agent ? () => onAgentClick(agent.id) : undefined}
                                                                isSelected={selectedAgentId === agent?.id}
                                                            />
                                                        );
                                                    })}
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </motion.div>
                                );
                            })
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
    const shouldAutoComplete = (
        node.status === 'pending'
        && !node.isParallelContainer
        && node.id !== 'rubric_review'
        && node.id !== 'review'
    );
    const inferredStatus = shouldAutoComplete ? 'completed' : node.status;
    const effectiveStatus = (node as any).isVisualCompleted ? 'completed' : inferredStatus;
    const styles = statusStyles[effectiveStatus] || statusStyles.pending;
    const isRunning = effectiveStatus === 'running';

    const isCrossPageMerge = node.id === 'cross_page_merge';
    const isLogicReview = node.id === 'logic_review';
    const isRubricReview = node.id === 'rubric_review';
    const isResultsReview = node.id === 'review';

    // Custom Icons
    let NodeIcon = styles.icon;
    if (isCrossPageMerge) NodeIcon = <GitMerge className="w-5 h-5" />;
    else if (isLogicReview) NodeIcon = <ShieldCheck className="w-5 h-5" />;
    else if (isRubricReview || isResultsReview) NodeIcon = <UserCheck className="w-5 h-5" />;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            whileHover={{ scale: 1.05, y: -4 }}
            whileTap={{ scale: 0.95 }}
            onClick={onClick}
            className={clsx(
                'relative min-w-[190px] rounded-2xl border p-1 cursor-pointer transition-all duration-300',
                styles.bg,
                styles.border,
                isSelected ? 'ring-2 ring-blue-500 ring-offset-2 shadow-lg' : '',
                styles.shadow,
                'backdrop-blur-xl group z-10',
                isCrossPageMerge && node.status === 'completed' && 'border-purple-400 bg-purple-50/80 shadow-[0_0_15px_rgba(168,85,247,0.2)]'
            )}
        >
            <div className="relative bg-white/60 rounded-xl p-5 flex flex-col items-center text-center gap-3 overflow-hidden h-full">
                <div
                    className={clsx(
                        'p-3.5 rounded-2xl shadow-sm transition-transform duration-500 group-hover:scale-110 group-hover:rotate-3',
                        'bg-white ring-1 ring-slate-100',
                        isCrossPageMerge && node.status === 'completed' ? 'text-purple-600' : styles.text
                    )}
                >
                    {NodeIcon}
                </div>

                <div className="flex flex-col items-center">
                    <h3 className="font-bold text-slate-800 text-sm tracking-wide">{node.label}</h3>
                    <AnimatePresence mode="wait">
                        {node.message && (
                            <motion.span
                                key={node.message}
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="text-[10px] font-medium text-slate-500 mt-1 max-w-[140px] truncate bg-white/50 px-2 py-0.5 rounded-full"
                            >
                                {node.message}
                            </motion.span>
                        )}
                    </AnimatePresence>
                </div>

                <div
                    className={clsx(
                        'absolute bottom-0 left-0 w-full h-1 opacity-0 transition-opacity duration-300',
                        isRunning ? 'opacity-100 bg-blue-100' : 'group-hover:opacity-100 bg-slate-200'
                    )}
                >
                    {isRunning && (
                        <motion.div
                            className="h-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.6)]"
                            layoutId="node-progress"
                            initial={{ width: '0%' }}
                            animate={{ width: '100%' }}
                            transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
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
        batchProgress,
        interactionEnabled,
        pendingReview,
        submissionId,
        setCurrentTab,
        setReviewFocus
    } = useConsoleStore();
    const containerRef = useRef<HTMLDivElement | null>(null);
    const scrollRef = useRef<HTMLDivElement | null>(null);
    const dragState = useRef({
        isDragging: false,
        startX: 0,
        startY: 0,
        scrollLeft: 0,
        scrollTop: 0
    });
    const nodeRefs = useRef<Record<string, HTMLDivElement | null>>({});

    const handleNodeClick = (node: WorkflowNode) => {
        setSelectedNodeId(node.id);
        if (!interactionEnabled || !submissionId) {
            return;
        }
        const reviewType = pendingReview?.reviewType || '';
        if (node.id === 'rubric_review') {
            const canNavigate = node.status === 'running' || reviewType.includes('rubric');
            if (canNavigate) {
                setReviewFocus('rubric');
                setCurrentTab('results');
            }
            return;
        }
        if (node.id === 'review') {
            const canNavigate = node.status === 'running' || reviewType.includes('results');
            if (canNavigate) {
                setReviewFocus('results');
                setCurrentTab('results');
            }
        }
    };

    const visibleNodes = useMemo(() => {
        const filteredNodes = interactionEnabled
            ? workflowNodes
            : workflowNodes.filter((node) => node.id !== 'rubric_review' && node.id !== 'review');
        if (status === 'IDLE' || status === 'UPLOADING') {
            return filteredNodes.map((node) => ({
                ...node,
                isVisualCompleted: false
            }));
        }
        const lastActiveIndex = filteredNodes.findLastIndex((node) => node.status !== 'pending');
        // 渐进式显示：只显示已激活的节点，不显示下一个 pending 节点
        const showIndex = lastActiveIndex === -1 ? 0 : lastActiveIndex;

        return filteredNodes.slice(0, showIndex + 1).map((node, index) => ({
            ...node,
            isVisualCompleted: index < lastActiveIndex && node.status === 'pending'
        }));
    }, [workflowNodes, status, interactionEnabled]);

    useEffect(() => {
        if (visibleNodes.length === 0) return;
        const selectedNode = selectedNodeId
            ? visibleNodes.find((node) => node.id === selectedNodeId)
            : null;
        const runningNode = [...visibleNodes].reverse().find((node) => node.status === 'running');
        const targetId = (selectedNode || runningNode || visibleNodes[visibleNodes.length - 1])?.id;
        if (!targetId) return;
        const target = nodeRefs.current[targetId];
        if (!target) return;
        requestAnimationFrame(() => {
            target.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        });
    }, [visibleNodes, selectedNodeId]);

    return (
        <div
            ref={scrollRef}
            className="w-full h-full flex flex-col items-center justify-start overflow-auto cursor-grab active:cursor-grabbing"
            onPointerDown={(event) => {
                const el = scrollRef.current;
                if (!el) return;
                if (event.pointerType === 'mouse' && event.button !== 0) return;
                dragState.current = {
                    isDragging: true,
                    startX: event.clientX,
                    startY: event.clientY,
                    scrollLeft: el.scrollLeft,
                    scrollTop: el.scrollTop
                };
                el.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
                const el = scrollRef.current;
                if (!el || !dragState.current.isDragging) return;
                const dx = event.clientX - dragState.current.startX;
                const dy = event.clientY - dragState.current.startY;
                el.scrollLeft = dragState.current.scrollLeft - dx;
                el.scrollTop = dragState.current.scrollTop - dy;
            }}
            onPointerUp={(event) => {
                const el = scrollRef.current;
                if (!el) return;
                dragState.current.isDragging = false;
                el.releasePointerCapture(event.pointerId);
            }}
            onPointerLeave={() => {
                dragState.current.isDragging = false;
            }}
        >
            <div
                ref={containerRef}
                className="w-full flex items-center justify-center py-14 px-10 scrollbar-hide perspective-1000"
            >
                <div className="flex items-center space-x-2 md:space-x-1 min-w-max">
                    <AnimatePresence mode="popLayout">
                        {visibleNodes.map((node, index) => (
                            <React.Fragment key={node.id}>
                                <motion.div
                                    ref={(el) => {
                                        nodeRefs.current[node.id] = el;
                                    }}
                                    className="relative z-10"
                                    initial={{ opacity: 0, x: 50, rotateY: 90 }}
                                    animate={{ opacity: 1, x: 0, rotateY: 0 }}
                                    transition={{ type: "spring", stiffness: 100, damping: 20, delay: index * 0.1 }}
                                >
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
                                            onClick={() => handleNodeClick(node)}
                                            isSelected={selectedNodeId === node.id}
                                        />
                                    )}
                                </motion.div>

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
        </div>
    );
};

export default WorkflowGraph;
