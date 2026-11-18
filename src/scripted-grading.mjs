import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createStudentAgent, StudentRegistry } from './cohort-core.mjs';
import { digest, validateGrade } from './core.mjs';
import { freezeJson, readImage } from './cohort-runtime.mjs';
import { exceptionTargets } from './exception-review.mjs';
import { validatePointDecisions } from './rubric-contract.mjs';
import { validateGuideApproval } from './marking-guide.mjs';

export const DEFAULT_EXECUTION_METHOD = '逐页查看答卷，按下列已核对的评分条件记录证据和理由。允许原 MS 支持的等价方法；不能确定的判断保留待定并请老师审阅。批改时尽可能记录证据位置；批注和汇总由脚本生成。';

export function validateReplayGuide(guide, frozen) {
  return validateGuideApproval(guide, { id: guide?.proposalId, rubricHash: frozen.hash,
    sourceHash: frozen.artifact.source_sha256, executionMode: guide?.method === 'automatic' ? 'auto' : 'review' });
}

export function gradingSourcePages(frozen, scheme, guide, allImages = false) {
  const all = scheme.pages.map(page => page.page);
  // Reducing duplicate source images requires a verified compilation and the
  // exact adopted guide. Unknown global scope keeps the complete original MS.
  if (allImages || !guide || frozen.verification?.final_rubric_hash !== frozen.hash
    || frozen.verification?.source_sha256 !== scheme.sha256 || frozen.artifact.unresolved_notes.length) return all;
  validateReplayGuide(guide, frozen);
  const required = new Set(frozen.artifact.general_instructions.flatMap(rule => rule.source_pages));
  for (const item of frozen.artifact.items) if (item.requires_source_image || item.uncertainties.length)
    for (const page of item.source_pages) required.add(page);
  return all.filter(page => required.has(page));
}

// The omitted independent exception reviewer is NOT replaced by automatic approval.
// Preserve its proposed award, but withhold it until the teacher resolves the point.
export function deferUnreviewedExceptions(primary, frozen, scheme, student) {
  const targets = exceptionTargets(primary);
  if (!targets.length) return structuredClone(primary);
  const grade = structuredClone(primary);
  for (const target of targets) {
    const item = grade.items.find(row => row.item_id === target.item_id);
    const point = item.point_decisions.find(row => row.point_id === target.point_id);
    point.primary_score = point.score;
    point.exception_review = { verdict: 'pending_teacher', reason: '例外给分尚未经独立复核，保留原提议供老师确认。' };
    point.score = null; point.relation = 'uncertain'; point.rule_ref = '';
    point.reason = `待老师复核例外给分；原判定：${point.reason}`;
    item.review_required = true;
  }
  const dependentTargets=[];
  for(const item of grade.items) {
    const criterion=frozen.artifact.items.find(row=>row.item_id===item.item_id);
    let changed;
    do {
      changed=false;
      for(const point of item.point_decisions.filter(p=>p.score>0)) {
        const rule=criterion.scoring_points.find(p=>p.point_id===point.point_id);
        const pending=rule.depends_on.filter(id=>item.point_decisions.find(p=>p.point_id===id)?.score===null);
        if(!pending.length)continue;
        point.primary_score=point.score;point.score=null;point.relation='uncertain';point.rule_ref='';
        point.reason=`前置评分点 ${pending.join(', ')} 待老师确认；原判定：${point.reason}`;
        item.review_required=true;changed=true;
        dependentTargets.push({item_id:item.item_id,point_id:point.point_id,depends_on:pending});
      }
    }while(changed);
    if(targets.some(t=>t.item_id===item.item_id)) {
      item.score=item.point_decisions.some(p=>p.score===null)?null:item.point_decisions.reduce((n,p)=>n+p.score,0);
      item.reason=item.point_decisions.map(p=>`${p.point_id}: ${p.reason}`).join('; ');
    }
    validatePointDecisions(item,criterion,student);
  }
  const coverage = new Set([...scheme.pages.map(p => `scheme:${p.page}`), ...student.pages.map(p => `student:${p.page}`)]);
  return { ...validateGrade(grade, { documents: { scheme, student } }, coverage),
    exception_review: { status: 'pending_teacher', targets, dependent_targets:dependentTargets, primary_hash: digest(primary), model_calls: 0 } };
}

