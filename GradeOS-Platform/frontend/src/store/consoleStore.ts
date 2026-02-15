import { create } from 'zustand';
import { wsClient, buildWsUrl } from '@/services/ws';
import { GradingAnnotationResult } from '@/types/annotation';
import { gradingApi } from '@/services/api';
import { normalizeStudentResults } from '@/lib/gradingResults';
import {
    applyStageSignal,
    buildMissingStageReason,
    canFinalizeWithGate,
    createInitialRequiredStageSeen,
    deriveStageSignalsFromResultsContext,
    deriveStageFromNodeUpdate,
    normalizeWorkflowNodeId,
    normalizeWorkflowStage,
    type RequiredStageSeen,
} from '@/lib/completionGate';

export type WorkflowStatus = 'IDLE' | 'UPLOADING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'REVIEWING';
export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ConsoleTab = 'process' | 'results';

const isNodeStatus = (value: unknown): value is NodeStatus =>
    value === 'pending' || value === 'running' || value === 'completed' || value === 'failed';

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
        streamingText?: string;
        reviewSummary?: {
            totalQuestions?: number;
            averageConfidence?: number;
            lowConfidenceCount?: number;
            notes?: string;
        };
        selfAudit?: SelfAudit;
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
    pointId?: string;           // 璇勫垎鐐圭紪锟?(e.g., "1.1", "1.2")
    description: string;
    score: number;
    maxScore: number;
    isCorrect: boolean;
    explanation: string;
    isRequired?: boolean;
    keywords?: string[];
}

export interface AuditInfo {
    confidence?: number;
    uncertainties?: string[];
    riskFlags?: string[];
    needsReview?: boolean;
    updatedAt?: string;
}

export interface QuestionResult {
    questionId: string;
    score: number;
    maxScore: number;
    feedback?: string;
    studentAnswer?: string;
    questionType?: string;
    confidence?: number;
    confidenceReason?: string;
    selfCritique?: string;
    selfCritiqueConfidence?: number;
    rubricRefs?: string[];
    reviewSummary?: string;
    reviewCorrections?: Array<{
        pointId: string;
        reviewReason?: string;
    }>;
    needsReview?: boolean;
    reviewReasons?: string[];
    auditFlags?: string[];
    honestyNote?: string;
    /** Per-question confession items (from ConfessionReport v1) */
    confessionItems?: any[];
    typoNotes?: string[];
    scoringPoints?: ScoringPoint[];
    /** 寰楀垎鐐规槑缁嗗垪琛紙鏂版牸寮忥級 */
    scoringPointResults?: Array<{
        pointId?: string;
        scoringPoint?: ScoringPoint;
        description?: string;
        awarded: number;
        maxPoints?: number;
        evidence: string;
        rubricReference?: string;
        rubricReferenceSource?: string;
        decision?: string;
        reason?: string;
        reviewAdjusted?: boolean;
        reviewBefore?: {
            awarded?: number;
            decision?: string;
            reason?: string;
            evidence?: string;
        };
        reviewReason?: string;
        reviewBy?: string;
        /** 閿欒鍖哄煙鍧愭爣 */
        errorRegion?: {
            x_min: number;
            y_min: number;
            x_max: number;
            y_max: number;
        };
    }>;
    /** 鍑虹幇鍦ㄥ摢浜涢〉?- 鏂板 */
    pageIndices?: number[];
    /** 鏄惁璺ㄩ〉棰樼洰 - 鏂板 */
    isCrossPage?: boolean;
    /** 鍚堝苟鏉ユ簮锛堝鏋滄槸鍚堝苟缁撴灉? 鏂板 */
    mergeSource?: string[];
    /** 棰樼洰瀹¤淇℃伅锛堢敱 LLM 鐢熸垚锛屽鏍稿彲鏇存柊锛?*/
    audit?: AuditInfo;
    /** 椤甸潰绱㈠紩 (snake_case) */
    page_index?: number;
    /** 椤甸潰绱㈠紩 (camelCase) */
    pageIndex?: number;
    /** 鎵规敞鍧愭爣鍒楄〃 */
    annotations?: Array<{
        type: string;
        page_index?: number;
        bounding_box: {
            x_min: number;
            y_min: number;
            x_max: number;
            y_max: number;
        };
        text?: string;
        color?: string;
    }>;
    /** 姝ラ淇℃伅锛堝寘鍚潗鏍囷級 */
    steps?: Array<{
        step_id: string;
        step_content: string;
        step_region?: {
            x_min: number;
            y_min: number;
            x_max: number;
            y_max: number;
            page_index?: number;
            pageIndex?: number;
        };
        is_correct: boolean;
        mark_type: string;
        mark_value: number;
        feedback?: string;
        error_detail?: string;
        page_index?: number;
        pageIndex?: number;
    }>;
    /** 绛旀鍖哄煙鍧愭爣 */
    answerRegion?: {
        x_min: number;
        y_min: number;
        x_max: number;
        y_max: number;
        page_index?: number;
        pageIndex?: number;
    };
}

// Interface definition
export interface LLMThought {
    id: string;
    nodeId: string;
    nodeName: string;
    agentId?: string;
    agentLabel?: string;
    streamType?: 'thinking' | 'output';
    pageIndex?: number;
    content: string;
    timestamp: number;
    isComplete: boolean;
}

export interface StudentResult {
    studentName: string;
    score: number;
    maxScore: number;
    gradingMode?: string;
    percentage?: number;
    totalRevisions?: number;
    questionResults?: QuestionResult[];
    studentSummary?: StudentSummary;
    selfAudit?: SelfAudit;
    /** 璧峰椤?*/
    startPage?: number;
    /** 缁撴潫椤?*/
    endPage?: number;
    /** 缃俊搴?*/
    confidence?: number;
    /** 鏄惁闇€瑕佷汉宸ョ‘璁?*/
    needsConfirmation?: boolean;
    /** 鑷櫧鎶ュ憡 */
    confession?: {
        // ConfessionReport v1 (preferred)
        version?: string;
        scope?: string;
        subject_id?: string;
        overall_confidence?: number;
        risk_score?: number;
        objectives?: any[];
        items?: any[];
        honesty?: any;
        budget?: any;
        generated_at?: string;

        // Frontend convenience aliases (may be added by backend/normalizer)
        overallStatus?: string;
        overallConfidence?: number;
        riskScore?: number;

        // Legacy keys (older runs)
        issues?: Array<{ questionId?: string; message?: string }>;
        warnings?: Array<{ questionId?: string; message?: string }>;
        highRiskQuestions?: Array<{ questionId?: string; description?: string }>;
        potentialErrors?: Array<{ questionId?: string; description?: string }>;
        generatedAt?: string;
        source?: string;
    };
    /** 绗竴娆℃壒鏀硅褰曪紙閫昏緫澶嶆牳鍓嶇殑鍘熷缁撴灉锛?*/
    draftQuestionDetails?: QuestionResult[];
    /** 绗竴娆℃壒鏀规€诲垎 */
    draftTotalScore?: number;
    /** 绗竴娆℃壒鏀规弧鍒?*/
    draftMaxScore?: number;
    /** 閫昏緫澶嶆牳 */
    logicReview?: any;
    /** 閫昏緫澶嶆牳鏃堕棿 */
    logicReviewedAt?: string;
    /** 椤甸潰鑼冨洿锛堟樉绀虹敤锛?*/
    pageRange?: string;
    /** 椤甸潰鍒楄〃 */
    pages?: string;
    /** 鎵规敞缁撴灉锛堟寜椤碉級 */
    gradingAnnotations?: GradingAnnotationResult;
}

export interface KnowledgePointSummary {
    questionId?: string;
    pointId?: string;
    description?: string;
    score?: number;
    maxScore?: number;
    masteryLevel?: string;
    ratio?: number;
    evidence?: string;
    rubricReference?: string;
}

export interface StudentSummary {
    overall?: string;
    percentage?: number;
    knowledgePoints?: KnowledgePointSummary[];
    improvementSuggestions?: string[];
    generatedAt?: string;
}

export interface SelfAuditIssue {
    issueType?: string;
    message?: string;
    questionId?: string;
}

export interface SelfAudit {
    summary?: string;
    confidence?: number;
    issues?: SelfAuditIssue[];
    complianceAnalysis?: Array<{
        goal?: string;
        tag?: string;
        notes?: string;
        evidence?: string;
    }>;
    uncertaintiesAndConflicts?: Array<{
        issue?: string;
        impact?: string;
        questionIds?: string[];
        reportedToUser?: boolean;
    }>;
    overallComplianceGrade?: number;
    honestyNote?: string;
    generatedAt?: string;
}

export interface ClassReport {
    totalStudents?: number;
    averageScore?: number;
    averagePercentage?: number;
    passRate?: number;
    scoreDistribution?: Record<string, number>;
    weakPoints?: Array<{ pointId?: string; description?: string; masteryRatio?: number }>;
    strongPoints?: Array<{ pointId?: string; description?: string; masteryRatio?: number }>;
    summary?: string;
    generatedAt?: string;
}

export interface PendingReview {
    reviewType: string;
    batchId?: string;
    message?: string;
    requestedAt?: string;
    payload: any;
}

// Interface definition
export interface CrossPageQuestion {
    questionId: string;
    pageIndices: number[];
    confidence: number;
    mergeReason: string;
}

// Interface definition
export interface StudentBoundary {
    studentKey: string;
    startPage: number;
    endPage: number;
    confidence: number;
    needsConfirmation: boolean;
}

// Interface definition
export interface BatchProgress {
    batchIndex: number;
    totalBatches: number;
    successCount: number;
    failureCount: number;
    processingTimeMs?: number;
}

// Interface definition
export interface RubricScoringPoint {
    pointId?: string;
    description: string;
    expectedValue?: string;
    score: number;
    isRequired: boolean;
    keywords?: string[];
}

// 瑙ｆ瀽鐨勮瘎鍒嗘爣锟?- 鍙︾被瑙ｆ硶
export interface RubricAlternativeSolution {
    description: string;
    scoringCriteria: string;
    note?: string;
}

// 瑙ｆ瀽鐨勮瘎鍒嗘爣锟?- 鍗曢璇︽儏
export interface RubricQuestion {
    questionId: string;
    maxScore: number;
    questionText?: string;
    standardAnswer?: string;
    scoringPoints: RubricScoringPoint[];
    alternativeSolutions?: RubricAlternativeSolution[];
    gradingNotes?: string;
    criteria?: string[];
    sourcePages?: number[];
    // 瑙ｆ瀽鑷櫧瀛楁
    parseConfidence?: number;
    parseUncertainties?: string[];
    parseQualityIssues?: string[];
}

