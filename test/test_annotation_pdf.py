import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas

from annotation_pdf import export_pdf, pdf_rectangle


class AnnotationPdfTests(unittest.TestCase):
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
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            audit = json.loads(Path(str(output) + '.audit.json').read_text())
            self.assertTrue(all(page['source_page'] == 1 for page in audit))


if __name__ == '__main__':
    unittest.main()
