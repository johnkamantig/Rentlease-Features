# Continuous capture: implementation boundaries and next design

Phase A is implemented in `video_ingestion.py`. Fresh video results are in [CONTINUOUS_SWEEP_RESULTS.md](CONTINUOUS_SWEEP_RESULTS.md). Keyframe selection and the existing calibrated export pass a cyclic synthetic-video test. The supplied real video remains incomplete. No Expo camera interface or sensor-assisted stitcher has been implemented.

## Phase B - practical sensor assistance, proposed and untested

### What was actually implemented

The video experiment includes a diagnostic short-range Lucas-Kanade optical-flow probe. It tracks detected corners between inspected frames and rejects inconsistent forward/backward tracks. It does not estimate camera orientation, feed the optimizer, bridge gaps, or certify angular coverage. Uniform synthetic frames yield no tracks. On the real video, many nearby frames retain tracks even when SIFT descriptors are weak, but at least one candidate interval has none. Track counts alone do not establish rigid camera rotation or accurate projection. OpenCV documents the local brightness/motion assumptions behind this method in its [optical-flow tutorial](https://docs.opencv.org/4.13.0/d4/dee/tutorial_optical_flow.html).

No synchronized gyro observations were supplied or parsed. Video presentation timestamps are not sensor/exposure timestamps. The experiment does not claim that an ordinary MP4 contains usable gyro measurements; vendor-private metadata, if present, is not used.

### Proposed measurement contract

Record these fields in a separate native-timestamped capture session, rather than inventing them during processing:

| Measurement | Required information |
| --- | --- |
| Camera frames | Frame index, presentation time, exposure timestamp where available, resolution/orientation, lens, zoom/crop/stabilization settings. |
| Gyroscope | Native monotonic sensor timestamp, x/y/z angular rates with explicit units and coordinate frame. |
| Gravity/level | Timestamped accelerometer or fused gravity/orientation, with accuracy/availability flags. |
| Synchronization | Declared clock sources, measured clock offset and uncertainty, dropped samples/frames. |
| Calibration | Camera intrinsics/distortion for that exact video mode, camera-to-IMU rotation, initial pitch/roll and bias estimate. |

Expo's [Gyroscope API](https://docs.expo.dev/versions/latest/sdk/gyroscope/) documents angular rates in rad/s and measurement time in seconds. [DeviceMotion](https://docs.expo.dev/versions/latest/sdk/devicemotion/) offers orientation/gravity-related data and rotation rates in deg/s. Those unit conventions differ and must not be mixed. These APIs are candidates for guidance; their availability is not proof of frame-accurate camera synchronization.

The [Expo Camera API](https://docs.expo.dev/versions/latest/sdk/camera/) provides asynchronous recording to a local file and recording progress. Its documented recording result/progress does not establish an exposure timestamp paired with every gyro observation. JS callback receipt time must not be substituted for sensor event time. Confirm the selected Expo SDK and native device behavior before implementation.

Android [camera exposure timestamps](https://developer.android.com/reference/android/hardware/camera2/CaptureResult#SENSOR_TIMESTAMP) and [sensor timestamps](https://developer.android.com/reference/android/hardware/SensorEvent#timestamp) have defined native timing semantics. Camera timestamp comparability depends on the device's [timestamp source](https://developer.android.com/reference/android/hardware/camera2/CameraMetadata#SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME); an UNKNOWN source cannot simply be assumed synchronized. A native capture/logger module or development build may be necessary to obtain and validate the required mapping. No such module is implemented here.

### Proposed alignment method

1. Estimate stationary gyro bias briefly before the sweep, record the raw samples and retain uncertainty. Integrate angular rates with their measured time intervals into relative rotations/quaternions. Do not derive absolute heading by assuming the recording lasted exactly one turn.
2. Map device rotation to camera coordinates using a measured camera-to-IMU transform and actual display/capture orientation. Use the gravity-referenced vertical axis for yaw progress, rather than blindly integrating a fixed device axis.
3. Interpolate rotations at calibrated frame times. Use these as match-search/RANSAC priors and initial camera orientations; use strong visual correspondences to correct drift where available.
4. Short-range optical flow may connect nearby feature-bearing frames before wide-view descriptor matching loses them. Track forward/backward consistency, spatial spread and geometric residuals. When both texture and tracks vanish, optical flow supplies no missing observation.
5. Across a short texture-poor interval, gyro propagation could supply measured relative orientation, with increasing uncertainty. It does not create wall texture, solve translation/parallax, establish image calibration or replace reliable visual anchors before/after the interval.
6. Validate the completed turn using measured motion, real source-mask coverage, strong anchor alignment, loop residuals and wrap appearance. Never normalize an arbitrary sensor trajectory to 360 degrees or force endpoint closure to claim success.

The stock current OpenCV bundle-adjustment path has no IMU residual/prior implementation. Feeding orientation initials alone is not joint visual-inertial optimization. A future pose-assisted pipeline and its acceptance policy need explicit implementation and tests; the current feature-only gates must not be weakened to let an unverified gap pass.

### Is sensor-assisted stitching necessary?

The present evidence does not prove that every room needs IMU assistance. Better texture/framing and validated optical-flow integration may improve video-only behavior. It does show that more video samples alone did not solve this room's missing visual connections. For reliable progress/level/too-fast guidance, sensor assistance is a practical next direction. For robust blank-wall stitching it is worth testing, but synchronization, drift, camera calibration and image-based verification remain unresolved. No sensor-assisted success is claimed.

## Phase C - barebones Expo interface plan only

The interaction is **tap Start, sweep, tap Finish**. No hold-to-record interaction, full-sphere targets, extra capture directions or design system is planned.

| State | Minimal screen and behavior |
| --- | --- |
| Ready | Live portrait preview, Start button, one-direction hint and phone-level indicator. Brief stationary bias/level measurement can occur in preview. |
| Capturing | Finish button, explicitly estimated 0-360 degree progress, direction arrow, level indicator and concise quality feedback. Keep recording raw timestamped observations. |
| Capture warning | Overlay a small too-fast/tilted/low-texture warning. Warn using measured motion/exposure and tracking evidence; do not make up progress if sensors are unavailable. |
| Processing | Basic status for selection, continuity checks, stitching and validation. Preserve the source video/session on failure and explain the affected interval. |
| Preview | Show Pannellum only after accepted metadata/image exist. Provide Accept and Retry. No flat image masquerading as 360 viewing. |
| Retry/error | Keep diagnostics/session provenance, explain the failure, and return to Ready for a new sweep. |

Progress reaching an estimated 360 degrees is guidance, not acceptance. Warn if the user keeps rotating past the starting scene. Do not silently truncate a second turn into a verified panorama. Rate thresholds should be derived and tested against actual calibration, exposure time and tracking quality, not treated as universal constants.

Python/OpenCV is a desktop experiment and cannot be assumed to run in Expo Go. Native Android frame processing or a separately authorized processing service remains a later architecture decision. This task adds no server or app implementation.

**Recommended direction:** preserve the simple continuous Start/Finish interaction, with automatic quality-based frame selection and measured orientation guidance. Do not finalize the Android processing method yet: the supplied video has not produced an accepted panorama. Next, obtain video-mode calibration and a synchronized sensor/video test capture, then compare video-only, validated optical-flow assistance and sensor priors on the same room/settings. If video still quality is insufficient, automatically acquired camera frames/stills could retain the same user interaction; that alternative is untested.
