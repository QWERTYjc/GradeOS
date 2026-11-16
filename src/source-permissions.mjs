import {digest} from './core.mjs';
import {COMPACT_POINTS_SCHEMA} from './compact-points.mjs';
import {objectSchema} from './rubric-contract.mjs';

const str={type:'string',minLength:1};
const ids={type:'array',minItems:1,uniqueItems:true,items:str};
export const INSPECT_SCORING_SOURCES_SCHEMA=objectSchema({targets:{type:'array',minItems:1,items:objectSchema({item_id:str,point_ids:ids})}});
export const PERMISSION_SUBMIT_SCHEMA=structuredClone(COMPACT_POINTS_SCHEMA);
PERMISSION_SUBMIT_SCHEMA.properties.source_assessments={type:'array',items:{type:'array',minItems:4,maxItems:4,
  items:{anyOf:[str,ids]},description:'Exactly [item_id,point_id,outcome,rule_refs]. outcome: resolved, unresolved_source, unresolved_evidence. rule_refs includes P and any applicable G IDs.'}};
PERMISSION_SUBMIT_SCHEMA.required.push('source_assessments');

export function sourcePermissionPrompt(prompt){
  return prompt.replace('Use submit_grading with items, review_notes and source_issues (empty array when none).',
    'Use submit_grading with items, review_notes, source_issues and source_assessments (empty arrays when none).')+`
SOURCE-PERMISSION REVIEW BEFORE FINAL SUBMISSION:
For EVERY point proposed below its source maximum or unknown, first inspect the original source with inspect_scoring_sources(targets). It mechanically supplies the point/item/related-item MS pages plus all general-instruction pages; pages already delivered need not be repeated. read_ms_pages also remains available. Source images must have appeared in a PRIOR model input, not a read and submit in the same assistant response. Work out provisional affected points first; do not emit the full final ledger just to discover missing pages.
Coverage is determined by the host from actual point awards, NOT from whether you classify a point as an exception, ordinary failure or blank. Blank/missing work is not exempt: inspect the full answer book and source rules for implicit working, continuation or alternative evidence before denying credit.
For every final non-full or null point, include exactly one source_assessments row: [item_id,point_id,outcome,rule_refs]. Cite P for the COMPLETE local source bundle (condition, source_text, award_type, allowed_awards, dependencies, item criterion/route/related context), plus G IDs used from the complete general rules. The source bundle is already supplied in the frozen rubric; inspect images rather than retranscribing it. Write the substantive assessment ONCE in that point's existing detailed reason, not an extra duplicate explanation.
Evaluate ALL applicable source allowances in both directions. A wrong final value or a failed earlier mark is not by itself a reason to ignore local follow-through, alternative methods, implicit steps or source-authorized partial credit. Do not infer that a permission is absent from the lack of a keyword. A local exception can qualify a general rule; do not let a general accuracy requirement silently erase a local permission. Identify why the local allowance does or does not cover the observed error/origin and why no higher award is supported. A rule's mere existence does not license arbitrary new errors either.
resolved means the actual source establishes the numerical award, including an exclusion from higher credit; retain the detailed source-bound reason. If permission scope is not established, do not force either positive credit or zero: choose unresolved_source, null, review=true, and a blocking source_issues entry for that point after source inspection. If the SOURCE is clear but required answer evidence is unreadable, use unresolved_evidence with null/review without inventing a source issue. The short full-credit attestation remains only for ordinary full-credit points; it cannot replace any of these assessments.
This is the primary grader's explicit source assessment, not an independent review or teacher certification.`;
}

