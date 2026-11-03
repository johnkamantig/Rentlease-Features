# Phase 4 - supersession and current status

The previous real-photo screening is **superseded and withdrawn from project acceptance evidence** because its inputs did not belong to this independent implementation. Its imported photographs, working copies, source/order manifests, contact sheets and real-photo diagnostic/failure reports have been removed from the active project. The earlier measurements and visual observations must not be reused to evaluate this approach.

## Current acceptance status

| Phase | Status |
| --- | --- |
| 1-2 | Independent OpenCV implementation, cyclic synthetic alignment/closure tests and calibrated JPEG/JSON export are retained. Synthetic success is not real-world validation. |
| 3 | Independent Pannellum viewer, metadata checks and browser/emulated-touch tests are retained. Physical Android remains unverified. |
| 4 | Fresh real-room acceptance pending. Phase 4B evaluated 41 eligible new photographs; missing matching connections and measured calibration prevent export. See PHASE4B_RESULTS.md. |
| Prior real-photo screening | Excluded from acceptance evidence; imported data/reports removed. |
| 5 | Standalone Expo capture application not started. |

## Eligible inputs

Use only fresh smartphone photographs captured specifically for this project. The staging directory `samples/fresh-room/input/` now contains 41 fresh photographs supplied after the isolation cleanup. Phase 4B evaluates these inputs only. The example calibration still contains no usable measured values. Follow [REAL_ROOM_WORKFLOW.md](REAL_ROOM_WORKFLOW.md) for capture, measured calibration, import, audit and eventual visual review.

Real input orders must declare `capture_origin: fresh_panorama_view`. This is a provenance declaration, not automatic scene authentication. The room workflow refuses inputs outside the project, excluded directory names, and linked input paths before image/metadata reads. Unmarked real capture manifests are ineligible.

## Retained independent evidence

`tests/cyclic_scene.py` builds a seeded numerical texture and colored circles, then samples analytical camera rays. It does not load photographs. During isolation correction all 18 stored perspective frames were reproduced pixel-for-pixel, the known-good reference JPEG was reproduced byte-for-byte, and viewer fixtures were matched to the independent Phase 2 output. Proof is recorded in `output/synthetic-independence.json`.

Independent synthetic resolution/resource results under `output/phase4/resolution-trial/` are retained as desktop synthetic experiments only. They do not establish room-photo quality, phone calibration, or Android feasibility. The mathematical full-sphere reference only checks the renderer; it is not a full-sphere capture requirement.

## Cleanup and verification

Only 37 individually verified active-project files were removed: 24 imported photographs, two contact sheets and 11 JSON manifests/reports. Only their nine empty directories were pruned. No broad recursive deletion was used and no unrelated files were overwritten. Origins were verified solely from local imported manifests and hashes. The excluded implementation was not accessed during correction.

The file/hash receipt is `output/isolation-cleanup-plan.json` with status `completed_targeted_removal`. It is a deletion receipt, not a dataset or acceptance report. The final independent test rerun and complete changed-file inventory are in [ISOLATION_RESULTS.md](ISOLATION_RESULTS.md).

See [PHASE4B_RESULTS.md](PHASE4B_RESULTS.md) for the subsequent fresh-photo evaluation. No real-room success, physical-device testing, Expo development, production integration, commit, push, merge or deployment is claimed.
