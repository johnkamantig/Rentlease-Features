# Continuous horizontal video experiment

`video_ingestion.py` adds independent local video ingestion and bounded keyframe selection. The existing OpenCV stitcher, coverage/closure gates and Pannellum viewer are retained. See [results](CONTINUOUS_SWEEP_RESULTS.md) and the [sensor/interface plan](CONTINUOUS_CAPTURE_PLAN.md).

## Record a new video

- Use a normal smartphone camera in portrait orientation with a fixed rear lens/zoom and consistent capture settings. Begin at an identifiable scene with unique details, such as a doorframe or desk.
- Tap record, hold a steady camera height and rotate slowly in one horizontal direction around the lens. Keep translation small. Finish when the starting area returns with closing overlap; avoid continuing into an extra revolution.
- Aim for roughly 30-60 seconds as initial recording guidance, not a measurement of coverage. Use good steady light and avoid moving people. 1080p at 30 or 60 fps is sufficient to test; more fps does not fix absent texture or guarantee sharpness.
- Choose a viewpoint that keeps distinctive details visible through wall/curtain transitions. A uniform wall cannot become geometrically observable merely by recording more identical-looking frames. No ceiling/floor directions are required.
- Keep the original video. Transfer it without transcoding into a clearly identified new file/folder inside `panorama-view/samples/`. Record device, lens, zoom, resolution, orientation and stabilization settings. Video calibration must match this mode/crop, not an unrelated photo mode.

An ordinary MP4 is accepted without a sensor sidecar for visual diagnostics. The program does not manufacture sensor data or camera calibration. Fresh real videos require the `--fresh` declaration.

## Run

From `RentLease-Features/panorama-view/`, using a new output name:

```powershell
.\.venv\Scripts\python.exe video_ingestion.py --video samples/fresh-room/input/VID_20261030_184519.mp4 --output output/my-video-run --fresh --evaluate
```

To supply measured calibration for that video's exact camera model:

```powershell
.\.venv\Scripts\python.exe video_ingestion.py --video samples/my-new-video.mp4 --output output/my-calibrated-video-run --fresh --evaluate --calibration samples/my-video-calibration.json
```

Optional `--diagnostic-baseline` runs the slower high-level OpenCV comparison after rejection. It never exports unverified angular metadata or promotes a partial baseline image. The supplied real video comparison took over a minute and failed camera adjustment, so this repeated comparison is opt-in.

Exit 0 with `--evaluate` means the existing calibrated export passed; 2 means incomplete/unverified; 1 means extraction/input failure. Without `--evaluate`, exit 0 only means keyframe extraction completed. Always inspect status/coverage fields, not the existence of a contact sheet.

## Selection and limits

- Decode sequentially with bounded image state; inspect up to four candidate images per second by default. Video timestamps come from OpenCV presentation milliseconds. Invalid/non-monotonic timing is rejected, not replaced with invented sensor timestamps.
- Check Laplacian variance, exposure and SIFT feature availability. The blur score is a provisional heuristic: a smooth wall can also have low variance, while noise can inflate it.
- Match each eligible candidate to the last selected anchor using nearest-neighbor descriptors and homography RANSAC, requiring inliers, ratio and spatial spread. Projected footprint overlap is a selection proxy, not a calibrated angular overlap measurement.
- Select new views when estimated visual overlap is approximately 40-68%. Reject stationary/redundant views, including confirmed near-duplicates of the initial view after substantial selection. This redundancy test does not prove a completed revolution.
- Keep timestamps/frame indices for selected and rejected candidates. If quality or visual tracking is lost for more than the configured interval, record a gap and start a disconnected segment. Never hide that gap by simply selecting the next textured view.
- The LK forward/backward flow probe is diagnostic only; it supplies no camera orientation or bridge through a missing interval.

Defaults/caps: 48 selected frames (configurable up to the existing 72-input limit), processing long edge 960, analysis long edge 640, 180 seconds, 12,000 decoded frames, 1,500 inspected candidates, 12 million source pixels/frame and 1.5 billion source bytes. The existing 36-million aggregate processing-pixel and 24-million warped-pixel guards remain active. Keyframe/pixel limits fail explicitly rather than silently truncating the sweep. These are desktop safeguards, not proven Android resource limits.

The selection thresholds and one-second gap rule are conservative prototype values, not a certified universal capture-quality model. No optimization of them is allowed to bypass geometric coverage or source-mask validation.

## Outputs and acceptance

Each new run writes `selection.json`, a numbered contact sheet and at most the configured count of selected JPEG keyframes. The source hash is checked again after extraction. If at least six frames are selected, `order.json` can be imported by the existing room workflow.

With `--evaluate`, the existing ring audit creates `audit/audit.json` and matching previews. Any temporal gap or weak selected-frame ring edge prevents calibrated export. Otherwise the existing calibrated processor runs and still checks single-revolution motion, final/first alignment, full row coverage, seams, compression and metadata. Missing video-mode calibration fails clearly.

Only a passing run has `stitch/panorama.jpg` plus matching `panorama.json`. Load those files through the existing viewer's local file controls. A failed real run has no accepted panorama to view. Never fill in `haov`, `vaov` or `vOffset` to make a failed run load.

## Independent synthetic proof

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests/run_video_synthetic.py
```

The second command creates a mathematical cyclic video with 120 frames, exact renderer calibration, selected keyframes and an accepted synthetic panorama. It is not property imagery. Its output tests the interface and geometry path independently of real-room acceptance. The current real video and test results are documented separately in [CONTINUOUS_SWEEP_RESULTS.md](CONTINUOUS_SWEEP_RESULTS.md).
