import { test } from 'node:test';
import assert from 'node:assert/strict';
import { crc32 as nativeCrc } from 'node:zlib';
import { crc32, StoredZip, writeSessionZip, type ExportSource } from '../src/exportSession';
import { makeSession, type Session } from '../src/domain';
import { CaptureRepository } from '../src/repository';
import { SessionService } from '../src/sessionService';
import { context, deferred, MemoryFiles } from './helpers';

const content = Uint8Array.from([255, 216, 12, 34, 56, 78, 255, 217]);
function complete(horizontal = false): Session {
  const session = makeSession(30, 'export-test', context.requestedAt);
  session.status = 'complete'; session.revision = 1;
  if (!horizontal) { delete session.captureMode; delete session.sweepDegrees; }
  session.targets = (horizontal ? session.targets : session.targets.slice(0, 2)).map((target, i) => ({ ...target, photo: {
    id: `photo-export-${i}`, filename: `photo-export-${i}.jpg`, width: 3000, height: 4000,
    ...context, savedAt: context.requestedAt, direction: target.direction,
    targetYaw: target.yaw, targetElevation: target.elevation, revision: 1,
  } }));
  return session;
}
const source: ExportSource = {
  async inspect() { return { bytes: content.length, width: 3000, height: 4000 }; },
  async *chunks() { yield content.slice(0, 3); yield content.slice(3); },
};
async function pack(session = complete(), input = source, available = 100_000_000) {
  const chunks: Uint8Array[] = [];
  const manifest = await writeSessionZip(session, input, name => name, async data => { chunks.push(data); }, available);
  return { archive: Buffer.concat(chunks), manifest };
}
// Independent central-directory reader verifies STORE entries, descriptors and CRCs.
function unpack(archive: Buffer) {
  const end = archive.length - 22;
  assert.equal(archive.readUInt32LE(end), 0x06054b50);
  let position = archive.readUInt32LE(end + 16);
  const entries = new Map<string, Buffer>();
  for (let i = 0; i < archive.readUInt16LE(end + 10); i++) {
    assert.equal(archive.readUInt32LE(position), 0x02014b50);
    const length = archive.readUInt16LE(position + 28), size = archive.readUInt32LE(position + 24);
    const offset = archive.readUInt32LE(position + 42), name = archive.subarray(position + 46, position + 46 + length).toString();
    assert.equal(archive.readUInt32LE(offset), 0x04034b50);
    assert.equal(archive.readUInt16LE(offset + 8), 0);
    const start = offset + 30 + archive.readUInt16LE(offset + 26);
    const data = archive.subarray(start, start + size);
    assert.equal(nativeCrc(data), archive.readUInt32LE(position + 16));
    assert.equal(archive.readUInt32LE(start + size), 0x08074b50);
    entries.set(name, data);
    position += 46 + length;
  }
  return entries;
}
test('streaming CRC32 agrees with independent native implementation', () => {
  assert.equal(crc32(content), nativeCrc(content));
  assert.equal(crc32(content.slice(3), crc32(content.slice(0, 3))), nativeCrc(content));
});
test('ZIP preserves byte-identical originals, target order, dimensions and metadata', async () => {
  const { archive, manifest } = await pack();
  const entries = unpack(archive);
  assert.deepEqual([...entries.keys()], [...manifest.photos.map(p => p.path), 'manifest.json']);
  for (const photo of manifest.photos) assert.deepEqual(entries.get(photo.path), Buffer.from(content));
  assert.deepEqual(JSON.parse(entries.get('manifest.json')!.toString()).session, complete());
  assert.deepEqual(manifest.photos.map(p => p.order), [1, 2]);
  assert.equal(manifest.photos[0]!.width, 3000);
  assert.equal(manifest.photos[0]!.orientation, null);
});
test('incomplete capture sets cannot export', async () => {
  const session = complete(); session.targets[0]!.photo = null;
  await assert.rejects(pack(session), /complete capture/);
});
test('missing or decoder-failed sources identify the affected photograph', async () => {
  await assert.rejects(pack(complete(), { ...source, inspect: async () => { throw new Error('decode failed'); } }), /Photo 1.*missing or unreadable/);
});
test('dimension mismatch fails before packing', async () => {
  await assert.rejects(pack(complete(), { ...source, inspect: async () => ({ bytes: 8, width: 4, height: 5 }) }), /dimensions/);
});
test('insufficient disk space is reported without deleting originals', async () => {
  await assert.rejects(pack(complete(), source, 1), /free storage/);
});
test('short source reads fail instead of producing a successful archive', async () => {
  await assert.rejects(pack(complete(), { ...source, async *chunks() { yield content.slice(0, 4); } }), /Incomplete read/);
});
test('write failures propagate and leave the session unchanged', async () => {
  const session = complete(), before = JSON.stringify(session);
  await assert.rejects(writeSessionZip(session, source, name => name, async () => { throw new Error('Disk full'); }, 100_000_000), /Disk full/);
  assert.equal(JSON.stringify(session), before);
});
test('unsafe ZIP entry names are rejected', async () => {
  for (const name of ['../photo.jpg', '/photo.jpg', 'C:/photo.jpg', 'images/../../photo.jpg']) {
    await assert.rejects(new StoredZip(async () => {}).add(name, source.chunks('')), /Invalid ZIP/);
  }
});
test('duplicate ZIP entry names are rejected', async () => {
  const zip = new StoredZip(async () => {});
  await zip.add('photo.jpg', source.chunks(''));
  await assert.rejects(zip.add('photo.jpg', source.chunks('')), /Invalid ZIP/);
});
test('export locks retakes and deletion until the transfer action settles', async () => {
  const files = new MemoryFiles(), repository = new CaptureRepository(files);
  await repository.save(complete());
  // Restore checks existence, so supply both original files.
  for (const target of complete().targets) files.files.set(`export-test/${target.photo!.filename}`, 'original');
  const service = new SessionService(repository);
  await service.initialize();
  const pending = deferred<string>();
  const exporting = service.exportSet(async (_, update) => { update('Packing'); return pending.promise; });
  assert.equal(service.getSnapshot().busy, true);
  assert.equal(await service.discard(), false);
  assert.equal(await service.resume(), false);
  pending.resolve('Transfer sheet closed; verify delivery');
  assert.equal(await exporting, true);
  assert.equal(service.getSnapshot().busy, false);
  assert.equal(service.getSnapshot().session?.status, 'complete');
});

test('horizontal export retains sweep intent, original bytes and all level targets', async () => {
  const {archive, manifest} = await pack(complete(true));
  assert.equal(manifest.session.captureMode, 'horizontal');
  assert.equal(manifest.session.sweepDegrees, 150);
  assert.equal(manifest.photos.length, 6);
  assert.ok(manifest.photos.every(p => p.direction === 'horizontal' && p.targetElevation === 0));
  for (const p of manifest.photos) assert.deepEqual(unpack(archive).get(p.path), Buffer.from(content));
});
