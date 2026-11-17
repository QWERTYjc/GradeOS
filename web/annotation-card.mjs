import {escape as e,icon,uncertaintyView} from './ui.mjs';

export function gradingCard(row,{pages,pageId,index,total,related=[]}) {
  const links=(ids,label)=>ids.map(id=>`<button type="button" data-note-action="source" data-id="${e(id)}">${label} · ${e(pages.find(page=>page.id===id)?.sourcePage)} 页 ${icon('right')}</button>`).join('');
  const reason=row.review?.reason||row.reason.replace(/^原批改判定：/,'');
  const generic=!row.review&&['Full criterion met.','满足该评分点。'].includes(reason);
  const explanation=row.review?'老师复核':row.tone==='deduction'?'扣分说明':row.tone==='review'?'待核实说明':'判定说明';
  return `<div class="annotation-heading"><span>评分批注 <i>·</i> 第 ${e(row.target.sourcePage)} 页</span><button type="button" data-note-action="close" aria-label="收起注释">${icon('close')}</button></div>
    <div class="grading-note-title ${e(row.tone)}"><div><h3>${e(row.label)}</h3><span class="grading-note-status">${e(row.review?'老师已复核':row.status)}</span></div><strong class="grading-score">${e(row.scoreLabel)}</strong></div>
    ${related.length?`<div class="grading-shared-points"><span>同一处笔迹</span>${[row,...related].map(point=>`<button type="button" class="${e(point.mark?.tone||point.tone)}" data-note-action="point" data-id="${e(point.id)}" aria-label="查看 ${e(point.label)}，${e(point.scoreLabel)}" aria-pressed="${point.id===row.id}">${e(point.mark?.text||point.scoreLabel)} <small>${e(point.label)}</small></button>`).join('')}</div>`:''}
    <div class="grading-note-body">${row.basisLabel?`<p class="grading-basis">${e(row.basisLabel)}</p>`:''}
      ${generic?'':`<section class="grading-explanation"><h4>${explanation}</h4><p class="grading-verdict">${e(reason)}</p></section>`}
      ${uncertaintyView(row)}
      <div class="grading-point-comparison"><section class="grading-evidence"><h4>模型转写 · 以高亮原稿为准</h4><p>${e(row.evidence||'未提供可引用证据，需核对答卷。')}</p></section>
        <section class="grading-criterion"><h4>对应评分要求</h4><p>${e(row.sourceText||'未提供，需核对 MS。')}</p></section></div>
      ${row.locationNote?`<p class="grading-location-note">${e(row.locationNote)}</p>`:row.location!=='region'?'<p class="grading-location-note">已关联到本页，尚未定位具体笔迹。</p>':''}
      <details class="grading-details"><summary>版本与记录 ${icon('down')}</summary><div>
        ${row.review||generic?`<section><h4>原始判定 · ${e(row.originalScoreLabel)}</h4><p>${e(row.reason)}</p></section>`:''}
        <p class="grading-note-provenance">${row.guide?`采用评分实施.md v${row.guide.revision} · `:''}来自已保存的批改结果${row.location==='region'?`<br>关联 ${row.regions.length} 处笔迹`:''}</p>
      </div></details>
    </div>
    <div class="grading-source-links">${links(row.schemePageIds,'对照 MS')}${links(row.questionPageIds||[],'题目')}${links(row.studentPageIds.filter(id=>id!==pageId),'答卷')}</div>
    <div class="annotation-actions"><button type="button" data-note-action="reference">${icon('message')}添加到对话</button><button type="button" class="grading-review-action" data-note-action="review">审阅评分 ${icon('right')}</button></div>
    <div class="grading-note-navigation"><span>本页 <strong>${index+1}</strong> / ${total}</span><div><button type="button" data-note-action="previous" aria-label="上一条评分批注" ${index===0?'disabled':''}>${icon('left')}</button><button type="button" data-note-action="next" aria-label="下一条评分批注" ${index===total-1?'disabled':''}>${icon('right')}</button></div></div>`;
}
