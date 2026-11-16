import test from 'node:test';
import assert from 'node:assert/strict';
import { wireEstimate } from '../src/core.mjs';
import { inputContextSnapshot, inputContextReceipt, inputContextEstimate } from '../src/input-context-estimate.mjs';

const payload = () => ({ model: 'neutral-model', tools: [], provider: { only: ['fixed'] }, messages: [
  { role: 'system', content: 'Source-bound grading.' },
  { role: 'user', content: '原页与实施要求。'.repeat(14000) },
] });
const receipt = (p, override = {}) => inputContextReceipt(inputContextSnapshot(p, wireEstimate(p)),
  { number: 3, http_status: 200, provider_prompt_tokens: 30100 }, { stopReason: 'toolUse',
    usage: { input: 100, cacheRead: 20000, cacheWrite: 10000, totalTokens: 30200 }, ...override });

test('unchanged provider-confirmed prefix bounds appended evidence without assuming a cache hit', () => {
  const before = payload(), anchor = receipt(before);
  const after = structuredClone(before);
  after.messages.push({ role: 'assistant', content: 'Read the next original page.' },
    { role: 'user', content: [{ type: 'image_url', image_url: { url: 'data:image/png;base64,aGVsbG8=' } }] });
  const estimate = wireEstimate(after), result = inputContextEstimate(inputContextSnapshot(after, estimate), estimate, anchor);
  assert.ok(estimate.inputTokenReserve > 272000);
  assert.equal(result.method, 'receipt_plus_append_bound');
  assert.equal(result.anchorInputTokens, 30100);
  assert.ok(result.upperBound < 40000);
  assert.equal(result.appendBound, estimate.textBytes - wireEstimate(before).textBytes + 4096 + 128);
  assert.equal(wireEstimate(after).inputTokenReserve, estimate.inputTokenReserve);
});

test('changed prefix, context checkpoint, model or tools fall back to the full conservative bound', () => {
  for (const mutate of [
    p => { p.messages[0].content = 'Changed'; }, p => { p.messages.shift(); },
    p => { p.model = 'different'; }, p => { p.tools.push({ name: 'another' }); },
    p => { p.provider.only = ['different']; }, p => { p.reasoning = { effort: 'high' }; },
  ]) {
    const before = payload(), after = structuredClone(before); mutate(after);
    const estimate = wireEstimate(after), result = inputContextEstimate(inputContextSnapshot(after, estimate), estimate, receipt(before));
    assert.equal(result.method, 'full_byte_image_bound');
    assert.equal(result.upperBound, estimate.inputTokenReserve);
  }
});

test('error, aborted, missing, negative or inconsistent usage never creates a context anchor', () => {
  const p = payload();
  for (const override of [
    { stopReason: 'error' }, { stopReason: 'aborted' }, { stopReason: 'length' }, { usage: undefined },
    { usage: { input: -1, cacheRead: 0, cacheWrite: 0, totalTokens: 1 } },
    { usage: { input: 1, totalTokens: 1 } },
    { usage: { input: 10, cacheRead: 20, cacheWrite: 30, totalTokens: 20 } },
  ]) assert.equal(receipt(p, override), null);
  const estimate = wireEstimate(p);
  assert.equal(inputContextEstimate(inputContextSnapshot(p, estimate), estimate, null).upperBound, estimate.inputTokenReserve);
  for (const provider_prompt_tokens of [undefined, 0, 30101, 30100.5]) assert.equal(inputContextReceipt(
    inputContextSnapshot(p, estimate), { number: 1, http_status: 200, provider_prompt_tokens },
    { stopReason: 'toolUse', usage: { input: 100, cacheRead: 20000, cacheWrite: 10000, totalTokens: 30200 } }), null);
});

test('changing an already delivered image or teacher document cannot reuse its receipt', () => {
  const before = payload();
  before.messages.push({ role: 'user', content: [{ type: 'image_url', image_url: { url: 'data:image/png;base64,aGVsbG8=', detail: 'high' } }] });
  for (const mutate of [p => { p.messages[1].content += 'changed teacher instruction'; },
    p => { p.messages[2].content[0].image_url.url += 'x'; },
    p => { p.messages[2].content[0].image_url.detail = 'low'; }]) {
    const after = structuredClone(before); mutate(after); const estimate = wireEstimate(after);
    assert.equal(inputContextEstimate(inputContextSnapshot(after, estimate), estimate, receipt(before)).method, 'full_byte_image_bound');
  }
});

