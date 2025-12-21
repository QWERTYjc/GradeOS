import { User, ClassEntity, Homework, Submission, Role } from '../types';

const DB_KEY = 'edu_platform_mock_db_v6'; // Incremented version to ensure fresh load

interface DBData {
  users: User[];
  classes: ClassEntity[];
  homeworks: Homework[];
  submissions: Submission[];
}

// Initial seed data with test scenarios
const initialData: DBData = {
  users: [
    { id: 'u1', name: 'Mr. Wang', username: 'teacher', password: '123456', role: Role.Teacher, classIds: [] },
    // Demo Student to match Login Screen credentials
    { id: 'u_demo', name: 'Demo Student', username: 'student', password: '123456', role: Role.Student, classIds: ['c1'] },
    // Students enrolled in Physics 101
    { id: 'u2', name: 'Alice Chen', username: 'alice', password: '123456', role: Role.Student, classIds: ['c1'] },
    { id: 'u3', name: 'Bob Liu', username: 'bob', password: '123456', role: Role.Student, classIds: ['c1'] },
    { id: 'u4', name: 'Charlie Zhang', username: 'charlie', password: '123456', role: Role.Student, classIds: ['c1'] },
    { id: 'u5', name: 'David Wu', username: 'david', password: '123456', role: Role.Student, classIds: ['c1'] },
    { id: 'u6', name: 'Eve Zhao', username: 'eve', password: '123456', role: Role.Student, classIds: ['c1'] }
  ],
  classes: [
    {
        id: 'c1',
        name: 'Physics 101 Advanced',
        teacherId: 'u1',
        inviteCode: 'PHY101',
        studentCount: 6
    }
  ],
  homeworks: [
    {
        id: 'h1',
        classId: 'c1',
        className: 'Physics 101 Advanced',
        title: 'Newton\'s Second Law Analysis',
        description: 'Explain the relationship between force, mass, and acceleration with real-world examples. Please keep it under 200 words.',
        deadline: '2024-01-15',
        createdAt: '2024-01-01T10:00:00'
    },
    {
        id: 'h2',
        classId: 'c1',
        className: 'Physics 101 Advanced',
        title: 'Kinematics Problem Set',
        description: 'Solve the projectile motion problems in Chapter 3. Upload your calculations.',
        deadline: '2024-02-01',
        createdAt: '2024-01-20T10:00:00'
    }
  ],
  submissions: [
      {
          id: 's1',
          homeworkId: 'h1',
          studentId: 'u2', // Alice
          studentName: 'Alice Chen',
          content: 'F=ma is the fundamental equation. For example, pushing a shopping cart...',
          submittedAt: '2024-01-14T15:30:00',
          status: 'graded',
          score: 92,
          aiFeedback: 'Excellent understanding. Great real-world application examples provided.'
      },
      {
          id: 's2',
          homeworkId: 'h1',
          studentId: 'u3', // Bob
          studentName: 'Bob Liu',
          content: 'Force equals mass times acceleration.',
          submittedAt: '2024-01-15T09:00:00',
          status: 'graded',
          score: 75,
          aiFeedback: 'Correct definition, but lacks the requested real-world examples. Please elaborate.'
      }
  ]
};

export const loadDB = (): DBData => {
  const stored = localStorage.getItem(DB_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch (e) {
      console.error('Failed to parse DB, resetting');
    }
  }
  // Initialize
  localStorage.setItem(DB_KEY, JSON.stringify(initialData));
  return initialData;
};

export const saveDB = (data: DBData) => {
  localStorage.setItem(DB_KEY, JSON.stringify(data));
};