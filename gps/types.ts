/** Geographic degrees; callers must use public listing locations only. */
export interface Coordinates {
  readonly latitude: number;
  readonly longitude: number;
}

export type RadiusKm = 1 | 3 | 5;

export interface Pagination {
  readonly limit: number;
  readonly offset: number;
}

export interface SearchOptions extends Coordinates {
  readonly radiusKm?: RadiusKm;
  readonly limit?: number;
  readonly offset?: number;
}

export interface ValidatedSearchOptions extends Coordinates, Pagination {
  readonly radiusKm: RadiusKm;
}

/** Input records represent already eligible listings; eligibility is not checked here. */
export interface RentalListing {
  readonly listing_id: string;
  readonly property_id: string;
  readonly public_location: Coordinates;
}

export interface NearbyListing extends RentalListing {
  readonly distanceMeters: number;
}
