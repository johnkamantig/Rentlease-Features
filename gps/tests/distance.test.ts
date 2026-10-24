import assert from 'node:assert/strict';
import { test } from 'node:test';
import { EARTH_RADIUS_METERS, haversineDistanceMeters } from '../index.ts';
import type { Coordinates } from '../index.ts';

function close(actual: number, expected: number, tolerance = 0.000001): void {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} differs from ${expected}`);
}

test('one equatorial degree has the independently tabulated spherical distance', () => {
  close(haversineDistanceMeters({ latitude: 0, longitude: 0 }, { latitude: 0, longitude: 1 }), 111_195.080233533, 0.000001);
});

test('identical coordinates return exactly zero', () => {
  for (const point of [{ latitude: 14.43, longitude: 120.94 }, { latitude: 0, longitude: 0 }, { latitude: -90, longitude: 180 }]) {
    assert.equal(haversineDistanceMeters(point, point), 0);
  }
});

test('distance is symmetric and handles both hemispheres', () => {
  const a = { latitude: -33.9, longitude: -70.7 };
  const b = { latitude: 14.43, longitude: 120.94 };
  const forward = haversineDistanceMeters(a, b);
  close(forward, haversineDistanceMeters(b, a));
  assert.ok(forward > 0 && forward <= Math.PI * EARTH_RADIUS_METERS);
});

test('antimeridian crossing takes the short route', () => {
  close(haversineDistanceMeters({ latitude: 0, longitude: 179.9 }, { latitude: 0, longitude: -179.9 }), 22_239.0160467066);
  close(haversineDistanceMeters({ latitude: 0, longitude: 180 }, { latitude: 0, longitude: -180 }), 0);
});

test('poles are independent of longitude and opposite poles span half the sphere', () => {
  close(haversineDistanceMeters({ latitude: 90, longitude: -120 }, { latitude: 90, longitude: 80 }), 0);
  close(haversineDistanceMeters({ latitude: -90, longitude: 10 }, { latitude: -90, longitude: 170 }), 0);
  close(haversineDistanceMeters({ latitude: 90, longitude: 0 }, { latitude: -90, longitude: 0 }), 20_015_114.442035925);
});

test('antipodal and nearly antipodal distances remain finite', () => {
  close(haversineDistanceMeters({ latitude: 0, longitude: 0 }, { latitude: 0, longitude: 180 }), Math.PI * EARTH_RADIUS_METERS);
  for (const point of [{ latitude: 0.000001, longitude: 179.999999 }, { latitude: -45.0000001, longitude: -170 }]) {
    const from = point.longitude < 0 ? { latitude: 45, longitude: 10 } : { latitude: 0, longitude: 0 };
    const distance = haversineDistanceMeters(from, point);
    assert.ok(Number.isFinite(distance));
    close(distance, Math.PI * EARTH_RADIUS_METERS, 1);
  }
});

test('very short distances retain submeter precision', () => {
  const distance = haversineDistanceMeters({ latitude: 0, longitude: 0 }, { latitude: 0.000000001, longitude: 0 });
  close(distance, 0.000111195080233533, 1e-12);
});

test('distance validates both endpoints at runtime', () => {
  const valid = { latitude: 0, longitude: 0 };
  for (const invalid of [null, {}, { latitude: NaN, longitude: 0 }, { latitude: 91, longitude: 0 }]) {
    assert.throws(() => haversineDistanceMeters(invalid as Coordinates, valid));
    assert.throws(() => haversineDistanceMeters(valid, invalid as Coordinates));
  }
});
