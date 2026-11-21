import { annotationEvidenceHash } from './inline-annotations.mjs';

export const resultAwardType = type => /^(a|accuracy|result)$/iu.test(type);

function parsePageBands(value) {
  const match=typeof value==='string'&&/^([1-9]\d*):([1-8])(?:[-–]([1-8]))?$/u.exec(value);
  if(!match)return null;
  const page=Number(match[1]),first=Number(match[2]),last=Number(match[3]??match[2]);
  return Number.isSafeInteger(page)&&last>=first ? {page,first,last} : null;
}

export function parseResultPage(value) {
  return parsePageBands(value)?.page??null;
}

export function parseResultLocation(value) {
  const region=parsePageBands(value);
  return region&&region.last-region.first<=1 ? region : null;
}

function originalBand(layout, first, last, representation, page) {
  const top = Math.max(0, (first - 1.5) / 8);
  const bottom = Math.min(1, (last + .5) / 8);
  if (representation === 'original') return [0, Math.floor(top * 1000), 1000, Math.ceil(bottom * 1000) - Math.floor(top * 1000)];
  if (representation !== 'resized_overview' || layout?.original_sha256 !== page.sha256 || !layout.source_binding_verified)
    return null;
  const [width, height] = layout.original_size ?? [];
  const [left, start, right, end] = layout.bbox ?? [];
  if (![width,height,left,start,right,end].every(Number.isSafeInteger) || left<0 || start<0 ||
    right<=left || end<=start || right>width || end>height) return null;
  const y = Math.floor(1000 * (start + top * (end-start)) / height);
  const y2 = Math.ceil(1000 * (start + bottom * (end-start)) / height);
  return [0,y,1000,y2-y];
}

export function bindResultLocations(submission, grade, frozen, student, geometry, receipts) {
  const locations = [];
  const delivered = [...receipts];
  const observations = submission.observations
    ? Object.entries(submission.observations).map(([id, points])=>({id,p:Object.entries(points).map(([pointId,row])=>
      ({id:pointId,v:row.v,f:row.t}))}))
    : submission.items;
  for (const rawItem of observations) {
    const item = grade.items.find(row=>row.item_id===rawItem.id);
    const rules = frozen.artifact.items.find(row=>row.item_id===rawItem.id);
    for (const raw of rawItem.p) {
      const location=parseResultLocation(raw.v);
      if (!location || typeof raw.f!=='string' || !raw.f.trim() ||
        !resultAwardType(rules?.scoring_points.find(point=>point.point_id===raw.id)?.award_type??'')) continue;
      const {page:number,first,last}=location;
      const point = item?.point_decisions.find(row=>row.point_id===raw.id);
      const page = student.pages.find(row=>row.page===number);
      if (!page || !point?.student_pages.includes(number)) continue;
      const receipt = delivered.find(row=>row.role==='student'&&row.page===number&&row.original_sha256===page.sha256);
      if (!receipt) continue;
      const region = originalBand(geometry.find(row=>row.page===number), first, last, receipt.representation, page);
      if (!region || region[3]<2) continue;
      locations.push({item_id:item.item_id,point_id:point.point_id,page:number,page_sha256:page.sha256,
        image_hash:receipt.image_hash,evidence_hash:annotationEvidenceHash(point),region});
    }
  }
  return locations;
}

export function boundResultLocation(primary, student, itemId, point) {
  const location = primary.primary_result_locations?.find(row=>row.item_id===itemId&&row.point_id===point.point_id);
  const page = student.pages.find(row=>row.page===location?.page);
  if (!page || location.page_sha256!==page.sha256 || !point.student_pages.includes(page.page) ||
    annotationEvidenceHash(point)!==location.evidence_hash || !primary.image_delivery_receipts?.some(receipt=>
      receipt.role==='student'&&receipt.page===page.page&&receipt.original_sha256===page.sha256&&receipt.image_hash===location.image_hash)) return null;
  const region=location.region;
  if(!Array.isArray(region)||region.length!==4||!region.every(Number.isSafeInteger)||region[0]!==0||region[2]!==1000||
    region[1]<0||region[3]<2||region[3]>376||region[1]+region[3]>1000)return null;
  return location;
}
