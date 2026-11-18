import test from 'node:test';
import assert from 'node:assert/strict';
import { freezeRubric } from '../src/rubric-contract.mjs';

const scheme = {sha256:'synthetic', pages:[{page:1},{page:2},{page:3}]};
const item = (item_id, page=2) => ({item_id,question_id:'Section',max_score:2,
  criteria:'Accept either supported explanation.',source_pages:[page],related_item_ids:[],uncertainties:[]});
const freeze = (ids,items,rows = [{page:1,item_ids:[]},{page:2,item_ids:ids},{page:3,item_ids:[]}]) =>
  freezeRubric({items,source_inventory:rows,general_instructions:[],unresolved_notes:[]},scheme,new Set([1,2,3]));

test('independent printed parts retain their identities across subjects and label systems', () => {
  for (const ids of [['B(a)(i)','B(a)(ii)'],['B.2.α','B.2.β'],['阅读甲·第一问','阅读甲·第二问']]) {
    assert.deepEqual(freeze(ids,ids.map(id=>item(id))).artifact.items.map(row=>row.item_id),ids);
    assert.throws(()=>freeze(ids,[item('parent')]),/absent/);
    assert.throws(()=>freeze(ids,[item(ids[0])]),/Missing independently scored/);
  }
});

test('shared routes and jointly awarded criteria can retain one printed item across pages', () => {
  const row = {...item('Essay'),source_pages:[2,3]};
  assert.equal(freeze(['Essay'],[row]).artifact.items.length,1);
  assert.throws(()=>freeze(['Essay'],[item('Method A'),item('Method B')]),/absent/);
  assert.throws(()=>freeze(['Essay'],[item('Essay',3)]),/starting page/);
  assert.throws(()=>freeze([], [row], [{page:2,item_ids:['Essay']}]),/MS pages/);
  assert.throws(()=>freeze([], [row], [{page:1,item_ids:[]},{page:2,item_ids:['Essay']},{page:3,item_ids:['Essay']}]),/duplicate/);
});
