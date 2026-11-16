import { mkdir, readFile, writeFile, rename, appendFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { readSelectionImage } from './workspace/canvas-context.mjs';
import { createInitialSystemMessage, toToolDeclaration } from '@earendil-works/pi-ai';
import { markingGuideMarkdown, validateGuideApproval } from './marking-guide.mjs';
import { digest } from './core.mjs';

export const readJSON = async (path, fallback = null) => { try { return JSON.parse(await readFile(path, 'utf8')); } catch (error) { if (error.code === 'ENOENT') return fallback; throw error; } };
export async function atomicJSON(path, value) {
  const temporary = `${path}.${randomUUID()}.pending`;
  await writeFile(temporary, JSON.stringify(value), { mode: 0o600 }); await rename(temporary, path);
}
export async function readQuestions(directory) {
  const names = await readdir(join(directory, 'questions')).catch(() => []);
  return (await Promise.all(names.filter(name => /^[\w-]+\.json$/.test(name)).map(name => readJSON(join(directory, 'questions', name))))).filter(Boolean).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}
const labels = { read_scheme_pages: '查看评分标准原页', read_student_pages: '查看答卷原页', read_pages: '查看材料原页',
  review_grading_requirements: '核对补充批改要求',
  read_selection: '查看老师圈选的区域', ask_teacher: '等待老师确认', submit_ms_review: '保存 MS 核对结果',
  submit_grading: '保存批改依据', delegate_student: '安排答卷批改', submit_student_feedback: '保存个人反馈',
  create_task_draft: '拟定任务安排', inspect_workspace: '核对材料范围', save_document: '保存整理成果' };

/** Optional UI bridge. The CLI without --interaction-dir keeps its original agent inputs. */
export class TeacherInteraction {
  constructor(directory, { signal, schemePages = [], questionPages = [], students = new Map() } = {}) {
    this.directory = directory; this.signal = signal; this.schemePages = schemePages; this.questionPages = questionPages; this.students = students;
    this.agents = new WeakMap(); this.queue = Promise.resolve();
    this.waiting = new Set(); this.waited = 0; this.waitStarted = null;
  }
  async init() {
    await mkdir(join(this.directory, 'questions'), { recursive: true });
    await mkdir(join(this.directory, 'answers'), { recursive: true });
    return this;
  }
  async publishGuide(frozen, implementation, { body = null } = {}) {
    const requirements = await this.requireCompatibleRequirements();
    const control = await readJSON(join(this.directory, 'control.json'), {});
    const proposal = { id: randomUUID(), title: '评分实施.md', rubricHash: frozen.hash, sourceHash: frozen.artifact.source_sha256,
      body: (body ?? markingGuideMarkdown(frozen, implementation, control.guideDraft)) + (requirements ? `\n\n## 本批已核对的补充要求\n\n${requirements}` : ''), executionMode: control.executionMode === 'auto' ? 'auto' : 'review', status: 'awaiting_teacher', createdAt: new Date().toISOString() };
    if (proposal.body.length > 120000) throw Error('The complete implementation document exceeds 120,000 characters; it cannot be silently truncated.');
    await atomicJSON(join(this.directory, 'guide-proposal.json'), proposal);
    await writeFile(join(this.directory, '评分实施-待确认.md'), proposal.body, { mode: 0o600 });
    await this.log({ type: 'guide_ready', label: proposal.executionMode === 'auto' ? '评分实施.md 已整理，按本批授权继续' : '评分要求已就绪，等待老师确认；答卷尚未开始批改', lane: 'main', proposalId: proposal.id });
    this.wait('marking-guide', true);
    try {
      for (;;) {
        this.signal?.throwIfAborted();
        const approval = await readJSON(join(this.directory, 'guide-approval.json'));
        if (approval) {
          this.guide = validateGuideApproval(approval, proposal);
          await atomicJSON(join(this.directory, 'guide-proposal.json'), { ...proposal, status: 'approved', approvedRevision: approval.revision, documentId: approval.documentId });
          await this.log({ type: 'guide_approved', label: `${approval.method === 'automatic' ? '按自动模式采用' : '老师已确认'}评分实施.md · v${approval.revision}`, lane: 'main', hash: approval.hash });
          return this.guide;
        }
        await delay(250, undefined, { signal: this.signal });
      }
    } finally { this.wait('marking-guide', false); }
  }
  async requirements() {
    const control = await readJSON(join(this.directory, 'control.json'), {});
    const input = { supplementalInstructions: control.supplementalInstructions || '', gradingContext: control.gradingContext || '' };
    const inputHash = digest(input);
    const saved = await readJSON(join(this.directory, 'requirements-review.json'));
    const review = saved?.inputHash === inputHash ? saved : null;
    const original = [input.gradingContext && `学科与考试背景：${input.gradingContext}`, input.supplementalInstructions && `补充批改要求：${input.supplementalInstructions}`].filter(Boolean).join('\n');
    return { input, inputHash, original, review };
  }
  async requireCompatibleRequirements() {
    const state = await this.requirements();
    if (state.original && state.review?.status !== 'compatible') throw Error('先调用 review_grading_requirements 核对补充要求；有冲突时说明原因并等待老师调整。自动继续模式也不能跳过。');
    return state.review?.effectiveInstructions || '';
  }
  async reviewRequirements({ decision, explanation, question = '', adjustedInstructions = '' }) {
    if (!['compatible', 'needs_adjustment'].includes(decision) || typeof explanation !== 'string' || !explanation.trim() || explanation.length > 4000 || typeof adjustedInstructions !== 'string' || adjustedInstructions.length > 12000) throw Error('Invalid grading requirements review');
    const state = await this.requirements();
    if (!state.original) return { status: 'not_needed', message: 'No supplemental requirements; proceed with source-based grading.' };
    const path = join(this.directory, 'requirements-review.json');
    if (decision === 'compatible') {
      if (state.review?.status === 'compatible') return state.review;
      // The agent cannot silently rewrite the initial request. Revisions require a real teacher reply.
      if (!state.review?.teacherAnswer && adjustedInstructions) throw Error('未经老师回复不能改写补充要求；若不适用，请先提出调整问题。');
      const effectiveInstructions = state.review?.teacherAnswer ? adjustedInstructions.trim() : state.original;
      const review = { ...state.review, inputHash: state.inputHash, status: 'compatible', explanation: explanation.trim(), effectiveInstructions, reviewedAt: new Date().toISOString() };
      await atomicJSON(path, review);
      await this.log({ type: 'requirements_reviewed', label: '补充批改要求已核对', lane: 'main' });
      return review;
    }
    if (typeof question !== 'string' || !question.trim() || question.length > 4000) throw Error('请向老师说明具体冲突并提出调整建议。');
    await atomicJSON(path, { inputHash: state.inputHash, status: 'awaiting_teacher', explanation: explanation.trim() });
    const answer = await this.ask('main', { question: `${explanation.trim()}\n\n${question.trim()}`, kind: 'grading_requirements' });
    const review = { inputHash: state.inputHash, status: 'awaiting_reassessment', explanation: explanation.trim(), teacherAnswer: answer.teacherAnswer };
    await atomicJSON(path, review);
    return { ...review, message: 'Assess the actual teacher reply against the sources, then call review_grading_requirements again. If resolved, provide the complete agreed instructions in adjustedInstructions; otherwise ask a focused follow-up. Do not silently accept an unresolved conflict.' };
  }
  log(event) {
    const entry = { id: randomUUID(), at: new Date().toISOString(), ...event };
    const pending = this.queue.then(() => appendFile(join(this.directory, 'activity.jsonl'), JSON.stringify(entry) + '\n'));
    this.queue = pending.catch(() => {}); return pending;
  }
  owner(lane) { return [...this.students.keys()].sort((a, b) => b.length - a.length).find(id => lane === `student-${id}` || lane === `feedback-${id}` || lane === `source-review-${id}` || lane.startsWith(`exception-${id}-`)); }
  wait(key, value) {
    if (value) { if (!this.waiting.size) this.waitStarted = Date.now(); this.waiting.add(key); }
    else { this.waiting.delete(key); if (!this.waiting.size && this.waitStarted !== null) { this.waited += Date.now() - this.waitStarted; this.waitStarted = null; } }
  }
  get waitMilliseconds() { return this.waited + (this.waitStarted === null ? 0 : Date.now() - this.waitStarted); }
  visibleQuestion(lane, row) {
    if (row.lane === lane) return true;
    return ['main', 'ms-review'].includes(row.lane) && row.references.length > 0 && row.references.every(ref => ['scheme', 'question'].includes(ref.role));
  }
  references(lane, refs = []) {
    if (!Array.isArray(refs) || refs.length > 12) throw Error('Invalid source references');
    return refs.map(ref => {
      const pages = ref.role === 'scheme' ? this.schemePages : ref.role === 'question' ? this.questionPages : ref.role === 'student' ? this.students.get(this.owner(lane)) || [] : [];
      const page = pages[ref.page - 1];
      if (!Number.isInteger(ref.page) || !page) throw Error('Source reference outside this agent lane');
      return { role: ref.role, page: ref.page, pageId: page.workspace_page_id || page.id, groupId: ref.role === 'student' ? this.owner(lane) : null };
    });
  }
  async ask(lane, { question, references = [], kind = 'source_clarification' }) {
    if (typeof question !== 'string' || !question.trim() || question.length > 4000) throw Error('Invalid teacher question');
    const row = { id: randomUUID(), lane, kind, question: question.trim(), references: this.references(lane, references), status: 'open', createdAt: new Date().toISOString() };
    const path = join(this.directory, 'questions', `${row.id}.json`);
    await atomicJSON(path, row); await this.log({ type: 'question', label: '需要老师确认', questionId: row.id, lane });
    this.wait(row.id, true);
    try {
      for (;;) {
        this.signal?.throwIfAborted();
        const answer = await readJSON(join(this.directory, 'answers', `${row.id}.json`));
        if (answer) {
          row.status = 'answered'; row.answer = answer.text; row.selections = answer.selections || []; row.documentReferences = answer.references || []; row.answeredAt = new Date().toISOString();
          await atomicJSON(path, row); await this.log({ type: 'answer_received', label: '已收到老师的说明', questionId: row.id, lane });
          return { question: row.question, teacherAnswer: answer.text, selections: answer.selections || [], documentReferences: answer.references || [],
            authority: 'Teacher clarification, recorded separately from the original source and immutable awards. It does not permit invented source rules or changes to already saved grades.' };
        }
        await delay(250, undefined, { signal: this.signal });
      }
    } catch (error) { row.status = 'interrupted'; await atomicJSON(path, row); throw error; }
    finally { this.wait(row.id, false); }
  }
  async beforeRequest(lane) {
    let reported = false;
    try {
    while ((await readJSON(join(this.directory, 'control.json'), {})).paused) {
      this.signal?.throwIfAborted();
      if (!reported) { this.wait(`pause:${lane}`, true); await this.log({ type: 'paused', label: '已暂停，等待继续', lane }); reported = true; }
      await delay(250, undefined, { signal: this.signal });
    }
    if (reported) await this.log({ type: 'resumed', label: '继续处理', lane });
    } finally { this.wait(`pause:${lane}`, false); }
  }
  applies(lane, note) {
    const owner = this.owner(lane);
    if (!owner) { const targets = [...(note.selections || []), ...(note.references || []).map(ref => ref.target)]; return targets.length > 0 && targets.every(target => ['scheme', 'question'].includes(target.role)); }
    return !note.groupIds?.length || note.groupIds.includes(owner);
  }
  noteContext(lane, note) {
    const allowed = new Set([...this.schemePages, ...this.questionPages, ...(this.students.get(this.owner(lane)) || [])].map(page => page.workspace_page_id || page.id));
    return { teacher: note.text, sourceSelections: (note.selections || []).filter(target => allowed.has(target.pageId)),
      documentReferences: (note.references || []).filter(ref => ref.target.kind === 'text' ? ref.target.sourcePageIds.every(id => allowed.has(id)) : allowed.has(ref.target.pageId)), applyTo: note.groupIds || [] };
  }
  attach(agent, lane, { interactiveTools = true, singlePass = false } = {}) {
    this.agents.set(agent, lane);
    this.singlePassAgents ||= new WeakSet();
    if(singlePass)this.singlePassAgents.add(agent);else this.singlePassAgents.delete(agent);
    if (lane === 'main' && interactiveTools) {
      const gated = new Set(['prepare_grading_plan', 'freeze_grading_plan', 'publish_marking_guide', 'grade_students']);
      agent.state.tools = agent.state.tools.map(tool => !gated.has(tool.name) ? tool : { ...tool,
        execute: async (...args) => { await this.requireCompatibleRequirements(); return tool.execute(...args); } });
      let deliveredRequirements = null;
      agent.state.tools.push({ name: 'review_grading_requirements', label: '核对补充批改要求', executionMode: 'sequential',
        description: 'After reading relevant sources, assess optional teacher requirements. Compatible requests proceed without asking. For conflicting, unclear, unsupported or unfair requirements, explain the concrete problem and propose an adjustment to the teacher; this tool waits for their actual reply even in automatic mode. Reassess their reply before grading. Never silently discard or rewrite a requirement.',
        parameters: { type: 'object', additionalProperties: false, required: ['decision', 'explanation', 'question', 'adjustedInstructions'], properties: {
          decision: { type: 'string', enum: ['compatible', 'needs_adjustment'] }, explanation: { type: 'string', minLength: 1, maxLength: 2000 },
          question: { type: 'string', maxLength: 1800, description: 'A concrete adjustment question when needed; otherwise empty.' },
          adjustedInstructions: { type: 'string', maxLength: 12000, description: 'Empty for an initial compatible review: original requirements are retained verbatim. Only after a teacher reply, supply the complete agreed supplemental requirements and exam context; empty then means the teacher withdrew them. Never include student answers or personal information.' } } },
        execute: async (_id, input) => {
          const review = await this.reviewRequirements(input);
          const checkpoint = digest(review);
          if (review.status === 'compatible' && deliveredRequirements !== checkpoint) {
            deliveredRequirements = checkpoint;
            // The coordinator retains user checkpoints when compacting its MS compilation transcript.
            agent.steer({ role: 'user', timestamp: Date.now(), content: [{ type: 'text', text: `Host-recorded requirements review ${checkpoint}: compatible. These agreed requirements replace the initial supplemental request; include them in the implementation guide. Original source rules still apply.\n${review.effectiveInstructions || 'No supplemental requirements remain.'}` }] });
          }
          return { content: [{ type: 'text', text: JSON.stringify(review) }], details: {} };
        } });
    }
    const systemPrompt = agent.state.systemPrompt + (singlePass
      ? '\n\nThe teacher-confirmed implementation document and notes are included. This grading pass submits once; unresolved source or handwriting questions must remain null/review with page references so the teacher can address them in the workspace. Do not claim clarification or independent review occurred.'
      : interactiveTools
      ? '\n\nA teacher is collaborating in the workspace. Question papers and MS are optional: their absence alone does not warrant a clarification or a request to supply them. Use the provided work without a materials-completion step. When source meaning, MS conditions, page boundaries or handwriting ambiguity prevents a reliable decision, use ask_teacher with a concise concrete question and the original source page. Wait for their answer; do not claim a teacher has approved anything before a reply. Teacher notes are source clarifications, not authority to invent rules, exceed fixed maxima, expand this lane, or overwrite a submitted grade. Do not expose hidden reasoning; report tool actions and findings concisely.'
      : '\n\nThe teacher implementation document accompanies these frozen grading records. Preserve their evidence and unresolved judgments in the feedback. This stage only submits feedback: it cannot reread source images, ask new grading questions, or change awards. Do not claim those actions occurred.') + (lane === 'main' ? '\nGrading is already the task; never ask what the teacher wants to do. Supplemental requirements are optional. Read the relevant question/MS evidence, then use review_grading_requirements before publishing a guide or dispatching when requirements are present. Apply compatible preferences without extra confirmation. If a preference conflicts with the question, MS, exam system, fair grading, or available capabilities, explain the specific issue and suggest an adjustment through that tool. Do not silently comply, discard, or substitute your preference. Automatic mode never authorizes bypassing an unresolved adjustment. After a reply reassess it, record the agreed requirements, and incorporate them in the grading guide. Preserve original source rules and distinguish explicitly agreed custom evaluation from official marking.' : '');
    if (interactiveTools) agent.state.tools = [...agent.state.tools, { name: 'read_teacher_selection', label: '查看老师圈选', description: 'Read the exact original pixels inside a teacher selection. The source page identity and normalized rectangle are preserved.',
      parameters: { type: 'object', required: ['selectionId'], additionalProperties: false, properties: { selectionId: { type: 'string' } } },
      execute: async (_id, { selectionId }) => {
        const control = await readJSON(join(this.directory, 'control.json'), {});
        const selections = [...(control.notes || []).filter(note => this.applies(lane, note)).flatMap(note => note.selections || []), ...(await readQuestions(this.directory)).filter(row => this.visibleQuestion(lane, row)).flatMap(row => row.selections || [])];
        const selection = selections.find(item => item.id === selectionId);
        const page = [...this.schemePages, ...this.questionPages, ...(this.students.get(this.owner(lane)) || [])].find(page => (page.workspace_page_id || page.id) === selection?.pageId);
        if (!selection || !page) throw Error('Selection outside this agent lane');
        return { content: [{ type: 'text', text: JSON.stringify(selection) }, await readSelectionImage(page, selection)], details: {} };
      } }, { name: 'ask_teacher', label: '请老师确认', description: 'Pause this agent for a teacher clarification about a specific source. Other independent students may continue.',
      parameters: { type: 'object', additionalProperties: false, required: ['question', 'references'], properties: { question: { type: 'string', minLength: 1, maxLength: 4000 }, references: { type: 'array', maxItems: 12, items: { type: 'object', additionalProperties: false, required: ['role', 'page'], properties: { role: { type: 'string', enum: ['scheme', 'question', 'student'] }, page: { type: 'integer', minimum: 1 } } } } } },
      execute: async (_id, input) => ({ content: [{ type: 'text', text: JSON.stringify(await this.ask(lane, input)) }], details: {} }) }];
    agent.state.messages = [createInitialSystemMessage(systemPrompt, agent.state.tools.map(toToolDeclaration)), ...agent.state.messages.filter(message => message.role !== 'system')];
    const queued = new Set();
    this.queued ||= new WeakMap(); this.queued.set(agent, queued);
    const pump = async () => {
      const control = await readJSON(join(this.directory, 'control.json'), {});
      for (const note of control.notes || []) if (!queued.has(note.id) && this.applies(lane, note)) {
        queued.add(note.id);
        agent.steer({ role: 'user', timestamp: Date.now(), content: [{ type: 'text', text: `[teacher-note:${note.id}]\n${JSON.stringify(this.noteContext(lane, note))}` }] });
      }
    };
    let pumping = false;
    const timer = setInterval(async () => { if (pumping) return; pumping = true; try { await pump(); } catch { /* Durable notes remain for the next boundary. */ } finally { pumping = false; } }, 250);
    timer.unref();
    const unsubscribe = agent.subscribe(async event => {
      if (event.type === 'turn_start') await pump();
      if (event.type === 'tool_execution_start' || event.type === 'tool_execution_end') {
        await this.log({ type: event.type, key: event.toolCallId, lane, label: labels[event.toolName] || '处理当前步骤', tool: event.toolName,
          status: event.type === 'tool_execution_start' ? 'running' : event.isError ? 'error' : 'done' });
      }
    });
    return () => { clearInterval(timer); unsubscribe(); };
  }
  async recordDelivery(lane, payload) {
    const text = JSON.stringify(payload.messages);
    const control = await readJSON(join(this.directory, 'control.json'), {});
    for (const note of control.notes || []) if (this.applies(lane, note) && text.includes(`[teacher-note:${note.id}]`)) {
      const key = `${lane}:${note.id}`; this.delivered ||= new Set();
      if (!this.delivered.has(key)) { this.delivered.add(key); await this.log({ type: 'note_delivered', label: '老师的补充已进入本轮上下文', noteId: note.id, lane }); }
    }
  }
  async preparePrompt(agent, prompt) {
    const lane = this.agents.get(agent);
    const answered = (await readQuestions(this.directory)).filter(row => row.status === 'answered' && this.visibleQuestion(lane, row));
    const control = await readJSON(join(this.directory, 'control.json'), {});
    const notes = (control.notes || []).filter(note => this.applies(lane, note));
    const guide = this.guide && lane !== 'ms-review' ? this.guide : null;
    const requirements = await this.requirements();
    const requirementText = lane === 'main' && requirements.original
      ? `Optional teacher requirements (not yet accepted unless the review is compatible):\n${JSON.stringify(requirements)}\nRead the sources and call review_grading_requirements. No extra confirmation is needed for compatible requirements.`
      : requirements.review?.status === 'compatible' && lane !== 'ms-review' ? `Agreed supplemental grading requirements:\n${requirements.review.effectiveInstructions}` : '';
    if (!answered.length && !notes.length && !guide && !requirementText) return prompt;
    for (const note of notes) this.queued?.get(agent)?.add(note.id);
    const original = typeof prompt === 'string' ? { role: 'user', timestamp: Date.now(), content: [{ type: 'text', text: prompt }] } : prompt;
    const teacherContext={ role: 'user', timestamp: Date.now(), content: [{ type: 'text', text: `${requirementText}\nRecorded teacher source clarifications (original source and fixed award bounds still apply):\n${JSON.stringify(answered.map(row => ({ question: row.question, answer: row.answer, references: row.references, selections: row.selections, documentReferences: row.documentReferences })))}\n${notes.map(note => `[teacher-note:${note.id}]\n${JSON.stringify(this.noteContext(lane, note))}`).join('\n')}${guide ? `\n${guide.method === 'automatic' ? 'Teacher-authorized automatic-mode' : 'Teacher-confirmed'} execution document v${guide.revision}, hash ${guide.hash}:\n${guide.body}\nApply this document. If it conflicts with source meaning or fixed award bounds, retain unresolved judgments for teacher review; never silently override the source.` : ''}` }] };
    const messages=Array.isArray(original)?original:[original];
    return this.singlePassAgents?.has(agent)?[...messages,teacherContext]:[teacherContext,...messages];
  }
}
