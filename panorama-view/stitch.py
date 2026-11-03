"""Standalone, offline calibrated full-circle room panorama prototype.

This script does not upload images, call a server, or change RentLease.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from errors import PanoramaError
from stitch360 import Calibration, align_ring, MAX_INPUT_FILES, MAX_TOTAL_PIXELS
from projection import project_ring
from closure import seam_diagnostics
MAX_IMAGE_PIXELS = 30_000_000
MAX_INPUT_BYTES = 40 * 1024 * 1024
DEFAULT_MAX_OUTPUT_BYTES = 9_500_000  # Below a decimal 10 MB bucket limit
DEFAULT_PROCESS_LONG_EDGE = 1200
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

STATUS_MESSAGES = {
    cv2.Stitcher_ERR_NEED_MORE_IMGS: "Too few photos could be matched. Increase overlap or photograph more textured areas.",
    cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Could not align photos. Avoid motion and keep a stable camera viewpoint.",
    cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera alignment failed. Retake the complete circle with steadier, overlapping photos.",
}


def natural_sort_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def collect_images(directory: Path | None, image_paths: list[Path] | None) -> list[Path]:
    if directory is not None:
        if not directory.is_dir():
            raise PanoramaError(f"Input directory not found: {directory}")
        unsupported = [p.name for p in directory.iterdir() if p.is_file()
                       and not p.name.startswith(".") and p.suffix.lower() not in SUPPORTED_SUFFIXES | {".json"}]
        if unsupported:
            raise PanoramaError(f"Unsupported files in capture directory: {', '.join(unsupported)}. Convert photos explicitly; no frames are silently dropped.")
        paths = sorted(
            (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES),
            key=natural_sort_key,
        )
    else:
        paths = image_paths or []
    if len(paths) < 6:
        raise PanoramaError("At least 6 distinct overlapping photos covering one complete circle are required.")
    if len(paths) > MAX_INPUT_FILES:
        raise PanoramaError(f"Only {MAX_INPUT_FILES} photos are supported per experiment.")
    if len(set(p.resolve() for p in paths)) != len(paths):
        raise PanoramaError("Duplicate input file paths are not allowed.")
    return paths


def load_image(path: Path, max_long_edge: int = DEFAULT_PROCESS_LONG_EDGE, *, require_opaque: bool = False) -> np.ndarray:
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise PanoramaError(f"Unsupported file extension: {path.name}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PanoramaError(f"Cannot access {path}: {exc}") from exc
    if size == 0 or size > MAX_INPUT_BYTES:
        raise PanoramaError(f"Invalid or oversized input file: {path.name}")
    try:
        with Image.open(path) as source:
            if source.format not in SUPPORTED_FORMATS:
                raise PanoramaError(f"Not a supported JPEG/PNG/WebP file: {path.name}")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise PanoramaError(f"Image exceeds {MAX_IMAGE_PIXELS} pixels: {path.name}")
            source.verify()
        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source)
            width, height = source.size
            if width < 160 or height < 160:
                raise PanoramaError(f"Image too small (minimum 160x160): {path.name}")
            if width * height > MAX_IMAGE_PIXELS:
                raise PanoramaError(f"Image exceeds {MAX_IMAGE_PIXELS} pixels: {path.name}")
            # Compositing transparent pixels over white prevents artificial black holes.
            if "A" in source.getbands() or "transparency" in source.info:
                rgba = source.convert("RGBA")
                if require_opaque and rgba.getchannel("A").getextrema()[0] < 255:
                    raise PanoramaError("Transparent pixels are not photographed content; use opaque source photos for 360-degree validation.")
                rgb = Image.new("RGB", rgba.size, "white")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
            else:
                rgb = source.convert("RGB")
            if max_long_edge < 200 or max_long_edge > 6000:
                raise PanoramaError("Processing long-edge limit must be between 200 and 6000 pixels.")
            if max(rgb.size) > max_long_edge:
                rgb.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
            return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR).copy()
    except PanoramaError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise PanoramaError(f"Unreadable or corrupted image {path.name}: {exc}") from exc


def baseline_stitch_images(images: list[np.ndarray]) -> np.ndarray:
    """High-level comparison only: NEVER evidence of a verified 360-degree loop."""
    if len(images) < 2:
        raise PanoramaError("Need at least two photographs.")
    try:
        stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
        status, panorama = stitcher.stitch(images)
    except cv2.error as exc:
        raise PanoramaError(f"OpenCV stitching error: {exc}") from exc
    if status != cv2.Stitcher_OK:
        raise PanoramaError(f"OpenCV status {status}: {STATUS_MESSAGES.get(status, 'Unknown stitching failure.')}")
    if panorama is None or panorama.size == 0:
        raise PanoramaError("OpenCV reported success but returned an empty panorama.")
    # OpenCV can return OK while quietly omitting one or more photos.
    # Never present a partial room capture as a complete panorama.
    used_indices = [int(x) for x in stitcher.component()]
    if sorted(used_indices) != list(range(len(images))):
        missing = sorted(set(range(len(images))) - set(used_indices))
        raise PanoramaError(
            f"Stitching was incomplete: {len(used_indices)} of {len(images)} "
            f"photos used (missing indices {missing}). Increase overlap or retake."
        )
    return panorama


def encode_under_limit(panorama: np.ndarray, max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES - 1) -> tuple[bytes, tuple[int, int]]:
    if max_bytes < 10_000 or max_bytes >= DEFAULT_MAX_OUTPUT_BYTES:
        raise PanoramaError("Maximum output size must be between 10000 and 9499999 bytes.")
    current = panorama
    for _ in range(8):
        for quality in (93, 88, 82, 76, 70):
            ok, buffer = cv2.imencode(
                ".jpg", current,
                [cv2.IMWRITE_JPEG_QUALITY, quality, cv2.IMWRITE_JPEG_OPTIMIZE, 1],
            )
            if not ok:
                raise PanoramaError("JPEG encoder failed.")
            if buffer.nbytes <= max_bytes:
                return buffer.tobytes(), (current.shape[1], current.shape[0])
        h, w = current.shape[:2]
        if min(h, w) < 400:
            break
        current = cv2.resize(current, (max(1, round(w * .85)), max(1, round(h * .85))), interpolation=cv2.INTER_AREA)
    raise PanoramaError("Could not compress panorama under the storage limit without excessive downsizing.")


def process(input_files: list[Path], output: Path, *, calibration: Calibration | None = None,
            max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES - 1,
            max_long_edge: int = DEFAULT_PROCESS_LONG_EDGE, output_width: int = 2048) -> dict:
    sidecar = output.with_suffix(".json")
    originals = {path.resolve() for path in input_files}
    if output.resolve() in originals or sidecar.resolve() in originals:
        raise PanoramaError("Output path would overwrite an input photograph. Choose another output file.")
    if output.suffix.lower() not in {".jpg", ".jpeg"}:
        raise PanoramaError("Output must be a .jpg or .jpeg file.")
    if output.exists() or sidecar.exists():
        raise PanoramaError("Output or metadata already exists; choose a new output name.")
    if calibration is None:
        raise PanoramaError("Measured camera calibration is required; angular coverage cannot be guessed.")
    calibration.validate()
    input_files = collect_images(None, input_files)
    start = time.perf_counter()
    images, total = [], 0
    for path in input_files:
        image = load_image(path, max_long_edge=max_long_edge, require_opaque=True)
        total += image.shape[0] * image.shape[1]
        if total > MAX_TOTAL_PIXELS:
            raise PanoramaError("Processing pixel budget exceeded; reduce --max-long-edge.")
        images.append(image)
    try:
        rotations, k, diagnostics = align_ring(images, calibration)
        panorama, projection = project_ring(images, rotations, k, calibration, width=output_width)
        encoded, encoded_size = encode_under_limit(panorama, max_bytes=max_bytes)
        decoded = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)
        jpeg_seam = seam_diagnostics(decoded)
    except cv2.error as exc:
        raise PanoramaError(f"Incomplete panorama: OpenCV processing failed: {exc}") from exc
    report = {
        "schema_version": 1, "output": str(output), **projection,
        "width_px": encoded_size[0], "height_px": encoded_size[1],
        "bytes": len(encoded), "input_count": len(images),
        "processing_seconds": round(time.perf_counter() - start, 3),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "coverage_validation_status": "verified_calibrated_rotation_model",
        "closure_verified": True, "diagnostics": diagnostics,
        "jpeg_seam_diagnostics": jpeg_seam,
        "warnings": ["Automated model checks do not replace real-room visual review for parallax, mirrors or moving objects.",
                     "Vertical geometry depends on the supplied calibration and first-frame pitch reference."]}
    # Serialize first. Exclusive creation prevents overwriting originals or previous
    # results. JSON is the completion marker; consumers also check its JPEG hash.
    metadata = json.dumps(report, indent=2, allow_nan=False).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for path, data in ((output, encoded), (sidecar, metadata)):
            with path.open("xb") as stream:
                created.append(path)
                stream.write(data)
    except OSError:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, calibrated full 360-degree horizontal stitching.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-dir", type=Path, help="One ordered capture set; filenames sorted numerically.")
    group.add_argument("--images", type=Path, nargs="+", help="Ordered input photo paths.")
    parser.add_argument("--calibration", type=Path, required=True, help="Measured rectilinear camera calibration JSON.")
    parser.add_argument("--output", type=Path, required=True, help="New .jpg path; exports a matching .json sidecar.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES - 1)
    parser.add_argument("--max-long-edge", type=int, default=DEFAULT_PROCESS_LONG_EDGE)
    parser.add_argument("--output-width", type=int, default=2048)
    args = parser.parse_args(argv)
    try:
        inputs = collect_images(args.input_dir, args.images)
        report = process(inputs, args.output, calibration=Calibration.read(args.calibration),
                         max_bytes=args.max_bytes, max_long_edge=args.max_long_edge, output_width=args.output_width)
    except (PanoramaError, OSError, cv2.error) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


