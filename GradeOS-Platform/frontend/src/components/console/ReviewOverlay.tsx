'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, ArrowRight, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';
import { useConsoleStore } from '@/store/consoleStore';
import { gradingApi } from '@/services/api';

const RUBRIC_REVIEW_TYPES = new Set([
  'rubric_review_required',
  'rubric_review',
]);

const RESULTS_REVIEW_TYPES = new Set([
  'results_review_required',
  'results_review',
]);

const GRADING_RETRY_TYPES = new Set([
  'grading_retry_required',
  'grading_retry',
]);

const REVIEW_LABELS: Record<string, string> = {
  rubric_review_required: '批改标准交互',
  rubric_review: '批改标准交互',
  results_review_required: '批改结果交互',
  results_review: '批改结果交互',
  grading_retry_required: '批改断点重试',
  grading_retry: '批改断点重试',
};

export default function ReviewOverlay() {
  const { pendingReview, submissionId, setPendingReview, setStatus, setCurrentTab, setReviewFocus } = useConsoleStore();
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reviewType = pendingReview?.reviewType || '';
  const isRubricReview = RUBRIC_REVIEW_TYPES.has(reviewType);
  const isResultsReview = RESULTS_REVIEW_TYPES.has(reviewType);
  const isGradingRetry = GRADING_RETRY_TYPES.has(reviewType);
  const reviewLabel = REVIEW_LABELS[reviewType] || '人工交互';
  const reviewMessage = pendingReview?.message || '需要人工介入确认。';

  const reviewFocus = isRubricReview ? 'rubric' : isResultsReview ? 'results' : null;

  if (!pendingReview || !submissionId) {
    return null;
  }

  const handleNavigate = () => {
    if (!reviewFocus) return;
    const target = isRubricReview
      ? `/grading/rubric-review/${submissionId}`
      : `/grading/results-review/${submissionId}`;
    setReviewFocus(reviewFocus);
    setCurrentTab(isRubricReview ? 'process' : 'results');
    router.push(target);
  };

  const handleSkip = async () => {
    if (!submissionId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      if (isRubricReview) {
        await gradingApi.submitRubricReview({ batch_id: submissionId, action: 'approve' });
      } else if (isResultsReview) {
        await gradingApi.submitResultsReview({ batch_id: submissionId, action: 'approve' });
      } else if (isGradingRetry) {
        await gradingApi.submitGradingRetry({ batch_id: submissionId, action: 'retry' });
      }
      setPendingReview(null);
      setStatus('RUNNING');
      setCurrentTab('process');
      setReviewFocus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[320px] rounded-2xl border border-blue-100 bg-white/90 p-4 shadow-xl backdrop-blur">
      <div className="flex items-start gap-3">
        <div className="rounded-full bg-blue-50 p-2 text-blue-600">
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-slate-900">{reviewLabel}</div>
          <p className="mt-1 text-xs text-slate-500">{reviewMessage}</p>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-600">
          {error}
        </div>
      )}

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={handleNavigate}
          disabled={isGradingRetry}
          className="flex-1 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-slate-300"
        >
          打开结果页
          <ArrowRight className="ml-2 inline h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={handleSkip}
          disabled={isSubmitting}
          className={clsx(
            'flex-1 rounded-full px-3 py-2 text-xs font-semibold text-white transition',
            isSubmitting ? 'bg-slate-300' : 'bg-slate-900 hover:bg-slate-800'
          )}
        >
          {isSubmitting ? '处理中...' : isGradingRetry ? '立刻重试' : '继续流程'}
          <CheckCircle2 className="ml-2 inline h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
