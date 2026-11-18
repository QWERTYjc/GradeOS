import {COMPACT_POINTS_PROMPT,expandCompactPoints} from './compact-points.mjs';

export const BRIEF_REASON_STYLE='brief-full-credit';
export const FULL_CREDIT_ATTESTATION='Full criterion met.';
export class BriefReasonError extends Error {
  constructor(targets) {
    super(`Brief reason requires ordinary full credit without source uncertainty; preserve a detailed reason for partial, unknown or exception decisions. Invalid reason locations: ${JSON.stringify(targets)}`);
    this.targets=targets;
  }
}
export function compactPromptForReasons(style='detailed') {
  if(style==='detailed')return COMPACT_POINTS_PROMPT;
  if(style!==BRIEF_REASON_STYLE)throw Error('Invalid point reason style');
  return COMPACT_POINTS_PROMPT.replace(
    'Evidence and reason are still separate mandatory nonempty strings for EVERY point. Keep literal mathematical work and the reason for the decision; avoid restating the whole source condition or repeating evidence in the reason. Do not replace substantive reasons with status codes.',
    `Record the decisive literal work directly in each evidence cell, with all components needed to check the point: exact signs, values, steps, diagram features or observed absence. Distinguish working from the written result. Cite a single page as a number, or all contributing pages for cross-page work.
For ordinary full credit (state=m, score=point maximum, review=false, no item uncertainty or source issue), "=" explicitly attests "${FULL_CREDIT_ATTESTATION}". Use it when evidence and criterion suffice. Otherwise give the specific scoring reason once, without narrating the observation again. For partial, zero or unknown credit name the unmet or unclear condition. For an exception identify its source permission, scope, error origin and why the current step qualifies. Preserve uncertainty and explain global source notes in review_notes. Choose the wording after grading each point; never change a score or review flag to abbreviate.`);
}

export function expandBriefFullCredit(raw,frozen,student,{allowReviewedItemAttestation=false}={}) {
  // Keep v4's complete schema/point validation, and only decode an explicit attestation.
  const restored=structuredClone(raw),shortened=new Set(),invalid=[];
  if(!Array.isArray(restored?.items)||!Array.isArray(restored.source_issues))throw Error('Invalid brief-reason submission');
  for(const row of restored.items){
    if(!Array.isArray(row?.p))throw Error('Missing point rows');
    for(const p of row.p){
      if(!Array.isArray(p)||p.length!==6)throw Error('Point row must have six cells');
      if(p[5]!=='=')continue;
      const item=frozen.artifact.items.find(i=>i.item_id===row.id);
      const point=item?.scoring_points.find(q=>q.point_id===p[0]);
      if(!point||p[4]!=='m'||typeof p[1]!=='number'||p[1]!==point.max_score||(!allowReviewedItemAttestation&&row.review!==false)||
          item.uncertainties.length||restored.source_issues.some(i=>i.item_id===row.id))
        {invalid.push({item_id:row.id,point_id:p[0]});continue;}
      p[5]=FULL_CREDIT_ATTESTATION;shortened.add(JSON.stringify([row.id,p[0]]));
    }
  }
  if(invalid.length) throw new BriefReasonError(invalid);
  const expanded=expandCompactPoints(restored,frozen,student);
  for(const item of expanded.items)for(const p of item.point_decisions)if(shortened.has(JSON.stringify([item.item_id,p.point_id])))
    p.reason_encoding='explicit_full_credit_attestation';
  return expanded;
}
