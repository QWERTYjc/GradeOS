import unittest
from PIL import Image
from student_images import exact_white_crop, source_grid


class ExactImageTests(unittest.TestCase):
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
