"""Read complete page scans without resizing; retain their PDF coordinate mapping."""
import hashlib
import subprocess
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def _compose(current, added):
    a, b, c, d, e, f = current
    g, h, i, j, k, l = added
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)


def complete_scan(page):
    """Extract only when the page paints exactly one image and nothing else.

    The entire embedded scan is returned, never an ink crop. PDF packaging
    whitespace is represented by the per-page transform. Text, annotations,
    clipping, masks and other visible page objects require full-page rendering.
    """
    if page.get('/Rotate', 0) or page.get('/Annots'):
        return None
    contents = page.get_contents()
    if contents is None:
        return None
    matrix = (1, 0, 0, 1, 0, 0)
    stack, paints = [], []
    nonpainting = {b'BT', b'ET', b'Td', b'TD', b'Tm', b'T*', b'Tf'}
    for operands, operator in contents.operations:
        if operator == b'q':
            stack.append(matrix)
        elif operator == b'Q':
            if not stack:
                return None
            matrix = stack.pop()
        elif operator == b'cm':
            matrix = _compose(matrix, tuple(float(value) for value in operands))
        elif operator == b'Do':
            paints.append((operands[0], matrix))
        elif operator not in nonpainting:
            return None
    if stack or len(paints) != 1:
        return None
    name, (a, b, c, d, e, f) = paints[0]
    objects = page['/Resources'].get('/XObject')
    source = objects.get_object().get(name) if objects is not None else None
    if source is None:
        return None
    source = source.get_object()
    if source.get('/Subtype') != '/Image' or any(key in source for key in ['/SMask', '/Mask', '/ImageMask', '/Decode']):
        return None
    left, bottom, right, top = map(float, page.cropbox)
    if abs(b) > 1e-9 or abs(c) > 1e-9 or a <= 0 or d <= 0:
        return None
    if e < left or f < bottom or e+a > right+1e-6 or f+d > top+1e-6:
        return None
    image = page.images[str(name)].image.convert('RGB')
    if image.width*image.height > 50_000_000:
        raise ValueError('Source scan exceeds 50 million pixels; no automatic downsampling')
    return image, {
        'representation': 'complete_native_scan',
        'source_image_size': list(image.size),
        'source_rgb_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
        'pdf_crop_box': [left, bottom, right, top],
        'image_to_pdf': {
            'x': (e-left)/(right-left), 'y': (top-f-d)/(top-bottom),
            'width': a/(right-left), 'height': d/(top-bottom),
        },
        'only_visible_page_object': True,
    }


def prepare_pdf(source, output, long_side=None, max_pages=300):
    """One PNG per physical page. Resizing is explicit, never the default."""
    source, output = Path(source), Path(output)
    if long_side is not None and (not isinstance(long_side, int) or long_side < 1):
        raise ValueError('Invalid requested image size')
    reader = PdfReader(source)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= max_pages:
        raise ValueError('Encrypted PDF or invalid page count')
    output.mkdir(parents=True, exist_ok=True)
    result = []
    for index, page in enumerate(reader.pages, 1):
        path = output/f'page-{index}.png'
        extracted = complete_scan(page)
        if extracted:
            image, metadata = extracted
        else:
            # Vector/mixed PDFs have no single original raster. Render the full
            # page, including text/annotations, instead of extracting fragments.
            subprocess.run(['pdftoppm', '-f', str(index), '-l', str(index), '-singlefile',
                            '-cropbox', '-png', '-r', '300', str(source), str(path.with_suffix(''))],
                           check=True, capture_output=True, timeout=110)
            with Image.open(path) as rendered:
                image = rendered.convert('RGB')
            metadata = {'representation': 'complete_pdf_render', 'render_dpi': 300,
                        'pdf_crop_box': list(map(float, page.cropbox)),
                        'image_to_pdf': {'x': 0, 'y': 0, 'width': 1, 'height': 1}}
        if image.width*image.height > 50_000_000:
            raise ValueError('Rendered page exceeds 50 million pixels')
        if long_side is not None:
            image.thumbnail((long_side, long_side), Image.Resampling.LANCZOS)
        image.save(path)
        with Image.open(path) as persisted:
            if persisted.size != image.size or persisted.tobytes() != image.tobytes():
                raise ValueError('Persisted page pixels changed')
        result.append({'page': index, 'path': path.name,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'size': list(image.size), 'requested_long_side': long_side,
                       'source_pixels_preserved': bool(extracted and image.size == tuple(metadata['source_image_size'])),
                       **metadata})
    return result
