"""Inspectable CYCLIC SYNTHETIC video, accepted output and viewer test assets.

This generates mathematical fixtures only, never real property imagery.
Run from panorama-view: .venv/Scripts/python.exe tests/run_video_synthetic.py
"""
from pathlib import Path
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyclic_scene import cyclic_scene
from room_validation import new_folder, write_json
from video_ingestion import extract_video, evaluate_selection, Settings


def main():
    cv2.setNumThreads(2); cv2.setRNGSeed(7)
    root = Path(__file__).resolve().parents[1]
    output = new_folder(root/'output/continuous-sweep'/f'synthetic-{time.time_ns()}')
    frames, _ = cyclic_scene(headings=np.arange(0, 360, 3))
    path = output/'synthetic.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 12, (320,480))
    if not writer.isOpened():
        raise RuntimeError('MJPG video encoder unavailable')
    try:
        for image in frames:
            writer.write(image)
    finally:
        writer.release()
    calibration = output/'calibration.json'
    write_json(calibration, {'model':'rectilinear_square_pixels_centered', 'horizontal_fov_deg':50,
                            'reference_pitch_deg':0, 'source':'Exact synthetic ray-renderer intrinsics; not phone calibration'})
    selection = extract_video(path, output/'run', Settings(min_sharpness=5), data_kind='synthetic_test')
    print('SYNTHETIC:', selection['decoded_frames'], 'decoded;', selection['selected_count'], 'selected', flush=True)
    result = evaluate_selection(output/'run', calibration, width=1024)
    if not result.get('coverage_verified'):
        raise RuntimeError(f'Synthetic video rejected: {result}')
    print('SYNTHETIC ONLY:', result['stitch']['panorama']['output'], flush=True)


if __name__ == '__main__':
    main()
