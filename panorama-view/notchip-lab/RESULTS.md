# Notchip feasibility review - 2026-10-30

**Recommendation: retain as a capture/native-packaging experiment; do not adopt
it as RentLease's verified 360 stitching replacement yet.** Guided automatic
stills may reduce capture mistakes and integration effort. Real-room reliability,
complete-circle output, image quality and device memory/stability remain unproven.
No physical Android is connected; no native room capture or successful real-room
stitch is claimed. See DEVICE_TEST.md for the required next evidence.

## Source and compatibility

The registry's current latest is **0.7.0**, published 2026-09-18. Its npm Git
revision is `bd61587ad68ba87de49099329a02e4b3e7176b28`, matching the GitHub HEAD
queried during this review. The tarball is retained with SHA-256
`090069e2548adfcc32fc5d76b6c5a467505db467c7bce36b729a5f224c6f594c`;
`published-package.json` records registry integrity/release metadata. The package's
actual TS, Kotlin, C++, Gradle, CMake, tests, README and license were inspected,
rather than relying on search-engine snippets (one raw-source web cache was stale).

The module's own code is MIT, copyright 2026 notchip; the full LICENSE is retained.
OpenCV and bundled third-party native dependencies retain their own license and
notice requirements; MIT on the wrapper does not replace those notices.

The README advertises SDK 56+ / RN 0.85+, tested against SDK 57 / RN 0.86,
Android minSdk 24. Core peer ranges for Expo/RN are broad; they are not proof of
compatibility with every version. The active panorama project had a Node viewer
and Python pipeline, no Expo runtime. No production frontend/runtime was inspected
or upgraded. The separate app resolves Expo **57.0.31**, React Native **0.86.3**,
React **19.2.3**, with matching camera/sensors/filesystem/manipulator/sharing/device
packages. SDK 58.0.21 was current at query time; it was deliberately not selected
for this test. `npm ci` and the lockfile reproduce the chosen SDK 57 environment.

This is custom native code, unavailable in Expo Go. Android statically links
OpenCV **4.13.0** via one JNI library, Gradle downloading/checking the official SDK.
No manually integrated Python runtime or remote stitching service is required.
Java 17, API 36, NDK 27.1.12297006, build-tools 36.0.0 and CMake are needed for the
generated project. Native compilation, linking and runtime loading must each be
verified; a passing TypeScript build is insufficient.

The original module selected AGP's default NDK 27.0 instead of the app's 27.1,
causing native configuration failure with the prepared app SDK. A reproducible
one-line `android.ndkVersion = rootProject.ext.ndkVersion` declaration is added
to the installed copy by `app/scripts/prepare-native.cjs` at npm postinstall.
The retained npm snapshot remains untouched; a test verifies that this is the
only Gradle-file change. No C++/Kotlin or stitch algorithm is patched. The
package's Gradle version string still says 0.5.0, despite npm/source being 0.7.0.
The legacy Expo Gradle helper does exist under expo-modules-core/android; an
initial path-based concern was corrected and no registration rewrite is retained.

## Actual algorithm, sensors and failure modes

`src/capture/useGuidedSweep.ts` integrates gravity-projected DeviceMotion angular
rate on sensor timestamps. Android's alpha/beta/gamma axis mapping and degrees/sec
agree with the installed SDK 57 native sensor source. It gates 15-degree still
targets on speed and relative tilt, relatches direction once, and aborts when
backgrounded. Sensor timestamp fallback to configured interval remains possible.
The initial gravity reference is relative: it does not establish a measured
camera optical-axis pitch or camera-to-IMU transform. Trigger/resolve times are
not actual exposure timestamps; the last in-flight shutter can race Finish.
The prototype disables Finish during HOLD and asks the tester to wait for the
final count, but this is not an exposure-synchronization fix.

**Sensor data do not enter native geometric alignment.** Kotlin/JNI receive image
paths and stitch options, not gyro rotations, EXIF focal priors or camera K.
Yaw affects the TS wrap-span threshold and diagnostic dropped-photo ranges.
Neighbor masks use input indices, not sensor-constrained homographies or a
visual-inertial optimizer. `fitGyroToPano` is a post-hoc agreement fit, not fusion.
These are capture guidance and yaw-tagged diagnostics, not sensor-assisted bundle
adjustment across blank walls.

The native implementation calls high-level `cv::Stitcher::PANORAMA`; no feature
finder override is installed. OpenCV 4.13's default is ORB, homography estimation,
BundleAdjusterRay and horizontal wave correction. It can still lose weakly
connected images or fail camera adjustment. It contains no mechanism to recover
unobserved wall details, calibrated priors across a textureless interval, or
translation/parallax correction.

Actual `stitchSweep` behavior:

