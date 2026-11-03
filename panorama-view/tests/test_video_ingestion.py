import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from errors import PanoramaError
import room_validation as rv
import video_ingestion as vi
from cyclic_scene import cyclic_scene


def write_video(path, frames, fps=12):
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), fps, (w, h))
    assert writer.isOpened(), 'Local MJPG codec is required for these video tests.'
    try:
        for frame in frames:
            writer.write(frame)
    finally:
        writer.release()
    return path


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, 'ROOT', tmp_path)
    (tmp_path/'samples').mkdir()
    return tmp_path


@pytest.fixture(scope='module')
def cyclic_frames():
    return cyclic_scene(headings=np.arange(0, 360, 3))[0]


def test_real_video_requires_fresh_declaration(project):
    path = project/'samples/input.avi'; path.write_bytes(b'not opened')
    with pytest.raises(PanoramaError, match='Declare --fresh'):
        vi.extract_video(path, project/'output/run')


def test_external_video_rejected_before_decode(project, monkeypatch):
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: pytest.fail('Must not open external input'))
    with pytest.raises(PanoramaError, match='staged inside'):
        vi.extract_video(project.parent/'outside.mp4', project/'output/run', fresh=True)


def test_corrupt_video_has_failure_report(project):
    path = project/'samples/broken.mp4'; path.write_bytes(b'invalid local video')
    report = vi.extract_video(path, project/'output/broken', data_kind='synthetic_test')
    assert report['status'] == 'failed'
    assert report['coverage_verified'] is False
    assert not (project/'output/broken/order.json').exists()


