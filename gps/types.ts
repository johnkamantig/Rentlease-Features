/** Geographic degrees; callers must use public listing locations only. */
export interface Coordinates {
  readonly latitude: number;
  readonly longitude: number;
}

export type RadiusKm = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20;

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
