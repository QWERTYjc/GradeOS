import test from 'node:test';
import assert from 'node:assert/strict';
import {annotationExportPacket} from '../src/workspace/annotation-export.mjs';
import {Budget} from '../src/core.mjs';

function fixture(){
  const page={id:'page',role:'student',active:true,sha256:'source',sourceId:'upload',sourcePage:7,path:'/source/page.png'};
  const group={id:'student',label:'答卷',pageIds:['page']};
  const record={id:'r',groupId:'student',itemId:'2b',pointId:'method',score:null,maximum:1,evidence:'Visible work',reason:'Check the indicated symbol',sourceText:'Supplied criterion',studentPageIds:['page'],schemePageIds:[],reviewRequired:true,originalHash:'grade',annotationRegions:[{pageId:'page',pageHash:'source',rect:{x:.2,y:.3,width:.4,height:.1},contextRect:{x:.1,y:.2,width:.6,height:.3}}]};
  return {title:'Unit test',pages:[page],groups:[group],tasks:[{id:'task',kind:'grade',status:'needs_review',groups:[group],pages:[structuredClone(page)],records:[record]}],reviews:[],annotations:[],documents:[]};
}
test('PDF packet uses the same visible regions and latest review without altering saved judgments',()=>{
  const state=fixture();state.reviews=[{id:'checked',taskId:'task',recordId:'r',originalHash:'grade',score:0,reason:'Teacher comment'}];
  const before=structuredClone(state),packet=annotationExportPacket(state,'task','student');
  assert.equal(packet.pages[0].notes[0].score,'0 / 1 分');
  assert.equal(packet.pages[0].notes[0].reason,'Teacher comment');
  assert.deepEqual(packet.pages[0].notes[0].regions[0].rect,state.tasks[0].records[0].annotationRegions[0].contextRect);
  assert.equal(packet.pages[0].sourcePage,7);assert.deepEqual(state,before);
});
test('stale pages and repartitions block export while invalid locations remain unboxed comments',()=>{
  for(const change of [s=>s.pages[0].sha256='new',s=>s.groups[0]={...s.groups[0],pageIds:['different']}]){
    const state=fixture();change(state);assert.throws(()=>annotationExportPacket(state,'task','student'));
  }
  const state=fixture();state.tasks[0].records[0].annotationRegions[0].rect.x=NaN;
  const note=annotationExportPacket(state,'task','student').pages[0].notes[0];
  assert.equal(note.regions.length,0);assert.equal(note.score,'待定');assert.equal(note.location,'page');
});
test('each student has a separate cumulative cost cap and missing receipts retain their reserve',()=>{
  const budget=new Budget({cap:.1,scopeCap:.01,maxRequests:10});
  const first=budget.admit(.006,{budget_scope:'student-a'});
  assert.doesNotThrow(()=>budget.admit(.006,{budget_scope:'student-b'}));
  assert.throws(()=>budget.admit(.005,{budget_scope:'student-a'}),/Per-student budget/);
  budget.settle(first,{usage:{cost:{total:.002,totalFromProvider:false}}});
  assert.throws(()=>budget.admit(.005,{budget_scope:'student-a'}),/Per-student budget/);
  budget.settle(first,{usage:{cost:{total:.002,totalFromProvider:true}}});
  assert.doesNotThrow(()=>budget.admit(.007,{budget_scope:'student-a'}));
  assert.throws(()=>budget.admit(.002,{budget_scope:'student-a'}),/Per-student budget/);
  assert.equal(budget.requests.length,3);
});
