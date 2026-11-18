import { pythonExecutable } from '../python.mjs';
import { mkdir, writeFile, readFile, copyFile, rm } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { digest } from '../core.mjs';
import { fail, id } from './store.mjs';

export const experimentRoot = fileURLToPath(new URL('../../', import.meta.url));
export const python = pythonExecutable();
const execute = promisify(execFile);

export async function importUpload(store, { bytes, name, role }) {
  fail(['student', 'scheme', 'question'].includes(role), '材料类别无效。');
  fail(bytes.length > 0 && bytes.length <= 40 * 1024 * 1024, '单个文件最多 40 MB。');
  const uploadId = id(), directory = join(store.directory, 'uploads', uploadId);
  await mkdir(directory, { recursive: true });
  const source = join(directory, 'source');
  await writeFile(source, bytes, { mode: 0o600 });
  try {
    await execute(python, [join(experimentRoot, 'scripts/python/workspace_documents.py'), '--source', source, '--output', directory], {
      timeout: 120000, maxBuffer: 1024 * 1024, env: { PATH: process.env.PATH },
    });
    const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
    const fileName = String(name || '上传材料').replace(/[\x00-\x1f]/g, '').slice(0, 180);
    const pages = manifest.pages.map(page => ({
      id: id(), sourceId: uploadId, fileName, sourcePage: page.page, role,
      sha256: page.sha256, path: join(directory, page.path), active: true,
      size: page.size, imageToPdf: page.image_to_pdf, imageRepresentation: page.representation,
    }));
    await store.mutate(null, state => {
      fail(state.pages.length + pages.length <= 1500, '此实验工作区最多保存 1500 页。');
      state.pages.push(...pages);
      if (role === 'student') state.groups.push({ id: id(), label: fileName.replace(/\.[^.]+$/, ''), pageIds: pages.map(page => page.id) });
      else (role === 'question' ? state.questions : state.schemes).push({ id: uploadId, label: fileName, pageIds: pages.map(page => page.id), sha256: manifest.sha256 });
      state.materialRevision++;
      if (state.title === '新的作业') state.title = fileName.replace(/\.[^.]+$/, '').slice(0, 80);
    });
    return { pages: pages.length };
  } catch (error) {
    await rm(directory, { recursive: true, force: true });
    if (error.status) throw error;
    throw Object.assign(new Error('无法读取材料。请上传未加密的 PDF、PNG 或 JPEG（每文件最多 300 页）。'), { status: 422 });
  }
}

export async function prepareTaskInput(store, task) {
  const directory = join(store.directory, 'runs', task.id);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, 'task.json'), JSON.stringify(task, null, 2), { flag: 'wx', mode: 0o600 });
  const prepare = async (name, role, pageIds, sourceHash = null) => {
    const destination = join(directory, 'input', name);
    await mkdir(destination, { recursive: true });
    const pages = [];
    for (const [index, pageId] of pageIds.entries()) {
      const page = task.pages.find(item => item.id === pageId);
      fail(page, '材料快照缺少页面。');
      const bytes = await readFile(page.path);
      fail(digest(bytes) === page.sha256, '原始材料已改变，停止执行。');
      const path = `page-${index + 1}.png`;
      await copyFile(page.path, join(destination, path));
      pages.push({ page: index + 1, path, sha256: page.sha256, source_id: page.sourceId, source_page: page.sourcePage, workspace_page_id: page.id,
        ...(page.size?{size:page.size}:{}),...(page.imageToPdf?{image_to_pdf:page.imageToPdf}:{}),...(page.imageRepresentation?{representation:page.imageRepresentation}:{}) });
    }
    await writeFile(join(destination, 'manifest.json'), JSON.stringify({
      version: 1, long_side: Math.max(...pages.map(page=>page.size?Math.max(...page.size):1400)),
      documents: { [role]: { sha256: sourceHash || digest(pages.map(page => [page.source_id, page.source_page, page.sha256])), pages } },
    }));
    return destination;
  };
  const verifySource = async (document, label) => {
    if (!document?.sha256) return null;
    const sourceDirectory = join(store.directory, 'uploads', document.id);
    const original = await readFile(join(sourceDirectory, 'source'));
    const manifest = JSON.parse(await readFile(join(sourceDirectory, 'manifest.json'), 'utf8'));
    fail(digest(original) === document.sha256 && manifest.sha256 === document.sha256, `${label}原件已改变，停止执行。`);
    fail(manifest.pages.length === document.pageIds.length && document.pageIds.every((id, index) => {
      const page = task.pages.find(row => row.id === id), originalPage = manifest.pages[index];
      return page?.sourceId === document.id && page.sourcePage === originalPage.page && page.sha256 === originalPage.sha256;
    }), `${label}页序或页面内容与原件不一致。`);
    return document.sha256;
  };
  const scheme = task.scheme ? await prepare('scheme', 'scheme', task.scheme.pageIds, await verifySource(task.scheme, '评分标准')) : null;
  const question = task.question ? await prepare('question', 'question', task.question.pageIds, await verifySource(task.question, '题目')) : null;
  const students = [];
  for (const group of task.groups) students.push({ id: group.id, input: await prepare(group.id, 'student', group.pageIds) });
  const manifest = join(directory, 'cohort.json');
  await writeFile(manifest, JSON.stringify({ scheme_input: scheme, question_input: question, students }, null, 2));
  return { directory, manifest, output: join(directory, 'output') };
}