// 瑙ｆ瀽鐨勮瘎鍒嗘爣鍑嗕俊鎭紙瀹屾暣鐗堬級
export interface ParsedRubric {
    totalQuestions: number;
    totalScore: number;
    questions?: RubricQuestion[];
    generalNotes?: string;
    rubricFormat?: string;
    // LLM generated confession summary (short form)
    confession?: {
        risks?: string[];
        uncertainties?: string[];
        blindSpots?: string[];
        needsReview?: string[];
        confidence?: number;
    };
    // 瑙ｆ瀽鑷櫧鐩稿叧瀛楁
    overallParseConfidence?: number;
    parseConfession?: {  // confession parse report
        overallStatus: 'ok' | 'caution' | 'error';
        overallConfidence: number;
        summary: string;
        issues: Array<{
            type: string;
            message: string;
            questionId?: string;
            severity: 'low' | 'medium' | 'high';
        }>;
        uncertainties: string[];
        qualityChecks: Array<{
            check: string;
            passed: boolean;
            detail?: string;
        }>;
        questionsWithIssues?: string[];
        generatedAt: string;
        parseMethod?: string;
    };
}

// === 鑷垜鎴愰暱绯荤粺绫诲瀷瀹氫箟 ===

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
    // 鍒や緥淇℃伅閫氬父涓庣壒锟?Agent/Page 鍏宠仈锛岃繖閲屽瓨鍌ㄦ渶杩戞绱㈠埌鐨勫垽渚嬬敤浜庡睍锟?
    recentExemplars: ExemplarInfo[];
}

// === 鐝骇鎵规敼涓婁笅锟?===

export interface ClassStudent {
    id: string;
    name: string;
    username?: string;
}

export interface StudentImageMapping {
    studentId: string;
    studentName: string;
    startIndex: number; // 璇ュ鐢熺殑璧峰鍥剧墖绱㈠紩
    endIndex: number;   // 璇ュ鐢熺殑缁撴潫鍥剧墖绱㈠紩 (inclusive)
}

export interface ClassContext {
    classId: string | null;
    homeworkId: string | null;
    className: string | null;
    homeworkName: string | null;
    students: ClassStudent[];
    studentImageMapping: StudentImageMapping[];
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
    interactionEnabled: boolean;
    gradingMode: string;
    nodeStatusTimestamps: Record<string, number>;
    nodeStatusTimers: Record<string, ReturnType<typeof setTimeout>>;

    // 鏂板锛氳嚜鎴戞垚闀跨郴缁熺姸锟?
    parsedRubric: ParsedRubric | null;
    batchProgress: BatchProgress | null;
    studentBoundaries: StudentBoundary[];
    selfEvolving: SelfEvolvingState;
    // 鏂板锛氳法椤甸鐩俊锟?
    crossPageQuestions: CrossPageQuestion[];
    // 鏂板锛歀LM 鎬濊€冭繃锟?
    llmThoughts: LLMThought[];
    // 鏂板锛氫笂浼犵殑鍥剧墖 (鐢ㄤ簬缁撴灉椤靛睍锟?
    uploadedImages: string[];  // base64 锟?URL
    rubricImages: string[];
    pendingReview: PendingReview | null;
    classReport: ClassReport | null;
    // 鏂板锛氱彮绾ф壒鏀逛笂涓嬫枃
    classContext: ClassContext;
    reviewFocus: 'rubric' | 'results' | null;
    expectedTotalScore: number | null;
    rubricScoreMismatch: {
        expectedTotalScore: number;
        parsedTotalScore: number;
        message: string;
    } | null;
    rubricParseError: {
        message: string;
        details?: string;
    } | null;
    completionBlockedReason: string | null;
    requiredStageSeen: RequiredStageSeen;
    lastObservedStage: string | null;
    pendingTerminalEvent: boolean;

    setView: (view: 'LANDING' | 'CONSOLE') => void;
    setCurrentTab: (tab: ConsoleTab) => void;
    setStatus: (status: WorkflowStatus) => void;
    setSubmissionId: (id: string) => void;
    addLog: (log: string, level?: LogEntry['level']) => void;
    updateNodeStatus: (nodeId: string, status: NodeStatus, message?: string) => void;
    setParallelAgents: (nodeId: string, agents: GradingAgent[]) => void;
    updateAgentStatus: (agentId: string, update: Partial<GradingAgent>, parentNodeId?: string) => void;
    addAgentLog: (agentId: string, log: string) => void;
    setFinalResults: (results: StudentResult[]) => void;
    reset: () => void;
    setSelectedNodeId: (id: string | null) => void;
    setSelectedAgentId: (id: string | null) => void;
    toggleMonitor: () => void;
    connectWs: (batchId: string) => void;

    // 鏂板锛氳嚜鎴戞垚闀跨郴缁熸柟锟?
    setParsedRubric: (rubric: ParsedRubric) => void;
    setBatchProgress: (progress: BatchProgress) => void;
    setStudentBoundaries: (boundaries: StudentBoundary[]) => void;
    updateSelfEvolving: (update: Partial<SelfEvolvingState>) => void;
    // 鏂板锛氳法椤甸鐩柟锟?
    setCrossPageQuestions: (questions: CrossPageQuestion[]) => void;
    // 鏂板锛歀LM 鎬濊€冩柟锟?
    appendLLMThought: (
        nodeId: string,
        nodeName: string,
        chunk: any,
        pageIndex?: number,
        streamType?: 'thinking' | 'output',
        agentId?: string,
        agentLabel?: string
    ) => void;
    completeLLMThought: (nodeId: string, pageIndex?: number, streamType?: 'thinking' | 'output', agentId?: string) => void;
    clearLLMThoughts: () => void;
    // 鏂板锛氬浘鐗囨柟锟?
    setUploadedImages: (images: string[]) => void;
    setRubricImages: (images: string[]) => void;
    setPendingReview: (review: PendingReview | null) => void;
    setClassReport: (report: ClassReport | null) => void;
    // 鏂板锛氱彮绾ф壒鏀逛笂涓嬫枃鏂规硶
    setClassContext: (context: Partial<ClassContext>) => void;
    clearClassContext: () => void;
    setInteractionEnabled: (enabled: boolean) => void;
    setGradingMode: (mode: string) => void;
    setReviewFocus: (focus: 'rubric' | 'results' | null) => void;
    setExpectedTotalScore: (score: number | null) => void;
    setRubricScoreMismatch: (
        mismatch: {
            expectedTotalScore: number;
            parsedTotalScore: number;
            message: string;
        } | null
    ) => void;
    setRubricParseError: (error: { message: string; details?: string } | null) => void;
}

const normalizeImageSource = (value: string) => {
    if (!value) {
        return value;
    }
    if (value.startsWith('data:') || value.startsWith('http') || value.startsWith('blob:') || value.startsWith('/')) {
        return value;
    }
    return `data:image/jpeg;base64,${value}`;
};

const normalizeNodeId = (value: string) => {
    if (!value) {
        return value;
    }
    const compact = value.trim().toLowerCase().replace(/\s+/g, '_');
    const base = compact
        .split(':', 1)[0]
        .split('.', 1)[0]
        .split('/', 1)[0]
        .replace(/-+/g, '_');

    const aliasMap: Record<string, string> = {
        index_node: 'index',
        indexer: 'index',
        grading: 'grade_batch',
        grade_student: 'grade_batch',
        batch_grading: 'grade_batch',
        confession: 'grading_confession_report',
        confession_report: 'grading_confession_report',
        grading_confession: 'grading_confession_report',
        final_review: 'review',
    };
    const aliased = aliasMap[base] || base;
    return normalizeWorkflowNodeId(aliased) || aliased;
};

const STREAM_DEDUPE_MIN_CHARS = 6;
const STREAM_MAX_OVERLAP_CHARS = 4096;

const clipStreamTail = (value: string, maxChars: number) => {
    if (maxChars <= 0 || value.length <= maxChars) {
        return value;
    }
    return value.slice(-maxChars);
};

const mergeStreamChunk = (currentText: string, incomingChunk: string, maxChars: number) => {
    const current = currentText || '';
    const incoming = incomingChunk || '';

    if (!incoming) {
        return clipStreamTail(current, maxChars);
    }
    if (!current) {
        return clipStreamTail(incoming, maxChars);
    }
    if (incoming === current) {
        return clipStreamTail(current, maxChars);
    }

    // Handle reconnect snapshots / repeated payloads safely.
    if (incoming.length >= STREAM_DEDUPE_MIN_CHARS) {
        if (current.endsWith(incoming) || current.includes(incoming)) {
            return clipStreamTail(current, maxChars);
        }
    }
    if (incoming.length >= current.length && incoming.startsWith(current)) {
        return clipStreamTail(incoming, maxChars);
    }
    if (current.length >= STREAM_DEDUPE_MIN_CHARS && incoming.includes(current)) {
        return clipStreamTail(incoming, maxChars);
    }

    // Merge overlap suffix(current) + prefix(incoming) to avoid duplicated joints.
    if (incoming.length >= STREAM_DEDUPE_MIN_CHARS) {
        const maxOverlap = Math.min(current.length, incoming.length, STREAM_MAX_OVERLAP_CHARS);
        for (let overlap = maxOverlap; overlap >= STREAM_DEDUPE_MIN_CHARS; overlap -= 1) {
            if (current.slice(-overlap) === incoming.slice(0, overlap)) {
                return clipStreamTail(current + incoming.slice(overlap), maxChars);
            }
        }
    }

    return clipStreamTail(current + incoming, maxChars);
};

