import test from 'node:test';
import assert from 'node:assert/strict';
import {compactGradingMark,occupancyFromRgba,occupancyFromPacked,inkFree,layoutGradingMarks,relatedGradingNotes,commentFootprints} from '../web/annotation-layout.mjs';
import {hitSelection} from '../web/canvas-selection.mjs';
import {placeExportMarks} from '../src/workspace/annotation-export.mjs';
import {gradingCard} from '../web/annotation-card.mjs';

const rect=(x=.2,y=.3,width=.3,height=.03)=>({x,y,width,height});
const note=(id='one',region=rect(),score=1)=>({id,source:'grading',score,maximum:1,pointId:'M1',regions:[{pageId:'p',pageHash:'hash',rect:region}]});
const overlap=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
const pixels=(width,height)=>new Uint8ClampedArray(width*height*4).fill(255);

test('compact marks use awarded marks, not the criterion ordinal; partial and unknown stay explicit',()=>{
  assert.deepEqual(compactGradingMark({pointId:'M2',score:1,maximum:1}),{text:'1M',tone:'credit',type:'M'});
  assert.equal(compactGradingMark({pointId:'a3',score:0,maximum:1}).text,'×A');
  assert.equal(compactGradingMark({awardType:'M',score:1,maximum:2}).text,'1/2M');
  assert.equal(compactGradingMark({score:1,maximum:1}).text,'✓');
  assert.deepEqual(compactGradingMark({pointId:'M1',score:null,maximum:1}),{text:'?M',tone:'review',type:'M'});
});

test('full-resolution occupancy retains isolated faint and coloured ink; transparent ink does not block white',()=>{
  const width=773,height=1103,data=pixels(width,height);
  const dot=(x,y,rgba)=>data.set(rgba,(y*width+x)*4);
  dot(33,77,[244,244,244,255]);dot(99,101,[255,0,255,255]);dot(150,150,[0,0,0,0]);
  const mask=occupancyFromRgba(data,width,height);
  assert.equal(mask.cellSize,3);
  for(const [x,y] of [[33,77],[99,101]])assert.equal(inkFree(mask,{x:x/width,y:y/height,width:1/width,height:1/height}),false);
  assert.equal(inkFree(mask,{x:150/width,y:150/height,width:1/width,height:1/height}),true);
  assert.equal(inkFree(null,rect()),false);
});

test('one badge per point avoids source ink, every evidence box, other badges, and manual circles',()=>{
  const width=700,height=1000,data=pixels(width,height);
  // Print a dense obstruction to the right of the upper writing step.
  for(let y=270;y<380;y++)for(let x=350;x<440;x++)data.set([0,0,0,255],(y*width+x)*4);
  const mask=occupancyFromRgba(data,width,height),rows=[note('a'),note('b',rect(.2,.35),0),note('c',rect(.2,.4))];
  rows[0].regions.push({...rows[0].regions[0],rect:rect(.6,.6,.15,.03)});
  const before=structuredClone(rows),obstacles=[rect(.08,.25,.1,.2)];
  const marks=layoutGradingMarks(rows,mask,{width,height,obstacles});
  assert.equal(marks.length,rows.length);assert.ok(marks.every(p=>p.mode==='inline'));
  for(const mark of marks){
    assert.ok(inkFree(mask,mark.rect));
    for(const r of [...rows.flatMap(n=>n.regions.map(r=>r.rect)),...obstacles])assert.equal(overlap(r,mark.rect),false);
    for(const other of marks)if(other!==mark)assert.equal(overlap(other.rect,mark.rect),false);
  }
  assert.deepEqual(rows,before);
  assert.deepEqual(layoutGradingMarks([...rows].reverse(),mask,{width,height,obstacles}),marks);
});

