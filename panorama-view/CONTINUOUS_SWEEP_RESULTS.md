# Continuous 360 horizontal sweep experiment - 2026-10-30

**Phase A is implemented and evaluated. The supplied fresh real video did not produce an accepted panorama.** Automatic selection reduced thousands of video frames to a bounded set, but texture/quality gaps and failed selected-frame closure remain. A separate cyclic synthetic video passes the existing calibrated stitcher and Pannellum interface. Sensor-assisted stitching and the Expo camera UI are not implemented.

## Fresh video and inspected/selected frames

Source, provided inside the active independent project:

```text
C:\Users\kaman\Rentlease-Features\panorama-view\samples\fresh-room\input\VID_20261030_184519.mp4
```

| Measurement | Actual result |
| --- | --- |
| Source size | 127,819,621 bytes |
| Decoder | OpenCV FFmpeg backend |
| Video metadata | Approximately 59.993 fps; 2,458 declared/decoded frames |
| Oriented decoded size | 1080 x 1920 |
| Rotation handling | Container rotation metadata 90 degrees; OpenCV auto-orientation enabled; no second rotation applied |
| Presentation timeline | 0 to 40.954 seconds; approximately 40.97-second nominal duration |
| Candidate frames inspected | **163**, approximately four per second including the final frame |
| Keyframes selected | **30**, each 540 x 960 JPEG; not hundreds of frames passed to stitching |
| Original preservation | SHA-256 unchanged across all three extraction runs |

The source hash is `7751736db51a72861b4cb4b7054ae8a2eeece9d343848d39865a1e7f811bf5dd`. The original video was never modified or transcoded. Audio and any vendor-private sensor streams are not processed.

Frames are decoded in presentation order. Every candidate's source index/time, quality score and selection/rejection reason is retained. No gyro clock, camera angle or sensor measurement is manufactured from the video. Presentation timestamps are not exposure or synchronized IMU timestamps.

The final selector records 60 redundant/stationary candidates, 40 low-Laplacian-variance candidates (labelled `blurred` by this provisional heuristic), four insufficient-texture candidates, 29 unverified-connection candidates and 30 selected frames. A smooth surface can also have low variance; those 40 cases are not all proven motion blur. Selection includes explicitly disconnected segment starts rather than pretending all 30 images form a valid chain.

The selected images span 0.75 to 40.121 seconds. Leading/trailing candidate handling, including rejection of the last frame if unusable/redundant, is visible in `candidate_events`. No temporal order was rearranged.

## Continuity and stitching result

The selector recorded **11 unverified intervals**. Important low-quality/texture intervals include approximately **13.97-14.98 s, 19.58-23.38 s and 30.23-34.03 s**. Other intervals lost sufficient anchor matching. Recorded gaps remain acceptance failures, even if later frames become textured again.

The existing selected-frame ring audit found **15 weak pairs out of 30**, including **zero closing-pair inliers** between selected frames 30 and 1. This is not successful 360-degree closure. The selection's looser nearest-neighbor/projective-overlap screen does not override the stricter existing audit or calibrated pose checks.

The high-level OpenCV baseline was attempted on the selected images in the earlier two trials. Both failed with **status 3: camera parameter adjustment failed**; no image was exported or given 360-degree metadata. Final comparison time was **67.626 seconds**; the earlier run took 63.797 seconds. The calibrated processor was not invoked after known continuity failures. No video-mode calibration was supplied in any case.

The overview and selected contact sheet were visually inspected. The video includes long views of curtains and plain walls and later revisits the starting area before continuing. This suggests an endpoint/extra-rotation issue to review, but no calibrated angular trajectory was measured. Starting and finishing at visually related scenes alone would not prove a complete revolution.

**Real panorama quality, resolution, JPEG size, seam appearance and calibrated vertical range are unavailable:** no accepted real panorama exists. The existing 9,500,000-byte export limit, full-circle turn/closure checks, source-mask coverage and warp validation remain unchanged. Pannellum was not used to display the failed real selection as a panorama.

### Does video improve reliability over the manual photos?

