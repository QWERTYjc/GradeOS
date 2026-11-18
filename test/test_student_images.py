import unittest
from PIL import Image
from student_images import exact_white_crop, source_grid, resize_overview, original_region


class ExactImageTests(unittest.TestCase):
    def test_local_crop_matches_the_visible_frame_at_original_resolution(self):
        im = Image.new('RGB', (181, 279), 'white')
        im.putpixel((55, 84), (23, 42, 61))
        frame = (15, 53, 174, 256)
        crop = original_region(im, [250, 150, 500, 500], frame, local_only=True)
        expected = im.crop((54, 83, 135, 185))
        self.assertEqual(crop.size, expected.size)
        self.assertEqual(crop.tobytes(), expected.tobytes())
        for bounds in (None, frame):
            with self.assertRaisesRegex(ValueError, 'local region'):
                original_region(im, [0, 0, 999, 999], bounds, local_only=True)
        with self.assertRaisesRegex(ValueError, 'outside'):
            original_region(im, [1, 1, 50, 50], (5, 5, 200, 256), local_only=True)

    def test_regions_preserve_native_pixels_across_page_shapes_and_positions(self):
        for size in [(120, 200), (200, 120), (100, 100)]:
            im = Image.new('RGB', size, 'white')
            for xy in [(0, 0), (size[0]-1, size[1]-1), (size[0]//2, size[1]//2)]:
                im.putpixel(xy, (10, 20, 30))
            before = im.tobytes()
            for region, box in [([0,0,1000,1000],(0,0,*size)),
                                ([0,0,500,500],(0,0,size[0]//2,size[1]//2)),
                                ([500,500,500,500],(size[0]//2,size[1]//2,*size))]:
                self.assertEqual(original_region(im,region).tobytes(),im.crop(box).tobytes())
            self.assertEqual(im.tobytes(),before)
        for bad in [None,[],[0,0,0,1],[-1,0,1,1],[0,0,1001,1],[900,900,101,101],[0,0,1.5,2],[0,0,True,2]]:
            with self.assertRaises(ValueError):
                original_region(im,bad)

    def test_overview_preserves_extent_aspect_ratio_and_source_bytes(self):
        for size in [(1600, 2400), (2400, 1600), (80, 100), (1600, 1600)]:
            for mode in ['RGB', 'RGBA', 'L']:
                source = Image.new(mode, size, 'white')
                before = source.tobytes()
                shown = resize_overview(source, 1280)
                self.assertLessEqual(max(shown.size), 1280)
                self.assertLessEqual(abs(shown.width / shown.height - size[0] / size[1]), .002)
                self.assertEqual(source.tobytes(), before)
                self.assertEqual(source.size, size)
                if max(size) <= 1280:
                    self.assertEqual(shown.tobytes(), before)
        for bad in [0, -1, 1.5, True, None]:
            with self.assertRaises(ValueError):
                resize_overview(Image.new('RGB', (20, 30)), bad)

    def test_resize_is_lossy_and_does_not_claim_symbol_equivalence(self):
        source = Image.new('RGB', (1600, 2400), 'white')
        source.putpixel((800, 1200), (254, 255, 255))
        shown = resize_overview(source, 1280)
        self.assertNotEqual(shown.size, source.size)
        self.assertEqual(source.getpixel((800, 1200)), (254, 255, 255))

    def test_external_grid_retains_every_source_pixel_and_blank_page(self):
        for size in [(999, 1400), (1400, 701), (180, 300)]:
            im = Image.new('RGB', size, 'white')
            for color in [(255, 255, 255), (254, 255, 255), (0, 0, 0)]:
                im.putpixel((size[0]-1, size[1]-1), color)
                im.putpixel((0, 0), color)
                shown, box, grid = source_grid(im)
                self.assertEqual(shown.crop(box).tobytes(), im.tobytes())
                self.assertEqual(shown.crop(box).size, size)
                self.assertEqual(grid, {'columns': 10, 'rows': 40, 'version': 'source-grid-v1'})

    def test_faint_colored_boundary_footer_and_minus_pixels_are_retained(self):
        for offset in [0, 17, 53]:
            im = Image.new('RGB', (200, 260), 'white')
            for x, y, color in [(80+offset, 90, (0, 0, 0)), (20, 1, (254, 255, 255)),
                                (199, 120, (255, 254, 255)), (100, 259, (255, 255, 254))]:
                im.putpixel((x, y), color)
            cropped, bounds = exact_white_crop(im)
            restored = Image.new('RGB', im.size, 'white'); restored.paste(cropped, bounds[:2])
            self.assertEqual(restored.tobytes(), im.tobytes())

    def test_blank_pages_and_non_rgb_are_not_omitted_or_rescaled(self):
        for mode, color in [('RGB', 'white'), ('RGBA', (255, 255, 255, 0)), ('L', 255)]:
            im = Image.new(mode, (100, 130), color)
            cropped, bounds = exact_white_crop(im)
            self.assertEqual(bounds, (0, 0, 100, 130))
            self.assertEqual(cropped.tobytes(), im.tobytes())

    def test_translation_changes_only_white_padding_and_keeps_native_glyph_dimensions(self):
        im = Image.new('RGB', (300, 400), 'white')
        for x in range(110, 116):
            im.putpixel((x, 220), (1, 2, 3))
        cropped, bounds = exact_white_crop(im)
        self.assertLess(cropped.width * cropped.height, im.width * im.height)
        self.assertEqual(sum(p != (255, 255, 255) for p in cropped.getdata()), 6)
        self.assertEqual(cropped.getpixel((110-bounds[0], 220-bounds[1])), (1, 2, 3))


if __name__ == '__main__':
    unittest.main()
