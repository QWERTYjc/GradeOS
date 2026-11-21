import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import { basename, join } from 'node:path';
import { fail, id, now } from './store.mjs';
import { digest } from '../core.mjs';
import { readDocument } from './editable-documents.mjs';
import { batchInputs, outputScope } from '../../web/grading-library.mjs';
import { gradingResult, resultMarkdown } from '../../web/grading-result.mjs';

export const BUILTIN_SKILLS = [
  { id: 'teaching', name: '教辅资料', description: '依据引用材料编写讲义、练习和答案解析。', format: 'Markdown', instructions: 'Create clear teaching material with goals, worked examples and exercises. Preserve uncertainty and cite consulted sources. Save a Markdown document.' },
  { id: 'slides', name: '演示文稿', description: '生成可预览、下载的 HTML 演示文稿。', format: 'HTML', instructions: 'Create a polished self-contained HTML slide deck. Each slide must be a section element. Use inline CSS, no scripts, external assets, embeds or remote requests. Save as .html. Be explicit that this is HTML, not a .pptx file.' },
  { id: 'tables', name: '表格与数据', description: '整理 CSV 数据，输出可由 Excel 打开的表格。', format: 'CSV', instructions: 'Read supplied CSV data, explain transformations, preserve missing values, never fabricate rows or statistics. Save a valid UTF-8 CSV with header and proper quoting. Do not claim to read XLSX or execute calculations with unavailable tools.' },
  { id: 'code', name: '代码草稿', description: '编写和解释小型脚本，保存为本地代码文件。', format: '文本', instructions: 'Write or explain simple code and save source files. There is no shell or execution tool. Do not claim code has been run or tested. Do not modify any file outside this workspace.' },
];
const publicFile = ({ body, versions, ...file }) => ({ ...file, versionCount: versions?.length || 1 });
export const referenceKey = file => `${file.id}@${file.revision}:${file.hash}`;

function fileKind(title) {
  if (/\.html$/i.test(title)) return 'presentation';
  if (/\.csv$/i.test(title)) return 'table';
  return 'document';
}