This run demonstrates automatic ingestion, denser temporal observations and fewer retained images without manual shutter presses. It does **not** demonstrate a successful reliability improvement. The earlier independent manual sequence had 12 weak connections among 41 photos; this video's selected ring has 15 among 30. Those are different captures with unmatched scene/viewpoint/settings, so the rates are not a controlled comparison and should not be interpreted as proof that one capture method is superior.

Denser frames did not by themselves solve the current low-texture transitions. A controlled repeat should use the same room, viewpoint, fixed video calibration/settings and a deliberately single-turn trajectory. The selector is a conservative proof of concept, not a tuned universal capture-quality model.

## Optical flow and sensor findings

Implemented: diagnostic corner-based Lucas-Kanade tracking between inspected frames, with forward/backward consistency checks. In the final run 161 of 162 probe pairs retained at least one consistent track; one had none. Counts varied considerably, including low-count periods through curtains and plain surfaces. Such tracks may be texture/noise/edge observations and are **not** verified rotation, angular progress or gap-free geometry. The probe does not feed camera alignment or repair the rejected intervals.

The independent uniform-wall test returns zero tracks. Optical flow can help preserve short-range associations while some visual structure exists, but provides no missing observation when all usable gradients disappear. A future calibrated geometric flow integration would need tests for spatial spread, rigid motion, aperture ambiguity, translation and drift.

No synchronized gyro sidecar was supplied or parsed. We cannot conclude from this video that gyro fusion succeeds or is universally necessary. It is a practical next experiment for progress/level warnings and as a measured prior across short weak-texture intervals, with native clock alignment, camera-to-IMU calibration and image anchors. It cannot invent wall detail or remove parallax.

The evidence, primary technical references, proposed timing/calibration contract and explicitly unimplemented alignment design are in [CONTINUOUS_CAPTURE_PLAN.md](CONTINUOUS_CAPTURE_PLAN.md).

## Independent synthetic video and Pannellum proof

The test renderer created **120 frames** from genuine cyclic scene geometry, with camera headings at three-degree increments and exact synthetic intrinsics. This is mathematical test imagery, not property imagery. Automatic selection retained **20 keyframes**. A near-start duplicate at the end initially caused the existing single-turn motion gate to reject the test; the selector now rejects confirmed redundant returns to the first view, without claiming that matching the first view proves a revolution.

The selected frames passed the existing ordered-ring audit, calibrated circular alignment, single-turn validation, periodic warping/blending, source coverage and JPEG seam checks. Actual exported result:

| Synthetic-only output | Result |
| --- | --- |
| JPEG | **1024 x 196**, **127,050 bytes** |
| Stitch processing time | **7.900 seconds**, excluding extraction/audit |
| Horizontal coverage | 360 degrees under exact synthetic calibration |
| Captured vertical strip | 68.90625 degrees |
| Vertical center offset | 0 degrees |
| Viewer smoke test | Matching SHA/metadata loaded successfully; automated mouse dragging traversed approximately 619 degrees |

The accepted synthetic output was loaded through the existing Pannellum file controls. Angle settings matched the output metadata exactly, and a screenshot was saved and opened for visual inspection. This is browser automation/visual review on a desktop software renderer; no physical Android or real-room success follows from it.

Artifact directory:

```text
C:\Users\kaman\Rentlease-Features\panorama-view\output\continuous-sweep\synthetic-1793358821725810600\
```

Its `run/stitch/panorama.jpg` and `panorama.json` can be selected in the existing local viewer. `viewer-validation.json` and `viewer-synthetic-video.png` preserve the extra integration check. No synthetic calibration values were applied to the real video.

## Time and resources

The final real run selected keyframes in **42.833 seconds**, with **257.18 MiB** process peak resident memory. The existing ring audit took **3.999 seconds**, with a process high-water mark of **324.14 MiB**. These stages ran in the same CLI process; peak values are not additive. Import/contact-sheet/report overhead is additional. Optional high-level baseline work can add over a minute and is opt-in after rejection.

These are observed desktop timings, with some automated checks running concurrently; they are not controlled throughput benchmarks or real-time mobile claims.

State during ingestion is bounded: first/anchor/previous diagnostic images, one decoded frame and bounded metadata, not all decoded images. At most the configured keyframe count is written. Duration, byte, source-frame, inspected-candidate and aggregate processing/warp limits are enforced. The existing OpenCV processing pixel limits are not hard OS-RSS guarantees. No Android runtime, memory, thermal or on-device-processing measurement was made.

