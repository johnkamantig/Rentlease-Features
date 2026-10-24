import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  mapSearchNearbyListingsRpcResponse, parseSearchNearbyListingsRpcRows,
  toSearchNearbyListingsRpcParams,
} from '../rpc/index.ts';
import { RPC_LISTINGS } from './fixtures/rpc-listings.ts';

const validRow = RPC_LISTINGS[0]!;

test('RPC parameters use exact names and resolve established defaults', () => {
  assert.deepEqual(toSearchNearbyListingsRpcParams({ latitude: 14.43, longitude: 120.94, ignored: true }), {
    p_latitude: 14.43, p_longitude: 120.94, p_radius_km: 3, p_limit: 20, p_offset: 0,
  });
  assert.deepEqual(toSearchNearbyListingsRpcParams({ latitude: -90, longitude: 180, radiusKm: 5, limit: 50, offset: 1000 }), {
    p_latitude: -90, p_longitude: 180, p_radius_km: 5, p_limit: 50, p_offset: 1000,
  });
  for (const radiusKm of [1, 3, 5]) {
    assert.equal(toSearchNearbyListingsRpcParams({ latitude: 0, longitude: 0, radiusKm, limit: 1, offset: 0 }).p_radius_km, radiusKm);
  }
});

test('RPC parameter adapter reuses strict validation with no coercion', () => {
  for (const input of [null, {}, [], { latitude: '0', longitude: 0 }, { latitude: 91, longitude: 0 }, { latitude: 0, longitude: Infinity }]) {
    assert.throws(() => toSearchNearbyListingsRpcParams(input));
  }
  for (const [field, values] of Object.entries({ radiusKm: [0, 2, 4, 6, null, '3'], limit: [0, 51, 1.5, null, '20'], offset: [-1, 1001, 0.5, null, '0'] })) {
    for (const value of values) assert.throws(() => toSearchNearbyListingsRpcParams({ latitude: 0, longitude: 0, [field]: value }));
  }
});

test('RPC response maps every established field explicitly', () => {
  assert.deepEqual(mapSearchNearbyListingsRpcResponse([validRow]), [{
    listingId: validRow.listing_id,
    propertyId: validRow.property_id,
    title: 'Synthetic Imus rental',
    askingRentMonthly: '12345.678901234567890123456789',
    propertyType: 'synthetic-apartment',
    city: 'Imus',
    barangay: null,
    availableFrom: '2028-02-29',
    publicLocation: { latitude: 14.43, longitude: 120.94 },
    distanceMeters: '102.12345678901234567890123456789',
  }]);
});

test('RPC parser returns copied SQL-shaped rows and ignores undocumented fields', () => {
  const input = { ...validRow, unexpected: 'omit me' };
  const parsed = parseSearchNearbyListingsRpcRows([input]);
  assert.deepEqual(parsed, [validRow]);
  assert.notEqual(parsed[0], input);
  assert.equal('unexpected' in mapSearchNearbyListingsRpcResponse([input])[0]!, false);
});

test('RPC descriptive fields, rent, and availability may be explicitly null', () => {
  const nullable = { ...validRow, title: null, asking_rent_monthly: null, property_type: null, city: null, barangay: null, available_from: null };
  assert.deepEqual(parseSearchNearbyListingsRpcRows([nullable]), [nullable]);
  const mapped = mapSearchNearbyListingsRpcResponse([nullable])[0]!;
  for (const field of ['title', 'askingRentMonthly', 'propertyType', 'city', 'barangay', 'availableFrom'] as const) {
    assert.equal(mapped[field], null);
  }
});

test('RPC rows must contain every documented field, including nullable fields', () => {
  for (const field of Object.keys(validRow)) {
    const row: Record<string, unknown> = { ...validRow };
    delete row[field];
    assert.throws(() => parseSearchNearbyListingsRpcRows([row]), field);
  }
});

test('RPC requires identifiers, public coordinates, and distance to be nonnull', () => {
  for (const field of ['listing_id', 'property_id', 'public_latitude', 'public_longitude', 'distance_meters']) {
    assert.throws(() => mapSearchNearbyListingsRpcResponse([{ ...validRow, [field]: null }]), field);
  }
});

test('RPC descriptive fields reject nonstring nonnull values', () => {
  for (const field of ['title', 'property_type', 'city', 'barangay']) {
    for (const value of [undefined, 42, true, {}, []]) {
      assert.throws(() => parseSearchNearbyListingsRpcRows([{ ...validRow, [field]: value }]));
    }
  }
});

