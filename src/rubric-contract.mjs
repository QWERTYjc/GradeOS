import { digest, SUBMIT_SCHEMA } from './core.mjs';

export const MS_SOURCE_RELATIONS = `Source layout carries rules: trace brackets, dashed links, merged cells and continuation notes to the exact steps and award they qualify; do not attach a remark to the nearest answer by proximity alone.
Each point requires only the act and qualifications the source assigns to THAT award. Subsequent demonstration, calculation, limits or conclusions do not become requirements of an earlier method/choice point merely because they follow it, precede the next mark label, or are mathematically needed later. Trace the actual award span, not just the next labelled row.
Conversely, retain explicit joint requirements and later notes qualifying that award, including brackets or merged cells spanning several lines/pages. Do not mechanically stop at the first line or mark label. Ambiguous scope stays uncertain; proximity alone cannot prove either independence or conjunction.
Preserve the linked steps AND their qualifying remark in source_text. An either/any-one permission is OR only within that award's condition: keep every permitted alternative, award the shared point once, and leave neighboring independent answer/method points unchanged. A both/all requirement remains AND; a choice of route is not permission to combine credits across routes.
Keep shared points under the same point_id across routes. Do not infer depends_on from row order or membership in a shared group; only source-supported unconditional prerequisites belong there.
If the link, scope or allocation cannot be resolved from the source, retain the ambiguity in uncertainties, set requires_source_image with the affected pages and a reason, and request review instead of inventing a narrower or broader rule.`;

export const objectSchema = properties => ({ type: 'object', properties, required: Object.keys(properties), additionalProperties: false });
const str = { type: 'string', minLength: 1 };
const strings = { type: 'array', items: str, uniqueItems: true };
const pages = { type: 'array', items: { type: 'integer', minimum: 1 }, minItems: 1, uniqueItems: true };
export const GENERAL_SCHEMA = { type: 'array', items: objectSchema({ text: str, source_pages: pages }) };
export const ITEM_SCHEMA = objectSchema({
  question_id: str, item_id: str, max_score: { type: 'number', exclusiveMinimum: 0 },
  criteria: str, source_pages: pages, related_item_ids: strings,
  requires_source_image: { type: 'boolean' }, image_reason: { type: 'string' }, uncertainties: strings,
  scoring_points: { type: 'array', minItems: 1, items: objectSchema({
    point_id: str, max_score: { type: 'number', exclusiveMinimum: 0 }, allowed_awards: {type:'array',minItems:2,uniqueItems:true,items:{type:'number',minimum:0}}, award_type: str,
    condition: str, depends_on: strings, source_text: str, source_pages: pages,
  }) },
  routes: { type: 'array', minItems: 1, items: objectSchema({ route_id: str, point_ids: { ...strings, minItems: 1 }, description: str }) },
});
export const RUBRIC_SCHEMA = objectSchema({ general_instructions: GENERAL_SCHEMA,
  items: { type: 'array', minItems: 1, items: ITEM_SCHEMA }, unresolved_notes: strings });

