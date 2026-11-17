import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { gradingAnnotations, validAnnotationRect } from '../../web/grading-annotations.mjs';
import { occupancyFromPacked, gradingConnection, layoutPointComments, pointCommentContent,gradingSymbol,layoutGradingSymbols } from '../../web/annotation-layout.mjs';
import {gradingResult,totalText,resultStatus} from '../../web/grading-result.mjs';
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
      id:`G${row.index}`,label:row.label,score:row.scoreLabel,tone:row.tone,mark:row.mark,symbol:gradingSymbol(row),
      evidence:row.evidence||'',condition:row.sourceText||'',reason:row.review?.reason||row.reason,
      reviewed:Boolean(row.review),uncertainties:row.review?[]:row.uncertainties,
      regions:row.regions.map(region=>({rect:region.rect,...(region.precision==='ocr-regions'?{
        precision:region.precision,regionId:region.regionId,regionManifestHash:region.regionManifestHash}: {})})),
      location:row.location,locationNote:row.locationNote,annotationStatus:row.annotationStatus,annotationIssues:row.annotationIssues,guide:row.guide,
    }));
    (state.annotations||[]).filter(note=>!note.archivedAt&&note.target?.kind==='page'
      &&note.target.pageId===pageId&&note.target.pageHash===page.sha256&&validAnnotationRect(note.target.rect))
      .forEach(note=>notes.push({id:`T${(state.annotations||[]).indexOf(note)+1}`,label:'老师注释',score:'',tone:'teacher',
        reason:note.text||'',regions:[{rect:note.target.rect,shape:note.target.shape,points:note.target.points}],location:'region'}));
    for(const note of notes)note.summary=pointCommentContent(note).map(part=>part.text).join(' ');
    return {id:page.id,image:page.path,sha256:page.sha256,sourceId:page.sourceId,sourcePage:page.sourcePage,
      imageToPdf:page.imageToPdf||null,notes};
  });
  // Records without a trustworthy page still appear in the export; never invent
  // a bounding box or silently omit a comment because localization is absent.
  const unplaced=all.filter(note=>!note.studentPageIds.length).map(note=>({id:`G${note.index}`,label:note.label,score:note.scoreLabel,tone:note.tone,
    mark:note.mark,
    evidence:note.evidence||'',condition:note.sourceText||'',reason:note.review?.reason||note.reason,
    reviewed:Boolean(note.review),uncertainties:note.review?[]:note.uncertainties,regions:[],location:'unlocated'}));
  for(const note of unplaced)note.summary=pointCommentContent(note).map(part=>part.text).join(' ');
  const result=gradingResult(state,taskId,groupId);
  const summary=result?{score:totalText(result),scoreUnit:result.feedbackOnly?'':'分',statusText:resultStatus(result),provisional:result.provisional,guide:result.guide,
    items:result.items.map(item=>({id:item.id,score:totalText(item),pages:[...new Set(item.rows.flatMap(r=>r.studentPageIds).map(id=>state.pages.find(p=>p.id===id)?.sourcePage).filter(Boolean))]}))}:null;
  return {version:1,title:state.title,student:group.label,taskId,taskTitle:task.title,status:task.status,resultSummary:summary,
    pages,unplaced,gradingRecordHashes:task.records.filter(row=>row.groupId===groupId).map(row=>row.originalHash)};
}

export function placeExportMarks(packet,occupancy) {
  for(const page of packet.pages) {
    const packed=occupancy[page.id];
    fail(packed?.pageHash===page.sha256,'空白检测与答卷原页不一致，停止导出。',409);
    const mask=occupancyFromPacked(packed,Buffer.from(packed.occupiedBase64,'base64'));
    const width=700,height=width*mask.sourceHeight/mask.sourceWidth;
    for(const note of page.notes)delete note.markPlacement;
    const symbols=layoutGradingSymbols(page.notes.filter(note=>note.symbol),mask,{width,height,
      obstacles:page.notes.filter(note=>!note.mark).flatMap(note=>note.regions.map(region=>region.rect))});
    const comments=layoutPointComments(page.notes,mask,{width,height,fontSize:13,
      measureText:packed.commentGlyphWidths?text=>[...text].reduce((sum,c)=>sum+(packed.commentGlyphWidths[c]??.7)*13,0):undefined,
      obstacles:[...symbols.map(s=>s.rect),...page.notes.filter(note=>!note.mark).flatMap(note=>note.regions.map(region=>region.rect))]});
    page.commentLayout={width,height};
    for(const note of page.notes){
      note.symbolPlacement=symbols.find(s=>s.id===note.id)||null;
      if(note.symbolPlacement)note.symbolPlacement.connection=gradingConnection(mask,note.symbolPlacement,width,height);
      note.commentPlacement=comments.find(comment=>comment.id===note.id);
      if(note.commentPlacement?.sourceRect)note.commentPlacement.connection=gradingConnection(mask,note.commentPlacement,width,height);
    }
  }
  return packet;
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
    const input=join(directory,'annotations.json'),output=join(directory,'annotated.pdf'),occupancy=join(directory,'occupancy.json');
    await writeFile(input,JSON.stringify(packet),{mode:0o600});
    await promisify(execFile)(python,[join(experimentRoot,'annotation_space.py'),'--input',input,'--output',occupancy],
      {timeout:120000,maxBuffer:1024*1024,env:{PATH:process.env.PATH}});
    placeExportMarks(packet,JSON.parse(await readFile(occupancy,'utf8')));
    await writeFile(input,JSON.stringify(packet),{mode:0o600});
    await promisify(execFile)(python,[join(experimentRoot,'annotation_pdf.py'),'--input',input,'--output',output],
      {timeout:120000,maxBuffer:1024*1024,env:{PATH:process.env.PATH}});
    return {bytes:await readFile(output),name:`${packet.student||'答卷'}-批改批注.pdf`};
  } finally { await rm(directory,{recursive:true,force:true}); }
}