const safe = value => String(value ?? '').replaceAll('|', '\\|').replaceAll('\n', ' ');
const score = value => value == null ? '待定' : value;
export function scriptedStudentReport(id, grade, frozen, guide) {
  const lines = [`# ${id} · 批改记录`, '', `总分：${score(grade.total_score)} / ${grade.max_score}。状态：${grade.status === 'review_required' ? '待老师审阅' : '暂定'}。`,
    '', `评分实施：${guide ? `v${guide.revision} · ${guide.hash}` : '冻结 MS'}`, '',
    '以下直接列出本次评分证据与原始理由，由脚本整理；没有额外模型解读。', '',
    '| 评分点 | 得分 | 答卷证据 | 原始理由 | MS 条件 | 答卷页 | 定位 |', '| --- | --- | --- | --- | --- | --- | --- |'];
  for (const item of grade.items) for (const point of item.point_decisions) {
    const criterion = frozen.artifact.items.find(row => row.item_id === item.item_id).scoring_points.find(row => row.point_id === point.point_id);
    lines.push(`| ${safe(item.item_id)}/${safe(point.point_id)} | ${score(point.score)} / ${criterion.max_score} | ${safe(point.evidence)} | ${safe(point.reason)} | ${safe(criterion.condition)} | ${point.student_pages.join(', ')} | ${point.annotation?.regions.length || 0} 处 |`);
  }
  lines.push('', '## 待审阅', '', ...grade.review_notes.map(note => `- ${note}`),
    ...grade.items.filter(item => item.review_required).map(item => `- ${item.item_id}：${item.reason}`), '');
  return lines.join('\n');
}

