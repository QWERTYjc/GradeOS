'use client';

import React, { useEffect, useState, useContext } from 'react';
import dynamic from 'next/dynamic';
import { useConsoleStore } from '@/store/consoleStore';
import { useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Space_Grotesk, Unbounded } from 'next/font/google';
import {
    Images,
    ScanLine,
    Trophy
} from 'lucide-react';
import clsx from 'clsx';
import { AppContext } from '@/components/bookscan/AppContext';
import Scanner from '@/components/bookscan/Scanner';
import Gallery from '@/components/bookscan/Gallery';
import { ScannedImage, Session } from '@/components/bookscan/types';
import { api } from '@/services/api';

// Dynamic imports
const WorkflowGraph = dynamic(() => import('@/components/console/WorkflowGraph'), { ssr: false });
const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });
const LLMThoughtsPanel = dynamic(() => import('@/components/console/LLMThoughtsPanel'), { ssr: false });
const ReviewOverlay = dynamic(() => import('@/components/console/ReviewOverlay'), { ssr: false });

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-space' });
const unbounded = Unbounded({ subsets: ['latin'], variable: '--font-display' });

// --- Components ---

type ScanTab = 'scan' | 'gallery';

interface HeaderProps {
    count: number;
}

const Header = ({ count }: HeaderProps) => (
    <header className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
        <div className="bg-white/70 backdrop-blur-md border border-gray-200/50 px-6 py-3 rounded-full shadow-sm flex items-center gap-4">
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="font-semibold text-gray-800 tracking-tight console-display console-shimmer">ANTIGRAVITY</span>
                <span className="text-gray-400 text-sm">CONSOLE</span>
            </div>
            {count > 0 && (
                <div className="flex items-center gap-2 pl-4 border-l border-gray-200">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Images</span>
                    <span className="text-sm font-bold text-slate-800">{count}</span>
                </div>
            )}
        </div>
    </header>
);

const dataUrlToFile = (dataUrl: string, filename: string): File => {
    const [meta, base64] = dataUrl.split(',');
    const match = meta.match(/:(.*?);/);
    const mime = match ? match[1] : 'image/jpeg';
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new File([bytes], filename, { type: mime });
};

// --- Components ---

type ScanViewMode = 'exams' | 'rubrics';
// Original ScanTab is now used for "List vs Scanner" toggle within the view

interface ScannerContainerProps {
    activeTab: ScanTab;
    onTabChange: (tab: ScanTab) => void;

    // Config
    examSessionId: string | null;
    rubricSessionId: string | null;

    // Actions
    onSubmitBatch: (images: ScannedImage[], boundaries: number[]) => Promise<void>;
    interactionEnabled: boolean;
    onInteractionToggle: (enabled: boolean) => void;
    gradingMode: string;
    onGradingModeChange: (mode: string) => void;

    // 班级批改模式下的学生映射
    studentNameMapping?: Array<{ studentId: string; studentName: string; startIndex: number; endIndex: number }>;
}

