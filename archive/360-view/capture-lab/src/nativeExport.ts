import { Directory, File, FileMode, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { Image } from 'react-native';
import { writeSessionZip, type ExportSource } from './exportSession';
import type { Session } from './domain';
import type { CaptureRepository } from './repository';
import { saveExportToFolder } from './folderExport';

const exportsDirectory = () => new Directory(Paths.cache, 'rentlease-capture-exports');
const source: ExportSource = {
  async inspect(uri) {
    const file = new File(uri);
    if (!file.exists || file.size < 4) throw new Error('Missing photograph');
    const handle = file.open(FileMode.ReadOnly);
    try {
      const start = await handle.readBytes(2);
      handle.offset = file.size - 2;
      const end = await handle.readBytes(2);
      if (start[0] !== 255 || start[1] !== 216 || end[0] !== 255 || end[1] !== 217) throw new Error('Damaged JPEG');
    } finally { handle.close(); }
    // Native image-header/decoder check; desktop validation subsequently fully decodes every image.
    const size = await Image.getSize(uri);
    return { bytes: file.size, width: size.width, height: size.height };
  },
  async *chunks(uri) {
    const handle = new File(uri).open(FileMode.ReadOnly);
    try {
      while (true) {
        const chunk = await handle.readBytes(256 * 1024);
        if (!chunk.length) break;
        yield chunk;
      }
    } finally { handle.close(); }
  },
};

export async function exportCapture(session: Session, repository: CaptureRepository,
  destination: 'share' | 'folder', onProgress: (message: string) => void): Promise<string> {
  if (destination === 'share' && !await Sharing.isAvailableAsync()) {
    throw new Error('Native sharing is unavailable. Use Save ZIP to folder instead.');
  }
  // Ask for destination before allocating a potentially large archive.
  const folder = destination === 'folder' ? await Directory.pickDirectoryAsync() : null;
  const directory = exportsDirectory();
  directory.create({ intermediates: true, idempotent: true });
  const name = `capture-${session.id}-r${session.revision}-${Date.now()}.zip`;
  const temporary = new File(directory, `${name}.partial`);
  temporary.create();
  const handle = temporary.open(FileMode.WriteOnly);
  let closed = false;
  try {
    await writeSessionZip(session, source,
      filename => repository.photoUri(session, session.targets.find(t => t.photo?.filename === filename)!.photo!),
      bytes => handle.writeBytes(bytes), Paths.availableDiskSpace, onProgress);
    handle.close(); closed = true;
    const archive = new File(directory, name);
    await temporary.move(archive);
    onProgress('ZIP ready. Choose an offline destination; originals stay on this phone.');
    if (folder) {
      await saveExportToFolder({ size: archive.size, openRead: () => archive.open(FileMode.ReadOnly) }, {
        createZip(filename) {
          const saved = folder.createFile(filename, 'application/zip');
          return { openWrite: () => saved.open(FileMode.WriteOnly), openRead: () => saved.open(FileMode.ReadOnly) };
        },
      }, name, onProgress);
      return `Saved ${name}. Copy it to your computer by USB. Originals are kept.`;
    }
    await Sharing.shareAsync(archive.uri, { mimeType: 'application/zip', dialogTitle: 'Transfer capture ZIP offline' });
    return 'Share sheet closed. Confirm the ZIP arrived on your computer; Android does not confirm delivery. Originals are kept.';
  } finally {
    if (!closed) handle.close();
    // move() updates the File URI; never delete the completed shared ZIP here.
    const partial = new File(directory, `${name}.partial`);
    if (partial.exists) partial.delete();
  }
}

export function clearExportCopies(): void {
  const directory = exportsDirectory();
  if (!directory.exists) return;
  for (const item of directory.list()) {
    if (item instanceof File && /^capture-[a-z0-9-]+-r\d+-\d+\.zip(?:\.partial)?$/.test(item.name)) item.delete();
  }
}
