"""Score-blind fixture verification and preparation. No posthoc files are read here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent / 'fixtures'
ROLES = {'scheme', 'student', 'question'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_directory(name: str, root: Path = ROOT) -> Path:
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name):
        raise ValueError('Invalid fixture name')
    path = (root / name).resolve()
    if path.parent != root.resolve() or not path.is_dir():
        raise ValueError('Unknown fixture')
    return path


def input_documents(directory: Path) -> dict:
    manifest = json.loads((directory / 'input.json').read_text())
    if set(manifest) != {'version', 'documents'} or manifest['version'] != 1:
        raise ValueError('Unexpected input manifest fields')
    documents = manifest['documents']
    if not {'scheme', 'student'} <= documents.keys() or not documents.keys() <= ROLES:
        raise ValueError('Unexpected document roles')
    for role, document in documents.items():
        if set(document) != {'path', 'sha256', 'page_count', 'pages'}:
            raise ValueError('Unexpected document fields')
        path = (directory / document['path']).resolve()
        if not path.is_relative_to(directory.resolve()) or 'posthoc' in path.parts:
            raise ValueError('Input outside source assets or inside posthoc labels')
        if path.suffix.lower() != '.pdf' or sha(path) != document['sha256']:
            raise ValueError(f'{role}: source hash mismatch')
        count = len(PdfReader(path).pages)
        pages = document['pages']
        if count != document['page_count'] or not pages or len(pages) != len(set(pages)):
            raise ValueError(f'{role}: page contract mismatch')
        if any(type(n) is not int or n < 1 or n > count for n in pages):
            raise ValueError(f'{role}: invalid selected page')
    return documents


def prepare(directory: Path, output: Path) -> dict:
    # Only declared source documents cross this boundary; fixture ID and labels do not.
    from native_pages import prepare_pdf

    documents = input_documents(directory)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'version': 1, 'pixel_policy': 'native_scan_or_full_pdf_render', 'documents': {}}
    uploads = []
    for role, document in documents.items():
        target = output / role
        target.mkdir()
        source = directory / document['path']
        original = target / 'original.pdf'
        selected = document['pages']
        if selected == list(range(1, document['page_count'] + 1)):
            shutil.copyfile(source, original)
        else:
            reader, writer = PdfReader(source), PdfWriter()
            for page in selected:
                writer.add_page(reader.pages[page - 1])
            with original.open('wb') as handle:
                writer.write(handle)
        rendered = prepare_pdf(original, target, None)
        pages = [{**page, 'path': str((target / page['path']).relative_to(output))}
                 for page in rendered]
        prepared = {'sha256': sha(original), 'pages': pages}
        if role in {'scheme', 'student'}:
            manifest['documents'][role] = prepared
        uploads.append({'role': role, 'path': f'{role}/original.pdf', 'sha256': sha(original)})
    manifest['long_side'] = max(max(p['size']) for d in manifest['documents'].values() for p in d['pages'])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'uploads.json').write_text(json.dumps(uploads, indent=2) + '\n')
    (output / 'cohort.json').write_text(json.dumps({
        'scheme_input': str(output), 'students': [{'id': 'student-001', 'input': str(output)}]
    }, indent=2) + '\n')
    return {'output': str(output), 'pages': {r: len(d['pages']) for r, d in documents.items()},
            'labels_loaded': False, 'model_requests': 0}
