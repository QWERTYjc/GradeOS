'use client';

import React, { useEffect, useMemo } from 'react';
import clsx from 'clsx';
import { useConsoleStore, WorkflowNode } from '@/store/consoleStore';
import { filterManualReviewNodes } from './manualReviewVisibility';
import {
  CheckCircle2,
  Clock,
  Loader2,
  AlertCircle,
  ChevronRight,
  Cpu,
  BookOpenText,
  ShieldCheck,
  Users,
  FileText,
  Eye,
} from 'lucide-react';

type StepTone = 'pending' | 'running' | 'completed' | 'failed';

const toneStyles: Record<StepTone, { dot: string; ring: string; text: string; bg: string }> = {
  pending: {
    dot: 'bg-slate-300',
    ring: 'ring-slate-200',
    text: 'text-slate-500',
    bg: 'bg-white',
  },
  running: {
    dot: 'bg-blue-500',
    ring: 'ring-blue-200',
    text: 'text-blue-700',
    bg: 'bg-blue-50/40',
  },
  completed: {
    dot: 'bg-emerald-500',
    ring: 'ring-emerald-200',
    text: 'text-emerald-700',
    bg: 'bg-emerald-50/40',
  },
  failed: {
    dot: 'bg-rose-500',
    ring: 'ring-rose-200',
    text: 'text-rose-700',
    bg: 'bg-rose-50/40',
  },
};

const normalizeTone = (status: WorkflowNode['status']): StepTone => {
  if (status === 'running') return 'running';
  if (status === 'completed') return 'completed';
  if (status === 'failed') return 'failed';
  return 'pending';
};

const stepIcon = (id: string) => {
  if (id === 'intake') return <FileText className="h-4 w-4" />;
  if (id === 'preprocess') return <Cpu className="h-4 w-4" />;
  if (id === 'rubric_parse') return <BookOpenText className="h-4 w-4" />;
  if (id === 'rubric_confession_report') return <Eye className="h-4 w-4" />;
  if (id === 'rubric_self_review') return <ShieldCheck className="h-4 w-4" />;
  if (id === 'rubric_review') return <Users className="h-4 w-4" />;
  if (id === 'grade_batch') return <Cpu className="h-4 w-4" />;
  if (id === 'grading_confession_report') return <Eye className="h-4 w-4" />;
  if (id === 'logic_review') return <ShieldCheck className="h-4 w-4" />;
  if (id === 'review') return <Users className="h-4 w-4" />;
  if (id === 'export') return <CheckCircle2 className="h-4 w-4" />;
  return <Clock className="h-4 w-4" />;
};

const statusGlyph = (tone: StepTone) => {
  if (tone === 'running') return <Loader2 className="h-4 w-4 animate-spin" />;
  if (tone === 'completed') return <CheckCircle2 className="h-4 w-4" />;
  if (tone === 'failed') return <AlertCircle className="h-4 w-4" />;
  return <Clock className="h-4 w-4" />;
};

