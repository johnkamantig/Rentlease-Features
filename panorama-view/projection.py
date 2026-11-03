"""Periodic equirectangular resampling and OpenCV exposure/seam/blending.

Inverse ray maps let one fixed circumference cross longitude zero exactly.
OpenCV's ordinary rectangular crop is deliberately absent. Only complete rows
of genuine source-mask coverage may survive the vertical crop.
"""
import cv2
import numpy as np

from closure import seam_diagnostics
from errors import IncompletePanoramaError, PanoramaError

MAX_WARP_PIXELS = 24_000_000


def complete_rows(mask):
    valid = np.all(mask > 0, axis=1)
    changes = np.diff(np.r_[False, valid, False].astype(int))
    starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
    if not len(starts):
        raise IncompletePanoramaError("missing horizontal sectors: no fully photographed row.")
    index = np.argmax(ends - starts)
    return int(starts[index]), int(ends[index])


def project_ring(images, rotations, k, calibration, width=2048):
    if not 512 <= width <= 4096:
        raise PanoramaError("Output width must be between 512 and 4096 pixels.")
    scale = width / (2 * np.pi)
    # This is a work envelope, not reported coverage. Masks determine coverage.
    half_angle = min(np.deg2rad(75), np.arctan(images[0].shape[0] / (2 * k[1, 1])) + np.deg2rad(16))
    half_rows = int(np.ceil(scale * half_angle))
    height = half_rows * 2
    pad = 64  # exceeds the support of the four-level multiband pyramid
    padded_width = width + 2 * pad
    if len(images) * padded_width * height > MAX_WARP_PIXELS:
        raise PanoramaError("Warp memory budget exceeded; reduce --output-width or input count.")
    lon, down = np.meshgrid((np.arange(-pad, width + pad) + .5) / scale,
                            (np.arange(height) - half_rows + .5) / scale)
    rays = np.stack([np.cos(down) * np.sin(lon), np.sin(down), np.cos(down) * np.cos(lon)], -1)
    pitch = np.deg2rad(calibration.reference_pitch_deg)
    level = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]])
    warped, masks = [], []
    coverage = np.zeros((height, padded_width), np.uint8)
    for image, rotation in zip(images, rotations):
        local = rays @ (level @ rotation)
        z = local[..., 2]
        safe_z = np.where(z > 1e-6, z, 1)
        mx = (local[..., 0] / safe_z * k[0, 0] + k[0, 2]).astype(np.float32)
        my = (local[..., 1] / safe_z * k[1, 1] + k[1, 2]).astype(np.float32)
        h, w = image.shape[:2]
        valid = (z > 1e-6) & (mx >= 1) & (mx < w - 2) & (my >= 1) & (my < h - 2)
        mask = valid.astype(np.uint8) * 255
        sample = cv2.remap(image, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        sample[~valid] = 0
        warped.append(sample)
        masks.append(mask)
        coverage |= mask
    top, bottom = complete_rows(coverage)
    if bottom - top < scale * np.deg2rad(20):
        raise IncompletePanoramaError("less than 20 degrees of fully covered vertical content remains.")
    warped = [im[top:bottom].copy() for im in warped]
    masks = [m[top:bottom].copy() for m in masks]
    corners = [(0, 0)] * len(images)
    compensator = cv2.detail.ExposureCompensator_createDefault(cv2.detail.ExposureCompensator_GAIN)
    compensator.feed(corners, warped, masks)
    for i in range(len(images)):
        compensator.apply(i, corners[i], warped[i], masks[i])
    overlaps = []
    for i in range(len(images)):
        j = (i + 1) % len(images)
        shared = (masks[i] > 0) & (masks[j] > 0)
        if np.count_nonzero(shared) < 100:
            raise IncompletePanoramaError(f"no usable projected overlap for pair {i}->{j}.")
        difference = np.mean(np.abs(warped[i][shared].astype(float) - warped[j][shared]), axis=1)
        median, p90 = (float(x) for x in np.percentile(difference, [50, 90]))
        if median > 22 or p90 > 65:
            raise IncompletePanoramaError(f"overlap disagreement for pair {i}->{j}; possible ghosting, parallax or motion.")
        overlaps.append({"from": i, "to": j, "median_rgb_difference": median, "p90_rgb_difference": p90})
    # Tight rectangles keep seam processing bounded; the periodic padding still
    # gives the zero-longitude source genuine pixels on both sides of the cut.
    cropped_images, cropped_masks, corners = [], [], []
    for im, mask in zip(warped, masks):
        x, y, w, h = cv2.boundingRect(mask)
        if not w or not h:
            raise IncompletePanoramaError("a photograph contributes no projected content.")
        cropped_images.append(im[y:y+h, x:x+w].copy())
        cropped_masks.append(mask[y:y+h, x:x+w].copy())
        corners.append((x, y))
    seam_finder = cv2.detail_DpSeamFinder("COLOR_GRAD")
    seam_masks = seam_finder.find([im.astype(np.float32) for im in cropped_images], corners, cropped_masks)
    blender = cv2.detail_MultiBandBlender()
    blender.setNumBands(4)
    blender.prepare((0, 0, padded_width, bottom - top))
    for im, mask, corner in zip(cropped_images, seam_masks, corners):
        mask = mask.get() if hasattr(mask, "get") else mask
        blender.feed(im.astype(np.int16), mask, corner)
    blended, blend_mask = blender.blend(None, None)
    if not np.all(blend_mask[:, pad:pad + width] > 0):
        raise IncompletePanoramaError("blending left unexplained empty regions.")
    result = np.clip(blended[:, pad:pad + width], 0, 255).astype(np.uint8)
    report = seam_diagnostics(result)
    report.update({"overlaps": overlaps, "source_mask_coverage_fraction": 1.0,
                   "periodic_padding_px": pad})
    return result, {"projection": "partial_equirectangular", "horizontal_coverage_deg": 360,
                    "vertical_coverage_deg": float(np.rad2deg((bottom - top) / scale)),
                    "vertical_offset_deg": float(-np.rad2deg(((top + bottom) / 2 - half_rows) / scale)),
                    "vertical_calibration": "fixed supplied intrinsics; square pixels; first-frame pitch reference",
                    "projection_diagnostics": report}
