import type { PendingReview, WorkflowNode } from '@/store/consoleStore';

const MANUAL_REVIEW_NODE_IDS = new Set(['rubric_review', 'review']);

const hasManualReviewRequest = (pendingReview: PendingReview | null): boolean => {
  const reviewType = String(pendingReview?.reviewType || '').toLowerCase();
  if (!reviewType) return false;
  return reviewType.includes('rubric') || reviewType.includes('results') || reviewType.includes('review');
};

export const shouldShowManualReviewNodes = (
  _workflowNodes: WorkflowNode[],
  interactionEnabled: boolean,
  pendingReview: PendingReview | null,
  manualReviewRequested: boolean,
): boolean => {
  if (interactionEnabled) return true;
  if (hasManualReviewRequest(pendingReview)) return true;
  if (manualReviewRequested) return true;
  return false;
};

export const filterManualReviewNodes = (
  workflowNodes: WorkflowNode[],
  interactionEnabled: boolean,
  pendingReview: PendingReview | null,
  manualReviewRequested: boolean,
): WorkflowNode[] => {
  if (shouldShowManualReviewNodes(workflowNodes, interactionEnabled, pendingReview, manualReviewRequested)) {
    return workflowNodes;
  }
  return workflowNodes.filter((node) => !MANUAL_REVIEW_NODE_IDS.has(node.id));
};
