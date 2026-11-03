import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2 as cv
import numpy as np

from check_horizontal import check, match_pair, passes_screen
from inputs import InputError
from synthetic import create_fixture


class OverlapTests(unittest.TestCase):
    def test_four_exact_inliers_never_pass(self):
        self.assertFalse(passes_screen({'ransac_inliers': 4, 'inlier_ratio': 1,
                                       'inlier_hull_fraction_a': .9, 'inlier_hull_fraction_b': .9,
                                       'median_fit_error_work_pixels': 0}))

    def test_featureless_pair_returns_diagnostic_without_crashing(self):
        image = np.zeros((120, 160, 3), np.uint8)
        row, drawing = match_pair(image, image, ([], None), ([], None))
        self.assertEqual(row['mutual_ratio_matches'], 0)
        self.assertFalse(row['enough_for_further_investigation'])
        self.assertEqual(drawing.shape[:2], (120, 320))

    def fixture(self, path):
        create_fixture(path, partial=True, width=160, height=120)
        manifest = json.loads((path / 'manifest.json').read_text())
        manifest['session'].update(captureMode='horizontal', sweepDegrees=120, step=40)
        for i, (photo, target) in enumerate(zip(manifest['photos'], manifest['session']['targets'])):
            target.update(yaw=i * 40, elevation=0, direction='horizontal', extra=False)
            photo.update(targetYaw=i * 40, targetElevation=0, direction='horizontal')
            target['photo'].update(targetYaw=i * 40, targetElevation=0, direction='horizontal')
        (path / 'manifest.json').write_text(json.dumps(manifest))

    def test_real_matching_produces_inspection_artifacts_without_success_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'capture', Path(directory) / 'result'
            self.fixture(source)
            original = {p.name: p.read_bytes() for p in (source / 'images').iterdir()}
            self.assertIn(check(source, output), (0, 3))
            report = json.loads((output / 'overlap-diagnostics.json').read_text())
            self.assertEqual(len(report['adjacent_pairs']), 3)
            self.assertFalse(report['panorama_generated'])
            self.assertFalse(report['visual_inspection_performed'])
            for name in ['contact-sheet.jpg', 'CHECK_RESULTS.txt', 'matches-1-2.jpg', 'matches-2-3.jpg', 'matches-3-4.jpg']:
                self.assertTrue((output / name).is_file())
            self.assertEqual(original, {p.name: p.read_bytes() for p in (source / 'images').iterdir()})
            with self.assertRaises(InputError): check(source, output)

    def test_processing_error_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'capture', Path(directory) / 'result'
            self.fixture(source)
            with patch('check_horizontal.cv.SIFT_create', side_effect=cv.error('feature failure')):
                self.assertEqual(check(source, output), 2)
            self.assertEqual(json.loads((output / 'overlap-diagnostics.json').read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
