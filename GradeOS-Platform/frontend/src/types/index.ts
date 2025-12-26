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
}

export interface QuestionResult {
  questionId: string;
  score: number;
  maxScore: number;
  feedback: string;
}
