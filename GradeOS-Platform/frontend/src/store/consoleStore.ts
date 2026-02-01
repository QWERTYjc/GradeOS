import { create } from 'zustand';
import { wsClient, buildWsUrl } from '@/services/ws';
import { GradingAnnotationResult } from '@/types/annotation';
import { gradingApi } from '@/services/api';

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
    pointId?: string;           // 评分点编�?(e.g., "1.1", "1.2")
    description: string;
    score: number;
    maxScore: number;
    isCorrect: boolean;
    explanation: string;
    isRequired?: boolean;
    keywords?: string[];
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
    typoNotes?: string[];
    scoringPoints?: ScoringPoint[];
    /** 得分点明细列表（新格式） */
    scoringPointResults?: Array<{
        pointId?: string;       // 评分点编号
        scoringPoint?: ScoringPoint;  // 旧格式兼容
        description?: string;   // 评分点描述
        awarded: number;        // 实际得分
        maxPoints?: number;     // 满分
        evidence: string;       // 评分依据/证据
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
        /** 错误区域坐标 */
        errorRegion?: {
            x_min: number;
            y_min: number;
            x_max: number;
            y_max: number;
        };
    }>;
    /** 出现在哪些页?- 新增 */
    pageIndices?: number[];
    /** 是否跨页题目 - 新增 */
    isCrossPage?: boolean;
    /** 合并来源（如果是合并结果? 新增 */
    mergeSource?: string[];
    /** 页面索引 (snake_case) */
    page_index?: number;
    /** 页面索引 (camelCase) */
    pageIndex?: number;
    /** 批注坐标列表 */
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
    /** 步骤信息（包含坐标） */
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
    /** 答案区域坐标 */
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
    /** 起始页 */
    startPage?: number;
    /** 结束页 */
    endPage?: number;
    /** 置信度 */
    confidence?: number;
    /** 是否需要人工确认 */
    needsConfirmation?: boolean;
    /** 自白报告 */
    confession?: {  // confession report
        overallStatus?: string;
        issues?: Array<{ questionId?: string; message?: string }>;
        warnings?: Array<{ questionId?: string; message?: string }>;
        highRiskQuestions?: Array<{ questionId?: string; description?: string }>;
        potentialErrors?: Array<{ questionId?: string; description?: string }>;
        overallConfidence?: number;
        generatedAt?: string;
        source?: string;
    };
    /** 第一次批改记录（逻辑复核前的原始结果） */
    draftQuestionDetails?: QuestionResult[];
    /** 第一次批改总分 */
    draftTotalScore?: number;
    /** 第一次批改满分 */
    draftMaxScore?: number;
    /** 逻辑复核 */
    logicReview?: any;
    /** 逻辑复核时间 */
    logicReviewedAt?: string;
    /** 页面范围（显示用） */
    pageRange?: string;
    /** 页面列表 */
    pages?: string;
    /** 批注结果（按页） */
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

// 解析的评分标�?- 另类解法
export interface RubricAlternativeSolution {
    description: string;
    scoringCriteria: string;
    note?: string;
}

// 解析的评分标�?- 单题详情
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
    // 解析自白字段
    parseConfidence?: number;
    parseUncertainties?: string[];
    parseQualityIssues?: string[];
}

// 解析的评分标准信息（完整版）
export interface ParsedRubric {
    totalQuestions: number;
    totalScore: number;
    questions?: RubricQuestion[];
    generalNotes?: string;
    rubricFormat?: string;
    // 解析自白相关字段
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
    // 判例信息通常与特�?Agent/Page 关联，这里存储最近检索到的判例用于展�?
    recentExemplars: ExemplarInfo[];
}

// === 班级批改上下�?===

export interface ClassStudent {
    id: string;
    name: string;
    username?: string;
}

export interface StudentImageMapping {
    studentId: string;
    studentName: string;
    startIndex: number; // 该学生的起始图片索引
    endIndex: number;   // 该学生的结束图片索引 (inclusive)
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

