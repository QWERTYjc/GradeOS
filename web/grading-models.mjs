// Shared by the task form, draft validation and the grading runtime.
const levels = ['low', 'medium', 'high'];
const openaiLevels = [...levels, 'xhigh', 'max'];
export const flashBudgets = { low: 512, medium: 2048, high: 8192 };
export const gradingModels = [
  { id: 'openai/gpt-6.2-sol', name: 'GPT-6.2 Sol', efforts: openaiLevels },
  { id: 'openai/gpt-6.1-terra', name: 'GPT-6.1 Terra', efforts: ['off', ...openaiLevels] },
  { id: 'openai/gpt-6-luna', name: 'GPT-6 Luna', efforts: ['off', ...openaiLevels] },
  { id: 'qwen/qwen4-max', name: 'Qwen4 Max', efforts: ['off','low','high','xhigh'] },
  { id: 'qwen/qwen3.8-flash', name: 'Qwen3.8 Flash', efforts: ['off', 'on', ...levels] },
  { id: 'openai/gpt-6.1-sol', name: 'GPT-6.1 Sol', efforts: openaiLevels },
  { id: 'google/gemini-4-carbon', name: 'Gemini 4 Carbon', efforts: levels },
  { id: 'google/gemini-4-hydrogen', name: 'Gemini 4 Hydrogen', efforts: [...levels, 'xhigh'] },
];
export const effortLabels = { off: '关闭', on: '模型默认', low: '低', medium: '中', high: '高', xhigh: '超高', max: '最高' };
export const gradingPresets = [
  { mainModel:'openai/gpt-6.2-sol', mainEffort:'medium', workerModel:'openai/gpt-6.1-terra', workerEffort:'medium' },
  { mainModel:'openai/gpt-6.2-sol', mainEffort:'medium', workerModel:'openai/gpt-6-luna', workerEffort:'medium' },
  { mainModel:'qwen/qwen4-max', mainEffort:'high', workerModel:'qwen/qwen3.8-flash', workerEffort:'medium' },
];
export const gradingModel = id => gradingModels.find(model => model.id === id);
export function modelConfigError(config) {
  for (const [role, label] of [['main','主模型'], ['worker','批改子模型']]) {
    const model = gradingModel(config?.[role + 'Model']);
    if (!model) return `请选择有效的${label}。`;
    if (!model.efforts.includes(config[role + 'Effort'])) return `${model.name} 不支持所选思考强度。`;
  }
  return null;
}

export function effortLabel(id, effort) {
  return id === 'qwen/qwen3.8-flash' && flashBudgets[effort]
    ? `${effortLabels[effort]} · ${flashBudgets[effort]} tokens` : effortLabels[effort];
}
