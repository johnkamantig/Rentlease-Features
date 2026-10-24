/** Simulation-only entry point. Authoritative searches use the production RPC. */
export type { RentalListing, NearbyListing, SearchOptions } from './types.ts';
export { searchNearbyListings } from './proximity.ts';
