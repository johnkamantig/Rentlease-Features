"""Local command-line entry point. Never writes into source capture sets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time

import cv2 as cv
import numpy as np
from PIL import Image

from inputs import CaptureInput, InputError
from pipeline import StitchError, align, compose, encode_jpeg, level_from_sensors, working_image


def run(input_path, output_path, width=2048, validate_only=False):
    source_path, output = Path(input_path).resolve(), Path(output_path).resolve()
    if output.exists():
        raise InputError('Choose a new output directory; existing results are never overwritten.')
    if source_path == output or (source_path.is_dir() and output.is_relative_to(source_path)):
        raise InputError('Output cannot be inside the source capture directory.')
    output.mkdir(parents=True)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
              'full_sphere_verified': False, 'physical_android_verified': False,
              'versions': {'python': platform.python_version(), 'opencv': cv.__version__, 'numpy': np.__version__},
              'model': 'central pinhole rotation; no translation or calibrated lens distortion correction',
              'warnings': [], 'input': str(source_path), 'width_requested': width}
    started, source = time.monotonic(), None
    exit_code = 2
    try:
        if width % 2 or not 512 <= width <= 4096:
            raise InputError('Width must be even and within 512–4096.')
        source = CaptureInput(source_path)
        photos = source.manifest['photos']
        report['photo_count'] = len(photos)
        report['photo_order'] = [p['path'] for p in photos]
        if not validate_only and len(photos) > 60:
            raise StitchError('Stitching is limited to 60 photos for bounded memory. Input validation supports 300; no images were dropped.')
        images = []
        for i, photo in enumerate(photos):
            print(f'Validating {i + 1}/{len(photos)}: {photo["path"]}', flush=True)
            decoded = source.image(photo)
            if not validate_only:
                images.append(working_image(decoded))
            del decoded
        report['input_validation'] = 'all byte counts, CRC32, dimensions and full JPEG decodes passed'
        if validate_only:
            report['status'] = 'inputs_valid'; exit_code = 0
        else:
            cameras = align(images, report)
            level_from_sensors(cameras, photos, report)
            report['cameras'] = [{'K_at_work_resolution': c.K().tolist(), 'camera_to_world_R': c.R.tolist(),
                                  'work_width': image.shape[1], 'work_height': image.shape[0]} for c, image in zip(cameras, images)]
            result = compose(source, images, cameras, width, report, output)
            severe = report['overlap_mean_absolute_difference_0_255'] > 35
            if severe:
                report['warnings'].append('Large overlap disagreement: possible ghosting, parallax, incorrect alignment or moving objects.')
            complete = report['coverage']['all_sampled_directions_supported']
            report['status'] = ('candidate_requires_visual_review' if complete and not severe else 'incomplete_or_suspect')
            name = 'candidate.jpg' if complete and not severe else 'diagnostic-only.jpg'
            encoded, metadata = encode_jpeg(result)
            (output / name).write_bytes(encoded)
            report['jpeg'] = {'file': name, **metadata}
            report['warnings'].append('A 2:1 JPEG is not proof of full-sphere stitching. Missing areas are black in JPEG and transparent in diagnostic.png. Coverage masks describe estimated support only.')
            exit_code = 0 if complete and not severe else 3
    except (InputError, StitchError, cv.error, OSError, ValueError, MemoryError) as error:
        report['error'] = str(error)
    finally:
        if source:
            source.close()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(f'{report["status"]}: {output / "report.json"}', flush=True)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Capture ZIP or extracted folder containing manifest.json and images/')
    parser.add_argument('--output', required=True, help='New local results directory')
    parser.add_argument('--width', type=int, default=2048)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    try:
        return run(args.input, args.output, args.width, args.validate_only)
    except (InputError, OSError) as error:
        print(f'Cannot start: {error}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
