# Standalone 360 panorama viewer

Local Pannellum 2.5.7 viewer for the calibrated Phase 2 JPEG/JSON contract. No upload service, framework, Expo app, remote CDN or production integration.

## Run

From the repository root:

```powershell
node .\panorama-view\viewer\serve.mjs
```

Open <http://127.0.0.1:4173/>. Stop with Ctrl+C. Node 24 was used for validation. This dependency-free server binds only to loopback and serves viewer assets, not the repository, `samples/`, or original outputs. Vendored Pannellum files and synthetic examples are included; npm installation is only needed for development/tests. Use the HTTP server rather than opening `index.html` directly.

1. Choose **Reference sphere**. This is the independent, known-good periodic spherical texture used to render the Phase 2 test cameras; it was not produced by stitching. Its explicit reference metadata records exact 360 x 180 geometry.
2. Choose **Phase 2 synthetic**. This uses a byte-identical copy of the existing 1536 x 293 JPEG and its original sidecar, including SHA-256. It retains 360 x 68.671875 degrees, with vertical offset +0.1171875 degrees.
3. To open another result, choose its JPEG and JSON, then **Open panorama**. Files are read in browser memory and are never uploaded. Reference-only metadata is not accepted through this capture-output form.

Drag with mouse or touch, scroll/pinch, or use the zoom buttons. Yaw is unrestricted through a whole revolution in either direction. Pitch and zoom adapt to the calibrated vertical bounds and viewport size. The 0.3-degree viewport safety margin avoids sampling outside photographed rows; it does not crop the source or change its angular metadata. A tall screen must zoom farther in to keep all viewport pixels inside a limited vertical strip.

## Validation contract

`horizontal_coverage_deg`, `vertical_coverage_deg`, and `vertical_offset_deg` map exactly to `haov`, `vaov`, and `vOffset`. There are no calibration defaults. The viewer checks schema, projection, complete rotation/closure evidence, source-mask coverage, encoded-seam diagnostics, dimensions, byte limit and SHA-256, then decodes and checks actual dimensions. Embedded GPano XMP cannot override the JSON. Unrecognized JSON fields never become Pannellum options; the legacy absolute `output` path is ignored.

Validation checks the processing contract, not the truth of a user-edited report or the authenticity of a scene. It cannot re-run image alignment from a JPEG, authenticate calibration measurements, or guarantee absence of local ghosts. Keep the original processing evidence and visually review real rooms.

Missing or invalid metadata, bad hashes, wrong dimensions, corrupt images, failed requests, unsupported WebGL and loading timeouts show a basic error; selecting valid files allows retry. Loading older files cannot replace a newer selection. Raw photos are not accepted as verified panoramas.

## Why there is a small Pannellum renderer patch

Upstream 2.5.7 uses `CLAMP_TO_EDGE` for WebGL1 image textures. On the non-power-of-two Phase 2 strip this creates a visible magnified jump between its last and first columns. Equivalent-yaw tests alone missed it; screenshot inspection and adjacent-column measurements detected it.

`build-vendor.mjs` adds periodic linear interpolation of existing horizontal pixels in the equirectangular shader, only for full horizontal coverage. This implements ordinary wrap texture sampling for arbitrary image dimensions, including the upstream split-texture path. It changes no source photograph, JPEG, hash, field of view, crop, or vertical sampling. No missing image content is generated. Mouse/touch interaction and projection remain Pannellum's. The bundled readable source retains the upstream MIT license; `vendor/COPYING` contains it.

The patch is version-locked and checks its source anchors. Review it before upgrading Pannellum. Automated rendered-edge tests cover the supplied single-texture fixtures; hardware-limited split textures and mobile GPU differences remain unvalidated.

## Tests and reproducible vendor build

From `panorama-view/viewer`:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run test:browser
# Only when rebuilding the checked-in vendor files:
npm.cmd run build:vendor
```

The lockfile pins Pannellum 2.5.7 and Playwright 1.64.1. Browser tests use installed Chrome by default, software WebGL for reproducible pixel checks, and a temporary loopback server. Set `$env:PLAYWRIGHT_CHANNEL = 'msedge'` to exercise an installed Edge instead; that browser is not claimed tested here. The suite requires port 4173 to be free and may need normal process-launch permissions on Windows. No browser download is required if Chrome is installed.

If 4173 is occupied, set `$env:PORT = '4174'` before the test command to use another free loopback port. The suite refuses to reuse or terminate an existing server. Phase 4 regression tests passed on 4174 while leaving the existing process on 4173 untouched.

Tests validate the known-good reference first, then synthetic output: full mouse turns, equal views at equivalent headings, continuity at the cut, local edge interpolation, exact FOV settings, pitch/zoom limits, resizing, no black pixels in sampled views, mouse wheel/buttons, emulated touch dragging and pinch, failures/recovery, and no external network requests. `test-results/` is regenerated by Playwright. Preserved evidence from this run is in `../output/viewer-phase3/` and summarized in [the phase report](../PHASE3_RESULTS.md).

## Remaining manual checks

- On physical Android Chrome, confirm repeated left/right turns, one-finger drag, two-finger pinch in and out, portrait/landscape changes, and entering/exiting fullscreen. Confirm page scrolling does not take over the panorama gesture. Emulated touch events do not establish hardware behavior.
- Visually cross the seam slowly at several zoom levels using authentic room imagery; inspect straight walls, doors, furniture, exposure and foreground ghosting. The current fixtures are synthetic textures.
- Exercise low-memory/WebGL texture limits and actual mobile GPU behavior. Performance and thermal behavior are not measured by the desktop software renderer.
- For USB device testing, with Android debugging already configured, `adb reverse tcp:4173 tcp:4173` lets Android Chrome use `http://127.0.0.1:4173/` while keeping the server on loopback. This has not been executed without a physical device. Do not expose private photographs through a public server to test gestures.

References: [Pannellum configuration](https://pannellum.org/documentation/reference/), [Pannellum 2.5.7 source](https://github.com/mpetroff/pannellum/tree/2.5.7), [upstream renderer](https://github.com/mpetroff/pannellum/blob/2.5.7/src/js/libpannellum.js).
