import {COMPACT_FEEDBACK_SCHEMA, COMPACT_FEEDBACK_PROMPT, compactFeedbackPacket, expandCompactFeedback} from './compact-feedback.mjs';

// A rendering shortcut for explicit ordinary full-credit attestations, never a scoring rule.
export function conciseFeedbackIds(grade, frozen) {
  if (grade.rubric_hash !== frozen.hash) throw Error('Feedback rubric binding differs');
  if (frozen.artifact.unresolved_notes.length) return [];
  return grade.items.filter(item => {
    const rule = frozen.artifact.items.find(row => row.item_id === item.item_id);
    const route = rule?.routes?.find(row => row.route_id === item.selected_route);
    const points = item.point_decisions ?? [];
    return rule && route && item.score === rule.max_score && item.max_score === rule.max_score &&
      !item.review_required && !rule.uncertainties.length &&
      !(grade.source_issues ?? []).some(issue => issue.item_id === item.item_id) &&
      points.length === route.point_ids.length && new Set(points.map(p => p.point_id)).size === points.length &&
      route.point_ids.every(id => points.some(p => p.point_id === id)) && points.every(point => {
        const source = rule.scoring_points.find(p => p.point_id === point.point_id);
        return source && point.score === source.max_score && point.relation === 'met' &&
          point.error_origin === 'none' && !point.rule_ref &&
          point.reason_encoding === 'explicit_full_credit_attestation' &&
          !point.source_review && !point.source_assessment && !point.exception_review;
      });
  }).map(item => item.item_id);
}

export const FOCUSED_FEEDBACK_SCHEMA = structuredClone(COMPACT_FEEDBACK_SCHEMA);
FOCUSED_FEEDBACK_SCHEMA.properties.items.minItems = 0;
export const FOCUSED_FEEDBACK_PROMPT = COMPACT_FEEDBACK_PROMPT
  .replace("The packet contains every selected point's source condition, original source text, recorded evidence, judgment and exception rule, once each.",
    'The packet keeps complete selected-point details for items needing commentary. Ordinary full-credit items with explicit grading attestations have a concise saved-observation view; their complete immutable ledgers are rendered directly in the report.')
  .replace('For EVERY item exactly once return [item_id, assessment, next_step, review_reason].',
    'For EVERY required_commentary_id exactly once return [item_id, assessment, next_step, review_reason]. For concise_full_credit_ids, the host supplies a clearly labeled fixed explanation and self-check alongside the complete original point table; omit these tuples unless you need to raise a new review concern or give substantive extra advice.')
  .replace('Full-credit items still need a supported observation and a useful verification step.',
    'Use the concise full-credit observations as evidence for the personal summary and strengths, without inventing omitted detail. Do not repeat the fixed explanations.');

export function focusedFeedbackPacket(grade, frozen) {
  const concise = new Set(conciseFeedbackIds(grade, frozen));
  const packet = compactFeedbackPacket(grade, frozen);
  return {...packet, concise_full_credit_ids: [...concise],
    required_commentary_ids: grade.items.filter(item => !concise.has(item.item_id)).map(item => item.item_id),
    items: packet.items.map(item => concise.has(item.id) ? {
      id: item.id, score: item.score, max_score: item.max_score, review: false, criterion: item.criterion,
      saved_judgment: 'Every selected point was explicitly attested as ordinary full credit; full original table is rendered by the host.',
      recorded_observations: item.points.map(row => ({point_id: row[0], evidence: row[5]})),
    } : item)};
}

export function expandFocusedFeedback(raw, grade, frozen) {
  const expanded = expandCompactFeedback(raw, grade);
  const concise = new Set(conciseFeedbackIds(grade, frozen));
  for (const item of grade.items) {
    if (expanded.items.some(row => row.item_id === item.item_id)) continue;
    if (!concise.has(item.item_id)) throw Error(`Missing substantive feedback for required item ${JSON.stringify(item.item_id)}`);
    expanded.items.push({item_id: item.item_id, criterion: '完整评分条件见下方原始逐点依据。',
      assessment: '原评分记录已逐点确认本题满足完整条件；具体作答证据见下表。',
      next_step: '复做时逐点核对下表条件，保留关键步骤，并自行核验结果。',
      review_recommended: false, review_reason: ''});
  }
  return expanded;
}

