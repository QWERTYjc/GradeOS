import { connectionFetch, nativeAllowance, nativeTools, safeNativeStream } from './pi-model-route.mjs';
import { configureFlashSubmission, flashSubmissionResult } from './flash-grading.mjs';
import { QWEN_PLUS_ID } from './experiment-models.mjs';
import { configurePointRows, gradingPointRowMode, restorePointRows, VISUAL_READBACK, FULL_CREDIT_READBACK } from './point-row-wire.mjs';
import { flashBudgets } from '../web/grading-models.mjs';
import { readFile, writeFile, mkdir, rename, appendFile, open } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pythonExecutable, helperEnvironment } from './python.mjs';
import { Budget, digest, wireEstimate } from './core.mjs';
import { inputContextSnapshot, inputContextReceipt, inputContextEstimate } from './input-context-estimate.mjs';
import {requireFeedbackSubmission,validateCorrectionRequest,requireGradingCorrectionTool} from './submission-contract.mjs';
import {outputBudget} from './output-budget.mjs';
import {HY4_FLASH_ID} from './experiment-models.mjs';

function jsonMemberCount(text) {
  // Match both keys and values so embedded quotes in a value cannot count as keys.
  return Array.from(text.matchAll(/"[^"\\]*(?:\\[\s\S][^"\\]*)*"(\s*:)?/g)).filter(match => match[1]).length;
}

function parseHy4Submission(text) {
  let value;
  try { value = JSON.parse(text); }
  catch { return null; }
  if (value === null || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).sort().join(',') !== 'items,observations,review_notes,source_issues'
      || jsonMemberCount(text) !== jsonMemberCount(JSON.stringify(value))) return null;
  return value;
}

function restoreHy4Submission(message, rawArguments) {
  if (message.stopReason === 'stop' && !rawArguments) {
    // The endpoint only offers automatic tool choice. Accept a single bare
    // JSON submission as the same tool input and let Pi validate it normally.
    const [part, ...others] = message.content.filter(block => block.type !== 'thinking');
    if (part?.type !== 'text' || others.length) return message;
    const args = parseHy4Submission(part.text);
    if (!args) return message;
    const toolCall = {type: 'toolCall', name: 'submit_grading', arguments: args,
      id: 'hy4_submit_' + digest(message.responseId ?? part.text).slice(0, 24)};
    return {...message, stopReason: 'toolUse', content: message.content.map(block => block === part ? toolCall : block)};
  }
  if (message.stopReason !== 'toolUse') return message;
  const calls = message.content.filter(part => part.type === 'toolCall');
  const [call] = calls;
  if (calls.length !== 1 || call.name !== 'submit_grading' || call.argumentsError) return message;
  const args = call.arguments;
  if (!args || Object.keys(args).join(',') !== 'observations' || typeof args.observations !== 'string') return message;

  // Tencent can return the JSON from the first field's opening brace to the
  // outer closing brace as one string. Verify this came from the complete wire
  // JSON before restoring only the missing framing.
  try {
    const wire = JSON.stringify(JSON.parse(rawArguments));
    if (wire !== JSON.stringify(args) || jsonMemberCount(rawArguments) !== 1) return message;
  }
  catch { return message; }
  const restored = parseHy4Submission('{"observations":' + args.observations);
  if (!restored) return message;
  // The original tool schema and grading validators still check every field.
  return {...message, content: message.content.map(part => part === call ? {...call, arguments: restored} : part)};
}

