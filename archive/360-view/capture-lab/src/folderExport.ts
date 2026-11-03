import { crc32 } from './exportSession';

export type ExportReader = { readBytes(length: number): Promise<Uint8Array>; close(): void };
export type ExportWriter = { writeBytes(bytes: Uint8Array): Promise<void>; close(): void };
export type CreatedExport = { openWrite(): ExportWriter; openRead(): ExportReader };
export type ExportFolder = { createZip(name: string): CreatedExport };

/** The provider creates the child; never append a pathname to a picked SAF URI.
 * Read back through its descriptor: some SDK 58 providers resolve File.size/exists
 * on a tree/document URI to the parent directory rather than the child.
 * No deletion or overwrite API is available here, including on failure.
 */
export async function saveExportToFolder(source: { size: number; openRead(): ExportReader },
  folder: ExportFolder, name: string, update: (message: string) => void = () => {}): Promise<void> {
  if (!/^[a-z0-9-]+\.zip$/.test(name) || !Number.isSafeInteger(source.size) || source.size <= 0) {
    throw new Error('Invalid export archive. Captured originals are kept.');
  }
  try {
    const input = source.openRead();
    let saved: CreatedExport, checksum = 0, copied = 0;
    try {
      saved = folder.createZip(name);
      const output = saved.openWrite();
      try {
        while (true) {
          const bytes = await input.readBytes(256 * 1024);
          if (!bytes.length) break;
          copied += bytes.length;
          if (copied > source.size) throw new Error('The source ZIP changed during export.');
          checksum = crc32(bytes, checksum);
          await output.writeBytes(bytes);
          update(`Saving ZIP to folder: ${Math.floor(copied / source.size * 100)}%`);
        }
        if (copied !== source.size) throw new Error('The source ZIP read was incomplete.');
      } finally { output.close(); }
    } finally { input.close(); }

    update('Verifying the saved ZIP…');
    const verification = saved.openRead();
    try {
      let verifiedBytes = 0, verifiedCrc = 0;
      while (true) {
        const bytes = await verification.readBytes(256 * 1024);
        if (!bytes.length) break;
        verifiedBytes += bytes.length;
        if (verifiedBytes > copied) throw new Error('Saved ZIP has unexpected extra bytes.');
        verifiedCrc = crc32(bytes, verifiedCrc);
      }
      if (verifiedBytes !== copied || verifiedCrc !== checksum) throw new Error('Saved ZIP verification failed.');
    } finally { verification.close(); }
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Android could not write or verify this destination.';
    throw new Error(`Could not save the ZIP to that folder. Captured originals and the cached ZIP are kept. ` +
      `Try another local folder or Share original capture ZIP. A failed copy may remain in the selected folder; do not use it. Details: ${detail}`);
  }
}
