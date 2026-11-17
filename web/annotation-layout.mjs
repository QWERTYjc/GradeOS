// Local presentation only: neither placement nor colour can award a mark.
export function compactGradingMark({score,maximum,pointId,awardType}={}) {
  const pointType=/^([MAB])\d*$/i.exec(String(pointId||''))?.[1].toUpperCase();
  const type=pointType||(/^[MAB]$/i.test(awardType||'')?awardType.toUpperCase():'');
  const tone=score==null?'review':maximum!=null&&score<maximum?'deduction':score===0?'deduction':'credit';
  const text=score==null?`?${type}`:score===0?`×${type}`:maximum!=null&&score<maximum?`${score}/${maximum}${type}`:type?`${score}${type}`:'✓';
  return {text,tone,type};
}

// A small ink-like symbol communicates the saved verdict, never a new award.
// The same normalized strokes are used by the screen and PDF renderers.
export function gradingSymbol(note) {
  if(note.disposition==='feedback_only')return null;
  if(note.symbol)return note.symbol;
  const kind=note.score==null?'review':note.score===0?'cross':note.maximum!=null&&note.score<note.maximum?'partial':'check';
  const paths={check:[[[2,10],[7,15],[18,3]]],cross:[[[5,5],[15,15]],[[15,5],[5,15]]],
    partial:[[[2,9],[6,13],[15,3]],[[12,17],[18,17]]],
    review:[[[5,6],[6,3],[10,2],[14,4],[14,7],[10,10],[10,12]],[[10,16],[10,16.2]]]};
  return {kind,label:{check:'得分',cross:'失分',partial:'部分得分',review:'待确认'}[kind],
    text:{check:'✓',cross:'×',partial:'±',review:'?'}[kind],tone:kind==='check'?'credit':kind==='cross'?'deduction':'review',paths:paths[kind],stroke:1.6};
}

export function symbolSvg(symbol) {
  return `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="${symbol.stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${symbol.paths.map(points=>`<path d="${points.map(([x,y],i)=>`${i?'L':'M'}${x} ${y}`).join(' ')}"/>`).join('')}</svg>`;
}

export function layoutGradingSymbols(notes,mask,options) {
  const size=clamp(options.width/44,10,20);
  const placements=layoutGradingMarks(notes.filter(note=>gradingSymbol(note)).map(note=>({...note,mark:gradingSymbol(note),
    regions:[...(note.regions||[])].sort((a,b)=>b.rect.width*b.rect.height-a.rect.width*a.rect.height)})),mask,{...options,fontSize:size,gap:clamp(options.width/350,1,3),regionPenalty:18,
      measureMark:()=>({width:size,height:size})});
  // A fully occupied page must never receive an invented in-answer position.
  // Its existing short verdict and explicit source link remain available.
  return placements.filter(p=>p.mode==='inline').map(p=>({...p,symbol:p.mark}));
}

export function occupancyMask({sourceWidth,sourceHeight,cellSize,columns,rows},occupied) {
  if(![sourceWidth,sourceHeight,cellSize,columns,rows].every(n=>Number.isSafeInteger(n)&&n>0)
    ||columns!==Math.ceil(sourceWidth/cellSize)||rows!==Math.ceil(sourceHeight/cellSize)
    ||occupied.length!==columns*rows)throw Error('Invalid page occupancy mask');
  const stride=columns+1,prefix=new Uint32Array(stride*(rows+1));
  for(let y=0;y<rows;y++) {
    let row=0;
    for(let x=0;x<columns;x++){row+=occupied[y*columns+x]?1:0;prefix[(y+1)*stride+x+1]=prefix[y*stride+x+1]+row;}
  }
  return {sourceWidth,sourceHeight,cellSize,columns,rows,occupied,prefix};
}

