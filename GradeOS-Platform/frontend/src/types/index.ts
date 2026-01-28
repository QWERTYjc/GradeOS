// ============ Auth & User Types ============
export enum Role {
  Teacher = 'teacher',
  Student = 'student',
  Admin = 'admin'
}

export interface User {
  id: string;
  name: string;
  username: string;
  password?: string;
  role: Role;
  classIds: string[];
}

// ============ Class & Homework Types ============
export interface ClassEntity {
  id: string;
  name: string;
  teacherId: string;
  inviteCode: string;
  studentCount: number;
}

export interface Homework {
  id: string;
  classId: string;
  className?: string;
  title: string;
  description: string;
  deadline: string;
  createdAt: string;
  allowEarlyGrading?: boolean;
}

export interface Submission {
  id: string;
  homeworkId: string;
  studentId: string;
  studentName: string;
  content: string;
  submittedAt: string;
  status: 'submitted' | 'pending' | 'graded';
  score?: number;
  aiFeedback?: string;
}

// ============ Grading Import Types ============
export interface GradingImportRecord {
  importId: string;
  batchId: string;
  classId: string;
  className?: string;
  assignmentId?: string;
  assignmentTitle?: string;
  studentCount: number;
  status: string;
  createdAt: string;
  revokedAt?: string;
}

export interface GradingImportItem {
  itemId: string;
  importId: string;
  batchId: string;
  classId: string;
  studentId: string;
  studentName: string;
  status: string;
  createdAt: string;
  revokedAt?: string;
  result?: Record<string, any>;
}

// ============ Student Assistant Types ============
export type Language = 'en' | 'zh';

export enum Subject {
  CHINESE = 'Chinese',
  ENGLISH = 'English',
  MATH = 'Mathematics',
  LIBERAL_STUDIES = 'Citizenship & Social Development',
  PHYSICS = 'Physics',
  CHEMISTRY = 'Chemistry',
  BIOLOGY = 'Biology',
  ECONOMICS = 'Economics',
  GEOGRAPHY = 'Geography',
  HISTORY = 'History',
  ICT = 'ICT',
}

export interface ScoreEntry {
  id: string;
  subject: Subject | string;
  score: number;
  averageScore: number;
  date: string;
  weakPoints: string[];
}

export interface WrongQuestion {
  id: string;
  subject: Subject;
  topic: string;
  description: string;
  correction: string;
  date: string;
}

export interface StudyPlan {
  dailyPlan: Array<{
    period: string;
    content: string;
    target: string;
  }>;
  weeklyReview: string;
  monthlyCheckPoint: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// ============ Grading Types ============
export interface GradingJob {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  results?: GradingResult[];
  createdAt: string;
}

export interface GradingResult {
  studentId: string;
  studentName: string;
  totalScore: number;
  maxScore: number;
  gradingMode?: string;
  questions: QuestionResult[];
  confidence?: number;
  needsConfirmation?: boolean;
  startPage?: number;
  endPage?: number;
}

export interface ScoringPoint {
  description: string;
  score: number;
  maxScore: number;
  isCorrect: boolean;
  explanation?: string;
  isRequired?: boolean;
}

/** 得分点评分结果 - 对应后端 ScoringPointResult */
export interface ScoringPointResult {
  scoringPoint: ScoringPoint;
  pointId?: string;
  description?: string;
  awarded: number;
  maxPoints?: number;
  evidence: string;
  rubricReference?: string;
  rubricReferenceSource?: string;
  decision?: string;
  reason?: string;
}

export interface QuestionResult {
  questionId: string;
  score: number;
  maxScore: number;
  feedback: string;
  confidence?: number;
  confidenceReason?: string;
  selfCritique?: string;
  selfCritiqueConfidence?: number;
  rubricRefs?: string[];
  needsReview?: boolean;
  reviewReasons?: string[];
  auditFlags?: string[];
  honestyNote?: string;
  typoNotes?: string[];
  studentAnswer?: string;
  questionType?: string;
  isCorrect?: boolean;
  scoringPoints?: ScoringPoint[];
  /** 得分点明细列表 - 新增 */
  scoringPointResults?: ScoringPointResult[];
  /** 出现在哪些页面 - 新增 */
  pageIndices?: number[];
  /** 是否跨页题目 - 新增 */
  isCrossPage?: boolean;
  /** 合并来源（如果是合并结果）- 新增 */
  mergeSource?: string[];
  /** 批注坐标列表 - 用于 Canvas 渲染 */
  annotations?: StepAnnotation[];
  /** 步骤信息列表 - 包含每一步的坐标和得分 */
  steps?: StepInfo[];
  /** 答案区域坐标 */
  answerRegion?: BoundingBoxCoords;
}

/** 步骤批注 - 后端返回的批注数据 */
export interface StepAnnotation {
  type: string;
  page_index?: number;
  bounding_box: BoundingBoxCoords;
  text?: string;
  color?: string;
}

/** 步骤信息 - 包含每一步的坐标和得分 */
export interface StepInfo {
  step_id: string;
  step_content?: string;
  step_region?: BoundingBoxCoords;
  is_correct: boolean;
  mark_type: 'M' | 'A';
  mark_value: number;
  feedback?: string;
  error_detail?: string;
}

/** 边界框坐标 */
export interface BoundingBoxCoords {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

/** 跨页题目信息 - 对应后端 CrossPageQuestion */
export interface CrossPageQuestion {
  questionId: string;
  pageIndices: number[];
  confidence: number;
  mergeReason: string;
}

/** 学生边界信息 - 对应后端 StudentBoundary */
export interface StudentBoundary {
  studentKey: string;
  studentId?: string;
  studentName?: string;
  startPage: number;
  endPage: number;
  confidence: number;
  needsConfirmation: boolean;
}

/** 批量批改结果 - 对应后端 BatchGradingResult */
export interface BatchGradingResult {
  batchId: string;
  studentResults: GradingResult[];
  totalPages: number;
  processedPages: number;
  crossPageQuestions: CrossPageQuestion[];
  errors: Array<{ type: string; message: string; pageIndex?: number }>;
}


// ============ OpenBoard Forum Types ============
export type ForumStatus = 'pending' | 'active' | 'rejected';

export interface Forum {
  forum_id: string;
  name: string;
  description: string;
  creator_id: string;
  creator_name?: string;
  status: ForumStatus;
  rejection_reason?: string;
  post_count: number;
  reply_count: number;
  last_activity_at?: string;
  created_at: string;
}

export interface ForumPost {
  post_id: string;
  forum_id: string;
  forum_name?: string;
  title: string;
  content: string;
  images?: string[];  // 图片列表（base64或URL）
  author_id: string;
  author_name?: string;
  reply_count: number;
  created_at: string;
  updated_at: string;
}

export interface ForumReply {
  reply_id: string;
  post_id: string;
  content: string;
  images?: string[];  // 图片列表（base64或URL）
  author_id: string;
  author_name?: string;
  created_at: string;
}

export interface ForumSearchResult {
  post_id: string;
  title: string;
  content_snippet: string;
  forum_id: string;
  forum_name: string;
  author_name: string;
  created_at: string;
}

export interface ForumUserStatus {
  user_id: string;
  name: string;
  is_banned: boolean;
  banned_at?: string;
  ban_reason?: string;
  posts: Array<{
    post_id: string;
    title: string;
    forum_name: string;
    is_deleted: boolean;
    created_at: string;
  }>;
}

export interface ForumModLog {
  log_id: string;
  moderator_id: string;
  moderator_name?: string;
  action: string;
  target_type: string;
  target_id: string;
  reason?: string;
  created_at: string;
}
