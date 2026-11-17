import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas

from annotation_pdf import export_pdf, pdf_rectangle, formatted_text


class AnnotationPdfTests(unittest.TestCase):
    def test_score_overview_and_vector_ticks_replace_permanent_grading_boxes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source.png'
            Image.new('RGB', (700, 1000), 'white').save(source)
            note = {'id': 'G1', 'label': 'Q1 M1', 'reason': 'Full reason',
                    'mark': {'text': '1M', 'tone': 'credit'},
                    'regions': [{'rect': {'x': .2, 'y': .3, 'width': .3, 'height': .04}}],
                    'symbolPlacement': {'rect': {'x': .51, 'y': .3, 'width': .025, 'height': .017},
                        'symbol': {'tone': 'credit', 'stroke': 1.6, 'paths': [[[2, 10], [7, 15], [18, 3]]]}},
                    'commentPlacement': {'mode': 'inline', 'fontSize': 13,
                        'rect': {'x': .6, 'y': .3, 'width': .3, 'height': .04},
                        'lines': [{'text': '1M · Correct method', 'width': 170, 'x': 3, 'y': 3, 'height': 16.25}]}}
            output = root / 'symbols.pdf'
            export_pdf({'student': 'Student', 'resultSummary': {'score': '1 / 1', 'provisional': True,
                         'items': [{'id': f'Q{i}', 'score': '1 / 1', 'pages': [1]} for i in range(40)]},
                        'pages': [{'id': 'p', 'image': str(source), 'sourcePage': 1,
                                   'commentLayout': {'width': 700, 'height': 1000}, 'notes': [note]}]}, output)
            reader = PdfReader(output)
            self.assertEqual(len(reader.pages), 3)
            self.assertIn('评分结果', reader.pages[0].extract_text())
            self.assertIn('Q39', reader.pages[1].extract_text())
            color, colored_rectangles, colored_lines = None, 0, 0
            for operands, operator in reader.pages[-1].get_contents().operations:
                if operator == b'RG':
                    color = tuple(float(v) for v in operands)
                green = color and abs(color[0] - 35/255) < .001 and abs(color[1] - 132/255) < .001
                if green and operator == b're': colored_rectangles += 1
                if green and operator == b'l': colored_lines += 1
            self.assertEqual(colored_rectangles, 0)
            self.assertGreaterEqual(colored_lines, 2)
            self.assertEqual(reader.pages[-1].extract_text().count('1M'), 1)
            self.assertIn('Full reason', reader.pages[-1]['/Annots'][0].get_object()['/Contents'])

    def test_short_printed_reasons_keep_complete_records_in_closed_clickable_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'source.png'
            Image.new('RGB', (700, 1000), 'white').save(image)
            full_reason = 'A long verdict. ' * 200 + 'END_OF_REASON'
            note = {'id': 'G1', 'label': 'Q1 M1', 'tone': 'deduction', 'regions': [],
                    'summary': '×M · Missing the required limit step.', 'reason': full_reason,
                    'condition': 'FULL_MS_ONLY_IN_DETAILS', 'evidence': 'ORIGINAL_TRANSCRIPTION',
                    'uncertainties': ['UNRESOLVED_QUESTION'], 'locationNote': 'LOCATION_WARNING',
                    'commentPlacement': {'mode': 'inline', 'fontSize': 13,
                        'rect': {'x': .6, 'y': .5, 'width': .3, 'height': .1},
                        'lines': [{'text': '×M · Missing the required limit step.', 'width': 260,
                                   'x': 3, 'y': 3, 'height': 16.25, 'kind': 'reason'}]}}
            overflow = {**note, 'id': 'G2', 'commentPlacement': {'mode': 'continuation'}}
            output = root / 'export.pdf'
            export_pdf({'pages': [{'id': 'p', 'sourcePage': 1, 'image': str(image),
                                  'commentLayout': {'width': 700, 'height': 1000},
                                  'notes': [note, overflow]}]}, output)
            pdf = PdfReader(output)
            self.assertEqual(len(pdf.pages), 2)
            visible = '\n'.join(page.extract_text() for page in pdf.pages)
            self.assertEqual(visible.count('Missing the required limit step.'), 2)
            self.assertNotIn('FULL_MS_ONLY_IN_DETAILS', visible)
            self.assertNotIn('END_OF_REASON', visible)
            annotations = [a.get_object() for page in pdf.pages for a in page.get('/Annots', [])]
            self.assertEqual([a['/NM'] for a in annotations], ['G1', 'G2'])
            for annotation in annotations:
                self.assertEqual(annotation['/Subtype'], '/Text')
                self.assertFalse(annotation['/Open'].value)
                self.assertEqual(annotation['/F'], 0)
                self.assertEqual(annotation['/AP']['/N'].get_data(), b'')
                for text in [full_reason, note['condition'], note['evidence'],
                             note['uncertainties'][0], note['locationNote']]:
                    self.assertIn(text, annotation['/Contents'])

    def test_nearby_comment_prints_on_full_width_source_without_a_side_column(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'source.png'
            Image.new('RGB', (700, 1000), 'white').save(image)
            note = {'id': 'G1', 'label': 'Point', 'tone': 'credit', 'regions': [],
                    'reason': 'COMPLETE_REASON_ONLY_IN_DETAILS',
                    'markPlacement': {'mode': 'inline', 'mark': {'text': '1M'}},
                    'commentPlacement': {'mode': 'inline', 'fontSize': 13,
                        'rect': {'x': .6, 'y': .5, 'width': .3, 'height': .1},
                        'lines': [{'text': '1M · Correct substitution.', 'width': 190, 'x': 3,
                                   'y': 3, 'height': 16.25, 'kind': 'reason'}]}}
            output = root / 'export.pdf'
            export_pdf({'pages': [{'id': 'p', 'sourcePage': 1, 'image': str(image),
                                  'commentLayout': {'width': 700, 'height': 1000},
                                  'notes': [note]}]}, output)
            pdf = PdfReader(output)
            self.assertEqual(len(pdf.pages), 1)
            visible = pdf.pages[0].extract_text()
            self.assertEqual(visible.count('1M'), 1)
            self.assertEqual(visible.count('Correct substitution.'), 1)
            self.assertNotIn('COMPLETE_REASON_ONLY_IN_DETAILS', visible)
            self.assertIn('COMPLETE_REASON_ONLY_IN_DETAILS', pdf.pages[0]['/Annots'][0].get_object()['/Contents'])
            audit = json.loads(Path(str(output) + '.audit.json').read_text())
            self.assertGreater(audit[0]['source_width_points'], 500)
            self.assertEqual(audit[0]['note_ids'], ['G1'])

    def test_legacy_mark_placements_do_not_duplicate_marks_in_printed_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'source.png'
            Image.new('RGB', (700, 1000), 'white').save(image)
            notes = []
            for index, text in enumerate(['1M', '×A', '✓']):
                mark = {'text': text, 'tone': 'deduction' if index == 1 else 'credit'}
                notes.append({'id': f'G{index+1}', 'label': f'point {index+1}', 'reason': f'REASON {index+1}',
                              'mark': mark, 'regions': [{'rect': {'x': .2, 'y': .2, 'width': .3, 'height': .03}}],
                              'markPlacement': {'mode': 'margin' if index == 1 else 'inline', 'marginColumn': 0,
                                                'fontSize': 16, 'reference': f'G{index+1}', 'mark': mark,
                                                'rect': {'x': .6, 'y': .2 + index * .1, 'width': .1, 'height': .028}}})
            notes.append({'id': 'G4', 'label': 'Unlocated', 'reason': 'No guess', 'regions': [], 'markPlacement': None})
            output = root / 'export.pdf'
            export_pdf({'student': 'Test', 'pages': [{'id': 'p', 'sourcePage': 1, 'image': str(image), 'notes': notes}]}, output)
            text = '\n'.join(page.extract_text() for page in PdfReader(output).pages)
            for mark in ['1M', '×A', '✓']:
                self.assertEqual(text.count(mark), 1)
            for index in range(1, 4):
                self.assertIn(f'REASON {index}', text)
            self.assertIn('No guess', text)

    def test_math_glyphs_preserve_super_and_subscript_without_missing_font_glyphs(self):
        self.assertEqual(formatted_text('eᵃ + x² + uₖ < 3'), 'e<super>a</super> + x<super>2</super> + u<sub>k</sub> &lt; 3')

    def test_native_image_context_uses_its_own_pdf_transform(self):
        rect = {'x': .25, 'y': .25, 'width': .5, 'height': .5}
        mapped = pdf_rectangle(rect, {'x': .1, 'y': .2, 'width': .8, 'height': .6})
        for key, expected in {'x': .3, 'y': .35, 'width': .4, 'height': .3}.items():
            self.assertAlmostEqual(mapped[key], expected)
        self.assertEqual(pdf_rectangle(rect), rect)

    def test_print_keeps_source_and_every_long_comment_with_cropbox_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / 'source.pdf'
            drawing = canvas.Canvas(str(original), pagesize=(300, 400))
            drawing.drawString(80, 100, 'ORIGINAL SOURCE')
            drawing.save()
            writer = PdfWriter()
            page = writer.add_page(PdfReader(original).pages[0])
            page.cropbox = RectangleObject((50, 60, 250, 360))
            page.rotate(90)
            with open(root / 'cropped.pdf', 'wb') as output:
                writer.write(output)
            source = root / 'cropped.pdf'
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            packet = {'student': '中文批注测试', 'status': 'needs_review', 'pages': [{
                'id': 'first', 'originalPdf': str(source), 'sourcePage': 1,
                'notes': [{'id': 'G1', 'label': '评分点', 'score': '待定', 'tone': 'review',
                           'locationNote': '部分引用区域未能定位，当前仅显示已匹配的框。',
                           'reason': ('中文说明和长注释 ABC ' * 450) + 'END_OF_COMMENT',
                           'regions': [{'rect': {'x': .2, 'y': .3, 'width': .2, 'height': .1}}]}]}]}
            output = root / 'export.pdf'
            export_pdf(packet, output)
            rendered = PdfReader(output)
            self.assertGreater(len(rendered.pages), 1)
            text = '\n'.join(page.extract_text() for page in rendered.pages)
            self.assertIn('END_OF_COMMENT', text)
            self.assertIn('中文批注测试', text)
            self.assertIn('ORIGINAL SOURCE', text)
            self.assertIn('部分引用区域未能定位', text)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            audit = json.loads(Path(str(output) + '.audit.json').read_text())
            self.assertTrue(all(page['source_page'] == 1 for page in audit))


if __name__ == '__main__':
    unittest.main()