/**
 * 宸ヤ綔娴佽妭鐐归厤锟? * 
 * 鍩轰簬 LangGraph 鏋舵瀯鐨勫墠绔睍绀烘祦绋嬶紙闅愯棌鍐呴儴 merge 鑺傜偣锛夛細
 * 1. intake - 鎺ユ敹鏂囦欢
 * 2. preprocess - 棰勫鐞嗭紙杞浘銆佸帇缂┿€佽竟鐣?绱㈠紩绛夛級
 * 3. rubric_parse - 瑙ｆ瀽璇勫垎鏍囧噯
 * 4. rubric_confession_report - Rubric confession (independent honesty report)
 * 5. rubric_self_review - 璇勫垎鏍囧噯鑷姩澶嶆牳
 * 6. rubric_review - 璇勫垎鏍囧噯浜哄伐浜や簰锛堝彲閫夛級
 * 7. grade_batch - 鎸夊鐢熸壒娆″苟琛屾壒鏀? * 8. grading_confession_report - Grading confession (independent honesty report)
 * 9. logic_review - 鎵规敼閫昏緫澶嶆牳锛堝彲閫夛紝confession 瑙﹀彂锛? * 10. review - 鎵规敼缁撴灉浜哄伐浜や簰锛堝彲閫夛級
 * 11. export - 瀵煎嚭缁撴灉
 * 
 * 鍚庣 LangGraph Graph 娴佺▼锛堝惈鍐呴儴鑺傜偣锛夛細
 * intake -> preprocess -> rubric_parse -> rubric_confession_report -> rubric_self_review -> rubric_review
 * -> grade_batch -> grading_confession_report -> logic_review -> review -> export -> END
 */
const initialNodes: WorkflowNode[] = [
    { id: 'intake', label: 'Intake', status: 'pending' },
    { id: 'preprocess', label: 'Preprocess', status: 'pending' },
    { id: 'rubric_parse', label: 'Rubric Parse', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'rubric_confession_report', label: 'Rubric Confession', status: 'pending' },
    { id: 'rubric_self_review', label: 'Auto Review', status: 'pending' },
    { id: 'rubric_review', label: 'Rubric Review', status: 'pending' },
    { id: 'grade_batch', label: 'Student Grading', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'grading_confession_report', label: 'Grading Confession', status: 'pending' },
    { id: 'logic_review', label: 'Logic Review', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'review', label: 'Results Review', status: 'pending' },
    { id: 'export', label: 'Export', status: 'pending' },
];

const POST_LOGIC_REVIEW_HOLD_MESSAGE = 'Blocked until logic_review_completed';

const STAGE_STATE_MAP: Record<string, { node: string; status: NodeStatus; message?: string }> = {
    rubric_parse_completed: { node: 'rubric_parse', status: 'completed' },
    rubric_confession_report_completed: { node: 'rubric_confession_report', status: 'completed' },
    rubric_confession_report_skipped: { node: 'rubric_confession_report', status: 'pending', message: 'Skipped' },
    rubric_self_review_completed: { node: 'rubric_self_review', status: 'completed' },
    rubric_self_review_skipped: { node: 'rubric_self_review', status: 'pending', message: 'Skipped' },
    rubric_self_review_failed: { node: 'rubric_self_review', status: 'failed' },
    rubric_review_completed: { node: 'rubric_review', status: 'completed' },
    rubric_review_skipped: { node: 'rubric_review', status: 'pending', message: 'Skipped' },
    grade_batch_completed: { node: 'grade_batch', status: 'completed' },
    cross_page_merge_completed: { node: 'grade_batch', status: 'completed' },
    index_merge_completed: { node: 'grade_batch', status: 'completed' },
    grading_confession_report_completed: { node: 'grading_confession_report', status: 'completed' },
    logic_review_completed: { node: 'logic_review', status: 'completed' },
    logic_review_skipped: { node: 'logic_review', status: 'pending', message: 'Skipped' },
    review_completed: { node: 'review', status: 'completed' },
    completed: { node: 'export', status: 'completed' },
};

const NODE_MIN_TRANSITION_MS = 2200;

const normalizeStudentSummary = (summary: any): StudentSummary | undefined => {
    if (!summary || typeof summary !== 'object') return undefined;
    const rawPoints = summary.knowledgePoints || summary.knowledge_points || [];
    const knowledgePoints = Array.isArray(rawPoints)
        ? rawPoints.map((point: any) => ({
            questionId: point.questionId || point.question_id,
            pointId: point.pointId || point.point_id,
            description: point.description,
            score: point.score,
            maxScore: point.maxScore ?? point.max_score,
            masteryLevel: point.masteryLevel || point.mastery_level,
            ratio: point.ratio,
            evidence: point.evidence,
            rubricReference: point.rubricReference || point.rubric_reference,
        }))
        : [];

    return {
        overall: summary.overall,
        percentage: summary.percentage,
        knowledgePoints,
        improvementSuggestions: summary.improvementSuggestions || summary.improvement_suggestions || [],
        generatedAt: summary.generatedAt || summary.generated_at,
    };
};

const normalizeParsedRubricPayload = (data: any): ParsedRubric | null => {
    if (!data || typeof data !== 'object') return null;
    const totalQuestions = data.totalQuestions ?? data.total_questions ?? 0;
    const totalScore = data.totalScore ?? data.total_score ?? 0;
    const rawQuestions = data.questions ?? data.question_list;
    const questions = Array.isArray(rawQuestions)
        ? rawQuestions.map((q: any) => ({
            questionId: q.questionId || q.question_id || '',
            maxScore: q.maxScore ?? q.max_score ?? 0,
            questionText: q.questionText || q.question_text || '',
            standardAnswer: q.standardAnswer || q.standard_answer || '',
            gradingNotes: q.gradingNotes || q.grading_notes || '',
            criteria: q.criteria || [],
            sourcePages: q.sourcePages || q.source_pages || [],
            parseConfidence: q.parseConfidence ?? q.parse_confidence ?? 1.0,
            parseUncertainties: q.parseUncertainties || q.parse_uncertainties || [],
            parseQualityIssues: q.parseQualityIssues || q.parse_quality_issues || [],
            scoringPoints: (q.scoringPoints || q.scoring_points || []).map((sp: any) => ({
                pointId: sp.pointId || sp.point_id || '',
                description: sp.description || '',
                expectedValue: sp.expectedValue || sp.expected_value || '',
                score: sp.score ?? 0,
                isRequired: sp.isRequired ?? sp.is_required ?? true,
                keywords: sp.keywords || [],
            })),
            alternativeSolutions: (q.alternativeSolutions || q.alternative_solutions || []).map((alt: any) => ({
                description: alt.description || '',
                scoringCriteria: alt.scoringCriteria || alt.scoring_criteria || '',
                note: alt.note || '',
            })),
        }))
        : undefined;

    // 瑙勮寖鍖栬嚜鐧芥姤锟?
    const rawConfession =
        data.parseConfession ||
        data.parse_confession;
    const parseConfession = rawConfession ? {
        overallStatus: rawConfession.overallStatus || rawConfession.overall_status || 'ok',
        overallConfidence: rawConfession.overallConfidence ?? rawConfession.overall_confidence ?? 1.0,
        summary: rawConfession.summary || '',
        issues: (rawConfession.issues || []).map((issue: any) => ({
            type: issue.type || '',
            message: issue.message || '',
            questionId: issue.questionId || issue.question_id,
            severity: issue.severity || 'low',
        })),
        uncertainties: rawConfession.uncertainties || [],
        qualityChecks: (rawConfession.qualityChecks || rawConfession.quality_checks || []).map((check: any) => ({
            check: check.check || '',
            passed: check.passed ?? false,
            detail: check.detail || '',
        })),
        questionsWithIssues: rawConfession.questionsWithIssues || rawConfession.questions_with_issues || [],
        generatedAt: rawConfession.generatedAt || rawConfession.generated_at || '',
        parseMethod: rawConfession.parseMethod || rawConfession.parse_method || '',
    } : undefined;

    return {
        totalQuestions,
        totalScore,
        questions,
        generalNotes: data.generalNotes || data.general_notes || '',
        rubricFormat: data.rubricFormat || data.rubric_format || '',
        overallParseConfidence: data.overallParseConfidence ?? data.overall_parse_confidence ?? 1.0,
        parseConfession,
    };
};

const normalizeSelfAudit = (audit: any): SelfAudit | undefined => {
    if (!audit || typeof audit !== 'object') return undefined;
    const rawIssues = audit.issues || [];
    const issues = Array.isArray(rawIssues)
        ? rawIssues.map((issue: any) => ({
            issueType: issue.issueType || issue.issue_type,
            message: issue.message,
            questionId: issue.questionId || issue.question_id,
        }))
        : [];

    return {
        summary: audit.summary,
        confidence: audit.confidence,
        issues,
        complianceAnalysis: audit.complianceAnalysis || audit.compliance_analysis || [],
        uncertaintiesAndConflicts: audit.uncertaintiesAndConflicts || audit.uncertainties_and_conflicts || [],
        overallComplianceGrade: audit.overallComplianceGrade ?? audit.overall_compliance_grade,
        honestyNote: audit.honestyNote || audit.honesty_note,
        generatedAt: audit.generatedAt || audit.generated_at,
    };
};

const normalizeClassReport = (report: any): ClassReport | null => {
    if (!report || typeof report !== 'object') return null;
    const rawWeak = report.weakPoints || report.weak_points || [];
    const rawStrong = report.strongPoints || report.strong_points || [];
    const mapPoints = (points: any[]) => points.map((point) => ({
        pointId: point.pointId || point.point_id,
        description: point.description,
        masteryRatio: point.masteryRatio ?? point.mastery_ratio,
    }));
    return {
        totalStudents: report.totalStudents ?? report.total_students,
        averageScore: report.averageScore ?? report.average_score,
        averagePercentage: report.averagePercentage ?? report.average_percentage,
        passRate: report.passRate ?? report.pass_rate,
        scoreDistribution: report.scoreDistribution || report.score_distribution,
        weakPoints: Array.isArray(rawWeak) ? mapPoints(rawWeak) : [],
        strongPoints: Array.isArray(rawStrong) ? mapPoints(rawStrong) : [],
        summary: report.summary,
        generatedAt: report.generatedAt || report.generated_at,
    };
};

const extractResultsPayload = (payload: any): StudentResult[] | null => {
    if (!payload) return null;
    const results = payload.results || payload.studentResults || payload.student_results;
    return Array.isArray(results) ? results : null;
};

type PostReviewPollOptions = {
    onStageSignal?: (stage?: string | null) => void;
    isCompletionGateSatisfied?: () => boolean;
};

