import { insertExtra, isHorizontalSession, makeSession, progress, type Session, type Step, type Sweep } from './domain';
import { CaptureRepository, type CapturedImage, type CaptureContext, type Stored } from './repository';

export type SessionState = { session: Session | null; busy: boolean; initialized: boolean; error: string | null; notice: string | null };

/** Serializes camera / disk actions; retained by App across capture and review screens. */
export class SessionService {
  private state: SessionState = { session: null, busy: false, initialized: false, error: null, notice: null };
  private readonly listeners = new Set<() => void>();
  private interrupted = false;
  constructor(readonly repository: CaptureRepository) {}
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private update(value: Partial<SessionState>) {
    this.state = { ...this.state, ...value };
    this.listeners.forEach(listener => listener());
  }
  private accept(result: Stored) { this.update({ session: result.session, notice: result.warning }); }
  private async run(task: () => Promise<void>): Promise<boolean> {
    if (this.state.busy) return false;
    this.update({ busy: true, error: null, notice: null });
    let success = false;
    try { await task(); success = true; }
    catch (error) {
      this.update({ error: error instanceof Error ? error.message : 'The local operation failed. Please try again.' });
    } finally {
      // An interruption can arrive during a photo copy or snapshot write.
      if (this.interrupted && this.state.session?.status === 'active') {
        const paused: Session = { ...this.state.session, status: 'paused' };
        try { this.accept(await this.repository.save(paused)); }
        catch { this.update({ session: paused, error: 'Capture paused, but the pause record could not be saved. The last saved photos will reopen paused.' }); }
      }
      this.update({ busy: false });
    }
    return success;
  }
  async initialize(): Promise<boolean> {
    return this.run(async () => {
      try {
        const restored = await this.repository.restore();
        if (restored) this.accept(restored);
      } finally { this.update({ initialized: true }); }
    });
  }
  async start(step: Step, sweep: Sweep = 150): Promise<boolean> {
    return this.run(async () => {
      if (this.state.session) throw new Error('Resume the current set or delete it before starting another.');
      this.interrupted = false;
      this.accept(await this.repository.save(makeSession(step, undefined, undefined, sweep)));
    });
  }
  async resume(): Promise<boolean> {
    return this.run(async () => {
      if (!this.state.session) throw new Error('Start a capture set first.');
      if (!isHorizontalSession(this.state.session)) throw new Error('This older capture set is available for review and export. Start a new horizontal set after preserving it.');
      this.interrupted = false;
      this.accept(await this.repository.save({ ...this.state.session, status: 'active' }));
    });
  }
  async pause(): Promise<boolean> {
    this.interrupted = true;
    return this.run(async () => {
      if (this.state.session?.status === 'active') this.accept(await this.repository.save({ ...this.state.session, status: 'paused' }));
    });
  }
  async capture(targetId: string, takePicture: () => Promise<CapturedImage>, context: CaptureContext): Promise<boolean> {
    return this.run(async () => {
      const session = this.state.session;
      if (!session || session.status !== 'active' || this.interrupted) throw new Error('Resume capture before taking a photograph.');
      if (!isHorizontalSession(session)) throw new Error('Older capture sets are review/export only.');
      if (!session.targets.some(t => t.id === targetId)) throw new Error('Choose a capture target.');
      let image: CapturedImage;
      try { image = await takePicture(); }
      catch { throw new Error('The camera could not take this photo. Keep the app open, check camera access, and try again.'); }
      if (!Number.isSafeInteger(image.width) || !Number.isSafeInteger(image.height) || image.width <= 0 || image.height <= 0) {
        throw new Error('The camera returned an invalid photo. Try again.');
      }
      this.accept(await this.repository.savePhoto({ ...session, status: this.interrupted ? 'paused' : 'active' }, targetId, image, context));
    });
  }
  async addExtra(afterId: string): Promise<boolean> {
    return this.run(async () => {
      if (!this.state.session) throw new Error('Start a capture set first.');
      if (!isHorizontalSession(this.state.session)) throw new Error('Older capture sets are review/export only.');
      this.accept(await this.repository.save(insertExtra(this.state.session, afterId)));
    });
  }
  async finish(): Promise<boolean> {
    return this.run(async () => {
      const session = this.state.session;
      if (!session || progress(session).remaining > 0) throw new Error('Capture each planned target before saving the set. Add extra overlap photos where needed.');
      this.accept(await this.repository.save({ ...session, status: 'complete' }));
    });
  }
  async discard(): Promise<boolean> {
    return this.run(async () => {
      await this.repository.discardAll();
      this.interrupted = false;
      this.update({ session: null, notice: 'Local capture photos and records deleted.' });
    });
  }
  async exportSet(exporter: (session: Session, progress: (message: string) => void) => Promise<string>): Promise<boolean> {
    return this.run(async () => {
      const session = this.state.session;
      if (!session || session.status !== 'complete' || progress(session).remaining) throw new Error('Finish the complete capture set before exporting.');
      const notice = await exporter(session, message => this.update({ notice: message }));
      this.update({ notice });
    });
  }
}
