"""Render only the two supplied PDFs; no GradeOS imports or reference labels."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from native_pages import prepare_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scheme', type=Path)
    parser.add_argument('--student', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--long-side', type=int, help='Explicit comparison resize; default preserves native scans')
    args = parser.parse_args()
    if not args.scheme and not args.student:
        parser.error('Supply --scheme, --student, or both')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {'version': 1, 'pixel_policy': 'native_scan_or_full_pdf_render', 'documents': {}}
    for role in ['scheme', 'student']:
        source = getattr(args, role)
        if source is None:
            continue
        target = args.output / role
        target.mkdir()
        shutil.copyfile(source, target / 'original.pdf')
        pages = prepare_pdf(target / 'original.pdf', target, args.long_side)
        manifest['documents'][role] = {
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'pages': [{**page, 'path': str((target/page['path']).relative_to(args.output))} for page in pages]}
    manifest['long_side'] = max(max(page['size']) for doc in manifest['documents'].values() for page in doc['pages'])
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: len(v['pages']) for k, v in manifest['documents'].items()}))


if __name__ == '__main__':
    main()
