/**
 * Pure-TS interpretation of the stitch geometry native reports
 * (`StitchGeometry`, parsed from the raw `geometryJson`). No native calls —
 * everything here is plain math over OpenCV's warp model, so it runs in
 * jest, on web and on saved results alike. Native deliberately reports only
 * the raw camera model (K, R, warpScale, ROIs); angles are derived HERE so
 * the coordinate conventions live in one place.
 *
 * Conventions (OpenCV's, verified against `stitching/detail/warpers_inl.hpp`):
 *  - Camera frame: x right, y DOWN, z forward (optical axis). `R` is
 *    camera-to-world, row-major; a pixel's world ray is
 *    `p = R · K⁻¹ · (x, y, 1)`.
 *  - Global warped coords `(u, v)`, pixels at compose scale:
 *      u = warpScale · atan2(p.x, p.z)                (both projections)
 *      v = warpScale · (π − acos(p.y / |p|))          (spherical)
 *      v = warpScale · p.y / hypot(p.x, p.z)          (cylindrical)
 *    so azimuth is linear in `u` and increases turning RIGHT; the horizon is
 *    `v = warpScale·π/2` (spherical; top pole at v = 0) or `v = 0`
 *    (cylindrical; `v = −warpScale·tan(elevation)`).
 *  - Composite pixel = global − origin; output pixel = `output` affine of
 *    that (`X_out = sx·X + tx`).
 *  - `affine` (warpMode 'plane') composites have no angles: the angle
 *    helpers return `null` for them; `imagePointToPano` still works.
 */
import type { AzimuthInterval, CameraAngles, GyroPanoFit, PanoAngles, PanoPoint, StitchCamera, StitchGeometry, SweepCoverage, SweepStripGeometry } from "./ExpoPanoramicStitcher.types";
/** Wrap an angle in degrees to (−180, 180]. */
export declare function wrapDeg(a: number): number;
/**
 * Parse native's compact `geometryJson` into a validated {@link StitchGeometry}.
 * Returns `null` (never throws) for an empty/missing string, malformed JSON,
 * a payload version other than 1, an unknown projection, or any non-finite
 * number (native writes `null` for non-finite values). The result is a fresh
 * object with exactly the documented shape.
 */
export declare function parseGeometry(json: string | null | undefined): StitchGeometry | null;
/**
 * Yaw / pitch / roll of a camera from its camera-to-world `R`. The optical
 * axis in world coords is the third column `(R[2], R[5], R[8])`, so
 * `yawDeg = atan2(R[2], R[8])` — the same `atan2(x, z)` the warper uses,
 * i.e. the camera's pano azimuth, increasing when turning right.
 * `pitchDeg = −asin(R[5])` (up positive); `rollDeg = atan2(R[3], R[0])` is
 * diagnostic only. Meaningless for `affine` composites.
 */
export declare function cameraAngles(cam: StitchCamera): CameraAngles;
/**
 * Azimuth interval a camera covers: `yawDeg ± hfov/2` with
 * `hfov = 2·atan(srcWidth / (2·focal))`. NOT normalised — the ends may fall
 * outside (−180, 180] (coverage helpers handle the wrap). Prefer this over
 * `roi.width` for coverage: an image straddling the ±180° seam gets a ROI
 * as wide as the whole canvas.
 */
export declare function cameraAzimuthIntervalDeg(cam: StitchCamera): AzimuthInterval;
/**
 * Direction of a pixel of the OUTPUT panorama (the JPEG you received).
 * `null` for `affine` composites (no angular model) or a degenerate
 * geometry. Azimuth is not wrapped — a full-turn composite spans (−180, 180].
 */
export declare function panoPixelToAngles(geometry: StitchGeometry, xOut: number, yOut: number): PanoAngles | null;
/**
 * Inverse of {@link panoPixelToAngles}: output-panorama pixel of a direction.
 * `null` for `affine` composites. The result is not clamped to the image.
 */
export declare function anglesToPanoPixel(geometry: StitchGeometry, azimuthDeg: number, elevationDeg: number): PanoPoint | null;
/**
 * Where a pixel `(x, y)` of input image `geometry.cameras[cameraIndex]`
 * landed in the OUTPUT panorama: `p = R · K⁻¹ · (x, y, 1)`, then the
 * projection's forward map, then `− origin`, then the output affine. Works
 * for all three projections (for `affine` it replays OpenCV's
 * `AffineWarper`: `u = warpScale·(t + (a·x' + b·y') / z')`). `null` for an
 * unknown camera, a degenerate K, or a ray on the vertical axis.
 */
export declare function imagePointToPano(geometry: StitchGeometry, cameraIndex: number, x: number, y: number): PanoPoint | null;
/**
 * Azimuth coverage of a composite: the union, on the circle, of every
 * camera's `yaw ± hfov/2` interval ({@link cameraAzimuthIntervalDeg}), plus
 * the complementary holes. `spanDeg` is the canvas's angular width
 * (`compositeWidth / warpScale`, capped at 360). `null` for `affine`
 * composites, a degenerate `warpScale`, or no cameras. Intervals use the
 * {@link AzimuthInterval} convention (`fromDeg` in [−180, 180), `toDeg` may
 * exceed 180 across the seam); a full turn is the single interval
 * `[−180, 180]` with no holes.
 */
export declare function coverageFromGeometry(geometry: StitchGeometry): SweepCoverage | null;
/**
 * Fit `panoAzimuth ≈ sign · gyroYaw + offsetDeg` between the capture-time
 * gyro yaws (`photos[photoIndex].yawDeg`) and the stitched camera azimuths
 * (`cameraAngles(cam).yawDeg`) of a strip. Both signs are tried (the sensor
 * handedness is not assumed); for each, the offset is the circular mean of
 * `wrap(pano − sign·gyro)` and the fit with the lower RMS residual wins
 * (ties → `+1`). All differences are wrapped to (−180, 180]. Needs at least
 * two cameras with a matching photo; `null` otherwise.
 */
export declare function fitGyroToPano(photos: readonly {
    yawDeg: number;
}[], stripGeometry: SweepStripGeometry): GyroPanoFit | null;
//# sourceMappingURL=geometry.d.ts.map