import {objectSchema,checkPages} from './rubric-contract.mjs';
import {COMPACT_POINTS_PROMPT,SOURCE_ISSUE_SCHEMA,expandCompactPoints} from './compact-points.mjs';

const str={type:'string',minLength:1};
const refs={type:'array',minItems:1,uniqueItems:true,items:str};
const pages={type:'array',minItems:1,uniqueItems:true,items:{type:'integer',minimum:1}};
export const SHARED_EVIDENCE_SCHEMA=objectSchema({
  items:{type:'array',minItems:1,items:objectSchema({id:str,route:str,review:{type:'boolean'},
    e:{type:'array',minItems:1,items:{type:'array',minItems:3,maxItems:3,
      items:{anyOf:[str,pages]},description:'Exactly [evidence_id,literal_observation,student_pages]. IDs are local to this item.'}},
    p:{type:'array',minItems:1,items:{type:'array',minItems:5,maxItems:5,
      items:{anyOf:[str,{type:'number'},{type:'null'},refs]},
      description:'Exactly [point_id,score_or_null,evidence_ids,state,reason]. Explicit judgment and references for every point.'}},
  })},review_notes:{type:'array',items:str},source_issues:{type:'array',items:SOURCE_ISSUE_SCHEMA},
});

// Reuse the unchanged v4 judgment rules, replacing only the transport instructions.
export const SHARED_EVIDENCE_PROMPT=`Use submit_grading with items, review_notes and source_issues (empty array when none).
Each item has id, route, review, e, p. e is an item-local evidence bank: each row is [evidence_id, literal_observation, student_pages]. Keep page ownership, literal mathematical work, errors and uncertainty. Use short explicit IDs. Record an observed passage ONCE and reuse its ID for every applicable point instead of repeating its text/pages. Do not invent text or combine contradictory observations. References cannot resolve another item's bank IDs. Needed earlier-part work may be recorded in this bank with its explicit origin label and true pages as dependency context; never present it as current-part work or grant credit merely for its presence. On the same pages an exactly identical observation must have only one ID. Do not put an entire answer in one vague summary; retain the actual supporting steps.
Every p row has exactly FIVE cells: [point_id, score_or_null, evidence_ids, state, reason]. evidence_ids is a nonempty array of IDs from THIS item's bank; more than one ID can support a point. Keep EVERY selected-route point including zero and null, with an explicit score, state and its OWN substantive reason. A reference does not imply credit: the same observation can satisfy one condition and fail another. Blank, missing or unreadable work must be explicitly recorded with inspected pages and referenced, never omitted or guessed.
The host restores literal evidence in reference order and the union of its source pages for each point, retaining the individual evidence-to-page bindings and original bank. All evidence entries must be used. Do not repeat cited observations in reasons; explain their relation to this specific condition. No score, reason or uncertainty is supplied by the host.
`+COMPACT_POINTS_PROMPT.slice(COMPACT_POINTS_PROMPT.indexOf('State is an EXPLICIT')).replace(
  'Evidence and reason are still separate mandatory nonempty strings for EVERY point.',
  'Every bank observation is a mandatory nonempty string; EVERY point has explicit nonempty evidence references and its own nonempty reason.');

function keys(value,expected) {
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join(',')!==[...expected].sort().join(','))throw Error('Invalid shared-evidence fields');
}
const text=value=>typeof value==='string'&&Boolean(value.trim());

export function expandSharedEvidence(raw,frozen,student) {
  keys(raw,['items','review_notes','source_issues']);
  if(!Array.isArray(raw.items))throw Error('Missing shared-evidence items');
  const banks=new Map();
  const compact={...raw,items:raw.items.map(row=>{
    keys(row,['id','route','review','e','p']);
    if(!Array.isArray(row.e)||!row.e.length||!Array.isArray(row.p))throw Error('Missing evidence bank or points');
    const bank=new Map(),used=new Set(),observations=new Set();
    for(const entry of row.e){
      if(!Array.isArray(entry)||entry.length!==3||!text(entry[0])||!text(entry[1])||bank.has(entry[0]))throw Error('Invalid or duplicate evidence ID');
      const [id,literal,pages]=entry;checkPages(pages,student);
      const identity=JSON.stringify([literal,[...pages].sort((a,b)=>a-b)]);
      if(observations.has(identity))throw Error('Duplicate literal evidence on the same pages; reuse its ID');
      observations.add(identity);bank.set(id,{evidence_id:id,evidence:literal,student_pages:[...pages]});
    }
    const p=row.p.map(point=>{
      if(!Array.isArray(point)||point.length!==5)throw Error('Referenced point must have five cells');
      const [id,score,refs,state,reason]=point;
      if(!Array.isArray(refs)||!refs.length||refs.some(ref=>!text(ref)||!bank.has(ref))||new Set(refs).size!==refs.length)throw Error('Missing, duplicate or foreign item evidence reference');
      const evidence=refs.map(ref=>{used.add(ref);return bank.get(ref);});
      return [id,score,evidence.map(e=>e.evidence).join('\n'),[...new Set(evidence.flatMap(e=>e.student_pages))].sort((a,b)=>a-b),state,reason];
    });
    if(used.size!==bank.size)throw Error('Unused evidence entry');
    if(banks.has(row.id))throw Error('Duplicate evidence owner');
    banks.set(row.id,{bank:[...bank.values()],refs:new Map(row.p.map(p=>[p[0],[...p[2]]]))});
    return {id:row.id,route:row.route,review:row.review,p};
  })};
  const expanded=expandCompactPoints(compact,frozen,student);
  for(const item of expanded.items){
    const binding=banks.get(item.item_id);item.evidence_bank=binding.bank;
    for(const point of item.point_decisions)point.evidence_refs=binding.refs.get(point.point_id);
  }
  return expanded;
}

// Preserve each fragment-to-page binding when a consumer expects a display string.
// This adds labels only; the original literal strings remain unchanged in the bank.
export function evidenceWithSourcePages(item,point) {
  if(!item.evidence_bank)return point.evidence;
  const bank=new Map(item.evidence_bank.map(e=>[e.evidence_id,e]));
  if(!Array.isArray(point.evidence_refs)||!point.evidence_refs.length)throw Error('Missing saved evidence references');
  const entries=point.evidence_refs.map(id=>{const e=bank.get(id);if(!e)throw Error('Unbound saved evidence reference');return e;});
  const pages=[...new Set(entries.flatMap(e=>e.student_pages))].sort((a,b)=>a-b);
  if(entries.map(e=>e.evidence).join('\n')!==point.evidence||JSON.stringify(pages)!==JSON.stringify(point.student_pages))throw Error('Saved evidence projection differs from source bank');
  return entries.map(e=>`[${e.evidence_id}; 答卷页 ${e.student_pages.join('、')}] ${e.evidence}`).join('\n');
}
