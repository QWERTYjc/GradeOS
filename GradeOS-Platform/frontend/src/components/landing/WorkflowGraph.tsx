'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    BookOpen,
    Cpu,
    Share2,
    Undo2,
    Loader2
} from 'lucide-react';

// --- Types ---

type NodeStatus = 'idle' | 'queued' | 'running' | 'success' | 'failed' | 'retrying';

interface NodeData {
    id: string;
    label: string;
    icon: React.ElementType;
    status: NodeStatus;
    logs: string[];
    x: number; // Relative position 0-100
    y: number;
}

interface WorkerData {
    id: string;
    status: NodeStatus;
    currentTask: string;
}

// --- Constants ---

const NODES_CONFIG = [
    { id: 'rubric_parse', label: 'Rubric Parse', icon: BookOpen, x: 10, y: 50 },
    { id: 'rubric_review', label: 'Rubric Review', icon: Undo2, x: 30, y: 50 },
    { id: 'grade_batch', label: 'Student Grading', icon: Cpu, x: 50, y: 50 },
    { id: 'logic_review', label: 'Logic Review', icon: Undo2, x: 70, y: 50 },
    { id: 'export', label: 'Export', icon: Share2, x: 90, y: 50 },
];


// --- Simulation Hook ---

const useWorkflowSimulation = () => {
    const [nodes, setNodes] = useState<NodeData[]>(NODES_CONFIG.map(n => ({ ...n, status: 'idle' as NodeStatus, logs: [] })));
    const [workers, setWorkers] = useState<WorkerData[]>([
        { id: 'w-01', status: 'idle', currentTask: '-' },
        { id: 'w-02', status: 'idle', currentTask: '-' },
        { id: 'w-03', status: 'idle', currentTask: '-' },
    ]);
    // Store packets with startTime for smooth animation
    const [activePackets, setActivePackets] = useState<{ from: string, to: string, startTime: number, duration: number, id: number }[]>([]);

    // Simulation Loop
    useEffect(() => {
        const interval = setInterval(() => {
            // Randomly trigger an "Ingest" event if idle
            if (Math.random() > 0.8) {
                triggerPipeline();
            }

            // Clean up old packets (older than duration + buffer)
            const now = Date.now();
            setActivePackets(prev => prev.filter(p => now - p.startTime < p.duration + 200));

            // Update worker states randomly
            setWorkers(prev => prev.map(w => {
                if (w.status === 'running' && Math.random() > 0.9) return { ...w, status: 'success', currentTask: 'Done' };
                if (w.status === 'idle' && Math.random() > 0.8) return { ...w, status: 'running', currentTask: `Task-${Math.floor(Math.random() * 100)}` };
                if (w.status === 'success' && Math.random() > 0.5) return { ...w, status: 'idle', currentTask: '-' };
                return w;
            }));

        }, 100); // Reduced frequency for state updates since animation is handled by Canvas

        return () => clearInterval(interval);
    }, []);

    const triggerPipeline = () => {
        const sequence = ['rubric_parse', 'rubric_review', 'grade_batch', 'logic_review', 'export'];

        // Staggered execution
        let accumulatedDelay = 0;

        sequence.forEach((id, idx) => {
            const stepDuration = 1500;

            // 1. Start Node
            setTimeout(() => {
                setNodes(prev => prev.map(n => n.id === id ? { ...n, status: 'running' as NodeStatus } : n));
            }, accumulatedDelay);

            // 2. Spawn Packet to next node (if exists)
            if (idx < sequence.length - 1) {
                setTimeout(() => {
                    const travelTime = 1000;
                    setActivePackets(prev => [...prev, {
                        from: id,
                        to: sequence[idx + 1],
                        startTime: Date.now(),
                        duration: travelTime,
                        id: Date.now() + Math.random()
                    }]);
                }, accumulatedDelay + stepDuration);
            }

            // 3. Finish Node
            setTimeout(() => {
                setNodes(prev => prev.map(n => n.id === id ? { ...n, status: (Math.random() > 0.95 ? 'failed' : 'success') as NodeStatus } : n));

                // Retry logic visual
                if (Math.random() > 0.95) {
                    setTimeout(() => {
                        setNodes(prev => prev.map(n => n.id === id ? { ...n, status: 'retrying' as NodeStatus } : n));
                        setTimeout(() => {
                            setNodes(prev => prev.map(n => n.id === id ? { ...n, status: 'success' as NodeStatus } : n));
                        }, 800);
                    }, 500);
                }
            }, accumulatedDelay + stepDuration);

            accumulatedDelay += (stepDuration + 1000); // Node time + Packet travel time
        });
    };

    return { nodes, workers, activePackets };
};