const ScannerContainer = ({
    activeTab,
    onTabChange,
    examSessionId,
    rubricSessionId,
    onSubmitBatch,
    interactionEnabled,
    onInteractionToggle,
    gradingMode,
    onGradingModeChange,
    studentNameMapping = []
}: ScannerContainerProps) => {
    const { setCurrentSessionId, sessions } = useContext(AppContext)!;
    const [viewMode, setViewMode] = useState<ScanViewMode>('exams');
    const [studentBoundaries, setStudentBoundaries] = useState<number[]>([]);

    console.log('ScannerContainer Render:', { viewMode, hasHandler: !!onSubmitBatch });

    useEffect(() => {
        if (viewMode === 'exams' && examSessionId) {
            setCurrentSessionId(examSessionId);
        } else if (viewMode === 'rubrics' && rubricSessionId) {
            setCurrentSessionId(rubricSessionId);
        }
    }, [viewMode, examSessionId, rubricSessionId, setCurrentSessionId]);

    const currentSession = sessions.find(s => s.id === (viewMode === 'exams' ? examSessionId : rubricSessionId));
    const imageCount = currentSession?.images.length || 0;

    const handleSubmit = async (images: ScannedImage[]) => {
        await onSubmitBatch(images, studentBoundaries);
    };

    return (
        <div className="h-full w-full flex flex-col bg-[#F5F7FB]">
            {/* Top Bar: View Switcher & Scan/Preview Toggle - Centered Layout */}
            <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-100 shadow-sm relative z-20">

                {/* Left: Placeholder for balance or back button if needed */}
                <div className="w-[200px]"></div>

                {/* Center: View Mode Switcher */}
                <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex bg-slate-100 p-1 rounded-lg">
                    <button
                        onClick={() => setViewMode('exams')}
                        className={clsx(
                            "px-6 py-1.5 rounded-md text-sm font-bold transition-all min-w-[140px]",
                            viewMode === 'exams'
                                ? "bg-white text-blue-600 shadow-sm ring-1 ring-black/5"
                                : "text-slate-500 hover:text-slate-700"
                        )}
                    >
                        Student Exams
                    </button>
                    <button
                        onClick={() => setViewMode('rubrics')}
                        className={clsx(
                            "px-6 py-1.5 rounded-md text-sm font-bold transition-all min-w-[140px]",
                            viewMode === 'rubrics'
                                ? "bg-white text-purple-600 shadow-sm ring-1 ring-black/5"
                                : "text-slate-500 hover:text-slate-700"
                        )}
                    >
                        Rubric / Standards
                    </button>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 w-[200px] justify-end">
                    <button
                        onClick={() => onTabChange('scan')}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold border transition",
                            activeTab === 'scan'
                                ? "bg-gray-800 text-white border-gray-800 shadow"
                                : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
                        )}
                    >
                        <ScanLine className="h-3.5 w-3.5" />
                        Capture
                    </button>
                    <button
                        onClick={() => onTabChange('gallery')}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold border transition",
                            activeTab === 'gallery'
                                ? "bg-gray-800 text-white border-gray-800 shadow"
                                : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
                        )}
                    >
                        <Images className="h-3.5 w-3.5" />
                        Review ({imageCount})
                    </button>
                </div>
            </div>

            {/* Content Content - Re-mount on view change to reset gallery state if needed */}
            <div className="flex-1 min-h-0 bg-white">
                {activeTab === 'scan' ? (
                    <Scanner />
                ) : (
                    <Gallery
                        key={viewMode} // Force re-mount when switching modes
                        session={currentSession} // Direct pass to avoid context lag
                        onSubmitBatch={handleSubmit}
                        submitLabel={viewMode === 'exams' ? "Start Grading" : undefined}
                        onBoundariesChange={viewMode === 'exams' ? setStudentBoundaries : undefined}
                        isRubricMode={viewMode === 'rubrics'}
                        studentNameMapping={viewMode === 'exams' ? studentNameMapping : undefined}
                        interactionEnabled={interactionEnabled}
                        onInteractionToggle={onInteractionToggle}
                        gradingMode={gradingMode}
                        onGradingModeChange={onGradingModeChange}
                    />
                )}
            </div>
        </div>
    );
};