// Transport aliases only: canonical persistence and every source validation stay unchanged.
const itemFields = {question_id:'q',item_id:'id',max_score:'max',criteria:'criteria',source_pages:'pages',related_item_ids:'related',requires_source_image:'visual',image_reason:'why',uncertainties:'uncertainties',scoring_points:'points',routes:'routes'};
const pointFields = {point_id:'id',max_score:'max',allowed_awards:'awards',award_type:'type',condition:'condition',depends_on:'depends',source_text:'source',source_pages:'pages'};
const routeFields = {route_id:'id',point_ids:'points',description:'description'};
const aliasSchema = (schema,fields) => objectSchema(Object.fromEntries(Object.entries(fields).map(([key,alias])=>[alias,schema.properties[key]])));
const compactItem = aliasSchema(ITEM_SCHEMA,itemFields);
compactItem.properties.points={...ITEM_SCHEMA.properties.scoring_points,items:aliasSchema(ITEM_SCHEMA.properties.scoring_points.items,pointFields)};
compactItem.properties.points.items.properties.condition={anyOf:[{type:"null"},str],description:"Prefer null to reference the complete source criterion verbatim; write a separate condition only when needed to express its source-supported scope. Never omit a qualification to enable this reference."};
compactItem.properties.routes={...ITEM_SCHEMA.properties.routes,items:aliasSchema(ITEM_SCHEMA.properties.routes.items,routeFields)};
export const MS_WRITE_SCHEMA = objectSchema({items:{type:'array',minItems:1,items:compactItem}});
export const MS_WRITE_PROMPT = `write_rubric_items uses short keys only to reduce repeated field names; the host restores the full canonical rubric without inferring values.
Item keys: q=printed parent question identifier, id=separately scored item identifier, max=max_score, criteria, pages=source_pages, related=related_item_ids, visual=requires_source_image, why=image_reason, uncertainties, points=scoring_points, routes. Keep the parent and subpart identities distinct when the source distinguishes them.
Point keys: id=point_id, max=max_score, awards=allowed_awards, type=award_type, condition, depends=depends_on, source=source_text, pages=source_pages. Write the faithful award-bearing source and its linked qualifications once. Prefer condition=null when that source already expresses the complete criterion: the host copies it verbatim. Do not also paraphrase the same criterion merely to fill both fields. This reference preserves method, justification, alternatives, qualifications and follow-through; it never means missing or uncertain. When source alone does not express the full scoped rule, retain a complete separate condition. Never shorten the source, drop a required step or merge a later award to make this reference possible.
Route keys: id=route_id, points=point_ids, description. All keys are required, including explicit empty arrays/strings and false. Keep the entire source condition, faithful original wording, page ownership, allowed awards, dependencies, alternatives and uncertainty. Do not substitute an answer summary. Review corrections use the full field names in their own schema.`;
function expandFields(value,fields) {
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==Object.keys(fields).length||Object.values(fields).some(alias=>!Object.hasOwn(value,alias)))throw Error('Incomplete or unknown MS write fields');
  return Object.fromEntries(Object.entries(fields).map(([key,alias])=>[key,structuredClone(value[alias])]));
}
export function expandMSItems(raw) {
  if(!raw||Object.keys(raw).length!==1||!Array.isArray(raw.items)||!raw.items.length)throw Error('Invalid MS write batch');
  return raw.items.map(value=>{
    const item=expandFields(value,itemFields);
    if(!Array.isArray(item.scoring_points)||!Array.isArray(item.routes))throw Error('Invalid MS point or route lists');
    item.scoring_points=item.scoring_points.map(point=>{
      const expanded=expandFields(point,pointFields);
      if(expanded.condition===null)expanded.condition=expanded.source_text;
      return expanded;
    });
    item.routes=item.routes.map(route=>expandFields(route,routeFields));
    return item;
  });
}

export function checkPages(numbers, document) {
  if (!Array.isArray(numbers) || !numbers.length || new Set(numbers).size !== numbers.length ||
      numbers.some(n => !Number.isInteger(n) || !document.pages.some(p => p.page === n))) throw Error('Invalid source pages');
}
const nonempty = value => typeof value === 'string' && value.trim();
const unique = values => Array.isArray(values) && values.every(nonempty) && new Set(values).size === values.length;
const sameNumber = (a, b) => Math.abs(a - b) < 1e-9;

// Each leaf is anchored to the first page on which it is independently scored.
// An empty row accounts for instructions, blank pages, or continuation only.
export function sourceItemOwners(inventory, allowedPages) {
  if (!Array.isArray(inventory)) throw Error('Missing printed item inventory');
  const owners = new Map(), pages = new Set();
  for (const {page, item_ids} of inventory) {
    if (!allowedPages.has(page) || pages.has(page) || !Array.isArray(item_ids))
      throw Error('Inventory pages must be distinct inspected MS pages');
    pages.add(page);
    for (const id of item_ids) {
      if (typeof id !== 'string' || !id.trim() || id !== id.trim() || owners.has(id))
        throw Error('Invalid or duplicate independently scored item: ' + id);
      owners.set(id, page);
    }
  }
  return owners;
}

export function checkSourceItem(item, owners) {
  if (!owners.has(item.item_id)) throw Error('Item is absent from the printed leaf inventory: ' + item.item_id);
  if (!item.source_pages.includes(owners.get(item.item_id)))
    throw Error('Item must cite its printed starting page: ' + item.item_id);
}

