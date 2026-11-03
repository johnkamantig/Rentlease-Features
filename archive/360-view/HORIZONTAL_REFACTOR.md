# Horizontal capture refactor — 2026-10-28

Scope: only `360-view/`, working branch `feature/360-view-local`. No commits, staging, pushes, deployment, new server, database changes or modifications to the main frontend/GPS/ML/Render. No original capture ZIP/image was deleted or changed. No files were removed from the final source tree.

## Rollback point

Created branch **backup/360-view-before-horizontal-20261028** before source changes, without committing. The folder was entirely untracked (`?? 360-view/`), so a branch pointer alone cannot preserve it. A complementary local archive contains all **61 nonignored source files** before this refactor, including vendor assets and lockfiles:

- `.rollback/before-horizontal-20261028/source.zip`
- `.rollback/before-horizontal-20261028/manifest.json`: original HEAD and per-file SHA256 hashes.
- Archive SHA256: `7510a133e3bfc6b00b0483e805ff93ea4bcc26edff30c45b816895af8cc1e1bd`.

Every archived member was CRC-checked and compared to its source SHA256. Private ZIPs/photos, virtual environments, installed dependencies and generated outputs were already ignored and remain in place. `.rollback/` is now ignored. The working branch stayed on feature/360-view-local. Switching branches alone does not restore these untracked sources.

For rollback, first preserve any newer work, verify the archive hash, and expand it into a new inspection directory under `.rollback/`; then restore the listed source files after review. Remove only the six newly added files listed below if reverting completely. Do not use git clean or delete data/runs/uploads. Reinstall capture dependencies with npm.cmd ci after restoring the original lockfile. No rollback was performed in this task.

## Retained and changed behavior

Reused camera permission/preview and cache-provenance handling; SDK 58 File/Directory export fix; approximate accelerometer/magnetometer guidance; local original photos and metadata; immutable saves/retake rollback; thumbnails; pause/resume/interruption recovery; confirmed cleanup and byte-preserving ordered ZIP export. Native camera/filesystem/sensor modules were not rebuilt or replaced.

New sessions contain one level horizontal sequence across a 120/150/180-degree planned turn. Spacing remains adjustable; additional overlap photos are inserted in order. Horizontal positions alone complete the set. Completion still says no panorama has been generated. UI is basic and the main frontend is untouched. Build label: **horizontal-1**.

Version-1 saved records gain validated optional captureMode/sweepDegrees fields. Existing full-sphere records remain readable/exportable without conversion/deletion. Old capture/retake stages are disabled. An incomplete legacy set remains on disk and needs the rollback build to complete; a fully photographed one can still finish/export. The actual 56-photo session parsed unchanged under the revised TypeScript validator.

The Pillow processor accepts non-2:1 proportions, bounds the long side to 4096 without upscaling, preserves dimensions proportionally and retains format/decompression/corruption/animation checks, metadata stripping, atomic saves and the strict 10 MiB cap. Minimum input: long side 1024, short side 256; maximum 40 million decoded pixels and 25 MiB input. Existing server routes/security restrictions remain, with three explicit flat-viewer asset routes added.

