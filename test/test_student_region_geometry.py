import unittest
from PIL import Image, ImageDraw

from scripts.python import student_region_geometry as geometry


class LocalInkGeometryTest(unittest.TestCase):
    def sheet(self,scale=1,offset=0,dotted=False):
        image=Image.new('RGB',(1000*scale,1400*scale),'white');d=ImageDraw.Draw(image)
        for y in range(180+offset,1200+offset,100):
            if dotted:
                for x in range(100,901,5):d.line((x*scale,y*scale,(x+3)*scale,y*scale),fill='black',width=scale)
            else:d.line((100*scale,y*scale,900*scale,y*scale),fill='black',width=scale)
        return image,d

    def test_fraction_completion_across_scale_spacing_and_translation(self):
        for scale,offset,dotted in [(1,0,False),(2,0,False),(1,23,True),(2,23,True)]:
            image,d=self.sheet(scale,offset,dotted)
            # OCR sees the numerator only; local source ink contains denominator.
            for box in [(300,225,360,240),(290,248,370,250),(315,257,347,272),
                        (300,325,380,345)]:
                x1,y1,x2,y2=box;d.rectangle((x1*scale,(y1+offset)*scale,x2*scale,(y2+offset)*scale),fill='black')
            rows=[{'rect':[.30,(225+offset)/1400,.06,15/1400],'candidates':[{'text':'neutral numerator'}]},
                  {'rect':[.30,(325+offset)/1400,.08,20/1400],'candidates':[{'text':'next distinct step'}]}]
            result,report=geometry.complete_regions(image,rows)
            target=next(r for r in result if r.get('ocr_rows')==[0])
            self.assertIn('writing-bands',report['mode'])
            self.assertGreaterEqual(target['rect'][1]+target['rect'][3],(272+offset)/1400)
            self.assertLess(target['rect'][1]+target['rect'][3],(325+offset)/1400)

    def test_separate_margin_block_does_not_join_main_calculation(self):
        image,d=self.sheet()
        d.rectangle((200,225,360,260),fill='black');d.rectangle((780,225,850,260),fill='black')
        rows=[{'rect':[x/1000,225/1400,w/1000,35/1400],'candidates':[{'text':'unrelated text'}]} for x,w in [(200,160),(780,70)]]
        result,_=geometry.complete_regions(image,rows)
        self.assertEqual(len(result),2)
        self.assertTrue(all(r['rect'][2]<.2 for r in result))

    def test_whitespace_keeps_disjoint_boxes_within_one_line(self):
        image,d=self.sheet()
        for x in [200,350]:d.rectangle((x,225,x+60,260),fill='black')
        rows=[{'rect':[.2,225/1400,.21,35/1400],'candidates':[{'text':'two fragments'}]}]
        result,_=geometry.complete_regions(image,rows)
        self.assertEqual(len(result[0]['rects']),2)
        self.assertLess(sum(r[2] for r in result[0]['rects']),result[0]['rect'][2])

    def test_denominator_tail_crossing_printed_baseline_is_preserved(self):
        image,d=self.sheet()
        d.rectangle((300,225,350,240),fill='black')
        d.line((310,257,318,287),fill='black',width=3)
        rows=[{'rect':[.3,225/1400,.05,15/1400],'candidates':[{'text':'numerator only'}]}]
        result,_=geometry.complete_regions(image,rows)
        self.assertGreaterEqual(result[0]['rect'][1]+result[0]['rect'][3],287/1400)
        self.assertLess(result[0]['rect'][2],.1)

    def test_unruled_and_isolated_bars_do_not_invent_a_grid(self):
        image=Image.new('RGB',(1000,1400),'white');d=ImageDraw.Draw(image)
        for y in [350,700]:d.line((100,y,900,y),fill='black',width=2)
        rows=[{'rect':[.2,.2,.1,.03],'candidates':[{'text':'unreadable'}]}]
        result,report=geometry.complete_regions(image,rows)
        self.assertEqual(result,rows);self.assertEqual(report['mode'],'ocr-unruled')

    def test_different_text_and_ocr_confidence_do_not_change_geometry(self):
        image,d=self.sheet();d.rectangle((300,225,360,270),fill='black')
        rows=[{'rect':[.3,225/1400,.06,20/1400],'candidates':[{'text':'History 1492','confidence':1}]}]
        a,_=geometry.complete_regions(image,rows)
        rows[0]['candidates']=[{'text':'incorrect or ambiguous','confidence':.01}]
        b,_=geometry.complete_regions(image,rows)
        self.assertEqual(a[0]['rects'],b[0]['rects'])


if __name__=='__main__':unittest.main()
