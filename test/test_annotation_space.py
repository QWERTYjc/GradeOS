import base64
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from annotation_space import page_occupancy, comment_glyph_widths
from annotation_pdf import register_font, formatted_text
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph


class AnnotationSpaceTests(unittest.TestCase):
    def test_two_line_js_excerpts_do_not_rewrap_when_printed_with_an_added_ellipsis(self):
        font = register_font()
        note = {'id': 'point', 'mark': {'text': '1M'}, 'regions': [],
                'reason': 'The approach is correct but the final substitution does not match the required value.'}
        script = """
          import {layoutPointComments} from './web/annotation-layout.mjs';
          let raw='';for await(const part of process.stdin)raw+=part;
          const {note,widths}=JSON.parse(raw);
          const [placement]=layoutPointComments([note],null,{width:260,height:400,fontSize:13,
            measureText:text=>[...text].reduce((sum,c)=>sum+(widths[c]??.7)*13,0)});
          console.log(JSON.stringify(placement));
        """
        placement = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script],
            input=json.dumps({'note': note, 'widths': comment_glyph_widths([note], font)}).encode()))
        self.assertTrue(placement['truncated'])
        self.assertEqual(len(placement['lines']), 2)
        self.assertTrue(placement['lines'][-1]['text'].endswith('…'))
        style = ParagraphStyle('line', fontName=font, fontSize=13, leading=16.25, splitLongWords=False)
        for line in placement['lines']:
            block = Paragraph(formatted_text(line['text']), style)
            self.assertLessEqual(block.wrap(line['width'] + 1, 1000)[1], 16.25)

    def test_python_and_browser_masks_match_including_partial_edge_cells_and_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'page.png'
            image = Image.new('RGBA', (773, 1103), 'white')
            dots = [(33, 77, (244, 244, 244, 255)), (772, 1102, (255, 0, 255, 255)),
                    (150, 150, (0, 0, 0, 0)), (130, 130, (0, 0, 0, 11)),
                    (270, 270, (0, 0, 0, 10))]
            for x, y, color in dots:
                image.putpixel((x, y), color)
            image.save(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            mask = page_occupancy(path, digest)
            script = """
              import {occupancyFromRgba} from './web/annotation-layout.mjs';
              let raw='';for await(const part of process.stdin)raw+=part;
              const {w,h,dots}=JSON.parse(raw),pixels=new Uint8ClampedArray(w*h*4).fill(255);
              for(const [x,y,rgba] of dots)pixels.set(rgba,(y*w+x)*4);
              const mask=occupancyFromRgba(pixels,w,h),packed=Buffer.alloc(Math.ceil(mask.occupied.length/8));
              mask.occupied.forEach((v,i)=>{if(v)packed[i>>3]|=1<<(i%8)});
              console.log(packed.toString('base64'));
            """
            browser_mask = subprocess.check_output(['node', '--input-type=module', '-e', script],
                                                   input=json.dumps({'w': 773, 'h': 1103, 'dots': dots}).encode()).decode().strip()
            self.assertEqual(mask['occupiedBase64'], browser_mask)
            bits = base64.b64decode(browser_mask)
            self.assertEqual(sum(value.bit_count() for value in bits), 3)
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                page_occupancy(path, 'wrong')


if __name__ == '__main__':
    unittest.main()