const waitForPostReviewResults = async (
    batchId: string,
    initialResults: StudentResult[] | null,
    options?: PostReviewPollOptions
) => {
    const stageSignal = options?.onStageSignal;
    const isCompletionGateSatisfied = options?.isCompletionGateSatisfied;

    if (initialResults && initialResults.length > 0 && (!isCompletionGateSatisfied || isCompletionGateSatisfied())) {
        return initialResults;
    }
    const pollIntervalMs = 4000;
    const maxAttempts = 30;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
        let fetchedResults: StudentResult[] | null = null;
        let shouldRefreshStage = !isCompletionGateSatisfied || !isCompletionGateSatisfied();
        try {
            const response = await gradingApi.getBatchResults(batchId);
            fetchedResults = extractResultsPayload(response);
            if (!fetchedResults || fetchedResults.length === 0) {
                shouldRefreshStage = true;
            }
        } catch (error) {
            console.warn('Polling results failed:', error);
            shouldRefreshStage = true;
        }
        if (shouldRefreshStage) {
            try {
                const reviewContext = await gradingApi.getResultsReviewContext(batchId);
                const stageDerivation = deriveStageSignalsFromResultsContext(reviewContext as any);
                stageDerivation.signals.forEach((signal) => stageSignal?.(signal));
                fetchedResults = extractResultsPayload(reviewContext) || (reviewContext as any)?.student_results || null;
            } catch (error) {
                console.warn('Polling results-review fallback failed:', error);
            }
        }
        if (fetchedResults && fetchedResults.length > 0) {
            if (!isCompletionGateSatisfied || isCompletionGateSatisfied()) {
                return fetchedResults;
            }
        }
    }
    return null;
};



