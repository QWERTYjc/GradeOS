'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useConsoleStore } from '@/store/consoleStore';
import { api } from '@/services/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Upload,
    Activity,
    CheckCircle,
    AlertCircle,
    X,
    Terminal,
    Minimize2,
    Loader2,
    FileText,
    Image as ImageIcon,
    Type,
    Trophy
} from 'lucide-react';
import clsx from 'clsx';

// Dynamic imports
const WorkflowGraph = dynamic(() => import('@/components/console/WorkflowGraph'), { ssr: false });
const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });

// --- Components ---

const Header = () => (
    <header className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
        <div className="bg-white/70 backdrop-blur-md border border-gray-200/50 px-6 py-3 rounded-full shadow-sm flex items-center gap-4">
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="font-semibold text-gray-800 tracking-tight">ANTIGRAVITY</span>
                <span className="text-gray-400 text-sm">CONSOLE</span>
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

        // If text input, convert to file
        if (inputType === 'text') {
            const blob = new Blob([textInput], { type: 'text/plain' });
            const file = new File([blob], 'submission.txt', { type: 'text/plain' });
            finalExamFiles = [file];
            addLog(`Converting text input to file...`, 'INFO');
        }

        addLog(`Starting upload: ${finalExamFiles.length} exams, ${rubricsFiles.length} rubrics`, 'INFO');

        try {
            // Real API call
            const submission = await api.createSubmission(finalExamFiles, rubricsFiles);
            addLog(`Upload complete. Submission ID: ${submission.id}`, 'SUCCESS');
            setSubmissionId(submission.id);

            // Transition to running state
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
        <div className="w-full max-w-3xl mx-auto space-y-6">
            {/* Input Type Switcher */}
            <div className="flex justify-center mb-8">
                <div className="bg-gray-100/80 p-1 rounded-full flex gap-1">
                    <button
                        onClick={() => setInputType('file')}
                        className={clsx(
                            "px-6 py-2 rounded-full text-sm font-medium transition-all flex items-center gap-2",
                            inputType === 'file' ? "bg-white text-black shadow-sm" : "text-gray-500 hover:text-gray-700"
                        )}
                    >
                        <ImageIcon size={16} />
                        File Upload
                    </button>
                    <button
                        onClick={() => setInputType('text')}
                        className={clsx(
                            "px-6 py-2 rounded-full text-sm font-medium transition-all flex items-center gap-2",
                            inputType === 'text' ? "bg-white text-black shadow-sm" : "text-gray-500 hover:text-gray-700"
                        )}
                    >
                        <Type size={16} />
                        Text Input
                    </button>
                </div>
            </div>

            <div className="bg-white/40 backdrop-blur-sm rounded-3xl border border-white/50 shadow-xl p-8">
                {inputType === 'file' ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Exam Upload */}
                        <div
                            className={clsx(
                                "relative group cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300 p-8 text-center bg-white/50 hover:bg-white/80",
                                isDragging ? "border-blue-500 bg-blue-50/50" : "border-gray-200 hover:border-blue-400"
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
                            <div className="flex flex-col items-center gap-3">
                                <div className="p-3 bg-blue-50 rounded-full text-blue-500 group-hover:scale-110 transition-transform">
                                    <Upload className="w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="font-medium text-gray-900">Exam Papers</h3>
                                    <p className="text-xs text-gray-500 mt-1">
                                        {examFiles.length > 0 ? (
                                            <span className="text-blue-600 font-semibold">{examFiles.length} files selected</span>
                                        ) : "PDF, Images, Text"}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Rubric Upload */}
                        <div
                            className={clsx(
                                "relative group cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300 p-8 text-center bg-white/50 hover:bg-white/80",
                                "border-gray-200 hover:border-green-400"
                            )}
                            onClick={() => rubricInputRef.current?.click()}
                        >
                            <input type="file" ref={rubricInputRef} className="hidden" multiple accept=".pdf,.md,.txt,.jpg,.png,.jpeg" onChange={(e) => e.target.files && setRubricsFiles(Array.from(e.target.files))} />
                            <div className="flex flex-col items-center gap-3">
                                <div className="p-3 bg-green-50 rounded-full text-green-500 group-hover:scale-110 transition-transform">
                                    <FileText className="w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="font-medium text-gray-900">Rubrics</h3>
                                    <p className="text-xs text-gray-500 mt-1">
                                        {rubricsFiles.length > 0 ? (
                                            <span className="text-green-600 font-semibold">{rubricsFiles.length} files selected</span>
                                        ) : "Optional (PDF/MD/Images)"}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="relative">
                            <textarea
                                value={textInput}
                                onChange={(e) => setTextInput(e.target.value)}
                                placeholder="Paste your text content here for grading..."
                                className="w-full h-64 p-4 rounded-xl border border-gray-200 bg-white/80 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono text-sm"
                            />
                            <div className="absolute bottom-4 right-4 text-xs text-gray-400">
                                {textInput.length} chars
                            </div>
                        </div>

                        {/* Rubric Upload for Text Mode */}
                        <div
                            className="flex items-center gap-4 p-4 rounded-xl border border-gray-200 bg-white/50 cursor-pointer hover:bg-white/80 transition-colors"
                            onClick={() => rubricInputRef.current?.click()}
                        >
                            <div className="p-2 bg-green-50 rounded-lg text-green-600">
                                <FileText size={20} />
                            </div>
                            <div className="flex-1">
                                <h4 className="text-sm font-medium text-gray-900">Attach Rubric (Optional)</h4>
                                <p className="text-xs text-gray-500">
                                    {rubricsFiles.length > 0 ? `${rubricsFiles.length} files attached` : "Click to upload PDF/MD/Image rubric"}
                                </p>
                            </div>
                            <input type="file" ref={rubricInputRef} className="hidden" multiple accept=".pdf,.md,.txt,.jpg,.png,.jpeg" onChange={(e) => e.target.files && setRubricsFiles(Array.from(e.target.files))} />
                        </div>
                    </div>
                )}

                <div className="flex justify-center mt-8">
                    <button
                        onClick={handleUpload}
                        disabled={inputType === 'file' ? examFiles.length === 0 : !textInput.trim()}
                        className={clsx(
                            "px-10 py-4 rounded-full font-medium transition-all flex items-center gap-2 shadow-lg hover:shadow-xl hover:-translate-y-0.5 text-lg",
                            (inputType === 'file' ? examFiles.length > 0 : textInput.trim())
                                ? "bg-black text-white hover:bg-gray-900"
                                : "bg-gray-200 text-gray-400 cursor-not-allowed"
                        )}
                    >
                        {inputType === 'file' && examFiles.length === 0 ? "Select Files" :
                            inputType === 'text' && !textInput.trim() ? "Enter Text" :
                                "Initialize Workflow"}
                    </button>
                </div>
            </div>
        </div>
    );
};

