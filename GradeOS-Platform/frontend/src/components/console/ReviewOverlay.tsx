'use client';

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useConsoleStore } from '@/store/consoleStore';

const RUBRIC_REVIEW_TYPES = new Set([
  'rubric_review_required',
  'rubric_review',
]);

const RESULTS_REVIEW_TYPES = new Set([
  'results_review_required',
  'results_review',
]);

export default function ReviewOverlay() {
  const router = useRouter();
  const { pendingReview, submissionId, setPendingReview } = useConsoleStore();
  const lastNavigateRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pendingReview || !submissionId) return;
    const reviewType = pendingReview.reviewType || '';
    const navKey = `${submissionId}:${reviewType}`;
    if (RUBRIC_REVIEW_TYPES.has(reviewType)) {
      if (lastNavigateRef.current === navKey) return;
      lastNavigateRef.current = navKey;
      setPendingReview(null);
      router.push(`/grading/rubric-review/${submissionId}`);
      return;
    }
    if (!RESULTS_REVIEW_TYPES.has(reviewType)) return;
    if (lastNavigateRef.current === navKey) return;
    lastNavigateRef.current = navKey;
    setPendingReview(null);
    router.push(`/grading/results-review/${submissionId}`);
  }, [pendingReview, submissionId, router, setPendingReview]);

  return null;
}