test('RPC IDs accept UUID shape without version restrictions or normalization', () => {
  const row = { ...validRow, listing_id: 'ABCDEFAB-0000-0000-0000-000000000000', property_id: '00000000-0000-0000-0000-000000000000' };
  assert.deepEqual(parseSearchNearbyListingsRpcRows([row]), [row]);
});

test('RPC UUID identifiers reject malformed and wrong-type values', () => {
  for (const field of ['listing_id', 'property_id']) {
    for (const value of ['', 'a', 'aaaaaaaa000040008000000000000001', 'gggggggg-0000-4000-8000-000000000001', ` ${validRow.listing_id}`, `${validRow.listing_id}\n`, 1, [], {}]) {
      assert.throws(() => mapSearchNearbyListingsRpcResponse([{ ...validRow, [field]: value }]));
    }
  }
});

test('RPC duplicate listing UUIDs are rejected case-insensitively; shared property IDs are allowed', () => {
  assert.throws(() => parseSearchNearbyListingsRpcRows([validRow, { ...validRow }]), /unique/);
  assert.throws(() => mapSearchNearbyListingsRpcResponse([validRow, { ...validRow, listing_id: validRow.listing_id.toUpperCase() }]), /unique/);
  assert.equal(mapSearchNearbyListingsRpcResponse(RPC_LISTINGS).length, 2);
});

test('RPC public coordinates validate inclusive geographic endpoints', () => {
  for (const [latitude, longitude] of [[-90, -180], [90, 180], [0, 0]]) {
    assert.deepEqual(mapSearchNearbyListingsRpcResponse([{ ...validRow, public_latitude: latitude, public_longitude: longitude }])[0]!.publicLocation, { latitude, longitude });
  }
});

test('RPC public coordinates reject out-of-range, nonfinite, and nonnumeric inputs', () => {
  for (const [field, invalids] of Object.entries({
    public_latitude: [-90.1, 90.1, NaN, Infinity, -Infinity, '14.43', true, {}],
    public_longitude: [-180.1, 180.1, NaN, Infinity, -Infinity, '120.94', false, []],
  })) {
    for (const invalid of invalids) assert.throws(() => mapSearchNearbyListingsRpcResponse([{ ...validRow, [field]: invalid }]));
  }
});

test('RPC calendar dates preserve leap days and boundary years without timezone conversion', () => {
  for (const date of ['0001-01-01', '2000-02-29', '2024-02-29', '2026-04-30', '9999-12-31']) {
    assert.equal(mapSearchNearbyListingsRpcResponse([{ ...validRow, available_from: date }])[0]!.availableFrom, date);
  }
});

test('RPC dates reject impossible days, non-leap centuries, timestamps, and unsupported formats', () => {
  for (const date of ['0000-01-01', '1900-02-29', '2100-02-29', '2026-02-29', '2026-04-31', '2026-00-01', '2026-13-01', '2026-01-00', '2026-01-32', '2026-1-01', '2026-01-01\n', '2026-01-01T00:00:00Z', '10000-01-01', 'infinity', '', 123, {}]) {
    assert.throws(() => parseSearchNearbyListingsRpcRows([{ ...validRow, available_from: date }]), String(date));
  }
});

test('RPC numeric values and well-formed decimal strings retain their exact representation', () => {
  for (const value of [0, -0, 123.45, Number.MAX_VALUE, Number.MIN_VALUE, '0', '+01.2300', '.5', '1.', '1e3', '1E+3', '1e-9999', '1e9999', '90071992547409931234567890.12345678901234567890']) {
    const mapped = mapSearchNearbyListingsRpcResponse([{ ...validRow, asking_rent_monthly: value, distance_meters: value }])[0]!;
    assert.equal(mapped.askingRentMonthly, value);
    assert.equal(mapped.distanceMeters, value);
  }
});

test('RPC numeric validation rejects nonfinite numbers and malformed strings', () => {
  for (const field of ['asking_rent_monthly', 'distance_meters']) {
    for (const value of [NaN, Infinity, -Infinity, '', ' ', ' 1', '1 ', '1\n', '1\r', '1\r\n', '1\u2028', 'NaN', 'Infinity', '-Infinity', '0x10', '1_000', '1,000', '.', '+', '--1', '1e', '1e+', '1.2.3', '1eInfinity', true, [], {}]) {
      assert.throws(() => parseSearchNearbyListingsRpcRows([{ ...validRow, [field]: value }]), `${field}: ${String(value)}`);
    }
  }
});

