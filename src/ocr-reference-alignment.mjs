// Presentation-only alignment. It never receives a rubric or changes an award.
// Raw model references remain in the audit. Every resolved ID must still pass
// the original page/manifest/delivery checks in decodeAnnotationRegions.
const normalized=value=>String(value||'').normalize('NFKC').toLowerCase().replace(/[−–]/g,'-').replace(/[′’]/g,"'").replace(/\s+/g,'');
const distance=(a,b)=>{
  let row=Array.from({length:b.length+1},(_,i)=>i);
  for(let i=1;i<=a.length;i++){
    const next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(next[j-1]+1,row[j]+1,row[j-1]+(a[i-1]===b[j-1]?0:1));row=next;
  }
  return row[b.length];
};
const similarity=(a,b)=>a&&b?1-distance(a,b)/Math.max(a.length,b.length):0;
const overlap=(a,b)=>Math.max(0,Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x))/Math.min(a.width,b.width);
const shortText=value=>normalized(value).replace(/[^\p{L}\p{N}]/gu,'');
const excerptSupport=(query,text)=>{
  // A value-only fragment must match the equation's value, not accidental
  // characters spanning its prose label and its left-hand variable.
  const value=!query.includes('=')&&text.includes('=')?text.slice(text.indexOf('=')+1):text;
  const q=shortText(query),t=shortText(value);if(q.length<4)return 0;
  let best=0;
  for(let start=0;start<t.length;start++)for(let length=Math.max(3,q.length-1);length<=q.length+1;length++)
    best=Math.max(best,similarity(q,t.slice(start,start+length)));
  return best;
};
const continues=text=>{
  const s=normalized(text).replace(/\|/g,'');
  return s.length>0&&!/[a-z]{3,}/i.test(s)&&!/^\p{L}[\p{L}\d]*=/u.test(s);
};

export function alignOCRReferences(raw,point,frames) {
  const original=typeof raw==='string'?[raw]:raw;
  if(!Array.isArray(original)||original.length!==1||!/^i[1-9]\d*\.r[1-9]\d*$/.test(original[0]))return {references:raw};
  const frame=frames.get(original[0].split('.')[0]);
  if(!frame?.ocrTexts||!point.student_pages.includes(frame.page))return {references:raw};
  const rows=frame.regions.map(region=>({...region,text:frame.ocrTexts[region.id]||''}));
  let selected=rows.find(r=>r.id===original[0]);if(!selected)return {references:raw};
  const quote=normalized(point.evidence),actions=[];
  // Only explicit clauses count; commas inside a function/matrix do not.
  const clauses=[];let depth=0,start=0;
  for(let i=0;i<quote.length;i++){
    if('([{'.includes(quote[i]))depth++;
    if(')]}'.includes(quote[i]))depth=Math.max(0,depth-1);
    if(depth===0&&';,\n'.includes(quote[i])){clauses.push(quote.slice(start,i));start=i+1;}
  }
  clauses.push(quote.slice(start));
  let retained=[];
  // A concrete quoted RHS may uniquely identify a different OCR line. Require
  // a substantial margin over every alternative; short/ambiguous strings stay
  // untouched. Fuzzy matching changes location only, never the observed quote.
  const rhs=quote.includes('=')?quote.slice(quote.indexOf('=')+1):quote;
  const query=rhs.replace(/^=+/,'');
  if(query.length>=8&&query.length<=120){
    const ranked=rows.map(row=>({row,score:similarity(query,normalized(row.text).replace(/^=+/,''))}))
      .sort((a,b)=>b.score-a.score);
    const current=ranked.find(r=>r.row.id===selected.id).score;
    if(ranked[0].row.id!==selected.id&&ranked[0].score>=.85&&ranked[0].score-current>=.2&&ranked[0].score-(ranked[1]?.score||0)>=.1){
      if(clauses.length>1&&clauses.some(clause=>similarity(clause,normalized(selected.text))>=.65))retained=[selected.id];
      actions.push({kind:retained.length?'additional_quoted_line':'unique_ocr_excerpt',from:selected.id,to:ranked[0].row.id,similarity:ranked[0].score});selected=ranked[0].row;
    }
  }
  const resolved=[...retained,selected.id];
  if(clauses.length>1)for(const clause of clauses){
    const support=Math.max(...resolved.map(id=>excerptSupport(clause,rows.find(r=>r.id===id).text)));
    if(support>=.75)continue;
    const nearby=rows.filter(row=>!resolved.includes(row.id)
      &&Math.abs(row.rect.y+row.rect.height/2-selected.rect.y-selected.rect.height/2)<Math.max(row.rect.height,selected.rect.height)*.6
      &&overlap(row.rect,selected.rect)===0)
      .map(row=>({row,score:excerptSupport(clause,row.text)})).sort((a,b)=>b.score-a.score);
    if(nearby[0]?.score>=.75&&nearby[0].score-support>=.2&&nearby[0].score-(nearby[1]?.score||0)>=.15){
      resolved.push(nearby[0].row.id);actions.push({kind:'same_line_quoted_fragment',from:selected.id,to:nearby[0].row.id,similarity:nearby[0].score});
    }
  }
  const fraction=/[/⁄]/.test(quote);
  const evaluation=/^\p{L}[\p{L}'\d^]*\([-+\d.]+\)=/u.test(quote)
    &&!normalized(selected.text).split('=').slice(1).join('=').includes(rhs);
  let previous=selected;
  for(let step=0;step<(evaluation?2:fraction?1:0);step++){
    const candidates=rows.filter(row=>!resolved.includes(row.id)&&row.rect.y>previous.rect.y+.004
      &&row.rect.y-previous.rect.y-previous.rect.height<Math.min(.018,previous.rect.height*.8)
      &&overlap(row.rect,previous.rect)>=.6&&continues(row.text))
      .sort((a,b)=>a.rect.y-b.rect.y);
    const next=candidates[0];if(!next)break;
    // A split fraction shares vertical ink extent across the physical rule.
    // Separate neighboring equations do not qualify for this completion.
    if(!evaluation&&(next.rect.y>=previous.rect.y+previous.rect.height||/^=/.test(normalized(next.text))
      ||next.rect.width>previous.rect.width*.75))break;
    // No continuation past a nearer independent equation/prose in the column.
    if(rows.some(row=>row.id!==previous.id&&!resolved.includes(row.id)&&row.rect.y>previous.rect.y+.004
      &&row.rect.y<next.rect.y&&overlap(row.rect,previous.rect)>=.6&&!continues(row.text)))break;
    actions.push({kind:evaluation?'evaluation_continuation':'split_fraction',from:previous.id,to:next.id});
    resolved.push(next.id);previous=next;
  }
  return actions.length?{references:resolved,resolution:{original_reference_ids:original,resolved_reference_ids:resolved,actions,
    method:'local OCR excerpt alignment and contiguous local geometry; no model or score changes'}}:{references:raw};
}
