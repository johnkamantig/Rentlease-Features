import { validateSearchOptions } from '../validation.ts';
import type { RpcNearbyListing, SearchNearbyListingsRpcParams } from './types.ts';
import { parseSearchNearbyListingsRpcRows } from './validation.ts';

/** Resolve the local input defaults and map to exact RPC parameter names. */
export function toSearchNearbyListingsRpcParams(input: unknown): SearchNearbyListingsRpcParams {
  const options = validateSearchOptions(input);
  return {
    p_latitude: options.latitude,
    p_longitude: options.longitude,
    p_radius_km: options.radiusKm,
    p_limit: options.limit,
    p_offset: options.offset,
  };
}

/** Map authoritative data only: no request, distance recalculation, or local search. */
export function mapSearchNearbyListingsRpcResponse(input: unknown): readonly RpcNearbyListing[] {
  return parseSearchNearbyListingsRpcRows(input).map(row => ({
    listingId: row.listing_id,
    propertyId: row.property_id,
    title: row.title,
    askingRentMonthly: row.asking_rent_monthly,
    propertyType: row.property_type,
    city: row.city,
    barangay: row.barangay,
    availableFrom: row.available_from,
    publicLocation: { latitude: row.public_latitude, longitude: row.public_longitude },
    distanceMeters: row.distance_meters,
  }));
}
