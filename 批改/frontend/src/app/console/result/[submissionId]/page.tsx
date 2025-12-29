'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { ArrowLeft, Share2, BookOpen, Trophy, CheckCircle, XCircle, ChevronDown, ChevronUp, Cpu, Sparkles, ScanLine, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';

// Types matching backend response
interface PageGradingResult {
    page_index: number;
    status: string;
    score: number;
    max_score: number;
    feedback: string;
    question_numbers?: string[];
    question_details?: Array<{
        question_id: string;
        score: number;
        max_score: number;
        feedback: string;
    }>;
}

interface StudentResult {
    student_key: string;
    start_page: number;
    end_page: number;
    total_score: number;
    max_total_score: number;
    page_results?: PageGradingResult[];
}

interface WorkerGroup {
    worker_id: string;
    batch_index: number;
    page_range: string;
    total_score: number;
    max_score: number;
    pages: PageGradingResult[];
}

interface BatchResults {
    status: string;
    total_pages?: number;
    grading_results?: PageGradingResult[];
    student_results?: StudentResult[];
    worker_groups?: WorkerGroup[];
    total_score?: number;
    max_total_score?: number;
}

export default function ResultPage() {
    const params = useParams();
    const router = useRouter();
    const submissionId = params.submissionId as string;

    const [result, setResult] = useState<BatchResults | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedStudent, setExpandedStudent] = useState<number | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const data = await api.getResults(submissionId);
                setResult(data);
            } catch (e: any) {
                console.error("Failed to fetch results", e);
                setError(e.message || 'Failed to load results');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [submissionId]);

    if (loading) return (
        <div className="flex h-screen items-center justify-center bg-transparent">
            <div className="flex flex-col items-center gap-4 text-cyan-400 font-mono">
                <Spinner className="w-8 h-8 text-cyan-400" />
                <p className="animate-pulse tracking-widest text-sm">LOADING REPORT DATA...</p>
            </div>
        </div>
    );

    if (error) return (
        <div className="flex h-screen items-center justify-center bg-transparent">
            <div className="text-center bg-slate-900/80 p-8 rounded-xl border border-red-500/30 backdrop-blur-md">
                <p className="text-red-400 mb-4 font-mono">{error}</p>
                <Button onClick={() => router.push('/console')} variant="destructive">Return to Console</Button>
            </div>
        </div>
    );

    const gradingResults = result?.grading_results || [];
    const studentResults = result?.student_results || [];
    const workerGroups = result?.worker_groups || [];

    const totalScore = result?.total_score || gradingResults.reduce((sum, r) => sum + (r.score || 0), 0);
    const maxScore = result?.max_total_score || gradingResults.reduce((sum, r) => sum + (r.max_score || 0), 0);
    const percentage = maxScore > 0 ? (totalScore / maxScore) * 100 : 0;

    return (
        <div className="min-h-screen text-slate-100 font-sans relative">

            {/* Header */}
            <motion.header
                initial={{ y: -50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-xl border-b border-white/5 px-6 py-4 shadow-lg"
            >
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => router.push('/console')} className="text-slate-400 hover:text-white">
                            <ArrowLeft size={20} />
                        </Button>
                        <div>
                            <h1 className="text-lg font-bold tracking-wide flex items-center gap-2">
                                <Activity className="text-cyan-400" size={18} />
                                GRADING REPORT
                            </h1>
                            <p className="text-xs text-slate-500 font-mono">ID: {submissionId.slice(0, 8)}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <Link href={`/console/student/${submissionId}`}>
                            <Button variant="outline" className="gap-2 border-white/10 bg-white/5 hover:bg-white/10 text-slate-200">
                                <BookOpen size={16} /> Student View
                            </Button>
                        </Link>
                        <Button className="gap-2 bg-cyan-600 hover:bg-cyan-500 text-white border-none shadow-[0_0_15px_rgba(8,145,178,0.4)]">
                            <Share2 size={16} /> Export Data
                        </Button>
                    </div>
                </div>
            </motion.header>

            <main className="max-w-7xl mx-auto px-6 py-8 relative z-10">

                {/* Score Overview Card */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="mb-8 rounded-3xl overflow-hidden relative border border-white/10 shadow-2xl"
                >
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-900/80 via-slate-900/90 to-purple-900/80 backdrop-blur-xl" />

                    <div className="relative p-8 px-12 text-white flex flex-col md:flex-row items-center justify-between gap-8">
                        <div>
                            <p className="text-blue-300 font-mono text-sm mb-1 tracking-widest uppercase">Total Assessment Score</p>
                            <div className="flex items-baseline gap-4">
                                <motion.span
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.2 }}
                                    className="text-7xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400"
                                >
                                    {totalScore}
                                </motion.span>
                                <span className="text-2xl text-slate-500 font-light">/ {maxScore}</span>
                            </div>
                            <div className="mt-4 flex items-center gap-4">
                                <div className="h-2 w-48 bg-slate-800 rounded-full overflow-hidden border border-white/5">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${percentage}%` }}
                                        transition={{ duration: 1.5, ease: "easeOut" }}
                                        className={cn("h-full rounded-full shadow-[0_0_10px_currentColor]", percentage >= 60 ? "bg-green-400 text-green-400" : "bg-orange-400 text-orange-400")}
                                    />
                                </div>
                                <span className="font-mono text-blue-200">{percentage.toFixed(1)}%</span>
                            </div>
                        </div>

                        <div className="flex gap-8">
                            <div className="text-center p-4 rounded-2xl bg-white/5 border border-white/5 backdrop-blur-sm min-w-[120px]">
                                <p className="text-3xl font-bold mb-1">{gradingResults.length}</p>
                                <p className="text-xs text-slate-400 uppercase tracking-widest font-mono">Pages Scanned</p>
                            </div>
                            <div className="text-center p-4 rounded-2xl bg-white/5 border border-white/5 backdrop-blur-sm min-w-[120px]">
                                <p className="text-3xl font-bold mb-1 text-green-400">{gradingResults.filter(r => r.status === 'completed').length}</p>
                                <p className="text-xs text-slate-400 uppercase tracking-widest font-mono">AI Validated</p>
                            </div>
                        </div>

                        <div className={cn(
                            "px-6 py-3 rounded-xl border backdrop-blur-md self-start md:self-center transform rotate-3",
                            percentage >= 60
                                ? "bg-green-500/10 border-green-500/30 text-green-400"
                                : "bg-orange-500/10 border-orange-500/30 text-orange-400"
                        )}>
                            <div className="font-bold tracking-wide flex items-center gap-2">
                                {percentage >= 60 ? <CheckCircle size={18} /> : <XCircle size={18} />}
                                {percentage >= 60 ? 'PASSED' : 'REVIEW NEEDED'}
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Worker Groups Visualization */}
                {workerGroups.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="mb-10"
                    >
                        <h2 className="text-sm font-bold flex items-center gap-2 mb-4 text-slate-400 font-mono tracking-widest uppercase">
                            <Cpu className="text-cyan-400" size={14} /> Processing Units
                        </h2>
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {workerGroups.map((group, idx) => (
                                <div key={idx} className="p-4 rounded-xl bg-slate-900/40 border border-white/5 border-l-2 border-l-cyan-500 relative overflow-hidden group hover:bg-slate-800/40 transition-colors">
                                    <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity">
                                        <Cpu size={48} />
                                    </div>
                                    <div className="flex items-center justify-between mb-3 relative z-10">
                                        <span className="font-mono text-xs bg-cyan-950/50 text-cyan-300 px-2 py-1 rounded border border-cyan-500/20">
                                            {group.worker_id}
                                        </span>
                                        <span className="text-xs text-slate-500 font-mono">
                                            PAGES {group.page_range}
                                        </span>
                                    </div>
                                    <div className="text-2xl font-bold text-white mb-1">
                                        {group.total_score} <span className="text-sm text-slate-500 font-normal">/ {group.max_score}</span>
                                    </div>
                                    <p className="text-xs text-slate-400 flex items-center gap-1">
                                        <CheckCircle size={10} className="text-green-500" />
                                        {group.pages?.length || 0} pages processed successfully
                                    </p>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* Detailed Results List */}
                <div className="space-y-6">
                    <h2 className="text-sm font-bold flex items-center gap-2 text-slate-400 font-mono tracking-widest uppercase">
                        {studentResults.length > 0 ? (
                            <><Trophy className="text-yellow-400" size={14} /> Student Leaderboard</>
                        ) : (
                            <><ScanLine className="text-purple-400" size={14} /> Page Analysis</>
                        )}
                    </h2>

                    {studentResults.length > 0 ? (
                        <div className="space-y-4">
                            {studentResults.map((student, idx) => {
                                const isExpanded = expandedStudent === idx;
                                const studentPct = student.max_total_score > 0
                                    ? (student.total_score / student.max_total_score) * 100
                                    : 0;

                                return (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.4 + idx * 0.05 }}
                                        className="rounded-xl overflow-hidden border border-white/5 bg-slate-900/60 backdrop-blur-sm hover:border-cyan-500/30 transition-all"
                                    >
                                        <div
                                            className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
                                            onClick={() => setExpandedStudent(isExpanded ? null : idx)}
                                        >
                                            <div className="flex items-center gap-4">
                                                <div className={cn(
                                                    "w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm border",
                                                    studentPct >= 60
                                                        ? "bg-green-500/10 border-green-500/20 text-green-400"
                                                        : "bg-red-500/10 border-red-500/20 text-red-400"
                                                )}>
                                                    #{idx + 1}
                                                </div>
                                                <div>
                                                    <p className="font-bold text-slate-200">{student.student_key || `Student ${idx + 1}`}</p>
                                                    <p className="text-xs text-slate-500 font-mono">
                                                        Pages {student.start_page + 1} - {student.end_page + 1}
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-6">
                                                <div className="text-right">
                                                    <span className="text-xl font-bold text-white block">{student.total_score}</span>
                                                    <span className="text-xs text-slate-500">of {student.max_total_score} pts</span>
                                                </div>
                                                {isExpanded ? <ChevronUp className="text-slate-500" /> : <ChevronDown className="text-slate-500" />}
                                            </div>
                                        </div>

                                        <AnimatePresence>
                                            {isExpanded && student.page_results && (
                                                <motion.div
                                                    initial={{ height: 0, opacity: 0 }}
                                                    animate={{ height: 'auto', opacity: 1 }}
                                                    exit={{ height: 0, opacity: 0 }}
                                                    className="border-t border-white/5 bg-black/20"
                                                >
                                                    <div className="p-4 space-y-2">
                                                        {student.page_results
                                                            .sort((a, b) => a.page_index - b.page_index)
                                                            .map((pg, pIdx) => (
                                                                <div key={pIdx} className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                                                                    <div className="flex items-center gap-3">
                                                                        {pg.status === 'completed' ? (
                                                                            <CheckCircle className="text-green-500" size={14} />
                                                                        ) : (
                                                                            <XCircle className="text-red-500" size={14} />
                                                                        )}
                                                                        <span className="text-sm font-medium text-slate-300">Page {pg.page_index + 1}</span>
                                                                        {pg.question_numbers && (
                                                                            <span className="text-xs text-slate-500 font-mono px-2 py-0.5 rounded bg-black/20">
                                                                                Q: {pg.question_numbers.join(', ')}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <span className="font-mono text-sm text-cyan-300">{pg.score} <span className="text-slate-600">/ {pg.max_score}</span></span>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </motion.div>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {gradingResults
                                .sort((a, b) => a.page_index - b.page_index)
                                .map((pg, idx) => (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.4 + idx * 0.05 }}
                                        className="p-5 rounded-xl bg-slate-900/60 border border-white/5 hover:border-cyan-500/30 transition-all group"
                                    >
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="flex items-center gap-3">
                                                <div className={cn(
                                                    "p-1.5 rounded-full",
                                                    pg.status === 'completed' ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
                                                )}>
                                                    {pg.status === 'completed' ? <CheckCircle size={18} /> : <XCircle size={18} />}
                                                </div>
                                                <div>
                                                    <p className="font-bold text-slate-200">Page {pg.page_index + 1}</p>
                                                    {pg.question_numbers && (
                                                        <p className="text-xs text-slate-500 font-mono mt-0.5">
                                                            Questions: {pg.question_numbers.join(', ')}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <span className="text-2xl font-bold text-white">{pg.score}</span>
                                                <span className="text-sm text-slate-500"> / {pg.max_score}</span>
                                            </div>
                                        </div>
                                        {pg.feedback && (
                                            <div className="mt-3 text-sm text-slate-300 bg-black/20 p-4 rounded-lg border border-white/5 font-light leading-relaxed">
                                                {pg.feedback}
                                            </div>
                                        )}
                                    </motion.div>
                                ))}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
