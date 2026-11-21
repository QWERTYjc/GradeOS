import { escape as e, markdown } from './ui.mjs';

export function batchReport(task) {
  return task.artifacts?.find(artifact => artifact.id === task.id + '-report' && artifact.groupId == null && typeof artifact.body === 'string');
}

// Native reports have a quoted executive summary. Older, editable reports may use
// a named section or introductory paragraphs before the detailed scoring tables.
export function reportSummaryMarkdown(body) {
  const text = String(body ?? '').replace(/\r\n?/g, '\n').trim();
  const intro = text.replace(/^# [^\n]*(?:\n+|$)/, '').replace(/^\*[^*\n]+\*\s*\n/, '').trim();
  const quoted = /^>\s*\*\*摘要\*\*[^\S\n]*\n((?:>[^\n]*(?:\n|$))+)/.exec(intro);
  if (quoted) return quoted[1].replace(/^> ?/gm, '').trim();
  const section = /^#{2,3} +(批改总结|班级总结|总结|总评|摘要|Executive summary|Summary)[ \t]*$/im.exec(intro);
  const opening = (section ? intro.slice(section.index + section[0].length).trimStart() : intro).split(/^#{1,6} /m)[0];
  return opening.split(/\n\s*\n/).filter(paragraph => paragraph.trim() && !/^(?:---+$|\[.+\]\(#|(?:作者|日期|署名|来源|版本|费用)[：:])/.test(paragraph.trim())).join('\n\n').trim();
}

// Personal reports carry the student's own narrative, usually before the strengths section.
// A legacy report may have only a title and introduction. Stop before item data or source notes.
export function studentSummaryMarkdown(body) {
  if (typeof body !== 'string') return '';
  const section = /^#{2,3}[ \t]+(?:学习总结|个人总评|学习总评|总体反馈|Learning summary)[ \t]*\r?$/im.exec(body);
  const start = section ? section.index + section[0].length : body.match(/^\s*#[ \t][^\n]*(?:\n|$)/)?.[0].length || 0;
  const lines = [];
  for (const match of body.slice(start).matchAll(/[^\n]*\n|[^\n]+$/g)) {
    const line = match[0].trim().replace(/^>\s?/, '');
    if (!line) { if (lines.length) lines.push(''); continue; }
    if (/^(?:#{1,6}\s|\||```|~~~|<\/?(?:details|summary)|---+$|\[.+\]\(#)/i.test(line)) break;
    if (/^(?:评分依据|本次评分|整卷总分|题目覆盖|本次得分|分数|状态|答卷依据|评分条件|来源|作者|日期|版本)[：:]|^(?:用户提供的 MS|根据题目推导|依据本份答卷内容) ·/.test(line)) break;
    if (!section && !lines.length && /^\*[^*]+\*$/.test(line)) continue;
    lines.push(line);
  }
  return lines.join('\n').trim();
}

// Use the batch snapshot: current upload groups may have been renamed or repartitioned.
export function outputScope(task, artifact, kind = 'document') {
  const group = task?.groups?.find(row => row.id === artifact?.groupId);
  const category = group ? '个人报告' : kind === 'marking_guide' ? '评分说明'
    : artifact?.id === task?.id + '-report' ? '汇总报告' : artifact ? '任务产出' : '文档';
  const owner = group ? 'student' : artifact?.groupId ? 'unassigned' : kind === 'marking_guide' ? 'scheme' : 'class';
  return { category, owner, taskId: task?.id ?? null, taskTitle: task?.title ?? null,
    groupId: group?.id ?? null, groupLabel: group?.label ?? null };
}

// Read the batch's original page membership, including its subset of a merged scan.
// Missing or changed pages stay unavailable instead of pointing to a newer submission.
export function batchInputs(state) {
  const current = new Map((state.pages || []).map(page => [page.id, page]));
  const inputs = [];
  for (const task of state.tasks) {
    if (task.kind !== 'grade') continue;
    const frozen = new Map((task.pages || []).map(page => [page.id, page]));
    function collect(selection, role, owner) {
      const sources = new Map();
      for (const id of selection?.pageIds || []) {
        const page = frozen.get(id) || current.get(id);
        if (!page || (page.role && page.role !== role)) continue;
        const sourceId = page.sourceId || page.id;
        let source = sources.get(sourceId);
        if (!source) {
          const groupId = owner === 'student' ? selection.id : null;
          source = { id: JSON.stringify([task.id, role, groupId, sourceId]), title: page.fileName || selection.label || '未命名原件',
            origin:'grading', input:true, owner, taskId:task.id, taskTitle:task.title,
            groupId, groupLabel:groupId ? selection.label : null,
            category:{ scheme:'评分标准原件', question:'题目原件', student:'学生原卷' }[role],
            updatedAt:task.createdAt, pages:[] };
          sources.set(sourceId, source);
          inputs.push(source);
        }
        const hash = frozen.get(id)?.sha256 || task.pageHashes?.[id] || (task.status === 'draft' ? page.sha256 : null);
        const live = current.get(id);
        const available = Boolean(hash && live?.sha256 === hash && (!live.role || live.role === role));
        source.pages.push({ id, hash, number:page.sourcePage, available });
      }
    }
    const guide = task.guideDraft || task.guideReference;
    if (guide?.documentId && guide.hash && Number.isInteger(guide.revision)) {
      const document = state.documents?.find(doc => doc.id === guide.documentId);
      inputs.push({ id:JSON.stringify([task.id,'guide',guide.documentId]), input:true, owner:'scheme', origin:'grading',
        taskId:task.id, taskTitle:task.title, title:guide.title || '评分说明', category:'批次引用的评分说明',
        documentId:guide.documentId, revision:guide.revision, hash:guide.hash,
        sourceDocumentExists:Boolean(document), sourceTaskId:document?.taskId || null,
        referenceable:Boolean(document?.history?.some(version => version.revision === guide.revision && version.hash === guide.hash)),
        updatedAt:task.startedAt || task.createdAt });
    }
    collect(task.scheme, 'scheme', 'scheme');
    collect(task.question, 'question', 'class');
    for (const group of task.groups || []) collect(group, 'student', 'student');
  }
  const archived = new Set(inputs.flatMap(file => (file.pages || []).filter(page => page.available).map(page => page.id)));
  const loose = new Map(), groupsByPage = new Map();
  for (const group of state.groups || []) for (const id of group.pageIds) groupsByPage.set(id, group);
  const names = {scheme:'评分标准原件', question:'题目原件', student:'学生原卷'};
  for (const page of current.values()) {
    if (page.active === false || archived.has(page.id)) continue;
    const group = page.role === 'student' && groupsByPage.get(page.id);
    const key = JSON.stringify([null, page.role, group?.id || null, page.sourceId || page.id]);
    if (!loose.has(key)) loose.set(key, {id:key, input:true, origin:'grading', taskId:null, folder:'待归档材料',
      owner:page.role === 'student' ? group ? 'student' : 'unassigned' : page.role === 'scheme' ? 'scheme' : 'class',
      groupId:group?.id || null, groupLabel:group?.label || null, title:page.fileName || '未命名原件', category:names[page.role] || '材料', pages:[]});
    loose.get(key).pages.push({id:page.id, number:page.sourcePage, hash:page.sha256, available:Boolean(page.sha256)});
  }
  inputs.push(...loose.values());
  return inputs;
}

export const archiveLabels = {reports:'批改总结', questions:'试题原件', scheme:'评分标准（MS）', students:'学生答卷', shared:'其他批次文件', unassigned:'归属待核对'};

export function archiveOwners(files) {
  const reports = [], questions = [], scheme = [], shared = [], unassigned = [], students = new Map();
  for (const file of files) {
    if (file.groupId) {
      if (!students.has(file.groupId)) students.set(file.groupId, { id:file.groupId, label:file.groupLabel || '未命名答卷', rows:[] });
      students.get(file.groupId).rows.push(file);
    } else if (file.owner === 'scheme' || file.category === '评分说明') scheme.push(file);
    else if (file.owner === 'unassigned') unassigned.push(file);
    else if (file.category === '汇总报告') reports.push(file);
    else if (file.category === '题目原件') questions.push(file);
    else shared.push(file);
  }
  const byLabel = new Map();
  for (const group of students.values()) {
    if (!byLabel.has(group.label)) byLabel.set(group.label, []);
    byLabel.get(group.label).push(group);
  }
  for (const peers of byLabel.values()) {
    if (peers.length < 2) continue;
    for (const group of peers) {
      let length = 8;
      while (length < group.id.length && peers.some(other => other !== group && other.id.startsWith(group.id.slice(0, length)))) length++;
      group.disambiguator = group.id.slice(0, length);
    }
  }
  return {reports, questions, scheme, shared, unassigned, students:[...students.values()]};
}

// An unassigned guide is already filed when a batch exposes that exact live version.
export function omitFiledGuides(files, inputs, documentId = file => file.id) {
  const versions = new Set(inputs.filter(file => file.documentId).map(file => JSON.stringify([file.documentId, file.revision, file.hash])));
  return files.filter(file => file.taskId || !versions.has(JSON.stringify([documentId(file), file.revision, file.hash])));
}

export function librarySections(state, includeInputs = false) {
  const sections = new Map();
  const tasks = new Map(state.tasks.map(task => [task.id, task]));
  const materialized = new Map();
  function add(task, row) {
    const key = task ? 'batch:' + task.id : 'folder:' + (row.folder || '');
    if (!sections.has(key)) sections.set(key, { taskId: task?.id || null, title: task?.title || row.folder || '未关联批次', rows: [] });
    sections.get(key).rows.push(row);
  }
  const inputs = includeInputs ? batchInputs(state) : [];
  for (const doc of omitFiledGuides(state.documents || [], inputs)) {
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
  for (const input of inputs) {
    add(tasks.get(input.taskId), { ...input, action:'history-source', version:input.revision, time:input.updatedAt });
  }
  for (const section of sections.values()) section.rows.sort((a,b) => (b.time || '').localeCompare(a.time || ''));
  return [...sections.values()].sort((a,b) => (b.rows[0].time || '').localeCompare(a.rows[0].time || ''));
}

// Both archives open the same batch-owned pages or the exact guide captured at dispatch.
export async function archiveSourceBody(file) {
  if (file.documentId) {
    const query = new URLSearchParams({ revision:file.revision, hash:file.hash });
    const url = '/api/tasks/' + encodeURIComponent(file.taskId) + '/guide-draft?' + query;
    const response = await fetch(url);
    const guide = await response.json();
    if (!response.ok) throw Error(guide.error || '无法读取这份评分说明。');
    const edit = file.sourceDocumentExists ? `<button type="button" data-action="archive-guide-document" data-id="${e(file.documentId)}" data-task="${e(file.sourceTaskId || '')}">编辑当前文档</button>` : '';
    return `<div class="archive-guide-meta"><span>${e(file.category)} · v${e(file.revision)}</span><div>${edit}<a href="${e(url)}&amp;download=1">导出</a></div></div><article class="prose">${markdown(guide.body)}</article>`;
  }
  return '<div class="archive-source-pages">' + file.pages.map((page, index) => {
    const label = '原件第 ' + (page.number || index + 1) + ' 页';
    if (!page.available) return `<p>${e(label)} · 原页暂不可用</p>`;
    const url = '/api/pages/' + encodeURIComponent(page.id) + '?hash=' + encodeURIComponent(page.hash);
    return `<figure><figcaption><span>${e(label)}</span><a href="${url}" target="_blank" rel="noopener">查看原图 ↗</a></figcaption><img loading="lazy" src="${url}" alt="${e(file.title + '，' + label)}"></figure>`;
  }).join('') + '</div>';
}
