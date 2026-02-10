/**
 * GradeOS 统一 API 服务
 * 连接前端与后端的所有 API 接口
 */

const getApiBase = () => {
  // 1. 优先尝试环境变量
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  // 2. 浏览器环境下提供容错
  if (typeof window !== 'undefined') {
    const origin = window.location.origin;
    const hostname = window.location.hostname;
    
    // 如果是 localhost 开发环境
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8001/api';
    }
    
    // 生产环境检测：Railway 部署的域名
    // 前端: gradeos.up.railway.app
    // 后端: gradeos-production.up.railway.app
    if (hostname.includes('railway.app')) {
      // 硬编码生产后端 URL，因为前后端是分开部署的
      return 'https://gradeos-production.up.railway.app/api';
    }
    
    // 其他生产环境（如自定义域名），尝试同源 API
    console.warn('API_URL not configured, falling back to relative path /api');
    return `${origin}/api`;
  }

  // 3. 服务端渲染时的默认值
  return 'http://localhost:8001/api';
};

// 导出获取 API 基础 URL 的函数
export const getApiBaseUrl = getApiBase;

const API_BASE = getApiBase();

// ============ 通用请求方法 ============

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============ 认证 API ============

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  role: 'teacher' | 'student';
}

export interface UserResponse {
  user_id: string;
  username: string;
  name: string;
  user_type: 'student' | 'teacher' | 'admin';
  class_ids: string[];
}

export const authApi = {
  login: (data: LoginRequest) =>
    request<UserResponse>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  register: (data: RegisterRequest) =>
    request<UserResponse>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  getUserInfo: (userId: string) =>
    request<UserResponse>(`/user/info?user_id=${userId}`),
};

// ============ 班级管理 API ============

export interface ClassResponse {
  class_id: string;
  class_name: string;
  teacher_id: string;
  invite_code: string;
  student_count: number;
}

export interface StudentInfo {
  id: string;
  name: string;
  username: string;
}

export const classApi = {
  getMyClasses: (studentId: string) =>
    request<ClassResponse[]>(`/class/my?student_id=${studentId}`),

  joinClass: (code: string, studentId: string) =>
    request<{ success: boolean; class: { id: string; name: string } }>('/class/join', {
      method: 'POST',
      body: JSON.stringify({ code, student_id: studentId }),
    }),

  getTeacherClasses: (teacherId: string) =>
    request<ClassResponse[]>(`/teacher/classes?teacher_id=${teacherId}`),

  createClass: (name: string, teacherId: string) =>
    request<ClassResponse>('/teacher/classes', {
      method: 'POST',
      body: JSON.stringify({ name, teacher_id: teacherId }),
    }),

  getClassStudents: (classId: string) =>
    request<StudentInfo[]>(`/class/students?class_id=${classId}`),
};

// ============ 作业管理 API ============

export interface HomeworkResponse {
  homework_id: string;
  class_id: string;
  class_name?: string;
  title: string;
  description: string;
  deadline: string;
  allow_early_grading?: boolean;
  rubric_images?: string[];
  created_at: string;
}

export interface SubmissionResponse {
  submission_id: string;
  homework_id: string;
  student_id: string;
  student_name: string;
  submitted_at: string;
  status: string;
  score?: number;
  feedback?: string;
}

