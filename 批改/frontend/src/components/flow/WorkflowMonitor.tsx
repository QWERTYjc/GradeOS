'use client';

import React, { useEffect, useState } from 'react';
import { useFlowStore, FlowNode } from '@/store/flowStore';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Cpu, Activity, Clock, AlertTriangle, CheckCircle, Disc, Terminal, Zap, Shield, Database, ScanLine, Box } from 'lucide-react';

// --- Icons & Visuals ---

const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
        case 'running': return <Activity className="animate-pulse text-cyan-400" size={16} />;
        case 'completed': return <CheckCircle className="text-green-400" size={16} />;
        case 'failed': return <AlertTriangle className="text-red-500" size={16} />;
        default: return <Disc className="text-slate-600" size={16} />;
    }
};

const TypeIcon = ({ label }: { label: string }) => {
    const l = label.toLowerCase();
    if (l.includes('intake')) return <Box size={14} className="text-blue-300" />;
    if (l.includes('grading')) return <Cpu size={14} className="text-cyan-300" />;
    if (l.includes('review')) return <Shield size={14} className="text-purple-300" />;
    if (l.includes('export')) return <Database size={14} className="text-emerald-300" />;
    return <ScanLine size={14} className="text-slate-400" />;
};

// --- Components ---

const TechBorder = ({ className }: { className?: string }) => (
    <div className={cn("absolute inset-0 pointer-events-none rounded-xl border border-white/5", className)}>
        {/* Corner Accents */}
        <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-cyan-500/50 rounded-tl-lg" />
        <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-cyan-500/50 rounded-tr-lg" />
        <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-cyan-500/50 rounded-bl-lg" />
        <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-cyan-500/50 rounded-br-lg" />
    </div>
);

const NodeCard = ({ node, onClick, isSelected }: { node: FlowNode, onClick: () => void, isSelected: boolean }) => {
    return (
        <motion.div
            layoutId={node.id}
            onClick={onClick}
            initial={{ opacity: 0, x: -20, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            whileHover={{ scale: 1.02, backgroundColor: 'rgba(56, 189, 248, 0.05)' }}
            className={cn(
                "relative z-10 p-3 mb-2 rounded-xl backdrop-blur-md cursor-pointer transition-all duration-300 group overflow-hidden",
                isSelected
                    ? "bg-slate-900/60 border border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.15)]"
                    : "bg-slate-900/30 border border-white/5 hover:border-cyan-500/30",
                node.parentId && "ml-4 border-l-2 border-l-slate-700/50 pl-4"
            )}
        >
            <TechBorder />

            {/* Active Running Effect */}
            {node.status === 'running' && (
                <div className="absolute inset-0 z-0">
                    <div className="absolute bottom-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-cyan-500 to-transparent animate-scan" />
                </div>
            )}

            <div className="relative z-10 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className={cn(
                        "p-1.5 rounded-lg flex items-center justify-center",
                        node.status === 'running' ? "bg-cyan-500/10 text-cyan-400" : "bg-slate-800/50 text-slate-400"
                    )}>
                        <TypeIcon label={node.label} />
                    </div>
                    <div>
                        <div className="font-bold text-xs text-slate-200 tracking-wide font-mono flex items-center gap-2">
                            {node.label}
                            <StatusIcon status={node.status} />
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex gap-2">
                            <span>{node.logs.length} OPS</span>
                            {node.status === 'running' && <span className="text-cyan-400 animate-pulse">PROCESSING</span>}
                        </div>
                    </div>
                </div>

                {node.aiStreamContent && (
                    <Zap size={14} className="text-yellow-400 animate-pulse drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
                )}
            </div>
        </motion.div>
    );
};

const WorkflowNodeList = ({
    nodeIds,
    nodes,
    selectedNodeId,
    onSelect
}: {
    nodeIds: string[],
    nodes: Record<string, FlowNode>,
    selectedNodeId: string | null,
    onSelect: (id: string) => void
}) => {
    return (
        <div className="flex flex-col gap-1">
            {nodeIds.map(id => {
                const node = nodes[id];
                if (!node) return null;
                return (
                    <React.Fragment key={id}>
                        <NodeCard
                            node={node}
                            isSelected={selectedNodeId === id}
                            onClick={() => onSelect(id)}
                        />
                        {/* Recursively render children */}
                        {node.children && node.children.length > 0 && (
                            <div className="relative ml-2 pl-2 border-l border-dashed border-slate-700/50 my-1">
                                <WorkflowNodeList
                                    nodeIds={node.children}
                                    nodes={nodes}
                                    selectedNodeId={selectedNodeId}
                                    onSelect={onSelect}
                                />
                            </div>
                        )}
                    </React.Fragment>
                );
            })}
        </div>
    );
};

