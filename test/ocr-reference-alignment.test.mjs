import test from 'node:test';
import assert from 'node:assert/strict';
import {alignOCRReferences} from '../src/ocr-reference-alignment.mjs';

const frames=entries=>new Map([['i3',{page:3,ocrTexts:Object.fromEntries(entries.map((r,i)=>[`i3.r${i+1}`,r.text])),
  regions:entries.map((r,i)=>({id:`i3.r${i+1}`,rect:{x:.3,y:.2+i*.035,width:.3,height:.03,...r.rect}}))}]]);
test('unique long OCR excerpt can correct an adjacent ID without changing judgment or quote',()=>{
  for(const [quote,text] of [['k=7z²+8z−9','=7z2+8z-9'],['pressure = 147.25 kPa','147.25 kPa'],['Code = Delta 9081','Delta 9081']]){
    const f=frames([{text:'An unrelated preceding calculation'},{text}]);
    const point={evidence:quote,student_pages:[3],score:0,reason:'Original error'},before=structuredClone(point);
    const result=alignOCRReferences('i3.r1',point,f);
    assert.deepEqual(result.references,['i3.r2']);assert.deepEqual(point,before);
    assert.deepEqual(result.resolution.original_reference_ids,['i3.r1']);
  }
});
test('short, duplicated, foreign-page and unclear strings never force a relocation',()=>{
  const f=frames([{text:'unrelated'},{text:'Delta 9081'},{text:'Delta 9081'}]);
  for(const evidence of ['D=Delta 9081','D=9','[unclear]'])assert.equal(alignOCRReferences('i3.r1',{evidence,student_pages:[3]},f).references,'i3.r1');
  assert.equal(alignOCRReferences('i3.r1',{evidence:'D=Delta 9081',student_pages:[8]},f).references,'i3.r1');
});
test('numeric evaluation follows separate contiguous calculation lines, stopping at a new variable',()=>{
  for(const [symbol,value] of [['g',7],['H',-2],['k',3.5]]){
    const f=frames([{text:`${symbol}(${value}) = 4*2`},{text:'= 8-3'},{text:'= 5'},{text:'y = 12'}]);
    const p={evidence:`${symbol}(${value})=5`,student_pages:[3],score:1};
    assert.deepEqual(alignOCRReferences('i3.r1',p,f).references,['i3.r1','i3.r2','i3.r3']);
  }
  const f=frames([{text:'g(7)=5'},{text:'= 8-3'},{text:'=5'}]);
  assert.equal(alignOCRReferences('i3.r1',{evidence:'g(7)=5',student_pages:[3]},f).references,'i3.r1');
  const newVariable=frames([{text:'g(7)=8-3'},{text:'x=12'},{text:'=5'}]);
  assert.equal(alignOCRReferences('i3.r1',{evidence:'g(7)=5',student_pages:[3]},newVariable).references,'i3.r1');
});
test('a split fraction adds only its overlapping narrow denominator, never the next equation',()=>{
  const f=frames([{text:'= z+5'},{text:'(z-7)',rect:{x:.4,y:.225,width:.12,height:.02}}]);
  assert.deepEqual(alignOCRReferences('i3.r1',{evidence:'(z+5)/(z-7)',student_pages:[3]},f).references,['i3.r1','i3.r2']);
  for(const text of ['=8','next question']){
    const other=frames([{text:'= z+5'},{text,rect:{x:.4,y:.225,width:.12,height:.02}}]);
    assert.equal(alignOCRReferences('i3.r1',{evidence:'(z+5)/(z-7)',student_pages:[3]},other).references,'i3.r1');
  }
});


test('composite quotes retain the original clause and can include a uniquely supported margin companion',()=>{
  const f=frames([{text:'UV . UW = 0'},{text:'7(t+2)+3t-8=0'}]);
  const r=alignOCRReferences('i3.r1',{evidence:'UV·UW=0; 7(t+2)+3t-8=0',student_pages:[3]},f);
  assert.deepEqual(r.references,['i3.r1','i3.r2']);
  const margin=frames([{text:'Let v=-z? | dv=-2z dz',rect:{x:.8,width:.1}},
    {text:'= J e"dv',rect:{x:.3,y:.204,width:.3}}]);
  const p={evidence:'∫ eᵛdv, v=-z²',student_pages:[3],score:0};
  assert.deepEqual(alignOCRReferences('i3.r1',p,margin).references,['i3.r1','i3.r2']);
  const wrong=structuredClone(margin);wrong.get('i3').ocrTexts['i3.r2']='different words';
  assert.equal(alignOCRReferences('i3.r1',p,wrong).references,'i3.r1');
});
