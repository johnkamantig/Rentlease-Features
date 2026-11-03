# Local spherical stitching experiment

**Current workflow: horizontal capture.** The spherical experiments below are retained historical work, not the active capture plan. No new complex spherical stitching is being implemented in this refactor.

## Horizontal capture preparation

New exports contain one horizontal sweep, with `session.captureMode: "horizontal"` and `session.sweepDegrees` of 120, 150 or 180. These additive version-1 fields preserve legacy readability. Original JPEG bytes, overlap order, dimensions, timestamps and approximate sensor readings remain intact. Capture completion does not mean a panorama was generated or coverage validated.

Use the existing dedicated environment and requirements.txt; no new dependency is needed. From `360-view/stitching-lab`:

```powershell
& .\.venv\Scripts\python.exe prepare_horizontal.py .\data\horizontal-room.zip --output .\runs\horizontal-room-prepared
Get-Content .\runs\horizontal-room-prepared\prepared.json
& .\.venv\Scripts\python.exe -m unittest -q
& .\.venv\Scripts\python.exe -m compileall -q inputs.py prepare_horizontal.py test_horizontal.py
& .\.venv\Scripts\python.exe -m pip check
```

Choose a NEW output directory outside the source folder. Exit 0 means `prepared_unstitched`; exit 2 means failure. The tool validates selected images, copies original bytes without recompression and writes ordered `prepared.json` with source indices and SHA256 hashes, plus the original manifest. It never renders a panorama. Orientations remain approximate; no originals are modified or deleted.

For a legacy multi-row ZIP explicitly select an ordered horizontal subset:

```powershell
& .\.venv\Scripts\python.exe prepare_horizontal.py .\data\old-room.zip --photos 1,2,3,4,5,6,7,8 --output .\runs\old-room-horizontal-prepared
```

Selected targets must be horizontal and span at most 180 planned degrees. Exclusions are reported; no stages are silently discarded. No actual coverage is inferred. This eight-photo preparation passed against the existing 56-photo POCO F7 ZIP, copying the selected originals unchanged. A four-image fixture exported by the actual TypeScript ZIP writer also passed Python preparation. These are preparation/interoperability results, not stitching success.

A future ordinary OpenCV pipeline can consume `prepared.json.photos` in order, match adjacent images, reject weak/disconnected matches and report projection/valid image bounds. Preserve proportions and visible gaps; do not generate room details or force a 2:1 canvas. Use the [flat viewer](../README.md) for planar/cylindrical/cropped output unless verified equirectangular projection and measured angular extents justify Pannellum's partial configuration. No automatic horizontal stitch is claimed by this preparation step.

Latest Python suite: **59 tests passed** (47 retained, eight horizontal preparation tests, four overlap-checker tests). The refactor itself previously passed 55. Historical results below apply to earlier spherical experiments.

## Check overlap yourself

`check_horizontal.py` repeats the input validation and adjacent-photo matching used for the first real horizontal ZIP. It uses installed OpenCV/Pillow, works offline, and never modifies source photos. A new output folder receives byte-identical copies, inspection pictures and reports. Nothing is stitched or uploaded.

From PowerShell on this PC:

```powershell
Set-Location C:\Users\kaman\Rentlease-Features\360-view\stitching-lab
& .\.venv\Scripts\python.exe check_horizontal.py .\data\capture-mvs8d7bp-axxmf8vj6p-r14-1793199290385.zip --output .\runs\my-horizontal-check
Write-Host "Check exit code: $LASTEXITCODE"
Get-Content .\runs\my-horizontal-check\CHECK_RESULTS.txt
Start-Process .\runs\my-horizontal-check\contact-sheet.jpg
Start-Process .\runs\my-horizontal-check\matches-1-2.jpg
```

Replace the ZIP filename for a future capture. Choose a NEW output folder each time; existing results are not overwritten. On another PC, first follow the Python virtual-environment installation below.

- `contact-sheet.jpg`: all photos in capture/overlap order. Check that neighboring images contain the same recognizable objects.
- `matches-A-B.jpg`: the algorithm's selected matching points, joined by lines. The two endpoints must refer to the **same physical detail**. A TV corner joined to a door corner is a false match. Repeated curtain rings or tiles can fool matching even when many lines are shown. No lines means no fitted set of matches was found; it does not prove zero physical overlap.
- `CHECK_RESULTS.txt`: readable per-join evidence and instructions. `WEAK` means this automatic screen found insufficient reliable evidence. `STRONGER` still needs manual inspection and actual stitching validation.
- `overlap-diagnostics.json`: detailed counts, heuristics and parameters. Its visual-inspection flag remains false because the script cannot perform human inspection.

