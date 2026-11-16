import { objectSchema, checkPages, validatePointDecisions } from './rubric-contract.mjs';

export const VISUAL_EVIDENCE_PROMPT = `Read the student's visible work literally before comparing it with the MS. Do not complete a missing or ambiguous digit, sign, label or step from the expected answer, and do not propagate a guessed reading into later evidence.
Before an award or deduction that depends on an uncertain visual distinction, compare the actual marks and their repeated occurrences on the relevant answer page. If the reading is still unresolved and page tools are available, call read_student_pages for only those original pages with a specific visual question; inspect the returned images in the next model turn before deciding. "Not clearly readable" does not establish "absent" or "incorrect".
If one targeted reinspection cannot resolve the reading, or page tools are unavailable, keep the affected point uncertain with null and review rather than guessing either credit or zero. State the unresolved readings briefly in the evidence/reason. Clearly readable incorrect work still follows the ordinary MS rules; clear pages need no reassurance reread.`;

const str = { type:'string', minLength:1 };
const pages = {type:'array',minItems:1,uniqueItems:true,items:{type:'integer',minimum:1}};
// A homogeneous JSON-Schema union keeps the tool compatible with the provider. Host validation
// below enforces every position, type and source binding before expansion or persistence.
const cell = {anyOf:[{type:'string'},{type:'number'},{type:'null'},pages]};
export const EVIDENCE_SUBMIT_SCHEMA = objectSchema({
  items:{type:'array',minItems:1,items:objectSchema({
    id:str,route:str,review:{type:'boolean'},
    p:{type:'array',minItems:1,items:{type:'array',minItems:8,maxItems:8,items:cell,
      description:'Exactly [point_id, score_or_null, observed_evidence, student_pages, relation, error_origin, rule_ref, reason]. relation=met|unmet|exception|uncertain; error_origin=none|inherited|current|mixed|unknown. rule_ref is empty except for a source-authorized exception.'}},
  })},
  review_notes:{type:'array',items:str},
});
export const EVIDENCE_PROTOCOL_PROMPT = `Use the compact submit_grading schema: each item has id, route, review and p.
Each p row has exactly eight positions: [point_id, score_or_null, observed_evidence, student_pages, relation, error_origin, rule_ref, reason].
The host restores question IDs, maxima, source references, item summaries and totals from the frozen rubric and your actual decisions. Do not repeat those fixed fields.
Keep EVERY selected-route point, its observed evidence, page references and its own judgment. Use concise mathematical evidence and reasons; never replace observations with generic praise.
relation is met, unmet, exception or uncertain. It describes evidence against this point's entire source condition, including any explicit partial-credit levels, not merely use of a similar technique.
For source-defined partial credit, met means the condition for the awarded level is satisfied; explain unearned components in the reason. Ordinary authorized partial credit is not an exception.
error_origin is none, inherited, current, mixed or unknown, relative to errors affecting the awarded condition. A different valid expression is not an error.
Use met for a satisfied condition with no affecting error; unmet for a known failed condition and zero; uncertain for indeterminate credit with null and review=true.
Use exception for positive credit relying on a source-permitted exception or follow-through. Cite G1, G2, etc from the numbered general rules, or P for this point's own source rule.
For an exception, the reason must identify the relevant error, the source permission, and why the CURRENT operation still qualifies. Mere rule existence is not permission for every deviation.
Separate an erroneous inherited input from a new error introduced while applying the method. A source rule permitting valid deductions from prior erroneous answers does not by itself excuse a new invalid operation.
Identify the origin item/step of EVERY error affecting an exception. A rule for earlier dependent parts does not automatically apply to an earlier line within the same part. If only one inherited value is licensed, keep other current working literal: do not silently repair a separate local error or treat it as another licensed input.
Local f.t. notation is real source authority, but its scope must still support this particular carry-forward. Do not infer an unlimited permission from the abbreviation alone. If the permitted input or current qualifying method is genuinely unresolved, use null/review and explain the source uncertainty rather than assuming either positive credit or zero.
Do not invent a blanket prerequisite saying every preceding method mark must be earned before an accuracy mark; apply only source-supported dependencies and exceptions.
An award-type label alone never proves its condition is satisfied. Compare evidence with both condition and source_text, allowing genuinely equivalent methods rather than literal formula matching.
If you notice a contradiction but cannot establish its allowed treatment from the source, inspect the relevant MS pages; if it remains unresolved use uncertain/null/review.
Do not automatically remove later credit because an earlier point failed: apply the actual dependency and exception rules.
Set review=true for any source-supported exception involving a current or mixed error; those positive awards remain provisional for human source verification.
For non-exceptions rule_ref must be an empty string. Do not output a progress narrative; submit when the full answer book has been considered.`;

