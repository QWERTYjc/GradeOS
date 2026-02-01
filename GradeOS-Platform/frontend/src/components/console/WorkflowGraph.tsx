'use client';

import React, { useMemo, useRef, useState } from 'react';
import { useConsoleStore, WorkflowNode, GradingAgent } from '@/store/consoleStore';
import clsx from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Loader2, AlertCircle, Clock, Cpu, GitMerge, Undo2, BookOpen, UserCheck, ShieldCheck, FileText, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react';

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const MIN_ZOOM = 0.6;
const MAX_ZOOM = 1.6;
const ZOOM_STEP = 0.1;

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
            data-no-drag="true"
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

                {agent.output && typeof (agent.output?.score ?? 0) === 'number' && (
                    <span className={clsx(
                        "text-[10px] font-bold px-1.5 py-0.5 rounded-md",
                        (agent.output?.score ?? 0) >= ((agent.output?.maxScore ?? 100) * 0.6) ? "bg-emerald-100/50 text-emerald-700" : "bg-red-100/50 text-red-700"
                    )}>
                        {agent.output?.score ?? 0}
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
    onClick: () => void;
    isSelected: boolean;
    streamPreview?: string;
}> = ({ node, onAgentClick, selectedAgentId, onClick, isSelected }) => {
    const styles = statusStyles[node.status];
    const agents = node.children || [];
    const isRunning = node.status === 'running';
    const isLogicReview = node.id === 'logic_review';
    const isRubricReview = node.id === 'rubric_review';
    const isRubricParse = node.id === 'rubric_parse';
    const isGradeBatch = node.id === 'grade_batch';
    const waitLabel = isLogicReview || isRubricReview
        ? 'Waiting for reviews...'
        : isRubricParse
            ? 'Waiting for parse...'
            : isGradeBatch
                ? 'Waiting for students...'
                : 'Waiting for tasks...';

    const gridClassName = clsx(
        'grid gap-2.5 max-h-[340px] overflow-y-auto pr-1 custom-scrollbar',
        isGradeBatch ? 'sm:grid-cols-2' : 'grid-cols-1'
    );

    return (
        <motion.div
            data-no-drag="true"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={onClick}
            className={clsx(
                'relative min-w-[280px] max-w-[340px] rounded-2xl border p-1.5 transition-all duration-500 z-0 cursor-pointer',
                styles.bg,
                styles.border,
                isSelected ? 'ring-2 ring-blue-500 ring-offset-2 shadow-lg' : '',
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
                </div>

                <div className={gridClassName}>
                    <AnimatePresence>
                        {agents.length === 0 ? (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="col-span-1 py-10 text-center flex flex-col items-center gap-2 text-slate-400 border border-dashed border-slate-200/60 rounded-xl bg-slate-50/30"
                            >
                                <Clock className="w-6 h-6 opacity-30" />
                                <span className="text-xs font-medium">Waiting for agents...</span>
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
    streamPreview?: string;
}> = ({ node, onClick, isSelected }) => {
    const shouldAutoComplete = (
        node.status === 'pending'
        && !node.isParallelContainer
        && node.id !== 'rubric_review'
        && node.id !== 'review'
        && node.id !== 'logic_review'
        && node.id !== 'confession'
    );
    const inferredStatus = shouldAutoComplete ? 'completed' : node.status;
    const effectiveStatus = (node as {isVisualCompleted?: boolean}).isVisualCompleted ? 'completed' : inferredStatus;
    const styles = statusStyles[effectiveStatus] || statusStyles.pending;
    const isRunning = effectiveStatus === 'running';
    const isCrossPageMerge = node.id === 'cross_page_merge';
    const isLogicReview = node.id === 'logic_review';
    const isRubricReview = node.id === 'rubric_review';
    const isResultsReview = node.id === 'review';
    const isConfession = node.id === 'confession';

    // Custom Icons
    let NodeIcon = styles.icon;
    if (isCrossPageMerge) NodeIcon = <GitMerge className="w-5 h-5" />;
    else if (isLogicReview) NodeIcon = <ShieldCheck className="w-5 h-5" />;
    else if (isRubricReview || isResultsReview) NodeIcon = <UserCheck className="w-5 h-5" />;
    else if (isConfession) NodeIcon = <FileText className="w-5 h-5" />;

    return (
        <motion.div
            data-no-drag="true"
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

                <div className="flex flex-col items-center gap-1">
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
        interactionEnabled,
        pendingReview,
        submissionId,
        setCurrentTab,
        setReviewFocus
    } = useConsoleStore();
    const viewportRef = useRef<HTMLDivElement | null>(null);
    const dragState = useRef({
        isDragging: false,
        startX: 0,
        startY: 0,
        panX: 0,
        panY: 0
    });
    const [zoom, setZoom] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
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
        const lastActiveIndex = filteredNodes.findLastIndex((node) => node.status !== 'pending');
        // 渐进式显示：只显示已激活的节点，不显示下一个 pending 节点
        const showIndex = lastActiveIndex === -1 ? 0 : lastActiveIndex;

        return filteredNodes.slice(0, showIndex + 1).map((node, index) => ({
            ...node,
            isVisualCompleted: index < lastActiveIndex && node.status === 'pending'
        }));
    }, [workflowNodes, interactionEnabled]);

    const shouldIgnoreDrag = (target: EventTarget | null) => {
        if (!(target instanceof HTMLElement)) return false;
        return Boolean(target.closest('[data-no-drag="true"]'));
    };

    return (
        <div
            ref={viewportRef}
            className="relative w-full min-h-screen flex flex-col items-center justify-start overflow-hidden cursor-grab active:cursor-grabbing touch-none"
            onPointerDown={(event) => {
                if (shouldIgnoreDrag(event.target)) return;
                if (event.pointerType === 'mouse' && event.button !== 0) return;
                const el = viewportRef.current;
                if (!el) return;
                dragState.current = {
                    isDragging: true,
                    startX: event.clientX,
                    startY: event.clientY,
                    panX: pan.x,
                    panY: pan.y
                };
                el.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
                if (!dragState.current.isDragging) return;
                const dx = event.clientX - dragState.current.startX;
                const dy = event.clientY - dragState.current.startY;
                setPan({
                    x: dragState.current.panX + dx,
                    y: dragState.current.panY + dy
                });
            }}
            onPointerUp={(event) => {
                const el = viewportRef.current;
                if (!el) return;
                dragState.current.isDragging = false;
                el.releasePointerCapture(event.pointerId);
            }}
            onPointerLeave={() => {
                dragState.current.isDragging = false;
            }}
            onWheel={(event) => {
                if (event.ctrlKey || event.metaKey) {
                    event.preventDefault();
                    const nextZoom = clamp(zoom - event.deltaY * 0.001, MIN_ZOOM, MAX_ZOOM);
                    setZoom(nextZoom);
                    return;
                }
                setPan((prev) => ({
                    x: prev.x - event.deltaX,
                    y: prev.y - event.deltaY
                }));
            }}
        >
            <div
                data-no-drag="true"
                className="absolute right-4 top-4 z-20 flex items-center gap-2 rounded-lg border border-slate-200 bg-white/90 px-2 py-1 shadow-sm"
            >
                <button
                    type="button"
                    className="h-8 w-8 rounded-md border border-slate-200 bg-white text-slate-600 hover:text-slate-900 hover:border-slate-300 transition"
                    onClick={() => setZoom((value) => clamp(value + ZOOM_STEP, MIN_ZOOM, MAX_ZOOM))}
                >
                    <ZoomIn className="w-4 h-4 mx-auto" />
                </button>
                <button
                    type="button"
                    className="h-8 w-8 rounded-md border border-slate-200 bg-white text-slate-600 hover:text-slate-900 hover:border-slate-300 transition"
                    onClick={() => setZoom((value) => clamp(value - ZOOM_STEP, MIN_ZOOM, MAX_ZOOM))}
                >
                    <ZoomOut className="w-4 h-4 mx-auto" />
                </button>
                <button
                    type="button"
                    className="h-8 w-8 rounded-md border border-slate-200 bg-white text-slate-600 hover:text-slate-900 hover:border-slate-300 transition"
                    onClick={() => {
                        setZoom(1);
                        setPan({ x: 0, y: 0 });
                    }}
                >
                    <RefreshCw className="w-4 h-4 mx-auto" />
                </button>
                <span className="text-xs font-semibold text-slate-500 tabular-nums w-12 text-right">
                    {Math.round(zoom * 100)}%
                </span>
            </div>
            <div
                className="w-full flex items-center justify-center py-14 px-10 scrollbar-hide perspective-1000"
            >
                <div
                    className="flex items-center space-x-2 md:space-x-1 min-w-max"
                    style={{
                        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                        transformOrigin: 'center'
                    }}
                >
                    <AnimatePresence>
                        {visibleNodes.map((node, index) => (
                            <React.Fragment key={node.id}>
                                <motion.div
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
                                            onClick={() => handleNodeClick(node)}
                                            isSelected={selectedNodeId === node.id}
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
