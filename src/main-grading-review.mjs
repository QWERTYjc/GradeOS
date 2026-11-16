import {digest,validateGrade} from './core.mjs';
import {objectSchema,checkPages} from './rubric-contract.mjs';
import {COMPACT_POINTS_SCHEMA,SOURCE_ISSUE_SCHEMA} from './compact-points.mjs';
import {expandBriefFullCredit,compactPromptForReasons,BRIEF_REASON_STYLE} from './full-credit-reasons.mjs';
import {validateSourceIssue} from './cohort-core.mjs';

const str={type:'string',minLength:1};
const ids={type:'array',uniqueItems:true,items:str};
const pageList={type:'array',minItems:1,maxItems:4,uniqueItems:true,items:{type:'integer',minimum:1}};
const reviewEncoding=compactPromptForReasons(BRIEF_REASON_STYLE).split('After original MS pages')[0]
  .replace('Use submit_grading with items, review_notes and source_issues (empty array when none).','Use revised_items only for changed items; use [] when no changes.')
  .replace(/Submit the complete ledger once\.[\s\S]*?Keep complete observed evidence/,'Keep complete observed evidence');
export const MAIN_GRADING_REVIEW_PROMPT=`Before final reports, YOU review every student's complete primary point ledger against the full source conditions, including ordinary full-credit points, independently of the worker's review flags. The worker's observations are claims, not verified facts.
grade_students attaches the first review packet automatically. Do not reread it. read_grading_review retrieves remaining packets when needed. Check every listed point: literal evidence, complete conditions and allowed partial credit, algebra/logic, dependencies, error origins and exception scope. Do not merely check sums or flags. Equivalent valid work must retain credit.
A statement such as "correct", "uses the required method" or a copied expected result does not establish the student's actual work. When an award/deduction depends on unsupported, ambiguous or contradictory observations, use inspect_student_answer for only the necessary ORIGINAL pages, with a concrete question. Inspect ordinary full-credit claims too; do not limit inspection to flagged or lost-mark points. Use inspect_ms when the written rules cannot resolve a source/diagram issue. Never reconstruct a missing digit/sign/step from the MS. If targeted inspection remains inconclusive, retain null and review instead of guessing credit or zero.
Consume new evidence in a subsequent model response before submitting changes. Prefer submitting checked_item_ids and patches for a completed group before inspecting another group: partial review commits return the remaining IDs while keeping the current full ledger visible. Do not reread that ledger. A new packet is attached only after the current packet is fully checked. This releases inspected images without rewriting unchanged points.
Keep at most four active images. If an unfinished item requires more images, save_report_notes with student_ids=[] and student/item refs records your literal observations and releases consumed images while retaining the uncommitted scoring ledger. A checkpoint with saved observations certifies the images already reached a previous response; it does NOT mean they were unavailable. Rely on your recorded observations; reopen only for a concrete unresolved reading. Do not reread the whole answer book or MS as a routine preflight.
submit_grading_review attests checked_item_ids for the delivered packet, with COMPLETE changed items only in revised_items. Unchanged full-credit points require no repeated explanation. Changes require original answer pages viewed by you; cite those pages. Add new source issues only after inspecting the original MS. Existing source issues are preserved. Keep substantive short reasons for losses, uncertainty and disputed awards. notes records your review findings, not a replacement grading ledger.
Final grades and personal reports are saved only after every item is reviewed. Successful submission checkpoints the consumed packet automatically and attaches the next review packet or the final report data. Do not regrade in the report.
Changed item encoding follows:\n${reviewEncoding}`;

