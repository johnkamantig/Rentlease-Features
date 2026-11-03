# Fresh real-room capture and validation

The current primary capture experiment is continuous video; see [VIDEO_WORKFLOW.md](VIDEO_WORKFLOW.md). This ordered-photo workflow remains available for independent comparisons and for processing the automatically selected images. It is not an instruction to build the manual-shutter Expo interface.

Phase 4 is pending. Use only photographs newly captured specifically for this independent project. Previous real-photo screening is superseded and excluded from acceptance evidence. See [PHASE4_RESULTS.md](PHASE4_RESULTS.md) and [AGENTS.md](AGENTS.md).

The dedicated staging directory is `panorama-view/samples/fresh-room/input/`. It now holds the 41 fresh photographs evaluated in [Phase 4B](PHASE4B_RESULTS.md). Keep those originals unchanged and retain the phone copies. Put any new capture in a separately identified input folder and record its provenance; do not mix sequences.

## Capture one horizontal turn

1. Record phone model, camera app/version, selected rear lens, photo resolution/aspect ratio, focus and zoom. Keep the same settings for calibration and room photos. Avoid automatic lens switching where possible. Use individual still photos.
2. Hold the phone vertically at a consistent height, with a level first frame. Stand at one viewpoint with space from nearby furniture. Turn around the camera lens rather than walking around the room.
3. Use steady diffuse lighting and stabilize exposure/focus where possible. Avoid motion and blur. Record which fresh retake replaces a bad attempt and retain attempts separately.
4. Rotate in one direction through one complete horizontal revolution. Aim for approximately 40-60% neighboring overlap containing recognizable stationary detail. Similar folds or blank surfaces alone may remain unmatchable.
5. Derive approximate spacing from measured portrait horizontal FOV: `step ~= hfov * (1 - overlap_fraction)`. Do not assume the synthetic example's FOV applies to a phone. Photo count and sensor progress do not prove coverage.
6. Finish at a distinct heading whose image overlaps the starting scene by roughly 40-60%. Confirm the starting landmarks reappear. Do not append an identical starting photo or a second turn.
7. Record actual capture order. Transfer originals by USB without resizing or social-app recompression; retain EXIF where available. JPEG/PNG/WebP are supported. Record any necessary format conversion and retain its originals.

This is one horizontal sequence with limited captured vertical content. No ceiling/floor or upper/lower capture rows are needed. No generated property content is permitted.

## Obtain fresh calibration

Record the actual lens, image crop/resolution, zoom, focus and app settings. Only measurements for the fresh settings in this project are eligible. Focal length without active sensor/crop geometry, JPEG dimensions, phone model, nominal zoom and compass headings cannot independently establish FOV.

The current model requires rectilinear images, square pixels, a centered principal point and negligible residual distortion. Retain measured intrinsics, distortion coefficients, oriented dimensions, uncertainty/residual report and any tested rectification mapping.

If calibration is unavailable, take approximately 15-20 sharp photos of a flat checkerboard with known square size, using the exact intended camera settings. Vary board placement/tilt to cover the center and edges, record inner corner counts, and retain held-out views. Use OpenCV corner detection/refinement and `calibrateCamera`; evaluate reprojection error and straight lines on held-out images. Calibration photos are separate from the room sequence. See [OpenCV's calibration tutorial](https://docs.opencv.org/4.13.0/dc/dbb/tutorial_py_calibration.html).

If measurements violate the current camera model, a tested rectification step is required. General arbitrary-phone rectification is not yet provided. Supply fresh calibration photos/report first rather than guessed values.

After suitable rectification and orientation correction, `horizontal_fov_deg = degrees(2 * atan(width / (2 * fx)))`. Measure first-frame optical-axis elevation for `reference_pitch_deg`; zero is valid only when the frame was level. Review calibration after any lens/zoom/crop change. See [CALIBRATION.md](CALIBRATION.md).

The supplied `samples/fresh-room/calibration.example.json` contains invalid nulls intentionally. Create a separate `calibration.json` with actual measured values. No valid smartphone calibration has been supplied.

## Import in actual order

From `RentLease-Features/panorama-view/`, copy `samples/fresh-room/order.example.json` to a new `order.json`. Populate `images` in actual order with paths such as `input/IMG_1234.jpg`, relative to that order file. Record date, device/app/lens/settings and retakes in `capture_notes`.

Real orders require `data_kind: real_room` and `capture_origin: fresh_panorama_view`. This is an explicit provenance declaration, not automated authentication of the scene. All source/order/calibration files must be staged inside this project; linked and out-of-project input paths are refused before file reads.

```powershell
.\.venv\Scripts\python.exe room_validation.py import --order samples/fresh-room/order.json --output samples/fresh-room/imported-01
```

The importer preserves supplied order, validates images, copies unchanged bytes, verifies hashes, and creates a numbered contact sheet plus `capture.json`. It does not sort by timestamps or silently remove frames. If recording a rejected fresh retake in `excluded_images`, supply its path and reason. Never omit a necessary horizontal sector to force a pass.

Destinations must be new. Originals are not overwritten. An incomplete import without its final capture manifest is unusable; inspect it and use a new destination for retry.

## Audit and stitch

```powershell
.\.venv\Scripts\python.exe room_validation.py audit --capture samples/fresh-room/imported-01/capture.json --output output/fresh-room-audit-01 --match-previews
$LASTEXITCODE
.\.venv\Scripts\python.exe room_validation.py stitch --capture samples/fresh-room/imported-01/capture.json --calibration samples/fresh-room/calibration.json --output output/fresh-room-stitch-01 --width 2048 --max-long-edge 1200
```

The audit rechecks hashes/order and preliminary neighboring/closing feature counts and ratios. Optional `--match-previews` writes numbered, annotated matching diagrams; insufficient descriptor counts become weak-pair diagnostics rather than a KNN crash. Exit 2 means weak matching; 1 means input/processing error; 0 means the limited screen passed. It does not establish angular geometry, spatial spread, closure alignment or stitched quality.

The stitch command calls the existing calibrated processor with all closure/resource safeguards. `validation.json` records automated success/failure, wall time and OS peak resident memory. Missing calibration produces failure, never guessed angles. Success exports `panorama.jpg` and `panorama.json`, and still requires visual review. Use a fresh process and new output directory per resource comparison.

## Review and acceptance

Run `node viewer/serve.mjs`, open <http://127.0.0.1:4173/>, and select a successful fresh JPEG/JSON. Compare every original with the output. Record pass/fail/unassessed with reviewer/date for:

- Complete room without missing/duplicated sectors.
- Seam crossing in both directions at several zoom levels.
- Walls, corners, doors, windows and furniture without unacceptable distortion, parallax or ghosts.
- Exposure consistency and useful photographed detail at normal viewing size.
- Vertical viewing limited to calibrated captured rows without empty regions.
- Drag/zoom/resizing, then user-confirmed physical Android pinch/fullscreen/orientation behavior.
- JPEG dimensions/bytes, processing time, OS peak RSS and failure/retry behavior.

Phase 4 remains pending until fresh photographs and calibration are supplied and actually pass these checks. Phase 5 Expo development has not started.
