"""Independent, bounded video-to-keyframe experiment. No sensor data is inferred.

Run with --help. Extraction never certifies a revolution; the existing calibrated
stitcher and wrap/coverage gates remain responsible for panorama acceptance.
"""
from dataclasses import dataclass, asdict
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw

from errors import PanoramaError
from room_validation import project_input, new_folder, digest, write_json, import_capture, audit_capture, measured_stitch, peak_memory
from stitch import baseline_stitch_images
from stitch360 import MAX_TOTAL_PIXELS

MAX_VIDEO_BYTES = 1_500_000_000
MAX_SECONDS = 180
MAX_DECODED = 12000
MAX_INSPECTED = 1500


@dataclass(frozen=True)
class Settings:
    sample_hz: float = 4
    max_keyframes: int = 48
    long_edge: int = 960
    analysis_edge: int = 640
    min_sharpness: float = 25
    min_features: int = 30
    min_overlap: float = .40
    max_overlap: float = .68
    max_gap_ms: float = 1000

    def validate(self):
        values = asdict(self)
        if not all(math.isfinite(v) for v in values.values()):
            raise PanoramaError('Selection settings must be finite.')
        if not (.5 <= self.sample_hz <= 8 and 6 <= self.max_keyframes <= 72 and
                200 <= self.long_edge <= 1200 and 160 <= self.analysis_edge <= 640 and
                self.min_sharpness >= 0 and self.min_features >= 30 and
                .25 <= self.min_overlap < self.max_overlap <= .85 and 250 <= self.max_gap_ms <= 3000):
            raise PanoramaError('Invalid selection settings or excessive resource limits.')


def resize_limit(image, edge):
    scale = min(1., edge / max(image.shape[:2]))
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image.copy()


def inspect_frame(image, frame_index, timestamp_ms, settings):
    small = resize_limit(image, settings.analysis_edge)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean())
    keypoints, descriptors = cv2.SIFT_create(nfeatures=1800).detectAndCompute(gray, None)
    reason = 'eligible'
    if mean < 8 or mean > 247:
        reason = 'exposure_unusable'
    elif sharpness < settings.min_sharpness:
        reason = 'blurred'
    elif len(keypoints) < settings.min_features:
        reason = 'insufficient_texture'
    return {'index': frame_index, 'timestamp_ms': timestamp_ms, 'sharpness': sharpness,
            'mean_luminance': mean, 'features': len(keypoints), 'reason': reason,
            'image': resize_limit(image, settings.long_edge), 'gray': gray,
            'keypoints': keypoints, 'descriptors': descriptors}


def pair_evidence(a, b):
    """Measured projective overlap proxy, not camera FOV or angular coverage."""
    result = {'verified_visual_match': False, 'inliers': 0, 'inlier_ratio': 0., 'overlap_fraction': None}
    if a['descriptors'] is None or b['descriptors'] is None or min(a['features'], b['features']) < 2:
        return result
    neighbors = cv2.BFMatcher().knnMatch(a['descriptors'], b['descriptors'], k=2)
    matches = [m for row in neighbors if len(row) == 2 for m, n in [row] if m.distance < .75 * n.distance]
    if len(matches) < 25:
        return result
    p = np.float32([a['keypoints'][m.queryIdx].pt for m in matches])
    q = np.float32([b['keypoints'][m.trainIdx].pt for m in matches])
    h, mask = cv2.findHomography(p, q, cv2.RANSAC, 3.)
    if h is None or mask is None or not np.isfinite(h).all():
        return result
    valid = mask.ravel().astype(bool)
    count = int(valid.sum()); ratio = count / len(matches)
    result.update(inliers=count, inlier_ratio=ratio)
    if count < 25 or ratio < .45:
        return result
    height, width = a['gray'].shape
    if np.ptp(p[valid, 0]) < width * .12 or np.ptp(p[valid, 1]) < height * .25:
        return result
    corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    projected = cv2.perspectiveTransform(corners[None], h)[0]
    if not np.isfinite(projected).all() or np.max(np.abs(projected)) > max(height, width) * 10:
        return result
    hull = cv2.convexHull(projected)
    area = cv2.contourArea(hull)
    if not width * height * .2 < area < width * height * 5:
        return result
    intersection, _ = cv2.intersectConvexConvex(hull, corners)
    overlap = float(np.clip(intersection / max(area, width * height), 0, 1))
    movement = float(np.median(np.linalg.norm(p[valid] - q[valid], axis=1)) / width)
    result.update(verified_visual_match=True, overlap_fraction=overlap, displacement_width_fraction=movement)
    return result


