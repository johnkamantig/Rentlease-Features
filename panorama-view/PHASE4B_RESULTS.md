# Phase 4B - fresh room photographs, 2026-10-30

**Result: no accepted full-circle panorama.** All 41 fresh photographs were evaluated in timestamp order. The final/first images have strong matching evidence, but a long blank-wall section disconnects the sequence. The existing high-level stitcher used only 15 of 41 images, so the completeness check rejected it. The calibrated pipeline separately refused export because measured active-image calibration is missing. No panorama JPEG or calibrated viewing JSON was generated, and no room image was loaded into Pannellum.

This evaluation used only the fresh user-supplied photographs in this independent project. Originals were not modified; all 41 original and imported-copy hashes were verified after diagnostics. No excluded material, production component, Expo application, paid service or generative reconstruction was used. Nothing was committed, pushed, merged or deployed.

## Input inventory and order

Source directory:

```text
C:\Users\kaman\Rentlease-Features\panorama-view\samples\fresh-room\input\
```

- **41 JPEGs**, all **1888 x 4096 pixels**, totalling **108,349,722 bytes**.
- Individual files range from **1,271,840 to 7,969,104 bytes**. There are 30 `IMG_` and 11 `MVIMG_` filenames.
- All files decoded/verified. No exact file duplicate, exact decoded-image duplicate, or near-duplicate under the existing thumbnail gate was found.
- Capture order was checked using unique EXIF `DateTimeOriginal` plus `SubsecTimeOriginal`. It agrees with the embedded filename time order, from **16:58:03 through 16:59:55**. Some filename seconds differ from EXIF by one second but do not change order. Alphabetically sorting the IMG/MVIMG prefixes would be wrong.
- The provided file set has no timestamp tie or corrupt image. Timestamps alone cannot prove whether additional shutter captures were omitted before transfer or whether a full physical revolution occurred.
- All images have EXIF orientation **0**, which is non-standard. Contact-sheet inspection found them visually upright. No rotation was invented or applied to the originals.
- The primary JPEG still image is decoded. Inspected MotionPhoto XMP includes appended video and an HDR gain-map payload; large byte counts need not imply a higher-resolution still. The entire original file was preserved, including its metadata/payloads.

The numbered filename/time list and original hashes are in `output/phase4b/input-summary.json` and `input-inventory.json`. The explicit order file is `output/phase4b/order.json`. All 41 files were imported unchanged into `samples/fresh-room/imported-phase4b/originals/`; none were excluded.

## Overlap and closing-pair evidence

Processing used SIFT at long edge 1200, at most 3500 features/frame, the existing OpenCV nearest-neighbor/RANSAC ring matcher, and unchanged count/ratio/confidence thresholds. Working images total about 27.2 million pixels, within the 36-million processing-pixel guard.

The initial audit exposed an OpenCV FLANN assertion: `knn <= index_->size()`. The existing audit attempted k=2 matching against a one-descriptor frame. The corrected audit leaves every photograph and pair in the report but masks out impossible KNN queries and marks those edges weak. It now emits a report and optional matching preview for every pair.

**29 / 41 pairs pass the preliminary count/ratio screen; 12 are weak.** This limited screen does not certify spatial distribution, calibrated geometry, actual overlap percentage or successful loop alignment.

| Weak pair, 1-based photo numbers | RANSAC inliers |
| --- | --- |
| 10 -> 11 | 5 |
| 13 -> 14 | 13 |
| 14 -> 15 | 6 |
| 29 -> 30 | 9 |
| 30 -> 31 | 0 |
| 31 -> 32 | 0 |
| 32 -> 33 | 0 |
| 33 -> 34 | 0 |
| 34 -> 35 | 0 |
| 35 -> 36 | 0 |
| 36 -> 37 | 0 |
| 37 -> 38 | 0 |

The closing pair **41 -> 1** has **198 tentative matches, 156 inliers, 78.8% inlier ratio, confidence 2.315**. The diagnostic lines connect recognizable details in the starting scene. This supports closing overlap but cannot by itself establish a complete revolution or repair the other broken connections.

Low-feature photographs:

| Photo | Filename | Keypoints at 1200 | At native resolution |
| --- | --- | --- | --- |
| 31 | IMG_20261030_165928.jpg | 3 | 3 |
| 32 | IMG_20261030_165931.jpg | 0 | 0 |
| 33 | IMG_20261030_165935.jpg | 0 | 0 |
| 34 | IMG_20261030_165937.jpg | 0 | 0 |
| 35 | IMG_20261030_165941.jpg | 0 | 0 |
| 36 | IMG_20261030_165943.jpg | 1 | 9 |
| 37 | IMG_20261030_165945.jpg | 4 | 13 |

