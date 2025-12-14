'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useConsoleStore } from '@/store/consoleStore';
import { api } from '@/services/api';
import { Upload, Loader2, ArrowUpRight, CheckCircle2, AlertCircle, FileText, X } from 'lucide-react';
import clsx from 'clsx';

const WorkflowGraph = dynamic(() => import('@/components/console/WorkflowGraph'), { ssr: false });
const NodeInspector = dynamic(() => import('@/components/console/NodeInspector'), { ssr: false });

const AdvancedUploader = () => {
    const { setStatus, setSubmissionId, addLog, connectWs } = useConsoleStore();
    const [rubricsFiles, setRubricsFiles] = useState<File[]>([]);
    const [examFiles, setExamFiles] = useState<File[]>([]);

    const rubricInputRef = useRef<HTMLInputElement>(null);
    const examInputRef = useRef<HTMLInputElement>(null);

    const handleRubricChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setRubricsFiles(prev => [...prev, ...Array.from(e.target.files!)]);
        }
    };

    const handleExamChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setExamFiles(prev => [...prev, ...Array.from(e.target.files!)]);
        }
    };

    const removeRubric = (index: number) => {
        setRubricsFiles(prev => prev.filter((_, i) => i !== index));
    };

    const removeExam = (index: number) => {
        setExamFiles(prev => prev.filter((_, i) => i !== index));
    };

    const handleStart = async () => {
        if (examFiles.length === 0) return;

        setStatus('UPLOADING');
        addLog(`Starting upload: ${examFiles.length} exams, ${rubricsFiles.length} rubrics`);

        try {
            const submission = await api.createSubmission(examFiles, rubricsFiles);

            addLog(`Upload complete. Submission ID: ${submission.id}`);
            setSubmissionId(submission.id);
            setStatus('RUNNING');
            connectWs(submission.id);

        } catch (error) {
            console.error(error);
            addLog(`Error: ${error instanceof Error ? error.message : 'Upload failed'}`);
            setStatus('FAILED');
        }
    };

    return (
        <div className="bg-white/50 backdrop-blur-sm rounded-2xl border border-gray-200 p-8 shadow-sm">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                {/* Rubric Section */}
                <div className="space-y-4">
                    <h3 className="font-medium text-gray-900 flex items-center gap-2">
                        <FileText className="w-4 h-4 text-blue-600" />
                        Grading Standards
                    </h3>
                    <div
                        className="border border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-500 hover:bg-blue-50/30 transition-all cursor-pointer"
                        onClick={() => rubricInputRef.current?.click()}
                    >
                        <input
                            type="file"
                            ref={rubricInputRef}
                            className="hidden"
                            multiple
                            accept=".pdf,.md,.txt"
                            onChange={handleRubricChange}
                        />
                        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                        <p className="text-sm text-gray-500">Upload Rubrics (PDF, MD)</p>
                    </div>
                    {rubricsFiles.length > 0 && (
                        <div className="space-y-2 max-h-[150px] overflow-y-auto pr-2 scrollbar-thin">
                            {rubricsFiles.map((f, i) => (
                                <div key={i} className="flex justify-between items-center text-sm bg-white p-2 rounded border border-gray-100">
                                    <span className="truncate max-w-[200px]">{f.name}</span>
                                    <button onClick={(e) => { e.stopPropagation(); removeRubric(i); }} className="text-gray-400 hover:text-red-500">
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Exam Section */}
                <div className="space-y-4">
                    <h3 className="font-medium text-gray-900 flex items-center gap-2">
                        <FileText className="w-4 h-4 text-green-600" />
                        Exam Papers
                    </h3>
                    <div
                        className="border border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-green-500 hover:bg-green-50/30 transition-all cursor-pointer"
                        onClick={() => examInputRef.current?.click()}
                    >
                        <input
                            type="file"
                            ref={examInputRef}
                            className="hidden"
                            multiple
                            accept=".pdf,.jpg,.png,.jpeg"
                            onChange={handleExamChange}
                        />
                        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                        <p className="text-sm text-gray-500">Upload Exams (PDF, IMG)</p>
                    </div>
                    {examFiles.length > 0 && (
                        <div className="space-y-2 max-h-[150px] overflow-y-auto pr-2 scrollbar-thin">
                            {examFiles.map((f, i) => (
                                <div key={i} className="flex justify-between items-center text-sm bg-white p-2 rounded border border-gray-100">
                                    <span className="truncate max-w-[200px]">{f.name}</span>
                                    <button onClick={(e) => { e.stopPropagation(); removeExam(i); }} className="text-gray-400 hover:text-red-500">
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            <div className="flex justify-center">
                <button
                    onClick={handleStart}
                    disabled={examFiles.length === 0}
                    className={clsx(
                        "px-8 py-3 rounded-full font-medium transition-all flex items-center gap-2",
                        examFiles.length > 0
                            ? "bg-black text-white hover:bg-gray-800 hover:scale-105 shadow-lg"
                            : "bg-gray-200 text-gray-400 cursor-not-allowed"
                    )}
                >
                    Start Grading Workflow
                    <ArrowUpRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

export default function ConsolePage() {
    const { status, logs, setView, currentTab, setCurrentTab } = useConsoleStore();

    useEffect(() => {
        setView('CONSOLE');
    }, [setView]);

    // Dynamically import ResultsView
    const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });

    return (
        <div className="min-h-screen flex flex-col relative text-black">
            {/* Minimal Header */}
            <header className="h-16 border-b border-gray-100 flex items-center px-8 justify-between bg-white/80 backdrop-blur-md sticky top-0 z-50">
                <div className="flex items-center gap-2">
                    <span className="text-blue-600 font-bold text-xl">A</span>
                    <span className="font-medium text-gray-900">Console</span>
                </div>

                {/* Tab Switcher - only show when not IDLE */}
                {status !== 'IDLE' && (
                    <div className="flex items-center bg-gray-100 rounded-full p-1">
                        <button
                            onClick={() => setCurrentTab('process')}
                            className={clsx(
                                "px-4 py-1.5 text-sm font-medium rounded-full transition-all",
                                currentTab === 'process'
                                    ? "bg-white shadow-sm text-gray-900"
                                    : "text-gray-500 hover:text-gray-700"
                            )}
                        >
                            批改过程
                        </button>
                        <button
                            onClick={() => setCurrentTab('results')}
                            className={clsx(
                                "px-4 py-1.5 text-sm font-medium rounded-full transition-all",
                                currentTab === 'results'
                                    ? "bg-white shadow-sm text-gray-900"
                                    : "text-gray-500 hover:text-gray-700"
                            )}
                        >
                            批改结果
                        </button>
                    </div>
                )}

                <div className="flex items-center gap-4">
                    <div className="text-xs font-mono text-gray-400 uppercase tracking-wider">Status</div>
                    <div className={clsx("text-sm font-medium px-3 py-1 rounded-full flex items-center gap-2",
                        status === 'IDLE' ? "bg-gray-100 text-gray-600" :
                            status === 'RUNNING' || status === 'UPLOADING' ? "bg-blue-50 text-blue-600" :
                                status === 'COMPLETED' ? "bg-green-50 text-green-600" :
                                    "bg-red-50 text-red-600"
                    )}>
                        {status === 'RUNNING' && <Loader2 className="w-3 h-3 animate-spin" />}
                        {status === 'COMPLETED' && <CheckCircle2 className="w-3 h-3" />}
                        {status === 'FAILED' && <AlertCircle className="w-3 h-3" />}
                        {status}
                    </div>
                </div>
            </header>

            <main className="flex-1 container mx-auto px-4 py-8 flex flex-col gap-8 max-w-[1400px]">
                {status === 'IDLE' && (
                    <div className="max-w-4xl mx-auto w-full mt-20 animate-in fade-in slide-in-from-bottom-5 duration-700">
                        <AdvancedUploader />
                    </div>
                )}

                {(status === 'RUNNING' || status === 'COMPLETED' || status === 'UPLOADING' || status === 'FAILED') && (
                    <>
                        {/* Process View */}
                        {currentTab === 'process' && (
                            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-10 duration-500 flex-1 flex flex-col">
                                {/* Workflow Visualization - taller to show parallel agents */}
                                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden min-h-[280px] shrink-0">
                                    <WorkflowGraph />
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-[300px]">
                                    {/* Node Inspector (left 2/3) */}
                                    <div className="lg:col-span-2">
                                        <NodeInspector className="h-full" />
                                    </div>

                                    {/* Logs / Sidebar (right 1/3) */}
                                    <div className="bg-gray-50 rounded-2xl border border-gray-100 p-6 overflow-hidden flex flex-col h-full min-h-[300px]">
                                        <div className="mb-4 text-xs font-semibold text-gray-400 uppercase tracking-wider flex justify-between items-center">
                                            <span>System Activity</span>
                                            <span className="text-[10px] bg-gray-200 px-2 py-0.5 rounded-full text-gray-500">{logs.length} events</span>
                                        </div>
                                        <div className="flex-1 overflow-y-auto font-mono text-xs space-y-2 pr-2 scrollbar-thin scrollbar-thumb-gray-300">
                                            {logs.slice().reverse().map((log, i) => (
                                                <div key={i} className="text-gray-600 border-l-2 border-blue-200 pl-2 py-1">
                                                    {log}
                                                </div>
                                            ))}
                                            {logs.length === 0 && <span className="text-gray-400 italic">Waiting for events...</span>}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Results View */}
                        {currentTab === 'results' && (
                            <div className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden animate-in fade-in slide-in-from-right-10 duration-500">
                                <ResultsView />
                            </div>
                        )}
                    </>
                )}
            </main>
        </div>
    );
}

