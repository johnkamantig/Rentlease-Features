# Project isolation correction - 2026-10-30

Historical checkpoint: this report describes the state immediately after cleanup. Fresh photographs were subsequently supplied and evaluated in [Phase 4B](PHASE4B_RESULTS.md); the former empty staging directory now contains that new set. The isolation restrictions and withdrawn-evidence status remain in force.

**The previous real-photo screening is superseded, withdrawn and excluded from current acceptance evidence.** Imported materials have been removed. This independent implementation has not been validated with eligible real-room photographs. Fresh real-room validation is pending; Expo capture development has not started.

All corrective inspection, verification and deletion stayed within `panorama-view/`. No excluded source directory was accessed, inspected, modified or deleted during this correction. No unrelated directories or production components were modified. No commit, push, merge or deployment occurred.

## Targeted data removal

Verified origins from the active project's stored capture/order manifests, copied-manifest hashes and imported-image hashes. No excluded originals were opened to perform this verification. A plan enumerated every exact target and refused unexpected files.

Removed **37 individually verified files**, totalling **48,627,774 bytes**:

- 24 imported JPEG photographs.
- Two derived contact sheets.
- Eleven JSON capture/source/order manifests and real-photo audit/failure reports.

Removed local data locations:

```text
samples/phase4-archived-partial/
samples/phase4-archived-horizontal18/
output/phase4/partial-audit/
output/phase4/horizontal18-audit/
output/phase4/horizontal18-audit-1600/
output/phase4/partial-stitch-attempt/
output/phase4/horizontal18-stitch-attempt/
```

Also removed the four associated order/source JSON files directly under `output/phase4/`. Only the nine now-empty capture/output directories, including the two `originals/` subdirectories, were pruned. No broad recursive deletion was used. Each absolute target was checked within the active project, checked for reparse points and matched against its planned SHA-256 before removal.

The deletion receipt `output/isolation-cleanup-plan.json` lists the exact active-project filenames/hashes and records `completed_targeted_removal`. This receipt contains no photographs or original source-manifest contents and is not an input dataset or acceptance report. Final verification confirms every listed file/directory is absent.

An initial PowerShell preflight encountered an unsupported parameter combination and was interrupted before removal. The corrected bounded preflight reverified all targets and completed removal. No files were deleted by the failed preflight.

## Independent functionality retained

Retained the existing OpenCV feature matching, fixed-intrinsic global alignment, independent turn/closure validation, periodic projection/blending, image validation/orientation handling, compression, JPEG/JSON export, memory guards and error handling. Retained Pannellum and its independent metadata/browser tests. No stitching thresholds or projection geometry were weakened.

Synthetic provenance was checked directly:

- `tests/cyclic_scene.py` constructs a NumPy texture with seed 730 and OpenCV circles, then samples perspective rays analytically. It contains no photograph reads.
- All 18 stored synthetic perspective frames reproduced pixel-for-pixel.
- The known-good mathematical reference JPEG reproduced byte-for-byte.
- Viewer assets matched those independent Phase 2 artifacts and their hashes.
- Proof is recorded in `output/synthetic-independence.json`.

Independent synthetic outputs and resolution/resource measurements remain available, including `output/phase4/resolution-trial/`. They are mathematical/desktop evidence only. The full-sphere mathematical reference is solely a renderer fixture; it introduces no ceiling/floor or multi-row capture requirement.

## Source and documentation changes

| File | Change |
| --- | --- |
| `AGENTS.md` | Added permanent project isolation and fresh-input instructions for future work. |
| `room_validation.py` | Added checks rejecting out-of-project, excluded-name and linked input paths before reads; requires an explicit fresh-capture declaration and eligibility marker for real-room imports/manifests. |
| `tests/benchmark_resolution.py` | Checks source scope before directory enumeration. |
| `tests/test_room_validation.py` | Added rejection/provenance regressions using generated test images and nonexistent sentinel paths only; replaced an unnecessary direction-based retake example. |
| `README.md`, `CALIBRATION.md`, `CODEX_STAGE1_HANDOFF.md`, `DEVELOPMENT_PLAN_360.md` | Removed obsolete evidence/references and set Phase 4 to fresh validation pending. |
| `REAL_ROOM_WORKFLOW.md` | Replaced with fresh-only capture, staging, measured calibration, import and acceptance instructions. |
| `PHASE4_RESULTS.md` | Replaced the prior screening report with explicit supersession, eligibility and corrected status. Old real-photo metrics are no longer acceptance evidence. |
| `PHASE_RESULTS.md`, `PHASE3_RESULTS.md` | Removed irrelevant excluded-project status references while retaining independent synthetic/browser results. |
| `samples/fresh-room/order.example.json`, `calibration.example.json` | Empty order/invalid-until-measured calibration templates outside the empty photo staging directory. |
| `ISOLATION_RESULTS.md` | This cleanup and validation report. |

The input checks help prevent accidental reuse, but a provenance declaration cannot authenticate arbitrary user-supplied image contents. Only fresh images specifically captured for this approach are eligible by policy. There is no automatic recovery of phone calibration and no generated property imagery.

## Automated validation

| Check | Result |
| --- | --- |
| Final independent Python suite | **65 passed, 0 failed in 44.50 seconds**. |
| Viewer unit/metadata suite | **27 passed, 0 failed**. |
| Chromium browser suite | **8 passed, 0 failed/skipped/flaky in 17.5 seconds**, using loopback port 4174 and software WebGL. |
| Synthetic provenance | 18 frame pixel comparisons and reference JPEG byte comparison passed. |
| Cleanup verification | All 37 files and nine empty directories absent; remaining data manifests contain no excluded input references. |
| Fresh staging directory | `samples/fresh-room/input/` exists and is empty. |

The browser report is preserved at `output/isolation-validation/browser-results.json`. Python compilation and CLI help checks passed. Browser tests use the independent reference sphere and synthetic strip; they make no real-room or physical-device claim. The owned test server is stopped after the run.

Commands from `panorama-view/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_room_validation.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q room_validation.py tests/test_room_validation.py tests/benchmark_resolution.py
.\.venv\Scripts\python.exe room_validation.py --help
```

Viewer commands from `panorama-view/viewer/`:

```powershell
$env:PORT = '4174'
npm.cmd test
npm.cmd run test:browser
```

Inspection used active-project-only `rg`, `Get-Content`, `Get-ChildItem` and Python manifest/hash checks. Cleanup used exact PowerShell `Remove-Item -LiteralPath` calls after full preflight. No command enumerated or loaded excluded originals. No real-photo experiment was run during correction.

## Remaining dependencies and next step

No runtime code, data, calibration or acceptance dependency on excluded material remains. Its names remain only in prohibition rules, negative-input tests and the local deletion receipt. These are isolation controls/history, not processing inputs. Standard OpenCV/Pillow/NumPy and Pannellum dependencies remain.

Current status:

- Phases 1-3: independent implementation and automated synthetic/browser validation retained.
- Phase 4: fresh real-room validation pending; prior screening excluded.
- Phase 5: standalone Expo capture application not started.

Next: capture a new portrait sequence around one horizontal revolution with approximately 40-60% neighboring overlap, fixed height/lens/settings and closing overlap. Stage originals in `samples/fresh-room/input/`, record actual order and fresh provenance, and obtain measured calibration for those same settings. Follow [REAL_ROOM_WORKFLOW.md](REAL_ROOM_WORKFLOW.md). No eligible real photographs or smartphone calibration values have been supplied yet.