    // 新增：自我成长系统状�?
    parsedRubric: ParsedRubric | null;
    batchProgress: BatchProgress | null;
    studentBoundaries: StudentBoundary[];
    selfEvolving: SelfEvolvingState;
    // 新增：跨页题目信�?
    crossPageQuestions: CrossPageQuestion[];
    // 新增：LLM 思考过�?
    llmThoughts: LLMThought[];
    // 新增：上传的图片 (用于结果页展�?
    uploadedImages: string[];  // base64 �?URL
    rubricImages: string[];
    pendingReview: PendingReview | null;
    classReport: ClassReport | null;
    // 新增：班级批改上下文
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

    // 新增：自我成长系统方�?
    setParsedRubric: (rubric: ParsedRubric) => void;
    setBatchProgress: (progress: BatchProgress) => void;
    setStudentBoundaries: (boundaries: StudentBoundary[]) => void;
    updateSelfEvolving: (update: Partial<SelfEvolvingState>) => void;
    // 新增：跨页题目方�?
    setCrossPageQuestions: (questions: CrossPageQuestion[]) => void;
    // 新增：LLM 思考方�?
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
    // 新增：图片方�?
    setUploadedImages: (images: string[]) => void;
    setRubricImages: (images: string[]) => void;
    setPendingReview: (review: PendingReview | null) => void;
    setClassReport: (report: ClassReport | null) => void;
    // 新增：班级批改上下文方法
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
    if (value === 'index_node') {
        return 'index';
    }
    if (value === 'grading') {
        return 'grade_batch';
    }
    return value;
};

/**
 * 工作流节点配�? * 
 * 基于 LangGraph 架构的前端展示流程（隐藏内部 merge 节点）：
 * 1. rubric_parse - 解析评分标准
 * 2. rubric_review - 评分标准人工交互（可选）
 * 3. grade_batch - 按学生批次并行批�? * 4. logic_review - 批改逻辑复核
 * 5. review - 批改结果人工交互（可选）
 * 6. export - 导出结果
 * 
 * 后端 LangGraph Graph 流程（含内部节点）：
 * index -> rubric_parse -> rubric_review -> grade_batch -> cross_page_merge -> index_merge -> logic_review -> review -> export -> END
 */
const initialNodes: WorkflowNode[] = [
    { id: 'rubric_parse', label: 'Rubric Parse', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'rubric_review', label: 'Rubric Review', status: 'pending' },
    { id: 'grade_batch', label: 'Student Grading', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'confession', label: 'Confession', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'logic_review', label: 'Logic Review', status: 'pending', isParallelContainer: true, children: [] },
    { id: 'review', label: 'Results Review', status: 'pending' },
    { id: 'export', label: 'Export', status: 'pending' },
];

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

    // 规范化自白报�?
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

const hasPostConfessionResults = (results: StudentResult[] | null): boolean => {
    if (!results || results.length === 0) return false;
    return results.every((item) =>
        Boolean(item.confession) && Boolean(item.logicReview || (item as any).logic_review || item.logicReviewedAt || (item as any).logic_reviewed_at)
    );
};

const waitForPostConfessionResults = async (batchId: string, initialResults: StudentResult[] | null) => {
    if (hasPostConfessionResults(initialResults)) {
        return initialResults;
    }
    const pollIntervalMs = 4000;
    const maxAttempts = 30;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
        let fetchedResults: StudentResult[] | null = null;
        try {
            const response = await gradingApi.getBatchResults(batchId);
            fetchedResults = extractResultsPayload(response);
        } catch (error) {
            console.warn('Polling post-confession results failed:', error);
        }
        if (!fetchedResults) {
            try {
                const reviewContext = await gradingApi.getResultsReviewContext(batchId);
                fetchedResults = extractResultsPayload(reviewContext) || (reviewContext as any)?.student_results || null;
            } catch (error) {
                console.warn('Polling results-review fallback failed:', error);
            }
        }
        if (hasPostConfessionResults(fetchedResults)) {
            return fetchedResults;
        }
    }
    return null;
};



