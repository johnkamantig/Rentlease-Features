import { newId, parseSession, replacePhoto, type OrientationReading, type Photo, type Session } from './domain';

export interface LocalFiles {
  mkdir(path: string): Promise<void>;
  list(path: string): Promise<string[]>;
  exists(path: string): Promise<boolean>;
  read(path: string): Promise<string>;
  write(path: string, content: string): Promise<void>;
  move(from: string, to: string): Promise<void>;
  copyCapture(uri: string, to: string): Promise<void>;
  remove(path: string): Promise<void>;
  uri(path: string): string;
}
export type CapturedImage = { uri: string; width: number; height: number };
export type CaptureContext = {
  requestedAt: string;
  orientation: OrientationReading | null;
  referenceHeading: number | null;
  referenceSetAt: string | null;
};
export type Stored = { session: Session; warning: string | null };
const manifestPattern = /^manifest-(\d{7})\.json$/;
const directoryPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const photoPattern = /^photo-[a-z0-9]+(?:-[a-z0-9]+)*\.jpg$/;

/** All paths here are relative to this prototype's private document directory. */
export class CaptureRepository {
  constructor(private readonly files: LocalFiles) {}

  photoUri(session: Session, photo: Photo): string {
    return this.files.uri(`${session.id}/${photo.filename}`);
  }

  async restore(): Promise<Stored | null> {
    await this.files.mkdir('');
    const folders = (await this.files.list('')).filter(name => directoryPattern.test(name));
    const candidates: Stored[] = [];
    for (const id of folders) {
      const names = (await this.files.list(id)).filter(n => manifestPattern.test(n)).sort().reverse();
      for (const [index, name] of names.entries()) {
        try {
          const session = parseSession(await this.files.read(`${id}/${name}`));
          if (session.id !== id || session.revision !== Number(name.match(manifestPattern)![1])) continue;
          let missing = false;
          for (const target of session.targets) {
            if (target.photo && !await this.files.exists(`${id}/${target.photo.filename}`)) {
              target.photo = null;
              missing = true;
            }
          }
          session.status = missing || session.status !== 'complete' ? 'paused' : 'complete';
          candidates.push({ session, warning: missing
            ? 'Some saved photos are missing. Their targets need to be captured again.'
            : index > 0 ? 'Recovered an earlier save after an interrupted or unreadable write. Check the last photos.' : null });
          break;
        } catch {
          // A fully written older snapshot can recover an interrupted newest write.
        }
      }
    }
    candidates.sort((a, b) => b.session.updatedAt.localeCompare(a.session.updatedAt));
    if (candidates[0]) return candidates[0];
    if (folders.length) throw new Error('Local files exist but no capture record can be read. Retry, or explicitly delete the local capture data to start again.');
    return null;
  }

  async save(session: Session): Promise<Stored> {
    // Validate before using the ID as a directory, including on a caller-created session.
    parseSession(JSON.stringify({ ...session, revision: session.revision + 1 }));
    await this.files.mkdir(session.id);
    const revisions = (await this.files.list(session.id)).filter(n => manifestPattern.test(n))
      .map(n => Number(n.match(manifestPattern)![1]));
    const revision = Math.max(session.revision, ...revisions) + 1;
    if (revision > 9999999) throw new Error('This capture set has reached its save limit.');
    const next: Session = { ...session, revision, updatedAt: new Date().toISOString() };
    const text = JSON.stringify(next, null, 2);
    parseSession(text);
    const name = `manifest-${String(next.revision).padStart(7, '0')}.json`;
    const temporary = `${next.id}/${name}.tmp`;
    const destination = `${next.id}/${name}`;
    // Immutable snapshots: previous valid record remains until a new one is published.
    try {
      await this.files.write(temporary, text);
      await this.files.move(temporary, destination);
    } catch {
      await this.files.remove(temporary).catch(() => {});
      throw new Error('Could not save on this phone. Check free storage and try again; the previous save is kept.');
    }
    let warning: string | null = null;
    try { await this.prune(next.id); }
    catch { warning = 'Saved, but some old local files could not be cleaned up. Delete this set when it is no longer needed.'; }
    return { session: next, warning };
  }

  async savePhoto(session: Session, targetId: string, image: CapturedImage, context: CaptureContext): Promise<Stored> {
    const target = session.targets.find(t => t.id === targetId);
    if (!target) throw new Error('The selected capture target is missing.');
    const id = `photo-${newId()}`;
    const filename = `${id}.jpg`;
    const destination = `${session.id}/${filename}`;
    const photo: Photo = { id, filename, width: image.width, height: image.height,
      requestedAt: context.requestedAt, savedAt: new Date().toISOString(),
      direction: target.direction, targetYaw: target.yaw, targetElevation: target.elevation,
      orientation: context.orientation, referenceHeading: context.referenceHeading,
      referenceSetAt: context.referenceSetAt, revision: (target.photo?.revision ?? 0) + 1 };
    try {
      await this.files.copyCapture(image.uri, destination);
      return await this.save(replacePhoto(session, targetId, photo));
    } catch (error) {
      await this.files.remove(destination).catch(() => {});
      throw error;
    }
  }

  private async prune(id: string): Promise<void> {
    const names = await this.files.list(id);
    const snapshots = names.filter(n => manifestPattern.test(n)).sort().reverse();
    const keep = new Set<string>();
    // Retain previous snapshot AND its photos so fallback after a retake is usable.
    for (const name of snapshots.slice(0, 2)) {
      const session = parseSession(await this.files.read(`${id}/${name}`));
      for (const target of session.targets) if (target.photo) keep.add(target.photo.filename);
    }
    for (const name of names) {
      if ((photoPattern.test(name) && !keep.has(name)) || snapshots.slice(2).includes(name) ||
          /^manifest-\d{7}\.json\.tmp$/.test(name)) await this.files.remove(`${id}/${name}`);
    }
  }

  async discardAll(): Promise<void> {
    await this.files.mkdir('');
    // Explicitly scoped to this app's capture root. Never delete camera roll files.
    for (const name of await this.files.list('')) {
      if (directoryPattern.test(name)) await this.files.remove(name);
    }
  }
}
