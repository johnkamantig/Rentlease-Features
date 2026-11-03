"""Ordered, local room import, non-calibrated overlap audit and measured runs.

This wrapper does not relax the existing stitcher's calibration/coverage gates.
Every output directory must be new and inside this prototype's samples/output.
"""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from errors import PanoramaError
from stitch import collect_images, load_image, process, MAX_INPUT_BYTES
from stitch360 import Calibration, MAX_TOTAL_PIXELS

ROOT = Path(__file__).resolve().parent


def project_input(path):
    """Reject out-of-project/excluded paths before opening or resolving them."""
    root = Path(os.path.abspath(ROOT))
    candidate = Path(os.path.abspath(path))
    if not candidate.is_relative_to(root):
        raise PanoramaError('Inputs must be staged inside the active panorama-view project.')
    relative = candidate.relative_to(root)
    if any(part.casefold() in ('archive', '360-view') for part in relative.parts):
        raise PanoramaError('Excluded project material is not permitted as input.')
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise PanoramaError('Linked input paths are not permitted; stage fresh files directly.')
    return candidate


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def digest(path):
    path = project_input(path)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    path = project_input(path)
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise PanoramaError(f'Cannot read JSON {path.name}: {exc}') from exc


def new_folder(path):
    path = path.resolve()
    if not any(path.is_relative_to(ROOT / name) and path != ROOT / name for name in ('samples', 'output')):
        raise PanoramaError('Destination must be a NEW directory beneath panorama-view/samples or output.')
    path.mkdir(parents=True, exist_ok=False)
    return path


