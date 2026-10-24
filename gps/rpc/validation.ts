import { validateCoordinates } from '../validation.ts';
import type { RpcNumeric, ValidatedSearchNearbyListingsRpcRow } from './types.ts';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function uuid(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.length !== 36 || !UUID.test(value)) {
    throw new TypeError(`${field} must be a UUID-shaped string`);
  }
  return value;
}

function nullableText(value: unknown, field: string): string | null {
  if (value !== null && typeof value !== 'string') {
    throw new TypeError(`${field} must be a string or null`);
  }
  return value;
}

function numeric(value: unknown, field: string, nonnegative = false): RpcNumeric {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError(`${field} must be finite`);
    if (nonnegative && value < 0) throw new RangeError(`${field} must be nonnegative`);
    return value;
  }
  // `$` alone also matches before a final newline; reject surrounding whitespace.
  if (typeof value !== 'string' || value.trim() !== value || !DECIMAL.test(value)) {
    throw new TypeError(`${field} must be a finite number or decimal string`);
  }
  // Inspect the coefficient, never Number(value): extreme exponents can overflow
  // or underflow JavaScript numbers while still denoting finite SQL numerics.
  const coefficient = value.split(/[eE]/, 1)[0]!;
  if (nonnegative && coefficient.startsWith('-') && /[1-9]/.test(coefficient)) {
    throw new RangeError(`${field} must be nonnegative`);
  }
  return value;
}

function calendarDate(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value !== 'string' || value.length !== 10 || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new TypeError('available_from must be a YYYY-MM-DD string or null');
  }
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1]!) {
    throw new RangeError('available_from must be a valid calendar date in years 0001–9999');
  }
  return value;
}

function parseRow(value: unknown): ValidatedSearchNearbyListingsRpcRow {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new TypeError('each RPC row must be an object');
  }
  const row = value as Record<string, unknown>;
  const location = validateCoordinates({ latitude: row.public_latitude, longitude: row.public_longitude });
  return {
    listing_id: uuid(row.listing_id, 'listing_id'),
    property_id: uuid(row.property_id, 'property_id'),
    title: nullableText(row.title, 'title'),
    asking_rent_monthly: row.asking_rent_monthly === null ? null : numeric(row.asking_rent_monthly, 'asking_rent_monthly'),
    property_type: nullableText(row.property_type, 'property_type'),
    city: nullableText(row.city, 'city'),
    barangay: nullableText(row.barangay, 'barangay'),
    available_from: calendarDate(row.available_from),
    public_latitude: location.latitude,
    public_longitude: location.longitude,
    distance_meters: numeric(row.distance_meters, 'distance_meters', true),
  };
}

/** Validate a complete RPC data array without coercion, reordering, or omission. */
export function parseSearchNearbyListingsRpcRows(input: unknown): readonly ValidatedSearchNearbyListingsRpcRow[] {
  if (!Array.isArray(input)) throw new TypeError('RPC data must be an array');
  const identifiers = new Set<string>();
  const result: ValidatedSearchNearbyListingsRpcRow[] = [];
  for (const value of input) {
    const row = parseRow(value);
    // UUID hex is case-insensitive; preserve the original spelling in results.
    const key = row.listing_id.toLowerCase();
    if (identifiers.has(key)) throw new RangeError('RPC listing_id values must be unique');
    identifiers.add(key);
    result.push(row);
  }
  return result;
}
