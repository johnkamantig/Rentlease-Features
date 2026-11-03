# Real horizontal capture checks

## 2026-10-29 — first 180-degree / 40-degree set

User supplied `data/capture-mvs8d7bp-axxmf8vj6p-r14-1793199290385.zip`, **10,662,000 bytes**, SHA256 `c3b64879e8a06b26778db3c03068b808a0465c255d6b12fe2a1bdc2cd4ba15f8`. The user previously identified the phone as POCO F7 with the prototype's default camera settings.

Actual command from `360-view/stitching-lab`:

```powershell
& .\.venv\Scripts\python.exe prepare_horizontal.py data/capture-mvs8d7bp-axxmf8vj6p-r14-1793199290385.zip --output runs/horizontal-room-01
```

Exit 0, `prepared_unstitched`. **6/6 photos passed** manifest, path/order, byte count, CRC32, dimension and complete decoding checks. Each JPEG is 3072 x 4096. The manifest correctly identifies horizontal capture, planned sweep 180 degrees, spacing 40 degrees, targets **0, 40, 80, 120, 160, 180**. No upper/lower/pole stages were required. All prepared files were independently compared byte-for-byte with the originals; archive CRC and SHA256 remained unchanged. No source photos were deleted, changed or uploaded.

Recorded approximate headings follow those targets, with tilt between about -1.55 and +0.57 degrees. Starting-wall reference is null on all six photos. These readings are not calibrated camera poses or proof of overlap. The next guided test should explicitly set the starting-wall reference, although its absence does not explain the observed visual matching failures by itself.

The contact sheet and pairwise match images were examined. Local diagnostic method: OpenCV SIFT, maximum working side 1920, up to 6000 features, mutual descriptor ratio 0.75, homography RANSAC threshold 3 working pixels, 5000 iterations, confidence 0.995, random seed 0, one thread. This was an overlap screen, **not a stitching run**. The source images were not resized on disk.

| Adjacent photos | Mutual descriptor matches | Homography inliers | Finding |
| --- | ---: | ---: | --- |
| 1–2 | 4 | 4 | Insufficient evidence; displayed matches connect different objects |
| 2–3 | 8 | 4 | Insufficient evidence; displayed matches connect different objects |
| 3–4 | 18 | 15 | Stronger connection on cabinet/wall details, narrow spatial support |
| 4–5 | 1 | Not estimable | No reliable connection found |
| 5–6 | 43 | 33 | Stronger connection, but repeated curtain hardware still needs review |

Feature counts per photo: 183, 1377, 559, 162, 212, 562. Experimental screening required at least 15 inliers, at least 50% inlier ratio and a feature convex hull covering at least 1% of each image. Only 3–4 and 5–6 passed this screen. The hull measures feature spread, **not overlap percentage**. A four-correspondence homography can fit exactly even when correspondences are wrong; the zero fit residuals in the first two pairs are not quality evidence. These thresholds are diagnostic heuristics, not universal stitchability rules.

**Result:** transfer/export succeeded, but the current feature check does not establish a reliably connected six-photo sequence. Plain walls, narrow shared views and repeated curtain details limit usable matches. No panorama was generated or accepted, and no new physical Android test is marked passed merely from receiving this ZIP.

For a small next capture test, use **120-degree sweep / 20-degree spacing** (seven guide positions), set the starting-wall reference, hold the lens near one point, keep level and retain roughly half of the previous scene. Include shared distinctive corners/furniture rather than mostly plain wall/curtain, and add an overlap photo where needed. Smaller turns should give the matcher more common content, but do not guarantee success. Preserve this ZIP for comparison before changing the phone's current session.

Artifacts, private/local and ignored by Git:

- [Prepared manifest](runs/horizontal-room-01/prepared.json).
- [Input summary and source hash](runs/horizontal-room-01/input-summary.json).
- [Contact sheet](runs/horizontal-room-01/contact-sheet.jpg).
- [Pairwise diagnostics and visual findings](runs/horizontal-room-01/overlap-diagnostics.json).
- Annotated matches in the same folder: `matches-1-2.jpg`, `matches-2-3.jpg`, `matches-3-4.jpg`, `matches-5-6.jpg`.

No application/library code changed during this check; the automated suites from the refactor were not rerun. Work stayed under `360-view/` on `feature/360-view-local`. No commit or push.

## Repeatable self-check tool added afterward

At the user's request to inspect the evidence themselves, added `check_horizontal.py` and `test_overlap.py`, with instructions in the README. The CLI reproduced the same counts and weak/stronger classifications in `runs/horizontal-room-01-repeat/`. It also emits a diagram for pair 4–5 (no accepted lines) and a readable `CHECK_RESULTS.txt`. Diagrams label matches as unverified; the script never claims to have visually inspected them or generated a panorama. Original proportions are retained in diagnostic thumbnails.

Actual reproduction command: `.\.venv\Scripts\python.exe check_horizontal.py data/capture-mvs8d7bp-axxmf8vj6p-r14-1793199290385.zip --output runs/horizontal-room-01-repeat`. Result: `weak_connections`, matching the earlier inspection. The CLI defines exit 3 for this status; it is not an input corruption error. The expanded Python suite passed **59/59 tests** in 6.001 seconds using `python -m unittest -q`; `python -m compileall -q check_horizontal.py test_overlap.py` passed. No phone capture, server or viewer source changed, and nothing was committed or pushed.
