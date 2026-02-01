'use client';

import React from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, Zap, Activity, Cpu } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';
import Link from 'next/link';
import { TiltCard } from '@/components/ui/TiltCard';

export default function Hero() {
    const { user } = useAuthStore();
    const isTeacher = user?.role === Role.Teacher || user?.role === Role.Admin;
    const ctaHref = user ? (isTeacher ? "/console" : "/student/dashboard") : "/login";
    const { scrollY } = useScroll();
    const y1 = useTransform(scrollY, [0, 500], [0, 200]);
    const y2 = useTransform(scrollY, [0, 500], [0, -150]);

    const stats = [
        { value: '90s', label: '平均批改', detail: '50 pages', icon: Zap, color: 'text-yellow-400' },
        { value: '3-8', label: '并行Worker', detail: '自动扩展', icon: Cpu, color: 'text-cyan-400' },
        { value: '98%', label: 'Rubric匹配', detail: '逐点引用', icon: Activity, color: 'text-emerald-400' },
    ];

    const pipeline = [
        { label: 'Rubric Parse', detail: 'Streaming rules', tone: 'emerald' },
        { label: 'Worker Pool', detail: '3 live workers', tone: 'azure' },
        { label: 'Consistency Check', detail: 'Confidence sync', tone: 'amber' },
    ];

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.25, // Increased stagger for distinct "pop" steps
                delayChildren: 0.3
            }
        }
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 100, rotateX: -20, scale: 0.9 }, // Deeper starting point
        visible: {
            opacity: 1,
            y: 0,
            rotateX: 0,
            scale: 1,
            transition: { type: "spring", stiffness: 300, damping: 20 } as any // Bouncier spring
        }
    };

    return (
        <section className="relative min-h-screen flex items-center px-4 pt-24 pb-16 overflow-hidden perspective-1000">
            <motion.div style={{ y: y1 }} className="absolute inset-0 pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-blue-600/10 blur-[120px] rounded-full mix-blend-screen animate-pulse" />
                <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-purple-600/10 blur-[120px] rounded-full mix-blend-screen animate-pulse delay-1000" />
            </motion.div>

            <motion.div
                className="relative z-10 w-full max-w-7xl mx-auto grid lg:grid-cols-[1.05fr_0.95fr] gap-12 items-center"
                variants={containerVariants}
                initial="hidden"
                animate="visible"
            >
                <div className="space-y-8">
                    {/* 1. Title is the most important, but maybe pill first? Lets do Title Pop */}
                    <motion.div variants={itemVariants} className="landing-pill inline-flex items-center gap-3 backdrop-blur-md bg-white/50 border border-white/60 shadow-sm">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span className="font-mono text-xs font-bold tracking-widest text-emerald-800">LIVE SYSTEM V3.0</span>
                        <span className="landing-pill-muted border-l pl-3 border-gray-300">LATENCY 24MS</span>
                    </motion.div>

                    <motion.h1 variants={itemVariants} className="landing-display text-5xl md:text-7xl font-black tracking-tighter text-ink leading-[1.05] drop-shadow-sm origin-left">
                        AI 批改，让反馈变成
                        <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-violet-600 to-indigo-600 animate-gradient-x">
                            实时可视系统
                        </span>
                    </motion.h1>

                    <motion.p variants={itemVariants} className="text-lg text-slate-600 leading-relaxed max-w-xl font-medium origin-left">
                        不只是打分，而是完整的批改控制台。你能看到每一次识别、每一次评分、
                        每一次修正的来龙去脉，并在关键节点快速介入。
                    </motion.p>

                    <motion.div variants={itemVariants} className="flex flex-col sm:flex-row gap-4 items-center origin-left">
                        <Link href={ctaHref} className="landing-cta-primary group relative overflow-hidden">
                            <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                            <span className="relative flex items-center gap-2">
                                立即体验
                                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                            </span>
                        </Link>
                        <a href="#workflow" className="landing-cta-secondary group">
                            <span className="group-hover:text-blue-600 transition-colors">查看工作流</span>
                        </a>
                    </motion.div>

                    <motion.div variants={containerVariants} className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
                        {stats.map((item, i) => (
                            <motion.div
                                key={item.label}
                                variants={itemVariants}
                                whileHover={{ y: -5, scale: 1.05 }}
                                className="landing-metric bg-white/60 backdrop-blur-lg border border-white/50 shadow-lg p-4 rounded-2xl"
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <div className={`p-2 rounded-lg bg-gray-50 ${item.color.replace('text-', 'bg-').replace('400', '100')}`}>
                                        <item.icon className={`w-5 h-5 ${item.color}`} />
                                    </div>
                                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{item.label}</div>
                                </div>
                                <div className="text-3xl font-black text-slate-800 tracking-tight">{item.value}</div>
                                <div className="text-xs font-medium text-slate-500 mt-1">{item.detail}</div>
                            </motion.div>
                        ))}
                    </motion.div>
                </div>

                <motion.div variants={itemVariants} style={{ y: y2 }} className="relative perspective-1000">
                    <TiltCard className="w-full" scale={1.02}>
                        <div className="landing-panel bg-gray-900/95 backdrop-blur-xl border border-white/10 shadow-2xl text-white p-8 rounded-3xl relative overflow-hidden group">
                            {/* Decorative background grid */}
                            <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-20 pointer-events-none" />

                            <div className="relative z-10">
                                <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.32em] text-slate-400 mb-8">
                                    <div className="flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                        <span>Control Plane</span>
                                    </div>
                                    <span className="font-mono text-emerald-400">Workers 3/3</span>
                                </div>

                                <div className="space-y-6">
                                    {pipeline.map((item, index) => (
                                        <div key={item.label} className="landing-pipeline">
                                            <div className="flex items-center justify-between text-xs text-slate-300 mb-2 font-medium">
                                                <span>{item.label}</span>
                                                <span className="font-mono text-slate-500">{item.detail}</span>
                                            </div>
                                            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                                                <motion.div
                                                    className={`h-full rounded-full bg-gradient-to-r ${item.tone === 'emerald' ? 'from-emerald-500 to-teal-400' :
                                                        item.tone === 'azure' ? 'from-blue-500 to-cyan-400' :
                                                            'from-amber-500 to-orange-400'
                                                        }`}
                                                    initial={{ width: '0%' }}
                                                    animate={{ width: ['0%', '100%', '0%'] }}
                                                    transition={{
                                                        duration: 3 + index,
                                                        repeat: Infinity,
                                                        ease: "easeInOut",
                                                        delay: index * 0.5
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-8 grid grid-cols-2 gap-4">
                                    <div className="bg-white/5 rounded-xl p-4 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-colors">
                                        <span className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Queue</span>
                                        <div className="flex items-end justify-between">
                                            <span className="text-2xl font-bold font-mono">12</span>
                                            <span className="text-xs text-emerald-400 mb-1">▼ 4%</span>
                                        </div>
                                    </div>
                                    <div className="bg-white/5 rounded-xl p-4 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-colors">
                                        <span className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Audit</span>
                                        <div className="flex items-end justify-between">
                                            <span className="text-2xl font-bold font-mono">99.1%</span>
                                            <span className="text-xs text-emerald-400 mb-1">Pass</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Scanning beam effect */}
                            <motion.div
                                className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent"
                                animate={{ top: ['0%', '100%'] }}
                                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                                style={{ boxShadow: '0 0 20px rgba(16, 185, 129, 0.5)' }}
                            />
                        </div>
                    </TiltCard>

                    {/* Floating orbs */}
                    <motion.div
                        className="absolute -top-12 -right-12 w-24 h-24 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full blur-xl opacity-60 z-0"
                        animate={{ y: [0, 20, 0], scale: [1, 1.1, 1] }}
                        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
                    />
                    <motion.div
                        className="absolute -bottom-8 -left-8 w-32 h-32 bg-gradient-to-br from-emerald-500 to-cyan-600 rounded-full blur-xl opacity-40 z-0"
                        animate={{ y: [0, -30, 0], scale: [1, 1.2, 1] }}
                        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
                    />
                </motion.div>
            </motion.div>
        </section>
    );
}
