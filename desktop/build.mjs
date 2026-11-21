import { packager } from '@electron/packager';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { copyFile, mkdir, mkdtemp, readFile, readdir, rename, rm, symlink, writeFile } from 'node:fs/promises';
import { dirname, extname, join, resolve } from 'node:path';

const here = import.meta.dirname, root = resolve(here, '..');
const target = process.argv[2] || `${process.platform}-${process.arch}`;
if (!['darwin-arm64', 'darwin-x64', 'win32-x64', 'source'].includes(target)) {
  throw Error('Choose darwin-arm64, darwin-x64, win32-x64 or source.');
}
const [platform, arch] = target.split('-');
if (platform === 'darwin' && process.platform !== 'darwin') throw Error('Build macOS disk images on macOS.');
const runs = join(root, 'runs');
await mkdir(runs, { recursive: true });
const work = await mkdtemp(join(runs, 'desktop-build-'));
const cache = resolve(process.env.GRADEOS_BUILD_CACHE || join(runs, 'desktop-downloads'));
const stage = join(work, 'source'), runtime = join(work, 'runtime');
const output = join(root, 'dist', 'desktop');
const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
const version = manifest.version;
const buildPython = process.env.GRADEOS_BUILD_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

function run(command, args, cwd = root) {
  execFileSync(command, args, { cwd, stdio: 'inherit', windowsHide: true });
}

// Build from an allowlist. Workspaces, evaluations, environment files and Git history
// may all be present next to the sources and must never enter a teacher's installer.
async function copySources(dir, extensions) {
  const visit = async relative => {
    await mkdir(join(stage, relative), { recursive: true });
    for (const entry of await readdir(join(root, relative), { withFileTypes: true })) {
      if (entry.name.startsWith('.')) continue;
      const child = join(relative, entry.name);
      if (entry.isDirectory()) await visit(child);
      else if (entry.isFile() && (extensions.includes(extname(entry.name)) || entry.name === 'LICENSE')) {
        await copyFile(join(root, child), join(stage, child));
      }
    }
  };
  await visit(dir);
}

await mkdir(stage);
await copySources('src', ['.mjs']);
await copySources('web', ['.mjs', '.html', '.css', '.svg', '.woff', '.woff2', '.ttf']);
await copyFile(join(root, 'web/assets/brand/google-g.png'), join(stage, 'web/assets/brand/google-g.png'));
await copySources('THIRD_PARTY_LICENSES', ['.txt']);
await mkdir(join(stage, 'desktop'));
for (const file of ['package.json', 'package-lock.json', 'uv.lock', 'pyproject.toml', 'LICENSE',
  'desktop/main.mjs', 'desktop/service.mjs', 'analytics.py', 'gradeos_analysis.py', 'annotation_pdf.py',
  'annotation_space.py', 'native_pages.py', 'prepare.py', 'student_images.py', 'workspace_crop.py',
  'workspace_documents.py', 'student_ocr.swift']) {
  await copyFile(join(root, file), join(stage, file));
}
if (target === 'source') {
  for (const file of ['build.mjs', 'runtime.py', 'installer.nsi', 'fonts.conf', 'smoke.mjs', 'README.md',
    'package.json', 'package-lock.json', 'poppler.lock.json', 'icons/GradeOS.ico', 'icons/GradeOS.icns']) {
    const dest = join(stage, 'desktop', file);
    await mkdir(dirname(dest), { recursive: true });
    await copyFile(join(here, file), dest);
  }
  await copyFile(join(here, 'README.md'), join(stage, 'README.md'));
  await mkdir(join(stage, '.github', 'workflows'), { recursive: true });
  await copyFile(join(root, '.github/workflows/desktop.yml'), join(stage, '.github/workflows/desktop.yml'));
  const name = `GradeOS-${version}-source.zip`;
  run(buildPython, ['-m', 'zipfile', '-c', join(work, name), 'source'], work);
  await finish(name);
  process.exit(0);
}
const deps = ['ci', '--omit=dev', '--ignore-scripts', '--no-fund', '--no-audit', `--os=${platform}`, `--cpu=${arch}`];
// npm exposes its JS entrypoint when invoked through npm run, including on Windows.
if (process.env.npm_execpath) run(process.execPath, [process.env.npm_execpath, ...deps], stage);
else if (process.platform === 'win32') run('cmd.exe', ['/d', '/c', 'npm', ...deps], stage);
else run('npm', deps, stage);
await writeFile(join(stage, 'package.json'), JSON.stringify({ ...manifest, main: 'desktop/main.mjs', productName: 'GradeOS' }, null, 2));
run(buildPython, [join(here, 'runtime.py'), target, runtime, cache]);

const { config } = JSON.parse(await readFile(join(here, 'package.json'), 'utf8'));
const [packed] = await packager({
  name: 'GradeOS', dir: stage, out: join(work, 'packed'), tmpdir: join(work, 'packager-temp'),
  platform, arch, electronVersion: config.electronVersion,
  electronZipDir: cache, appVersion: version, appBundleId: 'org.gradeos.desktop',
  appCategoryType: 'public.app-category.education', icon: join(here, 'icons', 'GradeOS'),
  win32metadata: { CompanyName: 'GradeOS', FileDescription: 'GradeOS 教师工作台', ProductName: 'GradeOS' },
  asar: false, prune: false, ignore: path => path.includes('/node_modules/.bin'),
});
const contents = platform === 'darwin' ? join(packed, 'GradeOS.app', 'Contents', 'Resources') : join(packed, 'resources');
// Moving the runtime preserves CPython and Poppler's relative library symlinks.
await rename(runtime, join(contents, 'runtime'));
await rm(stage, { recursive: true, force: true });
const lock = await readFile(join(root, 'package-lock.json'));
if (!(await readFile(join(contents, 'app', 'package-lock.json'))).equals(lock)) throw Error('Packaged runtime is missing its grading provenance.');
const filename = `GradeOS-${version}-${platform === 'darwin' ? 'macOS-' + arch + '.dmg' : 'Windows-x64-Setup.exe'}`;
const product = join(work, filename);
if (platform === 'darwin') {
  const imageFolder = join(work, 'disk-image');
  await mkdir(imageFolder);
  const app = join(imageFolder, 'GradeOS.app');
  await rename(join(packed, 'GradeOS.app'), app);
  run('codesign', ['--force', '--deep', '--sign', '-', app]);
  run('codesign', ['--verify', '--deep', '--strict', app]);
  await symlink('/Applications', join(imageFolder, 'Applications'));
  run('hdiutil', ['create', '-quiet', '-format', 'UDZO', '-fs', 'HFS+', '-volname', 'GradeOS',
    '-srcfolder', imageFolder, product]);
  run('hdiutil', ['verify', '-quiet', product]);
} else {
  const flag = process.platform === 'win32' ? '/' : '-';
  run('makensis', [flag + 'V2', flag + 'DAPP=' + packed, flag + 'DOUTPUT=' + product,
    flag + 'DVERSION=' + version, join(here, 'installer.nsi')]);
}
await finish(filename);

async function finish(filename) {
  const product = join(work, filename), hash = createHash('sha256');
  for await (const bytes of createReadStream(product)) hash.update(bytes);
  await mkdir(output, { recursive: true });
  await rename(product, join(output, filename));
  await writeFile(join(output, filename + '.sha256'), `${hash.digest('hex')}  ${filename}\n`);
  await rm(work, { recursive: true, force: true });
  console.log(join(output, filename));
}