export const useConsoleStore = create<ConsoleState>((set, get) => {
    // Store 鍐呴儴锟?WebSocket 澶勭悊鍣ㄦ敞鍐屾爣锟?
    let handlersRegistered = false;
    const LOGIC_REVIEW_SKIP_BLOCK_REASON = 'logic_review stage was skipped; completion is blocked by policy.';

    const canFinalizeCompletion = () => {
        const state = get();
        if (state.completionBlockedReason === LOGIC_REVIEW_SKIP_BLOCK_REASON) {
            return false;
        }
        return canFinalizeWithGate(state.requiredStageSeen, state.pendingTerminalEvent);
    };

    const recordStageSignal = (rawStage?: string | null) => {
        const normalized = normalizeWorkflowStage(rawStage);
        if (!normalized) return;
        set((state) => {
            const applied = applyStageSignal(state.requiredStageSeen, normalized);
            const nextRequired: RequiredStageSeen = applied.logicReviewSkipped
                ? { ...applied.required, logicReview: false }
                : applied.required;
            const nextTerminalSeen = state.pendingTerminalEvent || applied.terminalSeen;
            const gateSatisfied = canFinalizeWithGate(nextRequired, nextTerminalSeen);

            const hasSkipBlock = state.completionBlockedReason === LOGIC_REVIEW_SKIP_BLOCK_REASON;
            let nextBlockedReason = state.completionBlockedReason;
            if (applied.logicReviewSkipped || hasSkipBlock) {
                nextBlockedReason = LOGIC_REVIEW_SKIP_BLOCK_REASON;
            } else if (gateSatisfied) {
                nextBlockedReason = null;
            }

            return {
                requiredStageSeen: nextRequired,
                pendingTerminalEvent: nextTerminalSeen,
                lastObservedStage: applied.normalizedStage || state.lastObservedStage,
                completionBlockedReason: nextBlockedReason,
            };
        });
    };

    const shouldHoldPostLogicNodeCompletion = (nodeId: string, status: NodeStatus) =>
        status === 'completed'
        && (nodeId === 'review' || nodeId === 'export')
        && !get().requiredStageSeen.logicReview;

    const updateNodeStatusWithCompletionGate = (
        nodeId: string,
        status: NodeStatus,
        message?: string
    ) => {
        if (shouldHoldPostLogicNodeCompletion(nodeId, status)) {
            get().updateNodeStatus('logic_review', 'running', 'Waiting for logic review');
            get().updateNodeStatus(nodeId, 'pending', POST_LOGIC_REVIEW_HOLD_MESSAGE);
            return;
        }
        get().updateNodeStatus(nodeId, status, message);
    };

    const applyStageState = (rawStage?: string | null) => {
        const normalizedStage = normalizeWorkflowStage(rawStage);
        if (!normalizedStage) return;
        const stageState = STAGE_STATE_MAP[normalizedStage];
        if (!stageState) return;

        const pendingReview = get().pendingReview;
        const holdRubricReview = stageState.node === 'rubric_review'
            && pendingReview
            && (pendingReview.reviewType || '').includes('rubric');
        if (holdRubricReview) {
            get().updateNodeStatus(stageState.node, 'running', 'Waiting for interaction');
            return;
        }

        updateNodeStatusWithCompletionGate(stageState.node, stageState.status, stageState.message);
    };

    const blockCompletion = (reason?: string) => {
        const state = get();
        const fallbackReason =
            state.completionBlockedReason === LOGIC_REVIEW_SKIP_BLOCK_REASON
                ? LOGIC_REVIEW_SKIP_BLOCK_REASON
                : buildMissingStageReason(state.requiredStageSeen);
        const nextReason = reason || fallbackReason;
        if (state.completionBlockedReason !== nextReason) {
            get().addLog(`Completion blocked: ${nextReason}`, 'WARNING');
        }
        if (!state.requiredStageSeen.logicReview) {
            get().updateNodeStatus('logic_review', 'running', 'Waiting for logic review');
        }
        set((current) => ({
            completionBlockedReason: nextReason,
            status: current.status === 'FAILED' ? 'FAILED' : 'RUNNING',
        }));
    };

    const finalizeCompletion = (data: any, resultsOverride?: StudentResult[] | null) => {
        const message = data?.message || 'Workflow completed';
        get().addLog(message, 'SUCCESS');

        const resolvedResults = resultsOverride ?? extractResultsPayload(data);
        if (resolvedResults && resolvedResults.length > 0) {
            get().setFinalResults(resolvedResults);
            get().addLog(`Saved results for ${resolvedResults.length} students`, 'SUCCESS');
        }

        const classReport = data?.classReport || data?.class_report;
        if (classReport) {
            const normalizedReport = normalizeClassReport(classReport);
            if (normalizedReport) {
                get().setClassReport(normalizedReport);
            }
        }

        // Prevent delayed status timers from replaying stale "running" updates after completion.
        const activeTimers = Object.values(get().nodeStatusTimers);
        activeTimers.forEach((timer) => clearTimeout(timer));
        set({ nodeStatusTimers: {} });

        get().setStatus('COMPLETED');
        get().setPendingReview(null);
        get().setReviewFocus(null);

        set({
            completionBlockedReason: null,
            pendingTerminalEvent: true,
            lastObservedStage: 'completed',
        });

        const currentNodes = get().workflowNodes;
        currentNodes.forEach((node) => {
            if (node.status === 'running') {
                get().updateNodeStatus(node.id, 'completed');
            }
        });
        get().updateNodeStatus('logic_review', 'completed');
        get().updateNodeStatus('review', 'completed');
        get().updateNodeStatus('export', 'completed');
    };

    const maybeFinalizeCompletion = (data: any, resultsOverride?: StudentResult[] | null) => {
        if (canFinalizeCompletion()) {
            finalizeCompletion(data, resultsOverride);
            return true;
        }
        blockCompletion();
        return false;
    };

    return {
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
        interactionEnabled: false,
        gradingMode: 'auto',
        nodeStatusTimestamps: {},
        nodeStatusTimers: {},

        // 鑷垜鎴愰暱绯荤粺鐘舵€佸垵濮嬶拷?
        parsedRubric: null,
        batchProgress: null,
        studentBoundaries: [],
        selfEvolving: {
            calibration: null,
            activePatches: [],
            recentExemplars: []
        },
        // 璺ㄩ〉棰樼洰淇℃伅鍒濆锟?
        crossPageQuestions: [],
        // LLM 鎬濊€冭繃绋嬪垵濮嬶拷?
        llmThoughts: [],
        // 涓婁紶鐨勫浘鐗囧垵濮嬶拷?
        uploadedImages: [],
        rubricImages: [],
        pendingReview: null,
        classReport: null,
        // 鐝骇鎵规敼涓婁笅鏂囧垵濮嬶拷?
        classContext: {
            classId: null,
            homeworkId: null,
            className: null,
            homeworkName: null,
            students: [],
            studentImageMapping: [],
        },
        reviewFocus: null,
        expectedTotalScore: null,
        rubricScoreMismatch: null,
        rubricParseError: null,
        completionBlockedReason: null,
        requiredStageSeen: createInitialRequiredStageSeen(),
        lastObservedStage: null,
        pendingTerminalEvent: false,

        setView: (view) => set({ view }),
        setCurrentTab: (tab) => set({ currentTab: tab }),
        setStatus: (status) => set({ status }),
        setSubmissionId: (id) => set({ submissionId: id }),
        setInteractionEnabled: (enabled) => set({ interactionEnabled: enabled }),
        setGradingMode: (mode) => set({ gradingMode: mode }),
        setReviewFocus: (focus) => set({ reviewFocus: focus }),
        setExpectedTotalScore: (score) => set({ expectedTotalScore: score }),
        setRubricScoreMismatch: (mismatch) => set({ rubricScoreMismatch: mismatch }),
        setRubricParseError: (error) => set({ rubricParseError: error }),
        addLog: (message, level = 'INFO') => set((state) => ({
            logs: [...state.logs, {
                timestamp: new Date().toISOString(),
                level,
                message
            }]
        })),

        updateNodeStatus: (nodeId, status, message) => {
            const state = get();
            const targetIndex = state.workflowNodes.findIndex(n => n.id === nodeId);
            if (targetIndex === -1) return;
            if (
                (state.status === 'COMPLETED' || state.status === 'FAILED')
                && (status === 'running' || status === 'pending')
            ) {
                return;
            }

            const targetNode = state.workflowNodes[targetIndex];
            const isStatusChange = targetNode.status !== status;
            const now = Date.now();
            const lastUpdate = state.nodeStatusTimestamps[nodeId] || 0;
            const shouldDelay = isStatusChange && (status === 'running' || status === 'completed');
            const delay = shouldDelay ? Math.max(0, NODE_MIN_TRANSITION_MS - (now - lastUpdate)) : 0;

            const applyUpdate = () => {
                set((current) => {
                    const updatedNodes = current.workflowNodes.map((n, index) => {
                        if (index === targetIndex) {
                            const statusChanged = n.status !== status;
                            let nextMessage = n.message;

                            if (message !== undefined) {
                                nextMessage = message;
                            } else if (statusChanged && status === 'completed') {
                                nextMessage = `${n.label} completed`;
                            } else if (statusChanged && status === 'pending') {
                                nextMessage = undefined;
                            }

                            return { ...n, status: status as NodeStatus, message: nextMessage };
                        }
                        return n;
                    });
                    const nextTimers = { ...current.nodeStatusTimers };
                    delete nextTimers[nodeId];
                    return {
                        workflowNodes: updatedNodes,
                        nodeStatusTimestamps: {
                            ...current.nodeStatusTimestamps,
                            [nodeId]: Date.now(),
                        },
                        nodeStatusTimers: nextTimers,
                    };
                });
            };

            if (delay > 0) {
                const existingTimer = state.nodeStatusTimers[nodeId];
                if (existingTimer) {
                    clearTimeout(existingTimer);
                }
                const timer = setTimeout(applyUpdate, delay);
                set((current) => ({
                    nodeStatusTimers: {
                        ...current.nodeStatusTimers,
                        [nodeId]: timer,
                    },
                }));
                return;
            }

            applyUpdate();
        },

        setParallelAgents: (nodeId, agents) => set((state) => ({
            workflowNodes: state.workflowNodes.map((n) =>
                n.id === nodeId ? { ...n, children: agents } : n
            )
        })),

        updateAgentStatus: (agentId, update, parentNodeId) => set((state) => {
            const isWorker = agentId.startsWith('worker-');
            const isBatch = agentId.startsWith('batch_');
            const isReview = agentId.startsWith('review-worker-') || parentNodeId === 'logic_review';
            const isRubricReview = agentId.startsWith('rubric-review-batch-') || parentNodeId === 'rubric_review';
            const isRubricBatch = agentId.startsWith('rubric-batch-') || parentNodeId === 'rubric_parse';
            const targetNodeId = parentNodeId || (
                isWorker || isBatch ? 'grade_batch' :
                    isReview ? 'logic_review' :
                            isRubricReview ? 'rubric_review' :
                                isRubricBatch ? 'rubric_parse' :
                                    null
            );
            if (!targetNodeId) {
                return {};
            }
            const shouldAutoCreate = isWorker || isBatch || isReview || isRubricReview || isRubricBatch;
            const parsedIndex = (() => {
                const parts = agentId.split('-');
                const last = parts[parts.length - 1];
                const num = Number(last);
                return Number.isFinite(num) ? num : null;
            })();
            const inferredLabel = isWorker && parsedIndex !== null
                ? `Worker ${parsedIndex + 1}`
                : isBatch && parsedIndex !== null
                    ? `Student ${parsedIndex + 1}`
                    : isReview && parsedIndex !== null
                        ? `Review ${parsedIndex + 1}`
                        : isRubricReview && parsedIndex !== null
                                ? `Rubric Review ${parsedIndex + 1}`
                                : isRubricBatch && parsedIndex !== null
                                    ? `Rubric Page ${parsedIndex + 1}`
                                    : agentId;

            return {
                workflowNodes: state.workflowNodes.map((node) => {
                    if (!node.isParallelContainer || node.id !== targetNodeId) {
                        return node;
                    }

                    const children = node.children ? [...node.children] : [];
                    const existingIndex = children.findIndex((agent) => agent.id === agentId);
                    if (existingIndex === -1) {
                        if (!shouldAutoCreate) {
                            return node;
                        }
                        const newAgent: GradingAgent = {
                            id: agentId,
                            label: update.label || inferredLabel,
                            status: update.status || 'pending',
                            progress: update.progress,
                            logs: [],
                            output: update.output,
                            error: update.error
                        };
                        return {
                            ...node,
                            children: [...children, newAgent]
                        };
                    }

                    return {
                        ...node,
                        children: children.map((agent) =>
                            agent.id === agentId ? { ...agent, ...update } : agent
                        )
                    };
                })
            };
        }),

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

        setFinalResults: (results) => {
            const raw = Array.isArray(results) ? (results as any[]) : [];
            set({ finalResults: normalizeStudentResults(raw as any) });
        },

        reset: () => {
            Object.values(get().nodeStatusTimers).forEach((timer) => clearTimeout(timer));
            set({
                status: 'IDLE',
                currentTab: 'process',
                submissionId: null,
                selectedNodeId: null,
                selectedAgentId: null,
                isMonitorOpen: false,
                logs: [],
                finalResults: [],
                interactionEnabled: false,
                gradingMode: 'auto',
                workflowNodes: initialNodes.map(n => ({
                    ...n,
                    status: 'pending' as NodeStatus,
                    message: undefined,
                    children: n.isParallelContainer ? [] : undefined
                })),
                nodeStatusTimestamps: {},
                nodeStatusTimers: {},
                // 閲嶇疆鑷垜鎴愰暱绯荤粺鐘讹拷?
                parsedRubric: null,
                batchProgress: null,
                studentBoundaries: [],
                // 閲嶇疆璺ㄩ〉棰樼洰淇℃伅
                crossPageQuestions: [],
                // 閲嶇疆 LLM 鎬濊€冨拰鍥剧墖
                llmThoughts: [],
                uploadedImages: [],
                rubricImages: [],
                pendingReview: null,
                classReport: null,
                expectedTotalScore: null,
                rubricScoreMismatch: null,
                rubricParseError: null,
                completionBlockedReason: null,
                requiredStageSeen: createInitialRequiredStageSeen(),
                lastObservedStage: null,
                pendingTerminalEvent: false,
            });
        },

        setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedAgentId: null }),
        setSelectedAgentId: (id) => set((state) => {
            if (!id) {
                return { selectedAgentId: null };
            }
            const parentNode = state.workflowNodes.find((node) =>
                node.children?.some((agent) => agent.id === id)
            );
            return {
                selectedAgentId: id,
                selectedNodeId: parentNode?.id || state.selectedNodeId
            };
        }),
        toggleMonitor: () => set((state) => ({ isMonitorOpen: !state.isMonitorOpen })),

        // 鑷垜鎴愰暱绯荤粺鏂规硶
        setParsedRubric: (rubric) => set({ parsedRubric: rubric }),
        setBatchProgress: (progress) => set({ batchProgress: progress }),
        setStudentBoundaries: (boundaries) => set({ studentBoundaries: boundaries }),
        updateSelfEvolving: (update) => set((state) => ({
            selfEvolving: { ...state.selfEvolving, ...update }
        })),
        // 璺ㄩ〉棰樼洰鏂规硶
        setCrossPageQuestions: (questions) => set({ crossPageQuestions: questions }),

        // LLM 鎬濊€冩柟锟?
        appendLLMThought: (nodeId, nodeName, chunk, pageIndex, streamType, agentId, agentLabel) => set((state) => {
            // 闃插尽鎬у鐞嗭細纭繚 chunk 鏄瓧绗︿覆
            let contentStr = '';
            let shouldAppend = true;
            const normalizedStreamType = streamType || 'output';
            const isThinking = normalizedStreamType === 'thinking';
            const maxChars = 200000;

            if (isThinking) {
                if (typeof chunk === 'string') {
                    contentStr = chunk;
                } else if (chunk && typeof chunk === 'object') {
                    const obj = chunk as any;
                    contentStr = obj.text || obj.content || obj.thought || obj.summary || '';
                } else {
                    contentStr = String(chunk || '');
                }
                contentStr = contentStr.trim();
                shouldAppend = Boolean(contentStr);
            } else if (typeof chunk === 'string') {
                let processedChunk = chunk;
                // 绉婚櫎鍙兘瀛樺湪锟?markdown 浠ｇ爜鍧楀寘锟?
                if (processedChunk.startsWith('```json')) {
                    processedChunk = processedChunk.replace(/^```json\s*/, '').replace(/\s*```$/, '');
                } else if (processedChunk.startsWith('```')) {
                    processedChunk = processedChunk.replace(/^```\s*/, '').replace(/\s*```$/, '');
                }
                contentStr = processedChunk;
                shouldAppend = contentStr !== '';
            } else if (chunk && typeof chunk === 'object') {
                // 瀵硅薄绫诲瀷锛屽皾璇曟彁锟?text/content
                const obj = chunk as any;
                contentStr = obj.text || obj.content || obj.thought || obj.summary || JSON.stringify(obj, null, 2);
                shouldAppend = contentStr !== '';
            } else {
                contentStr = String(chunk || '');
                shouldAppend = contentStr !== '';
            }

            if (!shouldAppend || !contentStr) {
                return state; // KEEPALIVE
            }

            const normalizedNodeId = normalizeNodeId(nodeId);
            if (normalizedNodeId === 'index') {
                return state;
            }
            const normalizedAgentId = agentId || undefined;
            const baseNodeName = nodeName || normalizedNodeId;
            const normalizedNodeName = agentLabel ? `${baseNodeName} - ${agentLabel}` : baseNodeName;
            const normalizedPageIndex = pageIndex;

            const agentKey = normalizedAgentId || 'all';
            const baseThoughtId = normalizedPageIndex !== undefined
                ? `${normalizedNodeId}-${agentKey}-${normalizedStreamType}-${normalizedPageIndex}`
                : `${normalizedNodeId}-${agentKey}-${normalizedStreamType}`;

            // Keep rubric_parse / rubric_self_review / logic_review streams readable by chunking output.
            const shouldSegment = (!isThinking) && (
                normalizedNodeId === 'rubric_parse'
                || normalizedNodeId === 'rubric_self_review'
                || normalizedNodeId === 'logic_review'
            );
            const segmentMaxChars = 2500;

            if (shouldSegment) {
                const segmentPrefix = `${baseThoughtId}::seg=`;
                let activeIdx = -1;
                let maxSeg = -1;

                for (let i = 0; i < state.llmThoughts.length; i++) {
                    const t = state.llmThoughts[i];
                    if (!t.id.startsWith(segmentPrefix)) continue;
                    const rawSeg = t.id.slice(segmentPrefix.length);
                    const parsed = Number.parseInt(rawSeg, 10);
                    if (!Number.isNaN(parsed)) {
                        maxSeg = Math.max(maxSeg, parsed);
                    }
                    if (!t.isComplete) {
                        activeIdx = i;
                    }
                }

                const updated = [...state.llmThoughts];
                const nowTs = Date.now();

                const startNewSegment = () => {
                    const segId = `${segmentPrefix}${maxSeg + 1}`;
                    maxSeg = maxSeg + 1;
                    const truncated = maxChars > 0 && contentStr.length > maxChars ? contentStr.slice(-maxChars) : contentStr;
                    updated.push({
                        id: segId,
                        nodeId: normalizedNodeId,
                        nodeName: normalizedNodeName,
                        agentId: normalizedAgentId,
                        agentLabel,
                        streamType: normalizedStreamType,
                        pageIndex: normalizedPageIndex,
                        content: truncated,
                        timestamp: nowTs,
                        isComplete: false
                    });
                    return { llmThoughts: updated };
                };

                if (activeIdx < 0) {
                    return startNewSegment();
                }

                const active = updated[activeIdx];
                const previousContent = active.content || '';
                const combined = mergeStreamChunk(previousContent, contentStr, maxChars);
                const grew = combined.length > previousContent.length;

                if (!grew) {
                    return state;
                }

                if (combined.length > segmentMaxChars) {
                    updated[activeIdx] = { ...active, isComplete: true };
                    const appended = combined.startsWith(previousContent)
                        ? combined.slice(previousContent.length)
                        : contentStr;
                    const nextChunk = clipStreamTail(appended || combined, segmentMaxChars);
                    if (!nextChunk) {
                        return { llmThoughts: updated };
                    }
                    contentStr = nextChunk;
                    return startNewSegment();
                }

                updated[activeIdx] = {
                    ...active,
                    content: combined
                };

                return { llmThoughts: updated };
            }

            const existingIdx = state.llmThoughts.findIndex(t => t.id === baseThoughtId && !t.isComplete);

            if (existingIdx >= 0) {
                // Append to existing thought
                const updated = [...state.llmThoughts];
                const previousContent = updated[existingIdx].content || '';
                const combined = mergeStreamChunk(previousContent, contentStr, maxChars);
                if (combined === previousContent) {
                    return state;
                }
                updated[existingIdx] = {
                    ...updated[existingIdx],
                    content: combined
                };
                return { llmThoughts: updated };
            }

            // Create a new thought
            const truncated = maxChars > 0 && contentStr.length > maxChars ? contentStr.slice(-maxChars) : contentStr;
            return {
                llmThoughts: [...state.llmThoughts, {
                    id: baseThoughtId,
                    nodeId: normalizedNodeId,
                    nodeName: normalizedNodeName,
                    agentId: normalizedAgentId,
                    agentLabel,
                    streamType: normalizedStreamType,
                    pageIndex: normalizedPageIndex,
                    content: truncated,
                    timestamp: Date.now(),
                    isComplete: false
                }]
            };

        }),

        completeLLMThought: (nodeId, pageIndex, streamType, agentId) => set((state) => {
            const normalizedNodeId = normalizeNodeId(nodeId);
            if (normalizedNodeId === 'index') {
                return state;
            }
            const normalizedAgentId = agentId || undefined;
            const normalizedPageIndex = pageIndex;
            return {
                llmThoughts: state.llmThoughts.map(t => {
                    if (t.nodeId !== normalizedNodeId) {
                        if (normalizedAgentId && t.agentId !== normalizedAgentId) {
                            return t;
                        }
                        return t;
                    }
                    if (normalizedPageIndex !== undefined && t.pageIndex !== normalizedPageIndex) {
                        return t;
                    }
                    if (streamType && t.streamType !== streamType) {
                        return t;
                    }
                    return { ...t, isComplete: true };
                })
            };
        }),

        clearLLMThoughts: () => set({ llmThoughts: [] }),

        // 鍥剧墖鏂规硶
        setUploadedImages: (images) => set({
            uploadedImages: Array.isArray(images) ? images.map(normalizeImageSource) : []
        }),
        setRubricImages: (images) => set({
            rubricImages: Array.isArray(images) ? images.map(normalizeImageSource) : []
        }),
        setPendingReview: (review) => set({ pendingReview: review }),
        setClassReport: (report) => set({ classReport: report }),

        // 鐝骇鎵规敼涓婁笅鏂囨柟锟?
        setClassContext: (context) => set((state) => ({
            classContext: { ...state.classContext, ...context }
        })),
        clearClassContext: () => set({
            classContext: {
                classId: null,
                homeworkId: null,
                className: null,
                homeworkName: null,
                students: [],
                studentImageMapping: [],
            }
        }),

        connectWs: (batchId) => {
            // Reset workflow state when connecting to a new batch.
            set({
                workflowNodes: initialNodes.map((n) => ({
                    ...n,
                    status: 'pending' as NodeStatus,
                    message: undefined,
                    children: n.isParallelContainer ? [] : undefined
                })),
                llmThoughts: [],
                completionBlockedReason: null,
                requiredStageSeen: createInitialRequiredStageSeen(),
                lastObservedStage: null,
                pendingTerminalEvent: false,
            });

            // Register listeners once, before opening the socket.
            if (handlersRegistered) {
                wsClient.connect(buildWsUrl(`/api/batch/ws/${batchId}`));
                return;
            }
            handlersRegistered = true;

            // 澶勭悊宸ヤ綔娴佽妭鐐规洿锟?
            wsClient.on('workflow_update', (data: any) => {
                console.log('Workflow Update:', data);
                const { nodeId, status, message } = data as {
                    nodeId?: string;
                    status?: unknown;
                    message?: string;
                };

                // Fallback: some backend pause paths emit `workflow_update` with `status="paused"` (no interrupt payload).
                // If we ignore it, the UI looks like it "ended" after rubric parsing. Convert it into a review overlay.
                if (status === 'paused') {
                    const existing = get().pendingReview;
                    if (!existing) {
                        const nodes = get().workflowNodes;
                        const gradeNode = nodes.find((n) => n.id === 'grade_batch');
                        const isBeforeGrading = !gradeNode || gradeNode.status === 'pending';
                        const reviewType = isBeforeGrading ? 'rubric_review_required' : 'results_review_required';
                        const warningMessage = message || 'Workflow paused (awaiting input)';

                        get().setPendingReview({
                            reviewType,
                            batchId: get().submissionId || undefined,
                            message: warningMessage,
                            requestedAt: new Date().toISOString(),
                            payload: data && typeof data === 'object' ? data : { raw: data },
                        });
                        get().setStatus('REVIEWING');
                        const reviewNodeId = reviewType.includes('rubric') ? 'rubric_review' : 'review';
                        get().updateNodeStatus(reviewNodeId, 'running', 'Waiting for interaction');
                        get().setReviewFocus(reviewType.includes('rubric') ? 'rubric' : 'results');
                        get().addLog(warningMessage, 'WARNING');
                    }
                    return;
                }
                // 鍚庣鑺傜偣 ID 鏄犲皠鍒板墠绔紙鍏煎鏃у悕绉帮級
                const mappedNodeId = nodeId ? normalizeNodeId(nodeId) : undefined;
                const normalizedStatus = isNodeStatus(status) ? status : undefined;
                if (!mappedNodeId || !normalizedStatus) {
                    return;
                }
                if (message) {
                    updateNodeStatusWithCompletionGate(mappedNodeId, normalizedStatus, message);
                    get().addLog(message, 'INFO');
                } else {
                    updateNodeStatusWithCompletionGate(mappedNodeId, normalizedStatus);
                }

                const stageSignal = deriveStageFromNodeUpdate(mappedNodeId, normalizedStatus);
                if (stageSignal) {
                    recordStageSignal(stageSignal);
                }

                const shouldAttemptFinalize =
                    stageSignal === 'completed' || (get().pendingTerminalEvent && canFinalizeCompletion());
                if (shouldAttemptFinalize) {
                    maybeFinalizeCompletion(data);
                }
            });

            // 澶勭悊骞惰 Agent 鍒涘缓
            wsClient.on('parallel_agents_created', (data: any) => {
                console.log('Parallel Agents Created:', data);
                const { parentNodeId, agents } = data as {
                    parentNodeId?: string;
                    agents?: GradingAgent[];
                };
                if (!parentNodeId || !Array.isArray(agents)) {
                    return;
                }
                // 鍚庣鑺傜偣 ID 鏄犲皠鍒板墠锟?
                const mappedNodeId = normalizeNodeId(parentNodeId);
                get().setParallelAgents(mappedNodeId, agents);
                get().addLog(`Created ${agents.length} grading agents`, 'INFO');
            });

            // 澶勭悊鍗曚釜 Agent 鏇存柊
            wsClient.on('agent_update', (data: any) => {
                console.log('Agent Update:', data);
                const payload = data as any;
                const { agentId, status, progress, message, output, logs, error } = payload;
                const label = payload.agentLabel || payload.agent_label || payload.agentName || payload.agent_name;
                const rawParentNodeId = payload.parentNodeId || payload.nodeId;
                const parentNodeId = rawParentNodeId ? normalizeNodeId(rawParentNodeId) : rawParentNodeId;
                if (parentNodeId) {
                    const node = get().workflowNodes.find((n) => n.id === parentNodeId);
                    if (node && node.status === 'pending') {
                        get().updateNodeStatus(parentNodeId, 'running', message);
                    }
                }
                get().updateAgentStatus(agentId, { status, progress, output, error, label }, parentNodeId);
                if (logs && logs.length > 0) {
                    logs.forEach((log: string) => get().addAgentLog(agentId, log));
                }
                if (message) {
                    get().addLog(message, 'INFO');
                }
                // 濡傛灉鏈夐敊璇紝涔熻褰曞埌鏃ュ織
                if (error && error.details) {
                    error.details.forEach((detail: string) => get().addLog(`[Error] ${detail}`, 'ERROR'));
                }
            });

            // ===== 璁捐鏂囨。鏂板浜嬩欢绫诲瀷 =====

            // 澶勭悊璇勫垎鏍囧噯瑙ｆ瀽瀹屾垚浜嬩欢
            wsClient.on('rubric_parsed', (data: any) => {
                console.log('Rubric Parsed:', data);
                const normalized = normalizeParsedRubricPayload(data);
                if (normalized) {
                    const expectedTotalScore = get().expectedTotalScore;
                    if (typeof expectedTotalScore === 'number' && expectedTotalScore > 0) {
                        const parsedTotalScore = normalized.totalScore ?? 0;
                        if (parsedTotalScore > 0 && parsedTotalScore < expectedTotalScore) {
                            const message = `Parsed total (${parsedTotalScore}) is lower than expected (${expectedTotalScore}). Please re-upload the rubric.`;
                            get().setRubricScoreMismatch({
                                expectedTotalScore,
                                parsedTotalScore,
                                message,
                            });
                            get().setRubricParseError(null);
                            set({
                                status: 'IDLE',
                                currentTab: 'process',
                                submissionId: null,
                            });
                            get().addLog(message, 'ERROR');
                            return;
                        }
                    }
                    get().setParsedRubric(normalized);
                    get().addLog(
                        `Rubric parsed: ${normalized.totalQuestions} questions, total ${normalized.totalScore} points`,
                        'INFO'
                    );
                }
            });
            wsClient.on('rubric_score_mismatch', (data: any) => {
                console.log('Rubric Score Mismatch:', data);
                const expectedTotalScore = Number(data.expectedTotalScore ?? data.expected_total_score);
                const parsedTotalScore = Number(data.parsedTotalScore ?? data.parsed_total_score);
                if (Number.isFinite(expectedTotalScore) && Number.isFinite(parsedTotalScore)) {
                    const message = data.message
                        || `Parsed total (${parsedTotalScore}) is lower than expected (${expectedTotalScore}). Please re-upload the rubric.`;
                    get().setRubricScoreMismatch({
                        expectedTotalScore,
                        parsedTotalScore,
                        message,
                    });
                    get().setRubricParseError(null);
                    set({
                        status: 'IDLE',
                        currentTab: 'process',
                        submissionId: null,
                    });
                    get().addLog(message, 'ERROR');
                }
            });
            wsClient.on('rubric_parse_failed', (data: any) => {
                console.log('Rubric Parse Failed:', data);
                const message = data.message || 'Rubric parse failed. Please re-upload a clear rubric.';
                get().setRubricParseError({
                    message,
                    details: data.error,
                });
                get().setRubricScoreMismatch(null);
                set({
                    status: 'IDLE',
                    currentTab: 'process',
                    submissionId: null,
                });
                get().addLog(message, 'ERROR');
            });

            // Handle batch_not_found and stop noisy reconnect loops.
            wsClient.on('batch_not_found', (data: any) => {
                console.warn('Batch Not Found:', data);
                const message = data.message || 'This batch has completed or does not exist.';
                const currentBatchId = get().submissionId;
                const receivedBatchId = data.batchId || data.batch_id;

                // Ignore stale events from other batches.
                if (receivedBatchId && currentBatchId && receivedBatchId !== currentBatchId) {
                    console.log(`Ignoring batch_not_found for different batch: ${receivedBatchId} vs current ${currentBatchId}`);
                    return;
                }

                get().addLog(message, 'WARNING');
                // Prevent infinite reconnect loops when batch is gone.
                wsClient.disconnect();
            });

            // 馃敟 澶勭悊鍥剧墖棰勫鐞嗗畬鎴愪簨锟?- 鐢ㄤ簬缁撴灉椤垫樉绀虹瓟棰樺浘锟?
            wsClient.on('images_ready', (data: any) => {
                console.log('Images Ready:', data);
                const { images, totalCount } = data as any;
                if (images && Array.isArray(images)) {
                    get().setUploadedImages(images);
                    get().addLog(`Loaded ${images.length}/${totalCount} answer images`, 'INFO');
                }
            });

            wsClient.on('rubric_images_ready', (data: any) => {
                console.log('Rubric Images Ready:', data);
                const { images } = data as any;
                if (images && Array.isArray(images)) {
                    get().setRubricImages(images);
                    get().addLog(`Loaded ${images.length} rubric images`, 'INFO');
                }
            });

            // 澶勭悊鎵规寮€濮嬩簨浠讹紙瀵瑰簲璁捐鏂囨。 EventType.BATCH_START锟?
            wsClient.on('batch_start', (data: any) => {
                console.log('Batch Start:', data);
                const { batchIndex, totalBatches } = data as any;
                if (typeof batchIndex === 'number' && typeof totalBatches === 'number') {
                    get().setBatchProgress({
                        batchIndex,
                        totalBatches,
                        successCount: 0,
                        failureCount: 0,
                    });
                    get().addLog(`Starting run ${batchIndex + 1}/${totalBatches}`, 'INFO');
                }
            });

            // 澶勭悊鎵规杩涘害浜嬩欢锛堝悗锟?state_update -> batch_progress锟?
            wsClient.on('batch_progress', (data: any) => {
                console.log('Batch Progress:', data);
                const batchIndex = data.batchIndex ?? data.batch_index;
                const totalBatches = data.totalBatches ?? data.total_batches;
                const successCount = data.successCount ?? data.success_count ?? 0;
                const failureCount = data.failureCount ?? data.failure_count ?? 0;
                if (typeof batchIndex === 'number' && typeof totalBatches === 'number') {
                    get().setBatchProgress({
                        batchIndex,
                        totalBatches,
                        successCount,
                        failureCount,
                    });
                }
            });

            // 澶勭悊鍗曢〉瀹屾垚浜嬩欢锛堝搴旇璁℃枃锟?EventType.PAGE_COMPLETE锟?
            wsClient.on('page_complete', (data: any) => {
                console.log('Page Complete:', data);
                const { pageIndex, success, batchIndex, revisionCount } = data as any;
                const currentProgress = get().batchProgress;

                // 鏇存柊鎵规杩涘害
                if (currentProgress) {
                    get().setBatchProgress({
                        ...currentProgress,
                        successCount: success ? currentProgress.successCount + 1 : currentProgress.successCount,
                        failureCount: success ? currentProgress.failureCount : currentProgress.failureCount + 1,
                    });
                }

                // 鏇存柊瀵瑰簲 Agent 鐨勮嚜鎴戜慨姝ｆ锟?
                if (revisionCount && revisionCount > 0) {
                    const agentId = `batch_${batchIndex}`;
                    const nodes = get().workflowNodes;
                    const gradingNode = nodes.find(n => n.id === 'grade_batch');

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
                            get().addAgentLog(agentId, `Page ${pageIndex} triggered ${revisionCount} self-revisions`);
                        }
                    }
                }
            });

            // 澶勭悊 LLM 娴佸紡杈撳嚭娑堟伅 (P4) - 缁熶竴娴佸紡杈撳嚭灞曠ず
            wsClient.on('llm_stream_chunk', (data: any) => {
                const rawNodeId = data.nodeId || data.node || 'unknown';
                const normalizedNodeId = normalizeNodeId(rawNodeId);
                const nodeName = data.nodeName;
                const { pageIndex, chunk } = data as any;
                const agentId = data.agentId || data.agent_id;
                const agentLabel = data.agentLabel || data.agent_label;
                const rawStreamType = data.streamType || data.stream_type;
                const streamType = rawStreamType === 'thinking' ? 'thinking' : 'output';

                // 闃插尽鎬у鐞嗭細纭繚 chunk 鏄瓧绗︿覆
                let contentStr = '';
                if (typeof chunk === 'string') {
                    contentStr = chunk;
                } else if (chunk && typeof chunk === 'object') {
                    contentStr = (chunk as any).text || (chunk as any).content || JSON.stringify(chunk);
                } else {
                    contentStr = String(chunk || '');
                }

                // Use normalized labels for streamed LLM thoughts.
                const displayNodeName = nodeName || (
                    normalizedNodeId === 'rubric_parse' ? 'Rubric Parse' :
                        normalizedNodeId === 'rubric_self_review' ? 'Auto Review' :
                            normalizedNodeId === 'rubric_review' ? 'Rubric Review' :
                                    normalizedNodeId === 'logic_review' ? 'Logic Review' :
                                        normalizedNodeId === 'grade_batch' ? `Student Page ${pageIndex !== undefined ? pageIndex + 1 : ''}` :
                                            normalizedNodeId || 'Node'
                );
                get().appendLLMThought(normalizedNodeId, displayNodeName, contentStr, pageIndex, streamType, agentId, agentLabel);
                const nodeForStream = get().workflowNodes.find((n) => n.id === normalizedNodeId);
                if (nodeForStream && nodeForStream.status === 'pending') {
                    get().updateNodeStatus(normalizedNodeId, 'running');
                }

                // 鍚屾椂鏇存柊 Agent 鐘舵€侊紙鍏煎鏃ч€昏緫锟?
                if (streamType !== 'thinking' && normalizedNodeId === 'grade_batch') {
                    const nodes = get().workflowNodes;
                    const gradingNode = nodes.find(n => n.id === 'grade_batch');
                    if (gradingNode && gradingNode.children) {
                        const agentById = agentId
                            ? gradingNode.children.find(a => a.id === agentId)
                            : undefined;
                        const agent = agentById || gradingNode.children.find(a => a.status === 'running');
                        if (!agent) {
                            return;
                        }
                        const currentText = agent.output?.streamingText || '';
                        const maxChars = 8000;
                        const combined = mergeStreamChunk(currentText, contentStr, maxChars);
                        if (combined === currentText) {
                            return;
                        }
                        get().updateAgentStatus(agent.id, {
                            output: {
                                ...agent.output,
                                streamingText: combined
                            }
                        });
                    }
                }
            });

            // 澶勭悊 LLM 鎬濊€冨畬鎴愪簨锟?
            wsClient.on('llm_thought_complete', (data: any) => {
                const { nodeId, pageIndex, agentId } = data as any;
                const rawStreamType = data.streamType || data.stream_type;
                const streamType = rawStreamType === 'thinking' ? 'thinking' : 'output';
                get().completeLLMThought(nodeId || "unknown", pageIndex, streamType, agentId);
            });

            // 澶勭悊鎵规瀹屾垚浜嬩欢锛堝搴旇璁℃枃锟?EventType.BATCH_COMPLETE锟?
            wsClient.on('batch_complete', (data: any) => {
                console.log('Batch Complete:', data);
                const { batchIndex, successCount, failureCount, processingTimeMs, totalScore, totalBatches } = data as any;
                const resolvedBatchIndex = typeof batchIndex === 'number'
                    ? batchIndex
                    : get().batchProgress?.batchIndex;
                const resolvedTotalBatches = typeof totalBatches === 'number'
                    ? totalBatches
                    : get().batchProgress?.totalBatches;
                if (typeof resolvedBatchIndex === 'number' && typeof resolvedTotalBatches === 'number') {
                    get().setBatchProgress({
                        batchIndex: resolvedBatchIndex,
                        totalBatches: resolvedTotalBatches,
                        successCount: successCount ?? 0,
                        failureCount: failureCount ?? 0,
                        processingTimeMs,
                    });
                }
                if (typeof batchIndex === 'number') {
                    get().addLog(`Run ${batchIndex + 1} completed: success ${successCount}, failed ${failureCount}, total ${totalScore || 0}`, 'INFO');
                } else {
                    get().addLog(`Run completed: success ${successCount ?? 0}, failed ${failureCount ?? 0}, total ${totalScore || 0}`, 'INFO');
                }
            });

            // 澶勭悊瀛︾敓璇嗗埆浜嬩欢锛堝搴旇璁℃枃锟?EventType.STUDENT_IDENTIFIED锟?
            wsClient.on('students_identified', (data: any) => {
                console.log('Students Identified:', data);
                const { students, studentCount } = data as any;
                if (students && Array.isArray(students)) {
                    get().setStudentBoundaries(students.map((s: any) => ({
                        studentKey: s.studentKey,
                        startPage: s.startPage,
                        endPage: s.endPage,
                        confidence: s.confidence,
                        needsConfirmation: s.needsConfirmation,
                    })));
                    const nodes = get().workflowNodes;
                    const gradingNode = nodes.find(n => n.id === 'grade_batch');
                    if (gradingNode && (!gradingNode.children || gradingNode.children.length === 0)) {
                        const placeholders = students.map((s: any, idx: number) => ({
                            id: `batch_${idx}`,
                            label: s.studentKey || `Student ${idx + 1}`,
                            status: 'pending' as NodeStatus,
                            progress: 0,
                            logs: [],
                        }));
                        get().setParallelAgents('grade_batch', placeholders);
                    }
                    // 缁熻寰呯‘璁よ竟锟?
                    const needsConfirm = students.filter((s: any) => s.needsConfirmation).length;
                    if (needsConfirm > 0) {
                        get().addLog(`Identified ${studentCount} students, ${needsConfirm} boundaries need confirmation`, 'WARNING');
                    } else {
                        get().addLog(`Identified ${studentCount} students`, 'INFO');
                    }
                }
            });

            // 澶勭悊瀹℃牳璇锋眰浜嬩欢
            wsClient.on('review_required', (data: any) => {
                console.log('Review Required:', data);
                // 瑙勮寖鍖栨暟鎹粨鏋勪互鍖归厤 PendingReview 鎺ュ彛
                const reviewData = {
                    type: data.type || data.reviewType,
                    batchId: data.batchId || data.batch_id,
                    message: data.message,
                    requestedAt: data.requestedAt || data.requested_at,
                    parsedRubric: normalizeParsedRubricPayload(data.payload?.parsed_rubric || data.parsedRubric),
                    // 濡傛灉鏄粨鏋滃鏍革紝鍙兘闇€锟?studentResults
                    studentResults: data.payload?.student_results || data.studentResults,
                };
                const reviewType = (reviewData.type || '').toString();
                const isRubric = reviewType.includes('rubric_review');
                const isResults = reviewType.includes('results_review');
                const isGradingRetry = reviewType.includes('grading_retry');
                if (!get().interactionEnabled && (isRubric || isResults)) {
                    const resolvedBatchId = reviewData.batchId || get().submissionId;
                    if (resolvedBatchId) {
                        const approvePromise = isRubric
                            ? gradingApi.submitRubricReview({ batch_id: resolvedBatchId, action: 'approve' })
                            : gradingApi.submitResultsReview({ batch_id: resolvedBatchId, action: 'approve' });
                        void approvePromise
                            .then(() => {
                                get().addLog(
                                    `Manual review disabled; auto-approved ${isRubric ? 'rubric' : 'results'} review.`,
                                    'INFO'
                                );
                            })
                            .catch((error) => {
                                console.warn('Auto-approve review failed:', error);
                                get().addLog('Manual review auto-approval failed; backend may still be waiting.', 'WARNING');
                            });
                    }
                    const reviewNodeId = isRubric ? 'rubric_review' : 'review';
                    get().updateNodeStatus(reviewNodeId, 'pending', 'Skipped (manual review disabled)');
                    return;
                }
                const rawPayload = (data.payload && typeof data.payload === 'object') ? data.payload : {};
                const normalizedPayload = {
                    ...rawPayload,
                    parsed_rubric: reviewData.parsedRubric ?? rawPayload.parsed_rubric,
                    student_results: reviewData.studentResults ?? rawPayload.student_results,
                };
                get().setPendingReview({
                    reviewType: reviewData.type,
                    batchId: reviewData.batchId,
                    message: reviewData.message,
                    requestedAt: reviewData.requestedAt,
                    payload: normalizedPayload
                });
                // 鍚屾椂鏇存柊鐘舵€佹彁锟?
                get().setStatus('REVIEWING');
                const reviewNodeId = isRubric ? 'rubric_review' : isResults ? 'review' : 'grade_batch';
                get().updateNodeStatus(
                    reviewNodeId,
                    'running',
                    isGradingRetry ? 'Waiting for retry' : 'Waiting for interaction'
                );
                get().setReviewFocus(isRubric ? 'rubric' : isResults ? 'results' : null);
                get().addLog(`Review required: ${reviewType}`, 'WARNING');
            });

            // 澶勭悊璺ㄩ〉棰樼洰妫€娴嬩簨锟?
            wsClient.on('cross_page_detected', (data: any) => {
                console.log('Cross Page Questions Detected:', data);
                const { questions, mergedCount, crossPageCount } = data as any;
                if (questions && Array.isArray(questions)) {
                    get().setCrossPageQuestions(questions.map((q: any) => ({
                        questionId: q.question_id || q.questionId,
                        pageIndices: q.page_indices || q.pageIndices || [],
                        confidence: q.confidence || 0,
                        mergeReason: q.merge_reason || q.mergeReason || '',
                    })));
                    get().addLog(`Cross-page merge complete: detected ${crossPageCount || questions.length} cross-page questions, merged to ${mergedCount ?? 'unknown'} questions`, 'INFO');
                }
            });

            // 澶勭悊宸ヤ綔娴佸畬锟?

            wsClient.on('workflow_completed', async (data: any) => {
                console.log('Workflow Completed:', data);
                recordStageSignal('workflow_completed');

                const message = data?.message || 'Workflow completed';
                get().addLog(`Terminal event received: ${message}`, 'INFO');

                const initialResults = extractResultsPayload(data);
                if (initialResults && initialResults.length > 0) {
                    get().setFinalResults(initialResults);
                }

                const classReport = data?.classReport || data?.class_report;
                if (classReport) {
                    const normalizedReport = normalizeClassReport(classReport);
                    if (normalizedReport) {
                        get().setClassReport(normalizedReport);
                    }
                }

                const completionDerivation = deriveStageSignalsFromResultsContext({
                    status: data?.status || 'completed',
                    current_stage: data?.current_stage || data?.currentStage || null,
                    student_results: initialResults || data?.student_results || data?.studentResults,
                });
                completionDerivation.signals.forEach((signal) => {
                    recordStageSignal(signal);
                    applyStageState(signal);
                });

                if (maybeFinalizeCompletion(data, initialResults)) {
                    return;
                }

                get().addLog('Completion gate not satisfied; continuing to monitor post-review stages.', 'WARNING');

                const batchId = data?.batchId || data?.batch_id || get().submissionId;
                if (!batchId) {
                    get().addLog('Missing batch_id; cannot continue post-review completion checks.', 'WARNING');
                    return;
                }

                const gatedResults = await waitForPostReviewResults(batchId, initialResults, {
                    onStageSignal: (signal) => {
                        recordStageSignal(signal);
                        applyStageState(signal);
                    },
                    isCompletionGateSatisfied: canFinalizeCompletion,
                });

                if (gatedResults && maybeFinalizeCompletion(data, gatedResults)) {
                    return;
                }

                blockCompletion();
                get().addLog('Post-review stages are still incomplete; workflow remains in monitoring mode.', 'WARNING');
            });

            wsClient.on('page_graded', (data: any) => {
                console.log('Page Graded:', data);
                const { pageIndex, score, maxScore, questionNumbers } = data as any;
                get().addLog(
                    `Page ${pageIndex} graded: ${score}/${maxScore} points, questions: ${questionNumbers?.join(', ') || 'unknown'}`,
                    'INFO'
                );
            });

            // 澶勭悊鎵规敼杩涘害浜嬩欢
            wsClient.on('grading_progress', (data: any) => {
                console.log('Grading Progress:', data);
                if (get().status === 'COMPLETED' || get().status === 'FAILED') {
                    return;
                }
                const { completedPages, totalPages, percentage } = data as any;
                // 鏇存柊 grading 鑺傜偣鐨勮繘锟?
                const nodes =
                    get().workflowNodes;
                const gradingNode = nodes.find(n => n.id === 'grade_batch');
                if (gradingNode) {
                    get().updateNodeStatus('grade_batch', 'running', `Grading progress: ${completedPages}/${totalPages} (${percentage}%)`);
                }
                const currentStage = data.currentStage || data.current_stage;
                if (currentStage) {
                    const normalizedStage = normalizeWorkflowStage(currentStage);
                    recordStageSignal(normalizedStage);
                    applyStageState(normalizedStage);

                    if (normalizedStage === 'logic_review_skipped') {
                        blockCompletion(LOGIC_REVIEW_SKIP_BLOCK_REASON);
                    }

                    const shouldAttemptFinalize =
                        normalizedStage === 'completed' || (get().pendingTerminalEvent && canFinalizeCompletion());
                    if (shouldAttemptFinalize) {
                        maybeFinalizeCompletion(data);
                    }
                }
            });

            // 澶勭悊鎵规瀹屾垚浜嬩欢
            wsClient.on('batch_completed', (data: any) => {
                console.log('Batch Completed:', data);
                const { batchSize, successCount, totalScore } = data as any;
                get().addLog(`Run completed: ${successCount}/${batchSize} pages succeeded, total ${totalScore}`, 'INFO');
            });

            // 澶勭悊瀹℃牳瀹屾垚浜嬩欢
            wsClient.on('review_completed', (data: any) => {
                console.log('Review Completed:', data);
                const { summary } = data as any;
                if (summary) {
                    get().addLog(`Review completed: ${summary.total_students} students, ${summary.low_confidence_count} low-confidence results`, 'INFO');
                }
                // Only move out of REVIEWING; never regress a completed run back to RUNNING.
                if (get().status === 'REVIEWING') {
                    get().setStatus('RUNNING');
                }
                get().setPendingReview(null);
                get().setReviewFocus(null);
            });

            // 澶勭悊宸ヤ綔娴侀敊璇紙瀵瑰簲璁捐鏂囨。 EventType.ERROR锟?
            wsClient.on('workflow_error', (data: any) => {
                console.log('Workflow Error:', data);
                if (get().rubricScoreMismatch || get().rubricParseError) {
                    return;
                }
                set({ status: 'FAILED' });
                get().addLog(`Error: ${data.message || data.error || 'Unknown workflow error'}`, 'ERROR');
            });
            wsClient.connect(buildWsUrl(`/api/batch/ws/${batchId}`));
        }
    };
});
