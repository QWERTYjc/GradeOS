// Pi 1.5.2 predates these models. Reuse its OpenRouter serializer and agent loop.
// Source: public /models/google/gemini-4-{carbon,hydrogen}/endpoints, 2026-11-17.
export const HYDROGEN_ID = 'google/gemini-4-hydrogen';
export const CARBON_ID = 'google/gemini-4-carbon';
export const HY4_FLASH_ID = 'tencent/hy4-flash';
export const QWEN_PLUS_ID = 'qwen/qwen3.7-plus';
export const DEFAULT_MAIN_MODEL_ID = 'openai/gpt-6.1-terra';
export const DEFAULT_WORKER_MODEL_ID = 'openai/gpt-6-luna';
const googleModels = {
  'google/gemini-4-neon': {name:'Neon',cost:{input:3,output:15,cacheRead:0.15,cacheWrite:0.0833333333333333}},
  [HYDROGEN_ID]: {name:'Hydrogen',cost:{input:1.5,output:7.5,cacheRead:0.075,cacheWrite:0.0833333333333333}},
  [CARBON_ID]: {name:'Carbon',cost:{input:2,output:10,cacheRead:0.1,cacheWrite:0.1875}},
};
const SOL_62_ID = 'openai/gpt-6.2-sol';
const openaiIds = [SOL_62_ID, 'openai/gpt-6.1-terra', 'openai/gpt-6.1-sol', 'openai/gpt-6-luna'];

export function experimentModel(models, id) {
  if (id === QWEN_PLUS_ID) {
    const model = models.getModel('openrouter', id);
    if (!model) throw Error('Qwen3.7 Plus is absent from the Pi catalog');
    return { ...model, compat: { ...model.compat, maxTokensField: 'max_tokens' } };
  }
  if (id === HY4_FLASH_ID) {
    // OpenRouter Tencent FP8 endpoint metadata, verified 2026-11-18.
    return {
      type: 'chat', id, name: 'Tencent: Hy4 flash', provider: 'openrouter',
      api: 'openai-completions', baseUrl: 'https://openrouter.ai/api/v1',
      reasoning: true, input: ['text', 'image'],
      cost: {input: 0.035, output: 0.1405, cacheRead: 0.0015, cacheWrite: 0},
      contextWindow: 1048576, maxTokens: 65536,
      compat: {supportsDeveloperRole: false, thinkingFormat: 'openrouter', supportsStrictMode: true},
    };
  }
  if (id === 'qwen/qwen4-max' || id === 'qwen/qwen3.8-flash') {
    const flash = models.getModel('openrouter', 'qwen/qwen3.8-flash');
    if (!flash) throw Error('Qwen OpenRouter serializer is absent from the Pi catalog');
    // The Alibaba endpoint exposes max_tokens for both models. Use this
    // endpoint's cache-write pricing for budget reservations.
    const cost = id === 'qwen/qwen4-max'
      ? { input: 1.425, output: 4.275, cacheRead: 0.07125, cacheWrite: 1.78125 }
      : { ...flash.cost, cacheWrite: 0.2 };
    return { ...flash, id, name: id === 'qwen/qwen4-max' ? 'Qwen: Qwen4 Max' : flash.name,
      cost, compat: { ...flash.compat, maxTokensField: 'max_tokens' } };
  }
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
  if (id === HY4_FLASH_ID) return {
    only: ['tencent/fp8'], allow_fallbacks: false, require_parameters: true,
    data_collection: 'deny', zdr: true,
  };
  const qwen = id === 'qwen/qwen4-max' || id === 'qwen/qwen3.8-flash' || id === QWEN_PLUS_ID;
  if (!qwen && !googleModels[id] && !openaiIds.includes(id)) throw Error('Model has no declared provider route');
  return {only: [qwen ? 'alibaba' : googleModels[id] ? 'google-vertex/global' : 'openai'],
    allow_fallbacks: false, require_parameters: true, data_collection: 'deny'};
}
