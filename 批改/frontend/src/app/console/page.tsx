'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useConsoleStore } from '@/store/consoleStore';
import { api } from '@/services/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Upload,
    Activity,
    ImageIcon,
    Type,
    Trophy,
    Cpu,
    Sparkles,
    Zap,
    FileText
} from 'lucide-react';
import clsx from 'clsx';
import { useRouter } from 'next/navigation';

// Dynamic imports
const WorkflowMonitor = dynamic(() => import('@/components/flow/WorkflowMonitor').then(mod => mod.WorkflowMonitor), { ssr: false });

// --- Components ---

const Header = () => (
    <header className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
        <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 px-6 py-3 rounded-full shadow-[0_0_20px_rgba(0,0,0,0.5)] flex items-center gap-4">
            <div className="flex items-center gap-2">
                <div className="relative">
                    <div className="absolute inset-0 bg-cyan-500 blur-sm rounded-full opacity-50 animate-pulse" />
                    <div className="w-2.5 h-2.5 bg-cyan-400 rounded-full relative z-10" />
                </div>
                <span className="font-bold text-slate-200 tracking-wide font-mono">ANTIGRAVITY</span>
                <span className="text-cyan-500/50 text-xs tracking-widest font-mono border-l border-white/10 pl-2">CONSOLE V2</span>
            </div>
        </div>
    </header>
);

