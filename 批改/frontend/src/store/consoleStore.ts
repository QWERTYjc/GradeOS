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
}

export interface StudentResult {
    studentName: string;
    score: number;
    maxScore: number;
    percentage?: number;
    questionResults?: QuestionResult[];
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
}

/**
 * 工作流节点配置
 * 
 * 对应设计文档批改流程（注意：批改后学生分割）：
 * 1. intake - 接收文件
 * 2. preprocess - 预处理图像
 * 3. rubric_parse - 解析评分标准
 * 4. grading - 固定分批并行批改（10张图片一批）
 * 5. segment - 批改后学生分割（基于批改结果智能判断学生边界）
 * 6. review - 汇总审核
 * 7. export - 导出结果
 */
const initialNodes: WorkflowNode[] = [
    { id: 'intake', label: '接收文件', status: 'pending' },
    { id: 'preprocess', label: '图像预处理', status: 'pending' },
    { id: 'rubric_parse', label: '解析评分标准', status: 'pending' },
    { id: 'grading', label: '固定分批批改', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'segment', label: '学生分割', status: 'pending' },
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

    connectWs: (batchId) => {
        const wsUrl = process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://127.0.0.1:8001';
        wsClient.connect(`${wsUrl}/batch/ws/${batchId}`);

        // 处理工作流节点更新
        wsClient.on('workflow_update', (data) => {
            console.log('Workflow Update:', data);
            const { nodeId, status, message } = data;
            get().updateNodeStatus(nodeId, status, message);
            if (message) {
                get().addLog(message, 'INFO');
            }
        });

        // 处理并行 Agent 创建
        wsClient.on('parallel_agents_created', (data) => {
            console.log('Parallel Agents Created:', data);
            const { parentNodeId, agents } = data;
            get().setParallelAgents(parentNodeId, agents);
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
            const { pageIndex, success, batchIndex, totalBatches } = data;
            const currentProgress = get().batchProgress;
            if (currentProgress) {
                get().setBatchProgress({
                    ...currentProgress,
                    successCount: success ? currentProgress.successCount + 1 : currentProgress.successCount,
                    failureCount: success ? currentProgress.failureCount : currentProgress.failureCount + 1,
                });
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
        wsClient.on('student_identified', (data) => {
            console.log('Student Identified:', data);
            const { boundaries } = data;
            if (boundaries && Array.isArray(boundaries)) {
                get().setStudentBoundaries(boundaries.map((b: any) => ({
                    studentKey: b.student_key,
                    startPage: b.start_page,
                    endPage: b.end_page,
                    confidence: b.confidence,
                    needsConfirmation: b.needs_confirmation,
                })));
                // 统计待确认边界
                const needsConfirm = boundaries.filter((b: any) => b.needs_confirmation).length;
                if (needsConfirm > 0) {
                    get().addLog(`识别到 ${boundaries.length} 名学生，${needsConfirm} 个边界待确认`, 'WARNING');
                } else {
                    get().addLog(`识别到 ${boundaries.length} 名学生`, 'INFO');
                }
            }
        });

        // 处理工作流完成
        wsClient.on('workflow_completed', (data) => {
            console.log('Workflow Completed:', data);
            set({ status: 'COMPLETED' });
            get().addLog(data.message || '工作流完成', 'SUCCESS');

            // 保存最终结果并自动切换到结果页
            if (data.results && Array.isArray(data.results)) {
                get().setFinalResults(data.results);
                // 延迟切换到结果页，让用户看到完成状态
                setTimeout(() => {
                    set({ currentTab: 'results' });
                }, 1500);
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
