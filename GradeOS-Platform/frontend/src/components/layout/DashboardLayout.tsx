'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';

interface Props {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: Props) {
  const { user, logout } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  // 教师导航 - 完整功能
  const teacherNav = [
    { href: '/teacher/dashboard', label: '班级管理', icon: '📚', desc: '管理班级和学生' },
    { href: '/teacher/homework', label: '作业管理', icon: '📝', desc: '发布和批改作业' },
    { href: '/console', label: 'AI批改', icon: '🤖', desc: '智能批改控制台' },
    { href: '/teacher/statistics', label: '数据统计', icon: '📊', desc: '班级学情分析' },
  ];

  // 学生导航 - 完整功能
  const studentNav = [
    { href: '/student/dashboard', label: '我的课程', icon: '📚', desc: '查看作业和成绩' },
    { href: '/student/assistant', label: 'AI学习助手', icon: '🤖', desc: '智能学习规划' },
    { href: '/student/analysis', label: '错题分析', icon: '🔍', desc: '深度错题诊断' },
    { href: '/student/report', label: '学情报告', icon: '📈', desc: '个人成长分析' },
  ];

  const navItems = user?.role === Role.Teacher ? teacherNav : studentNav;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
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
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      pathname === item.href || pathname.startsWith(item.href + '/')
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <span className="mr-2">{item.icon}</span>
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

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
