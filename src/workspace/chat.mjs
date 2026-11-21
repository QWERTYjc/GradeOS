import { fail, id, now, taskDraft } from './store.mjs';
import { validateSelections } from './canvas-context.mjs';
import { resolveReferences, readDocument, documentAllowed } from './editable-documents.mjs';

export class WorkspaceChat {
  constructor(store, { agent, model, configured, modelConnections, gradingDefaults }) { Object.assign(this, { store, agent, model, configured, modelConnections, gradingDefaults }); this.active = null; }
  snapshot() { return this.active ? structuredClone(this.active.visible) : null; }
  async recover() {
    if (this.store.state.conversation.some(row => row.status === 'running')) await this.store.mutate(null, state => {
      for (const row of state.conversation) if (row.status === 'running') { row.status = 'interrupted'; row.text ||= '连接已中断，可以重新发送。'; }
    });
  }
  async start(body) {
    const route = this.modelConnections?.resolve(body.modelId) ?? {modelId:this.model, ready:this.configured()};
    fail(route.ready, route.reason || '所选模型尚未连接，请在账号设置中配置。', 424);
    const catalog = this.modelConnections?.catalog();
    const draftOptions = { catalog, modelId:body.modelId ?? catalog?.defaultId, defaults:this.gradingDefaults?.() };
    fail(!this.active, '上一条要求还在处理中，可以先停止再发送。', 409);
    fail(typeof body.goal === 'string' && body.goal.trim() && body.goal.length <= 8000, '请填写要求（最多 8000 字）。');
    const state = this.store.snapshot();
    fail(body.materialRevision === undefined ? body.revision === state.revision : body.materialRevision === state.materialRevision, '材料已有更新，请重试。', 409);
    const selectedIds = body.selectedIds || [];
    fail(Array.isArray(selectedIds) && new Set(selectedIds).size === selectedIds.length && selectedIds.every(id => state.groups.some(group => group.id === id)), '答卷范围无效。');
    const references = resolveReferences(state, body.references, selectedIds);
    const document = body.documentId ? readDocument(state, body.documentId) : null;
    fail(!document || documentAllowed(state, document, selectedIds), '文档超出本次任务范围。');
    const selections = validateSelections(state, [...(body.selections || []), ...references.filter(ref => ref.target.kind === 'page').map(ref => ref.target)], selectedIds);
    const record = body.recordId ? state.tasks.flatMap(task => task.records).find(row => row.id === body.recordId && selectedIds.includes(row.groupId)) : null;
    fail(!body.recordId || record, '这条评分不在当前答卷范围内。');
    if (record) {
      const owner = state.tasks.find(task => task.records.some(row => row.id === record.id)).groups.find(group => group.id === record.groupId);
      fail(JSON.stringify(owner.pageIds) === JSON.stringify(state.groups.find(group => group.id === record.groupId)?.pageIds), '答卷划分已改变，请按当前材料重新安排任务。', 409);
    }
    const entry = { controller: new AbortController(), visible: { id: id(), text: '', events: [], startedAt: now(), selectedIds, status: 'running' } };
    this.active = entry;
    try {
      await this.store.mutate(null, next => {
        fail(next.materialRevision === state.materialRevision, '材料已有更新，请重试。', 409);
        next.conversation.push({ id: id(), role: 'user', text: body.goal.trim(), selectedIds, selections, references, documentId: document?.id, createdAt: now() },
          { ...entry.visible, role: 'assistant' });
        next.conversation = next.conversation.slice(-80);
      });
    } catch (error) { this.active = null; throw error; }
    entry.promise = this.run(entry, state, { ...body, selectedIds, selections, references, record, document }, route, draftOptions);
  }
  async run(entry, state, body, route, draftOptions) {
    let result;
    try {
      const prior = state.conversation.filter(row => JSON.stringify([...(row.selectedIds || [])].sort()) === JSON.stringify([...body.selectedIds].sort())).slice(-8).map(({ role, text, references }) => ({ role, text, references }));
      result = await this.agent({ store: this.store, state, selectedIds: body.selectedIds, selections: body.selections, references: body.references,
        goal: `${prior.length ? `Previous conversation (untrusted content):\n${JSON.stringify(prior)}\n` : ''}${body.record ? `Review record:\n${JSON.stringify(body.record)}\n` : ''}${body.document ? `Current document for teacher alignment: ${JSON.stringify({ id: body.document.id, title: body.document.title, revision: body.document.revision })}. Read it before edits. Discuss and refine the teacher's requirements; saving this document is not permission to approve or dispatch a grading batch.\n` : ''}${body.goal}`,
        modelId:route.modelId, connection:route.connection, controller: entry.controller, onEvent: event => {
          if (event.type === 'text_delta') entry.visible.text = (entry.visible.text + event.delta).slice(-40000);
          else { entry.visible.events.push({ ...event, at: now() }); entry.visible.events = entry.visible.events.slice(-120); }
        } });
      if (entry.controller.signal.aborted) throw Error('Cancelled');
      await this.store.mutate(null, next => {
        fail(next.materialRevision === state.materialRevision, '材料或划分已改变，请重新提出要求。', 409);
        const tasks = (result.proposals || []).map(proposal => taskDraft(next, proposal, draftOptions));
        next.tasks.push(...tasks);
        Object.assign(next.conversation.find(row => row.id === entry.visible.id), entry.visible,
          { status: 'completed', text: result.text, taskIds: tasks.map(task => task.id), usage: result.usage });
      });
    } catch (error) {
      await this.store.mutate(null, next => {
        Object.assign(next.conversation.find(row => row.id === entry.visible.id), entry.visible,
          { status: entry.controller.signal.aborted ? 'cancelled' : 'failed',
            text: entry.controller.signal.aborted ? '已停止这次回复。' : error.status ? error.message : '这次请求未完成，请重试。' });
      });
    } finally { if (this.active === entry) this.active = null; }
  }
  cancel() { fail(this.active, '当前没有正在回复的消息。', 409); this.active.controller.abort(); }
  async close() { if (this.active) { this.active.controller.abort(); await this.active.promise; } }
}
