import assert from 'node:assert/strict';
import { test } from 'node:test';
import { EARTH_RADIUS_METERS } from '../index.ts';
import { searchNearbyListings } from '../local.ts';
import type { RentalListing, SearchOptions } from '../local.ts';
import { MOCK_LISTINGS, SYNTHETIC_TENANT_LOCATIONS } from './fixtures/mock-properties.ts';

const origin = { latitude: 0, longitude: 0 };

// Analytic meridian arc inversion, independent of the implementation under test.
function listingAt(meters: number, listingId: string, propertyId = 'shared-property'): RentalListing {
  return {
    listing_id: listingId,
    property_id: propertyId,
    public_location: { latitude: meters / EARTH_RADIUS_METERS * 180 / Math.PI, longitude: 0 },
  };
}

for (const radiusKm of [1, 3, 5] as const) {
  test(`${radiusKm} km includes the boundary and excludes points beyond numerical tolerance`, () => {
    const meters = radiusKm * 1000;
    const records = [listingAt(meters + 0.001, 'outside'), listingAt(meters, 'boundary'), listingAt(meters - 0.001, 'inside')];
    assert.deepEqual(searchNearbyListings(records, { ...origin, radiusKm }).map(item => item.listing_id), ['inside', 'boundary']);
  });
}

test('search uses a documented one-micrometer boundary tolerance', () => {
  const results = searchNearbyListings([listingAt(1000 + 0.0000005, 'roundoff'), listingAt(1000 + 0.000002, 'outside')], { ...origin, radiusKm: 1 });
  assert.deepEqual(results.map(item => item.listing_id), ['roundoff']);
});

for (const city of ['imus', 'dasmarinas', 'tagaytay'] as const) {
  test(`synthetic ${city} listings filter locally and sort nearest first`, () => {
    const coordinates = SYNTHETIC_TENANT_LOCATIONS[city];
    const near = searchNearbyListings(MOCK_LISTINGS, { ...coordinates, radiusKm: 1 });
    assert.deepEqual(near.map(item => item.listing_id), [`${city}-near`]);
    const wider = searchNearbyListings(MOCK_LISTINGS, coordinates);
    assert.deepEqual(wider.map(item => item.listing_id), city === 'imus'
      ? ['imus-near', 'imus-middle', 'imus-far'] : [`${city}-near`, `${city}-far`]);
    assert.ok(wider.every((item, index) => index === 0 || item.distanceMeters >= wider[index - 1]!.distanceMeters));
  });
}

test('equal distances use listing_id, not property_id or input order', () => {
  const records = [listingAt(100, 'b', 'a'), listingAt(100, 'a', 'z')];
  assert.deepEqual(searchNearbyListings(records, origin).map(item => item.listing_id), ['a', 'b']);
  assert.deepEqual(searchNearbyListings([...records].reverse(), origin).map(item => item.listing_id), ['a', 'b']);
});

test('unrounded distances take precedence over listing IDs', () => {
  const result = searchNearbyListings([listingAt(10.0005, 'a'), listingAt(10.0004, 'z')], origin);
  assert.deepEqual(result.map(item => item.listing_id), ['z', 'a']);
  assert.ok(result[0]!.distanceMeters < result[1]!.distanceMeters);
});

test('empty input, no matches, and exhausted offsets return empty arrays', () => {
  assert.deepEqual(searchNearbyListings([], origin), []);
  assert.deepEqual(searchNearbyListings(MOCK_LISTINGS, origin), []);
  assert.deepEqual(searchNearbyListings([listingAt(10, 'a')], { ...origin, offset: 1 }), []);
  assert.deepEqual(searchNearbyListings([listingAt(10, 'a')], { ...origin, offset: 1000 }), []);
});

test('pagination happens after filtering and sorting', () => {
  const records = [listingAt(6000, 'outside'), listingAt(300, 'c'), listingAt(200, 'b'), listingAt(100, 'a')];
  assert.deepEqual(searchNearbyListings(records, { ...origin, limit: 1, offset: 1 }).map(item => item.listing_id), ['b']);
  assert.deepEqual(searchNearbyListings(records, { ...origin, limit: 50, offset: 2 }).map(item => item.listing_id), ['c']);
});

test('default pagination returns 20 nearest records and accepts a limit of 50', () => {
  const records = Array.from({ length: 55 }, (_, index) => listingAt(55 - index, `listing-${index}`));
  const first = searchNearbyListings(records, origin);
  assert.equal(first.length, 20);
  assert.equal(first[0]!.listing_id, 'listing-54');
  assert.equal(first[19]!.listing_id, 'listing-35');
  assert.equal(searchNearbyListings(records, { ...origin, limit: 50 }).length, 50);
});

test('frozen inputs are unchanged and results do not alias input records or coordinates', () => {
  const source = [listingAt(200, 'b'), listingAt(100, 'a')];
  const snapshot = structuredClone(source);
  for (const item of source) { Object.freeze(item.public_location); Object.freeze(item); }
  Object.freeze(source);
  const options = Object.freeze({ ...origin, limit: 1 });
  const results = searchNearbyListings(source, options);
  assert.deepEqual(source, snapshot);
  assert.deepEqual(options, { ...origin, limit: 1 });
  assert.notEqual(results[0], source[1]);
  assert.notEqual(results[0]!.public_location, source[1]!.public_location);
});

test('duplicate listing identifiers are rejected even outside the radius or selected page', () => {
  assert.throws(() => searchNearbyListings([listingAt(10, 'same'), listingAt(6000, 'same')], { ...origin, limit: 1 }), /unique/);
  assert.throws(() => searchNearbyListings([listingAt(6000, 'same'), listingAt(7000, 'same')], origin), /unique/);
});

test('distinct listings may share one property', () => {
  assert.equal(searchNearbyListings([listingAt(10, 'a'), listingAt(20, 'b')], origin).length, 2);
});

test('invalid listing coordinates are rejected even after the requested page is filled', () => {
  for (const publicLocation of [null, {}, { latitude: 91, longitude: 0 }, { latitude: 0, longitude: 181 }, { latitude: '0', longitude: 0 }, { latitude: Infinity, longitude: 0 }]) {
    const invalid = { ...listingAt(10, 'bad'), public_location: publicLocation } as RentalListing;
    assert.throws(() => searchNearbyListings([listingAt(0, 'valid'), invalid], { ...origin, limit: 1 }));
  }
});

test('invalid listing containers and identifiers fail explicitly', () => {
  for (const invalid of [null, {}, 'listings']) {
    assert.throws(() => searchNearbyListings(invalid as unknown as RentalListing[], origin), TypeError);
  }
  for (const invalid of [null, [], undefined, {}, { ...listingAt(0, 'a'), listing_id: '' }, { ...listingAt(0, 'a'), listing_id: 1 }, { ...listingAt(0, 'a'), property_id: ' ' }]) {
    assert.throws(() => searchNearbyListings([invalid] as RentalListing[], origin), TypeError);
  }
});

test('public search validates options even when there are no listings', () => {
  for (const options of [{ ...origin, limit: 0 }, { ...origin, offset: 1001 }, { ...origin, radiusKm: 2 }, { latitude: NaN, longitude: 0 }]) {
    assert.throws(() => searchNearbyListings([], options as SearchOptions));
  }
});