export function occupancyFromRgba(data,width,height) {
  if(data.length!==width*height*4)throw Error('Image pixels do not match the complete page');
  const cellSize=Math.max(1,Math.ceil(Math.max(width/384,height/768))),columns=Math.ceil(width/cellSize),rows=Math.ceil(height/cellSize);
  const occupied=new Uint8Array(columns*rows);
  for(let y=0;y<height;y++) {
    const row=Math.floor(y/cellSize)*columns;
    for(let x=0;x<width;x++) {
      const i=(y*width+x)*4,alpha=data[i+3]/255;
      // Conservative min pooling: even a single faint/coloured source pixel
      // blocks its cell. Transparency is composited onto white, as in print.
      if(Math.round(Math.min(data[i],data[i+1],data[i+2])*alpha+255*(1-alpha))<245)
        occupied[row+Math.floor(x/cellSize)]=1;
    }
  }
  return occupancyMask({sourceWidth:width,sourceHeight:height,cellSize,columns,rows},occupied);
}

export function occupancyFromPacked(metadata,packed) {
  const count=metadata.columns*metadata.rows;
  if(!Number.isSafeInteger(count)||count<1||count>384*768||packed.length!==Math.ceil(count/8))throw Error('Invalid packed page occupancy');
  return occupancyMask(metadata,Uint8Array.from({length:count},(_,i)=>(packed[i>>3]>>(i%8))&1));
}

export function inkFree(mask,rect) {
  if(!mask||rect.x<0||rect.y<0||rect.width<=0||rect.height<=0||rect.x+rect.width>1||rect.y+rect.height>1)return false;
  const {sourceWidth:sw,sourceHeight:sh,cellSize:c,columns,rows,prefix}=mask,stride=columns+1;
  const x1=Math.max(0,Math.floor(rect.x*sw/c)),y1=Math.max(0,Math.floor(rect.y*sh/c));
  const x2=Math.min(columns,Math.ceil((rect.x+rect.width)*sw/c)),y2=Math.min(rows,Math.ceil((rect.y+rect.height)*sh/c));
  return prefix[y2*stride+x2]-prefix[y1*stride+x2]-prefix[y2*stride+x1]+prefix[y1*stride+x1]===0;
}

const intersects=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
const expand=(r,dx,dy)=>({x:r.x-dx,y:r.y-dy,width:r.width+2*dx,height:r.height+2*dy});
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const valid=r=>r&&[r.x,r.y,r.width,r.height].every(Number.isFinite)&&r.x>=0&&r.y>=0&&r.width>0&&r.height>0&&r.x+r.width<=1.000001&&r.y+r.height<=1.000001;
const units=text=>[...text].reduce((sum,ch)=>sum+(/[MW✓×?]/.test(ch)?.95:/[AB]/.test(ch)?.8:/[ .\/]/.test(ch)?.4:.65),0);

export function markDimensions(mark,fontSize,reference='') {
  return {width:Math.ceil(units(mark.text)*fontSize+8+(reference?units(reference)*fontSize*.65+3:0)),height:Math.ceil(fontSize*1.15+2)};
}

