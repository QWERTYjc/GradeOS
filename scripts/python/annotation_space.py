"""Conservative local ink occupancy for placing labels on complete source pages."""
import argparse
import base64
import hashlib
import json
import math
import unicodedata
from pathlib import Path

from PIL import Image, ImageChops


def page_occupancy(path, expected_hash):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Source changed before annotation placement')
    with Image.open(path) as source:
        rgba = source.convert('RGBA')
        rgb = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
    width, height = rgb.size
    cell = max(1, math.ceil(max(width / 384, height / 768)))
    columns, rows = math.ceil(width / cell), math.ceil(height / cell)
    red, green, blue = rgb.split()
    darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
    ink = darkest.point(lambda value: 255 if value < 245 else 0)
    padded = Image.new('L', (columns * cell, rows * cell), 0)
    padded.paste(ink, (0, 0))
    # Float averaging followed by >0 is exact any-ink pooling: unlike an 8-bit
    # thumbnail it cannot erase a single small dot in a large source cell.
    reduced = padded.convert('F').resize((columns, rows), Image.Resampling.BOX)
    packed = bytearray(math.ceil(columns * rows / 8))
    for index, value in enumerate(getattr(reduced, 'get_flattened_data', reduced.getdata)()):
        if value > 0:
            packed[index // 8] |= 1 << (index % 8)
    return {'version': 1, 'sourceWidth': width, 'sourceHeight': height, 'cellSize': cell,
            'columns': columns, 'rows': rows, 'pageHash': expected_hash,
            'occupiedBase64': base64.b64encode(packed).decode('ascii')}


def comment_glyph_widths(notes, font):
    from reportlab.pdfbase import pdfmetrics
    # The layout can add an ellipsis even when none occurs in the saved notes.
    # Match formatted_text: ordinary glyphs must not undergo NFKC (which would
    # turn the single ellipsis into three narrower dots, causing a third line).
    chars = set(json.dumps(notes, ensure_ascii=False) + ' ·待确认：…')
    widths = {}
    for char in chars:
        decomposition = unicodedata.decomposition(char)
        value = unicodedata.normalize('NFKC', char) if decomposition.startswith(('<super>', '<sub>')) else char
        # Unscaled super/subscript advances conservatively reserve enough room.
        widths[char] = pdfmetrics.stringWidth(value, 'ZapfDingbats' if char == '✓' else font, 1)
    return widths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    packet = json.loads(args.input.read_text())
    from .annotation_pdf import register_font
    font = register_font()
    cache, result = {}, {}
    for page in packet['pages']:
        if page['sha256'] not in cache:
            cache[page['sha256']] = page_occupancy(page['image'], page['sha256'])
        # Exact print-font advances; the shared JS layout wraps the same point
        # content as the UI without guessing PDF glyph widths or adding a model.
        result[page['id']] = {**cache[page['sha256']],
                              'commentGlyphWidths': comment_glyph_widths(page['notes'], font)}
    args.output.write_text(json.dumps(result))


if __name__ == '__main__':
    main()