def flow_evidence(previous_gray, gray):
    """Short-range LK probe only. It supplies no angular pose or gap repair."""
    points = cv2.goodFeaturesToTrack(previous_gray, 200, .01, 7)
    if points is None or len(points) < 6:
        return {'corners': 0 if points is None else len(points), 'reliable_tracks': 0,
                'reason': 'insufficient_corners', 'camera_rotation_verified': False}
    following, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, points, None)
    if following is None or status is None:
        return {'corners': len(points), 'reliable_tracks': 0, 'reason': 'tracking_failed', 'camera_rotation_verified': False}
    back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, previous_gray, following, None)
    if back is None or back_status is None:
        return {'corners': len(points), 'reliable_tracks': 0, 'reason': 'backward_tracking_failed', 'camera_rotation_verified': False}
    errors = np.linalg.norm(points[:, 0] - back[:, 0], axis=1)
    good = status.ravel().astype(bool) & back_status.ravel().astype(bool) & np.isfinite(errors) & (errors < 1.5)
    return {'corners': len(points), 'reliable_tracks': int(good.sum()),
            'median_roundtrip_px': float(np.median(errors[good])) if good.any() else None,
            'camera_rotation_verified': False}


class Selector:
    """Streaming greedy selection: bounded state, no hidden continuity repairs."""
    def __init__(self, destination, settings):
        self.destination, self.settings = destination, settings
        self.anchor = None
        self.selected, self.events, self.gaps = [], [], []
        self.quality_gap_start = None
        self.match_loss_start = None
        self.pixels = 0
        self.previous_gray = None
        self.first = None

    def save(self, frame, evidence=None, segment_restart=False):
        if len(self.selected) >= self.settings.max_keyframes:
            raise PanoramaError('Keyframe limit reached. Selection is incomplete; use a slower single revolution, not silent truncation.')
        self.pixels += frame['image'].shape[0] * frame['image'].shape[1]
        if self.pixels > MAX_TOTAL_PIXELS:
            raise PanoramaError('Selected-frame pixel budget exceeded; reduce processing long edge.')
        name = f'frame-{frame["index"]:06d}.jpg'
        if not cv2.imwrite(str(self.destination / name), frame['image'], [cv2.IMWRITE_JPEG_QUALITY, 95]):
            raise PanoramaError('Cannot save selected keyframe.')
        self.selected.append({'frame_index': frame['index'], 'timestamp_ms': frame['timestamp_ms'],
                              'path': name, 'sharpness': frame['sharpness'], 'features': frame['features'],
                              'sha256': digest(self.destination / name), 'segment_restart': segment_restart,
                              'selection_match': evidence})
        self.anchor = frame
        if self.first is None:
            self.first = frame
        self.match_loss_start = None

    def consider(self, frame):
        event = {k: frame[k] for k in ('index', 'timestamp_ms', 'sharpness', 'features', 'reason')}
        self.events.append(event)
        if self.previous_gray is not None:
            event['short_range_flow_probe'] = flow_evidence(self.previous_gray, frame['gray'])
        self.previous_gray = frame['gray']
        if frame['reason'] != 'eligible':
            if self.quality_gap_start is None:
                self.quality_gap_start = frame['timestamp_ms']
            return
        restart = False
        if self.quality_gap_start is not None:
            if frame['timestamp_ms'] - self.quality_gap_start > self.settings.max_gap_ms:
                self.gaps.append({'from_ms': self.quality_gap_start, 'to_ms': frame['timestamp_ms'], 'reason': 'unusable_frame_interval'})
                restart = True
            self.quality_gap_start = None
        if self.anchor is None or restart:
            event['reason'] = 'selected_segment_start' if restart else 'selected_start'
            self.save(frame, segment_restart=restart)
            return
        if len(self.selected) >= 6:
            start_match = pair_evidence(self.first, frame)
            if (start_match['verified_visual_match'] and start_match['overlap_fraction'] > .90
                    and start_match['displacement_width_fraction'] < .12):
                event.update(reason='redundant_return_to_start', starting_view_match=start_match)
                return
        match = pair_evidence(self.anchor, frame)
        event['anchor_match'] = match
        if not match['verified_visual_match'] or match['overlap_fraction'] < self.settings.min_overlap:
            event['reason'] = 'visual_connection_unverified'
            if self.match_loss_start is None:
                self.match_loss_start = frame['timestamp_ms']
            if frame['timestamp_ms'] - self.match_loss_start >= self.settings.max_gap_ms:
                self.gaps.append({'from_ms': self.anchor['timestamp_ms'], 'to_ms': frame['timestamp_ms'], 'reason': 'visual_overlap_lost'})
                event['reason'] = 'selected_disconnected_segment'
                self.save(frame, segment_restart=True)
            return
        self.match_loss_start = None
        if match['overlap_fraction'] > self.settings.max_overlap or match['displacement_width_fraction'] < .06:
            event['reason'] = 'redundant_overlap_or_stationary'
            return
        event['reason'] = 'selected_overlap'
        self.save(frame, match)

    def finish(self, end_ms):
        if self.quality_gap_start is not None and end_ms - self.quality_gap_start > self.settings.max_gap_ms:
            self.gaps.append({'from_ms': self.quality_gap_start, 'to_ms': end_ms, 'reason': 'unusable_tail'})
        if self.match_loss_start is not None:
            self.gaps.append({'from_ms': self.anchor['timestamp_ms'], 'to_ms': end_ms, 'reason': 'unverified_tail'})


