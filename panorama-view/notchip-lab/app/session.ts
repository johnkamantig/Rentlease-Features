import { Directory, File, Paths } from 'expo-file-system';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import { stitchSweep } from '@notchip/expo-panoramic-stitcher';
import type { SweepPhoto, SweepCaptureMeta } from '@notchip/expo-panoramic-stitcher/capture';
import { inspectResult } from './gates';

export const OPTIONS = { warpMode: 'spherical', autoResize: false, matchNeighbors: 2,
  matchWrap: true, panoConfidence: 0.7, matchConf: 0.3, outputWidth: 4096,
  jpegQuality: 92, sidecar: false } as const;

export async function evaluateCapture(photos: SweepPhoto[], meta: SweepCaptureMeta,
  notify: (s: string) => void) {
  const started = performance.now();
  const root = new Directory(Paths.document, 'sweeps'); root.create({ intermediates: true, idempotent: true });
  const folder = new Directory(root, `${Date.now()}-${Math.random().toString(16).slice(2)}`);
  folder.create();
  const reportFile = new File(folder, 'report.json');
  const record: Record<string, unknown> = { schemaVersion: 1, packageVersion: '0.7.0',
    accepted360: false, pannellumReady: false, options: OPTIONS, meta,
    device: { platform: Platform.OS, version: Platform.Version, model: Device.modelName,
      physicalDevice: Device.isDevice, totalMemoryBytes: Device.totalMemory },
    captureMs: meta.finishedAt === null ? null : meta.finishedAt-meta.startedAt,
    capturedCount: photos.length, peakMemoryBytes: null, sourcePhotos: photos, photos: [], error: null };
  const save = () => { reportFile.write(JSON.stringify(record, null, 2)); };
  save(); // Session remains discoverable even if native crashes later.
  try {
    if (photos.length>26) throw new Error('Capture exceeds 26-frame experiment cap');
    // Preserve even short/background-aborted sweeps before rejecting them.
    for (let i=0;i<photos.length;i++) {
      notify(`Preserving original ${i+1}/${photos.length}`);
      new File(photos[i]!.uri).copy(new File(folder, `original-${String(i).padStart(2,'0')}.jpg`));
    }
    if (photos.length<6 || meta.endedBy === 'background')
      throw new Error('Need 6-26 frames from a foreground sweep. Retry an interrupted capture.');
    const prepared: SweepPhoto[] = [];
    let pixels = 0;
    for (let i=0;i<photos.length;i++) {
      notify(`Preserving and resizing photograph ${i+1}/${photos.length}`);
      const original = photos[i]!;
      const source = new File(folder, `original-${String(i).padStart(2,'0')}.jpg`);
      const actions = Math.max(original.width, original.height)>1200
        ? [{ resize: original.width>original.height ? { width: 1200 } : { height: 1200 } }] : [];
      const resized = await manipulateAsync(source.uri, actions, { compress: 0.95, format: SaveFormat.JPEG });
      const input = new File(folder, `input-${String(i).padStart(2,'0')}.jpg`);
      new File(resized.uri).copy(input);
      prepared.push({ ...original, uri: input.uri, width: resized.width, height: resized.height });
      pixels += resized.width*resized.height;
      record.photos = prepared.map((p,j) => ({...p,
        originalUri: new File(folder, `original-${String(j).padStart(2,'0')}.jpg`).uri,
        originalWidthPx: photos[j]!.width, originalHeightPx: photos[j]!.height,
        inputScaleX: p.width/photos[j]!.width, inputScaleY: p.height/photos[j]!.height,
        exifNote: 'EXIF describes original capture; any focal-pixel prior must be scaled for prepared inputs. Not measured calibration.' }));
      save();
    }
    const nativePixels = pixels + prepared.slice(0,2).reduce((n,p)=>n+p.width*p.height,0);
    if (nativePixels>36_000_000) throw new Error('Native input exceeds 36-million-pixel experiment budget');
    record.nativeInputPixels = nativePixels;
    notify('Stitching and collecting wrap / coverage / gap diagnostics...');
    record.nativeStartedAt = new Date().toISOString(); save();
    const t = performance.now();
    const result = await stitchSweep(prepared, { ...OPTIONS, meta });
    record.stitchMs = performance.now()-t;
    record.result = result; save();
    // Retain every strip as evidence, including rejected or oversized results.
    for (let i=0;i<result.strips.length;i++) {
      new File(result.strips[i]!.path).copy(new File(folder, `diagnostic-strip-${i}.jpg`));
    }
    const bytes = new File(folder, 'diagnostic-strip-0.jpg').size;
    record.bytes = bytes;
    record.inspection = inspectResult(result, prepared, bytes);
    record.width = result.width; record.height = result.height;
  } catch (error) {
    record.error = error instanceof Error ? error.message : String(error);
  }
  record.totalProcessingMs = performance.now()-started; save();
  return { report: record, uri: reportFile.uri, directory: folder.uri,
    preview: new File(folder,'diagnostic-strip-0.jpg').exists ? new File(folder,'diagnostic-strip-0.jpg').uri : null };
}
