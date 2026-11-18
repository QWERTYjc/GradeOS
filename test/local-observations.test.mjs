import test from 'node:test';
import assert from 'node:assert/strict';
import {localObservationHint} from '../src/local-observations.mjs';

test('local optical hints bind to source bytes and retain alternatives without repairing math',()=>{
  const page={page:3,sha256:'source'},observations={page:3,source_sha256:'source',rows:[
    {rect:[.77,.414,.06,.012],candidates:[{text:'u = -x?'},{text:'u = -x²'}]},
    {rect:[.331,.517,.132,.026],candidates:[{text:'= 2e - 1'}]},
  ]};
  const before=structuredClone(observations),text=localObservationHint(page,observations);
  assert.match(text,/u = -x\? \/ alternative: u = -x²/);
  assert.match(text,/= 2e - 1/);assert.doesNotMatch(text,/2\/e/);
  assert.deepEqual(observations,before);
  assert.doesNotMatch(localObservationHint(page,observations),/i3\.[A-J]\d/);
  assert.throws(()=>localObservationHint({...page,sha256:'changed'},observations),/Unbound/);
  assert.throws(()=>localObservationHint({...page,page:4},observations),/Unbound/);
  const bad=structuredClone(observations);bad.rows[0].rect[0]=-.1;
  assert.throws(()=>localObservationHint(page,bad),/bounds/);
  assert.equal(localObservationHint(page,null),null);
});
