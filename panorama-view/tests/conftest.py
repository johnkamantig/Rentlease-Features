import sys
from pathlib import Path

import cv2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyclic_scene import cyclic_scene
from stitch360 import Calibration, align_ring


@pytest.fixture(autouse=True)
def deterministic_opencv():
    cv2.setNumThreads(2)
    cv2.setRNGSeed(7)


@pytest.fixture(scope="session")
def scene():
    return cyclic_scene()


@pytest.fixture(scope="session")
def calibration():
    return Calibration(50, "synthetic pinhole ground truth; first frame level")


@pytest.fixture(scope="session")
def aligned(scene, calibration):
    cv2.setNumThreads(2)
    cv2.setRNGSeed(7)
    return align_ring(scene[0], calibration)
