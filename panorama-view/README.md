# RentLease - full 360 degrees horizontal panorama prototype

Phases 1-2 implement offline Python/OpenCV stitching with synthetic cyclic validation. Phase 3 adds a standalone Pannellum viewer with desktop browser and emulated-touch tests. **Real rooms and physical Android are not yet validated.** Only a full horizontal revolution is accepted. No sphere completion, generated property content, or production integration.

The prototype is now at the intended `RentLease-Features/panorama-view/` location. All 3,613 original files were hash-verified during relocation. The feature branch is `feature/panoramic-room-view`. See [PHASE_RESULTS.md](PHASE_RESULTS.md) for stitching results, [PHASE3_RESULTS.md](PHASE3_RESULTS.md) for relocation/viewer results, and [CALIBRATION.md](CALIBRATION.md) before processing photographs.

## Open the standalone viewer

The latest isolated experiment evaluates [Notchip's native Expo guided sweep](notchip-lab/README.md), with [source/compatibility findings](notchip-lab/RESULTS.md) and [Android device instructions](notchip-lab/DEVICE_TEST.md). This does not replace the existing calibrated processor or viewer, and no module-produced real-room 360 success is established.

The previous capture experiment is [continuous horizontal video](VIDEO_WORKFLOW.md): tap Start, sweep, tap Finish, then automatic keyframe selection. See [measured results](CONTINUOUS_SWEEP_RESULTS.md) and the [sensor/interface plan](CONTINUOUS_CAPTURE_PLAN.md). The fresh video has not produced an accepted real-room panorama; the image-based pipeline and previous independent tests are preserved.

Phase 4B evaluated 41 fresh user-supplied photographs from `samples/fresh-room/input/`. Timestamp order is verified and closing-image matches are strong, but weak/featureless connections and missing measured calibration prevent an accepted panorama. See [PHASE4B_RESULTS.md](PHASE4B_RESULTS.md) for results and retake guidance. Earlier withdrawn screening remains excluded; [PHASE4_RESULTS.md](PHASE4_RESULTS.md) records that correction.

From `RentLease-Features`, run `node .\panorama-view\viewer\serve.mjs`, then open <http://127.0.0.1:4173/>. Choose **Reference sphere** first, then **Phase 2 synthetic**, or choose a validated JPEG and its matching JSON. The viewer uses local assets; photographs stay in the browser. No build or npm install is needed to view. See [viewer/README.md](viewer/README.md) for tests and manual validation steps.

## Setup and tests (PowerShell)

From `RentLease-Features`:

```powershell
cd .\panorama-view
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests/run_synthetic.py
```

The last command creates an ignored, uniquely named directory under `output/`, containing synthetic perspective frames, a known-good synthetic sphere, calibration, and the processed JPEG/JSON. These are test fixtures, not property imagery. It never replaces previous outputs.

## Process an ordered room capture

Use one fixed lens, resolution, zoom, focus and aspect ratio. Hold the phone upright, rotate in one direction about the camera with consistent height and minimal translation, and target 40-60% neighbor overlap. Include distinct final views overlapping the starting area, but omit an identical repeat of the starting photo. This implementation accepts exactly one ordered turn, not an overshoot or a second revolution. The count depends on the calibrated portrait horizontal FOV; 18 distinct headings at 20 degrees intervals is only the synthetic example.

Put only one capture's photos in `samples/room01/` and create its measured calibration using [CALIBRATION.md](CALIBRATION.md). No real calibration values are supplied with this project.

```powershell
.\.venv\Scripts\python.exe stitch.py --input-dir .\samples\room01 --calibration .\samples\room01\calibration.json --output .\output\room01.jpg
```

Alternatively, `--images` takes explicitly ordered paths. Directory names sort numerically. Unsupported files fail instead of silently dropping photographs. JPEG, PNG and WebP are decoded and EXIF-oriented; convert HEIC explicitly before use, preserving geometry. Transparent source content is rejected by the verified pipeline.

Success writes `room01.jpg` and `room01.json`. Failure returns exit code 1 with an actionable error and no newly completed output. Existing photos and exports are never overwritten. A sidecar is the completion marker: consumers must parse it and verify its JPEG SHA-256 before use. A crash can leave an incomplete file; use a new output name after inspecting that file.

## What is checked

- SIFT features and RANSAC matches for every ordered neighboring pair, including final-to-first; minimum inliers, ratio, confidence and spatial spread.
- Calibrated rotation geometry, consistent direction, distinct headings, an independent near-360 degrees accumulated turn and low loop drift before refinement.
- Global OpenCV bundle adjustment with fixed supplied intrinsics and all ring constraints; residual checks on every edge after refinement.
- Exact periodic equirectangular longitude sampling, projected overlap disagreement, and real source-mask coverage across every retained pixel.
- Exposure compensation, OpenCV dynamic-programming seams and multiband blending over periodic padding; boundary checks before and after JPEG encoding.

No horizontal crop is performed. Only a contiguous band of complete rows is retained. Black photographed surfaces count as valid content; pixel color is never a coverage mask. A successful high-level OpenCV stitch is retained only as `baseline_stitch_images()` for comparison, not as a verified export path.

## Limits and metadata

6-72 distinct frames; at most 30 million source pixels and 40 MiB per file; 1200-pixel processing long edge by default; 36 million aggregate decoded processing pixels; 24 million aggregate warped pixels. These limit major arrays, not measured peak RSS. Feature and seam temporaries still require desktop RAM. Reduce `--max-long-edge` for ingestion limits or `--output-width` for warp limits. Width is 512-4096, default 2048. More photos can require a smaller output width. These limits have not been validated on Android.

JPEG is strictly below 9,500,000 bytes. `--max-bytes` may lower the cap but cannot raise it. Compression may reduce both dimensions while preserving angular bounds. There is no assumed 2:1 aspect ratio.

The JSON reports dimensions, bytes, processing seconds, input count, SHA-256, projection, horizontal and vertical angles, vertical offset, calibration source, pair matches, residuals, coverage, overlap and seam diagnostics. `coverage_validation_status` is `verified_calibrated_rotation_model`, not a statement of real-room visual approval. No failed run emits a 360 degrees label.

## Boundaries

The supported camera model is a rectilinear camera with square pixels and a centered principal point, with a calibrated first-frame pitch and level roll. Lens distortion must already be negligible/corrected. Unknown intrinsics are rejected; there is no guessed FOV fallback. Significant parallax, rolling shutter, inconsistent crops, motion, mirrors, blank walls and repeated textures can cause failure. Images alone cannot universally distinguish a truly repetitive scene from an incorrect physical trajectory; human review and capture provenance remain necessary.

The Python code does not run in Expo Go. The viewer is standalone; no Expo capture app, upload API, database, Storage policy or production application is changed. See [DEVELOPMENT_PLAN_360.md](DEVELOPMENT_PLAN_360.md) for the remaining gates.
