import test from 'node:test';
import assert from 'node:assert/strict';
import { splitInlineAnnotations, annotationEvidenceHash, decodeAnnotationRegions } from '../src/inline-annotations.mjs';
import { makeRecord } from '../src/workspace/store.mjs';

test('geometry is a separate transport field for positive, zero, and unavailable awards', () => {
  for (const award of [null, 0, 2]) for (const ref of [undefined, 'i2.r9', ['i2.r9','i2.r7'], [], 'i9.r3', [4,5,6,7]]) {
    const row = ['basis', award, 'Copper wire', [2], award === null ? 'q:u' : award ? 'm' : 'u:c', 'Original judgment'];
    const input = {items:[{id:'materials',p:[[...row,...(ref===undefined?[]:[ref])]]}]};
    const prior = structuredClone(input), split = splitInlineAnnotations(input);
    assert.deepEqual(input,prior);
    assert.deepEqual(split.grading.items[0].p[0],row);
    assert.deepEqual(split.annotations.get('["materials","basis"]'),ref);
  }
});

test('the PDF transform uses the native scan and a stale excerpt loses its box', () => {
  const point={score:1,point_id:'p',student_pages:[1],evidence:'Copper wire',reason:'Conductor'};
  const local={x:.25,y:.2,width:.3,height:.1};
  const page={page:1,sha256:'source',image_to_pdf:{x:.1,y:.2,width:.8,height:.7},source_page:7};
  const manifest='a'.repeat(64);
  const frames=new Map([['i1',{page:1,pageHash:'source',representation:'source_regions',regionManifestHash:manifest,
    regions:[{id:'i1.r3',rect:local}]}]]);
  const receipts=new Map([['i1',{page:1,role:'student',original_sha256:'source',annotation_frame:'i1',representation:'source_regions',
    region_manifest_sha256:manifest,image_hash:'delivered'}]]);
  point.annotation=decodeAnnotationRegions('i1.r3',point,{pages:[page]},frames,receipts);
  const [r]=point.annotation.regions;
  assert.equal(r.pdfPage,7);
  assert.deepEqual(r.pdfRect,{x:.1+.25*.8,y:.2+.2*.7,width:.3*.8,height:.1*.7});
  const oldHash=annotationEvidenceHash(point);
  point.evidence='Plastic sleeve';
  assert.notEqual(oldHash,annotationEvidenceHash(point));
  const record=makeRecord({id:'task',pages:[{id:'p1',sha256:'source'}]}, {id:'s',pageIds:['p1']},
    {item_id:'q'},point,{max_score:1},'grade','rubric');
  assert.deepEqual(record.annotationRegions,[]);
  assert.equal(record.annotationStatus,'stale');
});
