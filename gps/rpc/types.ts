import type { Coordinates, RadiusKm } from '../types.ts';

/** Numbers or validated decimal strings, preserved exactly as supplied. */
export type RpcNumeric = number | string;

export interface SearchNearbyListingsRpcParams {
  readonly p_latitude: number;
  readonly p_longitude: number;
  readonly p_radius_km: RadiusKm;
  readonly p_limit: number;
  readonly p_offset: number;
}

/** SQL return fields; RETURNS TABLE alone supplies no non-null guarantees. */
export interface SearchNearbyListingsRpcRow {
  readonly listing_id: string | null;
  readonly property_id: string | null;
  readonly title: string | null;
  readonly asking_rent_monthly: RpcNumeric | null;
  readonly property_type: string | null;
  readonly city: string | null;
  readonly barangay: string | null;
  readonly available_from: string | null;
  readonly public_latitude: number | null;
  readonly public_longitude: number | null;
  readonly distance_meters: RpcNumeric | null;
}

/** Adapter policy: these fields must be usable, regardless of SQL nullability. */
export interface ValidatedSearchNearbyListingsRpcRow extends SearchNearbyListingsRpcRow {
  readonly listing_id: string;
  readonly property_id: string;
  readonly public_latitude: number;
  readonly public_longitude: number;
  readonly distance_meters: RpcNumeric;
}

/** Authoritative RPC values; deliberately separate from the local NearbyListing. */
export interface RpcNearbyListing {
  readonly listingId: string;
  readonly propertyId: string;
  readonly title: string | null;
  readonly askingRentMonthly: RpcNumeric | null;
  readonly propertyType: string | null;
  readonly city: string | null;
  readonly barangay: string | null;
  readonly availableFrom: string | null;
  readonly publicLocation: Coordinates;
  readonly distanceMeters: RpcNumeric;
}
