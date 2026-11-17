"""Print saved point comments in source whitespace; no model calls or grading logic."""
import argparse
import copy
import io
import json
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf._page import PageObject
from pypdf.generic import (BooleanObject, DecodedStreamObject, DictionaryObject, NameObject,
                           NumberObject, RectangleObject, TextStringObject)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

COLORS = {'credit': '#23845b', 'deduction': '#c64545', 'review': '#a47824', 'teacher': '#376fa0'}


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


def formatted_text(text):
    # Position ordinary glyphs for Unicode super/subscripts. This preserves
    # notation and avoids missing-glyph boxes in otherwise portable CJK fonts.
    parts, run, kind = [], [], None
    def flush():
        if not run:
            return
        value = escape(''.join(run)).replace('\n', '<br/>')
        parts.append(f'<{kind}>{value}</{kind}>' if kind else value)
        run.clear()
    for char in str(text):
        decomposition = unicodedata.decomposition(char)
        next_kind = 'super' if decomposition.startswith('<super>') else 'sub' if decomposition.startswith('<sub>') else None
        if next_kind != kind:
            flush()
            kind = next_kind
        run.append(unicodedata.normalize('NFKC', char) if kind else char)
    flush()
    return ''.join(parts)


def paragraphs(note, style, title_style):
    title = ' · '.join(value for value in [note['id'], note['label'], note.get('score', ''), (note.get('mark') or {}).get('text', '')] if value)
    blocks = [Paragraph(formatted_text(title), title_style)]
    for label, field in [('模型转写（以原稿为准）', 'evidence'), ('评分点', 'condition'),
                         ('老师复核' if note.get('reviewed') else '批注', 'reason')]:
        if note.get(field):
            blocks.append(Paragraph(formatted_text(f'{label}：{note[field]}'), style))
    for text in note.get('uncertainties', []):
        blocks.append(Paragraph(formatted_text('待确认：' + text), style))
    if note.get('locationNote'):
        blocks.append(Paragraph(formatted_text(note['locationNote']), style))
    elif not note.get('regions'):
        blocks.append(Paragraph('未提供具体位置；此条批注不在原卷上画框。', style))
    return blocks


def detail_text(note):
    title = ' · '.join(str(value) for value in [note['id'], note['label'], note.get('score', '')] if value)
    lines = [title]
    for label, field in [('判定理由', 'reason'), ('对应评分要求', 'condition'),
                         ('模型转写（以原稿为准）', 'evidence')]:
        if note.get(field):
            lines.append(f'{label}：{note[field]}')
    lines.extend('待确认：' + text for text in note.get('uncertainties', []))
    if note.get('locationNote'):
        lines.append(note['locationNote'])
    return '\n\n'.join(lines)


def add_detail_annotation(writer, page_index, note, rect):
    # The short reason is already printed on the page. The hit area has no icon
    # or fill, so the closed PDF note cannot obscure source ink or alter print.
    appearance = DecodedStreamObject()
    appearance.set_data(b'')
    appearance.update({NameObject('/Type'): NameObject('/XObject'),
                       NameObject('/Subtype'): NameObject('/Form'),
                       NameObject('/BBox'): RectangleObject((0, 0, rect[2]-rect[0], rect[3]-rect[1])),
                       NameObject('/Resources'): DictionaryObject()})
    annotation = DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Text'),
        NameObject('/Rect'): RectangleObject(rect), NameObject('/Contents'): TextStringObject(detail_text(note)),
        NameObject('/T'): TextStringObject('GradeOS · ' + note['label']),
        NameObject('/NM'): TextStringObject(note['id']), NameObject('/Name'): NameObject('/Comment'),
        NameObject('/Open'): BooleanObject(False), NameObject('/F'): NumberObject(0),
        NameObject('/AP'): DictionaryObject({NameObject('/N'): writer._add_object(appearance)}),
    })
    writer.add_annotation(page_index, annotation)


def visible_paragraphs(note, style, title_style):
    if 'summary' not in note:
        return paragraphs(note, style, title_style)
    # Continuations use the same brief display contract as the original page;
    # the complete record is embedded in the closed note, never discarded.
    tone = (note.get('mark') or {}).get('tone', note.get('tone'))
    brief_style = ParagraphStyle('brief-reason', parent=style,
                                textColor=colors.HexColor(COLORS.get(tone, '#376fa0')))
    lines = (note.get('commentPlacement') or {}).get('lines')
    summary = '\n'.join(line['text'] for line in lines) if lines else note['summary']
    return [Paragraph(formatted_text(summary), brief_style)]


