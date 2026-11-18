import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject,
                           NameObject, NumberObject)

from scripts.python.native_pages import complete_scan, prepare_pdf


def scan_pdf(path, images, overlay=False):
    writer = PdfWriter()
    for index, image in enumerate(images):
        page = writer.add_blank_page(width=300, height=420)
        stream = DecodedStreamObject()
        stream.set_data(image.tobytes())
        stream.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                       NameObject('/Width'): NumberObject(image.width), NameObject('/Height'): NumberObject(image.height),
                       NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
        resources = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/Scan'): writer._add_object(stream)})})
        text = b''
        if overlay:
            resources[NameObject('/Font')] = DictionaryObject({NameObject('/F1'): DictionaryObject({
                NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})})
            text = b'BT /F1 14 Tf 10 10 Td (Added margin note) Tj ET'
        page[NameObject('/Resources')] = resources
        contents = DecodedStreamObject()
        # Different page placements must not share a single guessed transform.
        contents.set_data(f'q 200 0 0 {280-index*10} 20 {100+index*10} cm /Scan Do Q\n'.encode()+text)
        page[NameObject('/Contents')] = writer._add_object(contents)
    with path.open('wb') as output:
        writer.write(output)


class NativePageTests(unittest.TestCase):
    def test_complete_scans_keep_tiny_edge_marks_all_pixels_and_page_specific_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);images=[]
            for size in [(2000,2800),(1800,2500)]:
                image=Image.new('RGB',size,'white')
                for position,color in [((0,0),(1,2,3)),((size[0]-1,size[1]-1),(254,253,252)),((100,40),(0,0,0))]:
                    image.putpixel(position,color)
                images.append(image)
            path=base/'input.pdf';scan_pdf(path,images)
            pages=prepare_pdf(path,base/'native')
            self.assertEqual([p['page'] for p in pages],[1,2])
            for source,row in zip(images,pages):
                with Image.open(base/'native'/row['path']) as result:
                    self.assertEqual(result.size,source.size)
                    self.assertEqual(result.tobytes(),source.tobytes())
                self.assertTrue(row['source_pixels_preserved'])
                self.assertEqual(row['source_rgb_sha256'],hashlib.sha256(source.tobytes()).hexdigest())
            self.assertAlmostEqual(pages[0]['image_to_pdf']['y'],40/420)
            self.assertAlmostEqual(pages[1]['image_to_pdf']['height'],270/420)
            small=prepare_pdf(path,base/'comparison',1400)
            self.assertEqual(small[0]['size'],[1000,1400])
            self.assertFalse(small[0]['source_pixels_preserved'])
            self.assertEqual(small[0]['image_to_pdf'],pages[0]['image_to_pdf'])

    def test_extra_page_text_is_rendered_instead_of_discarded_by_image_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path=base/'with-note.pdf'
            scan_pdf(path,[Image.new('RGB',(200,280),'white')],overlay=True)
            self.assertIsNone(complete_scan(PdfReader(path).pages[0]))
            row=prepare_pdf(path,base/'output')[0]
            self.assertEqual(row['representation'],'complete_pdf_render')
            with Image.open(base/'output'/row['path']) as image:
                # The only painted content is outside the scan's PDF rectangle.
                self.assertNotEqual(image.getextrema(),((255,255),(255,255),(255,255)))

    def test_rotation_clipping_or_annotations_cannot_silently_extract_only_the_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'input.pdf';scan_pdf(path,[Image.new('RGB',(20,28),'white')])
            page=PdfReader(path).pages[0]
            page[NameObject('/Rotate')]=NumberObject(90)
            self.assertIsNone(complete_scan(page))
            page[NameObject('/Rotate')]=NumberObject(0)
            page[NameObject('/Annots')]=ArrayObject([DictionaryObject({NameObject('/Subtype'):NameObject('/Text')})])
            self.assertIsNone(complete_scan(page))
            del page['/Annots']
            content=DecodedStreamObject();content.set_data(b'q 0 0 10 10 re W n /Scan Do Q')
            page[NameObject('/Contents')]=content
            self.assertIsNone(complete_scan(page))

    def test_mixed_pdf_render_uses_the_same_visible_cropbox_coordinate_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source=base/'source.pdf'
            scan_pdf(source,[Image.new('RGB',(200,280),'white')],overlay=True)
            page=PdfReader(source).pages[0]
            page[NameObject('/CropBox')]=ArrayObject([NumberObject(n) for n in [10,20,290,400]])
            writer=PdfWriter();writer.add_page(page)
            path=base/'cropped-view.pdf'
            with path.open('wb') as output:
                writer.write(output)
            row=prepare_pdf(path,base/'output')[0]
            self.assertEqual(row['size'],[1167,1584])
            self.assertEqual(row['pdf_crop_box'],[10,20,290,400])
            self.assertEqual(row['image_to_pdf'],{'x':0,'y':0,'width':1,'height':1})

    def test_uploaded_image_adapter_keeps_native_dimensions_and_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source=Image.new('RGB',(2100,2900),'white')
            source.putpixel((2099,2899),(1,2,3));source.save(base/'source.png')
            output=base/'upload';output.mkdir()
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/python/workspace_documents.py'),
                            '--source',str(base/'source.png'),'--output',str(output)],check=True)
            row=json.loads((output/'manifest.json').read_text())['pages'][0]
            self.assertEqual(row['size'],[2100,2900])
            with Image.open(output/row['path']) as result:
                self.assertEqual(result.tobytes(),source.tobytes())


if __name__ == '__main__':
    unittest.main()
