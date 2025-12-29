import { create } from 'zustand';
import { wsClient } from '@/services/ws';

export type WorkflowStatus = 'IDLE' | 'UPLOADING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ConsoleTab = 'process' | 'results';

export interface LogEntry {
    timestamp: string;
    level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
    message: string;
}

export interface GradingAgent {
    id: string;
    label: string;
    status: NodeStatus;
    progress?: number;
    logs?: string[];
    error?: {
        type?: string;
        message?: string;
        details?: string[];
    };
    output?: {
        score?: number;
        maxScore?: number;
        feedback?: string;
        questionResults?: Array<{
            questionId: string;
            score: number;
            maxScore: number;
        }>;
        totalRevisions?: number;
    };
}

export interface WorkflowNode {
    id: string;
    label: string;
    status: NodeStatus;
    message?: string;
    isParallelContainer?: boolean;
    children?: GradingAgent[];
}

export interface ScoringPoint {
    description: string;
    score: number;
    maxScore: number;
    isCorrect: boolean;
    explanation: string;
}

export interface QuestionResult {
    questionId: string;
    score: number;
    maxScore: number;
    feedback?: string;
    confidence?: number;
    scoringPoints?: ScoringPoint[];
    /** 得分点明细列表 - 新增 */
    scoringPointResults?: Array<{
        scoringPoint: ScoringPoint;
        awarded: number;
        evidence: string;
    }>;
    /** 出现在哪些页面 - 新增 */
    pageIndices?: number[];
    /** 是否跨页题目 - 新增 */
    isCrossPage?: boolean;
    /** 合并来源（如果是合并结果）- 新增 */
    mergeSource?: string[];
}

export interface StudentResult {
    studentName: string;
    score: number;
    maxScore: number;
    percentage?: number;
    totalRevisions?: number;
    questionResults?: QuestionResult[];
    /** 起始页 - 新增 */
    startPage?: number;
    /** 结束页 - 新增 */
    endPage?: number;
    /** 置信度 - 新增 */
    confidence?: number;
    /** 是否需要人工确认 - 新增 */
    needsConfirmation?: boolean;
}

// 跨页题目信息（对应设计文档 CrossPageQuestion）
export interface CrossPageQuestion {
    questionId: string;
    pageIndices: number[];
    confidence: number;
    mergeReason: string;
}

// 学生边界信息（对应设计文档 StudentBoundary）
export interface StudentBoundary {
    studentKey: string;
    startPage: number;
    endPage: number;
    confidence: number;
    needsConfirmation: boolean;
}

// 批次处理状态（对应设计文档 BatchResult）
export interface BatchProgress {
    batchIndex: number;
    totalBatches: number;
    successCount: number;
    failureCount: number;
    processingTimeMs?: number;
}

// 解析的评分标准信息
export interface ParsedRubric {
    totalQuestions: number;
    totalScore: number;
}

// === 自我成长系统类型定义 ===

export interface ExemplarInfo {
    id: string;
    score: number;
    similarity: number;
    description: string;
}

export interface CalibrationInfo {
    teacherId: string;
    profileId: string;
    strictnessLevel: number; // 0.0 - 2.0
    focusAreas: string[];
}

export interface PatchInfo {
    patchId: string;
    version: string;
    status: 'testing' | 'deployed' | 'rolled_back';
    description: string;
    trafficPercentage?: number;
}

export interface SelfEvolvingState {
    calibration: CalibrationInfo | null;
    activePatches: PatchInfo[];
    // 判例信息通常与特定 Agent/Page 关联，这里存储最近检索到的判例用于展示
    recentExemplars: ExemplarInfo[];
}

export interface ConsoleState {
    view: 'LANDING' | 'CONSOLE';
    currentTab: ConsoleTab;
    status: WorkflowStatus;
    submissionId: string | null;
    selectedNodeId: string | null;
    selectedAgentId: string | null;
    isMonitorOpen: boolean;
    logs: LogEntry[];
    workflowNodes: WorkflowNode[];
    finalResults: StudentResult[];

    // 新增：自我成长系统状态
    parsedRubric: ParsedRubric | null;
    batchProgress: BatchProgress | null;
    studentBoundaries: StudentBoundary[];
    selfEvolving: SelfEvolvingState;
    // 新增：跨页题目信息
    crossPageQuestions: CrossPageQuestion[];

