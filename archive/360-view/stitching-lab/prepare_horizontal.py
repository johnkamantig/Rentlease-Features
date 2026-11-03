"""Validate and copy an ordered horizontal set for later OpenCV stitching. No stitching."""
import argparse
import hashlib
import json
from pathlib import Path

from inputs import CaptureInput, InputError


def choose_photos(manifest, numbers=None):
    photos = manifest['photos']
    if numbers is None:
        if manifest['session'].get('captureMode') != 'horizontal':
            raise InputError('Legacy capture: explicitly select horizontal photo numbers with --photos; no stages are silently discarded.')
        numbers = list(range(1, len(photos) + 1))
    if (not 2 <= len(numbers) <= 60 or any(type(n) is not int or not 1 <= n <= len(photos) for n in numbers)
            or numbers != sorted(set(numbers))):
        raise InputError('Select 2-60 distinct photo numbers in original overlap order.')
    selected = [photos[n - 1] for n in numbers]
    if any(p['direction'] != 'horizontal' or p['targetElevation'] != 0 for p in selected):
        raise InputError('Only horizontal, level planned targets are supported; actual tilt remains approximate.')
    yaws = [p['targetYaw'] for p in selected if p['targetYaw'] is not None]
    if len(yaws) < 2 or any(type(y) not in (int, float) for y in yaws) or yaws != sorted(yaws) or yaws[-1] - yaws[0] > 180:
        raise InputError('Select one ordered horizontal sweep of at most 180 planned degrees; no full loop or wrap.')
    return numbers, selected


def prepare(input_path, output_path, numbers=None):
    original, output = Path(input_path).resolve(), Path(output_path).resolve()
    if output.exists() or (original.is_dir() and output.is_relative_to(original)):
        raise InputError('Choose a new output directory outside the original capture folder.')
    output.mkdir(parents=True)
    report = {'status': 'failed', 'source': str(original), 'panorama_generated': False,
              'coverage_validated': False, 'projection': 'unstitched-photographs', 'photos': []}
    source = None
    try:
        source = CaptureInput(original)
        selected_numbers, photos = choose_photos(source.manifest, numbers)
        report['selected_photo_numbers'] = selected_numbers
        report['excluded_photo_numbers'] = [n for n in range(1, len(source.manifest['photos']) + 1) if n not in selected_numbers]
        report['source_capture_mode'] = source.manifest['session'].get('captureMode', 'legacy')
        report['planned_sweep_degrees'] = source.manifest['session'].get('sweepDegrees')
        (output / 'images').mkdir()
        for number, photo in zip(selected_numbers, photos):
            source.image(photo)  # CRC, byte count, dimensions, full decode and paths checked.
            data = source.read(photo['path'])
            (output / photo['path']).write_bytes(data)
            report['photos'].append({**photo, 'source_order': number, 'sha256': hashlib.sha256(data).hexdigest()})
        (output / 'source-manifest.json').write_text(json.dumps(source.manifest, indent=2), encoding='utf-8')
        report['status'] = 'prepared_unstitched'
        report['notes'] = ['Original JPEG bytes copied without recompression. Metadata and overlap order retained.',
                           'Only selected photos decoded; excluded legacy photos remain in the original capture.',
                           'Future OpenCV stitching must verify visual matches and retain output projection/coverage diagnostics.',
                           'Do not wrap an arbitrary horizontal stitch into a sphere or infer angular coverage from dimensions.']
    except (InputError, OSError, ValueError, MemoryError) as error:
        report['error'] = str(error)
    finally:
        if source:
            source.close()
        (output / 'prepared.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(report['status'], output / 'prepared.json')
    return 0 if report['status'] == 'prepared_unstitched' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--output', required=True)
    parser.add_argument('--photos', help='Explicit legacy subset, one-based comma-separated indices in original order')
    args = parser.parse_args()
    try:
        raise SystemExit(prepare(args.input, args.output, None if args.photos is None else [int(n) for n in args.photos.split(',')]))
    except (InputError, OSError, ValueError) as error:
        print(f'Cannot prepare: {error}')
        raise SystemExit(2)