Exit **0** means all pairs passed the experimental screen but still need review; **3** means weak connections; **2** means input/processing failure (read prepared.json or overlap-diagnostics.json). No exit code certifies a panorama. The check does not measure actual overlap percentage. Four points can fit a homography exactly even when they refer to different objects.

Tested on the six-photo real ZIP: pairs 1–2, 2–3 and 4–5 remained weak; 3–4 and 5–6 had stronger evidence. Reproduction artifacts are under `runs/horizontal-room-01-repeat/`. Validation commands:

```powershell
& .\.venv\Scripts\python.exe -m unittest -q
& .\.venv\Scripts\python.exe -m compileall -q check_horizontal.py test_overlap.py
```

59/59 tests passed; compilation passed. Tests include featureless inputs, rejecting four-point false confidence, real synthetic feature matching/artifacts, source preservation, output overwrite protection and processing failure reporting. No camera/app code changed for this checker.

This isolated Python experiment consumes the capture app's ZIP export. It has no server, network upload, authentication, production integration or stitching code in the Android app. Sources are read without modification. Generated data, virtual environments and run artifacts are ignored by Git. Work remains on `feature/360-view-local`, inside `360-view/`; nothing is committed or pushed.

**Current finding:** OpenCV produced a visually inspected synthetic candidate, but neither real-room capture has produced an acceptable panorama. The new 20-degree set passed validation for all 56 original photographs. OpenCV still failed on low-feature images. Independent Hugin matching connected 46 photos but left ten isolated, including ceiling and floor; optimizing the connected group still produced large alignment errors. More photographs improved connectivity without establishing usable spherical stitching. See [EXPERIMENTS.md](EXPERIMENTS.md) for the actual runs. No real-room result is approved for Android or production integration.

## Windows PowerShell setup

Validated with 64-bit Python 3.13.7, OpenCV 4.13.0.92, NumPy 2.2.6 and Pillow 12.3.0. This is a separate environment from the viewer's `.venv`.

From the repository root, using the existing viewer Python:

```powershell
Set-Location .\360-view\stitching-lab
& ..\.venv\Scripts\python.exe -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --cache-dir .pip-cache -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m unittest -v
```

On a fresh PC without the viewer environment, install 64-bit Python 3.13, then use `py -3.13 -m venv .venv` for the environment creation command. If the launcher cannot locate Python, use its installed `python.exe` absolute path. Activation and changing PowerShell execution policy are unnecessary. Dependency installation needs internet; processing does not. Do not install both `opencv-python` and `opencv-python-headless` in this environment.

## Export a room from Android

