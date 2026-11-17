import { recordScoreText, recordBasisText } from './ui.mjs';
import {compactGradingMark} from './annotation-layout.mjs';

export const validAnnotationRect = rect => Boolean(rect && ['x','y','width','height'].every(key=>Number.isFinite(rect[key]))
  && rect.x>=0 && rect.y>=0 && rect.width>0 && rect.height>0
  && rect.x+rect.width<=1.000001 && rect.y+rect.height<=1.000001);

// The saved grading record is the authority. Rendering comments must never start
// a model request, invent a new judgement, or become a second copy of the grade.
export function annotationBatches(state, pageId) {
  return (state.tasks || []).filter(task => task.kind === 'grade'
    && task.groups?.some(group => group.pageIds.includes(pageId)) && task.records?.length);
}

export function gradingAnnotations(state, taskId, groupId, pageId = null) {
  const task = state.tasks?.find(task => task.id === taskId);
  const group = task?.groups?.find(group => group.id === groupId);
  if (!group) return [];
  const current = state.groups?.find(row => row.id === groupId);
  // A repartitioned answer book needs a new run, not old comments on new pupils.
  if (!current || JSON.stringify(current.pageIds) !== JSON.stringify(group.pageIds)) return [];
  const pages = new Map(state.pages.map(page => [page.id, page]));
  const frozenPages = new Map((task.pages || []).map(page => [page.id, page]));
  const validPage = id => {
    const page = pages.get(id), frozen = frozenPages.get(id);
    const hash = frozen?.sha256 || task.pageHashes?.[id];
    return page && page.active !== false && (!hash || hash === page.sha256);
  };
  const document = state.documents?.find(doc => doc.taskId === taskId && doc.proposalId);
  const approval = document?.approvals?.at(-1);
  const guide = approval ? { documentId: document.id, revision: approval.revision, hash: approval.hash } : null;
  return task.records.filter(record => record.groupId === groupId).map((record, index) => {
    const review = state.reviews?.findLast(row => row.taskId === taskId && row.recordId === record.id && row.originalHash === record.originalHash);
    const score = review ? review.score : record.score;
    const studentPageIds = [...new Set(record.studentPageIds || [])].filter(id => group.pageIds.includes(id) && validPage(id));
    const schemePageIds = [...new Set(record.schemePageIds || [])].filter(id => task.scheme?.pageIds.includes(id) && validPage(id));
    const questionPageIds = [...new Set(record.questionPageIds || [])].filter(id => task.question?.pageIds.includes(id) && validPage(id));
    const page = pages.get(pageId && studentPageIds.includes(pageId) ? pageId : studentPageIds[0]);
    const anchor = page && state.gradingAnchors?.findLast(row => row.taskId === taskId && row.recordId === record.id
      && row.originalHash === record.originalHash && row.target.pageId === page.id && row.target.pageHash === page.sha256);
    const inlineRegions=page?(record.annotationRegions||[]).filter(region=>region.pageId===page.id&&region.pageHash===page.sha256&&validAnnotationRect(region.rect)):[];
    const rectangles=anchor&&validAnnotationRect(anchor.target.rect)?[anchor.target.rect]:inlineRegions.map(region=>validAnnotationRect(region.contextRect)?region.contextRect:region.rect);
    const located=rectangles.length>0;
    const target=page?{kind:'page',pageId:page.id,pageHash:page.sha256,fileName:page.fileName,sourcePage:page.sourcePage,role:'student',shape:'rectangle',
      rect:rectangles.length===1?rectangles[0]:{x:0,y:0,width:1,height:1},points:[]}:null;
    const label = `${record.itemId}${record.pointId ? ` · ${record.pointId.toUpperCase()}` : ''}`;
    const scoreLabel = recordScoreText(record, score);
    const originalScoreLabel = recordScoreText(record);
    const basisLabel = recordBasisText(record);
    const tone = score == null || (record.reviewRequired && !review) ? 'review' : record.maximum != null && score === record.maximum ? 'credit' : 'deduction';
    const hasIssue = Array.isArray(record.uncertainties)
      ? record.uncertainties.length > 0 || (score == null && record.disposition !== 'feedback_only')
      : tone !== 'credit';
    const status = record.disposition === 'feedback_only' ? '定性反馈' : score == null ? '分数待定' : tone === 'review' ? '需要确认' : tone === 'credit' ? '已得分' : '未得满分';
    const reason = record.reason === 'Full criterion met.' ? '原批改判定：满足该评分点。' : record.reason || '原批改未提供判定说明。';
    const text = [
      `${label} · ${basisLabel || ""} · ${scoreLabel} · ${status}${review ? ' · 老师已复核' : ''}`,
      `答卷依据：${record.evidence || '原批改未提供可引用证据，需核对答卷。'}`,
      `评分条件：${record.sourceText || '原批改未提供评分条件，需核对 MS。'}`,
      `原始判定（${originalScoreLabel}）：${reason}`,
      ...(record.uncertainties || []).map(note => `待核实：${note}`),
      ...(review ? [`老师复核（${scoreLabel}）：${review.reason}`] : []),
      `答卷页：${studentPageIds.map(id => pages.get(id).sourcePage).join('、') || '未定位'}；MS 页：${schemePageIds.map(id => pages.get(id).sourcePage).join('、') || '未提供'}`,
      ...(guide ? [`本批采用评分实施.md v${guide.revision}`] : []),
      located ? inlineRegions.some(region=>region.precision==='grid-cells')&&!anchor ? `位置说明：批改时引用的 ${rectangles.length} 处区域，包含一格留白；请结合原页核对。` : `位置说明：${anchor?'按需定位':'批改时定位'}的 ${rectangles.length} 处笔迹区域，保留原始评分。` : '位置说明：根据原批改引用的页码显示在页边，未定位到具体笔迹。',
    ].join('\n\n');
    return {
      id: `grading-${record.id}-${review?.id || 'original'}`, source: 'grading', taskId, groupId,
      recordId: record.id, originalHash: record.originalHash, reviewId: review?.id || null,
      index: index + 1, itemId: record.itemId, disposition: record.disposition, label, score, maximum: record.maximum, originalScore: record.score,
      pointId:record.pointId,awardType:record.awardType,mark:record.disposition==='feedback_only'?{text:'评语',tone:'review',type:''}:compactGradingMark({score,maximum:record.maximum,pointId:record.pointId,awardType:record.awardType}),
      scoreLabel, originalScoreLabel, tone, hasIssue, status, reason, evidence: record.evidence, sourceText: record.sourceText,
      review, guide, text, studentPageIds, schemePageIds, questionPageIds, basisLabel, uncertainties: record.uncertainties || [], location: located ? 'region' : 'page',
      locationOrigin:anchor?'on-demand':located?'inline-grading':null, annotationStatus:record.annotationStatus,
      // A page-level comment references the whole original page, never a blank
      // crop of the margin marker. The marker is a display affordance only.
      locationNote:!located?'已关联到本页，尚未定位具体笔迹。':record.annotationStatus==='partial'?'部分引用区域未能定位，当前仅显示已匹配的框。':'',annotationIssues:record.annotationIssues||[],
      target, regions:rectangles.map((rect,index)=>({...target,rect,...(!anchor&&inlineRegions[index]?.precision==='ocr-regions'?{precision:'ocr-regions',regionId:inlineRegions[index].regionId,regionManifestHash:inlineRegions[index].regionManifestHash}:{})})),
    };
  }).filter(row => !pageId || row.studentPageIds.includes(pageId));
}

export function findGradingAnnotation(state, annotationId, pageId = null) {
  if (!annotationId?.startsWith('grading-')) return null;
  for (const task of state.tasks || []) for (const group of task.groups || []) {
    if (!task.records?.some(record => annotationId.startsWith(`grading-${record.id}-`))) continue;
    const note = gradingAnnotations(state, task.id, group.id, pageId).find(row => row.id === annotationId);
    if (note) return note;
  }
  return null;
}
