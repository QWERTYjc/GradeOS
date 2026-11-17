import {gradingAnnotations} from './grading-annotations.mjs';
import {escape as e,markdown} from './ui.mjs';

const sum=rows=>{
  const scored=rows.filter(r=>r.disposition!=='feedback_only');
  return {score:scored.reduce((n,r)=>n+(Number.isFinite(r.score)?r.score:0),0),
    maximum:scored.length&&scored.every(r=>Number.isFinite(r.maximum))?scored.reduce((n,r)=>n+r.maximum,0):null,
    pending:scored.filter(r=>r.score==null).length,feedbackOnly:!scored.length,hasFeedback:scored.length<rows.length};
};
export function gradingResult(state,taskId,groupId) {
  const task=state.tasks.find(t=>t.id===taskId),group=task?.groups?.find(g=>g.id===groupId);
  if(!group)return null;
  const rows=gradingAnnotations(state,taskId,groupId);if(!rows.length)return null;
  const items=[];
  for(const row of rows){let item=items.find(i=>i.id===row.itemId);if(!item){item={id:row.itemId,rows:[]};items.push(item);}item.rows.push(row);}
  return {taskId,groupId,student:group.label,rows,items:items.map(item=>({...item,...sum(item.rows)})),...sum(rows),
    provisional:task.status!=='completed',incomplete:!['completed','needs_review'].includes(task.status),guide:rows.find(r=>r.guide)?.guide||null};
}
export const totalText=result=>result.feedbackOnly?'定性反馈':`${result.pending?'已确定 ':''}${result.score}${result.maximum==null?'':` / ${result.maximum}`}${result.pending?` · ${result.pending} 项待定`:''}${result.hasFeedback?' · 另有定性反馈':''}`;
export const resultStatus=model=>model.incomplete?'批次未完成 · 仅显示已保存结果':model.provisional?'待老师审阅':'已完成审阅';

export function resultDocument(model,pages) {
  const sourceLinks=(row,ids,label)=>ids.map(id=>`<button data-pane-action="result-source" data-id="${e(id)}">${label} ${e(pages.find(p=>p.id===id)?.sourcePage??'')} 页 ↗</button>`).join('');
  return `<article class="result-document"><header><p class="result-eyebrow">${e(model.student)} · ${resultStatus(model)}</p><h1>批改结果</h1><div class="result-total"><strong>${e(totalText(model))}</strong>${model.feedbackOnly?'':'<span>分</span>'}</div><p>勾叉帮助定位作答；具体得分和判定依据在下方逐项保留。</p>${model.guide?`<p class="result-version">依据评分实施.md v${model.guide.revision}</p>`:''}</header>
    <nav class="result-outline" aria-label="逐题得分">${model.items.map(item=>`<button data-pane-action="result-item" data-id="${e(item.id)}"><span>${e(item.id)}</span><strong>${e(totalText(item))}</strong></button>`).join('')}</nav>
    ${model.items.map(item=>`<section class="result-item" data-item="${e(item.id)}"><h2><span>${e(item.id)}</span><span>${e(totalText(item))}${item.feedbackOnly?'':' 分'}</span></h2>${item.rows.map(row=>`<details class="result-point ${e(row.mark.tone)}" data-result-point="${e(row.id)}"><summary><span class="result-point-code">G${row.index} · ${e(row.pointId?.toUpperCase()||'评分点')}</span><strong>${e(row.scoreLabel)}</strong><span class="result-short-reason">${e(row.review?.reason||row.reason)}</span></summary><div class="result-point-body"><p>${e(row.status)}${row.review?' · 老师已复核':''}</p><h3>判定理由</h3><div class="prose">${markdown(row.review?.reason||row.reason)}</div><h3>对应评分要求</h3><div class="prose">${markdown(row.sourceText||'未提供评分要求')}</div><h3>模型转写 · 以原稿为准</h3><div class="prose">${markdown(row.evidence||'未发现可引用的作答')}</div>${row.locationNote?`<p class="result-location">${e(row.locationNote)}</p>`:''}${row.uncertainties?.map(text=>`<p class="result-location">待确认：${e(text)}</p>`).join('')||''}${row.review?`<p class="result-location">原判 ${e(row.originalScoreLabel)}：${e(row.reason)}</p>`:''}<div class="result-source-links">${row.target?`<button data-pane-action="result-point" data-id="${e(row.id)}">定位答卷 ↗</button>`:''}${sourceLinks(row,row.schemePageIds,'对照 MS')}${sourceLinks(row,row.questionPageIds,'题目')}<button data-pane-action="result-review" data-id="${e(row.recordId)}">老师复核</button></div></div></details>`).join('')}</section>`).join('')}</article>`;
}

export function resultMarkdown(model,pages) {
  const lines=[`# ${model.student} · 批改结果`,'',`得分：${totalText(model)}`,`状态：${resultStatus(model)}`,
    ...(model.guide?[`评分实施.md：v${model.guide.revision}`]:[]),'','## 逐题得分','','| 题目 | 得分 |','| --- | --- |',...model.items.map(item=>`| ${item.id} | ${totalText(item)} |`),''];
  for(const item of model.items){lines.push(`## ${item.id} · ${totalText(item)}${item.feedbackOnly?'':' 分'}`,'');for(const row of item.rows){
    lines.push(`### G${row.index} · ${row.label} · ${row.scoreLabel}`,'',row.review?.reason||row.reason,'',`评分要求：${row.sourceText||'未提供'}`,'',`模型转写（以原稿为准）：${row.evidence||'未发现可引用作答'}`,'',
      `答卷页：${row.studentPageIds.map(id=>pages.find(p=>p.id===id)?.sourcePage).join('、')||'未定位'}；MS 页：${row.schemePageIds.map(id=>pages.find(p=>p.id===id)?.sourcePage).join('、')||'未提供'}`,
      ...(row.locationNote?[row.locationNote]:[]),...row.uncertainties.map(text=>`待确认：${text}`),...(row.review?[`原判 ${row.originalScoreLabel}：${row.reason}`]:[]),'');
  }}return lines.join('\n');
}
