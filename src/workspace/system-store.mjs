import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import { fail, id, now } from './store.mjs';
import { digest } from '../core.mjs';
import { readDocument } from './editable-documents.mjs';
import { gradingResult, resultMarkdown } from '../../web/grading-result.mjs';

export const BUILTIN_SKILLS = [
  { id: 'teaching', name: '教辅资料', description: '依据引用材料编写讲义、练习和答案解析。', format: 'Markdown', instructions: 'Create clear teaching material with goals, worked examples and exercises. Preserve uncertainty and cite consulted sources. Save a Markdown document.' },
  { id: 'slides', name: '演示文稿', description: '生成可预览、下载的 HTML 演示文稿。', format: 'HTML', instructions: 'Create a polished self-contained HTML slide deck. Each slide must be a section element. Use inline CSS, no scripts, external assets, embeds or remote requests. Save as .html. Be explicit that this is HTML, not a .pptx file.' },
  { id: 'tables', name: '表格与数据', description: '整理 CSV 数据，输出可由 Excel 打开的表格。', format: 'CSV', instructions: 'Read supplied CSV data, explain transformations, preserve missing values, never fabricate rows or statistics. Save a valid UTF-8 CSV with header and proper quoting. Do not claim to read XLSX or execute calculations with unavailable tools.' },
  { id: 'code', name: '代码草稿', description: '编写和解释小型脚本，保存为本地代码文件。', format: '文本', instructions: 'Write or explain simple code and save source files. There is no shell or execution tool. Do not claim code has been run or tested. Do not modify any file outside this workspace.' },
];
const publicFile = ({ body, versions, ...file }) => ({ ...file, versionCount: versions?.length || 1 });
export const referenceKey = file => `${file.id}@${file.revision}:${file.hash}`;

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
      await this.mutate(state => { for (const thread of state.threads) for (const message of thread.messages) if (message.status === 'running') { message.status = 'interrupted'; message.text ||= '服务已重启，这次任务未完成。'; } });
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
    for (const doc of state.documents || []) files.push({ id: `document:${doc.id}`, title: doc.title, kind: 'document', origin: 'grading', revision: doc.revision, hash: doc.hash, updatedAt: doc.updatedAt, taskId: doc.taskId, versionCount: doc.history.length, status: doc.approvals?.length ? 'confirmed' : 'draft' });
    for (const task of state.tasks) {
      for (const artifact of task.artifacts || []) if (typeof artifact.body === 'string' && !state.documents.some(doc => doc.taskId === task.id && doc.artifactId === artifact.id)) {
        const fileId = `artifact:${task.id}:${artifact.id}`;
        files.push({ id: fileId, title: artifact.title || '批改报告', kind: 'document', origin: 'grading', taskId: task.id, revision: 1, hash: digest(artifact.body), updatedAt: task.completedAt || task.createdAt, status: task.status });
        this.gradingBodies.set(fileId, artifact.body);
      }
      for (const group of task.groups || []) {
        const result = gradingResult(state, task.id, group.id);
        if (!result) continue;
        const body = resultMarkdown(result, state.pages);
        files.push({ id: `result:${task.id}:${group.id}`, title: `${group.label || '答卷'} · 评分结果.md`, kind: 'document', origin: 'grading', taskId: task.id, revision: 1, hash: digest(body), updatedAt: task.completedAt || task.createdAt, status: task.status });
        this.gradingBodies.set(`result:${task.id}:${group.id}`, body);
      }
    }
    this.catalogCache = { key, files }; return structuredClone(files);
  }
  readFile(fileId, revision = null, expectedHash = null) {
    if (expectedHash && this.state.sourceSnapshots[`${fileId}:${expectedHash}`]) {
      const pinned = this.state.sourceSnapshots[`${fileId}:${expectedHash}`];
      fail(revision == null || revision === pinned.revision, '引用版本与文件快照不一致。', 409);
      return structuredClone(pinned);
    }
    let file;
    if (fileId.startsWith('document:')) {
      const doc = readDocument(this.grading.state, fileId.slice(9), revision);
      file = { ...this.catalog().find(row => row.id === fileId), body: doc.body, revision: doc.revision, hash: doc.hash };
    } else if (fileId.startsWith('artifact:') || fileId.startsWith('result:')) {
      const meta = this.catalog().find(row => row.id === fileId); fail(meta, '文件不存在。', 404);
      file = { ...meta, body: this.gradingBodies.get(fileId) };
    } else {
      const current = this.state.files.find(row => row.id === fileId); fail(current, '文件不存在。', 404);
      const version = revision == null ? current : current.versions.find(row => row.revision === revision); fail(version, '文件版本不存在。', 404);
      file = { ...publicFile(current), ...structuredClone(version), versions: undefined };
    }
    fail(!expectedHash || file.hash === expectedHash, '来源已有更新，请重新选择版本。', 409);
    return structuredClone(file);
  }
  async pinFile(file) {
    const key = `${file.id}:${file.hash}`;
    if (!this.state.sourceSnapshots[key]) await this.mutate(state => { state.sourceSnapshots[key] = structuredClone(file); });
  }
  async saveFile(input, { threadId = null, sources = null, origin = 'workspace' } = {}) {
    fail(typeof input.body === 'string' && Buffer.byteLength(input.body) <= 2 * 1024 * 1024, '文本文件最多支持 2 MB。', 413);
    fail(typeof input.title === 'string' && input.title.trim().length > 0 && input.title.length <= 120 && !/[\x00-\x1f/\\]/.test(input.title), '请输入有效文件名。');
    return this.mutate(async state => {
      const existing = input.id && state.files.find(row => row.id === input.id);
      fail(!input.id || existing, '文件不存在。', 404);
      fail(!existing || input.revision === existing.revision, '文件已有新版本，你的编辑尚未覆盖它。', 409);
      fail(existing || state.files.length < 1000, '工作区已达到 1000 个文件的上限。');
      const extension = input.title.split('.').at(-1).toLowerCase();
      fail(['md', 'txt', 'csv', 'json', 'html', 'js', 'mjs', 'py', 'css', 'ts', 'sql'].includes(extension), '支持 Markdown、CSV、HTML、JSON 和文本代码文件。');
      const fileId = existing?.id || id(), nextRevision = (existing?.revision || 0) + 1;
      const relativePath = `files/${fileId}/v${nextRevision}/${input.title.trim()}`;
      await mkdir(join(this.directory, 'files', fileId, `v${nextRevision}`), { recursive: true, mode: 0o700 });
      await writeFile(join(this.directory, relativePath), input.body, { mode: 0o600 });
      const version = { body: input.body, hash: digest(input.body), revision: nextRevision, updatedAt: now(), sources: structuredClone(sources ?? existing?.sources ?? []), relativePath };
      if (existing) { Object.assign(existing, version, { title: input.title.trim() }); existing.versions.push(version); return publicFile(existing); }
      const file = { id: fileId, title: input.title.trim(), kind: extension === 'html' ? 'presentation' : extension === 'csv' ? 'table' : 'document', origin, threadId, status: threadId ? 'draft' : 'completed', createdAt: now(), ...version, versions: [version] };
      state.files.push(file); return publicFile(file);
    });
  }
  snapshot() {
    return { revision: this.state.revision, preferences: this.state.preferences, threads: this.state.threads.map(({ messages, ...thread }) => ({ ...thread, lastMessage: messages.at(-1) || null })), files: this.catalog(), skills: this.state.skills.map(({ instructions, ...skill }) => skill) };
  }
}
