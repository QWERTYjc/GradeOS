import {markingGuideMarkdown} from './marking-guide.mjs';
import {digest} from './core.mjs';

// Only replace byte-identical, generated source sections. Every teacher edit,
// deletion, added note and reordered section stays in its original position.
// The receiver already has the entire frozen rubric. No summarizing model runs.
export function guideSourceSections(frozen) {
  const template=markingGuideMarkdown(frozen,'Source template');
  const markers=['\n## 通用规则\n',...frozen.artifact.items.map(item=>`\n## ${item.item_id} · ${item.max_score} 分\n`),'\n## 待确认与复核\n'];
  const ids=['general_instructions',...frozen.artifact.items.map(item=>`item:${item.item_id}`)];
  const sections=new Map();
  // A teacher/source may itself quote Markdown headings. In that case a
  // textual split cannot safely stand for a whole source item: send all text.
  if(markers.some(marker=>template.indexOf(marker)!==template.lastIndexOf(marker)))return sections;
  for(let index=0;index<ids.length;index++) {
    const start=template.indexOf(markers[index]),end=template.indexOf(markers[index+1],start+markers[index].length);
    if(start<0||end<start)throw Error('Generated guide source section is ambiguous');
    sections.set(ids[index],template.slice(start,end));
  }
  return sections;
}

export function unpackGuide(parts,frozen) {
  const sections=guideSourceSections(frozen);
  return parts.map(part=>{
    if(typeof part==='string')return part;
    if(!part||Object.keys(part).join(',')!=='source_section'||!sections.has(part.source_section))throw Error('Invalid guide source reference');
    return sections.get(part.source_section);
  }).join('');
}

export function packGuide(guide,frozen) {
  if(!guide||digest(guide.body)!==guide.hash)throw Error('Approved guide hash mismatch');
  let parts=[guide.body];
  for(const [id,section] of guideSourceSections(frozen)) {
    if(!section.length)continue;
    parts=parts.flatMap(part=>{
      if(typeof part!=='string')return [part];
      const pieces=part.split(section),result=[];
      for(let index=0;index<pieces.length;index++) {
        if(index)result.push({source_section:id});
        if(pieces[index])result.push(pieces[index]);
      }
      return result;
    });
  }
  if(unpackGuide(parts,frozen)!==guide.body)throw Error('Implementation document changed during transport deduplication');
  return {revision:guide.revision,hash:guide.hash,encoding:'source-sections-v1',parts};
}

export function guideWireText(guide,frozen) {
  return 'Teacher-confirmed implementation document, losslessly deduplicated against the complete frozen rubric above. '
    +'Read parts in order. A source_section reference stands for the unchanged generated Markdown section: general_instructions means all general rules in order with source pages; item:<id> means that entire rubric item, including criteria, every point, condition, source text, awards, dependencies, routes and source notes. '
    +'String parts are exact approved document text, including all teacher changes. Omitted or modified sections are never replaced by a reference. '
    +'The host reconstructed these parts and verified the exact approved Markdown hash before sending. Apply that version; source conflicts remain unresolved for teacher review.\n'
    +JSON.stringify(packGuide(guide,frozen));
}

// The frozen rubric describes every field. Transport scoring points as rows so
// a long paper does not repeat those field names for every single decision.
export function rubricWireText(artifact) {
  const columns = ['point_id','award_type','max_score','allowed_awards','source_pages','depends_on','condition','source_text'];
  const items = artifact.items.map(item => ({ ...item, scoring_points: item.scoring_points.map(point => {
    if (Object.keys(point).some(key => !columns.includes(key)) || columns.some(key => !Object.hasOwn(point, key))) return point;
    return columns.map(key => key === 'source_text' && point.source_text === point.condition ? null : point[key]);
  }) }));
  return 'Scoring point row columns: ' + JSON.stringify(columns) + '. A null source_text repeats the exact condition. Named objects retain all their fields.\n'
    + JSON.stringify({ ...artifact, items });
}
