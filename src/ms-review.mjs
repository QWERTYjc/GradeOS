import { digest } from './core.mjs';
import { objectSchema, ITEM_SCHEMA, GENERAL_SCHEMA, freezeRubric, checkPages } from './rubric-contract.mjs';

const str = { type: 'string', minLength: 1 };
const pages = { type: 'array', minItems: 1, uniqueItems: true, items: { type: 'integer', minimum: 1 } };
const nullable = schema => ({ anyOf: [schema, { type: 'null' }] });
export const MS_REVIEW_SCHEMA = objectSchema({
  summary: str,
  item_checks: { type: 'array', minItems: 1, items: objectSchema({
    item_id: str, verdict: { type: 'string', enum: ['verified','corrected','uncertain'] }, source_pages: pages, note: str,
  }) },
  revised_items: { type: 'array', items: ITEM_SCHEMA },
  removed_items: { type: 'array', items: objectSchema({ item_id: str, reason: str, source_pages: pages }) },
  general_instructions: nullable(GENERAL_SCHEMA),
  unresolved_notes: nullable({ type: 'array', items: str, uniqueItems: true }),
});
export const MS_REVIEW_PROMPT = `After prepare_ms_review returns, review your latest staged candidate in this SAME conversation using the original MS images and source-reading history already present.
Keep the existing context; do not request the entire MS again or rewrite the complete candidate. Reopen only specific pages needed to resolve a concrete source ambiguity. You have no student answers or reference scores.
Check every source page including general instructions, continuations and alternative routes. Reconstruct the item inventory from the source;
look for omissions, invented rules, mistranscribed formulae, scope errors, lost dependencies, follow-through, partial credit and equivalent methods.
Check each point's source_text, value, allowed_awards and condition against the image; never authorize intermediate awards absent source support. Alternative routes must not be added together.
Check award scope in BOTH directions, not only route totals: every necessary clause in condition must be authorized for that specific award, and every explicit qualification of that award must survive. A later worked step is not automatically required for an earlier method/choice mark. Preserve explicit joint conditions, linked later notes and cross-line/page scopes; do not infer the boundary from spacing or the next mark label alone. Correct unsupported added clauses and missing clauses, or retain uncertainty when the source does not resolve the boundary.
Each route lists a complete path to the item's source maximum; shared points may appear in multiple routes.
depends_on expresses only unconditional full-credit prerequisites within that route; conditional dependencies belong in condition.
Do not force source semantics into a guessed point split. Keep uncertainty and require source images where spatial or ambiguous information matters.
Return one check for EVERY final item. Use revised_items only for complete replacements or missing new items; use removed_items for source-proven spurious items.
All revised items need a corrected or uncertain check. For unchanged verified items keep the note short. general_instructions and unresolved_notes are null if unchanged.
Use uncertain for unresolved source meaning and explain it; preserve a faithful source transcription rather than inventing a rule. Keep an item-specific concern in that item only; global unresolved_notes are for genuinely global or unlocated concerns. Before declaring a source expression inconsistent, check algebraic equivalence and the exact variable being differentiated or transformed; state the concrete contradiction, not an unchecked suspicion.
Submit one complete source-bound review with submit_ms_review in a subsequent model turn after prepare_ms_review. This freezes the reviewed rules before any student dispatch.
Be concise: preserve necessary mathematical conditions, omit repeated prose. This is coordinator self-review, not an independent or human verification.`;

export function applyMSReview(raw, candidate, scheme, seen, sourceInventory) {
  if (candidate.artifact.version !== 2) throw Error('MS review requires point-structured rules');
  if (!scheme.pages.every(page => seen.has(page.page))) throw Error('MS review lacks complete image delivery');
  const artifact = structuredClone(candidate.artifact); const original = new Map(artifact.items.map(item => [item.item_id,item]));
  const items = new Map(original); const changed = new Set(); const removed = new Set();
  for (const item of raw.revised_items) {
    if (changed.has(item.item_id)) throw Error('Duplicate MS revision');
    changed.add(item.item_id); items.set(item.item_id,structuredClone(item));
  }
  for (const row of raw.removed_items) {
    if (!original.has(row.item_id) || removed.has(row.item_id) || changed.has(row.item_id) || !row.reason?.trim()) throw Error('Invalid MS removal');
    checkPages(row.source_pages,scheme); removed.add(row.item_id); items.delete(row.item_id);
  }
  if (raw.general_instructions !== null) artifact.general_instructions = structuredClone(raw.general_instructions);
  if (raw.unresolved_notes !== null) artifact.unresolved_notes = structuredClone(raw.unresolved_notes);
  if (raw.item_checks.length !== items.size || !raw.summary?.trim()) throw Error('Incomplete source item checks');
  const checked = new Set();
  for (const check of raw.item_checks) {
    const item = items.get(check.item_id);
    if (!item || checked.has(check.item_id) || !check.note?.trim()) throw Error('Invalid source item check');
    checked.add(check.item_id); checkPages(check.source_pages,scheme);
    if (item.source_pages.some(page => !check.source_pages.includes(page))) throw Error('Review omits item source pages');
    if (!['verified','corrected','uncertain'].includes(check.verdict) || (changed.has(check.item_id) && check.verdict === 'verified') ||
        (!changed.has(check.item_id) && check.verdict === 'corrected')) throw Error('Review verdict differs from revision');
    if (check.verdict === 'uncertain') item.uncertainties = [...new Set([...item.uncertainties,check.note])];
    if (check.verdict === 'verified' && item.uncertainties.length) throw Error('Unresolved item cannot be verified');
  }
  if (sourceInventory !== undefined) artifact.source_inventory = structuredClone(sourceInventory);
  artifact.items = [...items.values()];
  const frozen = freezeRubric(artifact,scheme,seen);
  const status = frozen.artifact.unresolved_notes.length || frozen.artifact.items.some(item => item.uncertainties.length) ? 'review_required' : 'verified';
  const review = { ...structuredClone(raw), version: 1, candidate_hash: candidate.hash,
    final_rubric_hash: frozen.hash, source_sha256: scheme.sha256,
    source_image_pages_delivered: [...seen].sort((a,b) => a-b), status,
    review_mode: 'coordinator', authority: 'Coordinator source-fidelity self-review in the compilation conversation; no student answers or external score labels' };
  frozen.verification = { candidate_hash: candidate.hash, final_rubric_hash: frozen.hash, review_hash: digest(review),
    source_sha256: scheme.sha256, status, review_mode: 'coordinator' };
  return { frozen, review };
}

