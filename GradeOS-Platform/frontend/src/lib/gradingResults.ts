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
          ? rawPointResults.map((spr: RawObject) => {
            const awardedRaw = spr.awarded ?? spr.score ?? 0;
            const scoringPointObj = (spr.scoring_point || spr.scoringPoint) as RawObject | undefined;
            const maxPointsRaw =
              spr.max_points ??
              spr.maxPoints ??
              scoringPointObj?.score ??
              0;
            return {
              pointId: String(spr.point_id || spr.pointId || scoringPointObj?.point_id || scoringPointObj?.pointId || ''),
              description: String(
                spr.description ||
                scoringPointObj?.description ||
                ''
              ),
              awarded: Number(awardedRaw),
              maxPoints: Number(maxPointsRaw),
              evidence: String(spr.evidence || ''),
              rubricReference: String(spr.rubric_reference || spr.rubricReference || spr.rubricRef || ''),
              rubricReferenceSource: (spr.rubric_reference_source || spr.rubricReferenceSource) as string | undefined,
              decision: (spr.decision || spr.result || spr.judgement || spr.judgment) as string | undefined,
              reason: (spr.reason || spr.rationale || spr.explanation) as string | undefined,
              reviewAdjusted: (spr.review_adjusted || spr.reviewAdjusted) as boolean | undefined,
              reviewBefore: (spr.review_before || spr.reviewBefore) as any,
              reviewReason: (spr.review_reason || spr.reviewReason) as string | undefined,
              reviewBy: (spr.review_by || spr.reviewBy) as string | undefined,
              scoringPoint: {
                description: String(scoringPointObj?.description || ''),
                score: Number(scoringPointObj?.score || 0),
                maxScore: Number(scoringPointObj?.score || 0),
                isCorrect: Number(awardedRaw) > 0,
                isRequired: (scoringPointObj?.is_required || scoringPointObj?.isRequired) as boolean | undefined,
                explanation: '',
              },
            };
          })
          : [];

        const questionIdRaw = q.questionId || q.question_id || '';
        const scoreRaw = q.score ?? 0;
        const maxScoreRaw = q.maxScore ?? q.max_score ?? 0;
        return {
          questionId: typeof questionIdRaw === 'string' ? questionIdRaw : String(questionIdRaw),
          score: Number(scoreRaw),
          maxScore: Number(maxScoreRaw),
          feedback: (q.feedback ?? '') as string,
          studentAnswer: (q.studentAnswer ?? q.student_answer ?? '') as string,
          questionType: (q.questionType ?? q.question_type ?? '') as string,
          confidence: q.confidence as number | undefined,
          confidenceReason: (q.confidence_reason || q.confidenceReason) as string | undefined,
          selfCritique: (q.self_critique || q.selfCritique) as string | undefined,
          selfCritiqueConfidence: (q.self_critique_confidence || q.selfCritiqueConfidence) as number | undefined,
          rubricRefs: (() => {
            const rawRefs = (q.rubric_refs || q.rubricRefs) as unknown;
            if (!Array.isArray(rawRefs)) return undefined;
            return (rawRefs as unknown[]).map((v) => String(v));
          })(),
          typoNotes: (() => {
            const rawTypos = (q.typo_notes || q.typoNotes) as unknown;
            if (!Array.isArray(rawTypos)) return undefined;
            return (rawTypos as unknown[]).map((v) => String(v));
          })(),
          reviewSummary: (q.review_summary || q.reviewSummary) as string | undefined,
          reviewCorrections: (() => {
            const rawCorrections = (q.review_corrections || q.reviewCorrections) as unknown;
            if (!Array.isArray(rawCorrections)) return [];
            return (rawCorrections as RawObject[]).map((c) => ({
              pointId: String(c.point_id || c.pointId || ''),
              reviewReason: (c.review_reason || c.reviewReason) as string | undefined,
            }));
          })(),
          needsReview: (q.needsReview ?? q.needs_review ?? false) as boolean,
          reviewReasons: (() => {
            const rawReasons = (q.reviewReasons || q.review_reasons) as unknown;
            if (!Array.isArray(rawReasons)) return [];
            return (rawReasons as unknown[]).map((v) => String(v));
          })(),
          auditFlags: (() => {
            const rawFlags = (q.auditFlags || q.audit_flags) as unknown;
            if (!Array.isArray(rawFlags)) return [];
            return (rawFlags as unknown[]).map((v) => String(v));
          })(),
          honestyNote: (q.honestyNote || q.honesty_note) as string | undefined,
          pageIndices: (() => {
            const rawPages = (q.page_indices ?? q.pageIndices) as unknown;
            if (Array.isArray(rawPages)) {
              return (rawPages as unknown[]).map((v) => Number(v));
            }
            if (rawPages !== undefined && rawPages !== null) {
              return [Number(rawPages)];
            }
            const singlePage = (q.page_index ?? q.pageIndex) as unknown;
            if (singlePage !== undefined && singlePage !== null) {
              return [Number(singlePage)];
            }
            return undefined;
          })(),
          isCrossPage: (q.is_cross_page || q.isCrossPage) as boolean | undefined,
          mergeSource: (() => {
            const rawMerge = (q.merge_source || q.mergeSource) as unknown;
            if (!Array.isArray(rawMerge)) return undefined;
            return (rawMerge as unknown[]).map((v) => String(v));
          })(),
          scoringPoints: (q.scoringPoints || q.scoring_points) as any,
          scoringPointResults: pointResults,
          // 🔥 新增：批注坐标和步骤信息
          annotations: Array.isArray(q.annotations)
            ? q.annotations.map((ann: RawObject) => ({
              type: String(ann.type || ann.annotation_type || ''),
              page_index: ann.page_index as number | undefined,
              bounding_box: {
                x_min: Number((ann.bounding_box as RawObject)?.x_min ?? 0),
                y_min: Number((ann.bounding_box as RawObject)?.y_min ?? 0),
                x_max: Number((ann.bounding_box as RawObject)?.x_max ?? 0),
                y_max: Number((ann.bounding_box as RawObject)?.y_max ?? 0),
              },
              text: (ann.text ?? ann.label) as string | undefined,
              color: ann.color as string | undefined,
            }))
            : undefined,
          steps: (() => {
            const rawSteps = (q.steps || []) as unknown;
            if (!Array.isArray(rawSteps)) return [];
            return (rawSteps as RawObject[]).map((step) => ({
              step_id: String(step.step_id || step.stepId || ''),
              step_content: String(step.step_content || step.stepContent || ''),
              step_region: (step.step_region || step.stepRegion) as any,
              is_correct: Boolean(step.is_correct ?? step.isCorrect ?? false),
              mark_type: String(step.mark_type || step.markType || 'M'),
              mark_value: Number(step.mark_value ?? step.markValue ?? 0),
              feedback: String(step.feedback || ''),
              error_detail: String(step.error_detail || step.errorDetail || ''),
            }));
          })(),
          answerRegion: (q.answer_region || q.answerRegion) as any,
        };
      })
      : [];

    const studentNameRaw =
      r.studentName ||
      r.student_name ||
      r.student_key ||
      r.studentId ||
      r.student_id ||
      'Unknown';
    const scoreRaw = r.score ?? r.total_score ?? 0;
    const maxScoreRaw = r.maxScore ?? r.max_score ?? r.max_total_score ?? 100;
    return {
      studentName: typeof studentNameRaw === 'string' ? studentNameRaw : String(studentNameRaw),
      score: Number(scoreRaw),
      maxScore: Number(maxScoreRaw),
      gradingMode: (r.gradingMode || r.grading_mode) as string | undefined,
      percentage: r.percentage as number | undefined,
      totalRevisions: (r.totalRevisions ?? r.total_revisions) as number | undefined,
      startPage: (r.startPage ?? r.start_page) as number | undefined,
      endPage: (r.endPage ?? r.end_page) as number | undefined,
      confidence: r.confidence as number | undefined,
      needsConfirmation: (r.needsConfirmation ?? r.needs_confirmation) as boolean | undefined,
      studentSummary: (r.studentSummary || r.student_summary) as any,
      selfAudit: normalizeSelfAudit(r.selfAudit || r.self_audit),
      confession: (r.confession || r.confession_data) as any,
      questionResults,
    };
  });
};
