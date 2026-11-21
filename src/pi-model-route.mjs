import { createProvider } from '@earendil-works/pi-ai';
import { openAICompletionsApi } from '@earendil-works/pi-ai/api/openai-completions.lazy';
import { openAIResponsesApi } from '@earendil-works/pi-ai/api/openai-responses.lazy';
import { anthropicMessagesApi } from '@earendil-works/pi-ai/api/anthropic-messages.lazy';
import { googleGenerativeAIApi } from '@earendil-works/pi-ai/api/google-generative-ai.lazy';
import { experimentModel, experimentProvider } from './experiment-models.mjs';

import { openaiProvider } from '@earendil-works/pi-ai/providers/openai';
import { anthropicProvider } from '@earendil-works/pi-ai/providers/anthropic';
import { googleProvider } from '@earendil-works/pi-ai/providers/google';
import { deepseekProvider } from '@earendil-works/pi-ai/providers/deepseek';
import { groqProvider } from '@earendil-works/pi-ai/providers/groq';
import { xaiProvider } from '@earendil-works/pi-ai/providers/xai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';

const providers = [openaiProvider,anthropicProvider,googleProvider,deepseekProvider,groqProvider,xaiProvider,openrouterProvider]
  .map(create=>create());
export function localModelCatalog(baseUrl) {
  return providers.find(provider=>provider.baseUrl===baseUrl)?.getModels() ?? [];
}
const adapters = {'openai-completions':openAICompletionsApi,'openai-responses':openAIResponsesApi,
  'anthropic-messages':anthropicMessagesApi,'google-generative-ai':googleGenerativeAIApi};

export function piModelRoute(models, modelId, connection) {
  if (!connection) return {model:experimentModel(models, modelId),provider:experimentProvider(modelId)};
  if (modelId !== connection.modelId || !connection.apiKey || !adapters[connection.api]) throw Error('模型连接与已选模型不一致。');
  if (connection.kind === 'openrouter') {
    return {model:{...experimentModel(models, modelId), baseUrl:connection.baseUrl}, provider:experimentProvider(modelId)};
  }
  const {id:providerId, name, api, baseUrl, inputRate, outputRate} = connection;
  // Explicit per-connection registration preserves model identity across endpoints.
  const known = localModelCatalog(baseUrl).find(row=>row.id===modelId);
  const model = {id:modelId, type:'chat', name:modelId, api, provider:providerId, baseUrl,
    input:known?.input ?? ['text','image'], reasoning:false, contextWindow:known?.contextWindow ?? 128000, maxTokens:known?.maxTokens ?? 16384,
    ...(known?.api === api && known.compat ? {compat:known.compat} : {}),
    cost:{input:inputRate,output:outputRate,cacheRead:inputRate,cacheWrite:inputRate}};
  models.setProvider(createProvider({id:providerId, name, baseUrl, models:[model], api:adapters[api](),
    auth:{apiKey:{name:'API Key',resolve:async ({credential})=>credential?.key ? {auth:{apiKey:credential.key},source:'workspace'} : undefined}}}));
  return {model, provider:{connectionId:providerId,name,api,baseUrl}};
}

export function connectionFetch(connection, fetchImpl = globalThis.fetch) {
  // SDKs can add environment-wide organization or custom credential headers.
  // Only protocol headers and this connection's credential go to its endpoint.
  const origin = new URL(connection.baseUrl).origin;
  return async (input, init) => {
    const request = new Request(input,init);
    if (new URL(request.url).origin !== origin) throw Error('模型请求离开了所配置的 API 地址。');
    const headers = new Headers();
    for (const name of ['content-type','accept','anthropic-version','anthropic-beta']) {
      const value = request.headers.get(name);
      if (value) headers.set(name,value);
    }
    if (connection.api === 'anthropic-messages') headers.set('x-api-key',connection.apiKey);
    else headers.set('authorization','Bearer ' + connection.apiKey);
    return fetchImpl(new Request(request,{headers,redirect:'error'}));
  };
}

export function nativeTools(payload, api, name, correction, validateCorrection) {
  const google = api === 'google-generative-ai';
  const tools = google ? (payload.config.tools || []).flatMap(group=>group.functionDeclarations || []) : payload.tools || [];
  const toolName = tool => tool.function?.name ?? tool.name;
  if (correction) {
    validateCorrection({tools:tools.map(tool=>({function:{name:toolName(tool)}}))},correction);
    return;
  }
  if (!name) return;
  const selected = tools.filter(tool=>toolName(tool)===name);
  if (selected.length !== 1) throw Error('缺少此批改阶段的提交工具。');
  if (google) {
    payload.config.tools = [{functionDeclarations:selected}];
    payload.config.toolConfig = {functionCallingConfig:{mode:'ANY',allowedFunctionNames:[name]}};
  } else {
    payload.tools = selected;
    payload.tool_choice = api === 'openai-completions' ? {type:'function',function:{name}}
      : {type:api === 'anthropic-messages'?'tool':'function',name};
  }
}

export function nativeAllowance(payload, api, calculate) {
  if (api !== 'google-generative-ai' && api !== 'openai-responses') return calculate(payload);
  const object = api === 'google-generative-ai' ? payload.config : payload;
  const key = api === 'google-generative-ai' ? 'maxOutputTokens' : 'max_output_tokens';
  const limit = {max_tokens:object[key]};
  const allowance = calculate(limit);
  object[key] = allowance.tokens;
  return allowance;
}

export function safeNativeStream(stream) {
  // Authentication errors sometimes include the submitted credential in their text.
  const sanitized = message => message?.errorMessage ? {...message,errorMessage:'模型服务请求失败，请检查 API 地址、密钥、模型权限及额度。'} : message;
  return {
    async *[Symbol.asyncIterator]() {
      for await (const event of stream) yield event.type === 'error' ? {...event,error:sanitized(event.error)} : event;
    },
    async result() { return sanitized(await stream.result()); }
  };
}
