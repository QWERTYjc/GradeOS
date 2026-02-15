import type { PendingReview, WorkflowNode } from '@/store/consoleStore';

const MANUAL_REVIEW_NODE_IDS = new Set(['rubric_review', 'review']);

const hasManualReviewRequest = (pendingReview: PendingReview | null): boolean => {
  const reviewType = String(pendingReview?.reviewType || '').toLowerCase();
  if (!reviewType) return false;
  return reviewType.includes('rubric') || reviewType.includes('results') || reviewType.includes('review');
};

const hasRenderedManualReviewSignals = (workflowNodes: WorkflowNode[]): boolean => (
  workflowNodes.some((node) => MANUAL_REVIEW_NODE_IDS.has(node.id) && node.status !== 'pending')
);

export const shouldShowManualReviewNodes = (
  workflowNodes: WorkflowNode[],
  interactionEnabled: boolean,
  pendingReview: PendingReview | null,
): boolean => {
  if (interactionEnabled) return true;
  if (hasManualReviewRequest(pendingReview)) return true;
  if (hasRenderedManualReviewSignals(workflowNodes)) return true;
  return false;
};

export const filterManualReviewNodes = (
  workflowNodes: WorkflowNode[],
  interactionEnabled: boolean,
  pendingReview: PendingReview | null,
): WorkflowNode[] => {
  if (shouldShowManualReviewNodes(workflowNodes, interactionEnabled, pendingReview)) {
    return workflowNodes;
  }
  return workflowNodes.filter((node) => !MANUAL_REVIEW_NODE_IDS.has(node.id));
};

