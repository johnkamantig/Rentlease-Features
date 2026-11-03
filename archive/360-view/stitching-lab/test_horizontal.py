import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inputs import InputError, parse_manifest
from prepare_horizontal import choose_photos, prepare
from synthetic import create_fixture


class HorizontalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'capture'
        create_fixture(self.source, partial=True, width=160, height=120)
        self.manifest = json.loads((self.source / 'manifest.json').read_text())
        self.manifest['session'].update(captureMode='horizontal', sweepDegrees=120, step=40)
        for i, (photo, target) in enumerate(zip(self.manifest['photos'], self.manifest['session']['targets'])):
            target.update(yaw=i * 40, elevation=0, direction='horizontal', extra=False)
            photo.update(targetYaw=i * 40, targetElevation=0, direction='horizontal')
            target['photo'].update(targetYaw=i * 40, targetElevation=0, direction='horizontal')
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_horizontal_manifest_roundtrip(self):
        self.assertEqual(parse_manifest(json.dumps(self.manifest)), self.manifest)

    def test_invalid_horizontal_mode_stages_and_plan(self):
        for mutate in (lambda m: m['session'].update(sweepDegrees=360),
                       lambda m: m['session']['targets'][0].update(direction='ceiling'),
                       lambda m: m['session']['targets'][1].update(yaw=99)):
            changed = copy.deepcopy(self.manifest)
            mutate(changed)
            with self.assertRaises(InputError): parse_manifest(json.dumps(changed))

    def test_preparation_keeps_original_bytes_metadata_and_order(self):
        output = self.root / 'prepared'
        self.assertEqual(prepare(self.source, output), 0)
        report = json.loads((output / 'prepared.json').read_text())
        self.assertEqual([p['source_order'] for p in report['photos']], [1, 2, 3, 4])
        self.assertFalse(report['panorama_generated'])
        self.assertFalse(report['coverage_validated'])
        for photo in report['photos']:
            self.assertEqual((self.source / photo['path']).read_bytes(), (output / photo['path']).read_bytes())
            self.assertEqual(photo['orientation'], self.manifest['photos'][photo['source_order'] - 1]['orientation'])

    def test_legacy_requires_explicit_ordered_horizontal_selection(self):
        legacy = copy.deepcopy(self.manifest)
        del legacy['session']['captureMode']
        with self.assertRaises(InputError): choose_photos(legacy)
        self.assertEqual(choose_photos(legacy, [1, 2])[0], [1, 2])
        for numbers in ([2, 1], [1, 1], [0, 1], [1, 5], [True, 2], [1]):
            with self.subTest(numbers=numbers), self.assertRaises(InputError): choose_photos(legacy, numbers)

    def test_selected_pole_or_full_loop_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['photos'][1]['direction'] = 'floor'
        with self.assertRaises(InputError): choose_photos(bad, [1, 2])
        bad = copy.deepcopy(self.manifest)
        bad['photos'][-1]['targetYaw'] = 300
        with self.assertRaises(InputError): choose_photos(bad)

    def test_missing_and_damaged_selected_images_are_reported(self):
        file = self.source / self.manifest['photos'][0]['path']
        file.write_bytes(b'broken')
        self.assertEqual(prepare(self.source, self.root / 'damaged'), 2)
        file.unlink()
        self.assertEqual(prepare(self.source, self.root / 'missing'), 2)

    def test_preparation_cannot_overwrite_sources_or_prior_outputs(self):
        for output in (self.source, self.source / 'results', self.root):
            with self.assertRaises(InputError): prepare(self.source, output)

    def test_disk_failure_is_reported_without_changing_originals(self):
        original = (self.source / self.manifest['photos'][0]['path']).read_bytes()
        with patch.object(Path, 'write_bytes', side_effect=OSError('disk full')):
            self.assertEqual(prepare(self.source, self.root / 'failed'), 2)
        self.assertEqual((self.source / self.manifest['photos'][0]['path']).read_bytes(), original)
        self.assertIn('disk full', json.loads((self.root / 'failed/prepared.json').read_text())['error'])


if __name__ == '__main__':
    unittest.main()
