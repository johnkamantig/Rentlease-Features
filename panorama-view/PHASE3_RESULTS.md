# Phase 3 results - completed 2026-10-30

Phase 3 is implemented and tested locally. This report distinguishes desktop synthetic-image/browser evidence from real-room and physical-device validation, which remain outstanding. No Expo capture work was started.

## Repository and relocation

`git rev-parse --show-toplevel` returned `C:/Users/kaman/Rentlease-Features`. The branch was already `feature/panoramic-room-view`; no branch change was necessary. The independent prototype was untracked. The prototype was incorrectly nested, and `RentLease-Features/panorama-view/` did not exist.

The move used native PowerShell `Move-Item -LiteralPath` after resolving and verifying both absolute paths within the intended repository and refusing an existing destination. All **3,613 files** were inventoried and SHA-256 checked before and after relocation, including hidden files, tests, documentation, generated images, original sidecars and the virtual environment. File counts and hashes all matched. The verification inventory is `output/relocation-verification.json`.

The empty `rentlease_panorama_360_revised_plan/` parent was left in place. Unrelated directories were untouched. Current untracked implementation lives at `panorama-view/`. Historical reports and original output JSON retain their original provenance, including old absolute output paths. Current instructions use the new root path, and the viewer ignores the historical `output` field.

Immediately after relocation, `.\.venv\Scripts\python.exe -m pytest -q` passed **47 tests in 44.59 seconds**. Python module invocation works from the moved environment; old generated activation/launcher scripts may still embed the former path, so use the documented interpreter commands rather than those launchers.

## Files changed or added

| Files | Purpose |
| --- | --- |
| Entire original prototype subtree | Relocated without content loss to `panorama-view/`. |
| `.gitignore` | Ignore viewer dependencies and regenerated browser-test evidence. |
| `README.md`, `CODEX_STAGE1_HANDOFF.md`, `DEVELOPMENT_PLAN_360.md` | Correct active paths and describe the completed viewer and remaining gates. |
| `viewer/index.html`, `viewer/viewer.css` | Minimal controls, file inputs, loading/error text and panorama surface. |
| `viewer/app.mjs` | Local example/file loading, validation, retry, resource cleanup and resize handling. |
| `viewer/metadata.mjs` | Strict metadata/integrity checks and calibrated Pannellum configuration. |
| `viewer/serve.mjs` | Dependency-free loopback preview server restricted to viewer assets. |
| `viewer/package.json`, `viewer/package-lock.json`, `viewer/playwright.config.mjs` | Pinned development dependencies and repeatable tests. |
| `viewer/build-vendor.mjs`, `viewer/vendor/*` | Local Pannellum 2.5.7 bundle, MIT license and documented periodic-sampling correction. |
| `viewer/fixtures/reference.*`, `viewer/fixtures/synthetic.*` | Known-good spherical reference with explicit mathematical metadata, and byte-identical Phase 2 JPEG/JSON copies. |
| `viewer/tests/metadata.test.mjs`, `viewer/tests/viewer.spec.mjs` | Contract/unit and real browser tests. |
| `viewer/README.md`, `PHASE3_RESULTS.md` | Run instructions, reproduction, evidence, limitations and next steps. |

No Python implementation or inherited Python test source was changed for Phase 3. No original output was rewritten. Final comparison against the relocation manifest confirmed all 35 original implementation/test/requirements/output files were unchanged; all three copied JPEG/JSON fixtures matched the originals byte for byte.

## Results

| Check | Actual result |
| --- | --- |
| Relocated Python suite | 47 passed, 0 failed, 44.59 seconds. |
| Viewer unit/contract suite | 27 passed, 0 failed. |
| Final browser suite | 8 passed, 0 failed/skipped/flaky, 17.1 seconds. |
| First viewer input | Independent 3072 x 1536 cyclic sphere, 360 x 180 degrees, 2,421,664-byte JPEG; explicit mathematical reference provenance. |
| Second viewer input | Original Phase 2 1536 x 293 strip; 249,498-byte JPEG; haov 360, vaov 68.671875, vOffset +0.1171875. |
| Mouse rotation | Repeated real mouse drags exceeded a full revolution in both directions without a wrap stop. |
| Wrap alignment | Equivalent headings render equal within 0.05 mean RGB levels; a small crossing remains below the test's 8-level mean difference bound. |
| Vertical bounds | Rendered pitch and vertical FOV stayed within metadata bounds at top/center/bottom, five yaw positions, desktop and portrait sizes. |
| Empty regions | Zero near-black pixels in sampled reference/synthetic views. This fixture has no real black surfaces; this is not a general black-content detector. |
| Interaction | Mouse zoom buttons/wheel and Chromium-emulated touch drag/pinch passed. |
| Invalid data/recovery | Missing calibration, incomplete closure, malformed JSON, mismatched hash/dimensions, corrupt JPEG, failed asset request and missing WebGL were rejected; valid retry passed. |
| Local-only behavior | Browser test detected no external requests; server denied repository/source-photo and dependency paths. |