function compactGrade(grade) {
  const origins={none:'n',inherited:'i',current:'c',mixed:'m',unknown:'u'};
  return {items:grade.items.map(i=>({id:i.item_id,route:i.selected_route,review:i.review_required,
    p:i.point_decisions.map(p=>[p.point_id,p.score,p.evidence,p.student_pages,
      p.relation==='met'?'m':p.relation==='exception'?`x:${origins[p.error_origin]}:${p.rule_ref}`:`${p.relation==='unmet'?'u':'q'}:${origins[p.error_origin]}`,
      p.reason_encoding==='explicit_full_credit_attestation'?'=':p.reason])})),
    review_notes:structuredClone(grade.review_notes??[]),source_issues:(grade.source_issues??[]).map(({issue_id,rubric_hash,...issue})=>issue)};
}

// Reuses the main conversation, existing bounded evidence views and canonical grading checks.
// Primary and final grades remain immutable; only this uncommitted review draft accepts patches.
export function createMainGradingReview({getRubric,scheme,students,views,readImage,log,persist,onFinalized,afterFinalized}) {
  const drafts=new Map();
  const pending=()=>[...drafts.values()].filter(d=>!d.finished);
  const get=id=>{const d=drafts.get(id);if(!d||d.finished)throw Error('Unknown or completed review student');return d;};
  const receipt=(kind,id)=>views.delivered(kind).filter(v=>v.meta.student_id===id);
  const packet=async id=>{
    const d=get(id),frozen=getRubric();
    if(views.pending().some(v=>v.kind==='grading_review'))throw Error('Review or checkpoint the current packet before reading another');
    const remaining=frozen.artifact.items.filter(i=>!d.checked.has(i.item_id));
    const items=[];let bytes=0;
    for(const source of remaining){
      const item={source,primary:d.grade.items.find(i=>i.item_id===source.item_id)};
      const size=Buffer.byteLength(JSON.stringify(item));if(items.length&&bytes+size>90000)break;
      items.push(item);bytes+=size;
    }
    const related=new Set(items.flatMap(i=>i.source.related_item_ids));
    const meta={student_id:id,primary_hash:d.hash,item_ids:items.map(i=>i.source.item_id),evidence_refs:items.map(i=>`${id}/${i.source.item_id}`)};
    const value={...meta,rubric_hash:frozen.hash,general_instructions:frozen.artifact.general_instructions,unresolved_notes:frozen.artifact.unresolved_notes,
      source_issues:d.grade.source_issues,review_notes:d.grade.review_notes,items,
      related_items:frozen.artifact.items.filter(i=>related.has(i.item_id)&&!meta.item_ids.includes(i.item_id)),
      answer_pages:students.get(id).pages.map(p=>p.page),remaining_items:remaining.length,
      message:'Substantively review all listed points, including ordinary full credit. Original answer inspection is available on demand. Submit only changed items.'};
    const result=views.add('grading_review',[{type:'text',text:JSON.stringify(value)}],
      {...meta,primary_path:d.primaryPath,checked_before:[...d.checked]},meta);
    d.started??=Date.now();await log({type:'grading_review_packet',...meta});return result;
  };
  const tools=[{
    name:'read_grading_review',label:'Read complete grading evidence',description:'Read the next pending student/packet with complete source rules and every primary scoring point, including full credit. The dispatch tool already attaches the first packet.',
    parameters:objectSchema({student_id:str}),executionMode:'sequential',execute:async(_id,args)=>packet(args.student_id),
  },{
    name:'inspect_student_answer',label:'Inspect original answer evidence',description:'Read up to four original answer pages for a concrete review question. Page numbers are physical PDF pages. Only this student is accessible. Consume images in the next response; save_report_notes before replacing four active images.',
    parameters:objectSchema({student_id:str,item_ids:{...ids,minItems:1},pages:pageList,question:{type:'string',minLength:8,maxLength:400}}),executionMode:'sequential',
    execute:async(_id,args)=>{
      const d=get(args.student_id),student=students.get(args.student_id);
      const delivered=new Set(receipt('grading_review',args.student_id).flatMap(v=>v.meta.item_ids));
      if(!args.item_ids.length||args.item_ids.some(id=>!delivered.has(id))||new Set(args.item_ids).size!==args.item_ids.length)throw Error('Consume these student/item review records first');
      if(!args.pages.length||args.pages.length>4||typeof args.question!=='string'||args.question.trim().length<8||args.question.length>400)throw Error('Specify up to four pages and a concrete question');
      checkPages(args.pages,student);
      const meta={...structuredClone(args),primary_hash:d.hash,answer_sha256:student.sha256};
      const content=[{type:'text',text:JSON.stringify(meta)}];
      for(const n of args.pages)content.push({type:'text',text:`student ${args.student_id} original physical PDF page ${n}`},await readImage(student.pages.find(p=>p.page===n)));
      const result=views.add('review_answer',content,meta,meta);
      await log({type:'main_answer_inspection',...meta,view_id:result.details.context_view_id});return result;
    },
  },{
    name:'submit_grading_review',label:'Commit substantive main review',description:'Attest every checked item, including full-credit points. Supply complete changed items only, new source issues (usually empty), and brief findings. Final persistence and personal feedback happen only after full item coverage. Never repeat unchanged items.',
    parameters:objectSchema({student_id:str,primary_hash:str,checked_item_ids:{...ids,minItems:1},revised_items:{...COMPACT_POINTS_SCHEMA.properties.items,minItems:0},
      new_source_issues:{type:'array',items:SOURCE_ISSUE_SCHEMA},notes:{type:'array',minItems:1,maxItems:6,items:{...str,maxLength:600}}}),executionMode:'sequential',
    execute:async(_id,args)=>{
      const d=get(args.student_id),frozen=getRubric(),student=students.get(args.student_id);
      if(args.primary_hash!==d.hash)throw Error('Stale primary hash');
      if(views.pending().some(v=>!v.delivered))throw Error('Consume every requested view in a subsequent model response before review submission');
      const delivered=new Set(receipt('grading_review',args.student_id).flatMap(v=>v.meta.item_ids));
      if(!args.checked_item_ids.length||new Set(args.checked_item_ids).size!==args.checked_item_ids.length||args.checked_item_ids.some(id=>!delivered.has(id)||d.checked.has(id)))throw Error('Check unique delivered, not previously committed, items');
      if(!args.notes?.length||args.notes.length>6||args.notes.some(n=>typeof n!=='string'||!n.trim()||n.length>600))throw Error('Keep review findings concise');
      const changed=args.revised_items.map(i=>i.id);
      if(new Set(changed).size!==changed.length||changed.some(id=>!args.checked_item_ids.includes(id)))throw Error('Revised items must be unique checked items');
      const answerViews=receipt('review_answer',args.student_id);
      for(const item of args.revised_items){
        const seen=new Set(answerViews.filter(v=>v.meta.item_ids.includes(item.id)).flatMap(v=>v.meta.pages));
        if(!seen.size||item.p.some(p=>!Array.isArray(p[3])||p[3].some(n=>!seen.has(n))))throw Error('Every revised item requires its cited original answer pages consumed by the main agent');
      }
      const msSeen=new Set(views.delivered('source').filter(v=>v.meta.rubric_hash===frozen.hash).flatMap(v=>v.meta.pages));
      const newIssues=args.new_source_issues.map((issue,index)=>validateSourceIssue(issue,frozen,scheme,msSeen,(d.grade.source_issues??[]).length+index));
      if(newIssues.some(i=>!changed.includes(i.item_id)))throw Error('New source issues require a revised affected item');
      const issues=[...(d.grade.source_issues??[]),...newIssues];
      const raw=compactGrade(d.grade);raw.items=raw.items.map(i=>args.revised_items.find(p=>p.id===i.id)??i);
      raw.source_issues=issues.map(({issue_id,rubric_hash,...issue})=>issue);
      const expanded=expandBriefFullCredit(raw,frozen,student);
      // Preserve untouched rows verbatim, including optional visual annotations and provenance.
      expanded.items=expanded.items.map(i=>changed.includes(i.item_id)?i:d.grade.items.find(p=>p.item_id===i.item_id));
      for(const issue of issues){const item=expanded.items.find(i=>i.item_id===issue.item_id);
        if(!item?.review_required||(issue.blocks_award&&(item.score!==null||issue.point_ids.some(id=>item.point_decisions.find(p=>p.point_id===id)?.score!==null))))throw Error('Existing source uncertainty must remain review/unknown');}
      const coverage=new Set([...student.pages.map(p=>`student:${p.page}`),...scheme.pages.map(p=>`scheme:${p.page}`)]);
      const next=validateGrade({...d.grade,...expanded,source_issues:issues,
        primary_submission_hash:d.grade.primary_submission_hash??d.grade.submission_hash??null,submission_hash:digest(raw)}, {documents:{scheme,student}},coverage);
      const checks=new Set([...d.checked,...args.checked_item_ids]);
      const audit={...structuredClone(args),rubric_hash:frozen.hash,answer_sha256:student.sha256,
        inspected_answer_pages:[...new Set(answerViews.flatMap(v=>v.meta.pages))].sort((a,b)=>a-b),inspected_ms_pages:[...msSeen].sort((a,b)=>a-b),
        changes:changed.map(id=>({item_id:id,before:d.grade.items.find(i=>i.item_id===id),after:next.items.find(i=>i.item_id===id)})),
        checked_item_count:checks.size,elapsed_seconds:(Date.now()-d.started)/1000};
      const binding=await persist(args.student_id,`review-${d.patches.length+1}.json`,audit);
      d.grade=next;d.checked=checks;d.patches.push(audit);
      const remainingDelivered=views.pending().filter(v=>v.kind==='grading_review'&&v.meta.student_id===args.student_id)
        .flatMap(v=>v.meta.item_ids).filter(id=>!checks.has(id));
      if(views.pending().length)views.checkpoint(binding,remainingDelivered.length?['grading_review']:[]);
      if(checks.size===frozen.artifact.items.length){
        const review={primary_hash:d.hash,checked_item_ids:[...checks],checked_point_count:next.items.reduce((n,i)=>n+i.point_decisions.length,0),
          inspected_answer_pages:audit.inspected_answer_pages,inspected_ms_pages:audit.inspected_ms_pages,elapsed_seconds:audit.elapsed_seconds,
          changes:d.patches.flatMap(p=>p.changes),notes:d.patches.flatMap(p=>p.notes),mode:'same_main_agent',coverage:'all point ledgers; original images on demand'};
        next.main_grading_review=review;
        await log({type:'main_grading_review_complete',student_id:args.student_id,...review});
        await d.finalize(next);d.finished=true;await onFinalized(args.student_id);
      }
      if(remainingDelivered.length)return {content:[{type:'text',text:JSON.stringify({student_id:args.student_id,primary_hash:d.hash,
        checked_item_ids:[...checks],remaining_item_ids:remainingDelivered,committed_patch:binding,
        message:'Keep reviewing the full ledger still visible in the current packet; do not reread it. Checked items are committed. Original image tools remain available.'})}],details:{}};
      const following=pending()[0];if(following)return packet(following.id);
      return await afterFinalized?.()??{content:[{type:'text',text:'Review complete; final grades and feedback saved. Continue remaining students or report.'}],details:{}};
    },
  }];
  return {tools,instructions:MAIN_GRADING_REVIEW_PROMPT,hasPending:()=>pending().length>0,
    register({id,primary,primaryPath,finalize}){if(drafts.has(id)||!students.has(id)||primary.rubric_hash!==getRubric().hash)throw Error('Invalid/duplicate primary review draft');
      drafts.set(id,{id,grade:structuredClone(primary),hash:digest(primary),primaryPath,finalize,checked:new Set(),patches:[],finished:false,started:null});},
    prefetch:()=>pending().length?packet(pending()[0].id):null};
}
