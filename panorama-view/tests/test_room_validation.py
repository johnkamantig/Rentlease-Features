import json
from pathlib import Path

import pytest
from PIL import Image

from errors import PanoramaError
import room_validation as rv
from stitch360 import Calibration


@pytest.fixture
def order(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, 'ROOT', tmp_path)
    source = tmp_path / 'source'
    source.mkdir()
    names = ['9.jpg', '2.jpg', '7.jpg', '1.jpg', '5.jpg', '3.jpg']
    for i, name in enumerate(names):
        Image.new('RGB', (180, 240), (20+i*20, 90, 150)).save(source / name)
    plan = tmp_path / 'order.json'
    plan.write_text(json.dumps({'schema_version': 1, 'data_kind': 'synthetic_test',
                               'images': [f'source/{name}' for name in names]}))
    return plan


def test_import_retains_supplied_order_original_bytes_and_unknown_calibration(order, tmp_path):
    dest = tmp_path / 'samples/room'
    result = rv.import_capture(order, dest)
    assert [Path(p['source_path']).name for p in result['photos']] == ['9.jpg', '2.jpg', '7.jpg', '1.jpg', '5.jpg', '3.jpg']
    for p in result['photos']:
        assert (dest / p['path']).read_bytes() == Path(p['source_path']).read_bytes()
        assert p['camera_metadata']['focal_length_mm'] is None
        assert p['oriented_size'] == [180, 240]
    assert result['coverage_verified'] is False
    assert (dest / 'contact-sheet.jpg').exists()


def test_import_records_every_declared_exclusion(order, tmp_path):
    extra = tmp_path / 'source/blurred-retake.jpg'
    Image.new('RGB', (180, 240), 'white').save(extra)
    plan = json.loads(order.read_text())
    plan['excluded_images'] = [{'path': 'source/blurred-retake.jpg', 'reason': 'Replaced blurred attempt; original retained'}]
    order.write_text(json.dumps(plan))
    result = rv.import_capture(order, tmp_path / 'samples/room')
    assert len(result['photos']) == 6
    assert result['excluded_images'][0]['sha256'] == rv.digest(extra)
    assert extra.exists()


def test_import_rejects_bad_files_before_completed_manifest(order, tmp_path):
    (tmp_path / 'source/7.jpg').write_bytes(b'bad')
    dest = tmp_path / 'samples/room'
    with pytest.raises(PanoramaError, match='corrupted'):
        rv.import_capture(order, dest)
    assert not dest.exists()


def test_no_overwrite_or_outside_destination(order, tmp_path):
    dest = tmp_path / 'samples/room'
    rv.import_capture(order, dest)
    with pytest.raises(FileExistsError):
        rv.import_capture(order, dest)
    with pytest.raises(PanoramaError, match='Destination'):
        rv.import_capture(order, tmp_path / 'unrelated')


def test_changed_import_and_order_cannot_be_stitched(order, tmp_path):
    dest = tmp_path / 'samples/room'
    result = rv.import_capture(order, dest)
    (dest / result['photos'][0]['path']).write_bytes(b'changed')
    with pytest.raises(PanoramaError, match='changed'):
        rv.capture_files(dest / 'capture.json')


def test_missing_calibration_writes_failure_report_without_panorama(order, tmp_path):
    dest = tmp_path / 'samples/room'
    rv.import_capture(order, dest)
    report = rv.measured_stitch(dest / 'capture.json', None, tmp_path / 'output/attempt')
    assert report['status'] == 'failed'
    assert 'calibration' in report['error']
    assert report['visual_review'] == 'not_performed'
    assert (tmp_path / 'output/attempt/validation.json').exists()
    assert not (tmp_path / 'output/attempt/panorama.jpg').exists()


def test_untextured_screen_never_certifies_coverage(order, tmp_path):
    dest = tmp_path / 'samples/room'
    rv.import_capture(order, dest)
    report = rv.audit_capture(dest / 'capture.json', tmp_path / 'output/audit')
    assert report['weak_pairs'] == 6
    assert report['pairs'][-1]['from'] == 6 and report['pairs'][-1]['to'] == 1
    assert report['pairs'][-1]['closing_pair'] is True
    assert report['coverage_verified'] is False


def test_reject_duplicate_and_unexplained_exclusion(order, tmp_path):
    plan = json.loads(order.read_text())
    plan['images'][-1] = plan['images'][0]
    order.write_text(json.dumps(plan))
    with pytest.raises(PanoramaError, match='Duplicate'):
        rv.import_capture(order, tmp_path / 'samples/room')
    plan['images'][-1] = 'source/3.jpg'
    plan['excluded_images'] = [{'path': 'anything'}]
    order.write_text(json.dumps(plan))
    with pytest.raises(PanoramaError, match='reason'):
        rv.import_capture(order, tmp_path / 'samples/room')


