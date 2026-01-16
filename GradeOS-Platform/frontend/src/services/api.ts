/**
 * GradeOS 统一 API 服务
 * 连接前端与后端的所有 API 接口
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';

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

  create: (data: { class_id: string; title: string; description: string; deadline: string; allow_early_grading?: boolean }) =>
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
  parsed_rubric?: Record<string, any>;
  selected_question_ids?: string[];
  notes?: string;
}

export interface ResultsReviewRequest {
  batch_id: string;
  action: string;
  results?: Array<Record<string, any>>;
  regrade_items?: Array<Record<string, any>>;
  notes?: string;
}

export interface GradingImportTarget {
  class_id: string;
  student_ids: string[];
  assignment_id?: string;
}

export interface GradingImportRequest {
  batch_id: string;
  targets: GradingImportTarget[];
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
  result?: Record<string, any>;
}

export interface GradingHistoryResponse {
  records: GradingImportRecord[];
}

export interface GradingHistoryDetailResponse {
  record: GradingImportRecord;
  items: GradingImportItem[];
}

export interface RubricReviewContext {
  batch_id: string;
  status?: string;
  current_stage?: string;
  parsed_rubric?: Record<string, any>;
  rubric_images: string[];
}

export interface ResultsReviewContext {
  batch_id: string;
  status?: string;
  current_stage?: string;
  student_results: Array<Record<string, any>>;
  answer_images: string[];
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
      studentMapping?: Array<{ studentId: string; studentName: string; startIndex: number; endIndex: number }>;
    },
    enableReview: boolean = true,
    gradingMode?: string
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

  importToClasses: (data: GradingImportRequest) =>
    request<GradingHistoryResponse>('/grading/import', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getGradingHistory: (params?: { class_id?: string; assignment_id?: string }) => {
    const query = new URLSearchParams(params as Record<string, string>).toString();
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
      studentMapping?: Array<{ studentId: string; studentName: string; startIndex: number; endIndex: number }>;
    },
    enableReview: boolean = true,
    gradingMode?: string
  ) => gradingApi.createSubmission(
    examFiles,
    rubricFiles,
    studentBoundaries || [],
    expectedStudents,
    classContext,
    enableReview,
    gradingMode
  ),
  getSubmission: gradingApi.getSubmission,
  getResults: gradingApi.getResults,
  getRubricReviewContext: gradingApi.getRubricReviewContext,
  getResultsReviewContext: gradingApi.getResultsReviewContext,
  submitRubricReview: gradingApi.submitRubricReview,
  submitResultsReview: gradingApi.submitResultsReview,

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

export default api;