// One compact badge per scoring point, not per box or per question. Never merge
// unrelated steps. Exhaust nearby white space before using an external gutter.
export function layoutGradingMarks(notes,mask,{width,height,fontSize=clamp(width/55,11,14),gap=4,obstacles=[],references=false,regionPenalty=0,measureMark=markDimensions}={}) {
  if(!(width>0&&height>0))return [];
  const rows=notes.map(note=>({...note,mark:note.mark||compactGradingMark(note),regions:(note.regions||[]).filter(r=>valid(r.rect))})).filter(n=>n.regions.length);
  const forbidden=[...obstacles,...rows.flatMap(n=>n.regions.map(r=>r.rect))].filter(valid);
  const rank=n=>Math.min(...n.regions.map(r=>r.rect.y));
  rows.sort((a,b)=>rank(a)-rank(b)||String(a.id).localeCompare(String(b.id)));
  const placed=[],dx=gap/width,dy=gap/height;
  for(const note of rows) {
    const reference=references?note.reference||note.id:'',size=measureMark(note.mark,fontSize,reference),bw=size.width/width,bh=size.height/height;
    const candidates=[];
    note.regions.forEach((region,regionIndex)=>{
      const r=region.rect,cy=r.y+r.height/2,baseY=cy-bh/2;
      // Small, symmetric offsets retain proximity without assuming line order
      // or that the student's steps are left-aligned.
      // Search between ruled lines as well as between handwriting blocks. A
      // whole-line jump can repeatedly land on the next printed rule.
      const offsets=[0];for(let offset=1;offset<=(size.height+gap)*2;offset++)offsets.push(-offset,offset);
      for(const vertical of offsets)for(const distance of [0,1,2,3]) {
        const extra=distance*8;
        for(const side of ['right','left'])candidates.push({region,regionIndex,
          rect:{x:side==='right'?r.x+r.width+(gap+extra)/width:r.x-(gap+extra)/width-bw,y:baseY+vertical/height,width:bw,height:bh},
          cost:extra+Math.abs(vertical)*1.2+(side==='left'?5:0)+regionIndex*(regionPenalty+.01)});
      }
      for(const shift of [0,1,-1])for(const side of ['below','above'])candidates.push({region,regionIndex,
        rect:{x:r.x+r.width/2-bw/2+shift*(size.width+gap)/width,y:side==='below'?r.y+r.height+dy:r.y-dy-bh,width:bw,height:bh},
        cost:14+Math.abs(shift)*(size.width+gap)+(side==='above'?3:0)+regionIndex*(regionPenalty+.01)});
    });
    candidates.sort((a,b)=>a.cost-b.cost||a.rect.y-b.rect.y||a.rect.x-b.rect.x);
    let chosen=candidates.find(c=>{
      const padded=expand(c.rect,dx/2,dy/2);
      return inkFree(mask,padded)&&!forbidden.some(r=>intersects(padded,r))&&!placed.some(p=>intersects(expand(p.rect,dx,dy),c.rect));
    });
    let mode='inline',marginColumn=0;
    if(!chosen) {
      mode='margin';const region=note.regions[0],r=region.rect;
      // Distinct gutter slots stay separate even on a crowded/fully inked page.
      const ideal=clamp((r.y+r.height/2)*height-size.height/2,0,Math.max(0,height-size.height));
      const ys=Array.from({length:Math.max(1,Math.ceil(height/(size.height+gap)))},(_,i)=>Math.min(Math.max(0,height-size.height),i*(size.height+gap)));
      ys.push(ideal);ys.sort((a,b)=>Math.abs(a-ideal)-Math.abs(b-ideal)||a-b);
      for(let column=0;!chosen;column++)for(const y of ys) {
        const rect={x:1+(8+column*(Math.max(64,size.width)+gap))/width,y:y/height,width:bw,height:bh};
        if(!placed.some(p=>intersects(expand(p.rect,dx,dy),rect))){chosen={rect,region,regionIndex:0};marginColumn=column;break;}
      }
    }
    placed.push({id:note.id,mark:note.mark,reference,fontSize,mode,marginColumn,rect:chosen.rect,sourceRect:chosen.region.rect,
      sourceRegionId:chosen.region.regionId||null,sourceIndex:chosen.regionIndex});
  }
  return placed;
}

export function sameEvidenceRegion(a,b) {
  if(a.pageId!==b.pageId||a.pageHash!==b.pageHash)return false;
  if(a.regionId&&b.regionId)return a.regionId===b.regionId&&a.regionManifestHash===b.regionManifestHash;
  return ['x','y','width','height'].every(k=>Math.abs(a.rect[k]-b.rect[k])<1e-8);
}

export function relatedGradingNotes(note,notes) {
  return notes.filter(other=>other.id!==note.id&&other.source==='grading'&&note.regions?.some(a=>other.regions?.some(b=>sameEvidenceRegion(a,b))));
}