The new `/horizontal.html` displays flat pixels with pan, pinch/buttons/keyboard zoom, Fit, loading/error/timeout handling, replacement and fullscreen fallback. Original Pannellum remains at `/`, with its pinned assets/licenses unchanged. Pannellum can show a partial equirectangular projection using correct angular extents; planned capture angles do not supply those extents for an arbitrary OpenCV output. See [official partial panorama documentation](https://pannellum.org/documentation/examples/partial-panorama/). Non-spherical output therefore uses the flat page. The existing spherical page directs non-2:1 shapes there.

`prepare_horizontal.py` validates and copies ordered original photos for a later ordinary OpenCV pipeline. New horizontal sets are selected in full; legacy subsets require explicit photo numbers. Exclusions are recorded, originals remain intact, and no stitching/projection or missing room content is generated. The old spherical experiment remains historical; no new complex spherical processing was implemented.

## Exact source inventory

Paths below are relative to `360-view/` and compared to the verified rollback archive.

Modified (23):

```text
.gitignore
README.md
capture-lab/App.tsx
capture-lab/README.md
capture-lab/package.json
capture-lab/package-lock.json
capture-lab/src/cameraCaptures.ts
capture-lab/src/domain.ts
capture-lab/src/exportSession.ts
capture-lab/src/sessionService.ts
capture-lab/tests/domain.test.ts
capture-lab/tests/export.test.ts
capture-lab/tests/session.test.ts
processor.py
server.py
static/app.js
static/index.html
stitching-lab/README.md
stitching-lab/inputs.py
tests/browser_smoke.py
tests/test_processor.py
tests/test_server.py
tests/test_static.py
```

Created (6):

```text
HORIZONTAL_REFACTOR.md
static/horizontal.html
static/horizontal.js
static/horizontal.css
stitching-lab/prepare_horizontal.py
stitching-lab/test_horizontal.py
```

Safely removed: **none**. Runtime private source/result directories remain ignored. Additional local artifacts include the rollback archive, byte-preserving prepared sets, a synthetic interoperability ZIP and a desktop mobile-size screenshot at `stitching-lab/runs/horizontal-flat-mobile-preview.png`, which was examined for layout. That screenshot is not Android evidence.

## Exact automated checks and results

Baseline before edits: capture TypeScript + **78/78 tests**, processor/server/static **59/59 tests**.

From `360-view/capture-lab` after edits and SDK patches:

```powershell
npm.cmd run check
npx.cmd expo install --check
npx.cmd --yes expo-doctor
npm.cmd run bundle:android
```

Final results: TypeScript passed; **83/83 tests passed**, no failures/skips; Expo reports dependencies up to date; **20/20 Doctor checks passed**; Android Hermes bundle exported successfully, 684 modules, approximately 1.8 MB. The initial sandboxed online checks encountered network EACCES. The allowed network-enabled checks then identified SDK patch mismatches, which were fixed and rechecked successfully. SDK 58 retained: expo 58.0.20, expo-camera 58.0.13, expo-file-system 58.0.12. No new direct dependency was introduced.

From `360-view`:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
& .\.venv\Scripts\python.exe tests/browser_smoke.py -q
& .\.venv\Scripts\python.exe -m compileall -q processor.py server.py tests
& .\.venv\Scripts\python.exe -m pip check
node --check static/app.js
node --check static/horizontal.js
```

Results: **64/64 processor/server/static tests passed** in 5.300 s; **20/20 desktop Chrome tests passed** in the final 12.447 s run (Chrome 156.0.8078.48); Python compilation and JavaScript syntax checks passed; pip found no broken requirements. Browser tests exercise both viewers, proportions, drag/pinch/keyboard, loading/timeouts/errors, replacement, mobile-width layout, fullscreen and local-only assets. The final run also checks that mobile expanded-mode controls/image fit on screen. No external image/network request was needed by either page.

From `360-view/stitching-lab`:

```powershell
& .\.venv\Scripts\python.exe -m unittest -q
& .\.venv\Scripts\python.exe -m compileall -q inputs.py prepare_horizontal.py test_horizontal.py
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe prepare_horizontal.py data/capture-mvrm2jus-lhdc5ugk5l-r59-1793162116582.zip --photos 1,2,3,4,5,6,7,8 --output runs/horizontal-real-prepared
```

Results: **55/55 Python tests passed** in 5.927 s; compilation and pip check passed. Real-input preparation exited 0: **8/8 selected JPEGs** decoded and were independently compared byte-for-byte against the original archive. Forty-eight excluded photos remain in the original ZIP. Source ZIP SHA256 still equals `6145ed0649e8307eda33233276a9cffe50e5af1a4bef411b5beaa97e4b0bde3f`. No panorama was created or claimed.

Cross-language check used a four-image synthetic fixture with horizontal guide metadata (guide angles are not ground-truth calibration). Actual commands:

```powershell
# From capture-lab:
npx.cmd tsx tools/export-fixture.ts ../stitching-lab/data/horizontal-export-fixture ../stitching-lab/data/horizontal-export-fixture.zip
# From stitching-lab:
& .\.venv\Scripts\python.exe prepare_horizontal.py data/horizontal-export-fixture.zip --output runs/horizontal-export-prepared
```

Both exited 0; the actual mobile ZIP writer's original bytes/order/metadata were accepted by Python. These desktop checks do not exercise the physical camera, native folder picker or sharing destination.

## Revised physical retest

All revised phone tests are **pending**, not marked passed. Preserve the existing ZIP/phone originals. Start Metro with `npx.cmd expo start --lan --clear` from capture-lab, scan the new QR in SDK-58-compatible Expo Go, and verify horizontal-1. Review/export the existing set before confirming its deletion to start a new one. Select 120-degree sweep / 20-degree spacing for the short seven-position retest. Verify permissions, live preview, starting reference, level guidance/manual fallback, overlap insertion, retakes, pause/background/reopen, horizontal-only completion, ZIP validation and confirmed cleanup. Full steps: [capture README](capture-lab/README.md).

For Chrome run `& .\.venv\Scripts\python.exe server.py --lan --port 8765` from 360-view and open `http://PC_WIFI_IPV4:8765/horizontal.html`. Verify proportions, pinch/pan/Fit, fullscreen, replacement and errors with a known image; then retest the existing `/` Pannellum grid. [Viewer checklist](README.md#android-chrome-retest).

Remaining limitations: overlap and compass readings are not validated alignment; a 120–180-degree guide turn is not measured output coverage; this task prepares photos but does not implement automatic horizontal stitching. No new real stitched result exists to validate. Physical behavior after the SDK patch updates must be confirmed on the POCO F7. Main-app/production integration remains outside this prototype.