test('matched opaque reasoning reuses complete measured output tokens without changing replay payload or cache prefix',()=>{
  for(const data of ['q'.repeat(96000),'s'.repeat(640000),'加密占位符'.repeat(35000)]){
    const before=payload(),details=[{type:'reasoning.encrypted',data,format:'openai-responses-v1',id:'neutral-proof'}];
    const message={stopReason:'toolUse',content:[{type:'thinking',thinking:'',thinkingSignature:JSON.stringify(details)}],
      usage:{input:100,cacheRead:20000,cacheWrite:10000,output:5200,totalTokens:35300}};
    const anchor=receipt(before,message),after=structuredClone(before);
    after.messages.push({role:'assistant',content:'Inspect the original source.',reasoning_details:details},
      {role:'tool',content:'An additional source-grounding entry is required.'});
    const unchanged=structuredClone(after),estimate=wireEstimate(after);
    const result=inputContextEstimate(inputContextSnapshot(after,estimate),estimate,anchor);
    assert.equal(result.method,'receipt_plus_output_append_bound');
    assert.equal(result.replayed_output_tokens,5200);
    assert.equal(result.encrypted_replay_bytes,Buffer.byteLength(JSON.stringify(data))-2);
    assert.equal(result.upperBound,30100+5200+estimate.textBytes-wireEstimate(before).textBytes-result.encrypted_replay_bytes+128);
    assert.ok(result.upperBound<40000);assert.deepEqual(after,unchanged);
    assert.equal(JSON.stringify(anchor).includes(data),false);
  }
});

test('unknown, altered, duplicated or unmeasured opaque data is never discounted as the generated response',()=>{
  const before=payload(),details=[{type:'reasoning.encrypted',data:'v'.repeat(400000)}];
  const output={stopReason:'toolUse',content:[{type:'thinking',thinkingSignature:JSON.stringify(details)}],
    usage:{input:100,cacheRead:20000,cacheWrite:10000,output:5200,totalTokens:35300}};
  const anchor=receipt(before,output);
  for(const mutate of [
    p=>{p.messages.at(-1).reasoning_details[0].data+='different';},
    p=>{p.messages.at(-1).reasoning_details[0].format='changed-format';},
    p=>{p.messages.at(-1).reasoning_details[0].id='changed-id';},
    p=>{p.messages.at(-1).reasoning_details[0].index=42;},
    p=>{p.messages.at(-1).reasoning_details.push({...details[0]});},
    p=>{p.messages.at(-1).role='tool';},
    p=>{p.messages.at(-1).content=details[0].data;p.messages.at(-1).reasoning_details=[];},
  ]){
    const after=structuredClone(before);after.messages.push({role:'assistant',content:'A reply.',reasoning_details:structuredClone(details)});mutate(after);
    const estimate=wireEstimate(after),r=inputContextEstimate(inputContextSnapshot(after,estimate),estimate,anchor);
    assert.equal(r.method,'receipt_plus_append_bound');assert.ok(r.upperBound>400000);
  }
  for(const bad of [undefined,-1,5200.5,900000]){
    const message=structuredClone(output);message.usage.output=bad;
    const after=structuredClone(before);after.messages.push({role:'assistant',content:'Reply.',reasoning_details:details});
    const estimate=wireEstimate(after),r=inputContextEstimate(inputContextSnapshot(after,estimate),estimate,receipt(before,message));
    assert.equal(r.method,'receipt_plus_append_bound');assert.ok(r.upperBound>400000);
  }
  const after=structuredClone(before);after.messages.push({role:'assistant',content:'Reply.',reasoning_details:details},
    {role:'assistant',content:'Copied again.',reasoning_details:details});
  const estimate=wireEstimate(after),r=inputContextEstimate(inputContextSnapshot(after,estimate),estimate,anchor);
  assert.equal(r.encrypted_replay_bytes,400000);assert.ok(r.upperBound>400000,'only the immediate measured response can receive credit');
});
