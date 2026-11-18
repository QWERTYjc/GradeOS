import { digest } from './core.mjs';
import { validateOCRRegions } from './ocr-regions.mjs';
import { alignOCRReferences } from './ocr-reference-alignment.mjs';

// Only source-bound local OCR can supply annotation geometry.
export function splitInlineAnnotations(raw) {
  const grading = structuredClone(raw), annotations = new Map();
  for (const item of grading.items || []) for (const point of item.p || []) {
    if (!Array.isArray(point) || ![6, 7].includes(point.length)) throw Error('Expected six grading cells and optional annotation regions');
    annotations.set(JSON.stringify([item.id, point[0]]), point.length === 7 ? point.pop() : undefined);
  }
  return { grading, annotations };
}

export const annotationEvidenceHash = point => digest({ evidence: point.evidence, student_pages: point.student_pages });

export function annotationFrame(page, representation, geometry = null) {
  if (representation !== 'source_regions') throw Error('Annotation frames require local OCR regions');
  const regions = validateOCRRegions(page, geometry);
  const [ow, oh] = geometry.original_size || [], [cw, ch] = geometry.content_size || [];
  const [iw, ih] = geometry.size || [], [x, y, right, bottom] = geometry.source_rect_in_image || [];
  if (!geometry.source_coverage_verified || geometry.overlay !== 'local-ocr-regions-v1'
    || ![ow, oh, cw, ch, iw, ih, x, y, right, bottom].every(Number.isSafeInteger)
    || Math.min(ow, oh, cw, ch, iw, ih) <= 0 || x < 0 || y < 0 || right > iw || bottom > ih
    || right - x !== cw || bottom - y !== ch || Math.abs(cw * oh - ch * ow) > Math.max(ow, oh)) throw Error('Invalid complete OCR page geometry');
  return { page: page.page, pageHash: page.sha256, representation, regions,
    regionManifestHash: geometry.region_manifest_sha256,
    originalSize: geometry.original_size, imageSize: geometry.size, sourceRectInImage: geometry.source_rect_in_image };
}

export function decodeAnnotationRegions(raw, point, student, frames, receipts) {
  const empty = status => ({ status, evidence_hash: annotationEvidenceHash(point), regions: [], origin: 'local-ocr-regions' });
  if (raw === undefined) return empty('missing');
  if (raw === 'absent') return { ...empty('absent'), location_note: 'Model explicitly reports no visible answer evidence.' };
  if (typeof raw === 'string' && /^unlocated:\s*\S/i.test(raw)) return { ...empty('unlocated'), location_note: raw.slice(raw.indexOf(':') + 1).trim() };
  if(typeof point.evidence==='string'&&!/[\p{L}\p{N}]/u.test(point.evidence))
    return {...empty('unlocated'),location_note:'The supplied excerpt contains only punctuation, so it cannot identify the cited step.',issues:['non_identifying_excerpt']};
  // A single region ID is the same location as a one-element list. It
  // still passes every syntax, page binding and bounds check below.
  if (typeof raw === 'string') raw = [raw];
  if (Array.isArray(raw) && raw.length === 0) return empty('unlocated');
  if (!Array.isArray(raw) || raw.length > 12) return { ...empty('invalid'), issue: 'invalid_region_list' };
  const regions = [], errors = [];
  for (const reference of new Set(raw)) {
    const match = typeof reference === 'string' && /^(i[1-9]\d*)\.r[1-9]\d*$/.exec(reference);
    if (!match) { errors.push('ocr_region_id_required'); continue; }
    const frameId = match[1], frame = frames.get(frameId);
    const page = student.pages.find(p => p.page === frame?.page);
    const region = frame?.regions?.find(r => r.id === reference);
    const receipt = [...receipts.values()].find(r => r.annotation_frame === frameId && r.role === 'student'
      && r.page === page?.page && r.original_sha256 === page?.sha256 && r.representation === 'source_regions'
      && r.region_manifest_sha256 === frame?.regionManifestHash);
    if (frame?.representation !== 'source_regions' || !page || !point.student_pages.includes(page.page) || frame.pageHash !== page.sha256 || !receipt || !region) {
      errors.push('unbound_ocr_region'); continue;
    }
    for(const localRect of region.rects||[region.rect]) {
    const rect = structuredClone(localRect), pdf = page.image_to_pdf;
    let pdfRect;
    if (pdf) {
      if (![pdf.x, pdf.y, pdf.width, pdf.height].every(Number.isFinite) || pdf.x < 0 || pdf.y < 0
        || pdf.width <= 0 || pdf.height <= 0 || pdf.x + pdf.width > 1.000001 || pdf.y + pdf.height > 1.000001) {
        errors.push('invalid_pdf_transform'); continue;
      }
      pdfRect = { x: pdf.x + rect.x * pdf.width, y: pdf.y + rect.y * pdf.height,
        width: rect.width * pdf.width, height: rect.height * pdf.height };
    }
    regions.push({ page: page.page, pageHash: page.sha256, rect, frameId, imageHash: receipt.image_hash,
      representation: 'source_regions', precision: 'ocr-regions', regionId: reference,
      regionManifestHash: frame.regionManifestHash, raw: reference,
      ...(pdfRect ? { pdfRect, pdfPage: page.source_page ?? page.page } : {}) });
    }
  }
  return { ...empty(errors.length ? regions.length ? 'partial' : 'invalid' : 'located'), regions,
    ...(errors.length ? { issues: errors } : {}) };
}

export function attachInlineAnnotations(grade, annotations, student, frames, receipts) {
  for (const item of grade.items) for (const point of item.point_decisions) {
    const aligned=alignOCRReferences(annotations.get(JSON.stringify([item.item_id, point.point_id])),point,frames);
    point.annotation = decodeAnnotationRegions(aligned.references, point, student, frames, receipts);
    if(aligned.resolution)point.annotation.selection_resolution=aligned.resolution;
  }
  return grade;
}

export function withoutAnnotationGeometry(value) {
  return JSON.parse(JSON.stringify(value, (key, field) => key === 'annotation' ? undefined : field));
}
