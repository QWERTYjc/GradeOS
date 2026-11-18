// Convert one complete schema-constrained response into the same Pi tool input.
// The tool still validates its arguments, evidence, routes and award bounds.
export function configureFlashSubmission(payload) {
  const submission = payload.tools.find(tool => tool.function.name === 'submit_grading');
  const schema = structuredClone(submission.function.parameters);
  // A later source issue can invalidate a short attestation for any point.
  // Request an explicit reason up front without changing the model's award.
  const reason = schema.$defs?.decision?.properties?.r;
  if (reason) Object.assign(reason, {minLength:2, description:'Give the specific scoring reason in words, including for full credit. Never use the equals-sign abbreviation.'});
  payload.response_format = {type:'json_schema', json_schema:{
    name:'submit_grading', strict:true, schema,
  }};
  delete payload.tools;
  delete payload.tool_choice;
  payload.messages.push({role:'user', content:'Return exactly the submit_grading arguments as one JSON object following the supplied response schema. For each point with no visible evidence use its absent-page object. Include every observation slot, including unselected alternative routes. Use a specific written scoring reason in every r field. Do not use the equals-sign abbreviation or invent evidence.'});
}

export function flashSubmissionResult(upstream, saveText) {
  const result = upstream.result().then(async message => {
    if (message.stopReason !== 'stop') return message;
    const blocks = message.content.filter(part=>part.type !== 'thinking');
    if (blocks.length !== 1 || blocks[0].type !== 'text') return message;
    const text = blocks[0].text;
    await saveText(text);
    let args;
    try { args = JSON.parse(text); } catch { return message; }
    if (!args || Object.keys(args).sort().join(',') !== 'items,observations,review_notes,source_issues') return message;
    const keys = value => Array.from(value.matchAll(/"[^"\\]*(?:\\[\s\S][^"\\]*)*"(\s*:)?/g)).filter(match => match[1]).length;
    if (keys(text) !== keys(JSON.stringify(args))) return message;
    const call = {type:'toolCall',name:'submit_grading',id:'flash_submit',arguments:args};
    return {...message, stopReason:'toolUse', content:message.content.map(part=>part===blocks[0]?call:part)};
  });
  return {[Symbol.asyncIterator]:()=>upstream[Symbol.asyncIterator](), result:()=>result};
}
