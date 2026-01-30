'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useParams } from 'next/navigation';
import { gradingApi, ActiveRunItem } from '@/services/api';
import { useConsoleStore } from '@/store/consoleStore';
import { normalizeStudentResults } from '@/lib/gradingResults';
import { useAuthStore } from '@/store/authStore';

const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });

type ResultsReviewContext = {
  batch_id: string;
  status?: string;
  current_stage?: string;
  student_results: Array<Record<string, unknown>>;
  answer_images: string[];
};

export default function ResultsReviewPage() {
  const router = useRouter();
  const params = useParams();
  const batchId = params?.batchId as string;
  const { user } = useAuthStore();
  const setFinalResults = useConsoleStore((state) => state.setFinalResults);
  const setUploadedImages = useConsoleStore((state) => state.setUploadedImages);
  const setSubmissionId = useConsoleStore((state) => state.setSubmissionId);
  const setStatus = useConsoleStore((state) => state.setStatus);
  const setCurrentTab = useConsoleStore((state) => state.setCurrentTab);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const pickLatestRun = (runs: ActiveRunItem[], preferCompleted: boolean) => {
      if (!runs.length) return null;
      const candidates = preferCompleted ? runs.filter((run) => run.status === 'completed') : runs;
      const pool = candidates.length > 0 ? candidates : runs;
      const parseTime = (value?: string) => {
        const ts = Date.parse(value || '');
        return Number.isNaN(ts) ? 0 : ts;
      };
      return pool.reduce<ActiveRunItem | null>((latest, run) => {
        const latestTime = latest
          ? parseTime(latest.updated_at || latest.completed_at || latest.started_at || latest.created_at)
          : 0;
        const runTime = parseTime(
          run.updated_at || run.completed_at || run.started_at || run.created_at
        );
        return runTime >= latestTime ? run : latest;
      }, null);
    };

    const resolveLastBatch = async () => {
      try {
        const response = await gradingApi.getActiveRuns(user?.id);
        const latest = pickLatestRun(response.runs || [], true);
        if (!latest) {
          if (active) {
            setError('No grading runs found yet.');
            setLoading(false);
          }
          return;
        }
        if (latest.status === 'completed') {
          router.replace(`/grading/results-review/${latest.batch_id}`);
        } else {
          router.replace(`/console?batchId=${latest.batch_id}`);
        }
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to resolve latest run.');
        setLoading(false);
      }
    };

    if (batchId === 'last') {
      setLoading(true);
      resolveLastBatch();
      return () => {
        active = false;
      };
    }

    gradingApi
      .getResultsReviewContext(batchId)
      .then((data: ResultsReviewContext) => {
        if (!active) return;
        setSubmissionId(data.batch_id || batchId);
        setFinalResults(normalizeStudentResults(data.student_results || []));
        const normalizedImages = (data.answer_images || []).map((img) => {
          if (!img) return img;
          const trimmed = img.trim();
          if (
            trimmed.startsWith('data:') ||
            trimmed.startsWith('http://') ||
            trimmed.startsWith('https://') ||
            trimmed.startsWith('blob:')
          ) {
            return trimmed;
          }
          return `data:image/jpeg;base64,${trimmed}`;
        });
        setUploadedImages(normalizedImages);
        setStatus('COMPLETED');
        setCurrentTab('results');
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load results.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [batchId, setFinalResults, setUploadedImages, setSubmissionId, setStatus, setCurrentTab, router, user?.id]);

  return (
    <div className="h-screen bg-white flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-xs font-semibold text-slate-500 hover:text-slate-700"
        >
          Back
        </button>
        <div className="text-[11px] text-slate-400">Batch {batchId}</div>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        {loading ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-400">Loading results...</div>
        ) : error ? (
          <div className="h-full flex items-center justify-center text-sm text-rose-500">{error}</div>
        ) : (
          <ResultsView />
        )}
      </div>
    </div>
  );
}
