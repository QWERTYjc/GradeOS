import { gradingAnnotations } from '../../web/grading-annotations.mjs';
import { validateSelections } from './canvas-context.mjs';
import { fail, now } from './store.mjs';

export function saveGradingAnchors(state, anchors) {
  fail(Array.isArray(anchors) && anchors.length > 0 && anchors.length <= 24, '一次最多定位 24 个评分点。');
  // Validate the whole operation before writing any anchor.
  const checked = anchors.map(anchor => {
    const note = gradingAnnotations(state, anchor.taskId, anchor.groupId, anchor.target?.pageId)
      .find(row => row.recordId === anchor.recordId && row.originalHash === anchor.originalHash);
    fail(note, '批改记录或材料已改变，请重新查看后定位。', 409);
    const target = validateSelections(state, [anchor.target], [anchor.groupId])[0];
    return { taskId: anchor.taskId, groupId: anchor.groupId, recordId: note.recordId,
      originalHash: note.originalHash, target: { kind: 'page', ...target }, actor: 'agent', updatedAt: now() };
  });
  state.gradingAnchors ||= [];
  for (const anchor of checked) {
    state.gradingAnchors = state.gradingAnchors.filter(row => !(row.taskId === anchor.taskId && row.recordId === anchor.recordId && row.target.pageId === anchor.target.pageId));
    state.gradingAnchors.push(anchor);
  }
  return checked.length;
}

export function annotationTools({ state, selectedIds, delivered, pendingDelivery, save }) {
  const object = properties => ({ type: 'object', properties, required: Object.keys(properties), additionalProperties: false });
  const source = { taskId: { type: 'string' }, pageId: { type: 'string' } };
  const notesFor = ({ taskId, pageId }) => {
    const group = state.tasks.find(task => task.id === taskId)?.groups.find(group => group.pageIds.includes(pageId));
    fail(group && selectedIds.includes(group.id), '批注超出老师选定的答卷范围。');
    const notes = gradingAnnotations(state, taskId, group.id, pageId);
    fail(notes.length, '这一页没有已有评分点。'); return notes;
  };
  return [{ name: 'read_annotation_points', label: '查看本页批注依据',
    description: 'Only for requested precise annotation placement. Read compact saved point numbers and evidence for one answer page. Comment text is rendered automatically; never regenerate it or regrade.',
    parameters: object(source), execute: async (_call, input) => {
      const notes = notesFor(input);
      for (const note of notes) pendingDelivery.add(`annotation-record:${note.recordId}`);
      return { content: [{ type: 'text', text: JSON.stringify(notes.map(note => ({ n: note.index, point: note.label, evidence: note.evidence }))) }], details: {} };
    },
  }, { name: 'place_grading_annotations', label: '定位答卷批注',
    description: 'After read_annotation_points AND read_pages deliver this full page, place existing comments using [pointNumber,x,y,width,height] tuples, normalized 0..1 from top-left. Match actual handwritten evidence, not printed question text. Omit uncertain or absent evidence; those comments stay in the margin. No text or score output.',
    parameters: object({ ...source, marks: { type: 'array', minItems: 1, maxItems: 24, items: { type: 'array', minItems: 5, maxItems: 5, items: { type: 'number' } } } }),
    execute: async (_call, input) => {
      const notes = notesFor(input);
      fail(delivered.has(`annotation-page:${input.pageId}`), '请先查看完整原页，不能凭文字猜测坐标。');
      fail(Array.isArray(input.marks) && input.marks.length > 0 && input.marks.length <= 24
        && new Set(input.marks.map(mark => mark[0])).size === input.marks.length, '批注定位条目无效。');
      const anchors = input.marks.map(mark => {
        fail(Array.isArray(mark) && mark.length === 5 && mark.every(Number.isFinite), '请提供评分点编号与四个归一化坐标。');
        const [n, x, y, width, height] = mark, note = notes.find(note => note.index === n);
        fail(note && delivered.has(`annotation-record:${note.recordId}`), '请先读取对应的评分依据。');
        return { taskId: note.taskId, groupId: note.groupId, recordId: note.recordId, originalHash: note.originalHash,
          target: { ...note.target, rect: { x, y, width, height }, shape: 'rectangle', points: [] } };
      });
      const count = await save(anchors);
      return { content: [{ type: 'text', text: JSON.stringify({ placed: count, scoresChanged: false }) }], details: {} };
    },
  }];
}
