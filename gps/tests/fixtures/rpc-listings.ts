import type { ValidatedSearchNearbyListingsRpcRow } from '../../rpc/types.ts';

/** Invented public map points and UUIDs. No actual listings or tenant data. */
export const RPC_LISTINGS: readonly ValidatedSearchNearbyListingsRpcRow[] = [
  {
    listing_id: 'aaaaaaaa-0000-4000-8000-000000000001',
    property_id: 'bbbbbbbb-0000-4000-8000-000000000001',
    title: 'Synthetic Imus rental',
    asking_rent_monthly: '12345.678901234567890123456789',
    property_type: 'synthetic-apartment',
    city: 'Imus',
    barangay: null,
    available_from: '2028-02-29',
    public_latitude: 14.43,
    public_longitude: 120.94,
    distance_meters: '102.12345678901234567890123456789',
  },
  {
    listing_id: 'aaaaaaaa-0000-4000-8000-000000000002',
    property_id: 'bbbbbbbb-0000-4000-8000-000000000001',
    title: null,
    asking_rent_monthly: 15000,
    property_type: null,
    city: 'Dasmariñas',
    barangay: 'Synthetic public area',
    available_from: null,
    public_latitude: 14.33,
    public_longitude: 120.94,
    distance_meters: 2300.5,
  },
];
