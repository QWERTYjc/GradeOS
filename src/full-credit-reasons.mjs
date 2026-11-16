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
    `Keep complete observed evidence and page references for EVERY point. First make the same full scoring judgment; never change a score or review flag to use a shorter explanation.
For an unambiguous ordinary FULL-credit point only, when state=m, the awarded score equals that point's source maximum, item review=false, and there are no uncertainties or source issues affecting that item, use reason "=" to explicitly attest "${FULL_CREDIT_ATTESTATION}" if a longer reason would only repeat the supplied evidence/criterion. This is your explicit judgment, not a host-inferred award. The host expands this exact phrase; all source conditions and observed evidence remain in the report. If a substantive explanation is needed even for full credit, write it normally.
Global source notes still require review_notes: explain their scope and flag affected items or source issues. A note does not by itself require repeating an explanation at unrelated points. If its scope or effect is unresolved, preserve review/unknown where affected; do not assume permission to award.
EVERY other point requires its own substantive nonempty reason: partial credit, zero, unknown, any exception/follow-through, uncertainty about that point or source dispute. State the unmet or uncertain condition and concrete evidence gap; retain applicable error origin, exception permission/scope and why current work does or does not qualify. Do not abbreviate these reasons to "=" or a generic status. Do not duplicate observations already in the evidence cell or repeat the whole criterion. Never omit or shorten the actual evidence to save explanation tokens.`);
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