export function markConnection(placement) {
  const a=placement.sourceRect,b=placement.rect;
  const x=clamp(b.x+b.width/2,a.x,a.x+a.width),y=clamp(b.y+b.height/2,a.y,a.y+a.height);
  return {from:[x,y],to:[clamp(x,b.x,b.x+b.width),clamp(y,b.y,b.y+b.height)]};
}

export function clearMarkConnection(mask,placement,width,height) {
  const line=markConnection(placement),[ax,ay]=line.from,[bx,by]=line.to;
  const length=Math.hypot((bx-ax)*width,(by-ay)*height),steps=Math.ceil(length/2);
  if(length<5||!mask)return null;
  for(let i=2;i<steps-1;i++) {
    const x=ax+(bx-ax)*i/steps,y=ay+(by-ay)*i/steps;
    if(x>=1)continue; // external paper gutter contains no source pixels
    if(!inkFree(mask,{x:x-1/width,y:y-1/height,width:2/width,height:2/height}))return null;
  }
  return line;
}

// A distant mark must never become an unexplained floating symbol. The short
// elbow candidates prefer white space; the end points always identify the
// precise cited box, including when the paper border must be crossed.
export function gradingConnection(mask,placement,width,height,{threshold=24}={}) {
  const line=markConnection(placement),[a,b]=[line.from,line.to];
  const distance=Math.hypot((b[0]-a[0])*width,(b[1]-a[1])*height);
  if(distance<=threshold)return null;
  const options=[[a,b],[a,[b[0],a[1]],b],[a,[a[0],b[1]],b]];
  const crossing=path=>path.slice(1).reduce((sum,end,i)=>{
    const start=path[i],n=Math.ceil(Math.hypot((end[0]-start[0])*width,(end[1]-start[1])*height)/2);
    for(let k=1;k<n;k++){
      const x=start[0]+(end[0]-start[0])*k/n,y=start[1]+(end[1]-start[1])*k/n;
      if(x>=1)continue;
      if(!inkFree(mask,{x:x-.5/width,y:y-.5/height,width:1/width,height:1/height}))sum++;
    }
    return sum;
  },0);
  options.sort((a,b)=>crossing(a)-crossing(b));
  return {points:options[0],distance,threshold};
}

// Quote the saved verdict, never the MS or model transcription. Long verdicts
// get an explicit excerpt; the complete, unchanged record opens on click.
export function briefPointReason(note) {
  const text=String(note.review?.reason||note.reason||note.text||'').replace(/^原批改判定：/,'').replace(/\s+/g,' ').trim();
  if(!text)return '暂无判定理由，查看详情';
  const chars=[...text];
  if(chars.length<=96)return text;
  const prefix=chars.slice(0,93).join(''),boundary=prefix.lastIndexOf(' ');
  return (boundary>prefix.length*.6?prefix.slice(0,boundary):prefix).trimEnd()+'…';
}

export function pointCommentContent(note) {
  // Without handwriting to identify the step, retain its short question/point
  // label (also useful for several otherwise identical "no response" reasons).
  return [{kind:'reason',text:[note.mark?.text,note.regions?.length?null:note.label,briefPointReason(note)].filter(Boolean).join(' · ')}];
}

// Ink is never erased or classified away. On ruled paper, only the TEXT lines
// fit between existing rules; the comment has no opaque rectangular backdrop.
// Measuring each line also keeps its painted area out of handwriting/diagrams.
export function writingLineSpacing(mask,height) {
  if(!mask)return null;
  const bands=[];
  for(let y=0;y<mask.rows;y++){
    let count=0;for(let x=0;x<mask.columns;x++)count+=mask.occupied[y*mask.columns+x];
    if(count<mask.columns*.55)continue;
    const last=bands.at(-1);if(last&&y===last[1]+1)last[1]=y;else bands.push([y,y]);
  }
  const centers=bands.filter(([a,b])=>b-a<=5).map(([a,b])=>(a+b)/2);
  const gaps=centers.slice(1).map((y,i)=>y-centers[i]).filter(d=>d>=5&&d<=mask.rows*.07).sort((a,b)=>a-b);
  if(gaps.length<5)return null;
  const median=gaps[Math.floor(gaps.length/2)];
  if(gaps.filter(d=>Math.abs(d-median)<median*.15).length<5)return null;
  return median*mask.cellSize/mask.sourceHeight*height;
}

