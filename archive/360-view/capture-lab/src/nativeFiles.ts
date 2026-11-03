import { Directory, File, Paths } from 'expo-file-system';
import type { LocalFiles } from './repository';
import { localPath as relative, isCameraCacheUri } from './localPaths';
import { CameraCaptures, cameraFileError } from './cameraCaptures';

const root = new Directory(Paths.document, 'rentlease-capture-lab');
const cameraCaptures = new CameraCaptures();

export function registerCameraTemporary(uri: string): void {
  cameraCaptures.register(uri);
}

export const nativeFiles: LocalFiles = {
  async mkdir(path) { new Directory(root, relative(path)).create({ intermediates: true, idempotent: true }); },
  async list(path) { return new Directory(root, relative(path)).list().map(item => item.name); },
  async exists(path) { return new File(root, relative(path)).exists; },
  async read(path) { return await new File(root, relative(path)).text(); },
  async write(path, content) {
    const file = new File(root, relative(path));
    file.create({ overwrite: true });
    await file.write(content);
  },
  async move(from, to) { await new File(root, relative(from)).move(new File(root, relative(to))); },
  async copyCapture(uri, to) {
    cameraCaptures.require(uri);
    try {
      const source = new File(uri);
      if (!source.exists || source.size <= 0) throw new Error('The camera photo is missing or unreadable. Please retake it.');
      if (Paths.availableDiskSpace < source.size + 10 * 1024 * 1024) {
        throw new Error('Not enough free space to save safely. Free some phone storage, then try again.');
      }
      const destination = new File(root, relative(to));
      await source.copy(destination);
      if (!destination.exists || destination.size !== source.size) throw new Error('Incomplete copy');
    } catch (error) { throw cameraFileError(uri, Paths.cache.uri, error); }
  },
  async remove(path) {
    relative(path);
    if (!path) throw new Error('The capture root cannot be deleted by this operation.');
    if (path.includes('/')) {
      const file = new File(root, path);
      if (file.exists) file.delete();
    } else {
      const directory = new Directory(root, path);
      if (directory.exists) directory.delete();
    }
  },
  uri(path) { return new File(root, relative(path)).uri; },
};

export function removeCameraTemporary(uri: string) {
  try {
    cameraCaptures.require(uri);
    // Copying a fresh native capture does not prove it is safe to delete from a
    // different cache tree. Leave those files to the camera host's cache cleanup.
    if (!isCameraCacheUri(uri, Paths.cache.uri)) return;
    const file = new File(uri);
    if (file.exists) file.delete();
  } catch {
    // Camera cache is OS-evictable. Never attempt deletion outside that cache.
  } finally { cameraCaptures.forget(uri); }
}
