import test from 'node:test';
import assert from 'node:assert/strict';
import {studentRubricText} from '../src/rubric-contract.mjs';

test('rubric presentation round trips exact source text, dependencies and alternatives',()=>{
 for(const condition of ['Accept either route, but never combine their credit.','矩阵须可逆；零值不允许。']){
  const original={unresolved_notes:[],general_instructions:[{source_text:'Preserve source-only global instructions.'}],
   items:[{item_id:'unrelated-item',related_item_ids:[],uncertainties:[],routes:[{point_ids:['first','last']}],scoring_points:[
    {point_id:'first',condition,source_text:condition,depends_on:[],allowed_awards:[0,.5,1],source_pages:[2]},
    {point_id:'last',condition:'A distinct interpretation.',source_text:'Do not infer equivalence.',depends_on:['first'],allowed_awards:[0,2],source_pages:[3]}]}]};
  const before=structuredClone(original),text=studentRubricText(original),wire=JSON.parse(text.slice(text.indexOf('\n')+1));
  function restore(value,shape){
   if(Array.isArray(shape))return value.map((v,i)=>restore(v,shape[i]));
   if(shape&&typeof shape==='object')return Object.fromEntries(Object.entries(shape).map(([k,v])=>{
    if(Object.hasOwn(value,k))return [k,restore(value[k],v)];
    if(k==='source_text')return [k,value.condition];
    assert.ok(['depends_on','related_item_ids','uncertainties'].includes(k));assert.deepEqual(v,[]);return [k,[]];
   }));
   return value;
  }
  assert.deepEqual(restore(wire,original),original);assert.deepEqual(original,before);
  assert.equal(wire.items[0].scoring_points[1].source_text,'Do not infer equivalence.');
  assert.deepEqual(wire.items[0].scoring_points[1].depends_on,['first']);
  assert.ok(!Object.hasOwn(wire.items[0].scoring_points[0],'source_text'));
 }
});
