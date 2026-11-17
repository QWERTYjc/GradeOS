import test from 'node:test';
import assert from 'node:assert/strict';
import {gradingResult,totalText,resultDocument,resultMarkdown} from '../web/grading-result.mjs';
import {gradingSymbol,layoutGradingSymbols,occupancyMask,inkFree} from '../web/annotation-layout.mjs';
import {annotationExportPacket} from '../src/workspace/annotation-export.mjs';

function fixture(){
 const page={id:'p',sha256:'frozen-page',sourcePage:7},group={id:'s',label:'Student',pageIds:['p']};
 const record={id:'m',itemId:'2a',pointId:'m1',groupId:'s',score:1,maximum:1,reason:'Correct method',sourceText:'Supplied criterion',evidence:'Original transcript',studentPageIds:['p'],schemePageIds:[],originalHash:'frozen-grade'};
 return {pages:[page],groups:[group],documents:[],reviews:[],tasks:[{id:'t',kind:'grade',status:'needs_review',pages:[page],groups:[group],records:[record,{...record,id:'a',pointId:'a1',score:null,reason:'Check the final value'}]}]};
}
test('result document keeps unresolved marks explicit and uses only matching teacher reviews',()=>{
 const state=fixture(),before=structuredClone(state),result=gradingResult(state,'t','s');
 assert.equal(totalText(result),'已确定 1 / 2 · 1 项待定');assert.equal(result.items.length,1);
 assert.deepEqual(state,before);assert.equal(result.provisional,true);
 state.reviews.push({id:'stale',taskId:'t',recordId:'a',originalHash:'wrong',score:1,reason:'Do not use this'});
 assert.equal(gradingResult(state,'t','s').pending,1);
 state.reviews.push({id:'valid',taskId:'t',recordId:'a',originalHash:'frozen-grade',score:0,reason:'Teacher confirmed omission'});
 const reviewed=gradingResult(state,'t','s');assert.equal(totalText(reviewed),'1 / 2');
 const markdown=resultMarkdown(reviewed,state.pages);
 for(const text of ['Teacher confirmed omission','Check the final value','Supplied criterion','Original transcript','答卷页：7'])assert.ok(markdown.includes(text));
 assert.ok(!markdown.includes('Do not use this'));
 state.groups[0]={...state.groups[0],pageIds:['new']};assert.equal(gradingResult(state,'t','s'),null);
});
test('unknown maximum remains unknown and result links retain individual records and escaped text',()=>{
 const state=fixture();state.tasks[0].records[0].maximum=null;state.tasks[0].records[0].reason='<img onerror=bad>';
 const model=gradingResult(state,'t','s');assert.equal(model.maximum,null);assert.ok(!totalText(model).includes('/'));
 const html=resultDocument(model,state.pages);assert.match(html,/&lt;img onerror=bad&gt;/);assert.doesNotMatch(html,/<img/);
 assert.equal((html.match(/data-result-point=/g)||[]).length,2);assert.match(html,/data-id="grading-m-original"/);
});
test('symbols distinguish full, absent, partial and unresolved credit without inventing locations',()=>{
 assert.deepEqual([{score:1,maximum:1},{score:0,maximum:1},{score:1,maximum:2},{score:null,maximum:1}].map(n=>gradingSymbol(n).kind),['check','cross','partial','review']);
 const mask=occupancyMask({sourceWidth:700,sourceHeight:1000,cellSize:2,columns:350,rows:500},new Uint8Array(350*500));
 const notes=[{id:'g',score:1,maximum:1,regions:[{rect:{x:.2,y:.4,width:.3,height:.025}},{rect:{x:.2,y:.45,width:.3,height:.025}}]},{id:'missing',score:0,maximum:1,regions:[]}];
 const placed=layoutGradingSymbols(notes,mask,{width:700,height:1000});
 assert.equal(placed.length,1);assert.equal(placed[0].id,'g');assert.ok(inkFree(mask,placed[0].rect));assert.ok(placed[0].rect.width*700<=24);
 const black=occupancyMask(mask,new Uint8Array(350*500).fill(1));assert.equal(layoutGradingSymbols(notes,black,{width:700,height:1000}).length,0);
});

test('integrated reports retain qualitative feedback, interrupted state and the successor math renderer',()=>{
 const state=fixture();state.tasks[0].status='interrupted';state.tasks[0].records=[{...state.tasks[0].records[0],score:null,maximum:null,disposition:'feedback_only',reason:'Use $x^2$ in the explanation.'}];
 const model=gradingResult(state,'t','s');assert.equal(totalText(model),'定性反馈');assert.equal(model.pending,0);
 const html=resultDocument(model,state.pages),md=resultMarkdown(model,state.pages);
 assert.match(html,/report-math/);assert.match(html,/仅显示已保存结果/);assert.doesNotMatch(md,/定性反馈 分/);
 assert.equal(gradingSymbol(model.rows[0]),null);assert.equal(model.rows[0].mark.text,'评语');
});

test('required review keeps numeric proposals pending in browser and PDF until a matching review',()=>{
 for(const score of [0,1]){
  const state=fixture(),record=state.tasks[0].records[0];record.score=score;record.reviewRequired=true;
  const before=structuredClone(record);
  state.reviews.push({id:'stale',taskId:'t',recordId:'m',originalHash:'older-grade',score,reason:'Stale'});
  let row=gradingResult(state,'t','s').rows[0],note=annotationExportPacket(state,'t','s').pages[0].notes[0];
  assert.equal(row.score,score);assert.equal(row.mark.text,'?M');assert.equal(row.mark.tone,'review');
  assert.equal(gradingSymbol(row).kind,'review');assert.equal(note.symbol.kind,'review');assert.equal(note.mark.text,'?M');
  state.reviews.push({id:'confirmed',taskId:'t',recordId:'m',originalHash:record.originalHash,score,reason:'Confirmed'});
  row=gradingResult(state,'t','s').rows[0];note=annotationExportPacket(state,'t','s').pages[0].notes[0];
  assert.equal(row.mark.text,score?'1M':'×M');assert.equal(gradingSymbol(row).kind,score?'check':'cross');
  assert.equal(note.symbol.kind,score?'check':'cross');assert.deepEqual(record,before);
 }
});
