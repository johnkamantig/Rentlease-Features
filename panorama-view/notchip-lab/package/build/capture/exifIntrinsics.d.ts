/**
 * EXIF → camera-intrinsics helpers for guided-sweep frames.
 *
 * Pure TypeScript with no imports so it unit-tests in isolation and can be
 * reused outside the hook. `normalizeExif` flattens the per-platform
 * dictionaries expo-camera returns from `takePictureAsync({ exif: true })`
 * into one shape; `deriveFocalPx` turns the 35 mm-equivalent focal length
 * into a pixel focal-length prior for metric monodepth / intrinsics.
 *
 * Platform shapes handled (expo-camera 57, verified against its sources):
 *
 *  - iOS hands back the Exif sub-dictionary with Apple key spellings:
 *    `FocalLength` (mm), `FocalLenIn35mmFilm` (note the `Len` spelling),
 *    `LensModel`, `ISOSpeedRatings` as an ARRAY, `SubsecTimeOriginal`, plus
 *    expo-injected `Orientation` / `PixelXDimension` / `PixelYDimension`.
 *    `Make` / `Model` are NOT returned (they live in the TIFF dictionary).
 *  - Android hands back androidx `ExifInterface` tag names with parsed
 *    types: `FocalLength` (double), `FocalLengthIn35mmFilm` (int, often
 *    absent), `DigitalZoomRatio`, `Make` / `Model`, `ISOSpeedRatings` (int),
 *    `SubSecTimeOriginal`, `Orientation`, `PixelX/YDimension`. No `LensModel`.
 *
 * Numeric strings (including `"28/10"` rationals) are accepted everywhere a
 * number is expected, so raw `ExifInterface.getAttribute` output works too.
 */
/** Camera metadata for one sweep frame, normalized across platforms. */
export type SweepPhotoExif = {
    /** Physical focal length, mm (`FocalLength`). */
    focalLengthMm: number | null;
    /** 35 mm-equivalent focal length (`FocalLenIn35mmFilm` / `FocalLengthIn35mmFilm`). */
    focalLength35mm: number | null;
    /**
     * Pixel focal-length PRIOR for the delivered frame, derived from
     * `focalLength35mm` by {@link deriveFocalPx}. Roughly ±5 % — a stitch-
     * estimated focal (bundle adjustment) supersedes it for stitched frames.
     */
    focalPx: number | null;
    /** How `focalPx` was obtained; `null` when it could not be derived. */
    focalPxSource: "exif35" | null;
    /** `LensModel` (iOS only in practice). */
    lensModel: string | null;
    /** `Make` (Android only in practice). */
    make: string | null;
    /** `Model` (Android only in practice). */
    model: string | null;
    /** ISO sensitivity — iOS's `[n]` array and Android's int both collapse to `n`. */
    iso: number | null;
    /** `ExposureTime`, seconds. */
    exposureTimeS: number | null;
    /** `FNumber`. */
    fNumber: number | null;
    /** `DigitalZoomRatio` (Android). `1` or `null` means no digital zoom. */
    digitalZoomRatio: number | null;
    /**
     * `PixelXDimension` — NOTE: on iOS this is the RAW sensor frame width
     * (before EXIF orientation), on Android whatever the HAL wrote. Prefer
     * `SweepPhoto.width`/`height` for the upright delivered size.
     */
    pixelWidth: number | null;
    /** `PixelYDimension` — see `pixelWidth`. */
    pixelHeight: number | null;
    /** `DateTimeOriginal` as the camera wrote it (`YYYY:MM:DD HH:MM:SS`). */
    dateTimeOriginal: string | null;
    /** `SubsecTimeOriginal` / `SubSecTimeOriginal` — fractional-second digits. */
    subsecTimeOriginal: string | null;
    /**
     * The untouched dictionary (minus `MakerNote` / maker blobs), present only
     * when normalized with `keepRaw: true` (`GuidedSweepOptions.exif: "full"`).
     */
    raw?: Record<string, unknown>;
};
/** Diagonal of a 36 × 24 mm full-frame sensor, mm — the 35 mm-equivalence reference. */
export declare const FULL_FRAME_DIAGONAL_MM = 43.2666;
/**
 * Pixel focal length from the 35 mm-equivalent focal length, using the
 * DIAGONAL equivalence (the CIPA definition — phones report `f35` as
 * `f × 43.27 / sensorDiagonal`) on the FULL 4:3 sensor frame.
 *
 * The delivered frame may be a crop of the sensor (a 9:16 or 1:1 capture
 * ratio, or expo-camera's preview-aspect crop); a crop changes the
 * delivered width/height but not the pixel focal length, so the full 4:3
 * frame is reconstructed from the delivered dims before applying the
 * diagonal:
 *
 *     long = max(w, h), short = min(w, h)
 *     fullLong  = max(long, short × 4/3)
 *     fullShort = max(short, long × 3/4)
 *     focalPx   = f35 × hypot(fullLong, fullShort) / 43.2666
 *
 * Accuracy: roughly ±5 % — `f35` is written as an integer by the camera
 * stack, phone sensors are not exactly 4:3, and some vendors fold digital
 * zoom or lens correction into it. Treat it as a PRIOR (good enough to seed
 * metric monodepth or a bundle adjuster); a focal estimated by the stitcher
 * itself supersedes it for frames that were stitched.
 *
 * Returns `null` when `focalLength35mm` or the dims are missing / non-positive.
 */
export declare function deriveFocalPx(focalLength35mm: number | null | undefined, width: number, height: number): number | null;
/**
 * Read the EXIF `Orientation` tag (1–8) from a raw expo-camera `exif`
 * dictionary; `null` when absent or out of range.
 */
export declare function readExifOrientation(raw: unknown): number | null;
/**
 * Normalize an expo-camera `photo.exif` dictionary (either platform's
 * shape, see the module doc) into a {@link SweepPhotoExif}.
 *
 * `opts.width` / `opts.height` are the UPRIGHT delivered pixel dims of the
 * frame (what `SweepPhoto.width`/`height` carry) and feed
 * {@link deriveFocalPx}; orientation does not matter to the formula.
 * `opts.keepRaw` attaches the source dictionary as `raw` (minus maker
 * blobs). Returns `null` when `raw` is not a dictionary — an empty
 * dictionary yields a record of `null`s, so "EXIF requested but empty" is
 * distinguishable from "EXIF not requested".
 */
export declare function normalizeExif(raw: unknown, opts: {
    width: number;
    height: number;
    keepRaw: boolean;
}): SweepPhotoExif | null;
//# sourceMappingURL=exifIntrinsics.d.ts.map