export const homeworkApi = {
  getList: (params?: { class_id?: string; student_id?: string }) => {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return request<HomeworkResponse[]>(`/homework/list${query ? `?${query}` : ''}`);
  },

  getDetail: (homeworkId: string) =>
    request<HomeworkResponse>(`/homework/detail/${homeworkId}`),

  create: (data: { class_id: string; title: string; description: string; deadline: string; allow_early_grading?: boolean; rubric_images?: string[] }) =>
    request<HomeworkResponse>('/homework/create', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submit: (data: { homework_id: string; student_id: string; student_name: string; content: string }) =>
    request<SubmissionResponse>('/homework/submit', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // 扫描提交作业（图片）
  submitScan: (data: { homework_id: string; student_id: string; student_name: string; images: string[] }) =>
    request<SubmissionResponse>('/homework/submit-scan', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getSubmissions: (homeworkId: string) =>
    request<SubmissionResponse[]>(`/homework/submissions?homework_id=${homeworkId}`),
};


// ============ 错题分析 API (IntelliLearn) ============

export interface ErrorAnalysisRequest {
  subject: string;
  question: string;
  student_answer: string;
  student_id?: string;
}

export interface KnowledgeGap {
  knowledge_point: string;
  mastery_level: number;
  confidence: number;
}

export interface ErrorAnalysisResponse {
  analysis_id: string;
  error_type: string;
  error_severity: string;
  root_cause: string;
  knowledge_gaps: KnowledgeGap[];
  detailed_analysis: {
    step_by_step_correction: string[];
    common_mistakes: string;
    correct_solution: string;
  };
  recommendations: {
    immediate_actions: string[];
    practice_exercises: string[];
    learning_path: { short_term: string[]; long_term: string[] };
  };
}

export interface DiagnosisReportResponse {
  student_id: string;
  report_period: string;
  overall_assessment: {
    mastery_score: number;
    improvement_rate: number;
    consistency_score: number;
  };
  progress_trend: Array<{ date: string; score: number; average: number }>;
  knowledge_map: Array<{
    knowledge_area: string;
    mastery_level: number;
    weak_points: string[];
    strengths: string[];
  }>;
  error_patterns: {
    most_common_error_types: Array<{ type: string; count: number; percentage: number }>;
  };
  personalized_insights: string[];
}

export const analysisApi = {
  submitError: (data: ErrorAnalysisRequest) =>
    request<ErrorAnalysisResponse>('/v1/analysis/submit-error', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getDiagnosisReport: (studentId: string) =>
    request<DiagnosisReportResponse>(`/v1/diagnosis/report/${studentId}`),

  getClassWrongProblems: (classId?: string) => {
    const query = classId ? `?class_id=${classId}` : '';
    return request<{
      problems: Array<{
        id: string;
        question: string;
        errorRate: string;
        tags: string[];
      }>;
    }>(`/v1/class/wrong-problems${query}`);
  },
};

// ============ 学生助手 API ============

export interface AssistantMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface AssistantChatRequest {
  student_id: string;
  message: string;
  class_id?: string;
  history?: AssistantMessage[];
  session_mode?: string;
  concept_topic?: string;
  // 新增：多模态支持
  images?: string[];  // base64 编码的图片列表
  wrong_question_context?: {
    questionId: string;
    score: number;
    maxScore: number;
    feedback?: string;
    studentAnswer?: string;
    scoringPointResults?: Array<{
      point_id?: string;
      description?: string;
      awarded: number;
      max_points?: number;
      evidence: string;
    }>;
    subject?: string;
    topic?: string;
  };
}

export interface ConceptNode {
  id: string;
  name: string;
  description: string;
  understood: boolean;
  children?: ConceptNode[];
}

export interface MasteryData {
  score: number;
  level: string;
  analysis: string;
  evidence: string[];
  suggestions: string[];
}

export interface AssistantChatResponse {
  content: string;
  model?: string;
  usage?: Record<string, number>;
  mastery?: MasteryData;
  next_question?: string;
  question_options?: string[];
  focus_mode?: boolean;
  concept_breakdown?: ConceptNode[];
  response_type?: string;
}

export interface MasterySnapshot {
  score: number;
  level: string;
  analysis: string;
  evidence: string[];
  suggestions: string[];
  created_at: string;
}

export interface AssistantProgressResponse {
  student_id: string;
  class_id?: string;
  concept_breakdown: ConceptNode[];
  mastery_history: MasterySnapshot[];
}

export const assistantApi = {
  chat: (data: AssistantChatRequest) =>
    request<AssistantChatResponse>('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getProgress: (studentId: string, classId?: string) => {
    const params = new URLSearchParams({ student_id: studentId });
    if (classId) {
      params.set('class_id', classId);
    }
    return request<AssistantProgressResponse>(`/assistant/progress?${params.toString()}`);
  },
};

// ============ 统计 API ============

export interface ClassStatistics {
  class_id: string;
  total_students: number;
  submitted_count: number;
  graded_count: number;
  average_score: number;
  max_score: number;
  min_score: number;
  pass_rate: number;
  score_distribution: Record<string, number>;
}

export const statisticsApi = {
  getClassStatistics: (classId: string, homeworkId?: string) => {
    const query = homeworkId ? `?homework_id=${homeworkId}` : '';
    return request<ClassStatistics>(`/teacher/statistics/class/${classId}${query}`);
  },

  mergeStatistics: (classId: string, externalData?: string) =>
    request<{
      students: Array<{ id: string; name: string; scores: Record<string, number> }>;
      internalAssignments: string[];
      externalAssignments: string[];
    }>(`/teacher/statistics/merge?class_id=${classId}`, {
      method: 'POST',
      body: externalData ? JSON.stringify({ external_data: externalData }) : undefined,
    }),
};

// ============ AI 批改 API (Console) ============

export interface Submission {
  id: string;
  status: string;
  created_at: string;
  total_pages?: number;
}

export interface GradingResult {
  submission_id: string;
  student_name: string;
  total_score: number;
  max_score: number;
  questions: Array<{
    question_id: string;
    score: number;
    max_score: number;
    feedback: string;
    confidence?: number;
    confidence_reason?: string;
    self_critique?: string;
    self_critique_confidence?: number;
    rubric_refs?: string[];
    typo_notes?: string[];
    page_indices?: number[];
    is_cross_page?: boolean;
    merge_source?: string[];
    scoring_point_results?: Array<{
      scoring_point: { description: string; score: number; is_required: boolean };
      point_id?: string;
      description?: string;
      awarded: number;
      max_points?: number;
      evidence: string;
      rubric_reference?: string;
      rubric_reference_source?: string;
      decision?: string;
      reason?: string;
    }>;
  }>;
  confidence?: number;
  needs_confirmation?: boolean;
  start_page?: number;
  end_page?: number;
}

/** 跨页题目信息 */
export interface CrossPageQuestionInfo {
  question_id: string;
  page_indices: number[];
  confidence: number;
  merge_reason: string;
}

/** 批量批改结果响应 */
export interface BatchGradingResponse {
  batch_id: string;
  student_results: GradingResult[];
  total_pages: number;
  processed_pages: number;
  cross_page_questions: CrossPageQuestionInfo[];
  errors: Array<{ type: string; message: string; page_index?: number }>;
}

/** 学生边界确认请求 */
export interface ConfirmBoundaryRequest {
  batch_id: string;
  student_key: string;
  confirmed_pages?: number[];
  confirmed_start_page?: number;
  confirmed_end_page?: number;
}

export interface RubricReviewRequest {
  batch_id: string;
  action: string;
  parsed_rubric?: Record<string, unknown>;
  selected_question_ids?: string[];
  notes?: string;
}

export interface ResultsReviewRequest {
  batch_id: string;
  action: string;
  results?: Array<Record<string, unknown>>;
  regrade_items?: Array<Record<string, unknown>>;
  notes?: string;
}

export interface GradingRetryRequest {
  batch_id: string;
  action: 'retry' | 'abort';
  notes?: string;
}

export interface GradingImportTarget {
  class_id: string;
  student_ids: string[];
  assignment_id?: string;
  student_mapping?: Array<{ student_key: string; student_id: string }>;
}

export interface GradingImportRequest {
  batch_id: string;
  targets: GradingImportTarget[];
}

export interface GradingRecordStatistics {
  average_score?: number;
  max_score?: number;
  min_score?: number;
  pass_rate?: number;
  score_distribution?: Record<string, number>;
}

export interface GradingImportRecord {
  import_id: string;
  batch_id: string;
  class_id: string;
  class_name?: string;
  assignment_id?: string;
  assignment_title?: string;
  student_count: number;
  status: string;
  created_at: string;
  revoked_at?: string;
  statistics?: GradingRecordStatistics;
}

export interface GradingImportItem {
  item_id: string;
  import_id: string;
  batch_id: string;
  class_id: string;
  student_id: string;
  student_name: string;
  status: string;
  created_at: string;
  revoked_at?: string;
  result?: Record<string, unknown>;
}

export interface GradingHistorySummary {
  total_records: number;
  total_students_graded: number;
  overall_average?: number;
  trend?: 'improving' | 'stable' | 'regressing';
}

export interface GradingHistoryResponse {
  records: GradingImportRecord[];
  summary?: GradingHistorySummary;
}

export interface GradingHistoryDetailResponse {
  record: GradingImportRecord;
  items: GradingImportItem[];
}

export interface RubricReviewContext {
  batch_id: string;
  status?: string;
  current_stage?: string;
  parsed_rubric?: Record<string, unknown>;
  rubric_images: string[];
}

export interface ResultsReviewContext {
  batch_id: string;
  status?: string;
  current_stage?: string;
  parsed_rubric?: Record<string, unknown>;
  student_results: Array<Record<string, unknown>>;
  answer_images: string[];
}

export interface ActiveRunItem {
  batch_id: string;
  status: string;
  class_id?: string;
  homework_id?: string;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  completed_at?: string;
  total_pages?: number;
  progress?: number;
  current_stage?: string;
}

export interface ActiveRunsResponse {
  teacher_id: string;
  runs: ActiveRunItem[];
}

export const gradingApi = {
  createSubmission: async (
    examFiles: File[],
    rubricFiles: File[],
    studentBoundaries: number[] = [],
    expectedStudents?: number,
    classContext?: {
      classId?: string;
      homeworkId?: string;
      studentMapping?: Array<{ studentId?: string; studentName?: string; studentKey?: string; startIndex: number; endIndex: number }>;
    },
    enableReview: boolean = true,
    gradingMode?: string,
    teacherId?: string,
    expectedTotalScore?: number
  ): Promise<Submission> => {
    const formData = new FormData();

    // 添加考试文件
    examFiles.forEach(file => formData.append('files', file));

    // 添加评分标准文件
    rubricFiles.forEach(file => formData.append('rubrics', file));

    // 添加学生边界 (JSON stringified)
    if (studentBoundaries.length > 0) {
      formData.append('student_boundaries', JSON.stringify(studentBoundaries));
    }

    // 添加预期学生数量
    if (expectedStudents && expectedStudents > 0) {
      formData.append('expected_students', expectedStudents.toString());
    }

    // 添加班级批改上下文（可选）
    if (classContext?.classId) {
      formData.append('class_id', classContext.classId);
    }
    if (classContext?.homeworkId) {
      formData.append('homework_id', classContext.homeworkId);
    }
    if (classContext?.studentMapping && classContext.studentMapping.length > 0) {
      formData.append('student_mapping_json', JSON.stringify(classContext.studentMapping));
    }
    formData.append('enable_review', enableReview ? 'true' : 'false');
    if (gradingMode) {
      formData.append('grading_mode', gradingMode);
    }
    if (teacherId) {
      formData.append('teacher_id', teacherId);
    }
    if (typeof expectedTotalScore === 'number' && expectedTotalScore >= 0) {
      formData.append('expected_total_score', expectedTotalScore.toString());
    }

    // 使用正确的批改 API 端点
    const response = await fetch(`${API_BASE}/batch/submit`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || 'Upload failed');
    }

    const result = await response.json();

    // 转换响应格式
    return {
      id: result.batch_id,
      status: result.status,
      created_at: new Date().toISOString(),
      total_pages: result.total_pages,
    };
  },

  getSubmission: (submissionId: string) =>
    request<Submission>(`/batch/status/${submissionId}`),

  getResults: (submissionId: string) =>
    request<GradingResult[]>(`/batch/results/${submissionId}`),

  getActiveRuns: (teacherId?: string) => {
    const query = teacherId ? `?teacher_id=${encodeURIComponent(teacherId)}` : '';
    return request<ActiveRunsResponse>(`/batch/active${query}`);
  },

  /** 获取批量批改完整结果（包含跨页题目信息） */
  getBatchResults: (batchId: string) =>
    request<BatchGradingResponse>(`/batch/full-results/${batchId}`),

  /** 获取跨页题目信息 */
  getCrossPageQuestions: (batchId: string) =>
    request<CrossPageQuestionInfo[]>(`/batch/cross-page-questions/${batchId}`),

  /** 确认学生边界 */
  confirmStudentBoundary: (data: ConfirmBoundaryRequest) => {
    const { confirmed_pages, confirmed_start_page, confirmed_end_page, ...rest } = data;
    let resolvedPages = confirmed_pages;
    if (!resolvedPages && confirmed_start_page != null && confirmed_end_page != null) {
      const start = Math.max(0, confirmed_start_page);
      const end = Math.max(start, confirmed_end_page);
      resolvedPages = Array.from({ length: end - start + 1 }, (_, idx) => start + idx);
    }
    return request<{ success: boolean; message: string }>('/batch/confirm-boundary', {
      method: 'POST',
      body: JSON.stringify({ ...rest, confirmed_pages: resolvedPages || [] }),
    });
  },

  /** 获取 rubric review 上下文 */
  getRubricReviewContext: (batchId: string) =>
    request<RubricReviewContext>(`/batch/rubric/${batchId}`),

  getResultsReviewContext: (batchId: string) =>
    request<ResultsReviewContext>(`/batch/results-review/${batchId}`),

  submitRubricReview: (data: RubricReviewRequest) =>
    request<{ success: boolean; message: string }>('/batch/review/rubric', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitResultsReview: (data: ResultsReviewRequest) =>
    request<{ success: boolean; message: string }>('/batch/review/results', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitGradingRetry: (data: GradingRetryRequest) =>
    request<{ success: boolean; message: string }>('/batch/review/grading', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  importToClasses: (data: GradingImportRequest) =>
    request<GradingHistoryResponse>('/grading/import', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getGradingHistory: (params?: { class_id?: string; assignment_id?: string; teacher_id?: string; include_stats?: boolean }) => {
    // 🔧 过滤掉 undefined 值，避免传递 "undefined" 字符串
    const queryParams: Record<string, string> = {};
    if (params?.class_id) queryParams.class_id = params.class_id;
    if (params?.assignment_id) queryParams.assignment_id = params.assignment_id;
    if (params?.teacher_id) queryParams.teacher_id = params.teacher_id;
    if (params?.include_stats) queryParams.include_stats = 'true';
    const query = new URLSearchParams(queryParams).toString();
    return request<GradingHistoryResponse>(`/grading/history${query ? `?${query}` : ''}`);
  },

  getGradingHistoryDetail: (importId: string) =>
    request<GradingHistoryDetailResponse>(`/grading/history/${importId}`),

  revokeGradingImport: (importId: string, reason?: string) =>
    request<GradingImportRecord>(`/grading/import/${importId}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
};

// ============ 导出所有 API ============

export const api = {
  auth: authApi,
  class: classApi,
  homework: homeworkApi,
  analysis: analysisApi,
  assistant: assistantApi,
  statistics: statisticsApi,
  // Console API (兼容旧接口)
  createSubmission: (
    examFiles: File[],
    rubricFiles: File[],
    studentBoundaries?: number[],
    expectedStudents?: number,
    classContext?: {
      classId?: string;
      homeworkId?: string;
      studentMapping?: Array<{ studentId?: string; studentName?: string; studentKey?: string; startIndex: number; endIndex: number }>;
    },
    enableReview: boolean = true,
    gradingMode?: string,
    teacherId?: string,
    expectedTotalScore?: number
  ) => gradingApi.createSubmission(
    examFiles,
    rubricFiles,
    studentBoundaries || [],
    expectedStudents,
    classContext,
    enableReview,
    gradingMode,
    teacherId,
    expectedTotalScore
  ),
  getSubmission: gradingApi.getSubmission,
  getResults: gradingApi.getResults,
  getRubricReviewContext: gradingApi.getRubricReviewContext,
  getResultsReviewContext: gradingApi.getResultsReviewContext,
  submitRubricReview: gradingApi.submitRubricReview,
  submitResultsReview: gradingApi.submitResultsReview,
  getActiveRuns: gradingApi.getActiveRuns,

  // Class grading console integration
  getSubmissionsForGrading: async (classId: string, homeworkId: string) => {
    return request<{
      class_id: string;
      class_name: string;
      homework_id: string;
      homework_name: string;
      students: Array<{
        student_id: string;
        student_name: string;
        images: string[];
        page_count: number;
      }>;
      total_pages: number;
    }>(`/class/${classId}/homework/${homeworkId}/submissions-for-grading`);
  },
};

// ============ 错题本手动录入 API ============

export interface ManualWrongQuestionCreate {
  student_id: string;
  class_id?: string;
  question_id?: string;
  subject?: string;
  topic?: string;
  question_content?: string;
  student_answer?: string;
  correct_answer?: string;
  score: number;
  max_score: number;
  feedback?: string;
  images: string[];  // base64 图片列表
  tags: string[];
}

export interface ManualWrongQuestionResponse {
  id: string;
  student_id: string;
  class_id?: string;
  question_id: string;
  subject?: string;
  topic?: string;
  question_content?: string;
  student_answer?: string;
  correct_answer?: string;
  score: number;
  max_score: number;
  feedback?: string;
  images: string[];
  tags: string[];
  source: 'manual' | 'grading';
  created_at: string;
}

export interface ManualWrongQuestionListResponse {
  questions: ManualWrongQuestionResponse[];
  total: number;
}

export const wrongbookApi = {
  // 添加手动录入的错题
  addQuestion: (data: ManualWrongQuestionCreate) =>
    request<ManualWrongQuestionResponse>('/wrongbook/add', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // 获取手动录入的错题列表
  listQuestions: (params: { student_id: string; class_id?: string; subject?: string; limit?: number }) => {
    const queryParams: Record<string, string> = { student_id: params.student_id };
    if (params.class_id) queryParams.class_id = params.class_id;
    if (params.subject) queryParams.subject = params.subject;
    if (params.limit !== undefined) queryParams.limit = params.limit.toString();
    const query = new URLSearchParams(queryParams).toString();
    return request<ManualWrongQuestionListResponse>(`/wrongbook/list?${query}`);
  },

  // 删除错题
  deleteQuestion: (entryId: string, studentId: string) =>
    request<{ success: boolean; message: string }>(`/wrongbook/${entryId}?student_id=${studentId}`, {
      method: 'DELETE',
    }),

  // 更新错题
  updateQuestion: (entryId: string, data: ManualWrongQuestionCreate) =>
    request<ManualWrongQuestionResponse>(`/wrongbook/${entryId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};

// ============ OpenBoard 论坛 API ============

import { Forum, ForumPost, ForumReply, ForumSearchResult, ForumUserStatus, ForumModLog } from '@/types';

export interface CreateForumRequest {
  name: string;
  description: string;
  creator_id: string;
}

export interface ApproveForumRequest {
  approved: boolean;
  reason?: string;
  moderator_id: string;
}

export interface CreatePostRequest {
  forum_id: string;
  title: string;
  content: string;
  author_id: string;
  images?: string[];  // 图片列表（base64）
}

export interface CreateReplyRequest {
  content: string;
  author_id: string;
  images?: string[];  // 图片列表（base64）
}

export interface BanUserRequest {
  user_id: string;
  moderator_id: string;
  banned: boolean;
  reason?: string;
}

export const openboardApi = {
  // 论坛管理
  getForums: (includePending: boolean = false) =>
    request<Forum[]>(`/openboard/forums${includePending ? '?include_pending=true' : ''}`),

  createForum: (data: CreateForumRequest) =>
    request<Forum>('/openboard/forums', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  approveForum: (forumId: string, data: ApproveForumRequest) =>
    request<Forum>(`/openboard/forums/${forumId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // 帖子管理
  getForumPosts: (forumId: string, page: number = 1, limit: number = 20) =>
    request<ForumPost[]>(`/openboard/forums/${forumId}/posts?page=${page}&limit=${limit}`),

  createPost: (data: CreatePostRequest) =>
    request<ForumPost>('/openboard/posts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getPostDetail: (postId: string) =>
    request<{ post: ForumPost; replies: ForumReply[] }>(`/openboard/posts/${postId}`),

  // 回复
  createReply: (postId: string, data: CreateReplyRequest) =>
    request<ForumReply>(`/openboard/posts/${postId}/replies`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // 搜索
  searchPosts: (query: string, forumId?: string, limit: number = 20) => {
    const params = new URLSearchParams({ q: query, limit: limit.toString() });
    if (forumId) params.set('forum_id', forumId);
    return request<ForumSearchResult[]>(`/openboard/search?${params.toString()}`);
  },

  // 管理员功能
  getPendingForums: () =>
    request<Forum[]>('/openboard/admin/pending-forums'),

  deletePost: (postId: string, moderatorId: string, reason?: string) =>
    request<{ success: boolean; message: string }>(`/openboard/admin/posts/${postId}`, {
      method: 'DELETE',
      body: JSON.stringify({ moderator_id: moderatorId, reason }),
    }),

  banUser: (data: BanUserRequest) =>
    request<{ success: boolean; message: string }>('/openboard/admin/ban', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getUserStatus: (userId: string) =>
    request<ForumUserStatus>(`/openboard/admin/users/${userId}/status`),

  getModLogs: (limit: number = 50) =>
    request<ForumModLog[]>(`/openboard/admin/mod-logs?limit=${limit}`),
};

export default api;