    setView: (view: 'LANDING' | 'CONSOLE') => void;
    setCurrentTab: (tab: ConsoleTab) => void;
    setStatus: (status: WorkflowStatus) => void;
    setSubmissionId: (id: string) => void;
    addLog: (log: string, level?: LogEntry['level']) => void;
    updateNodeStatus: (nodeId: string, status: NodeStatus, message?: string) => void;
    setParallelAgents: (nodeId: string, agents: GradingAgent[]) => void;
    updateAgentStatus: (agentId: string, update: Partial<GradingAgent>) => void;
    addAgentLog: (agentId: string, log: string) => void;
    setFinalResults: (results: StudentResult[]) => void;
    reset: () => void;
    setSelectedNodeId: (id: string | null) => void;
    setSelectedAgentId: (id: string | null) => void;
    toggleMonitor: () => void;
    connectWs: (batchId: string) => void;

    // 新增：自我成长系统方法
    setParsedRubric: (rubric: ParsedRubric) => void;
    setBatchProgress: (progress: BatchProgress) => void;
    setStudentBoundaries: (boundaries: StudentBoundary[]) => void;
    updateSelfEvolving: (update: Partial<SelfEvolvingState>) => void;
    // 新增：跨页题目方法
    setCrossPageQuestions: (questions: CrossPageQuestion[]) => void;
}

/**
 * 工作流节点配置
 * 
 * 基于 LangGraph 架构的批改流程（与后端 batch_grading.py 完全对应）：
 * 1. intake - 接收文件
 * 2. preprocess - 图像预处理
 * 3. index - 批改前索引（题目信息 + 学生识别）
 * 4. rubric_parse - 解析评分标准
 * 5. grade_batch - 可配置分批并行批改（支持批次失败重试、Worker 独立性）
 * 6. cross_page_merge - 跨页题目合并（检测并合并跨页题目，避免重复计分）
 * 7. index_merge - 索引聚合（基于索引聚合学生结果）
 * 8. review - 结果审核（标记低置信度结果、待确认边界）
 * 9. export - 导出结果（支持 JSON 导出、部分结果保存）
 * 
 * 后端 LangGraph Graph 流程：
 * intake → preprocess → index → rubric_parse → grade_batch (并行) → cross_page_merge → index_merge → review → export → END
 */
const initialNodes: WorkflowNode[] = [
    { id: 'intake', label: '接收文件', status: 'pending' },
    { id: 'preprocess', label: '图像预处理', status: 'pending' },
    { id: 'index', label: '索引层', status: 'pending' },
    { id: 'rubric_parse', label: '解析评分标准', status: 'pending' },
    { id: 'grade_batch', label: '分批并行批改', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'cross_page_merge', label: '跨页题目合并', status: 'pending' },
    { id: 'index_merge', label: '索引聚合', status: 'pending' },
    { id: 'review', label: '结果审核', status: 'pending' },
    { id: 'export', label: '导出结果', status: 'pending' },
];

