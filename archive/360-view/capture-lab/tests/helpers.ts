import type { LocalFiles } from '../src/repository';

export class MemoryFiles implements LocalFiles {
  files = new Map<string, string>();
  directories = new Set<string>(['']);
  fail: 'write' | 'move' | 'copy' | 'remove' | null = null;
  async mkdir(path: string) { this.directories.add(path); }
  async list(path: string) {
    const prefix = path ? path + '/' : '';
    return [...new Set([...this.files.keys(), ...this.directories])].filter(key => key.startsWith(prefix))
      .map(key => key.slice(prefix.length)).filter(key => !!key && !key.includes('/'));
  }
  async exists(path: string) { return this.files.has(path); }
  async read(path: string) {
    const content = this.files.get(path);
    if (content === undefined) throw new Error('File not found');
    return content;
  }
  async write(path: string, content: string) {
    if (this.fail === 'write') { this.files.set(path, '{incomplete'); throw new Error('Disk full'); }
    this.files.set(path, content);
  }
  async move(from: string, to: string) {
    if (this.fail === 'move') throw new Error('Rename failed');
    if (this.files.has(to)) throw new Error('Destination exists');
    this.files.set(to, await this.read(from));
    this.files.delete(from);
  }
  async copyCapture(uri: string, to: string) {
    if (this.fail === 'copy') { this.files.set(to, 'partial'); throw new Error('Copy failed'); }
    this.files.set(to, `image bytes from ${uri}`);
  }
  async remove(path: string) {
    if (this.fail === 'remove') throw new Error('Delete failed');
    this.files.delete(path);
    this.directories.delete(path);
    for (const key of this.files.keys()) if (key.startsWith(path + '/')) this.files.delete(key);
  }
  uri(path: string) { return `file:///private/capture-lab/${path}`; }
}
export const context = { requestedAt: '2026-10-25T08:00:00.000Z', orientation: null, referenceHeading: null, referenceSetAt: null };
export const image = { uri: 'file:///camera-cache/test.jpg', width: 3000, height: 4000 };

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
