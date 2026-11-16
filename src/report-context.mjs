import { digest } from './core.mjs';
import { checkPages, objectSchema } from './rubric-contract.mjs';

export function rubricOverview(frozen) {
  return {rubric_hash:frozen.hash,source_sha256:frozen.artifact.source_sha256,
    general_instructions:frozen.artifact.general_instructions,unresolved_notes:frozen.artifact.unresolved_notes,
    items:frozen.artifact.items.map(({item_id,question_id,max_score,source_pages,requires_source_image,image_reason,uncertainties,related_item_ids})=>
      ({item_id,question_id,max_score,source_pages,requires_source_image,image_reason,uncertainties,related_item_ids})),
    required_ms_pages:[...new Set(frozen.artifact.items.filter(i=>i.requires_source_image).flatMap(i=>i.source_pages))].sort((a,b)=>a-b),
    authority:'Navigation only. Students receive the complete immutable rubric; inspect selected source or saved point evidence for full conditions.'};
}

// The transcript and immutable records retain full content. Only future model context is compacted.
// A successful subsequent assistant response confirms that a view was in its input; executing
// a read and a checkpoint in the same assistant tool batch cannot claim consumption of that view.
export function createReportContext() {
  const views=new Map();let exposed=new Set();let next=0;
  return {
    add(kind,content,compact,meta={}) {
      const textBytes=content.filter(p=>p.type==='text').reduce((n,p)=>n+Buffer.byteLength(p.text),0);
      const images=content.filter(p=>p.type==='image').length;
      const pending=[...views.values()].filter(v=>!v.checkpoint);
      if (images+pending.reduce((n,v)=>n+v.images,0)>4) throw Error('Save notes on the delivered source view before opening another source image set (four active pages maximum).');
      if (textBytes+pending.reduce((n,v)=>n+v.textBytes,0)>150000) throw Object.assign(Error('Pending report evidence is large. Save notes before reading more; request fewer students/items in one call.'),{code:'REPORT_VIEW_CAPACITY'});
      const view={id:`view-${++next}`,kind,hash:digest(content),compact,meta,textBytes,images,delivered:false,checkpoint:null};
      views.set(view.id,view);
      return {content,details:{context_view_id:view.id}};
    },
    transform(messages) {
      exposed=new Set();
      let latestAnalysis;
      for (const message of messages) {
        const view=views.get(message.details?.context_view_id);
        if (view?.kind==='analysis'&&view.delivered) latestAnalysis=view;
      }
      return messages.map(message=>{
        const id=message.details?.context_view_id;const view=views.get(id);
        if (!view) return message;
        if (view.kind==='analysis'&&view.delivered&&latestAnalysis?.id!==id&&latestAnalysis?.hash===view.hash)
          return {...message,content:[{type:'text',text:JSON.stringify({view_id:id,content_hash:view.hash,same_content_as:latestAnalysis.id,message:'The same immutable analytics are retained in the later delivered view.'})}]};
        if (!view.checkpoint) {exposed.add(id);return message;}
        return {...message,content:[{type:'text',text:JSON.stringify({view_id:id,kind:view.kind,content_hash:view.hash,
          checkpoint:view.checkpoint,retained:view.compact,
          retrieval:'Full content remains in the immutable files and transcript. Use the same scoped tools to reread.'})}]};
      });
    },
    confirmDelivery() {for (const id of exposed) views.get(id).delivered=true;exposed=new Set();},
    pending() {return [...views.values()].filter(v=>!v.checkpoint);},
    delivered(kind) {return [...views.values()].filter(v=>v.delivered&&(!kind||v.kind===kind));},
    checkpoint(binding,retainKinds=[]) {
      const pending=this.pending();
      if (!pending.length || pending.some(v=>!v.delivered)) throw Error('Evidence must reach a subsequent model response before notes can checkpoint it.');
      const released=pending.filter(v=>!retainKinds.includes(v.kind));
      for (const view of released) view.checkpoint=binding;
      return released.map(v=>({view_id:v.id,kind:v.kind,content_hash:v.hash,meta:v.meta}));
    },
  };
}

export function createSourceInspection({getRubric,scheme,readImage,views,log}) {
  return {name:'inspect_ms',label:'Inspect scoped MS source',
    description:'After MS freezing, inspect original pages for a specific question about selected items. Not a full-MS preflight. Save report notes before replacing an active four-page image view.',
    parameters:objectSchema({item_ids:{type:'array',minItems:1,maxItems:4,uniqueItems:true,items:{type:'string',minLength:1}},
      pages:{type:'array',minItems:1,maxItems:4,uniqueItems:true,items:{type:'integer',minimum:1}},question:{type:'string',minLength:8,maxLength:400}}),executionMode:'sequential',
    execute:async (_id,args)=>{
      const frozen=getRubric();if (!frozen) throw Error('Review and freeze the MS first.');
      if (!args.item_ids?.length||args.item_ids.length>4||new Set(args.item_ids).size!==args.item_ids.length||
        !args.pages?.length||args.pages.length>4||new Set(args.pages).size!==args.pages.length||
        typeof args.question!=='string'||args.question.trim().length<8||args.question.length>400) throw Error('Specify up to four source items/pages and a concrete source question.');
      const items=args.item_ids.map(id=>frozen.artifact.items.find(item=>item.item_id===id));
      if (items.some(item=>!item)) throw Error('Unknown source item.');
      checkPages(args.pages,scheme);
      const related=new Set(items.flatMap(item=>item.related_item_ids));
      const allowed=new Set([...items.flatMap(item=>item.source_pages),...frozen.artifact.items.filter(item=>related.has(item.item_id)).flatMap(item=>item.source_pages),...frozen.artifact.general_instructions.flatMap(rule=>rule.source_pages)]);
      if (args.pages.some(page=>!allowed.has(page))) throw Error('Requested source page is unrelated to the selected items or general rules.');
      const binding={rubric_hash:frozen.hash,source_sha256:scheme.sha256,item_ids:args.item_ids,pages:args.pages,question:args.question};
      const content=[{type:'text',text:JSON.stringify({...binding,items,general_instructions:frozen.artifact.general_instructions})}];
      for (const n of args.pages) content.push({type:'text',text:`scheme physical PDF page ${n}`},await readImage(scheme.pages.find(page=>page.page===n)));
      const result=views.add('source',content,binding,binding);
      await log({type:'scoped_ms_inspection',...binding,view_id:result.details.context_view_id});
      return result;
    },
  };
}
