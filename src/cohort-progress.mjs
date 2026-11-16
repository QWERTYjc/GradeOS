import {access,writeFile,rename} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const phases={preparing:'准备材料',coordination:'安排批改',ms_compilation:'整理评分标准',ms_verification:'核对评分标准',student_self_review:'批改子agent自查',student_grading:'批改答卷',exception_review:'核对例外给分',source_permission_review:'核对源规则',student_feedback:'生成个人反馈',reporting:'整理汇总报告'};
const terminal=new Set(['completed','partial','failed','cancelled','preflight']);
const money=n=>`$${n.toFixed(5)}`;
const elapsed=n=>n<60?`${Math.floor(n)}秒`:`${Math.floor(n/60)}分${Math.floor(n%60)}秒`;
const safeId=id=>/^[A-Za-z0-9_-]{1,64}$/.test(id);
const allowedEvents=new Set(['request_admitted','request_terminal','first_output_delta','student_task_start','student_task_terminal','grading_result_saved','stage_start','stage_terminal','rubric_ready','report_submitted','request_rejected_before_send']);

// A read-only projection of execution events. No raw model content or retry decisions enter it.
export class CohortProgress {
  constructor({directory,studentIds,reusedRubric=false,reasonStyle='detailed',clock=()=>Date.now(),writeLine=line=>console.log(line)}) {
    if(!studentIds.length||new Set(studentIds).size!==studentIds.length||!studentIds.every(safeId))throw Error('Invalid progress roster');
    this.directory=resolve(directory);this.clock=clock;this.writeLine=writeLine;this.started=clock();this.requests=new Map();this.queue=Promise.resolve();this.timer=null;this.lastMessage='';this.warningSent=false;this.announcedPhases=new Set();
    this.state={version:1,status:'preparing',phase:'preparing',phase_label:phases.preparing,started_at:new Date(this.started).toISOString(),updated_at:new Date(this.started).toISOString(),elapsed_seconds:0,
      rubric:reusedRubric?'reused':'pending',reason_style:reasonStyle,students:studentIds.map(id=>({id,status:'waiting',grading_saved:false,feedback_status:'pending',review_required:false,report_url:null})),
      counts:{total:studentIds.length,grading_saved:0,completed:0,failed:0,cancelled:0,review_required:0},requests:{admitted:0,settled:0,in_flight:0,unknown_cost:0},settled_cost_usd:0,cost_complete:false,active_phases:[],message:'准备材料',next_action:'',reports:[]};
  }
  enqueue(fn){const task=this.queue.then(fn);this.queue=task.catch(()=>{if(!this.warningSent){this.warningSent=true;this.writeLine('进度显示暂时不可用；批改和原始运行记录继续保存。');}});return this.queue;}
  async save(message,{announce=false}={}){
    this.state.updated_at=new Date(this.clock()).toISOString();
    if(!terminal.has(this.state.status))this.state.elapsed_seconds=Math.max(0,(this.clock()-this.started)/1000);
    const rows=this.state.students;
    this.state.counts={total:rows.length,grading_saved:rows.filter(r=>r.grading_saved).length,completed:rows.filter(r=>r.status==='submitted'&&r.feedback_status==='submitted').length,
      failed:rows.filter(r=>r.status==='failed'||r.feedback_status==='failed').length,cancelled:rows.filter(r=>r.status==='cancelled').length,review_required:rows.filter(r=>r.review_required).length};
    const requests=[...this.requests.values()];
    if(!terminal.has(this.state.status)){
      this.state.requests={admitted:requests.length,settled:requests.filter(r=>r.terminal&&r.status==='provider_reported').length,in_flight:requests.filter(r=>!r.terminal).length,unknown_cost:requests.filter(r=>r.terminal&&r.status!=='provider_reported').length};
      this.state.settled_cost_usd=requests.filter(r=>r.terminal&&r.status==='provider_reported').reduce((sum,r)=>sum+r.cost_usd,0);
      this.state.active_phases=[...new Set(requests.filter(r=>!r.terminal).map(r=>r.phase))];
    }
    if(message)this.state.message=message;
    const path=resolve(this.directory,'progress.json'),pending=path+'.pending';
    await writeFile(pending,JSON.stringify(this.state,null,2)+'\n',{mode:0o600});await rename(pending,path);
    if(announce&&message&&message!==this.lastMessage){this.writeLine(message);this.lastMessage=message;}
  }
  start(){return this.enqueue(async()=>{
    this.state.status='running';
    await this.save(`开始处理 ${this.state.students.length} 份答卷 · ${this.state.rubric==='reused'?'复用已有评分标准':'评分标准整理一次，供全部答卷共用'} · ${this.state.reason_style==='brief-full-credit'?'普通满分点使用短理由':'保留详细理由'}。`,{announce:true});
    this.timer=setInterval(()=>void this.heartbeat(),25000);this.timer.unref();
  });}
  studentForLane(lane){return this.state.students.find(r=>lane===`student-${r.id}`||lane===`feedback-${r.id}`||lane===`source-review-${r.id}`||new RegExp(`^exception-${r.id}-[0-9]+$`).test(lane));}
  observe(event){
    if(!allowedEvents.has(event.type))return Promise.resolve();
    // Select fields before queuing: request objects are mutable and raw events can contain private content.
    const e={type:event.type,lane:event.lane,phase:event.phase,student_id:event.student_id,status:event.status,review_status:event.review_status,feedback_status:event.feedback_status,number:event.number,
      request:event.request?{number:event.request.number,lane:event.request.lane,phase:event.request.phase,status:event.request.status,cost_usd:event.request.cost_usd}:null};
    return this.enqueue(async()=>{
      if(terminal.has(this.state.status))return;
      let message=null;
      if(e.type==='request_admitted'){
        const r=e.request;if(!this.requests.has(r.number))this.requests.set(r.number,{...r,terminal:false});
        const student=this.studentForLane(r.lane);if(student&&student.status!=='submitted')student.status=r.phase==='student_feedback'?'feedback':'grading';
        this.state.phase=r.phase;this.state.phase_label=phases[r.phase]??'处理任务';
        if(!this.announcedPhases.has(r.phase)){this.announcedPhases.add(r.phase);message=`${this.state.phase_label}${student?` · 答卷 ${student.id}`:''}。`;}
      }else if(e.type==='request_terminal'){
        const r=e.request;this.requests.set(r.number,{...r,terminal:true});
      }else if(e.type==='student_task_start'){
        const row=this.state.students.find(r=>r.id===e.student_id);if(row)row.status='grading';
      }else if(e.type==='grading_result_saved'){
        const row=this.state.students.find(r=>r.id===e.student_id);if(row){row.grading_saved=true;row.review_required=e.review_status==='review_required';}
      }else if(e.type==='student_task_terminal'){
        const row=this.state.students.find(r=>r.id===e.student_id);if(row){row.status=e.status;row.grading_saved=row.grading_saved||e.status==='submitted';row.feedback_status=e.feedback_status??row.feedback_status;row.review_required=e.review_status==='review_required';
          if(row.status==='submitted'&&row.feedback_status==='submitted'){
            const report=await this.reportLink(resolve(this.directory,`feedback-${row.id}/REPORT.zh-CN.md`),`答卷 ${row.id} 个人报告`,row.id);row.report_url=report?.url??null;
            message=`答卷 ${row.id} 的批改与个人反馈已保存${row.review_required?'，有待审阅项':''}。${report?'\n个人报告：'+report.url:''}`;
          }
          else if(row.status==='submitted')message=`答卷 ${row.id} 的分数已保存，个人反馈尚未完成。`;
          else message=`答卷 ${row.id} ${row.status==='cancelled'?'已停止':'未完成'}，已有记录保留。`;
        }
      }else if(e.type==='rubric_ready'){
        this.state.rubric='ready';message='评分标准已保存，开始安排答卷批改。';
      }else if(e.type==='request_rejected_before_send')message='本轮已停止发送新请求，正在保存现有结果；请查看结束说明。';
      await this.save(message,{announce:Boolean(message)});
    });
  }
  heartbeat(){return this.enqueue(async()=>{
    if(terminal.has(this.state.status))return;
    const active=[...new Set([...this.requests.values()].filter(r=>!r.terminal).map(r=>phases[r.phase]??'处理任务'))];
    const label=this.state.status==='stopping'?'停止任务并保存已有结果':active.length?active.join('、'):'保存结果或执行本地工具';
    await this.save(`仍在${label} · 个人反馈完成 ${this.state.counts.completed}/${this.state.counts.total} 份 · 已用 ${elapsed((this.clock()-this.started)/1000)} · 已结算 ${money(this.state.settled_cost_usd)}${this.state.requests.unknown_cost?'，另有费用待确认':''}。`,{announce:true});
  });}
  stop(){clearInterval(this.timer);this.timer=null;}
  cancelRequested(){return this.enqueue(async()=>{
    if(terminal.has(this.state.status))return;this.state.status='stopping';
    await this.save('正在停止任务。已完成的评分和报告会保留，未完成的答卷不会自动重新批改。',{announce:true});
  });}
  failBeforeRun(message){this.stop();return this.enqueue(async()=>{
    this.state.status='failed';this.state.phase='finished';this.state.phase_label='尚未开始';this.state.elapsed_seconds=0;this.state.cost_complete=true;
    this.state.next_action=message;await this.save(`尚未开始批改，未调用模型。${message}`,{announce:true});
  });}
  async reportLink(path,label,studentId=null){try{await access(path);const existing=this.state.reports.find(row=>row.path===path);if(existing)return existing;const row={label,url:pathToFileURL(path).href,path,...(studentId?{student_id:studentId}:{})};this.state.reports.push(row);return row;}catch{return null;}}
  finish(summary,{cancelled=false}={}){
    this.stop();
    return this.enqueue(async()=>{
      this.state.status=cancelled?'cancelled':summary.status==='submitted'?'completed':summary.students?.some(r=>r.status==='submitted')?'partial':'failed';
      this.state.phase='finished';this.state.phase_label=this.state.status==='completed'?'批改与报告已完成':this.state.status==='cancelled'?'已停止':'部分工作未完成';
      this.state.elapsed_seconds=summary.elapsed_including_image_preparation_seconds??summary.elapsed_seconds;
      this.state.settled_cost_usd=summary.provider_reported_cost_usd;
      this.state.requests={admitted:summary.admitted_requests,settled:summary.requests.filter(r=>r.status==='provider_reported').length,in_flight:0,unknown_cost:summary.unknown_cost_requests};
      this.state.cost_complete=summary.cost_receipts_complete;this.state.active_phases=[];this.state.reports=[];
      for(const row of this.state.students){
        const final=summary.students.find(s=>s.student_id===row.id);if(final){row.status=final.status;row.grading_saved=row.grading_saved||final.status==='submitted';row.feedback_status=final.feedback_status??'unavailable';row.review_required=final.review_status==='review_required';row.total_score=Number.isFinite(final.total_score)?final.total_score:null;}
        if(row.grading_saved)await this.reportLink(resolve(this.directory,`student-${row.id}/grading.json`),`答卷 ${row.id} 评分依据`,row.id);
        if(row.feedback_status==='submitted'){const link=await this.reportLink(resolve(this.directory,`feedback-${row.id}/REPORT.zh-CN.md`),`答卷 ${row.id} 个人报告`,row.id);row.report_url=link?.url??null;}
      }
      if(summary.report_submitted)await this.reportLink(resolve(this.directory,'REPORT.zh-CN.md'),'汇总报告');
      const review=this.state.students.filter(r=>r.review_required).length;
      this.state.next_action=this.state.status==='completed'?(review?'打开个人报告，先查看待审阅项。':'打开个人报告查看总结与逐题建议。'):'先查看已保存的个人报告和运行摘要；本次不会自动重新批改。';
      await this.save(`${this.state.phase_label} · 用时 ${elapsed(this.state.elapsed_seconds)} · ${this.state.cost_complete?'实付':'已结算'} ${money(this.state.settled_cost_usd)}${this.state.requests.unknown_cost?`，${this.state.requests.unknown_cost} 个请求费用待确认`:''}。`,{announce:true});
      if(this.state.students.length===1&&this.state.students[0].status==='submitted')this.writeLine(`本份总分：${this.state.students[0].total_score===null?'待定':this.state.students[0].total_score+'（暂定）'}。`);
      this.writeLine(`完成批改与反馈 ${this.state.counts.completed}/${this.state.counts.total} 份${review?`；${review} 份有待审阅项`:''}。${this.state.next_action}`);
      for(const report of this.state.reports.slice(0,6))this.writeLine(`${report.label}：${report.url}`);
      if(this.state.reports.length>6)this.writeLine(`其余个人报告见汇总报告或 ${this.directory}`);
      this.writeLine(`结果目录：${this.directory}`);
    });
  }
  preflight(){this.stop();return this.enqueue(async()=>{
    this.state.status='preflight';this.state.phase='preflight';this.state.phase_label='配置已检查';this.state.elapsed_seconds=(this.clock()-this.started)/1000;this.state.cost_complete=true;
    this.state.next_action='配置已保存。需要实际批改时使用新输出目录并加 --execute。';
    await this.save(`配置已检查 · ${this.state.students.length} 份答卷 · ${this.state.rubric==='reused'?'复用已有评分标准':'将整理一次评分标准'} · 本次未调用模型、未产生费用。`,{announce:true});
    this.writeLine(this.state.next_action);this.writeLine(`运行计划：${pathToFileURL(resolve(this.directory,'plan.json')).href}`);
  });}
}
