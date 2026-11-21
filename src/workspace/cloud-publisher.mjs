import { readFile, writeFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { digest } from '../core.mjs';
import { fail } from './store.mjs';
import { cloudRequest } from './cloud-account.mjs';
import { gradingResult } from '../../web/grading-result.mjs';

const releasable = (task) =>
  task?.kind === 'grade' && ['completed', 'needs_review'].includes(task.status) && task.records?.length;
export function releasePayload(state, taskId, input) {
  const task = state.tasks.find((row) => row.id === taskId);
  fail(releasable(task), '请选择已有完整批改记录的批次。', 409);
  fail(
    typeof input.title === 'string' && input.title.trim() && input.title.trim().length <= 120,
    '请填写考试名称。',
  );
  fail(
    typeof input.date === 'string' &&
      /^\d{4}-\d{2}-\d{2}$/.test(input.date) &&
      Number.isFinite(Date.parse(input.date)) &&
      new Date(input.date).toISOString().slice(0, 10) === input.date,
    '考试日期无效。',
  );
  fail(Number.isSafeInteger(input.baseVersion) && input.baseVersion >= 0, '版本无效。');
  fail(
    Array.isArray(input.bindings) && input.bindings.length > 0 && input.bindings.length <= 300,
    '请至少选择一份答卷。',
  );
  const paperIds = new Set(),
    students = new Set();
  const papers = input.bindings.map((binding) => {
    const { paperId, studentId, note = '' } = binding;
    fail(
      typeof studentId === 'string' && studentId && !students.has(studentId) && !paperIds.has(paperId),
      '每份答卷和收件学生须一一对应。',
    );
    students.add(studentId);
    paperIds.add(paperId);
    fail(typeof note === 'string' && note.length <= 4000, '学生评语最多 4000 字。');
    const result = gradingResult(state, task.id, paperId);
    fail(result?.rows.length, '答卷或归属已变更，请重新检查。', 409);
    const points = result.rows.map((row) => {
      const status =
        row.disposition === 'feedback_only'
          ? 'feedback'
          : row.pendingReview || !Number.isFinite(row.score)
            ? 'pending'
            : 'scored';
      const source = /^[0-9a-f]{64}$/i.test(row.originalHash || '')
        ? row.originalHash
        : digest([taskId, paperId, row.recordId, row.originalHash ?? null]);
      return {
        source,
        question: String(row.itemId),
        point: String(row.pointId || row.itemId),
        score: status === 'scored' ? row.score : null,
        max: row.disposition === 'feedback_only' ? null : Number.isFinite(row.maximum) ? row.maximum : null,
        state: status,
      };
    });
    return { paperId, studentId, note, points };
  });
  return { schema: 1, baseVersion: input.baseVersion, title: input.title.trim(), date: input.date, papers };
}
function pairing(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    fail(false, '请粘贴教师门户生成的完整配对信息。');
  }
  const code = url.hash.slice(1);
  fail(
    url.pathname === '/' &&
      !url.search &&
      !url.username &&
      !url.password &&
      /^[A-Za-z0-9_-]{32,128}$/.test(code),
    '配对信息格式无效。',
  );
  fail(
    url.protocol === 'https:' ||
      (url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)),
    '云端服务需要 HTTPS。',
  );
  return { url: url.origin, code };
}
async function remote(connection, path, body) {
  let response;
  try {
    response = await fetch(connection.url + '/api/' + path, {
      method: body === undefined ? 'GET' : 'POST',
      redirect: 'error',
      signal: AbortSignal.timeout(18000),
      headers: {
        ...(connection.token ? { Authorization: 'Bearer ' + connection.token } : {}),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    fail(false, '云端连接失败，请检查网络后重试。', 503);
  }
  let data;
  try {
    data = await response.json();
  } catch {
    fail(false, '云端返回了无效响应。', 502);
  }
  fail(response.ok, typeof data?.error === 'string' ? data.error : '云端操作失败。', response.status);
  return data;
}
export class CloudPublisher {
  constructor(store, accounts) {
    this.store = store;
    this.accounts = accounts;
    this.file = join(store.directory, 'cloud-publisher.json');
    this.queue = Promise.resolve();
  }
  route(method, path, body) {
    const result = this.queue.then(() => this.handle(method, path, body));
    this.queue = result.catch(() => {});
    return result;
  }
  async save(data) {
    const temp = this.file + '.' + randomUUID() + '.pending';
    await writeFile(temp, JSON.stringify(data), { mode: 0o600, flag: 'wx' });
    await rename(temp, this.file);
  }
  async handle(method, path, body) {
    let saved;
    try {
      saved = JSON.parse(await readFile(this.file, 'utf8'));
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
      saved = { connection: null, outbox: {} };
    }
    const state = this.store.snapshot(), account = this.accounts?.cloud;
    const conn = account ? account.classConnection : saved.connection;
    const localKey = (id) => digest([conn?.url, conn?.classroom.id, id]);
    if (method === 'GET' && path === 'status') {
      return {
        user: account?.user || null,
        classes: account?.classes || [],
        classroom: conn?.classroom ?? null,
        origin: account?.origin || conn?.url || null,
        tasks: state.tasks
          .filter(releasable)
          .map((t) => ({
            id: t.id,
            title: t.title,
            queued: Boolean(saved.outbox[localKey(t.id)]),
            date: (t.finishedAt || t.completedAt || t.createdAt || '').slice(0, 10),
            groups: t.groups
              .filter((g) => t.records.some((r) => r.groupId === g.id))
              .map((g) => ({ id: g.id, label: g.label })),
          })),
      };
    }
    if (method === 'POST' && path === 'class') {
      fail(account, '请先登录 GradeOS Cloud。', 401);
      await this.accounts.selectClass(body.id);
      return {classroom:this.accounts.cloud.classConnection.classroom};
    }
    if (method === 'POST' && path === 'pair') {
      fail(!account, '请从当前教师账号选择班级。', 409);
      const setup = pairing(body.pairing),
        paired = await remote(setup, 'pair', { code: setup.code });
      fail(
        typeof paired.token === 'string' && typeof paired.classroom?.id === 'string',
        '配对响应无效。',
        502,
      );
      saved.connection = { url: setup.url, token: paired.token, classroom: paired.classroom };
      await this.save(saved);
      return { classroom: paired.classroom };
    }
    fail(conn, '请先连接云端班级。', 409);
    if (account) {
      // Publication also requires the teacher's current session, even if a device token survives longer.
      const roster = await cloudRequest(account, 'classes/' + encodeURIComponent(conn.classroom.id) + '/students');
      if (method === 'GET' && path === 'roster') return {classroom:conn.classroom,students:roster};
      fail(this.accounts.cloud?.session === account.session, '教师账号已变更，请重新选择班级。', 409);
    }
    if (method === 'GET' && path === 'roster') return remote(conn, 'device/roster');
    const [action, id] = path.split('/');
    fail(
      /^[A-Za-z0-9_-]{1,100}$/.test(id || '') && state.tasks.some((t) => t.id === id),
      '批次不存在。',
      404,
    );
    const key = localKey(id),
      target = 'device/exams/' + id;
    if (method === 'GET' && action === 'exam') return remote(conn, target);
    fail(method === 'POST', '不支持此请求。', 405);
    if (action === 'discard') {
      delete saved.outbox[key];
      await this.save(saved);
      return { discarded: true };
    }
    if (action === 'preview' || action === 'publish') {
      const payload = releasePayload(state, id, body);
      const signature = digest([conn.url, conn.classroom.id, payload]);
      if (action === 'preview') return { signature, payload };
      fail(signature === body.signature, '分数、收件人或评语已变更，请重新预览。', 409);
      fail(
        !saved.outbox[key] || digest(saved.outbox[key]) === digest(payload),
        '已有待确认的发布，请先重试或取消。',
        409,
      );
      saved.outbox[key] = payload;
      await this.save(saved);
    } else fail(action === 'retry', '不支持此操作。', 404);
    fail(saved.outbox[key], '没有待重传的发布。', 409);
    const receipt = await remote(conn, target, saved.outbox[key]);
    fail(Number.isSafeInteger(receipt?.version) && receipt.version > 0, '云端回执无效。', 502);
    delete saved.outbox[key];
    await this.save(saved);
    return receipt;
  }
}
