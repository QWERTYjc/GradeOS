"""Local UI input adapter. Original uploads and page identities remain immutable."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps
from native_pages import prepare_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.read_bytes()
    if source.startswith(b'%PDF-'):
        pages = prepare_pdf(args.source, args.output)
    else:
        Image.MAX_IMAGE_PIXELS = 50_000_000
        with Image.open(args.source) as original:
            if original.format not in ('PNG', 'JPEG', 'WEBP', 'TIFF', 'BMP'):
                raise ValueError('Unsupported image')
            count = getattr(original, 'n_frames', 1)
            if count > 300:
                raise ValueError('Too many pages')
            pages = []
            for index in range(count):
                original.seek(index)
                if original.width * original.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('Image dimensions')
                image = ImageOps.exif_transpose(original).convert('RGB')
                path = args.output / f'page-{index + 1}.png'
                image.save(path)
                pages.append({'page': index + 1, 'path': path.name, 'size': list(image.size),
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                              'representation': 'complete_source_image', 'source_pixels_preserved': True})
    manifest = {'sha256': hashlib.sha256(source).hexdigest(), 'pages': pages}
    (args.output / 'manifest.json').write_text(json.dumps(manifest))


if __name__ == '__main__':
    main()
