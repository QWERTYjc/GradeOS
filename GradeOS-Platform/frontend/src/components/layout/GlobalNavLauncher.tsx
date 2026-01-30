'use client';

import React, { useEffect, useMemo, useState, useCallback } from 'react';
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
import { gradingApi, ActiveRunItem } from '@/services/api';

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

const dismissedRunsKey = (userId?: string) => `gradeos-dismissed-runs:${userId || 'guest'}`;

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
  const [activeRuns, setActiveRuns] = useState<ActiveRunItem[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [dismissedRuns, setDismissedRuns] = useState<Set<string>>(new Set());
  const hideLauncher = pathname.startsWith('/student/student_assistant');

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const key = dismissedRunsKey(user?.id);
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? (JSON.parse(raw) as string[]) : [];
    setDismissedRuns(new Set(parsed));
  }, [user?.id]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const key = dismissedRunsKey(user?.id);
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== key) return;
      const parsed = event.newValue ? (JSON.parse(event.newValue) as string[]) : [];
      setDismissedRuns(new Set(parsed));
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [user?.id]);

  useEffect(() => {
    if (!user?.id || user.role !== Role.Teacher) {
      setActiveRuns([]);
      setRunsError(null);
      setRunsLoading(false);
      return;
    }
    let mounted = true;
    const fetchRuns = async () => {
      if (!mounted) return;
      setRunsLoading(true);
      try {
        const response = await gradingApi.getActiveRuns(user.id);
        if (mounted) {
          setActiveRuns(response.runs || []);
          setRunsError(null);
        }
      } catch {
        if (mounted) {
          setRunsError('无法加载批改批次');
        }
      } finally {
        if (mounted) {
          setRunsLoading(false);
        }
      }
    };
    fetchRuns();
    const interval = setInterval(fetchRuns, 8000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [user?.id, user?.role]);

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

  const visibleRuns = useMemo(
    () => activeRuns.filter((run) => !(run.status === 'completed' && dismissedRuns.has(run.batch_id))),
    [activeRuns, dismissedRuns]
  );

  const persistDismissedRun = useCallback((batchId: string) => {
    if (typeof window === 'undefined') return;
    const key = dismissedRunsKey(user?.id);
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? (JSON.parse(raw) as string[]) : [];
    if (!parsed.includes(batchId)) {
      const next = [...parsed, batchId];
      window.localStorage.setItem(key, JSON.stringify(next));
      setDismissedRuns(new Set(next));
    }
  }, [user?.id]);

  const resolveLatestRun = useCallback(
    async (target: 'results' | 'rubric') => {
      let runs = activeRuns;
      if (runs.length === 0 && user?.id) {
        try {
          const response = await gradingApi.getActiveRuns(user.id);
          runs = response.runs || [];
        } catch {
          return null;
        }
      }
      if (runs.length === 0) {
        try {
          const history = await gradingApi.getGradingHistory();
          const records = history.records || [];
          if (records.length === 0) return null;
          const parseTime = (value?: string) => {
            const ts = Date.parse(value || '');
            return Number.isNaN(ts) ? 0 : ts;
          };
          const latestRecord = records.reduce((latest, record) => {
            const latestTime = latest ? parseTime(latest.created_at) : 0;
            const recordTime = parseTime(record.created_at);
            return recordTime >= latestTime ? record : latest;
          }, records[0]);
          const resolvedBatchId = latestRecord.batch_id || latestRecord.import_id;
          if (!resolvedBatchId) return null;
          return {
            batch_id: resolvedBatchId,
            status: latestRecord.status || 'completed',
            class_id: latestRecord.class_id || undefined,
            homework_id: latestRecord.assignment_id || undefined,
            created_at: latestRecord.created_at,
            completed_at: latestRecord.created_at,
          } as ActiveRunItem;
        } catch {
          return null;
        }
      }

      const preferCompleted = target === 'results';
      const filtered = preferCompleted
        ? runs.filter((run) => run.status === 'completed')
        : runs.filter((run) => run.status !== 'completed');
      const pool = filtered.length > 0 ? filtered : runs;

      const parseTime = (value?: string) => {
        const ts = Date.parse(value || '');
        return Number.isNaN(ts) ? 0 : ts;
      };
      return pool.reduce<ActiveRunItem | null>((latest, run) => {
        const latestTime = latest
          ? parseTime(
              latest.updated_at || latest.completed_at || latest.started_at || latest.created_at
            )
          : 0;
        const runTime = parseTime(
          run.updated_at || run.completed_at || run.started_at || run.created_at
        );
        return runTime >= latestTime ? run : latest;
      }, null);
    },
    [activeRuns, user?.id]
  );

  const formatStageLabel = (stage?: string) => {
    if (!stage) return 'pending';
    return stage.replace(/_/g, ' ');
  };

  if (hideLauncher) {
    return null;
  }

  const handleJump = async (href: string) => {
    setOpen(false);
    if (href.endsWith('/last')) {
      const isResults = href.includes('/grading/results-review');
      const isRubric = href.includes('/grading/rubric-review');
      const target = isResults ? 'results' : 'rubric';
      const latest = await resolveLatestRun(target);
      if (!latest) {
        router.push('/console');
        return;
      }
      if (isResults) {
        if (latest.status === 'completed') {
          router.push(`/grading/results-review/${latest.batch_id}`);
        } else {
          router.push(`/console?batchId=${latest.batch_id}`);
        }
        return;
      }
      if (isRubric) {
        if (latest.status !== 'completed') {
          router.push(`/grading/rubric-review/${latest.batch_id}`);
        } else {
          router.push(`/grading/results-review/${latest.batch_id}`);
        }
        return;
      }
      router.push('/console');
      return;
    }
    router.push(href);
  };

  const handleRunJump = (run: ActiveRunItem) => {
    setOpen(false);
    if (run.status === 'completed') {
      persistDismissedRun(run.batch_id);
      router.push(`/grading/results-review/${run.batch_id}`);
      return;
    }
    router.push(`/console?batchId=${run.batch_id}`);
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

          {user?.role === Role.Teacher && (
            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-500">批改批次</div>
              {runsError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                  {runsError}
                </div>
              )}
              {!runsError && runsLoading && (
                <div className="text-xs text-slate-400">加载中...</div>
              )}
              {!runsError && !runsLoading && visibleRuns.length === 0 && (
                <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                  暂无进行中的批改批次
                </div>
              )}
              {!runsError && visibleRuns.length > 0 && (
                <div className="grid gap-2">
                  {visibleRuns.slice(0, 6).map((run) => {
                    const progressValue = typeof run.progress === 'number'
                      ? Math.max(0, Math.min(Math.round(run.progress * 100), 100))
                      : null;
                    return (
                      <button
                        key={run.batch_id}
                        onClick={() => handleRunJump(run)}
                        className={clsx(
                          'w-full rounded-lg border px-3 py-2 text-left text-xs transition',
                          run.status === 'completed'
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                            : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50 text-slate-700'
                        )}
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <span>Batch {run.batch_id.slice(0, 8)}</span>
                          <span className="uppercase tracking-[0.2em] text-[10px] text-slate-400">
                            {run.status}
                          </span>
                        </div>
                        <div className="mt-1 text-[10px] uppercase text-slate-400">
                          {formatStageLabel(run.current_stage)}
                        </div>
                        {progressValue !== null && (
                          <div className="mt-2">
                            <progress
                              value={progressValue}
                              max={100}
                              className="h-1.5 w-full overflow-hidden rounded-full [&::-webkit-progress-bar]:bg-slate-200 [&::-webkit-progress-value]:bg-slate-900 [&::-moz-progress-bar]:bg-slate-900"
                            />
                            <div className="mt-1 text-[10px] text-slate-400">{progressValue}%</div>
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
