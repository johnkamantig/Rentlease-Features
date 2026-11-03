"""Real image fixtures; small patched limits exercise large-image failure paths."""
import io
import struct
import tempfile
import unittest
import warnings
import zlib
from pathlib import Path
from unittest.mock import patch

from PIL import Image, PngImagePlugin
import processor
from processor import PanoramaError, process_panorama


def image_bytes(size=(1024, 512), format='PNG', **options):
    with Image.new('RGB', size, (28, 83, 118)) as im:
        out = io.BytesIO()
        im.save(out, format=format, **options)
        return out.getvalue()


def png_header(width, height):
    """A header-only bomb: rejection must happen without allocating its pixels."""
    payload = b'IHDR' + struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + payload + struct.pack('>I', zlib.crc32(payload)) + b'\x00\x00\x00\x00IDAT'


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.uploads = Path(self.temp.name) / 'uploads'

    def process(self, data, **options):
        return process_panorama(data, self.uploads, **options)

    def assert_rejected(self, data, message):
        with self.assertRaisesRegex(PanoramaError, message):
            self.process(data)
        self.assertFalse(self.uploads.exists())

    def assert_format(self, format):
        data = image_bytes(format=format)
        result = self.process(data)
        self.assertRegex(result.filename, r'^[a-f0-9]{32}\.jpg$')
        self.assertEqual(result.source_bytes, len(data))
        self.assertEqual(result.output_bytes, (self.uploads / result.filename).stat().st_size)
        self.assertLess(result.output_bytes, 10 * 1024 * 1024)
        self.assertEqual(result.as_dict()['url'], '/uploads/' + result.filename)
        with Image.open(self.uploads / result.filename) as out:
            out.load()
            self.assertEqual(out.format, 'JPEG')
            self.assertEqual(out.mode, 'RGB')
            self.assertEqual(out.size, (1024, 512))

    def test_supported_jpeg(self):
        self.assert_format('JPEG')

    def test_supported_png(self):
        self.assert_format('PNG')

    def test_supported_webp(self):
        self.assert_format('WEBP')

    def test_reject_other_formats(self):
        for format in ('GIF', 'BMP', 'TIFF'):
            with self.subTest(format=format):
                self.assert_rejected(image_bytes(format=format), 'JPEG, PNG, or WebP')

    def test_resize_large_to_mobile_friendly_width(self):
        result = self.process(image_bytes((6000, 3000)))
        self.assertEqual((result.width, result.height), (4096, 2048))

    def test_resize_preserves_nonexact_aspect_ratio(self):
        result = self.process(image_bytes((4200, 2107)))
        self.assertEqual((result.width, result.height), (4096, round(2107 * 4096 / 4200)))
        self.assertNotEqual(result.height, 2048)

    def test_does_not_upscale(self):
        result = self.process(image_bytes((1200, 600)))
        self.assertEqual((result.width, result.height), (1200, 600))

    def test_aspect_ratio_boundaries(self):
        for width in (1960, 2040):
            with self.subTest(width=width):
                self.assertEqual(self.process(image_bytes((width, 1000))).width, width)

    def test_accept_horizontal_and_other_image_proportions(self):
        for size in ((1959, 1000), (2041, 1000), (1200, 800), (4096, 512), (1024, 1024), (768, 1536)):
            with self.subTest(size=size):
                result = self.process(image_bytes(size))
                self.assertEqual((result.width, result.height), size)

    def test_portrait_resize_bounds_both_dimensions(self):
        result = self.process(image_bytes((1500, 6000)))
        self.assertEqual((result.width, result.height), (1024, 4096))

    def test_short_side_limit(self):
        self.assert_rejected(image_bytes((3000, 255)), 'too small')
        self.assertEqual(self.process(image_bytes((3000, 256))).height, 256)

    def test_wide_supported_formats_preserve_shape_and_remove_metadata(self):
        exif = Image.Exif()
        exif[270] = 'private-source-description'
        for format in ('JPEG', 'PNG', 'WEBP'):
            with self.subTest(format=format):
                result = self.process(image_bytes((3600, 900), format, exif=exif))
                with Image.open(self.uploads / result.filename) as out:
                    self.assertEqual(out.size, (3600, 900))
                    self.assertEqual(len(out.getexif()), 0)
                self.assertLess(result.output_bytes, processor.MAX_OUTPUT_BYTES)

    def test_reject_too_small(self):
        self.assert_rejected(image_bytes((1022, 511)), 'too small')

    def test_reject_unreadable(self):
        self.assert_rejected(b'not an image', 'Cannot decode')

    def test_reject_empty(self):
        self.assert_rejected(b'', 'empty')

    def test_input_byte_limit(self):
        data = image_bytes()
        with patch.object(processor, 'MAX_INPUT_BYTES', len(data) - 1):
            self.assert_rejected(data, '25 MiB')
        with patch.object(processor, 'MAX_INPUT_BYTES', len(data)):
            self.process(data)

    def test_real_input_byte_limit(self):
        self.assert_rejected(b'x' * (25 * 1024 * 1024 + 1), '25 MiB')

    def test_pixel_limit_before_decode(self):
        self.assert_rejected(png_header(10000, 5000), '40 million')

    def test_pixel_limit_boundary(self):
        data = image_bytes()
        with patch.object(processor, 'MAX_DECODED_PIXELS', 1024 * 512 - 1):
            self.assert_rejected(data, '40 million')
        with patch.object(processor, 'MAX_DECODED_PIXELS', 1024 * 512):
            self.process(data)

    def test_decompression_warning_is_error(self):
        data = image_bytes()
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 400000), warnings.catch_warnings(record=True) as caught:
            self.assert_rejected(data, 'safe decoded pixel')
            self.assertEqual(caught, [])

    def test_decompression_bomb_error(self):
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 200000):
            self.assert_rejected(image_bytes(), 'safe decoded pixel')

    def test_corrupt_truncated_supported_formats(self):
        for format in ('JPEG', 'PNG', 'WEBP'):
            data = image_bytes(format=format)
            with self.subTest(format=format):
                self.assert_rejected(data[:len(data) // 2], 'Cannot decode')

    def test_corrupt_png_checksum(self):
        data = bytearray(image_bytes())
        idat = data.index(b'IDAT')
        length = struct.unpack('>I', data[idat - 4:idat])[0]
        data[idat + 4 + length] ^= 1
        self.assert_rejected(bytes(data), 'Cannot decode')

    def test_reject_animated_png_and_webp(self):
        for format in ('PNG', 'WEBP'):
            with self.subTest(format=format), Image.new('RGB', (1024, 512), 'red') as first, Image.new('RGB', (1024, 512), 'blue') as second:
                out = io.BytesIO()
                first.save(out, format=format, save_all=True, append_images=[second], duration=100, loop=0)
                self.assert_rejected(out.getvalue(), 'Animated or multi-frame')

    def test_orientation_applied_without_forcing_aspect_ratio(self):
        exif = Image.Exif()
        exif[274] = 6
        result = self.process(image_bytes((512, 1024), 'JPEG', exif=exif))
        self.assertEqual((result.width, result.height), (1024, 512))
        with Image.open(self.uploads / result.filename) as out:
            self.assertEqual(len(out.getexif()), 0)

    def test_remove_exif_gps_xmp_icc_comments(self):
        exif = Image.Exif()
        exif[270] = 'private-source-description'
        exif[34853] = {1: 'N', 2: (22.0, 15.0, 0.0), 3: 'E', 4: (114.0, 10.0, 0.0)}
        for format in ('JPEG', 'PNG', 'WEBP'):
            with self.subTest(format=format):
                data = image_bytes(format=format, exif=exif, icc_profile=b'private-source-profile', xmp=b'private-source-xmp', comment=b'private-source-comment')
                with Image.open(io.BytesIO(data)) as source:
                    self.assertIn(34853, source.getexif())
                    self.assertIn('icc_profile', source.info)
                result = self.process(data)
                output = (self.uploads / result.filename).read_bytes()
                self.assertNotIn(b'private-source', output)
                with Image.open(io.BytesIO(output)) as out:
                    self.assertEqual(len(out.getexif()), 0)
                    for key in ('exif', 'xmp', 'icc_profile', 'comment'):
                        self.assertNotIn(key, out.info)

    def test_remove_png_text(self):
        info = PngImagePlugin.PngInfo()
        info.add_text('Location', 'private-location')
        info.add_itxt('XML:com.adobe.xmp', 'private-xmp')
        result = self.process(image_bytes(pnginfo=info))
        self.assertNotIn(b'private-', (self.uploads / result.filename).read_bytes())

    def test_alpha_is_composited_on_white(self):
        for format in ('PNG', 'WEBP'):
            with self.subTest(format=format), Image.new('RGBA', (1024, 512), (255, 0, 0, 0)) as im:
                out = io.BytesIO()
                im.save(out, format=format)
                result = self.process(out.getvalue())
                with Image.open(self.uploads / result.filename) as jpeg:
                    self.assertEqual(jpeg.getpixel((0, 0)), (255, 255, 255))

    def test_palette_transparency_is_composited_on_white(self):
        with Image.new('P', (1024, 512), 0) as im:
            out = io.BytesIO()
            im.save(out, format='PNG', transparency=0)
            result = self.process(out.getvalue())
        with Image.open(self.uploads / result.filename) as jpeg:
            self.assertEqual(jpeg.getpixel((0, 0)), (255, 255, 255))

    def test_invalid_maximum_width(self):
        for width in (0, 1023, 1025, 4098, 1024.0, None):
            with self.subTest(width=width), self.assertRaisesRegex(PanoramaError, 'configured maximum'):
                self.process(image_bytes(), max_width=width)

    def test_output_limit_is_strict_and_retries_quality(self):
        original_save = Image.Image.save
        qualities = []
        def fake_save(im, fp, format=None, **options):
            if format == 'JPEG':
                qualities.append(options['quality'])
                fp.write(b'x' * (100 if len(qualities) == 1 else 99))
            else:
                original_save(im, fp, format=format, **options)
        data = image_bytes()
        with patch.object(processor, 'MAX_OUTPUT_BYTES', 100), patch.object(Image.Image, 'save', fake_save):
            result = self.process(data)
        self.assertEqual(qualities, [86, 80])
        self.assertEqual(result.output_bytes, 99)
        self.assertEqual(result.jpeg_quality, 80)

    def test_output_compression_failure_leaves_no_file(self):
        with patch.object(processor, 'MAX_OUTPUT_BYTES', 1):
            self.assert_rejected(image_bytes(), 'below 10 MiB')

    def test_encode_error_is_clean(self):
        data = image_bytes()
        with patch.object(Image.Image, 'save', side_effect=OSError('private detail')):
            self.assert_rejected(data, 'Cannot optimize')

    def test_failed_atomic_write_cleans_temporary_file(self):
        with patch.object(Path, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.process(image_bytes())
        self.assertEqual(list(self.uploads.iterdir()), [])

    def test_names_are_unique(self):
        first, second = self.process(image_bytes()), self.process(image_bytes())
        self.assertNotEqual(first.filename, second.filename)


if __name__ == '__main__':
    unittest.main()