// --- Components ---

const NodeCard = ({ data, onClick }: { data: NodeData, onClick: () => void }) => {
    const statusColors: Record<NodeStatus, string> = {
        idle: 'border-slate-200 text-slate-400',
        queued: 'border-blue-200 text-blue-500 animate-pulse',
        running: 'border-blue-500 text-blue-700 shadow-[0_0_25px_rgba(37,99,235,0.35)]',
        success: 'border-emerald-400 text-emerald-600',
        failed: 'border-rose-500 text-rose-600',
        retrying: 'border-amber-400 text-amber-500',
    };

    return (
        // Positioning Wrapper - Isolates layout from animation
        <div
            className="absolute -translate-x-1/2 -translate-y-1/2 z-10"
            style={{ left: `${data.x}%`, top: `${data.y}%` }}
        >
            <motion.div
                className={`w-28 h-24 bg-white/90 rounded-2xl border-2 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors duration-300 ${statusColors[data.status] || statusColors.idle}`}
                whileHover={{ scale: 1.05, y: -5 }}
                animate={
                    data.status === 'failed'
                        ? { x: [-2, 2, -2, 2, 0] }
                        : { x: 0 }
                }
                transition={
                    data.status === 'failed'
                        ? { duration: 0.4, ease: "easeInOut" }
                        : { type: 'spring', stiffness: 300, damping: 20 }
                }
                onClick={onClick}
            >
                <div className={`p-2 rounded-full ${data.status === 'running' ? 'bg-blue-50' : 'bg-gray-50'}`}>
                    {data.icon && <data.icon size={20} className={data.status === 'running' ? 'animate-spin-slow' : ''} />}
                </div>
                <span className="text-[10px] font-bold font-mono uppercase tracking-wider text-center leading-tight px-1">
                    {data.label}
                </span>

                {/* Absolute Loader to prevent layout shifts */}
                {data.status === 'running' && (
                    <div className="absolute bottom-1">
                        <Loader2 size={10} className="animate-spin text-blue-500" />
                    </div>
                )}

                {/* Status Indicator Dot */}
                <div className={`absolute top-2 right-2 w-2 h-2 rounded-full ${data.status === 'running' ? 'bg-blue-500' :
                    data.status === 'success' ? 'bg-green-500' :
                        data.status === 'failed' ? 'bg-indigo-900' : 'bg-gray-200'
                    }`} />
            </motion.div>
        </div>
    );
};

const WorkerPool = ({ workers }: { workers: WorkerData[] }) => {
    return (
        <div className="absolute top-[80%] left-1/2 -translate-x-1/2 flex gap-2">
            {workers.map(w => (
                <motion.div
                    key={w.id}
                    className={`w-20 p-2 rounded-xl border bg-white/90 text-[10px] flex flex-col items-center gap-1
                ${w.status === 'running' ? 'border-blue-400 text-blue-600 shadow-lg shadow-blue-100' : 'border-slate-200 text-slate-400'}
            `}
                >
                    <Cpu size={12} />
                    <span>{w.id}</span>
                    <span className="truncate max-w-full">{w.currentTask}</span>
                </motion.div>
            ))}
        </div>
    );
};

