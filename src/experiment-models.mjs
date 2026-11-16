// The installed Pi 1.5.2 catalog predates Hydrogen. Keep the experiment's explicit
// model metadata here while reusing Pi's native OpenRouter serializer and agent loop.
// Source: public /models and /models/google/gemini-4-hydrogen/endpoints, 2026-11-15.
export const HYDROGEN_ID = 'google/gemini-4-hydrogen';
const openaiIds = ['openai/gpt-6.1-terra', 'openai/gpt-6.1-sol', 'openai/gpt-6-luna'];

export function experimentModel(models, id) {
  if (openaiIds.includes(id)) {
    const model = models.getModel('openrouter', id);
    if (!model) throw Error('Configured experiment model is absent from the Pi catalog');
    return model;
  }
  if (id !== HYDROGEN_ID) throw Error('Model not configured for this experiment');
  return {
    type: 'chat', id, name: 'Google: Gemini 4 Hydrogen', provider: 'openrouter',
    api: 'openai-completions', baseUrl: 'https://openrouter.ai/api/v1',
    reasoning: true, input: ['text', 'image'],
    thinkingLevelMap: {off: null, minimal: null, low: 'low', medium: 'medium', high: 'high', xhigh: 'xhigh', max: null},
    // Standard Google Vertex global endpoint, USD per million tokens. Actual bills
    // still require provider receipts; cache-write metadata is not assumed usage.
    cost: {input: 1.5, output: 7.5, cacheRead: 0.075, cacheWrite: 0.0833333333333333},
    contextWindow: 1048576, maxTokens: 943718,
    compat: {supportsDeveloperRole: false, thinkingFormat: 'openrouter', supportsStrictMode: true, sendSessionAffinityHeaders: true},
  };
}

export function experimentProvider(id) {
  if (id !== HYDROGEN_ID && !openaiIds.includes(id)) throw Error('Model has no declared provider route');
  return {only: [id === HYDROGEN_ID ? 'google-vertex/global' : 'openai'],
    allow_fallbacks: false, require_parameters: true, data_collection: 'deny'};
}