export const WorkflowMonitor = ({ runId }: { runId: string | null }) => {
    const { connect, isConnected, nodes, rootNodes, events } = useFlowStore();
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

    // Auto-select first running or last completed node if none selected
    useEffect(() => {
        if (!selectedNodeId && rootNodes.length > 0) {
            // Logic to find interesting node could go here
        }
    }, [rootNodes, selectedNodeId]);

    useEffect(() => {
        if (runId) connect(runId);
    }, [runId]);

    const activeNode = selectedNodeId ? nodes[selectedNodeId] : null;

    if (!runId) return (
        <div className="h-full flex flex-col items-center justify-center bg-transparent backdrop-blur-sm text-cyan-500 font-mono animate-pulse">
            <Cpu size={64} className="mb-6 drop-shadow-[0_0_15px_rgba(6,182,212,0.5)]" />
            <div className="text-2xl tracking-[0.5em] font-bold text-white mb-2">SYSTEM STANDBY</div>
            <div className="text-sm text-cyan-400/50">WAITING FOR NEURAL LINK...</div>
        </div>
    );

    return (
        <div className="h-full flex flex-col bg-slate-950/40 backdrop-blur-md rounded-2xl border border-white/5 overflow-hidden font-sans shadow-2xl relative">

            {/* Background Grid - Local Overlay */}
            <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-5 pointer-events-none" />

            {/* Header */}
            <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-slate-950/50 backdrop-blur-xl z-20">
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full" />
                        <Cpu className="text-cyan-400 relative z-10" size={24} />
                    </div>
                    <div>
                        <h2 className="font-bold text-lg tracking-widest text-white flex items-center gap-2">
                            GRADE_OS <span className="text-[10px] bg-cyan-950/50 text-cyan-400 px-2 py-0.5 rounded border border-cyan-500/20 font-mono py-0.5">V.2.0</span>
                        </h2>
                        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                            <span>SESSION ID:</span>
                            <span className="text-slate-300">{runId.slice(0, 8)}</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className={cn(
                        "flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-mono transition-all",
                        isConnected
                            ? "border-green-500/30 bg-green-500/10 text-green-400 shadow-[0_0_10px_rgba(34,197,94,0.2)]"
                            : "border-red-500/30 bg-red-500/10 text-red-400"
                    )}>
                        <div className={cn("w-1.5 h-1.5 rounded-full", isConnected ? "bg-green-400 animate-pulse" : "bg-red-400")} />
                        {isConnected ? "ONLINE" : "OFFLINE"}
                    </div>
                </div>
            </header>

            {/* Main Layout */}
            <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden z-10">

                {/* Left: Operations Tree */}
                <div className="col-span-3 border-r border-white/5 flex flex-col bg-slate-950/20 backdrop-blur-sm">
                    <div className="px-4 py-3 border-b border-white/5 text-[10px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                        <Activity size={12} /> Operations Matrix
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                        <WorkflowNodeList
                            nodeIds={rootNodes}
                            nodes={nodes}
                            selectedNodeId={selectedNodeId}
                            onSelect={setSelectedNodeId}
                        />
                    </div>
                </div>

                {/* Center: Main Viewport */}
                <div className="col-span-6 flex flex-col bg-slate-900/40 relative group">
                    {/* Header */}
                    <div className="px-6 py-3 border-b border-white/5 text-[10px] font-bold uppercase tracking-widest text-slate-500 flex justify-between items-center bg-slate-950/20">
                        <div className="flex items-center gap-2">
                            <Terminal size={12} /> Neural Console Output
                        </div>
                        {activeNode && (
                            <span className="text-cyan-400 font-mono bg-cyan-950/30 px-2 py-0.5 rounded border border-cyan-500/10">
                                {activeNode.label}
                            </span>
                        )}
                    </div>

                    {/* Content Area */}
                    <div className="flex-1 overflow-y-auto p-6 font-mono text-sm leading-relaxed custom-scrollbar relative">
                        {/* Decorative Corner Lines */}
                        <div className="absolute top-4 left-4 w-4 h-[1px] bg-white/10" />
                        <div className="absolute top-4 left-4 h-4 w-[1px] bg-white/10" />
                        <div className="absolute bottom-4 right-4 w-4 h-[1px] bg-white/10" />
                        <div className="absolute bottom-4 right-4 h-4 w-[1px] bg-white/10" />

                        {activeNode ? (
                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={activeNode.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -10 }}
                                    className="h-full"
                                >
                                    {activeNode.aiStreamContent ? (
                                        <div className="space-y-4 max-w-3xl mx-auto">
                                            <div className="flex items-center gap-2 text-xs text-cyan-400 mb-4 pb-2 border-b border-cyan-500/20">
                                                <Zap size={14} className="animate-pulse" /> AI THOUGHT STREAM ACTIVE
                                            </div>
                                            <div className="whitespace-pre-wrap text-slate-300 font-light tracking-wide leading-7 drop-shadow-md">
                                                {activeNode.aiStreamContent}
                                                <span className="inline-block w-2.5 h-5 bg-cyan-400 ml-1 animate-pulse align-middle" />
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="space-y-1">
                                            {activeNode.logs.length > 0 ? activeNode.logs.map((log, i) => (
                                                <div key={i} className="flex gap-3 text-xs group hover:bg-white/5 p-1 rounded transition-colors border-l-2 border-transparent hover:border-cyan-500/50 pl-2">
                                                    <span className="text-slate-600 font-bold select-none w-16 text-right">
                                                        {log.timestamp.split('T')[1].slice(0, 8)}
                                                    </span>
                                                    <span className={cn(
                                                        "font-bold w-16 text-center rounded px-1",
                                                        log.level === 'ERROR' ? "bg-red-500/20 text-red-400" :
                                                            log.level === 'WARNING' ? "bg-yellow-500/20 text-yellow-400" : "bg-blue-500/10 text-blue-400"
                                                    )}>{log.level}</span>
                                                    <span className="text-slate-300 flex-1 break-words">{log.message}</span>
                                                </div>
                                            )) : (
                                                <div className="flex flex-col items-center justify-center h-[50vh] opacity-20 gap-4">
                                                    <Terminal size={48} className="text-white" />
                                                    <p className="text-white tracking-widest">NO TELEMETRY DATA</p>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </motion.div>
                            </AnimatePresence>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full opacity-30 gap-6">
                                <div className="relative">
                                    <div className="absolute inset-0 bg-cyan-500/20 blur-2xl rounded-full animate-pulse" />
                                    <ScanLine size={64} className="text-cyan-400 relative z-10 animate-pulse" />
                                </div>
                                <p className="text-cyan-400 font-mono tracking-[0.2em] text-sm">SELECT OPERATION NODE TO INSPECT</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Timeline / Stats */}
                <div className="col-span-3 border-l border-white/5 flex flex-col bg-slate-950/20 backdrop-blur-sm">
                    <div className="px-4 py-3 border-b border-white/5 text-[10px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                        <Clock size={12} /> Event Stream
                    </div>
                    <div className="flex-1 overflow-y-auto p-0 custom-scrollbar relative">
                        {/* Timeline Line */}
                        <div className="absolute left-6 top-4 bottom-4 w-[1px] bg-gradient-to-b from-transparent via-white/10 to-transparent" />

                        <div className="py-4 pr-4">
                            <AnimatePresence initial={false}>
                                {events.map((ev, i) => (
                                    <motion.div
                                        key={ev.id}
                                        initial={{ opacity: 0, x: 20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.05 }}
                                        className="relative pl-10 mb-6 group"
                                    >
                                        <div className={cn(
                                            "absolute left-[1.35rem] top-1.5 w-2 h-2 rounded-full border border-slate-900 ring-4 ring-slate-900",
                                            ev.type.includes('error') ? "bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" :
                                                ev.type.includes('completed') ? "bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]" :
                                                    "bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]"
                                        )} />

                                        <div className="text-[10px] text-slate-500 font-mono mb-0.5">{ev.ts.split('T')[1].slice(0, 8)}</div>
                                        <div className="text-xs font-bold text-slate-200 group-hover:text-cyan-400 transition-colors cursor-default">
                                            {ev.title}
                                        </div>
                                        {ev.detail && (
                                            <div className="text-[10px] text-slate-400 mt-1 line-clamp-2 leading-relaxed border-l-2 border-white/5 pl-2">
                                                {ev.detail}
                                            </div>
                                        )}
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};
