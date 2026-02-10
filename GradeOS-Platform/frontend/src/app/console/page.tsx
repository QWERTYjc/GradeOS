'use client';

import React, { useEffect, useState, useContext, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useConsoleStore } from '@/store/consoleStore';
import { useAuthStore } from '@/store/authStore';
import { useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Images,
    ScanLine,
    Trophy
} from 'lucide-react';
import clsx from 'clsx';
import { AppContext } from '@/components/bookscan/AppContext';
import { ScannedImage, Session } from '@/components/bookscan/types';
import { api, classApi } from '@/services/api';

// Dynamic imports - Scanner and Gallery use pdfjs-dist which requires browser APIs
const Scanner = dynamic(() => import('@/components/bookscan/Scanner'), { ssr: false });
const Gallery = dynamic(() => import('@/components/bookscan/Gallery'), { ssr: false });
const WorkflowSteps = dynamic(() => import('@/components/console/WorkflowSteps'), { ssr: false });
const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });
const LLMThoughtsPanel = dynamic(() => import('@/components/console/LLMThoughtsPanel'), { ssr: false });
const ReviewOverlay = dynamic(() => import('@/components/console/ReviewOverlay'), { ssr: false });

// --- Components ---

type ScanTab = 'scan' | 'gallery';

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
    onSubmitBatch: (
        images: ScannedImage[],
        boundaries: number[],
        studentMapping?: Array<{ studentId?: string; studentName?: string; studentKey?: string; startIndex: number; endIndex: number }>
    ) => Promise<void>;
    interactionEnabled: boolean;
    onInteractionToggle: (enabled: boolean) => void;
    gradingMode: string;
    onGradingModeChange: (mode: string) => void;
    expectedTotalScore: number | null;
    onExpectedTotalScoreChange: (score: number | null) => void;

    // 班级批改模式下的学生映射
    studentNameMapping?: Array<{ studentId?: string; studentName?: string; studentKey?: string; startIndex: number; endIndex: number }>;
    
    // 当前用户信息（用于获取班级列表）
    userId?: string;
    userType?: string;
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
    expectedTotalScore,
    onExpectedTotalScoreChange,
    studentNameMapping = [],
    userId,
    userType
}: ScannerContainerProps) => {
    const { setCurrentSessionId, sessions } = useContext(AppContext)!;
    const [viewMode, setViewMode] = useState<ScanViewMode>('exams');
    const [studentBoundaries, setStudentBoundaries] = useState<number[]>([]);
    const [studentInfos, setStudentInfos] = useState<Array<{ studentName: string; studentId: string }>>([]);
    
    // 班级选择相关状态
    const [availableClasses, setAvailableClasses] = useState<Array<{ class_id: string; class_name: string }>>([]);
    const [selectedClassId, setSelectedClassId] = useState<string>('');
    const [classStudents, setClassStudents] = useState<Array<{ id: string; name: string; username: string }>>([]);
    const [isLoadingClasses, setIsLoadingClasses] = useState(false);
    const [isLoadingStudents, setIsLoadingStudents] = useState(false);

    useEffect(() => {
        if (viewMode === 'exams' && examSessionId) {
            setCurrentSessionId(examSessionId);
        } else if (viewMode === 'rubrics' && rubricSessionId) {
            setCurrentSessionId(rubricSessionId);
        }
    }, [viewMode, examSessionId, rubricSessionId, setCurrentSessionId]);

    const currentSession = sessions.find(s => s.id === (viewMode === 'exams' ? examSessionId : rubricSessionId));
    const imageCount = currentSession?.images.length || 0;

    // 加载班级列表
    useEffect(() => {
        if (!userId || !userType) return;
        
        const loadClasses = async () => {
            setIsLoadingClasses(true);
            try {
                let classes: Array<{ class_id: string; class_name: string }> = [];
                
                if (userType === 'teacher') {
                    const response = await classApi.getTeacherClasses(userId);
                    classes = response.map((c: any) => ({ class_id: c.class_id, class_name: c.class_name }));
                } else if (userType === 'student') {
                    const response = await classApi.getMyClasses(userId);
                    classes = response.map((c: any) => ({ class_id: c.class_id, class_name: c.class_name }));
                }
                
                setAvailableClasses(classes);
            } catch (error) {
                console.error('Failed to load classes:', error);
            } finally {
                setIsLoadingClasses(false);
            }
        };
        
        loadClasses();
    }, [userId, userType]);

    // 加载班级学生
    useEffect(() => {
        if (!selectedClassId) {
            setClassStudents([]);
            return;
        }
        
        const loadStudents = async () => {
            setIsLoadingStudents(true);
            try {
                const students = await classApi.getClassStudents(selectedClassId);
                setClassStudents(students);
                
                // 自动填充学生信息到 studentInfos
                if (students.length > 0) {
                    const autoMapping = students.map((s: any) => ({
                        studentName: s.name || s.username,
                        studentId: s.id,
                    }));
                    setStudentInfos(autoMapping);
                    
                    // 自动设置边界（假设每个学生平均分配页面）
                    if (imageCount > 0) {
                        const pagesPerStudent = Math.floor(imageCount / students.length);
                        const boundaries = students.map((_: any, idx: number) => idx * pagesPerStudent);
                        setStudentBoundaries(boundaries);
                    }
                }
            } catch (error) {
                console.error('Failed to load students:', error);
            } finally {
                setIsLoadingStudents(false);
            }
        };
        
        loadStudents();
    }, [selectedClassId, imageCount]);

    const normalizeBoundaries = (boundaries: number[], total: number) => {
        const normalized = Array.from(
            new Set(
                boundaries
                    .map((value) => Number(value))
                    .filter((value) => Number.isFinite(value) && value >= 0 && value < total)
            )
        ).sort((a, b) => a - b);

        if (total > 0) {
            if (normalized.length === 0 || normalized[0] !== 0) {
                normalized.unshift(0);
            }
        }
        return normalized;
    };

    const syncStudentInfos = useCallback((count: number) => {
        setStudentInfos((prev) => {
            const next = [];
            for (let i = 0; i < count; i += 1) {
                const existing = prev[i];
                const seeded = studentNameMapping[i];
                next.push({
                    studentName: (existing?.studentName ?? seeded?.studentName ?? '').toString(),
                    studentId: (existing?.studentId ?? seeded?.studentId ?? '').toString(),
                });
            }
            return next;
        });
    }, [studentNameMapping]);

    const handleBoundariesChange = (boundaries: number[]) => {
        const normalized = normalizeBoundaries(boundaries, imageCount);
        setStudentBoundaries(normalized);
        syncStudentInfos(normalized.length);
    };

    useEffect(() => {
        if (studentBoundaries.length > 0 && studentNameMapping.length > 0) {
            syncStudentInfos(studentBoundaries.length);
        }
    }, [studentBoundaries.length, studentNameMapping, syncStudentInfos]);

    const buildStudentMapping = (
        boundaries: number[],
        total: number,
        options: { fillDefaults?: boolean } = {}
    ) => {
        if (!total) return [];
        const normalized = normalizeBoundaries(boundaries, total);
        const fillDefaults = options.fillDefaults ?? false;
        return normalized.map((startIndex, idx) => {
            const endIndex = idx + 1 < normalized.length ? normalized[idx + 1] - 1 : total - 1;
            const info = studentInfos[idx] || { studentName: '', studentId: '' };
            const trimmedName = info.studentName.trim();
            const trimmedId = info.studentId.trim();
            const labelCandidate = trimmedName || trimmedId;
            const studentKey = fillDefaults
                ? (labelCandidate || `学生${idx + 1}`)
                : labelCandidate || undefined;
            return {
                studentId: trimmedId || undefined,
                studentName: trimmedName || undefined,
                studentKey,
                startIndex,
                endIndex,
            };
        }).filter(item => item.startIndex <= item.endIndex);
    };

    const handleSubmit = async (images: ScannedImage[]) => {
        const normalized = normalizeBoundaries(studentBoundaries, images.length);
        const mapping = buildStudentMapping(normalized, images.length, { fillDefaults: true });
        await onSubmitBatch(images, normalized, mapping);
    };

    const displayStudentMapping = viewMode === 'exams'
        ? buildStudentMapping(studentBoundaries, imageCount)
        : [];

    // Allow access without login for demo purposes
    // if (!user) {
    //     return null;
    // }

    return (
        <div className="h-full w-full flex flex-col bg-white">
            {/* Top Bar: View Switcher & Scan/Preview Toggle */}
            <div className="flex flex-col gap-3 px-4 py-4 bg-white border-b border-slate-100 relative z-20 md:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-6">
                        <button
                            onClick={() => setViewMode('exams')}
                            className={clsx(
                                "text-sm font-semibold pb-1 border-b-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70",
                                viewMode === 'exams'
                                    ? "border-slate-900 text-slate-900"
                                    : "border-transparent text-slate-400 hover:text-slate-700"
                            )}
                        >
                            Student Exams
                        </button>
                        <button
                            onClick={() => setViewMode('rubrics')}
                            className={clsx(
                                "text-sm font-semibold pb-1 border-b-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70",
                                viewMode === 'rubrics'
                                    ? "border-slate-900 text-slate-900"
                                    : "border-transparent text-slate-400 hover:text-slate-700"
                            )}
                        >
                            Rubric / Standards
                        </button>
                    </div>

                    <div className="flex items-center gap-4">
                        {viewMode === 'exams' && (
                            <>
                                {/* 班级选择器 */}
                                {availableClasses.length > 0 && (
                                    <div className="flex items-center gap-2">
                                        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">班级</span>
                                        <select
                                            value={selectedClassId}
                                            onChange={(e) => setSelectedClassId(e.target.value)}
                                            disabled={isLoadingClasses}
                                            className="text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
                                        >
                                            <option value="">选择班级...</option>
                                            {availableClasses.map(cls => (
                                                <option key={cls.class_id} value={cls.class_id}>
                                                    {cls.class_name}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                )}
                                
                                {/* 学生数量显示 */}
                                {classStudents.length > 0 && (
                                    <div className="flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-[11px] font-semibold text-blue-700">
                                        <span className="uppercase tracking-[0.2em]">学生</span>
                                        <span>{classStudents.length}</span>
                                    </div>
                                )}
                                
                                <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-semibold text-slate-600">
                                    <span className="uppercase tracking-[0.2em] text-slate-400">Total</span>
                                    <input
                                        type="number"
                                        min={0}
                                        step={0.5}
                                        value={expectedTotalScore ?? ''}
                                        onChange={(event) => {
                                            const nextValue = event.target.value.trim();
                                            if (!nextValue) {
                                                onExpectedTotalScoreChange(null);
                                                return;
                                            }
                                            const parsed = Number(nextValue);
                                            if (Number.isFinite(parsed) && parsed >= 0) {
                                                onExpectedTotalScoreChange(parsed);
                                            }
                                        }}
                                        placeholder="Max score"
                                        className="w-20 bg-transparent text-xs font-semibold text-slate-900 outline-none placeholder:text-slate-300"
                                    />
                                </div>
                            </>
                        )}
                        {viewMode === 'rubrics' && (
                            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-semibold text-slate-600">
                                <span className="uppercase tracking-[0.2em] text-slate-400">Total</span>
                                <input
                                    type="number"
                                    min={0}
                                    step={0.5}
                                    value={expectedTotalScore ?? ''}
                                    onChange={(event) => {
                                        const nextValue = event.target.value.trim();
                                        if (!nextValue) {
                                            onExpectedTotalScoreChange(null);
                                            return;
                                        }
                                        const parsed = Number(nextValue);
                                        if (Number.isFinite(parsed) && parsed >= 0) {
                                            onExpectedTotalScoreChange(parsed);
                                        }
                                    }}
                                    placeholder="Max score"
                                    className="w-20 bg-transparent text-xs font-semibold text-slate-900 outline-none placeholder:text-slate-300"
                                />
                            </div>
                        )}
                        <button
                            onClick={() => onTabChange('scan')}
                            className={clsx(
                                "flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70",
                                activeTab === 'scan'
                                    ? "border-slate-900 text-slate-900"
                                    : "border-transparent text-slate-400 hover:text-slate-700"
                            )}
                        >
                            <ScanLine className="h-3.5 w-3.5" />
                            Capture
                        </button>
                        <button
                            onClick={() => onTabChange('gallery')}
                            className={clsx(
                                "flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70",
                                activeTab === 'gallery'
                                    ? "border-slate-900 text-slate-900"
                                    : "border-transparent text-slate-400 hover:text-slate-700"
                            )}
                        >
                            <Images className="h-3.5 w-3.5" />
                            Review ({imageCount})
                        </button>
                    </div>
                </div>
            </div>

            {/* Content Area - 包含学生列表侧边栏和主内容区 */}
            <div className="flex-1 min-h-0 bg-transparent flex">
                {/* 学生列表侧边栏 - 仅在选择班级且有学生时显示 */}
                {viewMode === 'exams' && classStudents.length > 0 && (
                    <div className="w-64 border-r border-slate-200 bg-slate-50 overflow-y-auto">
                        <div className="p-4 border-b border-slate-200 bg-white">
                            <h3 className="text-sm font-semibold text-slate-900">班级学生</h3>
                            <p className="text-xs text-slate-500 mt-1">共 {classStudents.length} 人</p>
                        </div>
                        <div className="p-2 space-y-1">
                            {classStudents.map((student, index) => (
                                <div
                                    key={student.id}
                                    className="flex items-center gap-3 p-3 rounded-lg bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
                                >
                                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-semibold">
                                        {index + 1}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium text-slate-900 truncate">
                                            {student.name || student.username}
                                        </div>
                                        <div className="text-xs text-slate-500 truncate">
                                            {student.id}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                        {isLoadingStudents && (
                            <div className="p-4 text-center">
                                <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                                <p className="text-xs text-slate-500 mt-2">加载中...</p>
                            </div>
                        )}
                    </div>
                )}
                
                {/* 主内容区 */}
                <div className="flex-1 min-h-0 bg-transparent">
                    {activeTab === 'scan' ? (
                        <Scanner />
                    ) : (
                        <Gallery
                            key={viewMode} // Force re-mount when switching modes
                            session={currentSession} // Direct pass to avoid context lag
                            onSubmitBatch={handleSubmit}
                            submitLabel={viewMode === 'exams' ? "Start Grading" : undefined}
                            onBoundariesChange={viewMode === 'exams' ? handleBoundariesChange : undefined}
                            isRubricMode={viewMode === 'rubrics'}
                            studentNameMapping={viewMode === 'exams' ? displayStudentMapping : undefined}
                            onStudentInfoChange={viewMode === 'exams' ? (index, info) => {
                                setStudentInfos((prev) => {
                                    const next = [...prev];
                                    const current = next[index] || { studentName: '', studentId: '' };
                                    next[index] = {
                                        studentName: info.studentName ?? current.studentName,
                                        studentId: info.studentId ?? current.studentId,
                                    };
                                    return next;
                                });
                            } : undefined}
                            interactionEnabled={interactionEnabled}
                            onInteractionToggle={onInteractionToggle}
                            gradingMode={gradingMode}
                            onGradingModeChange={onGradingModeChange}
                        />
                    )}
                </div>
            </div>
        </div>
    );
};

export default function ConsolePage() {
    const status = useConsoleStore((state) => state.status);
    const reset = useConsoleStore((state) => state.reset);
    const submissionId = useConsoleStore((state) => state.submissionId);
    const { user } = useAuthStore();
    const selectedAgentId = useConsoleStore((state) => state.selectedAgentId);
    const selectedNodeId = useConsoleStore((state) => state.selectedNodeId);
    const setSelectedNodeId = useConsoleStore((state) => state.setSelectedNodeId);
    const interactionEnabled = useConsoleStore((state) => state.interactionEnabled);
    const setInteractionEnabled = useConsoleStore((state) => state.setInteractionEnabled);
    const gradingMode = useConsoleStore((state) => state.gradingMode);
    const setGradingMode = useConsoleStore((state) => state.setGradingMode);
    const expectedTotalScore = useConsoleStore((state) => state.expectedTotalScore);
    const setExpectedTotalScore = useConsoleStore((state) => state.setExpectedTotalScore);
    const classContext = useConsoleStore((state) => state.classContext);
    const rubricScoreMismatch = useConsoleStore((state) => state.rubricScoreMismatch);
    const setRubricScoreMismatch = useConsoleStore((state) => state.setRubricScoreMismatch);
    const rubricParseError = useConsoleStore((state) => state.rubricParseError);
    const setRubricParseError = useConsoleStore((state) => state.setRubricParseError);
    const currentTab = useConsoleStore((state) => state.currentTab);
    const isResultsView = currentTab === 'results';
    const setCurrentTab = useConsoleStore((state) => state.setCurrentTab);
    const isIdleView = status === 'IDLE';
    const dismissedRunsKey = user?.id ? `gradeos-dismissed-runs:${user.id}` : null;

    // Initial Sessions State
    const [sessions, setSessions] = useState<Session[]>([]);
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

    // Permanent sessions for isolation
    const [examSessionId, setExamSessionId] = useState<string | null>(null);
    const [rubricSessionId, setRubricSessionId] = useState<string | null>(null);

    // Global Split State
    const [splitImageIds, setSplitImageIds] = useState<Set<string>>(new Set());

    const [activeTab, setActiveTab] = useState<ScanTab>('scan'); // Sub-tab for ScannerContainer

    const [isStreamOpen, setIsStreamOpen] = useState(false);

    useEffect(() => {
        if (selectedAgentId || selectedNodeId) {
            setIsStreamOpen(true);
            return;
        }
        setIsStreamOpen(false);
    }, [selectedAgentId, selectedNodeId]);

    useEffect(() => {
        if (rubricScoreMismatch || rubricParseError) {
            setActiveTab('scan');
        }
    }, [rubricScoreMismatch, rubricParseError]);

    const dismissCompletedRun = useCallback((batchId: string) => {
        if (!dismissedRunsKey || typeof window === 'undefined') return;
        try {
            const raw = window.localStorage.getItem(dismissedRunsKey);
            const parsed = raw ? (JSON.parse(raw) as string[]) : [];
            if (!parsed.includes(batchId)) {
                const next = [...parsed, batchId];
                window.localStorage.setItem(dismissedRunsKey, JSON.stringify(next));
            }
        } catch (error) {
            console.warn('Failed to persist dismissed run:', error);
        }
    }, [dismissedRunsKey]);

    useEffect(() => {
        if (status === 'COMPLETED' && currentTab === 'results' && submissionId) {
            dismissCompletedRun(submissionId);
        }
    }, [status, currentTab, submissionId, dismissCompletedRun]);

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
        if (submissionId !== batchId) {
            reset();
        }
        useConsoleStore.getState().setSubmissionId(batchId);
        useConsoleStore.getState().connectWs(batchId);
        useConsoleStore.getState().setStatus('RUNNING');
    }, [searchParams, reset, submissionId]);

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

    // Batch Submission
    const handleSubmitBatch = async (
        images: ScannedImage[],
        boundaries: number[],
        studentMapping?: Array<{ studentId?: string; studentName?: string; studentKey?: string; startIndex: number; endIndex: number }>
    ) => {
        try {
            const rubricSession = sessions.find(s => s.id === rubricSessionId);
            if (!rubricSession || rubricSession.images.length === 0) {
                // warning logic if needed
            }

            useConsoleStore.getState().setStatus('UPLOADING');

            const examFiles = images.map(img => dataUrlToFile(img.url, img.name));
            const rubricFiles = rubricSession ? rubricSession.images.map(img => dataUrlToFile(img.url, img.name)) : [];

            // 获取班级批改上下文（如果存在）
            const studentMappingPayload = (studentMapping && studentMapping.length > 0)
                ? studentMapping
                : undefined;
            const classContextPayload = (classContext.classId || studentMappingPayload) ? {
                classId: classContext.classId || undefined,
                homeworkId: classContext.homeworkId || undefined,
                studentMapping: studentMappingPayload,
            } : undefined;

            // 2. Upload to backend with optional class context
            const response = await api.createSubmission(
                examFiles,
                rubricFiles,
                boundaries,
                undefined,
                classContextPayload,
                interactionEnabled,
                gradingMode,
                user?.id,
                expectedTotalScore ?? undefined
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
                "w-full relative console-shell flex flex-col",
                isResultsView ? "h-screen overflow-hidden bg-black" : isIdleView ? "h-screen overflow-md bg-white" : "min-h-screen overflow-auto"
            )}>

                <AnimatePresence>
                    {status === 'REVIEWING' && (
                        <motion.div
                            initial={{ opacity: 0, y: -12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -12 }}
                            className="fixed right-6 top-24 z-40 bg-white/90 backdrop-blur border border-amber-200 text-amber-900 shadow-lg rounded-2xl px-4 py-3 flex items-center gap-3"
                        >
                            <div className="text-sm font-semibold">Review required</div>
                            <button
                                onClick={() => setCurrentTab('results')}
                                className="px-3 py-1.5 text-xs font-semibold rounded-full bg-amber-500 text-white hover:bg-amber-600 transition"
                            >
                                Open
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                <AnimatePresence>
                    {status === 'COMPLETED' && currentTab !== 'results' && (
                        <motion.div
                            initial={{ opacity: 0, y: -12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -12 }}
                            className="fixed right-6 top-36 z-40 bg-white/90 backdrop-blur border border-emerald-200 text-emerald-900 shadow-lg rounded-2xl px-4 py-3 flex items-center gap-3"
                        >
                            <div className="text-sm font-semibold">Grading completed</div>
                            <button
                                onClick={() => setCurrentTab('results')}
                                className="px-3 py-1.5 text-xs font-semibold rounded-full bg-emerald-500 text-white hover:bg-emerald-600 transition"
                            >
                                View results
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Main Content Area - Centered */}
                <main
                    className={clsx(
                        "relative z-10 w-full flex flex-col items-center",
                        isResultsView
                            ? "flex-1 min-h-0 justify-start"
                            : isIdleView
                                ? "min-h-screen justify-start"
                                : "min-h-screen justify-center"
                    )}
                >

                    {/* Scanner/Uploader - Only visible when IDLE */}
                    <AnimatePresence mode="wait">
                        {status === 'IDLE' && (
                            <motion.div
                                key="idle-view"
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95, y: -30 }}
                                className="w-full h-full"
                            >
                                {rubricScoreMismatch && (
                                    <div className="mx-auto max-w-3xl px-6 pt-6">
                                        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 flex items-start justify-between gap-4">
                                            <div>
                                                <div className="font-semibold">Rubric total mismatch</div>
                                                <div className="mt-1 text-xs text-rose-600">{rubricScoreMismatch.message}</div>
                                            </div>
                                            <button
                                                onClick={() => setRubricScoreMismatch(null)}
                                                className="shrink-0 rounded-full border border-rose-200 bg-white px-3 py-1 text-xs font-semibold text-rose-600 hover:bg-rose-100"
                                            >
                                                Got it
                                            </button>
                                        </div>
                                    </div>
                                )}
                                {rubricParseError && (
                                    <div className="mx-auto max-w-3xl px-6 pt-4">
                                        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 flex items-start justify-between gap-4">
                                            <div>
                                                <div className="font-semibold">Rubric parse failed</div>
                                                <div className="mt-1 text-xs text-rose-600">{rubricParseError.message}</div>
                                                {rubricParseError.details && (
                                                    <div className="mt-1 text-[10px] text-rose-500">{rubricParseError.details}</div>
                                                )}
                                            </div>
                                            <button
                                                onClick={() => setRubricParseError(null)}
                                                className="shrink-0 rounded-full border border-rose-200 bg-white px-3 py-1 text-xs font-semibold text-rose-600 hover:bg-rose-100"
                                            >
                                                Got it
                                            </button>
                                        </div>
                                    </div>
                                )}
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
                                    expectedTotalScore={expectedTotalScore}
                                    onExpectedTotalScoreChange={setExpectedTotalScore}
                                    studentNameMapping={classContext.studentImageMapping}
                                    userId={user?.id}
                                    userType={user?.role}
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
                                <WorkflowSteps />
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
                                className="w-full flex-1 min-h-0 overflow-hidden flex flex-col"
                            >
                                <div className="flex-1 min-h-0 overflow-hidden">
                                    <ResultsView />
                                </div>
                                <div className="flex justify-center py-4 shrink-0 border-t border-slate-100 bg-white">
                                    <button
                                        onClick={reset}
                                        className="px-8 py-3 bg-black text-white rounded-full font-medium hover:bg-gray-800 transition-all"
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
                            className="fixed right-6 top-24 bottom-6 w-[360px] z-50 pointer-events-auto"
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