## Tests and files

- Final Python suite: **82 passed, zero failed in 85.24 seconds**; all 67 existing tests retained, plus 15 video tests.
- Existing viewer unit/metadata suite: **27 passed**.
- Existing browser suite: **8 passed in 17.5 seconds**, zero failures/skips/flakes, on owned loopback port 4174.
- Additional accepted synthetic-video viewer check passed and was visually inspected.
- Video tests cover cyclic geometry and calibrated export, partial arcs, blur/texture loss, duplicate/static views, chronological timing, temporal-gap rejection, corrupt video, missing timestamps, resource limits, source preservation and overwrite protection. Synthetic partial arcs never receive a full-circle export.
- Early cyclic-video tests exposed redundant closing-frame selection. Two earlier test runs failed that motion gate while the high-level comparison was unnecessarily repeated. The redundancy rejection was fixed, and redundant baseline work is now skipped for already accepted calibrated output. All final checks pass; no acceptance threshold was relaxed.

New files: `video_ingestion.py`, `tests/test_video_ingestion.py`, `tests/run_video_synthetic.py`, `VIDEO_WORKFLOW.md`, `CONTINUOUS_CAPTURE_PLAN.md`, and this report. Updated `AGENTS.md`, `README.md`, `CODEX_STAGE1_HANDOFF.md` and `DEVELOPMENT_PLAN_360.md` to point to the continuous-capture experiment. No core stitcher, closure, projection, compression or viewer implementation was changed in this experiment. No new dependency was required.

## Commands and exact outputs

Run from `panorama-view/`, always choosing a new output directory:

```powershell
.\.venv\Scripts\python.exe video_ingestion.py --video samples/fresh-room/input/VID_20261030_184519.mp4 --output output/continuous-sweep/run-03 --fresh --evaluate
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests/run_video_synthetic.py
.\.venv\Scripts\python.exe video_ingestion.py --help
.\.venv\Scripts\python.exe -m compileall -q video_ingestion.py tests/test_video_ingestion.py tests/run_video_synthetic.py
```

Earlier runs `run-01` and `run-02-flow` performed the slower diagnostic high-level comparison. The current CLI requests that explicitly with `--diagnostic-baseline`. Extraction-only success is not panorama acceptance; `--evaluate` exits 2 when incomplete.

Current real result directory:

```text
C:\Users\kaman\Rentlease-Features\panorama-view\output\continuous-sweep\run-03\
```

It contains `selection.json`, 30 JPEGs under `keyframes/`, `contact-sheet.jpg`, `order.json`, byte-verified imported copies/manifest under `capture/`, ring reports/matching previews under `audit/`, and `evaluation.json` with `coverage_verified: false`. Other evidence:

- `output/continuous-sweep/experiment-summary.json` - compact real-video status.
- `output/continuous-sweep/video-overview.jpg` - timestamp-labelled source overview.
- `output/continuous-sweep/run-02-flow/evaluation.json` - failed high-level baseline and its time.
- `output/continuous-sweep/viewer-regressions.json` - existing browser-suite evidence.

Viewer regression commands were `npm.cmd test` and, with `$env:PORT = '4174'`, `npm.cmd run test:browser`, from `viewer/`. The additional synthetic integration check used an owned local server and installed headless Chrome; both were stopped afterward. Original video hashes matched after processing.

## Recommendation for Android

Prefer the **tap Start / sweep / tap Finish interaction** with automatic quality feedback and bounded image selection. It removes manual shutter timing and is the best current UX direction. The present results do not justify declaring the final stitching architecture reliable or choosing video over automatically acquired stills on image quality grounds.

Next, obtain calibration for the exact video mode and a fresh, steady, single-turn capture starting at a textured landmark, with unique details visible through weak sectors. For sensor assistance, record real synchronized native camera/IMU observations and test the proposed priors/flow integration on matched captures. Do not assume that ordinary recording supplies that synchronization. The interface plan is ready for review, but Expo implementation remains deferred until this real-data acceptance gap is resolved.
