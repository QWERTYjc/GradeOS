import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { gradingAnnotations, validAnnotationRect } from '../../web/grading-annotations.mjs';
import { digest } from '../core.mjs';
import { fail } from './store.mjs';
import { experimentRoot, python } from './documents.mjs';

export function annotationExportPacket(state, taskId, groupId) {
  const task=state.tasks.find(row=>row.id===taskId),group=task?.groups?.find(row=>row.id===groupId);
  fail(task?.kind==='grade'&&group&&task.records?.some(row=>row.groupId===groupId),'这份答卷还没有可导出的批改结果。',404);
  const current=state.groups.find(row=>row.id===groupId);
  fail(JSON.stringify(current?.pageIds)===JSON.stringify(group.pageIds),'答卷划分已改变，请使用当前答卷的批改结果。',409);
  const all=gradingAnnotations(state,taskId,groupId);
  const pages=group.pageIds.map(pageId=>{
    const page=state.pages.find(row=>row.id===pageId),frozen=task.pages?.find(row=>row.id===pageId);
    fail(page?.active!==false&&page&&(frozen?.sha256||task.pageHashes?.[pageId])===page.sha256,'答卷原页已改变，无法导出这份旧批改。',409);
    fail(!page.imageToPdf||validAnnotationRect(page.imageToPdf),'原页坐标映射无效，停止导出。',409);
    const notes=gradingAnnotations(state,taskId,groupId,pageId).map(row=>({
      id:`G${row.index}`,label:row.label,score:row.scoreLabel,tone:row.tone,
      evidence:row.evidence||'',condition:row.sourceText||'',reason:row.review?.reason||row.reason,
      reviewed:Boolean(row.review),uncertainties:row.review?[]:row.uncertainties,
      regions:row.regions.map(region=>({rect:region.rect})),
      location:row.location,guide:row.guide,
    }));
    (state.annotations||[]).filter(note=>!note.archivedAt&&note.target?.kind==='page'
      &&note.target.pageId===pageId&&note.target.pageHash===page.sha256&&validAnnotationRect(note.target.rect))
      .forEach(note=>notes.push({id:`T${(state.annotations||[]).indexOf(note)+1}`,label:'老师注释',score:'',tone:'teacher',
        reason:note.text||'',regions:[{rect:note.target.rect,shape:note.target.shape,points:note.target.points}],location:'region'}));
    return {id:page.id,image:page.path,sha256:page.sha256,sourceId:page.sourceId,sourcePage:page.sourcePage,
      imageToPdf:page.imageToPdf||null,notes};
  });
  // Records without a trustworthy page still appear in the export; never invent
  // a bounding box or silently omit a comment because localization is absent.
  const unplaced=all.filter(note=>!note.studentPageIds.length).map(note=>({id:`G${note.index}`,label:note.label,score:note.scoreLabel,tone:note.tone,
    evidence:note.evidence||'',condition:note.sourceText||'',reason:note.review?.reason||note.reason,regions:[],location:'unlocated'}));
  return {version:1,title:state.title,student:group.label,taskId,taskTitle:task.title,status:task.status,
    pages,unplaced,gradingRecordHashes:task.records.filter(row=>row.groupId===groupId).map(row=>row.originalHash)};
}

export async function exportAnnotatedPdf(store,taskId,groupId) {
  const packet=annotationExportPacket(store.snapshot(),taskId,groupId);
  for(const page of packet.pages) {
    fail(digest(await readFile(page.image))===page.sha256,'答卷图片已改变，停止导出。',409);
    const directory=join(store.directory,'uploads',page.sourceId);
    try {
      const original=await readFile(join(directory,'source'));
      const manifest=JSON.parse(await readFile(join(directory,'manifest.json'),'utf8'));
      fail(digest(original)===manifest.sha256,'上传原件已改变，停止导出。',409);
      if(original.subarray(0,5).toString()==='%PDF-')page.originalPdf=join(directory,'source');
    } catch(error) { if(error.code!=='ENOENT')throw error; }
  }
  const directory=await mkdtemp(join(tmpdir(),'gradeos-annotations-'));
  try {
    const input=join(directory,'annotations.json'),output=join(directory,'annotated.pdf');
    await writeFile(input,JSON.stringify(packet),{mode:0o600});
    await promisify(execFile)(python,[join(experimentRoot,'annotation_pdf.py'),'--input',input,'--output',output],
      {timeout:120000,maxBuffer:1024*1024,env:{PATH:process.env.PATH}});
    return {bytes:await readFile(output),name:`${packet.student||'答卷'}-批改批注.pdf`};
  } finally { await rm(directory,{recursive:true,force:true}); }
}