export function freezeRubric(raw, scheme, seen) {
  if (!scheme.pages.every(p => seen.has(p.page))) throw Error('Read all MS pages before publishing');
  const copy = structuredClone(raw);
  if (!copy.items?.length) throw Error('No rubric items');
  if (copy.source_inventory !== undefined) {
    const pages = new Set(scheme.pages.map(p => p.page));
    const owners = sourceItemOwners(copy.source_inventory, pages);
    const unread = [...pages].filter(page => !copy.source_inventory.some(row => row.page === page));
    if (unread.length) throw Error('Record the printed item inventory for MS pages: ' + unread.join(', '));
    for (const item of copy.items) checkSourceItem(item, owners);
    const staged = new Set(copy.items.map(item => item.item_id));
    const missing = [...owners.keys()].filter(id => !staged.has(id));
    if (missing.length) throw Error('Missing independently scored printed items: ' + missing.join(', '));
  }
  const ids = new Set();
  const pointMode = copy.version === 2 || copy.items.some(item => 'scoring_points' in item);
  for (const item of copy.items) {
    if (!nonempty(item.item_id) || !nonempty(item.question_id) || ids.has(item.item_id)) throw Error('Invalid or duplicate rubric identity');
    ids.add(item.item_id);
    if (!Number.isFinite(item.max_score) || item.max_score <= 0 || !nonempty(item.criteria)) throw Error('Invalid rubric award');
    checkPages(item.source_pages, scheme);
    if (item.requires_source_image && !nonempty(item.image_reason)) throw Error('Missing visual requirement reason');
    if (!unique(item.related_item_ids) || !unique(item.uncertainties)) throw Error('Invalid rubric relations or uncertainties');
    if (pointMode) validatePoints(item, scheme);
  }
  for (const item of copy.items) if (item.related_item_ids.some(id => !ids.has(id))) throw Error('Unbound related rubric item');
  for (const rule of copy.general_instructions) { if (!nonempty(rule.text)) throw Error('Empty general rule'); checkPages(rule.source_pages, scheme); }
  if (!unique(copy.unresolved_notes)) throw Error('Invalid unresolved notes');
  const artifact = { ...copy, version: pointMode ? 2 : 1, source_sha256: scheme.sha256 };
  return { artifact, hash: digest(artifact) };
}

function validatePoints(item, scheme) {
  if (!Array.isArray(item.scoring_points) || !item.scoring_points.length || !Array.isArray(item.routes) || !item.routes.length) throw Error('Missing scoring points or routes');
  const points = new Map();
  for (const p of item.scoring_points) {
    if (![p.point_id,p.award_type,p.condition,p.source_text].every(nonempty) || points.has(p.point_id) ||
        !Number.isFinite(p.max_score) || p.max_score <= 0 || !unique(p.depends_on)) throw Error('Invalid scoring point');
    if (!Array.isArray(p.allowed_awards) || new Set(p.allowed_awards).size !== p.allowed_awards.length || !p.allowed_awards.includes(0) || !p.allowed_awards.includes(p.max_score) || p.allowed_awards.some(value => !Number.isFinite(value) || value < 0 || value > p.max_score)) throw Error('Invalid source-authorized point awards');
    checkPages(p.source_pages, scheme);
    if (p.source_pages.some(page => !item.source_pages.includes(page))) throw Error('Point source outside item');
    if (p.award_levels !== undefined) {
      const levels = p.award_levels;
      if (!Array.isArray(levels) || !levels.length ||
          !unique(levels.map(level => level.label)) || new Set(levels.map(level => level.score)).size !== levels.length ||
          levels.some(level => !p.allowed_awards.includes(level.score) || !p.source_pages.includes(level.source_page) ||
            !nonempty(level.criterion))) throw Error('Invalid source-bound award levels');
    }
    points.set(p.point_id, p);
  }
  const routes = new Set(); const covered = new Set();
  for (const route of item.routes) {
    if (!nonempty(route.route_id) || routes.has(route.route_id) || !nonempty(route.description) || !unique(route.point_ids) || !route.point_ids.length) throw Error('Invalid scoring route');
    routes.add(route.route_id);
    if (route.point_ids.some(id => !points.has(id))) throw Error('Unknown route point');
    if (!sameNumber(route.point_ids.reduce((sum,id) => sum + points.get(id).max_score, 0), item.max_score)) throw Error('Each complete alternative route must equal the item maximum');
    for (const id of route.point_ids) {
      covered.add(id);
      if (points.get(id).depends_on.some(dep => dep === id || !route.point_ids.includes(dep))) throw Error('Dependency outside route');
    }
  }
  if (covered.size !== points.size) throw Error('Unused scoring point');
  const visited = new Set(); const visiting = new Set();
  const visit = id => {
    if (visiting.has(id)) throw Error('Cyclic point dependency');
    if (visited.has(id)) return;
    visiting.add(id); for (const dep of points.get(id).depends_on) visit(dep);
    visiting.delete(id); visited.add(id);
  };
  for (const id of points.keys()) visit(id);
}