export default function ConsolePage() {
    const status = useConsoleStore((state) => state.status);
    const reset = useConsoleStore((state) => state.reset);
    const selectedAgentId = useConsoleStore((state) => state.selectedAgentId);
    const selectedNodeId = useConsoleStore((state) => state.selectedNodeId);
    const setSelectedNodeId = useConsoleStore((state) => state.setSelectedNodeId);
    const interactionEnabled = useConsoleStore((state) => state.interactionEnabled);
    const setInteractionEnabled = useConsoleStore((state) => state.setInteractionEnabled);
    const gradingMode = useConsoleStore((state) => state.gradingMode);
    const setGradingMode = useConsoleStore((state) => state.setGradingMode);

    // Initial Sessions State
    const [sessions, setSessions] = useState<Session[]>([]);
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

    // Permanent sessions for isolation
    const [examSessionId, setExamSessionId] = useState<string | null>(null);
    const [rubricSessionId, setRubricSessionId] = useState<string | null>(null);

    // Global Split State
    const [splitImageIds, setSplitImageIds] = useState<Set<string>>(new Set());

    const [activeTab, setActiveTab] = useState<ScanTab>('scan'); // Sub-tab for ScannerContainer

    // Used for Workflow view
    const [currentTab, setCurrentTab] = useState<'process' | 'results'>('process');
    const [isStreamOpen, setIsStreamOpen] = useState(false);

    useEffect(() => {
        if (selectedAgentId || selectedNodeId) {
            setIsStreamOpen(true);
            return;
        }
        setIsStreamOpen(false);
    }, [selectedAgentId, selectedNodeId]);

    const handleStreamClose = () => {
        setIsStreamOpen(false);
        setSelectedNodeId(null);
    };

    // Create default sessions on mount
    useEffect(() => {
        // Create only if empty to preserve state across remounts (if any)
        // In this implementation state is local to Page, so on refresh it resets.
        // We initialize two distinct sessions.
        const examId = 'session-exams';
        const rubricId = 'session-rubrics';

        const initialSessions: Session[] = [
            { id: examId, name: 'Student Exams', images: [], createdAt: Date.now() },
            { id: rubricId, name: 'Rubrics', images: [], createdAt: Date.now() }
        ];

        setSessions(initialSessions);
        setExamSessionId(examId);
        setRubricSessionId(rubricId);
        setCurrentSessionId(examId); // Default to exams
    }, []);

    // Parse classId and homeworkId from URL params for class-based grading
    const searchParams = useSearchParams();
    useEffect(() => {
        const classId = searchParams.get('classId');
        const homeworkId = searchParams.get('homeworkId');

        if (classId && homeworkId) {
            // Store class context
            useConsoleStore.getState().setClassContext({
                classId,
                homeworkId,
            });

            // Fetch class homework data from backend and populate Gallery
            api.getSubmissionsForGrading(classId, homeworkId).then(data => {
                // Update class context with names and students
                useConsoleStore.getState().setClassContext({
                    className: data.class_name,
                    homeworkName: data.homework_name,
                    students: data.students.map(s => ({
                        id: s.student_id,
                        name: s.student_name,
                    })),
                });

                // Auto-populate images and student boundaries
                const allImages: ScannedImage[] = [];
                const studentMapping: Array<{ studentId: string; studentName: string; startIndex: number; endIndex: number }> = [];
                const newSplitIds = new Set<string>();

                let currentIndex = 0;
                for (const student of data.students) {
                    const startIndex = currentIndex;

                    for (const imageData of student.images) {
                        const imageId = `class-img-${crypto.randomUUID()}`;
                        allImages.push({
                            id: imageId,
                            url: imageData, // base64 or URL
                            name: `${student.student_name}_page${currentIndex - startIndex + 1}.jpg`,
                            timestamp: Date.now(),
                        });

                        // Mark first image of each student (except first) as SPLIT point
                        if (currentIndex > 0 && currentIndex === startIndex) {
                            newSplitIds.add(imageId);
                        }

                        currentIndex++;
                    }

                    studentMapping.push({
                        studentId: student.student_id,
                        studentName: student.student_name,
                        startIndex,
                        endIndex: currentIndex - 1,
                    });
                }

                // Update exam session with the images
                if (examSessionId) {
                    setSessions(prev => prev.map(s => {
                        if (s.id === examSessionId) {
                            return { ...s, images: allImages };
                        }
                        return s;
                    }));
                }

                // Set split points
                setSplitImageIds(newSplitIds);

                // Store student mapping
                useConsoleStore.getState().setClassContext({
                    studentImageMapping: studentMapping,
                });

                console.log(`Loaded ${allImages.length} images for ${data.students.length} students`);
            }).catch(err => {
                console.error('Failed to load class submissions:', err);
            });

            console.log(`Class grading mode: classId=${classId}, homeworkId=${homeworkId}`);
        }

        return () => {
            // Clear class context when leaving the page
            useConsoleStore.getState().clearClassContext();
        };
    }, [searchParams, examSessionId]);

    useEffect(() => {
        const batchId = searchParams.get('batchId');
        if (!batchId) {
            return;
        }
        useConsoleStore.getState().setSubmissionId(batchId);
        useConsoleStore.getState().connectWs(batchId);
        useConsoleStore.getState().setStatus('RUNNING');
    }, [searchParams]);

    // Provider Methods
    const createNewSession = (name?: string) => {
        const newSession: Session = {
            id: crypto.randomUUID(),
            name: name || `Session ${sessions.length + 1}`,
            images: [],
            createdAt: Date.now(),
        };
        setSessions(prev => [...prev, newSession]);
        setCurrentSessionId(newSession.id);
    };

    const deleteSession = (id: string) => {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (currentSessionId === id && sessions.length > 0) {
            setCurrentSessionId(sessions[0].id);
        } else {
            setCurrentSessionId(null);
        }
    };

    const addImageToSession = (img: ScannedImage) => {
        if (!currentSessionId) return;
        setSessions(prev => prev.map(s => {
            if (s.id === currentSessionId) {
                return { ...s, images: [...s.images, img] };
            }
            return s;
        }));
    };

    const addImagesToSession = (newImgs: ScannedImage[]) => {
        if (!currentSessionId) return;
        setSessions(prev => prev.map(s => {
            if (s.id === currentSessionId) {
                return { ...s, images: [...s.images, ...newImgs] };
            }
            return s;
        }));
    };

    const deleteImages = (sessionId: string, imageIds: string[]) => {
        setSessions(prev => prev.map(s => {
            if (s.id === sessionId) {
                return { ...s, images: s.images.filter(img => !imageIds.includes(img.id)) };
            }
            return s;
        }));

        // 🔥 同步清理 splitImageIds，避免学生边界数据不一致
        setSplitImageIds(prev => {
            const newSet = new Set(prev);
            imageIds.forEach(id => newSet.delete(id));
            return newSet;
        });
    };

    const updateImage = (sessionId: string, imageId: string, newUrl: string, isOptimizing?: boolean) => {
        setSessions(prev => prev.map(s => {
            if (s.id === sessionId) {
                return {
                    ...s,
                    images: s.images.map(img => img.id === imageId ? { ...img, url: newUrl, isOptimizing: isOptimizing ?? img.isOptimizing } : img)
                };
            }
            return s;
        }));
    };

    const reorderImages = (sessionId: string, fromIndex: number, toIndex: number) => {
        setSessions(prev => prev.map(s => {
            if (s.id === sessionId) {
                const newImages = [...s.images];
                const [moved] = newImages.splice(fromIndex, 1);
                newImages.splice(toIndex, 0, moved);
                return { ...s, images: newImages };
            }
            return s;
        }));
    };

    // New: Split Management
    const markImageAsSplit = (imageId: string) => {
        const newSet = new Set(splitImageIds);
        if (newSet.has(imageId)) newSet.delete(imageId);
        else newSet.add(imageId);
        setSplitImageIds(newSet);
    };

    const contextValue = {
        sessions,
        currentSessionId,
        createNewSession,
        addImageToSession,
        addImagesToSession,
        deleteSession,
        deleteImages,
        setCurrentSessionId,
        updateImage,
        reorderImages,
        splitImageIds,
        markImageAsSplit
    };

    // Prepare Header Count
    const activeSession = sessions.find(s => s.id === currentSessionId);

    // Batch Submission
    const handleSubmitBatch = async (images: ScannedImage[], boundaries: number[]) => {
        try {
            const rubricSession = sessions.find(s => s.id === rubricSessionId);
            if (!rubricSession || rubricSession.images.length === 0) {
                // warning logic if needed
            }

            useConsoleStore.getState().setStatus('UPLOADING');

            const examFiles = images.map(img => dataUrlToFile(img.url, img.name));
            const rubricFiles = rubricSession ? rubricSession.images.map(img => dataUrlToFile(img.url, img.name)) : [];

            // 获取班级批改上下文（如果存在）
            const { classContext } = useConsoleStore.getState();
            const classContextPayload = classContext.classId ? {
                classId: classContext.classId,
                homeworkId: classContext.homeworkId || undefined,
                studentMapping: classContext.studentImageMapping,
            } : undefined;

            // 2. Upload to backend with optional class context
            const response = await api.createSubmission(
                examFiles,
                rubricFiles,
                boundaries,
                undefined,
                classContextPayload,
                interactionEnabled,
                gradingMode
            );

            useConsoleStore.getState().setSubmissionId(response.id);
            useConsoleStore.getState().connectWs(response.id);
            useConsoleStore.getState().setStatus('RUNNING');

        } catch (error) {
            console.error("Batch upload failed", error);
            useConsoleStore.getState().setStatus('FAILED');
        }
    };

    return (
        <AppContext.Provider value={contextValue}>
            <div className={clsx(
                spaceGrotesk.variable,
                unbounded.variable,
                "min-h-screen w-full relative overflow-hidden console-shell"
            )}>
                <div className="pointer-events-none absolute inset-0 console-aurora" />
                <div className="pointer-events-none absolute inset-0 console-grid" />
                <div className="pointer-events-none absolute -top-32 -left-24 w-[320px] h-[320px] console-orb orb-1" />
                <div className="pointer-events-none absolute top-24 right-[-120px] w-[260px] h-[260px] console-orb orb-2" />
                <div className="pointer-events-none absolute bottom-[-140px] left-1/3 w-[360px] h-[360px] console-orb orb-3" />

                <Header count={activeSession?.images.length || 0} />

                {/* Main Content Area - Centered */}
                <main className="relative z-10 w-full h-screen flex flex-col items-center justify-center">

                    {/* Scanner/Uploader - Only visible when IDLE */}
                    <AnimatePresence mode="wait">
                        {status === 'IDLE' && (
                            <motion.div
                                key="idle-view"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95, y: -30 }}
                                className="w-full h-full pt-20"
                            >
                                <ScannerContainer
                                    activeTab={activeTab}
                                    onTabChange={setActiveTab}
                                    examSessionId={examSessionId}
                                    rubricSessionId={rubricSessionId}
                                    onSubmitBatch={handleSubmitBatch}
                                    interactionEnabled={interactionEnabled}
                                    onInteractionToggle={setInteractionEnabled}
                                    gradingMode={gradingMode}
                                    onGradingModeChange={setGradingMode}
                                    studentNameMapping={useConsoleStore.getState().classContext.studentImageMapping}
                                />
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Workflow Graph - Visible when Running/Completed */}
                    <AnimatePresence mode="wait">
                        {(status === 'RUNNING' || status === 'COMPLETED' || status === 'UPLOADING' || status === 'FAILED') && currentTab === 'process' && (
                            <motion.div
                                key="process-view"
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
                    <AnimatePresence mode="wait">
                        {currentTab === 'results' && (
                            <motion.div
                                key="results-view"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0 }}
                                className="w-full max-w-6xl px-6 py-6 h-full overflow-hidden flex flex-col"
                            >
                                <div className="bg-white/60 backdrop-blur-md rounded-3xl border border-gray-200 shadow-xl overflow-hidden p-1 flex-1 min-h-0">
                                    <ResultsView />
                                </div>
                                <div className="flex justify-center py-4 shrink-0">
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
                <AnimatePresence>
                    {(selectedAgentId || selectedNodeId) && isStreamOpen && (
                        <motion.div
                            initial={{ opacity: 0, x: 30 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 30 }}
                            className="fixed right-6 top-24 bottom-6 w-[360px] z-40 pointer-events-auto"
                        >
                            <LLMThoughtsPanel className="h-full" onClose={handleStreamClose} />
                        </motion.div>
                    )}
                </AnimatePresence>
                <ReviewOverlay />

            </div>
        </AppContext.Provider>
    );
}
