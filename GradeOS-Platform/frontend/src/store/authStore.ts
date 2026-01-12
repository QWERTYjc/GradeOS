import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, Role } from '@/types';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (user: User) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      login: (user) => set({ user, isAuthenticated: true }),
      logout: () => set({ user: null, isAuthenticated: false }),
      updateUser: (updates) => set((state) => ({
        user: state.user ? { ...state.user, ...updates } : null
      })),
    }),
    {
      name: 'gradeos-auth',
    }
  )
);

// Mock users for demo
export const MOCK_USERS: User[] = [
  {
    id: 't-001',
    name: 'Demo Teacher',
    username: 'teacher',
    password: '123456',
    role: Role.Teacher,
    classIds: []
  },
  {
    id: 's-001',
    name: 'Demo Student',
    username: 'student',
    password: '123456',
    role: Role.Student,
    classIds: []
  }
];
