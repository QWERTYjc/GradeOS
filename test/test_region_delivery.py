import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from scripts.python.local_text_regions import line_rows


class RegionDeliveryTest(unittest.TestCase):
    def test_optical_word_boxes_join_by_source_line(self):
        header = 'level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\ttext\n'
        words = '5\t1\t1\t1\t10\t4\t20\t6\tCu\n5\t1\t1\t1\t35\t4\t10\t6\twire\n5\t2\t1\t1\t70\t4\t10\t8\tAg'
        rows = line_rows(header + words, 100, 100)
        self.assertEqual(rows[0]['candidates'][0]['text'], 'Cu wire')
        self.assertEqual(rows[0]['rect'], [.1, .04, .35, .06])
        self.assertEqual(len(rows), 2)

    def test_only_gutter_pixels_can_change(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            original = Image.new('RGB', (910, 1420), 'white')
            for x in (0, 275, 909):
                for y in range(original.height):
                    original.putpixel((x, y), (27, 35, 42))
            source = root / 'page.png'
            original.save(source)
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            (root/'documents.json').write_text(json.dumps({'s': {'sha256':'doc', 'pages':[{'page':1,'absolute_path':str(source),'sha256':sha}]}}))
            region = {'id':'i1.r1','rect':{'x':0,'y':.14,'width':1,'height':.82}}
            (root/'catalog.json').write_text(json.dumps({'documents':{'s':{'source_sha256':'doc','manifest_sha256':'a'*64,'pages':[{'page':1,'source_sha256':sha,'regions':[region]}]}}}))
            for side in (0, 960):
                out = root / str(side)
                subprocess.run([sys.executable, str(Path(__file__).parents[1]/'scripts/python/student_region_images.py'),
                                '--documents',str(root/'documents.json'),'--catalog',str(root/'catalog.json'),'--output',str(out),'--max-side',str(side)],check=True,capture_output=True)
                delivery = json.loads((out/'manifest.json').read_text())['documents']['s']['pages'][0]
                with Image.open(delivery['absolute_path']) as shown:
                    pixels = shown.crop(delivery['source_rect_in_image'])
                    expected = original.copy()
                    if side:
                        expected.thumbnail((side - 2 * round(side * .031), side), Image.Resampling.LANCZOS)
                    self.assertEqual(pixels.size, expected.size)
                    self.assertEqual(pixels.tobytes(), expected.tobytes())
                    self.assertTrue(shown.width > expected.width)
