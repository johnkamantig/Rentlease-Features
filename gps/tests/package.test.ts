import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const artifacts = join(root, '.test-artifacts');
const modules = ['index', 'local', 'types', 'validation', 'distance', 'proximity', 'rpc/index', 'rpc/types', 'rpc/validation', 'rpc/adapter'];
const expectedFiles = ['package.json', 'README.md', ...modules.flatMap(name => [`dist/${name}.js`, `dist/${name}.d.ts`])].sort();
let inventory: readonly string[] | undefined;

function packageFiles(): readonly string[] {
  if (inventory) return inventory;
  const npmCli = process.env.npm_execpath ?? join(dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js');
  const output = execFileSync(process.execPath, [npmCli, 'pack', '--dry-run', '--json', '--ignore-scripts', '--offline', '--cache', join(root, '.npm-cache'), '--update-notifier=false'], {
    cwd: root, encoding: 'utf8', maxBuffer: 1024 * 1024,
  });
  const pack = JSON.parse(output) as { files: { path: string }[] }[];
  assert.equal(pack.length, 1);
  inventory = pack[0]!.files.map(file => file.path).sort();
  return inventory;
}

function contained(base: string, target: string): boolean {
  const path = relative(resolve(base), resolve(target));
  return path !== '' && path !== '..' && !path.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`) && !isAbsolute(path);
}

function withConsumer(check: (directory: string) => void): void {
  mkdirSync(artifacts, { recursive: true });
  const directory = mkdtempSync(join(artifacts, 'consumer-'));
  assert.ok(contained(artifacts, directory));
  try {
    const packageRoot = join(directory, 'node_modules/@rentlease/gps-local');
    for (const file of packageFiles()) {
      const source = join(root, file);
      const destination = join(packageRoot, file);
      assert.ok(contained(root, source) && contained(packageRoot, destination));
      mkdirSync(dirname(destination), { recursive: true });
      copyFileSync(source, destination);
    }
    writeFileSync(join(directory, 'package.json'), JSON.stringify({ name: 'gps-offline-consumer', private: true, type: 'module' }));
    check(directory);
  } finally {
    // Verify the resolved target before recursively removing our temporary files.
    assert.ok(contained(artifacts, directory));
    rmSync(directory, { recursive: true, force: true });
  }
}

test('npm pack dry-run contains exactly the intended distribution files', () => {
  assert.deepEqual(packageFiles(), expectedFiles);
});

test('distribution is private ESM without runtime dependencies or platform engine restrictions', () => {
  const metadata = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
  assert.equal(metadata.private, true);
  assert.equal(metadata.type, 'module');
  assert.equal(metadata.sideEffects, false);
  assert.deepEqual(metadata.dependencies ?? {}, {});
  assert.equal(metadata.engines, undefined);
  assert.deepEqual(Object.keys(metadata.exports).sort(), ['.', './local', './rpc']);
});

test('packed JavaScript entry points import and execute without source or development dependencies', () => {
  withConsumer(directory => {
    const script = join(directory, 'consumer.mjs');
    writeFileSync(script, `
      import assert from 'node:assert/strict';
      import * as core from '@rentlease/gps-local';
      import * as rpc from '@rentlease/gps-local/rpc';
      import * as local from '@rentlease/gps-local/local';
      assert.deepEqual(Object.keys(core).sort(), ['EARTH_RADIUS_METERS', 'haversineDistanceMeters', 'validateCoordinates', 'validatePagination', 'validateRadiusKm', 'validateSearchOptions'].sort());
      assert.deepEqual(Object.keys(rpc).sort(), ['mapSearchNearbyListingsRpcResponse', 'parseSearchNearbyListingsRpcRows', 'toSearchNearbyListingsRpcParams'].sort());
      assert.deepEqual(Object.keys(local), ['searchNearbyListings']);
      assert.equal(core.haversineDistanceMeters({latitude:0, longitude:0}, {latitude:0, longitude:0}), 0);
      assert.equal(rpc.toSearchNearbyListingsRpcParams({latitude:0, longitude:0}).p_radius_km, 3);
      assert.deepEqual(rpc.mapSearchNearbyListingsRpcResponse([]), []);
      assert.deepEqual(local.searchNearbyListings([], {latitude:0, longitude:0}), []);
    `);
    execFileSync(process.execPath, [script], { cwd: directory, encoding: 'utf8' });
  });
});

const consumerTypes = `
  import { validateCoordinates, validateRadiusKm, validatePagination, validateSearchOptions, haversineDistanceMeters, EARTH_RADIUS_METERS } from '@rentlease/gps-local';
  import type { Coordinates, RadiusKm, Pagination, SearchOptions, ValidatedSearchOptions } from '@rentlease/gps-local';
  import { toSearchNearbyListingsRpcParams, parseSearchNearbyListingsRpcRows, mapSearchNearbyListingsRpcResponse } from '@rentlease/gps-local/rpc';
  import type { RpcNumeric, RpcNearbyListing, SearchNearbyListingsRpcParams, SearchNearbyListingsRpcRow, ValidatedSearchNearbyListingsRpcRow } from '@rentlease/gps-local/rpc';
  import { searchNearbyListings } from '@rentlease/gps-local/local';
  import type { RentalListing, NearbyListing } from '@rentlease/gps-local/local';
  declare const wire: unknown;
  const point: Coordinates = validateCoordinates(wire);
  const radius: RadiusKm = validateRadiusKm();
  const pagination: Pagination = validatePagination();
  const options: SearchOptions = { ...point, ...pagination, radiusKm: radius };
  const checked: ValidatedSearchOptions = validateSearchOptions(options);
  const params: SearchNearbyListingsRpcParams = toSearchNearbyListingsRpcParams(checked);
  const rows: readonly ValidatedSearchNearbyListingsRpcRow[] = parseSearchNearbyListingsRpcRows(wire);
  const raw: readonly SearchNearbyListingsRpcRow[] = rows;
  const mapped: readonly RpcNearbyListing[] = mapSearchNearbyListingsRpcResponse(wire);
  const distance: RpcNumeric = mapped[0]!.distanceMeters;
  const spherical: number = haversineDistanceMeters(point, point) + EARTH_RADIUS_METERS;
  const listings: readonly RentalListing[] = [];
  const local: NearbyListing[] = searchNearbyListings(listings, options);
  // @ts-expect-error unsupported radius
  const invalidRadius: RadiusKm = 2;
  // @ts-expect-error authoritative numeric may be a high precision string
  const lossyDistance: number = mapped[0]!.distanceMeters;
  // @ts-expect-error simulations must be imported from /local
  import { searchNearbyListings as wrongEntry } from '@rentlease/gps-local';
`;

for (const mode of ['NodeNext', 'Bundler'] as const) {
  test(`packed declarations resolve in ${mode} mode with no platform ambient types`, () => {
    withConsumer(directory => {
      const file = join(directory, 'consumer.mts');
      writeFileSync(file, consumerTypes);
      const program = ts.createProgram([file], {
        noEmit: true, strict: true, types: [], lib: ['lib.es2022.d.ts'],
        target: ts.ScriptTarget.ES2022,
        module: mode === 'NodeNext' ? ts.ModuleKind.NodeNext : ts.ModuleKind.ESNext,
        moduleResolution: mode === 'NodeNext' ? ts.ModuleResolutionKind.NodeNext : ts.ModuleResolutionKind.Bundler,
        skipLibCheck: false,
      });
      const errors = ts.getPreEmitDiagnostics(program);
      assert.equal(errors.length, 0, ts.formatDiagnosticsWithColorAndContext(errors, {
        getCanonicalFileName: fileName => fileName, getCurrentDirectory: () => directory, getNewLine: () => '\n',
      }));
      const packageRoot = resolve(directory, 'node_modules/@rentlease/gps-local');
      for (const entry of ['index', 'rpc/index', 'local']) {
        assert.ok(program.getSourceFiles().some(source => resolve(source.fileName) === join(packageRoot, `dist/${entry}.d.ts`)), `${entry} declaration was not resolved from packaged files`);
      }
    });
  });
}

test('built imports resolve to JavaScript and contain no external runtime dependencies', () => {
  for (const file of packageFiles().filter(file => file.endsWith('.js'))) {
    const text = readFileSync(join(root, file), 'utf8');
    for (const match of text.matchAll(/(?:from\s*|import\s*)['"]([^'"]+)['"]/g)) {
      const specifier = match[1]!;
      assert.ok(specifier.startsWith('.') && specifier.endsWith('.js'), `${file}: ${specifier}`);
      const target = resolve(root, dirname(file), specifier);
      assert.ok(contained(join(root, 'dist'), target));
      assert.ok(packageFiles().includes(relative(root, target).replaceAll('\\', '/')));
    }
  }
});

test('RPC runtime import graph excludes local search, Haversine, fixtures, and tests', () => {
  const visited = new Set<string>();
  function visit(file: string): void {
    if (visited.has(file)) return;
    visited.add(file);
    const text = readFileSync(join(root, file), 'utf8');
    for (const match of text.matchAll(/from\s*['"]([^'"]+)['"]/g)) {
      const target = relative(root, resolve(root, dirname(file), match[1]!)).replaceAll('\\', '/');
      visit(target);
    }
  }
  visit('dist/rpc/index.js');
  assert.deepEqual([...visited].sort(), ['dist/rpc/adapter.js', 'dist/rpc/index.js', 'dist/rpc/validation.js', 'dist/validation.js']);
});
