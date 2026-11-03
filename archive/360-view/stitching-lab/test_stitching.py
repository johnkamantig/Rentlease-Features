import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
import zlib

import cv2 as cv
import numpy as np
from PIL import Image

from inputs import CaptureInput, InputError, MAX_PIXELS, parse_manifest, safe_name
from pipeline import StitchError, align, coverage_metrics, encode_jpeg, spherical_warp
from stitch import run
from synthetic import create_fixture, rotation
from partial_stitch import select_photos, run as run_partial
from types import SimpleNamespace
from hugin_reference import control_point_graph, run as run_hugin


class InputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temporary.name) / 'capture'
        create_fixture(cls.path, partial=True, width=160, height=120)
        cls.raw = (cls.path / 'manifest.json').read_bytes()
        cls.manifest = json.loads(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def parse_changed(self, change):
        manifest = copy.deepcopy(self.manifest)
        change(manifest)
        return parse_manifest(json.dumps(manifest))

    def test_folder_discovery_and_decode(self):
        source = CaptureInput(self.path)
        self.assertEqual([p['order'] for p in source.manifest['photos']], [1, 2, 3, 4])
        self.assertEqual(source.image(source.manifest['photos'][0]).shape, (120, 160, 3))

    def test_zip_discovery_and_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'capture.zip'
            with zipfile.ZipFile(file, 'w') as archive:
                for path in self.path.rglob('*'):
                    if path.is_file():
                        archive.write(path, path.relative_to(self.path).as_posix())
            source = CaptureInput(file)
            try:
                self.assertEqual(source.image(source.manifest['photos'][0]).shape, (120, 160, 3))
            finally:
                source.close()

    def test_manifest_invalid_json(self):
        with self.assertRaises(InputError): parse_manifest('{')

    def test_malformed_nested_types(self):
        for change in (lambda m: m.update(session=[]), lambda m: m['photos'].__setitem__(0, []),
                       lambda m: m['photos'][0].update(order=True), lambda m: m['photos'][0].update(id=[])):
            with self.subTest(change=change), self.assertRaises(InputError): self.parse_changed(change)

    def test_size_limit(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'][0].update(bytes=51 * 1024**2))

    def test_approximate_orientation_required(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'][0]['orientation'].update(alignmentValidated=True))

    def test_duplicate_json_key(self):
        with self.assertRaises(InputError): parse_manifest('{"a":1,"a":2}')

    def test_nonfinite_json(self):
        with self.assertRaises(InputError): parse_manifest('{"a":NaN}')

    def test_manifest_version(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m.update(exportVersion=2))

    def test_incomplete_session(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['session'].update(status='paused'))

    def test_order_mismatch(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'].reverse())

    def test_duplicate_photo(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'].__setitem__(1, m['photos'][0]))

    def test_invalid_dimensions(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'][0].update(width=0))

    def test_pixel_limit(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'][0].update(width=MAX_PIXELS))

    def test_metadata_disagreement(self):
        with self.assertRaises(InputError): self.parse_changed(lambda m: m['photos'][0].update(savedAt='different'))

    def test_source_path_restrictions(self):
        for name in ('../a.jpg', '/a.jpg', 'C:/a.jpg', 'images/../a.jpg', 'images\\a.jpg', 'images/%2e%2e.jpg'):
            with self.subTest(name=name), self.assertRaises(InputError): safe_name(name)

    def test_zip_traversal_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(file, 'w') as archive: archive.writestr('../outside.jpg', b'bad')
            with self.assertRaises(InputError): CaptureInput(file)
            self.assertFalse((Path(directory) / 'outside.jpg').exists())

    def test_zip_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as directory, warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            file = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(file, 'w') as archive:
                archive.writestr('manifest.json', self.raw)
                archive.writestr('manifest.json', self.raw)
            with self.assertRaises(InputError): CaptureInput(file)

    def test_missing_images(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'manifest.json').write_bytes(self.raw)
            with self.assertRaisesRegex(InputError, 'Missing'): CaptureInput(directory)

    def test_wrong_checksum(self):
        source = CaptureInput(self.path)
        photo = {**source.manifest['photos'][0], 'crc32': '00000000'}
        with self.assertRaisesRegex(InputError, 'CRC'): source.image(photo)

    def test_corrupt_jpeg_with_valid_checksum(self):
        source = CaptureInput(self.path)
        raw = b'not a JPEG'
        photo = {**source.manifest['photos'][0], 'bytes': len(raw), 'crc32': f'{zlib.crc32(raw):08x}'}
        with patch.object(source, 'read', return_value=raw), self.assertRaisesRegex(InputError, 'decoding'): source.image(photo)

    def test_truncated_jpeg(self):
        source = CaptureInput(self.path)
        raw = source.read(source.manifest['photos'][0]['path'])[:-100]
        photo = {**source.manifest['photos'][0], 'bytes': len(raw), 'crc32': f'{zlib.crc32(raw):08x}'}
        with patch.object(source, 'read', return_value=raw), self.assertRaises(InputError): source.image(photo)

    def test_header_dimensions_disagree(self):
        source = CaptureInput(self.path)
        photo = {**source.manifest['photos'][0], 'width': 161}
        with self.assertRaisesRegex(InputError, 'Dimensions'): source.image(photo)

    def test_validate_cli_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            self.assertEqual(run(self.path, output, validate_only=True), 0)
            self.assertFalse(json.loads((output / 'report.json').read_text())['full_sphere_verified'])

    def test_processing_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory, patch('stitch.align', side_effect=StitchError('deliberate failure')):
            output = Path(directory) / 'run'
            self.assertEqual(run(self.path, output), 2)
            self.assertEqual(json.loads((output / 'report.json').read_text())['error'], 'deliberate failure')
            self.assertFalse((output / 'candidate.jpg').exists())

    def test_invalid_zip_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'bad.zip'
            file.write_bytes(b'broken')
            self.assertEqual(run(file, Path(directory) / 'run'), 2)

    def test_output_cannot_overwrite_sources(self):
        with self.assertRaises(InputError): run(self.path, self.path / 'results')
        with self.assertRaises(InputError): run(self.path, self.path)

    def test_partial_selection_is_explicit_unique_and_bounded(self):
        self.assertEqual(select_photos([4, 1, 3], 4), [1, 3, 4])
        for numbers in ([1], [1, 1], [0, 2], [1, 5], [True, 2]):
            with self.subTest(numbers=numbers), self.assertRaises(InputError): select_photos(numbers, 4)

    def test_hugin_check_failure_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / 'bin'
            binaries.mkdir()
            for name in ('pto_gen', 'cpfind', 'checkpto'):
                (binaries / (name + '.exe')).touch()
            output = root / 'result'
            def execute(argv, **kwargs):
                if Path(argv[0]).stem == 'cpfind':
                    (output / 'matched.pto').write_text('i w100\n' * 4 + 'c n0 N1\nc n1 N2\nc n2 N3\n')
                return SimpleNamespace(returncode=99 if Path(argv[0]).stem == 'checkpto' else 0)
            with patch('hugin_reference.subprocess.run', side_effect=execute):
                self.assertEqual(run_hugin(self.path, output, binaries), 2)
            report = json.loads((output / 'reference-report.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertIn('exit code 99', report['error'])
            self.assertFalse(report['full_sphere_verified'])

    def test_partial_cannot_overwrite_existing_or_source_directories(self):
        with self.assertRaises(InputError): run_partial(self.path, self.path / 'output', [1, 2])
        with self.assertRaises(InputError): run_partial(self.path, self.path, [1, 2])

    def test_partial_diagnostic_never_promotes_geometric_coverage_to_full_sphere(self):
        camera = SimpleNamespace(K=lambda: np.eye(3), R=np.eye(3))
        def full_support(source, images, cameras, width, report, output):
            report['coverage'] = {'all_sampled_directions_supported': True}
            return np.zeros((width // 2, width, 3), np.uint8)
        with tempfile.TemporaryDirectory() as directory, \
                patch('partial_stitch.align', return_value=[camera, camera]), \
                patch('partial_stitch.level_from_sensors'), patch('partial_stitch.compose', side_effect=full_support):
            output = Path(directory) / 'partial'
            self.assertEqual(run_partial(self.path, output, [1, 2], width=1024), 3)
            report = json.loads((output / 'report.json').read_text())
            self.assertEqual(report['excluded_photo_numbers'], [3, 4])
            self.assertFalse(report['full_sphere_verified'])
            self.assertTrue(report['diagnostic_only'])
            self.assertTrue((output / 'diagnostic-partial.jpg').exists())
            self.assertFalse((output / 'candidate.jpg').exists())

    def test_disconnected_images_fail_without_silently_dropping_inputs(self):
        images = [np.random.default_rng(seed).integers(0, 255, (300, 400, 3), np.uint8) for seed in (12, 43)]
        report = {}
        with self.assertRaisesRegex(StitchError, 'disconnected'): align(images, report)
        self.assertEqual(len(report['connected_components']), 2)

    def test_partial_integration_stays_diagnostic(self):
        # Render four overlapping views, estimate alignment and blend; assert missing poles.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture'
            create_fixture(path, partial=True)
            output = Path(directory) / 'run'
            self.assertEqual(run(path, output, width=512), 3)
            report = json.loads((output / 'report.json').read_text())
            self.assertFalse(report['coverage']['all_sampled_directions_supported'])
            self.assertFalse((output / 'candidate.jpg').exists())
            self.assertTrue((output / 'diagnostic-only.jpg').exists())


class GeometryTests(unittest.TestCase):
    def test_hugin_disconnected_graph_keeps_unmatched_images(self):
        graph = control_point_graph('i w100\ni w100\ni w100\nc n0 N1 x0 y0 X0 Y0 t0\n')
        self.assertEqual(graph['components_one_based'], [[1, 2], [3]])
        self.assertFalse(graph['all_images_connected'])

    def test_hugin_self_control_points_do_not_connect_images(self):
        graph = control_point_graph('i w100\ni w100\nc n0 N0 x0 y0 X0 Y0 t1\n')
        self.assertEqual(graph['cross_image_control_points'], 0)
        self.assertFalse(graph['all_images_connected'])

    def test_hugin_connected_graph_is_only_connectivity(self):
        graph = control_point_graph('i w100\ni w100\ni w100\nc n0 N1 x0 y0\nc n1 N2 x0 y0\n')
        self.assertTrue(graph['all_images_connected'])
        self.assertNotIn('full_sphere_verified', graph)

    def test_hugin_invalid_control_point_indices_are_rejected(self):
        for point in ('c n0 N2', 'c n0 N-1', 'c n0'):
            with self.subTest(point=point), self.assertRaises(InputError):
                control_point_graph('i w100\ni w100\n' + point)

    def test_invalid_descriptor_match_confidence_rejected(self):
        for value in (0, 1, -1, float('nan')):
            with self.subTest(value=value), self.assertRaises(StitchError): align([], {}, match_conf=value)

    def test_full_coverage_metrics(self):
        metrics = coverage_metrics(np.ones((128, 256), np.uint16))
        self.assertTrue(metrics['all_sampled_directions_supported'])
        self.assertAlmostEqual(metrics['supported_fraction_solid_angle'], 1)

    def test_missing_poles_not_full_sphere(self):
        coverage = np.ones((128, 256), np.uint16)
        coverage[:10] = coverage[-10:] = 0
        metrics = coverage_metrics(coverage)
        self.assertFalse(metrics['all_sampled_directions_supported'])
        self.assertEqual(metrics['ceiling_10deg_supported_fraction'], 0)
        self.assertEqual(metrics['floor_10deg_supported_fraction'], 0)

    def test_six_known_camera_views_cover_sphere(self):
        image = np.full((200, 200, 3), 80, np.uint8)
        intrinsic = np.array([[80, 0, 100], [0, 80, 100], [0, 0, 1]], np.float32)
        coverage = np.zeros((128, 256), np.uint16)
        for yaw, elevation in [(0, 0), (90, 0), (180, 0), (270, 0), (0, 90), (0, -90)]:
            result, mask = spherical_warp(image, intrinsic, rotation(yaw, elevation), 256)
            coverage += (mask > 0)
            self.assertTrue(np.all(result[mask == 0] == 0))
        self.assertTrue(coverage_metrics(coverage)['all_sampled_directions_supported'])

    def test_single_photo_cannot_cover_sphere(self):
        image = np.full((200, 200, 3), 80, np.uint8)
        intrinsic = np.array([[100, 0, 100], [0, 100, 100], [0, 0, 1]], np.float32)
        _, mask = spherical_warp(image, intrinsic, np.eye(3), 256)
        self.assertLess(coverage_metrics(mask)['supported_fraction_solid_angle'], .3)

    def test_featureless_images_fail_cleanly(self):
        report = {}
        with self.assertRaisesRegex(StitchError, 'few features'):
            align([np.zeros((200, 200, 3), np.uint8)] * 2, report)
        self.assertEqual(report['keypoints'], [0, 0])

    def test_output_dimensions_size_and_metadata(self):
        data, metadata = encode_jpeg(np.zeros((512, 1024, 3), np.uint8))
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1024, 512))
            self.assertEqual(len(image.getexif()), 0)
            self.assertNotIn('icc_profile', image.info)
            self.assertNotIn('xmp', image.info)
        self.assertLess(len(data), 10 * 1024**2)
        self.assertEqual(metadata['bytes'], len(data))

    def test_jpeg_limit_is_strict(self):
        image = np.random.default_rng(2).integers(0, 255, (512, 1024, 3), dtype=np.uint8)
        encoded, _ = encode_jpeg(image, limit=100_000)
        self.assertLess(len(encoded), 100_000)

    def test_impossible_jpeg_limit(self):
        with self.assertRaises(StitchError): encode_jpeg(np.zeros((256, 512, 3), np.uint8), limit=10)

    def test_bad_output_aspect_ratio(self):
        with self.assertRaises(StitchError): encode_jpeg(np.zeros((100, 300, 3), np.uint8))


if __name__ == '__main__':
    unittest.main()
