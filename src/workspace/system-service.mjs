import { fail, id, now } from './store.mjs';
import { SystemStore, referenceKey } from './system-store.mjs';
import { runSystemAgent } from './system-agent.mjs';

export class SystemService {
  constructor(grading, { model, cap, configured, agent = runSystemAgent }) { Object.assign(this, { grading, model, cap, configured, agent }); this.active = null; }
  async init() { this.store = await new SystemStore(this.grading.directory, this.grading).init(); return this; }
  snapshot() { return { ...this.store.snapshot(), active: this.active?.visible || null, connection: { provider: 'OpenRouter', ready: this.configured(), model: this.model, cap: this.cap }, directory: this.store.directory }; }
  async start(body) {
    fail(this.configured(), '尚未连接模型。请先在设置中查看模型连接；本地文件仍可使用。', 424);
    fail(!this.active, '当前任务仍在进行，可先停止后再发送。', 409);
    fail(typeof body.goal === 'string' && body.goal.trim() && body.goal.length <= 8000, '请输入任务要求（最多 8000 字）。');
    fail(!body.threadId || this.store.state.threads.some(thread => thread.id === body.threadId), '对话不存在。', 404);
    fail(Array.isArray(body.references || []) && (body.references || []).length <= 8, '最多引用 8 个文件。');
    const references = (body.references || []).map(ref => this.store.readFile(ref.id, ref.revision, ref.hash));
    const skills = this.store.state.skills.filter(skill => skill.enabled && (!body.skillId || skill.id === body.skillId));
    fail(!body.skillId || skills.length > 0, '这个 Skill 未启用。');
    const catalog = this.store.catalog();
    // Freeze contents at dispatch, but send metadata only until the model asks to read.
    const frozen = new Map(catalog.map(file => [file.id, this.store.readFile(file.id, file.revision, file.hash)]));
    for (const ref of references) frozen.set(ref.id, ref);
    const used = new Map(references.map(file => [referenceKey(file), { id: file.id, title: file.title, revision: file.revision, hash: file.hash }]));
    const threadId = body.threadId || id(), messageId = id();
    const entry = { controller: new AbortController(), visible: { id: messageId, threadId, status: 'running', startedAt: now(), text: '', events: [], fileIds: [] } }; this.active = entry;
    let history;
    try {
      for (const reference of references) await this.store.pinFile(reference);
      await this.store.mutate(state => {
        let thread = state.threads.find(row => row.id === threadId);
        if (!thread) { thread = { id: threadId, title: body.goal.trim().slice(0, 48), createdAt: now(), messages: [] }; state.threads.push(thread); }
        history = thread.messages.slice(-12).map(({ role, text }) => ({ role, text }));
        thread.updatedAt = now(); thread.messages.push({ id: id(), role: 'user', text: body.goal.trim(), references: [...used.values()], createdAt: now() }, { ...entry.visible, role: 'assistant' });
      });
    } catch (error) { this.active = null; throw error; }
    entry.promise = this.run(entry, { goal: body.goal.trim(), history, references, catalog, skills, readFile: async fileId => {
      entry.controller.signal.throwIfAborted(); const file = frozen.get(fileId); fail(file, '文件不在本次工作区快照中。', 404);
      await this.store.pinFile(file); used.set(referenceKey(file), { id: file.id, title: file.title, revision: file.revision, hash: file.hash }); return file;
    }, saveFile: async input => {
      entry.controller.signal.throwIfAborted();
      if (input.id) fail([...used.values()].some(file => file.id === input.id && file.revision === input.revision), '请先阅读要修改的文件版本。');
      const result = await this.store.saveFile(input, { threadId, sources: [...used.values()] });
      entry.visible.fileIds = [...new Set([...entry.visible.fileIds, result.id])];
      frozen.set(result.id, this.store.readFile(result.id)); return result;
    } });
    return threadId;
  }
  async run(entry, args) {
    try {
      const result = await this.agent({ ...args, directory: this.store.directory, modelId: this.model, cap: this.cap, controller: entry.controller, onEvent: event => {
        if (event.type === 'text_delta') entry.visible.text = (entry.visible.text + event.delta).slice(-60000);
        else entry.visible.events = [...entry.visible.events, { ...event, at: now() }].slice(-100);
      } });
      entry.controller.signal.throwIfAborted(); Object.assign(entry.visible, result, { status: 'completed' });
    } catch (error) { Object.assign(entry.visible, { status: entry.controller.signal.aborted ? 'cancelled' : 'failed', text: entry.controller.signal.aborted ? '已停止。已保存的文件仍保留在工作区。' : error.status ? error.message : '这次请求未完成，请重试。' }); }
    finally {
      entry.visible.completedAt = now();
      await this.store.mutate(state => { const thread = state.threads.find(row => row.id === entry.visible.threadId); Object.assign(thread.messages.find(row => row.id === entry.visible.id), entry.visible); thread.updatedAt = now(); for (const file of state.files) if (entry.visible.fileIds.includes(file.id)) file.status = entry.visible.status === 'completed' ? 'completed' : 'partial'; });
      if (this.active === entry) this.active = null;
    }
  }
  async close() { if (this.active) { this.active.controller.abort(); await this.active.promise; } }
  async route({ req, url, body, send, res }) {
    const path = url.pathname.replace('/api/system', '');
    if (req.method === 'GET' && path === '/state') return send(res, 200, this.snapshot());
    if (req.method === 'GET' && path.startsWith('/threads/')) {
      const thread = this.store.state.threads.find(row => row.id === path.slice(9)); fail(thread, '对话不存在。', 404); return send(res, 200, thread);
    }
    if (req.method === 'GET' && path.startsWith('/files/')) {
      const file = this.store.readFile(decodeURIComponent(path.slice(7)), url.searchParams.has('revision') ? Number(url.searchParams.get('revision')) : null, url.searchParams.get('hash'));
      if (url.searchParams.has('preview')) {
        fail(file.title.toLowerCase().endsWith('.html'), '此文件不支持 HTML 预览。');
        // Preview is an opaque-origin sandbox, with no script, remote asset or navigation privileges.
        res.setHeader('Content-Security-Policy', "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'");
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        const slide = Number(url.searchParams.get('slide'));
        const style = Number.isInteger(slide) && slide > 0 && slide <= 100 ? `<style>body>section{display:none!important}body>section:nth-of-type(${slide}){display:flex!important}html,body{margin:0;min-height:100%;overflow:auto}</style>` : '';
        return res.end(file.body + style);
      }
      if (!url.searchParams.has('download')) return send(res, 200, file);
      res.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(file.title)}` }); return res.end(file.body);
    }
    if (req.method === 'POST' && path === '/chat') { const threadId = await this.start(body); return send(res, 202, { ...this.snapshot(), threadId }); }
    if (req.method === 'POST' && path === '/cancel') { fail(this.active, '当前没有正在执行的任务。', 409); this.active.controller.abort(); return send(res, 202, this.snapshot()); }
    if (req.method === 'POST' && path === '/files') { const file = await this.store.saveFile(body); return send(res, 201, { ...this.snapshot(), file }); }
    if (req.method === 'PATCH' && path === '/preferences') {
      await this.store.mutate(state => { for (const key of ['displayName', 'workspaceName']) if (body[key] !== undefined) { fail(typeof body[key] === 'string' && body[key].trim().length > 0 && body[key].length <= 60, '名称应为 1–60 个字符。'); state.preferences[key] = body[key].trim(); }
        if (body.motion !== undefined) { fail(['system', 'reduce'].includes(body.motion), '动效设置无效。'); state.preferences.motion = body.motion; } });
      return send(res, 200, this.snapshot());
    }
    if (req.method === 'PATCH' && path.startsWith('/skills/')) {
      await this.store.mutate(state => { const skill = state.skills.find(row => row.id === path.slice(8)); fail(skill && typeof body.enabled === 'boolean', 'Skill 不存在或设置无效。'); skill.enabled = body.enabled; }); return send(res, 200, this.snapshot());
    }
    if (req.method === 'POST' && path === '/skills') {
      fail(typeof body.name === 'string' && body.name.trim() && body.name.length <= 60 && typeof body.instructions === 'string' && body.instructions.trim() && body.instructions.length <= 20000, '请提供名称和有效的 SKILL.md（最多 20,000 字）。');
      await this.store.mutate(state => { fail(state.skills.length < 40, '最多安装 40 个 Skills。'); state.skills.push({ id: id(), name: body.name.trim(), instructions: body.instructions, description: '从本地导入的任务指南', format: '本地', enabled: false, builtin: false }); }); return send(res, 201, this.snapshot());
    }
    fail(false, '找不到此操作。', 404);
  }
}
