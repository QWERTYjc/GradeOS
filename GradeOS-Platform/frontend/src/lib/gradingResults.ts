import { StudentResult, SelfAudit } from '@/store/consoleStore';

type RawObject = Record<string, any>;

const normalizeSelfAudit = (audit: any): SelfAudit | undefined => {
  if (!audit || typeof audit !== 'object') return undefined;
  const rawIssues = audit.issues || [];
  const issues = Array.isArray(rawIssues)
    ? rawIssues.map((issue: any) => ({
      issueType: issue.issueType || issue.issue_type,
      message: issue.message,
      questionId: issue.questionId || issue.question_id,
    }))
    : [];

  return {
    summary: audit.summary,
    confidence: audit.confidence,
    issues,
    complianceAnalysis: audit.complianceAnalysis || audit.compliance_analysis || [],
    uncertaintiesAndConflicts: audit.uncertaintiesAndConflicts || audit.uncertainties_and_conflicts || [],
    overallComplianceGrade: audit.overallComplianceGrade ?? audit.overall_compliance_grade,
    honestyNote: audit.honestyNote || audit.honesty_note,
    generatedAt: audit.generatedAt || audit.generated_at,
  };
};

export const normalizeStudentResults = (raw: RawObject[]): StudentResult[] => {
  if (!Array.isArray(raw)) return [];
  return raw.map((r: RawObject) => {
    const rawQuestions = r.questionResults || r.question_results || [];
    const questionResults = Array.isArray(rawQuestions)
      ? rawQuestions.map((q: RawObject) => {
        const rawPointResults =
          q.scoring_point_results ||
          q.scoringPointResults ||
          q.scoring_results ||
          q.scoringResults ||
          [];
        const pointResults = Array.isArray(rawPointResults)
          ? rawPointResults.map((spr: RawObject) => ({
            pointId: spr.point_id || spr.pointId || spr.scoring_point?.point_id || spr.scoringPoint?.pointId,
            description:
              spr.description ||
              spr.scoring_point?.description ||
              spr.scoringPoint?.description ||
              '',
            awarded: spr.awarded ?? spr.score ?? 0,
            maxPoints:
              spr.max_points ??
              spr.maxPoints ??
              spr.scoring_point?.score ??
              spr.scoringPoint?.score ??
              0,
            evidence: spr.evidence || '',
            rubricReference: spr.rubric_reference || spr.rubricReference || spr.rubricRef || '',
            rubricReferenceSource: spr.rubric_reference_source || spr.rubricReferenceSource,
            decision: spr.decision || spr.result || spr.judgement || spr.judgment,
            reason: spr.reason || spr.rationale || spr.explanation,
            reviewAdjusted: spr.review_adjusted || spr.reviewAdjusted,
            reviewBefore: spr.review_before || spr.reviewBefore,
            reviewReason: spr.review_reason || spr.reviewReason,
            reviewBy: spr.review_by || spr.reviewBy,
            scoringPoint: {
              description: spr.scoring_point?.description || spr.scoringPoint?.description || '',
              score: spr.scoring_point?.score || spr.scoringPoint?.score || 0,
              maxScore: spr.scoring_point?.score || spr.scoringPoint?.score || 0,
              isCorrect: (spr.awarded ?? spr.score ?? 0) > 0,
              isRequired: spr.scoring_point?.is_required || spr.scoringPoint?.isRequired,
              explanation: '',
            },
          }))
          : [];

        return {
          questionId: q.questionId || q.question_id || '',
          score: q.score || 0,
          maxScore: q.maxScore || q.max_score || 0,
          feedback: q.feedback || '',
          studentAnswer: q.studentAnswer || q.student_answer || '',
          questionType: q.questionType || q.question_type || '',
          confidence: q.confidence,
          confidenceReason: q.confidence_reason || q.confidenceReason,
          selfCritique: q.self_critique || q.selfCritique,
          selfCritiqueConfidence: q.self_critique_confidence || q.selfCritiqueConfidence,
          rubricRefs: q.rubric_refs || q.rubricRefs,
          typoNotes: q.typo_notes || q.typoNotes,
          reviewSummary: q.review_summary || q.reviewSummary,
          reviewCorrections: (q.review_corrections || q.reviewCorrections || []).map((c: RawObject) => ({
            pointId: c.point_id || c.pointId || '',
            reviewReason: c.review_reason || c.reviewReason,
          })),
          needsReview: q.needsReview ?? q.needs_review ?? false,
          reviewReasons: q.reviewReasons || q.review_reasons || [],
          auditFlags: q.auditFlags || q.audit_flags || [],
          honestyNote: q.honestyNote || q.honesty_note,
          pageIndices: q.page_indices || q.pageIndices,
          isCrossPage: q.is_cross_page || q.isCrossPage,
          mergeSource: q.merge_source || q.mergeSource,
          scoringPoints: q.scoringPoints || q.scoring_points,
          scoringPointResults: pointResults,
        };
      })
      : [];

    return {
      studentName: r.studentName || r.student_name || r.student_key || 'Unknown',
      score: r.score || r.total_score || 0,
      maxScore: r.maxScore || r.max_score || r.max_total_score || 100,
      gradingMode: r.gradingMode || r.grading_mode,
      percentage: r.percentage,
      totalRevisions: r.totalRevisions ?? r.total_revisions,
      startPage: r.startPage || r.start_page,
      endPage: r.endPage || r.end_page,
      confidence: r.confidence,
      needsConfirmation: r.needsConfirmation ?? r.needs_confirmation,
      studentSummary: r.studentSummary || r.student_summary,
      selfAudit: normalizeSelfAudit(r.selfAudit || r.self_audit),
      questionResults,
    };
  });
};
