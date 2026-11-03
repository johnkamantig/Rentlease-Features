# Calibration and local processing contract

Precise vertical geometry is unavailable without trustworthy camera intrinsics. This prototype requires a documented calibration instead of estimating an angle from JPEG aspect ratio or a marketing lens specification.

## Supported calibration

Use a rectilinear image after EXIF orientation, with equal horizontal/vertical focal length in pixels, principal point at `(width/2, height/2)`, and negligible residual distortion. All frames must have the same oriented dimensions and lens settings. A general calibration matrix or distortion model is not implemented here. If your camera cannot satisfy this model, stop and extend the calibration/rectification interface before claiming accurate geometry.

A practical lab procedure is to calibrate the actual lens, focus, zoom and capture resolution against a measured checkerboard using OpenCV camera calibration, and rectify to this centered, square-pixel model. Evaluate residuals on held-out board images and retain that report. Do not resize/crop/reorient frames inconsistently after calibration. Account for portrait orientation: the horizontal dimension is the corrected image width, not the sensor's landscape width. After uniform resizing, `hfov = degrees(2 * atan(width / (2 * fx)))` remains unchanged.

Set `source` to the device/settings and measurement/report identifier. Record uncertainty there: this prototype does not estimate calibration uncertainty. `reference_pitch_deg` is the measured first camera optical axis elevation above the horizon (positive upward), and first-frame roll must be level. The prototype permits reference pitch within +/-10 degrees; its single-row alignment rejects large relative tilts. Pitch correction rotates 3D rays, rather than merely shifting metadata.

JSON shape (replace the null and explanatory strings with measured data; this template intentionally cannot pass validation):

```json
{
  "model": "rectilinear_square_pixels_centered",
  "horizontal_fov_deg": null,
  "source": "REQUIRED: device, lens, zoom, resolution and calibration report",
  "reference_pitch_deg": 0
}
```

Use zero pitch only if the first frame was actually level. Optional `headings_deg` is one finite clockwise angle per ordered frame, in degrees with any common offset. It is checked against image-derived increments (12 degrees disagreement tolerance); it cannot establish a revolution or rescue image failures. No magnetic north or GPS is needed. Sensor noise can cause conservative rejection; omit unreliable headings and document why.

The synthetic runner supplies exact renderer intrinsics, not a reusable phone calibration.

For fresh-smartphone calibration handoff and ordered import commands, see [REAL_ROOM_WORKFLOW.md](REAL_ROOM_WORKFLOW.md). Only measurements for the new capture settings are eligible. Guide headings and nominal zoom cannot supply calibration. Stage the new calibration inside this project; `room_validation.py` reports missing calibration without generating a panorama.

## Verification tolerances

The current conservative, provisional gates are 25 inliers per ring edge, 45% inlier ratio, confidence >=0.7, match spread >=12% of image width and >=25% height, rotation singular-value deviation <=0.08, independent accumulated turn within 4 degrees of one revolution, loop rotation drift <=3 degrees, per-step magnitude at least 3 degrees and at most 75% of calibrated horizontal FOV. Refined 95th-percentile residual must be <=max(2.5 pixels, 0.6% of image width). Exact and near duplicates are rejected before matching.

Projected overlap must have median absolute RGB disagreement <=22 and 90th percentile <=65 after exposure correction. At least 20 degrees of fully covered vertical content must remain. Boundary mean absolute difference must not exceed max(12, three times the 95th percentile of ordinary column-edge differences), including after JPEG encoding. These are rejection heuristics, not universal guarantees against local ghosts. They have synthetic test evidence only; validate against real rooms before tuning or production use.

## Output interface

`process(ordered_paths, new_jpeg_path, calibration=Calibration(...))` returns the same dictionary written to the JSON sidecar. Expected errors are `PanoramaError` (including `IncompletePanoramaError`); I/O failures propagate as `OSError`. The CLI maps expected processing/I/O failures to exit code 1.

The standalone viewer checks the JSON, SHA-256, dimensions, `closure_verified`, and `coverage_validation_status` before enabling wrap. Map `projection=partial_equirectangular`, `horizontal_coverage_deg=360`, `vertical_coverage_deg`, and `vertical_offset_deg` to the corresponding viewer projection controls. Angle bounds come from actual valid rows at the calibrated angular sample scale. The vertical offset is the center elevation above the calibrated horizon. Resolution changes during compression do not change those angular bounds.

No universal full-sphere 2:1 dimensions, compass-derived coverage, synthetic fill, image stretching, or database fields are implied. The optional property-media integration remains a future standalone handoff.

Reference: [OpenCV camera calibration tutorial](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html).

## Fresh Phase 4B camera evidence

The new 41-photo set reports 4.94 mm focal length and 28 mm equivalent in EXIF, with 1888x4096 image dimensions. Active crop/intrinsics, distortion and measured first-frame elevation are still missing. Those nominal EXIF values were not converted into invented calibrated viewing angles. See [PHASE4B_RESULTS.md](PHASE4B_RESULTS.md) for the exact evidence and required next measurements.
