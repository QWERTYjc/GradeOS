import { helperEnvironment } from '../python.mjs';
import { readFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { join } from 'node:path';
import { digest } from '../core.mjs';
import { fail, id } from './store.mjs';

export function validateSelections(state, selections = [], groupIds = state.groups.map(group => group.id)) {
  fail(Array.isArray(selections) && selections.length <= 8, '一次最多引用 8 处圈选。');
  const allowed = new Set(state.groups.filter(group => groupIds.includes(group.id)).flatMap(group => group.pageIds));
  for (const source of [...state.schemes, ...(state.questions || [])]) for (const pageId of source.pageIds) allowed.add(pageId);
  return selections.map(selection => {
    const page = state.pages.find(page => page.id === selection.pageId);
    fail(page && allowed.has(page.id), '圈选页面不在当前材料范围内。');
    fail(selection.pageHash === page.sha256, '原页已改变，请重新圈选。', 409);
    const { x, y, width, height } = selection.rect || {};
    fail([x, y, width, height].every(Number.isFinite) && x >= 0 && y >= 0 && width >= 0.002 && height >= 0.002
      && x + width <= 1.000001 && y + height <= 1.000001, '圈选区域无效。');
    const points = selection.shape === 'lasso' ? selection.points : [];
    fail(Array.isArray(points) && points.length <= 512 && (selection.shape !== 'lasso' || points.length >= 3)
      && points.every(point => Array.isArray(point) && point.length === 2 && point.every(value => Number.isFinite(value) && value >= 0 && value <= 1)), '圈选路径无效。');
    fail(points.every(([px, py]) => px >= x - .000001 && px <= x + width + .000001 && py >= y - .000001 && py <= y + height + .000001), '圈选路径与引用区域不一致。');
    return { id: id(), pageId: page.id, pageHash: page.sha256, fileName: page.fileName, sourcePage: page.sourcePage,
      role: page.role, shape: selection.shape === 'lasso' ? 'lasso' : 'rectangle', rect: { x, y, width, height }, points };
  });
}

export async function readSelectionImage(page, selection, maxSide) {
  const { experimentRoot, python } = await import('./documents.mjs');
  const path = page.absolute_path || page.path;
  const bytes = await readFile(path);
  fail(digest(bytes) === selection.pageHash, '圈选原页哈希不一致。');
  const { stdout } = await promisify(execFile)(python, [join(experimentRoot, 'workspace_crop.py'),
    path, JSON.stringify(selection.rect), ...(maxSide ? [String(maxSide)] : [])], { maxBuffer: 6 * 1024 * 1024, timeout: 10000, env: helperEnvironment() });
  return { type: 'image', mimeType: 'image/png', data: stdout.trim() };
}
