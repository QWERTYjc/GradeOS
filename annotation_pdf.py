"""Print saved annotations beside original pages; no model calls or grading logic."""
import argparse
import copy
import io
import json
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf._page import PageObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

PAGE_W, PAGE_H = landscape(A4)
MARGIN, TOP, BOTTOM = 22, 43, 24
LEFT_W, GAP = 382, 22
COLORS = {'credit': '#277653', 'deduction': '#ad4b38', 'review': '#957015', 'teacher': '#376fa0'}


def register_font():
    candidates = [Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf'),
                  Path('/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf'),
                  Path('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc')]
    for path in candidates:
        if path.is_file():
            pdfmetrics.registerFont(TTFont('GradeOS', str(path)))
            return 'GradeOS'
    raise RuntimeError('A Unicode TTF font with Chinese glyphs is required for printable annotations')


def pdf_rectangle(rect, transform=None):
    """Both inputs use normalized top-left coordinates; no page number inference."""
    t = transform or {'x': 0, 'y': 0, 'width': 1, 'height': 1}
    return {'x': t['x'] + rect['x'] * t['width'], 'y': t['y'] + rect['y'] * t['height'],
            'width': rect['width'] * t['width'], 'height': rect['height'] * t['height']}


def paragraphs(note, style, title_style):
    title = ' · '.join(value for value in [note['id'], note['label'], note.get('score', '')] if value)
    blocks = [Paragraph(escape(title), title_style)]
    for label, field in [('依据', 'evidence'), ('条件', 'condition'),
                         ('老师复核' if note.get('reviewed') else '批注', 'reason')]:
        if note.get(field):
            blocks.append(Paragraph(escape(f'{label}：{note[field]}').replace('\n', '<br/>'), style))
    for text in note.get('uncertainties', []):
        blocks.append(Paragraph(escape('待确认：' + text), style))
    if not note.get('regions'):
        blocks.append(Paragraph('未提供具体位置；此条批注不在原卷上画框。', style))
    return blocks


