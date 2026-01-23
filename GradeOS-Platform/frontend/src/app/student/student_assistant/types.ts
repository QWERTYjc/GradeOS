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

export interface ElectiveCombo {
  comboId: string;
  subjects: Array<Subject | string>;
  advantage: string;
  suitableMajors: string[];
  difficulty: number; // 1-5
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface MasteryData {
  score: number;       // 0-100
  level: string;       // beginner / developing / proficient / mastery
  analysis: string;    // 分析说明
  evidence: string[];  // 证据列表
  suggestions: string[]; // 改进建议
}

export interface ConceptNode {
  id: string;
  name: string;
  description: string;
  understood: boolean;
  children?: ConceptNode[];
}

export interface EnhancedChatMessage extends ChatMessage {
  mastery?: MasteryData;
  focusMode?: boolean;
  conceptBreakdown?: ConceptNode[];
  nextQuestion?: string;
  responseType?: 'chat' | 'question' | 'assessment' | 'explanation';
}