Follow the [capture export instructions](../capture-lab/README.md#export-a-complete-capture-set-task-03). Finish all planned targets, then use **Save original capture ZIP to folder**. Choose a new subfolder such as `Documents/RentLeaseExports` if Android prevents selecting the Downloads root. Transfer the ZIP by USB File Transfer, Bluetooth or an offline native sharing destination. Keep the phone originals until the computer validation passes.

Put the ZIP at `360-view/stitching-lab/data/room-01.zip`. The app exports ordered `images/0001-photo-….jpg` files and `manifest.json` without resizing or recompressing JPEGs. CRC32 and byte counts detect accidental transfer damage, not malicious tampering. Original JPEGs and JSON can contain private information; only the final JPEG is metadata-stripped. No code uploads either.

```powershell
# Run from 360-view/stitching-lab. Each --output directory must be NEW.
& .\.venv\Scripts\python.exe stitch.py .\data\room-01.zip --validate-only --output .\runs\room-01-input-check
if ($LASTEXITCODE -ne 0) { throw 'Input validation failed. Read report.json before proceeding.' }
& .\.venv\Scripts\python.exe stitch.py .\data\room-01.zip --output .\runs\room-01 --width 2048
$stitchExit = $LASTEXITCODE
Get-Content .\runs\room-01\report.json
Write-Host "Stitch exit code: $stitchExit"
```

Exit `0` means inputs validated, or a candidate is ready for visual review. Exit `2` means a processing/input failure; exit `3` means incomplete or suspect geometry/appearance. **None means a verified full sphere.** Inspect `status`, `error`, coverage and warnings. A disconnected feature graph fails instead of dropping inconvenient photos. Choose a different output directory to retry; results are not overwritten.

Input accepts the ZIP directly or an extracted folder containing exactly the manifest and listed images. ZIP paths are not extracted by Python. Absolute paths, traversal, duplicate/encrypted/symlink entries, unlisted files, malformed manifests, changed bytes, wrong dimensions, oversized images, damaged JPEGs and unexpected EXIF rotation are rejected. Bounds: 300 exported/validated photos, 50 MiB per JPEG, 40 million decoded pixels, 2 GiB total. Stitching is deliberately limited to 60 photos to bound memory; larger sets need a separately assessed implementation, never silent subsampling. Validation decodes one image at a time. Stitching retains reduced working images and uses one full-resolution source at a time; allow several GB of desktop RAM and minutes for large sets. `Ctrl+C` stops processing without changing sources; use a new results folder on retry.

## Pipeline and limits

1. Decode every original strictly with Pillow; verify manifest ordering, dimensions, byte counts and CRCs. Reduce only internal matching copies to a 960-pixel maximum side.
2. Detect SIFT features; match all image pairs with OpenCV's homography matcher. Require a connected graph and sufficient inliers.
3. Estimate camera intrinsics/rotations and perform ray bundle adjustment. Reject implausible focal lengths and final feature reprojection errors above median 4 / p95 15 working-image pixels. These are experiment thresholds, not calibrated guarantees.
4. Optionally use fresh approximate heading/elevation readings for one global leveling rotation, only when sufficiently consistent. Relative camera alignment always comes from image features. Target guide angles never substitute for measured camera poses. Missing/stale/inconsistent sensor readings leave the result unlevelled with a warning.
5. Inverse-project each pinhole camera onto a longitude/latitude canvas covering 360 × 180 degrees. This is explicit spherical projection, not stretching a cropped stitch to 2:1. Masks include only valid source pixels; behind-camera pixels and image borders do not count.
6. Apply OpenCV gain compensation, graph-cut seams and feather blending with wrap padding. Multiband blending of zero-filled warps produced visible halos in an earlier attempt; the current feather method removed those bands in the inspected synthetic result. It can still ghost on misaligned real objects.
7. Measure pixel and solid-angle coverage, ten-degree pole bands, equator coverage, overlap disagreement, sharpness and the wrap edge. Write metadata-free JPEG pixels below **10 MiB (10,485,760 bytes)**, the existing viewer constraint. Quality/resolution may decrease to meet the cap; dimensions remain exactly 2:1. Default 2048 × 1024; maximum 4096 × 2048. Use at least width 1024 for the existing viewer.

The OpenCV components follow the rotation-model approach described in the [official detailed stitching example](https://github.com/opencv/opencv/blob/4.13.0/samples/python/stitching_detailed.py). This experiment adds manifest verification, conservative failure gates and full-canvas inverse projection. It does not solve camera translation, parallax, rolling shutter, lens distortion, moving people, reflections or exposure clipping. A blank ceiling may have enough planned photographs but no matchable features. Single ceiling/floor shots and fixed guide spacing are not coverage guarantees.

## Output and visual review

| Artifact | Meaning |
| --- | --- |
| `report.json` | Versions, ordered input paths, matches, camera estimates, alignment residuals, approximate sensor use, coverage, timings and warnings |
| `coverage.png` | White = geometrically supported output sample; black = missing |
| `overlap.png` | Brighter pixels have more supporting photographs |
| `seams.png` | Coarse graph-cut ownership colors; diagnostic only |
| `diagnostic.png` | RGBA equirectangular view; missing regions are transparent |
| `candidate.jpg` | All sampled directions supported and no large overlap disagreement; still requires review |
| `diagnostic-only.jpg` | Partial or suspect result; never represent it as a completed sphere |

Missing JPEG areas are black; they are not fabricated, mirrored, stretched or inpainted. A 2:1 canvas only establishes dimensions. Even a fully white coverage mask is conditional on estimated cameras and finite sampling, and cannot prove correct photographic alignment or complete scene capture. `full_sphere_verified` and `physical_android_verified` remain false in automated reports. Record manual judgments separately.

For an existing candidate:

```powershell
& .\.venv\Scripts\python.exe inspect_panorama.py .\runs\room-01\candidate.jpg .\runs\room-01\inspection.jpg
Start-Process .\runs\room-01\inspection.jpg
Start-Process .\runs\room-01\candidate.jpg
```

Inspect all six perspectives at full size, particularly doors, window frames, furniture, ceiling/floor corners and the first/last photo boundary. Reject duplicated objects, cut edges, visible holes, warped straight lines, severe blur, abrupt exposure bands or ghosts. Sharpness and overlap scores help find problems but are scene-dependent and cannot replace inspection.

## Hugin independent comparison

Hugin 2025.0.1 was obtained from the [official Hugin download page](https://hugin.sourceforge.io/download/) and run locally for the second room set. It is not installed on PATH here: extracted executables, dependencies, installer and licenses remain in ignored `.tools/hugin/`. See the experiment record for provenance. On another Windows PC, obtain the official build and set `$huginBin` to the directory containing its command-line executables and libraries.

```powershell
# From stitching-lab; this checkout already has the locally extracted tools.
$huginBin = (Resolve-Path .\.tools\hugin\bin).Path
& .\.venv\Scripts\python.exe hugin_reference.py .\data\room-01.zip --output .\runs\room-01-hugin-new --bin $huginBin --hfov 50
Get-Content .\runs\room-01-hugin-new\reference-report.json
```

The wrapper validates and copies original image bytes into a new result directory, generates a rectilinear project, runs all-pairs homography control-point matching, and reports disconnected images. The 50-degree initial horizontal FOV is an **assumption**, not camera calibration. Supply a measured value when available. Logs/PTO files are retained; each native stage has a 900-second timeout by default. Exit 0 means only that control points connect all images; it does not mean a successful stitch. Exit 2 means a failure or disconnected set. No network processing occurs.

For explicitly selected OpenCV diagnostics, `partial_stitch.py` accepts one-based photo numbers, e.g. `--photos 1,2,3,4`, with required input and new `--output` directory. It records excluded photos and uses 1920-pixel working images / matching confidence 0.3 by default; strict alignment checks remain. A rendered result always has the name `diagnostic-partial.jpg` and exit 3, never `candidate.jpg`, even if its estimated support fills the canvas. Failures return 2. The normal full-set pipeline still uses its original thresholds and never silently drops photos.

After ZIP validation succeeds, extract a separate debug copy with PowerShell `Expand-Archive -LiteralPath .\data\room-01.zip -DestinationPath .\data\room-01-hugin`. In Hugin, load the ordered JPEGs, use a rectilinear lens model, check focal/FOV estimates rather than assuming a sensor heading calibrates them, align and examine control points across every row and the closing seam. Optimize and inspect the ceiling/floor too. On the Stitcher tab select equirectangular projection, 360-degree horizontal / 180-degree vertical FOV, a full uncropped 2:1 canvas, exposure correction and blended output. Do not autocrop away missing regions. Keep the PTO and diagnostic TIFF/PNG, and compare to the OpenCV result using the same checklist. [Hugin's Stitcher documentation](https://hugin.sourceforge.io/docs/manual/Hugin_Stitcher_tab.html) describes its projection, crop and exposure/blending controls. Pole seams can remain problematic even in dedicated panorama software; see [Hugin's projection notes](https://hugin.sourceforge.io/docs/manual/Equirectangular_Projection.html).

## Physical Android Pannellum test — pending

Transfer the reviewed candidate JPEG back to the phone by USB. It is distinct from the large source ZIP. In a separate PowerShell window, from the repository root:

```powershell
Set-Location .\360-view
& .\.venv\Scripts\python.exe server.py --lan --port 8765
```

Find the computer's Wi-Fi IPv4 with `ipconfig`. On Android Chrome open `http://YOUR_PC_WIFI_IPV4:8765`, select the candidate from the phone's Files picker, and load it. This sends only that chosen JPEG to the existing local development viewer. It does not add a processing server or external upload. Without `--lan`, use `http://127.0.0.1:8765` on the computer only.

Both devices must be on the same trusted Wi-Fi; avoid guest/client isolation and VPN routing. Allow the viewer Python executable through Windows Firewall on Private networks only. Check the PC with `Test-NetConnection 127.0.0.1 -Port 8765`; use the Wi-Fi IP, not `localhost`, on the phone. For port conflicts stop the old viewer or choose a new port on both devices. Dependencies and Pannellum assets are local; no CDN is needed.

| Check | Required observation | Result |
| --- | --- | --- |
| Full horizontal loop | Turn through the closing seam; no repeated/missing wall sections | Pending user test |
| Ceiling | Tilt fully up; inspect fixture/corners and all azimuths near the pole | Pending user test |
| Floor | Tilt fully down; inspect corners, feet/tripod obstruction and pole | Pending user test |
| Seams and distortion | Doors, furniture and window edges remain continuous; no ghosts | Pending user test |
| Blending | No dark bands, exposure steps or color patches across joins | Pending user test |
| Sharpness | Zoom into each direction; report unreadable/blurred regions | Pending user test |
| Loading | Record selection-to-ready seconds, JPEG bytes, device/Android/Chrome versions and errors | Pending user test |
| Interaction | Touch pan, pinch zoom, fullscreen/exit and viewer replacement remain responsive | Pending user test |

The earlier user-confirmed synthetic-grid viewer tests do not certify a newly stitched room image. Do not mark these checks passed before user confirmation.

## Reproduce automated experiments

From this directory; use new names if the sample folders already exist:

```powershell
& .\.venv\Scripts\python.exe -m unittest -v
& .\.venv\Scripts\python.exe -m compileall -q inputs.py pipeline.py stitch.py partial_stitch.py hugin_reference.py synthetic.py inspect_panorama.py test_stitching.py
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe synthetic.py .\data\synthetic-full-new
& .\.venv\Scripts\python.exe stitch.py .\data\synthetic-full-new --output .\runs\synthetic-full-new --width 2048
& .\.venv\Scripts\python.exe synthetic.py .\data\synthetic-partial-new --partial
& .\.venv\Scripts\python.exe stitch.py .\data\synthetic-partial-new --output .\runs\synthetic-partial-new --width 1024
# The partial case MUST return 3 and produce diagnostic-only.jpg, not candidate.jpg.
```

Cross-language export check, from `360-view/capture-lab`, after generating the synthetic input:

```powershell
npx.cmd tsx tools/export-fixture.ts ../stitching-lab/data/synthetic-full-new ../stitching-lab/data/export-new.zip
& ..\stitching-lab\.venv\Scripts\python.exe ..\stitching-lab\stitch.py ..\stitching-lab\data\export-new.zip --validate-only --output ..\stitching-lab\runs\export-new-check
```

This uses the exact mobile ZIP writer, then Python's independent ZIP reader and complete JPEG decoding. It does not exercise Android filesystem/sharing adapters. Latest automated results: **47 Python tests** passed; the earlier capture export fix passed **78 capture tests**. Capture code was unchanged during the second-room investigation. See the experiment record for commands.

## Practicality and eventual Android implementation

Full-sphere projection is technically feasible in the demonstrated idealized, fixed-center rotation case. Reliable automatic stitching from the current handheld workflow is **not yet established**: both real sets failed, and the independent Hugin comparison also showed missing connections and poor optimized alignment. The next useful investigation is camera calibration and visual overlap/control-point review on these retained photographs, followed by capture guidance that detects weak overlap before export. Keep the camera lens near one point, overlap neighboring rows and the closing seam, and add pole/corner shots based on actual gaps. Fixed photo counts or approximate targets cannot certify overlap.

For a later Android implementation, use an isolated native Kotlin/C++ module and worker processing, not this desktop Python process or large image arrays passed through React Native JavaScript. [OpenCV documents Android SDK/NDK integration](https://docs.opencv.org/4.13.0/d5/df8/tutorial_dev_with_OCV_on_Android.html). Prototype bounded-memory feature extraction, incremental matching, tiled warping, cancellation, thermal/battery controls and resumable local jobs before full-size blending. Measure memory and latency on low/mid-range devices.

Capture calibration and quality feedback are likely the next useful work: record lens identity, zoom/crop, exposure-time synchronized sensor poses, available intrinsics/distortion, and exposure/focus settings; validate camera-to-sensor axes on real hardware. [Android Camera2 documents intrinsic calibration availability and coordinate conventions](https://developer.android.com/reference/android/hardware/camera2/CameraCharacteristics#LENS_INTRINSIC_CALIBRATION). These capabilities vary by device and are not currently supplied by the Expo manifest. Use calibrated FOV and visual match feedback to request additional shots; fuse sensors with image evidence rather than treating gyro integration or magnetic north as absolute alignment. Do not claim an on-device performance or production quality result from this experiment.
