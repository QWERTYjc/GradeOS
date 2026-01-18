'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import clsx from 'clsx';
import {
  Compass,
  LayoutDashboard,
  ClipboardList,
  History,
  BarChart3,
  Users,
  BookOpenText,
  Bot,
  GraduationCap,
  FileText,
  ChevronRight,
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';

type NavItem = {
  href: string;
  label: string;
  desc?: string;
  icon: React.ReactNode;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

type RecentEntry = {
  path: string;
  label: string;
};

const RECENT_STORAGE_KEY = 'gradeos-recent-paths';

const resolvePathLabel = (pathname: string): string => {
  if (pathname.startsWith('/teacher/dashboard')) return 'Teacher - Classes';
  if (pathname.startsWith('/teacher/homework')) return 'Teacher - Homework';
  if (pathname.startsWith('/teacher/grading/history')) return 'Teacher - Grading History';
  if (pathname.startsWith('/teacher/grading/import')) return 'Teacher - Import Grading';
  if (pathname.startsWith('/teacher/class/')) return 'Teacher - Class Detail';
  if (pathname.startsWith('/teacher/statistics')) return 'Teacher - Analytics';
  if (pathname.startsWith('/student/dashboard')) return 'Student - My Courses';
  if (pathname.startsWith('/student/analysis')) return 'Student - Mistake Analysis';
  if (pathname.startsWith('/student/report')) return 'Student - Progress Report';
  if (pathname.startsWith('/student/student_assistant')) return 'Student - Learning Assistant';
  if (pathname.startsWith('/student/assistant')) return 'Student - Practice Assistant';
  if (pathname.startsWith('/grading/rubric-review')) return 'Rubric Review';
  if (pathname.startsWith('/grading/results-review')) return 'Results Review';
  if (pathname.startsWith('/console')) return 'AI Grading Console';
  if (pathname === '/login') return 'Login';
  if (pathname === '/') return 'Home';
  return 'Current Page';
};

const isActivePath = (pathname: string, href: string) =>
  pathname === href || pathname.startsWith(`${href}/`);

export default function GlobalNavLauncher() {
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useAuthStore();
  const [open, setOpen] = useState(false);
  const [recent, setRecent] = useState<RecentEntry[]>([]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const label = resolvePathLabel(pathname);
    const raw = window.localStorage.getItem(RECENT_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as RecentEntry[]) : [];
    const next = [{ path: pathname, label }, ...parsed.filter((p) => p.path !== pathname)].slice(0, 6);
    window.localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(next));
    setRecent(next);
  }, [pathname]);

  const sections = useMemo<NavSection[]>(() => {
    const base: NavSection[] = [
      {
        title: 'General',
        items: [
          { href: '/', label: 'Home', desc: 'Product overview', icon: <LayoutDashboard className="h-4 w-4" /> },
        ],
      },
    ];

    if (user?.role === Role.Teacher) {
      base.push({
        title: 'Grading Console',
        items: [
          { href: '/console', label: 'AI Grading Console', desc: 'Upload and workflow', icon: <FileText className="h-4 w-4" /> },
          { href: '/grading/rubric-review/last', label: 'Rubric Review', desc: 'Access via active batch', icon: <BookOpenText className="h-4 w-4" /> },
          { href: '/grading/results-review/last', label: 'Results Review', desc: 'Access via active batch', icon: <ClipboardList className="h-4 w-4" /> },
        ],
      });
      base.push({
        title: 'Teacher',
        items: [
          { href: '/teacher/dashboard', label: 'Classes', desc: 'Class management', icon: <Users className="h-4 w-4" /> },
          { href: '/teacher/homework', label: 'Homework', desc: 'Publish and grade', icon: <ClipboardList className="h-4 w-4" /> },
          { href: '/teacher/grading/history', label: 'Grading History', desc: 'Result tracking', icon: <History className="h-4 w-4" /> },
          { href: '/teacher/statistics', label: 'Statistics', desc: 'Learning analytics', icon: <BarChart3 className="h-4 w-4" /> },
        ],
      });
    }

    if (user?.role === Role.Student) {
      base.push({
        title: 'Student',
        items: [
          { href: '/student/dashboard', label: 'My Courses', desc: 'Assignments and scores', icon: <GraduationCap className="h-4 w-4" /> },
          { href: '/student/analysis', label: 'Mistake Analysis', desc: 'Weakness tracking', icon: <BarChart3 className="h-4 w-4" /> },
          { href: '/student/student_assistant', label: 'Learning Assistant', desc: 'AI planning and Q&A', icon: <Bot className="h-4 w-4" /> },
          { href: '/student/report', label: 'Progress Report', desc: 'Growth insights', icon: <FileText className="h-4 w-4" /> },
        ],
      });
    }

    return base;
  }, [user?.role]);

  const handleJump = (href: string) => {
    setOpen(false);
    if (href.endsWith('/last')) {
      router.push('/console');
      return;
    }
    router.push(href);
  };

  return (
    <div className="fixed bottom-6 left-6 z-50">
      <button
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Open navigation guide"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full bg-white/90 backdrop-blur border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 shadow-lg hover:shadow-xl transition"
      >
        <Compass className="h-4 w-4" />
        Guide
      </button>

      {open && (
        <div className="mt-3 w-[320px] rounded-2xl border border-slate-200 bg-white/95 backdrop-blur shadow-2xl p-4 space-y-4">
          <div>
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.2em]">Quick Jump</div>
            <div className="mt-2 text-sm font-medium text-slate-900">{resolvePathLabel(pathname)}</div>
          </div>

          {sections.map((section) => (
            <div key={section.title} className="space-y-2">
              <div className="text-xs font-semibold text-slate-500">{section.title}</div>
              {section.items.map((item) => (
                <button
                  key={item.href}
                  onClick={() => handleJump(item.href)}
                  className={clsx(
                    'w-full flex items-start gap-3 rounded-xl border px-3 py-2 text-left transition',
                    isActivePath(pathname, item.href)
                      ? 'border-blue-200 bg-blue-50 text-blue-700'
                      : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50 text-slate-700'
                  )}
                >
                  <div className="mt-0.5 text-slate-500">{item.icon}</div>
                  <div className="flex-1">
                    <div className="text-sm font-semibold">{item.label}</div>
                    {item.desc && <div className="text-xs text-slate-500">{item.desc}</div>}
                  </div>
                  <ChevronRight className="h-4 w-4 text-slate-400" />
                </button>
              ))}
            </div>
          ))}

          {recent.length > 1 && (
            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-500">Recent</div>
              <div className="grid gap-2">
                {recent
                  .filter((entry) => entry.path !== pathname)
                  .slice(0, 4)
                  .map((entry) => (
                    <button
                      key={entry.path}
                      onClick={() => handleJump(entry.path)}
                      className="w-full flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-left text-xs text-slate-600 hover:bg-slate-50"
                    >
                      <span>{entry.label}</span>
                      <span className="text-slate-400">{entry.path}</span>
                    </button>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