export const useConsoleStore = create<ConsoleState>((set, get) => {
    // Store 内部�?WebSocket 处理器注册标�?
    let handlersRegistered = false;

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

        // 自我成长系统状态初始�?
        parsedRubric: null,
        batchProgress: null,
        studentBoundaries: [],
        selfEvolving: {
            calibration: null,
            activePatches: [],
            recentExemplars: []
        },
        // 跨页题目信息初始�?
        crossPageQuestions: [],
        // LLM 思考过程初始�?
        llmThoughts: [],
        // 上传的图片初始�?
        uploadedImages: [],
        rubricImages: [],
        pendingReview: null,
        classReport: null,
        // 班级批改上下文初始�?
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
                            return { ...n, status: status as NodeStatus, message: message || n.message };
                        }
                        if (index < targetIndex && (status === 'running' || status === 'completed')) {
                            if (n.status === 'pending' || n.status === 'running') {
                                return { ...n, status: 'completed' as NodeStatus };
                            }
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
            const isConfession = agentId.startsWith('report-worker-') || parentNodeId === 'confession';
            const isRubricReview = agentId.startsWith('rubric-review-batch-') || parentNodeId === 'rubric_review';
            const isRubricBatch = agentId.startsWith('rubric-batch-') || parentNodeId === 'rubric_parse';
            const targetNodeId = parentNodeId || (
                isWorker || isBatch ? 'grade_batch' :
                    isReview ? 'logic_review' :
                        isConfession ? 'confession' :
                            isRubricReview ? 'rubric_review' :
                                isRubricBatch ? 'rubric_parse' :
                                    null
            );
            if (!targetNodeId) {
                return {};
            }
            const shouldAutoCreate = isWorker || isBatch || isReview || isConfession || isRubricReview || isRubricBatch;
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
                        : isConfession && parsedIndex !== null
                            ? `Confession ${parsedIndex + 1}`
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

        setFinalResults: (results) => set({ finalResults: results }),

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
                // 重置自我成长系统状�?
                parsedRubric: null,
                batchProgress: null,
                studentBoundaries: [],
                // 重置跨页题目信息
                crossPageQuestions: [],
                // 重置 LLM 思考和图片
                llmThoughts: [],
                uploadedImages: [],
                rubricImages: [],
                pendingReview: null,
                classReport: null,
                expectedTotalScore: null,
                rubricScoreMismatch: null,
                rubricParseError: null,
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

        // 自我成长系统方法
        setParsedRubric: (rubric) => set({ parsedRubric: rubric }),
        setBatchProgress: (progress) => set({ batchProgress: progress }),
        setStudentBoundaries: (boundaries) => set({ studentBoundaries: boundaries }),
        updateSelfEvolving: (update) => set((state) => ({
            selfEvolving: { ...state.selfEvolving, ...update }
        })),
        // 跨页题目方法
        setCrossPageQuestions: (questions) => set({ crossPageQuestions: questions }),

        // LLM 思考方�?
        appendLLMThought: (nodeId, nodeName, chunk, pageIndex, streamType, agentId, agentLabel) => set((state) => {
            // 防御性处理：确保 chunk 是字符串
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
                // 移除可能存在�?markdown 代码块包�?
                if (processedChunk.startsWith('```json')) {
                    processedChunk = processedChunk.replace(/^```json\s*/, '').replace(/\s*```$/, '');
                } else if (processedChunk.startsWith('```')) {
                    processedChunk = processedChunk.replace(/^```\s*/, '').replace(/\s*```$/, '');
                }
                contentStr = processedChunk;
                shouldAppend = contentStr !== '';
            } else if (chunk && typeof chunk === 'object') {
                // 对象类型，尝试提�?text/content
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
            const thoughtId = normalizedPageIndex !== undefined
                ? `${normalizedNodeId}-${agentKey}-${normalizedStreamType}-${normalizedPageIndex}`
                : `${normalizedNodeId}-${agentKey}-${normalizedStreamType}`;
            const existingIdx = state.llmThoughts.findIndex(t => t.id === thoughtId && !t.isComplete);

            if (existingIdx >= 0) {
                // 追加到现有思�?
                const updated = [...state.llmThoughts];
                const combined = updated[existingIdx].content + contentStr;
                updated[existingIdx] = {
                    ...updated[existingIdx],
                    content: (maxChars > 0 && combined.length > maxChars) ? combined.slice(-maxChars) : combined
                };
                return { llmThoughts: updated };
            } else {
                // 创建新思�?
                const truncated = maxChars > 0 && contentStr.length > maxChars ? contentStr.slice(-maxChars) : contentStr;
                return {
                    llmThoughts: [...state.llmThoughts, {
                        id: thoughtId,
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
            }
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

        // 图片方法
        setUploadedImages: (images) => set({
            uploadedImages: Array.isArray(images) ? images.map(normalizeImageSource) : []
        }),
        setRubricImages: (images) => set({
            rubricImages: Array.isArray(images) ? images.map(normalizeImageSource) : []
        }),
        setPendingReview: (review) => set({ pendingReview: review }),
        setClassReport: (report) => set({ classReport: report }),

        // 班级批改上下文方�?
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
            wsClient.connect(buildWsUrl(`/api/batch/ws/${batchId}`));
            // 使用 store 内部状态而不是全局变量
            if (handlersRegistered) {
                return;
            }
            handlersRegistered = true;

            // 处理工作流节点更�?
            wsClient.on('workflow_update', (data: any) => {
                console.log('Workflow Update:', data);
                const { nodeId, status, message } = data as {
                    nodeId?: string;
                    status?: unknown;
                    message?: string;
                };
                // 后端节点 ID 映射到前端（兼容旧名称）
                const mappedNodeId = nodeId === 'grading' ? 'grade_batch' : nodeId;
                const normalizedStatus = isNodeStatus(status) ? status : undefined;
                if (!mappedNodeId || !normalizedStatus) {
                    return;
                }
                if (mappedNodeId === 'intake' || mappedNodeId === 'preprocess' || mappedNodeId === 'index') {
                    return;
                }
                if (message) {
                    get().updateNodeStatus(mappedNodeId, normalizedStatus, message);
                    get().addLog(message, 'INFO');
                } else {
                    get().updateNodeStatus(mappedNodeId, normalizedStatus);
                }
            });

            // 处理并行 Agent 创建
            wsClient.on('parallel_agents_created', (data: any) => {
                console.log('Parallel Agents Created:', data);
                const { parentNodeId, agents } = data as {
                    parentNodeId?: string;
                    agents?: GradingAgent[];
                };
                if (!parentNodeId || !Array.isArray(agents)) {
                    return;
                }
                // 后端节点 ID 映射到前�?
                const mappedNodeId = parentNodeId === 'grading' ? 'grade_batch' : parentNodeId;
                get().setParallelAgents(mappedNodeId, agents);
                get().addLog(`Created ${agents.length} grading agents`, 'INFO');
            });

            // 处理单个 Agent 更新
            wsClient.on('agent_update', (data: any) => {
                console.log('Agent Update:', data);
                const payload = data as any;
                const { agentId, status, progress, message, output, logs, error } = payload;
                const label = payload.agentLabel || payload.agent_label || payload.agentName || payload.agent_name;
                const rawParentNodeId = payload.parentNodeId || payload.nodeId;
                const parentNodeId = rawParentNodeId === 'grading' ? 'grade_batch' : rawParentNodeId;
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
                // 如果有错误，也记录到日志
                if (error && error.details) {
                    error.details.forEach((detail: string) => get().addLog(`[Error] ${detail}`, 'ERROR'));
                }
            });

            // ===== 设计文档新增事件类型 =====

            // 处理评分标准解析完成事件
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

            // 🔥 FIX: 处理批次不存在事件 - 停止重连并清理状态
            wsClient.on('batch_not_found', (data: any) => {
                console.warn('Batch Not Found:', data);
                const message = data.message || 'This batch has completed or does not exist.';
                const currentBatchId = get().submissionId;
                const receivedBatchId = data.batchId || data.batch_id;
                
                // 只有当消息对应当前批次时才处理
                if (receivedBatchId && currentBatchId && receivedBatchId !== currentBatchId) {
                    console.log(`Ignoring batch_not_found for different batch: ${receivedBatchId} vs current ${currentBatchId}`);
                    return;
                }
                
                get().addLog(message, 'WARNING');
                // 断开 WebSocket 连接，防止无限重连
                wsClient.disconnect();
            });

            // 🔥 处理图片预处理完成事�?- 用于结果页显示答题图�?
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

            // 处理批次开始事件（对应设计文档 EventType.BATCH_START�?
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

            // 处理批次进度事件（后�?state_update -> batch_progress�?
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

            // 处理单页完成事件（对应设计文�?EventType.PAGE_COMPLETE�?
            wsClient.on('page_complete', (data: any) => {
                console.log('Page Complete:', data);
                const { pageIndex, success, batchIndex, revisionCount } = data as any;
                const currentProgress = get().batchProgress;

                // 更新批次进度
                if (currentProgress) {
                    get().setBatchProgress({
                        ...currentProgress,
                        successCount: success ? currentProgress.successCount + 1 : currentProgress.successCount,
                        failureCount: success ? currentProgress.failureCount : currentProgress.failureCount + 1,
                    });
                }

                // 更新对应 Agent 的自我修正次�?
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

            // 处理 LLM 流式输出消息 (P4) - 统一流式输出展示
            wsClient.on('llm_stream_chunk', (data: any) => {
                const rawNodeId = data.nodeId || data.node || 'unknown';
                const normalizedNodeId = normalizeNodeId(rawNodeId);
                const nodeName = data.nodeName;
                const { pageIndex, chunk } = data as any;
                const agentId = data.agentId || data.agent_id;
                const agentLabel = data.agentLabel || data.agent_label;
                const rawStreamType = data.streamType || data.stream_type;
                const streamType = rawStreamType === 'thinking' ? 'thinking' : 'output';

                // 防御性处理：确保 chunk 是字符串
                let contentStr = '';
                if (typeof chunk === 'string') {
                    contentStr = chunk;
                } else if (chunk && typeof chunk === 'object') {
                    contentStr = (chunk as any).text || (chunk as any).content || JSON.stringify(chunk);
                } else {
                    contentStr = String(chunk || '');
                }

                // 使用统一�?LLM 思考追加方�?
                const displayNodeName = nodeName || (
                    normalizedNodeId === 'rubric_parse' ? 'Rubric Parse' :
                        normalizedNodeId === 'rubric_review' ? 'Rubric Review' :
                            normalizedNodeId === 'confession' ? 'Confession' :
                                normalizedNodeId === 'logic_review' ? 'Logic Review' :
                                    normalizedNodeId === 'grade_batch' ? `Student Page ${pageIndex !== undefined ? pageIndex + 1 : ''}` :
                                        normalizedNodeId || 'Node'
                );
                get().appendLLMThought(normalizedNodeId, displayNodeName, contentStr, pageIndex, streamType, agentId, agentLabel);
                const nodeForStream = get().workflowNodes.find((n) => n.id === normalizedNodeId);
                if (nodeForStream && nodeForStream.status === 'pending') {
                    get().updateNodeStatus(normalizedNodeId, 'running');
                }

                // 同时更新 Agent 状态（兼容旧逻辑�?
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
                        const combined = currentText + contentStr;
                        const maxChars = 8000;
                        get().updateAgentStatus(agent.id, {
                            output: {
                                ...agent.output,
                                streamingText: combined.length > maxChars ? combined.slice(-maxChars) : combined
                            }
                        });
                    }
                }
            });

            // 处理 LLM 思考完成事�?
            wsClient.on('llm_thought_complete', (data: any) => {
                const { nodeId, pageIndex, agentId } = data as any;
                const rawStreamType = data.streamType || data.stream_type;
                const streamType = rawStreamType === 'thinking' ? 'thinking' : 'output';
                get().completeLLMThought(nodeId || "unknown", pageIndex, streamType, agentId);
            });

            // 处理批次完成事件（对应设计文�?EventType.BATCH_COMPLETE�?
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

            // 处理学生识别事件（对应设计文�?EventType.STUDENT_IDENTIFIED�?
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
                    // 统计待确认边�?
                    const needsConfirm = students.filter((s: any) => s.needsConfirmation).length;
                    if (needsConfirm > 0) {
                        get().addLog(`Identified ${studentCount} students, ${needsConfirm} boundaries need confirmation`, 'WARNING');
                    } else {
                        get().addLog(`Identified ${studentCount} students`, 'INFO');
                    }
                }
            });

            // 处理审核请求事件
            wsClient.on('review_required', (data: any) => {
                console.log('Review Required:', data);
                // 规范化数据结构以匹配 PendingReview 接口
                const reviewData = {
                    type: data.type || data.reviewType,
                    batchId: data.batchId || data.batch_id,
                    message: data.message,
                    requestedAt: data.requestedAt || data.requested_at,
                    parsedRubric: normalizeParsedRubricPayload(data.payload?.parsed_rubric || data.parsedRubric),
                    // 如果是结果审核，可能需�?studentResults
                    studentResults: data.payload?.student_results || data.studentResults,
                };
                get().setPendingReview({
                    reviewType: reviewData.type,
                    batchId: reviewData.batchId,
                    message: reviewData.message,
                    requestedAt: reviewData.requestedAt,
                    payload: {
                        parsed_rubric: reviewData.parsedRubric,
                        student_results: reviewData.studentResults
                    }
                });
                // 同时更新状态提�?
                get().setStatus('REVIEWING');
                const reviewNodeId = (reviewData.type || '').includes('rubric') ? 'rubric_review' : 'review';
                get().updateNodeStatus(reviewNodeId, 'running', 'Waiting for interaction');
                get().setReviewFocus((reviewData.type || '').includes('rubric') ? 'rubric' : 'results');
                get().addLog(`Review required: ${reviewData.type}`, 'WARNING');
            });

            // 处理跨页题目检测事�?
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

            // 处理工作流完�?

            wsClient.on('workflow_completed', async (data: any) => {
                console.log('Workflow Completed:', data);
                const message = data.message || 'Workflow completed';
                get().addLog(message, 'SUCCESS');

                const initialResults = extractResultsPayload(data);
                if (initialResults) {
                    get().setFinalResults(initialResults);
                    get().addLog(`Saved results for ${initialResults.length} students`, 'SUCCESS');
                }

                const classReport = data.classReport || data.class_report;
                if (classReport) {
                    const normalizedReport = normalizeClassReport(classReport);
                    if (normalizedReport) {
                        get().setClassReport(normalizedReport);
                    }
                }

                get().setStatus('COMPLETED');
                get().setPendingReview(null);
                get().setReviewFocus(null);

                const orderedNodes = [
                    'rubric_parse',
                    'rubric_review',
                    'grade_batch',
                    'confession',
                    'logic_review',
                    'review',
                    'export'
                ];
                orderedNodes.forEach((nodeId) => get().updateNodeStatus(nodeId, 'completed'));

                const batchId =
                    data.batchId ||
                    data.batch_id ||
                    get().submissionId;
                if (!batchId) {
                    get().addLog('Missing batch_id; cannot verify confession/logic review completion.', 'WARNING');
                    return;
                }

                if (!hasPostConfessionResults(initialResults)) {
                    get().addLog('等待自白与逻辑复核完成后再进入结果页...', 'INFO');
                    const gatedResults = await waitForPostConfessionResults(batchId, initialResults);
                    if (gatedResults) {
                        get().setFinalResults(gatedResults);
                        get().addLog('自白与逻辑复核已完成，进入结果页。', 'SUCCESS');
                        set({ currentTab: 'results' });
                    } else {
                        get().addLog('自白/逻辑复核仍未完成，已停止自动跳转结果页。', 'WARNING');
                    }
                    return;
                }

                setTimeout(() => {
                    set({ currentTab: 'results' });
                }, 800);
            });

            wsClient.on('page_graded', (data: any) => {
                console.log('Page Graded:', data);
                const { pageIndex, score, maxScore, questionNumbers } = data as any;
                get().addLog(
                    `Page ${pageIndex} graded: ${score}/${maxScore} points, questions: ${questionNumbers?.join(', ') || 'unknown'}`,
                    'INFO'
                );
            });

            // 处理批改进度事件
            wsClient.on('grading_progress', (data: any) => {
                console.log('Grading Progress:', data);
                const { completedPages, totalPages, percentage } = data as any;
                // 更新 grading 节点的进�?
                const nodes =
                    get().workflowNodes;
                const gradingNode = nodes.find(n => n.id === 'grade_batch');
                if (gradingNode) {
                    get().updateNodeStatus('grade_batch', 'running', `Grading progress: ${completedPages}/${totalPages} (${percentage}%)`);
                }
                const currentStage = data.currentStage || data.current_stage;
                if (currentStage) {
                    const stageToNode: Record<string, string> = {
                        rubric_parse_completed: 'rubric_parse',
                        rubric_review_completed: 'rubric_review',
                        rubric_review_skipped: 'rubric_review',
                        grade_batch_completed: 'grade_batch',
                        cross_page_merge_completed: 'grade_batch',
                        index_merge_completed: 'grade_batch',
                        confession_completed: 'confession',
                        logic_review_completed: 'logic_review',
                        logic_review_skipped: 'logic_review',
                        review_completed: 'review',
                        completed: 'export'
                    };
                    const orderedNodes = [
                        'rubric_parse',
                        'rubric_review',
                        'grade_batch',
                        'confession',
                        'logic_review',
                        'review',
                        'export'
                    ];
                    const stageNode = stageToNode[currentStage];
                    if (stageNode) {
                        const stageIndex = orderedNodes.indexOf(stageNode);
                        if (stageIndex >= 0) {
                            orderedNodes.forEach((nodeId, idx) => {
                                if (idx < stageIndex) {
                                    get().updateNodeStatus(nodeId, 'completed');
                                }
                            });
                            const pendingReview = get().pendingReview;
                            const holdRubricReview = stageNode === 'rubric_review'
                                && pendingReview
                                && (pendingReview.reviewType || '').includes('rubric');
                            if (holdRubricReview) {
                                get().updateNodeStatus(stageNode, 'running', 'Waiting for interaction');
                                return;
                            }

                            get().updateNodeStatus(stageNode, 'completed');

                            const nextNode = orderedNodes[stageIndex + 1];
                            if (nextNode) {
                                get().updateNodeStatus(nextNode, 'running');
                            }
                        } else {
                            get().updateNodeStatus(stageNode, 'completed');
                        }
                    }
                }
            });

            // 处理批次完成事件
            wsClient.on('batch_completed', (data: any) => {
                console.log('Batch Completed:', data);
                const { batchSize, successCount, totalScore } = data as any;
                get().addLog(`Run completed: ${successCount}/${batchSize} pages succeeded, total ${totalScore}`, 'INFO');
            });

            // 处理审核完成事件
            wsClient.on('review_completed', (data: any) => {
                console.log('Review Completed:', data);
                const { summary } = data as any;
                if (summary) {
                    get().addLog(`Review completed: ${summary.total_students} students, ${summary.low_confidence_count} low-confidence results`, 'INFO');
                }
                get().setStatus('RUNNING');
                get().setPendingReview(null);
                get().setReviewFocus(null);
            });

            // 处理工作流错误（对应设计文档 EventType.ERROR�?
            wsClient.on('workflow_error', (data: any) => {
                console.log('Workflow Error:', data);
                if (get().rubricScoreMismatch || get().rubricParseError) {
                    return;
                }
                set({ status: 'FAILED' });
                get().addLog(`Error: ${data.message}`, 'ERROR');
            });
        }
    };
});
