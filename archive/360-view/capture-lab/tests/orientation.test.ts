import { test } from 'node:test';
import assert from 'node:assert/strict';
import { angleDelta, estimateOrientation, freshReading, wrap } from '../src/orientation';
import { validOrientation } from '../src/domain';

test('upright rear-camera estimate uses magnetic north and gravity', () => {
  const reading = estimateOrientation({ x: 0, y: 1, z: 0 }, { x: 0, y: 20, z: -40 });
  assert.equal(reading.headingDegrees, 0);
  assert.equal(Math.abs(reading.elevationDegrees!), 0);
  assert.equal(reading.source, 'accelerometer+magnetometer');
  assert.equal(reading.alignmentValidated, false);
  assert.ok(validOrientation(reading));
});
test('heading respects Android portrait device axes for rear camera', () => {
  const reading = estimateOrientation({ x: 0, y: 1, z: 0 }, { x: -40, y: 20, z: 0 });
  assert.equal(reading.headingDegrees, 90);
});
test('ceiling and floor retain tilt but omit undefined pole heading', () => {
  const floor = estimateOrientation({ x: 0, y: 0, z: 1 }, { x: 0, y: 40, z: 20 });
  const ceiling = estimateOrientation({ x: 0, y: 0, z: -1 }, { x: 0, y: 40, z: 20 });
  assert.equal(floor.elevationDegrees, -90);
  assert.equal(ceiling.elevationDegrees, 90);
  assert.equal(floor.headingDegrees, null);
  assert.equal(ceiling.headingDegrees, null);
});
test('missing magnetometer degrades to tilt only', () => {
  const reading = estimateOrientation({ x: 0, y: 1, z: 0 }, null);
  assert.equal(reading.source, 'accelerometer');
  assert.equal(reading.headingDegrees, null);
  assert.equal(Math.abs(reading.elevationDegrees!), 0);
});
test('missing accelerometer never invents orientation', () => {
  const reading = estimateOrientation(null, { x: 0, y: 20, z: -40 });
  assert.equal(reading.source, 'unavailable');
  assert.equal(reading.elevationDegrees, null);
  assert.equal(reading.headingDegrees, null);
});
test('invalid or moving gravity readings disable the estimate', () => {
  for (const gravity of [{ x: 0, y: 0, z: 0 }, { x: NaN, y: 1, z: 0 }, { x: 0, y: 2, z: 0 }]) {
    const reading = estimateOrientation(gravity, { x: 0, y: 20, z: -40 });
    assert.equal(reading.headingDegrees, null);
    assert.equal(reading.elevationDegrees, null);
  }
});
test('magnetic anomalies and vertical fields disable heading', () => {
  for (const magnetic of [{ x: 0, y: 0, z: 0 }, { x: 400, y: 0, z: 0 }, { x: 0, y: 40, z: 0 }, { x: NaN, y: 0, z: 0 }]) {
    assert.equal(estimateOrientation({ x: 0, y: 1, z: 0 }, magnetic).headingDegrees, null);
  }
});
test('wrap and shortest turn handle the north boundary', () => {
  assert.equal(wrap(-10), 350);
  assert.equal(wrap(370), 10);
  assert.equal(angleDelta(1, 359), 2);
  assert.equal(angleDelta(359, 1), -2);
});
test('stale, future, and absent readings are not attached to a shutter request', () => {
  const time = Date.parse('2026-10-25T08:00:00Z');
  const reading = estimateOrientation({ x: 0, y: 1, z: 0 }, null, new Date(time).toISOString());
  assert.equal(freshReading(reading, time + 1500), reading);
  assert.equal(freshReading(reading, time + 1501), null);
  assert.equal(freshReading(reading, time - 1), null);
  assert.equal(freshReading(null, time), null);
});