def import_capture(order_path, destination):
    specification = read_json(order_path)
    if not isinstance(specification, dict) or specification.get('schema_version') != 1:
        raise PanoramaError('Order file must have schema_version 1.')
    if specification.get('data_kind') not in ('real_room', 'synthetic_test'):
        raise PanoramaError('Explicit data_kind real_room or synthetic_test is required.')
    if specification['data_kind'] == 'real_room' and specification.get('capture_origin') != 'fresh_panorama_view':
        raise PanoramaError('Real-room inputs require capture_origin fresh_panorama_view and fresh photographs captured specifically for this project.')
    names = specification.get('images')
    if not isinstance(names, list) or not all(isinstance(p, str) and p.strip() for p in names):
        raise PanoramaError('images must list each source path in actual capture order.')
    paths = collect_images(None, [project_input(order_path.parent / p) for p in names])
    exclusions = specification.get('excluded_images', [])
    if not isinstance(exclusions, list) or any(not isinstance(e, dict) or not e.get('path') or not e.get('reason') for e in exclusions):
        raise PanoramaError('Each excluded image requires a path and reason.')
    excluded_paths = [project_input(order_path.parent / e['path']) for e in exclusions]
    if len(set(paths + excluded_paths)) != len(paths + excluded_paths):
        raise PanoramaError('Selected and excluded paths must be distinct.')
    entries, thumbs = [], []
    for i, path in enumerate(paths):
        image = load_image(path, max_long_edge=600, require_opaque=True)
        with Image.open(path) as source:
            exif = source.getexif()
            tags = dict(exif)
            if 34665 in exif:
                tags.update(exif.get_ifd(34665))
            size = source.size[::-1] if tags.get(274) in (5, 6, 7, 8) else source.size
            camera = {label: str(tags[tag]) if tag in tags else None for tag, label in
                      ((271, 'make'), (272, 'model'), (37386, 'focal_length_mm'),
                       (41989, 'focal_length_35mm_equivalent'), (42036, 'lens_model'), (36867, 'capture_time'))}
        thumb = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        thumb.thumbnail((180, 240))
        thumbs.append(thumb)
        entries.append({'order': i + 1, 'source_path': str(path),
                        'path': f'originals/{i+1:04d}-{path.name}', 'bytes': path.stat().st_size,
                        'sha256': digest(path), 'oriented_size': list(size), 'camera_metadata': camera})
    if len({e['sha256'] for e in entries}) != len(entries):
        raise PanoramaError('Duplicate image bytes in the ordered capture; no files were imported.')
    excluded = []
    for item, path in zip(exclusions, excluded_paths):
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise PanoramaError('Excluded source exceeds the input byte limit.')
        excluded.append({'source_path': str(path), 'reason': item['reason'], 'sha256': digest(path)})
    destination = new_folder(destination)
    (destination / 'originals').mkdir()
    for path, entry in zip(paths, entries):
        with path.open('rb') as source, (destination / entry['path']).open('xb') as target:
            shutil.copyfileobj(source, target)
        if digest(destination / entry['path']) != entry['sha256'] or digest(path) != entry['sha256']:
            raise PanoramaError('Source changed during import. No completed capture manifest was written.')
    sheet = Image.new('RGB', (4 * 200, ((len(thumbs) + 3) // 4) * 270), '#eeeeee')
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        x, y = i % 4 * 200, i // 4 * 270
        draw.text((x+8, y+5), f'Capture {i+1}', fill='black')
        sheet.paste(thumb, (x+8, y+25))
    sheet.save(destination / 'contact-sheet.jpg', quality=88)
    report = {'schema_version': 1, 'status': 'imported_unvalidated',
              'data_kind': specification['data_kind'], 'capture_notes': specification.get('capture_notes', ''),
              'capture_origin': specification.get('capture_origin'),
              'input_policy': 'panorama_view_isolated_v1',
              'photos': entries, 'excluded_images': excluded, 'coverage_verified': False,
              'calibration_status': 'not_supplied; EXIF fields are evidence, not an automatic FOV calibration'}
    write_json(destination / 'capture.json', report)
    return report


def capture_files(path):
    manifest = read_json(path)
    if not isinstance(manifest, dict) or manifest.get('status') != 'imported_unvalidated':
        raise PanoramaError('Expected an imported capture.json manifest.')
    if manifest.get('data_kind') not in ('real_room', 'synthetic_test'):
        raise PanoramaError('Capture data_kind is missing or invalid.')
    if manifest['data_kind'] == 'real_room' and (manifest.get('capture_origin') != 'fresh_panorama_view'
                                               or manifest.get('input_policy') != 'panorama_view_isolated_v1'):
        raise PanoramaError('Real-room capture is not eligible under the fresh-input policy; import fresh photographs for this project.')
    paths = []
    for i, entry in enumerate(manifest.get('photos', [])):
        photo = project_input(path.parent / entry['path'])
        if not photo.is_relative_to(path.parent.resolve()) or entry.get('order') != i+1:
            raise PanoramaError('Capture paths/order were altered; reimport from the source order file.')
        if digest(photo) != entry['sha256']:
            raise PanoramaError(f'Imported photograph changed: {photo.name}')
        paths.append(photo)
    return manifest, collect_images(None, paths)


def peak_memory():
    """OS high-water mark for this process, including libraries and startup."""
    try:
        if sys.platform == 'win32':
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in ('peak_rss', 'rss', 'peak_paged', 'paged',
                                                      'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            query = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
            query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            query.restype = wintypes.BOOL
            counters = Counters(); counters.cb = ctypes.sizeof(counters)
            if not query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                raise OSError(ctypes.get_last_error())
            value, method = counters.peak_rss, 'Windows PeakWorkingSetSize'
        else:
            import resource
            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
            method = 'getrusage ru_maxrss'
        return {'peak_resident_bytes': int(value), 'method': method,
                'scope': 'entire current process including libraries; use a fresh CLI process per comparison'}
    except (OSError, ImportError, AttributeError) as exc:
        return {'peak_resident_bytes': None, 'method': 'unavailable', 'reason': str(exc)}


def audit_capture(capture, destination, max_long_edge=1200, match_previews=False):
    start = time.perf_counter()
    manifest, paths = capture_files(capture)
    images, pixels = [], 0
    for path in paths:
        image = load_image(path, max_long_edge, require_opaque=True)
        pixels += image.shape[0] * image.shape[1]
        if pixels > MAX_TOTAL_PIXELS:
            raise PanoramaError('Audit pixel budget exceeded; reduce --max-long-edge.')
        images.append(image)
    features = [cv2.detail.computeImageFeatures2(cv2.SIFT_create(nfeatures=3500), im) for im in images]
    count = len(images)
    keypoint_counts = [len(f.keypoints) for f in features]
    ring = np.zeros((count, count), np.uint8)
    for i in range(count):
        j = (i+1) % count
        # FLANN's k=2 search asserts if either descriptor set has fewer than
        # two rows. Keep every photo/pair in the report, but do not attempt an
        # impossible KNN query. This never certifies a missing edge as valid.
        if min(keypoint_counts[i], keypoint_counts[j]) >= 2:
            ring[i, j] = ring[j, i] = 1
    matcher = cv2.detail_BestOf2NearestMatcher.create(False, .65, 6, 6, 4.0)
    matches = matcher.apply2(features, ring)
    matcher.collectGarbage()
    pairs = []
    destination = new_folder(destination)
    for i in range(count):
        j = (i+1) % count
        m = matches[i*count+j]
        total, inliers = len(m.getMatches()), int(m.num_inliers)
        ratio = inliers / max(total, 1)
        good = m.H is not None and inliers >= 25 and ratio >= .45 and m.confidence >= .7
        pair = {'from': i+1, 'to': j+1, 'closing_pair': j == 0, 'matches': total,
                      'inliers': inliers, 'inlier_ratio': ratio, 'confidence': float(m.confidence),
                      'passes_count_ratio_screen': bool(good),
                      'matching_status': 'insufficient_descriptors_for_knn' if min(keypoint_counts[i], keypoint_counts[j]) < 2 else 'ransac_evaluated'}
        if match_previews:
            selected = [item for item, valid in zip(m.getMatches(), m.getInliers()) if valid][:60]
            preview = cv2.drawMatches(images[i], features[i].keypoints, images[j], features[j].keypoints,
                                      selected, None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            if max(preview.shape[:2]) > 1200:
                factor = 1200 / max(preview.shape[:2])
                preview = cv2.resize(preview, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
            label = f'{i+1} -> {j+1}: {inliers} inliers; ' + ('SCREEN PASS' if good else 'WEAK / UNVERIFIED')
            cv2.rectangle(preview, (0, 0), (preview.shape[1], 32), (255, 255, 255), -1)
            cv2.putText(preview, label, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1, cv2.LINE_AA)
            name = f'matches-{i+1:02d}-{j+1:02d}.jpg'
            if not cv2.imwrite(str(destination / name), preview):
                raise PanoramaError('Cannot write diagnostic matching preview.')
            pair['diagnostic_image'] = name
        pairs.append(pair)
    report = {'schema_version': 1, 'status': 'overlap_screen_only', 'data_kind': manifest['data_kind'],
              'coverage_verified': False, 'calibration_used': False, 'photo_count': count,
              'keypoints': keypoint_counts, 'pairs': pairs,
              'weak_pairs': sum(not p['passes_count_ratio_screen'] for p in pairs),
              'processing_seconds': round(time.perf_counter()-start, 3), 'memory': peak_memory(),
              'limitations': 'Counts and RANSAC are preliminary evidence only. No angular geometry, spatial-spread, full coverage, loop alignment or stitch quality is certified.'}
    write_json(destination / 'audit.json', report)
    return report


def measured_stitch(capture, calibration_path, destination, width=2048, max_long_edge=1200):
    destination = new_folder(destination)
    start = time.perf_counter()
    report = {'status': 'failed', 'data_kind': None, 'requested_width': width,
              'processing_long_edge': max_long_edge, 'visual_review': 'not_performed',
              'physical_device_testing': 'not_performed', 'capture_manifest': str(capture.resolve())}
    try:
        manifest, paths = capture_files(capture)
        report['data_kind'] = manifest['data_kind']
        calibration = Calibration.read(project_input(calibration_path)) if calibration_path else None
        result = process(paths, destination / 'panorama.jpg', calibration=calibration,
                         output_width=width, max_long_edge=max_long_edge)
        report.update(status='automated_checks_passed_visual_review_required', panorama=result)
    except (PanoramaError, OSError, cv2.error) as exc:
        report['error'] = str(exc)
    report.update(elapsed_seconds=round(time.perf_counter()-start, 3), memory=peak_memory())
    write_json(destination / 'validation.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    importer = commands.add_parser('import')
    importer.add_argument('--order', type=Path, required=True)
    importer.add_argument('--output', type=Path, required=True)
    for name in ('audit', 'stitch'):
        command = commands.add_parser(name)
        command.add_argument('--capture', type=Path, required=True)
        command.add_argument('--output', type=Path, required=True)
        command.add_argument('--max-long-edge', type=int, default=1200)
        if name == 'stitch':
            command.add_argument('--calibration', type=Path)
            command.add_argument('--width', type=int, default=2048)
        else:
            command.add_argument('--match-previews', action='store_true')
    args = parser.parse_args(argv)
    cv2.setNumThreads(2)
    cv2.setRNGSeed(7)
    try:
        if args.command == 'import':
            report = import_capture(args.order, args.output)
        elif args.command == 'audit':
            report = audit_capture(args.capture, args.output, args.max_long_edge, args.match_previews)
        else:
            report = measured_stitch(args.capture, args.calibration, args.output, args.width, args.max_long_edge)
        print(json.dumps({k: report[k] for k in ('status', 'data_kind', 'weak_pairs', 'elapsed_seconds', 'memory', 'error') if k in report}, indent=2))
        return 1 if report['status'] == 'failed' else (2 if report.get('weak_pairs') else 0)
    except (PanoramaError, OSError, cv2.error, KeyError, TypeError, ValueError) as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
