// The wire ceiling and worst-case reservation share the same native/context/
// financial bound. No phase or correction-specific token quota is imposed.
export function outputBudget({model,payload,inputTokens,prices,available,requestedLimit=null}) {
  const positive=n=>Number.isSafeInteger(n)&&n>0;
  if(!positive(model.maxTokens)||!positive(model.contextWindow)||!Number.isSafeInteger(inputTokens)||inputTokens<0)
    throw Error('Missing model capacity or input bound');
  if(!Number.isFinite(prices.input)||prices.input<0||!Number.isFinite(prices.output)||prices.output<0||
      (prices.cacheWrite!==undefined&&(!Number.isFinite(prices.cacheWrite)||prices.cacheWrite<0)))throw Error('Invalid model prices');
  if(!Number.isFinite(available)||available<0||(requestedLimit!==null&&!positive(requestedLimit)))throw Error('Invalid output budget');
  if(payload.max_tokens!==undefined&&payload.max_completion_tokens!==undefined)throw Error('Conflicting native output ceilings');
  const native=Math.min(model.maxTokens,...['max_tokens','max_completion_tokens'].filter(k=>payload[k]!==undefined).map(k=>{
    if(!positive(payload[k]))throw Error('Invalid native output ceiling');return payload[k];
  }),requestedLimit??Infinity);
  const input_usd=inputTokens*Math.max(prices.input,prices.cacheWrite??0)/1e6;
  const affordable=prices.output===0?Infinity:Math.floor((available-input_usd)*1e6/prices.output);
  let tokens=Math.min(native,model.contextWindow-inputTokens-1,affordable);
  while(tokens>0&&input_usd+tokens*prices.output/1e6>available)tokens--;
  if(model.contextWindow-inputTokens-1<1)throw Error('Model context leaves no output allowance');
  if(tokens<1||input_usd>available)throw Object.assign(new Error('Budget reservation limit: no funded output allowance'),{code:'OUTPUT_BUDGET_LIMIT'});
  const key=Object.hasOwn(payload,'max_completion_tokens')?'max_completion_tokens':'max_tokens';
  payload[key]=tokens;
  return {tokens,native_tokens:native,context_tokens:model.contextWindow-inputTokens-1,affordable_tokens:Number.isFinite(affordable)?affordable:null,
    reservation:{input_usd,output_usd:tokens*prices.output/1e6}};
}
