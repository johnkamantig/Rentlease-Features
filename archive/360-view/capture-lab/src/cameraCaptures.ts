export const CAPTURE_BUILD = 'horizontal-1';

/** Short-lived provenance, never populated from persisted manifests or user input.
 * Expo Go / native camera cache paths can differ from Paths.cache. The native
 * filesystem checks read permission; this registry limits copying to this shutter.
 */
export class CameraCaptures {
  private readonly pending = new Set<string>();

  register(uri: string): void {
    // Only local JPEGs from the native camera. Do not normalize away traversal.
    const match = /^file:(?:\/\/)?(\/[^?#]*)$/i.exec(uri);
    let path: string;
    try { path = match ? decodeURIComponent(match[1]!) : ''; }
    catch { path = ''; }
    if (!path || path.startsWith('//') || /[\\\u0000-\u001f\u007f]/.test(path) ||
        path.split('/').some(part => part === '.' || part === '..') || !/\.jpe?g$/i.test(path)) {
      throw new Error(`[${CAPTURE_BUILD}] The camera did not return a local JPEG photo.`);
    }
    this.pending.add(uri);
  }

  require(uri: string): void {
    if (!this.pending.has(uri)) {
      throw new Error(`[${CAPTURE_BUILD}] This photo is not from the current camera capture. Please retake it.`);
    }
  }

  forget(uri: string): void { this.pending.delete(uri); }
}

export function cameraFileError(uri: string, cacheRoot: string, error: unknown): Error {
  const detail = error instanceof Error ? error.message : String(error);
  return new Error(`[${CAPTURE_BUILD}] Could not keep this camera photo on the phone.\n` +
    `Camera file: ${uri}\nFileSystem cache: ${cacheRoot}\nDetails: ${detail}`);
}
