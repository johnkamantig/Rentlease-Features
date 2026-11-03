"""Calibrated OpenCV ring matching and fixed-intrinsic global refinement.

Only rectilinear, orientation-corrected, same-lens photographs are supported.
Calibration is explicit: a guessed phone FOV is not sufficient.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from closure import nearest_rotation, rotation_angle, validate_rotations, validate_steps, yaw
from errors import PanoramaError, IncompletePanoramaError

MAX_INPUT_FILES = 72
MAX_TOTAL_PIXELS = 36_000_000


@dataclass(frozen=True)
class Calibration:
    horizontal_fov_deg: float
    source: str
    reference_pitch_deg: float = 0.0
    headings_deg: list | None = None

    def validate(self):
        if not np.isfinite(self.horizontal_fov_deg) or not 25 <= self.horizontal_fov_deg <= 100:
            raise PanoramaError("Calibration horizontal_fov_deg must be between 25 and 100 degrees.")
        if not isinstance(self.source, str) or not self.source.strip():
            raise PanoramaError("Calibration requires a documented measurement source.")
        if not np.isfinite(self.reference_pitch_deg) or abs(self.reference_pitch_deg) > 10:
            raise PanoramaError("Calibration reference_pitch_deg must be finite and within 10 degrees of level.")
        if self.headings_deg is not None:
            try:
                headings = np.asarray(self.headings_deg, dtype=float)
                if headings.ndim != 1 or not np.isfinite(headings).all():
                    raise ValueError("expected finite angles")
            except (TypeError, ValueError) as exc:
                raise PanoramaError("Calibration headings_deg must be a list of finite angles.") from exc

    @classmethod
    def read(cls, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("calibration must be a JSON object")
            if data.pop("model", None) != "rectilinear_square_pixels_centered":
                raise ValueError("expected model rectilinear_square_pixels_centered")
            result = cls(**data)
            result.validate()
            return result
        except (OSError, ValueError, TypeError) as exc:
            raise PanoramaError(f"Invalid calibration: {exc}") from exc


def align_ring(images, calibration):
    calibration.validate()
    count = len(images)
    if not 6 <= count <= MAX_INPUT_FILES:
        raise IncompletePanoramaError(f"use 6–{MAX_INPUT_FILES} distinct ordered photographs covering one turn.")
    if sum(im.shape[0] * im.shape[1] for im in images) > MAX_TOTAL_PIXELS:
        raise PanoramaError("Processing pixel budget exceeded; reduce --max-long-edge.")
    height, width = images[0].shape[:2]
    if any(im.shape != images[0].shape or im.dtype != np.uint8 for im in images):
        raise IncompletePanoramaError("all photographs must have the same oriented dimensions and lens settings.")
    hashes = [hashlib.sha256(im.tobytes()).digest() for im in images]
    if len(set(hashes)) != count:
        raise IncompletePanoramaError("duplicate photographs; remove exact repeats and capture distinct headings.")
    # Re-encoded copies must not pass as additional sectors either.
    thumbs = [cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (48, 64),
                         interpolation=cv2.INTER_AREA).astype(float) for im in images]
    for i in range(count):
        for j in range(i):
            if np.mean(np.abs(thumbs[i] - thumbs[j])) < 1.5:
                raise IncompletePanoramaError(f"near-duplicate photographs at indices {j}, {i}.")

    f = width / (2 * np.tan(np.deg2rad(calibration.horizontal_fov_deg / 2)))
    finder = cv2.SIFT_create(nfeatures=3500)
    features = [cv2.detail.computeImageFeatures2(finder, im) for im in images]
    low_feature_indices = [i+1 for i, feat in enumerate(features) if len(feat.keypoints) < 30]
    if low_feature_indices:
        raise IncompletePanoramaError(f"feature matching failed: insufficient textured image features in photos {low_feature_indices}; at least 30 keypoints per photo are required.")
    mask = np.zeros((count, count), np.uint8)
    for i in range(count):
        mask[i, (i + 1) % count] = mask[(i + 1) % count, i] = 1
    # OpenCV's default confidence>3 suppression discards very well textured
    # overlaps. Keep them; explicit duplicate and angular checks handle repeats.
    matcher = cv2.detail_BestOf2NearestMatcher.create(False, .65, 6, 6, 4.0)
    matches = matcher.apply2(features, mask)
    matcher.collectGarbage()
    centered_k = np.diag([f, f, 1.0])
    rotations = [np.eye(3)]
    relative = []
    edges = []
    correspondences = []
    for i in range(count):
        j = (i + 1) % count
        match = matches[i * count + j]
        pairs = match.getMatches()
        inliers = np.asarray(match.getInliers(), dtype=bool)
        label = "first-to-last closure" if j == 0 else f"neighbor {i}->{j}"
        if match.H is None or match.num_inliers < 25 or match.confidence < .7 or match.num_inliers / max(1, len(pairs)) < .45:
            raise IncompletePanoramaError(f"{label} feature matching failed or overlap is too weak.")
        selected = [pair for pair, valid in zip(pairs, inliers) if valid]
        p = np.array([features[i].keypoints[m.queryIdx].pt for m in selected])
        q = np.array([features[j].keypoints[m.trainIdx].pt for m in selected])
        if np.ptp(p[:, 0]) < width * .12 or np.ptp(p[:, 1]) < height * .25:
            raise IncompletePanoramaError(f"{label} matches are too spatially concentrated.")
        transform = np.linalg.inv(centered_k) @ match.H @ centered_k
        if not np.isfinite(transform).all() or abs(np.linalg.det(transform)) < 1e-9:
            raise IncompletePanoramaError(f"{label} has singular or non-finite geometry.")
        if np.linalg.det(transform) < 0:
            transform = -transform
        transform /= np.cbrt(np.linalg.det(transform))
        r = nearest_rotation(transform)
        if np.max(np.abs(np.linalg.svd(transform)[1] - 1)) > .08:
            raise IncompletePanoramaError(f"{label} geometry disagrees with calibrated camera rotation (parallax or wrong FOV).")
        relative.append(r)
        if j:
            rotations.append(rotations[-1] @ r.T)
        correspondences.append((p, q))
        edges.append({"from": i, "to": j, "inliers": int(match.num_inliers),
                      "inlier_ratio": match.num_inliers / len(pairs), "confidence": float(match.confidence)})

    # Check the unconstrained motion before optimization can hide a wrong loop.
    raw = validate_steps([-yaw(r) for r in relative], calibration.horizontal_fov_deg)
    closure = np.eye(3)
    for r in relative:
        closure = closure @ r.T
    closure_error = rotation_angle(closure)
    if closure_error > 3:
        raise IncompletePanoramaError(f"first-to-last alignment drift is {closure_error:.2f} degrees.")

    cameras = []
    for r in rotations:
        camera = cv2.detail_CameraParams()
        camera.focal, camera.aspect = f, 1.0
        camera.ppx, camera.ppy = width / 2, height / 2
        camera.R = r.astype(np.float32)
        camera.t = np.zeros((3, 1), np.float64)
        cameras.append(camera)
    adjuster = cv2.detail_BundleAdjusterReproj()
    adjuster.setConfThresh(.7)
    adjuster.setRefinementMask(np.zeros((3, 3), np.uint8))
    ok, cameras = adjuster.apply(features, matches, cameras)
    if not ok:
        raise IncompletePanoramaError("global circular camera refinement failed.")
    origin = cameras[0].R.T
    rotations = [origin @ c.R for c in cameras]
    geometry = validate_rotations(rotations, calibration.horizontal_fov_deg, calibration.headings_deg)
    k = np.array([[f, 0, width / 2], [0, f, height / 2], [0, 0, 1]])
    for i, (p, q) in enumerate(correspondences):
        j = (i + 1) % count
        homography = k @ rotations[j].T @ rotations[i] @ np.linalg.inv(k)
        predicted = cv2.perspectiveTransform(p.astype(np.float64)[None], homography)[0]
        error = np.linalg.norm(predicted - q, axis=1)
        residual = float(np.percentile(error, 95))
        if residual > max(2.5, width * .006):
            raise IncompletePanoramaError(f"refined pair {i}->{j} alignment residual {residual:.2f}px exceeds tolerance.")
        edges[i]["reprojection_p95_px"] = residual
    return rotations, k, {**geometry, "raw_turn_deg": raw["signed_turn_deg"],
                           "raw_closure_error_deg": closure_error, "pairs": edges,
                           "calibration_source": calibration.source,
                           "calibration_model": "rectilinear_square_pixels_centered",
                           "horizontal_fov_deg": calibration.horizontal_fov_deg}
