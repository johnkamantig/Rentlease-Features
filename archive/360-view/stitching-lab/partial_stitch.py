"""Explicit selected-photo diagnostic. Never produces an accepted full panorama."""
import argparse
import copy
import json
from pathlib import Path
import time

import cv2 as cv

from inputs import CaptureInput, InputError
from pipeline import StitchError, align, compose, encode_jpeg, level_from_sensors, working_image


def select_photos(numbers, count):
    if (len(numbers) < 2 or len(numbers) > 60 or len(numbers) != len(set(numbers)) or
            any(type(n) is not int or not 1 <= n <= count for n in numbers)):
        raise InputError('Select 2-60 distinct, existing one-based photograph numbers.')
    return sorted(numbers)


def run(input_path, output_path, numbers, work_size=1920, match_conf=.3, width=2048):
    original, output = Path(input_path).resolve(), Path(output_path).resolve()
    if output.exists() or (original.is_dir() and output.is_relative_to(original)):
        raise InputError('Choose a new diagnostic directory outside the source capture folder.')
    if work_size not in (960, 1920) or width not in (1024, 2048, 4096) or not 0 < match_conf < 1:
        raise InputError('Invalid diagnostic resolution or matching confidence.')
    output.mkdir(parents=True)
    report = {'status': 'failed', 'diagnostic_only': True, 'full_sphere_verified': False,
              'physical_android_verified': False, 'source': str(original), 'opencv': cv.__version__,
              'work_max_side': work_size, 'descriptor_match_confidence': match_conf,
              'warnings': ['Explicit selected-photo experiment. Excluded photographs are listed; this is never a completed capture-set stitch.']}
    source, started = None, time.monotonic()
    try:
        source = CaptureInput(original)
        all_photos = source.manifest['photos']
        selected = select_photos(numbers, len(all_photos))
        report['input_photo_count'] = len(all_photos)
        report['selected_photo_numbers'] = selected
        report['excluded_photo_numbers'] = [i for i in range(1, len(all_photos) + 1) if i not in selected]
        # Only this in-memory view changes; source ZIP/manifest/photographs remain untouched.
        source.manifest = copy.deepcopy(source.manifest)
        source.manifest['photos'] = [all_photos[i - 1] for i in selected]
        images = []
        for number, photo in zip(selected, source.manifest['photos']):
            print(f'Diagnostic source photo {number}', flush=True)
            images.append(working_image(source.image(photo), work_size))
        report['input_validation'] = 'Selected photos passed byte counts, CRC32, dimensions and complete decoding.'
        cameras = align(images, report, match_conf=match_conf)
        level_from_sensors(cameras, source.manifest['photos'], report)
        report['cameras'] = [{'source_photo': number, 'K_at_work_resolution': c.K().tolist(),
                              'camera_to_world_R': c.R.tolist()} for number, c in zip(selected, cameras)]
        result = compose(source, images, cameras, width, report, output)
        data, info = encode_jpeg(result)
        (output / 'diagnostic-partial.jpg').write_bytes(data)
        report['jpeg'] = {'file': 'diagnostic-partial.jpg', **info}
        report['status'] = 'diagnostic_partial_requires_inspection'
    except (InputError, StitchError, cv.error, OSError, ValueError, MemoryError) as error:
        report['error'] = str(error)
    finally:
        if source:
            source.close()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(report['status'], output / 'report.json', flush=True)
    return 3 if report['status'].startswith('diagnostic_partial') else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--output', required=True)
    parser.add_argument('--photos', required=True, help='Explicit one-based indices, comma-separated')
    parser.add_argument('--work-size', type=int, default=1920, choices=(960, 1920))
    parser.add_argument('--match-confidence', type=float, default=.3)
    parser.add_argument('--width', type=int, default=2048, choices=(1024, 2048, 4096))
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.input, args.output, [int(n) for n in args.photos.split(',')],
                             args.work_size, args.match_confidence, args.width))
    except (InputError, OSError, ValueError) as error:
        print(f'Cannot start diagnostic: {error}')
        raise SystemExit(2)
