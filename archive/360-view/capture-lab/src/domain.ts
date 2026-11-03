export const DIRECTIONS = ['horizontal', 'upper', 'lower', 'ceiling', 'floor'] as const;
export type Direction = typeof DIRECTIONS[number];
export const STEPS = [15, 20, 30, 40] as const;
export type Step = typeof STEPS[number];
export const SWEEPS = [120, 150, 180] as const;
export type Sweep = typeof SWEEPS[number];
export type Vector = { x: number; y: number; z: number };

export type OrientationReading = {
  observedAt: string;
  headingDegrees: number | null;
  elevationDegrees: number | null;
  acceleration: Vector | null;
  magneticField: Vector | null;
  source: 'accelerometer+magnetometer' | 'accelerometer' | 'unavailable';
  alignmentValidated: false;
};

export type Photo = {
  id: string;
  filename: string;
  width: number;
  height: number;
  requestedAt: string;
  savedAt: string;
  direction: Direction;
  targetYaw: number | null;
  targetElevation: number;
  orientation: OrientationReading | null;
  referenceHeading: number | null;
  referenceSetAt: string | null;
  revision: number;
};

export type Target = {
  id: string;
  direction: Direction;
  yaw: number | null;
  elevation: number;
  extra: boolean;
  photo: Photo | null;
};

export type Session = {
  schemaVersion: 1;
  id: string;
  revision: number;
  createdAt: string;
  updatedAt: string;
  status: 'active' | 'paused' | 'complete';
  step: Step;
  targets: Target[];
  coverageValidated: false;
  // Absent on legacy full-sphere records, which remain readable/exportable.
  captureMode?: 'horizontal';
  sweepDegrees?: Sweep;
};

export const DIRECTION_LABELS: Record<Direction, string> = {
  horizontal: 'Horizontal sweep', upper: 'Upper walls (legacy)', lower: 'Lower walls (legacy)',
  ceiling: 'Ceiling', floor: 'Floor',
};
export const INSTRUCTIONS: Record<Direction, string> = {
  horizontal: 'Keep the phone upright and level. Turn right slowly with the lens near one point. Keep roughly half of the previous scene visible. Stop at the end of the planned sweep.',
  upper: 'Tilt toward the tops of the walls. Make a full loop, overlapping the horizontal row and the neighboring photos.',
  lower: 'Tilt toward the bottoms of the walls. Make a full loop, overlapping the horizontal row and the neighboring photos.',
  ceiling: 'Point the rear camera toward the ceiling. Include overlap with the upper row. Add photos for any missing ceiling corners.',
  floor: 'Point the rear camera toward the floor. Keep the lens near the same position and avoid blocking the view with your feet. Fill gaps around the lower row.',
};

export function newId(): string {
  // Local filenames only; not an authentication token or a security identifier.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export function horizontalYaws(step: Step, sweep: Sweep): number[] {
  if (!STEPS.includes(step)) throw new Error('Choose a supported guide spacing.');
  if (!SWEEPS.includes(sweep)) throw new Error('Choose a 120, 150 or 180 degree sweep.');
  return Array.from({ length: Math.ceil(sweep / step) + 1 }, (_, i) => Math.min(i * step, sweep));
}

export function isHorizontalSession(session: Session): boolean {
  return session.captureMode === 'horizontal';
}

export function makeSession(step: Step, id = newId(), now = new Date().toISOString(), sweep: Sweep = 150): Session {
  const targets: Target[] = horizontalYaws(step, sweep).map((yaw, i) => ({
    id: `horizontal-${i}`, direction: 'horizontal', yaw, elevation: 0, extra: false, photo: null,
  }));
  return { schemaVersion: 1, id, revision: 0, createdAt: now, updatedAt: now,
    status: 'active', step, targets, coverageValidated: false, captureMode: 'horizontal', sweepDegrees: sweep };
}

export function progress(session: Session) {
  const captured = session.targets.filter(t => t.photo !== null).length;
  return { captured, planned: session.targets.length, remaining: session.targets.length - captured };
}

export function nextTarget(session: Session, afterId?: string): Target | undefined {
  const start = afterId ? session.targets.findIndex(t => t.id === afterId) + 1 : 0;
  return session.targets.slice(start).find(t => !t.photo) ?? session.targets.slice(0, start).find(t => !t.photo);
}

