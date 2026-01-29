import { StudentResult, SelfAudit } from '@/store/consoleStore';

type RawObject = Record<string, unknown>;

const normalizeSelfAudit = (audit: unknown): SelfAudit | undefined => {
  if (!audit || typeof audit !== 'object') return undefined;
  const auditObj = audit as RawObject;
  const rawIssues = auditObj.issues || [];
  const issues = Array.isArray(rawIssues)
    ? rawIssues.map((issue: unknown) => {
      const issueObj = issue as RawObject;
      return {
      issueType: (issueObj.issueType || issueObj.issue_type) as string,
      message: issueObj.message as string,
      questionId: (issueObj.questionId || issueObj.question_id) as string,
    };})
    : [];
  const rawCompliance = auditObj.complianceAnalysis || auditObj.compliance_analysis || [];
  const complianceAnalysis = Array.isArray(rawCompliance)
    ? rawCompliance.map((item: unknown) => {
      if (typeof item === 'string') {
        return { notes: item };
      }
      const obj = item as RawObject;
      return {
        goal: obj.goal as string,
        tag: obj.tag as string,
        notes: obj.notes as string,
        evidence: obj.evidence as string,
      };
    })
    : [];
  const rawUncertainties = auditObj.uncertaintiesAndConflicts || auditObj.uncertainties_and_conflicts || [];
  const uncertaintiesAndConflicts = Array.isArray(rawUncertainties)
    ? rawUncertainties.map((item: unknown) => {
      if (typeof item === 'string') {
        return { issue: item };
      }
      const obj = item as RawObject;
      return {
        issue: obj.issue as string,
        impact: obj.impact as string,
        questionIds: (obj.questionIds ?? obj.question_ids) as string[],
        reportedToUser: (obj.reportedToUser ?? obj.reported_to_user) as boolean,
      };
    })
    : [];

  return {
    summary: auditObj.summary as string,
    confidence: auditObj.confidence as number,
    issues,
    complianceAnalysis,
    uncertaintiesAndConflicts,
    overallComplianceGrade: (auditObj.overallComplianceGrade ?? auditObj.overall_compliance_grade) as number,
    honestyNote: (auditObj.honestyNote || auditObj.honesty_note) as string,
    generatedAt: (auditObj.generatedAt || auditObj.generated_at) as string,
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
          // 🔥 新增：批注坐标和步骤信息
          annotations: q.annotations || [],
          steps: (q.steps || []).map((step: RawObject) => ({
            step_id: step.step_id || step.stepId || '',
            step_content: step.step_content || step.stepContent || '',
            step_region: step.step_region || step.stepRegion,
            is_correct: step.is_correct ?? step.isCorrect ?? false,
            mark_type: step.mark_type || step.markType || 'M',
            mark_value: step.mark_value ?? step.markValue ?? 0,
            feedback: step.feedback || '',
            error_detail: step.error_detail || step.errorDetail || '',
          })),
          answerRegion: q.answer_region || q.answerRegion,
        };
      })
      : [];

    const studentNameRaw = r.studentName || r.student_name || r.student_key || 'Unknown';
    const scoreRaw = r.score ?? r.total_score ?? 0;
    const maxScoreRaw = r.maxScore ?? r.max_score ?? r.max_total_score ?? 100;
    return {
      studentName: typeof studentNameRaw === 'string' ? studentNameRaw : String(studentNameRaw),
      score: Number(scoreRaw),
      maxScore: Number(maxScoreRaw),
      gradingMode: (r.gradingMode || r.grading_mode) as string | undefined,
      percentage: r.percentage as number | undefined,
      totalRevisions: (r.totalRevisions ?? r.total_revisions) as number | undefined,
      startPage: (r.startPage || r.start_page) as number | undefined,
      endPage: (r.endPage || r.end_page) as number | undefined,
      confidence: r.confidence as number | undefined,
      needsConfirmation: (r.needsConfirmation ?? r.needs_confirmation) as boolean | undefined,
      studentSummary: (r.studentSummary || r.student_summary) as any,
      selfAudit: normalizeSelfAudit(r.selfAudit || r.self_audit),
      gradingAnnotations: (r.gradingAnnotations || r.grading_annotations || r.annotations || r.annotation_result) as any,
      questionResults,
    };
  });
};
