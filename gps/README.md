# RentLease GPS utilities and offline RPC adapters

An isolated TypeScript package for shared GPS validation, pure production RPC
data adapters, and local rental proximity simulations. No runtime dependencies,
network calls, credentials, or platform APIs are used by the public utilities.
The Python ML service is unrelated to this package. Production searching remains
the responsibility of the existing PostGIS RPC.

## Run locally in VS Code

Use Node 24.12 or later within the Node 24 release line. From a PowerShell terminal
at the repository root:

```powershell
Set-Location gps
npm.cmd ci --cache .npm-cache --ignore-scripts --no-audit --no-fund --update-notifier=false
npm.cmd run typecheck --cache .npm-cache
npm.cmd run build --cache .npm-cache
npm.cmd test --cache .npm-cache
npm.cmd pack --dry-run --offline --cache .npm-cache --update-notifier=false
```

After installation, all checks work offline. `npm.cmd run check --cache .npm-cache`
runs type-checking and tests; `pretest` builds automatically. `prepack` also builds
before the package inventory is checked. No publishing or live requests occur.
The local cache, dependencies, generated output, and temporary consumer projects
stay inside `gps/` and are ignored. On other shells, use `npm` instead of `npm.cmd`.

Node runs the tests directly from TypeScript using its built-in test runner and
type stripping. The only development dependencies are TypeScript and Node 24 type
definitions (with transitive development-only `undici-types`). The build emits
ESM JavaScript and declarations in `dist/`. The root `tsconfig.json` checks
public utilities with only ECMAScript library types and no platform ambient
types; `tests/tsconfig.json` separately checks tests with Node types enabled.

## Package entry points

| Import | Purpose |
| --- | --- |
| `@rentlease/gps-local` | Shared validation, types, and approximate distance utilities |
| `@rentlease/gps-local/rpc` | Exact RPC parameter mapping, response parsing, and result mapping |
| `@rentlease/gps-local/local` | Local simulations with already eligible mock listings |

The root entry no longer exports `searchNearbyListings`, `RentalListing`, or
`NearbyListing`: import these from `/local`. The RPC entry does not import the
local search implementation or Haversine calculation. Fixtures and Node tests are
never production exports.

## Shared and local API

In source, shared utilities are exported by `index.ts`, simulations by `local.ts`.
In a built package use the entry points above. Types use type-only exports.

```typescript
validateCoordinates(value: unknown): Coordinates
validateRadiusKm(value?: unknown): RadiusKm
validatePagination(limit?: unknown, offset?: unknown): Pagination
validateSearchOptions(value: unknown): ValidatedSearchOptions
haversineDistanceMeters(from: Coordinates, to: Coordinates): number
// Only from @rentlease/gps-local/local:
searchNearbyListings(
  listings: readonly RentalListing[],
  options: SearchOptions,
): NearbyListing[]
```

`EARTH_RADIUS_METERS` is also exported. The public data contracts are:

```typescript
interface Coordinates {
  readonly latitude: number;
  readonly longitude: number;
}
type RadiusKm = 1 | 3 | 5;
interface Pagination {
  readonly limit: number;
  readonly offset: number;
}
interface SearchOptions extends Coordinates {
  readonly radiusKm?: RadiusKm;
  readonly limit?: number;
  readonly offset?: number;
}
interface ValidatedSearchOptions extends Coordinates, Pagination {
  readonly radiusKm: RadiusKm;
}
interface RentalListing {
  readonly listing_id: string;
  readonly property_id: string;
  readonly public_location: Coordinates;
}
interface NearbyListing extends RentalListing {
  readonly distanceMeters: number;
}
```

### Validation and errors

- Latitude is inclusive from -90 to 90; longitude from -180 to 180.
- Missing coordinates, numeric strings, booleans, `null`, `NaN`, and infinities are
  rejected. Values are never coerced or wrapped into range.
- Radius accepts only 1, 3, or 5 kilometers; the default is 3.
- Limit is an integer from 1 to 50, default 20. Zero is invalid.
- Offset is an integer from 0 to 1000, default 0.
- Defaults apply to omitted or `undefined` optional values, never `null`.
- Malformed types or nonfinite numbers throw `TypeError`. Out-of-range numbers,
  unsupported radii, fractional pagination, and duplicate listing IDs throw
  `RangeError`. Error messages identify fields without echoing coordinates.
