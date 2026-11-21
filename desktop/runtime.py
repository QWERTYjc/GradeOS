"""Assemble a relocatable runtime from upstream, SHA-256-pinned binary distributions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ELECTRON = json.loads((HERE / 'package.json').read_text())['config']['electronVersion']
TARGETS = {
    'darwin-arm64': ('aarch64-apple-darwin', '2f11b8aa3726bdbd87dd9eb76568412faddf4f47e26913fa45d6a2e424972acd',
                     'd080c3b05a01bd16137f2c12ab9ebf083c577757fe846844ba325bafa8e8bdf4'),
    'darwin-x64': ('x86_64-apple-darwin', 'b78a4c479f1964ec484880bee567568266f68da102269fb93a05fe8716b45f91',
                   '1c80d2ccf71b02c8fd9940fd09cafe88090a48c1bab0193c79b597b08d890e79'),
    'win32-x64': ('x86_64-pc-windows-msvc', '355ee61b8207b91574491b1c6dc9b0ebb4408fc56bfafe498f3ef439314b52dc',
                  '2ba6223afa9121f42831fefe92c434334907540165294fc56697449d12e7cfe9'),
}
FONT = 'https://raw.githubusercontent.com/google/fonts/a85815a42757630ce188fdad368c2dfc444d4773/ofl/notosanssc/'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(cache, url, expected):
    path = cache / unquote(urlsplit(url).path.rsplit('/', 1)[1])
    if path.is_file() and digest(path) == expected:
        return path
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as file:
        pending = Path(file.name)
    try:
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location', '--retry', '3',
                        '--max-time', '600', '--output', str(pending), url], check=True)
        if digest(pending) != expected:
            raise ValueError(f'Checksum mismatch: {url}')
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
    return path


def unpack_conda(archive, runtime, windows):
    """Copy only the PDF utilities, their libraries, character maps and upstream notices."""
    label = archive.name.removesuffix('.conda')
    with zipfile.ZipFile(archive) as package:
        for entry in package.namelist():
            if not entry.endswith('.tar.zst'):
                continue
            with package.open(entry) as stream, tarfile.open(fileobj=stream, mode='r|zst') as members:
                for member in members:
                    rel = PurePosixPath(member.name)
                    if rel.is_absolute() or '..' in rel.parts:
                        raise ValueError(f'Invalid archive path: {rel}')
                    name = rel.as_posix().removeprefix('Library/')
                    if name.startswith('info/licenses/'):
                        output = runtime / 'licenses' / label / name.removeprefix('info/licenses/')
                    elif name in ('info/recipe/meta.yaml', 'info/recipe/recipe.yaml', 'info/about.json'):
                        output = runtime / 'licenses' / label / rel.name
                    elif (name.startswith('share/poppler/') or name in ('bin/pdfinfo', 'bin/pdftoppm',
                          'bin/pdfinfo.exe', 'bin/pdftoppm.exe') or
                          (windows and name.startswith('bin/') and name.lower().endswith('.dll')) or
                          (not windows and name.startswith('lib/') and name.endswith('.dylib'))):
                        output = runtime / 'poppler' / name
                    else:
                        continue
                    if member.isdir():
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    if member.issym():
                        # Native library aliases are relative to the real library in the same folder.
                        if Path(member.linkname).name != member.linkname:
                            raise ValueError(f'Unexpected library link: {member.linkname}')
                        output.symlink_to(member.linkname)
                    elif member.isfile():
                        with output.open('wb') as destination:
                            shutil.copyfileobj(members.extractfile(member), destination)
                        output.chmod(member.mode & 0o777)


def assemble(target, runtime, cache):
    runtime.mkdir(parents=True)
    cache.mkdir(parents=True, exist_ok=True)
    triple, python_hash, electron_hash = TARGETS[target]
    windows = target.startswith('win32')
    base = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261110/'
    python_url = base + f'cpython-3.12.16%2B20261110-{triple}-install_only_stripped.tar.gz'
    electron_url = f'https://github.com/electron/electron/releases/download/v{ELECTRON}/electron-v{ELECTRON}-{target}.zip'
    font_url = FONT + 'NotoSansSC%5Bwght%5D.ttf'
    license_url = FONT + 'OFL.txt'
    upstream = {python_url: python_hash, electron_url: electron_hash,
                font_url: 'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da',
                license_url: '1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9'}
    conda = json.loads((HERE / 'poppler.lock.json').read_text())[target]
    pdf_urls = {'https://conda.anaconda.org/conda-forge/' + name: sha for name, sha in conda.items()}
    upstream.update(pdf_urls)
    with ThreadPoolExecutor(8) as workers:
        files = dict(zip(upstream, workers.map(lambda url: download(cache, url, upstream[url]), upstream)))
    for url in pdf_urls:
        unpack_conda(files[url], runtime, windows)
    if not windows:
        # The official Mac zip places these beside Electron.app, outside the disk image's app.
        notices = runtime / 'licenses' / 'Electron'
        notices.mkdir(parents=True)
        with zipfile.ZipFile(files[electron_url]) as archive:
            for filename in ('LICENSE', 'LICENSES.chromium.html'):
                (notices / filename).write_bytes(archive.read(filename))
    (runtime / 'fonts').mkdir()
    shutil.copyfile(files[font_url], runtime / 'fonts/NotoSansSC.ttf')
    shutil.copyfile(files[license_url], runtime / 'fonts/OFL.txt')
    shutil.copyfile(HERE / 'fonts.conf', runtime / 'poppler/fonts.conf')
    (runtime / 'upstream.json').write_text(json.dumps(upstream, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(files[python_url]) as archive:
        archive.extractall(runtime, filter='data')
    site = runtime / 'python' / ('Lib' if windows else 'lib/python3.12') / 'site-packages'
    requirements = runtime.parent / 'requirements.txt'
    subprocess.run(['uv', 'export', '--locked', '--no-dev', '--no-emit-project', '--no-header',
                    '--output-file', str(requirements)], cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
    subprocess.run(['uv', 'pip', 'install', '--no-deps', '--require-hashes', '--only-binary', ':all:',
                    '--python-version', '3.12', '--python-platform', triple, '--target', str(site),
                    '--link-mode', 'copy', '-r', str(requirements)], cwd=ROOT, check=True)
    if not windows:
        arch = 'arm64' if target == 'darwin-arm64' else 'x86_64'
        subprocess.run(['xcrun', '--sdk', 'macosx', 'swiftc', '-O', '-target', f'{arch}-apple-macos13.0',
                        str(ROOT / 'student_ocr.swift'), '-o', str(runtime / 'gradeos-vision')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('target', choices=TARGETS)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('cache', type=Path)
    args = parser.parse_args()
    assemble(args.target, args.runtime.resolve(), args.cache.resolve())