@pytest.mark.parametrize('data', [None, [], 50, 'unknown'])
def test_non_object_calibration_has_clear_error(tmp_path, data):
    path = tmp_path / 'calibration.json'
    path.write_text(json.dumps(data))
    with pytest.raises(PanoramaError, match='JSON object'):
        Calibration.read(path)


def test_real_input_requires_fresh_project_declaration(order, tmp_path):
    plan = json.loads(order.read_text())
    plan['data_kind'] = 'real_room'
    order.write_text(json.dumps(plan))
    with pytest.raises(PanoramaError, match='fresh photographs'):
        rv.import_capture(order, tmp_path / 'samples/room')
    plan['capture_origin'] = 'fresh_panorama_view'
    order.write_text(json.dumps(plan))
    manifest = rv.import_capture(order, tmp_path / 'samples/room')
    assert manifest['input_policy'] == 'panorama_view_isolated_v1'
    rv.capture_files(tmp_path / 'samples/room/capture.json')


def test_source_outside_project_is_rejected_before_image_read(order, tmp_path, monkeypatch):
    plan = json.loads(order.read_text())
    plan['images'][0] = str(tmp_path.parent / 'not-a-project-input.jpg')
    order.write_text(json.dumps(plan))
    def unexpected_read(*args, **kwargs):
        pytest.fail('Must reject the source before reading images')
    monkeypatch.setattr(rv, 'load_image', unexpected_read)
    with pytest.raises(PanoramaError, match='staged inside'):
        rv.import_capture(order, tmp_path / 'samples/room')


@pytest.mark.parametrize('component', ['archive', '360-view'])
def test_excluded_path_rejected_before_access(order, tmp_path, monkeypatch, component):
    def unexpected_open(*args, **kwargs):
        pytest.fail('Excluded inputs must not be opened')
    monkeypatch.setattr(Path, 'open', unexpected_open)
    with pytest.raises(PanoramaError, match='Excluded'):
        rv.read_json(tmp_path / component / 'nonexistent.json')


def test_unmarked_real_capture_manifest_is_not_accepted(order, tmp_path):
    dest = tmp_path / 'samples/room'
    manifest = rv.import_capture(order, dest)
    manifest['data_kind'] = 'real_room'
    manifest.pop('capture_origin', None)
    (dest / 'capture.json').write_text(json.dumps(manifest))
    with pytest.raises(PanoramaError, match='fresh-input policy'):
        rv.capture_files(dest / 'capture.json')


def test_resolution_runner_rejects_external_input_before_enumeration(order, tmp_path, monkeypatch):
    import benchmark_resolution
    monkeypatch.setattr('sys.argv', ['benchmark_resolution.py', '--source',
                                    str(tmp_path.parent / 'not-a-project-input'), '--output',
                                    str(tmp_path / 'output/benchmark')])
    def unexpected_enumeration(*args, **kwargs):
        pytest.fail('External source must not be enumerated')
    monkeypatch.setattr(Path, 'glob', unexpected_enumeration)
    with pytest.raises(PanoramaError, match='staged inside'):
        benchmark_resolution.main()
    assert not (tmp_path / 'output/benchmark').exists()


def test_audit_skips_knn_for_one_descriptor_but_reports_every_pair(order, tmp_path, monkeypatch):
    from types import SimpleNamespace
    import numpy as np
    dest = tmp_path / 'samples/room'
    rv.import_capture(order, dest)
    counts = iter([5, 1, 5, 5, 5, 5])
    monkeypatch.setattr(rv.cv2.detail, 'computeImageFeatures2',
                        lambda *args: SimpleNamespace(keypoints=[object()] * next(counts)))
    class Matcher:
        def apply2(self, features, mask):
            assert np.all(mask[1] == 0) and np.all(mask[:, 1] == 0)
            assert mask[0, 5] == 1  # Closing pair is still evaluated.
            return [SimpleNamespace(H=None, num_inliers=0, confidence=0., getMatches=lambda: ()) for _ in range(36)]
        def collectGarbage(self):
            pass
    monkeypatch.setattr(rv.cv2, 'detail_BestOf2NearestMatcher', SimpleNamespace(create=lambda *args: Matcher()))
    report = rv.audit_capture(dest / 'capture.json', tmp_path / 'output/audit')
    assert len(report['pairs']) == 6
    assert report['pairs'][0]['matching_status'] == 'insufficient_descriptors_for_knn'
    assert report['pairs'][1]['matching_status'] == 'insufficient_descriptors_for_knn'
    assert report['coverage_verified'] is False


def test_audit_writes_previews_even_when_frames_are_featureless(order, tmp_path):
    dest = tmp_path / 'samples/room'
    rv.import_capture(order, dest)
    output = tmp_path / 'output/previews'
    report = rv.audit_capture(dest / 'capture.json', output, match_previews=True)
    assert report['weak_pairs'] == 6
    assert len(list(output.glob('matches-*.jpg'))) == 6
    assert all((output / pair['diagnostic_image']).exists() for pair in report['pairs'])