def export_pdf(packet, output):
    font = register_font()
    body = ParagraphStyle('body', fontName=font, fontSize=9, leading=12.4, textColor=colors.HexColor('#404954'), wordWrap='CJK', spaceAfter=2)
    heading = ParagraphStyle('heading', parent=body, fontSize=10, leading=14, textColor=colors.HexColor('#243443'), spaceAfter=3)
    writer, readers = PdfWriter(), {}
    sources = packet['pages'] + ([{'notes': packet['unplaced'], 'sourcePage': None}] if packet.get('unplaced') else [])
    audit = []
    for ordinal, source in enumerate(sources, 1):
        original, transform = None, None
        if source.get('originalPdf'):
            path = source['originalPdf']
            if path not in readers:
                readers[path] = PdfReader(path)
            # Deep-copying a PageObject recursively copies its owning reader and
            # every sibling page. Copy the page dictionary, keeping source
            # resources shared; the output writer clones referenced objects.
            original = copy.copy(readers[path].pages[source['sourcePage'] - 1])
            if original.rotation:
                oriented = PdfWriter()
                original = oriented.add_page(original)
                original.transfer_rotation_to_content()
            sw, sh = float(original.cropbox.width), float(original.cropbox.height)
            transform = source.get('imageToPdf')
        elif source.get('image'):
            with Image.open(source['image']) as image:
                sw, sh = image.size
        else:
            sw, sh = A4
        scale = min(LEFT_W / sw, (PAGE_H - TOP - BOTTOM) / sh)
        dw, dh = sw * scale, sh * scale
        left, bottom = MARGIN + (LEFT_W - dw) / 2, PAGE_H - TOP - dh
        text_x, text_w = MARGIN + LEFT_W + GAP, PAGE_W - MARGIN * 2 - LEFT_W - GAP
        # Split paragraph content rather than clipping a long comment. A
        # continuation retains the same original page and stable note IDs.
        pending = []
        for note in source['notes']:
            pending.extend((note, block) for block in paragraphs(note, body, heading))
            pending.append((note, None))
        continuation = 0
        while pending or continuation == 0:
            continuation += 1
            buffer = io.BytesIO()
            drawing = canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H))
            drawing.setTitle(f"{packet.get('student', '')} - 批改批注")
            drawing.setFont(font, 11)
            title = f"{packet.get('student') or '答卷'} · 批改批注"
            drawing.drawString(MARGIN, PAGE_H - 22, title[:65])
            drawing.setFont(font, 8)
            page_label = f"答卷第 {ordinal} 页 / 原文件第 {source['sourcePage']} 页" if source.get('sourcePage') else '未定位的批注'
            if continuation > 1:
                page_label += f' · 批注续页 {continuation}'
            drawing.drawRightString(PAGE_W - MARGIN, PAGE_H - 22, page_label)
            drawing.setStrokeColor(colors.HexColor('#e0e5e9'))
            drawing.line(text_x - GAP / 2, BOTTOM, text_x - GAP / 2, PAGE_H - TOP)
            if not original and source.get('image'):
                drawing.drawImage(source['image'], left, bottom, dw, dh, preserveAspectRatio=True)
            for note in source['notes']:
                color = colors.HexColor(COLORS.get(note.get('tone'), '#376fa0'))
                drawing.setStrokeColor(color)
                drawing.setFillColor(color)
                drawing.setLineWidth(.85)
                for region in note.get('regions', []):
                    rect = pdf_rectangle(region['rect'], transform)
                    x, y = left + rect['x'] * dw, bottom + (1 - rect['y'] - rect['height']) * dh
                    w, h = rect['width'] * dw, rect['height'] * dh
                    if region.get('shape') == 'lasso' and region.get('points'):
                        path = drawing.beginPath()
                        for index, (px, py) in enumerate(region['points']):
                            pt = pdf_rectangle({'x': px, 'y': py, 'width': 0, 'height': 0}, transform)
                            fn = path.moveTo if index == 0 else path.lineTo
                            fn(left + pt['x'] * dw, bottom + (1 - pt['y']) * dh)
                        path.close()
                        drawing.drawPath(path, fill=0, stroke=1)
                    else:
                        drawing.rect(x, y, w, h, fill=0, stroke=1)
                    drawing.setFont(font, 6.5)
                    label_w = pdfmetrics.stringWidth(note['id'], font, 6.5) + 5
                    label_x = max(left, min(x, left + dw - label_w))
                    label_y = min(bottom + dh - 9, y + h + 1)
                    drawing.setFillColor(colors.white)
                    drawing.rect(label_x, label_y, label_w, 9, fill=1, stroke=0)
                    drawing.setFillColor(color)
                    drawing.drawString(label_x + 2, label_y + 2, note['id'])
            y = PAGE_H - TOP
            printed = []
            while pending:
                note, block = pending[0]
                if block is None:
                    y -= 10
                    pending.pop(0)
                    continue
                _, height = block.wrap(text_w, PAGE_H)
                available = y - BOTTOM
                if block.style is heading and available < 60 and y < PAGE_H - TOP:
                    break
                if height > available:
                    pieces = block.split(text_w, available)
                    if not pieces:
                        break
                    block, *rest = pieces
                    pending[0:1] = [(note, piece) for piece in rest]
                    _, height = block.wrap(text_w, available)
                else:
                    pending.pop(0)
                block.drawOn(drawing, text_x, y - height)
                y -= height + block.style.spaceAfter
                printed.append(note['id'])
            if not source['notes']:
                empty = Paragraph('本页没有批改批注。', body)
                empty.wrap(text_w, 30)
                empty.drawOn(drawing, text_x, y - 14)
            drawing.setFont(font, 7)
            drawing.setFillColor(colors.HexColor('#737c86'))
            drawing.drawString(MARGIN, 10, '框与编号对应右侧批注 · 内容来自已保存结果' + (' · 待审阅' if packet.get('status') != 'completed' else ''))
            drawing.drawRightString(PAGE_W - MARGIN, 10, f'{len(writer.pages) + 1}')
            drawing.save()
            sheet = PageObject.create_blank_page(width=PAGE_W, height=PAGE_H)
            if original:
                sheet.merge_transformed_page(original, Transformation().translate(-float(original.cropbox.left), -float(original.cropbox.bottom)).scale(scale).translate(left, bottom))
            sheet.merge_page(PdfReader(buffer).pages[0])
            writer.add_page(sheet)
            audit.append({'output_page': len(writer.pages), 'source_page': source.get('sourcePage'), 'workspace_page': source.get('id'), 'note_ids': list(dict.fromkeys(printed)), 'continuation': continuation})
    writer.add_metadata({'/Title': f"{packet.get('student', '答卷')} - 批改批注", '/Creator': 'GradeOS - deterministic annotation export', '/Subject': 'Printable saved grading annotations; no additional model call'})
    with open(output, 'wb') as stream:
        writer.write(stream)
    Path(str(output) + '.audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    export_pdf(json.loads(Path(args.input).read_text()), args.output)