const NodeInspector = () => {
    const { selectedNodeId, selectedAgentId, workflowNodes, setSelectedNodeId, setSelectedAgentId } = useConsoleStore();

    // Find selected data
    const node = workflowNodes.find(n => n.id === selectedNodeId);
    const agent = workflowNodes
        .flatMap(n => n.children || [])
        .find(a => a.id === selectedAgentId);

    const activeItem = agent || node;
    const isOpen = !!activeItem;

    const closeInspector = () => {
        setSelectedNodeId(null);
        setSelectedAgentId(null);
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop - Reduced blur for performance */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={closeInspector}
                        className="fixed inset-0 bg-black/5 z-40 backdrop-blur-[2px]"
                    />

                    {/* Drawer */}
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="fixed right-0 top-0 bottom-0 w-[400px] bg-white/95 backdrop-blur-md border-l border-white/20 shadow-2xl z-50 p-6 overflow-y-auto"
                    >
                        <div className="flex items-center justify-between mb-8">
                            <div className="flex items-center gap-3">
                                {activeItem.status === 'completed' ? (
                                    <CheckCircle className="w-6 h-6 text-green-500" />
                                ) : activeItem.status === 'failed' ? (
                                    <AlertCircle className="w-6 h-6 text-red-500" />
                                ) : (
                                    <Activity className="w-6 h-6 text-blue-500 animate-pulse" />
                                )}
                                <div>
                                    <h2 className="text-xl font-bold text-gray-900">{activeItem.label}</h2>
                                    <p className="text-sm text-gray-500 uppercase tracking-wider">{activeItem.status}</p>
                                </div>
                            </div>
                            <button
                                onClick={closeInspector}
                                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                            >
                                <X className="w-5 h-5 text-gray-500" />
                            </button>
                        </div>

                        {/* Content based on type */}
                        <div className="space-y-6">
                            {/* Progress Bar */}
                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-gray-500">Progress</span>
                                    <span className="font-medium text-gray-900">
                                        {activeItem.status === 'completed' ? '100%' : 'Processing...'}
                                    </span>
                                </div>
                                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                    <motion.div
                                        className={clsx(
                                            "h-full rounded-full",
                                            activeItem.status === 'failed' ? "bg-red-500" : "bg-blue-500"
                                        )}
                                        initial={{ width: 0 }}
                                        animate={{ width: activeItem.status === 'completed' ? '100%' : '60%' }}
                                    />
                                </div>
                            </div>

                            {/* Agent Specific: Score */}
                            {'output' in activeItem && activeItem.output && (
                                <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                                    <h3 className="text-sm font-semibold text-blue-900 mb-1">Grading Result</h3>
                                    <div className="flex items-baseline gap-1">
                                        <span className="text-3xl font-bold text-blue-600">{activeItem.output.score}</span>
                                        <span className="text-sm text-blue-400">/ {activeItem.output.maxScore}</span>
                                    </div>
                                    {activeItem.output.feedback && (
                                        <p className="text-sm text-blue-800 mt-2 leading-relaxed">
                                            {activeItem.output.feedback}
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* Logs Preview */}
                            <div>
                                <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                    <Terminal className="w-4 h-4" /> Execution Log
                                </h3>
                                <div className="bg-gray-900 rounded-xl p-4 font-mono text-xs text-gray-300 max-h-[300px] overflow-y-auto">
                                    <div className="space-y-1">
                                        <div className="text-green-400">$ init process {activeItem.id}</div>
                                        <div className="text-gray-500">Loading context...</div>
                                        {'message' in activeItem && activeItem.message && (
                                            <div>{activeItem.message}</div>
                                        )}
                                        {'logs' in activeItem && activeItem.logs?.map((log, i) => (
                                            <div key={i} className="border-l-2 border-gray-700 pl-2 ml-1">{log}</div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};

const SystemLogsDrawer = () => {
    const { isMonitorOpen, toggleMonitor, logs } = useConsoleStore();
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, isMonitorOpen]);

    return (
        <AnimatePresence>
            {isMonitorOpen && (
                <motion.div
                    initial={{ y: '100%' }}
                    animate={{ y: 0 }}
                    exit={{ y: '100%' }}
                    transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                    className="fixed bottom-0 left-0 right-0 h-[300px] bg-gray-900/95 backdrop-blur-md border-t border-white/10 shadow-2xl z-40 flex flex-col"
                >
                    <div className="flex items-center justify-between px-6 py-3 border-b border-white/10 bg-black/20">
                        <div className="flex items-center gap-2 text-gray-100">
                            <Terminal className="w-4 h-4 text-blue-400" />
                            <span className="font-mono text-sm font-bold">SYSTEM MONITOR</span>
                        </div>
                        <button
                            onClick={toggleMonitor}
                            className="p-1 hover:bg-white/10 rounded text-gray-400 hover:text-white transition-colors"
                        >
                            <Minimize2 className="w-4 h-4" />
                        </button>
                    </div>

                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1.5">
                        {logs.length === 0 && (
                            <div className="text-gray-600 italic">System ready. Waiting for events...</div>
                        )}
                        {logs.map((log, i) => (
                            <div key={i} className="flex gap-3 hover:bg-white/5 p-0.5 rounded">
                                <span className="text-gray-500 shrink-0 select-none">
                                    {log.timestamp.split('T')[1].split('.')[0]}
                                </span>
                                <span className={clsx(
                                    "break-all",
                                    log.level === 'ERROR' ? 'text-red-400' :
                                        log.level === 'SUCCESS' ? 'text-green-400' :
                                            log.level === 'WARNING' ? 'text-yellow-400' :
                                                'text-gray-300'
                                )}>
                                    {log.message}
                                </span>
                            </div>
                        ))}
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

const FloatingMonitorButton = () => {
    const { toggleMonitor, isMonitorOpen } = useConsoleStore();

    return (
        <motion.button
            layout
            onClick={toggleMonitor}
            className={clsx(
                "fixed bottom-8 right-8 z-30 p-4 rounded-full shadow-lg border transition-all duration-300 flex items-center gap-2",
                isMonitorOpen
                    ? "bg-blue-500 border-blue-400 text-white translate-y-[300px] opacity-0"
                    : "bg-white border-gray-200 text-gray-700 hover:scale-105 hover:shadow-xl"
            )}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
        >
            <Activity className={clsx("w-5 h-5", !isMonitorOpen && "text-blue-500")} />
            <span className="font-medium pr-1">Real-time Monitor</span>
        </motion.button>
    );
};

export default function ConsolePage() {
    const { status, currentTab, reset, setCurrentTab } = useConsoleStore();

    return (
        <div className="min-h-screen w-full relative overflow-hidden">
            <Header />

            {/* Main Content Area - Centered */}
            <main className="relative z-10 w-full h-screen flex flex-col items-center justify-center">

                {/* Uploader - Only visible when IDLE */}
                <AnimatePresence>
                    {status === 'IDLE' && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9, y: -50 }}
                            className="w-full max-w-3xl px-6"
                        >
                            <div className="text-center mb-10">
                                <h1 className="text-4xl font-bold text-gray-900 mb-4 tracking-tight">
                                    Ready to Grade?
                                </h1>
                                <p className="text-gray-500 text-lg">
                                    Upload exam papers, images, or paste text to initialize the workflow.
                                </p>
                            </div>
                            <AdvancedUploader />
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Workflow Graph - Visible when Running/Completed */}
                <AnimatePresence>
                    {(status === 'RUNNING' || status === 'COMPLETED' || status === 'UPLOADING' || status === 'FAILED') && currentTab === 'process' && (
                        <motion.div
                            initial={{ opacity: 0, y: 50 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            className="w-full h-full flex items-center justify-center"
                        >
                            <WorkflowGraph />
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* View Results Button - Visible when Completed and in Process tab */}
                <AnimatePresence>
                    {status === 'COMPLETED' && currentTab === 'process' && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 20 }}
                            className="fixed bottom-24 left-1/2 -translate-x-1/2 z-30"
                        >
                            <button
                                onClick={() => setCurrentTab('results')}
                                className="px-8 py-3 bg-green-500 text-white rounded-full font-medium hover:bg-green-600 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 flex items-center gap-2"
                            >
                                <Trophy className="w-5 h-5" />
                                View Results
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Results View */}
                <AnimatePresence>
                    {currentTab === 'results' && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0 }}
                            className="w-full max-w-6xl px-6 py-20 h-full overflow-y-auto"
                        >
                            <div className="bg-white/60 backdrop-blur-md rounded-3xl border border-gray-200 shadow-xl overflow-hidden p-1 mb-8">
                                <ResultsView />
                            </div>
                            <div className="flex justify-center pb-10">
                                <button
                                    onClick={reset}
                                    className="px-8 py-3 bg-black text-white rounded-full font-medium hover:bg-gray-800 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                                >
                                    Start New Grading
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

            </main>

            {/* Drawers & Overlays */}
            <NodeInspector />
            <SystemLogsDrawer />
            <FloatingMonitorButton />

        </div>
    );
}
