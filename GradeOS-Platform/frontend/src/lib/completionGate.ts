export interface RequiredStageSeen {
  gradingConfession: boolean;
  logicReview: boolean;
}

const STAGE_ALIASES: Record<string, string> = {
  workflow_completed: "completed",
  workflow_complete: "completed",
  complete: "completed",
  done: "completed",
  export_completed: "completed",
  export_done: "completed",
  grading_confession_completed: "grading_confession_report_completed",
  confession_completed: "grading_confession_report_completed",
  confession_report_completed: "grading_confession_report_completed",
  logic_review_done: "logic_review_completed",
  review_done: "review_completed",
};

const NODE_ALIASES: Record<string, string> = {
  grading: "grade_batch",
  confession: "grading_confession_report",
  confession_report: "grading_confession_report",
  grading_confession: "grading_confession_report",
};

const STAGES_ALLOWING_RESULTS = new Set<string>([
  "logic_review",
  "logic_review_completed",
  "review",
  "review_completed",
  "export",
  "completed",
]);

const normalizeToken = (value: string) => value.trim().toLowerCase().replace(/\s+/g, "_");

export const createInitialRequiredStageSeen = (): RequiredStageSeen => ({
  gradingConfession: false,
  logicReview: false,
});

export const normalizeWorkflowStage = (stage?: string | null): string | null => {
  if (!stage || typeof stage !== "string") return null;
  const normalized = normalizeToken(stage);
  return STAGE_ALIASES[normalized] || normalized;
};

export const normalizeWorkflowNodeId = (nodeId?: string | null): string | null => {
  if (!nodeId || typeof nodeId !== "string") return null;
  const normalized = normalizeToken(nodeId);
  return NODE_ALIASES[normalized] || normalized;
};

export const deriveStageFromNodeUpdate = (
  nodeId?: string | null,
  status?: string | null
): string | null => {
  const normalizedNode = normalizeWorkflowNodeId(nodeId);
  if (!normalizedNode) return null;
  const normalizedStatus = status ? normalizeToken(status) : "";
  if (normalizedStatus === "completed") {
    if (normalizedNode === "export") {
      return "completed";
    }
    return `${normalizedNode}_completed`;
  }
  if (normalizedStatus === "failed") {
    return `${normalizedNode}_failed`;
  }
  if (normalizedStatus === "running" || normalizedStatus === "pending") {
    return normalizedNode;
  }
  return null;
};

export const applyStageSignal = (
  required: RequiredStageSeen,
  stage?: string | null
): {
  required: RequiredStageSeen;
  normalizedStage: string | null;
  terminalSeen: boolean;
  logicReviewSkipped: boolean;
} => {
  const normalizedStage = normalizeWorkflowStage(stage);
  if (!normalizedStage) {
    return {
      required,
      normalizedStage: null,
      terminalSeen: false,
      logicReviewSkipped: false,
    };
  }

  const nextRequired: RequiredStageSeen = {
    gradingConfession:
      required.gradingConfession || normalizedStage === "grading_confession_report_completed",
    logicReview: required.logicReview || normalizedStage === "logic_review_completed",
  };

  return {
    required: nextRequired,
    normalizedStage,
    terminalSeen: normalizedStage === "completed",
    logicReviewSkipped: normalizedStage === "logic_review_skipped",
  };
};

export const canFinalizeWithGate = (
  required: RequiredStageSeen,
  terminalSeen: boolean
): boolean => terminalSeen && required.gradingConfession && required.logicReview;

export const buildMissingStageReason = (required: RequiredStageSeen): string => {
  const missing: string[] = [];
  if (!required.gradingConfession) {
    missing.push("grading_confession_report_completed");
  }
  if (!required.logicReview) {
    missing.push("logic_review_completed");
  }
  if (missing.length === 0) {
    return "post-review stage mismatch detected.";
  }
  return `post-review stages missing: ${missing.join(", ")}`;
};

export const stageAllowsResultsEntry = (stage?: string | null): boolean => {
  const normalizedStage = normalizeWorkflowStage(stage);
  if (!normalizedStage) return false;
  if (normalizedStage === "logic_review_skipped") return false;
  return STAGES_ALLOWING_RESULTS.has(normalizedStage);
};