export function generalRuleCatalog(frozen) {
  return frozen.artifact.general_instructions.map((rule,index)=>({rule_id:`G${index+1}`,...rule}));
}

function exactKeys(value,keys) {
  if (!value || typeof value!=='object' || Array.isArray(value) ||
      Object.keys(value).length!==keys.length || keys.some(key=>!(key in value))) throw Error('Unexpected compact submission fields');
}

export function checkItemCoverage(raw,frozen) {
  if(!Array.isArray(raw?.items))throw Error('Missing item list');
  const expected=frozen.artifact.items.map(i=>i.item_id),ids=raw.items.map(i=>i?.id);
  if(ids.some(id=>!expected.includes(id))||new Set(ids).size!==ids.length)throw Error('Unknown or duplicate item IDs');
  const missing=expected.filter(id=>!ids.includes(id));
  if(missing.length)throw Object.assign(Error(`Incomplete compact submission; missing items: ${JSON.stringify(missing)}`),{itemIds:missing});
}

export function expandPointEvidence(raw,frozen,student) {
  if (frozen.artifact.version!==2) throw Error('Point evidence protocol requires a structured rubric');
  exactKeys(raw,['items','review_notes']);
  checkItemCoverage(raw,frozen);
  if (!Array.isArray(raw.review_notes) || raw.review_notes.some(note=>typeof note!=='string'||!note.trim())) throw Error('Invalid review notes');
  const seen=new Set();const rules=generalRuleCatalog(frozen);
  const items=raw.items.map(row=>{
    try {
    exactKeys(row,['id','route','review','p']);
    const item=frozen.artifact.items.find(item=>item.item_id===row.id);
    if (!item || seen.has(row.id) || typeof row.review!=='boolean' || !Array.isArray(row.p)) throw Error('Unbound compact item');
    seen.add(row.id);const sourcePages=new Set();
    const points=row.p.map(tuple=>{
      try {
      if (!Array.isArray(tuple)||tuple.length!==8) throw Error('Point row must have eight cells');
      const [point_id,score,evidence,student_pages,relation,error_origin,rule_ref,reason]=tuple;
      const point=item.scoring_points.find(point=>point.point_id===point_id);
      if (!point || !['met','unmet','exception','uncertain'].includes(relation) || !['none','inherited','current','mixed','unknown'].includes(error_origin)) throw Error('Invalid point relation or error origin');
      if (typeof evidence!=='string'||!evidence.trim()||typeof reason!=='string'||!reason.trim()||typeof rule_ref!=='string') throw Error('Missing point evidence, reason or rule ref');
      checkPages(student_pages,student);
      for (const page of point.source_pages) sourcePages.add(page);
      if (relation==='uncertain') {
        if (score!==null || !row.review || rule_ref) throw Error('Uncertain point requires null, review and no asserted exception');
      } else if (relation==='unmet') {
        if (score!==0 || rule_ref) throw Error('Unmet point cannot receive credit');
      } else {
        if (!(typeof score==='number'&&score>0)) throw Error('Positive relation requires positive award');
        if (relation==='met' && (error_origin!=='none'||rule_ref)) throw Error('Contradictory positive award: establish a source exception or mark unmet/uncertain');
        if (relation==='exception') {
          const rule=rule_ref==='P' ? {text:point.condition,source_pages:point.source_pages} : rules.find(rule=>rule.rule_id===rule_ref);
          if (!rule || ['none','unknown'].includes(error_origin)) throw Error('Exception requires an existing source rule and a known error origin');
          for (const page of rule.source_pages) sourcePages.add(page);
          if (['current','mixed'].includes(error_origin)&&!row.review) throw Error('Exception to a current error requires review');
        }
      }
      return {point_id,score,evidence,student_pages:[...student_pages],relation,error_origin,rule_ref,reason};
      } catch(error) {throw Error(`Item ${row.id}, point ${Array.isArray(tuple)?tuple[0]:'unknown'}: ${error.message}`);}
    });
    const result={question_id:item.question_id,item_id:item.item_id,max_score:item.max_score,
      score:points.some(point=>point.score===null)?null:points.reduce((sum,point)=>sum+point.score,0),
      scheme_pages:[...sourcePages].sort((a,b)=>a-b),student_pages:[...new Set(points.flatMap(point=>point.student_pages))].sort((a,b)=>a-b),
      reason:points.map(point=>`${point.point_id}: ${point.reason}`).join('; '),review_required:row.review,
      selected_route:row.route,point_decisions:points};
    validatePointDecisions(result,item,student);
    return result;
    } catch(error) {error.itemIds=[row.id];throw error;}
  });
  return {items,review_notes:[...raw.review_notes]};
}