export const useConsoleStore = create<ConsoleState>((set, get) => ({
    view: 'LANDING',
    currentTab: 'process',
    status: 'IDLE',
    submissionId: null,
    selectedNodeId: null,
    selectedAgentId: null,
    isMonitorOpen: false,
    logs: [],
    workflowNodes: initialNodes,
    finalResults: [],

    // 自我成长系统状态初始值
    parsedRubric: null,
    batchProgress: null,
    studentBoundaries: [],
    selfEvolving: {
        calibration: null,
        activePatches: [],
        recentExemplars: []
    },
    // 跨页题目信息初始值
    crossPageQuestions: [],

    setView: (view) => set({ view }),
    setCurrentTab: (tab) => set({ currentTab: tab }),
    setStatus: (status) => set({ status }),
    setSubmissionId: (id) => set({ submissionId: id }),
    addLog: (message, level = 'INFO') => set((state) => ({
        logs: [...state.logs, {
            timestamp: new Date().toISOString(),
            level,
            message
        }]
    })),

    updateNodeStatus: (nodeId, status, message) => set((state) => ({
        workflowNodes: state.workflowNodes.map((n) =>
            n.id === nodeId ? { ...n, status, message: message || n.message } : n
        )
    })),

    setParallelAgents: (nodeId, agents) => set((state) => ({
        workflowNodes: state.workflowNodes.map((n) =>
            n.id === nodeId ? { ...n, children: agents } : n
        )
    })),

    updateAgentStatus: (agentId, update) => set((state) => ({
        workflowNodes: state.workflowNodes.map((node) => {
            if (node.isParallelContainer && node.children) {
                return {
                    ...node,
                    children: node.children.map((agent) =>
                        agent.id === agentId ? { ...agent, ...update } : agent
                    )
                };
            }
            return node;
        })
    })),

    addAgentLog: (agentId, log) => set((state) => ({
        workflowNodes: state.workflowNodes.map((node) => {
            if (node.isParallelContainer && node.children) {
                return {
                    ...node,
                    children: node.children.map((agent) =>
                        agent.id === agentId
                            ? { ...agent, logs: [...(agent.logs || []), log] }
                            : agent
                    )
                };
            }
            return node;
        })
    })),

    setFinalResults: (results) => set({ finalResults: results }),

    reset: () => set({
        status: 'IDLE',
        currentTab: 'process',
        submissionId: null,
        selectedNodeId: null,
        selectedAgentId: null,
        isMonitorOpen: false,
        logs: [],
        finalResults: [],
        workflowNodes: initialNodes.map(n => ({
            ...n,
            status: 'pending' as NodeStatus,
            message: undefined,
            children: n.isParallelContainer ? [] : undefined
        })),
        // 重置自我成长系统状态
        parsedRubric: null,
        batchProgress: null,
        studentBoundaries: [],
        // 重置跨页题目信息
        crossPageQuestions: [],
    }),

    setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedAgentId: null }),
    setSelectedAgentId: (id) => set({ selectedAgentId: id }),
    toggleMonitor: () => set((state) => ({ isMonitorOpen: !state.isMonitorOpen })),

    // 自我成长系统方法
    setParsedRubric: (rubric) => set({ parsedRubric: rubric }),
    setBatchProgress: (progress) => set({ batchProgress: progress }),
    setStudentBoundaries: (boundaries) => set({ studentBoundaries: boundaries }),
    updateSelfEvolving: (update) => set((state) => ({
        selfEvolving: { ...state.selfEvolving, ...update }
    })),
    // 跨页题目方法
    setCrossPageQuestions: (questions) => set({ crossPageQuestions: questions }),

    connectWs: (batchId) => {
        const wsUrl = process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://127.0.0.1:8001';
        wsClient.connect(`${wsUrl}/batch/ws/${batchId}`);

        // 处理工作流节点更新
        wsClient.on('workflow_update', (data) => {
            console.log('Workflow Update:', data);
            const { nodeId, status, message } = data;
            // 后端节点 ID 映射到前端（兼容旧名称）
            const mappedNodeId = nodeId === 'grading' ? 'grade_batch' : nodeId;
            get().updateNodeStatus(mappedNodeId, status, message);
            if (message) {
                get().addLog(message, 'INFO');
            }
        });

        // 处理并行 Agent 创建
        wsClient.on('parallel_agents_created', (data) => {
            console.log('Parallel Agents Created:', data);
            const { parentNodeId, agents } = data;
            // 后端节点 ID 映射到前端
            const mappedNodeId = parentNodeId === 'grading' ? 'grade_batch' : parentNodeId;
            get().setParallelAgents(mappedNodeId, agents);
            get().addLog(`创建了 ${agents.length} 个批改 Agent`, 'INFO');
        });

        // 处理单个 Agent 更新
        wsClient.on('agent_update', (data) => {
            console.log('Agent Update:', data);
            const { agentId, status, progress, message, output, logs, error } = data;
            get().updateAgentStatus(agentId, { status, progress, output, error });
            if (logs && logs.length > 0) {
                logs.forEach((log: string) => get().addAgentLog(agentId, log));
            }
            if (message) {
                get().addLog(message, 'INFO');
            }
            // 如果有错误，也记录到日志
            if (error && error.details) {
                error.details.forEach((detail: string) => get().addLog(`[错误] ${detail}`, 'ERROR'));
            }
        });

        // ===== 设计文档新增事件类型 =====

        // 处理评分标准解析完成事件
        wsClient.on('rubric_parsed', (data) => {
            console.log('Rubric Parsed:', data);
            const { totalQuestions, totalScore } = data;
            get().setParsedRubric({ totalQuestions, totalScore });
            get().addLog(`评分标准解析完成：${totalQuestions} 道题，满分 ${totalScore} 分`, 'INFO');
        });

        // 处理批次开始事件（对应设计文档 EventType.BATCH_START）
        wsClient.on('batch_start', (data) => {
            console.log('Batch Start:', data);
            const { batchIndex, totalBatches } = data;
            get().setBatchProgress({
                batchIndex,
                totalBatches,
                successCount: 0,
                failureCount: 0,
            });
            get().addLog(`开始处理批次 ${batchIndex + 1}/${totalBatches}`, 'INFO');
        });

        // 处理单页完成事件（对应设计文档 EventType.PAGE_COMPLETE）
        wsClient.on('page_complete', (data) => {
            console.log('Page Complete:', data);
            const { pageIndex, success, batchIndex, totalBatches, revisionCount } = data;
            const currentProgress = get().batchProgress;

            // 更新批次进度
            if (currentProgress) {
                get().setBatchProgress({
                    ...currentProgress,
                    successCount: success ? currentProgress.successCount + 1 : currentProgress.successCount,
                    failureCount: success ? currentProgress.failureCount : currentProgress.failureCount + 1,
                });
            }

            // 更新对应 Agent 的自我修正次数
            if (revisionCount && revisionCount > 0) {
                const agentId = `batch_${batchIndex}`;
                const nodes = get().workflowNodes;
                const gradingNode = nodes.find(n => n.id === 'grading');

                if (gradingNode && gradingNode.children) {
                    const agent = gradingNode.children.find(a => a.id === agentId);
                    if (agent) {
                        const currentRevisions = agent.output?.totalRevisions || 0;
                        get().updateAgentStatus(agentId, {
                            output: {
                                ...agent.output,
                                totalRevisions: currentRevisions + revisionCount
                            }
                        });
                        get().addAgentLog(agentId, `页面 ${pageIndex} 触发了 ${revisionCount} 次自我修正`);
                    }
                }
            }
        });

        // 处理批次完成事件（对应设计文档 EventType.BATCH_COMPLETE）
        wsClient.on('batch_complete', (data) => {
            console.log('Batch Complete:', data);
            const { batchIndex, successCount, failureCount, processingTimeMs } = data;
            get().setBatchProgress({
                batchIndex,
                totalBatches: get().batchProgress?.totalBatches || 0,
                successCount,
                failureCount,
                processingTimeMs,
            });
            get().addLog(`批次 ${batchIndex + 1} 完成：成功 ${successCount}，失败 ${failureCount}`, 'INFO');
        });

        // 处理学生识别事件（对应设计文档 EventType.STUDENT_IDENTIFIED）
        wsClient.on('students_identified', (data) => {
            console.log('Students Identified:', data);
            const { students, studentCount } = data;
            if (students && Array.isArray(students)) {
                get().setStudentBoundaries(students.map((s: any) => ({
                    studentKey: s.studentKey,
                    startPage: s.startPage,
                    endPage: s.endPage,
                    confidence: s.confidence,
                    needsConfirmation: s.needsConfirmation,
                })));
                // 统计待确认边界
                const needsConfirm = students.filter((s: any) => s.needsConfirmation).length;
                if (needsConfirm > 0) {
                    get().addLog(`识别到 ${studentCount} 名学生，${needsConfirm} 个边界待确认`, 'WARNING');
                } else {
                    get().addLog(`识别到 ${studentCount} 名学生`, 'INFO');
                }
            }
        });

        // 处理跨页题目检测事件
        wsClient.on('cross_page_detected', (data) => {
            console.log('Cross Page Questions Detected:', data);
            const { questions, mergedCount, crossPageCount } = data;
            if (questions && Array.isArray(questions)) {
                get().setCrossPageQuestions(questions.map((q: any) => ({
                    questionId: q.question_id || q.questionId,
                    pageIndices: q.page_indices || q.pageIndices || [],
                    confidence: q.confidence || 0,
                    mergeReason: q.merge_reason || q.mergeReason || '',
                })));
                get().addLog(
                    `跨页题目合并完成：检测到 ${crossPageCount || questions.length} 道跨页题目，合并后共 ${mergedCount || '?'} 道题目`,
                    'INFO'
                );
            }
        });

        // 处理工作流完成
        wsClient.on('workflow_completed', (data) => {
            console.log('Workflow Completed:', data);
            set({ status: 'COMPLETED' });
            get().addLog(data.message || '工作流完成', 'SUCCESS');

            // 保存跨页题目信息
            if (data.cross_page_questions && Array.isArray(data.cross_page_questions)) {
                get().setCrossPageQuestions(data.cross_page_questions.map((q: any) => ({
                    questionId: q.question_id || q.questionId,
                    pageIndices: q.page_indices || q.pageIndices || [],
                    confidence: q.confidence || 0,
                    mergeReason: q.merge_reason || q.mergeReason || '',
                })));
            }

            // 保存最终结果
            if (data.results && Array.isArray(data.results)) {
                // 转换后端格式到前端格式
                const formattedResults: StudentResult[] = data.results.map((r: any) => ({
                    studentName: r.studentName || r.student_name || r.student_key || 'Unknown',
                    score: r.score || r.total_score || 0,
                    maxScore: r.maxScore || r.max_score || r.max_total_score || 100,
                    percentage: r.percentage,
                    totalRevisions: r.totalRevisions,
                    startPage: r.start_page || r.startPage,
                    endPage: r.end_page || r.endPage,
                    confidence: r.confidence,
                    needsConfirmation: r.needs_confirmation || r.needsConfirmation,
                    questionResults: (r.questionResults || r.question_results || []).map((q: any) => ({
                        questionId: q.questionId || q.question_id || '',
                        score: q.score || 0,
                        maxScore: q.maxScore || q.max_score || 0,
                        feedback: q.feedback || '',
                        confidence: q.confidence,
                        pageIndices: q.page_indices || q.pageIndices,
                        isCrossPage: q.is_cross_page || q.isCrossPage,
                        mergeSource: q.merge_source || q.mergeSource,
                        scoringPoints: q.scoringPoints || q.scoring_points,
                        scoringPointResults: (q.scoring_point_results || q.scoringPointResults || []).map((spr: any) => ({
                            scoringPoint: {
                                description: spr.scoring_point?.description || spr.scoringPoint?.description || '',
                                score: spr.scoring_point?.score || spr.scoringPoint?.score || 0,
                                maxScore: spr.scoring_point?.score || spr.scoringPoint?.score || 0,
                                isCorrect: spr.awarded > 0,
                                isRequired: spr.scoring_point?.is_required || spr.scoringPoint?.isRequired,
                            },
                            awarded: spr.awarded || 0,
                            evidence: spr.evidence || '',
                        }))
                    }))
                }));
                
                get().setFinalResults(formattedResults);
                get().addLog(`已保存 ${formattedResults.length} 名学生的批改结果`, 'SUCCESS');
                
                // 延迟切换到结果页，让用户看到完成状态
                setTimeout(() => {
                    set({ currentTab: 'results' });
                }, 1500);
            }
        });

        // 处理单页批改完成事件
        wsClient.on('page_graded', (data) => {
            console.log('Page Graded:', data);
            const { pageIndex, score, maxScore, feedback, questionNumbers, questionDetails } = data;
            get().addLog(
                `页面 ${pageIndex} 批改完成: ${score}/${maxScore} 分，题目: ${questionNumbers?.join(', ') || '未识别'}`,
                'INFO'
            );
        });

        // 处理批改进度事件
        wsClient.on('grading_progress', (data) => {
            console.log('Grading Progress:', data);
            const { completedPages, totalPages, percentage } = data;
            // 更新 grading 节点的进度
            const nodes = get().workflowNodes;
            const gradingNode = nodes.find(n => n.id === 'grading');
            if (gradingNode) {
                get().updateNodeStatus('grading', 'running', `批改进度: ${completedPages}/${totalPages} (${percentage}%)`);
            }
        });

        // 处理批次完成事件
        wsClient.on('batch_completed', (data) => {
            console.log('Batch Completed:', data);
            const { batchSize, successCount, totalScore, pages } = data;
            get().addLog(
                `批次完成: ${successCount}/${batchSize} 页成功，总分 ${totalScore}`,
                'INFO'
            );
        });

        // 处理审核完成事件
        wsClient.on('review_completed', (data) => {
            console.log('Review Completed:', data);
            const { summary } = data;
            if (summary) {
                get().addLog(
                    `审核完成: ${summary.total_students} 名学生，${summary.low_confidence_count} 个低置信度结果`,
                    'INFO'
                );
            }
        });

        // 处理工作流错误（对应设计文档 EventType.ERROR）
        wsClient.on('workflow_error', (data) => {
            console.log('Workflow Error:', data);
            set({ status: 'FAILED' });
            get().addLog(`错误: ${data.message}`, 'ERROR');
        });
    }
}));