const key=(item,point)=>JSON.stringify([item,point]);
export function sourceReviewBundle(frozen,itemId,pointId){
  const item=frozen.artifact.items.find(i=>i.item_id===itemId),point=item?.scoring_points.find(p=>p.point_id===pointId);
  if(!point)throw Error('Unknown source review point');
  const related=frozen.artifact.items.filter(i=>item.related_item_ids.includes(i.item_id));
  const pages=[...new Set([...item.source_pages,...point.source_pages,...related.flatMap(i=>i.source_pages),...frozen.artifact.general_instructions.flatMap(g=>g.source_pages)])].sort((a,b)=>a-b);
  const source={point,item_criterion:item.criteria,routes:item.routes,related_items:related,general_instructions:frozen.artifact.general_instructions};
  return {item_id:itemId,point_id:pointId,source_pages:pages,source_hash:digest(source),rubric_hash:frozen.hash};
}
export function inspectSourceTargets(raw,frozen){
  if(!raw||Object.keys(raw).join(',')!=='targets'||!Array.isArray(raw.targets)||!raw.targets.length)throw Error('Missing source review targets');
  const seen=new Set(),bundles=[];
  for(const t of raw.targets){
    if(!t||Object.keys(t).sort().join(',')!=='item_id,point_ids'||!Array.isArray(t.point_ids)||!t.point_ids.length)throw Error('Invalid source review target');
    for(const id of t.point_ids){const k=key(t.item_id,id);if(seen.has(k))throw Error('Duplicate source review point');seen.add(k);bundles.push(sourceReviewBundle(frozen,t.item_id,id));}
  }
  return {targets:bundles,pages:[...new Set(bundles.flatMap(b=>b.source_pages))].sort((a,b)=>a-b)};
}

export function validateSourceAssessments(raw,grade,frozen,schemeSeen){
  if(!Array.isArray(raw.source_assessments))throw Error('Missing source_assessments');
  const required=new Map();
  for(const item of grade.items)for(const p of item.point_decisions){
    const source=frozen.artifact.items.find(i=>i.item_id===item.item_id).scoring_points.find(q=>q.point_id===p.point_id);
    if(p.score===null||p.score<source.max_score)required.set(key(item.item_id,p.point_id),{item,p,bundle:sourceReviewBundle(frozen,item.item_id,p.point_id)});
  }
  if(raw.source_assessments.length!==required.size)throw Error('Assess every non-full or unknown point exactly once, including ordinary failures and blank work');
  const seen=new Set(),checks=[];
  for(const row of raw.source_assessments){
    if(!Array.isArray(row)||row.length!==4)throw Error('Source assessment must have four cells');
    const [itemId,pointId,outcome,refs]=row,k=key(itemId,pointId),target=required.get(k);
    if(!target||seen.has(k))throw Error('Foreign, full-credit or duplicate source assessment');seen.add(k);
    const {item,p,bundle}=target;
    if(outcome==='resolved'&&raw.source_issues.some(i=>i.item_id===itemId&&i.blocks_award&&(!i.point_ids.length||i.point_ids.includes(pointId))))throw Error('Resolved point contradicts its blocking source issue');
    const missing=bundle.source_pages.filter(n=>!schemeSeen.has(n));
    if(missing.length)throw Error(`Source assessment ${itemId}/${pointId} requires original MS pages ${JSON.stringify(missing)} in a prior model input; use inspect_scoring_sources`);
    if(!Array.isArray(refs)||!refs.includes('P')||new Set(refs).size!==refs.length||refs.some(r=>r!=='P'&&!(typeof r==='string'&&/^G[1-9]\d*$/.test(r)&&Number(r.slice(1))<=frozen.artifact.general_instructions.length)))throw Error('Bind assessment to P and valid general source references');
    if(!['resolved','unresolved_source','unresolved_evidence'].includes(outcome))throw Error('Invalid source assessment outcome');
    if(outcome==='resolved'){
      if(p.score===null)throw Error('Unresolved award cannot be a resolved source assessment');
    }else{
      if(p.score!==null||p.relation!=='uncertain'||!item.review_required)throw Error('Unresolved source/evidence assessment requires null and review');
      if(outcome==='unresolved_source'&&!raw.source_issues.some(i=>i.item_id===itemId&&i.blocks_award&&(!i.point_ids.length||i.point_ids.includes(pointId))))throw Error('Unresolved source scope requires a blocking source issue');
    }
    checks.push({...bundle,outcome,rule_refs:[...refs],proposed_score:p.score,authority:'primary model source-permission assessment; not independent verification'});
  }
  return checks;
}
