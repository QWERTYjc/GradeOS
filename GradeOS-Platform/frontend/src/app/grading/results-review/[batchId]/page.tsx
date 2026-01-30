'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useParams } from 'next/navigation';
import { gradingApi } from '@/services/api';
import { useConsoleStore } from '@/store/consoleStore';
import { normalizeStudentResults } from '@/lib/gradingResults';

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
  const setFinalResults = useConsoleStore((state) => state.setFinalResults);
  const setUploadedImages = useConsoleStore((state) => state.setUploadedImages);
  const setSubmissionId = useConsoleStore((state) => state.setSubmissionId);
  const setStatus = useConsoleStore((state) => state.setStatus);
  const setCurrentTab = useConsoleStore((state) => state.setCurrentTab);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
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
  }, [batchId, setFinalResults, setUploadedImages, setSubmissionId, setStatus, setCurrentTab]);

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
