import { modelConfigError } from '../../web/grading-models.mjs';
import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { digest } from '../core.mjs';
import { annotationEvidenceHash } from '../inline-annotations.mjs';
import { validateSelections } from './canvas-context.mjs';
import { resolveReferences } from './editable-documents.mjs';

export class WorkspaceError extends Error {
  constructor(message, status = 422) { super(message); this.status = status; }
}
export const fail = (condition, message, status) => {
  if (!condition) throw new WorkspaceError(message, status);
};
export const id = () => randomUUID();
export const now = () => new Date().toISOString();
export function executionMode(value = 'review') {
  fail(['review', 'auto'].includes(value), '请选择有效的批改授权方式。');
  return value;
}
export const activePages = state => state.pages.filter(page => page.active !== false);
export const answerPages = state => activePages(state).filter(page => page.role === 'student');
export const emptyState = () => ({
  version: 1, revision: 0, materialRevision: 0, title: '新的作业',
  pages: [], groups: [], schemes: [], questions: [], tasks: [], reviews: [], conversation: [], documents: [], annotations: [], executionMode: 'review',
});

export class WorkspaceStore {
  constructor(directory) { this.directory = directory; this.queue = Promise.resolve(); }
  async init() {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    try { this.state = JSON.parse(await readFile(join(this.directory, 'workspace.json'), 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; this.state = emptyState(); }
    fail(this.state.version === 1, '工作区版本不兼容。');
    this.state.documents ||= []; this.state.annotations ||= []; this.state.questions ||= [];
    this.state.executionMode = executionMode(this.state.executionMode);
    return this;
  }
  snapshot() { return structuredClone(this.state); }
  mutate(revision, update) {
    const pending = this.queue.then(async () => {
      fail(revision === null || revision === this.state.revision,
        '工作区已有更新，请刷新后再操作。', 409);
      const next = this.snapshot();
      const value = await update(next);
      next.revision++;
      const temporary = join(this.directory, `workspace-${id()}.pending`);
      await writeFile(temporary, JSON.stringify(next, null, 2), { mode: 0o600 });
      await rename(temporary, join(this.directory, 'workspace.json'));
      this.state = next;
      return value;
    });
    this.queue = pending.catch(() => {});
    return pending;
  }
}

export function replacePartition(state, groups, unassignedPageIds = []) {
  fail(Array.isArray(groups) && Array.isArray(unassignedPageIds) && (groups.length || unassignedPageIds.length), '请保留至少一份答卷。');
  const available = new Set(answerPages(state).map(page => page.id));
  fail(unassignedPageIds.every(id => available.has(id)) && new Set(unassignedPageIds).size === unassignedPageIds.length, '待分组页面无效。');
  const seen = new Set(unassignedPageIds), groupIds = new Set();
  const previous = new Map(state.groups.map(group => [group.id, group]));
  const next = groups.map((group, index) => {
    fail(typeof group.id === 'string' && /^[\w-]{1,64}$/.test(group.id) && !groupIds.has(group.id), '答卷标识重复或无效。');
    groupIds.add(group.id);
    fail(Array.isArray(group.pageIds) && group.pageIds.length > 0, '每份答卷至少需要一页。');
    for (const page of group.pageIds) {
      fail(available.has(page) && !seen.has(page), '页面归属重复，或包含不属于当前材料的页面。');
      seen.add(page);
    }
    const label = typeof group.label === 'string' ? group.label.trim().slice(0, 80) : '';
    return { id: group.id, label: label || previous.get(group.id)?.label || `答卷 ${String(index + 1).padStart(2, '0')}`, pageIds: [...group.pageIds] };
  });
  fail(seen.size === available.size, '划分必须包含全部答卷页面，不能遗漏。');
  state.groups = next;
  state.materialRevision++;
}

export function taskDraft(state, input) {
  const kind = input.kind ?? 'grade';
  let modelConfig;
  if (input.modelConfig !== undefined) {
    const error = modelConfigError(input.modelConfig);
    fail(kind === 'grade' && !error, error || '仅批改任务支持模型搭配。');
    const { mainModel, mainEffort, workerModel, workerEffort } = input.modelConfig;
    modelConfig = { mainModel, mainEffort, workerModel, workerEffort };
  }
  fail(['grade', 'assist'].includes(kind), '任务类型无效。');
  fail(input.goal == null || (typeof input.goal === 'string' && input.goal.length <= 8000), '任务要求最多 8000 字。');
  const legacyGoal = input.goal?.trim() || '';
  fail(kind !== 'assist' || legacyGoal.length > 0, '请填写任务要求（最多 8000 字）。');
  const supplementalInstructions = input.supplementalInstructions ?? (kind === 'grade' && legacyGoal !== '批改所选答卷' ? legacyGoal : '');
  fail(typeof supplementalInstructions === 'string' && supplementalInstructions.length <= 8000, '补充批改要求最多 8000 字。');
  const goal = kind === 'grade' ? '批改所选答卷' : legacyGoal;
  fail(Array.isArray(input.groupIds) && input.groupIds.length > 0 && input.groupIds.length <= 300 && new Set(input.groupIds).size === input.groupIds.length, '请选择有效的答卷范围。');
  const groups = input.groupIds.map(groupId => state.groups.find(group => group.id === groupId));
  fail(groups.every(Boolean), '所选答卷已改变，请重新选择。');
  const scheme = input.schemeId ? state.schemes.find(item => item.id === input.schemeId) : null;
  fail(!input.schemeId || scheme, '评分标准不存在。');
  const question = input.questionId ? (state.questions || []).find(item => item.id === input.questionId) : null;
  fail(!input.questionId || question, '题目不存在。');
  fail(input.gradingContext == null || (typeof input.gradingContext === 'string' && input.gradingContext.length <= 4000), '学科和考试要求最多 4000 字。');
  fail(input.allowWebSearch == null || typeof input.allowWebSearch === 'boolean', '联网设置无效。');
  fail(['review', 'stop'].includes(input.after), '完成条件无效。');
  return {
    id: id(), title: (typeof input.title === 'string' && input.title.trim() ? input.title : kind === 'grade' ? `批改 ${groups.length} 份答卷` : goal).trim().slice(0, 120), goal,
    supplementalInstructions: supplementalInstructions.trim(),
    ...(modelConfig ? { modelConfig } : {}), kind, groupIds: [...input.groupIds], schemeId: scheme?.id ?? null, after: input.after,
    questionId: question?.id ?? null, question: structuredClone(question),
    gradingContext: input.gradingContext?.trim() || '', allowWebSearch: input.allowWebSearch === true,
    executionMode: executionMode(input.executionMode ?? state.executionMode),
    status: 'draft', createdAt: now(), materialRevision: state.materialRevision,
    groups: structuredClone(groups), scheme: structuredClone(scheme), records: [], artifacts: [],
    selections: validateSelections(state, input.selections || [], input.groupIds),
    references: resolveReferences(state, input.references || [], input.groupIds),
  };
}

export function startTask(state, taskId) {
  const task = state.tasks.find(item => item.id === taskId);
  fail(task && task.status === 'draft', '此任务已开始，不能重复执行。', 409);
  fail(task.materialRevision === state.materialRevision, '材料或答卷划分已改变，请更新任务范围后再开始。', 409);
  if (task.kind === 'grade') {
    fail(!state.tasks.some(other => other.status === 'running' && other.kind === 'grade' && other.groupIds.some(group => task.groupIds.includes(group))),
      '这些答卷已有批改任务在执行，请等待完成。', 409);
  }
  task.pages = structuredClone(state.pages.filter(page => task.groups.some(group => group.pageIds.includes(page.id)) || task.scheme?.pageIds.includes(page.id) || task.question?.pageIds.includes(page.id)));
  const guide = task.scheme && !task.question ? state.documents?.findLast(document => document.kind === 'marking_guide' && document.schemeId === task.schemeId) : null;
  task.executionMode = executionMode(task.executionMode);
  if (guide) task.guideDraft = { documentId: guide.id, revision: guide.revision, hash: guide.hash, body: guide.body, title: guide.title };
  task.status = 'running'; task.startedAt = now(); task.progress = { completed: 0, total: task.groups.length, phase: task.kind === 'grade' ? '整理评分要求' : '准备材料' };
  return structuredClone(task);
}

export function saveReview(state, input) {
  const task = state.tasks.find(item => item.id === input.taskId);
  const record = task?.records.find(item => item.id === input.recordId);
  fail(record, '找不到这条评分记录。', 404);
  fail(input.originalHash === record.originalHash, '原始记录已改变，请重新打开审阅。', 409);
  fail(input.score === null || (typeof input.score === 'number' && Number.isFinite(input.score) && record.allowedAwards?.includes(input.score)), '请使用评分条文允许的分值；未知分值请保留待定。');
  fail(typeof input.reason === 'string' && input.reason.trim().length > 0 && input.reason.length <= 4000, '请填写复核理由。');
  const revision = {
    id: id(), taskId: task.id, recordId: record.id, originalHash: record.originalHash,
    originalScore: record.score, score: input.score, reason: input.reason.trim(), createdAt: now(),
  };
  state.reviews.push(revision);
  return revision;
}

export function publicState(state, configured, runtime = {}) {
  const copy = structuredClone(state);
  copy.documents = (copy.documents || []).map(({ body, history, ...document }) => ({ ...document, versionCount: history.length }));
  copy.pages = copy.pages.map(({ path, ...page }) => ({ ...page, url: `/api/pages/${page.id}` }));
  copy.tasks = copy.tasks.map(task => {
    const { pages, guideDraft, ...visible } = task;
    return { ...visible, pageHashes: Object.fromEntries((pages || []).map(page => [page.id, page.sha256])),
      pageCount: task.groups.reduce((sum, group) => sum + group.pageIds.length, 0) };
  });
  return { ...copy, agentReady: configured, ...runtime };
}

export function makeRecord(task, group, item, point, rule, gradeHash, rubricHash) {
  const selected = point ?? item;
  const annotation=selected.annotation, annotationCurrent=annotation?.evidence_hash===annotationEvidenceHash(selected);
  const annotationRegions=annotationCurrent?(annotation.regions||[]).flatMap(region=>{
    const pageId=group.pageIds[region.page-1],page=task.pages?.find(page=>page.id===pageId);
    return page&&page.sha256===region.pageHash&&selected.student_pages.includes(region.page)?[{pageId,pageHash:page.sha256,rect:region.rect,frameId:region.frameId,
      ...(region.precision==='ocr-regions'?{precision:region.precision,regionId:region.regionId,regionManifestHash:region.regionManifestHash}: {}),
      ...(region.precision==='grid-cells'?{precision:region.precision,contextRect:region.contextRect,contextPaddingCells:region.contextPaddingCells}: {})}]:[];
  }):[];
  const source = { task: task.id, group: group.id, item: item.item_id, point: point?.point_id ?? null, gradeHash, rubricHash };
  const maximum = rule?.max_score ?? null;
  return {
    id: digest(source).slice(0, 24), groupId: group.id, student: group.label,
    itemId: item.item_id, pointId: point?.point_id ?? null,
    score: selected.score ?? null, maximum,
    allowedAwards: Array.isArray(rule?.allowed_awards) ? rule.allowed_awards : [],
    reason: selected.reason || item.reason || '', evidence: selected.evidence || '',
    sourceText: rule?.source_text || rule?.criteria || '',
    studentPageIds: (selected.student_pages || item.student_pages || []).map(number => group.pageIds[number - 1]).filter(Boolean),
    schemePageIds: (rule?.source_pages || item.scheme_pages || []).map(number => task.scheme?.pageIds[number - 1]).filter(Boolean),
    reviewRequired: Boolean(item.review_required || selected.score == null),
    ...(annotation?{annotationStatus:annotationCurrent?annotation.status:'stale',annotationOrigin:annotation.origin,annotationIssues:annotation.issues||[],annotationRegions}:{}),
    originalHash: digest({ ...source, selected, rule }),
  };
}
