import type { StitchBase64Result, StitchOptions, StitchResult, StitchSweepOptions, StitchSweepResult, SweepCaptureMetaInput, SweepInputPhoto, SweepManifest, SweepManifestStitch } from "./ExpoPanoramicStitcher.types";
export * from "./ExpoPanoramicStitcher.types";
export * from "./geometry";
export { toFileUri } from "./optionalFileSystem";
/**
 * The raw native module. Unlike the wrappers below it takes fully-specified
 * options and resolves `NativeStitchResult` / `NativeStitchBase64Result`,
 * i.e. with the geometry still as the `geometryJson` string (parse it with
 * `parseGeometry`).
 */
export { default } from "./ExpoPanoramicStitcherModule";
/** True if OpenCV is loaded and stitching can run on this device. */
export declare function isStitchingAvailable(): boolean;
/** Verify the native bridge end-to-end. */
export declare function helloFromNative(name: string): string;
/**
 * Normalize an image location to the bare filesystem path native expects.
 * `file://` URIs (what expo-camera's `takePictureAsync` returns on both
 * platforms) are stripped and percent-decoded; anything else is returned
 * untouched. Native reads with `cv::imread`, which cannot open URL-scheme
 * strings — the wrappers below apply this automatically.
 */
export declare function normalizeImagePath(uri: string): string;
/**
 * Stitch image files into a panorama, written to a JPEG on disk.
 * Lowest memory path — prefer this for large / many images.
 * Accepts bare paths or `file://` URIs (see {@link normalizeImagePath}).
 * Failures reject the returned promise (including validation errors).
 */
export declare function stitchImagePaths(imagePaths: string[], options?: StitchOptions): Promise<StitchResult>;
/**
 * Stitch base64 JPEGs into a base64 JPEG panorama.
 * Returns the same payload shape on iOS and Android.
 * Failures reject the returned promise (including validation errors).
 */
export declare function stitchBase64(images: string[], options?: StitchOptions): Promise<StitchBase64Result>;
/**
 * Sweep-aware orchestration over `stitchImagePaths` (plain TS — no native
 * changes). Compared to a raw stitch it:
 *
 *  1. **Closes the wrap:** when the yaw span is ≥ ~330°, the first two photos
 *     are re-appended after the last so the matcher sees the chain's own
 *     loop, and `matchWrap` defaults to true so the ends are matched
 *     explicitly. `wrapClosed: true` does NOT mean the trailing edge
 *     duplicates the start — under OpenCV's rotation model the duplicates
 *     land on their sources; `wrapClosure` reports the measured closure
 *     error instead.
 *  2. **Salvages dropped arcs:** if the primary stitch used only a subset,
 *     the dropped complement is re-stitched once (same options, order
 *     preserved) and every successful strip is returned in `strips`,
 *     largest first. A failed complement is not an error.
 *  3. **Reports gaps:** `gaps` lists the yaw ranges of photos no strip used,
 *     so the caller can show "re-sweep near 280°".
 *  4. **Tags geometry:** each strip's `geometry` carries the canonical
 *     `photoIndex` per camera and a `coverage` (azimuth union on the circle)
 *     so consumers can turn pixels into angles (see `geometry.ts`).
 *  5. **Writes a manifest:** `manifest` (always, in memory) bundles the
 *     capture `meta`, every input photo with all the fields you passed, and
 *     the stitch result + the exact options sent to native; unless
 *     `sidecar: false` it is also written best-effort as `<pano>.json` next
 *     to the primary strip via `expo-file-system` (`sidecarPath` /
 *     `sidecarError` — a failed write never rejects).
 *
 * `matchNeighbors` passes through unchanged (0 = all pairs); `matchWrap`
 * defaults to `wrapClosed` unless given explicitly. `meta` and `sidecar`
 * are consumed here and never reach native.
 *
 * Defaults differ from `stitchImagePaths`: `warpMode: 'cylindrical'`,
 * `panoConfidence: 0.7` and `autoResize: false` — a sweep is NEVER stretched
 * to 2:1 by default (a 120° strip forced into an equirectangular frame is
 * geometrically meaningless; the strip keeps its natural aspect and is only
 * downscaled to `outputWidth`). `warpMode: 'plane'` is rejected (an affine/plane
 * projection cannot cover a rotational sweep beyond ~120° FOV — it stays
 * available through `stitchImagePaths` for diagnostics). A failed
 * `spherical` stitch falls back to `cylindrical` exactly once
 * (`fellBackToCylindrical`), never more.
 */
export declare function stitchSweep(photos: SweepInputPhoto[], options?: StitchSweepOptions): Promise<StitchSweepResult>;
/**
 * Build the {@link SweepManifest} for a sweep — pure, no I/O. `stitchSweep`
 * calls this for you (`result.manifest`); use it directly to re-create a
 * manifest from a saved result, e.g. `buildSweepManifest(photos, { ...res,
 * options }, meta)`.
 *
 * `photos` are the canonical input photos (never the wrap-extended list);
 * each entry keeps every field the caller passed (the capture record's
 * sensor tick, timing and EXIF travel through verbatim) plus `index` and
 * the normalized `path`. `platform` is `meta.platform` when given, else
 * `"unknown"` — the core entry deliberately imports nothing from
 * `react-native` (it would drag the RN runtime into every consumer's jest
 * suite); the capture entry's `meta` always carries the platform.
 */
export declare function buildSweepManifest(photos: SweepInputPhoto[], stitch: SweepManifestStitch, meta?: SweepCaptureMetaInput | null): SweepManifest;
/**
 * Build a panorama one image at a time.
 * Pass `null` (or '') as `existingPanorama` for the first image — that call is a
 * pass-through that returns the image itself (with its dimensions) as the seed
 * panorama. Feed each result's `base64Image` back in as `existingPanorama`.
 */
export declare function stitchIncrementalBase64(existingPanorama: string | null, newImage: string, options?: StitchOptions): Promise<StitchBase64Result>;
//# sourceMappingURL=index.d.ts.map