export const redactImages = value => JSON.parse(JSON.stringify(value, function(key, data) {
  if ((key === 'data' && typeof data === 'string' && (data.length > 1000 || this.mimeType?.startsWith?.('image/') || this.media_type?.startsWith?.('image/'))) ||
      ((key === 'url' || key === 'image_url') && typeof data === 'string' && data.startsWith('data:image/'))) return `<image sha256=${digest(data)}>`;
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
async function sourceViewBytes(page, args) {
  const {stdout}=await promisify(execFile)(pythonExecutable(),[fileURLToPath(new URL('../student_images.py',import.meta.url)),
    '--source',page.absolute_path,'--sha256',page.sha256,...args],
    {encoding:'buffer',maxBuffer:32*1024*1024,timeout:60000,env:helperEnvironment()});
  return stdout;
}
async function readSourceView(page, args, path) {
  const bytes=await sourceViewBytes(page,args);
  if (path) await writeFile(path,bytes);
  return {type:'image',mimeType:'image/png',data:bytes.toString('base64')};
}
// OpenRouter has no medium image-detail enum. Bound the full page locally
// before source delivery is recorded, preserving its aspect ratio and frame.
export const MEDIUM_IMAGE_MAX_SIDE = 1536;
export function readMediumPage(page) {
  return readPageOverview(page, MEDIUM_IMAGE_MAX_SIDE);
}
export function readPageOverview(page, maxSide, {trimWhiteMargins=false}={}) {
  return readSourceView(page, ['--max-side', String(maxSide), ...(trimWhiteMargins?['--trim-overview-margins']:[])]);
}

// Two overlapping, full-width views improve glyph resolution while preserving
// the complete physical page and its reading order.
export function readSourcePageBands(page) {
  return Promise.all([0, 420].map(top=>readSourceView(page, ['--region','0',String(top),'1000','580','--max-side','1440'])));
}

export function readResultEvidenceBand(page, region) {
  return readSourceView(page, ['--region', ...region.map(String), '--trim-region-margins','--max-side', String(MEDIUM_IMAGE_MAX_SIDE)]);
}

export async function readConcentratedAnswerView(page) {
  const {region,size}=JSON.parse((await sourceViewBytes(page,['--suggest-band'])).toString('utf8'));
  if(!region)return null;
  const [width,height]=size;
  const cropHeight=Math.ceil(height*region[3]/1000)+1;
  const patches=(w,h,maxSide)=>{
    const scale=Math.min(1,maxSide/Math.max(w,h));
    return Math.ceil(w*scale/32)*Math.ceil(h*scale/32);
  };
  const overviewSide=640, detailSide=1152;
  if(Math.min(1,detailSide/Math.max(width,cropHeight))<=Math.min(1,1280/Math.max(width,height)))return null;
  if(patches(width,height,overviewSide)+patches(width,cropHeight,detailSide)+64>patches(width,height,1280))return null;
  const [overview,band]=await Promise.all([
    readPageOverview(page,overviewSide),
    readSourceView(page,['--region',...region.map(String),'--max-side',String(detailSide)]),
  ]);
  return {region,overview,band};
}

let terraTokenizer;
async function countTerraPromptTokens() {
  terraTokenizer ??= Promise.all([import('js-tiktoken/lite'), import('js-tiktoken/ranks/o200k_base')])
    .then(([{Tiktoken},{default:ranks}]) => new Tiktoken(ranks));
  const tokenizer = await terraTokenizer;
  return text => tokenizer.encode(text, [], []).length;
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

function reviewOutputFloor(targets, countTokens) {
  const checks=targets.map(({item_id,point_id})=>({
    item_id,point_id,verdict:'unmet',evidence:'',student_pages:[1],reason:'',
    source_refs:[],quote_ref:'P',errors:[],alternate_reading:null,
  }));
  // Fund the whole payload, including the literal reading, a comparison and
  // room for an alternative or source exception, before making the request.
  return countTokens(JSON.stringify({checks})) + 112*checks.length + 64;
}

export function createRuntime({ models, model, output, cap, controller, maxRequests = 60, deadlineMs = 900000, maxOutputTokens = null, studentCacheNamespace = null, progress = null, interaction = null, structuredOutput = true, provider = { only: ['openai'], allow_fallbacks: false, require_parameters: true, data_collection: 'deny' }, workerModel = model, workerProvider = provider, mainConnection = null, workerConnection = mainConnection, mainEffort, workerEffort, singlePassGrading = false, coldCacheNamespace = null, studentCapUsd = null, mediumImages = false, studentOverviewMaxSide = null, visualReadback = false, compactStudentWire = false, fullCreditReadback = compactStudentWire }) {
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
  const io = async (lane, phase, { isolated = false, useMainModel = lane === 'main', singleToolReview = false } = {}) => {
    const directory = resolve(output, lane); await mkdir(directory);
    const laneModel = useMainModel ? model : workerModel;
    const transport = useMainModel ? mainConnection : workerConnection;
    // The Cloud relay and a saved OpenRouter key use the same model wire contract as the environment key.
    const connection = transport?.kind === 'openrouter' ? null : transport;
    const laneProvider = useMainModel ? provider : workerProvider;
    let current = null, currentInputSnapshot = null, previousInputReceipt = null;
    let rejectionCount = 0, lastBudgetRejection = null;
    const laneLog = event => log({ lane, ...event });
    const streamFn = (selectedModel, context, options) => {
      if (selectedModel.id !== laneModel.id || selectedModel.provider !== laneModel.provider) throw Error('Agent model differs from the declared lane model');
      const {gradingCorrectionRequest,sourceReviewAmendment:_sourceReviewAmendment,sourceReviewTargets,...providerOptions}=options??{};
      const requestPhase = phase();
      validateCorrectionRequest(requestPhase,lane,gradingCorrectionRequest);
      const flashSubmission = !connection && singlePassGrading && requestPhase === 'student_grading' && laneModel.id === 'qwen/qwen3.8-flash';
      const pinnedEndpoint = !connection && laneProvider.allow_fallbacks === false && laneProvider.only?.length === 1 ? laneProvider.only[0] : null;
      const boundedReview = singlePassGrading && requestPhase === 'source_permission_review' && singleToolReview;
      const effort = boundedReview && pinnedEndpoint === 'openai' && laneModel.id === 'openai/gpt-6-luna'
        ? 'low' : useMainModel ? mainEffort : workerEffort;
      const pointRowSubmission = !connection && singlePassGrading && !compactStudentWire && requestPhase === 'student_grading'
        ? gradingPointRowMode(laneModel.id,laneProvider,studentOverviewMaxSide) : null;
      const hy4Submission = !connection && singlePassGrading && requestPhase === 'student_grading' && laneModel.id === HY4_FLASH_ID;
      const hy4Arguments = [];
      const cacheScope = studentCacheNamespace && /^(student|feedback|exception|source-review)-/.test(lane) ? `${studentCacheNamespace}/${lane}` : null;
      if (connection && cacheScope) {
        context = {...context,messages:context.messages.map(message=>({...message}))};
        isolateStudentCache(context,cacheScope);
      }
      if (connection && !selectedModel.input.includes('image') && context.messages.some(message=>
        Array.isArray(message.content) && message.content.some(part=>part.type === 'image'))) {
        throw Error('所选模型仅支持文本，请选择支持图片的模型处理答卷。');
      }
      const upstream = models.streamSimple(selectedModel, context, {
      ...providerOptions, ...(effort ? { reasoning: effort === 'on' ? 'low' : effort === 'off' ? undefined : effort } : {}), apiKey: transport ? transport.apiKey : process.env.OPENROUTER_API_KEY,
      ...(transport ? {env:{}, ...(connection ? {reasoning:undefined} : {}),
        ...(transport.api === 'google-generative-ai' ? {} : {fetch:connectionFetch(transport,providerOptions.fetch)})} : {}), maxRetries: 0, maxTokens: maxOutputTokens??laneModel.maxTokens, timeoutMs: singlePassGrading ? 240000 : 180000,
      signal: options?.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal,
      onPayload: async payload => {
        await interaction?.beforeRequest(lane);
        if (interaction) budget.deadline = deadline + interaction.waitMilliseconds;
        if (controller.signal.aborted) throw Error('Cohort cancelled');
        if (!isolated) await interaction?.recordDelivery(lane, connection ? {messages:payload.messages ?? payload.input ?? payload.contents} : payload);
        if (payload.model !== laneModel.id) throw Error('Serialized model differs from the declared lane model');
        const standardOpenAI = pinnedEndpoint === 'openai';
        const terraStandard = standardOpenAI && singlePassGrading && studentCapUsd !== null
          && ['student_grading','source_permission_review'].includes(requestPhase) && laneModel.id === 'openai/gpt-6.1-terra';
        // This lane submits once. Main compilation and multi-turn review can
        // still reuse their cached contexts.
        const lunaOnePass = standardOpenAI && singlePassGrading && (requestPhase === 'student_grading' || boundedReview)
          && laneModel.id === 'openai/gpt-6-luna' && !cacheScope;
        if (connection) {
          const name = boundedReview ? 'submit_source_review' : requestPhase === 'student_feedback' ? 'submit_student_feedback'
            : singlePassGrading && requestPhase === 'student_grading' && !gradingCorrectionRequest ? 'submit_grading' : null;
          nativeTools(payload, connection.api, name, gradingCorrectionRequest, requireGradingCorrectionTool);
        } else {
          payload.provider = laneProvider; payload.usage = { include: true };
          if (effort) {
            if (laneModel.id === 'qwen/qwen3.8-flash') {
              payload.reasoning = flashBudgets[effort] ? { max_tokens: flashBudgets[effort] } : { enabled: effort !== 'off' };
            } else if (laneModel.id === QWEN_PLUS_ID) {
              payload.reasoning = { enabled: effort !== 'off' };
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
            payload.tool_choice=hy4Submission ? 'auto' : {type:'function',function:{name:'submit_grading'}};
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
          if (boundedReview) {
            payload.tool_choice={type:'function',function:{name:'submit_source_review'}};
            payload.tools[0].function.strict=true;
          }
          // Alibaba Flash accepts automatic tool choice. Keep only the requested
          // tool and let the existing submission validator decide completion.
          if (laneModel.id === 'qwen/qwen3.8-flash' && payload.tool_choice?.type === 'function') {
            const name = payload.tool_choice.function.name;
            payload.tools = payload.tools.filter(tool => tool.function.name === name);
            if (!payload.tools.length) throw Error('Requested tool is missing from the Flash request');
            payload.tool_choice = 'auto';
          }
          if (flashSubmission) configureFlashSubmission(payload);
          if (pointRowSubmission) configurePointRows(payload,pointRowSubmission === 'selected');
          if (visualReadback && singlePassGrading && requestPhase === 'student_grading' &&
            (pointRowSubmission === 'selected' || compactStudentWire || fullCreditReadback)) {
            payload.messages.push({role:'user',content:VISUAL_READBACK});
            if (fullCreditReadback) payload.messages.push({role:'user',content:FULL_CREDIT_READBACK});
          }
          if (cacheScope) isolateStudentCache(payload, cacheScope);
          if (terraStandard || lunaOnePass) {
            payload.service_tier = 'default';
            payload.prompt_cache_options = {mode:'explicit'};
          }
          for (const message of payload.messages) for (const part of Array.isArray(message.content) ? message.content : []) {
            if (part.type === 'image_url') part.image_url.detail = mediumImages && !terraStandard && !(lunaOnePass && boundedReview) ? 'auto' : 'high';
          }
        }
        const countTextTokens = terraStandard || (lunaOnePass && (boundedReview || compactStudentWire))
          ? await countTerraPromptTokens() : null;
        const estimate = wireEstimate(payload, countTextTokens);
        const inputSnapshot = inputContextSnapshot(payload, estimate);
        const inputContext = inputContextEstimate(inputSnapshot, estimate, previousInputReceipt);
        const tier=(laneModel.cost.tiers??[]).filter(t=>inputContext.upperBound>t.inputTokensAbove).at(-1)??laneModel.cost;
        const studentScope=/^(student|feedback|exception|source-review)-/.test(lane)?lane.replace(/^(feedback|exception|source-review)-/,'student-'):undefined;
        const scope=budget.scopes.has(lane)?lane:studentScope&&(budget.scopes.has(studentScope)||singlePassGrading)?studentScope:undefined;
        const minimumReviewTokens=boundedReview && sourceReviewTargets?.length
          ? reviewOutputFloor(sourceReviewTargets,countTextTokens??await countTerraPromptTokens()) : null;
        const prices = terraStandard || lunaOnePass ? {...tier,cacheWrite:0} : tier;
        const available = budget.available(scope);
        const minimumReviewReserve = minimumReviewTokens===null ? null :
          (inputContext.upperBound*Math.max(prices.input,prices.cacheWrite??0) + minimumReviewTokens*prices.output)/1e6;
        let reserve=null;
        const imageMaxSide = (requestPhase === 'student_grading' && studentOverviewMaxSide) || (mediumImages ? MEDIUM_IMAGE_MAX_SIDE : null);
        const metadata={lane,phase:requestPhase,...(scope?{budget_scope:scope,student_cap_usd:studentCapUsd}:{}),...(imageMaxSide ? {image_quality:'medium', image_max_side:imageMaxSide} : {}),configured_model:laneModel.id,configured_provider:laneProvider,configured_reasoning:effort ?? options?.reasoning,
          request_kind:gradingCorrectionRequest?.kind??'normal',grading_correction:gradingCorrectionRequest??null,
          student_cache_scope:cacheScope,...estimate,cost_input_token_reserve:inputContext.upperBound,input_context_estimate:inputContext,
          ...(minimumReviewTokens!==null?{
            minimum_review_output_tokens:minimumReviewTokens,
            minimum_review_reserve_usd:minimumReviewReserve,
          }:{})};
        try {
          const allowance=nativeAllowance(payload,connection?.api,wire => outputBudget({model:laneModel,payload:wire,
            inputTokens:inputContext.upperBound,prices,available,requestedLimit:maxOutputTokens}));
          if(minimumReviewTokens!==null&&allowance.tokens<minimumReviewTokens)
            throw Object.assign(Error(`The funded output allowance (${allowance.tokens}) cannot fit a complete local review (${minimumReviewTokens} tokens reserved).`),
              {code:'OUTPUT_BUDGET_LIMIT'});
          if (payload.reasoning?.max_tokens >= allowance.tokens) throw Object.assign(
            Error('本次费用或上下文余量不足以容纳所选思考预算，请降低思考强度。'), {code:'OUTPUT_BUDGET_LIMIT'});
          const {reservation}=allowance;reserve=reservation.input_usd+reservation.output_usd;
          Object.assign(metadata,wireEstimate(payload),{max_output_tokens:allowance.tokens,output_allowance:allowance,reservation});
          current = budget.admit(reserve,metadata);
          currentInputSnapshot = inputSnapshot;
        } catch (error) {
          if(scope?.startsWith('student-')&&error.code==='OUTPUT_BUDGET_LIMIT')error.code='STUDENT_BUDGET_LIMIT';
          const rejection={...metadata,reason:error.message,reserve_usd:reserve,cap_usd:budget.cap,
            charged_or_reserved_usd:budget.chargedOrReserved,available_usd:budget.cap-budget.chargedOrReserved,
            scope_available_usd:available,
            admitted_requests:budget.requests.length,max_requests:budget.maxRequests,deadline:budget.deadline};
          const rejectionFile = rejectionCount++ ? `rejected-request-${rejectionCount}.json` : 'rejected-request.json';
          if(error.code==='STUDENT_BUDGET_LIMIT')lastBudgetRejection=rejection;
          await writeFile(resolve(directory,rejectionFile),JSON.stringify({admission:rejection,payload:redactImages(payload)},null,2)+'\n',{flag:'wx'});
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
        if (hy4Submission) {
          for (const call of chunk?.choices?.[0]?.delta?.tool_calls ?? []) {
            if (typeof call.function?.arguments === 'string') hy4Arguments.push(call.function.arguments);
          }
        }
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
      if (connection) return safeNativeStream(upstream);
      if (flashSubmission) return flashSubmissionResult(upstream, text =>
        writeFile(resolve(directory, 'structured-submission-' + current.number + '.json'), text, {flag:'wx',mode:0o600}));
      if (pointRowSubmission) return restorePointRows(upstream, args =>
        writeFile(resolve(directory, 'point-row-submission-' + current.number + '.json'), JSON.stringify(args), {flag:'wx',mode:0o600}));
      if (!hy4Submission) return upstream;
      // Forward Pi's stream and normalize its final message before tool validation.
      const result = upstream.result().then(async message => {
        const rawArguments = hy4Arguments.join('');
        const restored = restoreHy4Submission(message, rawArguments);
        if (current) {
          const textSubmission = restored !== message && message.stopReason === 'stop';
          current.structured_output_adapter = restored === message ? null
            : textSubmission ? 'bare_json_submission' : 'wrapped_tool_arguments';
          if (rawArguments) {
            await writeFile(resolve(directory, 'tool-arguments-' + current.number + '.txt'),
              rawArguments, {flag:'wx', mode:0o600});
          }
          if (textSubmission) {
            await writeFile(resolve(directory, 'text-submission-' + current.number + '.json'),
              message.content.find(part => part.type === 'text').text, {flag:'wx', mode:0o600});
          }
        }
        return restored;
      });
      return {
        [Symbol.asyncIterator]: () => upstream[Symbol.asyncIterator](),
        result: () => result,
      };
    };
    const attach = agent => {
      const singlePass=singlePassGrading&&phase()==='student_grading';
      if (isolated) isolatedAgents.add(agent);
      const detachInteraction = isolated ? null : interaction?.attach(agent, lane, { interactiveTools: !singlePass&&phase() !== 'student_feedback', singlePass });
      const unsubscribe = agent.subscribe(async event => {
      if (event.type === 'message_end' && event.message.role === 'assistant') {
        if (current) {
          const settled=current;
          budget.settle(settled, event.message, connection ? laneModel.cost : null);
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
    return { directory, streamFn, log: laneLog, attach, takeBudgetRejection:()=>{
      const rejection=lastBudgetRejection;lastBudgetRejection=null;return rejection;
    } };
  };
  const run = async (agent, prompt, directory, {transcriptName='transcript.json'} = {}) => {
    active.add(agent);
    const abort = () => agent.abort(); controller.signal.addEventListener('abort', abort, { once: true });
    try {
      if (controller.signal.aborted) throw Error('Cohort cancelled before agent start');
      await agent.prompt(interaction && !isolatedAgents.has(agent) ? await interaction.preparePrompt(agent, prompt) : prompt);
    } finally {
      controller.signal.removeEventListener('abort', abort); active.delete(agent);
      await writeFile(resolve(directory, transcriptName), JSON.stringify(redactImages(agent.state.messages), null, 2) + '\n');
    }
  };
  const totals = requests => ({
    admitted_requests: requests.length,
    provider_reported_cost_usd: requests.filter(x => x.status === 'provider_reported').reduce((n, x) => n + x.cost_usd, 0),
    unknown_cost_requests: requests.filter(x => x.status === 'unknown').length,
    charged_or_reserved_usd: requests.reduce((n, x) => n + (x.cost_usd ?? x.usage_reserve_usd ?? x.reserve_usd), 0),
  });
  return { io, run, budget, provider, log, totals, close: () => clearTimeout(timer), active, signal: controller.signal,
    allocateStudentBudgets:(ids,{reserveCoordinator=true}={})=>budget.allocateScopes([...(reserveCoordinator&&ids.length>1?['main']:[]),...ids.map(id=>`student-${id}`)]),
    finishStudentBudget:id=>budget.closeScope(`student-${id}`) };
}
