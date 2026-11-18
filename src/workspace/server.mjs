import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { timingSafeEqual, randomBytes } from 'node:crypto';
import { WorkspaceStore, fail, replacePartition, taskDraft, saveReview, publicState, executionMode } from './store.mjs';
import { importUpload, experimentRoot } from './documents.mjs';
import { runWorkspaceAgent } from './agent.mjs';
import { SystemService } from './system-service.mjs';
import { WorkspaceRunner } from './runner.mjs';
import { WorkspaceChat } from './chat.mjs';
import { addDocument, readDocument, saveDocument, addAnnotation, updateAnnotation } from './editable-documents.mjs';
import { exportAnnotatedPdf } from './annotation-export.mjs';
import { DEFAULT_MAIN_MODEL_ID } from '../experiment-models.mjs';
import {gradingResult,resultMarkdown} from '../../web/grading-result.mjs';

const mime = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf' };
const readBody = async (req, limit) => {
  const chunks = []; let size = 0;
  for await (const chunk of req) { size += chunk.length; fail(size <= limit, '文件或请求过大。', 413); chunks.push(chunk); }
  return Buffer.concat(chunks);
};
export async function createWorkspaceServer({ directory, port = 4173, model = DEFAULT_MAIN_MODEL_ID, cap = 2, rubricPath = null, agent = runWorkspaceAgent, systemAgent, configured = () => Boolean(process.env.OPENROUTER_API_KEY) } = {}) {
  const store = await new WorkspaceStore(directory || join(experimentRoot, '.workspace')).init();
  const runner = new WorkspaceRunner(store, { model, cap, agent, rubricPath });
  const chat = new WorkspaceChat(store, { agent, model, configured });
  const system = await new SystemService(store, { model, cap, configured, agent: systemAgent }).init();
  const token = randomBytes(32).toString('hex');
  let planning = false;
  const state = () => publicState(store.snapshot(), configured(), { planning: planning || Boolean(chat.active), chat: chat.snapshot(),
    liveTasks: Object.fromEntries([...runner.active].map(([id, entry]) => [id, { events: entry.events?.slice(-120) || [] }])), runBudgetUsd: cap, researchAvailable: Boolean(process.env.BRAVE_SEARCH_API_KEY) });
  const send = (res, status, data) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(data)); };
  const server = createServer(async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; font-src 'self'; connect-src 'self'; frame-src 'self' blob:; frame-ancestors 'self'; base-uri 'none'; form-action 'self'");
    try {
      const address = server.address();
      const actualPort = typeof address === 'object' ? address.port : port;
      const allowedHosts = [`127.0.0.1:${actualPort}`, `localhost:${actualPort}`];
      fail(allowedHosts.includes(req.headers.host), '主机无效。', 403);
      fail(!req.headers['sec-fetch-site'] || ['same-origin', 'none'].includes(req.headers['sec-fetch-site']), '请从本地工作区打开。', 403);
      const url = new URL(req.url, `http://${req.headers.host}`);
      if(req.method==='GET'&&url.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}
      if (!['GET', 'HEAD'].includes(req.method)) {
        const submitted = Buffer.from(String(req.headers['x-workspace-token'] || ''));
        fail(submitted.length === token.length && timingSafeEqual(submitted, Buffer.from(token)), '请刷新工作区后重试。', 403);
        fail(!req.headers.origin || req.headers.origin === `http://${req.headers.host}`, '来源无效。', 403);
      }
      if (url.pathname.startsWith('/api/system/')) {
        const body = ['GET', 'HEAD'].includes(req.method) ? null : JSON.parse((await readBody(req, 3 * 1024 * 1024)).toString() || '{}');
        return await system.route({ req, url, body, send, res });
      }
      if (req.method === 'GET' && /^\/api\/tasks\/[^/]+\/result\.md$/.test(url.pathname)) {
        const snapshot=store.snapshot(),result=gradingResult(snapshot,url.pathname.split('/')[3],url.searchParams.get('groupId'));
        fail(result,'这份答卷还没有可导出的评分结果。',404);
        const body=resultMarkdown(result,snapshot.pages);
        res.writeHead(200,{'Content-Type':'text/markdown; charset=utf-8','Content-Disposition':`attachment; filename*=UTF-8''${encodeURIComponent('评分结果.md')}`});res.end(body);return;
      }
      if (req.method === 'GET' && url.pathname === '/api/state') return send(res, 200, { ...state(), token });
      if(req.method==='GET'&&/^\/api\/tasks\/[\w-]+\/annotated\.pdf$/.test(url.pathname)) {
        const result=await exportAnnotatedPdf(store,url.pathname.split('/')[3],url.searchParams.get('groupId'));
        res.writeHead(200,{'Content-Type':'application/pdf','Content-Disposition':`${url.searchParams.has('download')?'attachment':'inline'}; filename*=UTF-8''${encodeURIComponent(result.name)}`});
        return res.end(result.bytes);
      }
      if (req.method === 'GET' && /^\/api\/documents\/[\w-]+$/.test(url.pathname)) {
        const document = readDocument(store.state, url.pathname.split('/').at(-1), url.searchParams.has('revision') ? Number(url.searchParams.get('revision')) : null);
        if (url.searchParams.has('download')) {
          res.writeHead(200, { 'Content-Type': 'text/markdown; charset=utf-8', 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(document.title.endsWith('.md') ? document.title : document.title + '.md')}` });
          return res.end(document.body);
        }
        return send(res, 200, document);
      }
      if (req.method === 'GET' && /^\/api\/pages\/[\w-]+$/.test(url.pathname)) {
        const page = store.state.pages.find(item => item.id === url.pathname.split('/').at(-1));
        fail(page, '页面不存在。', 404);
        const bytes = await readFile(page.path);
        res.writeHead(200, { 'Content-Type': 'image/png' }); return res.end(bytes);
      }
      if (req.method === 'POST' && url.pathname === '/api/uploads') {
        const bytes = await readBody(req, 40 * 1024 * 1024);
        await importUpload(store, { bytes, role: url.searchParams.get('role'), name: url.searchParams.get('name') });
        return send(res, 201, state());
      }
      if (url.pathname.startsWith('/api/') && req.method !== 'GET') {
        const body = JSON.parse((await readBody(req, 512 * 1024)).toString() || '{}');
        if (req.method === 'POST' && url.pathname === '/api/documents') {
          const document = await store.mutate(null, snapshot => {
            if (body.artifactId) {
              const task = snapshot.tasks.find(row => row.id === body.taskId), artifact = task?.artifacts.find(row => row.id === body.artifactId);
              fail(artifact && typeof artifact.body === 'string', '此成果不是可编辑文本。');
              const existing = snapshot.documents.find(row => row.artifactId === artifact.id && row.taskId === task.id);
              if (existing) return readDocument(snapshot, existing.id);
              const added = addDocument(snapshot, { title: artifact.title, body: artifact.body, taskId: task.id,
                sourcePageIds: [...task.groups.flatMap(group => group.pageIds), ...(task.scheme?.pageIds || []), ...(task.question?.pageIds || [])] }, 'agent');
              snapshot.documents.find(row => row.id === added.id).artifactId = artifact.id; return added;
            }
            const scheme = body.schemeId ? snapshot.schemes.find(row => row.id === body.schemeId) : null;
            fail(!body.schemeId || scheme, '评分标准不存在。');
            return addDocument(snapshot, { title: body.title, body: body.body, kind: scheme ? 'marking_guide' : 'document', schemeId: scheme?.id, sourcePageIds: scheme?.pageIds || [] });
          });
          return send(res, 201, { ...state(), document });
        } else if (req.method === 'PATCH' && /^\/api\/documents\/[\w-]+$/.test(url.pathname)) {
          const document = await store.mutate(null, snapshot => saveDocument(snapshot, url.pathname.split('/').at(-1), body));
          return send(res, 200, { ...state(), document });
        } else if (req.method === 'POST' && /^\/api\/documents\/[\w-]+\/approve$/.test(url.pathname)) {
          fail(!chat.active, 'Agent 仍在调整文档，请等本轮完成后确认。', 409);
          await runner.approveGuide(url.pathname.split('/')[3], body);
        } else if (req.method === 'POST' && url.pathname === '/api/annotations') {
          const annotation = await store.mutate(null, snapshot => addAnnotation(snapshot, body));
          return send(res, 201, { ...state(), annotation });
        } else if (req.method === 'PATCH' && /^\/api\/annotations\/[\w-]+$/.test(url.pathname)) {
          const annotation = await store.mutate(null, snapshot => updateAnnotation(snapshot, url.pathname.split('/').at(-1), body));
          return send(res, 200, { ...state(), annotation });
        } else if (req.method === 'POST' && url.pathname === '/api/chat') {
          fail(!planning, 'Agent 正在处理上一条要求。', 409);
          await chat.start(body);
        } else if (req.method === 'POST' && url.pathname === '/api/chat/cancel') {
          chat.cancel();
        } else if (req.method === 'POST' && /^\/api\/tasks\/[\w-]+\/(pause|resume|note|answer)$/.test(url.pathname)) {
          await runner.control(url.pathname.split('/')[3], url.pathname.split('/')[4], body);
        } else if (req.method === 'PATCH' && url.pathname === '/api/materials') {
          await store.mutate(body.revision, snapshot => replacePartition(snapshot, body.groups));
        } else if (req.method === 'PATCH' && url.pathname === '/api/execution-mode') {
          await store.mutate(body.revision, snapshot => { snapshot.executionMode = executionMode(body.mode); });
        } else if (req.method === 'PATCH' && url.pathname === '/api/project') {
          await store.mutate(body.revision, snapshot => {
            fail(typeof body.title === 'string' && body.title.trim().length > 0 && body.title.length <= 80, '请输入作业名称（最多 80 字）。'); snapshot.title = body.title.trim();
          });
        } else if (req.method === 'POST' && url.pathname === '/api/tasks') {
          const createdTaskId = await store.mutate(body.revision, snapshot => {
            const task = taskDraft(snapshot, body); snapshot.tasks.push(task); return task.id;
          });
          return send(res, 200, { ...state(), createdTaskId });
        } else if (req.method === 'PATCH' && /^\/api\/tasks\/[\w-]+$/.test(url.pathname)) {
          await store.mutate(body.revision, snapshot => {
            const existing = snapshot.tasks.find(task => task.id === url.pathname.split('/').at(-1));
            fail(existing?.status === 'draft', '只能修改尚未开始的任务。', 409);
            const updated = taskDraft(snapshot, body);
            Object.assign(existing, updated, { id: existing.id, createdAt: existing.createdAt });
          });
        } else if (req.method === 'POST' && /^\/api\/tasks\/[\w-]+\/start$/.test(url.pathname)) {
          await runner.start(url.pathname.split('/')[3], body.revision);
        } else if (req.method === 'POST' && /^\/api\/tasks\/[\w-]+\/cancel$/.test(url.pathname)) {
          runner.cancel(url.pathname.split('/')[3]);
        } else if (req.method === 'POST' && url.pathname === '/api/reviews') {
          await store.mutate(body.revision, snapshot => saveReview(snapshot, body));
        } else if (req.method === 'POST' && /^\/api\/tasks\/[\w-]+\/review-complete$/.test(url.pathname)) {
          await store.mutate(body.revision, snapshot => {
            const task = snapshot.tasks.find(row => row.id === url.pathname.split('/')[3]);
            fail(task?.status === 'needs_review', '任务当前不处于待审阅状态。', 409);
            const pending = task.records.filter(record => record.reviewRequired).filter(record => {
              const latest = snapshot.reviews.findLast(review => review.recordId === record.id);
              return !latest || (latest.score === null && record.disposition !== 'feedback_only');
            });
            fail(!pending.length, '仍有待定评分，请完成复核后再结束审阅。');
            task.status = 'completed';
          });
        } else if (req.method === 'POST' && url.pathname === '/api/agent') {
          fail(!planning && !chat.active, 'Agent 正在处理上一条要求。', 409);
          fail(typeof body.goal === 'string' && body.goal.trim().length > 0 && body.goal.length <= 8000, '请填写任务要求。');
          const snapshot = store.snapshot();
          fail(body.revision === snapshot.revision, '材料已有更新，请重试。', 409);
          fail(Array.isArray(body.selectedIds) && body.selectedIds.length > 0 && body.selectedIds.every(value => snapshot.groups.some(group => group.id === value)), '请选择任务涉及的答卷。');
          planning = true;
          try {
            const context = snapshot.conversation.filter(message => JSON.stringify(message.selectedIds) === JSON.stringify(body.selectedIds)).slice(-8);
            const record = body.recordId ? snapshot.tasks.flatMap(task => task.records).find(item => item.id === body.recordId && body.selectedIds.includes(item.groupId)) : null;
            fail(!body.recordId || record, '这条评分不属于所选答卷。');
            if (record) {
              const owner = snapshot.tasks.find(task => task.records.some(item => item.id === record.id)).groups.find(group => group.id === record.groupId);
              const selected = snapshot.groups.find(group => group.id === record.groupId);
              fail(JSON.stringify(owner?.pageIds) === JSON.stringify(selected?.pageIds), '答卷划分已改变。请对照这条记录的原页复核，或按当前材料另建任务。', 409);
            }
            const result = await agent({ store, state: snapshot, selectedIds: body.selectedIds,
              goal: `${context.length ? `Previous visible conversation:\n${JSON.stringify(context)}\n` : ''}${record ? `Current review record:\n${JSON.stringify(record)}\n` : ''}${body.goal}`, modelId: model });
            await store.mutate(null, next => {
              fail(snapshot.materialRevision === next.materialRevision, '材料已改变，本次安排未保存，请重新提出要求。', 409);
              for (const draft of result.proposals) next.tasks.push(taskDraft(next, draft));
              next.conversation.push({ role: 'user', text: body.goal, selectedIds: body.selectedIds }, { role: 'assistant', text: result.text, selectedIds: body.selectedIds });
              next.conversation = next.conversation.slice(-40);
            });
            planning = false;
            return send(res, 200, { ...state(), agentReply: result.text });
          } finally { planning = false; }
        } else throw Object.assign(new Error('找不到此操作。'), { status: 404 });
        return send(res, 200, state());
      }
      fail(req.method === 'GET' || req.method === 'HEAD', '方法不支持。', 405);
      const files = new Set(['index.html', 'app.mjs', 'ui.mjs', 'materials.mjs', 'tasks.mjs', 'review.mjs', 'style.css', 'canvas-app.mjs', 'canvas-view.mjs', 'canvas-selection.mjs', 'canvas.css', 'workspace-canvas.mjs', 'document-editor.mjs', 'workspace-canvas.css', 'document-reader.mjs', 'document-reader.css', 'report-math.mjs', 'math-text-parser.mjs', 'results-view.mjs', 'results.css']);
      for (const file of ['system.html', 'system-app.mjs', 'system-view.mjs', 'system.css']) files.add(file);
      const relative = url.pathname === '/' ? 'system.html' : url.pathname === '/grading' ? 'index.html' : url.pathname.slice(1);
      let file;
      if (['grading-annotations.mjs','annotation-layout.mjs','annotation-card.mjs','grading-result.mjs','page-stream.mjs'].includes(relative)) file = join(experimentRoot, 'web', relative);
      else if (relative === 'node_modules/katex/dist/katex.mjs') file = join(experimentRoot, relative);
      else if (files.has(relative)) file = join(experimentRoot, 'web', relative);
      else if (/^assets\/icons\/(down|swap|undo|upload|plus|edit|form|message|left|right|column-width|zoom-in|file-text|close|arrow-up|pause|play|stop|select|history|check|minus)\.svg$/.test(relative)) file = join(experimentRoot, 'web', relative);
      else throw Object.assign(new Error('页面不存在。'), { status: 404 });
      const content = await readFile(file);
      res.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
      res.end(req.method === 'HEAD' ? undefined : content);
    } catch (error) {
      if (!res.headersSent) send(res, error.status || (error instanceof SyntaxError ? 400 : 500), { error: error.status ? error.message : '请求未完成，请重试。' });
      else res.end();
    }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  try { await runner.recover(); await chat.recover(); await system.store.recover(); }
  catch (error) { await new Promise(resolve => server.close(resolve)); throw error; }
  return { server, store, runner, chat, system, close: async () => { await system.close(); await chat.close(); await runner.close(); await new Promise(resolve => server.close(resolve)); } };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { values } = parseArgs({ options: { port: { type: 'string', default: '4173' }, data: { type: 'string' }, env: { type: 'string' }, rubric: { type: 'string' }, model: { type: 'string', default: DEFAULT_MAIN_MODEL_ID }, cap: { type: 'string', default: '2' } } });
  if (values.env) process.loadEnvFile(resolve(values.env));
  const port = Number(values.port), cap = Number(values.cap);
  fail(Number.isInteger(port) && port >= 0 && port <= 65535 && Number.isFinite(cap) && cap > 0 && cap <= 5, '端口或费用上限无效。');
  const app = await createWorkspaceServer({ port, directory: values.data ? resolve(values.data) : undefined, rubricPath: values.rubric ? resolve(values.rubric) : null, model: values.model, cap });
  console.log(`GradeOS workspace: http://127.0.0.1:${app.server.address().port}`);
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => { await app.close(); process.exit(0); });
}
