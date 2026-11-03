# Phase 1-2 handoff

Current direction: continuous horizontal video ingestion is implemented in `video_ingestion.py`; sensor-assisted alignment is research and the Expo Start/Finish UI is planning only. Read [CONTINUOUS_SWEEP_RESULTS.md](CONTINUOUS_SWEEP_RESULTS.md), [VIDEO_WORKFLOW.md](VIDEO_WORKFLOW.md) and [CONTINUOUS_CAPTURE_PLAN.md](CONTINUOUS_CAPTURE_PLAN.md) before further capture work. No accepted real-video panorama or physical Android processing result exists yet.

Read [README.md](README.md), [CALIBRATION.md](CALIBRATION.md), [PHASE_RESULTS.md](PHASE_RESULTS.md), and [PHASE3_RESULTS.md](PHASE3_RESULTS.md). The active code was safely relocated to `RentLease-Features/panorama-view/`; preserve existing untracked work. Historical Phase 1-2 reports and output JSON may record the former nested absolute path; the viewer does not use that field to locate images.

`stitch.py` handles ingestion, CLI, compression and exclusive export. `stitch360.py` supplies calibration, ring feature matching and fixed-intrinsic global refinement. `closure.py` owns coverage/geometry and seam gates. `projection.py` owns periodic resampling, real masks, exposure, seams and blending. Tests include a perspective-rendered cyclic sphere and a whole-circumference ground-truth comparison.

Do not use `baseline_stitch_images()` output as verified 360 degrees media. Do not weaken closure checks just to make a room dataset pass. When a room fails, inspect pair diagnostics and calibration, then retake or make an evidence-backed algorithm change.

Phase 3 is implemented in `viewer/` and tested first with the known-good sphere, then the produced strip. Physical touchscreen interaction still needs confirmation. The next development gate is real-room validation using authentic ordered photographs and measured calibration. No Expo camera app until those gates pass. Physical Android capture and on-device processing are later work; Python/OpenCV does not execute directly in Expo Go.

Phase 4B evaluated 41 fresh user-supplied photographs; see [PHASE4B_RESULTS.md](PHASE4B_RESULTS.md). No accepted panorama exists: blank-wall gaps and missing measured calibration remain. Follow [REAL_ROOM_WORKFLOW.md](REAL_ROOM_WORKFLOW.md) for retakes/calibration. The earlier withdrawn screening stays excluded under [PHASE4_RESULTS.md](PHASE4_RESULTS.md) and AGENTS.md. Never substitute unrelated inputs or synthetic FOV values.

Keep every implementation change in this subtree. No production frontend, backend, GPS, excluded projects, Supabase, deployment, commit or push changes. All photos and generated outputs stay local and ignored by Git.
