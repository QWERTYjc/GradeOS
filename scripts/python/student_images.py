"""Prepare source-bound initial views; optional resizing never replaces original pages."""
import argparse
import hashlib
import json
import time
import sys
import io
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont


def source_grid(image, columns=10, rows=40):
    """Add only an external ruler. Every source pixel remains at native scale.

    Cells are neutral spatial references, not OCR, handwriting detection or
    score evidence. A model selects cells; the host maps them to original pixels.
    """
    if image.mode != 'RGB':
        raise ValueError('Source grid requires prepared RGB pages')
    left, top = 64, 36
    shown = Image.new('RGB', (image.width + left, image.height + top), 'white')
    shown.paste(image, (left, top))
    draw = ImageDraw.Draw(shown)
    font = ImageFont.load_default(size=min(20, max(10, image.height // rows - 8)))
    for column in range(columns):
        x = left + (column + .5) * image.width / columns
        draw.text((x, 14), chr(65 + column), anchor='mm', font=font, fill='#174ea6')
        draw.line((left + column * image.width / columns, 25,
                   left + column * image.width / columns, top - 1), fill='#879bbb')
    for row in range(rows):
        y1 = top + row * image.height / rows
        y2 = top + (row + 1) * image.height / rows
        if row % 2 == 0:
            draw.rectangle((0, y1, left - 1, y2 - 1), fill='#eef3fa')
        draw.text((28, (y1 + y2) / 2), str(row + 1), anchor='mm', font=font, fill='#174ea6')
        draw.line((47, y1, left - 1, y1), fill='#879bbb')
    box = (left, top, left + image.width, top + image.height)
    if shown.crop(box).tobytes() != image.tobytes():
        raise ValueError('Grid altered original pixels')
    return shown, box, {'columns': columns, 'rows': rows, 'version': 'source-grid-v1'}


def exact_white_crop(image, padding=8):
    if image.mode != 'RGB':
        return image.copy(), (0, 0, image.width, image.height)
    box = ImageChops.difference(image, Image.new('RGB', image.size, 'white')).getbbox()
    if box is None:
        return image.copy(), (0, 0, image.width, image.height)
    left, top, right, bottom = box
    bounds = (max(0, left-padding), max(0, top-padding),
              min(image.width, right+padding), min(image.height, bottom+padding))
    cropped = image.crop(bounds)
    reconstructed = Image.new('RGB', image.size, 'white')
    reconstructed.paste(cropped, bounds[:2])
    if reconstructed.tobytes() != image.tobytes():
        raise ValueError('Crop would lose source pixels')
    return cropped, bounds


def resize_overview(image, max_side):
    if not isinstance(max_side, int) or isinstance(max_side, bool) or max_side <= 0:
        raise ValueError('max_side must be a positive integer')
    shown = image.copy()
    shown.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return shown


def original_region(image, region, frame=None, local_only=False):
    """Read native pixels from a rectangle located on the displayed page."""
    if not isinstance(region, list) or len(region) != 4 or any(
        not isinstance(n, int) or isinstance(n, bool) for n in region
    ):
        raise ValueError('Region requires four integer coordinates')
    x, y, width, height = region
    if min(x, y) < 0 or min(width, height) <= 0 or x + width > 1000 or y + height > 1000:
        raise ValueError('Region outside original page')
    left, top, right, bottom = frame if frame is not None else (0, 0, *image.size)
    if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
        raise ValueError('Displayed frame outside original page')
    w, h = right - left, bottom - top
    box = (left + x * w // 1000, top + y * h // 1000,
           left + math.ceil((x + width) * w / 1000),
           top + math.ceil((y + height) * h / 1000))
    if local_only and box == (left, top, right, bottom):
        raise ValueError('Select a local region within the displayed page')
    return image.crop(box)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--documents', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--region', type=int, nargs=4)
    parser.add_argument('--frame', type=int, nargs=4)
    parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--grid', action='store_true')
    parser.add_argument('--max-side', type=int)
    args = parser.parse_args(); started = time.monotonic()
    if args.source:
        data = args.source.read_bytes()
        if hashlib.sha256(data).hexdigest() != args.sha256:
            raise ValueError('Original page changed')
        with Image.open(io.BytesIO(data)) as image:
            if args.region is not None and args.max_side is None:
                shown = original_region(image, args.region, args.frame, args.local_only)
            elif args.max_side is not None and args.region is None and args.frame is None and not args.local_only:
                shown = resize_overview(image, args.max_side)
            else:
                parser.error('Select either a local region or a whole-page overview')
            shown.save(sys.stdout.buffer, format='PNG')
        return
    if not args.documents or not args.output:
        parser.error('--documents and --output are required for initial views')
    if args.max_side is not None and (args.max_side <= 0 or args.grid):
        parser.error('--max-side must be positive and cannot be combined with --grid')
    mode = 'resized_overview' if args.max_side else 'source_grid' if args.grid else 'exact_white_margin_trim'
    docs = json.loads(args.documents.read_text()); args.output.mkdir(exist_ok=False)
    outputs = {}; cache = {}; source_pixels = 0; retained_pixels = 0
    for student_id, doc in docs.items():
        pages = []
        for page in doc['pages']:
            data = Path(page['absolute_path']).read_bytes()
            original_hash = hashlib.sha256(data).hexdigest()
            if original_hash != page['sha256']:
                raise ValueError('Original page changed')
            if original_hash not in cache:
                with Image.open(page['absolute_path']) as image:
                    image.load()
                    if args.grid:
                        cropped, box, grid = source_grid(image)
                    else:
                        cropped, box = exact_white_crop(image); grid = None
                    native_size = cropped.size
                    if args.max_side:
                        cropped = resize_overview(cropped, args.max_side)
                    target = args.output / f'{original_hash}.png'; cropped.save(target)
                    # Verify persisted PNG, not just the in-memory image.
                    with Image.open(target) as persisted:
                        if persisted.tobytes() != cropped.tobytes() or persisted.size != cropped.size:
                            raise ValueError('Persisted image changed pixels')
                    cache[original_hash] = {'absolute_path':str(target.resolve()),
                        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                        'original_sha256':original_hash, 'original_size':list(image.size),
                        'size':list(cropped.size), 'bbox':list(box),
                        'pixel_identity_verified':cropped.size == native_size,
                        'source_binding_verified':True, 'mode':mode,
                        **({'max_side':args.max_side} if args.max_side else {}),
                        **({'grid':grid, 'source_rect_in_image':list(box)} if args.grid else {})}
            record = {**cache[original_hash], 'page':page['page'], 'source_document_sha256':doc['sha256']}
            pages.append(record)
            source_pixels += record['original_size'][0] * record['original_size'][1]
            retained_pixels += record['size'][0] * record['size'][1]
        outputs[student_id] = {'sha256':doc['sha256'], 'pages':pages}
    result = {'version':1, 'documents':outputs, 'original_pixels':source_pixels,
              'retained_pixels':retained_pixels, 'pixel_reduction_fraction':1-retained_pixels/source_pixels,
              'elapsed_seconds':time.monotonic()-started,
              'mode':mode, 'max_side':args.max_side,
              'policy':('Complete content extent resized proportionally with LANCZOS, without enlargement; small details may become ambiguous. Original files and original read tool unchanged.' if args.max_side else 'Original RGB rectangle is byte-identical at native resolution. Each page stays complete and in document order. Only external row/column labels are added; cells do not classify writing or determine marks.' if args.grid else 'All original nonwhite RGB pixels retained at native resolution; exact white padding reconstructs original. Blank/non-RGB pages remain complete. Original read tool unchanged.')}
    (args.output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'pages':sum(len(d['pages']) for d in outputs.values()), 'pixel_reduction_fraction':result['pixel_reduction_fraction']}))


if __name__ == '__main__':
    main()
