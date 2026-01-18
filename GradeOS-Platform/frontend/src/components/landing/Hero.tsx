'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';
import Link from 'next/link';

export default function Hero() {
    const { user } = useAuthStore();
    const isTeacher = user?.role === Role.Teacher || user?.role === Role.Admin;
    const ctaHref = user ? (isTeacher ? "/console" : "/student/dashboard") : "/login";

    const stats = [
        { value: '90s', label: '平均批改', detail: '50页批次' },
        { value: '3-8', label: '并行Worker', detail: '自动扩展' },
        { value: '98%', label: 'Rubric匹配', detail: '逐点引用' },
    ];

    const pipeline = [
        { label: 'Rubric Parse', detail: 'Streaming rules', tone: 'emerald' },
        { label: 'Worker Pool', detail: 'Batch x3 live', tone: 'azure' },
        { label: 'Consistency Check', detail: 'Confidence sync', tone: 'amber' },
    ];

    return (
        <section className="relative min-h-screen flex items-center px-4 pt-24 pb-16 overflow-hidden">
            <div className="absolute inset-0 pointer-events-none">
                <div className="landing-hero-glow landing-hero-glow-1" />
                <div className="landing-hero-glow landing-hero-glow-2" />
            </div>

            <div className="relative z-10 w-full max-w-7xl mx-auto grid lg:grid-cols-[1.05fr_0.95fr] gap-12 items-center">
                <div className="space-y-8">
                    <motion.div
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="landing-pill inline-flex items-center gap-3"
                    >
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        LIVE SYSTEM V3.0
                        <span className="landing-pill-muted">LATENCY 24MS</span>
                    </motion.div>

                    <motion.h1
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                        className="landing-display text-5xl md:text-7xl font-bold tracking-tight text-ink leading-[1.05]"
                    >
                        AI 批改，让反馈变成
                        <br />
                        <span className="landing-gradient-text">实时可视系统</span>
                    </motion.h1>

                    <motion.p
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3, duration: 0.7 }}
                        className="text-lg text-slate-600 leading-relaxed max-w-xl"
                    >
                        不只是打分，而是完整的批改控制台。你能看到每一次识别、每一次评分、
                        每一次修正的来龙去脉，并在关键节点快速介入。
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="flex flex-col sm:flex-row gap-4 items-center"
                    >
                        <Link href={ctaHref} className="landing-cta-primary group">
                            <span className="relative flex items-center gap-2">
                                立即体验
                                <ArrowRight size={18} />
                            </span>
                        </Link>
                        <a href="#workflow" className="landing-cta-secondary">
                            查看工作流
                        </a>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.6 }}
                        className="grid grid-cols-1 sm:grid-cols-3 gap-4"
                    >
                        {stats.map((item) => (
                            <div key={item.label} className="landing-metric">
                                <div className="text-2xl font-semibold text-ink">{item.value}</div>
                                <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{item.label}</div>
                                <div className="text-xs text-slate-500">{item.detail}</div>
                            </div>
                        ))}
                    </motion.div>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5, duration: 0.8 }}
                    className="relative"
                >
                    <div className="landing-panel">
                        <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.32em] text-slate-500">
                            <span>Control Plane</span>
                            <span className="text-slate-700">Workers 3/3</span>
                        </div>
                        <div className="mt-5 space-y-4">
                            {pipeline.map((item, index) => (
                                <div key={item.label} className="landing-pipeline">
                                    <div className="flex items-center justify-between text-xs text-slate-500">
                                        <span>{item.label}</span>
                                        <span className="text-slate-400">{item.detail}</span>
                                    </div>
                                    <div className="landing-pipeline-bar">
                                        <motion.span
                                            className={`landing-pipeline-fill landing-pipeline-${item.tone}`}
                                            initial={{ width: '20%' }}
                                            animate={{ width: ['20%', '85%', '45%'] }}
                                            transition={{
                                                delay: index * 0.2,
                                                duration: 4.5,
                                                repeat: Infinity,
                                                repeatType: 'mirror',
                                                ease: 'easeInOut'
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="mt-6 grid grid-cols-2 gap-3">
                            <div className="landing-chip">
                                <span className="text-xs text-slate-400">Queue</span>
                                <span className="text-sm text-slate-700 font-semibold">12 tasks</span>
                            </div>
                            <div className="landing-chip">
                                <span className="text-xs text-slate-400">Audit</span>
                                <span className="text-sm text-slate-700 font-semibold">99.1%</span>
                            </div>
                        </div>
                    </div>
                    <motion.div
                        className="landing-scan"
                        animate={{ y: ['-120%', '120%'] }}
                        transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
                    />
                    <motion.div
                        className="landing-orb"
                        animate={{ y: [0, -16, 0] }}
                        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
                    />
                </motion.div>
            </div>
        </section>
    );
}
