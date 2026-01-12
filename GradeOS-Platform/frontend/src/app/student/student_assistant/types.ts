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

export interface ElectiveCombo {
  comboId: string;
  subjects: Subject[];
  advantage: string;
  suitableMajors: string[];
  difficulty: number; // 1-5
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}