import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from closure import seam_diagnostics, validate_rotations, validate_steps
from errors import PanoramaError, IncompletePanoramaError
from projection import complete_rows, project_ring
from stitch import collect_images, encode_under_limit, load_image, main, process
from stitch360 import Calibration, align_ring


def test_complete_ring_closes_with_image_evidence(aligned):
    _, _, diagnostics = aligned
    assert diagnostics["signed_turn_deg"] == pytest.approx(360, abs=.01)
    assert diagnostics["raw_turn_deg"] == pytest.approx(360, abs=.2)
    assert diagnostics["raw_closure_error_deg"] < .2
    pairs = diagnostics["pairs"]
    assert len(pairs) == 18
    assert (pairs[-1]["from"], pairs[-1]["to"]) == (17, 0)
    assert min(p["inliers"] for p in pairs) > 25
    assert max(p["reprojection_p95_px"] for p in pairs) < .5


def test_periodic_projection_matches_all_ground_truth_sectors(scene, calibration, aligned):
    rotations, k, _ = aligned
    output, report = project_ring(scene[0], rotations, k, calibration, width=1536)
    assert report["horizontal_coverage_deg"] == 360
    assert 65 < report["vertical_coverage_deg"] < 72
    assert output.shape[1] == 1536
    assert output.shape[0] < output.shape[1] / 2
    assert report["projection_diagnostics"]["source_mask_coverage_fraction"] == 1
    # Independent oracle: resample the source sphere, not another stitched frame.
    texture = scene[1]
    h, w = output.shape[:2]
    lon, down = np.meshgrid((np.arange(w) + .5) * 2 * np.pi / w,
                            (np.arange(h) + .5 - h / 2) * 2 * np.pi / w - np.deg2rad(report["vertical_offset_deg"]))
    expected = cv2.remap(texture, ((lon / (2*np.pi) + .5) * texture.shape[1]).astype(np.float32),
                        ((down / np.pi + .5) * texture.shape[0]).astype(np.float32),
                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    errors = np.mean(np.abs(output.astype(float) - expected), axis=(0, 2))
    assert max(np.mean(part) for part in np.array_split(errors, 18)) < 9
    # Compare a band spanning the cut against the known-good sphere as well.
    assert np.mean(np.r_[errors[:32], errors[-32:]]) < 9
    assert report["projection_diagnostics"]["wrap_mean_absolute_difference"] < 20


def test_reference_pitch_rotates_geometry_and_keeps_correct_vertical_bounds(scene, aligned):
    rotations, k, _ = aligned
    output, report = project_ring(scene[0], rotations, k, Calibration(50, "synthetic pitch reference", 8), width=1024)
    h, w = output.shape[:2]
    longitude, down = np.meshgrid((np.arange(w) + .5) * 2*np.pi / w,
                                  (np.arange(h) + .5 - h/2) * 2*np.pi / w - np.deg2rad(report["vertical_offset_deg"]))
    rays = np.stack([np.cos(down)*np.sin(longitude), np.sin(down), np.cos(down)*np.cos(longitude)], -1)
    angle = np.deg2rad(8)
    level = np.array([[1, 0, 0], [0, np.cos(angle), -np.sin(angle)], [0, np.sin(angle), np.cos(angle)]])
    original = rays @ level
    lon = np.arctan2(original[..., 0], original[..., 2])
    lat = np.arctan2(original[..., 1], np.hypot(original[..., 0], original[..., 2]))
    texture = scene[1]
    expected = cv2.remap(texture, ((lon/(2*np.pi)+.5)*texture.shape[1]).astype(np.float32),
                        ((lat/np.pi+.5)*texture.shape[0]).astype(np.float32),
                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    assert np.mean(np.abs(output.astype(float) - expected)) < 9
    assert report["vertical_coverage_deg"] == pytest.approx(h * 360 / w)


@pytest.mark.parametrize("indices", [list(range(3, 18)), list(range(0, 8)) + list(range(11, 18)),
                                     [0, 2, 1] + list(range(3, 18))])
def test_missing_sequences_and_incorrect_order_are_rejected(scene, calibration, indices):
    with pytest.raises(IncompletePanoramaError):
        align_ring([scene[0][i] for i in indices], calibration)


def test_single_missing_frame_with_weak_overlap_is_rejected(scene, calibration):
    with pytest.raises(IncompletePanoramaError, match="overlap|coverage"):
        align_ring(scene[0][:8] + scene[0][9:], calibration)


def test_matching_first_and_last_does_not_prove_a_revolution(scene, calibration):
    # Turn out then back along the same arc, with near-duplicate frames altered.
    frames = scene[0][:8] + [np.clip(im.astype(int) + 3, 0, 255).astype(np.uint8) for im in scene[0][6:0:-1]]
    with pytest.raises(IncompletePanoramaError):
        align_ring(frames, calibration)


@pytest.mark.parametrize("steps", [[20]*17, [20]*36, [20]*8 + [-20]*8, [0] + [20]*18])
def test_partial_repeated_and_reversed_turns_do_not_validate(steps):
    with pytest.raises(IncompletePanoramaError):
        validate_steps(steps, 50)


def test_clockwise_and_counterclockwise_turns_are_supported(scene, calibration):
    _, _, report = align_ring(list(reversed(scene[0])), calibration)
    assert report["signed_turn_deg"] == pytest.approx(-360, abs=.01)


@pytest.mark.parametrize("reencode", [False, True])
def test_duplicate_photos_are_rejected(scene, calibration, reencode):
    frames = list(scene[0])
    duplicate = frames[2].copy()
    if reencode:
        ok, data = cv2.imencode(".jpg", duplicate, [cv2.IMWRITE_JPEG_QUALITY, 95])
        assert ok
        duplicate = cv2.imdecode(data, cv2.IMREAD_COLOR)
    frames[9] = duplicate
    with pytest.raises(IncompletePanoramaError, match="duplicate"):
        align_ring(frames, calibration)


def test_textureless_frame_fails(scene, calibration):
    frames = list(scene[0])
    frames[4] = np.full_like(frames[4], 120)
    with pytest.raises(IncompletePanoramaError, match="feature matching"):
        align_ring(frames, calibration)


def test_wrong_calibration_fails(scene):
    with pytest.raises(IncompletePanoramaError):
        align_ring(scene[0], Calibration(75, "intentionally incorrect test calibration"))


def test_headings_can_veto_but_cannot_replace_images(aligned):
    rotations, _, _ = aligned
    validate_rotations(rotations, 50, list(range(0, 360, 20)))
    with pytest.raises(IncompletePanoramaError, match="metadata"):
        validate_rotations(rotations, 50, [0]*18)


def test_crop_preserves_entire_width_and_real_dark_content():
    mask = np.zeros((100, 500), np.uint8)
    mask[20:80] = 255
    assert complete_rows(mask) == (20, 80)
    # Pixel colors (including black walls) never determine coverage.
    seam_diagnostics(np.zeros((60, 500, 3), np.uint8))
    mask[:, 240] = 0
    with pytest.raises(IncompletePanoramaError, match="missing horizontal"):
        complete_rows(mask)


def test_obvious_wrap_discontinuity_is_rejected():
    image = np.full((100, 800, 3), 70, np.uint8)
    image[:, -1] = 220
    with pytest.raises(IncompletePanoramaError, match="discontinuity"):
        seam_diagnostics(image)


def test_wrongly_aligned_overlap_cannot_be_hidden_by_blending(scene, calibration, aligned):
    rotations, k, _ = aligned
    wrong = list(scene[0])
    wrong[3] = np.roll(wrong[3], 90, axis=0)
    with pytest.raises(IncompletePanoramaError, match="overlap disagreement"):
        project_ring(wrong, rotations, k, calibration, width=1024)


def test_file_limits_and_natural_order(tmp_path):
    paths = [tmp_path / f"{i}.jpg" for i in range(72)]
    assert len(collect_images(None, paths)) == 72
    with pytest.raises(PanoramaError, match="72"):
        collect_images(None, paths + [tmp_path / "73.jpg"])
    with pytest.raises(PanoramaError, match="Duplicate"):
        collect_images(None, paths[:6] + paths[:1])


def test_warp_budget_rejects_before_allocation(scene, calibration, aligned):
    rotations, k, _ = aligned
    with pytest.raises(PanoramaError, match="memory budget"):
        project_ring(scene[0], rotations, k, calibration, width=4096)


@pytest.mark.parametrize("value", [float("nan"), 0, 120])
def test_invalid_calibration_is_rejected(value):
    with pytest.raises(PanoramaError, match="Calibration"):
        Calibration(value, "test").validate()


def test_missing_calibration_never_exports(tmp_path):
    out = tmp_path / "out.jpg"
    with pytest.raises(PanoramaError, match="calibration"):
        process([], out)
    assert not out.exists()


def test_unsupported_image(tmp_path):
    path = tmp_path / "input.gif"
    Image.new("RGB", (200, 200)).save(path)
    with pytest.raises(PanoramaError, match="Unsupported"):
        load_image(path)


def test_file_size_cap_cannot_be_disabled():
    with pytest.raises(PanoramaError, match="9499999"):
        encode_under_limit(np.zeros((200, 200, 3), np.uint8), 9_500_000)


def test_transparency_cannot_count_as_photographed_content(tmp_path):
    path = tmp_path / "transparent.png"
    Image.new("RGBA", (200, 200), (0, 0, 0, 0)).save(path)
    with pytest.raises(PanoramaError, match="not photographed"):
        load_image(path, require_opaque=True)


def test_capture_directory_cannot_silently_omit_unsupported_photos(tmp_path):
    for i in range(6):
        (tmp_path / f"{i}.jpg").touch()
    (tmp_path / "7.heic").touch()
    with pytest.raises(PanoramaError, match="silently dropped"):
        collect_images(tmp_path, None)


def test_ingestion_pixel_budget(tmp_path, monkeypatch, calibration):
    paths = []
    for i in range(6):
        path = tmp_path / f"{i}.png"
        Image.new("RGB", (200, 200)).save(path)
        paths.append(path)
    monkeypatch.setattr("stitch.MAX_TOTAL_PIXELS", 50_000)
    with pytest.raises(PanoramaError, match="pixel budget"):
        process(paths, tmp_path / "out.jpg", calibration=calibration)
    assert not (tmp_path / "out.jpg").exists()


def test_invalid_calibration_json_is_actionable(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text('{"model":"unknown"}')
    with pytest.raises(PanoramaError, match="Invalid calibration"):
        Calibration.read(path)


def test_export_write_failure_removes_only_new_artifacts(tmp_path, monkeypatch, calibration):
    paths = []
    for i in range(6):
        path = tmp_path / f"{i}.png"
        Image.new("RGB", (200, 200)).save(path)
        paths.append(path)
    monkeypatch.setattr("stitch.align_ring", lambda *args: ([], None, {}))
    monkeypatch.setattr("stitch.project_ring", lambda *args, **kw: (np.full((200, 800, 3), 100, np.uint8), {}))
    original_open = Path.open
    out = tmp_path / "out.jpg"
    sidecar = out.with_suffix(".json")
    def failed_open(path, *args, **kwargs):
        if path == sidecar:
            raise OSError("simulated metadata disk failure")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", failed_open)
    with pytest.raises(OSError, match="disk failure"):
        process(paths, out, calibration=calibration)
    assert not out.exists() and not sidecar.exists()
    assert all(p.exists() for p in paths)


def test_cli_failure_then_real_pipeline_recovery(tmp_path, scene, calibration, capsys):
    folder = tmp_path / "photos"
    folder.mkdir()
    paths = []
    for i, frame in enumerate(scene[0]):
        path = folder / f"{i:02}.png"
        assert cv2.imwrite(str(path), frame)
        paths.append(path)
    hashes = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    config = tmp_path / "calibration.json"
    config.write_text(json.dumps({"model": "rectilinear_square_pixels_centered", "horizontal_fov_deg": 50,
                                 "source": calibration.source}))
    out = tmp_path / "out.jpg"
    args = ["--input-dir", str(folder), "--calibration", str(config), "--output", str(out), "--output-width", "1536"]
    saved = paths[4].read_bytes()
    paths[4].write_bytes(b"corrupted")
    assert main(args) == 1
    assert "corrupted" in capsys.readouterr().err
    assert not out.exists() and not out.with_suffix(".json").exists()
    paths[4].write_bytes(saved)
    assert main(args) == 0
    capsys.readouterr()
    report = json.loads(out.with_suffix(".json").read_text())
    assert report["closure_verified"] is True
    assert report["input_count"] == 18
    assert report["bytes"] == out.stat().st_size < 9_500_000
    assert report["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    with Image.open(out) as result:
        assert result.size == (report["width_px"], report["height_px"])
        assert len(result.getexif()) == 0
    assert [hashlib.sha256(p.read_bytes()).digest() for p in paths] == hashes
    assert main(args) == 1
    assert "already exists" in capsys.readouterr().err
