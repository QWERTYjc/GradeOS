'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
    FileInput,
    ScanLine,
    FileSearch,
    Cpu,
    BrainCircuit,
    ShieldCheck,
    MessageSquarePlus,
    FileCheck,
    ArrowRight,
    Activity
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';
import Link from 'next/link';

// 1:1 还原后端 LangGraph 拓扑结构
interface WorkflowNode {
    id: string;
    label: string;
    icon: any;
    color: string;
    bg: string;
    isParallel?: boolean;
    highlight?: string;
}

const WORKFLOW_NODES: WorkflowNode[] = [
    { id: 'intake', label: 'Intake', icon: FileInput, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { id: 'preprocess', label: 'Preprocess', icon: ScanLine, color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
    { id: 'rubric_parse', label: 'Rubric Parse', icon: FileSearch, color: 'text-purple-400', bg: 'bg-purple-500/10' },
    { id: 'batch_grading', label: 'Batch Grading', icon: Cpu, color: 'text-amber-400', bg: 'bg-amber-500/10', isParallel: true, highlight: '并发处理' },
    { id: 'self_report', label: 'Self Report', icon: BrainCircuit, color: 'text-indigo-400', bg: 'bg-indigo-500/10', highlight: '模型自白' },
    { id: 'logic_review', label: 'Logic Review', icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/10', highlight: '逻辑复核' },
    { id: 'annotation', label: 'Annotation', icon: MessageSquarePlus, color: 'text-teal-400', bg: 'bg-teal-500/10' },
    { id: 'export', label: 'Export', icon: FileCheck, color: 'text-green-400', bg: 'bg-green-500/10' },
];

export default function Hero() {
    const { user } = useAuthStore();
    const isTeacher = user?.role === Role.Teacher || user?.role === Role.Admin;
    const ctaHref = user ? (isTeacher ? "/console" : "/student/dashboard") : "/login";
    const [activeNodeIndex, setActiveNodeIndex] = useState(0);

    // 模拟数据流在节点间流转
    useEffect(() => {
        const interval = setInterval(() => {
            setActiveNodeIndex((prev) => (prev + 1) % WORKFLOW_NODES.length);
        }, 1500);
        return () => clearInterval(interval);
    }, []);

    return (
        <section className="relative min-h-screen flex items-center px-4 pt-24 pb-16 overflow-hidden bg-[#0a0a0f]">
            {/* 背景光效 */}
            <div className="absolute inset-0 pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-blue-600/20 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-purple-600/20 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-[0.03]" />
            </div>

            <div className="relative z-10 w-full max-w-7xl mx-auto grid lg:grid-cols-[0.8fr_1.2fr] gap-16 items-center">

                {/* 左侧文案 */}
                <div className="space-y-8">
                    <motion.div
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm"
                    >
                        <Activity size={14} className="text-emerald-400 animate-pulse" />
                        <span className="text-sm font-medium text-gray-300">GradeOS Core v3.0 Online</span>
                    </motion.div>

                    <motion.h1
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                        className="text-5xl md:text-6xl font-bold tracking-tight text-white leading-[1.1]"
                    >
                        让 AI 批改<br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400">
                            严谨可见
                        </span>
                    </motion.h1>

                    <motion.p
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3, duration: 0.7 }}
                        className="text-lg text-gray-400 leading-relaxed max-w-xl"
                    >
                        拒绝黑盒。GradeOS 完整展示从文件接收、视觉识别、评分标准解析、并行批改到逻辑自查的每一个步骤。
                        专为追求极致准确率的教育场景打造。
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="flex flex-col sm:flex-row gap-4 pt-4"
                    >
                        <Link href={ctaHref} className="group relative px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 transition-all duration-300 overflow-hidden">
                            <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                            <span className="relative flex items-center gap-2 text-white font-medium">
                                立即体验
                                <ArrowRight size={18} />
                            </span>
                        </Link>
                        <a href="#features" className="px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white font-medium transition-colors">
                            查看架构详解
                        </a>
                    </motion.div>
                </div>

                {/* 右侧可视化 - 1:1 架构复刻 */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 1, delay: 0.2 }}
                    className="relative w-full aspect-[4/3] rounded-2xl bg-[#111116] border border-white/10 p-6 shadow-2xl overflow-hidden group"
                >
                    {/* 顶部状态栏 */}
                    <div className="flex items-center justify-between mb-8 border-b border-white/5 pb-4">
                        <div className="flex gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50" />
                            <div className="w-3 h-3 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
                            <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500/50" />
                        </div>
                        <div className="text-xs font-mono text-gray-500">SYSTEM_ARCHITECTURE_MAP</div>
                    </div>

                    {/* 节点网络 */}
                    <div className="relative h-full grid grid-cols-3 gap-6">
                        {WORKFLOW_NODES.map((node, index) => {
                            const isActive = index === activeNodeIndex;
                            const isProcessed = index < activeNodeIndex;

                            return (
                                <motion.div
                                    key={node.id}
                                    className={`relative z-10 flex flex-col items-center justify-center p-4 rounded-xl border transition-all duration-500 ${isActive
                                        ? `bg-white/5 border-${node.color.split('-')[1]}-500/50 shadow-[0_0_30px_-10px_rgba(var(--${node.color.split('-')[1]}-500-rgb),0.3)]`
                                        : isProcessed
                                            ? 'bg-white/5 border-white/10 opacity-50'
                                            : 'bg-transparent border-white/5 opacity-30'
                                        }`}
                                    animate={{
                                        scale: isActive ? 1.05 : 1,
                                    }}
                                >
                                    <div className={`p-3 rounded-lg mb-3 ${isActive ? node.bg : 'bg-white/5'} transition-colors duration-500`}>
                                        <node.icon className={`w-6 h-6 ${isActive ? node.color : 'text-gray-500'}`} />
                                    </div>
                                    <div className={`text-sm font-mono font-medium ${isActive ? 'text-white' : 'text-gray-500'}`}>
                                        {node.label}
                                    </div>

                                    {/* 高亮特性标记 */}
                                    {node.highlight && isActive && (
                                        <motion.div
                                            initial={{ opacity: 0, scale: 0.8, y: 10 }}
                                            animate={{ opacity: 1, scale: 1, y: 0 }}
                                            className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap px-3 py-1 rounded-full bg-white text-black text-xs font-bold shadow-[0_0_20px_rgba(255,255,255,0.3)] z-20"
                                        >
                                            {node.highlight}
                                        </motion.div>
                                    )}

                                    {/* 并行任务指示器 */}
                                    {node.isParallel && (
                                        <div className="absolute -right-2 -top-2 px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/30 text-[10px] text-amber-400 font-mono">
                                            x100
                                        </div>
                                    )}

                                    {/* 连接线动画 - 仅用于演示流转 */}
                                    {index < WORKFLOW_NODES.length - 1 && (
                                        <div className="absolute top-1/2 -right-8 w-6 h-[1px] bg-white/10 hidden md:block">
                                            {isActive && (
                                                <motion.div
                                                    className={`h-full w-full ${node.color.replace('text-', 'bg-')}`}
                                                    initial={{ x: '-100%' }}
                                                    animate={{ x: '100%' }}
                                                    transition={{ duration: 1.5, ease: "linear", repeat: Infinity }}
                                                />
                                            )}
                                        </div>
                                    )}
                                </motion.div>
                            );
                        })}

                        {/* 动态控制台输出 */}
                        <div className="absolute bottom-0 left-0 right-0 h-32 bg-black/50 backdrop-blur-md border-t border-white/10 p-4 font-mono text-xs overflow-hidden">
                            <div className="flex flex-col gap-1 text-gray-400">
                                {WORKFLOW_NODES.map((node, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{
                                            opacity: i === activeNodeIndex ? 1 : i < activeNodeIndex ? 0.4 : 0,
                                            x: i === activeNodeIndex ? 0 : i < activeNodeIndex ? 0 : -10
                                        }}
                                        className="flex gap-2"
                                    >
                                        <span className="text-gray-600">[{new Date().toLocaleTimeString()}]</span>
                                        <span className={node.color}>[INFO]</span>
                                        <span>Executing node: {node.id.toUpperCase()}...</span>
                                        {node.isParallel && <span className="text-amber-500">(Workers: 5)</span>}
                                    </motion.div>
                                ))}
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
