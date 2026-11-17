// Independent document scroll containers: comparing MS must not move the answer.
export class PageStream {
  constructor(owner,panel,source,content,continuous) {
    Object.assign(this,{owner,panel,source,continuous});this.views=new Map();this.frame=null;
    this.scroll=document.createElement('div');this.scroll.className='pane-page-scroll'+(continuous?' continuous-pages':'');
    content.replaceChildren(this.scroll);
    const ids=continuous?source.pageIds:[panel.pageId];
    for(const id of ids){
      const page=owner.getState().pages.find(p=>p.id===id),root=document.createElement('div');
      root.className='page-surface';root.dataset.pageSurface=id;
      if(continuous){const label=document.createElement('div');label.className='stream-page-label';label.textContent=`第 ${source.pageIds.indexOf(id)+1} / ${source.pageIds.length} 页`;root.append(label);}
      const body=document.createElement('div');body.className='page-surface-body';root.append(body);this.scroll.append(root);
      const view={id:panel.id,parent:panel,pageId:id,root,gradingTaskId:panel.gradingTaskId,gradingMode:panel.gradingMode};
      this.views.set(id,view);owner.mountPage(view,page,body);
    }
    this.scroll.addEventListener('scroll',()=>{
      if(this.frame)return;
      this.frame=requestAnimationFrame(()=>{this.frame=null;
        if(owner.note?.panel.parent===panel)owner.positionNote();
        if(!continuous)return;
        const box=this.scroll.getBoundingClientRect(),target=box.top+Math.min(140,box.height*.3);
        const visible=[...this.views.values()].filter(v=>{const b=v.root.getBoundingClientRect();return b.bottom>box.top&&b.top<box.bottom;});
        const next=visible.sort((a,b)=>Math.abs(a.root.getBoundingClientRect().top-target)-Math.abs(b.root.getBoundingClientRect().top-target))[0];
        if(next&&next.pageId!==panel.pageId){panel.pageId=next.pageId;owner.renderPanel(panel);owner.persist();}
      });
    },{passive:true});
  }
  update() {
    const {owner,panel}=this,width=Math.max(340,Math.min(960,panel.root.querySelector('.pane-content').clientWidth-24))*panel.zoom;
    const anchor=this.views.get(panel.pageId)?.root.querySelector('.canvas-paper');
    const before=anchor?.getBoundingClientRect(),readingY=this.scroll.getBoundingClientRect().top+Math.min(140,this.scroll.clientHeight*.3);
    const offset=this.width&&this.width!==width&&before?.height?(readingY-before.top)/before.height:null;
    for(const view of this.views.values()){
      view.gradingTaskId=panel.gradingTaskId;view.gradingMode=panel.gradingMode;
      const paper=view.root.querySelector('.canvas-paper');paper.style.width=`${width}px`;paper.style.maxWidth='none';
      const annotated=owner.gradingRows(view).length>0&&view.gradingMode!=='hidden';paper.classList.toggle('with-point-comments',annotated);
      const canvas=view.root.querySelector('canvas');canvas.style.touchAction=owner.mode==='browse'?'auto':'none';canvas.style.cursor=owner.mode==='browse'?'default':'crosshair';canvas.dataset.mode=owner.mode;
      owner.renderPins(view);
    }
    // Keep the same line in view when a review panel or comparison changes width.
    if(offset!==null){const after=anchor.getBoundingClientRect();this.scroll.scrollTop+=after.top+offset*after.height-readingY;}
    this.width=width;
  }
  go(id) {
    const view=this.views.get(id);if(!view)return;
    const top=view.root.getBoundingClientRect().top-this.scroll.getBoundingClientRect().top+this.scroll.scrollTop;
    this.scroll.scrollTo({top:Math.max(0,top),behavior:'instant'});
  }
  destroy(){if(this.frame)cancelAnimationFrame(this.frame);for(const v of this.views.values())v.selection?.destroy();this.views.clear();}
}