const AdvancedUploader = () => {
    const { setStatus, setSubmissionId, addLog, connectWs } = useConsoleStore();
    const [inputType, setInputType] = useState<'file' | 'text'>('file');
    const [isDragging, setIsDragging] = useState(false);
    const [rubricsFiles, setRubricsFiles] = useState<File[]>([]);
    const [examFiles, setExamFiles] = useState<File[]>([]);
    const [textInput, setTextInput] = useState('');
    const rubricInputRef = useRef<HTMLInputElement>(null);
    const examInputRef = useRef<HTMLInputElement>(null);

    const handleUpload = async () => {
        if (inputType === 'file' && examFiles.length === 0) return;
        if (inputType === 'text' && !textInput.trim()) return;

        setStatus('UPLOADING');

        let finalExamFiles = examFiles;

        if (inputType === 'text') {
            const blob = new Blob([textInput], { type: 'text/plain' });
            const file = new File([blob], 'submission.txt', { type: 'text/plain' });
            finalExamFiles = [file];
            addLog(`Converting text input to file...`, 'INFO');
        }

        addLog(`Starting upload: ${finalExamFiles.length} exams, ${rubricsFiles.length} rubrics`, 'INFO');

        try {
            const submission = await api.createSubmission(finalExamFiles, rubricsFiles);
            addLog(`Upload complete. Submission ID: ${submission.id}`, 'SUCCESS');
            setSubmissionId(submission.id);

            setTimeout(() => {
                setStatus('RUNNING');
                connectWs(submission.id);
            }, 500);

        } catch (error) {
            console.error(error);
            addLog(`Error: ${error instanceof Error ? error.message : 'Upload failed'}`, 'ERROR');
            setStatus('FAILED');
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto space-y-8">
            {/* Input Type Switcher */}
            <div className="flex justify-center mb-8">
                <div className="bg-slate-900/50 p-1 rounded-full flex gap-1 border border-white/5 backdrop-blur-sm">
                    <button
                        onClick={() => setInputType('file')}
                        className={clsx(
                            "px-8 py-2.5 rounded-full text-sm font-medium transition-all flex items-center gap-2",
                            inputType === 'file'
                                ? "bg-cyan-500/10 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.2)] border border-cyan-500/30"
                                : "text-slate-500 hover:text-slate-300"
                        )}
                    >
                        <ImageIcon size={16} />
                        File Upload
                    </button>
                    <button
                        onClick={() => setInputType('text')}
                        className={clsx(
                            "px-8 py-2.5 rounded-full text-sm font-medium transition-all flex items-center gap-2",
                            inputType === 'text'
                                ? "bg-cyan-500/10 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.2)] border border-cyan-500/30"
                                : "text-slate-500 hover:text-slate-300"
                        )}
                    >
                        <Type size={16} />
                        Direct Input
                    </button>
                </div>
            </div>

            <div className="glass-card rounded-3xl p-8 relative overflow-hidden group">
                {/* Glow Effect */}
                <div className="absolute -top-20 -right-20 w-64 h-64 bg-cyan-500/10 blur-[100px] rounded-full group-hover:bg-cyan-500/20 transition-all duration-700" />

                {inputType === 'file' ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                        {/* Exam Upload */}
                        <div
                            className={clsx(
                                "relative cursor-pointer overflow-hidden rounded-2xl border border-dashed transition-all duration-300 p-10 text-center group/card",
                                isDragging
                                    ? "border-cyan-500 bg-cyan-500/5"
                                    : "border-white/10 bg-black/20 hover:border-cyan-500/50 hover:bg-black/40"
                            )}
                            onClick={() => examInputRef.current?.click()}
                            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={(e) => {
                                e.preventDefault();
                                setIsDragging(false);
                                if (e.dataTransfer.files) setExamFiles(Array.from(e.dataTransfer.files));
                            }}
                        >
                            <input type="file" ref={examInputRef} className="hidden" multiple accept=".pdf,.jpg,.png,.txt,.md" onChange={(e) => e.target.files && setExamFiles(Array.from(e.target.files))} />
                            <div className="flex flex-col items-center gap-4">
                                <div className="p-4 bg-cyan-950/50 rounded-full text-cyan-400 border border-cyan-500/20 group-hover/card:scale-110 transition-transform shadow-[0_0_15px_rgba(6,182,212,0.15)]">
                                    <Upload className="w-8 h-8" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-slate-200 text-lg">Exam Papers</h3>
                                    <p className="text-xs text-slate-500 mt-2 font-mono">
                                        {examFiles.length > 0 ? (
                                            <span className="text-cyan-400 flex items-center gap-1 justify-center">
                                                <Sparkles size={12} /> {examFiles.length} SELECTED
                                            </span>
                                        ) : "DROP PDF / IMAGES"}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Rubric Upload */}
                        <div
                            className={clsx(
                                "relative cursor-pointer overflow-hidden rounded-2xl border border-dashed transition-all duration-300 p-10 text-center group/card",
                                "border-white/10 bg-black/20 hover:border-green-500/50 hover:bg-black/40"
                            )}
                            onClick={() => rubricInputRef.current?.click()}
                        >
                            <input type="file" ref={rubricInputRef} className="hidden" multiple accept=".pdf,.md,.txt,.jpg,.png,.jpeg" onChange={(e) => e.target.files && setRubricsFiles(Array.from(e.target.files))} />
                            <div className="flex flex-col items-center gap-4">
                                <div className="p-4 bg-green-950/50 rounded-full text-green-400 border border-green-500/20 group-hover/card:scale-110 transition-transform shadow-[0_0_15px_rgba(34,197,94,0.15)]">
                                    <FileText className="w-8 h-8" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-slate-200 text-lg">Rubrics</h3>
                                    <p className="text-xs text-slate-500 mt-2 font-mono">
                                        {rubricsFiles.length > 0 ? (
                                            <span className="text-green-400 flex items-center gap-1 justify-center">
                                                <Sparkles size={12} /> {rubricsFiles.length} SELECTED
                                            </span>
                                        ) : "OPTIONAL (PDF/MD)"}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4 relative z-10">
                        <div className="relative group/text">
                            <textarea
                                value={textInput}
                                onChange={(e) => setTextInput(e.target.value)}
                                placeholder="Paste content to verify..."
                                className="w-full h-64 p-6 rounded-2xl border border-white/10 bg-black/40 focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 resize-none font-mono text-sm text-slate-300 placeholder:text-slate-700 transition-all shadow-inner"
                            />
                            <div className="absolute bottom-4 right-4 text-xs font-mono text-slate-600 bg-black/40 px-2 py-1 rounded border border-white/5">
                                {textInput.length} CHARS
                            </div>
                        </div>

                        <div
                            className="flex items-center gap-4 p-4 rounded-xl border border-white/10 bg-black/20 cursor-pointer hover:bg-white/5 hover:border-green-500/30 transition-all"
                            onClick={() => rubricInputRef.current?.click()}
                        >
                            <div className="p-2 bg-green-900/20 rounded-lg text-green-500 border border-green-500/20">
                                <FileText size={20} />
                            </div>
                            <div className="flex-1">
                                <h4 className="text-sm font-bold text-slate-300">Attach Rubric Definition</h4>
                                <p className="text-xs text-slate-500 font-mono mt-0.5">
                                    {rubricsFiles.length > 0 ? `${rubricsFiles.length} FILES LINKED` : "CLICK TO UPLOAD"}
                                </p>
                            </div>
                            <input type="file" ref={rubricInputRef} className="hidden" multiple accept=".pdf,.md,.txt,.jpg,.png,.jpeg" onChange={(e) => e.target.files && setRubricsFiles(Array.from(e.target.files))} />
                        </div>
                    </div>
                )}

                <div className="flex justify-center mt-10 relative z-20">
                    <button
                        onClick={handleUpload}
                        disabled={inputType === 'file' ? examFiles.length === 0 : !textInput.trim()}
                        className={clsx(
                            "px-12 py-4 rounded-full font-bold tracking-wider transition-all flex items-center gap-3 text-sm shadow-2xl hover:-translate-y-1 relative overflow-hidden group",
                            (inputType === 'file' ? examFiles.length > 0 : textInput.trim())
                                ? "bg-cyan-500 hover:bg-cyan-400 text-black shadow-[0_0_30px_rgba(6,182,212,0.4)]"
                                : "bg-slate-800 text-slate-600 cursor-not-allowed border border-white/5"
                        )}
                    >
                        {(inputType === 'file' ? examFiles.length > 0 : textInput.trim()) && (
                            <div className="absolute inset-0 bg-white/20 -translate-x-full group-hover:animate-[shimmer_1s_infinite]" />
                        )}
                        <Zap size={18} className={clsx((inputType === 'file' ? examFiles.length > 0 : textInput.trim()) && "fill-current")} />
                        INITIALIZE SYSTEM
                    </button>
                </div>
            </div>
        </div>
    );
};

