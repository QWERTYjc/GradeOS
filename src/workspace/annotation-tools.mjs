import { gradingAnnotations } from '../../web/grading-annotations.mjs';
import { fail } from './store.mjs';

export function annotationTools({ state, selectedIds }) {
  return [{ name: 'read_annotation_points', label: '查看本页批注依据',
    description: 'Read saved scoring evidence and its source-bound local OCR region IDs on one answer page.',
    parameters: {type:'object', properties:{taskId:{type:'string'}, pageId:{type:'string'}},
      required:['taskId','pageId'], additionalProperties:false},
    execute: async (_call, {taskId, pageId}) => {
      const group = state.tasks.find(task => task.id === taskId)?.groups.find(group => group.pageIds.includes(pageId));
      fail(group && selectedIds.includes(group.id), '批注超出老师选定的答卷范围。');
      const notes = gradingAnnotations(state, taskId, group.id, pageId);
      fail(notes.length, '这一页没有已有评分点。');
      const rows = notes.map(note => ({ n: note.index, point: note.label, evidence: note.evidence,
        regionIds: [...new Set(note.regions.map(region => region.regionId).filter(Boolean))] }));
      return {content:[{type:'text', text:JSON.stringify(rows)}], details:{}};
    },
  }];
}