export async function writeAnnotationViewer(directory, student, grade, frozen) {
  const pages = [];
  for (const page of student.pages) {
    const bytes = await readFile(page.absolute_path);
    if (digest(bytes) !== page.sha256) throw Error('Annotation source image changed');
    pages.push({ page: page.page, url: `data:image/png;base64,${bytes.toString('base64')}` });
  }
  const points = grade.items.flatMap(item => item.point_decisions.map(point => ({
    id: `${item.item_id}/${point.point_id}`, itemId: item.item_id, score: point.score,
    maximum: frozen.artifact.items.find(row => row.item_id === item.item_id).scoring_points.find(row => row.point_id === point.point_id).max_score,
    condition: frozen.artifact.items.find(row => row.item_id === item.item_id).scoring_points.find(row => row.point_id === point.point_id).condition,
    locationStatus: point.annotation?.status || 'unlocated',
    evidence: point.evidence, reason: point.reason, pages: point.student_pages, regions: point.annotation?.regions || [],
  })));
  const data = JSON.stringify({ pages, points }).replaceAll('<', '\\u003c');
  const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>答卷批注</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f4f5f7;color:#24262b;font:14px system-ui}header{height:58px;padding:16px 24px;background:white;display:flex;gap:24px;align-items:center}header span{color:#757980;font-size:12px}main{display:grid;grid-template-columns:270px 1fr;height:calc(100vh - 58px)}aside{overflow:auto;padding:12px}button{cursor:pointer;border:0;background:transparent;border-radius:10px;padding:9px 12px;text-align:left;color:inherit}aside button{display:block;width:100%;margin-bottom:4px}button.active{background:#e0e9fb;color:#2455a4}#viewer{overflow:auto;padding:24px;position:relative}#sheet{position:relative;max-width:900px;margin:auto;background:white;box-shadow:0 3px 24px #20283512}img{width:100%;display:block}svg{position:absolute;inset:0;width:100%;height:100%}.related{fill:#617d7410;stroke:#617d74;stroke-dasharray:5 5;pointer-events:none}rect{fill:#397cf31c;stroke:#397cf3;stroke-width:2;cursor:pointer;vector-effect:non-scaling-stroke}#note{display:none;position:fixed;right:28px;bottom:28px;max-width:420px;background:white;padding:20px;border-radius:16px;box-shadow:0 8px 40px #1113;white-space:pre-wrap;max-height:55vh;overflow:auto}#note.show{display:block}#pager{margin-left:auto}small{color:#737880}</style>
<header><b>答卷批注</b><span>脚本绘制 · 点击区域查看原始批改依据</span><label><input id="context" type="checkbox" checked> 显示附近笔迹</label><label><input id="related" type="checkbox"> 同题依据</label><button id="details">批改依据</button><div id="pager"><button id="prev">上一页</button><b id="pageLabel"></b><button id="next">下一页</button></div></header><main><aside id="points"></aside><div id="viewer"><div id="sheet"><img id="page"><svg id="boxes" viewBox="0 0 1000 1000" preserveAspectRatio="none"></svg></div></div></main><div id="note"></div>
<script>const data=${data};let selected=0,page=data.points[0]?.pages[0]||1;const $=id=>document.getElementById(id);function note(p){$('note').textContent=p.id+' · '+(p.score??'待定')+' / '+p.maximum+'\\n\\n答卷证据：'+p.evidence+'\\n\\n评分条件：'+p.condition+'\\n\\n原始理由：'+p.reason+(p.regions.some(r=>r.precision==='grid-cells')?'\\n\\n位置按行列格确定；可显示附近笔迹。虚线为同题其他评分点的依据，不是当前点新增的定位。':'');$('note').classList.add('show')}function render(){const p=data.points[selected];$('page').src=data.pages.find(p=>p.page===page).url;$('pageLabel').textContent=page+' / '+data.pages.length;$('boxes').replaceChildren();const displayed=[...($('related').checked?data.points.filter(q=>q.itemId===p.itemId&&q.id!==p.id).flatMap(q=>q.regions.map(r=>({...r,related:true}))):[]),...p.regions];for(const r of displayed.filter(r=>r.page===page)){const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const k of ['x','y','width','height'])rect.setAttribute(k,($('context').checked&&r.contextRect?r.contextRect:r.rect)[k]*1000);if(r.related)rect.classList.add('related');else rect.onclick=()=>note(p);$('boxes').append(rect)}$('points').replaceChildren();data.points.forEach((p,i)=>{const b=document.createElement('button');b.className=i===selected?'active':'';b.textContent=(i+1)+'. '+p.id+' · '+(p.score??'待定')+'/'+p.maximum+(p.regions.length?'':p.locationStatus==='absent'?' · 无作答证据':' · 待定位');b.onclick=()=>{selected=i;page=p.regions[0]?.page||p.pages[0]||1;$('note').classList.remove('show');render()};b.ondblclick=()=>note(p);$('points').append(b)})}for(const [id,d]of [['prev',-1],['next',1]])$(id).onclick=()=>{page=Math.max(1,Math.min(data.pages.length,page+d));$('note').classList.remove('show');render()};$('note').onclick=()=> $('note').classList.remove('show');$('context').onchange=render;$('related').onchange=render;$('details').onclick=()=>note(data.points[selected]);render();</script></html>`;
  await writeFile(resolve(directory, 'annotations.html'), html, { flag: 'wx' });
}

export async function runScriptedGrading({ runtime, output, frozen, guide, scheme, students, model,
  concurrency = null, inlineAnnotations = false, imageVariants = null, interaction = null, gradingReasoning = 'low', allMsImages = false, localObservations = null, mainOwnsScheme = false, readPage = readImage }) {
  if (guide) validateReplayGuide(guide, frozen);
  const registry = new StudentRegistry([...students.keys()], concurrency);
  if (mainOwnsScheme && (frozen.verification?.final_rubric_hash !== frozen.hash ||
    frozen.verification?.source_sha256 !== scheme.sha256)) throw Error('Student grading requires a source-verified rubric');
  const sourcePages = mainOwnsScheme ? [] : gradingSourcePages(frozen, scheme, guide, allMsImages);
  await freezeJson(output, 'grading-input-policy.json', { scheme_pages:sourcePages, total_scheme_pages:scheme.pages.length,
    scheme_image_owner:mainOwnsScheme ? 'main' : 'shared',
    source_contract:mainOwnsScheme ? 'Student uses the source-verified text. Original-dependent awards remain pending.' : 'Unchanged frozen rubric and exact approved guide; selected originals retain visual dependencies, source uncertainties and general rules.',
    student_pages:'Complete original answer content once; no separate locator or model review.' });
  const started = Date.now();
  runtime.allocateStudentBudgets([...students.keys()],{reserveCoordinator:false});
  await registry.dispatch([...students.keys()], concurrency ?? students.size, async id => {
    try {
    const io = await runtime.io(`student-${id}`, () => 'student_grading');
    const student = students.get(id), start = Date.now(); let failure = null;
    await io.log({ type: 'student_task_start', student_id: id, rubric_hash: frozen.hash });
    const hasRegions = inlineAnnotations && imageVariants?.documents[id]?.pages.some(page => page.regions?.length);
    const child = createStudentAgent({ model, streamFn: io.streamFn, frozen, scheme, student, readImage:readPage, mainOwnsScheme,
      singlePass: true, protocol: 'evidence-v4', reasonStyle: 'brief-full-credit', inlineAnnotations: Boolean(hasRegions),
      markingGuide: interaction ? null : guide, gradingReasoning,localObservations:localObservations?.documents[id]?.pages||[],
      ...(imageVariants ? { readInitialStudentImage: page => readPage(imageVariants.documents[id].pages.find(p => p.page === page.page)),
        initialStudentImageMode: imageVariants.mode || 'exact_white_margin_trim', initialStudentGeometry: imageVariants.documents[id].pages } : {}),
      log: io.log, persistSubmission: raw => freezeJson(io.directory, 'submission.json', raw),
      persist: grade => freezeJson(io.directory, 'grading-primary.json', grade) });
    const detach = io.attach(child.agent, {guideRubric: inlineAnnotations ? frozen : null});
    try { await runtime.run(child.agent, await child.initialPrompt(sourcePages), io.directory); }
    catch (error) { failure = error.message; }
    finally { detach(); }
    const primary = child.getResult(); let grade = null, feedback = null;
    if (primary) {
      grade = deferUnreviewedExceptions(primary, frozen, scheme, student);
      await freezeJson(io.directory, 'grading.json', grade);
      await io.log({ type: 'grading_result_saved', student_id: id, review_status: grade.status });
      const reportDirectory = resolve(output, `feedback-${id}`);
      await mkdir(reportDirectory);
      await writeFile(resolve(reportDirectory, 'REPORT.zh-CN.md'), scriptedStudentReport(id, grade, frozen, guide), { flag: 'wx' });
      await writeAnnotationViewer(io.directory, student, grade, frozen);
      feedback = { status: 'submitted', mode: 'script', model_calls: 0, provider_reported_cost_usd: 0,
        report_path: resolve(reportDirectory, 'REPORT.zh-CN.md'), grade_hash: digest(grade), rubric_hash: frozen.hash };
      await freezeJson(reportDirectory, 'summary.json', feedback);
    }
    const requests = runtime.budget.requests.filter(row => row.lane === `student-${id}`);
    const summary = { student_id: id, status: grade ? 'submitted' : 'failed', failure: failure || child.agent.state.errorMessage || (!grade ? 'Single grading response did not pass validation; no automatic retry.' : null),
      mode: 'scripted-single-pass', total_score: grade?.total_score ?? null, primary_total_score: primary?.total_score ?? null,
      max_score: grade?.max_score ?? null, review_status: grade?.status ?? null,
      rubric_hash: frozen.hash, marking_guide_hash: guide?.hash ?? null, elapsed_seconds: (Date.now() - start) / 1000,
      feedback_status: feedback?.status ?? 'unavailable', feedback, ...runtime.totals(requests), requests,
      result_path: grade ? resolve(io.directory, 'grading.json') : null };
    await freezeJson(io.directory, 'summary.json', summary);
    await io.log({ type: 'student_task_terminal', ...summary, requests: undefined });
    return summary;
    } finally { runtime.finishStudentBudget(id); }
  }, runtime.signal);
  const rows = [...registry.rows.values()];
  await freezeJson(output, 'cohort.json', { rubric_hash: frozen.hash, students: rows });
  const report = ['# 批改汇总', '', '脚本依据已保存评分记录汇总；待定项不计作零分。', '', '| 答卷 | 状态 | 总分 | 审阅 |', '| --- | --- | --- | --- |',
    ...rows.map(row => `| ${safe(row.student_id)} | ${row.status} | ${score(row.total_score)} | ${row.review_status || row.failure || '未完成'} |`), ''].join('\n');
  await writeFile(resolve(output, 'REPORT.zh-CN.md'), report, { flag: 'wx' });
  await freezeJson(output, 'report.json', { mode: 'script', model_calls: 0, rubric_hash: frozen.hash, marking_guide_hash: guide?.hash ?? null, students: rows.map(row => ({ student_id: row.student_id, status: row.status, total_score: row.total_score })) });
  return { status: rows.every(row => row.status === 'submitted') ? 'submitted' : rows.some(row=>row.status==='submitted') ? 'partial_completed' : 'incomplete', students: rows,
    elapsed_seconds: (Date.now() - started) / 1000, rubric_hash: frozen.hash, marking_guide_hash: guide?.hash ?? null,
    feedback_submitted: rows.filter(row => row.feedback_status === 'submitted').length,
    feedback_complete: rows.every(row => row.feedback_status === 'submitted'), report_submitted: true, model_reporting_calls: 0 };
}
