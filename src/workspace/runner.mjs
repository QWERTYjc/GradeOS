import { spawn } from 'node:child_process';
import { readFile, access, appendFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { digest } from '../core.mjs';
import { fail, id, makeRecord, now, startTask } from './store.mjs';
import { prepareTaskInput, experimentRoot } from './documents.mjs';
import { runWorkspaceAgent } from './agent.mjs';
import { collectGradingProgress } from './grading-progress.mjs';
import { validateFrozenRubric } from '../rubric-contract.mjs';
import { atomicJSON, readJSON, readQuestions } from '../teacher-interaction.mjs';
import { validateSelections } from './canvas-context.mjs';
import { addDocument, readDocument, resolveReferences } from './editable-documents.mjs';
import { runAdaptiveGrading, usesAdaptiveGrading } from './adaptive-runtime.mjs';
import { DEFAULT_MAIN_MODEL_ID, DEFAULT_WORKER_MODEL_ID } from '../experiment-models.mjs';

const json = async path => { try { return JSON.parse(await readFile(path, 'utf8')); } catch { return null; } };
export async function snapshotFrozenRubric(sourcePath, directory, scheme) {
  fail(sourcePath.endsWith('.json'), '冻结评分标准需要 JSON 文件和对应哈希校验文件。');
  const bytes = await readFile(sourcePath);
  const hash = (await readFile(sourcePath.replace(/\.json$/, '.sha256'), 'utf8')).trim();
  fail(digest(bytes) === hash, '冻结评分标准的文件哈希不一致。');
  validateFrozenRubric(JSON.parse(bytes), scheme);
  const frozenPath = join(directory, 'reused-rubric.json');
  await writeFile(frozenPath, bytes, { flag: 'wx', mode: 0o600 });
  await writeFile(join(directory, 'reused-rubric.sha256'), hash + '\n', { flag: 'wx', mode: 0o600 });
  return frozenPath;
}
export class WorkspaceRunner {
  constructor(store, { model = DEFAULT_MAIN_MODEL_ID, cap = 2, agent = runWorkspaceAgent, rubricPath = null } = {}) {
    this.store = store; this.model = model; this.cap = cap; this.agent = agent; this.rubricPath = rubricPath; this.active = new Map();
  }
  async readFailureReason(task) {
    const directory = join(this.store.directory, 'runs', task.id, 'output');
    const lanes = await readdir(directory, {withFileTypes:true}).catch(() => []);
    for (const lane of lanes.filter(entry => entry.isDirectory() && (entry.name === 'main' || entry.name.startsWith('student-')))) {
      const messages = await json(join(directory, lane.name, 'transcript.json'));
      const failure = Array.isArray(messages) && messages.findLast(message => message.role === 'assistant' && message.stopReason === 'error');
      if (failure?.errorMessage?.includes('This model is not available in your region')) {
        return '模型服务拒绝了请求（403）：当前模型在此地区不可用。';
      }
    }
    return null;
  }
  async recover() {
    this.failureReasons = {};
    for (const task of this.store.state.tasks.filter(row => row.status === 'failed' && row.kind === 'grade')) {
      const reason = await this.readFailureReason(task);
      if (reason) this.failureReasons[task.id] = reason;
    }
    if (this.store.state.tasks.some(task => task.status === 'running')) await this.store.mutate(null, state => {
      for (const task of state.tasks.filter(item => item.status === 'running')) {
        task.status = 'interrupted'; task.error = '服务已重启。已保存的结果保留，任务不会自动重跑。';
      }
    });
  }
  async start(taskId, revision) {
    fail(Boolean(process.env.OPENROUTER_API_KEY), '尚未连接模型，请配置 OPENROUTER_API_KEY 后启动任务。', 424);
    const task = await this.store.mutate(revision, state => startTask(state, taskId));
    const controller = new AbortController();
    const entry = { controller, promise: null, child: null };
    this.active.set(taskId, entry);
    entry.promise = this.execute(task, entry).catch(async () => {
      const reason = !controller.signal.aborted && task.kind === 'grade' && await this.readFailureReason(task);
      await this.store.mutate(null, state => {
        const row = state.tasks.find(item => item.id === taskId);
        row.status = controller.signal.aborted ? 'cancelled' : (row.records.length || row.artifacts.length ? 'partial' : 'failed');
        row.error = controller.signal.aborted ? '任务已取消，已完成的记录仍保留。' : reason || '任务未完成。已有结果保留，可查看运行目录中的回执。';
        if (entry.events?.length) row.interaction = { events: entry.events.slice(-120), questions: [], notes: [] };
        row.finishedAt = now();
      });
    }).finally(() => this.active.delete(taskId));
    return task.id;
  }
  async execute(task, entry) {
    const input = await prepareTaskInput(this.store, task);
    if (entry.controller.signal.aborted) throw Error('Cancelled');
    if (task.kind === 'assist') {
      const current = this.store.snapshot();
      const records = current.tasks.flatMap(previous => previous.records.filter(record => {
        const selected = task.groups.find(group => group.id === record.groupId);
        const owner = previous.groups.find(group => group.id === record.groupId);
        return selected && owner && JSON.stringify(selected.pageIds) === JSON.stringify(owner.pageIds);
      })).map(record => ({ ...record,
        teacherReview: current.reviews.filter(review => review.recordId === record.id).at(-1) ?? null,
      }));
      const result = await this.agent({ store: this.store,
        state: { ...current, groups: task.groups, pages: task.pages, schemes: task.scheme ? [task.scheme] : [], questions: task.question ? [task.question] : [] },
        selectedIds: task.groupIds, goal: task.goal, mode: 'work', records, selections: task.selections || [], references: task.references || [],
        onEvent: event => { if (event.type !== 'text_delta') { entry.events ||= []; entry.events.push({ ...event, at: now() }); } },
        controller: entry.controller, modelId: this.model, cap: this.cap });
      if (entry.controller.signal.aborted) throw Error('Cancelled');
      fail(result.documents.length > 0, 'Agent 没有提交成果。');
      await this.store.mutate(null, state => {
        const row = state.tasks.find(item => item.id === task.id);
        row.artifacts = result.documents; row.usage = result.usage;
        for (const artifact of result.documents) {
          const document = addDocument(state, { title: artifact.title, body: artifact.body, taskId: task.id,
            sourcePageIds: [...task.groups.flatMap(group => group.pageIds), ...(task.scheme?.pageIds || []), ...(task.question?.pageIds || [])] }, 'agent');
          state.documents.find(item => item.id === document.id).artifactId = artifact.id;
        }
        row.interaction = { events: (entry.events || []).slice(-120), questions: [], notes: [] };
        row.status = row.after === 'review' ? 'needs_review' : 'completed'; row.finishedAt = now();
        row.progress = { phase: '成果已保存', elapsedSeconds: (Date.parse(row.finishedAt) - Date.parse(row.startedAt)) / 1000,
          settledCostUsd: result.usage?.provider_reported_cost_usd, unknownCostRequests: result.usage?.unknown_cost_requests };
      });
      return;
    }
    entry.interaction = join(input.directory, 'interaction');
    await mkdir(join(entry.interaction, 'answers'), { recursive: true });
    await atomicJSON(join(entry.interaction, 'control.json'), { paused: false, executionMode: task.executionMode || 'review', guideDraft: task.guideDraft || null,
      supplementalInstructions: task.supplementalInstructions ?? (task.goal === '批改所选答卷' ? '' : task.goal || ''), gradingContext: task.gradingContext || '',
      notes: [{ id: id(), text: '批改所选答卷',
      groupIds: task.groupIds, selections: task.selections || [], references: task.references || [], createdAt: now(), origin: 'task' }] });
    if (usesAdaptiveGrading(task)) return runAdaptiveGrading({ store: this.store, task, input, entry, runner: this });
    const config = task.modelConfig;
    const workerModel = config?.workerModel ?? DEFAULT_WORKER_MODEL_ID;
    const args = [join(experimentRoot, 'src/run-cohort.mjs'), '--manifest', input.manifest, '--output', input.output,
      '--interaction-dir', entry.interaction,
      '--execute', '--model', config?.mainModel ?? this.model, '--worker-model', workerModel, '--scripted', '--cap', String(this.cap), '--max-requests', '256',
      ...(config ? ['--main-reasoning', config.mainEffort, '--worker-reasoning', config.workerEffort] : ['--grading-reasoning', 'medium']), '--inline-annotations', '--student-cap', String(workerModel === 'openai/gpt-6-luna' ? Math.min(this.cap, .01) : this.cap)];
    if (this.rubricPath) {
      const manifest = await json(input.manifest);
      const scheme = (await json(join(manifest.scheme_input, 'manifest.json'))).documents.scheme;
      const frozenPath = await snapshotFrozenRubric(this.rubricPath, input.directory, scheme);
      args.push('--rubric', frozenPath);
    }
    for (const prior of this.rubricPath ? [] : [...this.store.state.tasks].reverse()) {
      if (prior.id === task.id || prior.schemeId !== task.schemeId || !['completed', 'needs_review', 'partial'].includes(prior.status)) continue;
      const rubric = join(this.store.directory, 'runs', prior.id, 'output/rubric.json');
      try { await access(rubric); args.push('--rubric', rubric); break; } catch { /* No frozen rubric yet. */ }
    }
    const child = spawn(process.execPath, args, { cwd: experimentRoot, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    entry.child = child;
    const logPath = join(input.directory, 'process.log');
    for (const stream of [child.stdout, child.stderr]) stream.on('data', data => { void appendFile(logPath, data).catch(() => {}); });
    let killTimer;
    const cancel = () => { child.kill('SIGINT'); killTimer = setTimeout(() => child.kill('SIGKILL'), 10000); killTimer.unref(); };
    entry.controller.signal.addEventListener('abort', cancel, { once: true });
    if (entry.controller.signal.aborted) cancel();
    let collecting = false;
    const timer = setInterval(async () => {
      if (collecting) return;
      collecting = true;
      try { await this.collect(task, input.output, false); } catch { /* Retry only the local projection, never model execution. */ }
      finally { collecting = false; }
    }, 1500);
    try {
      const code = await new Promise((resolve, reject) => { child.once('error', reject); child.once('exit', resolve); });
      clearInterval(timer);
      while (collecting) await new Promise(resolve => setTimeout(resolve, 10));
      await this.collect(task, input.output, true);
      if (entry.controller.signal.aborted) throw Error('Cancelled');
      if (code !== 0) throw Error('Grading incomplete');
    } finally {
      clearInterval(timer); clearTimeout(killTimer); entry.controller.signal.removeEventListener('abort', cancel);
    }
  }
  async collect(task, output, final) {
    await this.syncGuide(task);
    const rubric = await json(join(output, 'rubric.json'));
    const records = []; let completed = 0;
    for (const group of task.groups) {
      const grade = await json(join(output, `student-${group.id}/grading.json`));
      if (!grade || !rubric) continue;
      completed++;
      for (const item of grade.items) {
        const criterion = rubric.artifact.items.find(row => row.item_id === item.item_id);
        if (item.point_decisions?.length) {
          for (const point of item.point_decisions) records.push(makeRecord(task, group, item, point,
            criterion?.scoring_points.find(row => row.point_id === point.point_id), digest(grade), rubric.hash));
        } else records.push(makeRecord(task, group, item, null, criterion, digest(grade), rubric.hash));
      }
    }
    const summary = final ? await json(join(output, 'summary.json')) : null;
    const projection = await collectGradingProgress({ task, output, summary, gradingSaved: completed, records, rubricReady: Boolean(rubric), final });
    const previous = this.store.state.tasks.find(item => item.id === task.id);
    const interaction = await this.interactionSnapshot(task.id);
    if (interaction.guide?.status === 'awaiting_teacher') projection.progress.phase = task.executionMode === 'auto' ? '正在采用评分实施说明' : '请编辑并确认评分实施.md';
    if (!final && JSON.stringify(previous.progress) === JSON.stringify(projection.progress)
      && JSON.stringify(previous.artifacts) === JSON.stringify(projection.artifacts) && JSON.stringify(previous.interaction) === JSON.stringify(interaction)) return;
    await this.store.mutate(null, state => {
      const row = state.tasks.find(item => item.id === task.id);
      row.records = records; row.progress = projection.progress; row.artifacts = projection.artifacts;
      row.interaction = interaction;
      if (final) {
        row.status = summary?.status === 'submitted' ? (task.after === 'review' || records.some(record => record.reviewRequired) ? 'needs_review' : 'completed') : completed ? 'partial' : 'failed';
        row.finishedAt = now();
        row.usage = summary ? { provider_reported_cost_usd: summary.provider_reported_cost_usd, unknown_cost_requests: summary.unknown_cost_requests } : null;
        if (row.status === 'partial') row.error = '部分工作未完成；已产生的评分和报告分别保留。';
      }
    });
  }
  async interactionSnapshot(taskId) {
    const directory = join(this.store.directory, 'runs', taskId, 'interaction');
    const control = await readJSON(join(directory, 'control.json'), {});
    const activity = await readFile(join(directory, 'activity.jsonl'), 'utf8').catch(() => '');
    const events = activity.trim().split('\n').slice(-160).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
    const proposal = await readJSON(join(directory, 'guide-proposal.json'));
    const document = this.store.state.documents.find(row => row.taskId === taskId && row.proposalId === proposal?.id);
    const guide = document ? { documentId: document.id, status: document.approvals.length ? 'approved' : proposal.status, revision: document.revision, approvedRevision: document.approvals.at(-1)?.revision, approvalMethod: document.approvals.at(-1)?.method || 'teacher' } : null;
    return { paused: Boolean(control.paused), notes: control.notes || [], questions: await readQuestions(directory), events, guide };
  }
  async syncGuide(task) {
    const proposal = await readJSON(join(this.store.directory, 'runs', task.id, 'interaction/guide-proposal.json'));
    if (!proposal) return;
    const existing = this.store.state.documents.find(row => row.taskId === task.id && row.proposalId === proposal.id);
    if (existing) {
      const approval = await readJSON(join(this.store.directory, 'runs', task.id, 'interaction/guide-approval.json'));
      if (approval && !existing.approvals.length && existing.history.some(version => version.revision === approval.revision && version.hash === approval.hash))
        await this.store.mutate(null, state => { const document = state.documents.find(row => row.id === existing.id); if (!document.approvals.length) document.approvals.push({ revision: approval.revision, hash: approval.hash, approvedAt: approval.approvedAt, method: approval.method || 'teacher' }); });
      else if (!approval && task.executionMode === 'auto' && !existing.approvals.length)
        await this.approveGuide(existing.id, { revision: existing.revision, hash: existing.hash }, 'automatic');
      return;
    }
    await this.store.mutate(null, state => {
      if (state.documents.some(row => row.taskId === task.id && row.proposalId === proposal.id)) return;
      addDocument(state, { title: proposal.title, body: proposal.body, kind: 'marking_guide', taskId: task.id,
        schemeId: task.schemeId, sourcePageIds: usesAdaptiveGrading(task) ? task.pages.map(page => page.id) : task.scheme.pageIds, proposalId: proposal.id,
        rubricHash: proposal.rubricHash, sourceHash: proposal.sourceHash }, 'agent');
    });
  }
  async approveGuide(documentId, input, method = 'teacher') {
    const document = readDocument(this.store.state, documentId), entry = this.active.get(document.taskId);
    const task = this.store.state.tasks.find(row => row.id === document.taskId && row.status === 'running');
    fail(entry?.interaction && task, '这份文档当前没有等待确认的批改任务。', 409);
    fail(method === 'teacher' || (method === 'automatic' && task.executionMode === 'auto'), '本批次需要老师确认评分要求。', 409);
    const pending = (entry.controlQueue || Promise.resolve()).then(async () => {
      const proposal = await readJSON(join(entry.interaction, 'guide-proposal.json'));
      fail(proposal?.id === document.proposalId, '评分实施文档已改变。', 409);
      await this.store.mutate(null, async state => {
        const current = readDocument(state, documentId);
        fail(current.revision === input.revision && current.hash === input.hash, '文档已更新，请查看最新版本再确认。', 409);
        fail(current.body.trim(), '请先填写评分实施说明。');
        const previous = state.documents.find(row => row.id === documentId).approvals.at(-1);
        fail(!previous || previous.revision === current.revision, '本批次已采用之前确认的版本。后续编辑可用于新批次。', 409);
        const approved = { documentId, proposalId: proposal.id, revision: current.revision, hash: current.hash, body: current.body,
          rubricHash: proposal.rubricHash, sourceHash: proposal.sourceHash, approvedAt: previous?.approvedAt || now(), method };
        await atomicJSON(join(entry.interaction, 'guide-approval.json'), approved);
        if (!previous) state.documents.find(row => row.id === documentId).approvals.push({ revision: current.revision, hash: current.hash, approvedAt: approved.approvedAt, method });
      });
    });
    entry.controlQueue = pending.catch(() => {}); await pending;
  }
  async control(taskId, action, body = {}) {
    const entry = this.active.get(taskId), task = this.store.state.tasks.find(task => task.id === taskId);
    fail(entry?.interaction && task?.status === 'running', '此批改任务当前不可交互。', 409);
    const pending = (entry.controlQueue || Promise.resolve()).then(async () => {
      const path = join(entry.interaction, 'control.json'), control = await readJSON(path, { paused: false, notes: [] });
      if (action === 'pause' || action === 'resume') control.paused = action === 'pause';
      else {
        fail(typeof body.text === 'string' && body.text.trim() && body.text.length <= 4000, '请填写说明（最多 4000 字）。');
        const groups = body.groupIds || task.groupIds;
        fail(Array.isArray(groups) && groups.length && groups.every(id => task.groupIds.includes(id)), '补充要求超出当前任务范围。');
        const frozenState = { ...this.store.snapshot(), groups: task.groups, pages: task.pages, schemes: task.scheme ? [task.scheme] : [], questions: task.question ? [task.question] : [] };
        const references = resolveReferences(frozenState, body.references, groups);
        const selections = validateSelections(frozenState, [...(body.selections || []), ...references.filter(ref => ref.target.kind === 'page').map(ref => ref.target)], groups);
        const note = { id: id(), text: body.text.trim(), groupIds: groups, selections, references, createdAt: now() };
        if (action === 'answer') {
          const question = (await readQuestions(entry.interaction)).find(row => row.id === body.questionId);
          fail(question?.status === 'open', '这个问题已经结束。', 409);
          const own = [...task.groupIds].sort((a, b) => b.length - a.length).find(id => question.lane === `student-${id}` || question.lane === `feedback-${id}` || question.lane === `source-review-${id}` || question.lane.startsWith(`exception-${id}-`));
          fail(selections.every(selection => ['scheme', 'question'].includes(selection.role) || (own && task.groups.find(group => group.id === own).pageIds.includes(selection.pageId))), '圈选不属于当前问题，请仅引用对应答卷、题目或评分标准。');
          resolveReferences(frozenState, references, own ? [own] : []);
          const answerPath = join(entry.interaction, 'answers', `${question.id}.json`);
          fail(!await readJSON(answerPath), '已提交回复，正在等待 agent 接收。', 409);
          await atomicJSON(answerPath, note);
        } else { fail(control.notes.length < 100, '本次任务的补充已达上限。'); control.notes.push(note); }
        await this.store.mutate(null, state => state.conversation.push({ ...note, role: 'user', selectedIds: groups, taskId, questionId: body.questionId, delivery: 'queued' }));
      }
      await atomicJSON(path, control);
      await this.store.mutate(null, state => { state.tasks.find(row => row.id === taskId).interaction = { ...(task.interaction || {}), paused: control.paused, notes: control.notes }; });
    });
    entry.controlQueue = pending.catch(() => {}); await pending;
  }
  cancel(taskId) {
    const entry = this.active.get(taskId);
    fail(entry, '任务已经结束。', 409);
    entry.controller.abort();
  }
  async close() {
    for (const entry of this.active.values()) entry.controller.abort();
    await Promise.allSettled([...this.active.values()].map(entry => entry.promise));
  }
}
