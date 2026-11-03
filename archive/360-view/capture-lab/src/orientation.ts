import type { OrientationReading, Vector } from './domain';

const dot = (a: Vector, b: Vector) => a.x * b.x + a.y * b.y + a.z * b.z;
const scale = (v: Vector, n: number): Vector => ({ x: v.x * n, y: v.y * n, z: v.z * n });
const subtract = (a: Vector, b: Vector): Vector => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const cross = (a: Vector, b: Vector): Vector => ({ x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x });
const length = (v: Vector) => Math.hypot(v.x, v.y, v.z);
const isVector = (v: Vector | null): v is Vector => !!v && [v.x, v.y, v.z].every(Number.isFinite);
const normalize = (v: Vector) => scale(v, 1 / length(v));
const degrees = (radians: number) => radians * 180 / Math.PI;
export const wrap = (degrees: number) => ((degrees % 360) + 360) % 360;
export const angleDelta = (target: number, current: number) => ((target - current + 540) % 360) - 180;

/** Android portrait device axes: x right, y top, z out of screen; rear camera points -z.
 * Uses gravity + magnetic field, never integrated gyro heading. Indoor fields and
 * acceleration make this an advisory estimate, not a calibrated camera pose.
 */
export function estimateOrientation(acceleration: Vector | null, magneticField: Vector | null,
  now = new Date().toISOString()): OrientationReading {
  const result: OrientationReading = { observedAt: now, headingDegrees: null, elevationDegrees: null,
    acceleration: isVector(acceleration) ? { ...acceleration } : null,
    magneticField: isVector(magneticField) ? { ...magneticField } : null,
    source: 'unavailable', alignmentValidated: false };
  if (!isVector(acceleration)) return result;
  const magnitude = length(acceleration);
  // Expo Accelerometer units are g. Reject obvious movement / zero readings.
  if (magnitude < 0.8 || magnitude > 1.2) return result;
  const up = normalize(acceleration);
  const camera = { x: 0, y: 0, z: -1 };
  result.elevationDegrees = degrees(Math.asin(Math.max(-1, Math.min(1, dot(camera, up)))));
  result.source = 'accelerometer';
  if (!isVector(magneticField)) return result;
  // Broad sanity range only, NOT a magnetic calibration or accuracy guarantee.
  if (length(magneticField) < 10 || length(magneticField) > 100) return result;
  const north = subtract(magneticField, scale(up, dot(magneticField, up)));
  const forward = subtract(camera, scale(up, dot(camera, up)));
  // Heading is undefined when looking near the poles; don't show jumping targets.
  if (length(north) < 5 || length(forward) < 0.2) return result;
  const northUnit = normalize(north);
  const east = cross(northUnit, up);
  result.headingDegrees = wrap(degrees(Math.atan2(dot(forward, east), dot(forward, northUnit))));
  result.source = 'accelerometer+magnetometer';
  return result;
}

export function freshReading(reading: OrientationReading | null, now = Date.now()): OrientationReading | null {
  if (!reading) return null;
  const age = now - Date.parse(reading.observedAt);
  return age >= 0 && age <= 1500 ? reading : null;
}