export function validateFrozenRubric(frozen, scheme) {
  if (!frozen?.artifact || ![1,2].includes(frozen.artifact.version) || frozen.artifact.source_sha256 !== scheme.sha256 ||
      frozen.hash !== digest(frozen.artifact)) throw Error('Frozen rubric integrity or MS source mismatch');
  const checked = freezeRubric(frozen.artifact, scheme, new Set(scheme.pages.map(p => p.page)));
  if (checked.hash !== frozen.hash) throw Error('Frozen rubric changed during validation');
  if (frozen.artifact.version === 2 && !frozen.verification) throw Error('Point-structured MS requires source verification before reuse');
  if (frozen.verification && (frozen.verification.final_rubric_hash !== frozen.hash ||
      frozen.verification.source_sha256 !== scheme.sha256 || !/^[a-f0-9]{64}$/.test(frozen.verification.review_hash))) throw Error('MS verification binding mismatch');
  return structuredClone(frozen);
}

export const POINT_SUBMIT_SCHEMA = structuredClone(SUBMIT_SCHEMA);
Object.assign(POINT_SUBMIT_SCHEMA.properties.items.items.properties, {
  selected_route: str,
  point_decisions: { type: 'array', minItems: 1, items: objectSchema({
    point_id: str, score: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'null' }] },
    evidence: str, student_pages: pages, reason: str,
  }) },
});
POINT_SUBMIT_SCHEMA.properties.items.items.required.push('selected_route', 'point_decisions');

// Lossless presentation only: the frozen artifact remains the scoring authority.
export function rubricPromptPresentation(artifact,{reuseItemDefaults=false}={}){
  const owners=reuseItemDefaults?new Map(artifact.items.flatMap(item=>item.scoring_points.map(point=>[point,item]))):null;
  const items=reuseItemDefaults?new Set(artifact.items):null;
  const guide='Omitted source_text is identical to condition. Omitted depends_on, related_item_ids and uncertainties are empty arrays. All nonempty source conditions, exceptions and dependencies are retained.';
  const defaults=reuseItemDefaults?' Omitted point source_pages are the containing item source_pages; omitted point max_score is the largest allowed_awards value. Omitted requires_source_image is false and omitted image_reason is empty.':'';
  const json=JSON.stringify(artifact,function(key,value){
      if(key==='source_text'&&value===this.condition)return undefined;
      if(['depends_on','related_item_ids','uncertainties'].includes(key)&&Array.isArray(value)&&value.length===0)return undefined;
      if(key==='max_score'&&owners?.has(this)&&value===Math.max(...this.allowed_awards))return undefined;
      if(key==='source_pages'){
        const shared=owners?.get(this)?.source_pages;
        if(shared&&Array.isArray(value)&&shared.length===value.length&&shared.every((page,index)=>page===value[index]))return undefined;
      }
      if(items?.has(this)&&((key==='requires_source_image'&&value===false)||(key==='image_reason'&&value==='')))return undefined;
      return value;
    });
  return {guide:guide+defaults,json};
}

export function studentRubricText(artifact,options){
  const {guide,json}=rubricPromptPresentation(artifact,options);
  return guide+'\n'+json;
}

export function validatePointDecisions(row, item, student) {
  const route = item.routes.find(r => r.route_id === row.selected_route);
  if (!route || !Array.isArray(row.point_decisions) || row.point_decisions.length !== route.point_ids.length) throw Error('Select one complete scoring route');
  const decisions = new Map(); const points = new Map(item.scoring_points.map(p => [p.point_id,p]));
  for (const d of row.point_decisions) {
    const p = points.get(d.point_id);
    if (!p || !route.point_ids.includes(d.point_id) || decisions.has(d.point_id)) throw Error('Unknown, duplicate or mixed-route decision');
    if (d.score !== null && (!Number.isFinite(d.score) || !p.allowed_awards.includes(d.score))) throw Error('Invalid point award');
    if (!nonempty(d.evidence) || !nonempty(d.reason)) throw Error('Missing point evidence or reason');
    checkPages(d.student_pages, student);
    if (d.student_pages.some(page => !row.student_pages.includes(page))) throw Error('Point evidence outside item citations');
    decisions.set(d.point_id,d);
  }
  for (const d of decisions.values()) if (d.score > 0 && points.get(d.point_id).depends_on.some(id => decisions.get(id)?.score !== points.get(id).max_score)) throw Error('Unmet unconditional point dependency');
  const unknown = [...decisions.values()].some(d => d.score === null);
  if (unknown ? row.score !== null || !row.review_required : !sameNumber(row.score ?? NaN, [...decisions.values()].reduce((sum,d) => sum+d.score, 0))) throw Error('Item award must equal its selected point ledger; unknown remains unknown');
}
