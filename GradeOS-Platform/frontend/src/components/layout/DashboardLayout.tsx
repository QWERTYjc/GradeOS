'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';
import {
  BarChart3,
  Bot,
  ClipboardList,
  FileText,
  GraduationCap,
  History,
  LayoutDashboard,
  Users,
} from 'lucide-react';

interface Props {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: Props) {
  const { user, logout } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();
  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const teacherNav = [
    { href: '/teacher/dashboard', label: 'Classes', icon: <Users className="h-4 w-4" />, desc: 'Manage classes and students' },
    { href: '/teacher/homework', label: 'Homework', icon: <ClipboardList className="h-4 w-4" />, desc: 'Assign and grade' },
    { href: '/console', label: 'AI Grading', icon: <FileText className="h-4 w-4" />, desc: 'Grading console' },
    { href: '/teacher/grading/history', label: 'Grading History', icon: <History className="h-4 w-4" />, desc: 'Imports and results' },
    { href: '/teacher/statistics', label: 'Analytics', icon: <BarChart3 className="h-4 w-4" />, desc: 'Class insights' },
  ];

  const studentNav = [
    { href: '/student/dashboard', label: 'My Courses', icon: <GraduationCap className="h-4 w-4" />, desc: 'Assignments and scores' },
    { href: '/student/student_assistant', label: 'AI Assistant', icon: <Bot className="h-4 w-4" />, desc: 'Learning support' },
    { href: '/student/analysis', label: 'Mistake Analysis', icon: <LayoutDashboard className="h-4 w-4" />, desc: 'Targeted review' },
    { href: '/student/report', label: 'Progress Report', icon: <BarChart3 className="h-4 w-4" />, desc: 'Growth insights' },
  ];

  const navItems = user?.role === Role.Teacher ? teacherNav : studentNav;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-8">
              <Link href="/" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">G</span>
                </div>
                <span className="font-bold text-slate-800">GradeOS</span>
              </Link>

              <nav className="hidden md:flex items-center gap-1">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={item.desc}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      pathname === item.href || pathname.startsWith(item.href + '/')
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <span className="mr-2 inline-flex">{item.icon}</span>
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium text-slate-800">{user?.name}</p>
                <p className="text-xs text-slate-500 capitalize">{user?.role}</p>
              </div>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
