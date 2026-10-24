import type { Coordinates } from './types.ts';
import { validateCoordinates } from './validation.ts';

/** Mean spherical Earth radius used consistently by the local approximation. */
export const EARTH_RADIUS_METERS = 6_371_008.8;

/** Great-circle distance in meters, not authoritative PostGIS geography distance. */
export function haversineDistanceMeters(from: Coordinates, to: Coordinates): number {
  const start = validateCoordinates(from);
  const end = validateCoordinates(to);
  const radians = Math.PI / 180;
  const latitudeDelta = (end.latitude - start.latitude) * radians;
  const longitudeDelta = (end.longitude - start.longitude) * radians;
  const a = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(start.latitude * radians) * Math.cos(end.latitude * radians)
    * Math.sin(longitudeDelta / 2) ** 2;
  // Floating-point error can push antipodal calculations just beyond [0, 1].
  const clamped = Math.max(0, Math.min(1, a));
  return 2 * EARTH_RADIUS_METERS * Math.atan2(Math.sqrt(clamped), Math.sqrt(1 - clamped));
}
