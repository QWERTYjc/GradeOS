import { create } from 'zustand';
import { wsClient } from '@/services/ws';

export interface LogEntry {
    timestamp: string;
    level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
    message: string;
}

export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface FlowNode {
    id: string;
    label: string;
    type: 'node' | 'process' | 'step'; // node=High Level, process=Worker/Agent, step=Atomic
    parentId?: string;
    status: NodeStatus;
    startTime?: string;
    endTime?: string;
    inputs?: any;
    outputs?: any;
    logs: LogEntry[];
    aiScan?: string; // For particle effect intensity
    aiStreamContent: string; // Accumulated AI output
    error?: string;
    children: string[];
    isExpanded?: boolean;
}

export interface TimelineEvent {
    id: string;
    ts: string;
    type: string;
    title: string;
    detail?: string;
    nodeId?: string;
}

export interface FlowState {
    runId: string | null;
    isConnected: boolean;
    lastUpdated: string | null;
    nodes: Record<string, FlowNode>;
    rootNodes: string[]; // Top level nodes
    events: TimelineEvent[];

    // Actions
    connect: (runId: string) => void;
    disconnect: () => void;
    reset: () => void;

    // Internal reducers exposed as actions for WS callbacks
    handleEvent: (event: any) => void;
    toggleNode: (nodeId: string) => void;
}

// 1:1 Mapping helpers
const NODE_LABELS: Record<string, string> = {
    'intake': 'Data Intake',
    'preprocess': 'Image Preprocessing',
    'rubric_parse': 'Rubric Analysis',
    'grading': 'Batch Grading Orchestrator',
    'grading_fanout_router': 'Map Reduce Router',
    'segment': 'Identity Segmentation',
    'review': 'Safety & Confidence Review',
    'export': 'Final Export'
};

export const useFlowStore = create<FlowState>((set, get) => ({
    runId: null,
    isConnected: false,
    lastUpdated: null,
    nodes: {},
    rootNodes: [],
    events: [],

    connect: (runId) => {
        // Disconnect previous first
        get().disconnect();

        // Reset state
        set({
            runId,
            nodes: {},
            rootNodes: [],
            events: [],
            isConnected: true,
            lastUpdated: new Date().toISOString()
        });

        // Initialize predefined graph structure (to avoid empty screen start)
        const skeletonNodes = Object.keys(NODE_LABELS).map(key => ({
            id: key,
            label: NODE_LABELS[key],
            type: 'node' as const,
            status: 'pending' as NodeStatus,
            logs: [],
            aiStreamContent: '',
            children: []
        }));

        const nodesMap: Record<string, FlowNode> = {};
        skeletonNodes.forEach(n => nodesMap[n.id] = n);

        set({
            nodes: nodesMap,
            rootNodes: ['intake', 'preprocess', 'rubric_parse', 'grading', 'segment', 'review', 'export']
        });

        const wsUrl = process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://127.0.0.1:8001';
        wsClient.connect(`${wsUrl}/batch/ws/${runId}`); // runId is used as batchId in this simplified context

        // Bind events
        wsClient.on('connected', () => {
            set({ isConnected: true });
            get().handleEvent({ type: 'system', message: 'Connected to Workflow Stream' });
        });

        wsClient.on('disconnect', () => {
            set({ isConnected: false });
        });

        // Generic Event Handler
        const eventTypes = [
            'workflow_update',
            'ai_delta',
            'workflow_error',
            'workflow_completed',
            'page_graded',
            'batch_completed'
        ];

        eventTypes.forEach(type => {
            wsClient.on(type, (data) => get().handleEvent({ type, ...data }));
        });
    },

    disconnect: () => {
        wsClient.disconnect();
        set({ isConnected: false });
    },

    reset: () => set({ runId: null, nodes: {}, events: [] }),

    toggleNode: (nodeId) => set(state => ({
        nodes: {
            ...state.nodes,
            [nodeId]: {
                ...state.nodes[nodeId],
                isExpanded: !state.nodes[nodeId].isExpanded
            }
        }
    })),

    handleEvent: (event) => {
        const ts = new Date().toISOString();
        set({ lastUpdated: ts });

        // Add to timeline
        const timelineEvent: TimelineEvent = {
            id: Math.random().toString(36).substring(7),
            ts,
            type: event.type,
            title: event.type,
            detail: event.message || JSON.stringify(event.data || {}).slice(0, 50),
            nodeId: event.nodeId
        };

        set(state => ({ events: [timelineEvent, ...state.events].slice(0, 100) }));

        // Update Nodes
        if (event.type === 'workflow_update') {
            const { nodeId, status, message } = event;
            const targetId = nodeId || 'unknown';

            set(state => {
                let currentNode = state.nodes[targetId];

                // Dynamic Node Creation (if not exists)
                if (!currentNode) {
                    // Try to infer parent from ID like 'grading:page_1' or 'grading_page_1'
                    const isChild = targetId.includes(':') || targetId.includes('_page_');
                    const parentId = isChild ? (targetId.split(/[:_]/)[0] || 'grading') : undefined;

                    currentNode = {
                        id: targetId,
                        label: targetId,
                        type: isChild ? 'process' : 'node',
                        status: status as NodeStatus,
                        logs: [],
                        aiStreamContent: '',
                        children: [],
                        parentId
                    };

                    // Add to nodes map
                    state.nodes[targetId] = currentNode;

                    // Link to parent or root
                    if (parentId && state.nodes[parentId]) {
                        // Only add unique children
                        if (!state.nodes[parentId].children.includes(targetId)) {
                            state.nodes[parentId] = {
                                ...state.nodes[parentId],
                                children: [...state.nodes[parentId].children, targetId]
                            };
                        }
                    }
                }

                return {
                    nodes: {
                        ...state.nodes,
                        [targetId]: {
                            ...state.nodes[targetId],
                            status: status as NodeStatus,
                            logs: message ? [...state.nodes[targetId].logs, { timestamp: ts, level: status === 'failed' ? 'ERROR' : 'INFO', message }] : state.nodes[targetId].logs,
                            endTime: status === 'completed' || status === 'failed' ? ts : undefined,
                            startTime: status === 'running' && !state.nodes[targetId].startTime ? ts : state.nodes[targetId].startTime
                        }
                    }
                };
            });
        }

        if (event.type === 'ai_delta') {
            const { nodeId, data } = event;
            if (nodeId && data.content) {
                set(state => ({
                    nodes: {
                        ...state.nodes,
                        [nodeId]: {
                            ...state.nodes[nodeId],
                            aiStreamContent: (state.nodes[nodeId]?.aiStreamContent || '') + data.content,
                            aiScan: 'active' // trigger visual effect
                        }
                    }
                }));
            }
        }
    }
}));
