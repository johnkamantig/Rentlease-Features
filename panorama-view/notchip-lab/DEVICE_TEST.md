# Build and physical Android test procedure

Run only from this experiment. Do not use Expo Go. No EAS account, paid build,
server, production app or deployment is involved. The build status and remaining
blockers from this session are recorded in [RESULTS.md](RESULTS.md).

**An arm64 debug APK has already been built and signature-verified:**
`artifacts/rentlease-sweep-lab-debug.apk` (69,578,193 bytes). From `app/`, you may
install this existing artifact with
`adb install -r ..\artifacts\rentlease-sweep-lab-debug.apk`, then reverse port 8081
and start Metro as below. A connected phone is still required to verify runtime.
Rebuilding is optional unless source/native configuration has changed.

## Local build

Prerequisites: Node 24, Python from the existing project venv, Java 17 JDK,
several GB of disk space, and internet access for Gradle/Maven/OpenCV downloads.
The prepared `jdk17/` is local Temurin 17.0.20.1 extracted from Gradle's downloaded
distribution; otherwise set JAVA_HOME to your own JDK 17. Java 8 cannot build it.

```powershell
cd C:\Users\kaman\Rentlease-Features\panorama-view\notchip-lab
..\.venv\Scripts\python.exe prepare_android_sdk.py
cd app
npm.cmd ci
npm.cmd test
npm.cmd run typecheck
npx.cmd expo install --check
npm.cmd run bundle:android
npm.cmd run android
```

Read/accept Android SDK license prompts if preparation requests them. The script
uses the official repository and verifies its command-line-tools checksum. SDK
packages: platform-tools, API 36, build-tools 35.0.0 and 36.0.0, NDK 27.1.12297006 and CMake
3.22.1. SDK, Android user settings, Gradle and OpenCV caches stay in this lab.
The first native build downloads the package's checksum-pinned OpenCV 4.13 SDK
(318,235,406-byte ZIP). A successful JavaScript bundle is not an APK build.

SDK preparation also updates **only its own** CMake Ninja executable to pinned
1.13.2 (official release SHA-256 checked), preserving `ninja-1.10.2.exe`.
The bundled 1.10.2 fails on >260-character cached RN header paths on repeat builds.
No global long-path registry setting or system SDK is modified for this fix.
If using the already prepared SDK, `python prepare_ninja.py` is idempotent.

On this Windows checkout the build script additionally creates a temporary unused
drive R: (or S:-V: if occupied) pointing only to panorama-view, invokes the build
through that short path, and removes the mapping in `finally`. No files move and
no existing drive is replaced. This is needed with Windows long-path policy off;
upgrading Ninja alone did not remove the repeat-build failure here. Use the build
script for native rebuilds rather than calling Gradle from the long absolute path.

Expected debug APK after a successful native build:
`app/android/app/build/outputs/apk/debug/app-debug.apk` (arm64-v8a only).
This is a debuggable test app with the template debug key; never publish it.
For a self-contained local JS bundle, `build-android.ps1 -Release` builds a local
release variant with the same test signing configuration (`npm.cmd run android -- -Release`). This is not a deployment
or production signing setup. Debug is preferred for `run-as` evidence extraction.

Connect an arm64 Android 7+ phone, enable developer options/USB debugging, and
approve this computer on the phone. From `app/`:

```powershell
adb devices
adb install -r .\android\app\build\outputs\apk\debug\app-debug.apk
adb reverse tcp:8081 tcp:8081
npm.cmd start
```

Keep Metro running; launch **RentLease Sweep Lab** on the phone. Its application
ID is `com.rentlease.notchiplab`. Camera/motion permissions are requested. Do not
install over another app with that ID if it contains evidence you need; first use
the pull script. There is no automatic session deletion or upload.

## Capture matrix and measurements

1. Begin in a textured, evenly lit room. Portrait, back main camera, zoom zero,
   start upright/level. Tap Start, hold still for arming, rotate one direction
   about the camera optical center, keeping the same height. Stills fire near
   15-degree targets when motion/tilt gates permit. Follow HOLD/SLOW DOWN/GO BACK.
   This is guided automatic still capture with brief pauses, not continuous video.
