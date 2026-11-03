"""Fresh-process resolution/memory experiments using SYNTHETIC inputs only.

Run from panorama-view after tests/run_synthetic.py has supplied a source set:
  .venv/Scripts/python.exe tests/benchmark_resolution.py --source output/synthetic-... --output output/resolution-trial
No real-room sharpness or physical-device claim follows from this benchmark.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from room_validation import import_capture, new_folder, project_input, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.source = project_input(args.source)
    photos = sorted(project_input(args.source / 'photos').glob('*.png'))
    if not photos:
        raise SystemExit('No synthetic PNG frames in source/photos.')
    output = new_folder(args.output)
    order = output / 'order.json'
    write_json(order, {'schema_version': 1, 'data_kind': 'synthetic_test',
                       'capture_notes': 'Resolution and resource experiment, not real-room evidence.',
                       'images': [str(path.resolve()) for path in photos]})
    import_capture(order, output / 'capture')
    results = []
    for width in (1536, 2048, 2560, 3072, 4096):
        folder = output / f'width-{width}'
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'room_validation.py'), 'stitch',
                   '--capture', str(output / 'capture/capture.json'),
                   '--calibration', str((args.source / 'calibration.json').resolve()),
                   '--width', str(width), '--output', str(folder)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        report_path = folder / 'validation.json'
        report = json.loads(report_path.read_text()) if report_path.exists() else {'status': 'runner_failed', 'error': completed.stderr}
        report['exit_code'] = completed.returncode
        results.append(report)
        print(width, report['status'], report.get('elapsed_seconds'), report.get('memory'), flush=True)
    write_json(output / 'summary.json', {'data_kind': 'synthetic_test', 'runs': results,
                                        'limitation': 'Original frames are only 320x480. More output pixels do not prove additional photographed detail or tenant usability.'})


if __name__ == '__main__':
    main()