The contact sheet and selected previews were opened for visual inspection. These frames are overwhelmingly blank wall; there is insufficient identifiable texture for the current feature-based verification. Native-resolution probing confirms that simple downsizing is not the main explanation for the missing features. Higher-resolution processing of these same frames does not establish reliable geometry.

The full contact sheet is [here](samples/fresh-room/imported-phase4b/contact-sheet.jpg). Example diagnostics are [closing pair](output/phase4b/audit-1200-safe/matches-41-01.jpg), [pair 10 -> 11](output/phase4b/audit-1200-safe/matches-10-11.jpg), [pair 13 -> 14](output/phase4b/audit-1200-safe/matches-13-14.jpg), and [blank-wall pair 31 -> 32](output/phase4b/audit-1200-safe/matches-31-32.jpg).

### Capture limitations versus algorithm limitations

- **Audit implementation defect, fixed:** fewer than two descriptors could crash FLANN instead of producing weak-pair diagnostics. No image is removed by the fix.
- **Matcher sensitivity:** a separate diagnostic using match confidence 0.3 instead of production 0.65 gives 28 inliers for 13 -> 14 and lets that limited screen pass. It still leaves 11 weak pairs and all blank-wall gaps. Pair 10 -> 11 gains 31 inliers but has only a 39.7% inlier ratio, below the unchanged 45% gate. More matches are not automatically trustworthy alignment.
- **Capture limitation:** photos 31-37 lack sufficient identifiable detail, including four frames with zero native-resolution SIFT features. Lowering thresholds cannot provide geometric evidence where no stable features are found.
- **Unverified geometry:** close foreground, exposure shifts and camera translation can affect real-room alignment, but final panorama distortion/parallax cannot be judged because there is no complete calibrated output.

Production matcher/coverage thresholds remain unchanged. The sensitivity experiment is diagnostic evidence only, not accepted stitching or an implicit calibration.

## Available and missing calibration

All files report **Xiaomi / POCO F7**, **4.94 mm focal length**, and **28 mm 35mm-equivalent focal length**. The narrow **1888 x 4096** image crop is known. These are useful camera facts, but the EXIF inspected here does not supply the active sensor/crop mapping, usable focal-plane resolution, a full pixel intrinsic matrix, lens distortion calibration or a measured first-frame pitch/roll reference. Inspected XMP describes MotionPhoto/HDR payloads rather than those missing calibration values.

The processor needs either measured portrait horizontal FOV for this exact image crop plus validated centered/square-pixel/rectilinear assumptions, or measured intrinsics/distortion and a tested rectification to that supported model. Actual oriented `fx`, `fy`, principal point, distortion behavior and first-frame elevation need justification. A nominal 28 mm-equivalent value cannot silently become a precise active horizontal FOV or vertical coverage value.

The simplest reliable next step is to keep one lens, one zoom, one resolution/aspect mode and stable focus, then obtain an intrinsics report or approximately 15-20 checkerboard calibration photographs at those exact settings, including varied image positions and held-out validation. See [CALIBRATION.md](CALIBRATION.md) and [REAL_ROOM_WORKFLOW.md](REAL_ROOM_WORKFLOW.md). The supplied example JSON intentionally contains null values and is not a usable calibration. No guessed FOV or calibrated angular metadata was emitted in this phase.

## Stitching attempts and resources

| Operation | Result | Duration | Memory evidence |
| --- | --- | --- | --- |
| Corrected ring audit, all 41 frames | 12 weak pairs, strong closing pair | 9.697 s | 369.28 MiB process peak RSS |
| Existing high-level baseline, all 41 supplied | Rejected: only 15 images used | 14.715 s | 293.36 MiB process peak RSS |
| Calibrated production entry point | Refused: measured calibration required | 0.133 s precondition check | Same process as baseline; peak RSS is not a separate stitching measurement |
| Native-resolution low-feature probe | One photo at a time; four remain at zero features | About 0.87-0.90 s/photo | 1790.82 MiB process peak RSS |
| Diagnostic matching sensitivity | Still 11 weak pairs | 9.493 s | Recorded in matching-sensitivity.json |

The high-level baseline's accepted component corresponds to photos **15-29**. The completeness guard rejected the result because all 41 photographs must participate. It was not saved as a partial panorama or labelled 360 degrees. The calibrated processor refused at its calibration gate before circular alignment/projection/blending; it did not produce a JPEG/JSON pair.

