"""Label locally detected regions on complete pages; never crop or reorder ink."""
import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def label_positions(rows, height):
    gap = min(12, (height - 12) / max(1, len(rows)))
    ys = []
    for row in rows:
        wanted = (row['rect']['y'] + row['rect']['height'] / 2) * height
        ys.append(max(wanted, ys[-1] + gap if ys else 7))
    if ys:
        ys[-1] = min(ys[-1], height - 7)
        for i in range(len(ys) - 2, -1, -1):
            ys[i] = min(ys[i], ys[i + 1] - gap)
    return ys, gap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--documents', required=True, type=Path)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-side', type=int, required=True)
    args = parser.parse_args()
    if args.max_side != 0 and not 512 <= args.max_side <= 4000:
        raise ValueError('Expected native size or complete-page size 512..4000')
    started = time.monotonic()
    documents = json.loads(args.documents.read_text())
    catalog = json.loads(args.catalog.read_text())
    args.output.mkdir(exist_ok=False)
    outputs, pixels, retained = {}, 0, 0
    for student_id, doc in documents.items():
        detected = catalog['documents'][student_id]
        if detected['source_sha256'] != doc['sha256']:
            raise ValueError('OCR catalog document mismatch')
        pages = []
        for page in doc['pages']:
            data = Path(page['absolute_path']).read_bytes()
            if hashlib.sha256(data).hexdigest() != page['sha256']:
                raise ValueError('Source bytes changed')
            source = next(p for p in detected['pages'] if p['page'] == page['page'])
            if source['source_sha256'] != page['sha256']:
                raise ValueError('OCR catalog page mismatch')
            regions = source['regions']
            original = Image.open(io.BytesIO(data)).convert('RGB')
            content = original.copy()
            long_side = args.max_side or max(original.size)
            margin = max(14, round(long_side * .031)) if regions else 0
            if args.max_side:
                content.thumbnail((long_side - 2 * margin, long_side), Image.Resampling.LANCZOS)
            shown = Image.new('RGB', (content.width + 2 * margin, content.height), 'white')
            shown.paste(content, (margin, 0))
            box = [margin, 0, margin + content.width, content.height]
            # Verify whole-page base before adding the explicitly identified
            # OCR overlay. The original is retained separately for UI/export.
            if shown.crop(box).tobytes() != content.tobytes():
                raise ValueError('Incomplete page base')
            overlay = Image.new('RGBA', shown.size)
            draw = ImageDraw.Draw(overlay)
            font = ImageFont.load_default(size=max(10, round(long_side * .018)))
            ordered = sorted(regions, key=lambda r: (r['rect']['y'] + r['rect']['height'] / 2, r['rect']['x']))
            # Alternate sides in reading order to keep dense pages legible.
            gaps = []
            for side in (0, 1):
                rows = ordered[side::2]
                ys, gap = label_positions(rows, content.height)
                gaps.append(gap)
                for region, y in zip(rows, ys):
                    r = region['rect']
                    source_y = (r['y'] + r['height'] / 2) * content.height
                    label_x = margin / 2 if side == 0 else margin + content.width + margin / 2
                    # The leader ends in the added gutter. No overlay touches answer pixels.
                    outer, inner = (margin * .72, margin - 1) if side == 0 else (margin + content.width + margin * .28, margin + content.width)
                    draw.line((outer, y, inner, source_y), fill=(30, 97, 170, 150), width=1)
                    draw.text((label_x, y), region['id'].split('.r')[1], anchor='mm', font=font, fill=(15, 70, 135, 255))
            shown = Image.alpha_composite(shown.convert('RGBA'), overlay).convert('RGB')
            # Clip any overlong margin number at the paper edge.
            shown.paste(content, (margin, 0))
            if shown.crop(box).tobytes() != content.tobytes():
                raise ValueError('Region labels crossed into the source image')
            target = args.output / f"{page['sha256']}-{page['page']}.png"
            shown.save(target)
            with Image.open(target) as persisted:
                if persisted.tobytes() != shown.tobytes():
                    raise ValueError('Persisted labeled page changed')
            pages.append({'page': page['page'], 'absolute_path': str(target.resolve()),
                          'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                          'original_sha256': page['sha256'], 'source_document_sha256': doc['sha256'],
                          'original_size': list(original.size), 'size': list(shown.size),
                          'content_size': list(content.size), 'source_rect_in_image': box,
                          'mode': 'source_regions', 'source_coverage_verified': True,
                          'pixel_identity_verified': False, 'whole_page_scaled': content.size != original.size,
                          'overlay': 'local-ocr-regions-v1', 'regions': regions,
                          'region_manifest_sha256': detected['manifest_sha256'],
                          'minimum_label_gap_px': min(gaps), 'label_font_px': font.size})
            pixels += original.width * original.height
            retained += shown.width * shown.height
        outputs[student_id] = {'sha256': doc['sha256'], 'pages': pages}
    manifest = {'version': 1, 'mode': 'source_regions', 'documents': outputs,
                'original_pixels': pixels, 'retained_pixels': retained,
                'pixel_reduction_fraction': 1 - retained / pixels, 'max_side': args.max_side,
                'elapsed_seconds': time.monotonic() - started,
                'policy': 'Complete pages in original order, uniform scaling and local OCR overlay only. No crops. Original bytes retained. The image overlay contains geometry and IDs only; a separate source-bound OCR lookup may accompany the page.'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'pages': sum(len(d['pages']) for d in outputs.values()), 'elapsed_seconds': manifest['elapsed_seconds']}))


if __name__ == '__main__':
    main()
