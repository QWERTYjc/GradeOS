import { configureFlashSubmission, flashSubmissionResult } from './flash-grading.mjs';
import { flashBudgets } from '../web/grading-models.mjs';
import { readFile, writeFile, mkdir, rename, appendFile, open } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pythonExecutable } from './python.mjs';
import { Budget, digest, wireEstimate } from './core.mjs';
import { inputContextSnapshot, inputContextReceipt, inputContextEstimate } from './input-context-estimate.mjs';
import {requireFeedbackSubmission,validateCorrectionRequest,requireGradingCorrectionTool} from './submission-contract.mjs';
import {prepareLunaAnnotationRequest} from './luna-annotation-budget.mjs';
import {outputBudget} from './output-budget.mjs';

export const redactImages = value => JSON.parse(JSON.stringify(value, (key, data) => {
  if ((key === 'data' && typeof data === 'string' && data.length > 1000) ||
      (key === 'url' && typeof data === 'string' && data.startsWith('data:image/'))) return `<image sha256=${digest(data)}>`;
  return data;
}));
export async function freezeJson(directory, name, value) {
  const data = JSON.stringify(value, null, 2) + '\n';
  const pending = resolve(directory, `${name}.pending`);
  const handle = await open(pending, 'wx');
  try { await handle.writeFile(data); await handle.sync(); } finally { await handle.close(); }
  await writeFile(resolve(directory, name.replace(/\.json$/, '.sha256')), digest(data) + '\n', { flag: 'wx' });
  await rename(pending, resolve(directory, name));
}
export async function readImage(page) {
  const bytes = await readFile(page.absolute_path);
  if (digest(bytes) !== page.sha256) throw Error('Image changed after manifest freeze');
  return { type: 'image', mimeType: 'image/png', data: bytes.toString('base64') };
}
async function readSourceView(page, args, path) {
  const {stdout}=await promisify(execFile)(pythonExecutable(),[fileURLToPath(new URL('../scripts/python/student_images.py',import.meta.url)),
    '--source',page.absolute_path,'--sha256',page.sha256,...args],
    {encoding:'buffer',maxBuffer:32*1024*1024,timeout:60000});
  if (path) await writeFile(path,stdout);
  return {type:'image',mimeType:'image/png',data:stdout.toString('base64')};
}
// OpenRouter has no medium image-detail enum. Bound the full page locally
// before source delivery is recorded, preserving its aspect ratio and frame.
export const MEDIUM_IMAGE_MAX_SIDE = 1536;
export function readMediumPage(page) {
  return readSourceView(page, ['--max-side', String(MEDIUM_IMAGE_MAX_SIDE)]);
}

export async function readImageRegion(page, region, directory, {frame,localOnly=false}={}) {
  if(!Array.isArray(region)||region.length!==4||!region.every(Number.isSafeInteger)
    ||region[0]<0||region[1]<0||region[2]<=0||region[3]<=0||region[0]+region[2]>1000||region[1]+region[3]>1000)throw Error('Invalid original-page region');
  const path=resolve(directory,`source-region-${digest(frame?[page.sha256,region,frame]:[page.sha256,region])}.png`);
  return readSourceView(page,['--region',...region.map(String),...(frame?['--frame',...frame.map(String)]:[]),...(localOnly?['--local-only']:[])],path);
}

export function schemeOverviewReader(directory,maxSide) {
  const pending=new Map();
  return page=>{
    const key=page.sha256;
    if(!pending.has(key)){
      const path=resolve(directory,`ms-${maxSide}-${key}.png`);
      pending.set(key,readSourceView(page,['--max-side',String(maxSide)],path).catch(error=>{
        pending.delete(key);throw error;
      }));
    }
    return pending.get(key);
  };
}

export function isolateStudentCache(payload, scope) {
  if (!scope || !/^[A-Za-z0-9/_-]{1,160}$/.test(scope)) throw Error('Invalid student cache namespace');
  const firstUser = payload.messages.find(message => message.role === 'user');
  if (!firstUser) throw Error('Student request has no user content');
  const original = firstUser.content;
  if (typeof original !== 'string' && !Array.isArray(original)) throw Error('Unsupported student user content');
  firstUser.content = [{ type: 'text', text: `Submission namespace: ${scope}. This opaque identifier is bookkeeping only and has no grading meaning.` },
    ...(typeof original === 'string' ? [{ type: 'text', text: original }] : original)];
  return payload;
}

