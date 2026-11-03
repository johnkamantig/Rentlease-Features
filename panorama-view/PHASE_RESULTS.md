# Phase 1 and Phase 2 results - 2026-10-29

Scope: synthetic implementation validation only. No authentic room photos, browser viewer or physical Android validation took place. The synthetic image, mathematical coverage and automated seam checks support this restricted result; they do not establish an end-to-end room-view feature.

## Phase 1 - inspection and removal of incompatible assumptions

- Branch was already `feature/panoramic-room-view`; no switch was necessary. The independent prototype was untracked; nothing was staged or committed. It was initially nested under its preparation folder and was safely moved to the intended root in Phase 3. No AGENTS.md was present at the time of Phase 1 inspection. Parent-directory enumeration was sandbox-denied; it was not needed for the implementation.
- Inspected all prototype code, tests, dependencies, local documentation and sample inventory. `samples/` contained only `.gitkeep`. No real-room sequence was supplied.
- The unchanged baseline suite passed: **15 passed in 9.55 seconds**. Root Python lacked Pillow and pytest, so an isolated environment was created inside the prototype. The first dependency download was network-sandbox denied; the escalated retry was approved and completed. Root dependencies were not modified.
- `stitch.py`: raised the file ceiling from 20 to 72 with aggregate processing/warp budgets; replaced rectangular color-based cropping and unverified export with calibrated circular processing; updated errors and CLI. Reused decoding, EXIF orientation, format checks, natural ordering, baseline error handling, JPEG compression and original-file protection. The high-level stitcher remains a comparison helper only.
- Removed the `_largest_rectangle` and `crop_black_borders` helpers and `--no-crop`; horizontal cropping is incompatible with fixed 360-degree coverage. No entire working module was deleted.
- Updated `requirements.txt`, `README.md`, `DEVELOPMENT_PLAN_360.md`, `CODEX_STAGE1_HANDOFF.md`, `RESEARCH_NOTES.md`, `STAGE1_RESULTS.md`, and the inherited tests. Added `CALIBRATION.md`. There were no partial-angle capture presets or viewer modules in the inspected code to remove.
- Phase 1 limitation: cleanup alone cannot demonstrate coverage. Next action was the cyclic pipeline and tests below.

## Phase 2 - calibrated circular stitching

Added `errors.py`, `closure.py`, `stitch360.py` and `projection.py`. These separate expected failures, independent motion/closure checks, calibrated ring matching/global refinement, and periodic projection/blending. `stitch.py` orchestrates ingestion and safe JPEG/JSON export. Added `tests/conftest.py`, `tests/cyclic_scene.py`, `tests/test_circle.py` and `tests/run_synthetic.py`.

The fixture is a periodic spherical texture viewed through 18 perspective cameras, at 20-degree heading intervals, with 320x480 portrait images and an exact 50-degree horizontal FOV. It is not a sequence of rectangular crops from a flat strip. Ground-truth comparisons cover every horizontal sector and a band across the wrap boundary. Synthetic fixtures are only for tests, never property imagery.

### Baseline comparison

The original `cv2.Stitcher_create(cv2.Stitcher_PANORAMA)` returned status 0, used all 18 indices and produced 2157x420 pixels in 36.36 seconds. At the renderer's original focal scale a revolution is approximately 2155.89 pixels wide. That near agreement is not a closure or calibrated export test. No baseline image was saved or visually approved. The detailed implementation was selected to expose and check camera rotations, exact periodic projection and source-mask coverage; the experiment does **not** prove that high-level Stitcher cannot handle a full circle.

### Measured synthetic export

Command: `.\.venv\Scripts\python.exe tests/run_synthetic.py`

Artifact: `output/synthetic-1793284508583133900/synthetic_360.jpg`, with a matching JSON, source test frames, exact test calibration and a known-good synthetic sphere in the same ignored directory.

| Measurement | Result |
| --- | --- |
| JPEG dimensions | 1536 x 293 |
| JPEG bytes | 249,498 |
| Processing time, excluding fixture generation | 8.261 seconds |
| Horizontal coverage under calibrated model | 360 degrees |
| Retained vertical coverage | 68.671875 degrees |
| Vertical center offset | +0.1171875 degrees |
| Independent accumulated turn before refinement | 360.057912 degrees |
| Independent loop drift | 0.058273 degrees |
| Maximum refined pair p95 residual | 0.225453 pixels |
| Retained source-mask coverage | 100% |
| JPEG wrap mean absolute difference | 15.3413, below the 34.6730 rejection threshold |

