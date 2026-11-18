import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { promisify } from 'node:util';
import { digest } from './core.mjs';
import { freezeJson } from './cohort-runtime.mjs';
import { buildOCRRegionCatalog } from './ocr-regions.mjs';
import { pythonExecutable, projectRoot } from './python.mjs';

const run = promisify(execFile);
const read = async path => JSON.parse(await readFile(path, 'utf8'));

export async function prepareAnnotationPages({ students, output, maxSide }) {
  const sourcePath = join(output, 'local-observation-input.json');
  const observedPath = join(output, 'student-local-observations.json');
  const refinedPath = join(output, 'student-region-observations.json');
  const catalogPath = join(output, 'student-ocr-regions.json');
  const variantPath = join(output, 'student-image-variants');
  const pages = [...students.values()].reduce((n, doc) => n + doc.pages.length, 0);
  const options = { env: { PATH: process.env.PATH }, timeout: Math.max(120000, pages * 90000), maxBuffer: 1024 * 1024 };
  const python = (script, ...args) => run(pythonExecutable(), [join(projectRoot, 'scripts/python', script), ...args], options);
  await freezeJson(output, 'local-observation-input.json', Object.fromEntries(students));
  try {
    if (process.platform === 'darwin') {
      await run('xcrun', ['swift', join(projectRoot, 'scripts/macos/student_ocr.swift'), sourcePath, observedPath], options);
    } else {
      await python('local_text_regions.py', sourcePath, observedPath);
    }
  } catch (error) {
    // Keep the original page inventory even when no local engine is installed.
    const documents = Object.fromEntries([...students].map(([id, doc]) => [id, {source_sha256: doc.sha256,
      pages: doc.pages.map(page => ({page: page.page, source_sha256: page.sha256, rows: []}))}]));
    await freezeJson(output, 'ocr-status.json', {status:'unavailable', reason:error.code || 'engine_failed'});
    await freezeJson(output, 'student-local-observations.json', {engine:'unavailable', network_requests:0, documents});
  }
  const raw = await read(observedPath);
  // Reject stale or foreign artifacts before attempting local ink refinement.
  buildOCRRegionCatalog(raw, students);
  let observations = raw;
  if (raw.engine !== 'unavailable') {
    await python('student_region_geometry.py', '--documents', sourcePath, '--observations', observedPath, '--output', refinedPath);
    observations = await read(refinedPath);
  }
  const catalog = buildOCRRegionCatalog(observations, students);
  await freezeJson(output, 'student-ocr-regions.json', catalog);
  await python('student_region_images.py', '--documents', sourcePath, '--catalog', catalogPath, '--output', variantPath,
    '--max-side', String(maxSide));
  const variants = await read(join(variantPath, 'manifest.json'));
  for (const [id, doc] of students) {
    const variant = variants.documents[id], detected = catalog.documents[id];
    if (variant?.sha256 !== doc.sha256 || variant.pages.length !== doc.pages.length) throw Error('OCR page inventory changed');
    for (const [index, source] of doc.pages.entries()) {
      const page = variant.pages[index], binding = detected.pages[index];
      if (page.page !== source.page || page.original_sha256 !== source.sha256 || page.region_manifest_sha256 !== detected.manifest_sha256
        || digest(page.regions) !== digest(binding.regions) || !page.source_coverage_verified
        || !page.absolute_path.startsWith(variantPath + sep) || digest(await readFile(page.absolute_path)) !== page.sha256)
        throw Error('OCR delivery does not match its source catalog');
    }
  }
  return { observations, catalog, variants };
}