export function createRuntime({ models, model, output, cap, controller, maxRequests = 60, deadlineMs = 900000, maxOutputTokens = null, studentCacheNamespace = null, progress = null, interaction = null, structuredOutput = true, provider = { only: ['openai'], allow_fallbacks: false, require_parameters: true, data_collection: 'deny' }, workerModel = model, workerProvider = provider, mainEffort, workerEffort, singlePassGrading = false, economicalLuna = false, coldCacheNamespace = null, studentCapUsd = null, mediumImages = false }) {
  if (maxOutputTokens!==null&&(!Number.isInteger(maxOutputTokens) || maxOutputTokens < 1)) throw Error('Invalid explicit output token allowance');
  const budget = new Budget({ cap, maxRequests, deadlineMs, scopeCap:studentCapUsd });
  const active = new Set();
  const isolatedAgents = new WeakSet();
  const deadline = budget.deadline;
  const timer = interaction ? setInterval(() => {
    budget.deadline = deadline + interaction.waitMilliseconds;
    if (Date.now() >= budget.deadline) controller.abort(Error('Cohort deadline'));
  }, 250) : setTimeout(() => controller.abort(Error('Cohort deadline')), deadlineMs);
  const log = async event => {
    const entry={ at: new Date().toISOString(), ...event };
    await appendFile(resolve(output, 'events.jsonl'), JSON.stringify(entry) + '\n');
    await progress?.observe(entry);
  };
  const io = async (lane, phase, { isolated = false, useMainModel = lane === 'main' } = {}) => {
    const directory = resolve(output, lane); await mkdir(directory);
    const laneModel = useMainModel ? model : workerModel;
    const laneProvider = useMainModel ? provider : workerProvider;
    const effort = useMainModel ? mainEffort : workerEffort;
    let current = null, currentInputSnapshot = null, previousInputReceipt = null;
    const laneLog = event => log({ lane, ...event });
    const streamFn = (selectedModel, context, options) => {
      if (selectedModel.id !== laneModel.id || selectedModel.provider !== laneModel.provider) throw Error('Agent model differs from the declared lane model');
      const {gradingCorrectionRequest,...providerOptions}=options??{};
      const requestPhase = phase();
      validateCorrectionRequest(requestPhase,lane,gradingCorrectionRequest);
      const pricedRegions = economicalLuna && singlePassGrading && requestPhase === 'student_grading';
      const flashSubmission = singlePassGrading && requestPhase === 'student_grading' && laneModel.id === 'qwen/qwen3.8-flash';
      const upstream = models.streamSimple(selectedModel, context, {
      ...providerOptions, ...(effort ? { reasoning: effort === 'on' ? 'low' : effort === 'off' ? undefined : effort } : {}), apiKey: process.env.OPENROUTER_API_KEY, maxRetries: 0, maxTokens: maxOutputTokens??laneModel.maxTokens, timeoutMs: pricedRegions ? 600000 : singlePassGrading ? 240000 : 180000,
      signal: options?.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal,
      onPayload: async payload => {
        await interaction?.beforeRequest(lane);
        if (interaction) budget.deadline = deadline + interaction.waitMilliseconds;
        if (controller.signal.aborted) throw Error('Cohort cancelled');
        if (!isolated) await interaction?.recordDelivery(lane, payload);
        if (payload.model !== laneModel.id) throw Error('Serialized model differs from the declared lane model');
        payload.provider = laneProvider; payload.usage = { include: true };
        if (effort) {
          if (laneModel.id === 'qwen/qwen3.8-flash') {
            payload.reasoning = flashBudgets[effort] ? { max_tokens: flashBudgets[effort] } : { enabled: effort !== 'off' };
          } else {
            payload.reasoning = { effort: effort === 'off' ? 'none' : effort };
          }
        }
        // These pinned endpoints declare max_tokens for tool calls with images.
        if (['openai/gpt-6-luna', 'openai/gpt-6.2-sol', 'qwen/qwen4-max', 'qwen/qwen3.8-flash'].includes(laneModel.id) && payload.max_completion_tokens !== undefined) {
          payload.max_tokens=payload.max_completion_tokens;
          delete payload.max_completion_tokens;
        }
        if(singlePassGrading && requestPhase==='student_grading') {
          payload.tools=payload.tools.filter(tool=>tool.function.name==='submit_grading');
          payload.tool_choice={type:'function',function:{name:'submit_grading'}};
          // This source-bound schema is already authored for strict sampling.
          // Enable it on the serialized wire: Pi's optional normalizer rejects
          // valid provider-supported $defs/$ref and structured anyOf branches.
          payload.tools[0].function.strict=true;
        }
        if(coldCacheNamespace) {
          if(!/^[A-Za-z0-9_-]{1,100}$/.test(coldCacheNamespace))throw Error('Invalid cold cache namespace');
          const first=payload.messages[0], prefix=`Execution namespace ${coldCacheNamespace}. Bookkeeping only; no scoring meaning.\n`;
          first.content=typeof first.content==='string'?prefix+first.content:[{type:'text',text:prefix},...first.content];
        }
        requireFeedbackSubmission(payload, requestPhase);
        requireGradingCorrectionTool(payload, gradingCorrectionRequest);
        // Alibaba Flash accepts automatic tool choice. Keep only the requested
        // tool and let the existing submission validator decide completion.
        if (laneModel.id === 'qwen/qwen3.8-flash' && payload.tool_choice?.type === 'function') {
          const name = payload.tool_choice.function.name;
          payload.tools = payload.tools.filter(tool => tool.function.name === name);
          if (!payload.tools.length) throw Error('Requested tool is missing from the Flash request');
          payload.tool_choice = 'auto';
        }
        if (flashSubmission) configureFlashSubmission(payload);
        const cacheScope = studentCacheNamespace && /^(student|feedback|exception|source-review)-/.test(lane) ? `${studentCacheNamespace}/${lane}` : null;
        if (cacheScope) isolateStudentCache(payload, cacheScope);
        for (const message of payload.messages) for (const part of Array.isArray(message.content) ? message.content : []) {
          if (part.type === 'image_url') part.image_url.detail = mediumImages ? 'auto' : 'high';
        }
        const estimate = pricedRegions ? prepareLunaAnnotationRequest(payload, laneModel.cost) : wireEstimate(payload);
        const inputSnapshot = inputContextSnapshot(payload, estimate);
        const inputContext = inputContextEstimate(inputSnapshot, estimate, previousInputReceipt);
        const tier=(laneModel.cost.tiers??[]).filter(t=>inputContext.upperBound>t.inputTokensAbove).at(-1)??laneModel.cost;
        const studentScope=/^(student|feedback|exception|source-review)-/.test(lane)?lane.replace(/^(feedback|exception|source-review)-/,'student-'):undefined;
        const scope=budget.scopes.has(lane)?lane:studentScope&&(budget.scopes.has(studentScope)||singlePassGrading)?studentScope:undefined;
        let reserve=null;
        const metadata={lane,phase:requestPhase,...(scope?{budget_scope:scope,student_cap_usd:studentCapUsd}:{}),...(mediumImages ? {image_quality:'medium', image_max_side:MEDIUM_IMAGE_MAX_SIDE} : {}),configured_model:laneModel.id,configured_provider:laneProvider,configured_reasoning:effort ?? options?.reasoning,
          request_kind:gradingCorrectionRequest?.kind??'normal',grading_correction:gradingCorrectionRequest??null,
          student_cache_scope:cacheScope,...estimate,cost_input_token_reserve:inputContext.upperBound,input_context_estimate:inputContext};
        try {
          const allowance=outputBudget({model:laneModel,payload,inputTokens:inputContext.upperBound,prices:pricedRegions ? {...tier, cacheWrite: tier.input} : tier,available:budget.available(scope),requestedLimit:maxOutputTokens});
          if (payload.reasoning?.max_tokens >= allowance.tokens) throw Object.assign(
            Error('本次费用或上下文余量不足以容纳所选思考预算，请降低思考强度。'), {code:'OUTPUT_BUDGET_LIMIT'});
          const {reservation}=allowance;reserve=reservation.input_usd+reservation.output_usd;
          Object.assign(metadata,pricedRegions ? {payloadHash:digest(payload)} : wireEstimate(payload),{max_output_tokens:allowance.tokens,output_allowance:allowance,reservation});
          current = budget.admit(reserve,metadata);
          currentInputSnapshot = inputSnapshot;
        } catch (error) {
          if(scope?.startsWith('student-')&&error.code==='OUTPUT_BUDGET_LIMIT')error.code='STUDENT_BUDGET_LIMIT';
          const rejection={...metadata,reason:error.message,reserve_usd:reserve,cap_usd:budget.cap,
            charged_or_reserved_usd:budget.chargedOrReserved,available_usd:budget.cap-budget.chargedOrReserved,
            admitted_requests:budget.requests.length,max_requests:budget.maxRequests,deadline:budget.deadline};
          await writeFile(resolve(directory,'rejected-request.json'),JSON.stringify({admission:rejection,payload:redactImages(payload)},null,2)+'\n',{flag:'wx'});
          await laneLog({ type: 'request_rejected_before_send', ...rejection });
          if(error.code!=='STUDENT_BUDGET_LIMIT')controller.abort(error); throw error;
        }
        await writeFile(resolve(directory, `request-${current.number}.json`), JSON.stringify(redactImages(payload)), { flag: 'wx' });
        await laneLog({ type: 'request_admitted', request: current });
        return payload;
      },
      onResponse: async response => {
        if (current) { current.http_status = response.status; current.response_headers_at = new Date().toISOString(); }
        await laneLog({ type: 'http_response', number: current?.number, status: response.status });
      },
      onProviderStreamEvent: async chunk => {
        if (current) {
          const at=new Date().toISOString();
          if (!current.first_stream_event_at) current.first_stream_event_at=at;
          const deltas=Array.isArray(chunk?.choices)?chunk.choices.map(choice=>choice.delta ?? {}):[];
          for(const delta of deltas) for(const call of delta.tool_calls??[]) {
            current.stream_tool_names=[...new Set([...(current.stream_tool_names??[]),...(call.function?.name?[call.function.name]:[])])];
            current.stream_tool_argument_bytes=(current.stream_tool_argument_bytes??0)+Buffer.byteLength(call.function?.arguments??'');
          }
          for(const choice of chunk?.choices??[]) if(choice.finish_reason) current.provider_finish_reason=choice.finish_reason;
          if (!current.first_output_delta_at && deltas.some(delta=>(typeof delta.content==='string'&&delta.content.length)||delta.tool_calls?.some(call=>call.function?.arguments?.length))) {
            current.first_output_delta_at=at; await laneLog({type:'first_output_delta',number:current.number,at});
          }
          if (!current.first_reasoning_delta_at && deltas.some(delta=>delta.reasoning?.length||delta.reasoning_content?.length||delta.reasoning_details?.length)) current.first_reasoning_delta_at=at;
        }
        if (chunk?.provider && current) current.actual_provider = chunk.provider;
        if (chunk?.usage) {
          if (current) current.provider_prompt_tokens = Number.isSafeInteger(chunk.usage.prompt_tokens) ? chunk.usage.prompt_tokens : null;
          await laneLog({ type: 'provider_receipt', number: current?.number, id: chunk.id, model: chunk.model, provider: chunk.provider, usage: chunk.usage });
        }
      },
      });
      if (flashSubmission) return flashSubmissionResult(upstream, text =>
        writeFile(resolve(directory, 'structured-submission-' + current.number + '.json'), text, {flag:'wx',mode:0o600}));
      return upstream;
    };
    const attach = (agent, { guideRubric = null } = {}) => {
      const singlePass=singlePassGrading&&phase()==='student_grading';
      if (isolated) isolatedAgents.add(agent);
      const detachInteraction = isolated ? null : interaction?.attach(agent, lane, { interactiveTools: !singlePass&&phase() !== 'student_feedback', singlePass, guideRubric });
      const unsubscribe = agent.subscribe(async event => {
      if (event.type === 'message_end' && event.message.role === 'assistant') {
        if (current) {
          const settled=current;
          budget.settle(settled, event.message);
          previousInputReceipt = inputContextReceipt(currentInputSnapshot, settled, event.message);
          currentInputSnapshot = null;
          current = null;
          await laneLog({ type: 'request_terminal', request: settled });
          if(structuredOutput)console.log(JSON.stringify({ lane, request: settled.number, phase: settled.phase, stop: event.message.stopReason, cost_usd: settled.cost_usd ?? null }));
        }
        await laneLog({ type: 'assistant_message', message: event.message });
      }
      if (event.type === 'tool_execution_end') await laneLog({ type: event.type, tool: event.toolName, is_error: event.isError });
      });
      return () => { unsubscribe(); detachInteraction?.(); };
    };
    return { directory, streamFn, log: laneLog, attach };
  };
  const run = async (agent, prompt, directory) => {
    active.add(agent);
    const abort = () => agent.abort(); controller.signal.addEventListener('abort', abort, { once: true });
    try {
      if (controller.signal.aborted) throw Error('Cohort cancelled before agent start');
      await agent.prompt(interaction && !isolatedAgents.has(agent) ? await interaction.preparePrompt(agent, prompt) : prompt);
    } finally {
      controller.signal.removeEventListener('abort', abort); active.delete(agent);
      await writeFile(resolve(directory, 'transcript.json'), JSON.stringify(redactImages(agent.state.messages), null, 2) + '\n');
    }
  };
  const totals = requests => ({
    admitted_requests: requests.length,
    provider_reported_cost_usd: requests.filter(x => x.status === 'provider_reported').reduce((n, x) => n + x.cost_usd, 0),
    unknown_cost_requests: requests.filter(x => x.status === 'unknown').length,
    charged_or_reserved_usd: requests.reduce((n, x) => n + (x.cost_usd ?? x.reserve_usd), 0),
  });
  return { io, run, budget, provider, log, totals, close: () => clearTimeout(timer), active, signal: controller.signal,
    allocateStudentBudgets:(ids,{reserveCoordinator=true}={})=>budget.allocateScopes([...(reserveCoordinator&&ids.length>1?['main']:[]),...ids.map(id=>`student-${id}`)]),
    finishStudentBudget:id=>budget.closeScope(`student-${id}`) };
}
