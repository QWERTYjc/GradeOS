// Use the batch snapshot: current upload groups may have been renamed or repartitioned.
export function outputScope(task, artifact, kind = 'document') {
  const group = task?.groups?.find(row => row.id === artifact?.groupId);
  const category = group ? '个人报告' : kind === 'marking_guide' ? '评分说明'
    : artifact?.id === task?.id + '-report' ? '汇总报告' : artifact ? '任务产出' : '文档';
  return { category, taskId: task?.id ?? null, taskTitle: task?.title ?? null,
    groupId: group?.id ?? null, groupLabel: group?.label ?? null };
}

export function librarySections(state) {
  const sections = new Map();
  const tasks = new Map(state.tasks.map(task => [task.id, task]));
  const materialized = new Map();
  function add(task, row) {
    const key = task ? 'batch:' + task.id : 'folder:' + (row.folder || '');
    if (!sections.has(key)) sections.set(key, { title: task?.title || row.folder || '未关联批次', rows: [] });
    sections.get(key).rows.push(row);
  }
  for (const doc of state.documents || []) {
    const task = tasks.get(doc.taskId);
    const artifact = task?.artifacts?.find(row => row.id === doc.artifactId);
    if (artifact) {
      if (!materialized.has(task.id)) materialized.set(task.id, new Set());
      materialized.get(task.id).add(artifact.id);
    }
    add(task, { ...outputScope(task, artifact, doc.kind), action: 'open-document', id: doc.id,
      title: doc.title, folder: doc.folder, version: doc.revision, time: doc.updatedAt });
  }
  for (const task of state.tasks) {
    for (const artifact of task.artifacts || []) {
      if (materialized.get(task.id)?.has(artifact.id)) continue;
      add(task, { ...outputScope(task, artifact), action: 'artifact', id: artifact.id,
        title: artifact.title || '批改产出', time: task.completedAt || task.createdAt });
    }
    for (const group of task.groups || []) {
      if (!task.records?.some(record => record.groupId === group.id)) continue;
      add(task, { ...outputScope(task, { groupId: group.id }), category: '评分明细',
        action: 'group-result', id: group.id, title: group.label, time: task.completedAt || task.createdAt });
    }
  }
  for (const section of sections.values()) section.rows.sort((a,b) => (b.time || '').localeCompare(a.time || ''));
  return [...sections.values()].sort((a,b) => (b.rows[0].time || '').localeCompare(a.rows[0].time || ''));
}
