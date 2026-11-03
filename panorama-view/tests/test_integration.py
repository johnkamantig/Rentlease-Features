"""OpenCV integration smoke test with synthetic overlapping imagery, not room photos."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stitch import baseline_stitch_images


def test_baseline_linear_stitch_is_only_a_regression():
    rng = np.random.default_rng(14)
    base = np.full((600, 1500, 3), 180, dtype=np.uint8)
    for _ in range(350):
        x = int(rng.integers(0, 1500))
        y = int(rng.integers(0, 600))
        r = int(rng.integers(4, 24))
        color = tuple(int(c) for c in rng.integers(20, 240, size=3))
        cv2.circle(base, (x, y), r, color, -1)
    frames = [base[:, x:x + 750].copy() for x in (0, 350, 700)]
    result = baseline_stitch_images(frames)
    assert result.shape[1] > 1250
    assert result.shape[0] > 300