export default function ConsolePage() {
    const { status, submissionId } = useConsoleStore();
    const router = useRouter();

    return (
        <div className="min-h-screen w-full relative overflow-hidden text-slate-200 font-sans selection:bg-cyan-500/30">
            <Header />

            <main className="relative z-10 w-full h-screen flex flex-col items-center justify-center">

                {/* Initial Uploader State */}
                <AnimatePresence>
                    {status === 'IDLE' && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9, y: -50, filter: 'blur(10px)' }}
                            className="w-full max-w-4xl px-6"
                        >
                            <div className="text-center mb-12">
                                <motion.div
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-xs font-mono tracking-widest mb-6"
                                >
                                    <Sparkles size={12} /> AWAITING INPUT
                                </motion.div>
                                <h1 className="text-5xl md:text-6xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white via-slate-200 to-slate-500 mb-6 tracking-tight">
                                    Intelligent Grading
                                </h1>
                                <p className="text-slate-400 text-lg max-w-xl mx-auto font-light leading-relaxed">
                                    Upload assignments or rubric data to initialize the multi-agent grading workflow.
                                </p>
                            </div>
                            <AdvancedUploader />
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Workflow Monitor Overlay */}
                <AnimatePresence>
                    {(status === 'RUNNING' || status === 'COMPLETED' || status === 'UPLOADING' || status === 'FAILED') && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="w-full h-full absolute inset-0 z-40 bg-slate-950/90 backdrop-blur-xl"
                        >
                            <WorkflowMonitor runId={submissionId} />

                            {/* Success Action */}
                            {status === 'COMPLETED' && (
                                <motion.div
                                    initial={{ opacity: 0, y: 50 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="absolute bottom-10 left-1/2 -translate-x-1/2 z-50 w-full flex justify-center pointer-events-none"
                                >
                                    <button
                                        onClick={() => router.push(`/console/result/${submissionId}`)}
                                        className="pointer-events-auto px-10 py-4 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-full font-bold tracking-wide hover:brightness-110 transition-all shadow-[0_0_50px_rgba(6,182,212,0.5)] flex items-center gap-3 border border-white/20 group"
                                    >
                                        <Trophy className="w-5 h-5 group-hover:scale-110 transition-transform text-yellow-300 fill-current" />
                                        VIEW INTELLIGENCE REPORT
                                    </button>
                                </motion.div>
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>

            </main>
        </div>
    );
}
