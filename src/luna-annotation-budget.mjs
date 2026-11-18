import { getEncoding } from 'js-tiktoken';
import { digest } from './core.mjs';

export const LUNA_PAGE_SIDE = 960;
let encoder;

// Applies only to the single-use, standard OpenAI Luna route. Count the
// serialized rubric, teacher edits, OCR index and tool schema before reserving
// the remaining funds for the complete response. Settlement uses the receipt.
export function prepareLunaAnnotationRequest(payload, prices) {
  if (payload.model !== 'openai/gpt-6-luna' || payload.provider?.only?.length !== 1
    || payload.provider.only[0] !== 'openai' || payload.provider.allow_fallbacks !== false) throw Error('Unexpected Luna route');
  payload.service_tier = 'default';
  payload.provider = { ...payload.provider, max_price: { prompt: prices.input, completion: prices.output } };
  payload.prompt_cache_options = { mode: 'explicit' };
  delete payload.cache_control;
  delete payload.prompt_cache_key;
  delete payload.prompt_cache_retention;
  for (const message of payload.messages) for (const part of Array.isArray(message.content) ? message.content : []) {
    delete part.cache_control;
    delete part.prompt_cache_breakpoint;
  }
  let images = 0, imageTokenReserve = 0;
  const serialized = JSON.stringify(payload, (_key, part) => {
    if (part?.type !== 'image_url') return part;
    const url = part.image_url.url;
    if (part.image_url.detail !== 'high' || !url.startsWith('data:image/png;base64,')) throw Error('Expected complete high-detail PNG');
    const header = Buffer.from(url.slice(22, 66), 'base64');
    if (header.length < 24 || header.readUInt32BE(0) !== 0x89504e47 || header.toString('ascii',12,16) !== 'IHDR') throw Error('Invalid PNG');
    const width = header.readUInt32BE(16), height = header.readUInt32BE(20);
    if (!width || !height) throw Error('Invalid PNG dimensions');
    images++;
    imageTokenReserve += Math.ceil(Math.ceil(width / 32) * Math.ceil(height / 32) * 1.2) + 256;
    return { type: 'image_url', image_url: { detail: 'high', url: '<image>' } };
  });
  encoder ??= getEncoding('o200k_base');
  const textTokens = encoder.encode(serialized, [], []).length;
  const inputTokenReserve = Math.ceil(textTokens * 1.15) + 2048 + images * 32 + imageTokenReserve;
  return { images, textBytes: Buffer.byteLength(serialized), textTokens, imageTokenReserve, inputTokenReserve,
    estimator: 'luna-annotated-pages-v1', payloadHash: digest(payload) };
}
