// Shared by the task form, draft validation and the grading runtime.
const levels = ['low', 'medium', 'high'];
const openaiLevels = [...levels, 'xhigh', 'max'];
export const flashBudgets = { low: 512, medium: 2048, high: 8192 };
export const recommendedChatIds = [
  'openai/gpt-6.2-sol', 'openai/gpt-6.1-terra', 'google/gemini-4-hydrogen',
  'google/gemini-4-neon', 'qwen/qwen4-max',
];
export const gradingModels = [
  { id: 'openai/gpt-6.2-sol', name: 'GPT-6.2 Sol', efforts: openaiLevels },
  { id: 'openai/gpt-6.1-terra', name: 'GPT-6.1 Terra', efforts: ['off', ...openaiLevels] },
  { id: 'openai/gpt-6-luna', name: 'GPT-6 Luna', efforts: ['off', ...openaiLevels] },
  { id: 'qwen/qwen4-max', name: 'Qwen4 Max', efforts: ['off','low','high','xhigh'] },
  { id: 'qwen/qwen3.7-plus', name: 'Qwen3.7 Plus', efforts: ['off', 'on'] },
  { id: 'qwen/qwen3.8-flash', name: 'Qwen3.8 Flash', efforts: ['off', 'on', ...levels] },
  { id: 'openai/gpt-6.1-sol', name: 'GPT-6.1 Sol', efforts: openaiLevels },
  { id: 'google/gemini-4-carbon', name: 'Gemini 4 Carbon', efforts: levels },
  { id: 'google/gemini-4-hydrogen', name: 'Gemini 4 Hydrogen', efforts: [...levels, 'xhigh'] },
  { id: 'google/gemini-4-neon', name: 'Gemini 4 Neon', efforts: [...levels, 'xhigh'] },
];
export const effortLabels = { off: '关闭', on: '模型默认', low: '低', medium: '中', high: '高', xhigh: '超高', max: '最高' };
export const gradingPresets = [
  { mainModel:'openai/gpt-6.2-sol', mainEffort:'medium', workerModel:'openai/gpt-6.1-terra', workerEffort:'medium' },
  { mainModel:'openai/gpt-6.2-sol', mainEffort:'medium', workerModel:'openai/gpt-6-luna', workerEffort:'medium' },
  { mainModel:'qwen/qwen4-max', mainEffort:'high', workerModel:'qwen/qwen3.8-flash', workerEffort:'medium' },
  { mainModel:'qwen/qwen4-max', mainEffort:'high', workerModel:'qwen/qwen3.7-plus', workerEffort:'off' },
  { mainModel:'google/gemini-4-hydrogen', mainEffort:'medium', workerModel:'google/gemini-4-hydrogen', workerEffort:'low' },
];
export const modelOptions = catalog => catalog?.options ?? gradingModels;
export const gradingModel = (id, catalog) => modelOptions(catalog).find(model => model.id === id);

export function gradingConfigForModel(modelId, catalog, defaults = gradingPresets[0]) {
  const main = gradingModel(modelId || catalog?.defaultId, catalog);
  if (!main || main.id === defaults.mainModel) return defaults;
  const baseWorker = gradingModel(defaults.workerModel, catalog);
  // Keep the default worker pairing within a provider. A private endpoint uses its own model for both roles.
  const worker = !baseWorker || main.id.startsWith('connection:') || baseWorker.id.startsWith('connection:') || main.provider !== baseWorker.provider ? main : baseWorker;
  const effort = (model, preferred) => model.efforts.includes(preferred) ? preferred : model.efforts[0];
  return { mainModel:main.id, mainEffort:effort(main, defaults.mainEffort),
    workerModel:worker.id, workerEffort:effort(worker, defaults.workerEffort) };
}

export function modelConfigError(config, catalog) {
  for (const [role, label] of [['main','主模型'], ['worker','批改子模型']]) {
    const model = gradingModel(config?.[role + 'Model'], catalog);
    if (!model) return `请选择有效的${label}。`;
    if (!model.efforts.includes(config[role + 'Effort'])) return `${model.name} 不支持所选思考强度。`;
  }
  return null;
}

export function effortLabel(id, effort) {
  return id === 'qwen/qwen3.8-flash' && flashBudgets[effort]
    ? `${effortLabels[effort]} · ${flashBudgets[effort]} tokens` : effortLabels[effort];
}