test('RPC negative distances are rejected without underflow or rounding loopholes', () => {
  for (const value of [-1, -Number.MIN_VALUE, '-1', '-0.00000000000000000000000001', '-1e-99999', '-.01', '-001e+99999']) {
    assert.throws(() => mapSearchNearbyListingsRpcResponse([{ ...validRow, distance_meters: value }]), RangeError);
  }
  for (const value of ['-0', '-0.000', '-0e9999']) {
    assert.equal(mapSearchNearbyListingsRpcResponse([{ ...validRow, distance_meters: value }])[0]!.distanceMeters, value);
  }
});

test('RPC adapter does not add rent eligibility rules', () => {
  for (const value of [-1, '-1.25', null]) {
    assert.equal(mapSearchNearbyListingsRpcResponse([{ ...validRow, asking_rent_monthly: value }])[0]!.askingRentMonthly, value);
  }
});

test('RPC mapping preserves server order and distances without applying local search', () => {
  const rows = [
    { ...RPC_LISTINGS[1]!, distance_meters: '99999.1234567890123456789', public_latitude: 0, public_longitude: 0 },
    { ...validRow, distance_meters: '0.1', public_latitude: 0, public_longitude: 0 },
  ];
  const results = mapSearchNearbyListingsRpcResponse(rows);
  assert.deepEqual(results.map(row => row.listingId), rows.map(row => row.listing_id));
  assert.deepEqual(results.map(row => row.distanceMeters), rows.map(row => row.distance_meters));
});

test('RPC adapter preserves equal-distance server order instead of sorting by listing ID', () => {
  const rows = [{ ...RPC_LISTINGS[1]!, distance_meters: 10 }, { ...validRow, distance_meters: 10 }];
  assert.deepEqual(mapSearchNearbyListingsRpcResponse(rows).map(row => row.listingId), rows.map(row => row.listing_id));
});

test('RPC adapter does not impose local pagination on a response', () => {
  const rows = Array.from({ length: 55 }, (_, index) => ({
    ...validRow, listing_id: `aaaaaaaa-0000-4000-8000-${String(index).padStart(12, '0')}`,
  }));
  assert.equal(mapSearchNearbyListingsRpcResponse(rows).length, 55);
});

test('RPC accepts empty data arrays but rejects null data and malformed envelopes', () => {
  assert.deepEqual(parseSearchNearbyListingsRpcRows([]), []);
  assert.deepEqual(mapSearchNearbyListingsRpcResponse([]), []);
  for (const value of [null, undefined, {}, '[]', { data: [], error: null }]) {
    assert.throws(() => mapSearchNearbyListingsRpcResponse(value), TypeError);
  }
  for (const value of [null, undefined, [], 'row', 0, {}]) {
    assert.throws(() => mapSearchNearbyListingsRpcResponse([value]), TypeError);
  }
});

test('RPC rejects a malformed later row instead of returning partial data', () => {
  assert.throws(() => mapSearchNearbyListingsRpcResponse([validRow, { ...RPC_LISTINGS[1]!, title: 1 }]), TypeError);
});

test('RPC adapters preserve frozen inputs and return independent records', () => {
  const source = structuredClone(RPC_LISTINGS);
  const before = structuredClone(source);
  source.forEach(Object.freeze);
  Object.freeze(source);
  const parsed = parseSearchNearbyListingsRpcRows(source);
  const mapped = mapSearchNearbyListingsRpcResponse(source);
  assert.deepEqual(source, before);
  assert.notEqual(parsed[0], source[0]);
  assert.notEqual(mapped[0], source[0]);
  assert.notEqual(mapped[0]!.publicLocation, mapped[1]!.publicLocation);
  const options = Object.freeze({ latitude: 14.43, longitude: 120.94 });
  toSearchNearbyListingsRpcParams(options);
  assert.deepEqual(options, { latitude: 14.43, longitude: 120.94 });
});

test('RPC validation errors do not echo response values', () => {
  assert.throws(() => mapSearchNearbyListingsRpcResponse([{ ...validRow, listing_id: 'synthetic-invalid-id' }]), error => {
    assert.ok(error instanceof TypeError);
    assert.equal(error.message.includes('synthetic-invalid-id'), false);
    return true;
  });
});
