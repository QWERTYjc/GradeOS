import { digest } from './core.mjs';

// Geometry is presentation metadata, never an input to the grading validators.
export function inlineAnnotationSchema(base) {
  const schema = structuredClone(base), row = schema.properties.items.items.properties.p.items;
  row.minItems = 6; row.maxItems = 7;
  row.description = 'Six unchanged grading cells, then optional annotation regions: [[frame_id,x,y,width,height],...]. Coordinates are integers on a 0..1000 grid. Empty regions means no reliable visible evidence.';
  // Pi validates the transport schema before our tool executes. Keep this
  // heterogeneous tuple permissive so malformed optional geometry reaches the
  // decoder instead of causing another model turn. The unchanged grading
  // validators still enforce every one of the first six cells after splitting.
  row.items = {};
  return schema;
}

export function inlineAnnotationPrompt(base) {
  return base.replace('exactly SIX cells:', 'SIX grading cells:').replace('Keep all six cells', 'Keep all six grading cells') + `
While inspecting the already attached answer pages, also locate the literal handwritten/typed evidence supporting EACH point. Append a SEVENTH cell to its p row: a list of at most 3 small regions [[frame_id,x,y,width,height],...]. No extra annotation tool or second reading pass is needed.
Use integers on a 0..1000 grid relative to the TOP-LEFT of the EXACT image named by frame_id. x/y locate its top-left; width/height are its size, NOT the bottom-right. Initial images are i1,i2,...; original untrimmed rereads are o1,o2,... . Never mix these coordinate frames. The host restores trimmed frames to the original page.
Enclose the ACTUAL evidence you quoted, including errors when present. Keep separate steps/columns in separate small boxes. Do not mark printed question text as student evidence, invent writing for a blank answer, enclose an entire page, or guess a location. Use [] when evidence is absent, ambiguous or cannot be located. A point can have zero marks and still have locatable incorrect work; full marks never justify a guessed box. Coordinates have no influence on the score, reason or review state. Keep the first six grading cells unchanged in meaning. Do not repeat the evidence or comment text in this cell.`;
}

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
  if (!['original', 'source_grid', 'exact_white_margin_trim'].includes(representation)) throw Error('Unsupported answer image representation');
  const cropped = representation !== 'original';
  if (cropped && (!geometry || geometry.original_sha256 !== page.sha256 || !geometry.pixel_identity_verified)) throw Error('Missing source-bound annotation frame geometry');
  if (representation === 'source_grid') {
    const [width, height] = geometry.original_size || [], [left, top, right, bottom] = geometry.source_rect_in_image || [];
    const [shownWidth, shownHeight] = geometry.size || [];
    if (geometry.grid?.version !== 'source-grid-v1' || geometry.grid.columns !== 10 || geometry.grid.rows !== 40
      || ![width, height, left, top, right, bottom, shownWidth, shownHeight].every(Number.isSafeInteger)
      || width <= 0 || height <= 0 || left < 0 || top < 0 || right - left !== width || bottom - top !== height
      || right > shownWidth || bottom > shownHeight) throw Error('Invalid source grid geometry');
    return { page: page.page, pageHash: page.sha256, representation, grid: geometry.grid,
      originalSize: geometry.original_size, imageSize: geometry.size, sourceRectInImage: geometry.source_rect_in_image };
  }
  return { page: page.page, pageHash: page.sha256, representation,
    ...(cropped ? { originalSize: geometry.original_size, imageSize: geometry.size, bbox: geometry.bbox } : {}) };
}

