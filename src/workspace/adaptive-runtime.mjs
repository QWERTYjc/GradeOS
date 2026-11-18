import { mkdir, appendFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createModels } from '@earendil-works/pi-ai';
import { openrouterProvider } from '@earendil-works/pi-ai/providers/openrouter';
import { createRuntime, freezeJson, readMediumPage } from '../cohort-runtime.mjs';
import { experimentModel, experimentProvider, DEFAULT_WORKER_MODEL_ID } from '../experiment-models.mjs';
import { TeacherInteraction } from '../teacher-interaction.mjs';
import { digest } from '../core.mjs';
import { createGradingResearch } from './grading-research.mjs';
import { createAdaptiveCoordinator, createAdaptiveStudent } from './adaptive-agents.mjs';
import { adaptiveGuideMarkdown } from './adaptive-contract.mjs';
import { createReferenceDeriver, createReferenceReviewer, applyReferenceReview, taskOnlyInput } from './reference-audit.mjs';
import { fail, id, now } from './store.mjs';

export const usesAdaptiveGrading = task => !task.scheme || Boolean(task.question || task.allowWebSearch || task.gradingContext);
const basisLabels = { provided_scheme: '用户提供的 MS', derived_question: '根据题目推导 · 建议评分', answer_context: '依据本份答卷内容 · 建议评分' };
export function adaptiveRecords(task, group, grade, frozen) {
  return grade.items.map(item => {
    const rule = frozen.plan.items.find(row => row.id === item.id);
    const source = { taskId: task.id, groupId: group.id, itemId: item.id, planHash: frozen.hash, gradeHash: digest(grade) };
    return { id: digest(source).slice(0, 24), groupId: group.id, student: group.label, itemId: item.id, pointId: null,
      score: item.score, maximum: item.maxScore, allowedAwards: rule.allowedAwards,
      reason: item.reason, evidence: item.evidence, sourceText: rule.criteria,
      uncertainties: item.uncertainties ?? rule.uncertainties, verdict: item.verdict,
      referenceVerification: rule.referenceVerification, referenceCheck: item.referenceCheck,
      studentPageIds: item.studentPageIds, schemePageIds: rule.sourcePageIds.filter(id => task.scheme?.pageIds.includes(id)),
      questionPageIds: rule.sourcePageIds.filter(id => task.question?.pageIds.includes(id)),
      basis: item.basis, basisLabel: basisLabels[item.basis], disposition: rule.disposition,
      reviewRequired: grade.coverage.status !== 'complete' || item.reviewRequired, originalHash: digest({ ...source, item, rule }) };
  });
}

export function adaptiveReport(group, grade, frozen, references) {
  const lines = [`# ${group.label} · 批改结果`, '', `评分依据：${grade.provisional ? '含推导标准，评分供复核' : '用户提供的 MS'}`,
    grade.totalScore === null ? `整卷总分：未确定。${grade.knownScore === null ? '本次没有可确定的数值评分。' : `已判定项目得分小计：${grade.knownScore}（不代表整卷得分）。`}` : `本次评分：${grade.totalScore} / ${grade.maximum}`,
    `题目覆盖：${grade.coverage.status}。${grade.coverage.reason}`, ''];
  for (const item of grade.items) {
    const rule = frozen.plan.items.find(row => row.id === item.id);
    lines.push(`## ${item.id}`, '', `${basisLabels[item.basis]} · ${item.score ?? '待定 / 定性反馈'}${item.maxScore === null ? '' : ` / ${item.maxScore}`}`,
      '', `答卷依据：${item.evidence || '证据不足'}`, '', item.reason, '', `评分条件：${rule.criteria}`, '',
      ...(item.uncertainties ?? rule.uncertainties).map(note => `- 待核实：${note}`));
  }
  const used = new Set(frozen.plan.items.filter(item => item.groupIds.includes(group.id)).flatMap(item => item.webReferenceIds));
  if (used.size) lines.push('## 检索来源', '', ...[...used].map(id => {
    const ref = references.get(id);
    return `- [${ref.title.replace(/[\[\]]/g, '')}](<${ref.url.replace(/[<>]/g, '')}>) · 读取于 ${ref.readAt}`;
  }));
  return lines.join('\n');
}