test('missing or solid masks use distinct external slots, including multiple columns for dense pages',()=>{
  const rows=Array.from({length:40},(_,i)=>note(`point-${i}`,rect(.1,.8,.6,.06)));
  const marks=layoutGradingMarks(rows,null,{width:400,height:300});
  assert.equal(marks.length,40);assert.ok(marks.every(m=>m.mode==='margin'&&m.rect.x>1));
  assert.ok(marks.some(m=>m.marginColumn>0));
  for(const mark of marks)for(const other of marks)if(other!==mark)assert.equal(overlap(mark.rect,other.rect),false);
  const dark=new Uint8ClampedArray(400*300*4);for(let i=3;i<dark.length;i+=4)dark[i]=255;
  assert.ok(layoutGradingMarks([rows[0]],occupancyFromRgba(dark,400,300),{width:400,height:300}).every(m=>m.mode==='margin'));
});

test('shared-region choices bind the source and manifest; nearby and transitive regions never merge',()=>{
  const a=note('a'),b=note('b'),c=note('c',rect(.2,.5));
  for(const n of [a,b])Object.assign(n.regions[0],{regionId:'i1.r8',regionManifestHash:'manifest'});
  b.regions.push(c.regions[0]);
  assert.deepEqual(relatedGradingNotes(a,[a,b,c]).map(n=>n.id),['b']);
  for(const field of ['pageId','pageHash','regionManifestHash']){
    const foreign=structuredClone(b);foreign.regions[0][field]='foreign';
    assert.deepEqual(relatedGradingNotes(a,[a,foreign]),[]);
  }
});

test('shared-region card exposes individual, escaped point choices without opening all explanations',()=>{
  const row={...note('first'),mark:{text:'1M',tone:'credit'},label:'1a · M1',scoreLabel:'1 / 1 分',tone:'credit',reason:'Full criterion met.',
    target:{sourcePage:1},status:'已得分',location:'region',schemePageIds:[],studentPageIds:['p'],evidence:'x=1',sourceText:'Criterion'};
  const related=[{...row,id:'second',label:'1a · <A1>',mark:{text:'×A',tone:'deduction'},scoreLabel:'0 / 1 分'}];
  const html=gradingCard(row,{pages:[],pageId:'p',index:0,total:2,related});
  assert.match(html,/data-id="first"[^>]*aria-pressed="true"/);
  assert.match(html,/data-id="second"[^>]*aria-pressed="false"/);
  assert.match(html,/&lt;A1&gt;/);assert.doesNotMatch(html,/<A1>/);
  assert.equal((html.match(/class="grading-point-comparison"/g)||[]).length,1);
});

test('clicking overlapping source areas chooses the smaller step while manual lasso remains on top',()=>{
  const broad={id:'broad',generated:true,rect:rect(.1,.1,.7,.5)},step={id:'step',generated:true,rect:rect(.2,.2,.2,.04)};
  assert.equal(hitSelection([.25,.22],[step,broad],{width:700,height:1000}).id,'step');
  assert.equal(hitSelection([.25,.22],[{...broad,generated:false},step],{width:700,height:1000}).id,'broad');
});

test('export layout shares the ink-free algorithm and never drops unlocated comments',()=>{
  const mask=occupancyFromRgba(pixels(400,600),400,600),packed=Buffer.alloc(Math.ceil(mask.occupied.length/8));
  const metadata={...mask,pageHash:'source',occupiedBase64:packed.toString('base64')};delete metadata.prefix;delete metadata.occupied;
  const row=note('G1');row.mark=compactGradingMark(row);row.markPlacement={mode:'inline'};
  const packet={pages:[{id:'p',sha256:'source',notes:[row,{...note('G2'),regions:[],mark:{text:'?',tone:'review'}}]}]};
  placeExportMarks(packet,{p:metadata});
  assert.ok(packet.pages[0].notes.every(n=>!('markPlacement' in n)));
  const comment=packet.pages[0].notes[0].commentPlacement;
  assert.equal(comment.mode,'inline');assert.ok(comment.lines.length<=2);
  assert.equal(comment.lines.map(l=>l.text).join(' ').split(row.mark.text).length-1,1);
  assert.equal(packet.pages[0].notes[1].commentPlacement.mode,'continuation');
  assert.ok(commentFootprints(comment,700,1050).every(r=>inkFree(occupancyFromPacked(metadata,packed),r)));
  assert.throws(()=>placeExportMarks(packet,{p:{...metadata,pageHash:'changed'}}),/不一致/);
});