2. Return to the starting scene after one turn. At roughly 360 degrees, wait for
   the final photo count to update, then tap Finish. Finish is disabled during
   HOLD; no long press is required. The safety cap is 26 shots, not a completeness
   certificate. Retry if overshooting produces an extra-turn capture or if the
   app is backgrounded. Retain the failed session.
3. Repeat in the actual texture-poor indoor room, both rotation directions, at
   least three sweeps each. Also test a partial 180/270-degree sweep, a skipped
   wall sector, deliberate reversal, excess tilt, too-fast movement, camera
   permission denial and background interruption. No partial result may become
   an accepted export. Test the unreadable-image error button and record its text.
4. Run at least ten consecutive captures/stitches, watching for OOM, ANR, crashes,
   sustained heating, camera freeze, sensor stalls, storage growth and retry
   failure. Record model, Android version, available RAM, lighting, direction,
   duration and any manual pauses. The app's total device RAM is not process use.
5. For each run retain report.json, originals, processed inputs, every diagnostic
   strip, used indices, gap/coverage intervals, actual projection, fallback,
   duplicate-pose closure and fitted angles. Record actual quality/resolution/bytes
   and measured captureMs/stitchMs/totalProcessingMs. A thrown stitch error is a
   failed run. Do not selectively count only attractive strips.

From `notchip-lab/`, in another terminal, sample memory while testing:

```powershell
..\.venv\Scripts\python.exe measure_android.py artifacts\room-a-memory.jsonl
```

Ctrl+C stops sampling. Report the maximum **sampled process PSS**, its one-second
sampling interval and device. It is not a true peak or equivalent to desktop RSS.
Use Android Studio profiling if precise native allocation/peak behavior is needed.
Save crash evidence with `adb logcat -d -s AndroidRuntime`; do not clear logs first.

After a run, with the debug app still installed:

```powershell
..\.venv\Scripts\python.exe pull_sessions.py artifacts\device-run-01
```

The helper uses a binary-safe adb subprocess and rejects traversal/links. It
copies all `files/sweeps/` into a **new** lab artifacts directory, without deleting
device files. Do not use PowerShell 5 text redirection for binary adb output.
Uninstalling the app erases its local evidence, so pull before uninstalling.

## Comparison and viewer acceptance

Compare the module and existing Python pipeline on the **same saved input JPEGs**,
same resolution budget and actual measured camera calibration. Use the capture
report's photo array order, not arbitrary directory enumeration. Import a new
capture with the existing `room_validation.py import` fresh-image specification;
audit its full ring and run the existing calibrated stitch command. See
`../REAL_ROOM_WORKFLOW.md` and `../CALIBRATION.md`. Do not substitute EXIF 35-mm
equivalence or fitted OpenCV focal length for measured lens/crop calibration.
Record custom-pipeline rejection as well as module rejection; avoid comparing
device timings with desktop timings as if hardware were identical.

For a module output, first establish a single full-turn spherical/equirectangular
canvas without stretching, all sources retained, no footprint holes, independently
verified real closing-image alignment, raw turn, actual source-mask completeness,
valid full-width vertical rows, calibrated vertical extent/reference and JPEG seam
quality. The current module does not expose all evidence needed for that. Its
manifest must currently fail the preserved viewer's metadata validation.

Once an independently validated image and truthful existing-schema sidecar exist,
start the preserved viewer from `../viewer` with `node serve.mjs` on a free port
and load the matching JPEG/JSON. Verify repeated left/right full revolutions,
0/360 seam at several pitches, vertical bounds, corners/door alignment, no black
bands, no lost wall sectors, no vertical stretching, mouse/touch drag and physical
pinch zoom. Browser-emulated touch regressions do not certify physical Android
behavior. Do not create a sidecar by merely copying status flags from a synthetic
fixture. Until these checks pass there is no accepted 360 result to view.

For physical Android viewer regression tests without exposing the loopback server
to the network, use a free port (for example `$env:PORT='4174'; node serve.mjs`
from viewer/), then `adb reverse tcp:4174 tcp:4174` and open
`http://127.0.0.1:4174/` in Android Chrome. Start with the bundled independent
reference and synthetic fixtures. Reverse the actual free port you selected;
do not terminate an unrelated server. These tests certify interaction on those
fixtures only, not unvalidated module outputs.