const object = properties => ({type:'object', properties, required:Object.keys(properties), additionalProperties:false});
const commentary = () => object({
  assessment:{type:'string', minLength:1, maxLength:180, description:'Explain the saved judgment briefly; normally 15-40 Chinese characters.'},
  next_step:{type:'string', minLength:1, maxLength:180, description:'One specific check or practice action; normally 10-30 Chinese characters.'},
  review_reason:{type:'string', maxLength:180, description:'Required nonempty for an existing review or null award, otherwise empty unless raising a new concern.'},
});
// Named fields and required identities are derived solely from the immutable grade.
// Ordinary full-credit items may still receive additional commentary or a review concern.
export function namedFeedbackSchema(grade, frozen) {
  const concise = new Set(conciseFeedbackIds(grade, frozen));
  const schema = object({...COMPACT_FEEDBACK_SCHEMA.properties,
    items:object(Object.fromEntries(grade.items.filter(i=>!concise.has(i.item_id)).map(i=>{
      const row=commentary();
      if(i.review_required || i.score===null) row.properties.review_reason.minLength=1;
      return [i.item_id,row];
    }))),
    additional_items:{type:'array', maxItems:concise.size, items:object({
      item_id:{type:'string', ...(concise.size?{enum:[...concise]}:{})}, ...commentary().properties,
    }), description:'Optional extra feedback for concise_full_credit_ids only. Usually empty; never repeat required items.'},
  });
  return schema;
}
export const NAMED_FEEDBACK_PROMPT = FOCUSED_FEEDBACK_PROMPT.replace(
  'For EVERY required_commentary_id exactly once return [item_id, assessment, next_step, review_reason]. For concise_full_credit_ids, the host supplies a clearly labeled fixed explanation and self-check alongside the complete original point table; omit these tuples unless you need to raise a new review concern or give substantive extra advice.',
  'The submit tool schema lists every required item as a mandatory key in items. Return items as an object keyed by those exact IDs; each value has named fields assessment, next_step, review_reason. Never return positional tuples, an empty array, or omit a required key. For concise_full_credit_ids the host renders labeled fixed commentary and the full point table; additional_items is normally [], but may contain named item_id/assessment/next_step/review_reason records for substantive extra advice or a new review concern. Every field must obey its own length limit. Prose fields must contain an actual explanation, never serialized field fragments. When no review is needed, review_reason is the empty string, not a fragment of the next field.');

export function expandNamedFeedback(raw, grade, frozen) {
  if(!raw || Object.keys(raw).sort().join(',')!=='additional_items,items,priorities,strengths,summary' ||
      !raw.items || typeof raw.items!=='object' || Array.isArray(raw.items) || !Array.isArray(raw.additional_items)) throw Error('Invalid named feedback fields');
  const concise=new Set(conciseFeedbackIds(grade,frozen));
  const required=grade.items.filter(i=>!concise.has(i.item_id)).map(i=>i.item_id);
  const missing=required.filter(id=>!Object.hasOwn(raw.items,id));
  const unknown=Object.keys(raw.items).filter(id=>!required.includes(id));
  if(missing.length || unknown.length) throw Error(`Feedback identities: missing=${JSON.stringify(missing)}, unexpected=${JSON.stringify(unknown)}`);
  const tuple=(id,row,extra=false)=>{
    const keys=extra?['item_id','assessment','next_step','review_reason']:['assessment','next_step','review_reason'];
    if(!row || Array.isArray(row) || Object.keys(row).sort().join(',')!==keys.sort().join(',')) throw Error(`Invalid feedback fields for ${JSON.stringify(id)}`);
    return [id,row.assessment,row.next_step,row.review_reason];
  };
  const seen=new Set();
  const extras=raw.additional_items.map(row=>{
    if(!concise.has(row?.item_id) || seen.has(row.item_id)) throw Error('Unbound or duplicate additional feedback item');
    seen.add(row.item_id);return tuple(row.item_id,row,true);
  });
  return expandFocusedFeedback({summary:raw.summary,strengths:raw.strengths,priorities:raw.priorities,
    items:[...required.map(id=>tuple(id,raw.items[id])),...extras]},grade,frozen);
}