export function insertExtra(session: Session, afterId: string, id = `extra-${newId()}`): Session {
  if (session.targets.length >= 300) throw new Error('This prototype supports up to 300 planned photos per set.');
  const index = session.targets.findIndex(t => t.id === afterId);
  const anchor = session.targets[index];
  if (!anchor) throw new Error('Select a direction before adding an overlap photo.');
  if (session.targets.some(t => t.id === id)) throw new Error('This target already exists.');
  // Extra photos are deliberately free-framed: no invented field-of-view / coverage proof.
  const extra: Target = { id, direction: anchor.direction, yaw: null,
    elevation: anchor.elevation, extra: true, photo: null };
  const targets = [...session.targets];
  targets.splice(index + 1, 0, extra);
  return { ...session, status: 'paused', targets };
}

export function replacePhoto(session: Session, targetId: string, photo: Photo): Session {
  const target = session.targets.find(t => t.id === targetId);
  if (!target || photo.direction !== target.direction) throw new Error('The capture target changed. Please try again.');
  if (photo.width <= 0 || photo.height <= 0) throw new Error('The camera returned an invalid photograph.');
  return { ...session, targets: session.targets.map(t => t.id === targetId ? { ...t, photo } : t) };
}

// Validate persisted data before using any filenames. Paths are rebuilt from IDs.
const ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const date = (v: unknown): v is string => typeof v === 'string' && Number.isFinite(Date.parse(v));
const safeId = (v: unknown): v is string => typeof v === 'string' && v.length <= 100 && ID.test(v);
const nullableNumber = (v: unknown) => v === null || finite(v);

export function validOrientation(v: unknown): v is OrientationReading {
  if (!record(v) || !date(v.observedAt) || v.alignmentValidated !== false ||
      !['accelerometer+magnetometer', 'accelerometer', 'unavailable'].includes(String(v.source))) return false;
  if (!nullableNumber(v.headingDegrees) || !nullableNumber(v.elevationDegrees)) return false;
  if (finite(v.headingDegrees) && (v.headingDegrees < 0 || v.headingDegrees >= 360)) return false;
  if (finite(v.elevationDegrees) && Math.abs(v.elevationDegrees) > 90) return false;
  return ['acceleration', 'magneticField'].every(key => v[key] === null ||
    (record(v[key]) && ['x', 'y', 'z'].every(axis => finite((v[key] as Record<string, unknown>)[axis]))));
}

export function parseSession(text: string): Session {
  const s: unknown = JSON.parse(text);
  const fail = () => { throw new Error('The saved capture record is invalid.'); };
  if (!record(s) || s.schemaVersion !== 1 || s.coverageValidated !== false || !safeId(s.id) ||
      !Number.isSafeInteger(s.revision) || (s.revision as number) < 1 || !date(s.createdAt) || !date(s.updatedAt) ||
      !['active', 'paused', 'complete'].includes(String(s.status)) || !STEPS.includes(s.step as Step) ||
      !Array.isArray(s.targets) || s.targets.length === 0 || s.targets.length > 300) return fail();
  const ids = new Set<string>();
  const filenames = new Set<string>();
  for (const t of s.targets) {
    if (!record(t) || !safeId(t.id) || ids.has(t.id) || !DIRECTIONS.includes(t.direction as Direction) ||
        !nullableNumber(t.yaw) || (finite(t.yaw) && (t.yaw < 0 || t.yaw >= 360)) ||
        !finite(t.elevation) || Math.abs(t.elevation) > 90 || typeof t.extra !== 'boolean') return fail();
    ids.add(t.id);
    if (t.photo === null) continue;
    const p = t.photo;
    if (!record(p) || !safeId(p.id) || p.filename !== `${p.id}.jpg` || filenames.has(p.filename as string) ||
        !Number.isSafeInteger(p.width) || (p.width as number) <= 0 || !Number.isSafeInteger(p.height) || (p.height as number) <= 0 ||
        !date(p.requestedAt) || !date(p.savedAt) || p.direction !== t.direction || p.targetYaw !== t.yaw || p.targetElevation !== t.elevation ||
        !Number.isSafeInteger(p.revision) || (p.revision as number) < 1 ||
        !nullableNumber(p.referenceHeading) || !(p.referenceSetAt === null || date(p.referenceSetAt)) ||
        !(p.orientation === null || validOrientation(p.orientation))) return fail();
    filenames.add(p.filename as string);
  }
  if (s.captureMode !== undefined || s.sweepDegrees !== undefined) {
    if (s.captureMode !== 'horizontal' || !SWEEPS.includes(s.sweepDegrees as Sweep) ||
        s.targets.some(t => t.direction !== 'horizontal' || t.elevation !== 0 ||
          (t.extra ? t.yaw !== null : t.yaw === null))) return fail();
    const planned = s.targets.filter(t => !t.extra).map(t => t.yaw);
    if (JSON.stringify(planned) !== JSON.stringify(horizontalYaws(s.step as Step, s.sweepDegrees as Sweep))) return fail();
  }
  return s as unknown as Session;
}
