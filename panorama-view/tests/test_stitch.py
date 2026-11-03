import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stitch import (
    PanoramaError, collect_images, load_image, baseline_stitch_images,
    encode_under_limit, process,
)


def test_requires_six_photos(tmp_path):
    (tmp_path / "01.jpg").write_bytes(b"x")
    with pytest.raises(PanoramaError, match="At least 6"):
        collect_images(tmp_path, None)


def test_sort_photo_number_naturally(tmp_path):
    for name in ("photo10.jpg", "photo2.jpg", "photo1.jpg", "photo3.jpg", "photo4.jpg", "photo5.jpg"):
        (tmp_path / name).write_bytes(b"test")
    names = [p.name for p in collect_images(tmp_path, None)]
    assert names == ["photo1.jpg", "photo2.jpg", "photo3.jpg", "photo4.jpg", "photo5.jpg", "photo10.jpg"]


def test_reject_corrupted_image(tmp_path):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"this is not an image")
    with pytest.raises(PanoramaError, match="corrupted"):
        load_image(path)


def test_reject_small_image(tmp_path):
    path = tmp_path / "tiny.png"
    Image.new("RGB", (80, 80)).save(path)
    with pytest.raises(PanoramaError, match="too small"):
        load_image(path)


def test_exif_orientation(tmp_path):
    path = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (180, 300), color=(70, 120, 190))
    exif = image.getexif()
    exif[274] = 6  # rotate 90 degrees clockwise for correct display
    image.save(path, exif=exif)
    result = load_image(path)
    assert result.shape[:2] == (180, 300)


def test_encoding_under_size_limit():
    image = np.random.default_rng(8).integers(0, 255, (600, 2000, 3), dtype=np.uint8)
    output, output_size = encode_under_limit(image, max_bytes=350_000)
    assert len(output) <= 350_000
    decoded = cv2.imdecode(np.frombuffer(output, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert (decoded.shape[1], decoded.shape[0]) == output_size


def test_failed_stitch_status_is_reported(monkeypatch):
    class FailureStitcher:
        def stitch(self, images):
            return cv2.Stitcher_ERR_NEED_MORE_IMGS, None
    monkeypatch.setattr(cv2, "Stitcher_create", lambda mode: FailureStitcher())
    with pytest.raises(PanoramaError, match="Too few photos"):
        baseline_stitch_images([np.ones((200, 200, 3), np.uint8)] * 2)


def test_success_with_dropped_photo_is_rejected(monkeypatch):
    class IncompleteStitcher:
        def stitch(self, images):
            return cv2.Stitcher_OK, np.ones((280, 700, 3), np.uint8)
        def component(self):
            return np.array([0, 1])
    monkeypatch.setattr(cv2, "Stitcher_create", lambda mode: IncompleteStitcher())
    with pytest.raises(PanoramaError, match="incomplete"):
        baseline_stitch_images([np.ones((200, 200, 3), np.uint8)] * 3)


def test_does_not_overwrite_input(tmp_path):
    image = tmp_path / "source.jpg"
    Image.new("RGB", (200, 200)).save(image)
    before = image.read_bytes()
    with pytest.raises(PanoramaError, match="overwrite"):
        process([image, image], image)
    assert image.read_bytes() == before


def test_photo_downscale_preserves_aspect_ratio(tmp_path):
    path = tmp_path / "big.jpg"
    Image.new("RGB", (3200, 2400), color=(80, 90, 100)).save(path)
    result = load_image(path)
    assert result.shape[:2] == (900, 1200)


def test_transparent_image_composited_on_white(tmp_path):
    path = tmp_path / "transparent.png"
    image = Image.new("RGBA", (220, 220), (255, 0, 0, 0))
    image.save(path)
    result = load_image(path)
    assert tuple(int(v) for v in result[100, 100]) == (255, 255, 255)
