// Pi 1.5.2 predates these models. Reuse its OpenRouter serializer and agent loop.
// Source: public /models/google/gemini-4-{carbon,hydrogen}/endpoints, 2026-11-17.
export const HYDROGEN_ID = 'google/gemini-4-hydrogen';
export const CARBON_ID = 'google/gemini-4-carbon';
export const DEFAULT_MAIN_MODEL_ID = 'openai/gpt-6.1-terra';
export const DEFAULT_WORKER_MODEL_ID = 'openai/gpt-6-luna';
const googleModels = {
  [HYDROGEN_ID]: {name:'Hydrogen',cost:{input:1.5,output:7.5,cacheRead:0.075,cacheWrite:0.0833333333333333}},
  [CARBON_ID]: {name:'Carbon',cost:{input:2,output:10,cacheRead:0.1,cacheWrite:0.1875}},
};
const SOL_62_ID = 'openai/gpt-6.2-sol';
const openaiIds = [SOL_62_ID, 'openai/gpt-6.1-terra', 'openai/gpt-6.1-sol', 'openai/gpt-6-luna'];

export function experimentModel(models, id) {
  if (openaiIds.includes(id)) {
    const model = models.getModel('openrouter', id);
    // The pinned Pi catalog predates 6.2. The standard OpenRouter endpoint
    // advertises the same context, output limit and price tiers as 6.1 Sol.
    if (!model && id === SOL_62_ID) {
      const sol = models.getModel('openrouter', 'openai/gpt-6.1-sol');
      if (sol) return {...sol, id, name: 'OpenAI: GPT-6.2 Sol'};
    }
    if (!model) throw Error('Configured experiment model is absent from the Pi catalog');
    return model;
  }
  const configured=googleModels[id];
  if (!configured) throw Error('Model not configured for this experiment');
  return {
    type: 'chat', id, name: `Google: Gemini 4 ${configured.name}`, provider: 'openrouter',
    api: 'openai-completions', baseUrl: 'https://openrouter.ai/api/v1',
    reasoning: true, input: ['text', 'image'],
    thinkingLevelMap: {off: null, minimal: null, low: 'low', medium: 'medium', high: 'high', xhigh: 'xhigh', max: null},
    // Standard Google Vertex global endpoint, USD per million tokens. Actual bills
    // still require provider receipts; cache-write metadata is not assumed usage.
    cost: {...configured.cost},
    contextWindow: 1048576, maxTokens: 943718,
    compat: {supportsDeveloperRole: false, thinkingFormat: 'openrouter', supportsStrictMode: true, sendSessionAffinityHeaders: true},
  };
}

export function experimentProvider(id) {
  if (!googleModels[id] && !openaiIds.includes(id)) throw Error('Model has no declared provider route');
  return {only: [googleModels[id] ? 'google-vertex/global' : 'openai'],
    allow_fallbacks: false, require_parameters: true, data_collection: 'deny'};
}
