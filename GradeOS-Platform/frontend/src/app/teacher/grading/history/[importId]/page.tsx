'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { gradingApi } from '@/services/api';
import { useConsoleStore } from '@/store/consoleStore';
import { normalizeStudentResults } from '@/lib/gradingResults';

const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });

type ResultsReviewContext = {
  batch_id: string;
  status?: string;
  current_stage?: string;
  student_results: Array<Record<string, any>>;
  answer_images: string[];
};

export default function GradingHistoryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const importId = params?.importId as string;
  const setFinalResults = useConsoleStore((state) => state.setFinalResults);
  const setUploadedImages = useConsoleStore((state) => state.setUploadedImages);
  const setSubmissionId = useConsoleStore((state) => state.setSubmissionId);
  const setStatus = useConsoleStore((state) => state.setStatus);
  const setCurrentTab = useConsoleStore((state) => state.setCurrentTab);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!importId) return;
    let active = true;
    let resolvedBatchId = '';
    setLoading(true);
    gradingApi
      .getGradingHistoryDetail(importId)
      .then((detail) => {
        if (!active) return null;
        resolvedBatchId = detail.record.batch_id;
        setBatchId(resolvedBatchId);
        return gradingApi.getResultsReviewContext(resolvedBatchId);
      })
      .then((data: ResultsReviewContext | null) => {
        if (!active || !data) return;
        setSubmissionId(data.batch_id || resolvedBatchId || importId);
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
        setError(err instanceof Error ? err.message : 'Failed to load grading history.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [importId, setFinalResults, setUploadedImages, setSubmissionId, setStatus, setCurrentTab]);

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-3 -mx-4 sm:-mx-6 lg:-mx-8">
        <div className="px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <button
            type="button"
            onClick={() => router.push('/teacher/grading/history')}
            className="text-xs font-semibold text-slate-500 hover:text-slate-700"
          >
            Back to History
          </button>
          {batchId && <div className="text-[11px] text-slate-400">Batch {batchId}</div>}
        </div>
        <div className="h-[calc(100vh-8rem)] min-h-0 overflow-hidden bg-white border-t border-slate-100">
          {loading ? (
            <div className="h-full flex items-center justify-center text-sm text-slate-400">Loading results...</div>
          ) : error ? (
            <div className="h-full flex items-center justify-center text-sm text-rose-500">{error}</div>
          ) : (
            <ResultsView defaultExpandDetails={true} />
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
