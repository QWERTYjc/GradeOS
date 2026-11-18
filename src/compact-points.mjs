import {objectSchema} from './rubric-contract.mjs';
import {EVIDENCE_PROTOCOL_PROMPT,expandPointEvidence} from './point-evidence.mjs';

const str={type:'string',minLength:1};
const pages={type:'array',minItems:1,uniqueItems:true,items:{type:'integer',minimum:1}};
const cell={anyOf:[{type:'string'},{type:'number'},{type:'null'},pages]};
export const SOURCE_ISSUE_SCHEMA=objectSchema({item_id:str,point_ids:{type:'array',uniqueItems:true,items:str},scheme_pages:pages,
  observation:str,impact:str,blocks_award:{type:'boolean'}});
export const COMPACT_POINTS_SCHEMA=objectSchema({
  items:{type:'array',minItems:1,items:objectSchema({id:str,route:str,review:{type:'boolean'},p:{type:'array',minItems:1,
    items:{type:'array',minItems:6,maxItems:6,items:cell,description:'Exactly [point_id,score_or_null,literal_evidence,student_pages,state,reason]. Every point and its distinct evidence/reason remain explicit.'}}})},
  review_notes:{type:'array',items:str},source_issues:{type:'array',items:SOURCE_ISSUE_SCHEMA},
});
export const COMPACT_POINTS_PROMPT=`Use submit_grading with items, review_notes and source_issues (empty array when none).
Each item has id, route, review, p. Every p row has exactly SIX cells: [point_id, score_or_null, observed_evidence, student_pages, state, reason]. Keep all six cells and every selected-route point, including zero and null. Do not infer identity from order.
State is an EXPLICIT shorthand for the same judgment fields, never inferred from a score:
m = met / error_origin none / empty rule_ref.
u:N = unmet / error_origin N / empty rule_ref. q:N = uncertain / error_origin N / empty rule_ref.
x:N:R = exception / error_origin N / rule_ref R.
N is n=none, i=inherited, c=current, m=mixed, or u=unknown. For x use only i/c/m and R must be P or a supplied G number, e.g. x:i:G1. For unmet/uncertain specify N; do not emit a bare u or q.
For example, u:c explicitly asserts a known unmet condition caused by a current error; q:u means genuinely indeterminate credit. A met partial award is allowed only when explicitly source-authorized, with its unearned components explained.
Before submitting, check every score/state pair: u:N requires score 0; q:N requires null and review=true; m or x:N:R requires a positive source-allowed award. Current/mixed-error exceptions require review=true. Do not change a state merely to retain an unsupported award; the evidence and full source condition determine both.
Submit the complete ledger once. If rejected, use correct_grading with the host-provided hash and only complete changed or missing items; unchanged items are retained. For top-level review_notes or source_issues use null to keep them, or an explicit array to replace them. Every corrected item still includes its entire selected point route. Full validation runs on the merged ledger; this is not permission to skip points. Original images remain available. Use reopen_grading only when you need the original full context and a new complete submission.
Evidence and reason are still separate mandatory nonempty strings for EVERY point. Keep literal mathematical work and the reason for the decision; avoid restating the whole source condition or repeating evidence in the reason. Do not replace substantive reasons with status codes.
After original MS pages have actually appeared in a previous model input, append unresolved source issues to source_issues in the FINAL grading submission instead of spending a separate turn reporting them. Each issue has item_id, point_ids, scheme_pages, observation, impact, blocks_award. Blocking issues require null/review; all issues preserve review. Source inspection and submission in the SAME assistant response do not establish image delivery.
`+EVIDENCE_PROTOCOL_PROMPT.slice(EVIDENCE_PROTOCOL_PROMPT.indexOf('The host restores'));

const origins={n:'none',i:'inherited',c:'current',m:'mixed',u:'unknown'};
export function decodePointState(state) {
  if(state==='m')return ['met','none',''];
  if(typeof state!=='string')throw Error('Missing explicit point state');
  const parts=state.split(':');
  if(parts.length===2&&['u','q'].includes(parts[0])&&origins[parts[1]])return [parts[0]==='u'?'unmet':'uncertain',origins[parts[1]],''];
  if(parts.length===3&&parts[0]==='x'&&['i','c','m'].includes(parts[1])&&/^(P|G[1-9][0-9]*)$/.test(parts[2]))return ['exception',origins[parts[1]],parts[2]];
  throw Error('Invalid explicit point state');
}

// Lossless transport decoding only. An explicit "4-6" cites all three physical
// pages; never infer a missing citation from the score, evidence or geometry.
export function decodeCompactPageRefs(value, student) {
  if(Number.isSafeInteger(value)&&value>0&&student.pages.some(p=>p.page===value))return [value];
  if(Array.isArray(value))return value;
  if(typeof value!=='string'||!/^\s*[1-9]\d*(?:\s*-\s*[1-9]\d*)?(?:\s*,\s*[1-9]\d*(?:\s*-\s*[1-9]\d*)?)*\s*$/.test(value))throw Error('Invalid explicit student page references; use a bound page number, page array or explicit page range');
  const pages=[];
  for(const segment of value.split(',')) {
    const [first,last=first]=segment.trim().split(/\s*-\s*/).map(Number);
    if(!Number.isSafeInteger(first)||!Number.isSafeInteger(last)||last<first||last-first>=student.pages.length)throw Error('Invalid explicit student page range');
    for(let page=first;page<=last;page++)pages.push(page);
  }
  if(new Set(pages).size!==pages.length||pages.some(n=>!student.pages.some(p=>p.page===n)))throw Error('Unbound or duplicate explicit student page references');
  return pages;
}
export function expandCompactPoints(raw,frozen,student) {
  if(!raw||Object.keys(raw).sort().join(',')!=='items,review_notes,source_issues'||!Array.isArray(raw.source_issues)||!Array.isArray(raw.items))throw Error('Invalid compact point submission');
  const expanded={items:raw.items.map(row=>{
    if(!row||Object.keys(row).sort().join(',')!=='id,p,review,route'||!Array.isArray(row.p))throw Error('Invalid compact point item');
    return {...row,p:row.p.map(p=>{
      if(!Array.isArray(p)||p.length!==6)throw Error('Point row must have six cells');
      const [id,score,evidence,pages,state,reason]=p;
      try{return [id,score,evidence,decodeCompactPageRefs(pages,student),...decodePointState(state),reason];}
      catch(error){error.message=`${row.id}/${id}: ${error.message}`;error.itemIds=[row.id];throw error;}
    })};
  }),review_notes:raw.review_notes};
  return expandPointEvidence(expanded,frozen,student);
}
