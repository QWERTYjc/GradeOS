import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareLunaAnnotationRequest } from '../src/luna-annotation-budget.mjs';
import { outputBudget } from '../src/output-budget.mjs';
import { rubricWireText } from '../src/guide-wire.mjs';

function page(width, height) {
  const header = Buffer.alloc(32);
  Buffer.from('89504e470d0a1a0a','hex').copy(header);
  header.write('IHDR',12); header.writeUInt32BE(width,16); header.writeUInt32BE(height,20);
  return {type:'image_url',image_url:{detail:'high',url:'data:image/png;base64,' + header.toString('base64')}};
}
test('Luna prices include the full serialized schema, page area and all remaining output', () => {
  const req = {model:'openai/gpt-6-luna',provider:{only:['openai'],allow_fallbacks:false},
    max_tokens:120000,messages:[{role:'user',content:[{type:'text',text:'teacher edit',cache_control:{type:'ephemeral'}},page(650,960)]}]};
  const prices={input:.1,output:.5}, model={maxTokens:120000,contextWindow:200000};
  const first=prepareLunaAnnotationRequest(req,prices);
  assert.equal(first.images,1); assert.equal(req.prompt_cache_options.mode,'explicit');
  assert.equal(req.messages[0].content[0].cache_control,undefined); assert.deepEqual(req.provider.max_price,{prompt:.1,completion:.5});
  req.messages[0].content.push(page(1100,1400));req.tools=[{description:'Additional frozen material '.repeat(200)}];
  const actual=prepareLunaAnnotationRequest(req,prices);
  assert.ok(actual.textTokens>first.textTokens && actual.imageTokenReserve>first.imageTokenReserve);
  const limit=outputBudget({model,payload:req,inputTokens:actual.inputTokenReserve,prices,available:.01});
  assert.ok(limit.tokens>0 && limit.reservation.input_usd+limit.reservation.output_usd<=.01);
  assert.throws(()=>prepareLunaAnnotationRequest({...req,model:'other'},prices),/route/);
});

test('compact rubric rows retain each field, unfamiliar fields and edited source wording',()=> {
  const a={point_id:'p',award_type:'M',max_score:2,allowed_awards:[0,2],source_pages:[3],depends_on:['precursor'],condition:'Use the value',source_text:'Use the value'};
  const source={items:[{item_id:'q',scoring_points:[a,{...a,source_text:'Allow another method'},{...a,future_field:'retain'}]}]};
  const wire=rubricWireText(source), data=JSON.parse(wire.slice(wire.indexOf('\n')+1));
  const columns=JSON.parse(wire.slice(wire.indexOf('['),wire.indexOf(']')+1));
  const decoded=data.items[0].scoring_points.map(row=>{if(!Array.isArray(row))return row;
    const point=Object.fromEntries(columns.map((name,index)=>[name,row[index]]));point.source_text??=point.condition;return point;});
  assert.deepEqual(decoded,source.items[0].scoring_points);
});
