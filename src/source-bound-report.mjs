import {PRACTICE_ACTIONS} from './source-bound-feedback.mjs';

const obj=properties=>({type:'object',properties,required:Object.keys(properties),additionalProperties:false});
const ids={type:'array',minItems:1,maxItems:3,uniqueItems:true,items:{type:'string',minLength:1}};
export const REPORT_METHODS=['gradeos.class_report','gradeos.global_logic_audit','harness.repeatability'];
export const SOURCE_BOUND_REPORT_SCHEMA=obj({
  result_set_hash:{type:'string',minLength:1},analysis_hash:{type:'string',minLength:1},
  analysis_sections:{type:'array',minItems:3,maxItems:3,items:obj({method_id:{type:'string',enum:REPORT_METHODS},evidence_refs:{...ids,minItems:0}})},
  review_priorities:{type:'array',maxItems:4,items:obj({evidence_refs:ids})},
  learning_observations:{type:'array',maxItems:4,items:obj({kind:{type:'string',enum:['full_credit','credited','non_full','uncertain']},evidence_refs:ids,action:{type:'string',enum:Object.keys(PRACTICE_ACTIONS)}})},
});
export const SOURCE_BOUND_REPORT_POLICY=`The report submission contains structured evidence selections only. Do not generate title, executive_summary, interpretation, reasons, limitations or other free text in the tool arguments.
Build each evidence_ref by appending the exact item_id to its delivered record's evidence_ref_prefix (student_id + '/'). Preserve every character, including the slash; never substitute ':' or rewrite an ID. The same exact refs work in every report section and evidence tool.
Return all three analysis method IDs with up to three exact delivered student/item refs each. Select up to four learning_observations with kind full_credit/credited/non_full/uncertain, exact evidence_refs and one practice action ID. full_credit requires every cited item to have its full numeric award and no review; credited requires positive known credit and no review; non_full requires a known award below maximum; uncertain requires null or an actual recorded/recommended review. Do not mix predicates in a selection.
review_priorities may cite only items with an existing review, null, source issue or saved feedback review suggestion. These are source checks, not new proved errors.
Actions: reconstruct, check_scope, complete_evidence for known non-full items; verify_result for credited/full items; inspect_source for uncertain items. For a null award use uncertain+inspect_source. Never diagnose a cause for missing credit, infer blank from zero, generate a new solution, or compress IDs into ranges.
The host constructs all score/coverage statements and method interpretations directly from the frozen records and GradeOS statistics. It retains original judgments and MS references, and renders full numerical tables. This contract does not regrade or independently prove any mathematical solution. Do not treat free notes, grader reasons or earlier model summaries as new authority.`;
export function sourceBoundReportingInstructions(instructions){
  return instructions
    .replace('Then submit_cohort_report in Chinese, citing concrete student/item evidence refs (e.g. an actual student ID + \'/\' + actual item ID).','Then use submit_cohort_report with structured source selections.')
    .replace('Keep the entire narrative under 1800 Chinese characters. Write exactly three short analysis sections, at most three evidence refs per section,\nat most four review priorities, four learning observations and six limitations. Do not reproduce raw records, rubric text, long lists or analytics JSON.','Select exactly three analysis methods, at most three evidence refs per method, at most four review groups and four learning observations. The host renders the prose.')
    +'\n'+SOURCE_BOUND_REPORT_POLICY;
}
const exact=(value,keys)=>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k)))throw Error('Invalid source-bound report fields');
};
export function reportFactIndex(records){
  const index=new Map();
  for(const record of records){
    if(!record.grade)continue;
    for(const item of record.grade.items){
      const ref=`${record.student_id}/${item.item_id}`;
      const review=item.score===null||item.review_required||(record.grade.source_issues??[]).some(i=>i.item_id===item.item_id)||record.feedback?.items.some(i=>i.item_id===item.item_id&&i.review_recommended)||false;
      if(index.has(ref))throw Error('Duplicate reporting identity');
      index.set(ref,{student_id:record.student_id,item,review});
    }
  }
  return index;
}
export function sourceReportFacts(records){
  const index=reportFactIndex(records),rows=[...index.values()];
  return {record_count:records.length,scored_record_count:records.filter(r=>r.grade?.total_score!=null).length,
    full_item_count:rows.filter(({item})=>item.score!==null&&item.score===item.max_score).length,
    non_full_item_count:rows.filter(({item})=>item.score!==null&&item.score<item.max_score).length,
    unknown_item_count:rows.filter(({item})=>item.score===null).length,
    review_refs:rows.filter(r=>r.review).map(r=>`${r.student_id}/${r.item.item_id}`),
    authority:'Counts describe saved awards only; no cause, mastery or new source verification is inferred.'};
}
export function expandSourceBoundReport(raw,records,analysis,deliveredRefs){
  exact(raw,['result_set_hash','analysis_hash','analysis_sections','review_priorities','learning_observations']);
  if(raw.result_set_hash!==analysis.result_set_hash||raw.analysis_hash!==analysis.analysis_hash)throw Error('Report source hash mismatch');
  const index=reportFactIndex(records),facts=sourceReportFacts(records);
  const resolve=refs=>{
    if(!Array.isArray(refs)||refs.length>3||new Set(refs).size!==refs.length||refs.some(ref=>!index.has(ref)||!deliveredRefs.has(ref)))throw Error('Unbound source report evidence');
    return refs.map(ref=>index.get(ref));
  };
  if(!Array.isArray(raw.analysis_sections)||raw.analysis_sections.length!==3)throw Error('Report requires three analysis methods');
  const methods=new Set();
  const totalText=records.length===1&&records[0].grade?`本份原记录总分${records[0].grade.total_score===null?'待定':records[0].grade.total_score+'/'+records[0].grade.max_score}。`:'';
  const overview=`共${facts.record_count}份记录，${facts.scored_record_count}份有数值总分。${totalText}各记录小项合计：${facts.full_item_count}项记录为满分、${facts.non_full_item_count}项未获满额、${facts.unknown_item_count}项待定；${facts.review_refs.length}项保留或建议复核。`;
  const n=analysis.gradeos_global_logic_audit?.issue_count;
  const interpretations={
    'gradeos.class_report':overview+'得分分布和低分项依据GradeOS已计算统计展示；内部得分段和题项得分率不等于官方等级或知识掌握率。',
    'gradeos.global_logic_audit':`${n==null?'全局逻辑审计结果见下方源文件。':`GradeOS全局逻辑审计记录${n}项提示。`}这类统计不能证明每个内部评分点或数学推导正确；具体原始依据和复核状态仍需逐项核查。`,
    'harness.repeatability':records.length<2?`本次只有${records.length}份任务记录，其中${records.filter(r=>r.grade).length}份保存了评分结果；不能估计重复稳定性或跨学生准确率。`:analysis.cohort_context?.unique_answer_sources===1?'这些记录对应同一答卷的重复评分任务，完成与失败均保留；差异见已完成结果的题项分布，不能视作独立学生样本或泛化准确率。':'当前记录包含不同答卷；完成与失败均保留，题项分布不能替代对同一输入的重复稳定性测试。',
  };
  const sections=raw.analysis_sections.map(section=>{
    exact(section,['method_id','evidence_refs']);resolve(section.evidence_refs);
    if(!REPORT_METHODS.includes(section.method_id)||methods.has(section.method_id))throw Error('Unbound or duplicate report method');methods.add(section.method_id);
    return {...section,interpretation:interpretations[section.method_id]};
  });
  if(!Array.isArray(raw.review_priorities)||raw.review_priorities.length>4||!Array.isArray(raw.learning_observations)||raw.learning_observations.length>4)throw Error('Too many report observations');
  const reviews=raw.review_priorities.map(row=>{
    exact(row,['evidence_refs']);const matched=resolve(row.evidence_refs);
    if(!matched.length||matched.some(r=>!r.review))throw Error('Review priority requires recorded uncertainty');
    return {evidence_refs:[...row.evidence_refs],item_ids:[...new Set(matched.map(r=>r.item.item_id))],student_ids:[...new Set(matched.map(r=>r.student_id))],
      reason:'所引记录存在待定、原有复核要求或反馈核查建议；并不表示问题已获独立确认。',action:PRACTICE_ACTIONS.inspect_source.action};
  });
  const allowed={full_credit:['verify_result'],credited:['verify_result'],non_full:['reconstruct','check_scope','complete_evidence'],uncertain:['inspect_source']};
  const predicate={full_credit:r=>r.item.score!==null&&r.item.score===r.item.max_score&&!r.review,credited:r=>r.item.score>0&&!r.review,non_full:r=>r.item.score!==null&&r.item.score<r.item.max_score,uncertain:r=>r.review};
  const labels={full_credit:'所引小项已记录满分且未标注复核',credited:'所引小项有已记录正分',non_full:'所引小项仍有未获分部分',uncertain:'所引记录仍需核查'};
  const observations=raw.learning_observations.map(row=>{
    exact(row,['kind','evidence_refs','action']);const matched=resolve(row.evidence_refs);
    if(!matched.length||!Object.hasOwn(predicate,row.kind)||matched.some(r=>!predicate[row.kind](r))||!allowed[row.kind].includes(row.action))throw Error('Report claim or action contradicts frozen awards');
    return `${labels[row.kind]}（${row.evidence_refs.join('、')}）。练习建议：${PRACTICE_ACTIONS[row.action].action}`;
  });
  return {title:'批改结果与学习反馈',executive_summary:overview+'学习重点按具体评分条件安排；未获分本身不说明时间分配、学习态度或其他原因。',
    result_set_hash:raw.result_set_hash,analysis_hash:raw.analysis_hash,analysis_sections:sections,review_priorities:reviews,learning_observations:observations,
    limitations:['本报告使用已保存的评分记录；完整MS与作答证据保留，原模型理由不等同于已验证解法。','报告阶段没有新增笔迹识别或修改成绩；结构化来源约束不证明上游判分正确。','题项得分率不是知识掌握率，GradeOS内部得分段不是官方考试等级。','没有使用官方参考分数指导批改；未评估跨卷泛化或校准Risk。'],
    source_bound_selection:structuredClone(raw),fact_counts:facts};
}