- Defaults to **cylindrical**, not equirectangular; natural aspect (`autoResize:false`).
- At yaw span >=330 degrees it appends the first two input photographs and enables
  wrap matching. `wrapClosed` means this operation was triggered, not proven closure.
- A failed spherical attempt falls back once to cylindrical; the experiment records
  and rejects that fallback for direct Pannellum compatibility.
- Missing primary inputs can be stitched as a second strip. Its gaps describe
  photographs used **nowhere**, so two disconnected strips can report **no gaps**.
- Geometry `selfCheck` compares replayed bounding rectangle with composite size.
  It does not establish pixel validity, alignment quality or measured intrinsics.
- Coverage unions approximate yaw +/- half-HFOV camera intervals. It is not a
  per-row/per-pixel source mask, especially with pitch/roll. Its canvas span is
  capped at 360; our diagnostics separately compute the uncapped canvas angle.
- Duplicate-pose closure compares re-appended copies of the same source images.
  A small value alone is not an independent final-photo/first-photo loop residual.

## Implemented experiment and acceptance boundary

The app implements tap Start/Finish, live back-camera portrait preview, estimated
yaw, speed/direction/relative-level guidance and bounded auto-captured stills.
It retains source JPEGs in per-run app documents, prepares <=1200-long-edge files
and caps native aggregate inputs including wrap duplicates at 36 million pixels.
Up to 26 photographs allow the 360-degree endpoint without the package's default
24-shot auto-stop at roughly 345 degrees. This cap does not certify angular coverage.
No microphone, barcode capture, full-sphere rows, production styling or service is used.

It calls the installed `stitchSweep` with spherical warp, natural aspect,
neighbor range 2, explicit wrap, 4096 output width, JPEG quality 92 and confidence
0.7. It saves originals, prepared inputs, all strips, the full returned manifest,
capture timing, stitching timing and failure diagnostics. A run receipt is saved
before native stitching so an interrupted/crashed stitch remains identifiable. Process
peak memory is explicitly null until measured; total device RAM is separately named.
Short sweeps and background aborts preserve their completed photographs before
rejection, covered by two controller tests. A hard process kill during capture,
before Finish/abort handling, can still lose the in-memory pose record; camera
cache files alone are not a durable timestamp/orientation journal. That remains
a production-readiness limitation, not a successful recovery claim.

Rejection prerequisites cover multiple strips, lost primary inputs, gaps, missing
or bad geometry, incomplete fitted angular coverage, bad duplicate-pose diagnostics,
direction reversals, implausible sweep spans, cylindrical fallback and bytes
>=9,500,000. Oversized rejected diagnostics are retained as evidence, never an
accepted export. No automatic recompression masks a failed quality/completeness test.

**Every native result remains unvalidated for final 360 export.** The module does
not supply measured calibration, independent raw-turn/closing-edge proof, valid
source masks or encoded-JPEG seam/overlap acceptance. The existing Python checks
and viewer metadata contract remain untouched. Setting `accepted360:false` and
`pannellumReady:false` is intentional, not an assertion that all future module
captures will fail; it prevents missing evidence from being silently treated as a pass.

## Pannellum compatibility

A native **spherical** rotational warp is theoretically equirectangular: horizontal
pixel distance is azimuth and vertical pixel distance is polar angle. With its
actual `warpScale`, origin and output affine, the experiment computes:

```
haov = width / sx / warpScale * 180/pi
vaov = height / sy / warpScale * 180/pi
top = 90 - ((-ty)/sy + origin.y) / warpScale * 180/pi
vOffset = top - vaov/2
```

These describe the **fitted** canvas, not measured phone calibration or verified
valid coverage. No haov=360, vaov or zero pitch is invented. Native full bounding
rectangles may contain unphotographed/black corners or a discontinuous wrap.
The module does not export a valid-mask crop or periodic seam treatment equivalent
to the existing renderer. Its legacy `autoResize:true` merely stretches output to
2:1; it neither makes a strip complete nor repairs projection. We explicitly disable it.

Cylindrical vertical coordinates are tangent of elevation, so feeding cylindrical
output directly to Pannellum's equirectangular renderer is incorrect. Reprojection
and valid masks would be needed. Even spherical output requires independent
coverage/crop/seam/calibration validation before a truthful viewer sidecar can be
generated. The package manifest is not compatible with the current metadata schema;
an automated test verifies that it is rejected. **No module-produced real panorama
has been validated in Pannellum.** Existing independent synthetic/reference browser
tests pass; they are regression evidence, not module/device success.

## Measured results and comparison

