# Horizontal room capture lab

Barebones standalone Expo TypeScript prototype for optional horizontal room photos. New sessions plan a **120, 150 or 180 degree turn** with adjustable **15/20/30/40 degree spacing**. Defaults: 150 degrees, 20-degree spacing (nine guide positions). Counts and angles are guidance, not verified overlap or image coverage. This app saves original photographs for later stitching; it does not generate a panorama.

The existing camera, sensors, storage, thumbnails, manual capture, retakes, pause/resume, interruption recovery, confirmed cleanup and ZIP export remain. New captures have no upper, lower, ceiling or floor stages. No main frontend, Supabase, GPS, ML, Render, authentication, paid service or new application backend.

## Windows PowerShell setup

Use Node 24.x (at least 24.3) or 22.x (at least 22.13). Validated with Node 24.17.0/npm 11.13.0. From the repository root:

```powershell
Set-Location .\360-view\capture-lab
npm.cmd ci
npm.cmd run check
npx.cmd expo install --check
npx.cmd --yes expo-doctor
npm.cmd run bundle:android
```

Use .cmd to avoid PowerShell's npm.ps1 execution-policy error; no global CLI or policy change is necessary. The lockfile pins dependencies and .npmrc keeps npm caches inside this lab. SDK 58 is retained. Compatibility checks required patch updates to expo ~58.0.20, expo-camera ~58.0.13 and expo-file-system ~58.0.12. Other direct runtime packages remain expo-sensors ~58.0.4, expo-sharing ~58.0.20, React 19.3.0, React Native 0.88.0 and safe-area-context ~5.10.1. TypeScript/tsx are development tools, not a Node backend.

## Open on Android

Use Expo Go compatible with SDK 58 and the same trusted Wi-Fi as the PC. Stop the previous Metro terminal with Ctrl+C, then:

```powershell
Set-Location C:\Users\kaman\Rentlease-Features\360-view\capture-lab
npx.cmd expo start --lan --clear
```

Scan the NEW QR in Expo Go. Verify **Test build: horizontal-1**. An export-1 or export-fix-2 label means the old bundle is open: close that project, restart Metro with --clear and rescan. Do not uninstall Expo Go or clear its app storage while photos are needed.

For port conflicts stop the old Metro instance or use `npx.cmd expo start --lan --clear --port 8082`. Allow Node through Windows Firewall on Private networks. Avoid guest Wi-Fi/client isolation and VPN routing. Get the PC Wi-Fi IPv4 with ipconfig; localhost on the phone means the phone itself. Package installation/compatibility checks need internet; photos are not automatically uploaded. Metro only delivers the development app.

## Existing saved sessions

Old full-sphere records and photos are **not converted or deleted automatically**. They open for review/export; old capture stages and retakes are disabled. A fully photographed legacy set can still be finished and exported. An incomplete legacy set remains on disk but cannot be completed in this build; retain it and use the rollback build if needed.

Preserve an exported ZIP and verify it on the PC before confirming deletion/restart. To choose new settings, use **Delete local capture data**, confirm only after preserving the old set, then choose the sweep/spacing on the home screen. **Restart this room** retains spacing/sweep (150 degrees for a legacy set). Both require native confirmation. Cancelling keeps the files. Camera-roll files are untouched. There is still one active local session, not a new room-management system.

## Capture procedure

1. For the first retest choose **120-degree sweep / 20-degree spacing**: seven suggested positions including both ends.
2. Start capture and allow Camera. No microphone or photo-library permission is required.
3. Hold the phone upright and level with the rear lens near one point. Face the left edge of the desired room view and tap **Set starting-wall reference**. Keep the default lens/zoom.
4. Capture manually, turning right slowly. Keep roughly half of the previous scene visible and compare its thumbnail. Do not walk around or aim at the ceiling/floor.
5. Choose smaller spacing or **Add an overlap photo here** when needed. An extra photo is inserted in overlap order, not appended out of sequence.
6. Pause/review as needed. After interruption/resume, face the original starting direction and set the reference again, or use manual landmark guidance. Heading/tilt are approximate.
7. Review and retake; the same target is replaced without changing order or captured count. The previous valid save and its photos are retained for recovery until later pruning.
8. Finish when all planned and added positions have saved photos. The UI says **Capture set saved — no panorama yet**. Ceiling/floor coverage is not required.

Sensor unavailability/failure leaves manual capture available; Retry sensors retries detection. Indoor magnetic interference and movement may invalidate readings. Camera failures have a retry control; check Camera permission under Android Settings. Missing files are reported and horizontal targets become incomplete. Disk/write failures retain the previous valid snapshot. Cancel/delete requires confirmation.

## Export a complete capture set (Task 03)

On review use **Save original capture ZIP to folder** with Android's picker, or **Share original capture ZIP**. Choose offline transfer such as USB, Bluetooth or local sharing. Native destinations are selected by the user; successful handoff is not proof of delivery. Verify the ZIP on the PC.

The previous Android folder-export fix is preserved: create a provider-owned destination, stream bytes and verify length/CRC rather than copying a File into a folder URI. Names are unique; failures do not silently delete originals. **Clear temporary export copies** confirms removal of cached ZIPs only, not source photos or folder copies.

ZIP entries are original-resolution JPEG bytes (no export recompression) and manifest.json. Metadata retains overlap order, dimensions, timestamps, direction/yaw, approximate sensor readings and new session fields `captureMode: "horizontal"` / `sweepDegrees`. Version 1 is retained with validated additive fields for legacy compatibility. Retake timestamp order can differ from overlap order; consumers must use manifest order. coverageValidated remains false.

Copy the ZIP into 360-view/stitching-lab/data/ and follow [horizontal preparation](../stitching-lab/README.md#horizontal-capture-preparation). Individual capture photos are not stitched spherical panoramas.

## Automated checks and physical retest

Latest capture checks: **83 tests** and TypeScript passed. See [the refactor report](../HORIZONTAL_REFACTOR.md) for exact final Expo/bundle/results. Coverage includes camera-cache provenance, filesystem/export failures, immutable-save recovery, cleanup/path restrictions, archive bytes/order and horizontal completion/legacy preservation.

All revised physical tests are **pending user confirmation**. Previous full-sphere phone tests do not certify this build. On the POCO F7 check:

| Check | Expected observation |
| --- | --- |
| Build/permission | horizontal-1; deny then allow Camera; preview/retry works |
| Plan | Sweep and spacing change counts; no upper/lower/ceiling/floor tabs |
| Guidance/capture | Reference, heading/level feedback and manual fallback; saved photos |
| Overlap | Extra shot inserted beside selected target; count and thumbnails correct |
| Retake | Same position replaced; captured count unchanged; metadata retained |
| Interruption | Background/close/reopen restores saved photos paused; reference reset |
| Completion | Horizontal targets alone finish; no generated-panorama claim |
| Legacy | Previous set review/export works without silent deletion/conversion |
| Export | Folder and sharing routes; validate ZIP/order/originals on PC |
| Cleanup | Cancelling keeps files; confirmed cleanup affects only this prototype |

The separate [Android Chrome viewer checklist](../README.md#android-chrome-retest) remains pending too.
