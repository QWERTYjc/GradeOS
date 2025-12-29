'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { CheckCircle, XCircle, ArrowLeft, Loader2, Sparkles, Trophy, ScanLine } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface PageResult {
    page_index: number;
    status: string;
    score: number;
    max_score: number;
    feedback?: string;
    question_numbers?: string[];
}

interface BatchResults {
    batch_id: string;
    results?: any[];
    grading_results?: PageResult[];
    summary?: {
        total_pages: number;
        total_score: number;
    };
}

export default function StudentResultPage() {
    const { submissionId } = useParams();
    const router = useRouter();
    const [data, setData] = useState<BatchResults | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await api.getResults(submissionId as string);
                setData(res);
            } catch (e: any) {
                console.error("Failed to fetch student results", e);
                setError(e.message || 'Failed to load results');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [submissionId]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-transparent">
                <div className="flex flex-col items-center gap-4 text-cyan-400">
                    <Loader2 className="w-12 h-12 animate-spin drop-shadow-[0_0_10px_rgba(34,211,238,0.5)]" />
                    <p className="font-mono tracking-widest text-sm">ANALYZING SUBMISSION...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-transparent">
                <div className="text-center bg-slate-900/80 p-8 rounded-2xl border border-red-500/20 backdrop-blur-xl">
                    <p className="text-red-400 mb-4 font-mono">{error}</p>
                    <Button onClick={() => router.push('/console')} variant="destructive">RETURN TO CONSOLE</Button>
                </div>
            </div>
        );
    }

    // Calculate totals
    const gradingResults = data?.grading_results || [];
    const totalScore = gradingResults.reduce((sum, r) => sum + (r.score || 0), 0);
    const maxScore = gradingResults.reduce((sum, r) => sum + (r.max_score || 0), 0);
    const percentage = maxScore > 0 ? (totalScore / maxScore) * 100 : 0;

    return (
        <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 font-sans text-slate-100 relative overflow-hidden">
            {/* Background elements are handled globally now, but we add layout container */}

            <div className="max-w-3xl mx-auto space-y-8 relative z-10">

                {/* Navbar */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-between items-center"
                >
                    <Button
                        variant="ghost"
                        onClick={() => router.push('/console')}
                        className="text-slate-400 hover:text-white hover:bg-white/5"
                    >
                        <ArrowLeft className="mr-2" size={16} /> BACK
                    </Button>
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-500 px-3 py-1 rounded-full border border-white/5 bg-black/20">
                        <span>ID:</span>
                        <span className="text-slate-300">{(submissionId as string)?.slice(0, 8)}</span>
                    </div>
                </motion.div>

                {/* Score Card */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1 }}
                    className="relative rounded-3xl overflow-hidden border border-white/10 bg-slate-900/40 backdrop-blur-xl shadow-2xl"
                >
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-cyan-400 to-purple-500" />

                    <div className="p-8 sm:p-12 text-center relative">
                        {/* Decorative background glow */}
                        <div className="absolute inset-0 bg-blue-500/5 blur-3xl rounded-full transform -translate-y-1/2" />

                        <h1 className="text-2xl font-bold text-white mb-2 tracking-wide flex items-center justify-center gap-2">
                            <Sparkles className="text-yellow-400" size={20} /> ASSESSMENT COMPLETE
                        </h1>
                        <p className="text-slate-400 mb-8 font-mono text-sm">AI GRADING ANALYSIS</p>

                        <div className="relative inline-flex items-center justify-center mb-8">
                            <svg className="w-48 h-48 transform -rotate-90 drop-shadow-[0_0_15px_rgba(59,130,246,0.3)]">
                                <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-800" />
                                <motion.circle
                                    cx="96" cy="96" r="88"
                                    stroke="currentColor" strokeWidth="8" fill="transparent"
                                    strokeDasharray={552}
                                    strokeDashoffset={552}
                                    animate={{ strokeDashoffset: 552 - (552 * percentage) / 100 }}
                                    transition={{ duration: 1.5, ease: "easeOut", delay: 0.5 }}
                                    className={percentage >= 60 ? "text-cyan-400" : "text-orange-400"}
                                    strokeLinecap="round"
                                />
                            </svg>
                            <div className="absolute flex flex-col items-center">
                                <motion.span
                                    initial={{ opacity: 0, scale: 0.5 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    transition={{ delay: 0.8 }}
                                    className="text-5xl font-black text-white tracking-tighter"
                                >
                                    {totalScore}
                                </motion.span>
                                <span className="text-slate-500 font-medium text-sm border-t border-slate-700 px-4 pt-1 mt-1">/ {maxScore} PTS</span>
                            </div>
                        </div>

                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 1 }}
                            className={cn(
                                "inline-flex items-center gap-2 px-6 py-2 rounded-full border backdrop-blur-md",
                                percentage >= 60
                                    ? "bg-green-500/10 border-green-500/20 text-green-400"
                                    : "bg-orange-500/10 border-orange-500/20 text-orange-400"
                            )}
                        >
                            {percentage >= 60 ? <Trophy size={16} /> : <Sparkles size={16} />}
                            <span className="font-bold tracking-wide">{percentage >= 60 ? "EXCELLENT PERFORMANCE" : "NEEDS IMPROVEMENT"}</span>
                        </motion.div>
                    </div>
                </motion.div>

                {/* Page Breakdown */}
                <div className="space-y-4">
                    <h2 className="text-lg font-bold text-slate-200 px-2 flex items-center gap-2">
                        <ScanLine size={18} className="text-cyan-400" />
                        PAGE BREAKDOWN
                    </h2>

                    {gradingResults.length > 0 ? (
                        gradingResults
                            .sort((a, b) => a.page_index - b.page_index)
                            .map((pg, i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.2 + (i * 0.1) }}
                                    className="bg-slate-900/40 backdrop-blur-md rounded-2xl p-6 border border-white/5 hover:border-cyan-500/30 transition-all hover:bg-slate-800/40 group shadow-lg"
                                >
                                    <div className="flex justify-between items-start mb-4">
                                        <div className="flex items-center gap-4">
                                            <div className={cn(
                                                "p-2 rounded-full bg-black/30 border",
                                                pg.status === 'completed' ? "border-green-500/30 text-green-400" : "border-red-500/30 text-red-400"
                                            )}>
                                                {pg.status === 'completed' ? <CheckCircle size={20} /> : <XCircle size={20} />}
                                            </div>
                                            <div>
                                                <span className="font-bold text-lg text-white block">PAGE {pg.page_index + 1}</span>
                                                {pg.question_numbers && pg.question_numbers.length > 0 && (
                                                    <span className="text-xs text-slate-500 font-mono">
                                                        Q: {pg.question_numbers.join(', ')}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <span className="font-mono font-bold bg-white/5 border border-white/10 px-4 py-1.5 rounded-lg text-cyan-300">
                                            {pg.score} <span className="text-slate-500 text-xs">/ {pg.max_score}</span>
                                        </span>
                                    </div>
                                    {pg.feedback && (
                                        <div className="bg-black/20 p-4 rounded-xl text-slate-300 text-sm leading-relaxed border border-white/5 font-light">
                                            {pg.feedback}
                                        </div>
                                    )}
                                </motion.div>
                            ))
                    ) : (
                        <div className="bg-slate-900/40 rounded-2xl p-12 text-center text-slate-600 border border-white/5 border-dashed">
                            NO GRADING DATA AVAILABLE
                        </div>
                    )}
                </div>

                <div className="text-center pt-12 pb-8 text-slate-600 font-mono text-xs tracking-widest uppercase">
                    Antigravity GradeOS System V2.0
                </div>

            </div>
        </div>
    );
}