export default function WorkflowSteps() {
  const workflowNodes = useConsoleStore((s) => s.workflowNodes);
  const selectedNodeId = useConsoleStore((s) => s.selectedNodeId);
  const setSelectedNodeId = useConsoleStore((s) => s.setSelectedNodeId);
  const status = useConsoleStore((s) => s.status);
  const submissionId = useConsoleStore((s) => s.submissionId);
  const pendingReview = useConsoleStore((s) => s.pendingReview);
  const interactionEnabled = useConsoleStore((s) => s.interactionEnabled);

  const visibleNodes = useMemo(() => {
    const filteredNodes = filterManualReviewNodes(workflowNodes, interactionEnabled, pendingReview);

    const lastActiveIndex = filteredNodes.findLastIndex((n) => n.status !== 'pending');
    const hasAnyActive = lastActiveIndex >= 0;
    const revealIndex = hasAnyActive ? lastActiveIndex + 1 : 1; // show at least intake + preprocess
    return filteredNodes.map((n, idx) => ({
      node: n,
      isFuture: idx > revealIndex && n.status === 'pending',
    }));
  }, [interactionEnabled, pendingReview, workflowNodes]);

  useEffect(() => {
    if (!selectedNodeId) return;
    const stillVisible = visibleNodes.some(({ node }) => node.id === selectedNodeId);
    if (!stillVisible) {
      setSelectedNodeId(null);
    }
  }, [selectedNodeId, setSelectedNodeId, visibleNodes]);

  return (
    <div className="w-full h-full flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-slate-400">
              Workflow
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div className="text-xl font-semibold text-slate-900">AI Grading Run</div>
              <div
                className={clsx(
                  'rounded-full px-2.5 py-1 text-[11px] font-semibold',
                  status === 'RUNNING'
                    ? 'bg-blue-50 text-blue-700'
                    : status === 'REVIEWING'
                      ? 'bg-amber-50 text-amber-700'
                      : status === 'COMPLETED'
                        ? 'bg-emerald-50 text-emerald-700'
                        : status === 'FAILED'
                          ? 'bg-rose-50 text-rose-700'
                          : 'bg-slate-100 text-slate-600'
                )}
              >
                {status}
              </div>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {submissionId ? (
                <>
                  Batch <span className="font-mono text-slate-700">{submissionId.slice(0, 8)}</span>
                </>
              ) : (
                'No batch yet'
              )}
            </div>
          </div>

          {pendingReview && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
              <div className="font-semibold">Paused</div>
              <div className="mt-1 opacity-80">
                {pendingReview.reviewType || 'review_required'}
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 space-y-3">
          {visibleNodes.map(({ node, isFuture }, idx) => {
            const tone = normalizeTone(node.status);
            const styles = toneStyles[tone];
            const isSelected = selectedNodeId === node.id;
            const agents = node.children || [];
            const agentCounts = agents.length
              ? {
                  total: agents.length,
                  done: agents.filter((a) => a.status === 'completed').length,
                  failed: agents.filter((a) => a.status === 'failed').length,
                }
              : null;

            return (
              <button
                key={node.id}
                type="button"
                onClick={() => {
                  if (isFuture) return;
                  setSelectedNodeId(node.id);
                }}
                className={clsx(
                  'w-full text-left rounded-2xl border px-4 py-3 transition',
                  isFuture
                    ? 'cursor-default opacity-50 bg-white border-slate-100'
                    : 'hover:border-slate-200 hover:bg-slate-50/40 cursor-pointer',
                  isSelected ? 'ring-2 ring-blue-500 border-transparent' : 'border-slate-100',
                  styles.bg
                )}
                aria-disabled={isFuture}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <div
                      className={clsx(
                        'mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-white ring-1 shadow-sm',
                        styles.ring,
                        styles.text
                      )}
                    >
                      {stepIcon(node.id)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-semibold text-slate-900 truncate">
                          {node.label}
                        </span>
                        <span className={clsx('h-2 w-2 rounded-full', styles.dot)} />
                        <span className={clsx('text-[11px] font-semibold', styles.text)}>
                          {node.status}
                        </span>
                      </div>

                      <div className="mt-1 text-xs text-slate-500">
                        {node.message ? node.message : isFuture ? 'Not started' : 'Click to open stream'}
                      </div>

                      {agentCounts && (
                        <div className="mt-2 text-[11px] text-slate-500">
                          Agents: {agentCounts.done}/{agentCounts.total}
                          {agentCounts.failed > 0 ? `, failed ${agentCounts.failed}` : ''}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <div className={clsx('text-slate-400', tone === 'running' && 'text-blue-600')}>
                      {statusGlyph(tone)}
                    </div>
                    <ChevronRight className="h-4 w-4 text-slate-300" />
                  </div>
                </div>

                {/* Lightweight connector feel without a progress bar */}
                {idx < visibleNodes.length - 1 && !isFuture && (
                  <div className="mt-3">
                    <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