function wrapComment(note,limit,fontSize,lineHeight,measureText) {
  const lines=[],padding=3;
  for(const part of pointCommentContent(note))for(const paragraph of part.text.split(/\n/)){
    let line='';
    const push=()=>{if(line.trim())lines.push({kind:part.kind,text:line.trim(),width:measureText(line.trim(),part.kind)});line='';};
    for(const token of paragraph.split(/(\s+)/).filter(Boolean)){
      if(!line&&/^\s+$/.test(token))continue;
      if(measureText(line+token,part.kind)<=limit-padding*2){line+=token;continue;}
      push();
      if(measureText(token,part.kind)<=limit-padding*2){line=token.trimStart();continue;}
      for(const ch of token){if(line&&measureText(line+ch,part.kind)>limit-padding*2)push();line+=ch;}
    }
    push();
  }
  const originalLength=lines.reduce((n,line)=>n+line.text.length,0),truncated=lines.length>2;
  if(truncated){
    lines.splice(2);
    const last=lines.at(-1),chars=[...last.text];
    while(chars.length&&measureText(chars.join('')+'…',last.kind)>limit-padding*2)chars.pop();
    let excerpt=chars.join('').trimEnd();
    // Keep whole Latin words when possible; CJK and mathematical strings can
    // end at a character boundary. The full saved verdict is never modified.
    if(chars.length<last.text.length&&/[A-Za-z]$/.test(excerpt)&&excerpt.lastIndexOf(' ')>excerpt.length*.5)
      excerpt=excerpt.slice(0,excerpt.lastIndexOf(' '));
    last.text=excerpt+'…';last.width=measureText(last.text,last.kind);
  }
  const omitted=Math.max(0,originalLength-lines.reduce((n,line)=>n+line.text.length,0));
  const h=fontSize*1.25;
  return {fontSize,lineHeight,truncated,omitted,width:Math.max(42,...lines.map(l=>l.width))+padding*2,
    height:padding*2+Math.max(0,lines.length-1)*lineHeight+h,
    lines:lines.map((line,i)=>({...line,x:padding,y:padding+i*lineHeight,height:h}))};
}

export function commentFootprints(placement,width,height) {
  return placement.lines.map(line=>({x:placement.rect.x+line.x/width,y:placement.rect.y+line.y/height,
    width:line.width/width,height:line.height/height}));
}