def draw_grading_symbol(drawing, note, transform, left, bottom, dw, dh):
    place = note.get('symbolPlacement')
    if not place:
        return
    rect = pdf_rectangle(place['rect'], transform)
    x, top = left + rect['x'] * dw, bottom + (1 - rect['y']) * dh
    w, h = rect['width'] * dw, rect['height'] * dh
    symbol = place['symbol']
    drawing.saveState()
    drawing.setStrokeColor(colors.HexColor(COLORS[symbol['tone']]))
    drawing.setLineWidth(symbol['stroke'] * min(w, h) / 20)
    drawing.setLineCap(1); drawing.setLineJoin(1)
    for points in symbol['paths']:
        path = drawing.beginPath()
        for index, (px, py) in enumerate(points):
            (path.moveTo if index == 0 else path.lineTo)(x + px * w / 20, top - py * h / 20)
        drawing.drawPath(path, stroke=1, fill=0)
    if place.get('connection'):
        drawing.setStrokeAlpha(.42); drawing.setLineWidth(.4)
        path = drawing.beginPath()
        for index, (px, py) in enumerate(place['connection']['points']):
            pt = pdf_rectangle({'x': px, 'y': py, 'width': 0, 'height': 0}, transform)
            (path.moveTo if index == 0 else path.lineTo)(left + pt['x'] * dw, bottom + (1 - pt['y']) * dh)
        drawing.drawPath(path, stroke=1, fill=0)
    drawing.restoreState()


