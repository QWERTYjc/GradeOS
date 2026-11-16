import {digest} from './core.mjs';
import {conciseFeedbackIds, focusedFeedbackPacket} from './focused-feedback.mjs';

const obj=properties=>({type:'object',properties,required:Object.keys(properties),additionalProperties:false});
const enumeration=values=>({type:'string',enum:values});
const exact=(value,keys)=>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k))) throw Error('Invalid source-bound feedback fields');
};
export const PRACTICE_ACTIONS={
  reconstruct:{action:'重做所选步骤，对照评分条件说明依据，保留可核查的中间过程。',check:'所选条件要求的每一步都有相应作答证据；不以相似形式代替条件成立。'},
  check_scope:{action:'核对所选条件的适用范围与关联来源上下文，再检查每一步变形或推断。',check:'适用条件和特殊情况均已说明；没有在条件未确定时使用相应结论。'},
  verify_result:{action:'复做已获分步骤，并逐项核验原评分条件及适用的例外规则。',check:'能逐项说明条件或例外规则是否适用并保留证据；不能只复写最后答案。'},
  complete_evidence:{action:'按所选评分条件补全可核查的论证或作答证据。',check:'所选条件需要的证据已完整写出；完成练习不表示原分数自动改变。'},
  inspect_source:{action:'回看所引用的答卷与MS原页，核实条件、证据和适用范围后交教师确认。',check:'不确定之处有明确的来源核对记录；未核实前保留原有待定及复核状态。'},
};
const reviewCodes=['none','source_check','evidence_check'];
const pointMap=(item,rule)=>{
  const route=rule.routes?.find(route=>route.route_id===item.selected_route);
  const points=item.point_decisions??[];
  if(!route||points.length!==route.point_ids.length||new Set(points.map(p=>p.point_id)).size!==points.length||route.point_ids.some(id=>!points.some(p=>p.point_id===id))) throw Error('Source-bound feedback requires a complete selected-route ledger');
  return points.map(point=>{
    const source=rule.scoring_points.find(p=>p.point_id===point.point_id);
    if(!source||!source.condition||!source.source_text) throw Error('Missing source condition');
    return {point,source};
  });
};
export function feedbackFacts(grade,frozen){
  if(grade.rubric_hash!==frozen.hash)throw Error('Feedback source binding differs');
  const concise=new Set(conciseFeedbackIds(grade,frozen));
  return grade.items.map(item=>{
    const rule=frozen.artifact.items.find(r=>r.item_id===item.item_id);
    if(!rule||rule.question_id!==item.question_id||rule.max_score!==item.max_score)throw Error('Unbound feedback fact');
    const pairs=pointMap(item,rule);
    const needsFocus=pairs.filter(({point,source})=>point.score===null||point.score<source.max_score||point.relation!=='met');
    return {item,rule,pairs,concise:concise.has(item.item_id),focus:needsFocus.length?needsFocus:pairs};
  });
}
function actionIds(point,review){
  if(point.score===null)return ['inspect_source'];
  return [...(point.score>0&&point.relation==='met'?['verify_result']:[]),'reconstruct','check_scope','complete_evidence',...(review?['inspect_source']:[])];
}
function sourceFocus(fact,pointId,frozen){
  const pair=fact.pairs.find(({point})=>point.point_id===pointId);
  if(!pair)throw Error('Unbound source focus');
  const project=source=>({point_id:source.point_id,award_type:source.award_type,max_score:source.max_score,allowed_awards:source.allowed_awards,condition:source.condition,source_text:source.source_text,source_pages:source.source_pages,depends_on:source.depends_on});
  return {item_id:fact.item.item_id,selected_route:fact.item.selected_route,point:project(pair.source),
    prerequisite_points:(pair.source.depends_on??[]).map(id=>{
      const source=fact.rule.scoring_points.find(p=>p.point_id===id);if(!source)throw Error('Missing prerequisite source');return project(source);
    }),
    related_context:(fact.rule.related_item_ids??[]).map(id=>{
      const rule=frozen.artifact.items.find(item=>item.item_id===id);if(!rule)throw Error('Missing related source');
      return {item_id:id,criteria:rule.criteria,source_pages:rule.source_pages,routes:structuredClone(rule.routes),points:rule.scoring_points.map(project)};
    })};
}
export function sourceBoundFeedbackSchema(grade,frozen){
  const facts=feedbackFacts(grade,frozen),required=facts.filter(f=>!f.concise);
  const selection=fact=>{
    const groups=new Map();
    for(const {point} of fact.focus){
      const actions=actionIds(point,false).filter(id=>id!=='inspect_source');if(!actions.length)continue;
      const key=actions.join(',');if(!groups.has(key))groups.set(key,{actions,points:[]});groups.get(key).points.push(point.point_id);
    }
    const branches=[...groups.values()].map(({actions,points})=>obj({point_id:enumeration(points),action:enumeration(actions),review:enumeration(fact.item.review_required||fact.item.score===null?reviewCodes.slice(1):reviewCodes)}));
    branches.push(obj({point_id:enumeration(fact.focus.map(({point})=>point.point_id)),action:enumeration(['inspect_source']),review:enumeration(reviewCodes.slice(1))}));
    return branches.length===1?branches[0]:{anyOf:branches};
  };
  const target=obj({item_id:enumeration(grade.items.map(i=>i.item_id)),point_id:{type:'string',minLength:1}});
  return obj({strengths:{type:'array',maxItems:3,items:target},priorities:{type:'array',maxItems:3,items:target},
    items:obj(Object.fromEntries(required.map(f=>[f.item.item_id,selection(f)]))),
    additional_items:{type:'array',maxItems:facts.length-required.length,items:obj({item_id:enumeration(facts.filter(f=>f.concise).map(f=>f.item.item_id).length?facts.filter(f=>f.concise).map(f=>f.item.item_id):['__no_additional_items__']),point_id:{type:'string',minLength:1},action:enumeration(Object.keys(PRACTICE_ACTIONS)),review:enumeration(reviewCodes)})}});
}
export const SOURCE_BOUND_FEEDBACK_PROMPT=`Select concise professional feedback for this frozen grade; do not regrade.
Return only the tool's structured point references, practice action IDs and review codes. The host writes the Chinese summary from exact award counts and renders the complete original evidence ledger.
Select one focus point for EVERY required item. For lost/unknown/exception credit, focus on one of that item's supplied focus_points, never hide a loss by selecting only a fully met point. Every other point remains visible in the full ledger.
strengths: at most three distinct items with ordinary met positive credit, no review, source issue or uncertainty. These are credited observations, not mastery claims.
priorities: at most three distinct non-full or review items; cite the selected focus point. Choose a useful teaching order. additional_items is normally empty; it may add a concern for an ordinary full-credit item.
Actions: reconstruct=redo the step with evidence; check_scope=verify source conditions and scope; complete_evidence=provide the evidence required by the condition; verify_result=recheck an already credited point only; inspect_source=inspect unresolved source/evidence, mandatory for a null focus point. Review codes none/source_check/evidence_check are recommendations, never assertions that a conflict has been proved. Preserve existing review and null.
Recommended methods are the complete bound MS conditions, dependencies and related source context rendered by the host. A grader's reason is an unverified interpretation, not an authoritative solution. Do not derive new formulae, divide by a parameter, drop domain or boundary cases, or diagnose why an answer is blank. No free text fields are accepted. Do not copy or compress question ranges. No labels or previous grades are supplied.
Use submit_student_feedback once the selections are complete.`;
export function sourceBoundFeedbackPacket(grade,frozen){
  const facts=feedbackFacts(grade,frozen);
  return {...focusedFeedbackPacket(grade,frozen),
    practice_actions:PRACTICE_ACTIONS,
    strength_candidates:facts.filter(f=>!f.item.review_required&&!f.rule.uncertainties.length&&!frozen.artifact.unresolved_notes.length&&!(grade.source_issues??[]).some(issue=>issue.item_id===f.item.item_id)).flatMap(f=>f.pairs.filter(({point})=>point.score>0&&point.relation==='met').map(({point})=>({item_id:f.item.item_id,point_id:point.point_id}))),
    source_selection:facts.filter(f=>!f.concise).map(f=>({item_id:f.item.item_id,focus_points:f.focus.map(({point})=>({point_id:point.point_id,allowed_actions:actionIds(point,true)})),related_source_context:(f.rule.related_item_ids??[]).map(id=>frozen.artifact.items.find(i=>i.item_id===id))})),
    prose_authority:'Grader explanations are saved observations only, never a recommended derivation. The host quotes original source conditions without algebraic rewriting.'};
}
export function expandSourceBoundFeedback(raw,grade,frozen){
  exact(raw,['strengths','priorities','items','additional_items']);
  const facts=feedbackFacts(grade,frozen),byId=new Map(facts.map(f=>[f.item.item_id,f]));
  const required=facts.filter(f=>!f.concise).map(f=>f.item.item_id);
  exact(raw.items,required);
  if(!Array.isArray(raw.additional_items)||raw.additional_items.length>facts.length-required.length)throw Error('Invalid additional feedback');
  const selected=new Map(Object.entries(raw.items));
  for(const row of raw.additional_items){
    exact(row,['item_id','point_id','action','review']);
    if(!byId.get(row.item_id)?.concise||selected.has(row.item_id))throw Error('Unbound additional feedback');
    const {item_id,...selection}=row;selected.set(item_id,selection);
  }
  const source_focus={};
  const items=facts.map(f=>{
    const row=selected.get(f.item.item_id);let review=f.item.review_required||f.item.score===null;
    const lost=f.pairs.filter(({point,source})=>point.score!==null&&point.score<source.max_score).length;
    const unknown=f.pairs.filter(({point})=>point.score===null).length;
    const exceptional=f.pairs.filter(({point})=>point.relation==='exception').length;
    let assessment=`本题共${f.pairs.length}个评分点，${[lost?`${lost}个未获满额`:'',unknown?`${unknown}个分数待定`:'',exceptional?`${exceptional}个按例外规则判断`:''].filter(Boolean).join('、')||'均已获满额'}。完整条件、作答记录和判分理由可展开核对。`;
    let next_step='复做时保留关键步骤，再对照评分条件检查依据与结果。',review_reason=review?'原记录存在待定或复核要求，需核对原卷及对应MS条件。':'';
    if(row){
      exact(row,['point_id','action','review']);
      const pair=f.focus.find(({point})=>point.point_id===row.point_id);
      if(!pair||!Object.hasOwn(PRACTICE_ACTIONS,row.action)||!reviewCodes.includes(row.review))throw Error('Unbound feedback focus or action');
      if(review&&row.review==='none')throw Error('Existing review cannot be removed');
      review ||=row.review!=='none';
      if(!actionIds(pair.point,review).includes(row.action))throw Error('Practice action is incompatible with saved point state');
      if(row.action==='inspect_source'&&!review)throw Error('Source inspection must retain a review recommendation');
      source_focus[f.item.item_id]=sourceFocus(f,row.point_id,frozen);
      next_step=PRACTICE_ACTIONS[row.action].action;
      if(row.review!=='none')review_reason=(f.item.review_required||f.item.score===null?'保留原记录的复核要求：':'反馈模型建议核查，尚未独立确认问题：')+(row.review==='source_check'?'核对所选评分点的MS条件与适用范围。':'核对所选评分点的原始作答证据。');
    }else{
      if(!f.concise)throw Error('Missing required point feedback');
      assessment='本题记录为满分，所选评分路线的各点均已获分。复习时可用下方评分条件检查关键步骤是否完整。';
    }
    return {item_id:f.item.item_id,criterion:'完整评分条件见下方原始逐点依据。',assessment,next_step,review_recommended:review,review_reason};
  });
  const refs=(rows,kind)=>{
    if(!Array.isArray(rows)||rows.length>3)throw Error('Too many feedback priorities');
    const seen=new Set();return rows.map(row=>{
      exact(row,['item_id','point_id']);const f=byId.get(row.item_id),pair=f?.pairs.find(({point})=>point.point_id===row.point_id);
      if(!pair||seen.has(row.item_id))throw Error('Unbound or repeated feedback reference');seen.add(row.item_id);
      if(kind==='strength'){
        if(!(pair.point.score>0)||pair.point.relation!=='met'||f.item.review_required||f.rule.uncertainties.length||frozen.artifact.unresolved_notes.length||(grade.source_issues??[]).some(i=>i.item_id===row.item_id)||selected.get(row.item_id)?.review!=='none'&&selected.has(row.item_id))throw Error('Strength requires ordinary known positive evidence');
        return {observation:`本次作答在评分点 ${row.point_id} 获得分数，记录显示满足该点条件；可将这一步作为复做时的检查参照。`,item_ids:[row.item_id]};
      }
      const choice=selected.get(row.item_id);
      if(!choice||choice.point_id!==row.point_id||f.item.score===f.item.max_score&&!f.item.review_required&&choice.review==='none')throw Error('Priority must bind a selected non-full or review point');
      return {...PRACTICE_ACTIONS[choice.action],item_ids:[row.item_id]};
    });
  };
  const strengths=refs(raw.strengths,'strength'),priorities=refs(raw.priorities,'priority').map(({action,check,item_ids})=>({action,success_check:check,item_ids}));
  const full=facts.filter(f=>f.item.score!==null&&f.item.score===f.item.max_score).length;
  const partial=facts.filter(f=>f.item.score!==null&&f.item.score<f.item.max_score).length;
  const unknown=facts.filter(f=>f.item.score===null).length,reviewCount=items.filter(i=>i.review_recommended).length;
  const total=grade.total_score===null?'总分待定':`本次记录为${grade.total_score}/${grade.max_score}分`;
  const practice=priorities.length?`建议先练习第${priorities.flatMap(row=>row.item_ids).join('、')}项，对照原评分条件补全步骤，再用下方完成标准自查。`:'复习时先对照已获分步骤，再核查每一步的适用条件与依据。';
  return {feedback:{summary:`${total}。${facts.length}个小项中，${full}项记录为满分${partial?`、${partial}项尚有未获分部分`:''}${unknown?`、${unknown}项分数待定`:''}。${reviewCount?`${reviewCount}项保留或建议复核。`:''}${practice}具体失分依据见逐题记录；未获分本身不能说明失分原因。`,strengths,priorities,items},
    metadata:{source_focus,selection:structuredClone(raw),fact_counts:{full,non_full:partial,unknown,review:reviewCount},fixed_commentary_ids:facts.filter(f=>!selected.has(f.item.item_id)).map(f=>f.item.item_id),model_submission_hash:digest(raw)}};
}
