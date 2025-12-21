export enum Role {
  Teacher = 'teacher',
  Student = 'student'
}

export interface User {
  id: string;
  name: string;
  username: string;
  password?: string; // Only for mock logic, usually sanitized
  role: Role;
  classIds: string[]; // Changed to array for multiple classes support
}

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
  className?: string; // Helper for display
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
  content: string; // Mocking text content or file URL
  submittedAt: string;
  status: 'pending' | 'graded';
  score?: number;
  aiFeedback?: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}