def add_score_overview(writer, packet, font):
    summary = packet.get('resultSummary')
    if not summary:
        return
    pw, ph = A4
    rows = summary['items']
    table_top, row_height, bottom_margin = ph - 183, 18, 34
    rows_per_page = int((table_top - 10 - bottom_margin) // row_height)
    for start in range(0, max(1, len(rows)), rows_per_page):
        buffer = io.BytesIO(); drawing = canvas.Canvas(buffer, pagesize=A4)
        drawing.setFillColor(colors.HexColor('#34434c')); drawing.setFont(font, 11)
        drawing.drawString(44, ph - 36, packet.get('student', '答卷'))
        drawing.setFont(font, 22); drawing.drawString(44, ph - 70, '评分结果' + (' · 续表' if start else ''))
        drawing.setFont(font, 24); drawing.drawString(44, ph - 102, str(summary['score']) + ' ' + summary.get('scoreUnit', '分'))
        drawing.setFont(font, 10); drawing.setFillColor(colors.HexColor('#7a8591'))
        drawing.drawString(44, ph - 121, summary.get('statusText') or ('待老师审阅' if summary['provisional'] else '已完成审阅'))
        if summary.get('guide'):
            drawing.drawRightString(pw - 44, ph - 121, f"评分实施.md v{summary['guide']['revision']}")
        drawing.setFont(font, 9)
        drawing.drawString(44, ph - 142, '✓ 得分步骤   × 失分步骤   勾带短线：部分得分   ? 待确认')
        drawing.drawString(44, ph - 159, '具体分值以本表及逐项记录为准；数字 PDF 可点击简短理由查看完整依据。')
        y = table_top
        drawing.setFont(font, 10); drawing.setFillColor(colors.HexColor('#596878'))
        for x, title in [(44, '题目'), (240, '得分 / 满分'), (400, '原答卷页')]:
            drawing.drawString(x, y, title)
        y -= 10
        for item in rows[start:start + rows_per_page]:
            drawing.setStrokeColor(colors.HexColor('#e8ecef')); drawing.setLineWidth(.35)
            drawing.line(44, y, pw - 44, y); y -= 14
            drawing.setFont(font, 10); drawing.setFillColor(colors.HexColor('#445365'))
            drawing.drawString(44, y, str(item['id'])); drawing.drawString(240, y, str(item['score']))
            drawing.drawString(400, y, '、'.join(map(str, item['pages'])) or '未定位'); y -= 4
        drawing.save(); writer.add_page(PdfReader(buffer).pages[0])
    writer.add_outline_item('评分结果', 0)


def draw_point_comment(drawing, note, font, transform, left, bottom, dw, dh, layout):
    place = note['commentPlacement']
    t = transform or {'x': 0, 'y': 0, 'width': 1, 'height': 1}
    factor = dw*t['width']/layout['width']
    base = pdf_rectangle(place['rect'], transform)
    x, top = left+base['x']*dw, bottom+(1-base['y'])*dh
    color = colors.HexColor(COLORS.get((note.get('mark') or {}).get('tone', note.get('tone')), '#376fa0'))
    if place.get('connection'):
        drawing.saveState()
        drawing.setStrokeColor(color); drawing.setStrokeAlpha(.42); drawing.setLineWidth(.45)
        path = drawing.beginPath()
        for i, (px, py) in enumerate(place['connection']['points']):
            pt = pdf_rectangle({'x': px, 'y': py, 'width': 0, 'height': 0}, transform)
            (path.moveTo if i == 0 else path.lineTo)(left+pt['x']*dw, bottom+(1-pt['y'])*dh)
        drawing.drawPath(path, stroke=1, fill=0); drawing.restoreState()
    for line in place['lines']:
        style = ParagraphStyle('point-line', fontName=font, fontSize=place['fontSize']*factor,
                               leading=line['height']*factor, textColor=color, spaceAfter=0,
                               splitLongWords=False)
        block = Paragraph(formatted_text(line['text']), style)
        _, h = block.wrap((line['width']+1)*factor, 1000)
        block.drawOn(drawing, x+line['x']*factor, top-line['y']*factor-h)
    return (x, top-place['rect']['height']*dh*t['height'],
            x+place['rect']['width']*dw*t['width'], top)


def export_pdf(packet, output):
    font = register_font()
    body = ParagraphStyle('body', fontName=font, fontSize=10, leading=14, textColor=colors.HexColor('#404954'), wordWrap='CJK', spaceAfter=3)
    heading = ParagraphStyle('heading', parent=body, fontSize=11, leading=16, textColor=colors.HexColor('#243443'), spaceAfter=4)
    writer, readers, audit = PdfWriter(), {}, []
    add_score_overview(writer, packet, font)
    sources = packet['pages'] + ([{'notes': packet['unplaced'], 'sourcePage': None}] if packet.get('unplaced') else [])
    for ordinal, source in enumerate(sources, 1):
        original, transform = None, None
        if source.get('originalPdf'):
            path = source['originalPdf']
            if path not in readers:
                readers[path] = PdfReader(path)
            original = copy.copy(readers[path].pages[source['sourcePage']-1])
            if original.rotation:
                oriented = PdfWriter(); original = oriented.add_page(original)
                original.transfer_rotation_to_content()
            sw, sh = float(original.cropbox.width), float(original.cropbox.height)
            transform = source.get('imageToPdf')
        elif source.get('image'):
            with Image.open(source['image']) as image:
                sw, sh = image.size
        else:
            sw, sh = A4
        pw, ph = landscape(A4) if sw > sh else A4
        margin, top, bottom_margin = 16, 32, 24
        scale = min((pw-2*margin)/sw, (ph-top-bottom_margin)/sh)
        dw, dh = sw*scale, sh*scale
        left, bottom = (pw-dw)/2, ph-top-dh
        page_label = f"答卷第 {ordinal} 页 / 原文件第 {source['sourcePage']} 页" if source.get('sourcePage') else '未定位的批注'
        title = ' '.join(f"{packet.get('student') or '答卷'} · 批改批注".split())
        while pdfmetrics.stringWidth(title, font, 10) > pw-220:
            title = title[:-2]+'…'

        interactive = []

        def finish(drawing, buffer, printed, continuation, include_source=False):
            drawing.setFont(font, 10); drawing.setFillColor(colors.HexColor('#34434c'))
            drawing.drawString(margin, ph-17, title)
            drawing.setFont(font, 8)
            drawing.drawRightString(pw-margin, ph-17, page_label + (f' · 续注 {continuation}' if continuation else ''))
            drawing.setFillColor(colors.HexColor('#737c86')); drawing.setFont(font, 7)
            drawing.drawString(margin, 10, '简短理由随卷打印 · 完整说明见 PDF 注释' + (' · 待审阅' if packet.get('status') != 'completed' else ''))
            drawing.drawRightString(pw-margin, 10, str(len(writer.pages)+1))
            drawing.save()
            sheet = PageObject.create_blank_page(width=pw, height=ph)
            if include_source and original:
                sheet.merge_transformed_page(original, Transformation().translate(-float(original.cropbox.left), -float(original.cropbox.bottom)).scale(scale).translate(left, bottom))
            sheet.merge_page(PdfReader(buffer).pages[0]); writer.add_page(sheet)
            if include_source and source.get('sourcePage'):
                writer.add_outline_item(f"答卷第 {ordinal} 页", len(writer.pages) - 1)
            for note, rect in interactive:
                add_detail_annotation(writer, len(writer.pages)-1, note, rect)
            interactive.clear()
            audit.append({'output_page': len(writer.pages), 'source_page': source.get('sourcePage'),
                          'workspace_page': source.get('id'), 'note_ids': list(dict.fromkeys(printed)),
                          'symbol_ids': [n['id'] for n in source['notes'] if n.get('symbolPlacement')] if include_source else [],
                          'grading_boxes': 0,
                          'continuation': continuation, 'source_width_points': dw if include_source else None,
                          'source_scale': scale if include_source and original else None})

        buffer = io.BytesIO(); drawing = canvas.Canvas(buffer, pagesize=(pw, ph))
        if not original and source.get('image'):
            drawing.drawImage(source['image'], left, bottom, dw, dh, preserveAspectRatio=True)
        printed, overflow = [], []
        for note in source['notes']:
            color = colors.HexColor(COLORS.get((note.get('mark') or {}).get('tone', note.get('tone')), '#376fa0'))
            drawing.setStrokeColor(color); drawing.setFillColor(color); drawing.setLineWidth(.55)
            # Scoring boxes are interactive screen affordances. Print only the
            # nearby check/cross and brief verdict; preserve teachers' own ink.
            for region in ([] if note.get('mark') else note.get('regions', [])):
                rect = pdf_rectangle(region['rect'], transform)
                x, y = left+rect['x']*dw, bottom+(1-rect['y']-rect['height'])*dh
                if region.get('shape') == 'lasso' and region.get('points'):
                    path = drawing.beginPath()
                    for i, (px, py) in enumerate(region['points']):
                        pt = pdf_rectangle({'x': px, 'y': py, 'width': 0, 'height': 0}, transform)
                        (path.moveTo if i == 0 else path.lineTo)(left+pt['x']*dw, bottom+(1-pt['y'])*dh)
                    path.close(); drawing.drawPath(path, fill=0, stroke=1)
                else:
                    drawing.rect(x, y, rect['width']*dw, rect['height']*dh, fill=0, stroke=1)
            draw_grading_symbol(drawing, note, transform, left, bottom, dw, dh)
            comment = note.get('commentPlacement') or {}
            if comment.get('mode') == 'inline':
                rect = draw_point_comment(drawing, note, font, transform, left, bottom, dw, dh, source['commentLayout'])
                interactive.append((note, rect))
                printed.append(note['id'])
            else:
                overflow.append(note)
        if overflow:
            drawing.setFont(font, 7); drawing.setFillColor(colors.HexColor('#737c86'))
            drawing.drawString(margin, 20, f'另有 {len(overflow)} 条评分说明见续页')
        finish(drawing, buffer, printed, 0, include_source=True)

        # Crowded pages keep their full size. Only the comments that genuinely
        # cannot fit safely continue, with explicit source-page and point IDs.
        pending = []
        for note in overflow:
            pending.extend((note, block) for block in visible_paragraphs(note, body, heading))
            pending.append((note, None))
        continuation = 0
        while pending:
            continuation += 1
            buffer = io.BytesIO(); drawing = canvas.Canvas(buffer, pagesize=(pw, ph))
            y, printed = ph-top, []
            while pending:
                note, block = pending[0]
                if block is None:
                    y -= 12; pending.pop(0); continue
                _, h = block.wrap(pw-2*margin, ph)
                available = y-bottom_margin
                if block.style is heading and available < 60 and y < ph-top:
                    break
                if h > available:
                    pieces = block.split(pw-2*margin, available)
                    if not pieces: break
                    block, *rest = pieces; pending[0:1] = [(note, piece) for piece in rest]
                    _, h = block.wrap(pw-2*margin, available)
                else:
                    pending.pop(0)
                block.drawOn(drawing, margin, y-h)
                interactive.append((note, (margin, y-h, pw-margin, y)))
                y -= h+block.style.spaceAfter; printed.append(note['id'])
            finish(drawing, buffer, printed, continuation)
    writer.add_metadata({'/Title': f"{packet.get('student', '答卷')} - 批改批注", '/Creator': 'GradeOS - deterministic nearby annotation export', '/Subject': 'Saved grading, local whitespace layout; no model call'})
    with open(output, 'wb') as stream:
        writer.write(stream)
    Path(str(output)+'.audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    export_pdf(json.loads(Path(args.input).read_text()), args.output)