The native probe retained the existing input-pixel bounds and handled one native image at a time, but its large OpenCV SIFT temporaries produced about 1.75 GiB peak RSS. Pixel bounds are not a hard OS-memory ceiling. No whole-set native-resolution run or resource-limit increase was attempted. These measurements are desktop process high-water marks, including libraries/native allocations; they are not Android benchmarks.

**Panorama dimensions, panorama file size, final seam quality, ghosting, room geometry and tenant inspection sharpness: not available/unassessed because no complete panorama was exported.** The 9,500,000-byte export cap remains unchanged.

## Pannellum and testing

Pannellum room testing was not performed because no valid calibrated room output exists. The existing viewer requires passing coverage metadata, dimensions and image SHA-256. It would be inappropriate to manufacture metadata merely to load an incomplete image. No full-rotation, seam, pinch or physical-device success is claimed for this room.

- Unchanged initial Python suite: **65 passed in 43.02 seconds**.
- After the audit fix, diagnostic-preview support and new regressions: **67 passed in 42.89 seconds**, zero failures.
- Focused workflow suite: **20 passed in 1.72 seconds**.
- New regressions cover a one-descriptor frame being excluded from unsafe KNN queries while every pair remains reported, and preview output for featureless frames.
- Existing viewer code was not changed. Prior independent viewer tests remain separate evidence; browser tests were not rerun for an absent real-room panorama in this phase.
- All 41 original and imported-copy hashes matched after inspection and processing. No physical Android validation was performed.

## Files changed and generated paths

Code changes:

- `room_validation.py`: safe handling for descriptor-poor edges, explicit matching status and optional `--match-previews` diagnostics.
- `stitch360.py`: existing low-feature rejection now names the affected photo indices; requirements and thresholds unchanged.
- `tests/test_room_validation.py`: two targeted regressions.
- Current README, phase status/handoff and calibration/workflow documentation: record the fresh evaluation and its unresolved gates.
- `PHASE4B_RESULTS.md`: this report.

Exact generated locations, all within the independent project:

```text
C:\Users\kaman\Rentlease-Features\panorama-view\samples\fresh-room\imported-phase4b\capture.json
C:\Users\kaman\Rentlease-Features\panorama-view\samples\fresh-room\imported-phase4b\contact-sheet.jpg
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\input-inventory.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\input-summary.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\order.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\duplicate-check.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\audit-1200-safe\audit.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\audit-1200-safe\matches-01-02.jpg ... matches-41-01.jpg
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\baseline-diagnostic.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\calibrated-attempt\validation.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\native-feature-probe.json
C:\Users\kaman\Rentlease-Features\panorama-view\output\phase4b\matching-sensitivity.json
```

Key commands, from `panorama-view/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_room_validation.py -q
.\.venv\Scripts\python.exe room_validation.py audit --capture samples/fresh-room/imported-phase4b/capture.json --output output/phase4b/audit-1200-safe --max-long-edge 1200 --match-previews
```

The explicit fresh order was constructed from EXIF timestamps and passed to `import_capture()`; no directory-prefix sort was used. Targeted Python probes called the existing `baseline_stitch_images()`, `measured_stitch(..., calibration_path=None)`, SIFT at native resolution, and the same OpenCV matcher at diagnostic confidence 0.3. Reports record their exact parameters/status. Existing output directories must not be overwritten when reproducing these checks; choose new names.

## Recommendation

1. Preserve these originals as the first fresh dataset and inspect the numbered match previews.
2. Retake the weak transitions around photos **10-11, 13-15 and 29-38**, with particular attention to the blank-wall sequence **31-37**. Include distinctive stationary detail across neighboring frames, not merely another blank wall crop. Match the lens position/settings if augmenting a sequence.
3. A new complete sweep from a viewpoint farther from the close blank wall is safer than splicing unrelated viewpoints. Prefer the camera's standard portrait photo aspect mode over a narrow full-screen crop where available, then calibrate that chosen mode. Keep the one-row horizontal capture; no extra ceiling/floor directions are needed.
4. Obtain calibration for the exact settings/crop and keep consistent height, focus/exposure and roughly 40-60% recognizable overlap.
5. Re-run the unchanged geometric/coverage acceptance pipeline, then Pannellum only after an accepted JPEG/JSON exists. Current data cannot support a reliable calibrated 360-degree claim. Calibration alone will not repair the missing visual connections.

Phase 4B has produced real diagnostic evidence and one targeted audit reliability fix. Real-room acceptance remains pending, and Expo development remains deferred.
