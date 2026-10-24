import type { Coordinates, Pagination, RadiusKm, ValidatedSearchOptions } from './types.ts';

function record(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new TypeError(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function boundedNumber(value: unknown, name: string, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new TypeError(`${name} must be a finite number`);
  }
  if (value < min || value > max) {
    throw new RangeError(`${name} must be between ${min} and ${max}`);
  }
  return value;
}

/** Validate without coercion and return a fresh coordinate object. */
export function validateCoordinates(value: unknown): Coordinates {
  const coordinates = record(value, 'coordinates');
  return {
    latitude: boundedNumber(coordinates.latitude, 'latitude', -90, 90),
    longitude: boundedNumber(coordinates.longitude, 'longitude', -180, 180),
  };
}

/** Omitted/undefined radius defaults to 3 km; null and numeric strings are invalid. */
export function validateRadiusKm(value: unknown = 3): RadiusKm {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new TypeError('radiusKm must be a finite number');
  }
  if (value !== 1 && value !== 3 && value !== 5) {
    throw new RangeError('radiusKm must be 1, 3, or 5');
  }
  return value;
}

export function validatePagination(limit: unknown = 20, offset: unknown = 0): Pagination {
  const checkedLimit = boundedNumber(limit, 'limit', 1, 50);
  const checkedOffset = boundedNumber(offset, 'offset', 0, 1000);
  if (!Number.isInteger(checkedLimit) || !Number.isInteger(checkedOffset)) {
    throw new RangeError('limit and offset must be integers');
  }
  return { limit: checkedLimit, offset: checkedOffset };
}

export function validateSearchOptions(value: unknown): ValidatedSearchOptions {
  const options = record(value, 'search options');
  return {
    ...validateCoordinates(options),
    radiusKm: validateRadiusKm(options.radiusKm),
    ...validatePagination(options.limit, options.offset),
  };
}