- Both identifiers must be nonempty strings. Identifiers are preserved without
  trimming or case normalization. Duplicate `listing_id` values are rejected;
  multiple listings may share a `property_id`.
- Every record is validated, including records outside the search radius or
  requested page. Invalid records cause the whole search to throw; they are not
  silently skipped. No partial results are returned.

### Distance, boundaries, ordering, and pagination

The Haversine calculation uses a spherical Earth radius of 6,371,008.8 meters.
It returns unrounded meters and clamps its intermediate value to [0, 1] to avoid
nonfinite results from floating-point error near antipodal points.

**Haversine is an approximation and may differ from PostGIS geography-based
distances. This package does not establish exact production parity.** Near
antipodal points have less numerical precision; this does not affect the intended
1/3/5 km local simulation scope. Equivalent pole/antimeridian representations can
produce negligible nonzero distances from floating-point arithmetic.

The radius is inclusive. Filtering compares unrounded distance against
`radiusKm * 1000 + 0.000001`. The explicit one-micrometer numerical tolerance
accommodates roundoff at a mathematically exact boundary; consequently a point up
to one micrometer outside the computed boundary can also qualify. Tests cover
the exact boundary, this tolerance, and nearby excluded points.

Results sort by ascending unrounded distance, then by `listing_id` using
case-sensitive JavaScript string ordering (UTF-16 code units), without locale
dependence. This is deterministic locally and does not assert equivalence to a
database collation. Only exactly equal calculated distances use the ID tie-break.
Offset and limit are applied after filtering and sorting. An exhausted offset
returns an empty array. Results retain unrounded distance values.

Functions never mutate inputs. Search returns new records and new coordinate
objects and copies only the documented fields. TypeScript `readonly` expresses
the input contract; output objects are not frozen at runtime. The local search is
O(n + m log m), where n is the input count and m the number of matches; it is not
a spatial index or a production search engine.

## Synthetic example

```typescript
import { searchNearbyListings } from '@rentlease/gps-local/local';

const matches = searchNearbyListings([
  {
    listing_id: 'synthetic-listing-1',
    property_id: 'synthetic-property-1',
    public_location: { latitude: 14.435, longitude: 120.94 },
  },
], { latitude: 14.43, longitude: 120.94 });

// Default radius 3 km, limit 20, offset 0; matches include distanceMeters.
```

Test fixtures use invented, rounded public map positions around Imus,
Dasmariñas, and Tagaytay. They are not real listings, tenant coordinates, private
addresses, or exact private property locations. The numeric coordinate validators
cannot establish whether supplied coordinates are public; callers must supply
appropriate public listing locations.

## Production RPC contract and adapter

The contract below is based on the supplied sanitized `RETURNS TABLE` signature
for `public.search_nearby_listings`. No database connection was used to obtain it.
All eleven documented fields must be present, even when a nullable value is null.

| SQL response field | SQL type | Adapter policy | Mapped field |
| --- | --- | --- | --- |
| `listing_id` | uuid | Required UUID-shaped string | `listingId` |
| `property_id` | uuid | Required UUID-shaped string | `propertyId` |
| `title` | text | String or null | `title` |
| `asking_rent_monthly` | numeric | Number, decimal string, or null | `askingRentMonthly` |
| `property_type` | text | String or null | `propertyType` |
| `city` | text | String or null | `city` |
| `barangay` | text | String or null | `barangay` |
| `available_from` | date | Valid `YYYY-MM-DD` string or null | `availableFrom` |
| `public_latitude` | double precision | Required finite latitude | `publicLocation.latitude` |
| `public_longitude` | double precision | Required finite longitude | `publicLocation.longitude` |
| `distance_meters` | numeric | Required nonnegative number or decimal string | `distanceMeters` |

`RETURNS TABLE` alone does not establish non-null guarantees. Accordingly,
`SearchNearbyListingsRpcRow` models SQL fields as nullable, while
`ValidatedSearchNearbyListingsRpcRow` narrows the required identifiers,
coordinates, and distance after runtime validation. This is an adapter policy,
not an assertion that the database declares those fields non-null.

Public RPC functions:

