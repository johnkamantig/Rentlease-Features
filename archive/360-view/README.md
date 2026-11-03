# RentLease panorama prototypes

Local experiments on feature/360-view-local, scoped to 360-view/. No main frontend, Supabase, GPS, ML or Render changes, production service, deployment, commit or push. Current capture is an optional **horizontal 120–180 degree sweep**. UI is deliberately basic; the eventual frontend is separate.

- [capture-lab](capture-lab/README.md): existing Expo project and working camera/sensors/storage/export, simplified guidance.
- [stitching-lab](stitching-lab/README.md#horizontal-capture-preparation): validate/copy ordered original photos for later ordinary OpenCV stitching.
- **/horizontal.html**: new flat pan-and-zoom viewer, preserving horizontal image proportions.
- **/**: retained Pannellum 2.5.7 viewer for genuine full-sphere equirectangular images and the synthetic grid.

This refactor does not generate a stitched room panorama. A capture plan, aspect ratio or successful viewer load does not prove correct stitching or coverage.

## Windows PowerShell setup

Use 64-bit Python 3.13 (validated with 3.13.7). From the repository root:

```powershell
Set-Location .\360-view
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Reuse an existing .venv instead of recreating it. No activation or execution-policy change is necessary. If py is unavailable, use the installed Python executable's full path. Pillow remains the only processor runtime dependency. OpenCV stays in the separate stitching environment.

## Local-only and LAN startup

```powershell
# Computer only:
& .\.venv\Scripts\python.exe server.py --port 8765
# Stop with Ctrl+C before starting this LAN alternative:
& .\.venv\Scripts\python.exe server.py --lan --port 8765
```

Open http://127.0.0.1:8765/horizontal.html on the PC. On Android Chrome use http://YOUR_PC_WIFI_IPV4:8765/horizontal.html. Get the Wi-Fi IPv4 with ipconfig. Both devices must be on the same trusted Wi-Fi. The original spherical viewer remains at the same host's / address.

Troubleshooting: avoid guest Wi-Fi/client isolation and VPN routing; allow this Python executable through Windows Firewall on Private networks; run `Test-NetConnection 127.0.0.1 -Port 8765` on the PC. On the phone localhost means the phone itself. For occupied ports stop the old viewer or choose a different port in both command and URL. Localhost is the default binding; --lan must be explicit. Do not expose the unauthenticated development server to the internet.

Both viewers use the existing local HTTP processor. Output files remain under uploads/ on this computer until removed; no external upload occurs. Capture ZIPs go into stitching-lab/data/, not the image viewer picker. Both viewers work without a CDN.

## Validation and projection

The processor now accepts **non-2:1 proportions**. Limits: still JPEG/PNG/WebP, 25 MiB input, 40 million decoded pixels, at least 1024 pixels on the long side and 256 on the short side. The long side is resized to at most 4096, without upscaling or stretching (apart from whole-pixel rounding). Output JPEG must be strictly below **10 MiB = 10,485,760 bytes**, the existing prototype limit.

Decompression warnings/errors, animations, corruption/truncation and invalid dimensions remain rejected with clean messages. EXIF orientation is applied; a fresh RGB canvas strips source EXIF/GPS/XMP/ICC/comments. Transparent pixels are composited on white. Quality retries enforce the output cap. Random names, atomic writes, bounded HTTP reads, one processing slot and served-path allowlists remain.

Pannellum supports partial **equirectangular** images with correct angular extents and vertical offset: [official example](https://pannellum.org/documentation/examples/partial-panorama/) and [reference](https://pannellum.org/documentation/reference/). Arbitrary cylindrical, planar or cropped OpenCV output cannot simply use that projection. Our manifest has planned angles, not measured stitched extents. The flat page therefore displays pixels directly with drag/pinch/buttons/keyboard zoom, without inventing a projection or wrapping the scene into a sphere. No new viewer library was added.

The old spherical page still checks its expected image shape and directs other shapes to the flat viewer. Even 2:1 does not prove full-sphere coverage. It remains available until revised physical testing is confirmed. Vendored Pannellum assets, COPYING, VERSION and provenance.json under static/vendor/pannellum-2.5.7/ are unchanged and checksum-tested.

## Automated checks

From 360-view:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
& .\.venv\Scripts\python.exe -m compileall -q processor.py server.py tests
& .\.venv\Scripts\python.exe -m pip check
node --check static/app.js
node --check static/horizontal.js
# Optional desktop Chrome suite; existing Chrome, no browser download:
& .\.venv\Scripts\python.exe -m pip install playwright==1.55.0
& .\.venv\Scripts\python.exe tests/browser_smoke.py -v
```

**64 processor/server/static tests and 20 desktop Chrome tests passed.** Chrome covers both viewers, blocked external networking, proportions, drag/pinch/keyboard zoom, loading/error/timeout recovery, replacement, mobile-sized layout and fullscreen fallback. A desktop mobile-sized viewport is not a physical Android test. See [the refactor report](HORIZONTAL_REFACTOR.md) for the complete inventory, results and rollback.

## Android Chrome retest

Start server.py --lan and open /horizontal.html on the POCO F7:

1. Load the synthetic test image; verify loading feedback and synthetic labeling.
2. Select a known wide JPEG/PNG/WebP. Proportions must remain intact without wrapping. It can be an existing panorama; the app does not yet stitch capture photos.
3. Pinch/use zoom buttons, swipe to each edge and Fit image. Check surrounding page controls remain reachable.
4. Enter/exit fullscreen or expanded mode; rotate the phone and check layout.
5. Replace the image; try an invalid file, then recover. A failed replacement should keep the previous working image.
6. For a future real stitch, inspect seams, blur/holes and record loading time/output bytes.
7. Open / and repeat the existing Pannellum synthetic-grid interactions for regression checking.

All revised physical results remain **pending user confirmation**.