const ConnectionCanvas = ({ nodes, packets }: { nodes: NodeData[], packets: any[] }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const requestRef = useRef<number>();

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const render = () => {
            const { width, height } = canvas.getBoundingClientRect();
            // Handle high-DPI displays
            const dpr = window.devicePixelRatio || 1;
            if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
                canvas.width = width * dpr;
                canvas.height = height * dpr;
                ctx.scale(dpr, dpr);
            }

            ctx.clearRect(0, 0, width, height);

            // Draw connections
            ctx.strokeStyle = '#E5E7EB';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';

            for (let i = 0; i < nodes.length - 1; i++) {
                const start = nodes[i];
                const end = nodes[i + 1];

                const x1 = (start.x / 100) * width;
                const y1 = (start.y / 100) * height;
                const x2 = (end.x / 100) * width;
                const y2 = (end.y / 100) * height;

                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
            }

            // Draw Packets
            const now = Date.now();
            packets.forEach((p: any) => {
                const startNode = nodes.find(n => n.id === p.from);
                const endNode = nodes.find(n => n.id === p.to);
                if (!startNode || !endNode) return;

                // Calculate progress based on time
                const elapsed = now - p.startTime;
                let progress = elapsed / p.duration;
                if (progress > 1) progress = 1;
                if (progress < 0) progress = 0;

                const x1 = (startNode.x / 100) * width;
                const y1 = (startNode.y / 100) * height;
                const x2 = (endNode.x / 100) * width;
                const y2 = (endNode.y / 100) * height;

                const curX = x1 + (x2 - x1) * progress;
                const curY = y1 + (y2 - y1) * progress;

                // Glow
                const gradient = ctx.createRadialGradient(curX, curY, 0, curX, curY, 8);
                gradient.addColorStop(0, 'rgba(59, 130, 246, 1)');
                gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');

                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(curX, curY, 8, 0, Math.PI * 2);
                ctx.fill();

                ctx.fillStyle = '#fff';
                ctx.beginPath();
                ctx.arc(curX, curY, 3, 0, Math.PI * 2);
                ctx.fill();
            });

            requestRef.current = requestAnimationFrame(render);
        };

        render();

        return () => {
            if (requestRef.current) {
                cancelAnimationFrame(requestRef.current);
            }
        };
    }, [nodes, packets]); // Re-init loop when packets list changes (which is less frequent now)

    return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ width: '100%', height: '100%' }} />;
};

export default function WorkflowGraph() {
    const { nodes, workers, activePackets } = useWorkflowSimulation();
    const [selectedNode, setSelectedNode] = useState<string | null>(null);

    return (
        <div className="relative w-full h-[520px] bg-white/85 rounded-[32px] border border-slate-200/60 shadow-[0_40px_120px_rgba(15,23,42,0.15)] overflow-hidden overflow-x-auto backdrop-blur">
            <div className="landing-grid absolute inset-0" />
            {/* Header */}
            <div className="absolute top-0 left-0 w-full p-4 border-b border-slate-200/60 flex justify-between items-center bg-white/80 backdrop-blur z-20">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-[11px] font-mono uppercase tracking-[0.3em] text-slate-500">System Status: Online</span>
                </div>
                <div className="text-[11px] font-mono uppercase tracking-[0.3em] text-slate-400">
                    Latency 24ms | Workers {workers.filter(w => w.status === 'running').length}/3
                </div>
            </div>

            {/* Graph Area */}
            <div className="absolute inset-0 top-12 min-w-[1000px]">
                <ConnectionCanvas nodes={nodes} packets={activePackets} />

                {nodes.map(node => (
                    <NodeCard
                        key={node.id}
                        data={node}
                        onClick={() => setSelectedNode(node.id)}
                    />
                ))}

                <WorkerPool workers={workers} />
            </div>

            {/* Drawer for Node Details */}
            <AnimatePresence>
                {selectedNode && (
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        className="absolute right-0 top-12 bottom-0 w-80 bg-white border-l border-gray-100 shadow-xl p-6 z-30"
                    >
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="font-bold text-lg">{nodes.find(n => n.id === selectedNode)?.label}</h3>
                            <button onClick={() => setSelectedNode(null)} className="text-gray-400 hover:text-black">×</button>
                        </div>

                        <div className="space-y-4">
                            <div className="p-3 bg-gray-50 rounded text-xs font-mono text-gray-600">
                                ID: {selectedNode}<br />
                                STATUS: {nodes.find(n => n.id === selectedNode)?.status.toUpperCase()}
                            </div>

                            <div>
                                <h4 className="text-xs font-bold text-gray-400 mb-2">LIVE LOGS</h4>
                                <div className="h-64 overflow-y-auto font-mono text-[10px] text-gray-500 space-y-1">
                                    <div className="text-blue-500">[{new Date().toLocaleTimeString()}] Process started</div>
                                    <div>[{new Date().toLocaleTimeString()}] Loading context...</div>
                                    <div>[{new Date().toLocaleTimeString()}] Validating inputs...</div>
                                    {nodes.find(n => n.id === selectedNode)?.status === 'failed' && (
                                        <div className="text-indigo-800">[{new Date().toLocaleTimeString()}] ERROR: Connection timeout</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