```typescript
toSearchNearbyListingsRpcParams(input: unknown): SearchNearbyListingsRpcParams
parseSearchNearbyListingsRpcRows(input: unknown): readonly ValidatedSearchNearbyListingsRpcRow[]
mapSearchNearbyListingsRpcResponse(input: unknown): readonly RpcNearbyListing[]
```

Public RPC types are `RpcNumeric`, `SearchNearbyListingsRpcParams`,
`SearchNearbyListingsRpcRow`, `ValidatedSearchNearbyListingsRpcRow`, and
`RpcNearbyListing`. Their complete definitions are in `rpc/types.ts`.

The parameter adapter calls the existing shared input validator, resolves defaults
to radius 3 / limit 20 / offset 0, and emits exactly these parameter names:

| Local field | RPC parameter |
| --- | --- |
| `latitude` | `p_latitude` |
| `longitude` | `p_longitude` |
| `radiusKm` | `p_radius_km` |
| `limit` | `p_limit` |
| `offset` | `p_offset` |

The response parser accepts a data array, not a client response envelope.
`[]` means an empty successful result; `null`, `{ data, error }`, and malformed
rows are rejected. Every record is validated before a result is returned; no
partial response or silent skipping is performed. Malformed field types throw
`TypeError`; negative distances, invalid calendar dates, and duplicate IDs throw
`RangeError`. Error messages identify fields without echoing response values.

UUIDs accept canonical 8-4-4-4-12 hexadecimal shape without a version restriction.
Their spelling is preserved, but duplicate listing IDs are compared
case-insensitively. Distinct listings can share a property ID.

`RpcNumeric` is `number | string`. Finite numeric numbers and decimal strings
are accepted; string grammar is `[+-]?(digits[.digits?] | .digits)[exponent?]`,
where an exponent is `e` or `E`, an optional sign, and digits. Whitespace, hex,
separators, `NaN`, and infinity spellings are rejected. Strings are never passed
through `Number`, rounded, or trimmed. Very large or tiny finite decimal strings
such as `1e9999` and `1e-9999` remain strings even though converting them to a
JavaScript number would overflow or underflow. Negative nonzero distances are
rejected by inspecting the coefficient, including values such as `-1e-99999`;
signed zero is accepted. Rent receives numeric validation but no eligibility or
pricing rules. This transport-tolerant string policy does not claim the live
client returns numeric strings.

Precision already lost by a JSON parser producing a JavaScript number cannot be
recovered here. Consumers must not casually coerce high-precision strings for
calculations. Apply any display formatting explicitly at the presentation layer.

Dates are Gregorian calendar strings in years 0001–9999, including leap-year
checks. No `Date` object or timezone conversion is used. PostgreSQL dates outside
that supported application range, including BC dates and infinity, are rejected.

The mapper returns new camelCase objects and copies only the documented fields.
It preserves incoming row order and every numeric value exactly as received. It
does not recalculate distances, filter by radius, sort by identifiers, or apply
pagination. Even unexpectedly ordered input is preserved; deciding how to handle
server contract violations belongs to the calling application. Outputs are
readonly at the type level, not frozen at runtime.

## Future frontend and Deno consumption

All public source files use standard ECMAScript operations and relative imports.
They contain no Node, Deno, browser, Expo, FastAPI, or Supabase client APIs.

For future frontend reuse, consume the built package via a local/workspace
dependency or a separately prepared local package archive. Build it before
consumption. The package remains private and has not been published. The exports
point to ESM `.js` files and `.d.ts` declarations, so consuming its built entry
points does not require enabling `.ts` import extensions in the frontend.
There is no CommonJS build. The package no longer imposes a Node engine range;
Node 24 is the tested local tooling environment, not a React Native runtime
dependency.

Keep the frontend's Expo TypeScript and Metro configuration. Do not copy this
package's `NodeNext` tooling config into it. Verify package-export resolution and
Metro's workspace visibility against the actual frontend setup when integration
is separately authorized. No frontend configuration was changed here.

Illustrative future imports (no network request):

```typescript
import { validateCoordinates } from '@rentlease/gps-local';
import {
  toSearchNearbyListingsRpcParams,
  mapSearchNearbyListingsRpcResponse,
} from '@rentlease/gps-local/rpc';
import type { RpcNearbyListing } from '@rentlease/gps-local/rpc';

// Values supplied by the caller, not acquired by this package:
declare const expoCoordinates: unknown;
declare const successfulRpcData: unknown;

const coordinates = validateCoordinates(expoCoordinates);
const params = toSearchNearbyListingsRpcParams({ ...coordinates, radiusKm: 3 });
const listings: readonly RpcNearbyListing[] =
  mapSearchNearbyListingsRpcResponse(successfulRpcData);
```

