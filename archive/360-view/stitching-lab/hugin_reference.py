"""Independent, local Hugin control-point comparison; not a full-sphere certificate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from inputs import CaptureInput, InputError
from pipeline import _components


def control_point_graph(text):
    lines = text.splitlines()
    count = sum(line.startswith('i ') for line in lines)
    if count < 2:
        raise InputError('Hugin project contains fewer than two images.')
    edges, points = set(), 0
    for line in lines:
        if not line.startswith('c '):
            continue
        fields = dict(re.findall(r'(?:^|\s)([nN])(\d+)(?=\s|$)', line))
        if set(fields) != {'n', 'N'}:
            raise InputError('Malformed Hugin control-point indices.')
        a, b = int(fields['n']), int(fields['N'])
        if not 0 <= a < count or not 0 <= b < count:
            raise InputError('Hugin control point references an unknown image.')
        if a != b:
            points += 1
            edges.add(tuple(sorted((a, b))))
    components = [[n + 1 for n in group] for group in _components(count, sorted(edges))]
    return {'photo_count': count, 'cross_image_control_points': points, 'connected_pairs': len(edges),
            'components_one_based': components, 'all_images_connected': len(components) == 1}


def run(input_path, output_path, bin_path, hfov=50, timeout=900):
    source_path, output, binaries = Path(input_path).resolve(), Path(output_path).resolve(), Path(bin_path).resolve()
    if output.exists() or (source_path.is_dir() and output.is_relative_to(source_path)):
        raise InputError('Choose a new output directory outside the source capture folder.')
    if not 10 <= hfov <= 150 or not 1 <= timeout <= 3600:
        raise InputError('Invalid assumed field of view or time limit.')
    executables = {name: binaries / (name + '.exe') for name in ('pto_gen', 'cpfind', 'checkpto')}
    if any(not file.is_file() for file in executables.values()):
        raise InputError('Hugin command-line executables were not found in --bin.')
    output.mkdir(parents=True)
    profile = output / 'profile'
    profile.mkdir()
    # Only child processes receive these paths. No user environment or system install is changed.
    env = {**os.environ, 'APPDATA': str(profile), 'LOCALAPPDATA': str(profile),
           'TEMP': str(profile), 'TMP': str(profile), 'OMP_NUM_THREADS': '4'}
    report = {'status': 'failed', 'input': str(source_path), 'full_sphere_verified': False,
              'physical_android_verified': False, 'initial_hfov_degrees': hfov,
              'hfov_is_assumed_not_calibrated': True, 'commands': [],
              'note': 'Control-point connectivity is not validated alignment, image quality or full spherical coverage.'}
    source, started = None, time.monotonic()
    try:
        source = CaptureInput(source_path)
        photos = source.manifest['photos']
        if len(photos) > 60:
            raise InputError('This reference experiment is limited to 60 photos; no sources were discarded.')
        report['photo_count'] = len(photos)
        if source_path.is_file():
            with source_path.open('rb') as handle:
                report['source_zip_sha256'] = hashlib.file_digest(handle, 'sha256').hexdigest()
        (output / 'images').mkdir()
        images = []
        for index, photo in enumerate(photos):
            print(f'Validating reference photo {index + 1}/{len(photos)}', flush=True)
            source.image(photo)
            # Input paths have been allowlisted by CaptureInput; JPEG bytes remain unchanged.
            path = output / photo['path']
            path.write_bytes(source.read(photo['path']))
            images.append(str(path))
        commands = [
            ('generate', [str(executables['pto_gen']), '-p', '0', '-f', str(hfov), '-o', 'input.pto', *images]),
            ('match', [str(executables['cpfind']), '--allpairs', '--ransacmode', 'hom', '--ncores', '4', '-o', 'matched.pto', 'input.pto']),
            ('check', [str(executables['checkpto']), 'matched.pto']),
        ]
        for name, argv in commands:
            print(f'Hugin stage: {name}', flush=True)
            stage_started = time.monotonic()
            with (output / (name + '.log')).open('w', encoding='utf-8') as log:
                try:
                    result = subprocess.run(argv, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                except subprocess.TimeoutExpired:
                    report['commands'].append({'stage': name, 'argv': argv, 'timeout_seconds': timeout})
                    raise InputError(f'Hugin {name} exceeded the time limit. See the retained log.')
            report['commands'].append({'stage': name, 'argv': argv, 'exit_code': result.returncode,
                                       'seconds': round(time.monotonic() - stage_started, 3)})
            if result.returncode and name != 'check':
                raise InputError(f'Hugin {name} failed with exit code {result.returncode}. See {name}.log.')
        graph = control_point_graph((output / 'matched.pto').read_text(encoding='utf-8'))
        if graph['photo_count'] != len(photos):
            raise InputError('Hugin project no longer contains the complete capture set.')
        report['control_point_graph'] = graph
        if result.returncode and graph['all_images_connected']:
            raise InputError(f'Hugin check failed with exit code {result.returncode}. See check.log.')
        report['status'] = 'control_points_connected_unverified' if graph['all_images_connected'] else 'disconnected'
    except (InputError, OSError, ValueError) as error:
        report['error'] = str(error)
    finally:
        if source:
            source.close()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (output / 'reference-report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(report['status'], output / 'reference-report.json', flush=True)
    return 0 if report['status'] == 'control_points_connected_unverified' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--output', required=True)
    parser.add_argument('--bin', required=True, help='Directory containing the Hugin CLI executables and libraries')
    parser.add_argument('--hfov', type=float, default=50, help='Assumed initial horizontal FOV; not measured camera calibration')
    parser.add_argument('--timeout', type=int, default=900, help='Per-stage timeout in seconds')
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.input, args.output, args.bin, args.hfov, args.timeout))
    except (InputError, OSError) as error:
        print(f'Cannot start reference: {error}')
        raise SystemExit(2)