| Evidence | Observed result |
| --- | --- |
| Android arm64 debug native build | PASS; successful attempt 3m54s (191 tasks, 163 executed) |
| Short-path repeat builds | PASS, 2m36s then 1m54s; byte-identical APKs |
| APK | 69,578,193 bytes; valid v2 debug signature; minSdk 24 / targetSdk 36 |
| Packaged native library | libpanostitcher.so present for arm64-v8a, ELF LOAD alignment 16,384 bytes |
| Module native captures on physical Android | 0; no device connected |
| Module real photographs stitched on Android | Not measured |
| Module full-turn closure / black areas / quality | Not established |
| Module capture/stitch duration / output resolution / bytes | Not measured |
| Module peak memory / thermal behavior / stability | Not measured |
| Host feasibility tests | 21 pass (actual TS orchestration uses a substituted native bridge) |
| TypeScript, Expo dependency check, Android JS export | Pass; bundle includes the capture/native API imports |
| Existing Python regression suite | 82 pass, 89.58 seconds |
| Existing viewer unit / browser suites | 27 / 8 pass; browser suite 18.9 seconds |

Verified artifact: `artifacts/rentlease-sweep-lab-debug.apk`, SHA-256
`972989dcd5a6399d86fa3b2ef2cc9625271e87fb0790d30bef8239ae9d77b6a4`.
The APK contains 18 arm64 native libraries; no other ABI is packaged. Native
OpenCV C++ compilation/linking and Kotlin compilation succeeded after NDK
alignment. APK signature verification and aapt manifest inspection pass. The
debug APK loads JavaScript from Metro, so follow DEVICE_TEST.md; an APK build
does not prove runtime native loading or camera behavior. `validation-summary.json`
records build/host evidence separately from null/unperformed device measurements.
The panorama export byte limit applies to panorama JPEGs, not this APK.

The initial successful build is logged in `app/native-build-ready.log`. The
documented `npm.cmd run android` build passed in 1m54s; its preserved artifact is
`artifacts/rentlease-sweep-lab-debug-20261030-202519.apk` with SHA-256
`5aa62bc039effda72129c0067f537841a61cc2cda585b18344d33a6ecf91cd4c`, identical
to the preceding short-path build. The initial APK is retained separately.
The final command was repeated after normalizing native warning output for
PowerShell: `app/native-build-final-exit.log` records a successful 1m45s build,
and the wrapper's separately checked exit code was 0 (validation-summary.json),
with the same APK hash. The temporary drive was
removed and local.properties restored to the real isolated SDK path.
Earlier logs
retain the Java provisioning, NDK mismatch, missing secondary Build Tools and
Windows PowerShell stderr-handling failures. These were resolved locally; no
native module configuration blocker remained at that point. A subsequent
incremental-build check exposed Ninja 1.10.2's Windows 260-character path limit
on cached React Native headers. `prepare_ninja.py` installs checksum-pinned
Ninja 1.13.2 into the isolated SDK only and retains the original executable.
Windows long-path registry policy is disabled on this machine; the Ninja upgrade
alone did not fix the failure. The build script therefore uses a temporary unused
drive mapped only to panorama-view, removes it afterward, and restores the real
SDK path in local.properties. No files move or existing drives get replaced.
Kotlin incremental caching is disabled for this build wrapper to avoid cached
C:/R: root conflicts; the final documented run has no compiler fallback error.
No registry change was made. The isolated SDK contains
both Build Tools 35.0.0 (required by an Expo module) and 36.0.0. Initial local
SDK/tool setup and earlier failed attempts are not included in the 3m54s duration.

The online npm audit reports 8 findings (5 low, 3 high) in the selected Expo
dependency tree; see app/dependency-audit.json. No forced SDK downgrade/major
upgrade was applied to hide them. An offline npm lock operation reported zero
because it could not refresh advisories; that output is not the audit result.
The source-orchestration tests require normal Windows process/filesystem access:
the restricted agent sandbox prevented esbuild's ancestor-directory resolution,
so the passing run used an approved escalation. This is a tooling limitation,
not a native stitching measurement.

An early Gradle attempt against the pre-existing user SDK created installer
staging at `C:\Users\kaman\AppData\Local\Android\Sdk\ndk\27.1.12297006\.installer`.
That attempt was stopped; no cleanup or further modification of that external
SDK was performed. Subsequent SDK preparation/build scripts explicitly use
`notchip-lab/android-sdk/` with project-local Android/Gradle settings. No source
outside panorama-view, production component or excluded image dataset was changed.

The custom approach's existing fresh-photo evaluation used 41 photographs: 12
weak adjacent links and no accepted panorama; its baseline retained only 15/41.
The separate fresh video evaluated 2,458 decoded frames, inspected 163, selected
30, with 11 discontinuity intervals and 15 weak selected-ring links, no accepted
panorama. See ../PHASE4B_RESULTS.md and ../CONTINUOUS_SWEEP_RESULTS.md. Those are
previous active-project measurements, not module benchmarks or a controlled
same-input comparison. No older/excluded dataset was accessed for this task.

