# Notchip Android feasibility experiment

**Experimental, not adopted. No accepted real-room 360 result or device benchmark yet.**

The latest user request authorizes this isolated Expo prototype. It does not
replace the independent Python pipeline or relax its calibration/coverage gates.

- [Device/build procedure](DEVICE_TEST.md)
- [Source review and results](RESULTS.md)
- `app/App.tsx`: plain Android preview, tap Start / Finish, estimated yaw,
  direction/speed/relative-level guidance, automatic stills and retry.
- `app/session.ts`: preserve originals, prepare <=1200-pixel-long-edge inputs,
  record capture/stitch time, invoke actual `stitchSweep`, retain all strips.
- `app/gates.ts`: fail closed on partials, gaps, closure, geometry, projection,
  input loss and the strict **9,499,999-byte** maximum. Passing these diagnostic
  prerequisites never asserts measured calibration, valid masks or seam quality.
- `app/tests/feasibility.test.mts`: 21 host tests, including published orchestration
  with a native test double. These are not native/device stitching tests.
- `package/`: untouched source from the npm 0.7.0 tarball, including MIT license.
- `published-package.json`: registry metadata, integrity and release Git revision.
- `pull_sessions.py`, `measure_android.py`: USB evidence collection, new files only.
- `prepare_android_sdk.py`, `app/scripts/build-android.ps1`: scoped build preparation.
- `prepare_ninja.py`: checksum-pinned Ninja 1.13.2 inside this SDK, preserving
  CMake's original 1.10.2 executable for the Windows long-path rebuild fix.
- `app/scripts/prepare-native.cjs`: reproducible one-line installed-module NDK
  alignment patch. Original npm source remains untouched in `package/`.

All capture sessions are local app documents. Nothing uploads automatically.
Rejected/oversized diagnostic JPEGs are retained as evidence; they are never
offered as accepted exports. Sharing a report is a user-triggered Android action.
The report can include device model, EXIF and local paths; use only test-room data.

The current prototype deliberately has **no Pannellum acceptance adapter**. The
package manifest does not establish the existing viewer's calibrated acceptance
contract. Making one by filling status flags or guessing vaov/vOffset would be
false validation. Spherical geometry is analyzed, cylindrical fallback rejected
for direct viewing, and fitted angular extents are reported for investigation.

Run from `app/`:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run typecheck
npx.cmd expo install --check
npm.cmd run bundle:android
```

Use a native local build, not Expo Go. The package is pinned to 0.7.0 and the
lockfile resolves Expo 57.0.31 / React Native 0.86.3 / React 19.2.3. SDK 58 is
currently newer, but is not the package's documented tested environment. No
production app/runtime was inspected or upgraded.