export function decodeAnnotationRegions(raw, point, student, frames, receipts) {
  const empty = status => ({ status, evidence_hash: annotationEvidenceHash(point), regions: [], origin: 'inline-grading' });
  if (raw === undefined) return empty('missing');
  if (raw === 'absent') return { ...empty('absent'), location_note: 'Model explicitly reports no visible answer evidence.' };
  if (typeof raw === 'string' && /^unlocated:\s*\S/i.test(raw)) return { ...empty('unlocated'), location_note: raw.slice(raw.indexOf(':') + 1).trim() };
  // A single grid reference is the same location as a one-element list. It
  // still passes every syntax, page binding and bounds check below.
  if (typeof raw === 'string') raw = [raw];
  if (Array.isArray(raw) && raw.length === 0) return empty('unlocated');
  if (!Array.isArray(raw) || raw.length > 12) return { ...empty('invalid'), issue: 'invalid_region_list' };
  const regions = [], errors = [];
  for (const reference of raw) {
    let box = reference, gridReference = null;
    if (typeof reference === 'string') {
      const match = /^(i[1-9]\d*)\.([A-J])([1-9]\d?):([A-J])([1-9]\d?)$/.exec(reference);
      if (!match) { errors.push('invalid_grid_reference'); continue; }
      const [, id, firstColumn, firstRow, lastColumn, lastRow] = match, grid = frames.get(id)?.grid;
      const x = firstColumn.charCodeAt(0) - 65, endX = lastColumn.charCodeAt(0) - 65;
      const y = Number(firstRow) - 1, endY = Number(lastRow) - 1;
      if (!grid || endX < x || endY < y || endX >= grid.columns || endY >= grid.rows) { errors.push('invalid_grid_bounds'); continue; }
      box = [id, x * 1000 / grid.columns, y * 1000 / grid.rows,
        (endX - x + 1) * 1000 / grid.columns, (endY - y + 1) * 1000 / grid.rows];
      gridReference = reference;
    }
    if (!Array.isArray(box) || box.length !== 5 || typeof box[0] !== 'string') { errors.push('invalid_region'); continue; }
    const [frameId, x, y, width, height] = box, frame = frames.get(frameId);
    const page = frame && student.pages.find(page => page.page === frame.page);
    const delivered = [...receipts.values()].filter(row => row.annotation_frame === frameId && row.role === 'student'
      && row.page === frame?.page && row.original_sha256 === page?.sha256 && row.representation === frame?.representation);
    const receipt=delivered[0];
    if (!page || !point.student_pages.includes(page.page) || frame.pageHash !== page.sha256 || !receipt) { errors.push('unbound_frame'); continue; }
    if (![x, y, width, height].every(Number.isInteger) || x < 0 || y < 0 || width < 2 || height < 2
      || x + width > 1000 || y + height > 1000 || width * height > 600000) { errors.push('invalid_bounds'); continue; }
    let rect = { x: x / 1000, y: y / 1000, width: width / 1000, height: height / 1000 };
    if (frame.representation === 'source_grid' && !gridReference) { errors.push('grid_reference_required'); continue; }
    if (!['original', 'source_grid'].includes(frame.representation)) {
      const [ow, oh] = frame.originalSize || [], [iw, ih] = frame.imageSize || [], [left, top, right, bottom] = frame.bbox || [];
      if (![ow, oh, iw, ih, left, top, right, bottom].every(Number.isFinite) || ow <= 0 || oh <= 0 || iw <= 0 || ih <= 0
        || right - left !== iw || bottom - top !== ih || left < 0 || top < 0 || right > ow || bottom > oh) { errors.push('invalid_transform'); continue; }
      rect = { x: (left + rect.x * iw) / ow, y: (top + rect.y * ih) / oh, width: rect.width * iw / ow, height: rect.height * ih / oh };
    }
    if (rect.width < .002 || rect.height < .002) { errors.push('region_too_small'); continue; }
    // A grid is quantized, not a glyph outline. Show one cell of context to
    // avoid cutting strokes on cell boundaries; retain the selected cells
    // unchanged for audit. This does not recover missing/disjoint evidence.
    let contextRect;
    if (gridReference) {
      const dx=1/frame.grid.columns,dy=1/frame.grid.rows;
      const left=Math.max(0,rect.x-dx),top=Math.max(0,rect.y-dy);
      contextRect={x:left,y:top,width:Math.min(1,rect.x+rect.width+dx)-left,height:Math.min(1,rect.y+rect.height+dy)-top};
    }
    const pdf = page.image_to_pdf;
    let pdfRect;
    if(pdf) {
      if(![pdf.x,pdf.y,pdf.width,pdf.height].every(Number.isFinite)||pdf.x<0||pdf.y<0||pdf.width<=0||pdf.height<=0
        ||pdf.x+pdf.width>1.000001||pdf.y+pdf.height>1.000001) {errors.push('invalid_pdf_transform');continue;}
      pdfRect={x:pdf.x+rect.x*pdf.width,y:pdf.y+rect.y*pdf.height,width:rect.width*pdf.width,height:rect.height*pdf.height};
    }
    regions.push({ page: page.page, pageHash: page.sha256, rect, frameId,
      imageHash: receipt.image_hash, representation: frame.representation, raw: gridReference || [...box],
      ...(pdfRect?{pdfRect,pdfPage:page.source_page??page.page}:{}),
      ...(gridReference ? { precision: 'grid-cells', grid: frame.grid, contextRect, contextPaddingCells: 1 } : {}) });
  }
  // Keep usable boxes; expose partial coverage rather than silently hiding rejects.
  return { ...empty(errors.length ? regions.length ? 'partial' : 'invalid' : 'located'), regions, ...(errors.length ? { issues: errors } : {}) };
}

export function attachInlineAnnotations(grade, annotations, student, frames, receipts) {
  for (const item of grade.items) for (const point of item.point_decisions) {
    point.annotation = decodeAnnotationRegions(annotations.get(JSON.stringify([item.item_id, point.point_id])), point, student, frames, receipts);
  }
  return grade;
}

export function withoutAnnotationGeometry(value) {
  return JSON.parse(JSON.stringify(value, (key, field) => key === 'annotation' ? undefined : field));
}
