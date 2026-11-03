"""Produce inspectable synthetic artifacts; never a real-room validation result.

Run from panorama-view: .venv/Scripts/python.exe tests/run_synthetic.py
"""
import json
from pathlib import Path
import sys
import time

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyclic_scene import cyclic_scene
from stitch import process
from stitch360 import Calibration


def main():
    cv2.setNumThreads(2)
    cv2.setRNGSeed(7)
    root = Path(__file__).resolve().parents[1]
    folder = root / "output" / f"synthetic-{time.time_ns()}"
    photos = folder / "photos"
    photos.mkdir(parents=True)
    frames, sphere = cyclic_scene()
    files = []
    for i, frame in enumerate(frames):
        path = photos / f"{i:02}.png"
        if not cv2.imwrite(str(path), frame):
            raise RuntimeError("Cannot write synthetic frame")
        files.append(path)
    cv2.imwrite(str(folder / "known_good_synthetic_sphere.jpg"), sphere)
    config = {"model": "rectilinear_square_pixels_centered", "horizontal_fov_deg": 50,
              "source": "Synthetic perspective renderer: 320x480, f=320/(2*tan(25 degrees)); not a phone calibration",
              "reference_pitch_deg": 0}
    (folder / "calibration.json").write_text(json.dumps(config, indent=2))
    calibration = Calibration.read(folder / "calibration.json")
    report = process(files, folder / "synthetic_360.jpg", calibration=calibration, output_width=1536)
    print(json.dumps({key: report[key] for key in ("output", "width_px", "height_px", "bytes", "processing_seconds",
                                                  "horizontal_coverage_deg", "vertical_coverage_deg", "vertical_offset_deg")}, indent=2))
    print("SYNTHETIC ONLY. Viewer, room-photo fidelity and physical Android are untested.")


if __name__ == "__main__":
    main()
