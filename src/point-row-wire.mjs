// Each uniform row binds one observation and any decision to a single point
// ID, without expanding the provider schema for every point in a whole book.
const object = properties => ({ type:'object', properties, required:Object.keys(properties), additionalProperties:false });
const list = items => ({ type:'array', items, minItems:1 });
const id = { type:'string' };
export const VISUAL_READBACK = 'Before submission, make a second pass over the images for every mixed-credit or uncertain item. Re-read each score-changing stroke in its own line, column, and neighboring work. Check the ink behind both awards and deductions. Apply each criterion to the step it actually assesses, including a valid earlier step or an equivalent written form. Check the complete relation before accepting an equivalent form, including scale, signs, and any quantity carried forward. If competing readings still change the award, use the existing uncertainty state. Keep the final submission concise.';
export const FULL_CREDIT_READBACK = 'Give each item receiving full credit the same brief check. Match each positive award to the specific step or result it assesses. When a derivation contains multiple equalities, check the marked transition itself, including any multiplier, divisor, offset, sign, or operative assumption. Separate genuinely equivalent work from a change in the relation. Carry a preceding result forward only to the extent the source authorizes. A correct setup or plausible final result does not establish an intervening step. Keep independently met criteria, and use uncertainty when the supplied evidence cannot decide an award.';

export function gradingPointRowMode(modelId, provider, overviewMaxSide) {
  if (provider?.allow_fallbacks !== false || provider.only?.length !== 1) return null;
  const [endpoint] = provider.only;
  if (endpoint === 'google-vertex/global') return 'all';
  return endpoint === 'openai' && overviewMaxSide != null &&
    ['openai/gpt-6.1-terra','openai/gpt-6-luna'].includes(modelId) ? 'selected' : null;
}

export function configurePointRows(payload, selectedOnly = false) {
  const submission = payload.tools.find(tool => tool.function.name === 'submit_grading').function;
  const canonical = submission.parameters;
  if (!canonical.$defs?.observedPoint) throw Error('Point rows require the named evidence ledger');
  const { review_notes, source_issues } = canonical.properties;
  const { observedPoint, decision } = canonical.$defs;
  const locationField = observedPoint.anyOf?.[0]?.properties?.v ? ', plus v for the result-location field' : '';
  submission.parameters = object({
    items:list(object({ id, route:id, review:{type:'boolean'}, p:list(object({
      id, o:observedPoint, d:selectedOnly ? decision : {anyOf:[decision,{type:'null'}]},
    })) })),
    review_notes,
    source_issues,
  });
  const roster = selectedOnly ? Object.fromEntries(Object.entries(canonical.properties.items.properties).map(([item, schema]) =>
    [item, Object.fromEntries((schema.anyOf ?? [schema]).map(({properties}) =>
      [properties.route.enum[0], Object.keys(properties.p.properties)]))])) : null;
  payload.messages.push({role:'user',content:`Use the submit_grading schema supplied by the API. Submit each rubric item once as {id, route, review, p} with exact IDs. Each scoring point has one {id, o, d} row. Write o first using the observed p, t and l when requested${locationField}, or absent for checked absence. ${selectedOnly
    ? 'Return precisely the points of one route per item. Each d is {r, j, s}. Never add points from an unselected route. Here is the complete inventory of item IDs, route IDs and each route’s exact point IDs: ' + JSON.stringify(roster)
    : 'For each selected-route point d is {r, j, s}; d is null for all other points. Record every observation slot including unselected routes.'} Apply the same evidence and scoring rules. Use r="=" for ordinary unambiguous full credit where allowed, and write the specific reason only where required.`});
}

function exactFields(value, fields) {
  return value && !Array.isArray(value) && typeof value === 'object' &&
    Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}

function byId(rows, fields, read) {
  if (!Array.isArray(rows) || !rows.length) throw Error('Missing ledger rows');
  const values = Object.create(null);
  for (const row of rows) {
    if (!exactFields(row, ['id', ...fields]) || typeof row.id !== 'string' || !row.id || Object.hasOwn(values, row.id))
      throw Error('Invalid or duplicate ledger ID');
    values[row.id] = read(row);
  }
  return values;
}

export function restorePointRows(upstream, saveArguments) {
  const result = upstream.result().then(async message => {
    if (message.stopReason !== 'toolUse') return message;
    const calls = message.content.filter(part => part.type === 'toolCall');
    if (calls.length !== 1) return message;
    const [call] = calls;
    if (call.name !== 'submit_grading' || call.argumentsError) return message;
    const raw = call.arguments;
    await saveArguments(raw);
    try {
      if (!exactFields(raw, ['items','review_notes','source_issues'])) return message;
      const entries = byId(raw.items, ['route','review','p'], ({route,review,p}) =>
        ({route,review,points:byId(p, ['o','d'], point => point)}));
      const observations = Object.create(null), items = Object.create(null);
      for (const [id, {route,review,points}] of Object.entries(entries)) {
        const evidence = Object.create(null), decisions = Object.create(null);
        for (const [pointId, {o,d}] of Object.entries(points)) {
          evidence[pointId] = o;
          if (d !== null) decisions[pointId] = d;
        }
        observations[id] = evidence;
        items[id] = {route,review,p:decisions};
      }
      const args = {observations,items,review_notes:raw.review_notes,source_issues:raw.source_issues};
      return {...message,content:message.content.map(part => part === call ? {...call,arguments:args} : part)};
    } catch {
      // Let Pi reject the original shape; never coalesce invalid rows.
      return message;
    }
  });
  return {[Symbol.asyncIterator]:()=>upstream[Symbol.asyncIterator](),result:()=>result};
}