The JPEG was opened for visual inspection; it contains the synthetic texture with no visible empty band. Automated comparisons to the independent known-good sphere check alignment and sector content. Browser wrap/touch/pinch behavior was not tested and is not inferred from image inspection.

### Tests and observed failures

- Original suite: 15 passed before changes.
- First expanded run: 40 passed, 1 failed. A recompressed duplicate was correctly rejected later as a failed neighboring match, but the dedicated near-duplicate detector did not identify it. Area-resampled grayscale comparison fixed that detection; the rerun passed all 41 tests.
- After ingestion/export safety additions: **46 passed in 41.90 seconds**, zero failures. The subsequently added pitch-reference regression passed separately (**1 passed in 7.34 seconds**), checking the rotated sphere against an independent oracle. All 47 current tests have passed across these runs. Python compilation and CLI help also passed.
- Tests cover genuine cyclic geometry, first/last matching, clockwise and counterclockwise turns, missing frames/sectors, ordering, out-and-back false loops, repeated turns, exact/recompressed duplicates, textureless frames, incorrect calibration, heading disagreement, full-width valid masks, real black content, warp discontinuities, overlap corruption, memory limits, compression, portrait EXIF handling, formats/corruption, no calibration, original preservation, safe re-runs, failed-write cleanup, and CLI failure followed by successful recovery.
- During development the initial manually constructed OpenCV cameras lacked translation arrays; adding explicit zero translations fixed the binding conversion error. No translation optimization or 3D scene reconstruction was introduced.
- The first graph-cut projection experiment did not complete promptly and was interrupted. Tight seam bounds and OpenCV's dynamic-programming seam finder completed the tested pipeline. This is not a measured worst-case runtime guarantee.

### Commands and environment

From repository root, inspection used `Get-Content`, `Get-ChildItem`, `rg --files`, `git branch --show-current`, `git ls-files`, and `git status --short`. Setup used:

```powershell
.\.venv\Scripts\python.exe -m venv rentlease_panorama_360_revised_plan/panorama-view/.venv
cd .\rentlease_panorama_360_revised_plan\panorama-view
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests/run_synthetic.py
.\.venv\Scripts\python.exe -m pytest tests/test_circle.py::test_reference_pitch_rotates_geometry_and_keeps_correct_vertical_bounds -q
.\.venv\Scripts\python.exe -m compileall -q stitch.py stitch360.py closure.py projection.py errors.py tests
.\.venv\Scripts\python.exe stitch.py --help
```

Focused Python probes exercised the baseline, OpenCV bindings, independent alignment, projection and artifact diagnostics. Final checks include CLI help, Python compilation, source whitespace checks, tracked-file diff and Git status. Git diff is empty because the prototype was already untracked; that does not mean the prototype files were unchanged.

Observed Windows environment: Python 3.13.7, OpenCV 4.14.0, NumPy 2.5.4, Pillow 12.3.0, pytest 9.2.0. Tests set OpenCV RNG seed 7 and two threads for reproducibility. The source requirements allow compatible ranges; other versions have not been tested in this task.

### Limitations and next actions

The angular geometry depends on supplied, truthful calibration. The restricted centered rectilinear model does not calibrate arbitrary phones, rectify distorted lenses or model translation/parallax. Thresholds are provisional; masks prove sampled source coverage, not the authenticity or uniqueness of the photographed scene. Perfectly repetitive scenes remain ambiguous from images alone. Moving objects and local ghosts can escape aggregate checks and require visual review. Memory budgets bound large arrays but peak RSS and Android performance were not measured.

Phase 3 is next: validate a minimal Pannellum viewer on the known-good sphere first, then the strip, including continuous rotation, vertical restrictions, zoom, touch and errors. Phase 4 requires authentic ordered room photographs with first/last overlap and measured camera calibration. Stop before Expo capture development until those gates pass. Phases 5-7 (capture app, physical Android, native feasibility/handoff) remain unstarted.

No production files, root dependencies, GPS, excluded projects or database/Storage policies were changed. No commit, push, merge or deployment was performed.