Compared with the custom calibrated SIFT/fixed-K/periodic-render path, Notchip
offers native packaging, capture guidance and structured diagnostics, but relies
on feature-only fitted high-level OpenCV geometry. More regular overlap may help;
it cannot be assumed to solve feature starvation. The same saved new sweep must
be tested in both pipelines before claiming improvement. Memory may still be high:
native code decodes all selected photographs before stitching, then allocates
warps/blenders; reducing outputWidth only limits the final JPEG, not input decoding.
Our input resize reduces this risk but does not establish a measured peak cap.
Camera capture and the image-manipulator resize can still decode a full original
still before downscaling; the native aggregate budget does not bound those phases.

## Remaining work and recommendation

Native build verification is complete. Execute DEVICE_TEST.md on an
actual arm64 Android. Measure at least three sweeps per direction in textured and
blank-wall rooms, all failures included, and ten consecutive runs for stability.
Capture the same input data for the existing calibrated comparison. Establish
source masks, independently verified closure and truthful calibrated viewer
metadata before allowing a Pannellum panorama or accepted export.

Adopt the **Start/Finish interaction** as the preferred experiment direction.
Treat this module as a possible guided-capture/OpenCV packaging shortcut, not a
proven replacement for the acceptance pipeline. Sensor-constrained geometry may
still be needed for blank walls, but necessity and benefit are not yet measured.

## Files and commands

All implementation changes are inside panorama-view: new `notchip-lab/` source,
tests, pinned dependencies/lockfile, upstream source snapshot, local SDK/build
helpers, evidence collectors, APK and review/device documentation; root README,
AGENTS and .gitignore were updated for the isolated exception and generated files.
Existing Python/video sources, camera calibration rules, source photos and
Pannellum implementation/tests were preserved. The external SDK staging exception
is explicitly recorded above. Branch remains `feature/panoramic-room-view`;
root remains `C:/Users/kaman/Rentlease-Features`; no nested relocation was needed.
No commit, staging, push, merge, deployment or production change was performed.

Principal commands executed (from the appropriate project/lab/app directory):

```
git branch --show-current
git rev-parse --show-toplevel
git status --short -- .
npm.cmd view @notchip/expo-panoramic-stitcher@0.7.0 --json
git ls-remote https://github.com/notchip/expo-panoramic-stitcher.git HEAD
npm.cmd pack @notchip/expo-panoramic-stitcher
npm.cmd pack expo-template-blank-typescript@57.0.33
npm.cmd install --save-exact @notchip/expo-panoramic-stitcher@0.7.0
npx.cmd expo install expo-camera expo-sensors expo-file-system expo-image-manipulator expo-sharing expo-device
npx.cmd expo prebuild --platform android --no-install
python prepare_android_sdk.py
scripts/build-android.ps1
npm.cmd run android                  # final verified Windows wrapper
npm.cmd test
npm.cmd run typecheck
npm.cmd run bundle:android
npx.cmd expo install --check
npm.cmd audit --omit=dev --json
apksigner.bat verify --verbose artifacts/rentlease-sweep-lab-debug.apk
aapt.exe dump badging artifacts/rentlease-sweep-lab-debug.apk
python -m pytest -q
npm.cmd test                         # preserved viewer directory
npm.cmd run test:browser             # preserved viewer, free PORT=4174
adb devices                         # empty device list
```

Python commands used the existing active-project venv; build uses the local
Java 17 and isolated SDK/cache paths. Additional read-only source inspection,
hash, TypeScript/Python syntax and artifact-structure checks were performed.

## Primary references

- [Package repository and API documentation](https://github.com/notchip/expo-panoramic-stitcher)
- [Exact reviewed revision](https://github.com/notchip/expo-panoramic-stitcher/tree/bd61587ad68ba87de49099329a02e4b3e7176b28)
- [npm registry release](https://registry.npmjs.org/@notchip%2fexpo-panoramic-stitcher/0.7.0)
- [OpenCV 4.13 high-level stitcher defaults](https://github.com/opencv/opencv/blob/4.13.0/modules/stitching/src/stitcher.cpp)
- [Expo custom native code/build requirements](https://docs.expo.dev/workflow/customizing/)
- [Android NDK/CMake installation and automatic download behavior](https://developer.android.com/studio/projects/install-ndk)
- [Ninja Windows long-path support introduced in 1.12](https://github.com/ninja-build/ninja/releases/tag/v1.12.0)
- [Pinned Ninja 1.13.2 official release](https://github.com/ninja-build/ninja/releases/tag/v1.13.2)