In MVVM, the ViewModel obtains coordinates from Expo Location and handles location
permission states. The repository/service layer uses the parameter adapter,
performs the RPC request, handles client errors, and then maps successful data.
This package has no transport dependency and does not handle tokens or sessions.

For future Deno integration, import `index.ts` or `rpc/index.ts` directly from a
vendored source checkout, preserving the relative source layout. Source imports
retain explicit `.ts` extensions. The npm distribution intentionally contains
only built JavaScript, declarations, README, and package metadata; source-based
Deno usage requires the source files from this repository, not the npm archive.
TypeScript's build rewrites relative imports to `.js` for the built artifacts.

No Expo, Metro, device, Deno, or Edge Function runtime was tested. Node execution
and TypeScript's Bundler resolution checks provide useful packaging evidence but
do not prove those environments' runtime compatibility.

`searchNearbyListings` remains simulation-only. Production searching continues
to use `public.search_nearby_listings`. Do not locally refilter or repaginate an
authoritative RPC page with Haversine. The RPC returns PostGIS distances and
server order, which the adapter preserves unchanged.

All input listings are assumed already eligible. This module does not implement
authentication, RLS, tenancy access, publication rules, availability enforcement,
Tier 1 verification, or public-location disclosure policy. The existing
`public.tenancies` dependency is left to the backend developer. Device location
permission handling and privacy-conscious location lifecycle management belong
to the eventual frontend integration, not these utilities.

No frontend integration, Supabase connection, deployment, or ML service change is
included. The next phase requires separate authorization to verify consumption in
the actual frontend and later run live contract checks after the backend
permission dependency is resolved.

## Verification and distribution boundaries

The suite retains the original 55 GPS tests and adds 26 offline RPC contract tests
plus 7 packaging tests (88 total). Synthetic data covers nullable fields, dates,
UUIDs, public coordinates, numeric precision, duplicates, mapping, immutability,
and preservation of server order and distance values.

Packaging tests run `npm pack --dry-run` offline and compare its inventory with an
exact allowlist. They copy only those listed files into temporary consumer
projects inside `.test-artifacts/`, run all three JavaScript entry points, and
check declarations with TypeScript in both NodeNext and Bundler modes, with no
platform ambient types. These consumers have no installed development packages.
The temporary consumers are removed after each check. Further tests verify `.js`
import resolution and that the RPC runtime graph excludes local search and tests.

The distribution contains exactly 22 files: ten JavaScript modules, ten matching
declarations, `package.json`, and `README.md`. Tests, fixtures, source TypeScript,
configuration, dependencies, caches, and temporary projects are excluded. The
package metadata references development scripts, but consumers do not need the
omitted development files to import its built exports.

## Layout

```text
gps/
├── .gitignore
├── README.md
├── package.json
├── package-lock.json
├── tsconfig.json
├── tsconfig.build.json
├── index.ts
├── local.ts
├── types.ts
├── validation.ts
├── distance.ts
├── proximity.ts
├── rpc/
│   ├── index.ts
│   ├── types.ts
│   ├── validation.ts
│   └── adapter.ts
├── dist/                         # Generated and ignored
│   ├── index.js / index.d.ts
│   ├── local.js / local.d.ts
│   ├── types.js / types.d.ts
│   ├── validation.js / validation.d.ts
│   ├── distance.js / distance.d.ts
│   ├── proximity.js / proximity.d.ts
│   └── rpc/
│       ├── index.js / index.d.ts
│       ├── types.js / types.d.ts
│       ├── validation.js / validation.d.ts
│       └── adapter.js / adapter.d.ts
└── tests/
    ├── tsconfig.json
    ├── validation.test.ts
    ├── distance.test.ts
    ├── proximity.test.ts
    ├── rpc-contract.test.ts
    ├── package.test.ts
    └── fixtures/
        ├── mock-properties.ts
        └── rpc-listings.ts
```

Ignored local directories also include `node_modules/`, `.npm-cache/`, and
`.test-artifacts/`. All build and test artifacts stay inside this package.
