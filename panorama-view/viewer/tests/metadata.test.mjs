import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { validateMetadata, validateImageBytes, viewerConfig, fovBounds } from '../metadata.mjs';

const original = JSON.parse(await readFile(new URL('../fixtures/synthetic.json', import.meta.url)));
const jpeg = await readFile(new URL('../fixtures/synthetic.jpg', import.meta.url));
const ref = JSON.parse(await readFile(new URL('../fixtures/reference.json', import.meta.url)));
const clone = () => structuredClone(original);

test('Phase 2 angles map exactly to Pannellum without XMP overrides', () => {
  const g = validateMetadata(original);
  const c = viewerConfig(g, 'blob:local', 1000, 600);
  assert.equal(c.haov, original.horizontal_coverage_deg);
  assert.equal(c.vaov, original.vertical_coverage_deg);
  assert.equal(c.vOffset, original.vertical_offset_deg);
  assert.equal(c.maxYaw - c.minYaw, 360);
  assert.equal(c.maxPitch - c.minPitch, c.vaov);
  assert.equal(c.ignoreGPanoXMP, true);
  assert.equal(c.avoidShowingBackground, true);
});
test('bundled mathematical reference has an explicit separate provenance', () => {
  assert.equal(validateMetadata(ref, { reference: true }).vaov, 180);
  assert.throws(() => validateMetadata(ref), /not been verified/);
});
test('actual original JPEG SHA-256 and byte count pass', async () => {
  await validateImageBytes(jpeg, original);
});
for (const field of ['horizontal_coverage_deg', 'vertical_coverage_deg', 'vertical_offset_deg', 'sha256', 'vertical_calibration']) {
  test(`missing ${field} is rejected without a default`, () => {
    const m = clone(); delete m[field];
    assert.throws(() => validateMetadata(m));
  });
}
for (const [field, value] of [
  ['horizontal_coverage_deg', 180], ['vertical_coverage_deg', '68.67'], ['vertical_offset_deg', NaN],
  ['vertical_coverage_deg', 0], ['vertical_offset_deg', 89], ['closure_verified', false],
  ['coverage_validation_status', 'incomplete'], ['width_px', 1234], ['bytes', 9_500_000],
  ['schema_version', 2], ['projection', 'flat'], ['input_count', 2],
]) {
  test(`invalid ${field} (${value}) is rejected`, () => {
    const m = clone(); m[field] = value;
    assert.throws(() => validateMetadata(m));
  });
}
test('missing camera evidence, missing pixels and failing seam are rejected', () => {
  const m = clone(); m.diagnostics.raw_turn_deg = 180;
  assert.throws(() => validateMetadata(m), /revolution/);
  const n = clone(); n.projection_diagnostics.source_mask_coverage_fraction = .99;
  assert.throws(() => validateMetadata(n), /incomplete/);
  const p = clone(); p.jpeg_seam_diagnostics.wrap_mean_absolute_difference = 255;
  assert.throws(() => validateMetadata(p), /seam/);
});
test('tampered image and non-JPEG are rejected', async () => {
  const tampered = Buffer.from(jpeg); tampered[500] ^= 1;
  await assert.rejects(validateImageBytes(tampered, original), /SHA-256/);
  await assert.rejects(validateImageBytes(Buffer.alloc(jpeg.length), original), /not a JPEG/);
  await assert.rejects(validateImageBytes(jpeg.subarray(1), original), /byte count/);
});
test('untrusted viewer configuration is never merged', () => {
  const m = clone(); Object.assign(m, { hotSpots: [{}], minYaw: 0, panorama: 'https://example.invalid/photo.jpg' });
  const c = viewerConfig(validateMetadata(m), 'blob:local', 900, 500);
  assert.equal(c.hotSpots, undefined);
  assert.equal(c.panorama, 'blob:local');
  assert.equal(c.minYaw, -180);
});
for (const [w, h] of [[1100, 600], [390, 600], [320, 900], [900, 300]]) {
  test(`viewport ${w}x${h} fits inside the real vertical coverage`, () => {
    const g = validateMetadata(original);
    const [min, max] = fovBounds(g, w, h);
    const vfov = 2 * Math.atan(Math.tan(max * Math.PI / 360) * h / w) * 180 / Math.PI;
    assert.ok(min > 0 && min < max);
    assert.ok(vfov < g.vaov);
  });
}
