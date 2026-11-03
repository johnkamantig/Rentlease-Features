import { parseSession, type Session } from './domain';

export const EXPORT_LIMIT = 2 * 1024 ** 3; // Deliberately no ZIP64 in this prototype.
const table = Uint32Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let i = 0; i < 8; i++) c = (c >>> 1) ^ ((c & 1) ? 0xedb88320 : 0);
  return c >>> 0;
});
export function crc32(bytes: Uint8Array, previous = 0): number {
  let c = previous ^ 0xffffffff;
  for (const byte of bytes) c = table[(c ^ byte) & 255]! ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function record(length: number, values: [number, number, number][]): Uint8Array {
  const bytes = new Uint8Array(length), view = new DataView(bytes.buffer);
  for (const [offset, size, value] of values) {
    if (size === 2) view.setUint16(offset, value, true);
    else view.setUint32(offset, value, true);
  }
  return bytes;
}

/** Streaming ZIP STORE with data descriptors: JPEG bytes are never recompressed. */
export class StoredZip {
  private offset = 0;
  private entries: { name: Uint8Array; offset: number; size: number; crc: number }[] = [];
  private finished = false;
  constructor(private readonly sink: (data: Uint8Array) => Promise<void>) {}
  private async write(data: Uint8Array) {
    if (this.offset + data.length > EXPORT_LIMIT) throw new Error('Export exceeds the 2 GiB prototype limit. Originals are kept.');
    await this.sink(data); this.offset += data.length;
  }
  async add(name: string, chunks: AsyncIterable<Uint8Array>, expectedSize?: number) {
    if (this.finished || !/^[a-zA-Z0-9_.-]+(?:\/[a-zA-Z0-9_.-]+)?$/.test(name) || name.includes('..') ||
        this.entries.some(e => new TextDecoder().decode(e.name) === name)) throw new Error('Invalid ZIP entry.');
    const encoded = new TextEncoder().encode(name), offset = this.offset;
    await this.write(record(30, [[0, 4, 0x04034b50], [4, 2, 20], [6, 2, 0x808], [12, 2, 33], [26, 2, encoded.length]]));
    await this.write(encoded);
    let size = 0, crc = 0;
    for await (const chunk of chunks) { size += chunk.length; crc = crc32(chunk, crc); await this.write(chunk); }
    if (expectedSize !== undefined && size !== expectedSize) throw new Error(`Incomplete read: ${name}. Originals are kept.`);
    await this.write(record(16, [[0, 4, 0x08074b50], [4, 4, crc], [8, 4, size], [12, 4, size]]));
    this.entries.push({ name: encoded, offset, size, crc });
    return { bytes: size, crc32: crc.toString(16).padStart(8, '0') };
  }
  async close() {
    if (this.finished) throw new Error('ZIP already closed.');
    this.finished = true;
    const start = this.offset;
    for (const entry of this.entries) {
      await this.write(record(46, [[0, 4, 0x02014b50], [4, 2, 20], [6, 2, 20], [8, 2, 0x808], [14, 2, 33],
        [16, 4, entry.crc], [20, 4, entry.size], [24, 4, entry.size], [28, 2, entry.name.length], [42, 4, entry.offset]]));
      await this.write(entry.name);
    }
    await this.write(record(22, [[0, 4, 0x06054b50], [8, 2, this.entries.length], [10, 2, this.entries.length],
      [12, 4, this.offset - start], [16, 4, start]]));
  }
}
export interface ExportSource {
  inspect(uri: string): Promise<{ bytes: number; width: number; height: number }>;
  chunks(uri: string): AsyncIterable<Uint8Array>;
}
async function* bytes(data: Uint8Array) { yield data; }

export async function writeSessionZip(session: Session, source: ExportSource,
  photoUri: (filename: string) => string, sink: (data: Uint8Array) => Promise<void>,
  availableBytes: number, onProgress: (message: string) => void = () => {}) {
  parseSession(JSON.stringify(session));
  if (session.status !== 'complete' || session.targets.some(t => !t.photo)) throw new Error('Finish the complete capture set before exporting.');
  const files = [];
  for (const [index, target] of session.targets.entries()) {
    const photo = target.photo!;
    onProgress(`Checking photo ${index + 1} of ${session.targets.length}`);
    let info;
    try { info = await source.inspect(photoUri(photo.filename)); }
    catch { throw new Error(`Photo ${index + 1} (${target.direction}) is missing or unreadable. Retake it before exporting. Originals are kept.`); }
    if (!Number.isSafeInteger(info.bytes) || info.bytes < 4 || info.width !== photo.width || info.height !== photo.height) {
      throw new Error(`Photo ${index + 1} has invalid dimensions or size. Retake it before exporting. Originals are kept.`);
    }
    files.push({ order: index + 1, targetId: target.id, path: `images/${String(index + 1).padStart(4, '0')}-${photo.filename}`,
      ...photo, expectedBytes: info.bytes });
  }
  const needed = files.reduce((sum, f) => sum + f.expectedBytes, 0) + 4 * 1024 ** 2;
  if (needed > EXPORT_LIMIT) throw new Error('Export exceeds the 2 GiB prototype limit. Originals are kept.');
  if (availableBytes < needed + 10 * 1024 ** 2) throw new Error('Not enough free storage for the export copy. Originals are kept.');
  const zip = new StoredZip(sink), photos = [];
  for (const file of files) {
    onProgress(`Packing photo ${file.order} of ${files.length}`);
    const { expectedBytes, ...metadata } = file;
    const checksum = await zip.add(file.path, source.chunks(photoUri(file.filename)), expectedBytes);
    photos.push({ ...metadata, ...checksum });
  }
  const manifest = { exportVersion: 1, exportedAt: new Date().toISOString(),
    projection: 'unstitched-photographs', coverageValidated: false, session,
    notes: 'Target/overlap order, not shutter-time order. Horizontal sweep angles are a capture plan, not verified image coverage. Orientation is approximate and not camera calibration. Original JPEGs may contain sensitive metadata.', photos };
  await zip.add('manifest.json', bytes(new TextEncoder().encode(JSON.stringify(manifest, null, 2))));
  await zip.close();
  return manifest;
}