Screenshots of the reference, corrected wrap view, portrait layout and emulated pinch were saved and inspected. Preserved artifacts and the full JSON test report are in `output/viewer-phase3/`. These show synthetic visual checks, not a real-room walkthrough.

### Discovered rendering issue and fix

The first seven browser assertions passed, but screenshot inspection found a narrow visible line at the wrap boundary. Equivalent-yaw equality was insufficient to detect it. Further comparison showed the upstream WebGL1 `CLAMP_TO_EDGE` texture sampling stopped interpolation between the first and last columns. The original Phase 2 JPEG's geometry and hash were unchanged.

At the magnified cut, the mean adjacent-column jump was **13.60 RGB levels**, compared with **3.24** at the 95th percentile of ordinary image edges. A small local shader correction now interpolates periodically across existing horizontal pixels for a full-circle texture. After correction the cut jump is **4.24**, versus **3.26** for ordinary-edge p95, passing the new 1.7x edge-ratio regression. The corrected screenshot no longer shows the earlier sharp texture-clamping line.

This is a Pannellum renderer correction, not panorama stretching, source-image editing, invented imagery or new camera calibration. `build-vendor.mjs` reproduces it against version 2.5.7 and refuses unexpected source anchors. The split-texture branch is implemented but not exercised by the supplied fixtures; physical mobile GPUs remain a separate validation step.

### Commands and execution notes

Inspection: `git status --short`, `git branch --show-current`, `git rev-parse --show-toplevel`, `Get-ChildItem`, `Get-Content`, and `rg --files`. Relocation used `Resolve-Path`, `Get-FileHash`, and `Move-Item -LiteralPath`; its original file inventory was retained.

After relocation:

```powershell
cd C:\Users\kaman\Rentlease-Features\panorama-view
.\.venv\Scripts\python.exe -m pytest -q
cd viewer
npm.cmd install --save-exact pannellum@2.5.7
npm.cmd install --save-dev --save-exact @playwright/test
npm.cmd test
npm.cmd run build:vendor
npm.cmd run test:browser
```

`npm.cmd` avoids the machine's disabled PowerShell npm script policy. An initial sandboxed dependency attempt was interrupted when network access stalled; the approved escalated install succeeded. The initially evaluated Pannellum 2.5.6 was replaced with patched 2.5.7 before bundling; the final install reported zero audit findings. The final lockfile pins Pannellum 2.5.7 and Playwright 1.64.1.

The first sandboxed browser run passed its seven checks but stalled during Windows process teardown and was interrupted. After the seam regression and WebGL failure check were added, the approved run outside that sandbox completed all eight checks and cleaned up the server. No failing checks remain. The tests use installed Chrome 156.0.8078.48 with software WebGL and Node 24.17.0, not physical Android graphics.

Additional diagnostics compared rendered source/reference pixels and inspected screenshots; node syntax, local links, fixture hashes, tracked-file diffs and final scope were checked. The preview is not left running. Start it with `node .\panorama-view\viewer\serve.mjs` from the repository root and visit <http://127.0.0.1:4173/>.

## Unresolved validation and next actions

1. Physically confirm touch drag, pinch in/out, orientation changes and fullscreen on Android Chrome. Browser emulation cannot establish hardware smoothness, gesture conflicts or GPU correctness. Fullscreen interaction and alternate browsers were not automated.
2. Supply authentic, ordered, overlapping room photographs and measured calibration for Phase 4. Review the entire room and seam at multiple zoom levels for ghosts, exposure jumps, parallax and geometric distortion. Synthetic textures cannot establish real-room fidelity.
3. Measure mobile memory, texture-size limits and rendering performance, including any split-texture path. The desktop software-rendered results are not phone benchmarks.
4. Keep Expo capture development deferred until the real-photo and viewer gates pass.

The metadata checks establish consistency with the local processing contract, not authenticity of user-edited JSON or calibration claims. Viewer display cannot replace capture-to-stitching verification. No production frontend, Supabase, GPS, FastAPI, Render, database/Storage policy or unrelated directory was modified. No commit, push, merge or deployment was performed.
