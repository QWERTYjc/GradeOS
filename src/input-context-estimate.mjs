import { digest } from './core.mjs';

const encryptedReasoning = details => (Array.isArray(details)?details:[])
  .filter(detail=>detail?.type==='reasoning.encrypted'&&typeof detail.data==='string')
  .map(detail=>({hash:digest(detail),bytes:Buffer.byteLength(JSON.stringify(detail.data))-2}));

function outputReasoning(message) {
  // Pi preserves OpenRouter replay metadata in the first valid thinking signature.
  // Keep only fingerprints; the original encrypted contents stay in the conversation.
  for(const block of message.content??[])if(block.type==='thinking'&&block.thinkingSignature){
    try {const details=JSON.parse(block.thinkingSignature);if(Array.isArray(details))return encryptedReasoning(details);}catch{}
  }
  return [];
}

// Context and cost admission share the same token bound. A complete provider
// receipt can bound an unchanged prefix; cache discounts are never assumed.
// Only hashes are retained: no source images or credentials are copied here.
export function inputContextSnapshot(payload, estimate) {
  const { messages, ...configuration } = payload;
  if (!Array.isArray(messages)) return null;
  return {
    configurationHash: digest(configuration), messageHashes: messages.map(digest),
    encryptedReasoning: messages.map(message=>message.role==='assistant'?encryptedReasoning(message.reasoning_details):[]),
    textBytes: estimate.textBytes, images: estimate.images, imageTokenReserve: estimate.imageTokenReserve ?? estimate.images*4096,
  };
}

export function inputContextReceipt(snapshot, request, message) {
  const usage = message.usage;
  if (!snapshot || request.http_status !== 200 || !['stop', 'toolUse'].includes(message.stopReason)
    || !usage || ![usage.input, usage.cacheRead, usage.cacheWrite, usage.totalTokens].every(Number.isSafeInteger)
    || [usage.input, usage.cacheRead, usage.cacheWrite].some(value => value < 0)) return null;
  const inputTokens = usage.input + usage.cacheRead + usage.cacheWrite;
  if (inputTokens <= 0 || inputTokens > usage.totalTokens
    || !Number.isSafeInteger(request.provider_prompt_tokens) || request.provider_prompt_tokens !== inputTokens) return null;
  const outputTokens=Number.isSafeInteger(usage.output)&&usage.output>=0&&inputTokens+usage.output===usage.totalTokens?usage.output:null;
  return { ...snapshot, requestNumber: request.number, inputTokens, outputTokens,
    outputReasoning:outputTokens===null?[]:outputReasoning(message) };
}

export function inputContextEstimate(snapshot, estimate, receipt) {
  const fallback = { upperBound: estimate.inputTokenReserve, fullByteImageBound: estimate.inputTokenReserve,
    method: 'full_byte_image_bound', anchorRequest: null, reason: 'No matching complete provider receipt and unchanged prefix' };
  if (!snapshot || !receipt || snapshot.configurationHash !== receipt.configurationHash
    || snapshot.messageHashes.length < receipt.messageHashes.length
    || !receipt.messageHashes.every((hash, index) => snapshot.messageHashes[index] === hash)
    || snapshot.textBytes < receipt.textBytes || snapshot.images < receipt.images) return fallback;
  const appendedMessages = snapshot.messageHashes.length - receipt.messageHashes.length;
  // Exact unchanged prefix/config makes this the serialized appended messages,
  // including their roles/tool calls and delimiters, not just visible text.
  const appendedBytes = snapshot.textBytes - receipt.textBytes, appendedImages = snapshot.images - receipt.images;
  const appendedImageBound = snapshot.imageTokenReserve - (receipt.imageTokenReserve ?? receipt.images*4096);
  if(appendedImageBound<0)return fallback;
  const replayed=snapshot.encryptedReasoning?.[receipt.messageHashes.length]??[];
  const matchedOutput=receipt.outputTokens>0&&replayed.length>0&&digest(replayed)===digest(receipt.outputReasoning);
  const encryptedBytes=matchedOutput?replayed.reduce((sum,part)=>sum+part.bytes,0):0;
  if(encryptedBytes>appendedBytes)return fallback;
  // Charge the complete measured output (including reasoning), plus all remaining
  // appended bytes/images. Unknown or altered encrypted data keeps its byte bound.
  const appendBound = appendedBytes - encryptedBytes + (matchedOutput?receipt.outputTokens:0) + appendedImageBound
    + appendedMessages * 64;
  return { upperBound: receipt.inputTokens + appendBound, method: matchedOutput?'receipt_plus_output_append_bound':'receipt_plus_append_bound',
    anchorRequest: receipt.requestNumber, anchorInputTokens: receipt.inputTokens, appendBound,
    ...(matchedOutput?{replayed_output_tokens:receipt.outputTokens,encrypted_replay_bytes:encryptedBytes}:{}),
    appendedBytes, appendedImages, prefixMessageCount: receipt.messageHashes.length,
    configurationHash: snapshot.configurationHash, fullByteImageBound: estimate.inputTokenReserve };
}