def extract_video(video, output, settings=Settings(), data_kind='real_room', fresh=False):
    settings.validate()
    video = project_input(video)
    if data_kind not in ('real_room', 'synthetic_test') or (data_kind == 'real_room' and not fresh):
        raise PanoramaError('Declare --fresh for a video captured specifically for this project.')
    if not video.is_file() or not 0 < video.stat().st_size <= MAX_VIDEO_BYTES:
        raise PanoramaError('Missing, empty or oversized video.')
    original_hash = digest(video)
    output = new_folder(project_input(output))
    frames_dir = output / 'keyframes'; frames_dir.mkdir()
    selector = Selector(frames_dir, settings)
    start = time.perf_counter()
    cap = cv2.VideoCapture(str(video))
    report = {'schema_version': 1, 'data_kind': data_kind, 'source': str(video), 'source_sha256': original_hash,
              'settings': asdict(settings), 'status': 'failed', 'coverage_verified': False,
              'sensor_data': 'not supplied or inferred', 'timestamp_source': 'OpenCV presentation milliseconds; not exposure/sensor timestamps'}
    decoded, previous_ms, next_ms, last_frame, last_index = 0, -1., 0., None, -1
    error = None
    try:
        if not cap.isOpened():
            raise PanoramaError('Video decoder could not open the file.')
        report['video_metadata'] = {'fps': cap.get(cv2.CAP_PROP_FPS), 'declared_frames': cap.get(cv2.CAP_PROP_FRAME_COUNT),
                                    'orientation_meta_deg': cap.get(cv2.CAP_PROP_ORIENTATION_META),
                                    'orientation_auto': bool(cap.get(cv2.CAP_PROP_ORIENTATION_AUTO)), 'backend': cap.getBackendName()}
        declared = report['video_metadata']['declared_frames']
        if declared > MAX_DECODED:
            raise PanoramaError('Video frame budget exceeded before processing.')
        while True:
            ok, image = cap.read()
            if not ok:
                break
            t = float(cap.get(cv2.CAP_PROP_POS_MSEC))
            if not math.isfinite(t) or t < 0 or (decoded and t <= previous_ms):
                raise PanoramaError('Video presentation timestamps are unavailable or non-monotonic; no synthetic timestamps were substituted.')
            previous_ms = t
            decoded += 1
            if decoded > MAX_DECODED or t > MAX_SECONDS * 1000 or image.shape[0] * image.shape[1] > 12_000_000:
                raise PanoramaError('Video duration/frame/dimension resource limit exceeded.')
            if decoded == 1:
                report['decoded_dimensions'] = [image.shape[1], image.shape[0]]
            if t >= next_ms:
                if len(selector.events) >= MAX_INSPECTED:
                    raise PanoramaError('Candidate inspection budget exceeded.')
                selector.consider(inspect_frame(image, decoded-1, t, settings))
                next_ms = t + 1000 / settings.sample_hz
                last_index = decoded-1
            last_frame = image
        if not decoded or (declared > 0 and decoded < declared - 2):
            raise PanoramaError('Video is empty or decoding ended before its declared frame count.')
        if last_index != decoded-1:
            selector.consider(inspect_frame(last_frame, decoded-1, previous_ms, settings))
        selector.finish(previous_ms)
        report['status'] = 'keyframes_selected_unverified'
    except (PanoramaError, cv2.error) as exc:
        error = str(exc)
    finally:
        cap.release()
    if digest(video) != original_hash:
        error = 'Source video changed during processing.'
    if error:
        report.update(status='failed', error=error)
    report.update(decoded_frames=decoded, inspected_candidates=len(selector.events), selected_count=len(selector.selected),
                  selected=selector.selected, candidate_events=selector.events, temporal_gaps=selector.gaps,
                  seconds=round(time.perf_counter()-start, 3), memory=peak_memory())
    if selector.selected:
        sheet = Image.new('RGB', (800, math.ceil(len(selector.selected)/4)*250), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, item in enumerate(selector.selected):
            with Image.open(frames_dir/item['path']) as im:
                im.thumbnail((185, 215)); x, y = i % 4 * 200, i // 4 * 250
                sheet.paste(im, (x, y+28)); draw.text((x+3, y+5), f'{i+1}: {item["timestamp_ms"]/1000:.2f}s', fill='black')
        sheet.save(output/'contact-sheet.jpg', quality=90)
    write_json(output/'selection.json', report)
    if report['status'] != 'failed' and len(selector.selected) >= 6:
        write_json(output/'order.json', {'schema_version': 1, 'data_kind': data_kind,
                   'capture_origin': 'fresh_panorama_view' if data_kind == 'real_room' else None,
                   'capture_notes': 'Video-derived frames in presentation order. See selection.json for rejected candidates and unverified intervals. No angular coverage is implied.',
                   'images': [str(frames_dir/item['path']) for item in selector.selected], 'excluded_images': []})
    return report


def evaluate_selection(output, calibration=None, width=1536, diagnostic_baseline=False):
    """Use existing audit/stitch APIs. Never promote a temporal gap to success."""
    output = project_input(output)
    selection = json.loads((output/'selection.json').read_text())
    if selection['status'] == 'failed' or selection['selected_count'] < 6:
        return {'status': 'failed', 'error': selection.get('error', 'Too few selected keyframes.')}
    import_capture(output/'order.json', output/'capture')
    audit = audit_capture(output/'capture/capture.json', output/'audit', 960, match_previews=True)
    result = {'status': 'incomplete', 'coverage_verified': False, 'weak_pairs': audit['weak_pairs'],
              'temporal_gaps': selection['temporal_gaps'], 'calibration_provided': calibration is not None}
    if selection['temporal_gaps'] or audit['weak_pairs']:
        result['error'] = 'Temporal or visual continuity is unverified; calibrated export was not attempted.'
    else:
        run = measured_stitch(output/'capture/capture.json', calibration, output/'stitch', width, 960)
        result.update(status=run['status'], stitch=run,
                      coverage_verified=bool(run.get('panorama', {}).get('closure_verified', False)))
    if result['coverage_verified']:
        write_json(output/'evaluation.json', result)
        return result
    if not diagnostic_baseline:
        write_json(output/'evaluation.json', result)
        return result
    # A separate baseline may establish a diagnostic failure, never angular metadata.
    from room_validation import capture_files
    from stitch import load_image
    _, paths = capture_files(output/'capture/capture.json')
    t = time.perf_counter()
    try:
        image = baseline_stitch_images([load_image(p, 960) for p in paths])
        result['baseline'] = {'status': 'uncalibrated_image_returned_not_exported', 'dimensions': [image.shape[1], image.shape[0]]}
    except (PanoramaError, cv2.error) as exc:
        result['baseline'] = {'status': 'failed', 'error': str(exc)}
    result['baseline']['seconds'] = round(time.perf_counter()-t, 3)
    write_json(output/'evaluation.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--sample-hz', type=float, default=4)
    parser.add_argument('--max-keyframes', type=int, default=48)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--diagnostic-baseline', action='store_true', help='Also run the slower uncalibrated high-level comparison after rejection.')
    args = parser.parse_args(argv)
    cv2.setNumThreads(2); cv2.setRNGSeed(7)
    try:
        report = extract_video(args.video, args.output, Settings(sample_hz=args.sample_hz, max_keyframes=args.max_keyframes), fresh=args.fresh)
        print(json.dumps({k: report[k] for k in ('status', 'decoded_frames', 'inspected_candidates', 'selected_count', 'temporal_gaps', 'seconds')}, indent=2), flush=True)
        if args.evaluate and report['status'] != 'failed':
            evaluation = evaluate_selection(args.output, args.calibration, diagnostic_baseline=args.diagnostic_baseline)
            print(json.dumps(evaluation, indent=2), flush=True)
            return 0 if evaluation.get('coverage_verified') else 2
        return 1 if report['status'] == 'failed' else 0
    except (PanoramaError, OSError, cv2.error) as exc:
        print(f'FAILED: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