def test_blur_and_textureless_frames_are_unusable():
    rng = np.random.default_rng(8)
    image = rng.integers(0, 255, (320, 240, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(image, (51, 51), 12)
    assert vi.inspect_frame(blurred, 0, 0, vi.Settings())['reason'] != 'eligible'
    assert vi.inspect_frame(np.full_like(image, 120), 1, 10, vi.Settings())['features'] == 0


def test_static_video_is_not_sent_as_duplicate_keyframes(project, cyclic_frames):
    source = write_video(project/'samples/static.avi', [cyclic_frames[0]]*24)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    report = vi.extract_video(source, project/'output/static', data_kind='synthetic_test')
    assert report['decoded_frames'] == 24
    assert report['inspected_candidates'] < 24
    assert report['selected_count'] == 1
    assert any(e['reason'] == 'redundant_overlap_or_stationary' for e in report['candidate_events'])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert not (project/'output/static/order.json').exists()


def test_cyclic_video_selects_ordered_bounded_overlaps_and_stitches(project, cyclic_frames):
    source = write_video(project/'samples/cycle.avi', cyclic_frames)
    output = project/'output/cycle'
    report = vi.extract_video(source, output, vi.Settings(min_sharpness=5), data_kind='synthetic_test')
    assert report['status'] == 'keyframes_selected_unverified'
    assert report['decoded_frames'] == 120
    assert 6 <= report['selected_count'] <= 30 < report['decoded_frames']
    assert not report['temporal_gaps']
    indices = [item['frame_index'] for item in report['selected']]
    times = [item['timestamp_ms'] for item in report['selected']]
    assert indices == sorted(set(indices)) and times == sorted(set(times))
    assert report['coverage_verified'] is False  # Selection alone never proves a circle.
    calibration = project/'samples/calibration.json'
    calibration.write_text(json.dumps({'model':'rectilinear_square_pixels_centered', 'horizontal_fov_deg':50,
                                      'source':'Synthetic perspective renderer, exact ground truth', 'reference_pitch_deg':0}))
    result = vi.evaluate_selection(output, calibration, width=1024)
    assert result['coverage_verified'] is True
    assert result['stitch']['panorama']['horizontal_coverage_deg'] == 360
    assert result['stitch']['panorama']['bytes'] < 9_500_000
    assert result['stitch']['panorama']['closure_verified'] is True


def test_unusable_interval_is_recorded_without_hidden_bridge(project, cyclic_frames, monkeypatch):
    frames = list(cyclic_frames)
    for i in range(30, 57):
        frames[i] = np.full_like(frames[i], 120)
    source = write_video(project/'samples/gap.avi', frames)
    output = project/'output/gap'
    report = vi.extract_video(source, output, vi.Settings(min_sharpness=5), data_kind='synthetic_test')
    assert report['temporal_gaps']
    assert any(item['segment_restart'] for item in report['selected'])
    monkeypatch.setattr(vi, 'measured_stitch', lambda *args: pytest.fail('A temporal gap must not reach calibrated export'))
    monkeypatch.setattr(vi, 'baseline_stitch_images', lambda *args: (_ for _ in ()).throw(PanoramaError('diagnostic failed')))
    result = vi.evaluate_selection(output)
    assert result['coverage_verified'] is False
    assert not (output/'stitch/panorama.jpg').exists()


def test_partial_arc_video_never_becomes_a_full_circle(project, cyclic_frames):
    source = write_video(project/'samples/partial.avi', cyclic_frames[:60])
    output = project/'output/partial'
    report = vi.extract_video(source, output, vi.Settings(min_sharpness=5), data_kind='synthetic_test')
    assert report['selected_count'] >= 6
    assert report['coverage_verified'] is False
    result = vi.evaluate_selection(output)
    assert result['coverage_verified'] is False
    assert result['weak_pairs'] >= 1
    assert not (output/'stitch/panorama.jpg').exists()


def test_keyframe_budget_does_not_silently_truncate(project, cyclic_frames):
    source = write_video(project/'samples/budget.avi', cyclic_frames)
    output = project/'output/budget'
    report = vi.extract_video(source, output, vi.Settings(max_keyframes=6, min_sharpness=5), data_kind='synthetic_test')
    assert report['status'] == 'failed'
    assert report['selected_count'] == 6
    assert 'limit' in report['error']
    assert not (output/'order.json').exists()


def test_frame_budget_and_existing_output_are_safe(project, cyclic_frames, monkeypatch):
    source = write_video(project/'samples/frames.avi', cyclic_frames[:12])
    monkeypatch.setattr(vi, 'MAX_DECODED', 5)
    output = project/'output/frames'
    report = vi.extract_video(source, output, data_kind='synthetic_test')
    assert report['status'] == 'failed' and report['decoded_frames'] == 0
    with pytest.raises(FileExistsError):
        vi.extract_video(source, output, data_kind='synthetic_test')


def test_missing_timestamps_are_not_invented(project, cyclic_frames, monkeypatch):
    source = write_video(project/'samples/clock.avi', cyclic_frames[:12])
    original = cv2.VideoCapture
    class NoClock:
        def __init__(self, path): self.inner = original(path)
        def get(self, prop): return 0. if prop == cv2.CAP_PROP_POS_MSEC else self.inner.get(prop)
        def __getattr__(self, name): return getattr(self.inner, name)
    monkeypatch.setattr(cv2, 'VideoCapture', NoClock)
    report = vi.extract_video(source, project/'output/clock', data_kind='synthetic_test')
    assert report['status'] == 'failed' and 'timestamps' in report['error']


def test_short_range_flow_tracks_texture_but_not_a_uniform_wall(cyclic_frames):
    gray = cv2.cvtColor(cyclic_frames[0], cv2.COLOR_BGR2GRAY)
    moved = cv2.warpAffine(gray, np.float32([[1,0,3],[0,1,2]]), (gray.shape[1],gray.shape[0]))
    tracks = vi.flow_evidence(gray, moved)
    assert tracks['reliable_tracks'] > 50
    assert tracks['camera_rotation_verified'] is False
    blank = np.full_like(gray, 120)
    assert vi.flow_evidence(blank, blank)['reliable_tracks'] == 0


@pytest.mark.parametrize('settings', [vi.Settings(sample_hz=100), vi.Settings(max_keyframes=1000),
                                      vi.Settings(min_sharpness=float('nan'))])
def test_settings_limits(settings):
    with pytest.raises(PanoramaError): settings.validate()