// Search all nearby white space, on BOTH sides and above/below the actual
// fragments. If the source is genuinely packed, flow into a bottom continuation
// without stealing any of the original page's width or covering source ink.
export function layoutPointComments(notes,mask,{width,height,fontSize=clamp(width/62,11,13),gap=7,obstacles=[],measureText}={}) {
  if(!(width>0&&height>0))return [];
  measureText??=(text)=>[...text].reduce((n,c)=>n+fontSize*(/[^\x00-\xff]/.test(c)?1:/[il.,' ]/.test(c)?.28:.56),0);
  const rule=writingLineSpacing(mask,height),leading=fontSize*1.45;
  const lineHeights=[leading,...(rule>fontSize*1.4&&rule<fontSize*3.5&&Math.abs(rule-leading)>1?[rule]:[])];
  const preferred=clamp(width*.28,160,240),widths=[preferred,clamp(preferred*.72,120,180),clamp(preferred*1.35,210,310)];
  const rows=notes.map(note=>({...note,regions:(note.regions||[]).filter(r=>valid(r.rect))}));
  rows.sort((a,b)=>(a.regions[0]?.rect.y??1)-(b.regions[0]?.rect.y??1)||String(a.id).localeCompare(String(b.id)));
  const forbidden=[...obstacles,...rows.flatMap(n=>n.regions.map(r=>r.rect))],placed=[];
  for(const note of rows){
    const variants=widths.flatMap(w=>lineHeights.map(h=>wrapComment(note,w,fontSize,h,measureText)));
    let best=null;
    const sources=note.regions.length?note.regions.map(r=>r.rect):[{x:.15,y:.12,width:.7,height:.01}];
    // Unlocated notes must not be planted among other, located answers. On an
    // entirely unlocated page they may use measured whitespace, without a box
    // or a connector pretending to identify handwriting.
    for(const variant of note.regions.length||rows.every(n=>!n.regions.length)?variants:[]){
      if(variant.width>width-8||variant.height>height-8)continue;
      const bw=variant.width/width,bh=variant.height/height;
      const ys=[];for(let y=4;y<=height-variant.height-4;y+=3)ys.push(y);
      sources.forEach(r=>ys.push(clamp((r.y+r.height/2)*height-variant.height/2,4,height-variant.height-4),clamp((r.y+r.height)*height+gap,4,height-variant.height-4)));
      const ideal=sources[0].y*height;
      ys.sort((a,b)=>Math.abs(a+variant.height/2-ideal)-Math.abs(b+variant.height/2-ideal));
      const xs=[];for(let x=4;x<=width-variant.width-4;x+=8)xs.push(x);
      sources.forEach(r=>xs.push(clamp((r.x+r.width)*width+gap,4,width-variant.width-4),clamp(r.x*width-gap-variant.width,4,width-variant.width-4)));
      for(const y of ys)for(const x of xs){
        const rect={x:x/width,y:y/height,width:bw,height:bh};
        const nearest=sources.map(sourceRect=>{const c=markConnection({sourceRect,rect});return{sourceRect,distance:Math.hypot((c.to[0]-c.from[0])*width,(c.to[1]-c.from[1])*height)};}).sort((a,b)=>a.distance-b.distance)[0];
        const cost=nearest.distance+Math.abs(y+variant.height/2-(nearest.sourceRect.y+nearest.sourceRect.height/2)*height)*.18+variant.height*.06
          +(variant.truncated?24+variant.omitted*.6:0);
        if(best&&cost>=best.cost)continue;
        const padded=expand(rect,gap/width/2,gap/height/2);
        if(forbidden.some(r=>intersects(padded,r))||placed.some(p=>intersects(padded,p.rect)))continue;
        const candidate={...variant,id:note.id,mark:note.mark,rect,sourceRect:note.regions.length?nearest.sourceRect:null,mode:'inline',cost};
        if(!commentFootprints(candidate,width,height).every(r=>inkFree(mask,expand(r,1/width,1/height))))continue;
        best=candidate;
      }
    }
    if(!best){
      const variant=variants[0],bw=variant.width/width,bh=variant.height/height;
      const sourceRect=note.regions[0]?.rect||null;
      const xs=[];for(let x=4;x<=width-variant.width-4;x+=variant.width+gap)xs.push(x);
      if(!xs.length)xs.push(4);
      const ys=[height+18,...placed.filter(p=>p.mode==='continuation').map(p=>(p.rect.y+p.rect.height)*height+gap)];
      outer:for(const y of ys)for(const x of xs){
        const rect={x:x/width,y:y/height,width:bw,height:bh};
        if(!placed.some(p=>intersects(expand(rect,gap/width/2,gap/height/2),p.rect))){best={...variant,id:note.id,mark:note.mark,sourceRect,mode:'continuation',rect};break outer;}
      }
    }
    placed.push(best);
  }
  return placed;
}
