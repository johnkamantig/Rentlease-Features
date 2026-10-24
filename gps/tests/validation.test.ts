import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  validateCoordinates, validatePagination, validateRadiusKm, validateSearchOptions,
} from '../index.ts';

test('coordinates accept inclusive endpoints, zero, and ordinary locations', () => {
  for (const coordinates of [
    { latitude: -90, longitude: -180 },
    { latitude: 90, longitude: 180 },
    { latitude: 0, longitude: 0 },
    { latitude: 14.43, longitude: 120.94 },
  ]) {
    const result = validateCoordinates(coordinates);
    assert.deepEqual(result, coordinates);
    assert.notEqual(result, coordinates);
  }
});

for (const field of ['latitude', 'longitude'] as const) {
  for (const invalid of [undefined, null, '14.43', '', true, {}, [], NaN, Infinity, -Infinity]) {
    test(`${field} rejects ${String(invalid)} (${typeof invalid})`, () => {
      assert.throws(() => validateCoordinates({ latitude: 0, longitude: 0, [field]: invalid }), TypeError);
    });
  }
}

test('coordinates reject objects with missing fields and invalid containers', () => {
  for (const invalid of [undefined, null, [], '0,0', 0, {}, { latitude: 0 }, { longitude: 0 }]) {
    assert.throws(() => validateCoordinates(invalid), TypeError);
  }
});

test('coordinates reject values immediately beyond allowed ranges', () => {
  for (const latitude of [-90.000001, 90.000001]) {
    assert.throws(() => validateCoordinates({ latitude, longitude: 0 }), RangeError);
  }
  for (const longitude of [-180.000001, 180.000001]) {
    assert.throws(() => validateCoordinates({ latitude: 0, longitude }), RangeError);
  }
});

test('radius accepts only 1, 3, 5 and defaults to 3', () => {
  for (const radius of [1, 3, 5]) assert.equal(validateRadiusKm(radius), radius);
  assert.equal(validateRadiusKm(), 3);
  assert.equal(validateRadiusKm(undefined), 3);
});

test('radius rejects unsupported numbers and nonnumbers without coercion', () => {
  for (const radius of [0, -1, 2, 4, 6, 1.5]) {
    assert.throws(() => validateRadiusKm(radius), RangeError);
  }
  for (const radius of [null, '3', '', true, {}, [], NaN, Infinity, -Infinity]) {
    assert.throws(() => validateRadiusKm(radius), TypeError);
  }
});

test('pagination defaults and inclusive bounds match the contract', () => {
  assert.deepEqual(validatePagination(), { limit: 20, offset: 0 });
  assert.deepEqual(validatePagination(undefined, undefined), { limit: 20, offset: 0 });
  assert.deepEqual(validatePagination(1, 0), { limit: 1, offset: 0 });
  assert.deepEqual(validatePagination(50, 1000), { limit: 50, offset: 1000 });
});

test('pagination rejects zero limit, fractions, and out-of-range values', () => {
  for (const limit of [-1, 0, 1.5, 50.1, 51, Number.MAX_SAFE_INTEGER]) {
    assert.throws(() => validatePagination(limit), RangeError);
  }
  for (const offset of [-1, 0.5, 1000.1, 1001, Number.MAX_SAFE_INTEGER]) {
    assert.throws(() => validatePagination(20, offset), RangeError);
  }
});

test('pagination rejects nonnumbers and nonfinite numbers', () => {
  for (const invalid of [null, '20', true, {}, [], NaN, Infinity, -Infinity]) {
    assert.throws(() => validatePagination(invalid), TypeError);
    assert.throws(() => validatePagination(20, invalid), TypeError);
  }
});

test('search options resolve defaults and preserve explicit settings', () => {
  assert.deepEqual(validateSearchOptions({ latitude: 0, longitude: 0 }), {
    latitude: 0, longitude: 0, radiusKm: 3, limit: 20, offset: 0,
  });
  const options = { latitude: 14.43, longitude: 120.94, radiusKm: 5, limit: 50, offset: 1000 };
  assert.deepEqual(validateSearchOptions(options), options);
  for (const invalid of [null, [], undefined, {}]) {
    assert.throws(() => validateSearchOptions(invalid), TypeError);
  }
});
