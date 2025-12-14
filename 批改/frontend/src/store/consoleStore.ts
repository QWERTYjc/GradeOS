import { create } from 'zustand';
import { wsClient } from '@/services/ws';

export type WorkflowStatus = 'IDLE' | 'UPLOADING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ConsoleTab = 'process' | 'results';

export interface GradingAgent {
    id: string;
    label: string;
    status: NodeStatus;
    progress?: number;
    logs?: string[];
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

export interface StudentResult {
    studentName: string;
    score: number;
    maxScore: number;
}

export interface ConsoleState {
    view: 'LANDING' | 'CONSOLE';
    currentTab: ConsoleTab;
    status: WorkflowStatus;
    submissionId: string | null;
    selectedNodeId: string | null;
    selectedAgentId: string | null;
    logs: string[];
    workflowNodes: WorkflowNode[];
    finalResults: StudentResult[];

    setView: (view: 'LANDING' | 'CONSOLE') => void;
    setCurrentTab: (tab: ConsoleTab) => void;
    setStatus: (status: WorkflowStatus) => void;
    setSubmissionId: (id: string) => void;
    addLog: (log: string) => void;
    updateNodeStatus: (nodeId: string, status: NodeStatus, message?: string) => void;
    setParallelAgents: (nodeId: string, agents: GradingAgent[]) => void;
    updateAgentStatus: (agentId: string, update: Partial<GradingAgent>) => void;
    addAgentLog: (agentId: string, log: string) => void;
    setFinalResults: (results: StudentResult[]) => void;
    reset: () => void;
    setSelectedNodeId: (id: string | null) => void;
    setSelectedAgentId: (id: string | null) => void;
    connectWs: (batchId: string) => void;
}

const initialNodes: WorkflowNode[] = [
    { id: 'intake', label: 'Intake', status: 'pending' },
    { id: 'preprocess', label: 'Preprocess', status: 'pending' },
    { id: 'segment', label: 'Segment', status: 'pending' },
    { id: 'grading', label: 'AI Grading', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'review', label: 'Review', status: 'pending' },
    { id: 'export', label: 'Export', status: 'pending' },
];

export const useConsoleStore = create<ConsoleState>((set, get) => ({
    view: 'LANDING',
    currentTab: 'process',
    status: 'IDLE',
    submissionId: null,
    selectedNodeId: null,
    selectedAgentId: null,
    logs: [],
    workflowNodes: initialNodes,
    finalResults: [],

    setView: (view) => set({ view }),
    setCurrentTab: (tab) => set({ currentTab: tab }),
    setStatus: (status) => set({ status }),
    setSubmissionId: (id) => set({ submissionId: id }),
    addLog: (log) => set((state) => ({
        logs: [...state.logs, `[${new Date().toLocaleTimeString()}] ${log}`]
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
        logs: [],
        finalResults: [],
        workflowNodes: initialNodes.map(n => ({
            ...n,
            status: 'pending' as NodeStatus,
            message: undefined,
            children: n.isParallelContainer ? [] : undefined
        }))
    }),

    setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedAgentId: null }),
    setSelectedAgentId: (id) => set({ selectedAgentId: id }),

    connectWs: (batchId) => {
        const wsUrl = process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://localhost:8001';
        wsClient.connect(`${wsUrl}/batch/ws/${batchId}`);

        // 处理工作流节点更新
        wsClient.on('workflow_update', (data) => {
            console.log('Workflow Update:', data);
            const { nodeId, status, message } = data;
            get().updateNodeStatus(nodeId, status, message);
            if (message) {
                get().addLog(message);
            }
        });

        // 处理并行 Agent 创建
        wsClient.on('parallel_agents_created', (data) => {
            console.log('Parallel Agents Created:', data);
            const { parentNodeId, agents } = data;
            get().setParallelAgents(parentNodeId, agents);
            get().addLog(`创建了 ${agents.length} 个批改 Agent`);
        });

        // 处理单个 Agent 更新
        wsClient.on('agent_update', (data) => {
            console.log('Agent Update:', data);
            const { agentId, status, progress, message, output, logs } = data;
            get().updateAgentStatus(agentId, { status, progress, output });
            if (logs && logs.length > 0) {
                logs.forEach((log: string) => get().addAgentLog(agentId, log));
            }
            if (message) {
                get().addLog(message);
            }
        });

        // 处理工作流完成
        wsClient.on('workflow_completed', (data) => {
            console.log('Workflow Completed:', data);
            set({ status: 'COMPLETED' });
            get().addLog(data.message || '工作流完成');

            // 保存最终结果并自动切换到结果页
            if (data.results && Array.isArray(data.results)) {
                get().setFinalResults(data.results);
                // 延迟切换到结果页，让用户看到完成状态
                setTimeout(() => {
                    set({ currentTab: 'results' });
                }, 1500);
            }
        });

        // 处理工作流错误
        wsClient.on('workflow_error', (data) => {
            console.log('Workflow Error:', data);
            set({ status: 'FAILED' });
            get().addLog(`错误: ${data.message}`);
        });
    }
}));
