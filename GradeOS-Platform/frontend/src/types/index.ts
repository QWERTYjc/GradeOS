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
}

export interface Submission {
  id: string;
  homeworkId: string;
  studentId: string;
  studentName: string;
  content: string;
  submittedAt: string;
  status: 'pending' | 'graded';
  score?: number;
  aiFeedback?: string;
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
  subject: Subject;
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
  awarded: number;
  evidence: string;
}

export interface QuestionResult {
  questionId: string;
  score: number;
  maxScore: number;
  feedback: string;
  confidence?: number;
  studentAnswer?: string;
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
