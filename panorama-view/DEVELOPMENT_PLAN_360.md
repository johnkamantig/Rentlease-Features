# Full 360 degrees development gates

Current follow-up is continuous capture: Phase A video ingestion/keyframe selection is implemented and tested; the supplied real video remains incomplete. Phase B sensor assistance is a research proposal plus a diagnostic optical-flow probe. Phase C Start/Finish Expo interface is a plan only. See [CONTINUOUS_SWEEP_RESULTS.md](CONTINUOUS_SWEEP_RESULTS.md) and [CONTINUOUS_CAPTURE_PLAN.md](CONTINUOUS_CAPTURE_PLAN.md). Existing numbered-phase capture-app work remains deferred.

The only target is one complete horizontal revolution, with limited genuine vertical content. All work stays in this checkout's `panorama-view/` subtree. No frontend, Supabase, backend, GPS, excluded projects, infrastructure, commits, pushes or deployments are authorized by this prototype task.

| Phase | Gate and current state | Next action |
| --- | --- | --- |
| 1 - inspect and remove incompatible assumptions | Implemented. Original tests run; count limit, cropping, errors and active instructions replaced. | Review phase report. |
| 2 - full-circle stitching and closure | Implemented and tested on cyclic perspective geometry; JPEG plus calibrated metadata produced. This is synthetic evidence only. | Review the artifact and verification limits. |
| 3 - minimal viewer | Implemented in `viewer/`; known-good sphere then Phase 2 strip pass desktop Chromium and emulated-touch tests. | Confirm physical touchscreen/fullscreen behavior and review real imagery; see Phase 3 report. |
| 4 - actual rooms | 41 fresh photographs evaluated in Phase 4B. Strong closing overlap but missing connections and measured calibration prevent a complete accepted panorama. Earlier withdrawn screening remains excluded. | Review PHASE4B_RESULTS.md for specific weak transitions, retake guidance and required calibration. |
| 5 - standalone Expo capture | Deferred until the earlier gates pass. | Bare camera/progress/overlap/photo-count/retake/restart/process/preview/accept-retry flow; no production app changes. |
| 6 - physical Android workflow | No physical device validation. | Exercise actual capture -> local processing -> viewer, including failures and retries; measure runtime and memory. |
| 7 - on-device feasibility and handoff | Deferred. | Assess native Android OpenCV separately from Expo Go, and document optional property-media integration. |

For Phase 3 use `type: equirectangular`, `haov: 360`, measured `vaov` and `vOffset`, and vertical constraints appropriate to the viewport and zoom. Do not infer a working viewer from a JPEG or a configuration file. A full rotation and seam crossing need actual browser interaction. A flat scrolling image is insufficient.

For real capture keep lens/settings constant, the phone portrait, camera height stable, minimal translation, 40-60% overlap and one direction. End at a distinct heading overlapping the first area; this implementation rejects repeated starting images and extra revolutions. Frame count is derived from measured FOV. Sensors are guidance only.

Every phase report must identify changes, commands, tests and actual results, limitations, and next action. Never infer physical Android or real-room success from synthetic tests. See [PHASE_RESULTS.md](PHASE_RESULTS.md) and [PHASE3_RESULTS.md](PHASE3_RESULTS.md).
