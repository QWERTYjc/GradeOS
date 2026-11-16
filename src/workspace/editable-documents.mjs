import { digest } from '../core.mjs';
import { fail, id, now } from './store.mjs';
import { validateSelections } from './canvas-context.mjs';
import { findGradingAnnotation } from '../../web/grading-annotations.mjs';

const bodyText = body => { fail(typeof body === 'string' && body.length <= 120000, '文档最多支持 120,000 字。'); return body.replace(/\r\n/g, '\n'); };
export function addDocument(state, input, actor = 'teacher') {
  state.documents ||= [];
  fail(state.documents.length < 100, '此工作区最多保存 100 份可编辑文档。');
  const body = bodyText(input.body ?? '');
  const document = { id: input.id || id(), title: String(input.title || '未命名.md').slice(0, 100), kind: input.kind || 'document',
    schemeId: input.schemeId || null, taskId: input.taskId || null, proposalId: input.proposalId || null,
    sourcePageIds: input.sourcePageIds || [], rubricHash: input.rubricHash || null, sourceHash: input.sourceHash || null,
    revision: 1, hash: digest(body), body, createdAt: now(), updatedAt: now(), actor, approvals: [],
    history: [{ revision: 1, hash: digest(body), body, actor, at: now() }] };
  fail(!state.documents.some(row => row.id === document.id), '文档已经存在。', 409);
  state.documents.push(document); return structuredClone(document);
}
export function readDocument(state, documentId, revision = null) {
  const document = state.documents?.find(row => row.id === documentId);
  fail(document, '文档不存在。', 404);
  const version = revision == null ? document : document.history.find(row => row.revision === revision);
  fail(version, '文档版本不存在。', 404);
  const { history, ...publicDocument } = document;
  return { ...publicDocument, body: version.body, revision: version.revision, hash: version.hash, actor: version.actor,
    versions: document.history.map(({ body, ...row }) => row) };
}
export function saveDocument(state, documentId, input, actor = 'teacher') {
  const document = state.documents?.find(row => row.id === documentId);
  fail(document, '文档不存在。', 404);
  fail(input.revision === document.revision, '文档已有新版本。你的编辑仍保留，请先对照新版本。', 409);
  const body = bodyText(input.body), title = typeof input.title === 'string' && input.title.trim() ? input.title.trim().slice(0, 100) : document.title;
  if (body === document.body && title === document.title) return readDocument(state, documentId);
  document.body = body; document.title = title; document.hash = digest(body); document.revision++; document.updatedAt = now(); document.actor = actor;
  document.history.push({ revision: document.revision, hash: document.hash, body, actor, at: document.updatedAt });
  return readDocument(state, documentId);
}
export function textTarget(state, target) {
  const document = readDocument(state, target.documentId, target.revision);
  fail(document.hash === target.documentHash, '文档引用已改变，请重新选择。', 409);
  const { start, end } = target;
  fail(Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end <= document.body.length && end - start <= 12000, '请选择有效的文字范围（最多 12,000 字）。');
  fail(document.body.slice(start, end) === target.quote, '所选文字与文档版本不一致。', 409);
  const schemePages = new Set(state.schemes.flatMap(scheme => scheme.pageIds));
  return { kind: 'text', documentId: document.id, title: document.title, revision: document.revision, documentHash: document.hash,
    sourcePageIds: document.sourcePageIds, role: document.sourcePageIds.length && document.sourcePageIds.every(id => schemePages.has(id)) ? 'scheme' : 'document', start, end, quote: target.quote };
}
export function addAnnotation(state, input) {
  state.annotations ||= [];
  fail(state.annotations.filter(row => !row.archivedAt).length < 1000, '此工作区的注释已达上限。');
  fail(typeof input.text === 'string' && input.text.trim() && input.text.length <= 8000, '请填写注释（最多 8,000 字）。');
  const target = input.target?.kind === 'text' ? textTarget(state, input.target) : { kind: 'page', ...validateSelections(state, [input.target])[0] };
  const annotation = { id: id(), target, text: input.text.trim(), createdAt: now(), updatedAt: now() };
  state.annotations.push(annotation); return annotation;
}
export function updateAnnotation(state, annotationId, input) {
  const annotation = state.annotations?.find(row => row.id === annotationId && !row.archivedAt);
  fail(annotation, '注释不存在。', 404);
  if (input.archive) annotation.archivedAt = now();
  else { fail(typeof input.text === 'string' && input.text.trim() && input.text.length <= 8000, '请填写注释（最多 8,000 字）。'); annotation.text = input.text.trim(); annotation.updatedAt = now(); }
  return annotation;
}
export function documentAllowed(state, document, selectedIds) {
  const allowed = new Set([...state.groups.filter(row => selectedIds.includes(row.id)).flatMap(row => row.pageIds), ...[...state.schemes, ...(state.questions || [])].flatMap(row => row.pageIds)]);
  return document.sourcePageIds.every(page => allowed.has(page));
}
export function resolveReferences(state, input = [], selectedIds = []) {
  fail(Array.isArray(input) && input.length <= 16, '一次最多引用 16 处内容。');
  return input.map(reference => {
    const annotation = reference.annotationId ? state.annotations?.find(row => row.id === reference.annotationId && !row.archivedAt)
      || findGradingAnnotation(state, reference.annotationId, reference.target?.pageId) : null;
    fail(!reference.annotationId || annotation, '引用的注释已移除。', 409);
    const target = annotation?.target || reference.target;
    fail(target, '引用内容不存在。');
    if (target.kind === 'text') {
      const validated = textTarget(state, target), document = state.documents.find(row => row.id === target.documentId);
      fail(documentAllowed(state, document, selectedIds), '文档引用超出所选答卷范围。');
      return { target: validated, comment: annotation?.text || '', annotationId: annotation?.id };
    }
    return { target: { kind: 'page', ...validateSelections(state, [target], selectedIds)[0] }, comment: annotation?.text || '', annotationId: annotation?.id,
      ...(annotation?.source === 'grading' ? { origin: 'saved_grading_result', recordId: annotation.recordId, originalHash: annotation.originalHash,
        guide: annotation.guide, reviewId: annotation.reviewId } : {}) };
  });
}
