"""Fail-closed checks on image-derived rotations, independent of blending."""
import cv2
import numpy as np

from errors import IncompletePanoramaError


def rotation_angle(rotation):
    return float(np.rad2deg(np.linalg.norm(cv2.Rodrigues(rotation.astype(float))[0])))


def nearest_rotation(matrix):
    u, _, vt = np.linalg.svd(matrix)
    return u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt


def yaw(rotation):
    return float(np.rad2deg(np.arctan2(rotation[0, 2], rotation[2, 2])))


def validate_steps(steps, hfov):
    steps = np.asarray(steps)
    if not np.isfinite(steps).all():
        raise IncompletePanoramaError("non-finite camera geometry.")
    direction = np.sign(np.median(steps))
    if np.any(steps * direction < 3):
        raise IncompletePanoramaError("incorrect ordering, reversed motion or duplicated sectors.")
    if np.any(np.abs(steps) > hfov * .75):
        raise IncompletePanoramaError("missing horizontal coverage or insufficient neighbor overlap.")
    total = float(np.sum(steps))
    if abs(abs(total) - 360) > 4:
        raise IncompletePanoramaError(f"a single full revolution is unverified (image-derived turn {total:.2f} degrees).")
    return {"signed_turn_deg": total, "neighbor_steps_deg": steps.tolist()}


def validate_rotations(rotations, hfov, headings=None):
    angles = np.array([yaw(r) for r in rotations])
    steps = (np.roll(angles, -1) - angles + 180) % 360 - 180
    report = validate_steps(steps, hfov)
    for r in rotations:
        pitch = np.rad2deg(np.arcsin(np.clip(r[1, 2], -1, 1)))
        roll = np.rad2deg(np.arctan2(r[1, 0], r[1, 1]))
        if abs(pitch) > 15 or abs(roll) > 15:
            raise IncompletePanoramaError("camera tilt exceeds the single horizontal row model.")
    # Guidance metadata can veto inconsistent results; it can never prove a loop.
    if headings is not None:
        h = np.asarray(headings, dtype=float)
        if h.shape != angles.shape or not np.isfinite(h).all():
            raise IncompletePanoramaError("heading metadata must contain one finite angle per image.")
        sensor_steps = (np.roll(h, -1) - h + 180) % 360 - 180
        if np.max(np.abs(sensor_steps - steps)) > 12:
            raise IncompletePanoramaError("orientation metadata disagrees with image-derived motion.")
        report["orientation_metadata_consistent"] = True
    return report


def seam_diagnostics(image):
    """Reject unusually strong boundary jumps relative to ordinary column edges.

    Necessary quality gate, not a guarantee against every local ghost or parallax.
    """
    values = image.astype(np.float32)
    edges = np.mean(np.abs(np.diff(values, axis=1)), axis=(0, 2))
    wrap = float(np.mean(np.abs(values[:, 0] - values[:, -1])))
    threshold = max(12.0, float(np.percentile(edges, 95)) * 3)
    if wrap > threshold:
        raise IncompletePanoramaError(f"wrap boundary discontinuity ({wrap:.2f} > {threshold:.2f}).")
    return {"wrap_mean_absolute_difference": wrap, "wrap_threshold": threshold}