// The display and download name can be longer than one filesystem component.
function diskName(title) {
  if (Buffer.byteLength(title.normalize('NFD')) > 255 || /[<>:"|?*]|\.$/.test(title) ||
      /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(title)) return 'content.txt';
  return title;
}

// A separate file and mutation queue keep general work independent of grading revisions.
export class SystemStore {
  constructor(directory, grading) { this.directory = directory; this.grading = grading; this.queue = Promise.resolve(); }
  async init() {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    try { this.state = JSON.parse(await readFile(join(this.directory, 'system.json'), 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; this.state = { version: 1, revision: 0, preferences: { displayName: '本地用户', workspaceName: '我的工作区', motion: 'system' }, threads: [], files: [], skills: BUILTIN_SKILLS.map(skill => ({ ...skill, enabled: true, builtin: true })) }; }
    fail(this.state.version === 1, '工作台数据版本不兼容。');
    this.state.sourceSnapshots ||= {};
    return this;
  }
  async recover() {
    if (this.state.threads.some(thread => thread.messages.some(message => message.status === 'running')))
      await this.mutate(state => {
        for (const thread of state.threads) for (const message of thread.messages) if (message.status === 'running') {
          message.status = 'interrupted';
          message.text ||= '服务已重启，这次任务未完成。';
          for (const file of state.files) if (message.fileIds?.includes(file.id)) file.status = 'partial';
        }
      });
  }
  mutate(update) {
    const pending = this.queue.then(async () => {
      const next = structuredClone(this.state), value = await update(next); next.revision++;
      const temporary = join(this.directory, `system-${id()}.pending`);
      await writeFile(temporary, JSON.stringify(next), { mode: 0o600 });
      await rename(temporary, join(this.directory, 'system.json')); this.state = next; return value;
    });
    this.queue = pending.catch(() => {}); return pending;
  }
  catalog() {
    const key = `${this.state.revision}:${this.grading.state.revision}`;
    if (this.catalogCache?.key === key) return structuredClone(this.catalogCache.files);
    const state = this.grading.snapshot();
    const files = this.state.files.map(publicFile);
    this.gradingBodies = new Map();
    for (const doc of state.documents || []) {
      const task = state.tasks.find(task => task.id === doc.taskId);
      const artifact = task?.artifacts?.find(artifact => artifact.id === doc.artifactId);
      files.push({ id: `document:${doc.id}`, title: doc.title, kind: 'document', origin: 'grading', revision: doc.revision, hash: doc.hash, updatedAt: doc.updatedAt, ...outputScope(task, artifact, doc.kind), folder: doc.folder || null, versionCount: doc.history.length, status: doc.approvals?.length ? 'confirmed' : 'draft' });
    }
    for (const task of state.tasks) {
      for (const artifact of task.artifacts || []) if (typeof artifact.body === 'string' && !state.documents.some(doc => doc.taskId === task.id && doc.artifactId === artifact.id)) {
        const fileId = `artifact:${task.id}:${artifact.id}`;
        files.push({ id: fileId, title: artifact.title || '批改报告', kind: 'document', origin: 'grading', ...outputScope(task, artifact), revision: 1, hash: digest(artifact.body), updatedAt: task.completedAt || task.createdAt, status: task.status });
        this.gradingBodies.set(fileId, artifact.body);
      }
      for (const group of task.groups || []) {
        const result = gradingResult(state, task.id, group.id);
        if (!result) continue;
        const body = resultMarkdown(result, state.pages);
        files.push({ id: `result:${task.id}:${group.id}`, title: `${group.label || '答卷'} · 评分结果.md`, kind: 'document', origin: 'grading', ...outputScope(task, { groupId: group.id }), category: '评分明细', revision: 1, hash: digest(body), updatedAt: task.completedAt || task.createdAt, status: task.status });
        this.gradingBodies.set(`result:${task.id}:${group.id}`, body);
      }
    }
    this.catalogCache = { key, files, inputs:batchInputs(state) }; return structuredClone(files);
  }
  readFile(fileId, revision = null, expectedHash = null) {
    const snapshots = this.state.sourceSnapshots;
    const pinned = expectedHash && (snapshots[referenceKey({ id: fileId, revision, hash: expectedHash })] ||
      snapshots[`${fileId}:${expectedHash}`]);
    if (pinned && (revision == null || revision === pinned.revision)) {
      return structuredClone(pinned);
    }
    let file;
    if (fileId.startsWith('document:')) {
      const doc = readDocument(this.grading.state, fileId.slice(9), revision);
      file = { ...this.catalog().find(row => row.id === fileId), body: doc.body, revision: doc.revision, hash: doc.hash };
    } else if (fileId.startsWith('artifact:') || fileId.startsWith('result:')) {
      const meta = this.catalog().find(row => row.id === fileId);
      if (meta) file = { ...meta, body:this.gradingBodies.get(fileId) };
      else if (fileId.startsWith('artifact:')) {
        // Opening a report for editing creates a document, but its original permalink stays readable.
        const doc = this.grading.state.documents.find(row => row.artifactId && fileId === `artifact:${row.taskId}:${row.artifactId}`);
        const first = doc?.history?.find(version => version.revision === 1);
        if (first) {
          const current = this.catalogCache.files.find(row => row.id === 'document:' + doc.id);
          file = {...current, id:fileId, body:first.body, hash:first.hash, revision:1, versionCount:1};
        }
      }
      fail(file, '文件不存在。', 404);
    } else {
      const current = this.state.files.find(row => row.id === fileId); fail(current, '文件不存在。', 404);
      const version = revision == null ? current : current.versions.find(row => row.revision === revision); fail(version, '文件版本不存在。', 404);
      // Old version records stored the exact name in their relative path.
      const title = version.title ?? basename(version.relativePath);
      file = { ...publicFile(current), ...structuredClone(version), title, kind: fileKind(title), versions: undefined };
    }
    fail(revision == null || revision === file.revision, '引用版本与文件快照不一致。', 409);
    fail(!expectedHash || file.hash === expectedHash, '来源已有更新，请重新选择版本。', 409);
    return structuredClone(file);
  }
  async pinFile(file) {
    const bodyKey = `${file.id}:${file.hash}`;
    const keyFor = snapshots => snapshots[bodyKey] && snapshots[bodyKey].revision !== file.revision ? referenceKey(file) : bodyKey;
    if (!this.state.sourceSnapshots[keyFor(this.state.sourceSnapshots)]) await this.mutate(state => {
      const snapshots = state.sourceSnapshots;
      snapshots[keyFor(snapshots)] ??= structuredClone(file);
    });
  }
  async saveFile(input, { threadId = null, sources = null, origin = 'workspace' } = {}) {
    fail(typeof input.body === 'string' && Buffer.byteLength(input.body) <= 2 * 1024 * 1024, '文本文件最多支持 2 MB。', 413);
    const title = typeof input.title === 'string' ? input.title.trim() : '';
    fail(title && title !== '.' && title !== '..' && title.isWellFormed() && input.title.length <= 120 &&
      !/[\x00-\x1f\x7f/\\]/.test(input.title), '请输入有效文件名（最多 120 个字符）。');
    fail(!/\.pdf$/i.test(title) && !/^\s*%PDF-\d\.\d/.test(input.body), 'PDF 可在批改工作区作为材料导入。');
    fail(!/\.(?:doc[xm]?|xls[xmb]?|ppt[xm]?|od[tsp])$/i.test(title), '请将 Office 文件另存为 UTF-8 文本或 CSV 后导入。');
    fail(input.body.isWellFormed() && !/[\x00-\x08\x0b\x0e-\x1f\x7f-\x84\x86-\x9f]/.test(input.body),
      '此文件含有二进制数据。工作台支持 UTF-8 文本。');
    return this.mutate(async state => {
      const existing = input.id && state.files.find(row => row.id === input.id);
      fail(!input.id || existing, '文件不存在。', 404);
      fail(!existing || input.revision === existing.revision, '文件已有新版本，你的编辑尚未覆盖它。', 409);
      fail(existing || state.files.length < 1000, '工作区已达到 1000 个文件的上限。');
      const fileId = existing?.id || id(), nextRevision = (existing?.revision || 0) + 1;
      const relativePath = `files/${fileId}/v${nextRevision}/${diskName(title)}`;
      await mkdir(join(this.directory, 'files', fileId, `v${nextRevision}`), { recursive: true, mode: 0o700 });
      await writeFile(join(this.directory, relativePath), input.body, { mode: 0o600 });
      const version = { threadId:threadId ?? existing?.threadId ?? null, title, kind: fileKind(title), body: input.body, hash: digest(input.body), revision: nextRevision, updatedAt: now(), sources: structuredClone(sources ?? existing?.sources ?? []), relativePath };
      if (existing) {
        if (version.threadId !== existing.threadId) for (const previous of existing.versions) {
          if (!Object.hasOwn(previous, 'threadId')) previous.threadId = existing.threadId ?? null;
        }
        Object.assign(existing, version);
        existing.versions.push(version);
        return publicFile(existing);
      }
      const file = { id: fileId, origin, threadId, status: threadId ? 'draft' : 'completed', createdAt: now(), ...version, versions: [version] };
      state.files.push(file); return publicFile(file);
    });
  }
  snapshot() {
    const files = this.catalog();
    return { revision: this.state.revision, gradingRevision:this.grading.state.revision, preferences: this.state.preferences, threads: this.state.threads.map(({ messages, ...thread }) => ({ ...thread, lastMessage: messages.at(-1) || null })), files, archiveInputs:structuredClone(this.catalogCache.inputs), skills: this.state.skills.map(({ instructions, ...skill }) => skill) };
  }
}
