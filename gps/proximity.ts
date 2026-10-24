import { haversineDistanceMeters } from './distance.ts';
import type { NearbyListing, RentalListing, SearchOptions } from './types.ts';
import { validateCoordinates, validateSearchOptions } from './validation.ts';

/** One micrometer accommodates roundoff at an inclusive spherical boundary. */
const BOUNDARY_TOLERANCE_METERS = 0.000001;

function identifier(value: unknown, name: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(`${name} must be a nonempty string`);
  }
  return value;
}

/** Local simulation: validate all records, filter, sort by distance/ID, then paginate. */
export function searchNearbyListings(
  listings: readonly RentalListing[],
  options: SearchOptions,
): NearbyListing[] {
  const search = validateSearchOptions(options);
  if (!Array.isArray(listings)) {
    throw new TypeError('listings must be an array');
  }
  const seen = new Set<string>();
  const matches: NearbyListing[] = [];
  for (const candidate of listings) {
    if (typeof candidate !== 'object' || candidate === null || Array.isArray(candidate)) {
      throw new TypeError('each listing must be an object');
    }
    const listingId = identifier(candidate.listing_id, 'listing_id');
    const propertyId = identifier(candidate.property_id, 'property_id');
    if (seen.has(listingId)) {
      throw new RangeError('listing_id values must be unique');
    }
    seen.add(listingId);
    const location = validateCoordinates(candidate.public_location);
    const distanceMeters = haversineDistanceMeters(search, location);
    if (distanceMeters <= search.radiusKm * 1000 + BOUNDARY_TOLERANCE_METERS) {
      matches.push({
        listing_id: listingId,
        property_id: propertyId,
        public_location: location,
        distanceMeters,
      });
    }
  }
  matches.sort((a, b) => a.distanceMeters - b.distanceMeters
    || (a.listing_id < b.listing_id ? -1 : a.listing_id > b.listing_id ? 1 : 0));
  return matches.slice(search.offset, search.offset + search.limit);
}
