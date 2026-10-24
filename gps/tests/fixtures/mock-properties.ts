import type { Coordinates, RentalListing } from '../../types.ts';

// Rounded, invented public map positions, not actual rentals or tenant locations.
export const SYNTHETIC_TENANT_LOCATIONS = {
  imus: { latitude: 14.43, longitude: 120.94 },
  dasmarinas: { latitude: 14.33, longitude: 120.94 },
  tagaytay: { latitude: 14.12, longitude: 120.96 },
} as const satisfies Record<string, Coordinates>;

// All records are treated as eligible. Shared property IDs are intentional.
export const MOCK_LISTINGS: readonly RentalListing[] = [
  { listing_id: 'imus-far', property_id: 'mock-property-2', public_location: { latitude: 14.45, longitude: 120.94 } },
  { listing_id: 'tagaytay-near', property_id: 'mock-property-5', public_location: { latitude: 14.125, longitude: 120.96 } },
  { listing_id: 'imus-near', property_id: 'mock-property-1', public_location: { latitude: 14.435, longitude: 120.94 } },
  { listing_id: 'dasmarinas-near', property_id: 'mock-property-3', public_location: { latitude: 14.335, longitude: 120.94 } },
  { listing_id: 'imus-middle', property_id: 'mock-property-1', public_location: { latitude: 14.44, longitude: 120.94 } },
  { listing_id: 'dasmarinas-far', property_id: 'mock-property-4', public_location: { latitude: 14.35, longitude: 120.94 } },
  { listing_id: 'tagaytay-far', property_id: 'mock-property-6', public_location: { latitude: 14.14, longitude: 120.96 } },
];