export async function runAdaptiveGrading({ store, task, input, entry, runner, models = null }) {
  await mkdir(input.output, { recursive: true });
  const pagesFor = role => task.pages.filter(page => page.role === role);
  const interaction = await new TeacherInteraction(entry.interaction, { signal: entry.controller.signal,
    schemePages: pagesFor('scheme'), questionPages: pagesFor('question'),
    students: new Map(task.groups.map(group => [group.id, group.pageIds.map(id => task.pages.find(page => page.id === id))])) }).init();
  if (!models) { models = createModels(); models.setProvider(openrouterProvider()); }
  const config = task.modelConfig;
  const model = experimentModel(models, config?.mainModel ?? runner.model);
  const workerModel = experimentModel(models, config?.workerModel ?? DEFAULT_WORKER_MODEL_ID);
  const runtime = createRuntime({ models, model, output: input.output, cap: runner.cap, controller: entry.controller,
    maxRequests: 128, deadlineMs: 900000, structuredOutput: false,
    studentCacheNamespace: task.id, provider: experimentProvider(model.id), mainEffort: config?.mainEffort, workerEffort: config?.workerEffort,
    workerModel, workerProvider: experimentProvider(workerModel.id), mediumImages:true, interaction });
  const research = createGradingResearch({ enabled: task.allowWebSearch, signal: entry.controller.signal,
    persist: event => appendFile(join(input.output, 'research.jsonl'), JSON.stringify(event) + '\n', { mode: 0o600 }) });
  const readPage = async page => {
    entry.controller.signal.throwIfAborted();
    return readMediumPage({ absolute_path:page.path, sha256:page.sha256 });
  };
  let collecting = false, candidateNumber = 0, auditNumber = 0, failure = null, coordinator;
  const sync = async () => {
    await runner.syncGuide(task);
    const interactionState = await runner.interactionSnapshot(task.id);
    const previous = store.state.tasks.find(row => row.id === task.id);
    const phase = interactionState.guide?.status === 'awaiting_teacher' ? '请编辑并确认评分实施.md' : coordinator?.getPlan() ? '按已采用的评分依据处理答卷' : '整理批改依据';
    const usage = runtime.totals(runtime.budget.requests);
    if (JSON.stringify(previous.interaction) === JSON.stringify(interactionState) && previous.progress.phase === phase && JSON.stringify(previous.usage) === JSON.stringify(usage)) return;
    await store.mutate(null, state => {
      const row = state.tasks.find(row => row.id === task.id);
      row.interaction = interactionState;
      row.progress.phase = phase;
      row.usage = usage;
      row.progress.settledCostUsd = row.usage.provider_reported_cost_usd;
      row.progress.unknownCostRequests = row.usage.unknown_cost_requests;
    });
  };
  const timer = setInterval(async () => {
    if (collecting) return; collecting = true;
    try { await sync(); } catch { /* A later local projection retries; inference is never retried. */ }
    finally { collecting = false; }
  }, 500);
  const io = await runtime.io('main', () => coordinator?.getPlan() ? 'adaptive_coordination' : 'adaptive_preparation');
  try {
    await freezeJson(input.output, 'adaptive-run.json', { version: 1, taskId: task.id, model: model.id, workerModel: workerModel.id, mainEffort: config?.mainEffort ?? 'low', workerEffort: config?.workerEffort ?? 'low', provider: runtime.provider,
      sourcePages: task.pages.map(({ id, role, sha256 }) => ({ id, role, sha256 })), groupIds: task.groupIds,
      gradingContext: task.gradingContext, teacherGoal: task.goal, supplementalInstructions: task.supplementalInstructions, executionMode: task.executionMode, cap: runner.cap,
      researchAvailable: research.available, labelsInModelContext: false, referenceVerification: 'isolated-task-derivation-and-source-audit-v1' });
    coordinator = createAdaptiveCoordinator({ model, streamFn: io.streamFn, task, readPage, research, signal: entry.controller.signal, log: io.log,
      resolveRequirements: () => interaction.requireCompatibleRequirements(),
      persistCandidate: value => freezeJson(input.output, `candidate-${++candidateNumber}.json`, value),
      verifyPlan: async candidate => {
        fail(auditNumber < 3, '本批标准修订校核次数已达上限；保留具体问题供复核。');
        const number = ++auditNumber;
        const derivationIO = await runtime.io(`reference-derivation-${number}`, () => 'adaptive_reference_derivation', { isolated: true });
        await freezeJson(derivationIO.directory, 'task-only-input.json', taskOnlyInput(candidate));
        const deriver = createReferenceDeriver({ model: workerModel, streamFn: derivationIO.streamFn, candidate, log: derivationIO.log });
        const detachDeriver = derivationIO.attach(deriver.agent);
        try { await runtime.run(deriver.agent, deriver.prompt, derivationIO.directory); }
        finally { detachDeriver(); }
        const derivation = deriver.getResult(); fail(derivation, '独立推导未提交完整结果，不能发布未经核验的数值标准。');
        await freezeJson(derivationIO.directory, 'derivation.json', derivation);
        const reviewIO = await runtime.io(`reference-review-${number}`, () => 'adaptive_reference_review', { isolated: true, useMainModel:Boolean(task.scheme) });
        const reviewer = createReferenceReviewer({ model: task.scheme ? model : workerModel, streamFn: reviewIO.streamFn, candidate, derivation, pages: task.pages, readPage, log: reviewIO.log });
        const detachReviewer = reviewIO.attach(reviewer.agent);
        try { await runtime.run(reviewer.agent, reviewer.prompt, reviewIO.directory); }
        finally { detachReviewer(); }
        const review = reviewer.getResult(); fail(review, '独立标准校核未完成，不能直接采用候选标准。');
        await freezeJson(reviewIO.directory, 'reference-review.json', review);
        const verified = applyReferenceReview(candidate, derivation, review);
        await freezeJson(input.output, `verified-candidate-${number}.json`, verified);
        return verified;
      },
      persistPlan: async (value, sourceReview) => {
        await freezeJson(input.output, 'grading-plan.json', value);
        await freezeJson(input.output, 'plan-review.json', { planHash: value.hash, sourceReview });
      },
      publishGuide: frozen => interaction.publishGuide({ hash: frozen.hash, artifact: { source_sha256: frozen.sourceHash } }, frozen.plan.implementation, { body: adaptiveGuideMarkdown(frozen) }),
      executeStudent: async (groupId, frozen, guide, competencies) => {
        runtime.allocateStudentBudgets(task.groups.map(group=>group.id));
        try {
        const group = task.groups.find(group => group.id === groupId);
        const childIO = await runtime.io(`student-${groupId}`, () => 'adaptive_student');
        const child = createAdaptiveStudent({ model: workerModel, streamFn: childIO.streamFn, task, group, frozen, competencies, readPage, log: childIO.log,
          save: async grade => {
            entry.controller.signal.throwIfAborted();
            await freezeJson(childIO.directory, 'grading.json', grade);
            const body = adaptiveReport(group, grade, frozen, research.references);
            await store.mutate(null, state => {
              entry.controller.signal.throwIfAborted();
              const row = state.tasks.find(row => row.id === task.id);
              row.records.push(...adaptiveRecords(task, group, grade, frozen));
              const artifact = { id: id(), groupId: group.id, title: `${group.label} · 批改结果`, body };
              row.artifacts.push(artifact); row.progress.completed++;
            });
          } });
        const detach = childIO.attach(child.agent);
        try { await runtime.run(child.agent, child.prompt, childIO.directory); }
        finally { detach(); }
        fail(child.getResult(), '本份答卷没有提交完整结果。');
        return { status: 'submitted', reviewRequired: child.getResult().reviewRequired };
        } finally { runtime.finishStudentBudget(groupId); }
      } });
    const detach = io.attach(coordinator.agent);
    try { await runtime.run(coordinator.agent, coordinator.prompt, io.directory); }
    finally { detach(); }
    fail(coordinator.getResult(), '主 Agent 未完成本批处理。');
  } catch (error) { failure = error; }
  finally {
    clearInterval(timer); while (collecting) await new Promise(resolve => setTimeout(resolve, 10));
    runtime.close(); await sync();
    const students = coordinator ? [...coordinator.registry.rows.values()] : [];
    const summary = { status: !failure && students.every(row => row.status === 'submitted') ? 'submitted' : 'incomplete',
      failure: failure?.message || null, students, ...runtime.totals(runtime.budget.requests), research: research.summary() };
    await freezeJson(input.output, 'summary.json', summary);
    await store.mutate(null, state => {
      const row = state.tasks.find(row => row.id === task.id);
      row.status = entry.controller.signal.aborted ? 'cancelled' : summary.status === 'submitted'
        ? (task.after === 'review' || row.records.some(record => record.reviewRequired) ? 'needs_review' : 'completed')
        : row.records.length ? 'partial' : 'failed';
      row.finishedAt = now(); row.usage = runtime.totals(runtime.budget.requests);
      row.progress.phase = summary.status === 'submitted' ? '本批处理完成' : '本批未完整完成';
      row.research = { enabled: task.allowWebSearch, available: research.available, searches: summary.research.searches, reads: summary.research.reads };
      if (summary.status !== 'submitted') row.error = '部分处理未完成；已保存的评分、定性反馈和待定项均保留。';
    });
  }
}
