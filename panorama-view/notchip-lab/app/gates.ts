import type { StitchSweepResult, SweepInputPhoto } from '@notchip/expo-panoramic-stitcher';

export const MAX_BYTES = 9_499_999;
const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);
// Diagnostic prerequisites only. Passing is NOT permission to export a 360 image.
// Native camera intervals are not source masks; duplicate poses are not a raw loop test.
export function inspectResult(r: StitchSweepResult, photos: SweepInputPhoto[], bytes: number) {
  const reasons: string[] = [];
  const fail = (ok: boolean, why: string) => { if (!ok) reasons.push(why); };
  fail(r.success === true, 'Native stitch failed');
  fail(Number.isInteger(bytes) && bytes > 0 && bytes <= MAX_BYTES, 'JPEG exceeds export limit or is missing');
  fail(photos.length >= 6 && photos.length <= 26, 'Invalid input count');
  fail(photos.every(p => finite(p.yawDeg)), 'Non-finite capture yaw');
  const yaws = photos.map(p => p.yawDeg);
  const span = Math.max(...yaws) - Math.min(...yaws);
  fail(finite(span) && span >= 345 && span <= 365, 'Capture does not describe approximately one complete turn');
  const direction = Math.sign(yaws[yaws.length - 1]! - yaws[0]!);
  fail(direction !== 0 && yaws.slice(1).every((v,i) => (v-yaws[i]!) * direction >= -2), 'Capture reverses direction');
  fail(r.strips.length === 1, 'Multiple partial strips are not one panorama');
  fail(r.gaps.length === 0, 'Package reports dropped-photo gaps');
  fail(r.usedCount === photos.length && r.usedIndices.length === photos.length &&
    new Set(r.usedIndices).size === photos.length &&
    photos.every((_,i) => r.usedIndices.includes(i)), 'Primary strip lost input photographs');
  fail(r.wrapClosed === true, 'Wrap matching was not attempted');
  const closure = r.wrapClosure;
  fail(!!closure && finite(closure.closureErrorDeg) && closure.closureErrorDeg >= 0 &&
    closure.closureErrorDeg <= 3 && closure.pairs.length >= 2 &&
    closure.pairs.every(p => finite(p.azimuthDeg) && finite(p.duplicateAzimuthDeg) &&
      Math.abs(((p.duplicateAzimuthDeg-p.azimuthDeg+540)%360)-180) <= 3),
  'Missing or unacceptable duplicate-pose closure diagnostic');
  const g = r.geometry;
  fail(!!g && g.selfCheck === true, 'Geometry replay failed or missing');
  fail(r.warpModeUsed === 'spherical' && !r.fellBackToCylindrical && g?.projection === 'spherical',
    'Cylindrical or fallback output cannot be passed directly to Pannellum');
  const c = r.strips[0]?.coverage;
  fail(!!c && finite(c.coveredDeg) && c.coveredDeg >= 359.99 && c.holes.length === 0,
    'Estimated camera footprint coverage is incomplete');
  let angles = null;
  if (g && finite(g.warpScale) && g.warpScale > 0 &&
      [g.output.sx,g.output.sy].every(v => finite(v) && v>0) &&
      [g.output.tx,g.output.ty,g.origin.x,g.origin.y].every(finite) &&
      Number.isInteger(r.width) && Number.isInteger(r.height) && r.width>=512 && r.height>=2 &&
      r.width*r.height <= 32_000_000) {
    const deg = 180 / Math.PI;
    const haov = r.width / g.output.sx / g.warpScale * deg; // DO NOT cap to 360.
    const vaov = r.height / g.output.sy / g.warpScale * deg;
    const top = 90 - ((-g.output.ty)/g.output.sy + g.origin.y)/g.warpScale*deg;
    angles = { haov, vaov, vOffset: top-vaov/2, source: 'OpenCV fitted geometry; not measured calibration' };
    fail(Math.abs(haov-360) <= 360/r.width, 'Canvas is not exactly one horizontal period within one pixel');
    fail(vaov>=20 && vaov<180 && top<=90 && top-vaov>=-90, 'Invalid limited vertical field');
    fail(Math.abs(r.width*vaov/360-r.height)<=2, 'Pixels have incompatible horizontal/vertical angular scales');
  } else reasons.push('Invalid canvas geometry or dimensions');
  return {
    diagnosticPrerequisitesPass: reasons.length === 0, reasons, fittedAngles: angles,
    accepted360: false, pannellumReady: false,
    pending: ['Measured camera calibration and reference pitch', 'Independent raw turn and closing-image feature evidence',
      'Per-pixel source-mask coverage and valid full-width vertical crop',
      'Encoded JPEG wrap/overlap quality and manual visual validation'],
  };
}
